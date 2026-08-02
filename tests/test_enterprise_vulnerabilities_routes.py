"""Tests for /api/vulnerabilities — status and on-demand check endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_vulnerabilities_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestGetVulnerabilityStatus:
    def test_returns_latest_and_recent(self):
        fake_store = MagicMock()
        fake_store.list_latest_per_alert.return_value = [{"repo": "o/r", "alert_number": 1}]
        fake_store.list_recent.return_value = [{"repo": "o/r", "alert_number": 1}]

        with patch("backend.services.enterprise_vulnerability_monitor.vulnerability_history_store", fake_store):
            resp = _make_client().get("/api/vulnerabilities/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["latest"] == [{"repo": "o/r", "alert_number": 1}]
        assert body["recent"] == [{"repo": "o/r", "alert_number": 1}]

    def test_limit_passed_through(self):
        fake_store = MagicMock()
        fake_store.list_latest_per_alert.return_value = []
        fake_store.list_recent.return_value = []
        with patch("backend.services.enterprise_vulnerability_monitor.vulnerability_history_store", fake_store):
            resp = _make_client().get("/api/vulnerabilities/status?limit=5")

        assert resp.status_code == 200
        fake_store.list_recent.assert_called_once_with(5)

    def test_invalid_limit_rejected(self):
        resp = _make_client().get("/api/vulnerabilities/status?limit=0")
        assert resp.status_code == 422


class TestTriggerVulnerabilityCheck:
    def test_triggers_check_and_returns_results(self):
        with patch(
            "backend.services.enterprise_vulnerability_monitor.check_vulnerabilities",
            new=AsyncMock(return_value=[{"repo": "o/r", "alert_number": 1}]),
        ):
            resp = _make_client().post("/api/vulnerabilities/check")

        assert resp.status_code == 200
        assert resp.json() == {"checked": [{"repo": "o/r", "alert_number": 1}]}
