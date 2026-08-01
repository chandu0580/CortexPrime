"""Tests for GET /api/flaky-tests — exposes pending + recent flaky-test
occurrences for the frontend to display, regardless of which provider
(GitHub or GitLab) detected them."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_flaky_tests_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestListFlakyTests:
    def test_returns_pending_and_recent(self):
        fake_pending_store = MagicMock()
        fake_pending_store.list_pending.return_value = [{"run_key": "gh:org/repo:1"}]
        fake_history_store = MagicMock()
        fake_history_store.list_recent.return_value = [{"history_id": "abc", "service": "org/repo"}]

        with patch(
            "backend.services.enterprise_flaky_test_detector.pending_retry_store", fake_pending_store,
        ), patch(
            "backend.services.enterprise_flaky_test_detector.flaky_test_history_store", fake_history_store,
        ):
            resp = _make_client().get("/api/flaky-tests")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pending"] == [{"run_key": "gh:org/repo:1"}]
        assert body["recent"] == [{"history_id": "abc", "service": "org/repo"}]

    def test_limit_passed_through(self):
        fake_history_store = MagicMock()
        fake_history_store.list_recent.return_value = []
        with patch(
            "backend.services.enterprise_flaky_test_detector.pending_retry_store",
            MagicMock(list_pending=MagicMock(return_value=[])),
        ), patch(
            "backend.services.enterprise_flaky_test_detector.flaky_test_history_store", fake_history_store,
        ):
            resp = _make_client().get("/api/flaky-tests?limit=5")

        assert resp.status_code == 200
        fake_history_store.list_recent.assert_called_once_with(5)

    def test_invalid_limit_rejected(self):
        resp = _make_client().get("/api/flaky-tests?limit=0")
        assert resp.status_code == 422
