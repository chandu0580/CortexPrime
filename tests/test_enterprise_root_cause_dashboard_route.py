"""Test for GET /api/rca/dashboard — the summary endpoint the new
RootCauseAnalysisPanel frontend reads. The underlying service method
(RootCauseAnalysisService.get_dashboard) already has full coverage in
test_enterprise_root_cause_analysis.py; this just confirms the route
itself returns that shape over HTTP."""
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_root_cause_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRcaDashboardRoute:
    def test_returns_dashboard_shape(self):
        fake_dashboard = {
            "total_analyses": 2,
            "total_incidents": 1,
            "top_root_causes": [{"cause": "N+1 query", "count": 1}],
            "avg_confidence": 0.72,
            "recent_analyses": [
                {"analysis_id": "a1", "problem": "checkout latency", "root_cause": "N+1 query", "confidence": 0.72, "timestamp": "2026-08-01T10:00:00+00:00"}
            ],
        }
        with patch(
            "backend.api.enterprise_root_cause_routes.root_cause_analysis.get_dashboard",
            return_value=fake_dashboard,
        ):
            resp = _make_client().get("/api/rca/dashboard")

        assert resp.status_code == 200
        assert resp.json() == fake_dashboard

    def test_service_error_returns_502(self):
        with patch(
            "backend.api.enterprise_root_cause_routes.root_cause_analysis.get_dashboard",
            side_effect=RuntimeError("boom"),
        ):
            resp = _make_client().get("/api/rca/dashboard")
        assert resp.status_code == 502
