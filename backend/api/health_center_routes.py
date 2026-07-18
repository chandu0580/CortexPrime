from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.session import get_session
from backend.services.health_center_service import health_center_service

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/operations/health-center",
    tags=["Enterprise Operations — Health Center"],
    dependencies=[Depends(require_user)],
)


@router.get("")
async def get_health_dashboard() -> Dict[str, Any]:
    return await health_center_service.get_health_dashboard()


@router.get("/snapshot")
async def get_health_snapshot(
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    return await health_center_service.save_snapshot(db, triggered_by="api")


@router.get("/history")
async def get_health_history(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    history = await health_center_service.get_snapshot_history(db, limit=limit)
    return {"snapshots": history, "total": len(history)}


@router.get("/status")
async def get_cached_status() -> Dict[str, Any]:
    cached = health_center_service.get_cached_status()
    if cached:
        return cached
    return await health_center_service.get_health_dashboard()
