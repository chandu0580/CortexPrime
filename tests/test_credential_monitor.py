from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_credential_monitor import (
    CredentialCheckHistoryStore,
    _days_until,
    check_all_credentials,
)

@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield CredentialCheckHistoryStore(file_path=Path(tmpdir) / "credential_history.json")


class TestDaysUntil:
    def test_returns_none_for_none_input(self):
        assert _days_until(None) is None

    def test_returns_positive_days_for_future_date(self):
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        assert _days_until(future) in (9, 10)

    def test_returns_negative_days_for_past_date(self):
        past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        result = _days_until(past)
        assert result is not None and result < 0

    def test_returns_none_for_unparseable_string(self):
        assert _days_until("not-a-date") is None

    def test_parses_github_advisory_header_format(self):
        # Real format observed from GitHub-Authentication-Token-Expiration,
        # e.g. "2026-10-29 12:25:55 UTC" — not ISO 8601.
        future_dt = datetime.now(timezone.utc) + timedelta(days=30)
        header_value = future_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        result = _days_until(header_value)
        assert result in (29, 30)


class TestCredentialCheckHistoryStore:
    def test_list_recent_newest_first(self, store):
        store.record("github", True)
        store.record("gitlab_ci", True)
        recent = store.list_recent()
        assert [r["connector_type"] for r in recent] == ["gitlab_ci", "github"]

    def test_list_latest_per_connector_dedupes(self, store):
        store.record("github", True, error=None)
        store.record("github", False, error="401")
        store.record("gitlab_ci", True)
        latest = store.list_latest_per_connector()
        assert len(latest) == 2
        github_latest = next(e for e in latest if e["connector_type"] == "github")
        assert github_latest["valid"] is False


@pytest.fixture
def _fake_registry():
    fake_github = MagicMock()
    fake_github.check_credential = AsyncMock(return_value={"valid": True, "expires_at": None, "expires_at_source": None, "error": None})
    fake_gitlab = MagicMock()
    fake_gitlab.check_credential = AsyncMock(return_value={"valid": True, "expires_at": None, "expires_at_source": None, "error": None})
    fake_jira = MagicMock()
    fake_jira.check_credential = AsyncMock(return_value={"valid": True, "expires_at": None, "expires_at_source": None, "error": None})

    def _get(connector_type):
        return {"github": fake_github, "gitlab_ci": fake_gitlab, "jira": fake_jira}.get(connector_type)

    return _get, fake_github, fake_gitlab, fake_jira


@pytest.mark.asyncio
class TestCheckAllCredentials:
    async def test_healthy_credentials_recorded_without_ticket(self, store, _fake_registry):
        get_fn, *_ = _fake_registry
        with patch("backend.connectors.registry.connector_registry.get", side_effect=get_fn), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value=None)) as mock_correlate:
            results = await check_all_credentials(history_store=store)

        assert len(results) == 3
        assert all(r["valid"] for r in results)
        mock_correlate.assert_not_awaited()

    async def test_skips_unregistered_connectors(self, store):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            results = await check_all_credentials(history_store=store)
        assert results == []

    async def test_failing_credential_routes_through_correlator(self, store, _fake_registry):
        get_fn, fake_github, _, _ = _fake_registry
        fake_github.check_credential = AsyncMock(return_value={"valid": False, "expires_at": None, "expires_at_source": None, "error": "GitHub API: 401 Unauthorized"})

        with patch("backend.connectors.registry.connector_registry.get", side_effect=get_fn), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value={"key": "OPS-1"})) as mock_correlate:
            results = await check_all_credentials(history_store=store)

        github_result = next(r for r in results if r["connector_type"] == "github")
        assert github_result["valid"] is False
        assert github_result["ticket_key"] == "OPS-1"
        calls = [c for c in mock_correlate.call_args_list if c.kwargs["service"] == "github"]
        assert len(calls) == 1
        assert calls[0].kwargs["severity"] == "critical"

    async def test_expiring_soon_credential_routes_through_correlator(self, store, _fake_registry):
        get_fn, _, fake_gitlab, _ = _fake_registry
        soon = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        fake_gitlab.check_credential = AsyncMock(return_value={"valid": True, "expires_at": soon, "expires_at_source": "api", "error": None})

        with patch("backend.connectors.registry.connector_registry.get", side_effect=get_fn), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value={"key": "OPS-2"})) as mock_correlate:
            results = await check_all_credentials(history_store=store)

        gitlab_result = next(r for r in results if r["connector_type"] == "gitlab_ci")
        assert gitlab_result["valid"] is True
        assert gitlab_result["days_until_expiry"] in (4, 5)
        assert gitlab_result["ticket_key"] == "OPS-2"
        calls = [c for c in mock_correlate.call_args_list if c.kwargs["service"] == "gitlab_ci"]
        assert calls[0].kwargs["severity"] == "warning"

    async def test_far_future_expiry_does_not_alert(self, store, _fake_registry):
        get_fn, _, fake_gitlab, _ = _fake_registry
        far = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
        fake_gitlab.check_credential = AsyncMock(return_value={"valid": True, "expires_at": far, "expires_at_source": "api", "error": None})

        with patch("backend.connectors.registry.connector_registry.get", side_effect=get_fn), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value=None)) as mock_correlate:
            await check_all_credentials(history_store=store)

        calls = [c for c in mock_correlate.call_args_list if c.kwargs["service"] == "gitlab_ci"]
        assert len(calls) == 0

    async def test_check_raising_is_recorded_as_invalid_not_propagated(self, store, _fake_registry):
        get_fn, fake_github, _, _ = _fake_registry
        fake_github.check_credential = AsyncMock(side_effect=RuntimeError("connector exploded"))

        with patch("backend.connectors.registry.connector_registry.get", side_effect=get_fn), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value=None)):
            results = await check_all_credentials(history_store=store)  # must not raise

        github_result = next(r for r in results if r["connector_type"] == "github")
        assert github_result["valid"] is False
        assert "connector exploded" in github_result["error"]
