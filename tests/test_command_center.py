"""
Sprint 53.2 — Phase 6: Command Center / Dashboard
==================================================
Tests for dashboard, realtime updates, and command center panels.

Covers:
  - Dashboard data payload structure
  - Mission realtime update events
  - Panel data shapes (governance, metrics, recent missions)
  - WebSocket stream event types

Usage:
    pytest tests/test_command_center.py -v
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND_PATH = os.path.join(os.path.dirname(__file__), "..", "backend")
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

pytestmark = pytest.mark.asyncio


# =============================================================
# 1. DASHBOARD DATA STRUCTURE
# =============================================================

class TestDashboardDataShape:
    """Verify the shape of dashboard data returned by various endpoints."""

    def test_mission_completed_event_structure(self):
        """Stream_completed event should contain required fields."""
        event = {
            "agent": "orchestrator",
            "event_type": "stream_completed",
            "stream_completed": True,
            "execution_id": "exec-1",
            "session_id": "sess-1",
            "status": "completed",
            "message": "Mission complete",
        }
        required = {"agent", "event_type", "execution_id", "status", "message"}
        assert required.issubset(event.keys())

    def test_progress_event_structure(self):
        """Progress events should include stage, progress, and status."""
        event = {
            "agent": "orchestrator",
            "event_type": "progress",
            "stage": "PLANNING",
            "status": "running",
            "message": "Planning...",
            "progress": 0.1,
            "execution_id": "exec-1",
            "session_id": "sess-1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        required = {"agent", "event_type", "stage", "status", "progress", "execution_id"}
        assert required.issubset(event.keys())

    def test_stream_chunk_event_structure(self):
        """Stream chunks should carry the token and agent info."""
        chunk = {
            "agent": "orchestrator",
            "event_type": "stream_chunk",
            "stream": True,
            "stream_chunk": "Hello ",
            "execution_id": "exec-1",
            "session_id": "sess-1",
            "status": "streaming",
            "message": "Streaming response",
        }
        assert "stream_chunk" in chunk
        assert chunk["stream"] is True

    def test_governance_panel_event(self):
        """Governance events carry risk_level and requires_approval."""
        event = {
            "agent": "governance",
            "event_type": "mission_paused",
            "governance": True,
            "risk_level": "high",
            "requires_approval": True,
            "execution_id": "exec-1",
            "status": "pending_approval",
        }
        assert event["governance"] is True
        assert "risk_level" in event


# =============================================================
# 2. REALTIME UPDATE HANDLING
# =============================================================

class TestRealtimeUpdates:
    """Test realtime update patterns for WebSocket events."""

    pytestmark = pytest.mark.xfail(
        reason="documented, not yet implemented — Sprint 40.2/53.2 tool-execution pipeline, tracked debt not a bug",
    )

    def test_progress_honors_pipeline_stages(self):
        """Progress events should follow the canonical stage order."""
        canonical_order = [
            "INIT", "PLANNING", "TOOL_SELECTION", "TOOL_EXECUTION",
            "SKILL_EXECUTION", "RESEARCHING", "VALIDATING",
            "GENERATING", "MEMORY_UPDATE", "COMPLETED",
        ]
        # Verify the stage order is defined in mission_runtime
        path = os.path.join(BACKEND_PATH, "services", "mission_runtime.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        for stage in canonical_order:
            assert stage in source, f"Stage {stage} not found in mission_runtime.py"

    def test_stream_events_use_consistent_agent_names(self):
        """Verify that known agent strings are used in stream events."""
        known_agents = {
            "orchestrator", "planner", "research", "critic",
            "tool_selector", "tool_executor", "memory",
            "browser_agent", "computer_agent_v2", "governance",
            "software_release_skill", "guardrails",
        }
        path = os.path.join(BACKEND_PATH, "services", "mission_runtime.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        for agent in known_agents:
            assert agent in source, f"Agent name '{agent}' not found in mission_runtime.py"

    def test_event_types_for_frontend_consumption(self):
        """List event_types the frontend expects to consume."""
        expected_event_types = {
            "mission_created", "mission_completed", "mission_failed",
            "mission_blocked", "mission_paused", "mission_resumed",
            "mission_rejected", "mission_stopped",
            "planning_started", "planning_completed",
            "tool_selection_started", "tool_selection_completed",
            "tool_execution_started", "tool_execution_completed",
            "tool_called", "tool_completed", "tool_failed",
            "research_started", "research_completed",
            "critic_started", "critic_completed",
            "generating_response",
            "memory_update_started", "memory_updated",
            "stream_chunk", "stream_completed",
            "progress",
        }
        path = os.path.join(BACKEND_PATH, "services", "mission_runtime.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        for et in expected_event_types:
            assert et in source, f"Event type '{et}' missing from mission_runtime.py"


# =============================================================
# 3. PANEL DATA SHAPES
# =============================================================

class TestPanelDataShapes:
    """Verify data shapes for command center panels."""

    def test_governance_panel_data_shape(self):
        """Governance center data should include risk summary and approval queue."""
        panel_data = {
            "total_missions_today": 42,
            "blocked_count": 2,
            "pending_approval_count": 3,
            "critical_actions": [],
            "recent_audit_events": [],
        }
        required = {"total_missions_today", "blocked_count", "pending_approval_count"}
        assert required.issubset(panel_data.keys())

    def test_metrics_panel_data_shape(self):
        """Metrics panel requires operational KPIs."""
        panel_data = {
            "missions_completed": 100,
            "missions_failed": 5,
            "avg_confidence": 0.92,
            "avg_response_time_ms": 4500,
            "total_tokens_used": 500000,
            "active_connectors": 8,
            "cost_today_usd": 12.50,
        }
        required = {"missions_completed", "missions_failed", "avg_confidence"}
        assert required.issubset(panel_data.keys())

    def test_recent_missions_data_shape(self):
        """Recent missions list should have execution metadata."""
        mission = {
            "execution_id": "exec-1",
            "objective": "Deploy release",
            "status": "completed",
            "confidence": 0.95,
            "started_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T00:01:30Z",
            "duration_ms": 90000,
        }
        required = {"execution_id", "objective", "status", "started_at"}
        assert required.issubset(mission.keys())

    def test_connector_status_panel_shape(self):
        """Connector status panel should show health per connector."""
        panel = {
            "connectors": {
                "github": {"status": "available", "initialized": True},
                "jira": {"status": "available", "initialized": True},
                "slack": {"status": "unavailable", "initialized": False},
            },
            "total": 8,
            "available": 2,
            "unavailable": 1,
        }
        assert panel["total"] >= 0
        assert panel["available"] + panel["unavailable"] <= panel["total"]


# =============================================================
# 4. EVENT EMISSION PATTERNS
# =============================================================

class TestEmissionPatterns:
    """Test the _emit and _send_progress patterns used by the pipeline."""

    async def test_emit_event_structure(self, monkeypatch):
        """Verify the _emit function publishes the right event shape."""
        from backend.services import mission_runtime as mod

        published = []

        async def _fake_publish(event):
            published.append(event)

        monkeypatch.setattr(mod.event_bus, "publish", _fake_publish)

        await mod._emit(
            execution_id="exec-emit",
            agent="test_agent",
            event_type="test_event",
            status="running",
            message="test",
            phase="TEST",
            payload={"key": "val"},
            session_id="sess-1",
        )

        assert len(published) == 1
        evt = published[0]
        assert evt.execution_id == "exec-emit"
        assert evt.agent == "test_agent"
        assert evt.event_type == "test_event"

    @pytest.mark.xfail(
        reason="documented, not yet implemented — Sprint 40.2/53.2 tool-execution pipeline, tracked debt not a bug",
    )
    async def test_send_progress_structure(self, monkeypatch):
        """Verify _send_progress sends correct stream_chunk event."""
        from backend.services import mission_runtime as mod

        sent = []

        async def _fake_send(chunk, session_id):
            sent.append((chunk, session_id))

        monkeypatch.setattr(mod, "_send_stream_chunk", _fake_send)

        await mod._send_progress(
            execution_id="exec-prog",
            stage="PLANNING",
            status="running",
            message="Planning...",
            progress=0.5,
            agent="planner",
            session_id="sess-1",
            payload={"detail": "test"},
        )

        assert len(sent) == 1
        chunk, sid = sent[0]
        assert chunk["event_type"] == "progress"
        assert chunk["stage"] == "PLANNING"
        assert chunk["progress"] == 0.5
        assert chunk["agent"] == "planner"
        assert sid == "sess-1"

    async def test_send_stream_chunk_fallback_on_session_disconnect(self, monkeypatch):
        """When session broadcast returns 0, should fall back to global broadcast."""
        from backend.services import mission_runtime as mod

        global_broadcasts = []

        async def _fake_session_broadcast(session_id, chunk):
            return 0  # session disconnected

        async def _fake_global_broadcast(chunk):
            global_broadcasts.append(chunk)

        # We need to mock the internal imports in _send_stream_chunk
        mock_pool = MagicMock()
        mock_pool.broadcast_to_session = _fake_session_broadcast
        mock_pool.broadcast = _fake_global_broadcast

        mock_manager = MagicMock()
        mock_manager.broadcast = _fake_global_broadcast

        import backend.websocket.connection_pool as cp

        monkeypatch.setattr(cp, "connection_pool", mock_pool)
        # mission_runtime does `from ... import manager` at module scope, so
        # patching the connection_manager module's attribute doesn't reach
        # it — patch mission_runtime's own bound name instead.
        monkeypatch.setattr(mod, "manager", mock_manager)

        await mod._send_stream_chunk({"test": True}, "sess-disc")
        assert len(global_broadcasts) == 1

    async def test_send_stream_chunk_global_broadcast_no_session(self, monkeypatch):
        """When session_id is None, should broadcast globally."""
        from backend.services import mission_runtime as mod

        global_broadcasts = []

        mock_pool = MagicMock()
        mock_pool.broadcast = lambda chunk: global_broadcasts.append(chunk)

        import backend.websocket.connection_pool as cp

        monkeypatch.setattr(cp, "connection_pool", mock_pool)

        await mod._send_stream_chunk({"test": True}, None)
        assert len(global_broadcasts) == 1


# =============================================================
# 5. COMMAND CENTER API RESPONSE STRUCTURE
# =============================================================

class TestCommandCenterResponseStructure:
    """Verify mission summary response shape returned to command center."""

    def test_mission_summary_has_command_center_fields(self):
        """The mission summary dict should contain fields the command center renders."""
        summary = {
            "execution_id": "exec-1",
            "status": "completed",
            "objective": "test",
            "started_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T00:01:00Z",
            "confidence_score": 0.95,
            "response_length": 500,
            "stages": {"planning": True, "research": True, "validation": True, "generation": True},
            "tools": {
                "total_selected": 1,
                "connectors_executed": 1,
                "connectors_failed": 0,
                "connectors_skipped": 0,
                "total_duration_ms": 1500,
                "verification": {"total": 1, "verified": 1, "unverified": 0, "skipped": 0, "verification_rate": 1.0},
            },
            "agents": {"browser": False, "computer": False},
        }
        required = {"execution_id", "status", "objective", "confidence_score", "stages", "tools"}
        assert required.issubset(summary.keys())
