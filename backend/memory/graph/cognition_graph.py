"""
CortexPrime Cognitive Graph — Neo4j.

Models memory nodes, agent nodes, and mission nodes with typed
relationships so the system can traverse execution lineage, find
related memories, and understand agent collaboration patterns.

Node labels  : Memory, Agent, Mission
Relationships: PRODUCED, PART_OF, RELATED_TO, TRIGGERED
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.memory.db.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


class CognitionGraph:
    """
    Cognitive relationship graph backed by Neo4j.

    All methods are no-ops when Neo4j is unavailable; callers do not
    need to check availability — the methods return empty lists / None.
    """

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    async def ensure_constraints(self) -> None:
        """Idempotent constraint creation — call once at startup."""
        statements = [
            "CREATE CONSTRAINT memory_id IF NOT EXISTS "
            "FOR (m:Memory) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT mission_id IF NOT EXISTS "
            "FOR (ms:Mission) REQUIRE ms.id IS UNIQUE",
            "CREATE CONSTRAINT agent_id IF NOT EXISTS "
            "FOR (a:Agent) REQUIRE a.id IS UNIQUE",
        ]
        for stmt in statements:
            try:
                await neo4j_client.run(stmt)
            except Exception as exc:
                logger.debug(f"Constraint skipped: {exc}")

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    async def create_memory_node(
        self,
        id:         str,
        type:       str,
        agent:      str,
        content:    str,
        session_id: Optional[str] = None,
        mission_id: Optional[str] = None,
    ) -> None:
        await neo4j_client.run(
            """
            MERGE (m:Memory {id: $id})
            SET m.type       = $type,
                m.agent      = $agent,
                m.content    = $content,
                m.session_id = $session_id,
                m.mission_id = $mission_id,
                m.created_at = timestamp()
            """,
            id=id,
            type=type,
            agent=agent,
            content=content[:500],
            session_id=session_id,
            mission_id=mission_id,
        )
        # Link to Agent node
        await neo4j_client.run(
            """
            MERGE (a:Agent {id: $agent_id})
            WITH a
            MATCH (m:Memory {id: $mem_id})
            MERGE (a)-[:PRODUCED]->(m)
            """,
            agent_id=agent,
            mem_id=id,
        )

    async def create_mission_node(
        self,
        mission_id: str,
        objective:  str,
        status:     str = "active",
    ) -> None:
        await neo4j_client.run(
            """
            MERGE (ms:Mission {id: $mission_id})
            SET ms.objective  = $objective,
                ms.status     = $status,
                ms.created_at = timestamp()
            """,
            mission_id=mission_id,
            objective=objective[:500],
            status=status,
        )

    # ------------------------------------------------------------------
    # Relationship management
    # ------------------------------------------------------------------

    async def link_memories(
        self,
        source_id:  str,
        target_id:  str,
        rel_type:   str                      = "RELATED_TO",
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        props = {k: str(v) for k, v in (properties or {}).items()}
        # rel_type must be a valid Cypher identifier (no injection risk
        # from internal code, but we sanitise anyway)
        safe_rel = rel_type.upper().replace(" ", "_").replace("-", "_")
        await neo4j_client.run(
            f"""
            MATCH (a:Memory {{id: $source_id}})
            MATCH (b:Memory {{id: $target_id}})
            MERGE (a)-[r:{safe_rel}]->(b)
            SET r += $props
            """,
            source_id=source_id,
            target_id=target_id,
            props=props,
        )

    async def link_to_mission(
        self,
        memory_id:  str,
        mission_id: str,
    ) -> None:
        await neo4j_client.run(
            """
            MATCH (m:Memory  {id: $mem_id})
            MATCH (ms:Mission {id: $mis_id})
            MERGE (m)-[:PART_OF]->(ms)
            """,
            mem_id=memory_id,
            mis_id=mission_id,
        )

    async def record_execution_step(
        self,
        parent_id:   str,
        child_id:    str,
        agent:       str,
        step_number: int = 0,
    ) -> None:
        await neo4j_client.run(
            """
            MATCH (p:Memory {id: $parent_id})
            MATCH (c:Memory {id: $child_id})
            MERGE (p)-[r:TRIGGERED]->(c)
            SET r.agent       = $agent,
                r.step_number = $step_number,
                r.created_at  = timestamp()
            """,
            parent_id=parent_id,
            child_id=child_id,
            agent=agent,
            step_number=step_number,
        )

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    async def get_related(
        self,
        memory_id: str,
        depth:     int = 2,
        limit:     int = 20,
    ) -> List[Dict[str, Any]]:
        """Return nodes reachable from *memory_id* within *depth* hops."""
        return await neo4j_client.run(
            """
            MATCH path = (start:Memory {id: $id})-[*1..$depth]-(related:Memory)
            RETURN DISTINCT
                   related.id      AS id,
                   related.type    AS type,
                   related.agent   AS agent,
                   related.content AS content,
                   length(path)    AS distance
            ORDER BY distance ASC
            LIMIT $limit
            """,
            id=memory_id,
            depth=depth,
            limit=limit,
        )

    async def get_execution_lineage(
        self,
        mission_id: str,
        limit:      int = 50,
    ) -> List[Dict[str, Any]]:
        """Return memory nodes that belong to a mission, ordered by depth."""
        return await neo4j_client.run(
            """
            MATCH (ms:Mission {id: $mission_id})<-[:PART_OF]-(m:Memory)
            OPTIONAL MATCH (m)<-[:TRIGGERED*]-(parent:Memory)
            RETURN m.id      AS id,
                   m.type    AS type,
                   m.agent   AS agent,
                   m.content AS content,
                   count(parent) AS depth
            ORDER BY depth ASC
            LIMIT $limit
            """,
            mission_id=mission_id,
            limit=limit,
        )

    async def get_agent_memory_graph(
        self,
        agent: str,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """Return all memories produced by *agent* with their first relationship."""
        return await neo4j_client.run(
            """
            MATCH (a:Agent {id: $agent})-[:PRODUCED]->(m:Memory)
            OPTIONAL MATCH (m)-[r]->(related:Memory)
            RETURN m.id       AS id,
                   m.type     AS type,
                   m.content  AS content,
                   type(r)    AS rel_type,
                   related.id AS related_id
            LIMIT $limit
            """,
            agent=agent,
            limit=limit,
        )


cognition_graph = CognitionGraph()
