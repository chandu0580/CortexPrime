from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_flaky_test_detector import FlakyTestHistoryStore
from backend.services.enterprise_flaky_test_incident_reporter import (
    DEFAULT_ISSUE_TYPE,
    DEFAULT_JIRA_PROJECT_KEY,
    build_flaky_incident_description,
    report_flaky_incident,
)


@pytest.fixture
def history_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield FlakyTestHistoryStore(file_path=Path(tmpdir) / "history.json")


def _occurrences():
    return [
        {"detected_at": "2026-08-01T10:00:00+00:00", "run_key": "gh:org/repo:1"},
        {"detected_at": "2026-07-30T10:00:00+00:00", "run_key": "gh:org/repo:2"},
    ]


class TestBuildFlakyIncidentDescription:
    def test_includes_service_and_workflow_name(self):
        desc = build_flaky_incident_description("org/repo", "CI", _occurrences(), "job X failed then passed")
        assert "org/repo" in desc
        assert "CI" in desc

    def test_includes_occurrence_count(self):
        desc = build_flaky_incident_description("org/repo", "CI", _occurrences(), "evidence")
        assert "2 time(s)" in desc

    def test_includes_latest_evidence(self):
        desc = build_flaky_incident_description("org/repo", "CI", _occurrences(), "job X failed then passed")
        assert "job X failed then passed" in desc

    def test_includes_occurrence_history_entries(self):
        desc = build_flaky_incident_description("org/repo", "CI", _occurrences(), "evidence")
        assert "gh:org/repo:1" in desc
        assert "gh:org/repo:2" in desc

    def test_truncates_long_occurrence_history(self):
        occs = [{"detected_at": f"t{i}", "run_key": f"run:{i}"} for i in range(15)]
        desc = build_flaky_incident_description("org/repo", "CI", occs, "evidence")
        assert "5 more not shown" in desc

    def test_omits_hypothesis_section_when_none(self):
        desc = build_flaky_incident_description("org/repo", "CI", _occurrences(), "evidence", hypothesis=None)
        assert "AI-generated" not in desc

    def test_includes_hypothesis_section_when_given(self):
        desc = build_flaky_incident_description("org/repo", "CI", _occurrences(), "evidence", hypothesis="Likely a race condition.")
        assert "AI-generated hypothesis" in desc
        assert "unverified" in desc
        assert "Likely a race condition." in desc


@pytest.mark.asyncio
class TestReportFlakyIncident:
    async def test_returns_none_when_jira_not_registered(self, history_store):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await report_flaky_incident("org/repo", "CI", "evidence", [], history_store=history_store)
        assert result is None

    async def test_returns_none_when_jira_unavailable(self, history_store):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "unavailable"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_flaky_incident("org/repo", "CI", "evidence", [], history_store=history_store)
        assert result is None

    async def test_creates_issue_with_correct_fields_when_healthy(self, history_store, monkeypatch):
        # Real deployments may set FLAKY_JIRA_PROJECT_KEY/FLAKY_JIRA_ISSUE_TYPE
        # (e.g. backend/.env) — clear them so this test genuinely exercises
        # the hardcoded defaults regardless of what's in the environment
        # this suite happens to run in.
        monkeypatch.delenv("FLAKY_JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("FLAKY_JIRA_ISSUE_TYPE", raising=False)
        history_store.record("org/repo", "CI", "run:1", "evidence 1")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-201", "id": "2001"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_flaky_test_root_cause_reasoner.generate_flaky_hypothesis", new=AsyncMock(return_value=None)):
            result = await report_flaky_incident("org/repo", "CI", "job X failed then passed", [], history_store=history_store)

        assert result == {"key": "OPS-201", "id": "2001"}
        fake_jira.create_issue.assert_awaited_once()
        _, kwargs = fake_jira.create_issue.call_args
        assert kwargs["project_key"] == DEFAULT_JIRA_PROJECT_KEY
        assert kwargs["issue_type"] == DEFAULT_ISSUE_TYPE
        assert "org/repo" in kwargs["title"]
        assert "CI" in kwargs["title"]

    async def test_only_includes_occurrences_for_this_service_and_workflow(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        history_store.record("other/repo", "CI", "run:2", "evidence")
        history_store.record("org/repo", "other-workflow", "run:3", "evidence")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-202"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_flaky_test_root_cause_reasoner.generate_flaky_hypothesis", new=AsyncMock(return_value=None)):
            await report_flaky_incident("org/repo", "CI", "evidence", [], history_store=history_store)

        _, kwargs = fake_jira.create_issue.call_args
        assert "1 time(s)" in kwargs["description"]

    async def test_includes_hypothesis_in_ticket_when_available(self, history_store):
        history_store.record("org/repo", "CI", "run:1", "evidence")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-203"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch(
                 "backend.services.enterprise_flaky_test_root_cause_reasoner.generate_flaky_hypothesis",
                 new=AsyncMock(return_value="Likely a shared test-database fixture."),
             ) as mock_hyp:
            await report_flaky_incident("org/repo", "CI", "evidence", [{"job_name": "x"}], history_store=history_store)

        mock_hyp.assert_awaited_once()
        _, kwargs = fake_jira.create_issue.call_args
        assert "Likely a shared test-database fixture." in kwargs["description"]

    async def test_returns_none_when_create_issue_raises(self, history_store):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(side_effect=RuntimeError("Jira API: HTTP 500"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_flaky_test_root_cause_reasoner.generate_flaky_hypothesis", new=AsyncMock(return_value=None)):
            result = await report_flaky_incident("org/repo", "CI", "evidence", [], history_store=history_store)
        assert result is None
