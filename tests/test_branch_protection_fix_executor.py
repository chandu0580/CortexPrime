from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.approval_center.models import ApprovalWorkflow, RiskLevel, WorkflowStatus
from backend.services.enterprise_branch_protection_fix_executor import enable_minimal_protection


def _workflow(status: WorkflowStatus) -> ApprovalWorkflow:
    return ApprovalWorkflow(
        workflow_id="wf_bp123",
        execution_id="test-exec",
        mission_id="enterprise.branch_protection_autofix",
        policy_id="policy_medium",
        objective="test",
        risk_level=RiskLevel.MEDIUM,
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
class TestEnableMinimalProtection:
    async def test_blocks_and_does_not_touch_github_when_not_approved(self, isolated_pending_action_store):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.PENDING)),
        ), patch("backend.connectors.registry.connector_registry.get") as mock_get:
            result = await enable_minimal_protection("o", "r", "main")
        assert result is None
        mock_get.assert_not_called()

        pending = isolated_pending_action_store.list_pending()
        assert "wf_bp123" in pending
        assert pending["wf_bp123"]["action_type"] == "branch_protection_fix"
        assert pending["wf_bp123"]["payload"]["branch"] == "main"

    async def test_returns_none_when_github_not_registered(self):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await enable_minimal_protection("o", "r", "main")
        assert result is None

    async def test_calls_update_branch_protection_when_approved(self):
        fake_gh = MagicMock()
        fake_gh.update_branch_protection = AsyncMock(return_value={"enforce_admins": {"enabled": True}})

        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await enable_minimal_protection("o", "r", "main", ticket_key="OPS-9")

        assert result == {"enforce_admins": {"enabled": True}}
        fake_gh.update_branch_protection.assert_awaited_once()
        _, kwargs = fake_gh.update_branch_protection.call_args
        assert kwargs["enforce_admins"] is True
        assert kwargs["required_pull_request_reviews"] == {"required_approving_review_count": 1}

    async def test_proceeds_on_break_glass(self):
        fake_gh = MagicMock()
        fake_gh.update_branch_protection = AsyncMock(return_value={"ok": True})

        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.BREAK_GLASS)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await enable_minimal_protection("o", "r", "main")
        assert result == {"ok": True}

    async def test_does_not_recreate_workflow_when_one_already_exists(self, monkeypatch):
        existing = _workflow(WorkflowStatus.APPROVED)
        monkeypatch.setattr(
            "backend.approval_center.workflows.approval_workflow_engine.get_workflow_by_execution",
            lambda execution_id: existing,
        )
        create_mock = AsyncMock(side_effect=AssertionError("should not create a new workflow"))
        monkeypatch.setattr("backend.approval_center.workflows.approval_workflow_engine.create_workflow", create_mock)

        fake_gh = MagicMock()
        fake_gh.update_branch_protection = AsyncMock(return_value={"ok": True})

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await enable_minimal_protection("o", "r", "main")

        assert result == {"ok": True}
        create_mock.assert_not_awaited()

    async def test_exception_during_update_returns_none(self):
        fake_gh = MagicMock()
        fake_gh.update_branch_protection = AsyncMock(side_effect=RuntimeError("API exploded"))

        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await enable_minimal_protection("o", "r", "main")
        assert result is None
