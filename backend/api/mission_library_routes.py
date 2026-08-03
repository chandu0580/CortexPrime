from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from backend.auth.dependencies import require_user
from backend.mission_library.definitions import get_mission, list_missions
from backend.mission_library.executor import mission_executor

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/mission-library",
    tags=["Mission Library"],
    dependencies=[Depends(require_user)],
)


@router.get("/missions")
async def get_all_missions():
    """List all available enterprise mission definitions."""
    return {
        "missions": list_missions(),
        "total": len(list_missions()),
    }


@router.get("/missions/{mission_id}")
async def get_mission_detail(mission_id: str):
    """Get detailed definition for a specific mission."""
    mission = get_mission(mission_id)
    if mission is None:
        return {"status": "not_found", "mission_id": mission_id}
    return {"status": "found", "mission": mission.to_dict()}


@router.post("/missions/{mission_id}/execute")
async def execute_mission(
    mission_id: str,
    session_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
):
    """Execute an enterprise mission by ID with bound parameters."""
    mission = get_mission(mission_id)
    if mission is None:
        return {"status": "error", "error": f"Unknown mission: {mission_id}"}

    kwargs = params or {}
    result = await mission_executor.execute(
        mission_id=mission_id,
        session_id=session_id,
        workspace_id=workspace_id,
        **kwargs,
    )

    return {
        "status": "completed" if result.status == "completed" else "error",
        "mission_id": mission_id,
        "execution_id": result.execution_id,
        "result": {
            "status": result.status,
            "confidence_score": result.confidence_score,
            "response_length": result.response_length,
            "stages_completed": result.stages_completed,
            "worker_invocations": result.worker_invocations,
            "total_tokens": result.total_tokens,
            "duration_seconds": result.duration_seconds,
            "error": result.error,
        },
    }


@router.get("/running")
async def get_running_missions():
    """List currently executing missions."""
    return {
        "running": mission_executor.list_running(),
        "count": len(mission_executor.list_running()),
    }
