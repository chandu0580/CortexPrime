from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_user
from backend.database.models.connector_activity import ConnectorActivityModel
from backend.database.repositories.connector_activity_repository import ConnectorActivityRepository
from backend.database.session import get_session
from backend.safety.audit_logger import audit_logger

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/connectors/activity",
    tags=["Connector Activity"],
    dependencies=[Depends(require_user)],
)


class ConnectorActivityCreate(BaseModel):
    connector_name: str
    connector_type: str
    operation: str
    resource: Optional[str] = None
    resource_id: Optional[str] = None
    status: str = "success"
    initiated_by: Optional[str] = None
    duration_ms: Optional[int] = None
    request_id: Optional[uuid.UUID] = None
    correlation_id: Optional[uuid.UUID] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------
# List / Search
# ------------------------------------------------------------------

@router.get("")
async def list_connector_activity(
    connector: Optional[str] = Query(None, description="Filter by connector_name"),
    connector_type: Optional[str] = Query(None, description="Filter by connector_type (github, jira, slack, etc.)"),
    operation: Optional[str] = Query(None, description="Filter by operation (sync, create, update, delete, fetch)"),
    status: Optional[str] = Query(None, description="Filter by status (success, failed, in_progress, pending)"),
    initiated_by: Optional[str] = Query(None, description="Filter by who initiated"),
    start_date: Optional[datetime] = Query(None, description="Start of date range (ISO-8601)"),
    end_date: Optional[datetime] = Query(None, description="End of date range (ISO-8601)"),
    query: Optional[str] = Query(None, description="Search across connector_name, message, resource"),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = ConnectorActivityRepository(db)
    limit = page_size
    offset = (page - 1) * page_size
    items = await repo.search(
        connector=connector,
        connector_type=connector_type,
        operation=operation,
        status=status,
        initiated_by=initiated_by,
        start_date=start_date,
        end_date=end_date,
        query=query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_filtered(
        connector=connector,
        connector_type=connector_type,
        operation=operation,
        status=status,
        initiated_by=initiated_by,
        start_date=start_date,
        end_date=end_date,
        query=query,
    )
    return {
        "activities": [a.to_dict() for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ------------------------------------------------------------------
# Get by ID
# ------------------------------------------------------------------

@router.get("/{activity_id}")
async def get_connector_activity(
    activity_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = ConnectorActivityRepository(db)
    activity = await repo.get(activity_id)
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector activity not found")
    return {"activity": activity.to_dict()}


# ------------------------------------------------------------------
# Create (record activity)
# ------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_connector_activity(
    body: ConnectorActivityCreate,
    current_user: dict = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    repo = ConnectorActivityRepository(db)
    activity = await repo.create(
        ConnectorActivityModel(
            connector_name=body.connector_name,
            connector_type=body.connector_type,
            operation=body.operation,
            resource=body.resource,
            resource_id=body.resource_id,
            status=body.status,
            initiated_by=body.initiated_by,
            duration_ms=body.duration_ms,
            request_id=body.request_id,
            correlation_id=body.correlation_id,
            message=body.message,
            metadata_=body.metadata,
        )
    )

    user_id = current_user.get("sub", current_user.get("user_id", "unknown"))
    await audit_logger.alog(
        execution_id=str(activity.id),
        agent="connector_activity_api",
        action="connector.activity.recorded",
        target=f"connector_activity/{activity.id}",
        risk_level="low",
        outcome="allowed",
        reason=f"Activity recorded for {body.connector_type}/{body.connector_name}: {body.operation}",
        user=user_id,
        metadata={
            "activity_id": str(activity.id),
            "connector_type": body.connector_type,
            "connector_name": body.connector_name,
            "operation": body.operation,
            "status": body.status,
        },
    )
    log.info("Recorded connector activity %s: %s/%s - %s", activity.id, body.connector_type, body.connector_name, body.operation)
    return {"activity": activity.to_dict()}
