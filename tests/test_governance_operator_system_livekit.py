from __future__ import annotations

from types import ModuleType, SimpleNamespace
import sys

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_governance_routes(monkeypatch):
    from backend.api import governance_routes as mod

    req_obj = SimpleNamespace(request_id="r1", status=SimpleNamespace(value="approved"), execution_id="exec-1", agent="planner", action="run", risk_level="high")
    rejected = SimpleNamespace(request_id="r2", status=SimpleNamespace(value="rejected"), execution_id="exec-2", agent="critic", action="stop", risk_level="high")

    monkeypatch.setattr(mod.approval_queue, "get_queue", lambda status=None: [{"id": "q1", "status": status or "all"}])
    monkeypatch.setattr(mod.approval_queue, "get_pending", lambda: [{"id": "p1"}])
    monkeypatch.setattr(mod.approval_queue, "approve", lambda request_id, approved_by="operator": req_obj)
    monkeypatch.setattr(mod.approval_queue, "reject", lambda request_id, rejected_by="operator", reason="x": rejected)
    monkeypatch.setattr(mod.audit_logger, "alog", _async_none)
    monkeypatch.setattr(mod.audit_logger, "get_page", _async_return({"entries": []}))
    monkeypatch.setattr(mod.audit_logger, "get_summary_async", _async_return({"total": 2}))
    monkeypatch.setattr(mod.audit_logger, "get_by_execution_async", _async_return([{"id": 1}]))
    monkeypatch.setattr(mod.audit_logger, "summary", lambda: {"total": 2})
    monkeypatch.setattr(mod.audit_logger, "log", lambda **kwargs: None)
    monkeypatch.setattr(mod.emergency_stop, "activate_global", _async_return({"scope": "global"}))
    monkeypatch.setattr(mod.emergency_stop, "deactivate_global", _async_return({"scope": "global", "active": False}))
    monkeypatch.setattr(mod.emergency_stop, "stop_mission", _async_return({"scope": "mission"}))
    monkeypatch.setattr(mod.emergency_stop, "stop_browser_agent", _async_return({"scope": "browser"}))
    monkeypatch.setattr(mod.emergency_stop, "stop_computer_agent", _async_return({"scope": "computer"}))
    monkeypatch.setattr(mod.emergency_stop, "get_status", lambda: {"global": False})
    monkeypatch.setattr(mod.safety_guard, "assess_action", lambda **kwargs: SimpleNamespace(as_dict=lambda: {"risk": "low"}))
    mod.emergency_stop._global_stop = False

    assert (await mod.get_queue())["total"] == 1
    assert (await mod.get_pending_queue())["total"] == 1
    assert await mod.approve_request(mod.ApproveRequest(request_id="r1")) == {"success": True, "request_id": "r1", "status": "approved", "approved_by": "operator"}
    assert (await mod.reject_request(mod.RejectRequest(request_id="r2")))["status"] == "rejected"
    assert await mod.get_audit_log(limit=5) == {"entries": []}
    assert await mod.get_audit_summary() == {"total": 2}
    assert await mod.get_audit_by_execution("exec-1") == {"execution_id": "exec-1", "entries": [{"id": 1}], "total": 1}
    assert (await mod.activate_emergency_stop(mod.EmergencyStopRequest(reason="halt")))["success"] is True
    assert (await mod.deactivate_emergency_stop(stopped_by="operator"))["success"] is True
    assert (await mod.stop_mission(mod.StopMissionRequest(execution_id="exec-1")))["success"] is True
    assert (await mod.stop_browser_agent(mod.EmergencyStopRequest()))["success"] is True
    assert (await mod.stop_computer_agent(mod.EmergencyStopRequest()))["success"] is True
    assert await mod.get_stop_status() == {"global": False}
    assert await mod.assess_action(mod.SafetyAssessRequest(action="read")) == {"risk": "low"}
    assert (await mod.governance_health())["status"] == "online"


@pytest.mark.asyncio
async def test_governance_error_routes(monkeypatch):
    from backend.api import governance_routes as mod

    monkeypatch.setattr(mod.approval_queue, "approve", lambda request_id, approved_by="operator": (_ for _ in ()).throw(KeyError("missing")))
    monkeypatch.setattr(mod.approval_queue, "reject", lambda request_id, rejected_by="operator", reason="x": (_ for _ in ()).throw(KeyError("missing")))

    with pytest.raises(HTTPException):
        await mod.approve_request(mod.ApproveRequest(request_id="missing"))
    with pytest.raises(HTTPException):
        await mod.reject_request(mod.RejectRequest(request_id="missing"))


@pytest.mark.asyncio
async def test_operator_routes(monkeypatch):
    from backend.api import operator_routes as mod

    observer = SimpleNamespace(
        list_monitors=_async_return([{"id": 1}]),
        last_snapshot=SimpleNamespace(as_dict=lambda: {"image": "ok"}),
    )
    agent = SimpleNamespace(
        list_active=lambda: [{"execution_id": "exec-1"}],
        capture_screen=_async_return({"image": "ok"}),
        execute_autonomous_mission=_async_return({"success": True, "status": "completed"}),
    )

    monkeypatch.setattr(mod, "_observer", lambda: observer)
    monkeypatch.setattr(mod, "_agent", lambda: agent)

    assert (await mod.operator_health())["active_missions"] == 1
    assert await mod.list_monitors() == {"monitors": [{"id": 1}], "count": 1}
    assert await mod.get_current_snapshot() == {"image": "ok"}
    assert await mod.capture_screen(mod.CaptureRequest()) == {"image": "ok"}
    assert await mod.list_active_missions() == {"missions": [{"execution_id": "exec-1"}], "count": 1}
    assert await mod.execute_mission(mod.ExecuteMissionRequest(goal="open app")) == {"success": True, "status": "completed"}
    assert (await mod.get_mission_status("exec-1"))["status"] == "running"
    assert (await mod.get_mission_status("missing"))["status"] == "not_active"


@pytest.mark.asyncio
async def test_operator_route_errors(monkeypatch):
    from backend.api import operator_routes as mod

    monkeypatch.setattr(mod, "_observer", lambda: SimpleNamespace(last_snapshot=None))
    with pytest.raises(HTTPException):
        await mod.get_current_snapshot()

    monkeypatch.setattr(mod, "_agent", lambda: SimpleNamespace(capture_screen=_async_return({"error": "boom"})))
    with pytest.raises(HTTPException):
        await mod.capture_screen(mod.CaptureRequest())

    monkeypatch.setattr(mod, "_agent", lambda: SimpleNamespace(capture_screen=_raise_async(RuntimeError("bad"))))
    with pytest.raises(HTTPException):
        await mod.capture_screen(mod.CaptureRequest())

    with pytest.raises(HTTPException):
        await mod.execute_mission(mod.ExecuteMissionRequest(goal="   "))


@pytest.mark.asyncio
async def test_system_health_helpers(monkeypatch):
    from backend.api import system_health_routes as mod

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}

        @staticmethod
        def json():
            return {"status": "ok", "detail": "fine", "items": [1, 2, 3]}

    class FakeClient:
        async def get(self, url, timeout=4.0):
            return FakeResponse()

    probed = await mod._probe("auth", "/health/auth", FakeClient())
    assert probed["status"] == "healthy"
    assert probed["detail"] == {"detail": "fine"}

    class FailingClient:
        async def get(self, url, timeout=4.0):
            raise RuntimeError("offline")

    failed = await mod._probe("auth", "/health/auth", FailingClient())
    assert failed["status"] == "offline"

    redis_module = ModuleType("backend.infrastructure.redis.connection")
    redis_module.redis_connection = SimpleNamespace(is_available=True)
    monkeypatch.setitem(sys.modules, "backend.infrastructure.redis.connection", redis_module)
    rabbit_module = ModuleType("backend.infrastructure.rabbitmq.connection")
    rabbit_module.rabbitmq_connection = SimpleNamespace(is_available=False)
    monkeypatch.setitem(sys.modules, "backend.infrastructure.rabbitmq.connection", rabbit_module)
    neo_module = ModuleType("backend.infrastructure.neo4j.connection")
    neo_module.neo4j_connection = SimpleNamespace(is_available=True)
    monkeypatch.setitem(sys.modules, "backend.infrastructure.neo4j.connection", neo_module)
    health_module = ModuleType("backend.database.health")
    health_module.check_database_health = _async_return({"status": "healthy", "latency_ms": 1.2, "pgvector": True})
    monkeypatch.setitem(sys.modules, "backend.database.health", health_module)

    assert (await mod._infra_probe("redis"))["status"] == "healthy"
    assert (await mod._infra_probe("rabbitmq"))["status"] == "degraded"
    assert (await mod._infra_probe("neo4j"))["status"] == "healthy"
    assert (await mod._infra_probe("postgres"))["status"] == "healthy"
    assert mod._overall_status({"a": {"status": "healthy"}, "b": {"status": "degraded"}}) == "degraded"
    assert mod._overall_status({"a": {"status": "offline"}}) == "critical"

    monkeypatch.setattr(mod, "_check_observability", lambda: {"request_tracing": {"status": "healthy", "latency_ms": 0, "detail": {}}})

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mod.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(mod, "_probe", _async_return({"status": "healthy", "latency_ms": 1, "detail": {}}))
    monkeypatch.setattr(mod, "_infra_probe", _async_return({"status": "healthy", "latency_ms": 1, "detail": {}}))

    result = await mod.system_health()
    assert result["status"] == "healthy"
    assert "request_tracing" in result["components"]


def test_livekit_manager(monkeypatch):
    from backend.voice_v2 import livekit_manager as mod

    monkeypatch.setattr(mod, "_livekit_available", False)
    assert mod.is_livekit_configured() is False
    with pytest.raises(RuntimeError):
        mod.generate_user_token("room", "user")
    with pytest.raises(RuntimeError):
        mod.generate_agent_token("room")

    class FakeToken:
        def __init__(self, api_key=None, api_secret=None):
            self.steps = []

        def with_identity(self, identity):
            self.steps.append(("identity", identity))
            return self

        def with_name(self, name):
            self.steps.append(("name", name))
            return self

        def with_ttl(self, ttl):
            self.steps.append(("ttl", ttl))
            return self

        def with_grants(self, grants):
            self.steps.append(("grants", grants.room))
            return self

        def to_jwt(self):
            return "jwt-token"

    class FakeGrants:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    livekit_module = ModuleType("livekit.api")
    livekit_module.AccessToken = FakeToken
    livekit_module.VideoGrants = FakeGrants
    monkeypatch.setitem(sys.modules, "livekit.api", livekit_module)

    monkeypatch.setattr(mod, "_livekit_available", True)
    monkeypatch.setattr(mod, "LIVEKIT_API_KEY", "key")
    monkeypatch.setattr(mod, "LIVEKIT_API_SECRET", "secret")

    assert mod.generate_user_token("room", "user") == "jwt-token"
    assert mod.generate_agent_token("room") == "jwt-token"


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


async def _async_none(*args, **kwargs):
    return None


def _raise_async(exc):
    async def _inner(*args, **kwargs):
        raise exc

    return _inner