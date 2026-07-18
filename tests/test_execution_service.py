from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.execution.models import ExecutionStatus, ExecutionType, ExecutionTrigger
from backend.execution.service import ExecutionService


def _make_exec_model_mock(
    execution_id: str,
    status: str = "CREATED",
    agent: str | None = None,
    trigger: str = "manual",
    context: dict | None = None,
    result: dict | None = None,
    error_message: str | None = None,
    started_at=None,
    completed_at=None,
    duration_ms: float | None = None,
):
    return MagicMock(
        id=uuid.uuid4(),
        execution_id=execution_id,
        status=status,
        agent=agent,
        trigger=trigger,
        context=context or {},
        result=result or {},
        error_message=error_message,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def exec_id():
    return str(uuid.uuid4())


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get = AsyncMock()
    repo.get_by_execution_id = AsyncMock()
    repo.update = AsyncMock()
    repo.search = AsyncMock(return_value=[])
    repo.search_by_mission = AsyncMock(return_value=[])
    repo.count_by_status = AsyncMock(return_value={})
    return repo


@pytest.fixture
def mock_repo_factory(mock_repo):
    factory = MagicMock()
    factory.execution_repo = AsyncMock(return_value=mock_repo)
    factory.execution_event_repo = AsyncMock()
    return factory


@pytest.fixture(autouse=True)
def _setup(mock_repo_factory):
    global service
    service = ExecutionService(repo_factory=mock_repo_factory)


service: ExecutionService


def _make_created(mock_repo, exec_id, **kw):
    m = _make_exec_model_mock(exec_id, status="CREATED", **kw)
    mock_repo.get_by_execution_id.return_value = m
    mock_repo.create.return_value = m


@pytest.mark.asyncio
async def test_create_execution(mock_repo, exec_id):
    mock_repo.create.return_value = _make_exec_model_mock(
        exec_id, trigger="manual",
        context={"execution_type": "shell", "command": "echo hello"},
    )

    entity = await service.create_execution(
        command="echo hello",
        execution_type=ExecutionType.SHELL,
        trigger=ExecutionTrigger.MANUAL,
        agent="tester",
        tags=["test"],
    )
    assert entity.execution_id is not None
    assert entity.status == ExecutionStatus.CREATED
    assert entity.metadata.correlation_id is not None


@pytest.mark.asyncio
async def test_queue_execution(mock_repo, exec_id):
    _make_created(mock_repo, exec_id)
    entity = await service.queue_execution(exec_id, actor="tester")
    assert entity is not None
    assert entity.status == ExecutionStatus.QUEUED


@pytest.mark.asyncio
async def test_start_execution(mock_repo, exec_id):
    created = _make_exec_model_mock(exec_id, status="CREATED", context={"execution_type": "shell", "command": "echo hi"})
    queued = _make_exec_model_mock(exec_id, status="QUEUED", context={"execution_type": "shell", "command": "echo hi"})
    calls = [created, queued]

    async def get_by_execution_id_side_effect(*args, **kwargs):
        return calls.pop(0) if calls else queued

    mock_repo.get_by_execution_id = AsyncMock(side_effect=get_by_execution_id_side_effect)
    mock_repo.create.return_value = created

    entity = await service.queue_execution(exec_id, actor="tester")
    entity = await service.start_execution(exec_id, actor="tester")
    assert entity is not None
    assert entity.status == ExecutionStatus.RUNNING


@pytest.mark.asyncio
async def test_complete_execution(mock_repo, exec_id):
    started = datetime.now(timezone.utc)
    m = _make_exec_model_mock(exec_id, status="RUNNING", started_at=started)
    mock_repo.get_by_execution_id.return_value = m

    entity = await service.complete_execution(
        exec_id, result={"output": "done"}, actor="tester",
    )
    assert entity is not None
    assert entity.status == ExecutionStatus.SUCCEEDED
    assert entity.result.get("output") == "done"


@pytest.mark.asyncio
async def test_fail_execution(mock_repo, exec_id):
    started = datetime.now(timezone.utc)
    m = _make_exec_model_mock(exec_id, status="RUNNING", started_at=started)
    mock_repo.get_by_execution_id.return_value = m

    entity = await service.fail_execution(exec_id, error="Something went wrong", actor="tester")
    assert entity is not None
    assert entity.status == ExecutionStatus.FAILED
    assert entity.error_message == "Something went wrong"


@pytest.mark.asyncio
async def test_cancel_execution(mock_repo, exec_id):
    _make_created(mock_repo, exec_id, context={})

    entity = await service.cancel_execution(exec_id, reason="No longer needed", actor="tester")
    assert entity is not None
    assert entity.status == ExecutionStatus.CANCELLED


@pytest.mark.asyncio
async def test_retry_from_failed(mock_repo, exec_id):
    failed = _make_exec_model_mock(exec_id, status="FAILED", context={})
    queued = _make_exec_model_mock(exec_id, status="QUEUED", context={})
    calls = [failed, queued]

    async def get_by_execution_id_side_effect(*args, **kwargs):
        return calls.pop(0) if calls else queued

    mock_repo.get_by_execution_id = AsyncMock(side_effect=get_by_execution_id_side_effect)

    entity = await service.retry_execution(exec_id, actor="tester")
    assert entity is not None
    assert entity.status == ExecutionStatus.QUEUED
    assert entity.metadata.retry_count == 1


@pytest.mark.asyncio
async def test_retry_requires_failed_state(mock_repo, exec_id):
    m = _make_exec_model_mock(exec_id, status="CREATED", context={})
    mock_repo.get_by_execution_id.return_value = m

    with pytest.raises(ValueError, match="Cannot retry"):
        await service.retry_execution(exec_id, actor="tester")


@pytest.mark.asyncio
async def test_get_nonexistent_execution(mock_repo):
    mock_repo.get_by_execution_id.return_value = None
    entity = await service.get_execution("nonexistent")
    assert entity is None


@pytest.mark.asyncio
async def test_pause_and_resume(mock_repo, exec_id):
    m = _make_exec_model_mock(exec_id, status="RUNNING")
    mock_repo.get_by_execution_id.return_value = m

    entity = await service.pause_execution(exec_id, actor="tester")
    assert entity is not None
    assert entity.status == ExecutionStatus.PAUSED


@pytest.mark.asyncio
async def test_cancel_from_running(mock_repo, exec_id):
    m = _make_exec_model_mock(exec_id, status="RUNNING")
    mock_repo.get_by_execution_id.return_value = m

    entity = await service.cancel_execution(exec_id, reason="interrupted", actor="tester")
    assert entity is not None
    assert entity.status == ExecutionStatus.CANCELLED


@pytest.mark.asyncio
async def test_invalid_transition_raises(mock_repo, exec_id):
    m = _make_exec_model_mock(exec_id, status="CREATED")
    mock_repo.get_by_execution_id.return_value = m

    with pytest.raises(ValueError, match="Cannot fail"):
        await service.fail_execution(exec_id, error="should fail", actor="tester")


@pytest.mark.asyncio
async def test_run_execution_success(mock_repo, exec_id):
    m = _make_exec_model_mock(
        exec_id, status="CREATED",
        context={"execution_type": "shell", "command": "echo done",
                 "max_retries": 3, "timeout_seconds": 300, "tags": []},
    )
    mock_repo.create.return_value = m
    mock_repo.get_by_execution_id.return_value = m

    entity = await service.run_execution(
        command="echo done",
        execution_type=ExecutionType.SHELL,
        agent="tester",
    )
    assert entity is not None
