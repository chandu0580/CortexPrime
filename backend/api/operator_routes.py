"""
Operator Routes  (CortexPrime Computer Agent V2)
=================================================
REST API for the /operator frontend page and autonomous computer agent.

Endpoints
---------
GET  /operator/health            — service health check
GET  /operator/monitors          — enumerate connected monitors
GET  /operator/screen/current    — latest cached snapshot (no re-capture)
POST /operator/screen/capture    — trigger a fresh screen capture
GET  /operator/active-missions   — currently running autonomous missions
POST /operator/execute           — submit a new autonomous mission
GET  /operator/missions/{id}     — mission status by execution_id
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependencies import require_admin, require_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/operator", tags=["Operator"])

# Apply to every protected route individually so /health stays open.
_SECURE = [Depends(require_user)]
_ADMIN = [Depends(require_admin)]


# =========================================================
# REQUEST / RESPONSE MODELS
# =========================================================

class ExecuteMissionRequest(BaseModel):
    goal:           str
    execution_id:   Optional[str] = None
    session_id:     Optional[str] = None
    success_text:   Optional[str] = None
    max_iterations: int           = 30
    use_vision:     bool          = True


class CaptureRequest(BaseModel):
    monitor:   int  = 0
    run_ocr:   bool = True
    detect_ui: bool = True


# =========================================================
# LAZY AGENT ACCESS
# =========================================================

def _agent():
    from backend.computer.computer_agent_v2 import computer_agent_v2
    return computer_agent_v2


def _observer():
    from backend.computer.screen_observer import screen_observer
    return screen_observer


# =========================================================
# ROUTES
# =========================================================

@router.get("/health")
async def operator_health() -> Dict[str, Any]:
    """Operator system health and capability probe."""
    caps = {
        "screen_capture": False,
        "ocr":            False,
        "vision_llm":     False,
        "computer_input": False,
    }

    try:
        import mss  # noqa: F401
        caps["screen_capture"] = True
    except ImportError:
        pass

    try:
        import pytesseract  # noqa: F401
        caps["ocr"] = True
    except ImportError:
        pass

    try:
        import pyautogui  # noqa: F401
        caps["computer_input"] = True
    except ImportError:
        pass

    try:
        from backend.providers.openai_provider import openai_provider
        if openai_provider.client:
            caps["vision_llm"] = True
    except Exception:
        pass

    active = _agent().list_active()
    return {
        "status":           "ok",
        "capabilities":     caps,
        "active_missions":  len(active),
    }


@router.get("/monitors", dependencies=_SECURE)
async def list_monitors() -> Dict[str, Any]:
    """List all available monitors/displays."""
    monitors = await _observer().list_monitors()
    return {"monitors": monitors, "count": len(monitors)}


@router.get("/screen/current", dependencies=_SECURE)
async def get_current_snapshot() -> Dict[str, Any]:
    """Return the most recently captured snapshot without re-capturing."""
    snap = _observer().last_snapshot
    if not snap:
        raise HTTPException(status_code=404, detail="No snapshot captured yet. Call /operator/screen/capture first.")
    return snap.as_dict()


@router.post("/screen/capture", dependencies=_SECURE)
async def capture_screen(req: CaptureRequest) -> Dict[str, Any]:
    """Trigger a fresh screen capture and return the snapshot."""
    try:
        result = await _agent().capture_screen(
            monitor   = req.monitor,
            run_ocr   = req.run_ocr,
            detect_ui = req.detect_ui,
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/active-missions", dependencies=_SECURE)
async def list_active_missions() -> Dict[str, Any]:
    """Return all currently executing autonomous missions."""
    active = _agent().list_active()
    return {"missions": active, "count": len(active)}


@router.post("/execute", dependencies=_ADMIN)
async def execute_mission(req: ExecuteMissionRequest) -> Dict[str, Any]:
    """
    Submit a new autonomous mission.
    Runs synchronously (awaited) — returns result when complete.
    For long missions consider pairing with WebSocket updates.
    """
    if not req.goal.strip():
        raise HTTPException(status_code=422, detail="goal must not be empty")

    payload: Dict[str, Any] = req.model_dump()
    result = await _agent().execute_autonomous_mission(payload)

    if not result.get("success") and result.get("status") == "failed":
        # Still return 200 with error details so the frontend can show the result
        return result

    return result


@router.get("/missions/{execution_id}", dependencies=_SECURE)
async def get_mission_status(execution_id: str) -> Dict[str, Any]:
    """
    Check if a mission is active.
    (Full history is in memory/event stream; this just checks live state.)
    """
    active = {m.get("execution_id"): m for m in _agent().list_active()}
    if execution_id in active:
        return {"execution_id": execution_id, "status": "running", **active[execution_id]}
    return {
        "execution_id": execution_id,
        "status":       "not_active",
        "detail":       "Mission is no longer running — check audit log or memory for results.",
    }
