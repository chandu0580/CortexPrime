from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.models.department import DepartmentModel
from backend.database.repositories.department_repository import DepartmentRepository
from backend.database.repositories.organization_repository import OrganizationRepository
from backend.database.session import get_session

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/departments",
    tags=["Departments"],
    dependencies=[Depends(require_user)],
)


class DepartmentCreate(BaseModel):
    name: str
    organization_id: uuid.UUID
    description: Optional[str] = None
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    organization_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------
# List / Search
# ------------------------------------------------------------------

@router.get("")
async def list_departments(
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


# ------------------------------------------------------------------
# Get by ID
# ------------------------------------------------------------------

@router.get("/{dept_id}")
async def get_department(
    dept_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = DepartmentRepository(db)
    dept = await repo.get(dept_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return {"department": dept.to_dict()}


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreate,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    org_repo = OrganizationRepository(db)
    org = await org_repo.get(body.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    dept_repo = DepartmentRepository(db)
    dept = await dept_repo.create(
        DepartmentModel(
            name=body.name,
            organization_id=body.organization_id,
            description=body.description,
            is_active=body.is_active,
            metadata_=body.metadata,
        )
    )
    log.info("Created department %s (%s) in org %s", dept.id, dept.name, body.organization_id)
    return {"department": dept.to_dict()}


# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------

@router.put("/{dept_id}")
async def update_department(
    dept_id: uuid.UUID,
    body: DepartmentUpdate,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = DepartmentRepository(db)
    dept = await repo.get(dept_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    if body.name is not None:
        dept.name = body.name

    if body.organization_id is not None:
        org_repo = OrganizationRepository(db)
        org = await org_repo.get(body.organization_id)
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        dept.organization_id = body.organization_id

    if body.description is not None:
        dept.description = body.description

    if body.is_active is not None:
        dept.is_active = body.is_active

    if body.metadata is not None:
        dept.metadata_ = body.metadata

    updated = await repo.update(dept)
    log.info("Updated department %s (%s)", updated.id, updated.name)
    return {"department": updated.to_dict()}


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------

@router.delete("/{dept_id}")
async def delete_department(
    dept_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, str]:
    repo = DepartmentRepository(db)
    deleted = await repo.delete(dept_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    log.info("Deleted department %s", dept_id)
    return {"status": "deleted"}



