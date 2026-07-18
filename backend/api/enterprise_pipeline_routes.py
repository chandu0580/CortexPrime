"""
Enterprise Pipeline Routes — REST API for the AI Pipeline Orchestrator.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from backend.services.enterprise_pipeline_orchestrator import (
    pipeline_orchestrator,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])


# ── CRUD ────────────────────────────────────────────────────────────────────


@router.get("/pipelines")
async def list_pipelines(status: str = "", limit: int = 50):
    return await pipeline_orchestrator.list_pipelines(status=status, limit=limit)


@router.post("/pipelines")
async def create_pipeline(
    name: str = "",
    description: str = "",
    mission_id: str = "",
    repo_url: str = "",
    workspace_id: str = "",
    sandbox_id: str = "",
    trigger_policy_id: str = "",
):
    return await pipeline_orchestrator.create_pipeline(
        name=name,
        description=description,
        mission_id=mission_id,
        repo_url=repo_url,
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        trigger_policy_id=trigger_policy_id,
    )


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    pipeline = await pipeline_orchestrator.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
    return pipeline


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    ok = await pipeline_orchestrator.delete_pipeline(pipeline_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
    return {"status": "deleted", "pipeline_id": pipeline_id}


# ── Execution ────────────────────────────────────────────────────────────────


@router.post("/pipelines/{pipeline_id}/start")
async def start_pipeline(pipeline_id: str):
    try:
        result = await pipeline_orchestrator.start_pipeline(pipeline_id)
        return {"status": "started", "pipeline": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines/{pipeline_id}/pause")
async def pause_pipeline(pipeline_id: str):
    result = await pipeline_orchestrator.pause_pipeline(pipeline_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
    return {"status": "paused", "pipeline": result}


@router.post("/pipelines/{pipeline_id}/resume")
async def resume_pipeline(pipeline_id: str):
    try:
        result = await pipeline_orchestrator.resume_pipeline(pipeline_id)
        return {"status": "resumed", "pipeline": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines/{pipeline_id}/cancel")
async def cancel_pipeline(pipeline_id: str):
    result = await pipeline_orchestrator.cancel_pipeline(pipeline_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
    return {"status": "cancelled", "pipeline": result}


# ── Patch-to-PR Auto-Workflow ────────────────────────────────────────────────


@router.post("/patch-to-pr")
async def patch_to_pr(
    repo_url: str,
    plan_id: str,
    candidate_id: str,
    branch_name: str = "",
    mission_id: str = "",
    commit_description: str = "",
    pr_title: str = "",
    reviewers: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
):
    try:
        result = await pipeline_orchestrator.patch_to_pr(
            repo_url=repo_url,
            plan_id=plan_id,
            candidate_id=candidate_id,
            branch_name=branch_name,
            mission_id=mission_id,
            commit_description=commit_description,
            pr_title=pr_title,
            reviewers=reviewers,
            labels=labels,
        )
        return {"status": "pr_created", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/dashboard")
async def pipeline_dashboard():
    return await pipeline_orchestrator.get_dashboard_stats()
