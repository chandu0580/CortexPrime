"""
Autonomous Trigger Routes — REST API for the Autonomous Trigger Runtime.

Endpoints:
  GET    /api/triggers                    — List trigger policies
  GET    /api/triggers/history            — List trigger history
  POST   /api/triggers/policies           — Create a trigger policy
  PUT    /api/triggers/policies/{id}      — Update a trigger policy
  DELETE /api/triggers/policies/{id}      — Delete a trigger policy
  POST   /api/triggers/simulate           — Simulate a trigger event
  GET    /api/triggers/stats              — Get trigger dashboard stats
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.services.autonomous_trigger_runtime import (
    TRIGGER_SOURCES,
    TriggerPolicy,
    autonomous_trigger_runtime,
)

log = logging.getLogger(__name__)

# Phase 11.1: a trigger policy turns events into missions. Writing one is a
# privileged act and reading them reveals what the deployment reacts to, so
# every route needs a verified identity. Mission generation itself remains
# behind the legacy execution guard (enterprise_mission_orchestrator.launch).
router = APIRouter(
    prefix="/api/triggers",
    tags=["Autonomous Triggers"],
    dependencies=[Depends(require_user)],
)


# ── Schemas ─────────────────────────────────────────────────────────────────

class PolicyCreateRequest(BaseModel):
    name: str
    description: str = ""
    source: str = ""
    event_pattern: str = ""
    conditions: Optional[Dict[str, Any]] = None
    mission_template: str = "software_release"
    requires_approval: bool = False
    cooldown_seconds: int = 300
    priority: str = "medium"
    enabled: bool = True
    tags: Optional[List[str]] = None


class PolicyUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    event_pattern: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    mission_template: Optional[str] = None
    requires_approval: Optional[bool] = None
    cooldown_seconds: Optional[int] = None
    priority: Optional[str] = None
    enabled: Optional[bool] = None
    tags: Optional[List[str]] = None


class SimulateRequest(BaseModel):
    source: str = "github"
    event_type: str = "push"
    payload: Dict[str, Any] = {}


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("")
async def list_policies(
    source: str = Query("", description="Filter by trigger source"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
):
    """List all trigger policies."""
    return {
        "policies": await autonomous_trigger_runtime.list_policies(source, enabled),
    }


@router.get("/sources")
async def list_sources():
    """List available trigger sources."""
    return {"sources": TRIGGER_SOURCES}


@router.get("/history")
async def get_history(
    source: str = Query("", description="Filter by source"),
    status: str = Query("", description="Filter by status"),
    limit: int = Query(100, description="Max results"),
):
    """Get trigger event history."""
    return {
        "history": await autonomous_trigger_runtime.get_history(source, status, limit),
    }


@router.get("/stats")
async def get_stats():
    """Get trigger dashboard statistics."""
    return await autonomous_trigger_runtime.get_dashboard_stats()


@router.post("/policies")
async def create_policy(req: PolicyCreateRequest):
    """Create a new trigger policy."""
    policy = TriggerPolicy(
        name=req.name,
        description=req.description,
        source=req.source,
        event_pattern=req.event_pattern,
        conditions=req.conditions or {},
        mission_template=req.mission_template,
        requires_approval=req.requires_approval,
        cooldown_seconds=req.cooldown_seconds,
        priority=req.priority,
        enabled=req.enabled,
        tags=req.tags or [],
    )
    try:
        created = await autonomous_trigger_runtime.create_policy(policy)
        return created.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, req: PolicyUpdateRequest):
    """Update a trigger policy."""
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items() if v is not None}
    policy = await autonomous_trigger_runtime.update_policy(policy_id, updates)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")
    return policy.to_dict()


@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str):
    """Delete a trigger policy."""
    deleted = await autonomous_trigger_runtime.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")
    return {"deleted": True, "policy_id": policy_id}


@router.post("/simulate")
async def simulate_trigger(req: SimulateRequest):
    """Simulate a trigger event and see which policies would match."""
    result = await autonomous_trigger_runtime.simulate(req.source, req.event_type, req.payload)
    return result
