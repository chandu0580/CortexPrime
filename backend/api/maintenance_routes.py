from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_admin, require_user
from backend.database.session import get_session
from backend.services.maintenance_service import maintenance_service

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/operations/maintenance",
    tags=["Enterprise Operations — Maintenance Mode"],
    dependencies=[Depends(require_user)],
)


class MaintenanceEnableRequest(BaseModel):
    banner_message: Optional[str] = None
    allow_existing_missions: bool = True
    block_new_missions: bool = True


class MaintenanceDisableRequest(BaseModel):
    pass


@router.post("/enable", dependencies=[Depends(require_admin)])
async def enable_maintenance(
    body: MaintenanceEnableRequest,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    state = await maintenance_service.enable(
        banner_message=body.banner_message,
        allow_existing_missions=body.allow_existing_missions,
        block_new_missions=body.block_new_missions,
        triggered_by=user_id,
        db=db,
    )
    return state.to_dict()


@router.post("/disable", dependencies=[Depends(require_admin)])
async def disable_maintenance(
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    state = await maintenance_service.disable(triggered_by=user_id, db=db)
    return state.to_dict()


@router.get("/status")
async def get_maintenance_status() -> Dict[str, Any]:
    return await maintenance_service.get_status()


@router.get("/banner")
async def get_maintenance_banner() -> Dict[str, Any]:
    message = maintenance_service.get_banner()
    return {
        "maintenance_active": maintenance_service.is_maintenance_active(),
        "banner_message": message,
    }


@router.get("/events")
async def get_maintenance_events(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    events = await maintenance_service.get_event_history(db, limit=limit)
    return {"events": events, "total": len(events)}
