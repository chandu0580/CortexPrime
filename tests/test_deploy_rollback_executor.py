from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.approval_center.models import ApprovalWorkflow, RiskLevel, WorkflowStatus
from backend.services.enterprise_deploy_regression_detector import MetricWindow, RegressionVerdict
from backend.services.enterprise_deploy_rollback_executor import trigger_rollback
from backend.services.enterprise_deploy_rollback_store import RollbackHistoryStore

pytestmark = pytest.mark.asyncio


def _workflow(status: WorkflowStatus, risk_level: RiskLevel = RiskLevel.HIGH) -> ApprovalWorkflow:
    return ApprovalWorkflow(
        workflow_id="wf_test123",
        execution_id="test-exec",
        mission_id="enterprise.automated_rollback",
        policy_id="policy_high",
        objective="test rollback",
        risk_level=risk_level,
        status=status,
    )


@pytest.fixture(autouse=True)
def default_approved_workflow(monkeypatch):
    """By default, every test in this file gets an auto-approved workflow —
    these tests exercise the rollback LOGIC, not the approval gate itself
    (that's covered by TestApprovalGate below)."""
    monkeypatch.setattr(
        "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
        AsyncMock(return_value=_workflow(WorkflowStatus.APPROVED)),
    )


def _verdict(regressed=True, deployment_id="42") -> RegressionVerdict:
    return RegressionVerdict(
        service="org/repo",
        deployment_id=deployment_id,
        regressed=regressed,
        reasons=["p95 latency +25.9% (0.194s -> 0.245s)"],
        before=MetricWindow(label="before", p95_latency_seconds=0.194, error_rate=0.0),
        after=MetricWindow(label="after", p95_latency_seconds=0.245, error_rate=0.06),
    )


def _github_ctx() -> dict:
    return {"source": "github_webhook", "environment": "production"}


def _gitlab_ctx() -> dict:
    return {"source": "gitlab_webhook", "environment": "production", "project_id": 999}


@pytest.fixture
def store(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        test_store = RollbackHistoryStore(file_path=Path(tmpdir) / "rollback_history.json")
        monkeypatch.setattr(
            "backend.services.enterprise_deploy_rollback_executor.rollback_history_store", test_store
        )
        yield test_store


class TestTriggerRollback:
    async def test_returns_none_when_not_regressed(self, store):
        result = await trigger_rollback(_verdict(regressed=False), _github_ctx())
        assert result is None

    async def test_returns_none_for_unrecognized_source(self, store):
        result = await trigger_rollback(_verdict(), {"source": "unknown_webhook"})
        assert result is None

    async def test_github_triggers_deployment_at_last_good_sha(self, store):
        fake_gh = MagicMock()
        fake_gh.get_last_successful_deployment = AsyncMock(return_value={"id": 41, "sha": "goodsha"})
        fake_gh.create_deployment = AsyncMock(return_value={"id": 99})

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await trigger_rollback(_verdict(), _github_ctx())

        assert result["triggered"] is True
        assert result["target_sha"] == "goodsha"
        assert result["rollback_deployment_id"] == 99
        assert result["provider"] == "github"
        fake_gh.create_deployment.assert_awaited_once()
        _, kwargs = fake_gh.create_deployment.call_args
        assert kwargs["ref"] == "goodsha"
        assert kwargs["task"] == "rollback"

    async def test_github_records_untriggered_when_no_good_target(self, store):
        fake_gh = MagicMock()
        fake_gh.get_last_successful_deployment = AsyncMock(return_value=None)

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await trigger_rollback(_verdict(), _github_ctx())

        assert result["triggered"] is False
        assert "No known-good deployment" in result["error"]

    async def test_github_returns_untriggered_when_connector_not_registered(self, store):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await trigger_rollback(_verdict(), _github_ctx())
        assert result["triggered"] is False

    async def test_gitlab_triggers_pipeline_at_last_good_sha(self, store):
        fake_gl = MagicMock()
        fake_gl.get_last_successful_deployment = AsyncMock(return_value={"id": 10, "sha": "goodsha2"})
        fake_gl.create_pipeline = AsyncMock(return_value={"id": 77})

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gl):
            result = await trigger_rollback(_verdict(), _gitlab_ctx())

        assert result["triggered"] is True
        assert result["target_sha"] == "goodsha2"
        assert result["provider"] == "gitlab"
        fake_gl.create_pipeline.assert_awaited_once()
        _, kwargs = fake_gl.create_pipeline.call_args
        assert kwargs["ref"] == "goodsha2"

    async def test_gitlab_returns_untriggered_without_project_id(self, store):
        ctx = {"source": "gitlab_webhook", "environment": "production"}
        with patch("backend.connectors.registry.connector_registry.get", return_value=MagicMock()):
            result = await trigger_rollback(_verdict(), ctx)
        assert result["triggered"] is False

    async def test_records_ticket_key_when_given(self, store):
        fake_gh = MagicMock()
        fake_gh.get_last_successful_deployment = AsyncMock(return_value={"id": 41, "sha": "goodsha"})
        fake_gh.create_deployment = AsyncMock(return_value={"id": 99})

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await trigger_rollback(_verdict(), _github_ctx(), ticket_key="OPS-55")

        assert result["ticket_key"] == "OPS-55"

    async def test_exception_during_rollback_is_recorded_not_raised(self, store):
        fake_gh = MagicMock()
        fake_gh.get_last_successful_deployment = AsyncMock(side_effect=RuntimeError("GitHub API: 500"))

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await trigger_rollback(_verdict(), _github_ctx())

        assert result["triggered"] is False
        assert "GitHub API: 500" in result["error"]

    async def test_result_is_persisted_to_history_store(self, store):
        fake_gh = MagicMock()
        fake_gh.get_last_successful_deployment = AsyncMock(return_value={"id": 41, "sha": "goodsha"})
        fake_gh.create_deployment = AsyncMock(return_value={"id": 99})

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            await trigger_rollback(_verdict(), _github_ctx())

        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0]["service"] == "org/repo"


class TestApprovalGate:
    async def test_blocks_and_does_not_touch_github_when_not_approved(self, store, monkeypatch):
        monkeypatch.setattr(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            AsyncMock(return_value=_workflow(WorkflowStatus.PENDING)),
        )
        fake_gh = MagicMock()
        fake_gh.get_last_successful_deployment = AsyncMock(return_value={"id": 41, "sha": "goodsha"})

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            result = await trigger_rollback(_verdict(), _github_ctx())

        assert result["triggered"] is False
        assert "Awaiting approval" in result["error"]
        assert "wf_test123" in result["error"]
        fake_gh.get_last_successful_deployment.assert_not_awaited()

    async def test_proceeds_on_break_glass(self, store):
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            AsyncMock(return_value=_workflow(WorkflowStatus.BREAK_GLASS)),
        ):
            fake_gh = MagicMock()
            fake_gh.get_last_successful_deployment = AsyncMock(return_value={"id": 41, "sha": "goodsha"})
            fake_gh.create_deployment = AsyncMock(return_value={"id": 99})

            with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
                result = await trigger_rollback(_verdict(), _github_ctx())

        assert result["triggered"] is True
        fake_gh.create_deployment.assert_awaited_once()

    async def test_still_returns_none_for_non_regression_before_gate_runs(self, store):
        # Should short-circuit before ever creating a workflow.
        with patch(
            "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
            AsyncMock(side_effect=AssertionError("should not be called")),
        ):
            result = await trigger_rollback(_verdict(regressed=False), _github_ctx())
        assert result is None
