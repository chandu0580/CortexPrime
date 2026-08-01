"""Tests for GET /api/rollbacks — exposes recent automated rollback
attempts for the frontend to display, regardless of which provider
(GitHub or GitLab) triggered them."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_rollbacks_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestListRollbacks:
    def test_returns_recent(self):
        fake_history_store = MagicMock()
        fake_history_store.list_recent.return_value = [
            {"history_id": "abc", "service": "org/repo", "triggered": True}
        ]

        with patch(
            "backend.services.enterprise_deploy_rollback_store.rollback_history_store", fake_history_store,
        ):
            resp = _make_client().get("/api/rollbacks")

        assert resp.status_code == 200
        body = resp.json()
        assert body["recent"] == [{"history_id": "abc", "service": "org/repo", "triggered": True}]

    def test_limit_passed_through(self):
        fake_history_store = MagicMock()
        fake_history_store.list_recent.return_value = []
        with patch(
            "backend.services.enterprise_deploy_rollback_store.rollback_history_store", fake_history_store,
        ):
            resp = _make_client().get("/api/rollbacks?limit=5")

        assert resp.status_code == 200
        fake_history_store.list_recent.assert_called_once_with(5)

    def test_invalid_limit_rejected(self):
        resp = _make_client().get("/api/rollbacks?limit=0")
        assert resp.status_code == 422
