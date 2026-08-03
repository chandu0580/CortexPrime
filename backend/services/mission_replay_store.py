"""
Mission Replay Store
====================
Dual-layer persistence for every mission event:

  Layer 1 — Redis (hot)
    Key:   cx:replay:{execution_id}
    Type:  Redis List (RPUSH / LRANGE)
    TTL:   72 h  (configurable via REPLAY_REDIS_TTL_HOURS)
    Use:   Sub-second reads, live playback while the mission is running,
           ordered sequence counter using Redis HINCRBY.

  Layer 2 — PostgreSQL (cold / permanent)
    Table: mission_replay_events
    Use:   Long-term audit trail, graph queries, timeline reconstruction
           for any past execution.

Public API
----------
    from backend.services.mission_replay_store import replay_store

    # Persist a CognitionEvent (call from event_bus.publish)
    await replay_store.record(event)

    # Retrieve all events for playback
    events = await replay_store.get_events(execution_id)

    # Get replay summary metadata
    meta   = await replay_store.get_summary(execution_id)

    # Get ordered timeline (chronological)
    tl     = await replay_store.get_timeline(execution_id)

    # Get agent-graph snapshot at each sequence step
    graph  = await replay_store.get_graph(execution_id)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.events.event_models import CognitionEvent
from backend.infrastructure.redis.connection import redis_connection

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPLAY_REDIS_TTL    = int(os.getenv("REPLAY_REDIS_TTL_HOURS",  "72")) * 3600
_REPLAY_MAX_EVENTS   = int(os.getenv("REPLAY_MAX_EVENTS_REDIS", "2000"))

# Canonical event types captured for replay
REPLAY_EVENT_TYPES = {
    "mission_started",
    "mission_completed",
    "mission_failed",
    "agent_started",
    "agent_completed",
    "agent_failed",
    "tool_called",
    "tool_completed",
    "tool_failed",
    "memory_retrieved",
    "memory_stored",
    "response_generated",
    "stream_completed",
    # Map existing EventTypes to replay types
    "execution_started",
    "execution_completed",
    "execution_failed",
    "research_started",
    "research_completed",
    "planning_started",
    "planning_completed",
    "critic_started",
    "critic_completed",
    "optimization_started",
    "optimization_completed",
    "orchestration_started",
    "orchestration_completed",
    "orchestration_failed",
    "reflection_started",
    "reflection_completed",
    "context_built",
    "memory_ranked",
    "memory_retrieval_started",
}

# Mapping from existing event_type strings to canonical replay event_type
_CANONICAL: Dict[str, str] = {
    "execution_started":      "mission_started",
    "execution_completed":    "mission_completed",
    "execution_failed":       "mission_failed",
    "orchestration_started":  "agent_started",
    "orchestration_completed":"agent_completed",
    "orchestration_failed":   "agent_failed",
    "research_started":       "agent_started",
    "research_completed":     "agent_completed",
    "planning_started":       "agent_started",
    "planning_completed":     "agent_completed",
    "critic_started":         "agent_started",
    "critic_completed":       "agent_completed",
    "optimization_started":   "agent_started",
    "optimization_completed": "agent_completed",
    "reflection_started":     "agent_started",
    "reflection_completed":   "agent_completed",
    "memory_retrieval_started": "memory_retrieved",
    "memory_retrieved":       "memory_retrieved",
    "memory_stored":          "memory_stored",
    "context_built":          "memory_retrieved",
    "stream_completed":       "response_generated",
}


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

def _list_key(execution_id: str) -> str:
    return f"cx:replay:events:{execution_id}"

def _seq_key(execution_id: str) -> str:
    return f"cx:replay:seq:{execution_id}"

def _meta_key(execution_id: str) -> str:
    return f"cx:replay:meta:{execution_id}"


# ---------------------------------------------------------------------------
# Inline DB import helper — lazy so startup still works if DB is unavailable
# ---------------------------------------------------------------------------

async def _db_append(execution_id: str, sequence: int, raw: Dict[str, Any]) -> None:
    """Write one replay event row to PostgreSQL.  Silently no-ops if DB is down."""
    try:
        from backend.database.engine import AsyncSessionLocal
        from backend.database.models.mission_replay import MissionReplayEvent

        async with AsyncSessionLocal() as session:
            row = MissionReplayEvent(
                execution_id = execution_id,
                sequence     = sequence,
                event_type   = raw.get("event_type", ""),
                agent        = raw.get("agent", ""),
                status       = raw.get("status", "info"),
                message      = raw.get("message", ""),
                event_ts     = raw.get("timestamp"),
                latency_ms   = raw.get("latency_ms"),
                payload      = raw.get("payload") or {},
            )
            session.add(row)
            await session.commit()
    except Exception as exc:  # pragma: no cover
        log.debug("replay_store DB write skipped: %s", exc)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class MissionReplayStore:
    """
    Dual-layer (Redis + PostgreSQL) replay event store.
    Thread-safe; designed to be called from ``event_bus.publish``.
    """

    # In-memory fallback when Redis is unavailable
    _mem: Dict[str, List[Dict[str, Any]]] = {}
    _seq: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # record()
    # ------------------------------------------------------------------

    async def record(self, event: CognitionEvent) -> None:
        """
        Persist a single CognitionEvent to the replay store.

        Only events whose ``event_type`` is in ``REPLAY_EVENT_TYPES`` (or
        that can be mapped via ``_CANONICAL``) are persisted to keep the
        store focused on mission-level narrative rather than noise.
        """
        et = event.event_type
        if et not in REPLAY_EVENT_TYPES and et not in _CANONICAL:
            return

        exec_id = event.execution_id
        if not exec_id:
            return  # no execution scope — skip

        canonical = _CANONICAL.get(et, et)

        raw: Dict[str, Any] = {
            "event_id":     event.event_id,
            "execution_id": exec_id,
            "event_type":   canonical,
            "original_type": et,
            "agent":        event.agent,
            "status":       event.status,
            "message":      event.message,
            "timestamp":    event.timestamp,
            "latency_ms":   event.latency_ms,
            "phase":        event.phase,
            "confidence_score": event.confidence_score,
            "token_usage":  event.token_usage,
            "payload":      event.payload or {},
        }

        seq = await self._next_seq(exec_id)
        raw["sequence"] = seq

        # ── Redis ────────────────────────────────────────────────────────
        await self._redis_append(exec_id, raw)

        # ── PostgreSQL ───────────────────────────────────────────────────
        await _db_append(exec_id, seq, raw)

    # ------------------------------------------------------------------
    # get_events()  — primary read path
    # ------------------------------------------------------------------

    async def get_events(
        self,
        execution_id: str,
        start: int = 0,
        end:   int = -1,
    ) -> List[Dict[str, Any]]:
        """
        Return all recorded events for *execution_id* ordered by sequence.

        Tries Redis first (fast path); falls back to PostgreSQL.
        ``start`` / ``end`` are 0-based slice indices (Redis LRANGE semantics).
        """
        events = await self._redis_fetch(execution_id, start, end)
        if events:
            return events
        return await self._pg_fetch(execution_id, start, end)

    # ------------------------------------------------------------------
    # get_summary()
    # ------------------------------------------------------------------

    async def get_summary(self, execution_id: str) -> Dict[str, Any]:
        """Return metadata about the replay: duration, agent set, event counts."""
        events = await self.get_events(execution_id)
        if not events:
            return {"execution_id": execution_id, "found": False}

        agents: set[str] = set()
        event_counts: Dict[str, int] = {}
        first_ts: Optional[str] = None
        last_ts:  Optional[str] = None
        total_latency = 0.0
        latency_count = 0

        for e in events:
            agents.add(e.get("agent", ""))
            et = e.get("event_type", "")
            event_counts[et] = event_counts.get(et, 0) + 1
            ts = e.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
            lat = e.get("latency_ms")
            if lat:
                total_latency += lat
                latency_count += 1

        # Compute wall-clock duration
        duration_ms: Optional[float] = None
        if first_ts and last_ts:
            try:
                t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(last_ts.replace("Z",  "+00:00"))
                duration_ms = (t1 - t0).total_seconds() * 1000
            except Exception:
                pass

        return {
            "execution_id":   execution_id,
            "found":          True,
            "total_events":   len(events),
            "event_counts":   event_counts,
            "agents":         sorted(agents),
            "first_ts":       first_ts,
            "last_ts":        last_ts,
            "duration_ms":    duration_ms,
            "avg_latency_ms": (total_latency / latency_count) if latency_count else None,
            "is_complete":    any(
                e.get("event_type") in ("mission_completed", "mission_failed")
                for e in events
            ),
        }

    # ------------------------------------------------------------------
    # get_timeline()  — chronological flat list for the timeline panel
    # ------------------------------------------------------------------

    async def get_timeline(self, execution_id: str) -> List[Dict[str, Any]]:
        """
        Return events as a flat ordered timeline suitable for the
        MissionTimeline component.  Each item carries a relative offset_ms
        from mission start.
        """
        events = await self.get_events(execution_id)
        if not events:
            return []

        # Establish t0 from first event
        t0: Optional[datetime] = None
        for e in events:
            ts = e.get("timestamp")
            if ts:
                try:
                    t0 = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    break
                except Exception:
                    pass

        timeline = []
        for e in events:
            offset_ms: Optional[float] = None
            ts = e.get("timestamp")
            if t0 and ts:
                try:
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    offset_ms = (t - t0).total_seconds() * 1000
                except Exception:
                    pass

            timeline.append({
                **e,
                "offset_ms": offset_ms,
            })

        return timeline

    # ------------------------------------------------------------------
    # get_graph()  — agent-node state at each step for replay animation
    # ------------------------------------------------------------------

    async def get_graph(self, execution_id: str) -> Dict[str, Any]:
        """
        Return a graph-replay structure: for each sequence step, the state
        of every agent node.  The frontend can scrub through this to animate
        the AgentGraph.
        """
        events = await self.get_events(execution_id)

        # Track cumulative state per agent
        agent_state: Dict[str, str] = {}
        steps: List[Dict[str, Any]] = []

        for e in events:
            agent = e.get("agent", "")
            et    = e.get("event_type", "")
            seq   = e.get("sequence", 0)

            if et in ("agent_started", "mission_started"):
                agent_state[agent] = "active"
            elif et in ("agent_completed", "mission_completed", "response_generated"):
                agent_state[agent] = "done"
            elif et in ("agent_failed", "mission_failed"):
                agent_state[agent] = "error"
            elif et in ("memory_retrieved",):
                agent_state[agent] = "processing"
            elif et in ("tool_called",):
                agent_state[agent] = "processing"
            elif et in ("tool_completed",):
                agent_state[agent] = "active"

            steps.append({
                "sequence":    seq,
                "event_type":  et,
                "agent":       agent,
                "message":     e.get("message", ""),
                "timestamp":   e.get("timestamp"),
                "offset_ms":   None,  # populated by get_timeline if needed
                "agent_states": dict(agent_state),
            })

        return {
            "execution_id": execution_id,
            "total_steps":  len(steps),
            "steps":        steps,
            "final_states": agent_state,
        }

    # ------------------------------------------------------------------
    # Internal: Redis helpers
    # ------------------------------------------------------------------

    async def _next_seq(self, execution_id: str) -> int:
        """Atomically increment and return the next sequence number."""
        client = redis_connection.client
        if client:
            # A single transient Redis error mid-run (connection-pool
            # pressure, a momentary network blip) must not silently switch
            # this call to the in-memory counter while a sibling call for
            # the same execution_id stays on Redis — that desyncs the two
            # counters and produces duplicate/out-of-order sequence numbers.
            # One retry covers the transient case; only fall back to
            # in-memory if Redis is genuinely unavailable.
            for _ in range(2):
                try:
                    seq = await client.incr(_seq_key(execution_id))
                    await client.expire(_seq_key(execution_id), _REPLAY_REDIS_TTL)
                    return int(seq)
                except Exception:
                    continue
        # In-memory fallback
        self._seq[execution_id] = self._seq.get(execution_id, 0) + 1
        return self._seq[execution_id]

    async def _redis_append(self, execution_id: str, raw: Dict[str, Any]) -> None:
        client = redis_connection.client
        if not client:
            # In-memory fallback
            self._mem.setdefault(execution_id, [])
            self._mem[execution_id].append(raw)
            return
        try:
            key = _list_key(execution_id)
            await client.rpush(key, json.dumps(raw, default=str))
            # Trim to max size
            await client.ltrim(key, -_REPLAY_MAX_EVENTS, -1)
            await client.expire(key, _REPLAY_REDIS_TTL)
        except Exception as exc:
            log.debug("replay_store Redis write skipped: %s", exc)
            self._mem.setdefault(execution_id, [])
            self._mem[execution_id].append(raw)

    async def _redis_fetch(
        self, execution_id: str, start: int, end: int
    ) -> List[Dict[str, Any]]:
        # Try Redis
        client = redis_connection.client
        if client:
            try:
                key = _list_key(execution_id)
                items = await client.lrange(key, start, end)
                if items:
                    return [json.loads(item) for item in items]
            except Exception as exc:
                log.debug("replay_store Redis read skipped: %s", exc)

        # In-memory fallback — sort by sequence to match _pg_fetch's
        # ORDER BY sequence, since events can land in _mem out of sequence
        # order (e.g. a Redis write failing mid-stream falls a later event
        # back to _mem while earlier ones already made it to Redis).
        mem = self._mem.get(execution_id, [])
        if mem:
            ordered = sorted(mem, key=lambda e: e.get("sequence", 0))
            end_idx = len(ordered) if end == -1 else end + 1
            return ordered[start:end_idx]
        return []

    async def _pg_fetch(
        self, execution_id: str, start: int, end: int
    ) -> List[Dict[str, Any]]:
        """Read from PostgreSQL ordered by sequence (fallback / long-term storage)."""
        try:
            from sqlalchemy import select

            from backend.database.engine import AsyncSessionLocal
            from backend.database.models.mission_replay import MissionReplayEvent

            async with AsyncSessionLocal() as session:
                q = (
                    select(MissionReplayEvent)
                    .where(MissionReplayEvent.execution_id == execution_id)
                    .order_by(MissionReplayEvent.sequence)
                )
                if end >= 0:
                    q = q.slice(start, end + 1)
                elif start > 0:
                    q = q.offset(start)

                result = await session.execute(q)
                rows = result.scalars().all()
                return [r.to_dict() for r in rows]
        except Exception as exc:
            log.debug("replay_store PG read skipped: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

replay_store = MissionReplayStore()
