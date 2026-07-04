"""
Governance API Routes  (CortexPrime)
========================================
POST /governance/request-approval   — submit a manual approval request
POST /governance/approve            — approve a pending request
POST /governance/reject             — reject a pending request
GET  /governance/queue              — list all queued requests
GET  /governance/queue/pending      — list pending requests only
GET  /governance/audit              — full audit trail
GET  /governance/audit/summary      — aggregate statistics
POST /governance/emergency-stop     — activate global emergency stop
POST /governance/emergency-stop/deactivate — lift global stop
POST /governance/stop-mission       — stop a specific mission
POST /governance/stop-browser       — stop browser agent sessions
POST /governance/stop-computer      — stop computer agent missions
GET  /governance/stop-status        — emergency stop status
POST /governance/safety/assess      — assess an action for risk
GET  /governance/health             — governance system health check
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_admin, require_user
from backend.safety.safety_guard    import safety_guard
from backend.safety.permission_engine import permission_engine
from backend.safety.approval_queue  import approval_queue
from backend.safety.audit_logger    import audit_logger
from backend.safety.emergency_stop  import emergency_stop

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/governance", tags=["Governance"])

# Convenience: apply to every protected route individually so /health stays open.
_SECURE = [Depends(require_user)]
_ADMIN = [Depends(require_admin)]


# =========================================================
# REQUEST MODELS
# =========================================================

class ManualApprovalRequest(BaseModel):
    execution_id: str              = Field(..., max_length=128)
    agent:        str              = Field(default="operator", max_length=64)
    action:       str              = Field(..., max_length=256)
    description:  str              = Field(..., max_length=1024)
    risk_level:   str              = Field(default="high", max_length=32)
    context:      Optional[Dict[str, Any]] = None
    session_id:   Optional[str]    = None


class ApproveRequest(BaseModel):
    request_id:  str = Field(..., max_length=128)
    approved_by: str = Field(default="operator", max_length=64)


class RejectRequest(BaseModel):
    request_id:   str = Field(..., max_length=128)
    rejected_by:  str = Field(default="operator", max_length=64)
    reason:       str = Field(default="Rejected by operator", max_length=512)


class EmergencyStopRequest(BaseModel):
    reason:     str = Field(default="Operator emergency stop", max_length=512)
    stopped_by: str = Field(default="operator", max_length=64)


class StopMissionRequest(BaseModel):
    execution_id: str = Field(..., max_length=128)
    reason:       str = Field(default="Stopped by operator", max_length=512)
    stopped_by:   str = Field(default="operator", max_length=64)


class SafetyAssessRequest(BaseModel):
    action:  str            = Field(..., max_length=1024)
    target:  str            = Field(default="", max_length=1024)
    agent:   str            = Field(default="", max_length=64)
    context: str            = Field(default="", max_length=2048)


# =========================================================
# APPROVAL QUEUE ROUTES
# =========================================================

@router.post("/request-approval", dependencies=_SECURE)
async def request_approval(body: ManualApprovalRequest) -> Dict[str, Any]:
    """
    Submit a manual approval request to the governance queue.
    Returns immediately with the request ID (non-blocking).
    """
    import asyncio

    # Create the request and immediately snapshot — do not await the long-running
    # approval wait here; the operator uses /approve or /reject to resolve it.
    req_id = None
    try:
        # We fire the request as a background task so the HTTP call returns
        # instantly with the request_id while the approval wait happens async.
        import uuid as _uuid

        from backend.safety.approval_queue import ApprovalRequest, ApprovalStatus

        req = ApprovalRequest(
            request_id   = str(_uuid.uuid4()),
            execution_id = body.execution_id,
            agent        = body.agent,
            action       = body.action,
            description  = body.description,
            risk_level   = body.risk_level,
            context      = body.context or {},
            session_id   = body.session_id,
        )
        approval_queue._requests[req.request_id] = req
        req_id = req.request_id

        # Log to audit trail
        audit_logger.log(
            execution_id = body.execution_id,
            agent        = body.agent,
            action       = body.action,
            target       = body.context.get("target", "") if body.context else "",
            risk_level   = body.risk_level,
            outcome      = "pending",
            reason       = "Manual approval submitted via API",
            request_id   = req_id,
        )

        # Emit WebSocket notification
        from backend.safety.approval_queue import _emit_governance_event
        asyncio.ensure_future(_emit_governance_event("approval_requested", req, body.session_id))

        return {
            "accepted":   True,
            "request_id": req_id,
            "status":     "pending",
            "message":    "Approval request queued. Waiting for operator decision.",
        }

    except Exception as exc:
        log.error("request-approval error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/approve", dependencies=_ADMIN)
async def approve_request(body: ApproveRequest) -> Dict[str, Any]:
    """Approve a pending governance request."""
    try:
        req = approval_queue.approve(body.request_id, approved_by=body.approved_by)

        await audit_logger.alog(
            execution_id = req.execution_id,
            agent        = req.agent,
            action       = req.action,
            risk_level   = req.risk_level,
            outcome      = "approved",
            reason       = f"Approved by {body.approved_by}",
            user         = body.approved_by,
            request_id   = req.request_id,
        )

        return {
            "success":    True,
            "request_id": req.request_id,
            "status":     req.status.value,
            "approved_by": body.approved_by,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval request not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/reject", dependencies=_ADMIN)
async def reject_request(body: RejectRequest) -> Dict[str, Any]:
    """Reject a pending governance request."""
    try:
        req = approval_queue.reject(
            body.request_id,
            rejected_by = body.rejected_by,
            reason      = body.reason,
        )

        await audit_logger.alog(
            execution_id = req.execution_id,
            agent        = req.agent,
            action       = req.action,
            risk_level   = req.risk_level,
            outcome      = "rejected",
            reason       = body.reason,
            user         = body.rejected_by,
            request_id   = req.request_id,
        )

        return {
            "success":     True,
            "request_id":  req.request_id,
            "status":      req.status.value,
            "rejected_by": body.rejected_by,
            "reason":      body.reason,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval request not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/queue", dependencies=_SECURE)
async def get_queue(status: Optional[str] = None) -> Dict[str, Any]:
    """List all governance requests, optionally filtered by status."""
    items = approval_queue.get_queue(status=status)
    return {
        "requests": items,
        "total":    len(items),
        "filter":   status or "all",
    }


@router.get("/queue/pending", dependencies=_SECURE)
async def get_pending_queue() -> Dict[str, Any]:
    """List all pending approval requests."""
    items = approval_queue.get_pending()
    return {
        "requests": items,
        "total":    len(items),
    }


# =========================================================
# AUDIT TRAIL ROUTES
# =========================================================

@router.get("/audit", dependencies=_SECURE)
async def get_audit_log(
    page:       int           = 1,
    page_size:  int           = 50,
    limit:      Optional[int] = None,
    risk_level: Optional[str] = None,
    outcome:    Optional[str] = None,
    agent:      Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the governance audit trail from PostgreSQL.

    Supports pagination (page / page_size) and filtering by risk_level,
    outcome, and agent.  The legacy ``limit`` query param is still accepted
    and maps to page_size=limit, page=1 for backward compatibility.
    """
    if limit is not None:
        # Legacy callers: ?limit=N  →  first page of N entries
        result = await audit_logger.get_page(
            page=1, page_size=min(limit, 1000),
            risk_level=risk_level, outcome=outcome, agent=agent,
        )
    else:
        result = await audit_logger.get_page(
            page=page, page_size=min(page_size, 200),
            risk_level=risk_level, outcome=outcome, agent=agent,
        )
    return result


@router.get("/audit/summary", dependencies=_SECURE)
async def get_audit_summary() -> Dict[str, Any]:
    """Return aggregated governance statistics from PostgreSQL."""
    return await audit_logger.get_summary_async()


@router.get("/audit/{execution_id}", dependencies=_SECURE)
async def get_audit_by_execution(execution_id: str) -> Dict[str, Any]:
    """Return all audit entries for a specific execution from PostgreSQL."""
    entries = await audit_logger.get_by_execution_async(execution_id)
    return {
        "execution_id": execution_id,
        "entries":      entries,
        "total":        len(entries),
    }


# =========================================================
# EMERGENCY STOP ROUTES
# =========================================================

@router.post("/emergency-stop", dependencies=_ADMIN)
async def activate_emergency_stop(body: EmergencyStopRequest) -> Dict[str, Any]:
    """Activate global emergency stop — halts all running agents."""
    result = await emergency_stop.activate_global(
        reason     = body.reason,
        stopped_by = body.stopped_by,
    )
    audit_logger.log(
        execution_id = "global",
        agent        = "governance",
        action       = "emergency_stop",
        risk_level   = "critical",
        outcome      = "stopped",
        reason       = body.reason,
        user         = body.stopped_by,
    )
    return {"success": True, "detail": result}


@router.post("/emergency-stop/deactivate", dependencies=_ADMIN)
async def deactivate_emergency_stop(stopped_by: str = "operator") -> Dict[str, Any]:
    """Lift the global emergency stop."""
    result = await emergency_stop.deactivate_global(deactivated_by=stopped_by)
    return {"success": True, "detail": result}


@router.post("/stop-mission", dependencies=_ADMIN)
async def stop_mission(body: StopMissionRequest) -> Dict[str, Any]:
    """Stop a specific mission execution."""
    result = await emergency_stop.stop_mission(
        execution_id = body.execution_id,
        reason       = body.reason,
        stopped_by   = body.stopped_by,
    )
    audit_logger.log(
        execution_id = body.execution_id,
        agent        = "governance",
        action       = "stop_mission",
        risk_level   = "high",
        outcome      = "stopped",
        reason       = body.reason,
        user         = body.stopped_by,
    )
    return {"success": True, "detail": result}


@router.post("/stop-browser", dependencies=_ADMIN)
async def stop_browser_agent(body: EmergencyStopRequest) -> Dict[str, Any]:
    """Stop all active browser agent sessions."""
    result = await emergency_stop.stop_browser_agent(
        reason     = body.reason,
        stopped_by = body.stopped_by,
    )
    return {"success": True, "detail": result}


@router.post("/stop-computer", dependencies=_ADMIN)
async def stop_computer_agent(body: EmergencyStopRequest) -> Dict[str, Any]:
    """Stop all active computer agent missions."""
    result = await emergency_stop.stop_computer_agent(
        reason     = body.reason,
        stopped_by = body.stopped_by,
    )
    return {"success": True, "detail": result}


@router.get("/stop-status", dependencies=_SECURE)
async def get_stop_status() -> Dict[str, Any]:
    """Return current emergency stop status."""
    return emergency_stop.get_status()


# =========================================================
# SAFETY ASSESSMENT ROUTE
# =========================================================

@router.post("/safety/assess", dependencies=_SECURE)
async def assess_action(body: SafetyAssessRequest) -> Dict[str, Any]:
    """Assess an action for risk level without executing it."""
    assessment = safety_guard.assess_action(
        action  = body.action,
        target  = body.target,
        agent   = body.agent,
        context = body.context,
    )
    return assessment.as_dict()


# =========================================================
# HEALTH
# =========================================================

@router.get("/health")
async def governance_health() -> Dict[str, Any]:
    """Governance system health check."""
    pending_count = len(approval_queue.get_pending())
    return {
        "status":          "online",
        "global_stop":     emergency_stop.is_globally_stopped,
        "pending_approvals": pending_count,
        "audit_summary":   audit_logger.summary(),
    }
