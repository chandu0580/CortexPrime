"""
Graph REST API Routes
=====================
Exposes Neo4j cognitive graph operations via FastAPI endpoints.

All endpoints degrade gracefully when Neo4j is unavailable — they
return empty results rather than 503 errors, keeping the API surface
stable in development environments without Neo4j running.

Mount with: app.include_router(graph_router)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_user

log = logging.getLogger(__name__)

graph_router = APIRouter(
    prefix="/api/graph",
    tags=["cognitive-graph"],
    dependencies=[Depends(require_user)],
)


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class UpsertAgentRequest(BaseModel):
    name: str
    agent_type: str
    capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentDependencyRequest(BaseModel):
    from_agent: str
    to_agent: str
    reason: str = ""


class UpsertMemoryRequest(BaseModel):
    memory_id: str
    memory_type: str
    content: str
    agent: Optional[str] = None
    execution_id: Optional[str] = None
    mission_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LinkMemoriesRequest(BaseModel):
    source_id: str
    target_id: str
    rel_type: str = "RELATED_TO"
    weight: float = 1.0


class UpsertConceptRequest(BaseModel):
    name: str
    domain: str = "general"
    description: str = ""
    confidence: float = 1.0


class RelateConceptsRequest(BaseModel):
    concept_a: str
    concept_b: str
    rel_type: str = "RELATED_TO"
    weight: float = 1.0
    description: str = ""


class UpsertWorldModelRequest(BaseModel):
    model_id: str
    name: str
    domain: str
    description: str = ""


class CognitionEventRequest(BaseModel):
    event_id: str
    event_type: str
    agent: str
    execution_id: Optional[str] = None
    payload_summary: Optional[str] = None


class ReflectionRequest(BaseModel):
    reflection_id: str
    agent: str
    summary: str
    execution_id: Optional[str] = None
    memory_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper: lazy-import query service
# ---------------------------------------------------------------------------

def _qs():
    from backend.infrastructure.neo4j.query_service import graph_query_service
    return graph_query_service

def _agents():
    from backend.infrastructure.neo4j.repositories.agent_repository import agent_repository
    return agent_repository

def _executions():
    from backend.infrastructure.neo4j.repositories.execution_repository import execution_repository
    return execution_repository

def _memories():
    from backend.infrastructure.neo4j.repositories.memory_repository import memory_repository
    return memory_repository

def _cognition():
    from backend.infrastructure.neo4j.repositories.cognition_repository import cognition_repository
    return cognition_repository

def _world_models():
    from backend.infrastructure.neo4j.repositories.world_model_repository import world_model_repository
    return world_model_repository


# ===========================================================================
# HEALTH
# ===========================================================================

@graph_router.get("/health")
async def graph_health():
    """Return Neo4j connection status and basic graph stats."""
    try:
        from backend.infrastructure.neo4j.connection import neo4j_connection
        connected = neo4j_connection.is_available
        stats = await _qs().get_graph_stats() if connected else {}
        return {"status": "connected" if connected else "disconnected", "stats": stats}
    except Exception as exc:
        log.warning("graph_health error: %s", exc)
        return {"status": "unavailable", "stats": {}}


# ===========================================================================
# AGENT ENDPOINTS
# ===========================================================================

@graph_router.get("/agents")
async def list_agents() -> Dict[str, Any]:
    """List all Agent nodes."""
    return {"agents": await _agents().list_agents()}


@graph_router.get("/agents/{name}")
async def get_agent(name: str) -> Dict[str, Any]:
    """Get an Agent node by name."""
    agent = await _agents().get_agent(name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return agent


@graph_router.post("/agents", status_code=201)
async def upsert_agent(req: UpsertAgentRequest) -> Dict[str, Any]:
    """Create or update an Agent node."""
    await _agents().upsert_agent(
        name=req.name,
        agent_type=req.agent_type,
        capabilities=req.capabilities,
        metadata=req.metadata,
    )
    return {"status": "ok", "name": req.name}


@graph_router.post("/agents/dependency")
async def add_agent_dependency(req: AgentDependencyRequest) -> Dict[str, Any]:
    """Record a DEPENDS_ON edge between two agents."""
    await _agents().add_dependency(req.from_agent, req.to_agent, req.reason)
    return {"status": "ok"}


@graph_router.get("/agents/{name}/context")
async def get_agent_context(name: str) -> Dict[str, Any]:
    """Return the full cognitive context for an agent."""
    return await _qs().get_agent_context(name)


@graph_router.get("/agents/{name}/dependencies")
async def get_agent_dependencies(
    name: str,
    depth: int = Query(default=3, ge=1, le=10),
) -> Dict[str, Any]:
    """Return the transitive dependency chain for an agent."""
    deps = await _agents().get_agent_dependencies(name, depth=depth)
    return {"agent": name, "dependencies": deps}


@graph_router.get("/agents/{name}/centrality")
async def get_agent_centrality_single(name: str) -> Dict[str, Any]:
    """Return influence context (upstream/downstream) for an agent."""
    from backend.infrastructure.neo4j.traversal import graph_traversal
    return await graph_traversal.get_influence_graph(name)


@graph_router.get("/agents/graph/full")
async def get_full_agent_graph() -> Dict[str, Any]:
    """Return the full agent collaboration graph."""
    return await _qs().get_agent_graph()


@graph_router.get("/agents/graph/centrality")
async def get_graph_centrality(
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """Return agents ranked by graph centrality."""
    return {"centrality": await _qs().get_agent_centrality(limit=limit)}


# ===========================================================================
# MEMORY ENDPOINTS
# ===========================================================================

@graph_router.post("/memories", status_code=201)
async def upsert_memory(req: UpsertMemoryRequest) -> Dict[str, Any]:
    """Create or update a Memory node."""
    await _memories().upsert_memory(
        memory_id=req.memory_id,
        memory_type=req.memory_type,
        content=req.content,
        agent=req.agent,
        execution_id=req.execution_id,
        mission_id=req.mission_id,
        metadata=req.metadata,
    )
    return {"status": "ok", "memory_id": req.memory_id}


@graph_router.get("/memories/{memory_id}")
async def get_memory(memory_id: str) -> Dict[str, Any]:
    """Get a Memory node."""
    mem = await _memories().get_memory(memory_id)
    if mem is None:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")
    return mem


@graph_router.get("/memories/{memory_id}/related")
async def get_related_memories(
    memory_id: str,
    depth: int = Query(default=2, ge=1, le=5),
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """Return memories related to *memory_id*."""
    related = await _qs().get_related_memories(memory_id, depth=depth, limit=limit)
    return {"memory_id": memory_id, "related": related}


@graph_router.get("/memories/{memory_id}/context")
async def expand_memory_context(
    memory_id: str,
    depth: int = Query(default=2, ge=1, le=4),
) -> Dict[str, Any]:
    """Expand memory into multi-hop context."""
    context = await _qs().expand_memory_context(memory_id, depth=depth)
    return {"memory_id": memory_id, "context": context}


@graph_router.post("/memories/link")
async def link_memories(req: LinkMemoriesRequest) -> Dict[str, Any]:
    """Create a relationship between two Memory nodes."""
    await _memories().link_memories(
        source_id=req.source_id,
        target_id=req.target_id,
        rel_type=req.rel_type,
        weight=req.weight,
    )
    return {"status": "ok"}


@graph_router.get("/memories/search/fts")
async def search_memories(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=10, ge=1, le=50),
) -> Dict[str, Any]:
    """Full-text search over memory content."""
    results = await _qs().search_memories(q, limit=limit)
    return {"query": q, "results": results}


# ===========================================================================
# EXECUTION ENDPOINTS
# ===========================================================================

@graph_router.get("/executions/{execution_id}/lineage")
async def get_execution_lineage(
    execution_id: str,
    depth: int = Query(default=5, ge=1, le=20),
) -> Dict[str, Any]:
    """Return the execution lineage tree."""
    lineage = await _qs().get_execution_lineage(execution_id, depth=depth)
    return {"execution_id": execution_id, "lineage": lineage}


@graph_router.get("/executions/{execution_id}/impact")
async def get_execution_impact(
    execution_id: str,
    depth: int = Query(default=3, ge=1, le=10),
) -> Dict[str, Any]:
    """Return the full downstream impact of an execution."""
    return await _qs().get_execution_impact(execution_id, depth=depth)


@graph_router.get("/executions/{execution_id}/replay")
async def get_execution_replay(execution_id: str) -> Dict[str, Any]:
    """Return complete ordered lineage for replay."""
    lineage = await _qs().get_execution_replay_lineage(execution_id)
    return {"execution_id": execution_id, "replay_lineage": lineage}


@graph_router.get("/executions/recent")
async def get_recent_executions(
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Return recent executions."""
    execs = await _executions().get_recent_executions(limit=limit, status=status)
    return {"executions": execs}


@graph_router.get("/missions/{mission_id}")
async def get_mission_overview(mission_id: str) -> Dict[str, Any]:
    """Return execution summary for a mission."""
    return await _qs().get_mission_overview(mission_id)


# ===========================================================================
# COGNITION ENDPOINTS
# ===========================================================================

@graph_router.post("/cognition/events", status_code=201)
async def record_cognition_event(req: CognitionEventRequest) -> Dict[str, Any]:
    """Record a CognitionEvent node."""
    await _cognition().record_event(
        event_id=req.event_id,
        event_type=req.event_type,
        agent=req.agent,
        execution_id=req.execution_id,
        payload_summary=req.payload_summary,
    )
    return {"status": "ok", "event_id": req.event_id}


@graph_router.get("/cognition/events/{event_id}/pipeline")
async def get_cognition_pipeline(
    event_id: str,
    depth: int = Query(default=10, ge=1, le=30),
) -> Dict[str, Any]:
    """Return the downstream cognition pipeline from *event_id*."""
    pipeline = await _qs().get_cognition_pipeline(event_id, depth=depth)
    return {"event_id": event_id, "pipeline": pipeline}


@graph_router.post("/cognition/reflections", status_code=201)
async def record_reflection(req: ReflectionRequest) -> Dict[str, Any]:
    """Record a Reflection node."""
    await _cognition().record_reflection(
        reflection_id=req.reflection_id,
        agent=req.agent,
        summary=req.summary,
        execution_id=req.execution_id,
        memory_ids=req.memory_ids,
    )
    return {"status": "ok", "reflection_id": req.reflection_id}


@graph_router.get("/cognition/patterns")
async def get_collaboration_patterns() -> Dict[str, Any]:
    """Return agent collaboration patterns."""
    patterns = await _qs().get_collaboration_patterns()
    return {"patterns": patterns}


# ===========================================================================
# WORLD MODEL ENDPOINTS
# ===========================================================================

@graph_router.get("/world-models")
async def list_world_models() -> Dict[str, Any]:
    """List all WorldModel nodes."""
    models = await _world_models().list_world_models()
    return {"world_models": models}


@graph_router.post("/world-models", status_code=201)
async def upsert_world_model(req: UpsertWorldModelRequest) -> Dict[str, Any]:
    """Create or update a WorldModel node."""
    await _world_models().upsert_world_model(
        model_id=req.model_id,
        name=req.name,
        domain=req.domain,
        description=req.description,
    )
    return {"status": "ok", "model_id": req.model_id}


@graph_router.get("/world-models/{model_id}/subgraph")
async def get_world_model_subgraph(model_id: str) -> Dict[str, Any]:
    """Return the full concept graph for a WorldModel."""
    return await _qs().get_world_model_subgraph(model_id)


@graph_router.post("/concepts", status_code=201)
async def upsert_concept(req: UpsertConceptRequest) -> Dict[str, Any]:
    """Create or update a Concept node."""
    await _world_models().upsert_concept(
        name=req.name,
        domain=req.domain,
        description=req.description,
        confidence=req.confidence,
    )
    return {"status": "ok", "name": req.name}


@graph_router.post("/concepts/relate")
async def relate_concepts(req: RelateConceptsRequest) -> Dict[str, Any]:
    """Create a semantic relationship between two concepts."""
    await _world_models().relate_concepts(
        concept_a=req.concept_a,
        concept_b=req.concept_b,
        rel_type=req.rel_type,
        weight=req.weight,
        description=req.description,
    )
    return {"status": "ok"}


@graph_router.get("/concepts/{name}/neighborhood")
async def get_concept_neighborhood(
    name: str,
    depth: int = Query(default=2, ge=1, le=5),
    limit: int = Query(default=30, ge=1, le=100),
) -> Dict[str, Any]:
    """Return the semantic neighborhood of a concept."""
    return await _qs().get_semantic_neighborhood(name, depth=depth)


@graph_router.get("/concepts/search")
async def search_concepts(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=10, ge=1, le=50),
) -> Dict[str, Any]:
    """Full-text search over concepts."""
    results = await _qs().search_concepts(q, limit=limit)
    return {"query": q, "results": results}


# ===========================================================================
# CROSS-DOMAIN CONTEXT
# ===========================================================================

@graph_router.get("/context/{agent_name}")
async def get_full_cognitive_context(
    agent_name: str,
    execution_id: Optional[str] = Query(default=None),
    memory_depth: int = Query(default=2, ge=1, le=4),
) -> Dict[str, Any]:
    """Return the full cognitive context for an agent (cross-domain)."""
    return await _qs().get_full_cognitive_context(
        agent_name=agent_name,
        execution_id=execution_id,
        memory_depth=memory_depth,
    )


@graph_router.get("/path/agents")
async def shortest_path_between_agents(
    from_agent: str = Query(...),
    to_agent: str = Query(...),
    max_depth: int = Query(default=6, ge=2, le=15),
) -> Dict[str, Any]:
    """Find the shortest path(s) between two agents."""
    from backend.infrastructure.neo4j.traversal import graph_traversal
    paths = await graph_traversal.shortest_path_between_agents(
        from_agent=from_agent,
        to_agent=to_agent,
        max_depth=max_depth,
    )
    return {"from": from_agent, "to": to_agent, "paths": paths}
