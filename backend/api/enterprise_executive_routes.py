"""
Enterprise Engineering Executive Runtime Routes — REST API for executive supervision.

Endpoints:
  POST   /api/engineering/executive/mission          — Create mission
  POST   /api/engineering/executive/mission/{id}/plan  — Plan mission
  POST   /api/engineering/executive/mission/{id}/run   — Run mission
  GET    /api/engineering/executive/missions           — List missions
  GET    /api/engineering/executive/missions/active    — List active
  GET    /api/engineering/executive/mission/{id}       — Get mission detail
  POST   /api/engineering/executive/mission/{id}/pause     — Pause
  POST   /api/engineering/executive/mission/{id}/resume    — Resume
  POST   /api/engineering/executive/mission/{id}/escalate  — Escalate
  POST   /api/engineering/executive/mission/{id}/rollback  — Rollback
  POST   /api/engineering/executive/mission/{id}/retry     — Retry
  POST   /api/engineering/executive/mission/{id}/abort     — Abort
  POST   /api/engineering/executive/mission/{id}/replan    — Re-plan
  GET    /api/engineering/executive/dashboard              — Dashboard
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_executive_runtime import enterprise_executive_runtime

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engineering/executive", tags=["Enterprise Engineering Executive Runtime"])


class CreateMissionRequest(BaseModel):
    source: str
    source_event: str = "push"
    repository: str = ""
    branch: str = "main"
    commit_sha: str = ""
    service: str = ""
    environment: str = "production"
    execution_id: str = ""
    change_categories: Optional[List[str]] = None
    changed_services: Optional[List[str]] = None


class RunMissionRequest(BaseModel):
    approval_granted: bool = False
    delivery_params: Optional[Dict[str, Any]] = None


class EscalateRequest(BaseModel):
    reason: str = ""


class GenericReasonRequest(BaseModel):
    reason: str = ""


@router.post("/mission")
async def create_mission(req: CreateMissionRequest) -> Dict[str, Any]:
    """Create a new engineering mission."""
    try:
        return await enterprise_executive_runtime.create_mission(
            source=req.source,
            source_event=req.source_event,
            repository=req.repository,
            branch=req.branch,
            commit_sha=req.commit_sha,
            service=req.service,
            environment=req.environment,
            execution_id=req.execution_id,
            change_categories=req.change_categories,
            changed_services=req.changed_services,
        )
    except Exception as exc:
        log.error("Create mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/plan")
async def plan_mission(mission_id: str) -> Dict[str, Any]:
    """Plan mission — gather context, make decision, run prediction."""
    try:
        return await enterprise_executive_runtime.plan_mission(mission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Plan mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/run")
async def run_mission(mission_id: str, req: RunMissionRequest) -> Dict[str, Any]:
    """Run mission through deployment, monitoring, verification, learning."""
    try:
        return await enterprise_executive_runtime.run_mission(
            mission_id, approval_granted=req.approval_granted, delivery_params=req.delivery_params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Run mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions")
async def list_missions(
    status: str = Query(default=""),
    limit: int = Query(default=50),
) -> List[Dict[str, Any]]:
    """List all missions, optionally filtered by status."""
    try:
        return await enterprise_executive_runtime.list_missions(status=status, limit=limit)
    except Exception as exc:
        log.error("List missions failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions/active")
async def list_active_missions() -> List[Dict[str, Any]]:
    """List active missions."""
    try:
        return await enterprise_executive_runtime.list_active_missions()
    except Exception as exc:
        log.error("List active missions failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/mission/{mission_id}")
async def get_mission(mission_id: str) -> Dict[str, Any]:
    """Get mission detail by ID."""
    try:
        result = await enterprise_executive_runtime.get_mission(mission_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Get mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/pause")
async def pause_mission(mission_id: str) -> Dict[str, Any]:
    """Pause a running mission."""
    try:
        return await enterprise_executive_runtime.pause_mission(mission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Pause mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/resume")
async def resume_mission(mission_id: str) -> Dict[str, Any]:
    """Resume a paused mission."""
    try:
        return await enterprise_executive_runtime.resume_mission(mission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Resume mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/escalate")
async def escalate_mission(mission_id: str, req: EscalateRequest) -> Dict[str, Any]:
    """Escalate mission — require human intervention."""
    try:
        return await enterprise_executive_runtime.escalate_mission(mission_id, reason=req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Escalate mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/rollback")
async def rollback_mission(mission_id: str, req: GenericReasonRequest) -> Dict[str, Any]:
    """Rollback a mission."""
    try:
        return await enterprise_executive_runtime.rollback_mission(mission_id, reason=req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Rollback mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/retry")
async def retry_mission(mission_id: str) -> Dict[str, Any]:
    """Retry mission from current phase."""
    try:
        return await enterprise_executive_runtime.retry_mission(mission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Retry mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/abort")
async def abort_mission(mission_id: str, req: GenericReasonRequest) -> Dict[str, Any]:
    """Abort and cancel a mission."""
    try:
        return await enterprise_executive_runtime.abort_mission(mission_id, reason=req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Abort mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mission/{mission_id}/replan")
async def replan_mission(mission_id: str) -> Dict[str, Any]:
    """Re-plan a failed or cancelled mission."""
    try:
        return await enterprise_executive_runtime.replan_mission(mission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        log.error("Replan mission failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dashboard")
async def get_executive_dashboard() -> Dict[str, Any]:
    """Get executive dashboard with active missions, health, decisions."""
    try:
        return await enterprise_executive_runtime.get_dashboard()
    except Exception as exc:
        log.error("Dashboard failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
