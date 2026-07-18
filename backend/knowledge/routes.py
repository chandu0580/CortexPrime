from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Runtime"])

log = logging.getLogger(__name__)

_handlers: dict[str, Any] = {}


def register_knowledge_routes(service: Any, events: Any) -> None:
    _handlers["service"] = service
    _handlers["events"] = events


def _get_service():
    svc = _handlers.get("service")
    if not svc:
        from backend.knowledge.service import KnowledgeService
        svc = KnowledgeService()
        _handlers["service"] = svc
    return svc


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


class CreateKnowledgeRequest(BaseModel):
    title: str
    content: str
    summary: str = ""
    category: str = "document"
    tags: list[str] = []
    source: str = ""
    source_url: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = {}


class UpdateKnowledgeRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None


class CreateRelationshipRequest(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str = "related_to"
    strength: float = 1.0
    metadata: dict[str, Any] = {}


class SearchRequest(BaseModel):
    query: str = ""
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    source: Optional[str] = None
    confidence_min: Optional[float] = None
    confidence_max: Optional[float] = None
    metadata_filter: Optional[dict[str, Any]] = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    limit: int = 20
    offset: int = 0
    include_relationships: bool = False


class IndexMissionRequest(BaseModel):
    mission_id: str
    title: str
    objective: str
    status: str
    owner: str
    result: Optional[str] = None
    metadata: dict[str, Any] = {}


class IndexExecutionRequest(BaseModel):
    execution_id: str
    mission_id: Optional[str] = None
    agent: str = ""
    status: str
    trigger: str = "manual"
    result_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class IndexGovernanceRequest(BaseModel):
    decision_id: str
    policy_name: str
    decision: str
    resource_type: str
    resource_id: str
    action: str
    reason: str = ""


class IndexConnectorRequest(BaseModel):
    connector_id: str
    name: str
    connector_type: str
    status: str
    metadata: dict[str, Any] = {}


class IndexArtifactRequest(BaseModel):
    name: str
    description: str
    source: str = ""
    tags: list[str] = []
    metadata: dict[str, Any] = {}


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------


@router.post("", response_model=dict[str, Any], status_code=201)
async def create_knowledge(req: CreateKnowledgeRequest):
    from backend.knowledge.models import IndexRequest
    svc = _get_service()
    request = IndexRequest(
        title=req.title,
        content=req.content,
        summary=req.summary,
        category=req.category,
        tags=req.tags,
        source=req.source,
        source_url=req.source_url,
        confidence=req.confidence,
        metadata=req.metadata,
    )
    doc = await svc.create_entry(request)
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to create knowledge entry")
    return _doc_to_response(doc)


@router.get("", response_model=list[dict[str, Any]])
async def list_knowledge(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = _get_service()
    entries = await svc.list_entries(category=category, limit=limit, offset=offset)
    return [_doc_to_response(e) for e in entries]


@router.get("/{entry_id}", response_model=dict[str, Any])
async def get_knowledge(entry_id: str):
    svc = _get_service()
    doc = await svc.get_entry(entry_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Knowledge entry {entry_id} not found")
    return _doc_to_response(doc)


@router.put("/{entry_id}", response_model=dict[str, Any])
async def update_knowledge(entry_id: str, req: UpdateKnowledgeRequest):
    svc = _get_service()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    doc = await svc.update_entry(entry_id, updates)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Knowledge entry {entry_id} not found")
    return _doc_to_response(doc)


@router.delete("/{entry_id}", response_model=dict[str, Any])
async def delete_knowledge(entry_id: str):
    svc = _get_service()
    success = await svc.delete_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Knowledge entry {entry_id} not found")
    return {"success": True, "entry_id": entry_id}


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------


@router.post("/search", response_model=dict[str, Any])
async def search_knowledge(req: SearchRequest):
    from backend.knowledge.models import KnowledgeQuery
    svc = _get_service()
    kq = KnowledgeQuery(
        query=req.query,
        category=req.category,
        tags=req.tags,
        source=req.source,
        confidence_min=req.confidence_min,
        confidence_max=req.confidence_max,
        metadata_filter=req.metadata_filter,
        sort_by=req.sort_by,
        sort_order=req.sort_order,
        limit=req.limit,
        offset=req.offset,
        include_relationships=req.include_relationships,
    )
    result = await svc.search(kq)
    return {
        "entries": [_doc_to_response(e) for e in result.entries],
        "total": result.total,
        "query": result.query,
        "limit": result.limit,
        "offset": result.offset,
        "relationships": [
            _rel_to_response(r) for r in (result.relationships or [])
        ] if result.relationships else None,
    }


@router.get("/search", response_model=dict[str, Any])
async def search_knowledge_get(
    q: str = Query(""),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    from backend.knowledge.models import KnowledgeQuery
    svc = _get_service()
    kq = KnowledgeQuery(query=q, category=category, limit=limit, offset=offset)
    result = await svc.search(kq)
    return {
        "entries": [_doc_to_response(e) for e in result.entries],
        "total": result.total,
        "query": result.query,
        "limit": result.limit,
        "offset": result.offset,
    }


# ------------------------------------------------------------------
# Relationships
# ------------------------------------------------------------------


@router.post("/relationships", response_model=dict[str, Any], status_code=201)
async def create_relationship(req: CreateRelationshipRequest):
    svc = _get_service()
    rel = await svc.create_relationship(
        source_id=req.source_id,
        target_id=req.target_id,
        relationship_type=req.relationship_type,
        strength=req.strength,
        metadata=req.metadata,
    )
    if not rel:
        raise HTTPException(status_code=500, detail="Failed to create relationship")
    return _rel_to_response(rel)


@router.get("/relationships", response_model=list[dict[str, Any]])
async def list_relationships(
    relationship_type: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = _get_service()
    rels = await svc.search_relationships(
        relationship_type=relationship_type,
        source_id=source_id,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    return [_rel_to_response(r) for r in rels]


@router.delete("/relationships/{relationship_id}", response_model=dict[str, Any])
async def delete_relationship(relationship_id: str):
    svc = _get_service()
    success = await svc.delete_relationship(relationship_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Relationship {relationship_id} not found")
    return {"success": True, "relationship_id": relationship_id}


@router.get("/{entry_id}/relationships", response_model=list[dict[str, Any]])
async def get_entry_relationships(entry_id: str):
    svc = _get_service()
    rels = await svc.get_entry_relationships(entry_id)
    return [_rel_to_response(r) for r in rels]


# ------------------------------------------------------------------
# Indexing
# ------------------------------------------------------------------


@router.post("/index/mission", response_model=dict[str, Any], status_code=201)
async def index_mission(req: IndexMissionRequest):
    svc = _get_service()
    doc = await svc.index_mission(
        mission_id=req.mission_id, title=req.title, objective=req.objective,
        status=req.status, owner=req.owner, result=req.result, metadata=req.metadata,
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to index mission")
    return _doc_to_response(doc)


@router.post("/index/execution", response_model=dict[str, Any], status_code=201)
async def index_execution(req: IndexExecutionRequest):
    svc = _get_service()
    doc = await svc.index_execution(
        execution_id=req.execution_id, mission_id=req.mission_id,
        agent=req.agent, status=req.status, trigger=req.trigger,
        result_data=req.result_data, error=req.error,
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to index execution")
    return _doc_to_response(doc)


@router.post("/index/governance", response_model=dict[str, Any], status_code=201)
async def index_governance(req: IndexGovernanceRequest):
    svc = _get_service()
    doc = await svc.index_governance_decision(
        decision_id=req.decision_id, policy_name=req.policy_name,
        decision=req.decision, resource_type=req.resource_type,
        resource_id=req.resource_id, action=req.action, reason=req.reason,
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to index governance decision")
    return _doc_to_response(doc)


@router.post("/index/connector", response_model=dict[str, Any], status_code=201)
async def index_connector(req: IndexConnectorRequest):
    svc = _get_service()
    doc = await svc.index_connector(
        connector_id=req.connector_id, name=req.name,
        connector_type=req.connector_type, status=req.status, metadata=req.metadata,
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to index connector")
    return _doc_to_response(doc)


@router.post("/index/artifact", response_model=dict[str, Any], status_code=201)
async def index_artifact(req: IndexArtifactRequest):
    svc = _get_service()
    doc = await svc.index_artifact(
        name=req.name, description=req.description, source=req.source,
        tags=req.tags, metadata=req.metadata,
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to index artifact")
    return _doc_to_response(doc)


# ------------------------------------------------------------------
# Categories / Metadata
# ------------------------------------------------------------------


@router.get("/categories", response_model=list[str])
async def list_categories():
    svc = _get_service()
    return await svc.list_categories()


@router.get("/categories/counts", response_model=dict[str, int])
async def category_counts():
    svc = _get_service()
    return await svc.count_by_category()


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@router.get("/health", response_model=dict[str, Any])
async def knowledge_health():
    svc = _get_service()
    return await svc.health()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _doc_to_response(doc: Any) -> dict[str, Any]:
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "summary": doc.summary,
        "category": doc.category,
        "tags": doc.tags,
        "source": doc.source,
        "source_url": doc.source_url,
        "confidence": doc.confidence,
        "metadata": doc.metadata,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


def _rel_to_response(rel: Any) -> dict[str, Any]:
    return {
        "id": rel.id,
        "source_id": rel.source_id,
        "target_id": rel.target_id,
        "relationship_type": rel.relationship_type,
        "strength": rel.strength,
        "metadata": rel.metadata,
        "created_at": rel.created_at,
    }
