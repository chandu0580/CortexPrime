"""
Tests for the deploy-regression-detection hook wired into the GitHub
webhook flow (backend.services.enterprise_github_integration).

Deliberately isolated from tests/test_enterprise_github_integration.py,
which has 68 pre-existing failures from stale method signatures unrelated
to this feature (e.g. PRIntelligence.list_prs() call-site/signature drift)
— not something introduced by or fixed as part of this change.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_github_integration import (
    DeployCheckHistoryStore,
    PendingDeployCheckStore,
    _check_deploy_regression,
    github_integration,
)
from backend.services.enterprise_deploy_regression_detector import MetricWindow, RegressionVerdict

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolate_deploy_check_stores():
    # _check_deploy_regression schedules a background task that writes
    # through the module-level pending/history store singletons — without
    # this, every test run here appends real records to the real dev
    # data files (backend/data/*.json) instead of a throwaway temp store.
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "deploy_check_history.json"
        pending_path = Path(tmpdir) / "pending_deploy_checks.json"
        with patch("backend.services.enterprise_github_integration._DEPLOY_CHECK_HISTORY_FILE", history_path), \
             patch("backend.services.enterprise_github_integration._PENDING_DEPLOY_CHECKS_FILE", pending_path), \
             patch("backend.services.enterprise_github_integration.deploy_check_history_store", DeployCheckHistoryStore()), \
             patch("backend.services.enterprise_github_integration.pending_deploy_check_store", PendingDeployCheckStore()):
            yield


class TestCheckDeployRegressionGating:
    async def test_returns_none_without_service(self):
        task = await _check_deploy_regression({"deployment_id": "1"})
        assert task is None

    async def test_returns_none_without_deployment_id(self):
        task = await _check_deploy_regression({"repo_full_name": "org/checkout-service"})
        assert task is None

    async def test_schedules_task_when_context_complete(self):
        with patch("asyncio.sleep", new=AsyncMock()):
            fake_prom = MagicMock()
            fake_prom.is_ready = False
            with patch(
                "backend.connectors.registry.connector_registry.get",
                return_value=fake_prom,
            ):
                task = await _check_deploy_regression(
                    {"repo_full_name": "org/checkout-service", "deployment_id": 42}
                )
                assert task is not None
                await task  # drain — should complete cleanly even with an unready connector


class TestRegressionTriggersIncidentReport:
    """Verifies the full chain: detected regression -> report_incident called."""

    async def test_report_incident_called_when_regressed(self):
        verdict = RegressionVerdict(
            service="org/checkout-service",
            deployment_id="42",
            regressed=True,
            reasons=["p95 latency +30.0% (0.100s -> 0.130s)"],
            before=MetricWindow(label="before", p95_latency_seconds=0.10, error_rate=0.0),
            after=MetricWindow(label="after", p95_latency_seconds=0.13, error_rate=0.0),
        )
        with patch("asyncio.sleep", new=AsyncMock()), \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(return_value=verdict),
             ), \
             patch(
                 "backend.services.enterprise_deploy_incident_reporter.report_incident",
                 new=AsyncMock(return_value={"key": "OPS-1"}),
             ) as mock_report:
            task = await _check_deploy_regression(
                {"repo_full_name": "org/checkout-service", "deployment_id": 42}
            )
            await task
            mock_report.assert_awaited_once()
            call_verdict, call_ctx = mock_report.call_args.args
            assert call_verdict.regressed is True
            assert call_ctx["repo_full_name"] == "org/checkout-service"

    async def test_report_incident_not_called_when_clean(self):
        verdict = RegressionVerdict(service="org/checkout-service", deployment_id="42", regressed=False, reasons=[])
        with patch("asyncio.sleep", new=AsyncMock()), \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(return_value=verdict),
             ), \
             patch(
                 "backend.services.enterprise_deploy_incident_reporter.report_incident",
                 new=AsyncMock(return_value=None),
             ) as mock_report:
            task = await _check_deploy_regression(
                {"repo_full_name": "org/checkout-service", "deployment_id": 42}
            )
            await task
            mock_report.assert_not_awaited()


class TestDeploymentStatusWiring:
    """Verifies process_and_wire only triggers the check on a successful deploy."""

    @pytest.fixture(autouse=True)
    def _clear_state(self):
        github_integration.clear_state()

    def _payload(self, state: str) -> dict:
        return {
            "repository": {"full_name": "org/checkout-service"},
            "sender": {"login": "ops"},
            "deployment": {"id": 42, "environment": "production"},
            "deployment_status": {"state": state, "description": "", "log_url": "", "environment_url": ""},
        }

    async def test_success_triggers_regression_check(self):
        with patch(
            "backend.services.enterprise_github_integration._check_deploy_regression",
            new=AsyncMock(return_value=None),
        ) as mock_check:
            await github_integration.process_and_wire("deployment_status", self._payload("success"))
            mock_check.assert_awaited_once()

    async def test_pending_does_not_trigger_regression_check(self):
        with patch(
            "backend.services.enterprise_github_integration._check_deploy_regression",
            new=AsyncMock(return_value=None),
        ) as mock_check:
            await github_integration.process_and_wire("deployment_status", self._payload("pending"))
            mock_check.assert_not_awaited()

    async def test_failure_does_not_trigger_regression_check(self):
        with patch(
            "backend.services.enterprise_github_integration._check_deploy_regression",
            new=AsyncMock(return_value=None),
        ) as mock_check:
            await github_integration.process_and_wire("deployment_status", self._payload("failure"))
            mock_check.assert_not_awaited()
