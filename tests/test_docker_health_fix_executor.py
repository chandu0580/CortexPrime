from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.approval_center.models import ApprovalWorkflow, RiskLevel, WorkflowStatus
from backend.services.enterprise_docker_health_fix_executor import restart_crashlooping_container


def _workflow(status: WorkflowStatus, risk_level: RiskLevel = RiskLevel.LOW) -> ApprovalWorkflow:
    return ApprovalWorkflow(
        workflow_id="wf_dh123",
        execution_id="test-exec",
        mission_id="enterprise.docker_health_autofix",
        policy_id="policy_low",
        objective="test",
        risk_level=risk_level,
        status=status,
    )


@pytest.fixture(autouse=True)
def default_no_existing_workflow(monkeypatch):
    monkeypatch.setattr(
        "backend.approval_center.workflows.approval_workflow_engine.get_workflow_by_execution",
        lambda execution_id: None,
    )


@pytest.fixture(autouse=True)
def isolated_pending_action_store(monkeypatch):
    from backend.services.enterprise_approval_action_dispatcher import PendingActionStore
    with tempfile.TemporaryDirectory() as tmpdir:
        test_store = PendingActionStore(file_path=Path(tmpdir) / "pending_actions.json")
        monkeypatch.setattr(
            "backend.services.enterprise_approval_action_dispatcher.pending_action_store", test_store
        )
        yield test_store


@pytest.mark.asyncio
class TestRestartCrashloopingContainer:
    async def test_blocks_and_does_not_touch_docker_when_not_approved(self, isolated_pending_action_store):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.PENDING)),
        ), patch("backend.connectors.registry.connector_registry.get") as mock_get:
            result = await restart_crashlooping_container("my-app", "abc123")
        assert result is None
        mock_get.assert_not_called()

        pending = isolated_pending_action_store.list_pending()
        assert "wf_dh123" in pending
        assert pending["wf_dh123"]["action_type"] == "docker_health_fix"
        assert pending["wf_dh123"]["payload"]["container_id"] == "abc123"

    async def test_non_critical_container_creates_low_risk_workflow(self):
        create_mock = AsyncMock(return_value=_workflow(WorkflowStatus.PENDING))
        with patch("backend.approval_center.workflows.approval_workflow_engine.create_workflow", new=create_mock):
            await restart_crashlooping_container("my-app", "abc123")
        assert create_mock.call_args.kwargs["risk_level"] == RiskLevel.LOW

    async def test_critical_container_creates_medium_risk_workflow(self):
        create_mock = AsyncMock(return_value=_workflow(WorkflowStatus.PENDING))
        with patch("backend.approval_center.workflows.approval_workflow_engine.create_workflow", new=create_mock):
            await restart_crashlooping_container("cortex-postgres", "abc123")
        assert create_mock.call_args.kwargs["risk_level"] == RiskLevel.MEDIUM

    async def test_returns_none_when_docker_not_registered(self):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await restart_crashlooping_container("my-app", "abc123")
        assert result is None

    async def test_calls_restart_container_when_approved(self):
        fake_docker = MagicMock()
        fake_docker.restart_container = AsyncMock(return_value=True)

        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker):
            result = await restart_crashlooping_container("my-app", "abc123", ticket_key="OPS-9")

        assert result == {"restarted": True, "container": "my-app", "container_id": "abc123"}
        fake_docker.restart_container.assert_awaited_once_with("abc123")

    async def test_proceeds_on_break_glass(self):
        fake_docker = MagicMock()
        fake_docker.restart_container = AsyncMock(return_value=True)

        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.BREAK_GLASS)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker):
            result = await restart_crashlooping_container("my-app", "abc123")
        assert result is not None

    async def test_does_not_recreate_workflow_when_one_already_exists(self, monkeypatch):
        existing = _workflow(WorkflowStatus.APPROVED)
        monkeypatch.setattr(
            "backend.approval_center.workflows.approval_workflow_engine.get_workflow_by_execution",
            lambda execution_id: existing,
        )
        create_mock = AsyncMock(side_effect=AssertionError("should not create a new workflow"))
        monkeypatch.setattr("backend.approval_center.workflows.approval_workflow_engine.create_workflow", create_mock)

        fake_docker = MagicMock()
        fake_docker.restart_container = AsyncMock(return_value=True)

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker):
            result = await restart_crashlooping_container("my-app", "abc123")

        assert result is not None
        create_mock.assert_not_awaited()

    async def test_exception_during_restart_returns_none(self):
        fake_docker = MagicMock()
        fake_docker.restart_container = AsyncMock(side_effect=RuntimeError("daemon unreachable"))

        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=fake_docker):
            result = await restart_crashlooping_container("my-app", "abc123")
        assert result is None
