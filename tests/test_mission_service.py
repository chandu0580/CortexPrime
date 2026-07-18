from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mission.models import MissionEntity, MissionPriority, MissionStatus, MissionTimeline, MissionType
from backend.mission.service import MissionService


def _make_model_mock(
    id: uuid.UUID,
    title: str = "Test Mission",
    objective: str = "Test objective",
    status: str = "CREATED",
    priority: int = 3,
    category: str = "standard",
    owner: str = "tester",
    context: dict | None = None,
    created_at=None,
    started_at=None,
    completed_at=None,
):
    return MagicMock(
        id=id,
        title=title,
        objective=objective,
        status=status,
        priority=priority,
        category=category,
        owner=owner,
        context=context or {},
        created_at=created_at or datetime.now(timezone.utc),
        started_at=started_at,
        completed_at=completed_at,
    )


@pytest.fixture
def model_id():
    return uuid.uuid4()


@pytest.fixture
def created_model(model_id):
    return _make_model_mock(model_id, status="CREATED")


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.search = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_repo_factory(mock_repo):
    factory = MagicMock()
    factory.mission_repo = AsyncMock(return_value=mock_repo)
    return factory


@pytest.fixture(autouse=True)
def _setup_service(mock_repo_factory):
    global service
    service = MissionService(repo_factory=mock_repo_factory)


service: MissionService


def _make_created(mock_repo, model_id, **kw):
    mock_repo.get.return_value = _make_model_mock(model_id, status="CREATED", **kw)
    mock_repo.create.return_value = _make_model_mock(model_id, status="CREATED", **kw)


@pytest.mark.asyncio
async def test_create_mission(mock_repo, model_id):
    mock_repo.create.return_value = _make_model_mock(model_id, title="Test Mission",
                                                      objective="Test the mission runtime", owner="test-user")

    entity = await service.create_mission(
        title="Test Mission",
        objective="Test the mission runtime",
        priority=MissionPriority.MEDIUM,
        mission_type=MissionType.STANDARD,
        owner="test-user",
        created_by="test-user",
    )
    assert entity.title == "Test Mission"
    assert entity.objective == "Test the mission runtime"
    assert entity.status == MissionStatus.CREATED
    assert entity.metadata.correlation_id is not None
    assert entity.ownership is not None
    assert entity.ownership.owner == "test-user"


@pytest.mark.asyncio
async def test_create_and_plan(mock_repo, model_id):
    _make_created(mock_repo, model_id, title="Plan Test", objective="Test planning")

    entity = await service.create_mission(
        title="Plan Test", objective="Test planning", owner="tester",
    )
    entity = await service.plan_mission(entity.id, actor="tester")
    assert entity is not None
    assert entity.status == MissionStatus.PLANNING

    plan = await service.get_plan(entity.id)
    assert plan is not None
    assert len(plan.steps) == 4


@pytest.mark.asyncio
async def test_cancel_mission(mock_repo, model_id):
    _make_created(mock_repo, model_id, title="Cancel Test", objective="Test cancel")

    entity = await service.create_mission(
        title="Cancel Test", objective="Test cancellation", owner="tester",
    )
    entity = await service.cancel_mission(entity.id, reason="No longer needed", actor="tester")
    assert entity is not None
    assert entity.status == MissionStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_from_planning(mock_repo, model_id):
    _make_created(mock_repo, model_id, title="Cancel During Planning",
                   objective="Test cancel from planning")

    entity = await service.create_mission(
        title="Cancel During Planning", objective="Test cancel from planning", owner="tester",
    )
    entity = await service.plan_mission(entity.id, actor="tester")
    entity = await service.cancel_mission(entity.id, reason="Changed mind", actor="tester")
    assert entity is not None
    assert entity.status == MissionStatus.CANCELLED


@pytest.mark.asyncio
async def test_invalid_transition_execute_from_created(mock_repo, model_id):
    _make_created(mock_repo, model_id, title="Invalid", objective="Test")

    entity = await service.create_mission(
        title="Invalid Transition", objective="Test invalid transition", owner="tester",
    )
    with pytest.raises(ValueError, match="Cannot execute"):
        await service.execute_mission(entity.id, actor="tester")


@pytest.mark.asyncio
async def test_get_nonexistent_mission(mock_repo):
    mock_repo.get.return_value = None
    entity = await service.get_mission(uuid.uuid4())
    assert entity is None


@pytest.mark.asyncio
async def test_full_lifecycle(mock_repo, model_id):
    _make_created(mock_repo, model_id, title="Lifecycle", objective="Test lifecycle")

    entity = await service.create_mission(
        title="Full Lifecycle", objective="Test full lifecycle",
        owner="tester", created_by="tester",
    )
    assert entity.status == MissionStatus.CREATED

    entity = await service.plan_mission(entity.id, actor="tester")
    assert entity.status == MissionStatus.PLANNING

    entity = await service.analyze_risk(entity.id, actor="tester")
    assert entity.status == MissionStatus.RISK_ANALYSIS

    entity = await service.submit_for_approval(entity.id, requester="tester")
    assert entity.status in (MissionStatus.AWAITING_APPROVAL, MissionStatus.APPROVED)


@pytest.mark.asyncio
async def test_retry_requires_failed_state(mock_repo, model_id):
    _make_created(mock_repo, model_id, title="Retry Guard", objective="Test")

    entity = await service.create_mission(
        title="Retry Guard", objective="Test retry guard", owner="tester",
    )
    with pytest.raises(ValueError, match="Cannot retry"):
        await service.retry_mission(entity.id, actor="tester")


@pytest.mark.asyncio
async def test_create_mission_with_context(mock_repo, model_id):
    mock_repo.create.return_value = _make_model_mock(
        model_id, title="Context Mission", objective="Test with context",
        context={"target": "production", "timeout": 3600},
    )

    entity = await service.create_mission(
        title="Context Mission", objective="Test with context", owner="tester",
        context={"target": "production", "timeout": 3600},
        tags=["critical", "prod"],
    )
    assert entity.context.inputs.get("target") == "production"
    assert "critical" in entity.metadata.tags


@pytest.mark.asyncio
async def test_structure_plan(mock_repo, model_id):
    mock_repo.create.return_value = _make_model_mock(model_id, title="Plan Shape", objective="Test plan structure")

    entity = await service.create_mission(
        title="Plan Shape", objective="Test plan structure", owner="tester",
    )
    plan = await service._planner.create_plan(
        str(entity.id), entity.title, entity.objective, {},
    )
    assert plan.plan_id is not None
    assert plan.mission_id == str(entity.id)
    assert len(plan.steps) > 0
    assert plan.steps[0].order < plan.steps[1].order
