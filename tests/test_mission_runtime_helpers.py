from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_task_classifiers_cover_browser_and_computer_paths():
    from backend.services import mission_runtime as mod

    assert mod._is_browser_task("Open github.com and inspect issues") is True
    assert mod._is_browser_task("Summarize this local note") is False
    assert mod._is_computer_task("open notepad and type hello") is True
    assert mod._is_computer_task("research the latest AI paper") is False


def test_guardrail_helpers_fail_closed_on_import_errors(monkeypatch):
    from backend.services import mission_runtime as mod

    original_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "backend.safety.guardrails_engine":
            raise RuntimeError("boom")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)

    assert mod._guardrails_check_input("test") is None
    assert mod._guardrails_check_output("test") is None
    assert mod._guardrails_check_tool("browser", "open") is None


@pytest.mark.asyncio
async def test_execute_mission_returns_blocked_when_governance_blocks(monkeypatch):
    from backend.services import mission_runtime as mod

    service = mod.MissionRuntimeService()
    events = []
    chunks = []
    logs = []

    monkeypatch.setattr(mod, "_emit", lambda *args, **kwargs: events.append((args, kwargs)) or _awaitable())
    monkeypatch.setattr(mod, "_send_stream_chunk", lambda chunk, session_id: chunks.append((chunk, session_id)) or _awaitable())
    monkeypatch.setattr(mod, "_governance_log", lambda *args, **kwargs: logs.append((args, kwargs)))
    monkeypatch.setattr(
        mod,
        "_governance_assess",
        lambda objective: SimpleNamespace(
            risk_level=SimpleNamespace(value="critical"),
            reason="policy block",
            blocked=True,
            requires_approval=False,
        ),
    )

    result = await service.execute_mission("dangerous objective", session_id="sess-1")

    assert result["status"] == "blocked"
    assert result["risk_level"] == "critical"
    assert chunks[0][0]["status"] == "blocked"
    assert logs[-1][0][4] == "blocked"
    assert events[0][0][2] == "mission_blocked"


@pytest.mark.asyncio
async def test_execute_mission_returns_rejected_when_approval_not_granted(monkeypatch):
    from backend.services import mission_runtime as mod

    service = mod.MissionRuntimeService()
    events = []
    chunks = []

    monkeypatch.setattr(mod, "_emit", lambda *args, **kwargs: events.append((args, kwargs)) or _awaitable())
    monkeypatch.setattr(mod, "_send_stream_chunk", lambda chunk, session_id: chunks.append((chunk, session_id)) or _awaitable())
    monkeypatch.setattr(mod, "_governance_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        mod,
        "_governance_assess",
        lambda objective: SimpleNamespace(
            risk_level=SimpleNamespace(value="high"),
            reason="needs approval",
            blocked=False,
            requires_approval=True,
        ),
    )
    async def _approval_request(**kwargs):
        return SimpleNamespace(
            status=SimpleNamespace(value="rejected"),
            reject_reason="denied",
            resolved_by=None,
        )

    monkeypatch.setattr(mod, "_governance_request_approval", _approval_request)

    result = await service.execute_mission("sensitive objective", session_id="sess-2")

    assert result["status"] == "rejected"
    assert result["reason"] == "denied"
    assert any(item[0][2] == "approval_requested" for item in events)
    assert any(chunk[0]["status"] == "pending_approval" for chunk in chunks)
    assert chunks[-1][0]["status"] == "rejected"


@pytest.mark.asyncio
async def test_execute_mission_returns_stopped_before_pipeline(monkeypatch):
    from backend.services import mission_runtime as mod

    service = mod.MissionRuntimeService()

    monkeypatch.setattr(mod, "_governance_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "_governance_assess", lambda objective: None)
    monkeypatch.setattr(mod, "_is_emergency_stopped", lambda execution_id: True)

    result = await service.execute_mission("normal objective")

    assert result["status"] == "stopped"
    assert result["reason"] == "Emergency stop active"


@pytest.mark.asyncio
async def test_execute_mission_logs_completion(monkeypatch):
    from backend.services import mission_runtime as mod

    service = mod.MissionRuntimeService()
    logs = []

    monkeypatch.setattr(mod, "_governance_log", lambda *args, **kwargs: logs.append(args))
    monkeypatch.setattr(mod, "_governance_assess", lambda objective: None)
    monkeypatch.setattr(mod, "_is_emergency_stopped", lambda execution_id: False)
    async def _run_pipeline(execution_id, objective, session_id, workspace_id, voice_context=None):
        return {"status": "completed", "execution_id": execution_id, "response": "ok"}

    monkeypatch.setattr(service, "_run_pipeline", _run_pipeline)

    result = await service.execute_mission("safe objective", session_id="sess-3")

    assert result["status"] == "completed"
    assert logs[-1][2] == "mission_complete"


@pytest.mark.asyncio
async def test_execute_mission_handles_pipeline_exception(monkeypatch):
    from backend.services import mission_runtime as mod

    service = mod.MissionRuntimeService()
    chunks = []
    events = []
    logs = []

    monkeypatch.setattr(mod, "_governance_log", lambda *args, **kwargs: logs.append(args))
    monkeypatch.setattr(mod, "_governance_assess", lambda objective: None)
    monkeypatch.setattr(mod, "_is_emergency_stopped", lambda execution_id: False)
    monkeypatch.setattr(mod, "_send_stream_chunk", lambda chunk, session_id: chunks.append((chunk, session_id)) or _awaitable())
    monkeypatch.setattr(mod, "_emit", lambda *args, **kwargs: events.append((args, kwargs)) or _awaitable())

    async def _boom(*args, **kwargs):
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(service, "_run_pipeline", _boom)

    result = await service.execute_mission("safe objective")

    assert result["status"] == "failed"
    assert result["error"] == "pipeline failed"
    assert chunks[-1][0]["status"] == "failed"
    assert events[-1][0][2] == "mission_failed"
    assert logs[-1][2] == "mission_failure"


def _awaitable():
    async def _inner():
        return None

    return _inner()
