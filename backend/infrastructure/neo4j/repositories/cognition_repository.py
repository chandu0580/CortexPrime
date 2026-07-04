"""
Cognition Repository
====================
Manages CognitionEvent nodes and the pipeline-flow edges that model
how cognitive signals propagate through the agent network.

Merge key: CognitionEvent.event_id (unique constraint in schema.py)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.repositories.base_repository import BaseRepository
from backend.infrastructure.neo4j.schema import Rels


class CognitionRepository(BaseRepository):
    """Graph persistence for CognitionEvent nodes and pipeline flows."""

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    async def record_event(
        self,
        event_id: str,
        event_type: str,
        agent: str,
        execution_id: Optional[str] = None,
        payload_summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a cognition event.
        Automatically creates TRIGGERED_COGNITION from Execution if
        *execution_id* is provided.
        Also creates EXECUTED_BY from the event to the Agent.
        """
        extra = metadata or {}
        await self._execute(
            """
            MERGE (ce:CognitionEvent {event_id: $event_id})
            SET ce.event_type      = $event_type,
                ce.agent           = $agent,
                ce.execution_id    = $execution_id,
                ce.payload_summary = $payload_summary,
                ce.created_at      = coalesce(ce.created_at, $created_at)
            SET ce += $extra
            """,
            event_id=event_id,
            event_type=event_type,
            agent=agent,
            execution_id=execution_id,
            payload_summary=(payload_summary or "")[:500],
            created_at=datetime.utcnow().isoformat(),
            extra=extra,
        )

        # Link to agent
        await self._execute(
            f"""
            MERGE (a:Agent {{name: $agent}})
            WITH a
            MATCH (ce:CognitionEvent {{event_id: $event_id}})
            MERGE (ce)-[r:{Rels.EXECUTED_BY}]->(a)
            SET r.created_at = $created_at
            """,
            agent=agent,
            event_id=event_id,
            created_at=datetime.utcnow().isoformat(),
        )

        # Link to execution
        if execution_id:
            await self._execute(
                f"""
                MERGE (e:Execution {{execution_id: $execution_id}})
                WITH e
                MATCH (ce:CognitionEvent {{event_id: $event_id}})
                MERGE (e)-[r:{Rels.TRIGGERED_COGNITION}]->(ce)
                SET r.created_at = $created_at
                """,
                execution_id=execution_id,
                event_id=event_id,
                created_at=datetime.utcnow().isoformat(),
            )

    async def record_flow(
        self,
        from_event_id: str,
        to_event_id: str,
        flow_type: str = "pipeline",
        latency_ms: Optional[int] = None,
    ) -> None:
        """
        Record a FLOWS_TO edge between two CognitionEvents.
        Models how a cognition signal propagates through the pipeline.
        """
        await self._execute(
            f"""
            MATCH (a:CognitionEvent {{event_id: $from_id}})
            MATCH (b:CognitionEvent {{event_id: $to_id}})
            MERGE (a)-[r:{Rels.FLOWS_TO}]->(b)
            SET r.flow_type  = $flow_type,
                r.latency_ms = $latency_ms,
                r.created_at = $created_at
            """,
            from_id=from_event_id,
            to_id=to_event_id,
            flow_type=flow_type,
            latency_ms=latency_ms,
            created_at=datetime.utcnow().isoformat(),
        )

    async def record_agent_cognition_flow(
        self,
        from_agent: str,
        to_agent: str,
        execution_id: str,
        relation: str = "FEEDS",
    ) -> None:
        """
        Record an agent-level cognition data-flow (wraps agent_repository
        pattern but kept here for convenience from cognition pipeline callers).
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

    # ------------------------------------------------------------------
    # Reflection nodes
    # ------------------------------------------------------------------

    async def record_reflection(
        self,
        reflection_id: str,
        agent: str,
        summary: str,
        execution_id: Optional[str] = None,
        memory_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Persist a Reflection node and link it to agent, execution,
        and source memories.
        """
        extra = metadata or {}
        await self._execute(
            """
            MERGE (r:Reflection {reflection_id: $reflection_id})
            SET r.agent      = $agent,
                r.summary    = $summary,
                r.created_at = coalesce(r.created_at, $created_at)
            SET r += $extra
            """,
            reflection_id=reflection_id,
            agent=agent,
            summary=summary[:1000],
            created_at=datetime.utcnow().isoformat(),
            extra=extra,
        )

        await self._execute(
            f"""
            MERGE (a:Agent {{name: $agent}})
            WITH a
            MATCH (r:Reflection {{reflection_id: $reflection_id}})
            MERGE (r)-[rel:{Rels.EXECUTED_BY}]->(a)
            SET rel.created_at = $created_at
            """,
            agent=agent,
            reflection_id=reflection_id,
            created_at=datetime.utcnow().isoformat(),
        )

        if execution_id:
            await self._execute(
                f"""
                MATCH (r:Reflection {{reflection_id: $reflection_id}})
                MERGE (e:Execution {{execution_id: $execution_id}})
                MERGE (r)-[rel:{Rels.REFLECTS_ON}]->(e)
                SET rel.created_at = $created_at
                """,
                reflection_id=reflection_id,
                execution_id=execution_id,
                created_at=datetime.utcnow().isoformat(),
            )

        for mem_id in memory_ids or []:
            await self._execute(
                f"""
                MATCH (r:Reflection {{reflection_id: $reflection_id}})
                MATCH (m:Memory {{memory_id: $memory_id}})
                MERGE (r)-[rel:{Rels.REFLECTS_ON}]->(m)
                SET rel.created_at = $created_at
                """,
                reflection_id=reflection_id,
                memory_id=mem_id,
                created_at=datetime.utcnow().isoformat(),
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_events_for_execution(
        self, execution_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return all CognitionEvents triggered by an execution."""
        return await self._run(
            f"""
            MATCH (e:Execution {{execution_id: $execution_id}})
                  -[:{Rels.TRIGGERED_COGNITION}]->(ce:CognitionEvent)
            RETURN ce.event_id        AS event_id,
                   ce.event_type      AS event_type,
                   ce.agent           AS agent,
                   ce.payload_summary AS payload_summary,
                   ce.created_at      AS created_at
            ORDER BY ce.created_at ASC
            LIMIT $limit
            """,
            execution_id=execution_id,
            limit=limit,
        )

    async def get_cognition_pipeline(
        self, event_id: str, depth: int = 10
    ) -> List[Dict[str, Any]]:
        """Return the downstream FLOWS_TO chain from *event_id*."""
        return await self._run(
            f"""
            MATCH path = (start:CognitionEvent {{event_id: $event_id}})
                         -[:{Rels.FLOWS_TO}*1..$depth]->(ce:CognitionEvent)
            RETURN ce.event_id   AS event_id,
                   ce.event_type AS event_type,
                   ce.agent      AS agent,
                   length(path)  AS hop
            ORDER BY hop ASC
            """,
            event_id=event_id,
            depth=depth,
        )

    async def get_agent_cognition_history(
        self, agent_name: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Return recent cognition events for *agent_name*."""
        return await self._run(
            f"""
            MATCH (ce:CognitionEvent {{agent: $agent_name}})
            RETURN ce.event_id        AS event_id,
                   ce.event_type      AS event_type,
                   ce.execution_id    AS execution_id,
                   ce.payload_summary AS payload_summary,
                   ce.created_at      AS created_at
            ORDER BY ce.created_at DESC
            LIMIT $limit
            """,
            agent_name=agent_name,
            limit=limit,
        )

    async def get_reflections_for_agent(
        self, agent_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return recent reflections authored by *agent_name*."""
        return await self._run(
            """
            MATCH (r:Reflection {agent: $agent_name})
            RETURN r.reflection_id AS reflection_id,
                   r.summary       AS summary,
                   r.created_at    AS created_at
            ORDER BY r.created_at DESC
            LIMIT $limit
            """,
            agent_name=agent_name,
            limit=limit,
        )

    async def get_agent_collaboration_patterns(self) -> List[Dict[str, Any]]:
        """
        Return agent pairs ranked by cognition event co-occurrence.
        Useful for identifying which agents frequently work together.
        """
        return await self._run(
            f"""
            MATCH (a:Agent)-[:{Rels.FEEDS}]->(b:Agent)
            RETURN a.name AS from_agent,
                   b.name AS to_agent,
                   count(*) AS event_count
            ORDER BY event_count DESC
            LIMIT 50
            """
        )


# Singleton
cognition_repository = CognitionRepository()
