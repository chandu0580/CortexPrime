"""
Tests for the durable pending-check store backing deploy-regression checks
(backend.services.enterprise_github_integration.PendingDeployCheckStore),
and the startup recovery path that resumes checks in flight when the
process was restarted mid-wait.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_github_integration import (
    PendingDeployCheckStore,
    _check_deploy_regression,
    recover_pending_deploy_checks,
)

@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "pending_deploy_checks.json"
        with patch(
            "backend.services.enterprise_github_integration._PENDING_DEPLOY_CHECKS_FILE",
            temp_path,
        ):
            yield PendingDeployCheckStore()


class TestPendingDeployCheckStore:
    def test_starts_empty(self, temp_store):
        assert temp_store.list_pending() == []

    def test_add_then_list(self, temp_store):
        temp_store.add("svc::1", "svc", "1", {"repo_full_name": "svc"}, "2026-01-01T00:00:00+00:00")
        pending = temp_store.list_pending()
        assert len(pending) == 1
        assert pending[0]["check_id"] == "svc::1"
        assert pending[0]["service"] == "svc"

    def test_add_replaces_existing_same_check_id(self, temp_store):
        temp_store.add("svc::1", "svc", "1", {}, "2026-01-01T00:00:00+00:00")
        temp_store.add("svc::1", "svc", "1", {}, "2026-02-01T00:00:00+00:00")
        pending = temp_store.list_pending()
        assert len(pending) == 1
        assert pending[0]["check_due_at"] == "2026-02-01T00:00:00+00:00"

    def test_remove(self, temp_store):
        temp_store.add("svc::1", "svc", "1", {}, "2026-01-01T00:00:00+00:00")
        temp_store.remove("svc::1")
        assert temp_store.list_pending() == []

    def test_remove_nonexistent_is_a_noop(self, temp_store):
        temp_store.remove("does-not-exist")
        assert temp_store.list_pending() == []

    def test_persists_across_instances(self, temp_store):
        temp_store.add("svc::1", "svc", "1", {"a": 1}, "2026-01-01T00:00:00+00:00")
        # A fresh instance reading the same (patched) file should see it.
        reloaded = PendingDeployCheckStore()
        pending = reloaded.list_pending()
        assert len(pending) == 1
        assert pending[0]["ctx"] == {"a": 1}

    def test_clear(self, temp_store):
        temp_store.add("svc::1", "svc", "1", {}, "2026-01-01T00:00:00+00:00")
        temp_store.clear()
        assert temp_store.list_pending() == []


@pytest.mark.asyncio
class TestCheckDeployRegressionPersistence:
    async def test_schedule_persists_pending_record(self, temp_store):
        with patch("backend.services.enterprise_github_integration.pending_deploy_check_store", temp_store), \
             patch("asyncio.sleep", new=AsyncMock()):
            task = await _check_deploy_regression({"repo_full_name": "org/checkout-service", "deployment_id": 42})
            # Persisted synchronously, before the task even runs.
            pending = temp_store.list_pending()
            assert len(pending) == 1
            assert pending[0]["check_id"] == "org/checkout-service::42"
            await task  # drain
            # Removed once the check completes.
            assert temp_store.list_pending() == []

    async def test_pending_record_removed_even_if_check_raises(self, temp_store):
        with patch("backend.services.enterprise_github_integration.pending_deploy_check_store", temp_store), \
             patch("asyncio.sleep", new=AsyncMock()), \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(side_effect=RuntimeError("boom")),
             ):
            task = await _check_deploy_regression({"repo_full_name": "org/checkout-service", "deployment_id": 99})
            await task
            assert temp_store.list_pending() == []


@pytest.mark.asyncio
class TestRecoverPendingDeployChecks:
    async def test_recovers_overdue_check_immediately(self, temp_store):
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        temp_store.add("org/svc::7", "org/svc", "7", {"repo_full_name": "org/svc"}, past)

        with patch("backend.services.enterprise_github_integration.pending_deploy_check_store", temp_store), \
             patch(
                 "backend.services.enterprise_deploy_regression_detector.DeployRegressionDetector.check",
                 new=AsyncMock(return_value=_clean_verdict()),
             ):
            count = await recover_pending_deploy_checks()
            assert count == 1
            # Give the created task a tick to run and clean itself up.
            import asyncio
            await asyncio.sleep(0)
            await asyncio.sleep(0)

    async def test_recovers_future_check_with_remaining_delay(self, temp_store):
        future = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
        temp_store.add("org/svc::8", "org/svc", "8", {"repo_full_name": "org/svc"}, future)

        captured_delay = {}

        async def _fake_run(check_id, service, deployment_id, ctx, delay_seconds):
            captured_delay["value"] = delay_seconds

        with patch("backend.services.enterprise_github_integration.pending_deploy_check_store", temp_store), \
             patch(
                 "backend.services.enterprise_github_integration._run_deploy_regression_check",
                 new=_fake_run,
             ):
            count = await recover_pending_deploy_checks()
            assert count == 1
            import asyncio
            await asyncio.sleep(0)

        assert 25 <= captured_delay["value"] <= 30

    async def test_removes_malformed_record_without_scheduling(self, temp_store):
        temp_store.add("", "", "", {}, "2026-01-01T00:00:00+00:00")
        with patch("backend.services.enterprise_github_integration.pending_deploy_check_store", temp_store):
            count = await recover_pending_deploy_checks()
        assert count == 0
        assert temp_store.list_pending() == []

    async def test_no_pending_checks_returns_zero(self, temp_store):
        with patch("backend.services.enterprise_github_integration.pending_deploy_check_store", temp_store):
            count = await recover_pending_deploy_checks()
            assert count == 0


def _clean_verdict():
    from backend.services.enterprise_deploy_regression_detector import RegressionVerdict
    return RegressionVerdict(service="org/svc", deployment_id="7", regressed=False, reasons=[])
