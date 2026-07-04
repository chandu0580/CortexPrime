"""
Execution Repository
====================
Manages Execution nodes, mission linkage, stage tracking, and
parent→child lineage chains.

Merge key: Execution.execution_id (unique constraint in schema.py)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.repositories.base_repository import BaseRepository
from backend.infrastructure.neo4j.schema import Rels


class ExecutionRepository(BaseRepository):
    """Graph persistence for Execution nodes and lineage."""

    # ------------------------------------------------------------------
    # Create / update
    # ------------------------------------------------------------------

    async def create_execution(
        self,
        execution_id: str,
        objective: str,
        priority: int = 5,
        parent_id: Optional[str] = None,
        mission_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create an Execution node.  If *parent_id* is given, a SPAWNED
        edge from the parent is created automatically.
        If *mission_id* is given, a PART_OF edge to the Mission is added.
        """
        extra = metadata or {}
        await self._execute(
            """
            MERGE (e:Execution {execution_id: $execution_id})
            SET e.objective  = $objective,
                e.priority   = $priority,
                e.status     = 'running',
                e.created_at = $created_at
            SET e += $extra
            """,
            execution_id=execution_id,
            objective=objective[:500],
            priority=priority,
            created_at=datetime.utcnow().isoformat(),
            extra=extra,
        )

        if parent_id:
            await self._execute(
                f"""
                MATCH (p:Execution {{execution_id: $parent_id}})
                MATCH (c:Execution {{execution_id: $child_id}})
                MERGE (p)-[r:{Rels.SPAWNED}]->(c)
                SET r.created_at = $created_at
                """,
                parent_id=parent_id,
                child_id=execution_id,
                created_at=datetime.utcnow().isoformat(),
            )

        if mission_id:
            await self._execute(
                f"""
                MATCH (e:Execution {{execution_id: $execution_id}})
                MERGE (ms:Mission {{mission_id: $mission_id}})
                MERGE (e)-[r:{Rels.PART_OF}]->(ms)
                SET r.created_at = $created_at
                """,
                execution_id=execution_id,
                mission_id=mission_id,
                created_at=datetime.utcnow().isoformat(),
            )

    async def complete_execution(
        self,
        execution_id: str,
        status: str = "completed",
        duration_ms: Optional[int] = None,
    ) -> None:
        """Mark an execution as completed (or failed)."""
        await self._execute(
            """
            MATCH (e:Execution {execution_id: $execution_id})
            SET e.status       = $status,
                e.completed_at = $completed_at,
                e.duration_ms  = $duration_ms
            """,
            execution_id=execution_id,
            status=status,
            completed_at=datetime.utcnow().isoformat(),
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Stage / agent tracking
    # ------------------------------------------------------------------

    async def record_stage(
        self,
        execution_id: str,
        agent_name: str,
        stage: str,
        status: str,
        duration_ms: Optional[int] = None,
    ) -> None:
        """
        Attach a stage record to an Execution and create an
        EXECUTED_BY relationship to the handling Agent.
        """
        await self._execute(
            f"""
            MATCH (e:Execution {{execution_id: $execution_id}})
            MERGE (a:Agent {{name: $agent_name}})
            MERGE (e)-[r:{Rels.EXECUTED_BY} {{stage: $stage}}]->(a)
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

    # ------------------------------------------------------------------
    # Mission nodes
    # ------------------------------------------------------------------

    async def upsert_mission(
        self,
        mission_id: str,
        objective: str,
        status: str = "active",
    ) -> None:
        """Create or update a Mission node."""
        await self._execute(
            """
            MERGE (ms:Mission {mission_id: $mission_id})
            SET ms.objective  = $objective,
                ms.status     = $status,
                ms.updated_at = $updated_at
            """,
            mission_id=mission_id,
            objective=objective[:500],
            status=status,
            updated_at=datetime.utcnow().isoformat(),
        )

    async def complete_mission(
        self, mission_id: str, status: str = "completed"
    ) -> None:
        """Mark a Mission node as completed."""
        await self._execute(
            """
            MATCH (ms:Mission {mission_id: $mission_id})
            SET ms.status       = $status,
                ms.completed_at = $completed_at
            """,
            mission_id=mission_id,
            status=status,
            completed_at=datetime.utcnow().isoformat(),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_execution(
        self, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the Execution node dict or None."""
        return await self._run_single(
            "MATCH (e:Execution {execution_id: $execution_id}) RETURN e{.*} AS execution",
            execution_id=execution_id,
        )

    async def get_execution_lineage(
        self, execution_id: str, depth: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Return the full descendant tree (SPAWNED*0..depth) rooted at
        *execution_id*.  Each row contains the ordered list of
        execution_ids along the path.
        """
        return await self._run(
            f"""
            MATCH path = (root:Execution {{execution_id: $execution_id}})
                         -[:{Rels.SPAWNED}*0..$depth]->(child:Execution)
            RETURN [n IN nodes(path) | n.execution_id] AS lineage,
                   length(path) AS depth,
                   child.execution_id AS leaf_id,
                   child.status AS leaf_status
            ORDER BY depth
            """,
            execution_id=execution_id,
            depth=depth,
        )

    async def get_ancestor_chain(
        self, execution_id: str, depth: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Return the ancestor chain (reverse SPAWNED*0..depth) up to root.
        """
        return await self._run(
            f"""
            MATCH path = (child:Execution {{execution_id: $execution_id}})
                         <-[:{Rels.SPAWNED}*0..$depth]-(ancestor:Execution)
            RETURN ancestor.execution_id AS execution_id,
                   ancestor.objective    AS objective,
                   ancestor.status       AS status,
                   length(path)          AS depth
            ORDER BY depth
            """,
            execution_id=execution_id,
            depth=depth,
        )

    async def get_mission_executions(
        self, mission_id: str
    ) -> List[Dict[str, Any]]:
        """Return all Execution nodes belonging to a Mission."""
        return await self._run(
            f"""
            MATCH (e:Execution)-[:{Rels.PART_OF}]->(ms:Mission {{mission_id: $mission_id}})
            RETURN e.execution_id AS execution_id,
                   e.objective    AS objective,
                   e.status       AS status,
                   e.created_at   AS created_at,
                   e.duration_ms  AS duration_ms
            ORDER BY e.created_at
            """,
            mission_id=mission_id,
        )

    async def get_agent_executions(
        self, agent_name: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Return recent executions handled by *agent_name*."""
        return await self._run(
            f"""
            MATCH (e:Execution)-[r:{Rels.EXECUTED_BY}]->(a:Agent {{name: $agent_name}})
            RETURN e.execution_id AS execution_id,
                   e.objective    AS objective,
                   r.stage        AS stage,
                   r.status       AS status,
                   r.duration_ms  AS duration_ms,
                   r.executed_at  AS executed_at
            ORDER BY r.executed_at DESC
            LIMIT $limit
            """,
            agent_name=agent_name,
            limit=limit,
        )

    async def get_recent_executions(
        self, limit: int = 50, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return recent executions optionally filtered by status."""
        if status:
            return await self._run(
                """
                MATCH (e:Execution {status: $status})
                RETURN e.execution_id AS execution_id,
                       e.objective    AS objective,
                       e.status       AS status,
                       e.created_at   AS created_at
                ORDER BY e.created_at DESC
                LIMIT $limit
                """,
                status=status,
                limit=limit,
            )
        return await self._run(
            """
            MATCH (e:Execution)
            RETURN e.execution_id AS execution_id,
                   e.objective    AS objective,
                   e.status       AS status,
                   e.created_at   AS created_at
            ORDER BY e.created_at DESC
            LIMIT $limit
            """,
            limit=limit,
        )


# Singleton
execution_repository = ExecutionRepository()
