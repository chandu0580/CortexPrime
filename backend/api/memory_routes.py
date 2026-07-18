"""
Memory API Routes — /api/memory/*

Exposes the CortexPrime Memory Orchestration Layer over REST.
All endpoints delegate to memory_orchestrator which coordinates the
underlying PostgreSQL, Redis, and Neo4j stores.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.memory.memory_orchestrator import memory_orchestrator
from backend.memory.models import (
    AssembledContext,
    MemoryType,
    ReflectRequest,
    SearchRequest,
    StoreMemoryRequest,
)

router = APIRouter(prefix="/api/memory", tags=["Memory"], dependencies=[Depends(require_user)])


# =========================================================
# ── STATUS ────────────────────────────────────────────────
# =========================================================

@router.get("/status", response_model=Dict[str, Any])
async def memory_status():
    """Return the availability status of each memory subsystem."""
    health = await memory_orchestrator.health()
    return {
        "status": "online",
        **health,
    }


# =========================================================
# ── STORE ─────────────────────────────────────────────────
# =========================================================

@router.post("/store", response_model=Dict[str, str])
async def store_memory(req: StoreMemoryRequest):
    """
    Store a memory entry in the appropriate store.

    - type=episodic   → episodic store (session-scoped event)
    - type=semantic   → semantic store (factual knowledge)
    - type=reflection → reflection store (agent self-critique)
    """
    if req.type == MemoryType.EPISODIC:
        mem_id = await memory_orchestrator.store_cognition_event(
            agent      = req.agent,
            event_type = req.event_type,
            content    = req.content,
            session_id = req.session_id or "global",
            mission_id = req.mission_id,
            metadata   = req.metadata,
        )

    elif req.type == MemoryType.SEMANTIC:
        mem_id = await memory_orchestrator.store_semantic_knowledge(
            concept    = req.concept or req.event_type,
            content    = req.content,
            agent      = req.agent,
            metadata   = req.metadata,
        )

    elif req.type == MemoryType.REFLECTION:
        mem_id = await memory_orchestrator.store_reflection(
            agent      = req.agent,
            reflection = req.content,
            mission_id = req.mission_id,
            metadata   = req.metadata,
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported memory type: {req.type}")

    return {"memory_id": mem_id, "type": req.type}


# =========================================================
# ── SEARCH ────────────────────────────────────────────────
# =========================================================

@router.post("/search", response_model=List[Dict[str, Any]])
async def search_memories(req: SearchRequest):
    """Multi-store semantic search across episodic and semantic memory."""
    return await memory_orchestrator.search_memories(
        query=req.query,
        n=req.n_results,
    )


@router.get("/search", response_model=List[Dict[str, Any]])
async def search_memories_get(
    q: str = Query(..., description="Search query"),
    n: int = Query(default=10, ge=1, le=50),
):
    """GET-friendly semantic search shortcut."""
    return await memory_orchestrator.search_memories(query=q, n=n)


# =========================================================
# ── CONTEXT ───────────────────────────────────────────────
# =========================================================

@router.get("/context/{session_id}", response_model=AssembledContext)
async def get_context(
    session_id: str,
    query:      Optional[str] = Query(default=None),
    n_episodic: int           = Query(default=10, ge=1, le=50),
    n_semantic: int           = Query(default=10, ge=1, le=50),
):
    """Assemble and return the full cognitive context for a session."""
    return await memory_orchestrator.retrieve_context(
        session_id = session_id,
        query      = query,
        config     = {"n_episodic": n_episodic, "n_semantic": n_semantic},
    )


# =========================================================
# ── EPISODIC ──────────────────────────────────────────────
# =========================================================

@router.get("/episodic/{session_id}", response_model=List[Dict[str, Any]])
async def get_episodic_memory(
    session_id: str,
    limit:      int = Query(default=50, ge=1, le=200),
):
    """Return recent episodic events for a session."""
    from backend.memory.stores.episodic_store import episodic_store

    entries = await episodic_store.get_session(session_id, limit=limit)
    return [e.model_dump() for e in entries]


# =========================================================
# ── SEMANTIC ──────────────────────────────────────────────
# =========================================================

@router.get("/semantic", response_model=List[Dict[str, Any]])
async def get_semantic_by_concept(
    concept: Optional[str] = Query(default=None),
    limit:   int           = Query(default=20, ge=1, le=100),
):
    """
    Look up semantic entries.
    - With ?concept=X  → exact concept lookup
    - Without concept  → return most recent entries (up to limit)
    """
    from backend.memory.stores.semantic_store import semantic_store

    if concept:
        entries = await semantic_store.get_by_concept(concept, limit=limit)
    else:
        # Recent semantic entries — fall back to search with empty query
        try:
            results = await semantic_store.search("", limit=limit)
            entries = results
        except Exception:
            entries = []
    return [e.model_dump() for e in entries]


# =========================================================
# ── REFLECTION ────────────────────────────────────────────
# =========================================================

@router.post("/reflect", response_model=Dict[str, str])
async def store_reflection(req: ReflectRequest):
    """Store a self-reflective cognitive entry."""
    mem_id = await memory_orchestrator.store_reflection(
        agent      = req.agent,
        reflection = req.reflection,
        mission_id = req.mission_id,
        score      = req.score,
        metadata   = req.metadata,
    )
    return {"memory_id": mem_id}


@router.get("/reflections/agent/{agent}", response_model=List[Dict[str, Any]])
async def get_agent_reflections(
    agent: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    from backend.memory.stores.reflection_store import reflection_store

    entries = await reflection_store.get_by_agent(agent, limit=limit)
    return [e.model_dump() for e in entries]


@router.get("/reflections/mission/{mission_id}", response_model=List[Dict[str, Any]])
async def get_mission_reflections(mission_id: str):
    from backend.memory.stores.reflection_store import reflection_store

    entries = await reflection_store.get_by_mission(mission_id)
    return [e.model_dump() for e in entries]


# =========================================================
# ── SESSION MANAGEMENT ────────────────────────────────────
# =========================================================

class InitSessionRequest(BaseModel):
    objective: Optional[str]       = None
    agents:    Optional[List[str]] = None


@router.post("/session/{session_id}/init", response_model=Dict[str, str])
async def init_session(session_id: str, req: InitSessionRequest):
    """Initialise a new cognitive session context."""
    await memory_orchestrator.init_session(
        session_id = session_id,
        objective  = req.objective,
        agents     = req.agents,
    )
    return {"session_id": session_id, "status": "initialised"}


@router.post("/session/{session_id}/consolidate", response_model=Dict[str, Any])
async def consolidate_session(session_id: str):
    """Consolidate session short-term memory into long-term semantic store."""
    mem_id = await memory_orchestrator.consolidate_session(session_id)
    if mem_id:
        return {"session_id": session_id, "semantic_memory_id": mem_id, "status": "consolidated"}
    return {"session_id": session_id, "status": "no_messages"}


# =========================================================
# ── GRAPH ─────────────────────────────────────────────────
# =========================================================

@router.get("/graph/lineage/{mission_id}", response_model=List[Dict[str, Any]])
async def get_execution_lineage(mission_id: str):
    """Return the cognitive execution lineage for a mission."""
    return await memory_orchestrator.get_memory_lineage(mission_id)


@router.get("/graph/related/{memory_id}", response_model=List[Dict[str, Any]])
async def get_related_memories(
    memory_id: str,
    depth:     int = Query(default=2, ge=1, le=4),
):
    """Return memories related to *memory_id* via graph traversal."""
    return await memory_orchestrator.get_related_memories(memory_id, depth=depth)
