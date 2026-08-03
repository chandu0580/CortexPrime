from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.approval_center.models import ApprovalWorkflow, RiskLevel, WorkflowStatus
from backend.services.enterprise_cost_anomaly_fix_executor import disable_provider_temporarily


def _workflow(status: WorkflowStatus) -> ApprovalWorkflow:
    return ApprovalWorkflow(
        workflow_id="wf_ca123",
        execution_id="test-exec",
        mission_id="enterprise.cost_anomaly_autofix",
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


@pytest.fixture(autouse=True)
def reset_router_stats():
    from backend.llm.llm_router import llm_router
    llm_router.reset_stats()
    yield
    llm_router.reset_stats()


@pytest.mark.asyncio
class TestDisableProviderTemporarily:
    async def test_blocks_and_does_not_disable_when_not_approved(self, isolated_pending_action_store):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.PENDING)),
        ):
            from backend.llm.llm_router import llm_router
            result = await disable_provider_temporarily("openai", 10.0)
        assert result is None
        assert llm_router._stats["openai"].circuit_open is False

        pending = isolated_pending_action_store.list_pending()
        assert "wf_ca123" in pending
        assert pending["wf_ca123"]["action_type"] == "cost_anomaly_fix"
        assert pending["wf_ca123"]["payload"]["provider"] == "openai"

    async def test_always_creates_medium_risk_workflow(self):
        create_mock = AsyncMock(return_value=_workflow(WorkflowStatus.PENDING))
        with patch("backend.approval_center.workflows.approval_workflow_engine.create_workflow", new=create_mock):
            await disable_provider_temporarily("openai", 10.0)
        assert create_mock.call_args.kwargs["risk_level"] == RiskLevel.MEDIUM

    async def test_calls_force_circuit_open_when_approved(self):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ):
            result = await disable_provider_temporarily("openai", 10.0, ticket_key="OPS-9")

        assert result == {"disabled": True, "provider": "openai", "duration_secs": 1800}
        from backend.llm.llm_router import llm_router
        assert llm_router._stats["openai"].circuit_open is True

    async def test_proceeds_on_break_glass(self):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.BREAK_GLASS)),
        ):
            result = await disable_provider_temporarily("openai", 10.0)
        assert result is not None

    async def test_does_not_recreate_workflow_when_one_already_exists(self, monkeypatch):
        existing = _workflow(WorkflowStatus.APPROVED)
        monkeypatch.setattr(
            "backend.approval_center.workflows.approval_workflow_engine.get_workflow_by_execution",
            lambda execution_id: existing,
        )
        create_mock = AsyncMock(side_effect=AssertionError("should not create a new workflow"))
        monkeypatch.setattr("backend.approval_center.workflows.approval_workflow_engine.create_workflow", create_mock)

        result = await disable_provider_temporarily("openai", 10.0)

        assert result is not None
        create_mock.assert_not_awaited()

    async def test_unknown_provider_returns_none(self):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            new=AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
        ):
            result = await disable_provider_temporarily("not-a-real-provider", 10.0)
        assert result is None
