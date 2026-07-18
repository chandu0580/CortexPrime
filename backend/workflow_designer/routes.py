from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.workflow_designer.engine import workflow_engine

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/workflows", tags=["workflows"])


class CreateWorkflowRequest(BaseModel):
    name: str
    org_id: str
    description: str = ""
    tags: List[str] = []


class AddNodeRequest(BaseModel):
    node_type: str
    label: str
    config: Dict[str, Any] = {}
    position: Dict[str, float] = {"x": 0.0, "y": 0.0}


class AddEdgeRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    label: Optional[str] = None
    condition: Optional[str] = None


@router.post("")
async def create_workflow(
    req: CreateWorkflowRequest,
    user: Dict = Depends(require_user),
):
    workflow = await workflow_engine.create_workflow(
        name=req.name,
        org_id=req.org_id,
        description=req.description,
        tags=req.tags,
    )
    return {"workflow": workflow.to_dict()}


@router.get("")
async def list_workflows(
    org_id: Optional[str] = None,
    user: Dict = Depends(require_user),
):
    workflows = await workflow_engine.list_workflows(org_id=org_id)
    return {"workflows": [w.to_dict() for w in workflows]}


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    user: Dict = Depends(require_user),
):
    workflow = await workflow_engine.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"workflow": workflow.to_dict()}


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    user: Dict = Depends(require_user),
):
    ok = await workflow_engine.delete_workflow(workflow_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"status": "deleted"}


@router.post("/{workflow_id}/nodes")
async def add_node(
    workflow_id: str,
    req: AddNodeRequest,
    user: Dict = Depends(require_user),
):
    node = await workflow_engine.add_node(
        workflow_id=workflow_id,
        node_type=req.node_type,
        label=req.label,
        config=req.config,
        position=req.position,
    )
    if not node:
        raise HTTPException(status_code=404, detail="Workflow not found or invalid node type")
    return {"node": node}


@router.post("/{workflow_id}/edges")
async def add_edge(
    workflow_id: str,
    req: AddEdgeRequest,
    user: Dict = Depends(require_user),
):
    edge = await workflow_engine.add_edge(
        workflow_id=workflow_id,
        source_node_id=req.source_node_id,
        target_node_id=req.target_node_id,
        label=req.label,
        condition=req.condition,
    )
    if not edge:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"edge": edge}


@router.get("/{workflow_id}/compile")
async def compile_workflow(
    workflow_id: str,
    user: Dict = Depends(require_user),
):
    compiled = await workflow_engine.compile_workflow(workflow_id)
    if not compiled:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"mission_definition": compiled}


@router.get("/health")
async def workflow_health():
    return await workflow_engine.health()
