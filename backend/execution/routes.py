from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/executions", tags=["executions"])


class CreateExecutionRequest(BaseModel):
    command: str
    execution_type: str = "shell"
    trigger: str = "manual"
    mission_id: Optional[str] = None
    mission_step_id: Optional[str] = None
    agent: Optional[str] = None
    inputs: Optional[dict[str, Any]] = None
    environment: Optional[dict[str, Any]] = None
    parameters: Optional[dict[str, Any]] = None
    timeout_seconds: int = 300
    max_retries: int = 3
    tags: Optional[list[str]] = None
    source: str = "api"


class ExecutionResponse(BaseModel):
    id: str
    execution_id: str
    status: str
    execution_type: str
    trigger: str
    mission_id: Optional[str] = None
    agent: Optional[str] = None
    result: dict[str, Any] = {}
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    created_at: str


_handlers: dict[str, Any] = {}


def register_execution_routes(service: Any, events: Any) -> None:
    _handlers["service"] = service
    _handlers["events"] = events


def _get_service():
    svc = _handlers.get("service")
    if not svc:
        from backend.execution.service import ExecutionService
        svc = ExecutionService()
        _handlers["service"] = svc
    return svc


def _entity_to_response(entity: Any) -> dict[str, Any]:
    return {
        "id": str(entity.id),
        "execution_id": entity.execution_id,
        "status": entity.status.value if hasattr(entity.status, "value") else str(entity.status),
        "execution_type": entity.execution_type.value if hasattr(entity.execution_type, "value") else str(entity.execution_type),
        "trigger": entity.trigger.value if hasattr(entity.trigger, "value") else str(entity.trigger),
        "mission_id": entity.mission_id,
        "agent": entity.agent,
        "result": entity.result or {},
        "error_message": entity.error_message,
        "started_at": entity.started_at.isoformat() if entity.started_at else None,
        "completed_at": entity.completed_at.isoformat() if entity.completed_at else None,
        "duration_ms": entity.duration_ms,
        "created_at": entity.created_at.isoformat() if entity.created_at else "",
    }


@router.post("", response_model=dict[str, Any])
async def create_execution(req: CreateExecutionRequest):
    from backend.execution.models import ExecutionTrigger, ExecutionType
    try:
        exec_type = ExecutionType(req.execution_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid execution type: {req.execution_type}")
    try:
        exec_trigger = ExecutionTrigger(req.trigger)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid trigger: {req.trigger}")

    svc = _get_service()
    entity = await svc.create_execution(
        command=req.command,
        execution_type=exec_type,
        trigger=exec_trigger,
        mission_id=req.mission_id,
        mission_step_id=req.mission_step_id,
        agent=req.agent,
        inputs=req.inputs,
        environment=req.environment,
        parameters=req.parameters,
        timeout_seconds=req.timeout_seconds,
        max_retries=req.max_retries,
        tags=req.tags,
        source=req.source,
    )
    return _entity_to_response(entity)


@router.get("", response_model=list[dict[str, Any]])
async def list_executions(
    status: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
    trigger: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = _get_service()
    entities = await svc.list_executions(
        status=status, agent=agent, trigger=trigger,
        limit=limit, offset=offset,
    )
    return [_entity_to_response(e) for e in entities]


@router.get("/{execution_id}", response_model=dict[str, Any])
async def get_execution(execution_id: str):
    svc = _get_service()
    entity = await svc.get_execution(execution_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    return _entity_to_response(entity)


@router.post("/{execution_id}/cancel", response_model=dict[str, Any])
async def cancel_execution(execution_id: str, reason: Optional[str] = None):
    svc = _get_service()
    try:
        entity = await svc.cancel_execution(execution_id, reason=reason, actor="api")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not entity:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    return _entity_to_response(entity)


@router.post("/{execution_id}/retry", response_model=dict[str, Any])
async def retry_execution(execution_id: str):
    svc = _get_service()
    try:
        entity = await svc.retry_execution(execution_id, actor="api")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not entity:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    return _entity_to_response(entity)


@router.get("/{execution_id}/events", response_model=list[dict[str, Any]])
async def get_execution_events(execution_id: str, limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
    svc = _get_service()
    events = await svc.get_execution_events(execution_id, limit=limit, offset=offset)
    return [
        {
            "id": str(e.id),
            "execution_id": e.execution_id,
            "event_type": e.event_type,
            "message": e.message,
            "payload": e.payload,
            "timestamp": e.timestamp.isoformat() if e.timestamp else "",
        }
        for e in events
    ]


@router.get("/{execution_id}/progress", response_model=Optional[dict[str, Any]])
async def get_execution_progress(execution_id: str):
    svc = _get_service()
    progress = await svc.get_progress(execution_id)
    if not progress:
        return None
    return {
        "execution_id": progress.execution_id,
        "total_steps": progress.total_steps,
        "completed_steps": progress.completed_steps,
        "failed_steps": progress.failed_steps,
        "percent": progress.percent,
        "status": progress.status,
    }


@router.get("/{execution_id}/in-memory-events", response_model=list[dict[str, Any]])
async def get_in_memory_events(execution_id: str):
    svc = _get_service()
    events = await svc.get_in_memory_events(execution_id)
    return [
        {
            "event_id": e.event_id,
            "execution_id": e.execution_id,
            "event_type": e.event_type,
            "correlation_id": e.correlation_id,
            "from_status": e.from_status,
            "to_status": e.to_status,
            "actor": e.actor,
            "message": e.message,
            "payload": e.payload,
        }
        for e in events
    ]


@router.post("/run", response_model=dict[str, Any])
async def run_execution(req: CreateExecutionRequest):
    from backend.execution.models import ExecutionTrigger, ExecutionType
    try:
        exec_type = ExecutionType(req.execution_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid execution type: {req.execution_type}")
    try:
        exec_trigger = ExecutionTrigger(req.trigger)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid trigger: {req.trigger}")

    svc = _get_service()
    entity = await svc.run_execution(
        command=req.command,
        execution_type=exec_type,
        trigger=exec_trigger,
        mission_id=req.mission_id,
        mission_step_id=req.mission_step_id,
        agent=req.agent,
        inputs=req.inputs,
        environment=req.environment,
        parameters=req.parameters,
        timeout_seconds=req.timeout_seconds,
        max_retries=req.max_retries,
        tags=req.tags,
        source=req.source,
    )
    return _entity_to_response(entity)
