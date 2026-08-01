"""Tests for /api/credentials — status and on-demand check endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_credentials_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestGetCredentialStatus:
    def test_returns_latest_and_recent(self):
        fake_store = MagicMock()
        fake_store.list_latest_per_connector.return_value = [{"connector_type": "github", "valid": True}]
        fake_store.list_recent.return_value = [{"connector_type": "github", "valid": True}]

        with patch("backend.services.enterprise_credential_monitor.credential_history_store", fake_store):
            resp = _make_client().get("/api/credentials/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["latest"] == [{"connector_type": "github", "valid": True}]
        assert body["recent"] == [{"connector_type": "github", "valid": True}]

    def test_limit_passed_through(self):
        fake_store = MagicMock()
        fake_store.list_latest_per_connector.return_value = []
        fake_store.list_recent.return_value = []
        with patch("backend.services.enterprise_credential_monitor.credential_history_store", fake_store):
            resp = _make_client().get("/api/credentials/status?limit=5")

        assert resp.status_code == 200
        fake_store.list_recent.assert_called_once_with(5)

    def test_invalid_limit_rejected(self):
        resp = _make_client().get("/api/credentials/status?limit=0")
        assert resp.status_code == 422


class TestTriggerCredentialCheck:
    def test_triggers_check_and_returns_results(self):
        with patch(
            "backend.services.enterprise_credential_monitor.check_all_credentials",
            new=AsyncMock(return_value=[{"connector_type": "github", "valid": True}]),
        ):
            resp = _make_client().post("/api/credentials/check")

        assert resp.status_code == 200
        assert resp.json() == {"checked": [{"connector_type": "github", "valid": True}]}
