"""Tests for GET /api/github/deploy-checks — exposes pending + recent
deploy-regression check history for the frontend to display."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_github_routes import router
from backend.auth.dependencies import require_user


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    # Phase 11.1: the operator router requires a verified identity; overridden
    # here so these tests stay about the route's own behaviour.
    app.dependency_overrides[require_user] = lambda: {"sub": "op", "role": "operator"}
    return TestClient(app)


class TestListDeployChecks:
    def test_returns_pending_and_recent(self):
        fake_pending_store = MagicMock()
        fake_pending_store.list_pending.return_value = [{"check_id": "svc::1"}]
        fake_history_store = MagicMock()
        fake_history_store.list_recent.return_value = [{"check_id": "svc::0", "regressed": False}]

        with patch(
            "backend.services.enterprise_github_integration.pending_deploy_check_store", fake_pending_store,
        ), patch(
            "backend.services.enterprise_github_integration.deploy_check_history_store", fake_history_store,
        ):
            resp = _make_client().get("/api/github/deploy-checks")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pending"] == [{"check_id": "svc::1"}]
        assert body["recent"] == [{"check_id": "svc::0", "regressed": False}]

    def test_limit_passed_through(self):
        fake_history_store = MagicMock()
        fake_history_store.list_recent.return_value = []
        with patch(
            "backend.services.enterprise_github_integration.pending_deploy_check_store",
            MagicMock(list_pending=MagicMock(return_value=[])),
        ), patch(
            "backend.services.enterprise_github_integration.deploy_check_history_store", fake_history_store,
        ):
            resp = _make_client().get("/api/github/deploy-checks?limit=5")

        assert resp.status_code == 200
        fake_history_store.list_recent.assert_called_once_with(5)

    def test_invalid_limit_rejected(self):
        resp = _make_client().get("/api/github/deploy-checks?limit=0")
        assert resp.status_code == 422
