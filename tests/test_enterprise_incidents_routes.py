"""Tests for GET /api/incidents — exposes recent correlated incidents for
the frontend to display, regardless of which detector's signal opened
each one."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_incidents_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestListIncidents:
    def test_returns_recent(self):
        fake_history_store = MagicMock()
        fake_history_store.list_recent.return_value = [
            {"incident_id": "abc", "service": "org/repo", "suppressed_count": 2}
        ]

        with patch(
            "backend.services.enterprise_alert_correlator.incident_history_store", fake_history_store,
        ):
            resp = _make_client().get("/api/incidents")

        assert resp.status_code == 200
        body = resp.json()
        assert body["recent"] == [{"incident_id": "abc", "service": "org/repo", "suppressed_count": 2}]

    def test_limit_passed_through(self):
        fake_history_store = MagicMock()
        fake_history_store.list_recent.return_value = []
        with patch(
            "backend.services.enterprise_alert_correlator.incident_history_store", fake_history_store,
        ):
            resp = _make_client().get("/api/incidents?limit=5")

        assert resp.status_code == 200
        fake_history_store.list_recent.assert_called_once_with(5)

    def test_invalid_limit_rejected(self):
        resp = _make_client().get("/api/incidents?limit=0")
        assert resp.status_code == 422
