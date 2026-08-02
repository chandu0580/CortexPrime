"""
Tests confirming the three existing detectors actually route through the
alert correlator rather than filing tickets / attaching signals directly —
this is what makes noise-reduction real rather than just available.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


class TestDeployRegressionRoutesThroughCorrelator:
    async def test_correlate_and_report_called_instead_of_report_incident_directly(self):
        import tempfile as _tempfile
        from backend.services.enterprise_deploy_regression_detector import MetricWindow, RegressionVerdict
        from backend.services.enterprise_github_integration import (
            DeployCheckHistoryStore,
            PendingDeployCheckStore,
            _check_deploy_regression,
        )

        verdict = RegressionVerdict(
            service="org/checkout-service", deployment_id="42", regressed=True,
            reasons=["p95 latency +30.0% (0.100s -> 0.130s)"],
            before=MetricWindow(label="before", p95_latency_seconds=0.10, error_rate=0.0),
            after=MetricWindow(label="after", p95_latency_seconds=0.13, error_rate=0.0),
        )

        with _tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "deploy_check_history.json"
            pending_path = Path(tmpdir) / "pending_deploy_checks.json"
            with patch("backend.services.enterprise_github_integration._DEPLOY_CHECK_HISTORY_FILE", history_path), \
                 patch("backend.services.enterprise_github_integration._PENDING_DEPLOY_CHECKS_FILE", pending_path), \
                 patch("backend.services.enterprise_github_integration.deploy_check_history_store", DeployCheckHistoryStore()), \
                 patch("backend.services.enterprise_github_integration.pending_deploy_check_store", PendingDeployCheckStore()), \
                 patch("asyncio.sleep", new=AsyncMock()), \
                 patch(
                     "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                     new=AsyncMock(return_value=verdict),
                 ), \
                 patch(
                     "backend.services.enterprise_alert_correlator.correlate_and_report",
                     new=AsyncMock(return_value={"key": "OPS-1"}),
                 ) as mock_correlate, \
                 patch(
                     "backend.services.enterprise_deploy_rollback_executor.trigger_rollback",
                     new=AsyncMock(return_value=None),
                 ):
                task = await _check_deploy_regression(
                    {"repo_full_name": "org/checkout-service", "deployment_id": 42, "source": "github_webhook"}
                )
                await task

        mock_correlate.assert_awaited_once()
        _, kwargs = mock_correlate.call_args
        assert kwargs["source"] == "deploy_regression"
        assert kwargs["service"] == "org/checkout-service"
        assert "reporter" in kwargs


class TestFlakyTestRoutesThroughCorrelator:
    async def test_correlate_and_report_called_when_threshold_crossed(self):
        from backend.services.enterprise_flaky_test_detector import (
            FlakyTestHistoryStore,
            PendingRetryStore,
            handle_ci_completion,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            hstore = FlakyTestHistoryStore(file_path=Path(tmpdir) / "history.json")
            pstore = PendingRetryStore(file_path=Path(tmpdir) / "pending.json")
            # Pre-seed 2 prior occurrences so this 3rd one crosses the default threshold of 3.
            hstore.record("org/repo", "CI", "run:1", "evidence 1")
            hstore.record("org/repo", "CI", "run:2", "evidence 2")
            pstore.add("gh:org/repo:3", "org/repo", "CI", {})

            with patch(
                "backend.services.enterprise_alert_correlator.correlate_and_report",
                new=AsyncMock(return_value={"key": "OPS-2"}),
            ) as mock_correlate:
                result = await handle_ci_completion(
                    "org/repo", "CI", "gh:org/repo:3", "success", {},
                    trigger_retry=AsyncMock(return_value=True),
                    fetch_evidence=AsyncMock(return_value=[{"attempt": 2, "job_name": "test", "conclusion": "success"}]),
                    pending_store=pstore, history_store=hstore,
                )

        mock_correlate.assert_awaited_once()
        _, kwargs = mock_correlate.call_args
        assert kwargs["source"] == "flaky_test"
        assert kwargs["service"] == "org/repo"
        assert result == {"key": "OPS-2"}


class TestRollbackAttachesSignal:
    async def test_attach_signal_called_after_recording(self):
        from backend.approval_center.models import ApprovalWorkflow, RiskLevel, WorkflowStatus
        from backend.services.enterprise_deploy_regression_detector import MetricWindow, RegressionVerdict
        from backend.services.enterprise_deploy_rollback_executor import trigger_rollback

        verdict = RegressionVerdict(
            service="org/repo", deployment_id="42", regressed=True,
            reasons=["p95 latency +30%"],
            before=MetricWindow(label="before", p95_latency_seconds=0.1, error_rate=0.0),
            after=MetricWindow(label="after", p95_latency_seconds=0.13, error_rate=0.0),
        )
        fake_gh = MagicMock()
        fake_gh.get_last_successful_deployment = AsyncMock(return_value={"id": 41, "sha": "goodsha"})
        fake_gh.create_deployment = AsyncMock(return_value={"id": 99})

        approved_workflow = ApprovalWorkflow(
            workflow_id="wf_test", execution_id="test-exec", mission_id="enterprise.automated_rollback",
            policy_id="policy_low", objective="test", risk_level=RiskLevel.LOW,
            status=WorkflowStatus.APPROVED,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            from backend.services.enterprise_deploy_rollback_store import RollbackHistoryStore
            test_store = RollbackHistoryStore(file_path=Path(tmpdir) / "rollback_history.json")
            with patch("backend.services.enterprise_deploy_rollback_executor.rollback_history_store", test_store), \
                 patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh), \
                 patch(
                     "backend.approval_center.workflows.approval_workflow_engine.create_workflow",
                     new=AsyncMock(return_value=approved_workflow),
                 ), \
                 patch(
                     "backend.services.enterprise_alert_correlator.attach_signal",
                     new=AsyncMock(return_value=None),
                 ) as mock_attach:
                await trigger_rollback(verdict, {"source": "github_webhook", "environment": "production"})

        fake_gh.create_deployment.assert_awaited_once()
        mock_attach.assert_awaited_once()
        _, kwargs = mock_attach.call_args
        assert kwargs["source"] == "rollback"
        assert kwargs["service"] == "org/repo"
