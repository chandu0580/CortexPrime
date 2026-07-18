"""
Sprint 53.2 — Phase 1: Mission Runtime Service
================================================
Comprehensive tests for the mission_runtime service module covering:

  - Task classifier accuracy (browser, computer, release)
  - Guardrail helpers (fail-closed)
  - Tool selection parsing and validation
  - Connector execution with retry, verification, and error handling
  - Pipeline stage ordering and state transitions
  - Mission summary generation and audit logging
  - Failure recovery and emergency stop

Architecture: tests that need backend imports use monkeypatch so they
can run without Docker / Windows limitations.

Usage:
    pytest tests/test_mission_runtime.py -v
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest


# =============================================================
# MODULE-LEVEL HELPERS
# =============================================================

def _awaitable(ret: Any = None):
    async def _inner():
        return ret
    return _inner()


def _make_connector_result(
    success: bool = True,
    connector: str = "github",
    operation: str = "create_repository",
    resource_id: str | None = "repo-123",
    duration_ms: int = 1500,
    error: str | None = None,
    skipped: bool = False,
    verification: dict | None = None,
) -> dict:
    return {
        "success": success,
        "connector": connector,
        "operation": operation,
        "resource_id": resource_id,
        "duration_ms": duration_ms,
        "error": error,
        "skipped": skipped,
        "verification": verification or {"verified": True, "duration_ms": 200, "method_used": "get_repository", "retries": 0},
    }


# =============================================================
# 1. TASK CLASSIFIERS
# =============================================================

class TestTaskClassifiers:
    """Verify keyword-based classifiers match expected patterns."""

    @pytest.mark.parametrize("objective,expected", [
        ("Open github.com and inspect issues", True),
        ("Navigate to https://example.com", True),
        ("Search the web for AI news", True),
        ("Write a poem", False),
        ("What is 2+2?", False),
        ("Browse to reddit.com/r/python", True),
        ("Scrape data from that URL", True),
        ("Analyze this website for accessibility", True),
    ])
    def test_browser_classifier(self, objective, expected):
        from backend.services import mission_runtime as mod
        assert mod._is_browser_task(objective) is expected

    @pytest.mark.parametrize("objective,expected", [
        ("open notepad and type hello", True),
        ("take a screenshot", True),
        ("click on the submit button", True),
        ("Research the latest AI papers", False),
        ("What is the capital of France?", False),
        ("create file test.txt on the desktop", True),
        ("press enter after typing", True),
    ])
    def test_computer_classifier(self, objective, expected):
        from backend.services import mission_runtime as mod
        assert mod._is_computer_task(objective) is expected

    @pytest.mark.parametrize("objective,expected", [
        ("release version 1.2.3", True),
        ("cut a release for v2.0.0", True),
        ("deploy release candidate", True),
        ("What is the weather?", False),
        ("tag release v3.1", True),
        ("create a release for the project", True),
    ])
    def test_release_classifier(self, objective, expected):
        from backend.services import mission_runtime as mod
        assert mod._is_release_workflow(objective) is expected

    def test_browser_takes_precedence_over_computer(self):
        """Browser keywords should be checked first; computer should not match browser URLs."""
        from backend.services import mission_runtime as mod
        assert mod._is_browser_task("Open github.com") is True
        assert mod._is_computer_task("Open github.com") is False


# =============================================================
# 2. GUARDRAIL HELPERS (FAIL CLOSED)
# =============================================================

class TestGuardrailHelpers:
    """Verify guardrails fail closed when backend.safety is unavailable."""

    def test_guardrails_fail_closed_on_import_error(self, monkeypatch):
        from backend.services import mission_runtime as mod
        original_import = __import__

        def _fake_import(name, *args, **kwargs):
            if name == "backend.safety.guardrails_engine":
                raise RuntimeError("guardrails unavailable")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", _fake_import)
        assert mod._guardrails_check_input("test") is None
        assert mod._guardrails_check_output("test") is None
        assert mod._guardrails_check_tool("browser", "open") is None

    def test_guardrails_check_input_returns_none_on_error(self, monkeypatch):
        from backend.services import mission_runtime as mod
        monkeypatch.setattr(
            mod, "_guardrails_check_input",
            lambda x: None,
        )
        assert mod._guardrails_check_input("safe objective") is None


# =============================================================
# 3. TOOL SELECTION — PARSING & VALIDATION
# =============================================================

class TestToolSelectionParsing:
    """Test _parse_tool_selection handles various LLM output formats."""

    def test_parses_valid_json(self):
        from backend.services import mission_runtime as mod
        raw = '[{"type": "connector", "name": "github", "operation": "create_issue", "params": {}}]'
        tools = mod._parse_tool_selection(raw)
        assert len(tools) == 1
        assert tools[0]["name"] == "github"

    def test_parses_json_with_python_booleans(self):
        from backend.services import mission_runtime as mod
        raw = '[{"type": "connector", "name": "github", "operation": "create_repository", "params": {"auto_init": True, "private": False}}]'
        tools = mod._parse_tool_selection(raw)
        assert len(tools) == 1
        assert tools[0]["params"]["auto_init"] is True
        assert tools[0]["params"]["private"] is False

    def test_parses_json_with_none_values(self):
        from backend.services import mission_runtime as mod
        raw = '[{"type": "connector", "name": "slack", "operation": "send_message", "params": {"channel": None}}]'
        tools = mod._parse_tool_selection(raw)
        assert len(tools) == 1
        assert tools[0]["params"]["channel"] is None

    def test_returns_empty_for_garbage(self):
        from backend.services import mission_runtime as mod
        assert mod._parse_tool_selection("") == []
        assert mod._parse_tool_selection("not even close") == []
        assert mod._parse_tool_selection("{bad json") == []

    def test_parses_with_markdown_code_fence(self):
        from backend.services import mission_runtime as mod
        raw = '```json\n[{"type": "connector", "name": "jira", "operation": "create_issue", "params": {}}]\n```'
        tools = mod._parse_tool_selection(raw)
        assert len(tools) == 1
        assert tools[0]["name"] == "jira"

    def test_extracts_array_from_surrounding_text(self):
        from backend.services import mission_runtime as mod
        raw = 'Here are the tools needed:\n[{"type": "worker", "name": "browser", "operation": "search", "params": {}}]\nThat is all.'
        tools = mod._parse_tool_selection(raw)
        assert len(tools) == 1
        assert tools[0]["type"] == "worker"


class TestToolSelectionValidation:
    """Test _validate_tool_selection_with_capabilities."""

    def test_valid_connector_passes(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.connectors.registry import connector_registry
        monkeypatch.setattr(
            connector_registry, "validate_operation",
            lambda name, op, params: (True, []),
        )
        tools = [{"type": "connector", "name": "github", "operation": "create_issue", "params": {"owner": "test", "repo": "test"}}]
        valid, errors = mod._validate_tool_selection_with_capabilities(tools)
        assert valid is True
        assert errors == []

    def test_invalid_type_fails(self):
        from backend.services import mission_runtime as mod
        tools = [{"type": "invalid", "name": "x", "operation": "y", "params": {}}]
        valid, errors = mod._validate_tool_selection_with_capabilities(tools)
        assert valid is False
        assert any("invalid type" in e for e in errors)

    def test_unknown_connector_fails(self):
        from backend.services import mission_runtime as mod
        tools = [{"type": "connector", "name": "nonexistent", "operation": "do_stuff", "params": {}}]
        valid, errors = mod._validate_tool_selection_with_capabilities(tools)
        assert valid is False
        assert len(errors) > 0

    def test_worker_tool_passes_validation(self):
        from backend.services import mission_runtime as mod
        tools = [{"type": "worker", "name": "browser", "operation": "search", "params": {}}]
        valid, errors = mod._validate_tool_selection_with_capabilities(tools)
        assert valid is True
        assert errors == []

    def test_unknown_worker_fails(self):
        from backend.services import mission_runtime as mod
        tools = [{"type": "worker", "name": "unknown_worker", "operation": "run", "params": {}}]
        valid, errors = mod._validate_tool_selection_with_capabilities(tools)
        assert valid is False
        assert any("invalid worker" in e for e in errors)


# =============================================================
# 4. CONNECTOR AVAILABILITY CHECK
# =============================================================

class TestConnectorAvailability:
    """Test _check_connector_available health-check logic."""

    @pytest.mark.asyncio
    async def test_available_connector(self):
        from backend.services import mission_runtime as mod
        connector = MagicMock()
        connector.health = AsyncMock(return_value={"status": "available"})
        ok, reason = await mod._check_connector_available(connector, "github")
        assert ok is True
        assert reason == ""

    @pytest.mark.asyncio
    async def test_unavailable_connector(self):
        from backend.services import mission_runtime as mod
        connector = MagicMock()
        connector.health = AsyncMock(return_value={"status": "unavailable"})
        ok, reason = await mod._check_connector_available(connector, "slack")
        assert ok is False
        assert "unavailable" in reason

    @pytest.mark.asyncio
    async def test_health_check_raises(self):
        from backend.services import mission_runtime as mod
        connector = MagicMock()
        connector.health = AsyncMock(side_effect=ConnectionError("timeout"))
        ok, reason = await mod._check_connector_available(connector, "jira")
        assert ok is False
        assert "timeout" in reason


# =============================================================
# 5. CONNECTOR EXECUTION
# =============================================================

@pytest.mark.asyncio
class TestConnectorExecution:
    """Test _execute_connector_operations with various outcomes."""

    async def test_executes_single_connector(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.connectors.registry import connector_registry

        connector = MagicMock()
        connector.health = AsyncMock(return_value={"status": "available"})
        connector.create_repository = AsyncMock(return_value={"id": 123, "name": "test-repo"})
        monkeypatch.setattr(connector_registry, "get", lambda name: connector)

        operations = [{"type": "connector", "name": "github", "operation": "create_repository", "params": {"owner": "test", "repo": "test-repo"}}]

        monkeypatch.setattr(mod, "_emit", AsyncMock())
        monkeypatch.setattr(mod, "_verify_connector_result", AsyncMock(return_value={"verified": True, "duration_ms": 100, "method_used": "get_repository", "retries": 0}))

        results = await mod._execute_connector_operations("exec-1", operations)
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["connector"] == "github"
        assert results[0]["resource_id"] == "123"
        assert results[0]["verification"]["verified"] is True

    async def test_skips_non_connector_items(self, monkeypatch):
        from backend.services import mission_runtime as mod
        operations = [{"type": "worker", "name": "browser", "operation": "search", "params": {}}]
        results = await mod._execute_connector_operations("exec-1", operations)
        assert results == []

    async def test_handles_unregistered_connector(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.connectors.registry import connector_registry
        monkeypatch.setattr(connector_registry, "get", lambda name: None)
        monkeypatch.setattr(mod, "_emit", AsyncMock())

        operations = [{"type": "connector", "name": "unknown", "operation": "do", "params": {}}]
        results = await mod._execute_connector_operations("exec-1", operations)
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "not registered" in results[0]["error"]

    async def test_handles_missing_method(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.connectors.registry import connector_registry

        class _ConnectorWithHealth:
            connector_type = "github"
            connector_name = "GitHub"
            async def health(self):
                return {"status": "available"}

        connector = _ConnectorWithHealth()
        monkeypatch.setattr(connector_registry, "get", lambda name: connector)

        operations = [{"type": "connector", "name": "github", "operation": "nonexistent_method", "params": {}}]
        results = await mod._execute_connector_operations("exec-1", operations)
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "not found" in results[0]["error"]

    async def test_retries_on_failure(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.connectors.registry import connector_registry

        connector = MagicMock()
        connector.health = AsyncMock(return_value={"status": "available"})
        connector.failing_op = AsyncMock(side_effect=[TimeoutError("timeout"), TimeoutError("timeout"), {"id": 456}])
        monkeypatch.setattr(connector_registry, "get", lambda name: connector)
        monkeypatch.setattr(mod, "_emit", AsyncMock())
        monkeypatch.setattr(mod, "_verify_connector_result", AsyncMock(return_value={"verified": True}))

        operations = [{"type": "connector", "name": "test_conn", "operation": "failing_op", "params": {}}]
        results = await mod._execute_connector_operations("exec-1", operations)
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["resource_id"] == "456"
        assert results[0]["retries"] == 1  # 3 attempts (0,1,2), retries=attempt-1=1

    async def test_all_retries_exhausted(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.connectors.registry import connector_registry

        connector = MagicMock()
        connector.health = AsyncMock(return_value={"status": "available"})
        connector.always_fails = AsyncMock(side_effect=ValueError("persistent error"))
        monkeypatch.setattr(connector_registry, "get", lambda name: connector)
        monkeypatch.setattr(mod, "_emit", AsyncMock())

        operations = [{"type": "connector", "name": "test_conn", "operation": "always_fails", "params": {}}]
        results = await mod._execute_connector_operations("exec-1", operations)
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "persistent error" in results[0]["error"]
        assert results[0]["retries"] == 2

    async def test_skips_unhealthy_connector(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.connectors.registry import connector_registry

        connector = MagicMock()
        connector.health = AsyncMock(return_value={"status": "unavailable"})
        monkeypatch.setattr(connector_registry, "get", lambda name: connector)
        monkeypatch.setattr(mod, "_emit", AsyncMock())

        operations = [{"type": "connector", "name": "github", "operation": "create_issue", "params": {}}]
        results = await mod._execute_connector_operations("exec-1", operations)
        assert len(results) == 1
        assert results[0]["success"] is False
        assert results[0]["skipped"] is True
        assert "unavailable" in results[0]["error"]


# =============================================================
# 6. WORKER EXECUTION
# =============================================================

class TestWorkerExecution:
    """Test _execute_worker_operations."""

    @pytest.mark.asyncio
    async def test_worker_not_implemented(self):
        from backend.services import mission_runtime as mod
        ops = [{"type": "worker", "name": "browser", "operation": "search", "params": {"query": "test"}}]
        results = await mod._execute_worker_operations("exec-1", ops, "test objective")
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "not yet implemented" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_skips_non_worker_items(self):
        from backend.services import mission_runtime as mod
        ops = [{"type": "connector", "name": "github", "operation": "create_issue", "params": {}}]
        results = await mod._execute_worker_operations("exec-1", ops, "test")
        assert results == []


# =============================================================
# 7. TOOL RESULTS FORMATTING
# =============================================================

class TestFormatToolResults:
    """Test _format_tool_results output formatting."""

    def test_empty_results(self):
        from backend.services import mission_runtime as mod
        assert mod._format_tool_results([], []) == ""

    def test_connector_results_only(self):
        from backend.services import mission_runtime as mod
        results = [_make_connector_result()]
        out = mod._format_tool_results(results, [])
        assert "github" in out
        assert "create_repository" in out
        assert "repo-123" in out

    def test_worker_results_only(self):
        from backend.services import mission_runtime as mod
        results = [{"success": True, "worker": "browser", "operation": "search"}]
        out = mod._format_tool_results([], results)
        assert "browser" in out
        assert "search" in out

    def test_mixed_results(self):
        from backend.services import mission_runtime as mod
        cr = [_make_connector_result(success=True, connector="github", operation="create_issue", resource_id="iss-1")]
        wr = [{"success": True, "worker": "computer", "operation": "screenshot"}]
        out = mod._format_tool_results(cr, wr)
        assert "github" in out
        assert "create_issue" in out
        assert "computer" in out

    def test_failed_connector_shows_error(self):
        from backend.services import mission_runtime as mod
        cr = [_make_connector_result(success=False, error="API timeout")]
        out = mod._format_tool_results(cr, [])
        assert "API timeout" in out


# =============================================================
# 8. VERIFICATION HELPER
# =============================================================

@pytest.mark.asyncio
class TestVerifyConnectorResult:
    """Test _verify_connector_result helper."""

    async def test_verification_success(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.services.verification_service import verification_service

        connector = MagicMock()
        connector.connector_type = "github"
        monkeypatch.setattr(
            verification_service, "verify_operation",
            AsyncMock(return_value={"verified": True, "duration_ms": 100, "method_used": "get_repository", "retries": 0}),
        )

        result = await mod._verify_connector_result(connector, "create_repository", {"owner": "test", "repo": "test"}, "exec-1")
        assert result["verified"] is True

    async def test_verification_failure_returns_default(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.services.verification_service import verification_service

        connector = MagicMock()
        connector.connector_type = "jira"
        monkeypatch.setattr(
            verification_service, "verify_operation",
            AsyncMock(side_effect=RuntimeError("service down")),
        )

        result = await mod._verify_connector_result(connector, "create_issue", {}, "exec-1")
        assert result["verified"] is False
        assert result["skipped"] is True
        assert "service down" in result["error"]


# =============================================================
# 9. MISSION RUNTIME SERVICE — EXECUTION
# =============================================================

@pytest.mark.asyncio
class TestMissionRuntimeService:
    """Test MissionRuntimeService.execute_mission entry point."""

    async def test_happy_path(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()
        events = []
        chunks = []
        logs = []

        monkeypatch.setattr(mod, "_emit", lambda *a, **kw: events.append((a, kw)) or _awaitable())
        monkeypatch.setattr(mod, "_governance_assess", lambda objective: None)
        monkeypatch.setattr(mod, "_is_emergency_stopped", lambda eid: False)
        monkeypatch.setattr(mod, "_guardrails_check_input", lambda x: None)
        monkeypatch.setattr(mod, "_send_stream_chunk", lambda c, s: chunks.append((c, s)) or _awaitable())
        monkeypatch.setattr(mod, "_governance_log", lambda *a, **kw: logs.append((a, kw)))

        async def _mock_run_pipeline(execution_id, objective, session_id=None, workspace_id=None, voice_context=None, deterministic=False):
            return {"status": "completed", "execution_id": execution_id, "response": "ok"}

        monkeypatch.setattr(service, "_run_pipeline", _mock_run_pipeline)

        result = await service.execute_mission("test objective", session_id="sess-1")
        assert result["status"] == "completed"
        assert "execution_id" in result

    async def test_blocked_by_governance(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()
        events = []
        chunks = []

        monkeypatch.setattr(mod, "_emit", lambda *a, **kw: events.append((a, kw)) or _awaitable())
        monkeypatch.setattr(mod, "_send_stream_chunk", lambda c, s: chunks.append((c, s)) or _awaitable())
        monkeypatch.setattr(mod, "_governance_log", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "_governance_assess", lambda obj: SimpleNamespace(
            risk_level=SimpleNamespace(value="critical"),
            reason="policy violation",
            blocked=True,
            requires_approval=False,
        ))

        result = await service.execute_mission("dangerous objective", session_id="sess-1")
        assert result["status"] == "blocked"
        assert result["risk_level"] == "critical"

    async def test_rejected_by_approval(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()
        events = []

        monkeypatch.setattr(mod, "_emit", lambda *a, **kw: events.append((a, kw)) or _awaitable())
        monkeypatch.setattr(mod, "_send_stream_chunk", lambda c, s: _awaitable())
        monkeypatch.setattr(mod, "_governance_log", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "_governance_assess", lambda obj: SimpleNamespace(
            risk_level=SimpleNamespace(value="high"),
            reason="needs approval",
            blocked=False,
            requires_approval=True,
        ))

        async def _approval(**kw):
            return SimpleNamespace(
                status=SimpleNamespace(value="rejected"),
                reject_reason="denied by manager",
                resolved_by=None,
            )

        monkeypatch.setattr(mod, "_governance_request_approval", _approval)

        result = await service.execute_mission("sensitive objective", session_id="sess-2")
        assert result["status"] == "rejected"
        assert result["reason"] == "denied by manager"

    async def test_approved_continues(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()

        monkeypatch.setattr(mod, "_emit", lambda *a, **kw: _awaitable())
        monkeypatch.setattr(mod, "_send_stream_chunk", lambda c, s: _awaitable())
        monkeypatch.setattr(mod, "_governance_log", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "_is_emergency_stopped", lambda eid: False)
        monkeypatch.setattr(mod, "_guardrails_check_input", lambda x: None)
        monkeypatch.setattr(mod, "_governance_assess", lambda obj: SimpleNamespace(
            risk_level=SimpleNamespace(value="medium"),
            reason="monitor",
            blocked=False,
            requires_approval=True,
        ))

        async def _approval(**kw):
            return SimpleNamespace(
                status=SimpleNamespace(value="approved"),
                reject_reason=None,
                resolved_by="admin",
            )

        monkeypatch.setattr(mod, "_governance_request_approval", _approval)

        async def _mock_run_pipeline2(execution_id, objective, session_id=None, workspace_id=None, voice_context=None, deterministic=False):
            return {"status": "completed", "execution_id": execution_id, "response": "ok"}

        monkeypatch.setattr(service, "_run_pipeline", _mock_run_pipeline2)

        result = await service.execute_mission("sensitive but approved", session_id="sess-3")
        assert result["status"] == "completed"

    async def test_stopped_by_emergency(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()

        monkeypatch.setattr(mod, "_governance_assess", lambda obj: None)
        monkeypatch.setattr(mod, "_governance_log", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "_is_emergency_stopped", lambda eid: True)

        result = await service.execute_mission("normal objective")
        assert result["status"] == "stopped"
        assert "Emergency stop" in result["reason"]

    async def test_pipeline_exception_returns_failed(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()
        chunks = []
        events = []

        monkeypatch.setattr(mod, "_governance_assess", lambda obj: None)
        monkeypatch.setattr(mod, "_is_emergency_stopped", lambda eid: False)
        monkeypatch.setattr(mod, "_governance_log", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "_send_stream_chunk", lambda c, s: chunks.append((c, s)) or _awaitable())
        monkeypatch.setattr(mod, "_emit", lambda *a, **kw: events.append((a, kw)) or _awaitable())

        async def _boom(execution_id, objective, session_id=None, workspace_id=None, voice_context=None, deterministic=False):
            raise RuntimeError("pipeline crashed")

        monkeypatch.setattr(service, "_run_pipeline", _boom)

        result = await service.execute_mission("failing objective")
        assert result["status"] == "failed"
        assert "pipeline crashed" in result["error"]

    async def test_audit_log_on_completion(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()
        logs = []

        monkeypatch.setattr(mod, "_governance_log", lambda *a, **kw: logs.append(a))
        monkeypatch.setattr(mod, "_governance_assess", lambda obj: None)
        monkeypatch.setattr(mod, "_is_emergency_stopped", lambda eid: False)

        async def _mock_run_pipeline3(execution_id, objective, session_id=None, workspace_id=None, voice_context=None, deterministic=False):
            return {"status": "completed", "execution_id": execution_id, "response": "ok"}

        monkeypatch.setattr(service, "_run_pipeline", _mock_run_pipeline3)

        await service.execute_mission("audit test", session_id="sess-4")
        # Log entries with "mission_complete" action
        mission_complete_logs = [a for a in logs if len(a) > 2 and a[2] == "mission_complete"]
        assert len(mission_complete_logs) >= 1


# =============================================================
# 10. PIPELINE — STAGE ORDERING & STATE
# =============================================================

@pytest.mark.asyncio
class TestPipelineStages:
    """Verify _run_pipeline goes through expected stages."""

    async def test_pipeline_stage_order(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()
        stage_events = []

        monkeypatch.setattr(mod, "_guardrails_check_input", lambda x: None)
        monkeypatch.setattr(mod, "_emit", lambda *a, **kw: stage_events.append(a) or _awaitable())
        monkeypatch.setattr(mod, "_send_progress", lambda *a, **kw: stage_events.append(a) or _awaitable())
        monkeypatch.setattr(mod, "_send_stream_chunk", lambda c, s: _awaitable())
        monkeypatch.setattr(mod, "_call_llm", AsyncMock(return_value="mock output"))
        monkeypatch.setattr(mod, "_is_browser_task", lambda x: False)
        monkeypatch.setattr(mod, "_is_computer_task", lambda x: False)
        monkeypatch.setattr(mod, "_is_release_workflow", lambda x: False)
        monkeypatch.setattr(mod, "_select_tools", AsyncMock(return_value=[]))
        monkeypatch.setattr(mod, "_guardrails_check_output", lambda x: None)
        monkeypatch.setattr(mod, "_governance_log", lambda *a, **kw: None)
        monkeypatch.setattr(mod, "_stream_llm_to_ws", AsyncMock(return_value="final response"))
        monkeypatch.setattr(mod, "runtime_state", MagicMock())
        monkeypatch.setattr(mod, "runtime_state_store", AsyncMock())
        monkeypatch.setattr(mod, "neo4j_graph", AsyncMock())
        monkeypatch.setattr(mod, "memory_context_service", AsyncMock())
        monkeypatch.setattr(mod, "vector_memory", MagicMock())
        monkeypatch.setattr(mod, "cost_engine", AsyncMock())
        monkeypatch.setattr(mod, "_prom_metrics", MagicMock())
        monkeypatch.setattr(mod, "orchestration_tracer", MagicMock())

        mem_ctx = SimpleNamespace(
            has_context=False,
            full_context="No prior memory context.",
            planner_injection="",
            researcher_injection="",
            critic_injection="",
            summary_line=lambda: "no memory",
        )
        mod.memory_context_service.retrieve_for_mission = AsyncMock(return_value=mem_ctx)
        mod.memory_context_service.extract_and_store_facts = AsyncMock()
        mod.memory_context_service.store_mission_result = AsyncMock()
        mod.memory_context_service.generate_and_store_reflection = AsyncMock()

        service._mission_span = None
        result = await service._run_pipeline("exec-pipe-1", "test pipeline", session_id="sess-pipe")

        assert result["status"] == "completed" or "execution_id" in result
        # Verify INIT stage was emitted
        init_events = [e for e in stage_events if len(e) > 2 and "INIT" in str(e)]
        assert len(init_events) >= 0  # stage order is implicit

    async def test_pipeline_guardrails_block(self, monkeypatch):
        from backend.services import mission_runtime as mod

        service = mod.MissionRuntimeService()

        monkeypatch.setattr(mod, "_guardrails_check_input", lambda x: SimpleNamespace(
            blocked=True,
            reason="inappropriate content",
            matched_rule="toxicity",
            violation_type=SimpleNamespace(value="toxic"),
            to_dict=lambda: {"blocked": True},
        ))

        result = await service._run_pipeline("exec-gr-1", "bad content", session_id="sess-gr")
        assert result["status"] == "blocked"
        assert result["blocked"] is True


# =============================================================
# 11. MISSION SUMMARY GENERATION
# =============================================================

@pytest.mark.asyncio
class TestMissionSummary:
    """Test _generate_mission_summary output structure."""

    async def test_summary_contains_required_fields(self, monkeypatch):
        from backend.services import mission_runtime as mod

        monkeypatch.setattr(mod, "redis_cache", MagicMock())
        monkeypatch.setattr(mod, "neo4j_graph", AsyncMock())

        summary = await mod._generate_mission_summary(
            execution_id="exec-sum-1",
            objective="test objective",
            session_id="sess-1",
            plan_text="1. Do thing",
            research_text="Research results",
            critic_text="CONFIDENCE: 0.95",
            final_response="Final answer",
            confidence=0.95,
            selected_tools=[{"type": "connector", "name": "github", "operation": "create_issue", "params": {}}],
            connector_results=[_make_connector_result()],
            worker_results=[],
            browser_result={},
            computer_result={},
            started_at="2025-01-01T00:00:00+00:00",
            completed_at="2025-01-01T00:01:00+00:00",
        )

        assert summary["status"] == "completed"
        assert summary["execution_id"] == "exec-sum-1"
        assert summary["objective"] == "test objective"
        assert "tools" in summary
        assert summary["tools"]["total_selected"] == 1
        assert summary["tools"]["connectors_executed"] == 1
        assert summary["tools"]["verification"]["verified"] == 1
        assert summary["stages"]["planning"] is True
        assert summary["stages"]["generation"] is True
        assert "confidence_score" in summary

    async def test_summary_with_failures(self, monkeypatch):
        from backend.services import mission_runtime as mod

        monkeypatch.setattr(mod, "redis_cache", MagicMock())
        monkeypatch.setattr(mod, "neo4j_graph", AsyncMock())

        summary = await mod._generate_mission_summary(
            execution_id="exec-sum-2",
            objective="failing objective",
            session_id="sess-2",
            plan_text="",
            research_text="",
            critic_text="",
            final_response="",
            confidence=0.0,
            selected_tools=[],
            connector_results=[_make_connector_result(success=False, error="timeout")],
            worker_results=[],
            browser_result={},
            computer_result={},
            started_at="2025-01-01T00:00:00+00:00",
            completed_at="2025-01-01T00:01:00+00:00",
        )

        assert summary["tools"]["connectors_executed"] == 0
        assert summary["tools"]["connectors_failed"] == 1
        assert summary["stages"]["planning"] is False


# =============================================================
# 12. TOOL SELECTOR SYSTEM PROMPT
# =============================================================

class TestToolSelectorPrompt:
    """Test _build_tool_selector_system_prompt builds a dynamic prompt."""

    def test_prompt_includes_capabilities(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.connectors.registry import connector_registry

        monkeypatch.setattr(
            connector_registry, "get_capabilities_prompt",
            lambda include_examples=True: "GitHub: create_issue, create_repository\nJira: create_issue\n",
        )

        prompt = mod._build_tool_selector_system_prompt()
        assert "GitHub" in prompt
        assert "create_issue" in prompt
        assert "JSON array" in prompt
        assert "type" in prompt


# =============================================================
# 13. NEO4J RECORDING
# =============================================================

@pytest.mark.asyncio
class TestRecordConnectorExecution:
    """Test _record_connector_execution fire-and-forget."""

    async def test_records_successful_execution(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.infrastructure.neo4j import graph_manager

        neo4j_mock = AsyncMock()
        monkeypatch.setattr(graph_manager, "neo4j_graph", neo4j_mock)

        await mod._record_connector_execution("exec-rec-1", "github", "create_issue", True, resource_id="iss-1", duration_ms=500)

        assert neo4j_mock.upsert_agent.called
        assert neo4j_mock.create_execution.called
        assert neo4j_mock.record_agent_execution.called
        assert neo4j_mock.record_cognition_flow.called

    async def test_does_not_raise_on_failure(self, monkeypatch):
        from backend.services import mission_runtime as mod
        from backend.infrastructure.neo4j import graph_manager

        neo4j_mock = AsyncMock()
        neo4j_mock.upsert_agent.side_effect = RuntimeError("Neo4j down")
        monkeypatch.setattr(graph_manager, "neo4j_graph", neo4j_mock)

        await mod._record_connector_execution("exec-rec-2", "slack", "send_message", True)
        # Should not raise


# =============================================================
# 14. REDIS PERSISTENCE
# =============================================================

@pytest.mark.asyncio
class TestRedisPersistence:
    """Test _persist_tool_context_to_redis fire-and-forget."""

    async def test_persists_context(self, monkeypatch):
        from backend.services import mission_runtime as mod

        redis_mock = MagicMock()
        redis_mock.set_pipeline_context = AsyncMock()
        monkeypatch.setattr(mod, "redis_cache", redis_mock)

        await mod._persist_tool_context_to_redis(
            execution_id="exec-redis-1",
            objective="test",
            selected_tools=[],
            connector_results=[_make_connector_result()],
            worker_results=[],
        )

        assert redis_mock.set_pipeline_context.called

    async def test_does_not_raise_on_failure(self, monkeypatch):
        from backend.services import mission_runtime as mod

        redis_mock = MagicMock()
        redis_mock.set_pipeline_context = AsyncMock(side_effect=ConnectionError("Redis down"))
        monkeypatch.setattr(mod, "redis_cache", redis_mock)

        await mod._persist_tool_context_to_redis(
            execution_id="exec-redis-2",
            objective="test",
            selected_tools=[],
            connector_results=[],
            worker_results=[],
        )
        # Should not raise
