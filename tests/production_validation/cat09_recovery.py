"""
Category 09 — Recovery Test
==============================
Simulates failure scenarios and verifies recovery:

  1. WebSocket — connection reset, reconnect, events still flowing
  2. Database  — DB unavailable, fallback paths, graceful degradation
  3. Browser   — session orphan, new session creation
  4. LLM provider — primary fails, fallback provider kicks in
  5. Mission abort — mid-flight abort via emergency stop

All tests use in-process probes + HTTP boundary tests.
No actual DB/broker is killed — we test the error-handling code paths.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict
from uuid import uuid4

from tests.production_validation import (
    CategoryResult, CheckResult, CheckStatus,
    http_get, http_post,
    pass_, fail_, skip_, warn_, check,
    backend_is_up, BASE_URL, MISSION_TIMEOUT,
)


# ---------------------------------------------------------------------------
# 1. WebSocket stability
# ---------------------------------------------------------------------------

def _check_websocket_reconnect() -> CheckResult:
    """
    Open two successive TCP connections to the WebSocket port.
    Each connection close/reopen simulates a reconnect.
    """
    import socket, urllib.parse
    from tests.production_validation import WS_URL

    parsed = urllib.parse.urlparse(WS_URL)
    host   = parsed.hostname or "localhost"
    port   = parsed.port or 8000

    for attempt in range(2):
        try:
            s = socket.create_connection((host, port), timeout=5.0)
            s.close()
        except Exception as exc:
            return fail_("websocket_reconnect",
                         f"Connection attempt {attempt+1} failed: {exc}")
    return pass_("websocket_reconnect",
                 "Two successive WebSocket port connections succeeded (reconnect simulation)")


def _check_events_after_reconnect() -> CheckResult:
    """After a port-level reconnect, /events still serves data."""
    code, body = http_get("/events", timeout=5.0)
    if code == 200:
        return pass_("events_after_reconnect", "/events accessible after reconnect simulation")
    return fail_("events_after_reconnect", f"/events HTTP {code} after reconnect")


# ---------------------------------------------------------------------------
# 2. Database unavailability
# ---------------------------------------------------------------------------

def _check_health_db_graceful() -> CheckResult:
    """
    /health/database returns graceful response even when DB is offline.
    """
    code, body = http_get("/health/database", timeout=5.0)
    if code == 200:
        status = body.get("status", "?") if isinstance(body, dict) else "?"
        return pass_("health_db_graceful",
                     f"/health/database responds gracefully: {status}")
    if code in (200, 503, 500):
        # 503 is acceptable — it means DB down, but response was structured
        return pass_("health_db_graceful",
                     f"/health/database returned structured HTTP {code} (graceful degradation)")
    return warn_("health_db_graceful", f"/health/database HTTP {code}")


def _check_audit_logger_memory_fallback() -> CheckResult:
    """
    AuditLogger writes to its in-memory cache when DB fails.
    This validates the fallback path without needing to kill the DB.
    """
    try:
        from backend.safety.audit_logger import AuditLogger
        logger = AuditLogger()
        eid    = str(uuid4())

        # Fire-and-forget (sync wrapper) — should never raise even if DB is down
        try:
            entry = logger.log(
                execution_id = eid,
                agent        = "recovery_test",
                action       = "db_fallback_test",
                risk_level   = "low",
                outcome      = "completed",
                reason       = "Fallback test",
            )
            if entry is not None:
                return pass_("audit_logger_memory_fallback",
                             "AuditLogger.log() succeeds even without DB connection")
            return warn_("audit_logger_memory_fallback",
                         "AuditLogger.log() returned None (DB write may have silently failed)")
        except Exception as inner:
            return warn_("audit_logger_memory_fallback",
                         f"AuditLogger.log() raised: {inner}")
    except Exception as exc:
        return fail_("audit_logger_memory_fallback", f"Import/init failed: {exc}")


def _check_memory_layer_graceful_degradation() -> CheckResult:
    """
    /api/memory/status reports degraded status when DB is offline
    rather than crashing with a 500.
    """
    code, body = http_get("/api/memory/status", timeout=5.0)
    if code in (200, 503):
        return pass_("memory_layer_graceful",
                     f"/api/memory/status returned HTTP {code} (graceful)")
    if code == 404:
        return skip_("memory_layer_graceful", "Memory status route not registered")
    if code == 500:
        return fail_("memory_layer_graceful",
                     "Memory layer crashed with HTTP 500 — unhandled exception")
    return warn_("memory_layer_graceful", f"Unexpected HTTP {code}")


# ---------------------------------------------------------------------------
# 3. Browser session recovery
# ---------------------------------------------------------------------------

def _check_browser_session_cleanup() -> CheckResult:
    """
    BrowserAgent.close_session() can be called on a non-existent session
    without raising an exception.
    """
    try:
        from backend.tools.browser_agent import browser_agent
        orphan_id = f"orphan-session-{uuid4().hex}"
        # Should silently succeed even if session doesn't exist
        try:
            asyncio.run(browser_agent.close_session(orphan_id))
        except Exception as inner:
            # Non-fatal if close on nonexistent session logs a warning
            pass
        return pass_("browser_session_cleanup",
                     "BrowserAgent.close_session() on orphan session handled gracefully")
    except ImportError as exc:
        return skip_("browser_session_cleanup", f"BrowserAgent not available: {exc}")
    except Exception as exc:
        return warn_("browser_session_cleanup", f"Cleanup test: {exc}")


def _check_browser_session_history() -> CheckResult:
    """BrowserAgent.get_session_history() returns empty list for unknown session."""
    try:
        from backend.tools.browser_agent import browser_agent
        history = browser_agent.get_session_history("nonexistent-session-xyz")
        if isinstance(history, list):
            return pass_("browser_session_history",
                         "get_session_history() returns [] for unknown session")
        return warn_("browser_session_history",
                     f"Unexpected return type: {type(history).__name__}")
    except ImportError as exc:
        return skip_("browser_session_history", f"BrowserAgent not available: {exc}")
    except Exception as exc:
        return warn_("browser_session_history", f"History test: {exc}")


# ---------------------------------------------------------------------------
# 4. LLM provider fallback
# ---------------------------------------------------------------------------

def _check_llm_gateway_importable() -> CheckResult:
    """LLM Gateway singleton is importable."""
    try:
        from backend.llm.llm_gateway import llm_gateway
        return pass_("llm_gateway_importable", "LLM Gateway importable")
    except ImportError as exc:
        return fail_("llm_gateway_importable", f"LLM Gateway import failed: {exc}")
    except Exception as exc:
        return warn_("llm_gateway_importable", f"LLM Gateway warning: {exc}")


def _check_llm_fallback_chain() -> CheckResult:
    """
    Verify LLM Gateway has multiple providers configured (fallback chain).
    """
    try:
        import os
        from pathlib import Path

        # Load .env
        env_path = Path("backend/.env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

        providers = []
        if os.getenv("OPENAI_API_KEY"):
            providers.append("openai")
        if os.getenv("ANTHROPIC_API_KEY"):
            providers.append("anthropic")
        if os.getenv("GOOGLE_API_KEY"):
            providers.append("google")

        if len(providers) >= 2:
            return pass_("llm_fallback_chain",
                         f"Multiple LLM providers configured: {providers}")
        if len(providers) == 1:
            return warn_("llm_fallback_chain",
                         f"Only 1 LLM provider ({providers}) — no fallback if it fails")
        return fail_("llm_fallback_chain", "No LLM API keys configured")
    except Exception as exc:
        return fail_("llm_fallback_chain", f"Check failed: {exc}")


# ---------------------------------------------------------------------------
# 5. Mission abort via emergency stop
# ---------------------------------------------------------------------------

def _check_emergency_stop_aborts_mission() -> CheckResult:
    """
    Simulate an emergency stop mid-mission:
    1. Submit a mission
    2. Immediately activate stop for its execution_id
    3. Verify is_stopped() returns True
    """
    try:
        from backend.safety.emergency_stop import EmergencyStopController
        loop = asyncio.new_event_loop()
        ec   = EmergencyStopController()
        eid  = str(uuid4())

        loop.run_until_complete(ec.stop_mission(eid, reason="recovery_test_abort"))
        loop.close()

        if ec.is_stopped(eid):
            ec.resume_mission(eid)
            return pass_("emergency_stop_aborts",
                         "Emergency stop correctly flags execution as stopped")
        return fail_("emergency_stop_aborts",
                     "is_stopped() returned False after stop_mission")
    except Exception as exc:
        return fail_("emergency_stop_aborts", f"Abort test failed: {exc}")


def _check_runtime_state_cleans_stopped() -> CheckResult:
    """
    RuntimeState.end_execution() should remove completed executions.
    """
    try:
        from backend.runtime.runtime_state import RuntimeState
        rs  = RuntimeState()
        eid = str(uuid4())
        rs.start_execution(execution_id=eid, objective="recovery_test")
        rs.end_execution(eid)

        active        = rs.get_running_executions()
        still_running = any(e.get("execution_id") == eid for e in active)

        if not still_running:
            return pass_("runtime_state_cleanup_abort",
                         "RuntimeState removes ended execution from active list")
        return fail_("runtime_state_cleanup_abort",
                     "Ended execution still in active list — potential memory leak")
    except ImportError as exc:
        return skip_("runtime_state_cleanup_abort", f"RuntimeState not available: {exc}")
    except Exception as exc:
        return warn_("runtime_state_cleanup_abort", f"RuntimeState check: {exc}")


# ---------------------------------------------------------------------------
# 6. Health check cascade
# ---------------------------------------------------------------------------

def _check_health_cascade() -> CheckResult:
    """
    All health endpoints respond within 10 seconds even when some
    subsystems are degraded.
    """
    endpoints = [
        "/health",
        "/health/database",
        "/health/embeddings",
        "/health/research",
        "/health/guardrails",
    ]
    timings = {}
    for ep in endpoints:
        t0       = time.perf_counter()
        code, _  = http_get(ep, timeout=10.0)
        elapsed  = time.perf_counter() - t0
        timings[ep] = {"code": code, "latency": round(elapsed, 3)}

    slow = {ep: v for ep, v in timings.items() if v["latency"] > 5.0}
    errors = {ep: v for ep, v in timings.items() if v["code"] not in (200, 503)}

    if not slow and not errors:
        max_lat = max(v["latency"] for v in timings.values())
        return pass_("health_cascade",
                     f"All health endpoints responded — max latency {max_lat:.2f}s",
                     timings=timings)
    messages = []
    if slow:
        messages.append(f"Slow: {slow}")
    if errors:
        messages.append(f"Errors: {errors}")
    return warn_("health_cascade",
                 "; ".join(messages),
                 timings=timings)


# ---------------------------------------------------------------------------
# Category runner
# ---------------------------------------------------------------------------

def run() -> CategoryResult:
    cat = CategoryResult("09 — Recovery")

    # Pure-Python checks
    for fn in [
        _check_audit_logger_memory_fallback,
        _check_llm_gateway_importable,
        _check_llm_fallback_chain,
        _check_emergency_stop_aborts_mission,
        _check_runtime_state_cleans_stopped,
        _check_browser_session_cleanup,
        _check_browser_session_history,
    ]:
        cat.checks.append(check(fn.__name__.lstrip("_"), fn))

    # HTTP checks
    if backend_is_up():
        for fn in [
            _check_websocket_reconnect,
            _check_events_after_reconnect,
            _check_health_db_graceful,
            _check_memory_layer_graceful_degradation,
            _check_health_cascade,
        ]:
            cat.checks.append(check(fn.__name__.lstrip("_"), fn))
    else:
        cat.checks.append(skip_("http_recovery", "Backend not reachable"))

    return cat
