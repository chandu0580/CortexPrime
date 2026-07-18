from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.learning.engine import LearningEngine
from backend.learning.models import (
    LearningContext,
    LearningResult,
    LearningSession,
    Pattern,
    Recommendation,
)


@pytest.fixture
def mock_detector():
    d = MagicMock()
    d.detect_all = AsyncMock(return_value=[])
    d.detect_mission_patterns = AsyncMock(return_value=[])
    d.detect_execution_patterns = AsyncMock(return_value=[])
    d.detect_connector_patterns = AsyncMock(return_value=[])
    d.detect_governance_patterns = AsyncMock(return_value=[])
    return d


@pytest.fixture
def mock_recommender():
    r = MagicMock()
    r.generate_all = AsyncMock(return_value=[])
    r.generate_for_mission = AsyncMock(return_value=[])
    r.generate_for_execution = AsyncMock(return_value=[])
    r.generate_for_connector = AsyncMock(return_value=[])
    r.generate_for_governance = AsyncMock(return_value=[])
    return r


@pytest.fixture
def mock_events():
    pub = MagicMock()
    pub.publish = AsyncMock()
    return pub


@pytest.fixture
def engine(mock_detector, mock_recommender, mock_events):
    return LearningEngine(
        detector=mock_detector,
        recommender=mock_recommender,
        events=mock_events,
    )


# ---------------------------------------------------------------------------
# run_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_session_no_patterns(engine, mock_detector, mock_recommender, mock_events):
    mock_detector.detect_all.return_value = []
    mock_recommender.generate_all.return_value = []
    session = LearningSession(
        session_id="ls-test",
        mission_type="general",
        status="active",
        metadata={},
    )
    result = await engine.run_session(session)
    assert isinstance(result, LearningResult)
    assert result.session_id == "ls-test"
    assert len(result.patterns_found) == 0
    assert len(result.recommendations) == 0
    assert result.score == 0.0
    assert mock_events.publish.called


@pytest.mark.asyncio
async def test_run_session_with_patterns(engine, mock_detector, mock_recommender, mock_events):
    pattern = Pattern(name="fail-1", description="desc", category="mission", confidence=0.8, occurrences=3)
    mock_detector.detect_all.return_value = [pattern]
    rec = Recommendation(category="performance", title="Review", priority="high")
    mock_recommender.generate_all.return_value = [rec]
    session = LearningSession(session_id="ls-patterns", mission_type="general", status="active")
    result = await engine.run_session(session)
    assert len(result.patterns_found) == 1
    assert len(result.recommendations) == 1
    assert result.score > 0


@pytest.mark.asyncio
async def test_run_session_with_context_mission_source(engine, mock_detector, mock_recommender):
    mock_detector.detect_mission_patterns.return_value = [
        Pattern(name="m1", description="m1 desc", category="mission", confidence=0.9, occurrences=2),
    ]
    mock_recommender.generate_all.return_value = []
    session = LearningSession(session_id="ls-context", mission_type="mission", status="active")
    context = LearningContext(mission_id="mis-1", source="mission_runtime")
    result = await engine.run_session(session, context)
    assert len(result.patterns_found) == 1
    assert result.patterns_found[0].name == "m1"


# ---------------------------------------------------------------------------
# Mission analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_mission_analysis(engine, mock_detector, mock_recommender):
    mock_detector.detect_mission_patterns.return_value = [
        Pattern(name="mp1", description="pat", category="mission", confidence=0.7, occurrences=1),
    ]
    mock_recommender.generate_all.return_value = []
    mock_recommender.generate_for_mission.return_value = [
        Recommendation(category="performance", title="Mission rec", priority="high"),
    ]
    result = await engine.run_mission_analysis({"mission_id": "mis-1", "title": "test"})
    assert isinstance(result, LearningResult)
    assert len(result.patterns_found) >= 1
    assert len(result.recommendations) >= 1


# ---------------------------------------------------------------------------
# Execution analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_execution_analysis(engine, mock_detector, mock_recommender):
    mock_detector.detect_execution_patterns.return_value = [
        Pattern(name="ep1", description="pat", category="execution", confidence=0.6, occurrences=2),
    ]
    mock_recommender.generate_for_execution.return_value = [
        Recommendation(category="retry", title="Retry", priority="medium"),
    ]
    result = await engine.run_execution_analysis({"execution_id": "exec-1", "status": "failed"})
    assert len(result.patterns_found) >= 1
    assert len(result.recommendations) >= 1


# ---------------------------------------------------------------------------
# Connector analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_connector_analysis(engine, mock_detector, mock_recommender):
    mock_detector.detect_connector_patterns.return_value = [
        Pattern(name="cp1", description="pat", category="connector", confidence=0.8, occurrences=5),
    ]
    mock_recommender.generate_for_connector.return_value = [
        Recommendation(category="connector", title="Investigate", priority="high"),
    ]
    result = await engine.run_connector_analysis({"connector_id": "conn-1", "failure_rate": 0.5})
    assert len(result.patterns_found) >= 1
    assert len(result.recommendations) >= 1


# ---------------------------------------------------------------------------
# Governance analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_governance_analysis(engine, mock_detector, mock_recommender):
    mock_detector.detect_governance_patterns.return_value = [
        Pattern(name="gp1", description="pat", category="governance", confidence=0.9, occurrences=3),
    ]
    mock_recommender.generate_for_governance.return_value = [
        Recommendation(category="governance", title="Review policy", priority="high"),
    ]
    result = await engine.run_governance_analysis({"decision_id": "dec-1", "decision": "DENY"})
    assert len(result.patterns_found) >= 1
    assert len(result.recommendations) >= 1


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_score_no_patterns_no_recs(engine):
    score = engine._compute_score([], [])
    assert score == 0.0


@pytest.mark.asyncio
async def test_compute_score_with_patterns(engine):
    patterns = [Pattern(name="p1", confidence=0.8), Pattern(name="p2", confidence=0.6)]
    score = engine._compute_score(patterns, [])
    assert score == pytest.approx(0.49, rel=0.1)


@pytest.mark.asyncio
async def test_compute_score_with_patterns_and_recs(engine):
    patterns = [Pattern(name="p1", confidence=0.9)]
    recs = [Recommendation(category="test", title="r1")]
    score = engine._compute_score(patterns, recs)
    assert score > 0.5


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_published(engine, mock_events):
    mock_detector = engine._detector
    mock_detector.detect_all.return_value = [
        Pattern(name="p1", description="d", category="mission", confidence=0.5, occurrences=1),
    ]
    session = LearningSession(session_id="ls-events", mission_type="general", status="active")
    await engine.run_session(session)
    assert mock_events.publish.called
