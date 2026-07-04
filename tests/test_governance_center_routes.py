from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def _iso_utc(delta: timedelta = timedelta()) -> str:
    return (datetime.now(timezone.utc) - delta).isoformat()


@pytest.fixture
def audit_entries() -> list[dict]:
    return [
        {
            "audit_id": "a-1",
            "timestamp": _iso_utc(timedelta(hours=1)),
            "action": "mission_start",
            "outcome": "approved",
            "risk_level": "low",
            "agent": "orchestrator",
            "reason": "ok",
            "execution_id": "exec-1",
            "target": "mission",
        },
        {
            "audit_id": "a-2",
            "timestamp": _iso_utc(timedelta(hours=2)),
            "action": "tool_browser_open",
            "outcome": "blocked",
            "risk_level": "high",
            "agent": "browser_agent",
            "reason": "blocked by policy",
            "execution_id": "exec-1",
            "target": "browser",
        },
        {
            "audit_id": "a-3",
            "timestamp": _iso_utc(timedelta(days=3)),
            "action": "memory_recall",
            "outcome": "approved",
            "risk_level": "medium",
            "agent": "memory",
            "reason": "allowed",
            "execution_id": "exec-2",
            "target": "memory",
        },
        {
            "audit_id": "a-4",
            "timestamp": _iso_utc(timedelta(days=10)),
            "action": "response_release",
            "outcome": "timed_out",
            "risk_level": "critical",
            "agent": "critic",
            "reason": "timeout",
            "execution_id": "exec-3",
            "target": "response",
        },
    ]


def test_governance_helper_classifiers():
    from backend.api import governance_center_routes as mod

    assert mod._risk_score_to_level(0.9) == "critical"
    assert mod._risk_score_to_level(0.7) == "high"
    assert mod._risk_score_to_level(0.4) == "medium"
    assert mod._risk_score_to_level(0.1) == "low"

    assert mod._compliance_grade(95) == "A+"
    assert mod._compliance_grade(86) == "A"
    assert mod._compliance_grade(79) == "B+"
    assert mod._compliance_grade(71) == "B"
    assert mod._compliance_grade(61) == "C"
    assert mod._compliance_grade(10) == "D"

    assert mod._ts("not-a-date") == 0.0
    assert mod._ts(_iso_utc()) > 0


def test_build_pipeline_maps_statuses(audit_entries):
    from backend.api import governance_center_routes as mod

    stages = mod._build_pipeline(
        audit_entries,
        {
            "total_blocked": 1,
            "total_checked": 4,
            "total_warned": 1,
            "recent_violations": [{"timestamp": datetime.now(timezone.utc).timestamp()}],
        },
        pending_approvals=2,
    )

    by_id = {stage.id: stage for stage in stages}
    assert by_id["input_validation"].status == "blocked"
    assert by_id["input_validation"].count == 4
    assert by_id["tool_approval"].status == "blocked"
    assert by_id["execution_approval"].status == "approved"
    assert by_id["output_validation"].status == "warned"


@pytest.mark.asyncio
async def test_get_overview_aggregates(monkeypatch, audit_entries):
    from backend.api import governance_center_routes as mod
    from backend.runtime.agent_registry import agent_registry
    from backend.safety.approval_queue import approval_queue
    from backend.safety.audit_logger import audit_logger
    from backend.safety.emergency_stop import emergency_stop
    from backend.safety.guardrails_engine import guardrails_engine

    monkeypatch.setattr(audit_logger, "get_all", lambda limit=500: audit_entries)
    monkeypatch.setattr(
        guardrails_engine.telemetry,
        "snapshot",
        lambda recent_n=20: {
            "total_blocked": 2,
            "total_warned": 1,
            "block_rate": 0.1,
            "recent_violations": [{"timestamp": datetime.now(timezone.utc).timestamp()}],
        },
    )
    monkeypatch.setattr(approval_queue, "get_pending", lambda: [{"id": "p-1"}])
    monkeypatch.setattr(emergency_stop, "is_active", lambda: True, raising=False)
    monkeypatch.setattr(
        agent_registry,
        "get_all",
        lambda: [SimpleNamespace(status="active"), SimpleNamespace(status="idle")],
        raising=False,
    )

    response = await mod.get_overview()

    assert response.active_missions == 1
    assert response.blocked_today == 1
    assert response.approved_today == 1
    assert response.guardrail_hits == 3
    assert response.emergency_stop is True
    assert response.compliance_score > 0
    assert len(response.pipeline) == 6


@pytest.mark.asyncio
async def test_get_risk_builds_buckets_and_series(monkeypatch, audit_entries):
    from backend.api import governance_center_routes as mod
    from backend.safety.audit_logger import audit_logger

    monkeypatch.setattr(audit_logger, "get_all", lambda limit=2000: audit_entries)

    response = await mod.get_risk("30d")

    assert response.today.total == 2
    assert response.seven_day.total == 3
    assert response.thirty_day.total == 4
    assert len(response.series) == 30
    assert any(day["critical"] == 1 for day in response.series)


@pytest.mark.asyncio
async def test_get_events_merges_and_filters(monkeypatch, audit_entries):
    from backend.api import governance_center_routes as mod
    from backend.safety.audit_logger import audit_logger
    from backend.safety.guardrails_engine import guardrails_engine

    monkeypatch.setattr(audit_logger, "get_all", lambda limit=100: audit_entries)

    snapshots = iter(
        [
            {
                "recent_violations": [
                    {
                        "timestamp": datetime.now(timezone.utc).timestamp(),
                        "violation_type": "prompt_injection",
                        "matched_rule": "jailbreak",
                        "text_preview": "ignore system prompt",
                    }
                ]
            },
            {"by_violation": {"prompt_injection": 1}},
        ]
    )
    monkeypatch.setattr(guardrails_engine.telemetry, "snapshot", lambda recent_n=50: next(snapshots))

    response = await mod.get_events(limit=10, event_type="tool_blocked", decision="blocked")

    assert response.total == 1
    assert response.events[0].event_type == "tool_blocked"
    assert response.events[0].decision == "blocked"
    assert response.guardrail_summary == {"prompt_injection": 1}


@pytest.mark.asyncio
async def test_get_compliance_scores(monkeypatch, audit_entries):
    from backend.api import governance_center_routes as mod
    from backend.safety.audit_logger import audit_logger
    from backend.safety.guardrails_engine import guardrails_engine

    monkeypatch.setattr(audit_logger, "get_all", lambda limit=1000: audit_entries)
    monkeypatch.setattr(
        guardrails_engine.telemetry,
        "snapshot",
        lambda recent_n=5: {"block_rate": 0.1, "total_blocked": 2, "total_warned": 1},
    )

    response = await mod.get_compliance()

    assert response.overall > 0
    assert response.grade in {"A+", "A", "B+", "B", "C", "D"}
    assert [category.label for category in response.categories] == [
        "Safety Score",
        "Policy Score",
        "Governance Score",
    ]


@pytest.mark.asyncio
async def test_get_governance_replay_merges_replay_and_audit(monkeypatch):
    from backend.api import governance_center_routes as mod
    from backend.safety.audit_logger import audit_logger
    from backend.services.mission_replay_store import replay_store

    raw_events = [
        {
            "event_type": "mission_started",
            "event_ts": _iso_utc(timedelta(seconds=5)),
            "agent": "system",
            "message": "mission started",
            "status": "completed",
            "payload": {"reason": "accepted"},
        },
        {
            "event_type": "tool_failed",
            "event_ts": _iso_utc(timedelta(seconds=4)),
            "agent": "browser_agent",
            "message": "browser open failed",
            "status": "failed",
            "payload": '{"reason": "blocked"}',
        },
        {
            "event_type": "response_generated",
            "event_ts": _iso_utc(timedelta(seconds=3)),
            "agent": "orchestrator",
            "message": "response generated",
            "status": "warning",
            "payload": {},
        },
    ]
    audit_events = [
        {
            "timestamp": _iso_utc(timedelta(seconds=2)),
            "action": "memory_access",
            "outcome": "approved",
            "risk_level": "low",
            "agent": "memory",
            "reason": "ok",
        }
    ]

    monkeypatch.setattr(replay_store, "get_events", lambda execution_id: pytest.raises(Exception))
    async def _get_events(execution_id: str):
        return raw_events
    monkeypatch.setattr(replay_store, "get_events", _get_events)
    monkeypatch.setattr(audit_logger, "get_by_execution", lambda execution_id: audit_events)

    response = await mod.get_governance_replay("exec-42")

    assert response.execution_id == "exec-42"
    assert response.total_events == 4
    assert response.summary["approved"] == 2
    assert response.summary["blocked"] == 1
    assert response.summary["warned"] == 1
    assert response.events[0].stage == "input_validation"
    assert response.events[-1].stage in {"memory_approval", "output_validation"}