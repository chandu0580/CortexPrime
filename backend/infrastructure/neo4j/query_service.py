"""
Graph Query Service
===================
High-level façade that composes repositories and traversal algorithms
into domain-oriented query operations.

This is the primary entry point for application-layer code that needs
graph intelligence.  Callers should use this service rather than
importing individual repositories directly.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.repositories.agent_repository import (
    AgentRepository,
    agent_repository,
)
from backend.infrastructure.neo4j.repositories.cognition_repository import (
    CognitionRepository,
    cognition_repository,
)
from backend.infrastructure.neo4j.repositories.execution_repository import (
    ExecutionRepository,
    execution_repository,
)
from backend.infrastructure.neo4j.repositories.memory_repository import (
    MemoryRepository,
    memory_repository,
)
from backend.infrastructure.neo4j.repositories.world_model_repository import (
    WorldModelRepository,
    world_model_repository,
)
from backend.infrastructure.neo4j.traversal import GraphTraversal, graph_traversal

log = logging.getLogger(__name__)


class GraphQueryService:
    """
    Unified interface for graph-backed intelligence queries.

    All methods are safe to call even when Neo4j is unavailable;
    they return empty defaults in that case.
    """

    def __init__(
        self,
        agents: AgentRepository,
        executions: ExecutionRepository,
        memories: MemoryRepository,
        cognition: CognitionRepository,
        world_models: WorldModelRepository,
        traversal: GraphTraversal,
    ) -> None:
        self._agents      = agents
        self._executions  = executions
        self._memories    = memories
        self._cognition   = cognition
        self._wm          = world_models
        self._traversal   = traversal

    # ------------------------------------------------------------------
    # Agent intelligence
    # ------------------------------------------------------------------

    async def get_agent_context(self, agent_name: str) -> Dict[str, Any]:
        """
        Build a rich context object for an agent:
        - Agent metadata
        - Dependency chain
        - Collaboration partners
        - Recent cognition history
        - Influence graph
        """
        agent        = await self._agents.get_agent(agent_name)
        deps         = await self._agents.get_agent_dependencies(agent_name)
        partners     = await self._agents.get_collaboration_partners(agent_name)
        cognition_h  = await self._cognition.get_agent_cognition_history(agent_name, limit=10)
        influence    = await self._traversal.get_influence_graph(agent_name, depth=2)
        reflections  = await self._cognition.get_reflections_for_agent(agent_name, limit=5)

        return {
            "agent": agent,
            "dependencies": deps,
            "collaboration_partners": partners,
            "recent_cognition": cognition_h,
            "influence": influence,
            "recent_reflections": reflections,
        }

    async def get_agent_graph(self) -> Dict[str, Any]:
        """Return the full agent collaboration and dependency graph."""
        return await self._agents.get_agent_graph()

    async def get_agent_centrality(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return agents ranked by graph centrality."""
        return await self._traversal.get_agent_centrality(limit=limit)

    # ------------------------------------------------------------------
    # Memory intelligence
    # ------------------------------------------------------------------

    async def get_related_memories(
        self,
        memory_id: str,
        depth: int = 2,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return memories semantically/causally related to *memory_id*."""
        return await self._memories.get_related_memories(memory_id, depth=depth, limit=limit)

    async def expand_memory_context(
        self,
        memory_id: str,
        depth: int = 2,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """Expand memory into multi-hop context (memories + concepts + executions)."""
        return await self._traversal.expand_memory_context(memory_id, depth=depth, limit=limit)

    async def get_agent_memory_summary(
        self, agent_name: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return recent memories produced by *agent_name*."""
        return await self._memories.get_agent_memories(agent_name, limit=limit)

    async def search_memories(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search over memory content."""
        return await self._memories.fulltext_search(query, limit=limit)

    # ------------------------------------------------------------------
    # Execution intelligence
    # ------------------------------------------------------------------

    async def get_execution_lineage(
        self, execution_id: str, depth: int = 5
    ) -> List[Dict[str, Any]]:
        """Return the execution lineage tree rooted at *execution_id*."""
        return await self._executions.get_execution_lineage(execution_id, depth=depth)

    async def get_execution_impact(
        self, execution_id: str, depth: int = 3
    ) -> Dict[str, Any]:
        """Analyse the full downstream impact of an execution."""
        return await self._traversal.get_execution_impact(execution_id, depth=depth)

    async def get_execution_replay_lineage(
        self, execution_id: str
    ) -> List[Dict[str, Any]]:
        """Return complete ordered lineage for execution replay."""
        return await self._traversal.get_execution_replay_lineage(execution_id)

    async def get_mission_overview(self, mission_id: str) -> Dict[str, Any]:
        """Return execution list + memory summary for a mission."""
        executions = await self._executions.get_mission_executions(mission_id)
        return {
            "mission_id": mission_id,
            "executions": executions,
            "execution_count": len(executions),
        }

    # ------------------------------------------------------------------
    # Cognition intelligence
    # ------------------------------------------------------------------

    async def get_cognition_pipeline(
        self, event_id: str, depth: int = 10
    ) -> List[Dict[str, Any]]:
        """Return the downstream cognition pipeline from *event_id*."""
        return await self._cognition.get_cognition_pipeline(event_id, depth=depth)

    async def get_collaboration_patterns(self) -> List[Dict[str, Any]]:
        """Return agent pairs ranked by cognition event co-occurrence."""
        return await self._cognition.get_agent_collaboration_patterns()

    # ------------------------------------------------------------------
    # World model intelligence
    # ------------------------------------------------------------------

    async def get_world_model_subgraph(self, model_id: str) -> Dict[str, Any]:
        """Return the full concept graph for a WorldModel."""
        return await self._wm.get_world_model_subgraph(model_id)

    async def get_semantic_neighborhood(
        self, concept_name: str, depth: int = 2
    ) -> Dict[str, Any]:
        """Return the full semantic neighborhood of a concept."""
        return await self._traversal.get_semantic_neighborhood(
            concept_name, depth=depth
        )

    async def search_concepts(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Full-text search over world-model concepts."""
        return await self._wm.search_concepts(query, limit=limit)

    # ------------------------------------------------------------------
    # Cross-domain: agent + memory + world model
    # ------------------------------------------------------------------

    async def get_full_cognitive_context(
        self,
        agent_name: str,
        execution_id: Optional[str] = None,
        memory_depth: int = 2,
    ) -> Dict[str, Any]:
        """
        Assemble the richest possible cognitive context for an agent,
        optionally anchored to an execution.

        Returns:
          - Agent node + influence graph
          - Recent memories + related memory expansion
          - Recent cognition history
          - Execution lineage (if execution_id provided)
        """
        agent_ctx    = await self.get_agent_context(agent_name)
        recent_mems  = await self._memories.get_agent_memories(agent_name, limit=10)

        memory_context: List[Dict[str, Any]] = []
        for mem in recent_mems[:3]:
            expanded = await self._traversal.expand_memory_context(
                mem.get("memory_id", ""), depth=memory_depth, limit=15
            )
            memory_context.extend(expanded)

        exec_lineage: List[Dict[str, Any]] = []
        if execution_id:
            exec_lineage = await self._executions.get_execution_lineage(execution_id)

        return {
            "agent": agent_ctx,
            "recent_memories": recent_mems,
            "memory_context": memory_context,
            "execution_lineage": exec_lineage,
        }

    # ------------------------------------------------------------------
    # Health / stats
    # ------------------------------------------------------------------

    async def get_graph_stats(self) -> Dict[str, Any]:
        """Return basic graph statistics (node/edge counts)."""
        agents       = await self._agents.list_agents()
        world_models = await self._wm.list_world_models()
        recent_execs = await self._executions.get_recent_executions(limit=5)

        return {
            "agent_count": len(agents),
            "world_model_count": len(world_models),
            "recent_executions": recent_execs,
        }


# Singleton
graph_query_service = GraphQueryService(
    agents=agent_repository,
    executions=execution_repository,
    memories=memory_repository,
    cognition=cognition_repository,
    world_models=world_model_repository,
    traversal=graph_traversal,
)
