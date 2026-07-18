from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.models.project import ProjectModel
from backend.database.repositories.department_repository import DepartmentRepository
from backend.database.repositories.organization_repository import OrganizationRepository
from backend.database.repositories.project_repository import ProjectRepository
from backend.database.session import get_session
from backend.safety.audit_logger import audit_logger

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects",
    tags=["Projects"],
    dependencies=[Depends(require_user)],
)


class ProjectCreate(BaseModel):
    name: str
    key: str
    organization_id: uuid.UUID
    department_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    status: str = "active"
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    key: Optional[str] = None
    department_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------
# List / Search
# ------------------------------------------------------------------

@router.get("")
async def list_projects(
    query: Optional[str] = Query(None, description="Search across name, key, description"),
    status: Optional[str] = Query(None),
    organization_id: Optional[uuid.UUID] = Query(None),
    department_id: Optional[uuid.UUID] = Query(None),
    owner: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = ProjectRepository(db)
    limit = page_size
    offset = (page - 1) * page_size
    items = await repo.search(
        query=query,
        status=status,
        organization_id=organization_id,
        department_id=department_id,
        owner=owner,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_filtered(
        query=query,
        status=status,
        organization_id=organization_id,
        department_id=department_id,
        owner=owner,
    )
    return {
        "projects": [p.to_dict() for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ------------------------------------------------------------------
# Get by ID
# ------------------------------------------------------------------

@router.get("/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = ProjectRepository(db)
    project = await repo.get(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return {"project": project.to_dict()}


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    org_repo = OrganizationRepository(db)
    org = await org_repo.get(body.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.department_id:
        dept_repo = DepartmentRepository(db)
        dept = await dept_repo.get(body.department_id)
        if not dept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        if dept.organization_id != body.organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Department does not belong to the specified organization",
            )

    repo = ProjectRepository(db)

    existing_key = await repo.get_by_key(body.key)
    if existing_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project key '{body.key}' already exists",
        )

    existing_name = await repo.get_by_name_in_org(body.name, body.organization_id)
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project name '{body.name}' already exists in this organization",
        )

    project = await repo.create(
        ProjectModel(
            name=body.name,
            key=body.key,
            organization_id=body.organization_id,
            department_id=body.department_id,
            description=body.description,
            status=body.status,
            owner=body.owner,
            tags=body.tags,
            metadata_=body.metadata,
        )
    )

    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    await audit_logger.alog(
        execution_id=str(project.id),
        agent="project_api",
        action="project.created",
        target=f"project/{project.id}",
        risk_level="low",
        outcome="allowed",
        reason=f"Project '{project.name}' created in org {body.organization_id}",
        user=user_id,
        metadata={
            "project_id": str(project.id),
            "organization_id": str(body.organization_id),
            "key": body.key,
        },
    )
    log.info("Created project %s (%s) in org %s", project.id, project.name, body.organization_id)
    return {"project": project.to_dict()}


# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------

@router.put("/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = ProjectRepository(db)
    project = await repo.get(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if body.key is not None and body.key != project.key:
        existing = await repo.get_by_key(body.key)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project key '{body.key}' already exists",
            )
        project.key = body.key

    if body.name is not None and body.name != project.name:
        existing = await repo.get_by_name_in_org(body.name, project.organization_id)
        if existing and existing.id != project_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project name '{body.name}' already exists in this organization",
            )
        project.name = body.name

    if body.department_id is not None and body.department_id != project.department_id:
        if body.department_id != uuid.UUID(int=0):
            dept_repo = DepartmentRepository(db)
            dept = await dept_repo.get(body.department_id)
            if not dept:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
            if dept.organization_id != project.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Department does not belong to the project's organization",
                )
        project.department_id = body.department_id

    if body.description is not None:
        project.description = body.description

    if body.status is not None:
        project.status = body.status

    if body.owner is not None:
        project.owner = body.owner

    if body.tags is not None:
        project.tags = body.tags

    if body.metadata is not None:
        project.metadata_ = body.metadata

    updated = await repo.update(project)

    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    await audit_logger.alog(
        execution_id=str(updated.id),
        agent="project_api",
        action="project.updated",
        target=f"project/{updated.id}",
        risk_level="low",
        outcome="allowed",
        reason=f"Project '{updated.name}' updated",
        user=user_id,
        metadata={
            "project_id": str(updated.id),
        },
    )
    log.info("Updated project %s (%s)", updated.id, updated.name)
    return {"project": updated.to_dict()}


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------

@router.delete("/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, str]:
    repo = ProjectRepository(db)
    project = await repo.get(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    await repo.delete(project_id)

    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    await audit_logger.alog(
        execution_id=str(project_id),
        agent="project_api",
        action="project.deleted",
        target=f"project/{project_id}",
        risk_level="medium",
        outcome="allowed",
        reason=f"Project '{project.name}' deleted",
        user=user_id,
        metadata={
            "project_id": str(project_id),
            "name": project.name,
        },
    )
    log.info("Deleted project %s (%s)", project_id, project.name)
    return {"status": "deleted"}
