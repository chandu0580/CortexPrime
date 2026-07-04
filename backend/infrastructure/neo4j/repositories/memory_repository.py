"""
Memory Repository
=================
Graph persistence for Memory nodes (episodic, semantic, working,
reflection) and the relationships that connect them to agents,
executions, missions, and concepts.

Merge key: Memory.memory_id (unique constraint in schema.py)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.repositories.base_repository import BaseRepository
from backend.infrastructure.neo4j.schema import Rels


class MemoryRepository(BaseRepository):
    """Graph persistence for Memory nodes and their relationships."""

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    async def upsert_memory(
        self,
        memory_id: str,
        memory_type: str,           # episodic | semantic | working | reflection
        content: str,
        agent: Optional[str] = None,
        execution_id: Optional[str] = None,
        mission_id: Optional[str] = None,
        embedding_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create or update a Memory node.
        Automatically creates PRODUCED, PART_OF relationships if
        *agent* / *execution_id* / *mission_id* are provided.
        """
        extra = metadata or {}
        await self._execute(
            """
            MERGE (m:Memory {memory_id: $memory_id})
            SET m.type           = $memory_type,
                m.content        = $content,
                m.agent          = $agent,
                m.execution_id   = $execution_id,
                m.embedding_hash = $embedding_hash,
                m.created_at     = coalesce(m.created_at, $created_at),
                m.updated_at     = $updated_at
            SET m += $extra
            """,
            memory_id=memory_id,
            memory_type=memory_type,
            content=content[:1000],
            agent=agent,
            execution_id=execution_id,
            embedding_hash=embedding_hash,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            extra=extra,
        )

        if agent:
            await self._execute(
                f"""
                MERGE (a:Agent {{name: $agent}})
                WITH a
                MATCH (m:Memory {{memory_id: $memory_id}})
                MERGE (a)-[r:{Rels.PRODUCED}]->(m)
                SET r.created_at = $created_at
                """,
                agent=agent,
                memory_id=memory_id,
                created_at=datetime.utcnow().isoformat(),
            )

        if execution_id:
            await self._execute(
                f"""
                MATCH (m:Memory {{memory_id: $memory_id}})
                MERGE (e:Execution {{execution_id: $execution_id}})
                MERGE (m)-[r:{Rels.PART_OF}]->(e)
                SET r.created_at = $created_at
                """,
                memory_id=memory_id,
                execution_id=execution_id,
                created_at=datetime.utcnow().isoformat(),
            )

        if mission_id:
            await self._execute(
                f"""
                MATCH (m:Memory {{memory_id: $memory_id}})
                MERGE (ms:Mission {{mission_id: $mission_id}})
                MERGE (m)-[r:{Rels.PART_OF}]->(ms)
                SET r.created_at = $created_at
                """,
                memory_id=memory_id,
                mission_id=mission_id,
                created_at=datetime.utcnow().isoformat(),
            )

    # ------------------------------------------------------------------
    # Relationship management
    # ------------------------------------------------------------------

    async def link_memories(
        self,
        source_id: str,
        target_id: str,
        rel_type: str = Rels.RELATED_TO,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create a directional relationship between two Memory nodes.
        rel_type must be one of the Rels constants (sanitised before use).
        """
        # Sanitise to prevent Cypher injection from internal callers
        safe_rel = rel_type.upper().replace(" ", "_").replace("-", "_")[:64]
        props = metadata or {}
        await self._execute(
            f"""
            MATCH (a:Memory {{memory_id: $source_id}})
            MATCH (b:Memory {{memory_id: $target_id}})
            MERGE (a)-[r:{safe_rel}]->(b)
            SET r.weight     = $weight,
                r.created_at = $created_at
            SET r += $props
            """,
            source_id=source_id,
            target_id=target_id,
            weight=weight,
            created_at=datetime.utcnow().isoformat(),
            props=props,
        )

    async def add_similarity_edge(
        self,
        memory_id_a: str,
        memory_id_b: str,
        similarity_score: float,
    ) -> None:
        """Add or update a semantic similarity edge between two memories."""
        await self._execute(
            f"""
            MATCH (a:Memory {{memory_id: $id_a}})
            MATCH (b:Memory {{memory_id: $id_b}})
            MERGE (a)-[r:{Rels.SIMILAR_TO}]-(b)
            SET r.score      = $score,
                r.updated_at = $updated_at
            """,
            id_a=memory_id_a,
            id_b=memory_id_b,
            score=similarity_score,
            updated_at=datetime.utcnow().isoformat(),
        )

    async def record_retrieval(
        self,
        memory_id: str,
        agent_name: str,
        execution_id: Optional[str] = None,
    ) -> None:
        """Record that an agent retrieved a memory (usage tracking)."""
        await self._execute(
            f"""
            MATCH (m:Memory {{memory_id: $memory_id}})
            MERGE (a:Agent {{name: $agent_name}})
            CREATE (m)-[r:{Rels.RETRIEVED_BY}]->(a)
            SET r.execution_id = $execution_id,
                r.retrieved_at = $retrieved_at
            """,
            memory_id=memory_id,
            agent_name=agent_name,
            execution_id=execution_id,
            retrieved_at=datetime.utcnow().isoformat(),
        )

    async def link_to_concept(
        self,
        memory_id: str,
        concept_name: str,
    ) -> None:
        """Create an INSTANCE_OF edge from a Memory to a Concept."""
        await self._execute(
            f"""
            MATCH (m:Memory {{memory_id: $memory_id}})
            MERGE (c:Concept {{name: $concept_name}})
            MERGE (m)-[r:{Rels.INSTANCE_OF}]->(c)
            SET r.created_at = $created_at
            """,
            memory_id=memory_id,
            concept_name=concept_name,
            created_at=datetime.utcnow().isoformat(),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Return the Memory node dict, or None."""
        return await self._run_single(
            "MATCH (m:Memory {memory_id: $memory_id}) RETURN m{.*} AS memory",
            memory_id=memory_id,
        )

    async def get_related_memories(
        self,
        memory_id: str,
        depth: int = 2,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return memories reachable from *memory_id* within *depth* hops."""
        return await self._run(
            """
            MATCH path = (start:Memory {memory_id: $memory_id})
                         -[*1..$depth]-(related:Memory)
            WHERE related.memory_id <> $memory_id
            RETURN DISTINCT
                   related.memory_id AS memory_id,
                   related.type      AS type,
                   related.agent     AS agent,
                   related.content   AS content,
                   length(path)      AS distance
            ORDER BY distance ASC
            LIMIT $limit
            """,
            memory_id=memory_id,
            depth=depth,
            limit=limit,
        )

    async def get_agent_memories(
        self,
        agent_name: str,
        memory_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return memories produced by *agent_name*, optionally filtered by type."""
        if memory_type:
            return await self._run(
                f"""
                MATCH (a:Agent {{name: $agent_name}})-[:{Rels.PRODUCED}]->(m:Memory {{type: $memory_type}})
                RETURN m.memory_id AS memory_id,
                       m.type      AS type,
                       m.content   AS content,
                       m.created_at AS created_at
                ORDER BY m.created_at DESC
                LIMIT $limit
                """,
                agent_name=agent_name,
                memory_type=memory_type,
                limit=limit,
            )
        return await self._run(
            f"""
            MATCH (a:Agent {{name: $agent_name}})-[:{Rels.PRODUCED}]->(m:Memory)
            RETURN m.memory_id AS memory_id,
                   m.type      AS type,
                   m.content   AS content,
                   m.created_at AS created_at
            ORDER BY m.created_at DESC
            LIMIT $limit
            """,
            agent_name=agent_name,
            limit=limit,
        )

    async def get_execution_memories(
        self, execution_id: str
    ) -> List[Dict[str, Any]]:
        """Return all memories linked to an execution."""
        return await self._run(
            f"""
            MATCH (m:Memory)-[:{Rels.PART_OF}]->(e:Execution {{execution_id: $execution_id}})
            RETURN m.memory_id AS memory_id,
                   m.type      AS type,
                   m.agent     AS agent,
                   m.content   AS content
            ORDER BY m.created_at ASC
            """,
            execution_id=execution_id,
        )

    async def get_similar_memories(
        self,
        memory_id: str,
        min_score: float = 0.7,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return memories with high similarity to *memory_id*."""
        return await self._run(
            f"""
            MATCH (m:Memory {{memory_id: $memory_id}})
                  -[r:{Rels.SIMILAR_TO}]-(similar:Memory)
            WHERE r.score >= $min_score
            RETURN similar.memory_id AS memory_id,
                   similar.type      AS type,
                   similar.content   AS content,
                   r.score           AS score
            ORDER BY r.score DESC
            LIMIT $limit
            """,
            memory_id=memory_id,
            min_score=min_score,
            limit=limit,
        )

    async def fulltext_search(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Full-text search over Memory.content using the
        ``memory_content_fts`` index created in schema.py.
        """
        return await self._run(
            """
            CALL db.index.fulltext.queryNodes('memory_content_fts', $query)
            YIELD node, score
            RETURN node.memory_id AS memory_id,
                   node.type      AS type,
                   node.agent     AS agent,
                   node.content   AS content,
                   score
            ORDER BY score DESC
            LIMIT $limit
            """,
            query=query,
            limit=limit,
        )


# Singleton
memory_repository = MemoryRepository()
