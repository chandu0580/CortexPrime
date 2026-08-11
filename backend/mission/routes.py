from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.api.legacy_execution_boundary import guard_legacy_execution
from pydantic import BaseModel, Field

from backend.mission.models import MissionPriority, MissionType
from backend.mission.service import MissionService

router = APIRouter(prefix="/api/missions", tags=["Missions"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateMissionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    objective: str = Field(..., min_length=1)
    priority: MissionPriority = MissionPriority.MEDIUM
    mission_type: MissionType = MissionType.STANDARD
    category: Optional[str] = None
    owner: Optional[str] = None
    team: Optional[str] = None
    department: Optional[str] = None
    created_by: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class MissionResponse(BaseModel):
    id: str
    title: str
    objective: str
    status: str
    priority: int
    mission_type: str
    category: Optional[str] = None
    owner: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    correlation_id: Optional[str] = None


class PlanResponse(BaseModel):
    plan_id: str
    mission_id: str
    steps: list[dict[str, Any]]
    estimated_duration_ms: Optional[int] = None


class ProgressResponse(BaseModel):
    mission_id: str
    total_steps: int
    completed_steps: int
    failed_steps: int
    current_step: Optional[str] = None
    percent: float = 0.0
    status: str = "running"


class TimelineEntryResponse(BaseModel):
    entry_id: str
    mission_id: str
    entry_type: str
    status: str
    actor: Optional[str] = None
    message: str
    details: dict[str, Any]
    duration_ms: Optional[float] = None
    timestamp: str


class MissionEventResponse(BaseModel):
    event_id: str
    mission_id: str
    event_type: str
    correlation_id: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor: Optional[str] = None
    reason: Optional[str] = None
    payload: dict[str, Any]
    timestamp: str


class ApproveMissionRequest(BaseModel):
    request_id: str = Field(..., min_length=1)
    approved_by: str = Field(..., min_length=1)


class RejectMissionRequest(BaseModel):
    request_id: str = Field(..., min_length=1)


class CancelMissionRequest(BaseModel):
    reason: Optional[str] = None
    actor: Optional[str] = None


class RetryMissionRequest(BaseModel):
    actor: Optional[str] = None


# ---------------------------------------------------------------------------
# DI helper
# ---------------------------------------------------------------------------

async def get_mission_service() -> MissionService:
    return MissionService()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(
    request: CreateMissionRequest,
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.create_mission(
        title=request.title,
        objective=request.objective,
        priority=request.priority,
        mission_type=request.mission_type,
        category=request.category,
        owner=request.owner,
        team=request.team,
        department=request.department,
        created_by=request.created_by,
        context=request.context,
        tags=request.tags,
    )
    return _entity_to_response(entity)


@router.get("", response_model=list[MissionResponse])
async def list_missions(
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: MissionService = Depends(get_mission_service),
):
    if query or status or category or owner:
        entities = await service.search_missions(
            query=query, status=status, category=category,
            owner=owner, limit=limit, offset=offset,
        )
    else:
        entities = await service.list_missions(limit=limit, offset=offset)
    return [_entity_to_response(e) for e in entities]


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: uuid.UUID,
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.get_mission(mission_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/plan", response_model=MissionResponse)
async def plan_mission(
    mission_id: uuid.UUID,
    actor: Optional[str] = Query(None),
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.plan_mission(mission_id, actor=actor)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/risk-analysis", response_model=MissionResponse)
async def analyze_risk(
    mission_id: uuid.UUID,
    actor: Optional[str] = Query(None),
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.analyze_risk(mission_id, actor=actor)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/submit-for-approval", response_model=MissionResponse)
async def submit_for_approval(
    mission_id: uuid.UUID,
    requester: str = Query(..., min_length=1),
    reason: Optional[str] = Query(None),
    reviewers: Optional[str] = Query(None),
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.submit_for_approval(
        mission_id, requester=requester, reason=reason,
        reviewers=reviewers.split(",") if reviewers else None,
    )
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/approve", response_model=MissionResponse)
async def approve_mission(
    mission_id: uuid.UUID,
    request: ApproveMissionRequest,
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.approve_mission(mission_id, request.request_id, request.approved_by)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission or approval request not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/reject", response_model=MissionResponse)
async def reject_mission(
    mission_id: uuid.UUID,
    request: RejectMissionRequest,
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.reject_mission(mission_id, request.request_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission or approval request not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/queue", response_model=MissionResponse)
async def queue_mission(
    mission_id: uuid.UUID,
    actor: Optional[str] = Query(None),
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.queue_mission(mission_id, actor=actor)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.post(
    "/{mission_id}/execute",
    response_model=MissionResponse,
    dependencies=[Depends(guard_legacy_execution(
        "POST /api/missions/{mission_id}/execute"))],
)
async def execute_mission(
    mission_id: uuid.UUID,
    actor: Optional[str] = Query(None),
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.execute_mission(mission_id, actor=actor)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/verify", response_model=MissionResponse)
async def verify_mission(
    mission_id: uuid.UUID,
    verified: bool = Query(True),
    actor: Optional[str] = Query(None),
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.verify_mission(mission_id, verified=verified, actor=actor)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/cancel", response_model=MissionResponse)
async def cancel_mission(
    mission_id: uuid.UUID,
    request: CancelMissionRequest,
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.cancel_mission(mission_id, reason=request.reason, actor=request.actor)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.post("/{mission_id}/retry", response_model=MissionResponse)
async def retry_mission(
    mission_id: uuid.UUID,
    request: RetryMissionRequest,
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.retry_mission(mission_id, actor=request.actor)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return _entity_to_response(entity)


@router.get("/{mission_id}/plan", response_model=PlanResponse)
async def get_mission_plan(
    mission_id: uuid.UUID,
    service: MissionService = Depends(get_mission_service),
):
    plan = await service.get_plan(mission_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return PlanResponse(
        plan_id=plan.plan_id,
        mission_id=plan.mission_id,
        steps=[s.__dict__ for s in plan.steps],
        estimated_duration_ms=plan.estimated_duration_ms,
    )


@router.get("/{mission_id}/timeline", response_model=list[TimelineEntryResponse])
async def get_mission_timeline(
    mission_id: uuid.UUID,
    service: MissionService = Depends(get_mission_service),
):
    entries = await service.get_mission_timeline(mission_id)
    return [
        TimelineEntryResponse(
            entry_id=e.entry_id,
            mission_id=e.mission_id,
            entry_type=e.entry_type,
            status=e.status,
            actor=e.actor,
            message=e.message,
            details=e.details,
            duration_ms=e.duration_ms,
            timestamp=e.timestamp.isoformat(),
        )
        for e in entries
    ]


@router.get("/{mission_id}/events", response_model=list[MissionEventResponse])
async def get_mission_events(
    mission_id: uuid.UUID,
    service: MissionService = Depends(get_mission_service),
):
    events = await service.get_mission_events(mission_id)
    return [
        MissionEventResponse(
            event_id=e.event_id,
            mission_id=e.mission_id,
            event_type=e.event_type,
            correlation_id=e.correlation_id,
            from_status=e.from_status,
            to_status=e.to_status,
            actor=e.actor,
            reason=e.reason,
            payload=e.payload,
            timestamp=e.timestamp.isoformat(),
        )
        for e in events
    ]


@router.get("/{mission_id}/status", response_model=MissionResponse)
async def get_mission_status(
    mission_id: uuid.UUID,
    service: MissionService = Depends(get_mission_service),
):
    entity = await service.get_mission(mission_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Mission not found")
    return _entity_to_response(entity)


@router.get("/{mission_id}/progress", response_model=ProgressResponse)
async def get_mission_progress(
    mission_id: uuid.UUID,
    service: MissionService = Depends(get_mission_service),
):
    progress = await service.get_progress(mission_id)
    if not progress:
        entity = await service.get_mission(mission_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Mission not found")
        return ProgressResponse(
            mission_id=str(mission_id),
            total_steps=0, completed_steps=0, failed_steps=0,
            percent=0.0, status=entity.status.value,
        )
    return ProgressResponse(
        mission_id=progress.mission_id,
        total_steps=progress.total_steps,
        completed_steps=progress.completed_steps,
        failed_steps=progress.failed_steps,
        current_step=progress.current_step,
        percent=progress.percent,
        status=progress.status,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _entity_to_response(entity: Any) -> MissionResponse:
    return MissionResponse(
        id=str(entity.id),
        title=entity.title,
        objective=entity.objective,
        status=entity.status.value if hasattr(entity.status, 'value') else str(entity.status),
        priority=entity.priority.value if hasattr(entity.priority, 'value') else int(entity.priority),
        mission_type=entity.mission_type.value if hasattr(entity.mission_type, 'value') else str(entity.mission_type),
        category=entity.category,
        owner=entity.ownership.owner if entity.ownership else None,
        created_at=entity.timeline.created_at.isoformat() if entity.timeline.created_at else None,
        updated_at=None,
        started_at=entity.timeline.executing_at.isoformat() if entity.timeline.executing_at else None,
        completed_at=entity.timeline.completed_at.isoformat() if entity.timeline.completed_at else None,
        correlation_id=entity.metadata.correlation_id if entity.metadata else None,
    )
