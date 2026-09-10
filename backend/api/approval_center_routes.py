from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.legacy_execution_boundary import guard_legacy_execution
from backend.approval_center.models import (
    ApproverRole,
    RiskLevel,
    WorkflowStatus,
)
from backend.approval_center.policies import (
    assess_risk_from_context,
    get_policy,
    get_policy_for_mission,
    list_policies,
)
from backend.approval_center.workflows import approval_workflow_engine
from backend.auth.dependencies import require_user

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/approval-center",
    tags=["Approval Center"],
    dependencies=[Depends(require_user)],
)

# Phase 11.1 (ADR-121). This is the V1 approval centre: an in-memory workflow
# engine with no tenant and no action digest, whose approvals are replayed as
# real provider writes by ``enterprise_approval_action_dispatcher``. It is a
# second approval authority beside the governed one (``cp_approval``,
# ADR-090/113), and the platform may have only one. Reads stay available to a
# verified identity; every mutation sits behind the legacy execution guard
# (refused by default) and, when the flag is set for a migration, binds the
# approver to the *authenticated* principal rather than a query parameter.


def _bind_actor(claimed: str, current_user: dict, *, field: str) -> str:
    """The acting identity is the verified token subject, never a parameter."""
    subject = str(current_user.get("sub") or "").strip()
    if not subject:
        raise HTTPException(status_code=403, detail="the authenticated identity names no principal")
    if claimed and claimed != subject:
        raise HTTPException(
            status_code=403,
            detail=f"{field} must be the authenticated principal; an approval cannot be "
                   "recorded on behalf of someone else",
        )
    return subject


# ------------------------------------------------------------------
# Policies
# ------------------------------------------------------------------

@router.get("/policies")
async def get_all_policies():
    """List all approval policies."""
    return {"policies": list_policies(), "total": len(list_policies())}


@router.get("/policies/{policy_id}")
async def get_policy_detail(policy_id: str):
    """Get a specific approval policy."""
    policy = get_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")
    return {"policy": policy.to_dict()}


# ------------------------------------------------------------------
# Workflows
# ------------------------------------------------------------------

@router.get("/workflows")
async def get_workflows(status: Optional[str] = None):
    """List approval workflows, optionally filtered by status."""
    s = WorkflowStatus(status) if status else None
    workflows = approval_workflow_engine.list_workflows(status=s)
    return {
        "workflows": [w.to_dict() for w in workflows],
        "total": len(workflows),
        "filter": status or "all",
    }


@router.get("/workflows/{workflow_id}")
async def get_workflow_detail(workflow_id: str):
    """Get detailed approval workflow state."""
    wf = approval_workflow_engine.get_workflow(workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
    return {"workflow": wf.to_dict()}


@router.post("/workflows",
             dependencies=[Depends(guard_legacy_execution("POST /api/approval-center/workflows"))])
async def create_workflow(
    execution_id: str,
    mission_id: str,
    objective: str,
    risk_level: str = "medium",
    policy_id: Optional[str] = None,
    target_environment: Optional[str] = None,
    affected_systems: Optional[List[str]] = None,
    needs_browser: bool = False,
    needs_voice: bool = False,
):
    """Create a new approval workflow for a mission."""
    rl = RiskLevel(risk_level.lower())

    adjusted_risk = assess_risk_from_context(
        risk_level=rl,
        mission_id=mission_id,
        needs_browser=needs_browser,
        needs_voice=needs_voice,
        target_environment=target_environment,
        affected_systems=affected_systems,
    )

    policy = get_policy(policy_id) if policy_id else get_policy_for_mission(mission_id, adjusted_risk)

    workflow = await approval_workflow_engine.create_workflow(
        execution_id=execution_id,
        mission_id=mission_id,
        objective=objective,
        risk_level=adjusted_risk,
        policy=policy,
    )

    return {
        "status": "created",
        "workflow": workflow.to_dict(),
        "risk_adjusted": adjusted_risk.value if adjusted_risk != rl else None,
    }


@router.post("/workflows/{workflow_id}/approve",
             dependencies=[Depends(guard_legacy_execution("POST /api/approval-center/workflows/{id}/approve"))])
async def approve_step(
    workflow_id: str,
    role: str,
    approver: str = "",
    reason: Optional[str] = None,
    current_user: dict = Depends(require_user),
):
    """Approve the current step of an approval workflow."""
    approver = _bind_actor(approver, current_user, field="approver")
    try:
        workflow = await approval_workflow_engine.approve_step(
            workflow_id=workflow_id,
            approver=approver,
            role=ApproverRole(role.lower()),
            reason=reason,
        )
        return {"status": "approved", "workflow": workflow.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workflows/{workflow_id}/reject",
             dependencies=[Depends(guard_legacy_execution("POST /api/approval-center/workflows/{id}/reject"))])
async def reject_step(
    workflow_id: str,
    reason: str,
    approver: str = "",
    current_user: dict = Depends(require_user),
):
    """Reject the current step of an approval workflow."""
    approver = _bind_actor(approver, current_user, field="approver")
    try:
        workflow = await approval_workflow_engine.reject_step(
            workflow_id=workflow_id,
            approver=approver,
            reason=reason,
        )
        return {"status": "rejected", "workflow": workflow.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workflows/{workflow_id}/delegate",
             dependencies=[Depends(guard_legacy_execution("POST /api/approval-center/workflows/{id}/delegate"))])
async def delegate_step(
    workflow_id: str,
    to_user: str,
    reason: str,
    from_user: str = "",
    current_user: dict = Depends(require_user),
):
    """Delegate current approval step to another user."""
    from_user = _bind_actor(from_user, current_user, field="from_user")
    try:
        workflow = await approval_workflow_engine.delegate(
            workflow_id=workflow_id,
            from_user=from_user,
            to_user=to_user,
            reason=reason,
        )
        return {"status": "delegated", "workflow": workflow.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workflows/{workflow_id}/break-glass",
             dependencies=[Depends(guard_legacy_execution("POST /api/approval-center/workflows/{id}/break-glass"))])
async def break_glass(
    workflow_id: str,
    role: str,
    reason: str,
    overridden_by: str = "",
    justification: Optional[str] = None,
    current_user: dict = Depends(require_user),
):
    """Activate emergency break-glass override for a workflow."""
    overridden_by = _bind_actor(overridden_by, current_user, field="overridden_by")
    try:
        workflow = await approval_workflow_engine.break_glass(
            workflow_id=workflow_id,
            overridden_by=overridden_by,
            role=ApproverRole(role.lower()),
            reason=reason,
            justification=justification,
        )
        return {"status": "break_glass_activated", "workflow": workflow.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ------------------------------------------------------------------
# Delegations
# ------------------------------------------------------------------

@router.get("/delegations")
async def get_delegations():
    """List all active approval delegations."""
    return {
        "delegations": [d.to_dict() for d in approval_workflow_engine.list_delegations()],
        "total": len(approval_workflow_engine.list_delegations()),
    }


# ------------------------------------------------------------------
# Break-Glass Records
# ------------------------------------------------------------------

@router.get("/break-glass")
async def get_break_glass_records():
    """List all break-glass emergency override records."""
    records = approval_workflow_engine.list_break_glass_records()
    return {
        "records": [r.to_dict() for r in records],
        "total": len(records),
    }


# ------------------------------------------------------------------
# Summary & Analytics
# ------------------------------------------------------------------

@router.get("/summary")
async def get_summary():
    """Get approval center summary statistics."""
    return approval_workflow_engine.get_workflow_summary()


@router.get("/analytics")
async def get_analytics():
    """Get approval workflow analytics including timing and risk distribution."""
    workflows = approval_workflow_engine.list_workflows()
    total = len(workflows)

    by_risk: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    pending_count = 0
    active_escalations = 0
    break_glass_count = 0

    for wf in workflows:
        rl = wf.risk_level.value
        by_risk[rl] = by_risk.get(rl, 0) + 1

        st = wf.status.value
        by_status[st] = by_status.get(st, 0) + 1

        if wf.status in (WorkflowStatus.PENDING, WorkflowStatus.IN_PROGRESS):
            pending_count += 1

        if wf.status == WorkflowStatus.ESCALATED:
            active_escalations += 1

        if wf.break_glass:
            break_glass_count += 1

    return {
        "total_workflows": total,
        "by_risk": by_risk,
        "by_status": by_status,
        "pending_approvals": pending_count,
        "active_escalations": active_escalations,
        "break_glass_count": break_glass_count,
        "approval_bottlenecks": [
            {"level": s.level, "role": [r.value for r in s.required_roles]}
            for wf in workflows if wf.current_step_obj
            for s in [wf.current_step_obj]
            if s.status.value == "pending"
        ],
    }
