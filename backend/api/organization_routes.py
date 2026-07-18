from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.models.organization import OrganizationModel
from backend.database.repositories.organization_repository import OrganizationRepository
from backend.database.session import get_session

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/organizations",
    tags=["Organizations"],
    dependencies=[Depends(require_user)],
)


class OrganizationCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------
# List / Search
# ------------------------------------------------------------------

@router.get("")
async def list_organizations(
    query: Optional[str] = Query(None, description="Search across name, description, domain"),
    is_active: Optional[bool] = Query(None),
    domain: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = OrganizationRepository(db)
    items = await repo.search(
        query=query,
        is_active=is_active,
        domain=domain,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_filtered(
        query=query,
        is_active=is_active,
        domain=domain,
    )
    return {
        "organizations": [o.to_dict() for o in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ------------------------------------------------------------------
# Get by ID
# ------------------------------------------------------------------

@router.get("/{org_id}")
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = OrganizationRepository(db)
    org = await repo.get(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return {"organization": org.to_dict()}


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = OrganizationRepository(db)

    existing = await repo.get_by_name(body.name)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Organization '{body.name}' already exists")

    if body.domain:
        existing = await repo.get_by_domain(body.domain)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Domain '{body.domain}' already in use")

    org = await repo.create(
        OrganizationModel(
            name=body.name,
            domain=body.domain,
            description=body.description,
            is_active=body.is_active,
            metadata_=body.metadata,
        )
    )
    log.info("Created organization %s (%s)", org.id, org.name)
    return {"organization": org.to_dict()}


# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------

@router.put("/{org_id}")
async def update_organization(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = OrganizationRepository(db)
    org = await repo.get(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.name is not None:
        existing = await repo.get_by_name(body.name)
        if existing and existing.id != org_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Organization '{body.name}' already exists")
        org.name = body.name

    if body.domain is not None:
        existing = await repo.get_by_domain(body.domain)
        if existing and existing.id != org_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Domain '{body.domain}' already in use")
        org.domain = body.domain

    if body.description is not None:
        org.description = body.description

    if body.is_active is not None:
        org.is_active = body.is_active

    if body.metadata is not None:
        org.metadata_ = body.metadata

    updated = await repo.update(org)
    log.info("Updated organization %s (%s)", updated.id, updated.name)
    return {"organization": updated.to_dict()}


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------

@router.delete("/{org_id}")
async def delete_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, str]:
    repo = OrganizationRepository(db)
    deleted = await repo.delete(org_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    log.info("Deleted organization %s", org_id)
    return {"status": "deleted"}



