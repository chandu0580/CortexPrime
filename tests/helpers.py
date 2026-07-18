"""
Test helpers for Sprint 40.1 — Mission Execution Validation.
Provides mock / stub factories so that import-heavy tests can run
without the full Docker environment.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock


# =============================================================
# MOCK MISSION RUNTIME
# =============================================================

def _mock_mission_runtime():
    """
    Return a mock module-like namespace for
    ``backend.services.mission_runtime``.

    All attributes are default MagicMock / AsyncMock so they respond
    to any call without raising.
    """
    mod = SimpleNamespace()

    mod.MissionRuntimeService = MagicMock()
    mod.MissionStage = SimpleNamespace(
        INIT="INIT",
        PLANNING="PLANNING",
        RESEARCHING="RESEARCHING",
        REASONING="REASONING",
        VALIDATING="VALIDATING",
        GENERATING="GENERATING",
        MEMORY_UPDATE="MEMORY_UPDATE",
        COMPLETED="COMPLETED",
        FAILED="FAILED",
    )
    mod._call_llm = AsyncMock(return_value="mock llm output")
    mod._emit = AsyncMock()
    mod._stream_llm_to_ws = AsyncMock(return_value="mock stream output")
    mod._is_browser_task = MagicMock(return_value=False)
    mod._is_computer_task = MagicMock(return_value=False)
    mod._guardrails_check_input = MagicMock(return_value=None)
    mod._guardrails_check_output = MagicMock(return_value=None)
    mod._guardrails_check_tool = MagicMock(return_value=None)
    mod._governance_assess = MagicMock(return_value=None)
    mod._governance_log = MagicMock()
    mod._is_emergency_stopped = MagicMock(return_value=False)
    mod._send_stream_chunk = AsyncMock()
    mod.event_bus = AsyncMock()
    mod.llm_router = AsyncMock()
    mod.llm_gateway = AsyncMock()
    mod.vector_memory = MagicMock()
    mod.memory_context_service = AsyncMock()
    mod.runtime_state = MagicMock()
    mod.cost_engine = AsyncMock()
    mod._prom_metrics = MagicMock()
    mod.runtime_metrics = MagicMock()
    mod.orchestration_tracer = MagicMock()
    mod.runtime_state = MagicMock()

    return mod


# =============================================================
# MOCK MISSION STAGE CONSTANTS
# =============================================================

def _get_stage_constants() -> set[str]:
    """Return the expected MissionStage constant values."""
    return {
        "INIT",
        "PLANNING",
        "TOOL_SELECTION",
        "TOOL_EXECUTION",
        "RESEARCHING",
        "REASONING",
        "VALIDATING",
        "GENERATING",
        "MEMORY_UPDATE",
        "COMPLETED",
        "FAILED",
    }


# =============================================================
# MOCK STREAM FALLBACK
# =============================================================

def _mock_stream_fallback() -> list[str]:
    """Return the expected fallback chain order."""
    return ["stream", "azure", "openai"]


# =============================================================
# MOCK STREAM EMIT
# =============================================================

# =============================================================
# MOCK TOOL RESULTS FORMATTER
# =============================================================

def _mock_tool_results_formatter(
    connector_results: list[dict],
    worker_results: list[dict],
) -> str:
    """Replicate _format_tool_results logic for testing."""
    parts: list[str] = []
    if connector_results:
        parts.append("## Connector Execution Results\n")
        for r in connector_results:
            status = "✅" if r.get("success") else "❌"
            rid = r.get("resource_id", "")
            dur = r.get("duration_ms", 0)
            line = f"{status} {r.get('connector', '?')}.{r.get('operation', '?')} ({dur}ms)"
            if rid:
                line += f" resource_id={rid}"
            if r.get("error"):
                line += f" error={r['error']}"
            parts.append(line)
    if worker_results:
        parts.append("\n## Worker Execution Results\n")
        for r in worker_results:
            status = "✅" if r.get("success") else "❌"
            parts.append(f"{status} {r.get('worker', '?')}.{r.get('operation', '?')}")
            if r.get("error"):
                parts[-1] += f" error={r['error']}"
    return "\n".join(parts)

async def _mock_stream_emit(
    send_fn: AsyncMock,
    inject_error: type[Exception] | None = None,
) -> None:
    """
    Simulate _stream_llm_to_ws's emit logic.

    Sends ``stream_chunk`` events, then a final ``stream_completed``.
    If *inject_error* is given, simulates a fallback path that still
    emits ``stream_completed``.
    """
    if inject_error:
        # Simulate fallback path: send fallback tokens then completed
        await send_fn({
            "agent": "orchestrator",
            "event_type": "stream_chunk",
            "stream_chunk": "fallback ",
        }, "s1")
        await send_fn({
            "agent": "orchestrator",
            "event_type": "stream_chunk",
            "stream_chunk": "response. ",
        }, "s1")
    else:
        await send_fn({
            "agent": "orchestrator",
            "event_type": "stream_chunk",
            "stream_chunk": "Normal ",
        }, "s1")
        await send_fn({
            "agent": "orchestrator",
            "event_type": "stream_chunk",
            "stream_chunk": "response. ",
        }, "s1")

    await send_fn({
        "agent": "orchestrator",
        "event_type": "stream_completed",
        "stream_completed": True,
        "execution_id": "e1",
        "session_id": "s1",
        "status": "completed",
        "message": "Stream complete",
    }, "s1")
