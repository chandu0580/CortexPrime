"""
CortexPrime Memory Orchestrator.

Central facade that coordinates all memory sub-systems:
  - Episodic store    (PostgreSQL)
  - Semantic store    (PostgreSQL + pgvector)
  - Reflection store  (PostgreSQL)
  - Runtime context   (Redis)
  - Cognitive graph   (Neo4j)
  - Retrieval engine  (multi-source)
  - Compression engine

All agent memory operations should flow through this class so that
the correct stores are updated consistently and WebSocket events are
emitted for real-time UI updates.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.memory.models import (
    AssembledContext,
    EpisodicEntry,
    SemanticEntry,
    ReflectionEntry,
)
from backend.memory.stores.episodic_store       import episodic_store
from backend.memory.stores.semantic_store       import semantic_store
from backend.memory.stores.reflection_store     import reflection_store
from backend.memory.stores.context_store        import context_store
from backend.memory.graph.cognition_graph       import cognition_graph
from backend.memory.retrieval.retrieval_engine  import retrieval_engine, RetrievalConfig
from backend.memory.retrieval.compression_engine import compression_engine
from backend.events.event_bus                   import event_bus
from backend.events.event_models                import CognitionEvent

logger = logging.getLogger(__name__)


class MemoryOrchestrator:
    """
    Unified memory operations API.

    Every public method is async and safe to call from agent code.
    """

    # ==================================================================
    # STORE — Episodic
    # ==================================================================

    async def store_cognition_event(
        self,
        agent:      str,
        event_type: str,
        content:    str,
        session_id: str                      = "global",
        mission_id: Optional[str]            = None,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Persist a cognition event in episodic memory + cognitive graph.

        Call this after every significant agent action.  A WebSocket event
        is published asynchronously so the UI stays in sync.
        """
        meta = {**(metadata or {})}
        if mission_id:
            meta["mission_id"] = mission_id

        # Episodic store (primary)
        mem_id = await episodic_store.store(
            session_id=session_id,
            agent=agent,
            event_type=event_type,
            content=content,
            metadata=meta,
        )

        # Cognitive graph (fire-and-forget)
        asyncio.ensure_future(
            cognition_graph.create_memory_node(
                id=mem_id,
                type="episodic",
                agent=agent,
                content=content,
                session_id=session_id,
                mission_id=mission_id,
            )
        )

        # Append to active session context
        asyncio.ensure_future(
            context_store.append_message(session_id, {
                "agent":      agent,
                "event_type": event_type,
                "content":    content[:500],
                "memory_id":  mem_id,
            })
        )

        # WebSocket notification
        asyncio.ensure_future(
            event_bus.publish(CognitionEvent(
                agent      = agent,
                event_type = "MEMORY_STORED",
                status     = "completed",
                message    = f"Episodic memory stored: {content[:80]}",
                payload    = {"memory_id": mem_id, "session_id": session_id},
            ))
        )

        return mem_id

    # ==================================================================
    # STORE — Semantic
    # ==================================================================

    async def store_semantic_knowledge(
        self,
        concept:    str,
        content:    str,
        agent:      str                      = "system",
        source:     Optional[str]            = None,
        confidence: float                    = 1.0,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist a factual knowledge entry in semantic memory."""
        mem_id = await semantic_store.store(
            concept=concept,
            content=content,
            source=source,
            confidence=confidence,
            metadata=metadata,
        )
        asyncio.ensure_future(
            cognition_graph.create_memory_node(
                id=mem_id,
                type="semantic",
                agent=agent,
                content=content,
            )
        )
        return mem_id

    # ==================================================================
    # STORE — Reflection
    # ==================================================================

    async def store_reflection(
        self,
        agent:      str,
        reflection: str,
        mission_id: Optional[str]            = None,
        score:      Optional[float]          = None,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist a self-reflective cognitive entry."""
        mem_id = await reflection_store.store(
            agent=agent,
            reflection=reflection,
            mission_id=mission_id,
            score=score,
            metadata=metadata,
        )
        asyncio.ensure_future(
            cognition_graph.create_memory_node(
                id=mem_id,
                type="reflection",
                agent=agent,
                content=reflection,
                mission_id=mission_id,
            )
        )
        asyncio.ensure_future(
            event_bus.publish(CognitionEvent(
                agent      = agent,
                event_type = "REFLECTION_STORED",
                status     = "completed",
                message    = f"Reflection logged: {reflection[:80]}",
                payload    = {"memory_id": mem_id, "score": score},
            ))
        )
        return mem_id

    # ==================================================================
    # RETRIEVE — Context Assembly
    # ==================================================================

    async def retrieve_context(
        self,
        session_id: str,
        query:      Optional[str]            = None,
        config:     Optional[Dict[str, Any]] = None,
    ) -> AssembledContext:
        """
        Assemble full cognitive context for an agent query.

        Retrieves relevant episodic, semantic, and reflection memories,
        then applies compression if the combined context is too large.
        """
        cfg = RetrievalConfig(**(config or {}))
        ctx = await retrieval_engine.retrieve(query or "", session_id, cfg)

        compressed_ep, compressed_sm, was_compressed = (
            await compression_engine.compress_context(ctx.episodic, ctx.semantic)
        )
        ctx.episodic            = compressed_ep
        ctx.semantic            = compressed_sm
        ctx.compression_applied = was_compressed

        return ctx

    # ==================================================================
    # RETRIEVE — Semantic Search
    # ==================================================================

    async def search_memories(
        self,
        query: str,
        n:     int = 10,
    ) -> List[Dict[str, Any]]:
        """Fast multi-store semantic search for agent context injection."""
        return await retrieval_engine.quick_search(query, n)

    # ==================================================================
    # SESSION MANAGEMENT
    # ==================================================================

    async def init_session(
        self,
        session_id: str,
        objective:  Optional[str]       = None,
        agents:     Optional[List[str]] = None,
    ) -> None:
        """Initialise a new cognitive session in Redis context store."""
        if objective:
            await context_store.set_objective(session_id, objective)
        if agents:
            await context_store.set_active_agents(session_id, agents)

    async def consolidate_session(self, session_id: str) -> Optional[str]:
        """
        Consolidate short-term session memory → long-term semantic store.

        Summarises the session history and stores the result as a semantic
        knowledge entry.  Returns the new semantic memory ID.
        """
        messages = await context_store.get_messages(session_id, n=50)
        if not messages:
            return None

        narrative = "\n".join(
            f"[{m.get('agent', '?')}] {m.get('content', '')}"
            for m in reversed(messages)
        )
        summary = await compression_engine.summarize(narrative, max_tokens=300)

        mem_id = await self.store_semantic_knowledge(
            concept    = f"Session {session_id} summary",
            content    = summary,
            agent      = "memory_orchestrator",
            source     = f"session:{session_id}",
            metadata   = {
                "session_id":    session_id,
                "message_count": len(messages),
            },
        )
        logger.info(f"Session {session_id} consolidated → memory {mem_id}")
        return mem_id

    # ==================================================================
    # GRAPH OPERATIONS
    # ==================================================================

    async def link_execution(
        self,
        parent_memory_id: str,
        child_memory_id:  str,
        agent:            str,
        step:             int = 0,
    ) -> None:
        await cognition_graph.record_execution_step(
            parent_id=parent_memory_id,
            child_id=child_memory_id,
            agent=agent,
            step_number=step,
        )

    async def get_memory_lineage(
        self,
        mission_id: str,
    ) -> List[Dict[str, Any]]:
        return await cognition_graph.get_execution_lineage(mission_id)

    async def get_related_memories(
        self,
        memory_id: str,
        depth:     int = 2,
    ) -> List[Dict[str, Any]]:
        return await cognition_graph.get_related(memory_id, depth)

    # ==================================================================
    # INFRASTRUCTURE
    # ==================================================================

    async def health(self) -> Dict[str, Any]:
        """Return availability status of each memory subsystem."""
        from backend.memory.db.postgres_client import postgres_client
        from backend.memory.db.redis_client    import redis_client
        from backend.memory.db.neo4j_client    import neo4j_client
        from backend.memory.embedding_pipeline import embedding_pipeline

        return {
            "postgres":   postgres_client.is_available,
            "redis":      redis_client.is_available,
            "neo4j":      neo4j_client.is_available,
            "embeddings": embedding_pipeline.backend,
        }


# =========================================================
# SINGLETON
# =========================================================

memory_orchestrator = MemoryOrchestrator()
