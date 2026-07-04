"""
Computer Agent Routes
=====================
POST /computer/execute-workflow  — execute a multi-step desktop/browser workflow
GET  /computer/status            — active mission count + health
GET  /computer/tasks             — active + completed task history
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/computer", tags=["Computer Agent"], dependencies=[Depends(require_user)])


# =========================================================
# REQUEST / RESPONSE MODELS
# =========================================================

class WorkflowStep(BaseModel):
    action:   str
    url:      Optional[str]         = None
    query:    Optional[str]         = None
    selector: Optional[str]         = None
    text:     Optional[str]         = None
    target:   Optional[str]         = None
    keys:     Optional[List[str]]   = None
    seconds:  Optional[float]       = None


class WorkflowRequest(BaseModel):
    mission_name: str                   = Field(default="Unnamed Mission", max_length=256)
    steps:        List[WorkflowStep]    = Field(default_factory=list)


# =========================================================
# LAZY IMPORT — computer_agent depends on pyautogui/mss which
# may not be installed in every environment
# =========================================================

def _get_agent():
    from backend.computer.computer_agent import computer_agent  # type: ignore
    return computer_agent


# =========================================================
# POST /computer/execute-workflow
# =========================================================

@router.post("/execute-workflow")
async def execute_workflow(request: WorkflowRequest) -> Dict[str, Any]:
    """
    Submit a multi-step computer-use workflow to the Computer Agent.

    Each step must specify an ``action`` (open_website, google_search,
    click, type, hotkey, wait, analyze_screen).
    """
    try:
        agent = _get_agent()
        result = await agent.execute_mission(request.model_dump())
        return result
    except Exception as exc:
        log.error("execute-workflow error: %s", exc)
        return {
            "success":  False,
            "error":    str(exc),
            "status":   "failed",
        }


# =========================================================
# GET /computer/status
# =========================================================

@router.get("/status")
async def get_computer_status() -> Dict[str, Any]:
    """
    Return Computer Agent health and active mission count.
    """
    try:
        agent = _get_agent()
        return {
            "status":             "online",
            "active_missions":    len(agent.active_missions),
            "active_mission_ids": list(agent.active_missions.keys()),
        }
    except Exception as exc:
        log.warning("computer status unavailable: %s", exc)
        return {
            "status":          "degraded",
            "active_missions": 0,
            "detail":          str(exc),
        }


# =========================================================
# GET /computer/tasks
# =========================================================

@router.get("/tasks")
async def get_computer_tasks() -> Dict[str, Any]:
    """
    Return the full list of active missions and recent completed tasks.
    """
    try:
        agent = _get_agent()
        return {
            "active_tasks":    list(agent.active_missions.values()),
            "completed_tasks": agent.mission_history[-50:],
            "total_completed": len(agent.mission_history),
        }
    except Exception as exc:
        log.warning("computer tasks unavailable: %s", exc)
        return {
            "active_tasks":    [],
            "completed_tasks": [],
            "total_completed": 0,
            "detail":          str(exc),
        }
