from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.fleet.manager import fleet_manager
from backend.fleet.models import DeploymentStrategy

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/fleets", tags=["fleets"])


class CreateFleetRequest(BaseModel):
    name: str
    org_id: str
    config: Dict[str, Any] = {}


class RegisterAgentRequest(BaseModel):
    agent_type: str
    agent_name: str
    version: str = "1.0.0"
    region: str = "default"
    labels: Dict[str, str] = {}


class CreateDeploymentRequest(BaseModel):
    target_environment: str
    strategy: str = "rolling"
    config: Dict[str, Any] = {}


class HeartbeatRequest(BaseModel):
    agent_id: str


@router.post("")
async def create_fleet(
    req: CreateFleetRequest,
    user: Dict = Depends(require_user),
):
    fleet = await fleet_manager.create_fleet(
        name=req.name,
        org_id=req.org_id,
        config=req.config,
    )
    return {"fleet": fleet.to_dict()}


@router.get("")
async def list_fleets(
    org_id: Optional[str] = None,
    user: Dict = Depends(require_user),
):
    fleets = await fleet_manager.list_fleets(org_id=org_id)
    return {"fleets": [f.to_dict() for f in fleets]}


@router.get("/{fleet_id}")
async def get_fleet(
    fleet_id: str,
    user: Dict = Depends(require_user),
):
    fleet = await fleet_manager.get_fleet(fleet_id)
    if not fleet:
        raise HTTPException(status_code=404, detail="Fleet not found")
    return {"fleet": fleet.to_dict()}


@router.delete("/{fleet_id}")
async def delete_fleet(
    fleet_id: str,
    user: Dict = Depends(require_user),
):
    ok = await fleet_manager.delete_fleet(fleet_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Fleet not found")
    return {"status": "deleted"}


@router.post("/{fleet_id}/agents")
async def register_agent(
    fleet_id: str,
    req: RegisterAgentRequest,
    user: Dict = Depends(require_user),
):
    agent = await fleet_manager.register_agent(
        fleet_id=fleet_id,
        agent_type=req.agent_type,
        agent_name=req.agent_name,
        version=req.version,
        region=req.region,
        labels=req.labels,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Fleet not found")
    return {"agent": agent.to_dict()}


@router.get("/{fleet_id}/agents")
async def list_agents(
    fleet_id: str,
    user: Dict = Depends(require_user),
):
    agents = await fleet_manager.list_agents(fleet_id)
    return {"agents": [a.to_dict() for a in agents]}


@router.post("/{fleet_id}/heartbeat")
async def report_heartbeat(
    fleet_id: str,
    req: HeartbeatRequest,
    user: Dict = Depends(require_user),
):
    ok = await fleet_manager.report_heartbeat(fleet_id, req.agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "ok"}


@router.post("/{fleet_id}/deployments")
async def create_deployment(
    fleet_id: str,
    req: CreateDeploymentRequest,
    user: Dict = Depends(require_user),
):
    try:
        strategy = DeploymentStrategy(req.strategy)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {req.strategy}")

    deployment = await fleet_manager.create_deployment(
        fleet_id=fleet_id,
        target_environment=req.target_environment,
        strategy=strategy,
        config=req.config,
    )
    if not deployment:
        raise HTTPException(status_code=404, detail="Fleet not found")
    return {"deployment": deployment.to_dict()}


@router.get("/{fleet_id}/deployments")
async def list_deployments(
    fleet_id: str,
    user: Dict = Depends(require_user),
):
    deployments = await fleet_manager.list_deployments(fleet_id)
    return {"deployments": [d.to_dict() for d in deployments]}


@router.get("/{fleet_id}/health")
async def get_fleet_health(
    fleet_id: str,
    user: Dict = Depends(require_user),
):
    health = await fleet_manager.get_fleet_health(fleet_id)
    return {"health": health}


@router.get("/health")
async def fleet_health():
    return await fleet_manager.health()
