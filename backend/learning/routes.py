from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/learning", tags=["Learning Runtime"])

log = logging.getLogger(__name__)

_handlers: dict[str, Any] = {}


def register_learning_routes(service: Any, events: Any) -> None:
    _handlers["service"] = service
    _handlers["events"] = events


def _get_service():
    svc = _handlers.get("service")
    if not svc:
        from backend.learning.service import LearningService
        svc = LearningService()
        _handlers["service"] = svc
    return svc


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


class StartSessionRequest(BaseModel):
    mission_type: str = "general"
    metadata: dict[str, Any] = {}


class AnalyzeMissionRequest(BaseModel):
    mission_id: str
    title: str = ""
    status: str = ""
    owner: str = ""
    mission_type: str = "standard"
    retry_count: int = 0
    metadata: dict[str, Any] = {}


class AnalyzeExecutionRequest(BaseModel):
    execution_id: str
    mission_id: Optional[str] = None
    agent: str = ""
    status: str = ""
    trigger: str = "manual"
    error: str = ""
    metadata: dict[str, Any] = {}


class AnalyzeConnectorRequest(BaseModel):
    connector_id: str
    name: str = ""
    connector_type: str = ""
    status: str = ""
    failure_rate: float = 0.0
    total: int = 0
    failed: int = 0
    metadata: dict[str, Any] = {}


class AnalyzeGovernanceRequest(BaseModel):
    decision_id: str
    policy_name: str = ""
    decision: str = ""
    resource_type: str = ""
    resource_id: str = ""
    action: str = ""
    reason: str = ""
    metadata: dict[str, Any] = {}


# ------------------------------------------------------------------
# Sessions
# ------------------------------------------------------------------


@router.post("/sessions", response_model=dict[str, Any])
async def start_learning_session(req: StartSessionRequest):
    svc = _get_service()
    session = await svc.start_session(
        mission_type=req.mission_type,
        metadata=req.metadata,
    )
    return _session_to_response(session)


@router.post("/sessions/{session_id}/analyze", response_model=dict[str, Any])
async def analyze_session(session_id: str):
    from backend.learning.models import LearningSession
    svc = _get_service()
    session = LearningSession(session_id=session_id, mission_type="general", status="active")
    result = await svc.run_full_analysis(session)
    return _result_to_response(result)


@router.get("/sessions", response_model=list[dict[str, Any]])
async def list_sessions(
    mission_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = _get_service()
    sessions = await svc.list_sessions(mission_type=mission_type, limit=limit, offset=offset)
    return [_session_to_response(s) for s in sessions]


# ------------------------------------------------------------------
# Analysis endpoints
# ------------------------------------------------------------------


@router.post("/analyze/mission", response_model=dict[str, Any])
async def analyze_mission(req: AnalyzeMissionRequest):
    svc = _get_service()
    result = await svc.analyze_mission(req.model_dump())
    return _result_to_response(result)


@router.post("/analyze/execution", response_model=dict[str, Any])
async def analyze_execution(req: AnalyzeExecutionRequest):
    svc = _get_service()
    result = await svc.analyze_execution(req.model_dump())
    return _result_to_response(result)


@router.post("/analyze/connector", response_model=dict[str, Any])
async def analyze_connector(req: AnalyzeConnectorRequest):
    svc = _get_service()
    result = await svc.analyze_connector(req.model_dump())
    return _result_to_response(result)


@router.post("/analyze/governance", response_model=dict[str, Any])
async def analyze_governance(req: AnalyzeGovernanceRequest):
    svc = _get_service()
    result = await svc.analyze_governance(req.model_dump())
    return _result_to_response(result)


# ------------------------------------------------------------------
# Patterns
# ------------------------------------------------------------------


@router.get("/patterns", response_model=list[dict[str, Any]])
async def list_patterns(
    category: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = _get_service()
    patterns = await svc.list_patterns(
        category=category, min_confidence=min_confidence,
        limit=limit, offset=offset,
    )
    return [_pattern_to_response(p) for p in patterns]


@router.get("/patterns/{pattern_id}", response_model=dict[str, Any])
async def get_pattern(pattern_id: str):
    svc = _get_service()
    pattern = await svc.get_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail=f"Pattern {pattern_id} not found")
    return _pattern_to_response(pattern)


# ------------------------------------------------------------------
# Statistics / Health
# ------------------------------------------------------------------


@router.get("/statistics", response_model=dict[str, Any])
async def learning_statistics():
    svc = _get_service()
    return await svc.get_statistics()


@router.get("/health", response_model=dict[str, Any])
async def learning_health():
    svc = _get_service()
    return await svc.health()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _session_to_response(s: Any) -> dict[str, Any]:
    return {
        "id": s.id,
        "session_id": s.session_id,
        "mission_type": s.mission_type,
        "status": s.status,
        "outcome": s.outcome,
        "score": s.score,
        "patterns_extracted": s.patterns_extracted,
        "lessons_learned": s.lessons_learned,
        "metadata": s.metadata,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def _pattern_to_response(p: Any) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "confidence": p.confidence,
        "occurrences": p.occurrences,
        "pattern_data": p.pattern_data,
        "is_active": p.is_active,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _result_to_response(r: Any) -> dict[str, Any]:
    return {
        "session_id": r.session_id,
        "patterns_found": [_pattern_to_response(p) for p in r.patterns_found],
        "recommendations": [_rec_to_response(rec) for rec in r.recommendations],
        "score": r.score,
        "summary": r.summary,
        "duration_ms": r.duration_ms,
    }


def _rec_to_response(rec: Any) -> dict[str, Any]:
    return {
        "id": rec.id,
        "category": rec.category,
        "title": rec.title,
        "description": rec.description,
        "reason": rec.reason,
        "evidence": rec.evidence,
        "confidence": rec.confidence,
        "priority": rec.priority,
        "risk": rec.risk,
        "estimated_impact": rec.estimated_impact,
        "actions": rec.actions,
        "related_id": rec.related_id,
        "status": rec.status,
    }
