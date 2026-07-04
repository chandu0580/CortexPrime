"""
Agent Repository
================
CRUD operations for Agent nodes plus agent-dependency and
collaboration relationship management.

Merge key: Agent.name (unique constraint enforced in schema.py)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.repositories.base_repository import BaseRepository
from backend.infrastructure.neo4j.schema import Labels, Rels


class AgentRepository(BaseRepository):
    """Graph persistence for Agent nodes and inter-agent edges."""

    # ------------------------------------------------------------------
    # Upsert / create
    # ------------------------------------------------------------------

    async def upsert_agent(
        self,
        name: str,
        agent_type: str,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create or update an Agent node.
        ``capabilities`` is stored as a list property.
        ``metadata`` keys are merged as extra properties.
        """
        extra = metadata or {}
        await self._execute(
            """
            MERGE (a:Agent {name: $name})
            SET a.type         = $agent_type,
                a.capabilities = $capabilities,
                a.updated_at   = $updated_at
            SET a += $extra
            """,
            name=name,
            agent_type=agent_type,
            capabilities=capabilities or [],
            updated_at=datetime.utcnow().isoformat(),
            extra=extra,
        )

    # ------------------------------------------------------------------
    # Dependency edges
    # ------------------------------------------------------------------

    async def add_dependency(
        self,
        from_agent: str,
        to_agent: str,
        reason: str = "",
    ) -> None:
        """Record that *from_agent* statically depends on *to_agent*."""
        await self._execute(
            f"""
            MERGE (a:Agent {{name: $from_agent}})
            MERGE (b:Agent {{name: $to_agent}})
            MERGE (a)-[r:{Rels.DEPENDS_ON}]->(b)
            SET r.reason     = $reason,
                r.created_at = $created_at
            """,
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            created_at=datetime.utcnow().isoformat(),
        )

    async def record_feeds(
        self,
        from_agent: str,
        to_agent: str,
        execution_id: str,
        relation: str = "output",
    ) -> None:
        """
        Record a runtime data-flow edge (agent output consumed by another).
        One edge per execution to preserve lineage without duplication.
        """
        await self._execute(
            f"""
            MERGE (a:Agent {{name: $from_agent}})
            MERGE (b:Agent {{name: $to_agent}})
            MERGE (a)-[r:{Rels.FEEDS} {{execution_id: $execution_id}}]->(b)
            SET r.relation   = $relation,
                r.updated_at = $updated_at
            """,
            from_agent=from_agent,
            to_agent=to_agent,
            execution_id=execution_id,
            relation=relation,
            updated_at=datetime.utcnow().isoformat(),
        )

    async def record_collaboration(
        self,
        agent_a: str,
        agent_b: str,
        execution_id: str,
    ) -> None:
        """Record that two agents collaborated on the same execution."""
        await self._execute(
            f"""
            MERGE (a:Agent {{name: $agent_a}})
            MERGE (b:Agent {{name: $agent_b}})
            MERGE (a)-[r:{Rels.COLLABORATES} {{execution_id: $execution_id}}]->(b)
            SET r.created_at = $created_at
            """,
            agent_a=agent_a,
            agent_b=agent_b,
            execution_id=execution_id,
            created_at=datetime.utcnow().isoformat(),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """Return the Agent node dict, or None if not found."""
        return await self._run_single(
            "MATCH (a:Agent {name: $name}) RETURN a{.*} AS agent",
            name=name,
        )

    async def list_agents(self) -> List[Dict[str, Any]]:
        """Return all Agent nodes."""
        rows = await self._run(
            "MATCH (a:Agent) RETURN a.name AS name, a.type AS type, "
            "a.capabilities AS capabilities ORDER BY a.name"
        )
        return rows

    async def get_agent_graph(self) -> Dict[str, Any]:
        """
        Return the full agent collaboration graph: nodes + weighted edges.
        Weight = number of distinct executions on the FEEDS relationship.
        """
        agents = await self._run(
            "MATCH (a:Agent) RETURN a.name AS name, a.type AS type, "
            "a.capabilities AS capabilities"
        )
        edges = await self._run(
            f"""
            MATCH (a:Agent)-[r:{Rels.FEEDS}]->(b:Agent)
            RETURN a.name AS source,
                   b.name AS target,
                   count(r) AS weight,
                   collect(DISTINCT r.relation) AS relations
            """
        )
        deps = await self._run(
            f"""
            MATCH (a:Agent)-[r:{Rels.DEPENDS_ON}]->(b:Agent)
            RETURN a.name AS source, b.name AS target, r.reason AS reason
            """
        )
        return {"agents": agents, "feeds": edges, "depends_on": deps}

    async def get_agent_dependencies(
        self, name: str, depth: int = 3
    ) -> List[Dict[str, Any]]:
        """Return transitive DEPENDS_ON chain up to *depth* hops."""
        return await self._run(
            f"""
            MATCH path = (a:Agent {{name: $name}})
                         -[:{Rels.DEPENDS_ON}*1..$depth]->(dep:Agent)
            RETURN dep.name AS name,
                   dep.type AS type,
                   length(path) AS depth
            ORDER BY depth
            """,
            name=name,
            depth=depth,
        )

    async def get_collaboration_partners(
        self, name: str
    ) -> List[Dict[str, Any]]:
        """Return agents that have collaborated with *name*."""
        return await self._run(
            f"""
            MATCH (a:Agent {{name: $name}})
                  -[r:{Rels.COLLABORATES}]-(partner:Agent)
            RETURN partner.name AS name,
                   partner.type AS type,
                   count(r) AS collaborations
            ORDER BY collaborations DESC
            """,
            name=name,
        )

    async def get_most_active_agents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return agents ranked by outgoing FEEDS edge count."""
        return await self._run(
            f"""
            MATCH (a:Agent)-[r:{Rels.FEEDS}]->()
            RETURN a.name AS name, a.type AS type, count(r) AS activity
            ORDER BY activity DESC
            LIMIT $limit
            """,
            limit=limit,
        )

    async def delete_agent(self, name: str) -> None:
        """Remove an Agent node and all its relationships."""
        await self._execute(
            "MATCH (a:Agent {name: $name}) DETACH DELETE a",
            name=name,
        )


# Singleton
agent_repository = AgentRepository()
