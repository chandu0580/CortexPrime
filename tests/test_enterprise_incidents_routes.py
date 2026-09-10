"""Tests for GET /api/incidents — exposes recent correlated incidents for
the frontend to display, regardless of which detector's signal opened
each one.

Phase 11.1: the route requires a verified identity (incident history is
tenant data held in a tenant-unaware store); the identity is overridden
here so the tests stay about the route's own behaviour."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_incidents_routes import router
from backend.auth.dependencies import require_user


def _make_client(authenticated: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    if authenticated:
        app.dependency_overrides[require_user] = lambda: {"sub": "op", "role": "operator"}
    return TestClient(app)


class TestListIncidents:
    def test_requires_authentication(self):
        assert _make_client(authenticated=False).get("/api/incidents").status_code == 401

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
