from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.api.admin_routes import router
from backend.auth.dependencies import require_user
from backend.core.autonomy_config import DEFAULT_THRESHOLDS

_SAMPLE_CONFIG = dict(DEFAULT_THRESHOLDS)


@pytest.fixture
def mock_autonomy_config():
    with patch("backend.api.admin_routes.get_autonomy_config") as mock_get:
        mock_config = MagicMock()
        mock_config.get_all.return_value = _SAMPLE_CONFIG
        mock_config.set.return_value = True
        mock_config.reset.return_value = True
        mock_get.return_value = mock_config
        yield mock_config


@pytest.fixture
def client(mock_autonomy_config):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_user] = lambda: {"sub": "admin", "role": "admin"}
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestAdminRoutes:
    def test_get_autonomy_settings(self, client, mock_autonomy_config):
        res = client.get("/api/admin/autonomy")
        assert res.status_code == 200
        data = res.json()
        assert data["max_concurrent_missions"] == 5

    def test_get_autonomy_settings_calls_get_all(self, client, mock_autonomy_config):
        client.get("/api/admin/autonomy")
        mock_autonomy_config.get_all.assert_called_once()

    def test_update_autonomy_setting(self, client, mock_autonomy_config):
        res = client.put("/api/admin/autonomy", json={"key": "max_concurrent_missions", "value": 10})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "updated"
        assert data["key"] == "max_concurrent_missions"
        assert data["value"] == 10

    def test_update_autonomy_setting_calls_set(self, client, mock_autonomy_config):
        client.put("/api/admin/autonomy", json={"key": "max_concurrent_missions", "value": 10})
        mock_autonomy_config.set.assert_called_once_with("max_concurrent_missions", 10)

    def test_update_unknown_setting(self, client, mock_autonomy_config):
        mock_autonomy_config.set.return_value = False
        res = client.put("/api/admin/autonomy", json={"key": "bogus", "value": "x"})
        assert res.status_code == 400
        data = res.json()
        assert "Unknown setting" in data["detail"]

    def test_reset_autonomy_all(self, client, mock_autonomy_config):
        res = client.post("/api/admin/autonomy/reset")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "reset"
        assert data["key"] == "all"
        mock_autonomy_config.reset_all.assert_called_once()

    def test_reset_autonomy_single_key(self, client, mock_autonomy_config):
        res = client.post("/api/admin/autonomy/reset?key=max_concurrent_missions")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "reset"
        assert data["key"] == "max_concurrent_missions"
        mock_autonomy_config.reset.assert_called_once_with("max_concurrent_missions")

    def test_reset_unknown_key(self, client, mock_autonomy_config):
        res = client.post("/api/admin/autonomy/reset?key=nonexistent")
        assert res.status_code == 200
        mock_autonomy_config.reset.assert_called_once_with("nonexistent")

    def test_update_with_invalid_body(self, client):
        res = client.put("/api/admin/autonomy", json={"wrong": "data"})
        assert res.status_code == 422
