from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import ModuleType
import sys

import pytest


def _iso_utc(delta: timedelta = timedelta()) -> str:
    return (datetime.now(timezone.utc) - delta).isoformat()


@pytest.fixture
def executive_audit_entries() -> list[dict]:
    return [
        {
            "timestamp": _iso_utc(timedelta(hours=1)),
            "action": "mission_start",
            "outcome": "approved",
            "agent": "orchestrator",
            "execution_id": "exec-1",
        },
        {
            "timestamp": _iso_utc(timedelta(hours=2)),
            "action": "tool_browser_open",
            "outcome": "blocked",
            "agent": "research",
            "execution_id": "exec-1",
        },
        {
            "timestamp": _iso_utc(timedelta(days=1)),
            "action": "voice_session_started",
            "outcome": "approved",
            "agent": "memory",
            "execution_id": "exec-2",
        },
        {
            "timestamp": _iso_utc(timedelta(days=2)),
            "action": "memory_store",
            "outcome": "failed",
            "agent": "critic",
            "execution_id": "exec-3",
        },
    ]


def test_status_score_and_ts_float_helpers():
    from backend.api import executive_routes as mod

    assert mod._status_score("healthy") == 100.0
    assert mod._status_score("degraded") == 55.0
    assert mod._status_score("offline") == 0.0
    assert mod._status_score("something-else") == 50.0
    assert mod._ts_float("bad-date") == 0.0
    assert mod._ts_float(_iso_utc()) > 0


@pytest.mark.asyncio
async def test_get_snapshot_aggregates(monkeypatch, executive_audit_entries):
    from backend.api import executive_routes as mod
    from backend.safety.audit_logger import audit_logger
    from backend.safety.guardrails_engine import guardrails_engine
    from backend.safety.emergency_stop import emergency_stop
    from backend.safety.approval_queue import approval_queue

    monkeypatch.setattr(audit_logger, "get_all", lambda limit=500: executive_audit_entries)
    monkeypatch.setattr(
        guardrails_engine.telemetry,
        "snapshot",
        lambda recent_n=5: {"block_rate": 0.2},
    )
    monkeypatch.setattr(emergency_stop, "is_active", lambda: False, raising=False)
    monkeypatch.setattr(approval_queue, "get_pending", lambda: [{"id": "p1"}, {"id": "p2"}])

    class FakePostgres:
        async def fetch(self, query: str):
            return [
                {
                    "execution_id": "exec-running",
                    "goal": "Investigate issue",
                    "status": "running",
                    "started_at": _iso_utc(timedelta(minutes=5)),
                    "completed_at": None,
                    "metadata": {},
                    "progress": 60,
                },
                {
                    "execution_id": "exec-done",
                    "goal": "Done mission",
                    "status": "completed",
                    "started_at": _iso_utc(timedelta(hours=2)),
                    "completed_at": _iso_utc(timedelta(hours=1)),
                    "metadata": {},
                },
            ]

        async def fetchrow(self, query: str):
            if "episodic_memory" in query:
                return {"cnt": 10}
            if "semantic_memory" in query:
                return {"cnt": 20}
            return {"cnt": 5}

    class FakeVoiceManager:
        @staticmethod
        def get_active_sessions():
            return [{"id": "s1"}, {"id": "s2"}]

    class FakeLLMRouter:
        @staticmethod
        def get_active_provider():
            return "Azure"

        @staticmethod
        def health():
            return {"healthy": False}

    class FakeEmbeddingPipeline:
        @staticmethod
        async def validate_dimensions():
            return {"ok": False, "model": "text-embedding-3-large"}

    class FakeAgentRegistry:
        @staticmethod
        def list_agents():
            return ["orchestrator", "planner", "research"]

    monkeypatch.setattr("backend.memory.db.postgres_client.postgres_client", FakePostgres())
    voice_module = ModuleType("backend.voice.voice_manager")
    voice_module.voice_manager = FakeVoiceManager()
    monkeypatch.setitem(sys.modules, "backend.voice.voice_manager", voice_module)
    llm_module = ModuleType("backend.llm.router")
    llm_module.llm_router = FakeLLMRouter()
    monkeypatch.setitem(sys.modules, "backend.llm.router", llm_module)
    monkeypatch.setattr("backend.memory.embedding_pipeline.embedding_pipeline", FakeEmbeddingPipeline(), raising=False)
    monkeypatch.setattr("backend.runtime.agent_registry.agent_registry", FakeAgentRegistry(), raising=False)

    response = await mod.get_snapshot()

    assert response.system_status == "degraded"
    assert response.active_missions == 1
    assert response.active_voice == 2
    assert response.total_memories == 35
    assert response.llm_provider == "Azure"
    assert response.current_mission is not None
    assert response.current_mission.execution_id == "exec-running"
    assert len(response.health_matrix) == 6
    assert len(response.autonomy) == 5


@pytest.mark.asyncio
async def test_get_snapshot_falls_back_from_audit_only(monkeypatch, executive_audit_entries):
    from backend.api import executive_routes as mod
    from backend.safety.audit_logger import audit_logger

    monkeypatch.setattr(audit_logger, "get_all", lambda limit=500: executive_audit_entries)

    response = await mod.get_snapshot()

    assert response.current_mission is not None
    assert response.current_mission.stage in {"completed", "running"}
    assert response.active_missions >= 0


@pytest.mark.asyncio
async def test_get_analytics_builds_series(monkeypatch, executive_audit_entries):
    from backend.api import executive_routes as mod
    from backend.safety.audit_logger import audit_logger

    monkeypatch.setattr(audit_logger, "get_all", lambda limit=2000: executive_audit_entries)

    response = await mod.get_analytics()

    assert len(response.series) == 7
    assert response.totals["missions"] >= 1
    assert response.totals["tool_calls"] >= 1
    assert response.totals["voice_sessions"] >= 1
    assert response.totals["memory_ops"] >= 1