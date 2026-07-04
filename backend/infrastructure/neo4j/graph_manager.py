from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

from backend.infrastructure.neo4j.connection import neo4j_connection
from backend.infrastructure.neo4j.schema import SCHEMA_STATEMENTS


# =========================================================
# NEO4J GRAPH MANAGER
# =========================================================

class Neo4jGraphManager:
    """
    Manages the cognitive agent graph in Neo4j.

    Tracks:
    - Agent nodes and their relationships
    - Execution lineage (parent → child executions)
    - Cognition relationships (which agent fed which)
    - Pipeline flow visualisation
    """

    # ---------------------------------------------------------
    # SCHEMA INIT
    # ---------------------------------------------------------

    async def ensure_schema(self) -> None:
        if not await neo4j_connection.ensure_connected():
            return

        async with neo4j_connection.driver.session() as session:
            for stmt in SCHEMA_STATEMENTS:
                try:
                    await session.run(stmt)
                except Exception:
                    pass  # Constraint/index already exists — idempotent

        log.info("✅ Neo4j schema ready")

    # ---------------------------------------------------------
    # UPSERT AGENT NODE
    # ---------------------------------------------------------

    async def upsert_agent(
        self,
        agent_name: str,
        agent_type: str,
        capabilities: List[str] = [],
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return

        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (a:Agent {name: $name})
                    SET a.type         = $type,
                        a.capabilities = $capabilities,
                        a.updated_at   = $updated_at
                    """,
                    name=agent_name,
                    type=agent_type,
                    capabilities=capabilities,
                    updated_at=datetime.utcnow().isoformat(),
                )
        except Exception as exc:
            log.warning("Neo4j upsert_agent failed: %s", exc)

    # ---------------------------------------------------------
    # CREATE EXECUTION NODE
    # ---------------------------------------------------------

    async def create_execution(
        self,
        execution_id: str,
        objective: str,
        priority: int = 5,
        parent_execution_id: Optional[str] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return

        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (e:Execution {execution_id: $execution_id})
                    SET e.objective  = $objective,
                        e.priority   = $priority,
                        e.status     = 'running',
                        e.started_at = $started_at
                    """,
                    execution_id=execution_id,
                    objective=objective,
                    priority=priority,
                    started_at=datetime.utcnow().isoformat(),
                )

                # Link to parent execution if provided
                if parent_execution_id:
                    await session.run(
                        """
                        MATCH (parent:Execution {execution_id: $parent_id})
                        MATCH (child:Execution  {execution_id: $child_id})
                        MERGE (parent)-[:SPAWNED]->(child)
                        """,
                        parent_id=parent_execution_id,
                        child_id=execution_id,
                    )
        except Exception as exc:
            log.warning("Neo4j create_execution failed: %s", exc)

    # ---------------------------------------------------------
    # RECORD AGENT EXECUTION
    # ---------------------------------------------------------

    async def record_agent_execution(
        self,
        execution_id: str,
        agent_name: str,
        stage: str,
        status: str = "completed",
        duration_ms: Optional[float] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return

        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MATCH (e:Execution {execution_id: $execution_id})
                    MATCH (a:Agent     {name: $agent_name})
                    MERGE (e)-[r:EXECUTED_BY {stage: $stage}]->(a)
                    SET r.status      = $status,
                        r.duration_ms = $duration_ms,
                        r.executed_at = $executed_at
                    """,
                    execution_id=execution_id,
                    agent_name=agent_name,
                    stage=stage,
                    status=status,
                    duration_ms=duration_ms,
                    executed_at=datetime.utcnow().isoformat(),
                )
        except Exception as exc:
            log.warning("Neo4j record_agent_execution failed: %s", exc)

    # ---------------------------------------------------------
    # RECORD COGNITION FLOW (Agent → Agent)
    # ---------------------------------------------------------

    async def record_cognition_flow(
        self,
        from_agent: str,
        to_agent: str,
        execution_id: str,
        relation: str = "FEEDS",
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return

        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MATCH (a:Agent {name: $from_agent})
                    MATCH (b:Agent {name: $to_agent})
                    MERGE (a)-[r:FEEDS {execution_id: $execution_id}]->(b)
                    SET r.relation = $relation,
                        r.at      = $at
                    """,
                    from_agent=from_agent,
                    to_agent=to_agent,
                    execution_id=execution_id,
                    relation=relation,
                    at=datetime.utcnow().isoformat(),
                )
        except Exception as exc:
            log.warning("Neo4j record_cognition_flow failed: %s", exc)

    # ---------------------------------------------------------
    # COMPLETE EXECUTION
    # ---------------------------------------------------------

    async def complete_execution(
        self,
        execution_id: str,
        status: str = "completed",
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return

        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MATCH (e:Execution {execution_id: $execution_id})
                    SET e.status       = $status,
                        e.completed_at = $completed_at
                    """,
                    execution_id=execution_id,
                    status=status,
                    completed_at=datetime.utcnow().isoformat(),
                )
        except Exception as exc:
            log.warning("Neo4j complete_execution failed: %s", exc)

    # ---------------------------------------------------------
    # GET EXECUTION LINEAGE
    # ---------------------------------------------------------

    async def get_execution_lineage(
        self,
        execution_id: str,
        depth: int = 5,
    ) -> List[Dict[str, Any]]:
        if not await neo4j_connection.ensure_connected():
            return []

        try:
            async with neo4j_connection.driver.session() as session:
                result = await session.run(
                    """
                    MATCH path = (root:Execution {execution_id: $execution_id})
                                 -[:SPAWNED*0..{depth}]->(child:Execution)
                    RETURN [n IN nodes(path) | n.execution_id] AS lineage
                    """,
                    execution_id=execution_id,
                    depth=depth,
                )
                records = await result.data()
                return records
        except Exception as exc:
            log.warning("Neo4j get_execution_lineage failed: %s", exc)
            return []

    # ---------------------------------------------------------
    # GET AGENT GRAPH
    # ---------------------------------------------------------

    async def get_agent_graph(self) -> Dict[str, Any]:
        if not await neo4j_connection.ensure_connected():
            return {"agents": [], "edges": []}

        try:
            async with neo4j_connection.driver.session() as session:
                # Agents
                agents_result = await session.run(
                    "MATCH (a:Agent) RETURN a.name AS name, a.type AS type"
                )
                agents = await agents_result.data()

                # Edges
                edges_result = await session.run(
                    """
                    MATCH (a:Agent)-[r:FEEDS]->(b:Agent)
                    RETURN a.name AS from, b.name AS to, count(r) AS weight
                    """
                )
                edges = await edges_result.data()

                return {"agents": agents, "edges": edges}
        except Exception as exc:
            log.warning("Neo4j get_agent_graph failed: %s", exc)
            return {"agents": [], "edges": []}

    # ---------------------------------------------------------
    # MEMORY NODE
    # ---------------------------------------------------------

    async def upsert_memory(
        self,
        memory_id: str,
        memory_type: str,
        content: str,
        agent: Optional[str] = None,
        execution_id: Optional[str] = None,
        mission_id: Optional[str] = None,
    ) -> None:
        """Delegate to memory_repository for graph persistence."""
        from backend.infrastructure.neo4j.repositories.memory_repository import (
            memory_repository,
        )
        await memory_repository.upsert_memory(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            agent=agent,
            execution_id=execution_id,
            mission_id=mission_id,
        )

    # ---------------------------------------------------------
    # CONCEPT NODE
    # ---------------------------------------------------------

    async def upsert_concept(
        self,
        name: str,
        domain: str = "general",
        description: str = "",
        confidence: float = 1.0,
    ) -> None:
        """Delegate to world_model_repository for graph persistence."""
        from backend.infrastructure.neo4j.repositories.world_model_repository import (
            world_model_repository,
        )
        await world_model_repository.upsert_concept(
            name=name,
            domain=domain,
            description=description,
            confidence=confidence,
        )

    # ---------------------------------------------------------
    # REFLECTION NODE
    # ---------------------------------------------------------

    async def record_reflection(
        self,
        reflection_id: str,
        agent: str,
        summary: str,
        execution_id: Optional[str] = None,
        memory_ids: Optional[List[str]] = None,
    ) -> None:
        """Delegate to cognition_repository for graph persistence."""
        from backend.infrastructure.neo4j.repositories.cognition_repository import (
            cognition_repository,
        )
        await cognition_repository.record_reflection(
            reflection_id=reflection_id,
            agent=agent,
            summary=summary,
            execution_id=execution_id,
            memory_ids=memory_ids,
        )

    # ---------------------------------------------------------
    # COGNITION EVENT
    # ---------------------------------------------------------

    async def record_cognition_event(
        self,
        event_id: str,
        event_type: str,
        agent: str,
        execution_id: Optional[str] = None,
        payload_summary: Optional[str] = None,
    ) -> None:
        """Delegate to cognition_repository."""
        from backend.infrastructure.neo4j.repositories.cognition_repository import (
            cognition_repository,
        )
        await cognition_repository.record_event(
            event_id=event_id,
            event_type=event_type,
            agent=agent,
            execution_id=execution_id,
            payload_summary=payload_summary,
        )


# =========================================================
# SINGLETON
# =========================================================

neo4j_graph = Neo4jGraphManager()
