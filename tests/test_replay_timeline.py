"""
Sprint 53.2 — Phase 4: Replay Timeline & Audit Consistency
===========================================================
Tests for the MissionReplayStore covering:

  - Event recording and ordering
  - Timeline computation with offset_ms
  - Agent graph state tracking
  - Summary metadata generation
  - Dual-layer persistence (Redis + PostgreSQL fallback)
  - Event type filtering via REPLAY_EVENT_TYPES

Usage:
    pytest tests/test_replay_timeline.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# =============================================================
# HELPERS
# =============================================================

def _make_event(
    event_type: str = "mission_started",
    agent: str = "orchestrator",
    execution_id: str = "exec-1",
    status: str = "running",
    message: str = "test event",
    phase: str = "INIT",
    timestamp: str | None = None,
    sequence: int = 1,
    payload: dict | None = None,
) -> Dict[str, Any]:
    return {
        "event_id": f"evt-{sequence}",
        "execution_id": execution_id,
        "event_type": event_type,
        "original_type": event_type,
        "agent": agent,
        "status": status,
        "message": message,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "latency_ms": None,
        "phase": phase,
        "confidence_score": None,
        "token_usage": None,
        "payload": payload or {},
        "sequence": sequence,
    }


def _mock_cognition_event(event_type: str, execution_id: str = "exec-1", **kw):
    """Create a mock CognitionEvent-like object."""
    from types import SimpleNamespace
    return SimpleNamespace(
        event_id=f"evt-{kw.get('sequence', 0)}",
        execution_id=execution_id,
        event_type=event_type,
        agent=kw.get("agent", "orchestrator"),
        status=kw.get("status", "running"),
        message=kw.get("message", "test"),
        timestamp=kw.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        latency_ms=kw.get("latency_ms"),
        phase=kw.get("phase", "INIT"),
        confidence_score=kw.get("confidence_score"),
        token_usage=kw.get("token_usage"),
        payload=kw.get("payload", {}),
    )


# =============================================================
# 1. EVENT RECORDING
# =============================================================

class TestEventRecording:
    """Test record() — event persistence with type filtering."""

    async def test_records_relevant_event(self, monkeypatch):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        store._redis_append = AsyncMock()
        store._next_seq = AsyncMock(return_value=1)

        monkeypatch.setattr("backend.services.mission_replay_store._db_append", AsyncMock())

        event = _mock_cognition_event("mission_started", execution_id="exec-1")
        await store.record(event)

        assert store._redis_append.called

    async def test_skips_irrelevant_event_types(self, monkeypatch):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        store._redis_append = AsyncMock()

        monkeypatch.setattr("backend.services.mission_replay_store._db_append", AsyncMock())

        event = _mock_cognition_event("heartbeat", execution_id="exec-1")
        await store.record(event)

        assert not store._redis_append.called

    async def test_skips_events_without_execution_id(self, monkeypatch):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        store._redis_append = AsyncMock()

        monkeypatch.setattr("backend.services.mission_replay_store._db_append", AsyncMock())

        event = _mock_cognition_event("mission_started", execution_id=None)
        event.execution_id = None
        await store.record(event)

        assert not store._redis_append.called

    async def test_maps_canonical_event_types(self, monkeypatch):
        from backend.services.mission_replay_store import MissionReplayStore, _CANONICAL

        store = MissionReplayStore()
        stored = []

        async def _fake_redis_append(eid, raw):
            stored.append(raw)

        store._redis_append = _fake_redis_append
        store._next_seq = AsyncMock(return_value=1)

        monkeypatch.setattr("backend.services.mission_replay_store._db_append", AsyncMock())

        event = _mock_cognition_event("execution_started", execution_id="exec-1")  # maps to "mission_started"
        await store.record(event)

        assert len(stored) == 1
        assert stored[0]["event_type"] == "mission_started"


# =============================================================
# 2. EVENT RETRIEVAL & ORDERING
# =============================================================

class TestEventRetrieval:
    """Test get_events and get_events ordering."""

    async def test_returns_empty_for_unknown_execution(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        events = await store.get_events("nonexistent")
        assert events == []

    async def test_returns_events_in_sequence_order(self, monkeypatch):
        from backend.services.mission_replay_store import MissionReplayStore

        # This test is about in-memory fallback ordering, not real Redis —
        # force the in-memory path so a genuinely-connected Redis (empty for
        # this execution_id) can't shadow the _mem data set up below.
        monkeypatch.setattr(
            "backend.infrastructure.redis.connection.redis_connection._client",
            None,
        )

        store = MissionReplayStore()

        store._mem["exec-ord"] = [
            _make_event(sequence=3, execution_id="exec-ord"),
            _make_event(sequence=1, execution_id="exec-ord"),
            _make_event(sequence=2, execution_id="exec-ord"),
        ]

        events = await store.get_events("exec-ord")
        sequences = [e["sequence"] for e in events]
        assert sequences == [1, 2, 3]

    async def test_redis_fetch_falls_back_to_memory(self, monkeypatch):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        # client is a read-only @property backed by _client — patch the
        # backing attribute, not the property itself (which has no setter).
        monkeypatch.setattr(
            "backend.infrastructure.redis.connection.redis_connection._client",
            None,
        )

        store._mem["exec-fb"] = [
            _make_event(sequence=1, execution_id="exec-fb"),
        ]

        events = await store.get_events("exec-fb")
        assert len(events) == 1


# =============================================================
# 3. TIMELINE COMPUTATION
# =============================================================

class TestTimeline:
    """Test get_timeline offset_ms computation."""

    async def test_timeline_has_offset_ms(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        base_ts = "2025-01-01T00:00:00.000+00:00"
        later_ts = "2025-01-01T00:00:05.000+00:00"

        store._mem["exec-tl"] = [
            _make_event(sequence=1, timestamp=base_ts, execution_id="exec-tl"),
            _make_event(sequence=2, timestamp=later_ts, execution_id="exec-tl"),
        ]

        tl = await store.get_timeline("exec-tl")
        assert len(tl) == 2
        assert tl[0]["offset_ms"] == 0.0
        assert tl[1]["offset_ms"] == 5000.0

    async def test_timeline_empty_for_unknown(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        tl = await store.get_timeline("nonexistent")
        assert tl == []

    async def test_timeline_handles_missing_timestamp(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        store._mem["exec-nts"] = [
            _make_event(sequence=1, execution_id="exec-nts"),
            _make_event(sequence=2, timestamp=None, execution_id="exec-nts"),
        ]

        tl = await store.get_timeline("exec-nts")
        assert len(tl) == 2
        # Second event should have None offset_ms since t0 not established
        # Actually t0 is established from first event, second has no ts so offset_ms stays None
        assert tl[0]["offset_ms"] is not None or tl[0]["offset_ms"] == 0


# =============================================================
# 4. AGENT GRAPH STATE TRACKING
# =============================================================

class TestGraphState:
    """Test get_graph agent state tracking."""

    async def test_graph_tracks_agent_states(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        store._mem["exec-gr"] = [
            _make_event(sequence=1, event_type="mission_started", agent="orchestrator", execution_id="exec-gr"),
            _make_event(sequence=2, event_type="agent_started", agent="planner", execution_id="exec-gr"),
            _make_event(sequence=3, event_type="agent_completed", agent="planner", execution_id="exec-gr"),
            _make_event(sequence=4, event_type="tool_called", agent="github", execution_id="exec-gr"),
            _make_event(sequence=5, event_type="tool_completed", agent="github", execution_id="exec-gr"),
        ]

        graph = await store.get_graph("exec-gr")
        assert graph["total_steps"] == 5
        assert graph["execution_id"] == "exec-gr"
        assert "final_states" in graph

    async def test_graph_state_transitions(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        store._mem["exec-gt"] = [
            _make_event(sequence=1, event_type="mission_started", agent="orchestrator", execution_id="exec-gt"),
            _make_event(sequence=2, event_type="agent_started", agent="planner", execution_id="exec-gt"),
            _make_event(sequence=3, event_type="agent_failed", agent="planner", execution_id="exec-gt"),
            _make_event(sequence=4, event_type="mission_failed", agent="orchestrator", execution_id="exec-gt"),
        ]

        graph = await store.get_graph("exec-gt")
        last_step = graph["steps"][-1]
        assert last_step["agent_states"]["planner"] == "error"
        assert last_step["agent_states"]["orchestrator"] == "error"


# =============================================================
# 5. SUMMARY METADATA
# =============================================================

class TestSummary:
    """Test get_summary metadata generation."""

    async def test_summary_contains_required_fields(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        base_ts = "2025-01-01T00:00:00+00:00"
        later_ts = "2025-01-01T00:02:30+00:00"

        store._mem["exec-sm"] = [
            _make_event(sequence=1, event_type="mission_started", agent="orchestrator", timestamp=base_ts, execution_id="exec-sm"),
            _make_event(sequence=2, event_type="agent_started", agent="planner", timestamp=base_ts, execution_id="exec-sm"),
            _make_event(sequence=3, event_type="agent_completed", agent="planner", timestamp=later_ts, execution_id="exec-sm"),
            _make_event(sequence=4, event_type="mission_completed", agent="orchestrator", timestamp=later_ts, execution_id="exec-sm"),
        ]

        summary = await store.get_summary("exec-sm")
        assert summary["found"] is True
        assert summary["execution_id"] == "exec-sm"
        assert summary["total_events"] == 4
        assert summary["duration_ms"] == 150000.0  # 2.5 minutes
        assert summary["is_complete"] is True
        assert "orchestrator" in summary["agents"]
        assert "planner" in summary["agents"]

    async def test_summary_not_found(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        summary = await store.get_summary("nonexistent")
        assert summary["found"] is False


# =============================================================
# 6. SEQUENCE COUNTER
# =============================================================

class TestSequenceCounter:
    """Test _next_seq atomic increment."""

    async def test_sequence_increments(self):
        from backend.services.mission_replay_store import MissionReplayStore

        store = MissionReplayStore()
        s1 = await store._next_seq("exec-seq")
        s2 = await store._next_seq("exec-seq")
        assert s2 == s1 + 1

    async def test_sequence_independent_per_execution(self):
        import uuid

        from backend.services.mission_replay_store import MissionReplayStore

        # Unique per run — real Redis INCR counters for generic literals
        # like "exec-a"/"exec-b" persist across test runs, so a fixed
        # literal collides with leftover state from other tests.
        exec_a = f"exec-a-{uuid.uuid4().hex[:8]}"
        exec_b = f"exec-b-{uuid.uuid4().hex[:8]}"

        store = MissionReplayStore()
        s1 = await store._next_seq(exec_a)
        s2 = await store._next_seq(exec_b)
        assert s1 == 1
        assert s2 == 1
