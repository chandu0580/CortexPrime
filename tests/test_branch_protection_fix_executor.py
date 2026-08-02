from __future__ import annotations

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


@pytest.mark.asyncio
class TestEnableMinimalProtection:
    async def test_blocks_and_does_not_touch_github_when_not_approved(self):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.PENDING)),
        ), patch("backend.connectors.registry.connector_registry.get") as mock_get:
            result = await enable_minimal_protection("o", "r", "main")
        assert result is None
        mock_get.assert_not_called()

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

    async def test_exception_during_update_returns_none(self):
        fake_gh = MagicMock()
        fake_gh.update_branch_protection = AsyncMock(side_effect=RuntimeError("API exploded"))

        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ), patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await enable_minimal_protection("o", "r", "main")
        assert result is None
