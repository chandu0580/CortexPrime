from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.repositories.enterprise_audit_repository import EnterpriseAuditRepository
from backend.database.session import get_session

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/audit",
    tags=["Enterprise Audit"],
    dependencies=[Depends(require_user)],
)


# ------------------------------------------------------------------
# List / Search
# ------------------------------------------------------------------

@router.get("")
async def list_audit_entries(
    category: Optional[str] = Query(None, description="Filter by agent/category"),
    actor: Optional[str] = Query(None, description="Filter by user_id/actor"),
    status: Optional[str] = Query(None, description="Filter by outcome/status (allowed, blocked, approved, rejected, pending, started, completed, failed, stopped)"),
    severity: Optional[str] = Query(None, description="Filter by risk_level/severity (low, medium, high, critical)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type prefix on execution_id"),
    resource_id: Optional[str] = Query(None, description="Filter by exact execution_id"),
    start_date: Optional[datetime] = Query(None, description="Start of date range (ISO-8601)"),
    end_date: Optional[datetime] = Query(None, description="End of date range (ISO-8601)"),
    query: Optional[str] = Query(None, description="Search across action, reason, agent, user_id, execution_id"),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = EnterpriseAuditRepository(db)
    limit = page_size
    offset = (page - 1) * page_size
    items = await repo.search(
        category=category,
        actor=actor,
        status=status,
        severity=severity,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        query=query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_filtered(
        category=category,
        actor=actor,
        status=status,
        severity=severity,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        query=query,
    )
    return {
        "entries": [EnterpriseAuditRepository.to_enterprise_dict(e) for e in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ------------------------------------------------------------------
# Get by ID
# ------------------------------------------------------------------

@router.get("/{entry_id}")
async def get_audit_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = EnterpriseAuditRepository(db)
    entry = await repo.get(entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit entry not found")
    return {"entry": EnterpriseAuditRepository.to_enterprise_dict(entry)}


# ------------------------------------------------------------------
# List / Logs (alias for the list endpoint)
# ------------------------------------------------------------------

@router.get("/logs")
async def list_audit_logs(
    category: Optional[str] = Query(None, description="Filter by agent/category"),
    actor: Optional[str] = Query(None, description="Filter by user_id/actor"),
    status: Optional[str] = Query(None, description="Filter by outcome/status (allowed, blocked, approved, rejected, pending, started, completed, failed, stopped)"),
    severity: Optional[str] = Query(None, description="Filter by risk_level/severity (low, medium, high, critical)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type prefix on execution_id"),
    resource_id: Optional[str] = Query(None, description="Filter by exact execution_id"),
    start_date: Optional[datetime] = Query(None, description="Start of date range (ISO-8601)"),
    end_date: Optional[datetime] = Query(None, description="End of date range (ISO-8601)"),
    query: Optional[str] = Query(None, description="Search across action, reason, agent, user_id, execution_id"),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = EnterpriseAuditRepository(db)
    limit = page_size
    offset = (page - 1) * page_size
    items = await repo.search(
        category=category,
        actor=actor,
        status=status,
        severity=severity,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        query=query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_filtered(
        category=category,
        actor=actor,
        status=status,
        severity=severity,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        query=query,
    )
    return {
        "entries": [EnterpriseAuditRepository.to_enterprise_dict(e) for e in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
