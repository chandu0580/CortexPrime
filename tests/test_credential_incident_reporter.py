from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_credential_incident_reporter import (
    DEFAULT_ISSUE_TYPE,
    DEFAULT_JIRA_PROJECT_KEY,
    build_credential_incident_description,
    report_credential_incident,
)


class TestBuildCredentialIncidentDescription:
    def test_failing_kind_includes_error(self):
        desc = build_credential_incident_description("github", "failing", error="401 Unauthorized")
        assert "github" in desc
        assert "401 Unauthorized" in desc
        assert "already invalid" in desc

    def test_expiring_soon_kind_includes_days_and_date(self):
        desc = build_credential_incident_description("gitlab_ci", "expiring_soon", expires_at="2026-12-01", expires_at_source="api", days_until_expiry=5)
        assert "5 day(s)" in desc
        assert "2026-12-01" in desc
        assert "introspection API" in desc

    def test_expiring_soon_advisory_header_flags_caveat(self):
        desc = build_credential_incident_description("github", "expiring_soon", expires_at="2026-12-01", expires_at_source="advisory_header", days_until_expiry=5)
        assert "advisory only" in desc


@pytest.mark.asyncio
class TestReportCredentialIncident:
    async def test_returns_none_when_jira_not_registered(self):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await report_credential_incident("github", "failing", error="401")
        assert result is None

    async def test_returns_none_when_jira_unavailable(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "unavailable"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_credential_incident("github", "failing", error="401")
        assert result is None

    async def test_creates_issue_with_correct_fields_when_healthy(self, monkeypatch):
        monkeypatch.delenv("CREDENTIAL_JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("CREDENTIAL_JIRA_ISSUE_TYPE", raising=False)
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-1", "id": "1"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_credential_incident("github", "failing", error="401 Unauthorized")

        assert result == {"key": "OPS-1", "id": "1"}
        _, kwargs = fake_jira.create_issue.call_args
        assert kwargs["project_key"] == DEFAULT_JIRA_PROJECT_KEY
        assert kwargs["issue_type"] == DEFAULT_ISSUE_TYPE
        assert "github" in kwargs["title"]

    async def test_returns_none_when_create_issue_raises(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(side_effect=RuntimeError("Jira API: HTTP 500"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_credential_incident("github", "failing", error="401")
        assert result is None
