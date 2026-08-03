from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_docker_health_incident_reporter import (
    DEFAULT_ISSUE_TYPE,
    DEFAULT_JIRA_PROJECT_KEY,
    build_docker_health_incident_description,
    report_docker_health_incident,
)

_GAPS = [{"gap": "crash_loop", "severity": "critical", "description": "Container restarted 5 times since the last check (restart_count 0 -> 5)."}]


class TestBuildDockerHealthIncidentDescription:
    def test_includes_core_fields(self):
        desc = build_docker_health_incident_description("cortex-web", _GAPS, "critical")
        assert "cortex-web" in desc
        assert "critical" in desc
        assert "restarted 5 times" in desc


@pytest.mark.asyncio
class TestReportDockerHealthIncident:
    async def test_returns_none_when_jira_not_registered(self):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await report_docker_health_incident("cortex-web", "abc123", _GAPS, "critical")
        assert result is None

    async def test_returns_none_when_jira_unavailable(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "unavailable"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_docker_health_incident("cortex-web", "abc123", _GAPS, "critical")
        assert result is None

    async def test_creates_issue_with_correct_fields(self, monkeypatch):
        monkeypatch.delenv("DOCKER_HEALTH_JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("DOCKER_HEALTH_JIRA_ISSUE_TYPE", raising=False)
        monkeypatch.delenv("DOCKER_HEALTH_AUTO_FIX", raising=False)
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-9"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_docker_health_incident("cortex-web", "abc123", _GAPS, "critical")

        assert result == {"key": "OPS-9"}
        _, kwargs = fake_jira.create_issue.call_args
        assert kwargs["project_key"] == DEFAULT_JIRA_PROJECT_KEY
        assert kwargs["issue_type"] == DEFAULT_ISSUE_TYPE
        assert "cortex-web" in kwargs["title"]

    async def test_returns_none_when_create_issue_raises(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(side_effect=RuntimeError("Jira API: HTTP 500"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_docker_health_incident("cortex-web", "abc123", _GAPS, "critical")
        assert result is None

    async def test_auto_fix_not_triggered_when_flag_off(self, monkeypatch):
        monkeypatch.setenv("DOCKER_HEALTH_AUTO_FIX", "false")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-9"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_docker_health_fix_executor.restart_crashlooping_container", new=AsyncMock()) as mock_fix:
            await report_docker_health_incident("cortex-web", "abc123", _GAPS, "critical")
        mock_fix.assert_not_awaited()

    async def test_auto_fix_triggered_when_flag_on(self, monkeypatch):
        monkeypatch.setenv("DOCKER_HEALTH_AUTO_FIX", "true")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-9"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_docker_health_fix_executor.restart_crashlooping_container", new=AsyncMock()) as mock_fix:
            await report_docker_health_incident("cortex-web", "abc123", _GAPS, "critical")
        mock_fix.assert_awaited_once()
        assert mock_fix.call_args.kwargs["container_name"] == "cortex-web"
        assert mock_fix.call_args.kwargs["container_id"] == "abc123"

    async def test_auto_fix_failure_does_not_break_ticket_result(self, monkeypatch):
        monkeypatch.setenv("DOCKER_HEALTH_AUTO_FIX", "true")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-9"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_docker_health_fix_executor.restart_crashlooping_container", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await report_docker_health_incident("cortex-web", "abc123", _GAPS, "critical")
        assert result == {"key": "OPS-9"}
