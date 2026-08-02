"""Tests for /api/branch-protection — status and on-demand check endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_branch_protection_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestGetBranchProtectionStatus:
    def test_returns_recent(self):
        fake_store = MagicMock()
        fake_store.list_recent.return_value = [{"repo": "o/r", "branch": "main", "severity": "critical"}]

        with patch("backend.services.enterprise_branch_protection_monitor.branch_protection_history_store", fake_store):
            resp = _make_client().get("/api/branch-protection/status")

        assert resp.status_code == 200
        assert resp.json() == {"recent": [{"repo": "o/r", "branch": "main", "severity": "critical"}]}

    def test_limit_passed_through(self):
        fake_store = MagicMock()
        fake_store.list_recent.return_value = []
        with patch("backend.services.enterprise_branch_protection_monitor.branch_protection_history_store", fake_store):
            resp = _make_client().get("/api/branch-protection/status?limit=5")

        assert resp.status_code == 200
        fake_store.list_recent.assert_called_once_with(5)

    def test_invalid_limit_rejected(self):
        resp = _make_client().get("/api/branch-protection/status?limit=0")
        assert resp.status_code == 422


class TestTriggerBranchProtectionCheck:
    def test_triggers_check_and_returns_results(self):
        with patch(
            "backend.services.enterprise_branch_protection_monitor.check_all_repos",
            new=AsyncMock(return_value=[{"repo": "o/r", "severity": "critical"}]),
        ):
            resp = _make_client().post("/api/branch-protection/check")

        assert resp.status_code == 200
        assert resp.json() == {"checked": [{"repo": "o/r", "severity": "critical"}]}
