"""
Enterprise Mission REST API — launch, list, and monitor template-driven autonomous workflows.

Endpoints
---------
GET  /api/enterprise/missions/templates         — List all mission templates
GET  /api/enterprise/missions/templates/{id}    — Get template detail
POST /api/enterprise/missions/launch            — Launch a template mission
GET  /api/enterprise/missions/active            — List active missions
GET  /api/enterprise/missions/history           — List all mission history
GET  /api/enterprise/missions/{id}              — Get mission status
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from backend.api.legacy_execution_boundary import guard_legacy_execution
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.services.enterprise_mission_orchestrator import enterprise_orchestrator
from backend.services.mission_templates import (
    get_template,
    list_templates,
    template_to_dict,
)

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/enterprise/missions",
    tags=["Enterprise Missions"],
    dependencies=[Depends(require_user)],
)


class LaunchRequest(BaseModel):
    template_id: str
    params: Dict[str, Any] = {}
    launched_by: str = "api"


# =====================================================================
# Templates
# =====================================================================

@router.get("/templates")
async def list_mission_templates() -> Dict[str, Any]:
    """Return all available enterprise mission templates."""
    templates = list_templates()
    return {
        "templates": [template_to_dict(t) for t in templates],
        "total": len(templates),
    }


@router.get("/templates/{template_id}")
async def get_mission_template(template_id: str) -> Dict[str, Any]:
    """Return a single template with its full schema."""
    t = get_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return {"template": template_to_dict(t)}


# =====================================================================
# Launch & status
# =====================================================================

@router.post(
    "/launch",
    dependencies=[Depends(guard_legacy_execution(
        "POST /api/enterprise/missions/launch"))],
)
async def launch_mission(body: LaunchRequest) -> Dict[str, Any]:
    """Launch an enterprise mission from a template."""
    t = get_template(body.template_id)
    if t is None:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{body.template_id}' not found. "
                   f"Available: {[tt.id for tt in list_templates()]}",
        )

    try:
        result = await enterprise_orchestrator.launch(
            template=t,
            params=body.params,
            launched_by=body.launched_by,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/active")
async def list_active_missions() -> Dict[str, Any]:
    """List all currently active enterprise missions."""
    active = enterprise_orchestrator.list_active()
    return {"missions": active, "total": len(active)}


@router.get("/history")
async def list_mission_history() -> Dict[str, Any]:
    """List all enterprise missions (completed and failed)."""
    all_missions = enterprise_orchestrator.list_all()
    return {"missions": all_missions, "total": len(all_missions)}


@router.get("/{mission_id}")
async def get_mission_status(mission_id: str) -> Dict[str, Any]:
    """Get the status of a specific enterprise mission."""
    mission = enterprise_orchestrator.get_mission(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
    return {"mission": mission}
