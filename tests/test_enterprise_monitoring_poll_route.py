"""Test for POST /api/monitoring/poll — confirms it delegates to the same
evaluate_event_against_rules() shared helper the continuous poll loop now
uses too (see test_enterprise_watchers_polling.py), rather than the
duplicate inline logic it had before."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_monitoring_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestTriggerPoll:
    def test_aggregates_results_across_events(self):
        events = [
            {"connector_type": "github", "event_type": "issue_opened"},
            {"connector_type": "jira", "event_type": "issue_created"},
        ]
        with patch(
            "backend.api.enterprise_monitoring_routes.watcher_manager.poll_once",
            new=AsyncMock(return_value=events),
        ), patch(
            "backend.api.enterprise_monitoring_routes.evaluate_event_against_rules",
            new=AsyncMock(side_effect=[
                {"rules_matched": 1, "missions_created": 1},
                {"rules_matched": 2, "missions_created": 0},
            ]),
        ) as mock_eval:
            resp = _make_client().post("/api/monitoring/poll")

        assert resp.status_code == 200
        body = resp.json()
        assert body["events_detected"] == 2
        assert body["rules_matched"] == 3
        assert body["missions_created"] == 1
        assert mock_eval.await_count == 2

    def test_no_events_returns_zeroed_summary(self):
        with patch(
            "backend.api.enterprise_monitoring_routes.watcher_manager.poll_once",
            new=AsyncMock(return_value=[]),
        ):
            resp = _make_client().post("/api/monitoring/poll")

        assert resp.status_code == 200
        assert resp.json() == {
            "status": "completed", "events_detected": 0, "rules_matched": 0, "missions_created": 0,
        }

    def test_poll_failure_returns_500(self):
        with patch(
            "backend.api.enterprise_monitoring_routes.watcher_manager.poll_once",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            resp = _make_client().post("/api/monitoring/poll")
        assert resp.status_code == 500
