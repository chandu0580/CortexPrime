from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.session import get_session
from backend.services.backup_service import SUPPORTED_ENTITIES, backup_service

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/operations/backup",
    tags=["Enterprise Operations — Backup & Restore"],
    dependencies=[Depends(require_user)],
)


class BackupCreateRequest(BaseModel):
    entities: List[str]


class BackupRestoreRequest(BaseModel):
    backup_id: str
    entities: Optional[List[str]] = None


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_backup(
    body: BackupCreateRequest,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    invalid = [e for e in body.entities if e not in SUPPORTED_ENTITIES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported entities: {invalid}. Supported: {list(SUPPORTED_ENTITIES.keys())}",
        )
    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    return await backup_service.create_backup(
        entities=body.entities,
        triggered_by=user_id,
        db=db,
    )


@router.post("/restore")
async def restore_backup(
    body: BackupRestoreRequest,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    result = await backup_service.restore_backup(
        backup_id=body.backup_id,
        entities=body.entities,
        triggered_by=user_id,
        db=db,
    )
    if result.get("status") == "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))
    return result


@router.post("/verify")
async def verify_backup(body: BackupRestoreRequest) -> Dict[str, Any]:
    return await backup_service.verify_backup(body.backup_id)


@router.post("/rollback")
async def rollback_backup(
    body: BackupRestoreRequest,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    return await backup_service.rollback(
        backup_id=body.backup_id,
        triggered_by=user_id,
        db=db,
    )


@router.get("/list")
async def list_backups(
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    backups = await backup_service.list_backups(limit=limit)
    return {"backups": backups, "total": len(backups)}


@router.get("/entities")
async def list_supported_entities() -> Dict[str, Any]:
    return {"entities": SUPPORTED_ENTITIES}
