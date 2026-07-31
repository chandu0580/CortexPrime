from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_deploy_incident_reporter import (
    DEFAULT_ISSUE_TYPE,
    DEFAULT_JIRA_PROJECT_KEY,
    build_incident_description,
    report_incident,
)
from backend.services.enterprise_deploy_regression_detector import MetricWindow, RegressionVerdict

def _verdict(regressed=True, reasons=None) -> RegressionVerdict:
    return RegressionVerdict(
        service="checkout-service",
        deployment_id="42",
        regressed=regressed,
        reasons=reasons or ["p95 latency +25.9% (0.194s -> 0.245s)"],
        before=MetricWindow(label="before", p95_latency_seconds=0.194, error_rate=0.0),
        after=MetricWindow(label="after", p95_latency_seconds=0.245, error_rate=0.06),
    )


def _ctx() -> dict:
    return {
        "environment": "production",
        "sender": "ops-bot",
        "deployment_log_url": "https://example.com/log/42",
    }


class TestBuildIncidentDescription:
    def test_includes_service_and_deployment_id(self):
        desc = build_incident_description(_verdict(), _ctx())
        assert "checkout-service" in desc
        assert "42" in desc

    def test_includes_the_real_evidence_reasons(self):
        desc = build_incident_description(_verdict(), _ctx())
        assert "p95 latency +25.9%" in desc

    def test_includes_environment_and_sender(self):
        desc = build_incident_description(_verdict(), _ctx())
        assert "production" in desc
        assert "ops-bot" in desc

    def test_flags_as_correlation_not_confirmed_cause(self):
        desc = build_incident_description(_verdict(), _ctx())
        assert "not a" in desc and "confirmed root cause" in desc


@pytest.mark.asyncio
class TestReportIncident:
    async def test_returns_none_when_not_regressed(self):
        result = await report_incident(_verdict(regressed=False), _ctx())
        assert result is None

    async def test_returns_none_when_jira_not_registered(self):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await report_incident(_verdict(), _ctx())
            assert result is None

    async def test_returns_none_when_jira_unavailable(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "unavailable"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_incident(_verdict(), _ctx())
            assert result is None

    async def test_creates_issue_with_correct_fields_when_healthy(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-101", "id": "1001"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_incident(_verdict(), _ctx())

        assert result == {"key": "OPS-101", "id": "1001"}
        fake_jira.create_issue.assert_awaited_once()
        _, kwargs = fake_jira.create_issue.call_args
        assert kwargs["project_key"] == DEFAULT_JIRA_PROJECT_KEY
        assert kwargs["issue_type"] == DEFAULT_ISSUE_TYPE
        assert "checkout-service" in kwargs["title"]
        assert "p95 latency +25.9%" in kwargs["description"]

    async def test_returns_none_when_create_issue_raises(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(side_effect=RuntimeError("Jira API: HTTP 500"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await report_incident(_verdict(), _ctx())
        assert result is None
