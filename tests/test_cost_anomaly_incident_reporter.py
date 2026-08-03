from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_cost_anomaly_incident_reporter import (
    DEFAULT_ISSUE_TYPE,
    DEFAULT_JIRA_PROJECT_KEY,
    build_cost_anomaly_incident_description,
    report_cost_anomaly_incident,
)

_GAPS = [{"gap": "cost_spike", "severity": "critical", "description": "Spend for 'openai' today is $10.0000 - 20.0x its trailing average (baseline $0.50/day)."}]


class TestBuildCostAnomalyIncidentDescription:
    def test_includes_core_fields(self):
        desc = build_cost_anomaly_incident_description("openai", 10.0, _GAPS, "critical")
        assert "openai" in desc
        assert "critical" in desc
        assert "$10.0000" in desc


@pytest.mark.asyncio
class TestReportCostAnomalyIncident:
    async def test_returns_none_when_jira_not_registered(self):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await report_cost_anomaly_incident("openai", 10.0, _GAPS, "critical")
        assert result is None

    async def test_returns_none_when_jira_unavailable(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "unavailable"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_cost_anomaly_incident("openai", 10.0, _GAPS, "critical")
        assert result is None

    async def test_creates_issue_with_correct_fields(self, monkeypatch):
        monkeypatch.delenv("COST_ANOMALY_JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("COST_ANOMALY_JIRA_ISSUE_TYPE", raising=False)
        monkeypatch.delenv("COST_ANOMALY_AUTO_FIX", raising=False)
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-9"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_cost_anomaly_incident("openai", 10.0, _GAPS, "critical")

        assert result == {"key": "OPS-9"}
        _, kwargs = fake_jira.create_issue.call_args
        assert kwargs["project_key"] == DEFAULT_JIRA_PROJECT_KEY
        assert kwargs["issue_type"] == DEFAULT_ISSUE_TYPE
        assert "openai" in kwargs["title"]

    async def test_returns_none_when_create_issue_raises(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(side_effect=RuntimeError("Jira API: HTTP 500"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_cost_anomaly_incident("openai", 10.0, _GAPS, "critical")
        assert result is None

    async def test_auto_fix_not_triggered_when_flag_off(self, monkeypatch):
        monkeypatch.setenv("COST_ANOMALY_AUTO_FIX", "false")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-9"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_cost_anomaly_fix_executor.disable_provider_temporarily", new=AsyncMock()) as mock_fix:
            await report_cost_anomaly_incident("openai", 10.0, _GAPS, "critical")
        mock_fix.assert_not_awaited()

    async def test_auto_fix_triggered_when_flag_on(self, monkeypatch):
        monkeypatch.setenv("COST_ANOMALY_AUTO_FIX", "true")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-9"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_cost_anomaly_fix_executor.disable_provider_temporarily", new=AsyncMock()) as mock_fix:
            await report_cost_anomaly_incident("openai", 10.0, _GAPS, "critical")
        mock_fix.assert_awaited_once()
        assert mock_fix.call_args.kwargs["provider"] == "openai"
        assert mock_fix.call_args.kwargs["today_cost"] == 10.0

    async def test_auto_fix_failure_does_not_break_ticket_result(self, monkeypatch):
        monkeypatch.setenv("COST_ANOMALY_AUTO_FIX", "true")
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-9"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_cost_anomaly_fix_executor.disable_provider_temporarily", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await report_cost_anomaly_incident("openai", 10.0, _GAPS, "critical")
        assert result == {"key": "OPS-9"}
