"""
Runtime State Store — CortexPrime
====================================
Redis-backed canonical store for execution state.

Redis is the single source of truth.  In-memory dicts are a write-through
cache only — on any cache miss the store always queries Redis first before
returning None.  After a backend restart all active executions are
immediately recoverable by scanning Redis.

Key Schema (prefix ``cx:rt:``)
-------------------------------
cx:rt:exec:{execution_id}   HASH   Rich execution record (see _EXEC_FIELDS)
cx:rt:active                ZSET   member=execution_id, score=started_at_epoch
cx:rt:hist:{execution_id}   HASH   Completed execution record (longer TTL)
cx:rt:history               ZSET   member=execution_id, score=completed_at_epoch
cx:rt:recovered             STRING Counter of sessions recovered on startup

TTLs
----
Active execution record  : 86400 s (24 h)    — refreshed on every update
Completed/failed history : 604800 s (7 days) — permanent audit trail
Active ZSET entry        : pruned when execution completes / TTL auto-expires
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key helpers (all under cx:rt: to avoid collision with legacy cx:exec: keys)
# ---------------------------------------------------------------------------

_PFX         = "cx:rt:"
_KEY_EXEC    = "cx:rt:exec:{eid}"        # HASH
_KEY_ACTIVE  = "cx:rt:active"            # ZSET — score=started_at_epoch
_KEY_HIST    = "cx:rt:hist:{eid}"        # HASH
_KEY_HISTORY = "cx:rt:history"           # ZSET — score=completed_at_epoch
_KEY_RCVD    = "cx:rt:recovered"         # STRING counter


def _exec_key(eid: str) -> str:
    return _KEY_EXEC.format(eid=eid)


def _hist_key(eid: str) -> str:
    return _KEY_HIST.format(eid=eid)


# ---------------------------------------------------------------------------
# TTLs
# ---------------------------------------------------------------------------

_TTL_ACTIVE  = 86_400     # 24 h
_TTL_HISTORY = 604_800    # 7 days


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_epoch() -> float:
    return time.time()


def _duration(started_at: str, ended_at: str) -> float:
    """Return elapsed seconds between two ISO timestamps."""
    try:
        t0 = datetime.fromisoformat(started_at)
        t1 = datetime.fromisoformat(ended_at)
        return max(0.0, (t1 - t0).total_seconds())
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# RuntimeStateStore
# ---------------------------------------------------------------------------

class RuntimeStateStore:
    """
    Canonical Redis-backed store for execution lifecycle management.

    Every write goes to Redis first, then updates the local write-through
    cache.  Every read checks the local cache first; on a miss it
    transparently loads from Redis.  This means state survives:

    - Backend restart (cold start)
    - Docker restart
    - WebSocket reconnect

    All public methods are async and may be called from any FastAPI
    route handler or background task.
    """

    def __init__(self) -> None:
        # Write-through cache: execution_id → record dict
        self._cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Redis access
    # ------------------------------------------------------------------

    async def _redis(self) -> Optional[Any]:
        """Return a live Redis client, or None if unavailable."""
        try:
            from backend.infrastructure.redis.connection import redis_connection
            if await redis_connection.ensure_connected():
                return redis_connection.client
        except Exception as exc:
            log.debug("RuntimeStateStore: Redis unavailable: %s", exc)
        return None

    # ------------------------------------------------------------------
    # Start an execution
    # ------------------------------------------------------------------

    async def start(
        self,
        execution_id: str,
        objective:    str,
        user_id:      str = "system",
        session_id:   Optional[str] = None,
        mission_type: str = "general",
        priority:     int = 5,
    ) -> Dict[str, Any]:
        """
        Register a new execution as active.

        Adds:
        - A HASH record at ``cx:rt:exec:{execution_id}``
        - The execution_id to the ``cx:rt:active`` ZSET (score = started_at)
        """
        now   = _now_iso()
        epoch = _now_epoch()

        record: Dict[str, Any] = {
            "execution_id": execution_id,
            "objective":    objective,
            "user_id":      user_id,
            "session_id":   session_id or "",
            "status":       "running",
            "started_at":   now,
            "updated_at":   now,
            "current_step": "initializing",
            "mission_type": mission_type,
            "priority":     priority,
        }

        self._cache[execution_id] = record

        redis = await self._redis()
        if redis:
            try:
                pipe = redis.pipeline()
                pipe.hset(_exec_key(execution_id), mapping=_flatten(record))
                pipe.expire(_exec_key(execution_id), _TTL_ACTIVE)
                pipe.zadd(_KEY_ACTIVE, {execution_id: epoch})
                await pipe.execute()
                log.debug("RuntimeStateStore.start: persisted %s", execution_id)
            except Exception as exc:
                log.warning("RuntimeStateStore.start Redis write failed: %s", exc)

        return record

    # ------------------------------------------------------------------
    # Update execution progress
    # ------------------------------------------------------------------

    async def update(
        self,
        execution_id: str,
        *,
        status:       Optional[str] = None,
        current_step: Optional[str] = None,
        extra:        Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update mutable fields of a running execution.

        Fields not passed are left unchanged.
        """
        # Load current record (cache-first, then Redis)
        record = await self.get(execution_id)
        if record is None:
            log.warning("RuntimeStateStore.update: unknown execution %s", execution_id)
            return

        if status is not None:
            record["status"] = status
        if current_step is not None:
            record["current_step"] = current_step
        if extra:
            record.update(extra)

        record["updated_at"] = _now_iso()
        self._cache[execution_id] = record

        redis = await self._redis()
        if redis:
            try:
                fields: Dict[str, Any] = {"updated_at": record["updated_at"]}
                if status is not None:
                    fields["status"] = status
                if current_step is not None:
                    fields["current_step"] = current_step
                if extra:
                    fields.update(extra)

                pipe = redis.pipeline()
                pipe.hset(_exec_key(execution_id), mapping=_flatten(fields))
                pipe.expire(_exec_key(execution_id), _TTL_ACTIVE)
                await pipe.execute()
            except Exception as exc:
                log.warning("RuntimeStateStore.update Redis write failed: %s", exc)

    # ------------------------------------------------------------------
    # Complete / fail an execution
    # ------------------------------------------------------------------

    async def complete(
        self,
        execution_id:    str,
        *,
        status:          str = "completed",  # "completed" | "failed" | "cancelled"
        final_response:  Optional[str]  = None,
        failure_reason:  Optional[str]  = None,
        result_summary:  Optional[str]  = None,
    ) -> None:
        """
        Mark an execution as terminal and move it to the history store.

        - Updates the HASH record with terminal fields.
        - Removes from ``cx:rt:active`` ZSET.
        - Copies to ``cx:rt:hist:{execution_id}`` with longer TTL.
        - Adds to ``cx:rt:history`` ZSET.
        """
        record = await self.get(execution_id)
        if record is None:
            record = {
                "execution_id": execution_id,
                "status":       status,
                "started_at":   _now_iso(),
                "updated_at":   _now_iso(),
                "objective":    "",
                "user_id":      "system",
                "session_id":   "",
                "current_step": "unknown",
                "mission_type": "general",
                "priority":     5,
            }

        now            = _now_iso()
        epoch          = _now_epoch()
        started_at     = record.get("started_at", now)
        duration_secs  = _duration(started_at, now)

        record.update({
            "status":          status,
            "completed_at":    now,
            "updated_at":      now,
            "duration_seconds": duration_secs,
            "final_response":  (final_response or "")[:2000],  # cap stored size
            "failure_reason":  failure_reason or "",
            "result_summary":  result_summary or "",
        })

        self._cache[execution_id] = record

        redis = await self._redis()
        if redis:
            try:
                pipe = redis.pipeline()
                # Update active record
                pipe.hset(_exec_key(execution_id), mapping=_flatten(record))
                pipe.expire(_exec_key(execution_id), _TTL_HISTORY)
                # Remove from active ZSET
                pipe.zrem(_KEY_ACTIVE, execution_id)
                # Write history
                pipe.hset(_hist_key(execution_id), mapping=_flatten(record))
                pipe.expire(_hist_key(execution_id), _TTL_HISTORY)
                pipe.zadd(_KEY_HISTORY, {execution_id: epoch})
                await pipe.execute()
            except Exception as exc:
                log.warning("RuntimeStateStore.complete Redis write failed: %s", exc)

        log.info(
            "Execution %s %s in %.1fs",
            execution_id, status, duration_secs,
        )

    # ------------------------------------------------------------------
    # Get a single execution (cache-first, Redis fallback)
    # ------------------------------------------------------------------

    async def get(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return execution record or None."""
        # 1. Check write-through cache
        if execution_id in self._cache:
            return self._cache[execution_id]

        # 2. Try Redis
        redis = await self._redis()
        if redis:
            try:
                raw = await redis.hgetall(_exec_key(execution_id))
                if raw:
                    record = _unflatten(raw)
                    self._cache[execution_id] = record
                    return record
                # Try history key (completed executions)
                raw = await redis.hgetall(_hist_key(execution_id))
                if raw:
                    record = _unflatten(raw)
                    self._cache[execution_id] = record
                    return record
            except Exception as exc:
                log.debug("RuntimeStateStore.get Redis read error: %s", exc)

        return None

    # ------------------------------------------------------------------
    # List active executions
    # ------------------------------------------------------------------

    async def list_active(self) -> List[Dict[str, Any]]:
        """Return all currently active (non-terminal) executions."""
        redis = await self._redis()
        if redis:
            try:
                # ZRANGE returns all members; ZRANGEBYSCORE with all scores
                members = await redis.zrange(_KEY_ACTIVE, 0, -1)
                results = []
                for eid in members:
                    rec = await self.get(eid)
                    if rec:
                        results.append(rec)
                return results
            except Exception as exc:
                log.warning("RuntimeStateStore.list_active Redis error: %s", exc)

        # In-memory fallback
        return [
            r for r in self._cache.values()
            if r.get("status") in ("running", "pending")
        ]

    # ------------------------------------------------------------------
    # List execution history
    # ------------------------------------------------------------------

    async def list_history(
        self,
        limit:  int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return completed execution history, newest first."""
        redis = await self._redis()
        if redis:
            try:
                # ZREVRANGE: newest first (highest score = latest epoch)
                members = await redis.zrevrange(_KEY_HISTORY, offset, offset + limit - 1)
                results = []
                for eid in members:
                    raw = await redis.hgetall(_hist_key(eid))
                    if raw:
                        results.append(_unflatten(raw))
                return results
            except Exception as exc:
                log.warning("RuntimeStateStore.list_history Redis error: %s", exc)

        # In-memory fallback (completed entries from cache)
        terminal = [
            r for r in self._cache.values()
            if r.get("status") in ("completed", "failed", "cancelled")
        ]
        return sorted(terminal, key=lambda r: r.get("completed_at", ""), reverse=True)[:limit]

    # ------------------------------------------------------------------
    # Active execution count
    # ------------------------------------------------------------------

    async def active_count(self) -> int:
        redis = await self._redis()
        if redis:
            try:
                return await redis.zcard(_KEY_ACTIVE)
            except Exception:
                pass
        return sum(
            1 for r in self._cache.values()
            if r.get("status") in ("running", "pending")
        )

    # ------------------------------------------------------------------
    # Startup recovery
    # ------------------------------------------------------------------

    async def recover_on_startup(self) -> int:
        """
        Scan Redis for active executions that survived a restart.

        For each execution found in the active ZSET that is not already
        in the local cache, load it from Redis and add it to the cache.

        Returns the count of recovered executions.
        """
        redis = await self._redis()
        if not redis:
            log.warning("RuntimeStateStore.recover: Redis unavailable — nothing to recover")
            return 0

        try:
            members = await redis.zrange(_KEY_ACTIVE, 0, -1)
        except Exception as exc:
            log.warning("RuntimeStateStore.recover: ZRANGE failed: %s", exc)
            return 0

        recovered = 0
        for eid in members:
            if eid in self._cache:
                continue
            try:
                raw = await redis.hgetall(_exec_key(eid))
                if raw:
                    record = _unflatten(raw)
                    # Mark as recovered rather than orphaned-running
                    if record.get("status") == "running":
                        record["status"]       = "recovered"
                        record["updated_at"]   = _now_iso()
                        record["current_step"] = "recovered_after_restart"
                        # Persist the updated status back
                        await redis.hset(
                            _exec_key(eid),
                            mapping=_flatten({
                                "status":       "recovered",
                                "updated_at":   record["updated_at"],
                                "current_step": record["current_step"],
                            }),
                        )
                    self._cache[eid] = record
                    recovered += 1
            except Exception as exc:
                log.warning("RuntimeStateStore.recover: failed to load %s: %s", eid, exc)

        if recovered:
            # Bump the recovered counter
            try:
                await redis.incrby(_KEY_RCVD, recovered)
                await redis.expire(_KEY_RCVD, _TTL_HISTORY)
            except Exception:
                pass

            log.info("RuntimeStateStore: recovered %d execution(s) from Redis", recovered)

            # Fire audit
            _audit_recovery(recovered)

        return recovered

    async def total_recovered_count(self) -> int:
        """Return the cumulative total of sessions recovered since Redis was last flushed."""
        redis = await self._redis()
        if redis:
            try:
                raw = await redis.get(_KEY_RCVD)
                return int(raw) if raw else 0
            except Exception:
                pass
        return 0

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def status(self) -> Dict[str, Any]:
        """Health snapshot for /health/runtime."""
        redis = await self._redis()
        connected = redis is not None

        active_count    = await self.active_count()
        recovered_total = await self.total_recovered_count()

        return {
            "status":              "healthy" if connected else "degraded",
            "redis_connected":     connected,
            "active_executions":   active_count,
            "recovered_sessions":  recovered_total,
            "cache_size":          len(self._cache),
        }

    # ------------------------------------------------------------------
    # Clear local cache (for testing / maintenance)
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Drop the local write-through cache (does not affect Redis)."""
        self._cache.clear()


# ---------------------------------------------------------------------------
# Flat / unflatten helpers (Redis HSET stores str→str)
# ---------------------------------------------------------------------------

def _flatten(d: Dict[str, Any]) -> Dict[str, str]:
    """Serialise all values to strings suitable for Redis HSET."""
    out: Dict[str, str] = {}
    for k, v in d.items():
        if v is None:
            out[k] = ""
        elif isinstance(v, (dict, list)):
            out[k] = json.dumps(v, default=str)
        else:
            out[k] = str(v)
    return out


def _unflatten(raw: Dict[bytes | str, bytes | str]) -> Dict[str, Any]:
    """Decode raw Redis HGETALL output back to Python types."""
    record: Dict[str, Any] = {}
    for k, v in raw.items():
        key = k.decode() if isinstance(k, bytes) else k
        val = v.decode() if isinstance(v, bytes) else v

        # Attempt JSON decode for structured fields
        if val.startswith("{") or val.startswith("["):
            try:
                val = json.loads(val)
            except Exception:
                pass

        # Coerce known numeric fields
        if key in ("priority",):
            try:
                val = int(val)
            except Exception:
                pass
        elif key in ("duration_seconds",):
            try:
                val = float(val)
            except Exception:
                pass

        record[key] = val
    return record


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

def _audit_recovery(count: int) -> None:
    """Fire-and-forget audit log for recovery events."""
    try:
        import asyncio
        from backend.safety.audit_logger import audit_logger
        audit_logger.log(
            execution_id = "startup",
            agent        = "runtime_state_store",
            action       = "runtime_recovered",
            target       = "executions",
            risk_level   = "low",
            outcome      = "recovered",
            reason       = f"{count} execution(s) recovered from Redis after restart",
            metadata     = {"recovered_count": count},
        )
    except Exception as exc:
        log.debug("_audit_recovery non-fatal: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

runtime_state_store = RuntimeStateStore()
