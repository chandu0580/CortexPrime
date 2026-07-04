"""
World Model Repository
======================
Manages WorldModel nodes, Concept nodes, and the semantic relationships
between them.  The world model is the system's structured representation
of domain knowledge — concepts, their definitions, and their
inter-relationships.

Merge keys:
  WorldModel.model_id (unique constraint in schema.py)
  Concept.name        (unique constraint in schema.py)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.repositories.base_repository import BaseRepository
from backend.infrastructure.neo4j.schema import Rels


class WorldModelRepository(BaseRepository):
    """Graph persistence for WorldModel and Concept nodes."""

    # ------------------------------------------------------------------
    # WorldModel nodes
    # ------------------------------------------------------------------

    async def upsert_world_model(
        self,
        model_id: str,
        name: str,
        domain: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create or update a WorldModel node."""
        extra = metadata or {}
        await self._execute(
            """
            MERGE (wm:WorldModel {model_id: $model_id})
            SET wm.name        = $name,
                wm.domain      = $domain,
                wm.description = $description,
                wm.updated_at  = $updated_at,
                wm.created_at  = coalesce(wm.created_at, $updated_at)
            SET wm += $extra
            """,
            model_id=model_id,
            name=name,
            domain=domain,
            description=description[:500],
            updated_at=datetime.utcnow().isoformat(),
            extra=extra,
        )

    async def mark_model_updated_by_execution(
        self,
        model_id: str,
        execution_id: str,
    ) -> None:
        """Record that an execution informed/updated a WorldModel."""
        await self._execute(
            f"""
            MATCH (wm:WorldModel {{model_id: $model_id}})
            MERGE (e:Execution {{execution_id: $execution_id}})
            MERGE (wm)-[r:{Rels.INFORMED_BY}]->(e)
            SET r.created_at = $created_at
            """,
            model_id=model_id,
            execution_id=execution_id,
            created_at=datetime.utcnow().isoformat(),
        )

    # ------------------------------------------------------------------
    # Concept nodes
    # ------------------------------------------------------------------

    async def upsert_concept(
        self,
        name: str,
        domain: str = "general",
        description: str = "",
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create or update a Concept node."""
        extra = metadata or {}
        await self._execute(
            """
            MERGE (c:Concept {name: $name})
            SET c.domain      = $domain,
                c.description = $description,
                c.confidence  = $confidence,
                c.updated_at  = $updated_at,
                c.created_at  = coalesce(c.created_at, $updated_at)
            SET c += $extra
            """,
            name=name,
            domain=domain,
            description=description[:500],
            confidence=confidence,
            updated_at=datetime.utcnow().isoformat(),
            extra=extra,
        )

    async def link_concept_to_model(
        self, concept_name: str, model_id: str
    ) -> None:
        """Create PART_OF_MODEL edge: Concept → WorldModel."""
        await self._execute(
            f"""
            MATCH (c:Concept {{name: $concept_name}})
            MERGE (wm:WorldModel {{model_id: $model_id}})
            MERGE (c)-[r:{Rels.PART_OF_MODEL}]->(wm)
            SET r.created_at = $created_at
            """,
            concept_name=concept_name,
            model_id=model_id,
            created_at=datetime.utcnow().isoformat(),
        )

    async def relate_concepts(
        self,
        concept_a: str,
        concept_b: str,
        rel_type: str = Rels.RELATED_TO,
        weight: float = 1.0,
        description: str = "",
    ) -> None:
        """
        Create a semantic relationship between two Concepts.
        *rel_type* must be a valid Rels constant or a safe identifier.
        """
        safe_rel = rel_type.upper().replace(" ", "_").replace("-", "_")[:64]
        await self._execute(
            f"""
            MERGE (a:Concept {{name: $concept_a}})
            MERGE (b:Concept {{name: $concept_b}})
            MERGE (a)-[r:{safe_rel}]->(b)
            SET r.weight      = $weight,
                r.description = $description,
                r.updated_at  = $updated_at
            """,
            concept_a=concept_a,
            concept_b=concept_b,
            weight=weight,
            description=description[:200],
            updated_at=datetime.utcnow().isoformat(),
        )

    async def extract_concepts_from_execution(
        self,
        execution_id: str,
        concepts: List[str],
        model_id: Optional[str] = None,
    ) -> None:
        """
        Bulk-upsert concepts discovered during an execution, linking
        each to the execution and optionally to a world model.
        """
        for concept in concepts:
            await self.upsert_concept(name=concept)
            # Link concept → execution
            await self._execute(
                f"""
                MATCH (c:Concept {{name: $concept}})
                MERGE (e:Execution {{execution_id: $execution_id}})
                MERGE (c)-[r:{Rels.INFORMED_BY}]->(e)
                SET r.created_at = $created_at
                """,
                concept=concept,
                execution_id=execution_id,
                created_at=datetime.utcnow().isoformat(),
            )
            if model_id:
                await self.link_concept_to_model(concept, model_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_world_model(
        self, model_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return a WorldModel node dict or None."""
        return await self._run_single(
            "MATCH (wm:WorldModel {model_id: $model_id}) RETURN wm{.*} AS model",
            model_id=model_id,
        )

    async def get_concept(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a Concept node dict or None."""
        return await self._run_single(
            "MATCH (c:Concept {name: $name}) RETURN c{.*} AS concept",
            name=name,
        )

    async def get_model_concepts(
        self, model_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Return all Concept nodes belonging to a WorldModel."""
        return await self._run(
            f"""
            MATCH (c:Concept)-[:{Rels.PART_OF_MODEL}]->(wm:WorldModel {{model_id: $model_id}})
            RETURN c.name        AS name,
                   c.domain      AS domain,
                   c.description AS description,
                   c.confidence  AS confidence
            ORDER BY c.name
            LIMIT $limit
            """,
            model_id=model_id,
            limit=limit,
        )

    async def get_concept_neighborhood(
        self,
        concept_name: str,
        depth: int = 2,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """Return concepts reachable from *concept_name* within *depth* hops."""
        return await self._run(
            """
            MATCH path = (start:Concept {name: $concept_name})
                         -[*1..$depth]-(related:Concept)
            WHERE related.name <> $concept_name
            RETURN DISTINCT
                   related.name        AS name,
                   related.domain      AS domain,
                   related.description AS description,
                   length(path)        AS distance
            ORDER BY distance ASC
            LIMIT $limit
            """,
            concept_name=concept_name,
            depth=depth,
            limit=limit,
        )

    async def get_world_model_subgraph(
        self, model_id: str
    ) -> Dict[str, Any]:
        """Return the full concept graph for a WorldModel."""
        concepts = await self.get_model_concepts(model_id)
        edges = await self._run(
            f"""
            MATCH (a:Concept)-[r]->(b:Concept)
            WHERE (a)-[:{Rels.PART_OF_MODEL}]->(:WorldModel {{model_id: $model_id}})
            RETURN a.name AS source,
                   b.name AS target,
                   type(r) AS rel_type,
                   r.weight AS weight
            """,
            model_id=model_id,
        )
        return {"concepts": concepts, "edges": edges, "model_id": model_id}

    async def search_concepts(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Full-text search over Concept names and descriptions."""
        return await self._run(
            """
            CALL db.index.fulltext.queryNodes('concept_desc_fts', $query)
            YIELD node, score
            RETURN node.name        AS name,
                   node.domain      AS domain,
                   node.description AS description,
                   score
            ORDER BY score DESC
            LIMIT $limit
            """,
            query=query,
            limit=limit,
        )

    async def list_world_models(self) -> List[Dict[str, Any]]:
        """Return all WorldModel nodes."""
        return await self._run(
            """
            MATCH (wm:WorldModel)
            RETURN wm.model_id   AS model_id,
                   wm.name       AS name,
                   wm.domain     AS domain,
                   wm.updated_at AS updated_at
            ORDER BY wm.name
            """
        )


# Singleton
world_model_repository = WorldModelRepository()
