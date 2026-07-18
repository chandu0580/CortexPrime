from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.ai.models import AIResponse, AIRequestStatus, IntentType
from backend.ai.routes import router, _get_service, register_ai_routes


@pytest.fixture
def client():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.process_request = AsyncMock(return_value=AIResponse(
        request_id="ai-test",
        status=AIRequestStatus.COMPLETED,
        intent=IntentType.QUESTION,
        summary="test completed",
        result={"data": "test"},
    ))
    svc.process_plan = AsyncMock(return_value=AIResponse(
        request_id="ai-plan-test",
        status=AIRequestStatus.COMPLETED,
        summary="plan executed",
    ))
    svc.get_runtime_map = AsyncMock(return_value=[
        {"intent": "question", "runtimes": [{"name": "knowledge_runtime", "priority": 1, "reason": "test"}]},
    ])
    svc.get_reasoning_trace = AsyncMock(return_value=MagicMock(
        request_id="ai-test",
        trace_id="trace-test",
        steps=[{"label": "test", "detail": "detail"}],
        get_summary=lambda: ["test: detail"],
    ))
    svc.cancel_request = AsyncMock(return_value=True)
    svc.health = AsyncMock(return_value={
        "status": "healthy",
        "service": "ai_runtime",
        "intents_supported": ["question"],
        "runtimes_available": ["knowledge_runtime"],
    })
    return svc


@pytest.fixture(autouse=True)
def setup_routes(mock_service):
    register_ai_routes(mock_service, MagicMock())
    yield
    register_ai_routes(None, None)


class TestAIAPI:
    def test_health(self, client):
        resp = client.get("/api/ai/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai_runtime"

    def test_request(self, client):
        resp = client.post("/api/ai/request", json={
            "prompt": "what is the status?",
            "user_id": "user-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "request_id" in data
        assert data["intent"] == "question"

    def test_request_no_context(self, client):
        resp = client.post("/api/ai/request", json={
            "prompt": "analyze the system",
        })
        assert resp.status_code == 200

    def test_plan(self, client):
        resp = client.post("/api/ai/plan", json={
            "prompt": "create a new mission",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "plan_id" in data or "steps" in data

    def test_orchestrate(self, client):
        resp = client.post("/api/ai/orchestrate", json={
            "request_id": "ai-test",
            "steps": [
                {
                    "name": "step1",
                    "runtime": "knowledge_runtime",
                    "action": "search",
                    "timeout_seconds": 10.0,
                },
            ],
        })
        assert resp.status_code == 200

    def test_runtime_map(self, client):
        resp = client.get("/api/ai/runtime-map")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_reasoning_trace_found(self, client):
        resp = client.get("/api/ai/reasoning/ai-test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == "ai-test"

    def test_reasoning_trace_not_found(self, client):
        svc = _get_service()
        svc.get_reasoning_trace = AsyncMock(return_value=None)
        resp = client.get("/api/ai/reasoning/nonexistent")
        assert resp.status_code == 404

    def test_cancel(self, client):
        resp = client.post("/api/ai/cancel/ai-test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled"] is True
