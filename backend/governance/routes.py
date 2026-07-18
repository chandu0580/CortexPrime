from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance"])

_handlers: dict[str, Any] = {}


def register_governance_routes(service: Any, events: Any) -> None:
    _handlers["service"] = service
    _handlers["events"] = events


def _get_service():
    svc = _handlers.get("service")
    if not svc:
        from backend.governance.service import GovernanceService
        svc = GovernanceService()
        _handlers["service"] = svc
    return svc


# ------------------------------------------------------------------
# Request/Response models
# ------------------------------------------------------------------


class CreatePolicyRequest(BaseModel):
    name: str
    category: str = "general"
    description: str = ""
    severity: str = "medium"
    conditions: Optional[dict[str, Any]] = None
    actions: Optional[dict[str, Any]] = None
    enabled: bool = True


class UpdatePolicyRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    conditions: Optional[dict[str, Any]] = None
    actions: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


class EvaluateRequest(BaseModel):
    requester: str = ""
    user: str = ""
    role: str = ""
    tenant: str = ""
    resource_type: str = ""
    resource_id: str = ""
    action: str = ""
    mission_id: Optional[str] = None
    mission_type: Optional[str] = None
    execution_id: Optional[str] = None
    execution_type: Optional[str] = None
    connector_type: Optional[str] = None
    connector_capability: Optional[str] = None
    scope: str = "mission"
    risk_level: str = "low"
    context: dict[str, Any] = {}


class ApprovalRequestCreate(BaseModel):
    requester: str = ""
    user: str = ""
    resource_type: str = ""
    resource_id: str = ""
    action: str = ""
    reason: str = ""
    reviewers: list[str] = []


class ApprovalActionRequest(BaseModel):
    request_id: str
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None


# ------------------------------------------------------------------
# Policy CRUD
# ------------------------------------------------------------------


@router.get("/policies", response_model=list[dict[str, Any]])
async def list_policies(
    category: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
):
    svc = _get_service()
    return await svc.list_policies(category=category, enabled_only=enabled_only)


@router.get("/policies/{policy_id}", response_model=dict[str, Any])
async def get_policy(policy_id: str):
    svc = _get_service()
    policy = await svc.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy


@router.post("/policies", response_model=dict[str, Any])
async def create_policy(req: CreatePolicyRequest):
    svc = _get_service()
    policy = await svc.create_policy(
        name=req.name,
        category=req.category,
        description=req.description,
        severity=req.severity,
        conditions=req.conditions,
        actions=req.actions,
        enabled=req.enabled,
    )
    return policy


@router.put("/policies/{policy_id}", response_model=dict[str, Any])
async def update_policy(policy_id: str, req: UpdatePolicyRequest):
    svc = _get_service()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = await svc.update_policy(policy_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return result


@router.delete("/policies/{policy_id}", response_model=dict[str, Any])
async def delete_policy(policy_id: str):
    svc = _get_service()
    success = await svc.delete_policy(policy_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return {"success": True, "policy_id": policy_id}


# ------------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------------


@router.post("/evaluate", response_model=dict[str, Any])
async def evaluate(req: EvaluateRequest):
    from backend.governance.models import DecisionRequest
    request = DecisionRequest(
        requester=req.requester,
        user=req.user,
        role=req.role,
        tenant=req.tenant,
        resource_type=req.resource_type or "mission",
        resource_id=req.resource_id or "",
        action=req.action or "execute",
        mission_id=req.mission_id,
        mission_type=req.mission_type,
        execution_id=req.execution_id,
        execution_type=req.execution_type,
        connector_type=req.connector_type,
        connector_capability=req.connector_capability,
        scope=req.scope,
        risk_level=req.risk_level,
        context=req.context,
    )
    svc = _get_service()
    response = await svc.evaluate(request)
    return {
        "decision": response.decision.value,
        "reason_code": response.reason_code.value,
        "message": response.message,
        "allowed": response.allowed,
        "denied": response.denied,
        "requires_approval": response.requires_approval,
        "matched_policies": [
            {
                "policy_name": p.policy_name,
                "policy_id": p.policy_id,
                "matched": p.matched,
                "decision": p.decision.value,
                "message": p.message,
            }
            for p in response.matched_policies
        ],
        "risk_level": response.risk_level,
    }


# ------------------------------------------------------------------
# Approvals
# ------------------------------------------------------------------


@router.post("/approvals", response_model=dict[str, Any])
async def request_approval(req: ApprovalRequestCreate):
    from backend.governance.models import DecisionRequest
    request = DecisionRequest(
        requester=req.requester or req.user,
        user=req.user,
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        action=req.action,
        context={"reason": req.reason},
    )
    svc = _get_service()
    result = await svc.request_approval(
        request=request,
        reason=req.reason,
        reviewers=req.reviewers,
    )
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create approval request")
    return result


@router.get("/approvals", response_model=list[dict[str, Any]])
async def list_approvals(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = _get_service()
    return await svc.list_approval_requests(status=status, limit=limit, offset=offset)


@router.get("/approvals/{request_id}", response_model=dict[str, Any])
async def get_approval(request_id: str):
    svc = _get_service()
    result = await svc.get_approval_request(request_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Approval request {request_id} not found")
    return result


@router.post("/approve", response_model=dict[str, Any])
async def approve(req: ApprovalActionRequest):
    svc = _get_service()
    result = await svc.approve(req.request_id, approved_by=req.approved_by or "api")
    if not result:
        raise HTTPException(status_code=404, detail=f"Approval request {req.request_id} not found or not pending")
    return result


@router.post("/reject", response_model=dict[str, Any])
async def reject(req: ApprovalActionRequest):
    svc = _get_service()
    result = await svc.reject(req.request_id, rejected_by=req.rejected_by)
    if not result:
        raise HTTPException(status_code=404, detail=f"Approval request {req.request_id} not found or not pending")
    return result


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@router.get("/health", response_model=dict[str, Any])
async def governance_health():
    svc = _get_service()
    return await svc.health()
