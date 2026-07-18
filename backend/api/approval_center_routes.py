from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

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

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approval-center", tags=["Approval Center"])


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


@router.post("/workflows")
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


@router.post("/workflows/{workflow_id}/approve")
async def approve_step(
    workflow_id: str,
    approver: str,
    role: str,
    reason: Optional[str] = None,
):
    """Approve the current step of an approval workflow."""
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


@router.post("/workflows/{workflow_id}/reject")
async def reject_step(
    workflow_id: str,
    approver: str,
    reason: str,
):
    """Reject the current step of an approval workflow."""
    try:
        workflow = await approval_workflow_engine.reject_step(
            workflow_id=workflow_id,
            approver=approver,
            reason=reason,
        )
        return {"status": "rejected", "workflow": workflow.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workflows/{workflow_id}/delegate")
async def delegate_step(
    workflow_id: str,
    from_user: str,
    to_user: str,
    reason: str,
):
    """Delegate current approval step to another user."""
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


@router.post("/workflows/{workflow_id}/break-glass")
async def break_glass(
    workflow_id: str,
    overridden_by: str,
    role: str,
    reason: str,
    justification: Optional[str] = None,
):
    """Activate emergency break-glass override for a workflow."""
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
