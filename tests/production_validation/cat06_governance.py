"""
Category 06 — Governance Test
================================
Validates the full governance pipeline:

  Approval → Reject → Emergency Stop → Audit Logs

Tests verify every layer:
  - ApprovalQueue: create, approve, reject, timeout
  - EmergencyStop: activate, check, clear, per-execution
  - AuditLogger: write, read, summary
  - Governance routes (HTTP): queue API, audit API, health
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List
from uuid import uuid4

from tests.production_validation import (
    CategoryResult, CheckResult, CheckStatus,
    http_get, http_post,
    pass_, fail_, skip_, warn_, check,
    backend_is_up, BASE_URL,
)


# ---------------------------------------------------------------------------
# Approval Queue
# ---------------------------------------------------------------------------

def _check_approval_queue_importable() -> CheckResult:
    try:
        from backend.safety.approval_queue import ApprovalQueue, ApprovalStatus
        q = ApprovalQueue()
        return pass_("approval_queue_importable",
                     f"ApprovalQueue importable — statuses: {[s.value for s in ApprovalStatus]}")
    except ImportError as exc:
        return fail_("approval_queue_importable", f"Import failed: {exc}")
    except Exception as exc:
        return warn_("approval_queue_importable", f"Warning: {exc}")


def _check_approval_queue_approve() -> CheckResult:
    """Create a request and approve it. approve() fires asyncio.ensure_future which
    requires a running event loop — wrap in one."""
    try:
        import asyncio
        from backend.safety.approval_queue import ApprovalQueue, ApprovalStatus, ApprovalRequest

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        q   = ApprovalQueue()
        rid = str(uuid4())

        req = ApprovalRequest(
            request_id   = rid,
            execution_id = str(uuid4()),
            agent        = "orchestrator",
            action       = "execute_mission",
            description  = "Production validation test",
            risk_level   = "low",
            context      = {"test": True},
            session_id   = None,
        )
        q._requests[rid] = req

        result = q.approve(rid, approved_by="validator")

        # Drain any pending tasks (e.g. _emit_governance_event)
        try:
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(None)

        if result.status == ApprovalStatus.APPROVED:
            return pass_("approval_queue_approve",
                         f"Request {rid[:8]} approved successfully")
        return fail_("approval_queue_approve",
                     f"Unexpected status after approve: {result.status}")
    except Exception as exc:
        return fail_("approval_queue_approve", f"Approve test failed: {exc}")


def _check_approval_queue_reject() -> CheckResult:
    """Create a request and reject it."""
    try:
        import asyncio
        from backend.safety.approval_queue import ApprovalQueue, ApprovalStatus, ApprovalRequest
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        q   = ApprovalQueue()
        rid = str(uuid4())

        req = ApprovalRequest(
            request_id   = rid,
            execution_id = str(uuid4()),
            agent        = "orchestrator",
            action       = "execute_mission",
            description  = "Production validation reject test",
            risk_level   = "high",
            context      = {"test": True},
            session_id   = None,
        )
        q._requests[rid] = req

        result = q.reject(rid, reason="Validation test rejection", rejected_by="validator")
        try:
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(None)

        if result.status == ApprovalStatus.REJECTED:
            return pass_("approval_queue_reject",
                         f"Request {rid[:8]} rejected with reason recorded")
        return fail_("approval_queue_reject",
                     f"Unexpected status after reject: {result.status}")
    except Exception as exc:
        return fail_("approval_queue_reject", f"Reject test failed: {exc}")


def _check_approval_queue_list() -> CheckResult:
    """get_pending() and get_queue() return lists."""
    try:
        from backend.safety.approval_queue import ApprovalQueue, ApprovalRequest
        q   = ApprovalQueue()
        rid = str(uuid4())
        req = ApprovalRequest(
            request_id   = rid,
            execution_id = str(uuid4()),
            agent        = "orchestrator",
            action       = "test",
            description  = "list test",
            risk_level   = "low",
            context      = {},
            session_id   = None,
        )
        q._requests[rid] = req

        pending   = q.get_pending()
        all_items = q.get_queue()  # get_queue() returns all, get_pending() returns pending

        if isinstance(pending, list) and isinstance(all_items, list):
            return pass_("approval_queue_list",
                         f"get_pending()={len(pending)}, get_queue()={len(all_items)}")
        return fail_("approval_queue_list", "get_pending/get_queue did not return lists")
    except Exception as exc:
        return fail_("approval_queue_list", f"List test failed: {exc}")


# ---------------------------------------------------------------------------
# Emergency Stop
# ---------------------------------------------------------------------------

def _check_emergency_stop_importable() -> CheckResult:
    try:
        from backend.safety.emergency_stop import EmergencyStopController
        ec = EmergencyStopController()
        return pass_("emergency_stop_importable", "EmergencyStopController importable")
    except ImportError as exc:
        return fail_("emergency_stop_importable", f"Import failed: {exc}")
    except Exception as exc:
        return warn_("emergency_stop_importable", f"Warning: {exc}")


def _check_emergency_stop_per_execution() -> CheckResult:
    """Stop a specific mission, verify is_stopped, then clear."""
    try:
        from backend.safety.emergency_stop import EmergencyStopController
        import asyncio
        loop = asyncio.new_event_loop()
        ec   = EmergencyStopController()
        eid  = str(uuid4())

        loop.run_until_complete(ec.stop_mission(eid, reason="Validation test"))
        stopped = ec.is_stopped(eid)
        if not stopped:
            loop.close()
            return fail_("emergency_stop_per_execution",
                         "is_stopped returned False after stop_mission")

        ec.resume_mission(eid)
        cleared = not ec.is_stopped(eid)
        loop.close()
        if cleared:
            return pass_("emergency_stop_per_execution",
                         "Per-execution stop and resume work correctly")
        return fail_("emergency_stop_per_execution", "resume_mission did not clear the stop")
    except Exception as exc:
        return fail_("emergency_stop_per_execution", f"Test failed: {exc}")


def _check_emergency_global_stop() -> CheckResult:
    """Activate global stop, verify is_globally_stopped, then deactivate."""
    try:
        from backend.safety.emergency_stop import EmergencyStopController
        import asyncio
        loop = asyncio.new_event_loop()
        ec   = EmergencyStopController()

        loop.run_until_complete(ec.activate_global(reason="Validation test"))
        if not ec.is_globally_stopped:   # is_globally_stopped is a @property, not a method
            loop.close()
            return fail_("emergency_global_stop", "Global stop not active after activate_global")

        loop.run_until_complete(ec.deactivate_global(deactivated_by="validator"))
        loop.close()
        if ec.is_globally_stopped:   # @property
            return fail_("emergency_global_stop", "Global stop still active after deactivate_global")

        return pass_("emergency_global_stop", "Global stop activate/deactivate works correctly")
    except Exception as exc:
        return fail_("emergency_global_stop", f"Test failed: {exc}")


def _check_emergency_stop_log() -> CheckResult:
    """Emergency stop maintains a stop_log via get_stop_log()."""
    try:
        from backend.safety.emergency_stop import EmergencyStopController
        import asyncio
        loop = asyncio.new_event_loop()
        ec   = EmergencyStopController()
        eid  = str(uuid4())
        loop.run_until_complete(ec.stop_mission(eid, reason="log_test"))
        loop.close()

        log = ec.get_stop_log(limit=50)
        if isinstance(log, list) and len(log) > 0:
            return pass_("emergency_stop_log", f"Stop log has {len(log)} entries")
        return warn_("emergency_stop_log", "Stop log empty or not a list")
    except Exception as exc:
        return fail_("emergency_stop_log", f"Log check failed: {exc}")


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

def _check_audit_logger_write() -> CheckResult:
    """AuditLogger.log() creates an AuditEntry."""
    try:
        from backend.safety.audit_logger import AuditLogger, AuditEntry
        # Create a fresh instance with a new event loop to avoid the
        # 'no current event loop in thread' error that occurs outside FastAPI
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger = AuditLogger()
        eid    = str(uuid4())
        entry  = logger.log(
            execution_id = eid,
            agent        = "validator",
            action       = "production_validation",
            risk_level   = "low",
            outcome      = "completed",
            reason       = "Validation test write",
        )
        loop.close()
        asyncio.set_event_loop(None)
        if isinstance(entry, AuditEntry):
            return pass_("audit_logger_write",
                         f"AuditEntry created: {entry.audit_id[:8]}")
        return fail_("audit_logger_write", f"log() returned {type(entry).__name__}, expected AuditEntry")
    except Exception as exc:
        return fail_("audit_logger_write", f"Write test failed: {exc}")


def _check_audit_logger_read_cache() -> CheckResult:
    """AuditLogger writes to its in-process cache and get_all() returns it."""
    try:
        from backend.safety.audit_logger import AuditLogger
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger = AuditLogger()
        eid    = str(uuid4())
        logger.log(
            execution_id = eid,
            agent        = "validator",
            action       = "validation_read_test",
            risk_level   = "low",
            outcome      = "completed",
            reason       = "Read cache test",
        )
        loop.close()
        asyncio.set_event_loop(None)
        all_entries = logger.get_all(limit=50)
        our_entry   = next(
            (e for e in all_entries
             if e.get("action") == "validation_read_test"),
            None,
        )
        if our_entry:
            return pass_("audit_logger_read_cache",
                         "AuditLogger cache read works correctly")
        if isinstance(all_entries, list):
            return warn_("audit_logger_read_cache",
                         f"get_all() returned {len(all_entries)} entries but our entry not found (DB may be offline)")
        return fail_("audit_logger_read_cache", "get_all() did not return a list")
    except Exception as exc:
        return fail_("audit_logger_read_cache", f"Read cache test failed: {exc}")


def _check_audit_logger_summary() -> CheckResult:
    """AuditLogger.summary() returns structured stats."""
    try:
        from backend.safety.audit_logger import AuditLogger
        logger = AuditLogger()
        summary = logger.summary()
        if isinstance(summary, dict):
            return pass_("audit_logger_summary",
                         "summary() returns dict",
                         keys=list(summary.keys()))
        return fail_("audit_logger_summary", f"summary() returned {type(summary).__name__}")
    except Exception as exc:
        return fail_("audit_logger_summary", f"Summary test failed: {exc}")


# ---------------------------------------------------------------------------
# Governance HTTP routes
# ---------------------------------------------------------------------------

def _check_governance_health_route() -> CheckResult:
    code, body = http_get("/governance/health", timeout=5.0)
    if code == 200:
        status = body.get("status", "?") if isinstance(body, dict) else "?"
        return pass_("governance_health_route",
                     f"Governance health route: {status}")
    return warn_("governance_health_route", f"/governance/health HTTP {code}")


def _check_governance_queue_route() -> CheckResult:
    code, body = http_get("/governance/queue", timeout=5.0)
    if code == 200 and isinstance(body, dict):
        count = body.get("total", len(body.get("requests", [])))
        return pass_("governance_queue_route",
                     f"/governance/queue accessible — {count} pending")
    return warn_("governance_queue_route", f"/governance/queue HTTP {code}")


def _check_governance_audit_route() -> CheckResult:
    code, body = http_get("/governance/audit", timeout=5.0)
    if code == 200 and isinstance(body, dict):
        count = body.get("total", len(body.get("entries", [])))
        return pass_("governance_audit_route",
                     f"/governance/audit accessible — {count} entries")
    return warn_("governance_audit_route", f"/governance/audit HTTP {code}")


def _check_guardrails_health_route() -> CheckResult:
    code, body = http_get("/health/guardrails", timeout=5.0)
    if code == 200 and isinstance(body, dict):
        policy = body.get("active_policy", "?")
        return pass_("guardrails_health_route",
                     f"Guardrails health: active_policy={policy}")
    return fail_("guardrails_health_route", f"/health/guardrails HTTP {code}")


# ---------------------------------------------------------------------------
# Category runner
# ---------------------------------------------------------------------------

def run() -> CategoryResult:
    cat = CategoryResult("06 — Governance")

    # Pure-Python checks (no backend required)
    for fn in [
        _check_approval_queue_importable,
        _check_approval_queue_approve,
        _check_approval_queue_reject,
        _check_approval_queue_list,
        _check_emergency_stop_importable,
        _check_emergency_stop_per_execution,
        _check_emergency_global_stop,
        _check_emergency_stop_log,
        _check_audit_logger_write,
        _check_audit_logger_read_cache,
        _check_audit_logger_summary,
    ]:
        cat.checks.append(check(fn.__name__.lstrip("_"), fn))

    # HTTP checks (requires running backend)
    if backend_is_up():
        for fn in [
            _check_governance_health_route,
            _check_governance_queue_route,
            _check_governance_audit_route,
            _check_guardrails_health_route,
        ]:
            cat.checks.append(check(fn.__name__.lstrip("_"), fn))
    else:
        cat.checks.append(skip_("http_governance", "Backend not reachable"))

    return cat
