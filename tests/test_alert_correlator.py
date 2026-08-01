from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_alert_correlator import (
    IncidentHistoryStore,
    attach_signal,
    correlate_and_report,
)

@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield IncidentHistoryStore(file_path=Path(tmpdir) / "incidents.json")


class TestIncidentHistoryStore:
    def test_find_open_returns_none_when_no_incidents(self, store):
        assert store.find_open("org/repo") is None

    def test_open_incident_then_find_open_returns_it(self, store):
        store.open_incident("org/repo", "OPS-1", {"source": "x", "summary": "y", "severity": "warning", "detected_at": "t"})
        found = store.find_open("org/repo")
        assert found is not None
        assert found["ticket_key"] == "OPS-1"

    def test_find_open_ignores_other_services(self, store):
        store.open_incident("org/repo-a", "OPS-1", {"source": "x", "summary": "y", "severity": "warning", "detected_at": "t"})
        assert store.find_open("org/repo-b") is None

    def test_find_open_ignores_stale_incidents(self, store):
        entry = store.open_incident("org/repo", "OPS-1", {"source": "x", "summary": "y", "severity": "warning", "detected_at": "t"})
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        entry["last_signal_at"] = stale_time
        store._incidents[0]["last_signal_at"] = stale_time
        assert store.find_open("org/repo", window_minutes=30) is None

    def test_append_signal_increments_suppressed_count(self, store):
        entry = store.open_incident("org/repo", "OPS-1", {"source": "x", "summary": "y", "severity": "warning", "detected_at": "t"})
        store.append_signal(entry["incident_id"], {"source": "z", "summary": "w", "severity": "info", "detected_at": "t2"})
        updated = store.find_open("org/repo")
        assert updated["suppressed_count"] == 1
        assert len(updated["signals"]) == 2

    def test_list_recent_respects_limit(self, store):
        for i in range(5):
            store.open_incident(f"svc{i}", None, {"source": "x", "summary": "y", "severity": "warning", "detected_at": "t"})
        assert len(store.list_recent(limit=2)) == 2


@pytest.mark.asyncio
class TestCorrelateAndReport:
    async def test_first_signal_calls_reporter_and_opens_incident(self, store):
        reporter = AsyncMock(return_value={"key": "OPS-42"})
        with patch("backend.services.enterprise_alert_correlator.incident_history_store", store):
            result = await correlate_and_report("deploy_regression", "org/repo", "p95 latency spike", reporter)

        reporter.assert_awaited_once()
        assert result == {"key": "OPS-42"}
        assert store.find_open("org/repo")["ticket_key"] == "OPS-42"

    async def test_second_signal_within_window_suppresses_reporter(self, store):
        reporter1 = AsyncMock(return_value={"key": "OPS-42"})
        reporter2 = AsyncMock(return_value={"key": "OPS-99"})
        with patch("backend.services.enterprise_alert_correlator.incident_history_store", store), \
             patch("backend.services.enterprise_alert_incident_reasoner.generate_incident_hypothesis", new=AsyncMock(return_value=None)), \
             patch("backend.services.enterprise_alert_incident_reporter.comment_correlated_signal", new=AsyncMock(return_value=True)) as mock_comment:
            await correlate_and_report("deploy_regression", "org/repo", "p95 latency spike", reporter1)
            result = await correlate_and_report("flaky_test", "org/repo", "CI flaky", reporter2)

        reporter2.assert_not_awaited()
        assert result["suppressed"] is True
        assert result["ticket_key"] == "OPS-42"
        assert result["signal_count"] == 2
        mock_comment.assert_awaited_once()

    async def test_signal_outside_window_opens_a_fresh_incident(self, store):
        reporter1 = AsyncMock(return_value={"key": "OPS-42"})
        reporter2 = AsyncMock(return_value={"key": "OPS-99"})
        with patch("backend.services.enterprise_alert_correlator.incident_history_store", store):
            await correlate_and_report("deploy_regression", "org/repo", "first", reporter1)
            # simulate the incident having gone stale
            store._incidents[0]["last_signal_at"] = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
            result = await correlate_and_report("deploy_regression", "org/repo", "second", reporter2)

        reporter2.assert_awaited_once()
        assert result == {"key": "OPS-99"}

    async def test_correlated_signal_carries_when_reporter_returned_no_ticket(self, store):
        """First signal's reporter fails to file a ticket (e.g. Jira down) —
        the incident still opens (with ticket_key=None) so a second signal
        still correlates rather than silently filing its own ticket too."""
        reporter1 = AsyncMock(return_value=None)
        reporter2 = AsyncMock(return_value={"key": "OPS-1"})
        with patch("backend.services.enterprise_alert_correlator.incident_history_store", store), \
             patch("backend.services.enterprise_alert_incident_reasoner.generate_incident_hypothesis", new=AsyncMock(return_value=None)), \
             patch("backend.services.enterprise_alert_incident_reporter.comment_correlated_signal", new=AsyncMock(return_value=False)):
            first = await correlate_and_report("deploy_regression", "org/repo", "first", reporter1)
            second = await correlate_and_report("flaky_test", "org/repo", "second", reporter2)

        assert first is None
        reporter2.assert_not_awaited()
        assert second["suppressed"] is True
        assert second["ticket_key"] is None


@pytest.mark.asyncio
class TestAttachSignal:
    async def test_noop_when_no_open_incident(self, store):
        with patch("backend.services.enterprise_alert_correlator.incident_history_store", store):
            result = await attach_signal("rollback", "org/repo", "rollback triggered")
        assert result is None

    async def test_attaches_to_open_incident(self, store):
        store.open_incident("org/repo", "OPS-1", {"source": "deploy_regression", "summary": "x", "severity": "critical", "detected_at": "t"})
        with patch("backend.services.enterprise_alert_correlator.incident_history_store", store):
            result = await attach_signal("rollback", "org/repo", "rollback triggered")
        assert result is not None
        assert result["suppressed_count"] == 1
        assert result["signals"][-1]["source"] == "rollback"
