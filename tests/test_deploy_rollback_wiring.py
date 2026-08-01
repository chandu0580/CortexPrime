"""
Tests for the rollback-trigger hook wired into _run_deploy_regression_check
(backend.services.enterprise_github_integration) — shared by both GitHub
and GitLab wiring, since GitLab's _process_deployment_event calls
_check_deploy_regression directly rather than duplicating this logic.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_deploy_regression_detector import MetricWindow, RegressionVerdict
from backend.services.enterprise_github_integration import (
    DeployCheckHistoryStore,
    PendingDeployCheckStore,
    _check_deploy_regression,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolate_deploy_check_stores():
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "deploy_check_history.json"
        pending_path = Path(tmpdir) / "pending_deploy_checks.json"
        with patch("backend.services.enterprise_github_integration._DEPLOY_CHECK_HISTORY_FILE", history_path), \
             patch("backend.services.enterprise_github_integration._PENDING_DEPLOY_CHECKS_FILE", pending_path), \
             patch("backend.services.enterprise_github_integration.deploy_check_history_store", DeployCheckHistoryStore()), \
             patch("backend.services.enterprise_github_integration.pending_deploy_check_store", PendingDeployCheckStore()):
            yield


def _regressed_verdict() -> RegressionVerdict:
    return RegressionVerdict(
        service="org/checkout-service",
        deployment_id="42",
        regressed=True,
        reasons=["p95 latency +30.0% (0.100s -> 0.130s)"],
        before=MetricWindow(label="before", p95_latency_seconds=0.10, error_rate=0.0),
        after=MetricWindow(label="after", p95_latency_seconds=0.13, error_rate=0.0),
    )


class TestRollbackTriggeredOnRegression:
    async def test_trigger_rollback_called_when_regressed(self):
        with patch("asyncio.sleep", new=AsyncMock()), \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(return_value=_regressed_verdict()),
             ), \
             patch(
                 "backend.services.enterprise_deploy_incident_reporter.report_incident",
                 new=AsyncMock(return_value={"key": "OPS-1"}),
             ), \
             patch(
                 "backend.services.enterprise_deploy_rollback_executor.trigger_rollback",
                 new=AsyncMock(return_value={"triggered": True}),
             ) as mock_rollback:
            task = await _check_deploy_regression(
                {"repo_full_name": "org/checkout-service", "deployment_id": 42, "source": "github_webhook"}
            )
            await task

            mock_rollback.assert_awaited_once()
            call_verdict, call_ctx = mock_rollback.call_args.args
            assert call_verdict.regressed is True
            assert call_ctx["repo_full_name"] == "org/checkout-service"
            assert mock_rollback.call_args.kwargs["ticket_key"] == "OPS-1"

    async def test_trigger_rollback_not_called_when_clean(self):
        clean_verdict = RegressionVerdict(service="org/checkout-service", deployment_id="42", regressed=False, reasons=[])
        with patch("asyncio.sleep", new=AsyncMock()), \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(return_value=clean_verdict),
             ), \
             patch(
                 "backend.services.enterprise_deploy_rollback_executor.trigger_rollback",
                 new=AsyncMock(return_value=None),
             ) as mock_rollback:
            task = await _check_deploy_regression(
                {"repo_full_name": "org/checkout-service", "deployment_id": 42, "source": "github_webhook"}
            )
            await task

            mock_rollback.assert_not_awaited()

    async def test_rollback_failure_does_not_break_the_regression_check(self):
        """A raised exception inside trigger_rollback must not prevent the
        history record from being written — matches the try/except wrapping
        it in _run_deploy_regression_check."""
        with patch("asyncio.sleep", new=AsyncMock()), \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(return_value=_regressed_verdict()),
             ), \
             patch(
                 "backend.services.enterprise_deploy_incident_reporter.report_incident",
                 new=AsyncMock(return_value=None),
             ), \
             patch(
                 "backend.services.enterprise_deploy_rollback_executor.trigger_rollback",
                 new=AsyncMock(side_effect=RuntimeError("boom")),
             ):
            from backend.services.enterprise_github_integration import deploy_check_history_store

            task = await _check_deploy_regression(
                {"repo_full_name": "org/checkout-service", "deployment_id": 42, "source": "github_webhook"}
            )
            await task  # must not raise

            recent = deploy_check_history_store.list_recent()
            assert len(recent) == 1
            assert recent[0]["regressed"] is True
