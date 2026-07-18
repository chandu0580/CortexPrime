"""
SemanticRepository — async CRUD + vector similarity search for semantic_memory.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.semantic_memory import SemanticMemoryRecord
from backend.database.repositories.base import BaseRepository


class SemanticRepository(BaseRepository[SemanticMemoryRecord]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SemanticMemoryRecord, session)

    # ------------------------------------------------------------------
    # Domain reads
    # ------------------------------------------------------------------

    async def get_by_concept(
        self,
        concept: str,
        limit: int = 10,
    ) -> List[SemanticMemoryRecord]:
        """Case-insensitive prefix / exact match on concept."""
        result = await self._session.execute(
            select(SemanticMemoryRecord)
            .where(SemanticMemoryRecord.concept.ilike(f"%{concept}%"))
            .order_by(SemanticMemoryRecord.confidence.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_high_confidence(
        self,
        threshold: float = 0.8,
        limit: int = 50,
    ) -> List[SemanticMemoryRecord]:
        result = await self._session.execute(
            select(SemanticMemoryRecord)
            .where(SemanticMemoryRecord.confidence >= threshold)
            .order_by(SemanticMemoryRecord.confidence.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Vector similarity search
    # ------------------------------------------------------------------

    async def search_similar(
        self,
        embedding: List[float],
        limit: int = 10,
        min_similarity: float = 0.0,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Cosine similarity search over semantic concepts.

        Returns dicts with a ``similarity`` key (0–1, higher is more similar).
        """
        embed_literal = f"[{','.join(str(v) for v in embedding)}]"

        stmt = text("""
            SELECT
                id,
                concept,
                content,
                source,
                confidence,
                metadata,
                created_at,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM semantic_memory
            WHERE embedding IS NOT NULL
              AND confidence >= :min_conf
              AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_sim
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :lim
        """)

        rows = (await self._session.execute(
            stmt, {
                "embedding": embed_literal,
                "min_conf": min_confidence,
                "min_sim": min_similarity,
                "lim": limit,
            }
        )).mappings().all()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Hybrid search (vector + full-text re-rank)
    # ------------------------------------------------------------------

    async def hybrid_search(
        self,
        query: str,
        embedding: Optional[List[float]],
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Run both vector search and full-text search, merge and deduplicate
        results, then sort by combined score.
        """
        results: Dict[str, Dict[str, Any]] = {}

        if embedding:
            for row in await self.search_similar(embedding, limit=limit, min_confidence=min_confidence):
                results[str(row["id"])] = {**row, "score": float(row.get("similarity", 0))}

        # Full-text search
        fts_stmt = text("""
            SELECT
                id, concept, content, source, confidence, metadata, created_at,
                NULL::float AS similarity
            FROM semantic_memory
            WHERE to_tsvector('english', concept || ' ' || content)
                  @@ plainto_tsquery('english', :q)
              AND confidence >= :min_conf
            ORDER BY confidence DESC
            LIMIT :lim
        """)
        fts_rows = (
            await self._session.execute(
                fts_stmt, {"q": query, "min_conf": min_confidence, "lim": limit}
            )
        ).mappings().all()

        for row in fts_rows:
            rid = str(row["id"])
            if rid not in results:
                results[rid] = {**dict(row), "score": float(row.get("confidence", 0) * 0.5)}

        return sorted(results.values(), key=lambda r: r["score"], reverse=True)[:limit]
