"""Tests for /api/docker-health — status and on-demand check endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_docker_health_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestGetDockerHealthStatus:
    def test_returns_recent(self):
        fake_store = MagicMock()
        fake_store.list_recent.return_value = [{"container": "cortex-web", "severity": "critical"}]

        with patch("backend.services.enterprise_docker_health_monitor.docker_health_history_store", fake_store):
            resp = _make_client().get("/api/docker-health/status")

        assert resp.status_code == 200
        assert resp.json() == {"recent": [{"container": "cortex-web", "severity": "critical"}]}

    def test_limit_passed_through(self):
        fake_store = MagicMock()
        fake_store.list_recent.return_value = []
        with patch("backend.services.enterprise_docker_health_monitor.docker_health_history_store", fake_store):
            resp = _make_client().get("/api/docker-health/status?limit=5")

        assert resp.status_code == 200
        fake_store.list_recent.assert_called_once_with(5)

    def test_invalid_limit_rejected(self):
        resp = _make_client().get("/api/docker-health/status?limit=0")
        assert resp.status_code == 422


class TestTriggerDockerHealthCheck:
    def test_triggers_check_and_returns_results(self):
        with patch(
            "backend.services.enterprise_docker_health_monitor.check_all_containers",
            new=AsyncMock(return_value=[{"container": "cortex-web", "severity": "critical"}]),
        ):
            resp = _make_client().post("/api/docker-health/check")

        assert resp.status_code == 200
        assert resp.json() == {"checked": [{"container": "cortex-web", "severity": "critical"}]}
