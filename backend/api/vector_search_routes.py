"""
Vector Search & Memory Retrieval API — /api/vector/*

Provides dedicated endpoints for:
  - pgvector cosine similarity search (episodic, semantic, reflection)
  - Hybrid search (vector + full-text)
  - Direct repository CRUD
  - Runtime analytics ingest and query
  - Embedding cache status

All endpoints use the SQLAlchemy async session dependency and the
repository pattern — zero raw SQL in route handlers.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session                               import get_session
from backend.database.repositories.episodic_repository     import EpisodicRepository
from backend.database.repositories.semantic_repository     import SemanticRepository
from backend.database.repositories.reflection_repository   import ReflectionRepository
from backend.database.repositories.analytics_repository    import AnalyticsRepository
from backend.database.models.episodic_memory               import EpisodicMemoryRecord
from backend.database.models.semantic_memory               import SemanticMemoryRecord
from backend.database.models.reflection_history            import ReflectionHistoryRecord
from backend.database.models.runtime_analytics             import RuntimeAnalyticsRecord
from backend.database.health                               import check_database_health

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vector", tags=["Vector Search"])


# ===========================================================================
# Request / Response schemas
# ===========================================================================

class VectorSearchRequest(BaseModel):
    embedding:      List[float]        = Field(..., min_length=1)
    limit:          int                = Field(10, ge=1, le=100)
    min_similarity: float              = Field(0.0, ge=0.0, le=1.0)
    session_id:     Optional[str]      = None
    agent:          Optional[str]      = None
    min_confidence: float              = Field(0.0, ge=0.0, le=1.0)


class HybridSearchRequest(BaseModel):
    query:          str
    embedding:      Optional[List[float]] = None
    limit:          int                   = Field(10, ge=1, le=100)
    min_confidence: float                 = Field(0.0, ge=0.0, le=1.0)


class StoreEpisodicRequest(BaseModel):
    session_id: str
    agent:      str
    event_type: str
    content:    str
    embedding:  Optional[List[float]] = None
    metadata:   Dict[str, Any]        = Field(default_factory=dict)


class StoreSemanticRequest(BaseModel):
    concept:    str
    content:    str
    embedding:  Optional[List[float]] = None
    source:     Optional[str]         = None
    confidence: float                 = 1.0
    metadata:   Dict[str, Any]        = Field(default_factory=dict)


class StoreReflectionRequest(BaseModel):
    agent:      str
    reflection: str
    embedding:  Optional[List[float]] = None
    mission_id: Optional[str]         = None
    score:      Optional[float]       = None
    metadata:   Dict[str, Any]        = Field(default_factory=dict)


class RecordAnalyticsRequest(BaseModel):
    agent:         str
    event_type:    str
    model:         Optional[str]   = None
    mission_id:    Optional[str]   = None
    session_id:    Optional[str]   = None
    prompt_tokens: Optional[int]   = None
    output_tokens: Optional[int]   = None
    latency_ms:    Optional[float] = None
    cost_usd:      Optional[float] = None
    success:       bool            = True
    error_message: Optional[str]   = None
    payload:       Dict[str, Any]  = Field(default_factory=dict)


# ===========================================================================
# Health
# ===========================================================================

@router.get("/health", response_model=Dict[str, Any])
async def database_health():
    """Return PostgreSQL + pgvector health status."""
    return await check_database_health()


# ===========================================================================
# Episodic — store + search
# ===========================================================================

@router.post("/episodic", response_model=Dict[str, str], status_code=201)
async def store_episodic(
    req: StoreEpisodicRequest,
    db: AsyncSession = Depends(get_session),
):
    """Persist an episodic memory event with an optional pre-computed embedding."""
    repo = EpisodicRepository(db)
    record = EpisodicMemoryRecord(
        session_id = req.session_id,
        agent      = req.agent,
        event_type = req.event_type,
        content    = req.content,
        embedding  = req.embedding,
        metadata   = req.metadata,
    )
    saved = await repo.create(record)
    return {"id": str(saved.id)}


@router.get("/episodic/{session_id}", response_model=List[Dict[str, Any]])
async def get_episodic_session(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    """Return recent episodic events for a session."""
    repo    = EpisodicRepository(db)
    records = await repo.get_by_session(session_id, limit=limit)
    return [r.to_dict() for r in records]


@router.post("/episodic/search/vector", response_model=List[Dict[str, Any]])
async def vector_search_episodic(
    req: VectorSearchRequest,
    db: AsyncSession = Depends(get_session),
):
    """Cosine similarity search over episodic memory embeddings."""
    repo = EpisodicRepository(db)
    return await repo.search_similar(
        embedding       = req.embedding,
        limit           = req.limit,
        min_similarity  = req.min_similarity,
        session_id      = req.session_id,
    )


@router.get("/episodic/search/text", response_model=List[Dict[str, Any]])
async def text_search_episodic(
    q:     str = Query(..., description="Full-text search query"),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """PostgreSQL full-text search over episodic memory (fallback for no embeddings)."""
    repo = EpisodicRepository(db)
    return await repo.search_text(q, limit=limit)


# ===========================================================================
# Semantic — store + search
# ===========================================================================

@router.post("/semantic", response_model=Dict[str, str], status_code=201)
async def store_semantic(
    req: StoreSemanticRequest,
    db: AsyncSession = Depends(get_session),
):
    """Persist a semantic knowledge entry."""
    repo = SemanticRepository(db)
    record = SemanticMemoryRecord(
        concept    = req.concept,
        content    = req.content,
        embedding  = req.embedding,
        source     = req.source,
        confidence = req.confidence,
        metadata   = req.metadata,
    )
    saved = await repo.create(record)
    return {"id": str(saved.id)}


@router.get("/semantic", response_model=List[Dict[str, Any]])
async def get_semantic_by_concept(
    concept: str = Query(...),
    limit:   int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
):
    """Fetch semantic entries by concept name (case-insensitive LIKE)."""
    repo    = SemanticRepository(db)
    records = await repo.get_by_concept(concept, limit=limit)
    return [r.to_dict() for r in records]


@router.post("/semantic/search/vector", response_model=List[Dict[str, Any]])
async def vector_search_semantic(
    req: VectorSearchRequest,
    db: AsyncSession = Depends(get_session),
):
    """Cosine similarity search over semantic memory."""
    repo = SemanticRepository(db)
    return await repo.search_similar(
        embedding       = req.embedding,
        limit           = req.limit,
        min_similarity  = req.min_similarity,
        min_confidence  = req.min_confidence,
    )


@router.post("/semantic/search/hybrid", response_model=List[Dict[str, Any]])
async def hybrid_search_semantic(
    req: HybridSearchRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Hybrid semantic search: combines vector similarity + full-text,
    deduplicates, and returns a unified ranked list.
    """
    repo = SemanticRepository(db)
    return await repo.hybrid_search(
        query          = req.query,
        embedding      = req.embedding,
        limit          = req.limit,
        min_confidence = req.min_confidence,
    )


# ===========================================================================
# Reflection — store + search
# ===========================================================================

@router.post("/reflection", response_model=Dict[str, str], status_code=201)
async def store_reflection(
    req: StoreReflectionRequest,
    db: AsyncSession = Depends(get_session),
):
    """Persist a reflection entry."""
    repo = ReflectionRepository(db)
    mission_uuid: Optional[uuid.UUID] = None
    if req.mission_id:
        try:
            mission_uuid = uuid.UUID(req.mission_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid mission_id UUID")

    record = ReflectionHistoryRecord(
        agent      = req.agent,
        reflection = req.reflection,
        embedding  = req.embedding,
        mission_id = mission_uuid,
        score      = req.score,
        metadata   = req.metadata,
    )
    saved = await repo.create(record)
    return {"id": str(saved.id)}


@router.get("/reflection/agent/{agent}", response_model=List[Dict[str, Any]])
async def get_reflections_by_agent(
    agent: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    repo    = ReflectionRepository(db)
    records = await repo.get_by_agent(agent, limit=limit)
    return [r.to_dict() for r in records]


@router.post("/reflection/search/vector", response_model=List[Dict[str, Any]])
async def vector_search_reflection(
    req: VectorSearchRequest,
    db: AsyncSession = Depends(get_session),
):
    """Cosine similarity search over reflection embeddings."""
    repo = ReflectionRepository(db)
    return await repo.search_similar(
        embedding      = req.embedding,
        limit          = req.limit,
        min_similarity = req.min_similarity,
        agent          = req.agent,
    )


# ===========================================================================
# Runtime Analytics — ingest + query
# ===========================================================================

@router.post("/analytics", response_model=Dict[str, str], status_code=201)
async def record_analytics(
    req: RecordAnalyticsRequest,
    db: AsyncSession = Depends(get_session),
):
    """Ingest a runtime analytics event."""
    repo = AnalyticsRepository(db)
    mission_uuid: Optional[uuid.UUID] = None
    if req.mission_id:
        try:
            mission_uuid = uuid.UUID(req.mission_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid mission_id UUID")

    record = RuntimeAnalyticsRecord(
        agent         = req.agent,
        event_type    = req.event_type,
        model         = req.model,
        mission_id    = mission_uuid,
        session_id    = req.session_id,
        prompt_tokens = req.prompt_tokens,
        output_tokens = req.output_tokens,
        latency_ms    = req.latency_ms,
        cost_usd      = req.cost_usd,
        success       = req.success,
        error_message = req.error_message,
        payload       = req.payload,
    )
    saved = await repo.create(record)
    return {"id": str(saved.id)}


@router.get("/analytics/agent/{agent}", response_model=Dict[str, Any])
async def agent_analytics_summary(
    agent: str,
    db: AsyncSession = Depends(get_session),
):
    """Return aggregated performance stats for an agent."""
    repo = AnalyticsRepository(db)
    return await repo.agent_summary(agent)


@router.get("/analytics/hourly", response_model=List[Dict[str, Any]])
async def hourly_call_volume(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_session),
):
    """Return per-agent, per-hour call volume for the last *hours* hours."""
    repo = AnalyticsRepository(db)
    return await repo.hourly_call_volume(hours=hours)


@router.get("/analytics/models", response_model=List[Dict[str, Any]])
async def model_usage_stats(
    db: AsyncSession = Depends(get_session),
):
    """Return aggregated token and cost breakdown per LLM model."""
    repo = AnalyticsRepository(db)
    return await repo.model_usage_stats()


@router.get("/analytics/errors", response_model=List[Dict[str, Any]])
async def recent_errors(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    """Return the most recent failed analytics events."""
    repo    = AnalyticsRepository(db)
    records = await repo.get_recent_errors(limit=limit)
    return [r.to_dict() for r in records]
