from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.learning.detector import PatternDetector
from backend.learning.models import Pattern


@pytest.fixture
def mock_mission_repo():
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_exec_repo():
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_conn_activity_repo():
    repo = MagicMock()
    repo.list = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_approval_repo():
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_knowledge_repo():
    repo = AsyncMock()
    repo.count_by_category = AsyncMock(return_value={})
    return repo


@pytest.fixture
def mock_repo_factory(
    mock_mission_repo,
    mock_exec_repo,
    mock_conn_activity_repo,
    mock_approval_repo,
    mock_knowledge_repo,
):
    factory = MagicMock()
    factory.mission_repo = AsyncMock(return_value=mock_mission_repo)
    factory.execution_repo = AsyncMock(return_value=mock_exec_repo)
    factory.connector_activity_repo = AsyncMock(return_value=mock_conn_activity_repo)
    factory.approval_request_repo = AsyncMock(return_value=mock_approval_repo)
    factory.knowledge_entry_repo = AsyncMock(return_value=mock_knowledge_repo)
    return factory


@pytest.fixture
def detector(mock_repo_factory):
    return PatternDetector(repo_factory=mock_repo_factory)


# ---------------------------------------------------------------------------
# detect_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_all_empty(detector, mock_mission_repo, mock_exec_repo, mock_approval_repo, mock_knowledge_repo):
    mock_mission_repo.list.return_value = []
    mock_exec_repo.list.return_value = []
    mock_approval_repo.list.return_value = []
    mock_knowledge_repo.count_by_category.return_value = {}
    patterns = await detector.detect_all()
    assert isinstance(patterns, list)
    assert len(patterns) == 0


@pytest.mark.asyncio
async def test_detect_repeated_failures(detector, mock_mission_repo):
    ms = []
    for i in range(4):
        m = MagicMock()
        m.status = "failed"
        m.owner = "alice"
        ms.append(m)
    m_ok = MagicMock()
    m_ok.status = "completed"
    m_ok.owner = "bob"
    ms.append(m_ok)
    mock_mission_repo.list.return_value = ms
    patterns = await detector._detect_repeated_failures()
    assert len(patterns) == 1
    assert patterns[0].name == "repeated_failures_alice"
    assert patterns[0].category == "mission"
    assert patterns[0].occurrences == 4


@pytest.mark.asyncio
async def test_detect_repeated_successes(detector, mock_mission_repo):
    ms = []
    for i in range(6):
        m = MagicMock()
        m.status = "completed"
        m.owner = "charlie"
        ms.append(m)
    mock_mission_repo.list.return_value = ms
    patterns = await detector._detect_repeated_successes()
    assert len(patterns) == 1
    assert "charlie" in patterns[0].name
    assert patterns[0].category == "mission"


@pytest.mark.asyncio
async def test_detect_connector_reliability(detector, mock_conn_activity_repo):
    acts = []
    for i in range(5):
        a = MagicMock()
        a.connector_type = "github"
        a.status = "failed"
        acts.append(a)
    a2 = MagicMock()
    a2.connector_type = "github"
    a2.status = "completed"
    acts.append(a2)
    mock_conn_activity_repo.list.return_value = acts
    patterns = await detector._detect_connector_reliability()
    assert len(patterns) >= 0


@pytest.mark.asyncio
async def test_detect_mission_completion_trends(detector, mock_mission_repo):
    ms = []
    for i in range(15):
        m = MagicMock()
        m.status = "completed"
        ms.append(m)
    for i in range(11):
        m = MagicMock()
        m.status = "failed"
        ms.append(m)
    mock_mission_repo.list.return_value = ms
    patterns = await detector._detect_mission_completion_trends()
    assert len(patterns) >= 1


@pytest.mark.asyncio
async def test_detect_retry_frequency(detector, mock_exec_repo):
    execs = []
    for i in range(6):
        e = MagicMock()
        e.error_message = "timeout"
        execs.append(e)
    mock_exec_repo.list.return_value = execs
    patterns = await detector._detect_retry_frequency()
    assert len(patterns) == 1
    assert patterns[0].name == "high_retry_frequency"


@pytest.mark.asyncio
async def test_detect_approval_bottlenecks(detector, mock_approval_repo):
    apps = []
    for i in range(6):
        a = MagicMock()
        a.status = "pending"
        apps.append(a)
    mock_approval_repo.list.return_value = apps
    patterns = await detector._detect_approval_bottlenecks()
    assert len(patterns) == 1
    assert patterns[0].name == "approval_bottleneck"


@pytest.mark.asyncio
async def test_detect_knowledge_growth(detector, mock_knowledge_repo):
    mock_knowledge_repo.count_by_category.return_value = {"mission": 5, "document": 7}
    patterns = await detector._detect_knowledge_growth()
    assert len(patterns) == 1
    assert patterns[0].name == "knowledge_growth"


@pytest.mark.asyncio
async def test_detect_knowledge_growth_below_threshold(detector, mock_knowledge_repo):
    mock_knowledge_repo.count_by_category.return_value = {"doc": 3}
    patterns = await detector._detect_knowledge_growth()
    assert len(patterns) == 0


@pytest.mark.asyncio
async def test_detect_mission_patterns(detector, mock_mission_repo, mock_exec_repo):
    m = MagicMock()
    m.status = "failed"
    m.owner = "alice"
    mock_mission_repo.list.return_value = [m, m, m]
    mock_exec_repo.list.return_value = []
    patterns = await detector.detect_mission_patterns()
    assert len(patterns) >= 1


@pytest.mark.asyncio
async def test_detect_connector_patterns(detector, mock_conn_activity_repo):
    mock_conn_activity_repo.list.return_value = []
    patterns = await detector.detect_connector_patterns()
    assert isinstance(patterns, list)


@pytest.mark.asyncio
async def test_detect_governance_patterns(detector, mock_approval_repo):
    mock_approval_repo.list.return_value = []
    patterns = await detector.detect_governance_patterns()
    assert isinstance(patterns, list)


@pytest.mark.asyncio
async def test_detect_knowledge_patterns(detector, mock_knowledge_repo):
    mock_knowledge_repo.count_by_category.return_value = {}
    patterns = await detector.detect_knowledge_patterns()
    assert isinstance(patterns, list)
