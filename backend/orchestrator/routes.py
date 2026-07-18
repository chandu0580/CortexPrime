from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from backend.orchestrator.service import AutonomousMissionOrchestrator, orchestrator_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestrator", tags=["Orchestrator"])


def _get_service() -> AutonomousMissionOrchestrator:
    return orchestrator_service


@router.post("/start")
async def start_mission(
    goal: str,
    mission_id: Optional[str] = None,
    tenant_id: str = "",
    user_id: str = "",
    trace_id: str = "",
    correlation_id: str = "",
    permissions: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    svc = _get_service()
    mission = svc.start_mission(
        goal=goal, mission_id=mission_id,
        tenant_id=tenant_id, user_id=user_id,
        trace_id=trace_id, correlation_id=correlation_id,
        permissions=permissions, metadata=metadata,
    )
    result = await svc.run_mission(mission.mission_id)
    if result:
        summary = svc.get_mission_summary(result.mission_id)
        return summary or {
            "mission_id": result.mission_id,
            "status": result.status.value,
            "current_state": result.current_state.value,
            "error": result.error,
        }
    return {"status": "error", "detail": "Mission execution failed"}


@router.post("/pause")
async def pause_mission(mission_id: str):
    svc = _get_service()
    success = await svc.pause_mission(mission_id)
    return {"success": success, "mission_id": mission_id, "paused": success}


@router.post("/resume")
async def resume_mission(mission_id: str):
    svc = _get_service()
    success = await svc.resume_mission(mission_id)
    return {"success": success, "mission_id": mission_id, "resumed": success}


@router.post("/cancel")
async def cancel_mission(mission_id: str):
    svc = _get_service()
    success = await svc.cancel_mission(mission_id)
    return {"success": success, "mission_id": mission_id, "cancelled": success}


@router.get("/{mission_id}")
async def get_mission(mission_id: str, include_reasoning: bool = False):
    svc = _get_service()
    summary = svc.get_mission_summary(mission_id)
    if not summary:
        return {"status": "not_found", "mission_id": mission_id}
    summary["timeline"] = svc.get_events(mission_id)
    summary["artifacts"] = svc.get_artifacts(mission_id)
    if include_reasoning:
        try:
            from backend.orchestrator.runtime_resolver import get_cognitive_memory_service
            mem = get_cognitive_memory_service()
            if mem:
                ctx = mem.get_context(mission_id)
                if ctx:
                    steps = getattr(ctx, "reasoning_steps", None) or ctx.get("reasoning_steps", [])
                    summary["reasoning_trace"] = [
                        {"step": i, "description": s.get("description", ""), "decision": s.get("decision", ""),
                         "confidence": s.get("confidence", 0.0), "critical": s.get("critical", False)}
                        for i, s in enumerate(steps)
                    ]
                    summary["memory_context"] = {
                        "current_phase": getattr(ctx, "current_phase", "") or ctx.get("working_memory", {}).get("current_phase", ""),
                        "completed_steps": getattr(ctx, "completed_steps", []) or ctx.get("working_memory", {}).get("completed_steps", []),
                    }
        except Exception as exc:
            summary["reasoning_trace"] = []
            summary["reasoning_error"] = str(exc)
    return summary


@router.get("/{mission_id}/timeline")
async def get_mission_timeline(mission_id: str):
    svc = _get_service()
    events = svc.get_events(mission_id)
    return {"mission_id": mission_id, "events": events, "count": len(events)}


@router.post("/restart")
async def restart_mission(mission_id: str):
    svc = _get_service()
    result = await svc.restart_from_checkpoint(mission_id)
    if result:
        return {
            "mission_id": result.mission_id,
            "status": result.status.value,
            "current_state": result.current_state.value,
        }
    return {"status": "not_found", "mission_id": mission_id}


@router.get("/")
async def list_missions(status: Optional[str] = None, limit: int = 50):
    svc = _get_service()
    missions = svc.list_missions(status=status, limit=limit)
    return {
        "missions": [
            {
                "mission_id": m.mission_id,
                "goal": m.goal,
                "current_state": m.current_state.value,
                "status": m.status.value,
                "created_at": m.created_at,
            }
            for m in missions
        ],
        "total": len(missions),
    }


@router.get("/runtime-status")
async def runtime_status():
    from backend.orchestrator.runtime_resolver import resolve_runtime_status
    return {"runtimes": resolve_runtime_status()}


@router.get("/health")
async def orchestrator_health():
    svc = _get_service()
    return svc.health()
