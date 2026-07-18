"""
Enterprise Governance Routes — REST API for policy management,
compliance checks, and audit trail.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.enterprise_governance_service import GovernanceService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["Enterprise Governance"])

governance = GovernanceService()


class CreatePolicyRequest(BaseModel):
    name: str
    description: str = ""
    scope: str = "all"
    rule_type: str = "custom"
    condition: Optional[Dict[str, Any]] = None
    action: str = "warn"
    severity: str = "medium"
    enabled: bool = True
    tags: Optional[List[str]] = None


class UpdatePolicyRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    rule_type: Optional[str] = None
    condition: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    severity: Optional[str] = None
    enabled: Optional[bool] = None
    tags: Optional[List[str]] = None


class ComplianceCheckRequest(BaseModel):
    target_type: str
    target_id: str
    context: Optional[Dict[str, Any]] = None


class AuditRecordRequest(BaseModel):
    action: str
    actor: str
    target_type: str
    target_id: str
    details: Optional[Dict[str, Any]] = None
    result: str = "success"


@router.get("/dashboard")
async def governance_dashboard():
    return await governance.get_dashboard_stats()


@router.post("/policies")
async def create_policy(body: CreatePolicyRequest):
    return await governance.create_policy(**body.model_dump())


@router.get("/policies")
async def list_policies(scope: str = "", severity: str = "", enabled: Optional[bool] = None):
    return {"policies": await governance.list_policies(scope, severity, enabled)}


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str):
    policy = await governance.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, body: UpdatePolicyRequest):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    policy = await governance.update_policy(policy_id, updates)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str):
    if not await governance.delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"ok": True}


@router.post("/compliance/check")
async def run_compliance_check(body: ComplianceCheckRequest):
    return await governance.run_compliance_check(body.target_type, body.target_id, body.context)


@router.get("/compliance/history")
async def compliance_history(target_type: str = "", target_id: str = "", limit: int = 50):
    return {"checks": await governance.get_compliance_history(target_type, target_id, limit)}


@router.post("/audit")
async def record_audit(body: AuditRecordRequest):
    return await governance.record_audit(**body.model_dump())


@router.get("/audit")
async def get_audit_log(target_type: str = "", actor: str = "", action: str = "", limit: int = 100):
    return {"entries": await governance.get_audit_log(target_type, actor, action, limit)}
