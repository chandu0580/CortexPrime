"""
Tests for DeployCheckHistoryStore — the durable record of *completed*
deploy-regression checks (PendingDeployCheckStore only tracks checks
still in flight; the moment one finishes, its pending record disappears).
This is what a UI reads to show what actually happened.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_github_integration import (
    MAX_DEPLOY_CHECK_HISTORY,
    DeployCheckHistoryStore,
    _run_deploy_regression_check,
)


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "deploy_check_history.json"
        with patch(
            "backend.services.enterprise_github_integration._DEPLOY_CHECK_HISTORY_FILE",
            temp_path,
        ):
            yield DeployCheckHistoryStore()


class TestDeployCheckHistoryStore:
    def test_starts_empty(self, temp_store):
        assert temp_store.list_recent() == []

    def test_record_then_list(self, temp_store):
        temp_store.record("svc::1", "svc", "1", regressed=True, reasons=["p95 +30%"], ticket_key="OPS-1")
        recent = temp_store.list_recent()
        assert len(recent) == 1
        assert recent[0]["service"] == "svc"
        assert recent[0]["regressed"] is True
        assert recent[0]["reasons"] == ["p95 +30%"]
        assert recent[0]["ticket_key"] == "OPS-1"
        assert "checked_at" in recent[0]

    def test_most_recent_first(self, temp_store):
        temp_store.record("svc::1", "svc", "1", regressed=False, reasons=[])
        temp_store.record("svc::2", "svc", "2", regressed=True, reasons=["x"])
        recent = temp_store.list_recent()
        assert recent[0]["deployment_id"] == "2"
        assert recent[1]["deployment_id"] == "1"

    def test_respects_limit(self, temp_store):
        for i in range(5):
            temp_store.record(f"svc::{i}", "svc", str(i), regressed=False, reasons=[])
        assert len(temp_store.list_recent(limit=2)) == 2

    def test_caps_total_history_size(self, temp_store):
        for i in range(MAX_DEPLOY_CHECK_HISTORY + 10):
            temp_store.record(f"svc::{i}", "svc", str(i), regressed=False, reasons=[])
        assert len(temp_store.list_recent(limit=MAX_DEPLOY_CHECK_HISTORY + 50)) == MAX_DEPLOY_CHECK_HISTORY

    def test_ticket_key_defaults_to_none(self, temp_store):
        temp_store.record("svc::1", "svc", "1", regressed=False, reasons=[])
        assert temp_store.list_recent()[0]["ticket_key"] is None

    def test_persists_across_instances(self, temp_store):
        temp_store.record("svc::1", "svc", "1", regressed=True, reasons=["x"], ticket_key="OPS-9")
        reloaded = DeployCheckHistoryStore()
        assert reloaded.list_recent()[0]["ticket_key"] == "OPS-9"

    def test_clear(self, temp_store):
        temp_store.record("svc::1", "svc", "1", regressed=False, reasons=[])
        temp_store.clear()
        assert temp_store.list_recent() == []


@pytest.mark.asyncio
class TestRunDeployRegressionCheckRecordsHistory:
    async def test_records_clean_outcome(self, temp_store):
        from backend.services.enterprise_deploy_regression_detector import RegressionVerdict

        clean_verdict = RegressionVerdict(service="org/svc", deployment_id="1", regressed=False, reasons=[])
        with patch("backend.services.enterprise_github_integration.deploy_check_history_store", temp_store), \
             patch("backend.services.enterprise_github_integration.pending_deploy_check_store") as mock_pending, \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(return_value=clean_verdict),
             ):
            await _run_deploy_regression_check("org/svc::1", "org/svc", "1", {}, delay_seconds=0)

        recorded = temp_store.list_recent()
        assert len(recorded) == 1
        assert recorded[0]["regressed"] is False
        assert recorded[0]["ticket_key"] is None
        mock_pending.remove.assert_called_once_with("org/svc::1")

    async def test_records_regressed_outcome_with_ticket_key(self, temp_store):
        from backend.services.enterprise_deploy_regression_detector import RegressionVerdict

        bad_verdict = RegressionVerdict(service="org/svc", deployment_id="2", regressed=True, reasons=["p95 +50%"])
        with patch("backend.services.enterprise_github_integration.deploy_check_history_store", temp_store), \
             patch("backend.services.enterprise_github_integration.pending_deploy_check_store"), \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(return_value=bad_verdict),
             ), \
             patch(
                 "backend.services.enterprise_deploy_incident_reporter.report_incident",
                 new=AsyncMock(return_value={"key": "OPS-42"}),
             ):
            await _run_deploy_regression_check("org/svc::2", "org/svc", "2", {}, delay_seconds=0)

        recorded = temp_store.list_recent()
        assert recorded[0]["regressed"] is True
        assert recorded[0]["ticket_key"] == "OPS-42"
        assert recorded[0]["reasons"] == ["p95 +50%"]
