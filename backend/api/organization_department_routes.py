from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.repositories.department_repository import DepartmentRepository
from backend.database.session import get_session

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/organization",
    tags=["Organization Departments"],
    dependencies=[Depends(require_user)],
)


@router.get("/departments")
async def list_organization_departments(
    query: Optional[str] = Query(None, description="Search across name, description"),
    is_active: Optional[bool] = Query(None),
    organization_id: Optional[uuid.UUID] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = DepartmentRepository(db)
    items = await repo.search(
        query=query,
        is_active=is_active,
        organization_id=organization_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_filtered(
        query=query,
        is_active=is_active,
        organization_id=organization_id,
    )
    return {
        "departments": [d.to_dict() for d in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
