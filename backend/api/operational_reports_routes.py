from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.session import get_session
from backend.services.operational_reports_service import operational_reports_service

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/operations/reports",
    tags=["Enterprise Operations — Operational Reports"],
    dependencies=[Depends(require_user)],
)


class ReportGenerateRequest(BaseModel):
    report_type: str


@router.post("/generate")
async def generate_report(
    body: ReportGenerateRequest,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    if body.report_type not in ("daily", "weekly", "monthly"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type '{body.report_type}'. Must be one of: daily, weekly, monthly",
        )
    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    return await operational_reports_service.generate_report(
        report_type=body.report_type,
        db=db,
        generated_by=user_id,
    )


@router.get("/list")
async def list_reports(
    report_type: Optional[str] = Query(None, description="Filter by type: daily, weekly, monthly"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    reports = await operational_reports_service.list_reports(
        db=db,
        report_type=report_type,
        limit=limit,
    )
    return {"reports": reports, "total": len(reports)}


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    report = await operational_reports_service.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return {"report": report}
