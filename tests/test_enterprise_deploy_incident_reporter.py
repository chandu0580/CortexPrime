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

    def test_omits_hypothesis_section_when_none(self):
        desc = build_incident_description(_verdict(), _ctx(), hypothesis=None)
        assert "AI-generated" not in desc

    def test_includes_hypothesis_section_when_given(self):
        desc = build_incident_description(_verdict(), _ctx(), hypothesis="Looks like the new index was dropped.")
        assert "AI-generated root-cause hypothesis" in desc
        assert "unverified" in desc
        assert "Looks like the new index was dropped." in desc


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

    async def test_creates_issue_with_correct_fields_when_healthy(self, monkeypatch):
        # Real deployments may set DEPLOY_JIRA_PROJECT_KEY/DEPLOY_JIRA_ISSUE_TYPE
        # (e.g. backend/.env) — clear them so this test genuinely exercises
        # the hardcoded defaults regardless of what's in the environment
        # this suite happens to run in.
        monkeypatch.delenv("DEPLOY_JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("DEPLOY_JIRA_ISSUE_TYPE", raising=False)
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-101", "id": "1001"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_deploy_root_cause_reasoner.generate_hypothesis", new=AsyncMock(return_value=None)):
            result = await report_incident(_verdict(), _ctx())

        assert result == {"key": "OPS-101", "id": "1001"}
        fake_jira.create_issue.assert_awaited_once()
        _, kwargs = fake_jira.create_issue.call_args
        assert kwargs["project_key"] == DEFAULT_JIRA_PROJECT_KEY
        assert kwargs["issue_type"] == DEFAULT_ISSUE_TYPE
        assert "checkout-service" in kwargs["title"]
        assert "p95 latency +25.9%" in kwargs["description"]

    async def test_includes_hypothesis_in_ticket_when_available(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-102", "id": "1002"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch(
                 "backend.services.enterprise_deploy_root_cause_reasoner.generate_hypothesis",
                 new=AsyncMock(return_value="The new N+1 query in getCartTotals likely explains this."),
             ) as mock_hyp:
            result = await report_incident(_verdict(), _ctx())

        assert result == {"key": "OPS-102", "id": "1002"}
        mock_hyp.assert_awaited_once()
        _, kwargs = fake_jira.create_issue.call_args
        assert "The new N+1 query in getCartTotals likely explains this." in kwargs["description"]
        assert "AI-generated root-cause hypothesis" in kwargs["description"]

    async def test_omits_hypothesis_from_ticket_when_unavailable(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(return_value={"key": "OPS-103", "id": "1003"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_deploy_root_cause_reasoner.generate_hypothesis", new=AsyncMock(return_value=None)):
            await report_incident(_verdict(), _ctx())

        _, kwargs = fake_jira.create_issue.call_args
        assert "AI-generated" not in kwargs["description"]

    async def test_returns_none_when_create_issue_raises(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.create_issue = AsyncMock(side_effect=RuntimeError("Jira API: HTTP 500"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira), \
             patch("backend.services.enterprise_deploy_root_cause_reasoner.generate_hypothesis", new=AsyncMock(return_value=None)):
            result = await report_incident(_verdict(), _ctx())
        assert result is None
