from __future__ import annotations

from types import ModuleType, SimpleNamespace
import sys

import pytest


@pytest.mark.asyncio
async def test_global_stop_lifecycle(monkeypatch):
    from backend.safety.emergency_stop import EmergencyStopController

    controller = EmergencyStopController()
    events = []

    monkeypatch.setattr(controller, "_stop_browser_agent", _async_return(2))
    monkeypatch.setattr(controller, "_cancel_pending_approvals", _async_none)
    monkeypatch.setattr(controller, "_broadcast_stop_event", lambda *args, **kwargs: events.append((args, kwargs)) or _awaitable())

    entry = await controller.activate_global(reason="panic", stopped_by="admin")
    assert controller.is_globally_stopped is True
    assert entry["reason"] == "panic"
    assert events[0][0][0] == "emergency_stop_activated"

    cleared = await controller.deactivate_global(deactivated_by="admin")
    assert controller.is_globally_stopped is False
    assert cleared["scope"] == "global"
    assert events[-1][0][0] == "emergency_stop_deactivated"


@pytest.mark.asyncio
async def test_mission_and_agent_stop_paths(monkeypatch):
    from backend.safety.emergency_stop import EmergencyStopController

    controller = EmergencyStopController()
    events = []

    monkeypatch.setattr(controller, "_broadcast_stop_event", lambda *args, **kwargs: events.append((args, kwargs)) or _awaitable())
    monkeypatch.setattr(controller, "_stop_browser_session", _async_none)
    monkeypatch.setattr(controller, "_cancel_approvals_for_execution", _async_none)
    monkeypatch.setattr(controller, "_stop_browser_agent", _async_return(3))
    monkeypatch.setattr(controller, "_stop_computer_agent", _async_return(4))

    mission = await controller.stop_mission("exec-1", reason="halt", stopped_by="admin")
    assert mission["execution_id"] == "exec-1"
    assert controller.is_stopped("exec-1") is True

    controller.resume_mission("exec-1")
    assert controller.is_stopped("exec-1") is False

    browser = await controller.stop_browser_agent(reason="browser")
    assert browser["sessions_closed"] == 3

    computer = await controller.stop_computer_agent(reason="computer")
    assert computer["missions_cancelled"] == 4

    workflow = await controller.cancel_workflow("exec-2", reason="cancel")
    assert workflow["execution_id"] == "exec-2"
    assert len(events) >= 3


def test_status_and_log_helpers():
    from backend.safety.emergency_stop import EmergencyStopController

    controller = EmergencyStopController()
    controller._global_stop = True
    controller._global_stop_reason = "panic"
    controller._stopped_executions.add("exec-1")
    controller._stop_log.extend([{"id": 1}, {"id": 2}])

    status = controller.get_status()
    assert status["global_stop"] is True
    assert status["global_stop_reason"] == "panic"
    assert status["stopped_missions"] == ["exec-1"]
    assert controller.get_stop_log(limit=1) == [{"id": 2}]


@pytest.mark.asyncio
async def test_internal_browser_helpers(monkeypatch):
    from backend.safety.emergency_stop import EmergencyStopController

    controller = EmergencyStopController()
    closed = []

    browser_module = ModuleType("backend.tools.browser_agent")
    browser_module.browser_agent = SimpleNamespace(
        list_sessions=lambda: ["s1", "s2"],
        close_session=lambda session_id: _record_close(closed, session_id),
    )
    monkeypatch.setitem(sys.modules, "backend.tools.browser_agent", browser_module)

    assert await controller._stop_browser_agent() == 2
    await controller._stop_browser_session("s3")
    assert closed == ["s1", "s2", "s3"]

    monkeypatch.setitem(sys.modules, "backend.tools.browser_agent", ModuleType("backend.tools.browser_agent"))
    assert await controller._stop_browser_agent() == 0


@pytest.mark.asyncio
async def test_internal_browser_session_close_swallow_exception(monkeypatch):
    from backend.safety.emergency_stop import EmergencyStopController

    controller = EmergencyStopController()

    async def boom(session_id):
        raise RuntimeError("close failed")

    browser_module = ModuleType("backend.tools.browser_agent")
    browser_module.browser_agent = SimpleNamespace(close_session=boom)
    monkeypatch.setitem(sys.modules, "backend.tools.browser_agent", browser_module)

    await controller._stop_browser_session("s1")


@pytest.mark.asyncio
async def test_internal_computer_and_approval_helpers(monkeypatch):
    from backend.safety.emergency_stop import EmergencyStopController

    controller = EmergencyStopController()
    rejected = []

    computer_module = ModuleType("backend.computer.computer_agent")
    computer_module.computer_agent = SimpleNamespace(active_missions={"m1": {}, "m2": {}})
    monkeypatch.setitem(sys.modules, "backend.computer.computer_agent", computer_module)

    approval_module = ModuleType("backend.safety.approval_queue")
    approval_module.approval_queue = SimpleNamespace(
        get_pending=lambda: [
            {"request_id": "r1", "execution_id": "exec-1"},
            {"request_id": "r2", "execution_id": "exec-2"},
        ],
        reject=lambda request_id, rejected_by="emergency_stop", reason="": rejected.append((request_id, reason)),
    )
    monkeypatch.setitem(sys.modules, "backend.safety.approval_queue", approval_module)

    assert await controller._stop_computer_agent() == 2
    await controller._cancel_pending_approvals("panic")
    await controller._cancel_approvals_for_execution("exec-2", "halt")
    assert ("r1", "Emergency stop: panic") in rejected
    assert ("r2", "halt") in rejected


@pytest.mark.asyncio
async def test_internal_computer_and_approval_helpers_swallow_exceptions(monkeypatch):
    from backend.safety.emergency_stop import EmergencyStopController

    controller = EmergencyStopController()

    computer_module = ModuleType("backend.computer.computer_agent")
    computer_module.computer_agent = SimpleNamespace(active_missions=None)
    monkeypatch.setitem(sys.modules, "backend.computer.computer_agent", computer_module)

    approval_module = ModuleType("backend.safety.approval_queue")
    approval_module.approval_queue = SimpleNamespace(get_pending=lambda: (_ for _ in ()).throw(RuntimeError("pending failed")))
    monkeypatch.setitem(sys.modules, "backend.safety.approval_queue", approval_module)

    assert await controller._stop_computer_agent() == 0
    await controller._cancel_pending_approvals("panic")
    await controller._cancel_approvals_for_execution("exec-2", "halt")


@pytest.mark.asyncio
async def test_broadcast_stop_event(monkeypatch):
    from backend.safety.emergency_stop import EmergencyStopController

    controller = EmergencyStopController()
    published = []

    event_bus_module = ModuleType("backend.events.event_bus")
    event_bus_module.event_bus = SimpleNamespace(publish=lambda event: published.append(event) or _awaitable())
    monkeypatch.setitem(sys.modules, "backend.events.event_bus", event_bus_module)

    event_models_module = ModuleType("backend.events.event_models")

    class FakeEvent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    event_models_module.CognitionEvent = FakeEvent
    monkeypatch.setitem(sys.modules, "backend.events.event_models", event_models_module)

    await controller._broadcast_stop_event("mission_stopped", {"reason": "halt"}, execution_id="exec-1")
    assert published[0].event_type == "mission_stopped"
    assert published[0].execution_id == "exec-1"

    monkeypatch.setitem(sys.modules, "backend.events.event_bus", ModuleType("backend.events.event_bus"))
    await controller._broadcast_stop_event("ignored", {"reason": "noop"})


async def _record_close(closed: list[str], session_id: str):
    closed.append(session_id)


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


async def _async_none(*args, **kwargs):
    return None


def _awaitable():
    async def _inner():
        return None

    return _inner()