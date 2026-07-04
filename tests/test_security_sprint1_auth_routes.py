from __future__ import annotations

import importlib
import sys
import types
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.auth.dependencies import require_user


class _StubCostEngine:
    async def executive_summary(self) -> dict[str, Any]:
        return {"today_spend": 0.0, "month_spend": 0.0}

    async def daily_summary(self, days: int = 30) -> list[dict[str, Any]]:
        return []

    async def provider_breakdown(self, days: int = 30) -> list[dict[str, Any]]:
        return []

    async def mission_cost(self, mission_id: str) -> dict[str, Any]:
        return {"mission_id": mission_id, "cost": 0.0}

    async def user_cost(self, user_id: str, days: int = 30) -> dict[str, Any]:
        return {"user_id": user_id, "cost": 0.0}


def _inject_cost_engine_stub() -> None:
    mod = types.ModuleType("backend.analytics.cost_engine")
    mod.cost_engine = _StubCostEngine()
    sys.modules["backend.analytics.cost_engine"] = mod


def _router_from(module_path: str):
    module = importlib.import_module(module_path)
    return module.router


@pytest.fixture
def auth_app() -> FastAPI:
    _inject_cost_engine_stub()

    app = FastAPI()
    app.include_router(_router_from("backend.api.cost_routes"))
    app.include_router(_router_from("backend.api.llm_health_routes"))
    app.include_router(_router_from("backend.api.workspace_routes"))
    app.include_router(_router_from("backend.api.routes.mission_routes"), prefix="/api/missions")
    app.include_router(_router_from("backend.api.routes.orchestrator_routes"), prefix="/api/orchestrator")
    return app


@pytest.fixture
def admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(_router_from("backend.api.rabbitmq_routes"))
    app.include_router(_router_from("backend.api.governance_routes"))
    app.include_router(_router_from("backend.api.operator_routes"))
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/costs/summary", None),
        ("GET", "/health/llm/telemetry", None),
        ("GET", "/api/missions/active", None),
        ("GET", "/api/orchestrator/loops/active", None),
        ("POST", "/api/workspace/", {"name": "test-workspace"}),
    ],
)
async def test_privileged_routes_require_auth(auth_app: FastAPI, method: str, path: str, body: Any) -> None:
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        response = await _request(client, method, path, body)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_standard_authenticated_routes_return_200(auth_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_user() -> dict[str, Any]:
        return {"sub": "u1", "role": "operator"}

    monkeypatch.setattr("backend.api.llm_health_routes.llm_router.telemetry", lambda: {"status": "ok"})

    auth_app.dependency_overrides[require_user] = _fake_user

    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        cost_resp = await client.get("/api/costs/summary")
        telemetry_resp = await client.get("/health/llm/telemetry")

    assert cost_resp.status_code == 200
    assert telemetry_resp.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/api/rabbitmq/dlq/replay/nonexistent", None),
        ("POST", "/governance/emergency-stop", {"reason": "test"}),
        ("POST", "/operator/execute", {"goal": "open notepad"}),
    ],
)
async def test_admin_routes_return_403_for_non_admin(admin_app: FastAPI, method: str, path: str, body: Any) -> None:
    async def _non_admin_user() -> dict[str, Any]:
        return {"sub": "u2", "role": "operator"}

    admin_app.dependency_overrides[require_user] = _non_admin_user

    async with AsyncClient(transport=ASGITransport(app=admin_app), base_url="http://test") as client:
        response = await _request(client, method, path, body)

    assert response.status_code == 403


async def _request(client: AsyncClient, method: str, path: str, body: Any):
    if body is None:
        return await client.request(method, path)
    return await client.request(method, path, json=body)
