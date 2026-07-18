from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.learning.models import (
    LearningResult,
    LearningSession,
    Pattern,
    Recommendation,
)
from backend.learning.service import LearningService


@pytest.fixture
def mock_pattern_repo():
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.list_by_category = AsyncMock(return_value=[])
    repo.list_high_confidence = AsyncMock(return_value=[])
    repo.get = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_session_repo():
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.list_by_mission_type = AsyncMock(return_value=[])
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_repo_factory(mock_pattern_repo, mock_session_repo):
    factory = MagicMock()
    factory.learning_pattern_repo = AsyncMock(return_value=mock_pattern_repo)
    factory.learning_session_repo = AsyncMock(return_value=mock_session_repo)
    return factory


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.run_session = AsyncMock(return_value=LearningResult(
        session_id="ls-test", patterns_found=[], recommendations=[],
        score=0.5, summary="test",
    ))
    engine.run_mission_analysis = AsyncMock(return_value=LearningResult(
        session_id="ls-mission", patterns_found=[], recommendations=[], score=0.7, summary="mission analysis",
    ))
    engine.run_execution_analysis = AsyncMock(return_value=LearningResult(
        session_id="ls-exec", patterns_found=[], recommendations=[], score=0.6, summary="exec analysis",
    ))
    engine.run_connector_analysis = AsyncMock(return_value=LearningResult(
        session_id="ls-conn", patterns_found=[], recommendations=[], score=0.8, summary="conn analysis",
    ))
    engine.run_governance_analysis = AsyncMock(return_value=LearningResult(
        session_id="ls-gov", patterns_found=[], recommendations=[], score=0.9, summary="gov analysis",
    ))
    return engine


@pytest.fixture
def service(mock_repo_factory, mock_engine):
    return LearningService(engine=mock_engine, repo_factory=mock_repo_factory)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_session(service):
    session = await service.start_session(mission_type="test", metadata={"key": "val"})
    assert session.mission_type == "test"
    assert session.metadata == {"key": "val"}
    assert session.status == "active"


@pytest.mark.asyncio
async def test_run_full_analysis(service, mock_engine):
    session = LearningSession(session_id="ls-test", mission_type="general", status="active")
    result = await service.run_full_analysis(session)
    assert result.session_id == "ls-test"
    mock_engine.run_session.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_mission(service, mock_engine):
    result = await service.analyze_mission({"mission_id": "mis-1", "title": "test"})
    assert result.session_id == "ls-mission"
    mock_engine.run_mission_analysis.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_execution(service, mock_engine):
    result = await service.analyze_execution({"execution_id": "exec-1", "status": "failed"})
    assert result.session_id == "ls-exec"
    mock_engine.run_execution_analysis.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_connector(service, mock_engine):
    result = await service.analyze_connector({"connector_id": "conn-1", "failure_rate": 0.5})
    assert result.session_id == "ls-conn"
    mock_engine.run_connector_analysis.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_governance(service, mock_engine):
    result = await service.analyze_governance({"decision_id": "dec-1", "decision": "DENY"})
    assert result.session_id == "ls-gov"
    mock_engine.run_governance_analysis.assert_called_once()


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_patterns(service, mock_pattern_repo):
    pid = uuid.uuid4()
    m = MagicMock()
    m.id = pid
    m.name = "test-pattern"
    m.description = "desc"
    m.category = "mission"
    m.confidence = 0.8
    m.occurrences = 5
    m.pattern_data = {}
    m.is_active = True
    m.created_at = None
    m.updated_at = None
    mock_pattern_repo.list.return_value = [m]
    patterns = await service.list_patterns()
    assert len(patterns) == 1
    assert patterns[0].name == "test-pattern"
    assert patterns[0].category == "mission"


@pytest.mark.asyncio
async def test_list_patterns_by_category(service, mock_pattern_repo):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.name = "p1"
    m.description = ""
    m.category = "execution"
    m.confidence = 0.5
    m.occurrences = 2
    m.pattern_data = {}
    m.is_active = True
    m.created_at = None
    m.updated_at = None
    mock_pattern_repo.list_by_category.return_value = [m]
    patterns = await service.list_patterns(category="execution")
    assert len(patterns) == 1
    assert patterns[0].category == "execution"


@pytest.mark.asyncio
async def test_get_pattern_found(service, mock_pattern_repo):
    pid = uuid.uuid4()
    m = MagicMock()
    m.id = pid
    m.name = "found"
    m.description = ""
    m.category = "mission"
    m.confidence = 0.9
    m.occurrences = 1
    m.pattern_data = {}
    m.is_active = True
    m.created_at = None
    m.updated_at = None
    mock_pattern_repo.get.return_value = m
    p = await service.get_pattern(str(pid))
    assert p is not None
    assert p.name == "found"


@pytest.mark.asyncio
async def test_get_pattern_not_found(service, mock_pattern_repo):
    mock_pattern_repo.get.return_value = None
    p = await service.get_pattern(str(uuid.uuid4()))
    assert p is None


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_statistics(service, mock_pattern_repo, mock_session_repo):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.name = "p1"
    m.description = ""
    m.category = "mission"
    m.confidence = 0.9
    m.occurrences = 3
    m.pattern_data = {}
    m.is_active = True
    m.created_at = None
    m.updated_at = None
    mock_pattern_repo.list.return_value = [m]
    mock_session_repo.list.return_value = []
    stats = await service.get_statistics()
    assert stats["total_patterns"] == 1
    assert "mission" in stats["patterns_by_category"]


@pytest.mark.asyncio
async def test_get_statistics_empty(service, mock_pattern_repo, mock_session_repo):
    mock_pattern_repo.list.return_value = []
    mock_session_repo.list.return_value = []
    stats = await service.get_statistics()
    assert stats["total_patterns"] == 0
    assert stats["total_sessions"] == 0


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(service, mock_pattern_repo, mock_session_repo):
    mock_pattern_repo.list.return_value = []
    mock_session_repo.list.return_value = []
    h = await service.health()
    assert h["status"] == "healthy"
    assert h["service"] == "learning_runtime"


@pytest.mark.asyncio
async def test_health_degraded(service):
    svc = LearningService(engine=None, repo_factory=MagicMock())
    svc._repo_factory.learning_pattern_repo = AsyncMock(side_effect=Exception("db down"))
    h = await svc.health()
    assert h["status"] == "degraded"


# ---------------------------------------------------------------------------
# Sessions list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions(service, mock_session_repo):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.session_id = "ls-1"
    m.mission_type = "general"
    m.status = "completed"
    m.outcome = "completed"
    m.score = 0.8
    m.patterns_extracted = []
    m.lessons_learned = []
    m.metadata_ = {}
    m.created_at = None
    m.updated_at = None
    mock_session_repo.list.return_value = [m]
    sessions = await service.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == "ls-1"


@pytest.mark.asyncio
async def test_list_sessions_by_mission_type(service, mock_session_repo):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.session_id = "ls-2"
    m.mission_type = "connector"
    m.status = "completed"
    m.outcome = "completed"
    m.score = 0.9
    m.patterns_extracted = []
    m.lessons_learned = []
    m.metadata_ = {}
    m.created_at = None
    m.updated_at = None
    mock_session_repo.list_by_mission_type.return_value = [m]
    sessions = await service.list_sessions(mission_type="connector")
    assert len(sessions) == 1
    assert sessions[0].mission_type == "connector"
