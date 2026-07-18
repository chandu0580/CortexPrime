"""
Runtime State Store — CortexPrime
====================================
Redis-backed read-through / write-through cache for execution state.

THE CANONICAL STORE IS THE ENGINEERING RUNTIME STORE
(backend.services.enterprise_runtime_store.RuntimeStore → runtime_store.json).

Redis NEVER owns execution state.  It is a best-effort cache that:
  - Speeds up reads for active executions.
  - Survives backend restart (Redis retains cached data).
  - Publishes state-change events so WebSocket clients react in realtime.

Key Schema (prefix ``cx:rt:``)
-------------------------------
cx:rt:exec:{execution_id}   HASH   Active execution record (from RuntimeStore)
cx:rt:active                ZSET   member=execution_id, score=started_at_epoch
cx:rt:hist:{execution_id}   HASH   Completed execution record (longer TTL)
cx:rt:history               ZSET   member=execution_id, score=completed_at_epoch
cx:rt:recovered             STRING Counter of sessions recovered on startup

TTLs
----
Active execution record  : 86400 s (24 h)    — refreshed on every update
Completed/failed history : 604800 s (7 days) — permanent audit trail
Active ZSET entry        : pruned when execution completes / TTL auto-expires

Data Flow
---------
  start()     → RuntimeStore.create_execution()  +  Redis HSET/ZADD (cache)
  update()    → RuntimeStore.update_execution()   +  Redis HSET    (cache)
  complete()  → RuntimeStore.update_execution()   +  Redis HSET/ZADD/ZREM (cache)
  get()       → in-memory cache  →  RuntimeStore  →  Redis (write-through)
  list_active()  → RuntimeStore.list_executions(status=...)
  list_history() → RuntimeStore.list_executions(status=...)
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


_ACTIVE_STATUSES = ("running", "pending")
_TERMINAL_STATUSES = ("completed", "failed", "cancelled")


# =============================================================================
# Helper: map EngineeringExecution ↔ dict for Redis cache
# =============================================================================

_EXEC_TO_CACHE_FIELDS = {
    "execution_id", "objective", "user_id", "session_id", "status",
    "started_at", "updated_at", "completed_at", "current_step",
    "mission_type", "priority", "duration_seconds",
    "final_response", "failure_reason", "result_summary",
}


def _execution_to_cache(execution: Any) -> Dict[str, Any]:
    """Convert an EngineeringExecution to a flat dict for Redis caching."""
    d = execution.to_dict() if hasattr(execution, "to_dict") else dict(execution)
    return {k: v for k, v in d.items() if k in _EXEC_TO_CACHE_FIELDS}


def _cache_to_execution(record: Dict[str, Any]) -> Any:
    """Convert a Redis cache dict back to EngineeringExecution (lazy import)."""
    from backend.services.enterprise_runtime_store import EngineeringExecution
    return EngineeringExecution.from_dict(record)


# =============================================================================
# RuntimeStateStore — Redis cache facade
# =============================================================================

class RuntimeStateStore:
    """
    Redis-backed read-through / write-through cache for execution state.

    The canonical source of truth is ``RuntimeStore`` (runtime_store.json).
    Every write goes to RuntimeStore first, then the Redis cache is updated
    best-effort.  Every read checks the local in-memory cache, then RuntimeStore,
    then Redis.
    """

    def __init__(self) -> None:
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
    # Internal: write-through helpers
    # ------------------------------------------------------------------

    def _store(self) -> Any:
        """Lazy import of the canonical RuntimeStore singleton."""
        from backend.services.enterprise_runtime_store import runtime_store
        return runtime_store

    def _store_create(self, execution_id: str, objective: str, **extra: Any) -> None:
        """Create an EngineeringExecution in the canonical RuntimeStore."""
        from backend.services.enterprise_runtime_store import EngineeringExecution
        exec_kwargs = {
            "execution_id": execution_id,
            "objective": objective,
            "status": "running",
            "started_at": extra.pop("started_at", _now_iso()),
            **extra,
        }
        execution = EngineeringExecution(**exec_kwargs)
        self._store().create_execution(execution)

    def _store_update(self, execution_id: str, **kwargs: Any) -> bool:
        """Update an execution in the canonical RuntimeStore."""
        result = self._store().update_execution(execution_id, **kwargs)
        return result is not None

    def _store_get(self, execution_id: str) -> Optional[Any]:
        """Get an EngineeringExecution from the canonical RuntimeStore."""
        return self._store().get_execution(execution_id)

    def _store_list(self, status: str = "", limit: int = 1000) -> List[Any]:
        """List executions from the canonical RuntimeStore."""
        return self._store().list_executions(status=status, limit=limit)

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
        Register a new execution in the canonical RuntimeStore,
        then cache in Redis best-effort.
        """
        now   = _now_iso()
        epoch = _now_epoch()

        # 1. Write through to canonical store
        self._store_create(
            execution_id=execution_id,
            objective=objective,
            user_id=user_id,
            session_id=session_id or "",
            mission_type=mission_type,
            priority=priority,
            started_at=now,
            current_step="initializing",
        )

        # 2. Build cache record
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

        # 3. Best-effort Redis cache write
        redis = await self._redis()
        if redis:
            try:
                pipe = redis.pipeline()
                pipe.hset(_exec_key(execution_id), mapping=_flatten(record))
                pipe.expire(_exec_key(execution_id), _TTL_ACTIVE)
                pipe.zadd(_KEY_ACTIVE, {execution_id: epoch})
                await pipe.execute()
                log.debug("RuntimeStateStore.start: cached %s in Redis", execution_id)
            except Exception as exc:
                log.warning("RuntimeStateStore.start Redis cache write failed: %s", exc)

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

        Writes through to RuntimeStore, then best-effort Redis cache write.
        """
        # 1. Write through to canonical store
        store_kwargs: Dict[str, Any] = {}
        if status is not None:
            store_kwargs["status"] = status
        if current_step is not None:
            store_kwargs["current_step"] = current_step
        if extra:
            store_kwargs.update(extra)
        self._store_update(execution_id, **store_kwargs)

        # 2. Update local cache
        record = self._cache.get(execution_id)
        if record is None:
            record = {}
            self._cache[execution_id] = record
        if status is not None:
            record["status"] = status
        if current_step is not None:
            record["current_step"] = current_step
        if extra:
            record.update(extra)
        record["updated_at"] = _now_iso()

        # 3. Best-effort Redis cache update
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
                log.warning("RuntimeStateStore.update Redis cache write failed: %s", exc)

    # ------------------------------------------------------------------
    # Complete / fail an execution
    # ------------------------------------------------------------------

    async def complete(
        self,
        execution_id:    str,
        *,
        status:          str = "completed",
        final_response:  Optional[str]  = None,
        failure_reason:  Optional[str]  = None,
        result_summary:  Optional[str]  = None,
    ) -> None:
        """
        Mark an execution as terminal in the canonical RuntimeStore.

        Also cache in Redis (best-effort) for fast reads.
        """
        now           = _now_iso()
        epoch         = _now_epoch()

        # 1. Load current record (try cache first, then RuntimeStore)
        record = self._cache.get(execution_id)
        if record is None:
            exec_obj = self._store_get(execution_id)
            if exec_obj:
                record = exec_obj.to_dict()
        if record is None:
            record = {
                "execution_id": execution_id,
                "status":       status,
                "started_at":   now,
                "updated_at":   now,
                "objective":    "",
                "user_id":      "system",
                "session_id":   "",
                "current_step": "unknown",
                "mission_type": "general",
                "priority":     5,
            }

        started_at    = record.get("started_at", now)
        duration_secs = _duration(started_at, now)

        terminal_fields = {
            "status":           status,
            "completed_at":     now,
            "updated_at":       now,
            "duration_seconds": duration_secs,
            "final_response":   (final_response or ""),
            "failure_reason":   failure_reason or "",
            "result_summary":   result_summary or "",
        }

        # 2. Write through to canonical store
        self._store_update(execution_id, **terminal_fields)

        # 3. Update local cache
        record.update(terminal_fields)
        self._cache[execution_id] = record

        # 4. Best-effort Redis cache write
        redis = await self._redis()
        if redis:
            try:
                pipe = redis.pipeline()
                pipe.hset(_exec_key(execution_id), mapping=_flatten(record))
                pipe.expire(_exec_key(execution_id), _TTL_HISTORY)
                pipe.zrem(_KEY_ACTIVE, execution_id)
                pipe.hset(_hist_key(execution_id), mapping=_flatten(record))
                pipe.expire(_hist_key(execution_id), _TTL_HISTORY)
                pipe.zadd(_KEY_HISTORY, {execution_id: epoch})
                await pipe.execute()
            except Exception as exc:
                log.warning("RuntimeStateStore.complete Redis cache write failed: %s", exc)

        log.info(
            "Execution %s %s in %.1fs",
            execution_id, status, duration_secs,
        )

    # ------------------------------------------------------------------
    # Get a single execution (cache → RuntimeStore → Redis)
    # ------------------------------------------------------------------

    async def get(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return execution record from canonical store, caching best-effort."""
        # 1. Check in-memory cache
        if execution_id in self._cache:
            return self._cache[execution_id]

        # 2. Check canonical RuntimeStore
        exec_obj = self._store_get(execution_id)
        if exec_obj:
            record = exec_obj.to_dict()
            self._cache[execution_id] = record
            return record

        # 3. Fallback to Redis (in case RuntimeStore is stale / recovering)
        redis = await self._redis()
        if redis:
            try:
                raw = await redis.hgetall(_exec_key(execution_id))
                if raw:
                    record = _unflatten(raw)
                    self._cache[execution_id] = record
                    return record
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
        """Return all currently active (non-terminal) executions from RuntimeStore."""
        execs = self._store_list(limit=1000)
        return [
            e.to_dict() for e in execs
            if e.status in _ACTIVE_STATUSES
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
        all_execs = self._store_list(limit=1000)
        terminal = [
            e.to_dict() for e in all_execs
            if e.status in _TERMINAL_STATUSES
        ]
        terminal.sort(key=lambda r: r.get("completed_at", r.get("updated_at", "")), reverse=True)
        return terminal[offset:offset + limit]

    # ------------------------------------------------------------------
    # Active execution count
    # ------------------------------------------------------------------

    async def active_count(self) -> int:
        return len(await self.list_active())

    # ------------------------------------------------------------------
    # Startup recovery (load from Redis into cache)
    # ------------------------------------------------------------------

    async def recover_on_startup(self) -> int:
        """
        Scan Redis for active executions that survived a restart.

        Redis is a cache, not the source of truth, but this helps rebuild
        the in-memory cache after a cold start.
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
                    if record.get("status") == "running":
                        record["status"] = "recovered"
                        record["updated_at"] = _now_iso()
                        record["current_step"] = "recovered_after_restart"
                        await redis.hset(
                            _exec_key(eid),
                            mapping=_flatten({
                                "status": "recovered",
                                "updated_at": record["updated_at"],
                                "current_step": record["current_step"],
                            }),
                        )
                    self._cache[eid] = record
                    recovered += 1
            except Exception as exc:
                log.warning("RuntimeStateStore.recover: failed to load %s: %s", eid, exc)

        if recovered:
            try:
                await redis.incrby(_KEY_RCVD, recovered)
                await redis.expire(_KEY_RCVD, _TTL_HISTORY)
            except Exception:
                pass

            log.info("RuntimeStateStore: recovered %d execution(s) from Redis", recovered)
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
        """Drop the local write-through cache (does not affect RuntimeStore or Redis)."""
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

        if val.startswith("{") or val.startswith("["):
            try:
                val = json.loads(val)
            except Exception:
                pass

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
        from backend.safety.audit_logger import audit_logger
        audit_logger.log(
            execution_id="startup",
            agent="runtime_state_store",
            action="runtime_recovered",
            target="executions",
            risk_level="low",
            outcome="recovered",
            reason=f"{count} execution(s) recovered from Redis after restart",
            metadata={"recovered_count": count},
        )
    except Exception as exc:
        log.debug("_audit_recovery non-fatal: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

runtime_state_store = RuntimeStateStore()
