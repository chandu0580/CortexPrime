"""
Mission Execution Routes
========================
POST /execute  — fire-and-forget mission with streaming via WebSocket
POST /execute/sync — wait for completion (for testing)
GET  /status/{execution_id} — check mission status
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_user
from backend.services.mission_runtime import mission_runtime

log = logging.getLogger(__name__)
router = APIRouter()


# =========================================================
# REQUEST / RESPONSE MODELS
# =========================================================

class ExecuteRequest(BaseModel):
    objective:    str = Field(..., min_length=1, max_length=4000)
    session_id:   str | None = Field(default=None, max_length=128)
    workspace_id: str | None = Field(default=None, max_length=128)


class ExecuteResponse(BaseModel):
    accepted:     bool
    execution_id: str | None = None
    message:      str = ""


# =========================================================
# POST /execute  (async — returns immediately, streams via WS)
# =========================================================

@router.post("/execute", response_model=ExecuteResponse)
async def execute_mission(
    request:          ExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user:     dict = Depends(require_user),
):
    """
    Accept a mission objective and run the full pipeline in the background.

    The client should already be connected to ``/ws``.  Token chunks will
    arrive as ``stream_chunk`` messages; ``stream_completed`` signals the end.
    """
    objective = request.objective.strip()
    if not objective:
        return ExecuteResponse(accepted=False, message="Objective cannot be empty")

    # Fire and forget — execution streams tokens via WebSocket
    background_tasks.add_task(_run_mission_bg, objective, request.session_id, request.workspace_id)

    return ExecuteResponse(
        accepted = True,
        message  = "Mission accepted — streaming via WebSocket",
    )


async def _run_mission_bg(
    objective:    str,
    session_id:   str | None = None,
    workspace_id: str | None = None,
) -> None:
    try:
        await mission_runtime.execute_mission(
            objective,
            session_id=session_id,
            workspace_id=workspace_id,
        )
    except Exception as exc:
        log.error("Background mission failed: %s", exc)


# =========================================================
# POST /execute/sync  (waits for completion — dev/test)
# =========================================================

@router.post("/execute/sync")
async def execute_mission_sync(
    request:      ExecuteRequest,
    current_user: dict = Depends(require_user),
):
    """
    Run the mission and wait for full completion before responding.
    Tokens still stream via WebSocket during execution.
    """
    result = await mission_runtime.execute_mission(
        request.objective.strip(),
        session_id=request.session_id,
        workspace_id=request.workspace_id,
    )
    return result


# =========================================================
# POST /orchestrate  (alias — same as /execute)
# Used by the existing frontend CenterPanel fetch call
# =========================================================

@router.post("/orchestrate")
async def orchestrate_alias(
    request:          ExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user:     dict = Depends(require_user),
):
    """
    Alias for /execute — keeps the existing frontend API call working.
    Runs in background so the frontend receives HTTP 200 immediately while
    tokens stream via WebSocket.
    """
    objective = request.objective.strip()
    if not objective:
        return {"status": "error", "message": "Objective cannot be empty"}

    background_tasks.add_task(_run_mission_bg, objective, request.session_id, request.workspace_id)

    return {
        "status":  "accepted",
        "message": "Mission started — streaming via WebSocket",
        "result":  "",
    }
