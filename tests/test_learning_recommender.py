from __future__ import annotations

import pytest

from backend.learning.models import Pattern, Recommendation
from backend.learning.recommender import RecommendationEngine


@pytest.fixture
def engine():
    return RecommendationEngine()


# ---------------------------------------------------------------------------
# Pattern-based recommendations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_all_empty(engine):
    recs = await engine.generate_all([])
    assert len(recs) == 0


@pytest.mark.asyncio
async def test_generate_all_repeated_failure(engine):
    patterns = [
        Pattern(
            name="repeated_failures_alice",
            description="",
            category="mission",
            confidence=0.8,
            occurrences=4,
            pattern_data={"type": "repeated_failure", "owner": "alice", "failure_count": 4},
        ),
    ]
    recs = await engine.generate_all(patterns)
    assert len(recs) >= 1
    assert recs[0].category == "performance"
    assert "alice" in recs[0].title


@pytest.mark.asyncio
async def test_generate_all_connector_reliability(engine):
    patterns = [
        Pattern(
            name="connector_reliability_github",
            description="",
            category="connector",
            confidence=0.9,
            occurrences=5,
            pattern_data={"type": "connector_reliability", "connector_type": "github", "failure_rate": 0.6, "failed": 5, "total": 8},
        ),
    ]
    recs = await engine.generate_all(patterns)
    assert len(recs) >= 1
    assert recs[0].category == "connector"


@pytest.mark.asyncio
async def test_generate_all_approval_bottleneck(engine):
    patterns = [
        Pattern(
            name="approval_bottleneck",
            description="",
            category="governance",
            confidence=0.7,
            occurrences=8,
            pattern_data={"type": "approval_bottleneck", "total": 10, "pending": 8},
        ),
    ]
    recs = await engine.generate_all(patterns)
    assert len(recs) >= 1
    assert recs[0].category == "approval"


@pytest.mark.asyncio
async def test_generate_all_retry_frequency(engine):
    patterns = [
        Pattern(
            name="high_retry_frequency",
            description="",
            category="execution",
            confidence=0.6,
            occurrences=12,
            pattern_data={"type": "retry_frequency", "total": 50, "retried": 12},
        ),
    ]
    recs = await engine.generate_all(patterns)
    assert len(recs) >= 1
    assert recs[0].category == "retry"


@pytest.mark.asyncio
async def test_generate_all_policy_violation(engine):
    patterns = [
        Pattern(
            name="frequent_policy_violations",
            description="",
            category="governance",
            confidence=0.8,
            occurrences=5,
            pattern_data={"type": "policy_violation", "total": 20, "violations": 5},
        ),
    ]
    recs = await engine.generate_all(patterns)
    assert len(recs) >= 1
    assert recs[0].category == "governance"


@pytest.mark.asyncio
async def test_generate_all_completion_trend_high_failure(engine):
    patterns = [
        Pattern(
            name="high_mission_failure_rate",
            description="",
            category="mission",
            confidence=0.9,
            occurrences=10,
            pattern_data={"type": "completion_trend", "total": 20, "failed": 10, "failure_rate": 0.5},
        ),
    ]
    recs = await engine.generate_all(patterns)
    assert len(recs) >= 1
    assert recs[0].priority == "critical"


# ---------------------------------------------------------------------------
# Domain-specific recommendations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_for_mission_failed(engine):
    recs = await engine.generate_for_mission({"mission_id": "m1", "title": "test", "status": "failed", "owner": "alice"})
    assert len(recs) >= 1
    assert recs[0].category == "performance"


@pytest.mark.asyncio
async def test_generate_for_mission_high_retry(engine):
    recs = await engine.generate_for_mission({"mission_id": "m2", "retry_count": 3, "status": "completed"})
    assert len(recs) >= 1
    assert recs[0].category == "retry"


@pytest.mark.asyncio
async def test_generate_for_mission_ok(engine):
    recs = await engine.generate_for_mission({"mission_id": "m3", "status": "completed", "retry_count": 0})
    assert len(recs) == 0


@pytest.mark.asyncio
async def test_generate_for_execution_failed(engine):
    recs = await engine.generate_for_execution({"execution_id": "e1", "status": "failed", "error": "timeout", "agent": "agent1"})
    assert len(recs) >= 1
    assert recs[0].category == "retry"


@pytest.mark.asyncio
async def test_generate_for_execution_ok(engine):
    recs = await engine.generate_for_execution({"execution_id": "e2", "status": "completed"})
    assert len(recs) == 0


@pytest.mark.asyncio
async def test_generate_for_connector_high_failure(engine):
    recs = await engine.generate_for_connector({"connector_id": "c1", "name": "gh", "connector_type": "github", "failure_rate": 0.5, "failed": 5, "total": 10})
    assert len(recs) >= 1
    assert recs[0].category == "connector"


@pytest.mark.asyncio
async def test_generate_for_connector_low_failure(engine):
    recs = await engine.generate_for_connector({"connector_id": "c2", "failure_rate": 0.1})
    assert len(recs) == 0


@pytest.mark.asyncio
async def test_generate_for_governance_denied(engine):
    recs = await engine.generate_for_governance({"decision_id": "d1", "decision": "DENY", "policy_name": "test-policy", "reason": "not allowed", "resource_type": "mission", "resource_id": "r1", "action": "execute"})
    assert len(recs) >= 1
    assert recs[0].category == "governance"


@pytest.mark.asyncio
async def test_generate_for_governance_allowed(engine):
    recs = await engine.generate_for_governance({"decision_id": "d2", "decision": "ALLOW"})
    assert len(recs) == 0
