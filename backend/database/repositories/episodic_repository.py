"""
EpisodicRepository — async CRUD + vector similarity search for episodic_memory.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.episodic_memory import EpisodicMemoryRecord
from backend.database.repositories.base import BaseRepository


class EpisodicRepository(BaseRepository[EpisodicMemoryRecord]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(EpisodicMemoryRecord, session)

    # ------------------------------------------------------------------
    # Domain reads
    # ------------------------------------------------------------------

    async def get_by_session(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[EpisodicMemoryRecord]:
        """Return recent events for a session, newest first."""
        result = await self._session.execute(
            select(EpisodicMemoryRecord)
            .where(EpisodicMemoryRecord.session_id == session_id)
            .order_by(EpisodicMemoryRecord.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_agent(
        self,
        agent: str,
        limit: int = 50,
    ) -> List[EpisodicMemoryRecord]:
        result = await self._session.execute(
            select(EpisodicMemoryRecord)
            .where(EpisodicMemoryRecord.agent == agent)
            .order_by(EpisodicMemoryRecord.created_at.desc())
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
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return episodic events ranked by cosine similarity to *embedding*.

        Uses the <=> (cosine distance) pgvector operator.
        similarity = 1 - cosine_distance

        Returns dicts with an extra ``similarity`` key.
        """
        embed_literal = f"[{','.join(str(v) for v in embedding)}]"

        where_parts = [
            "embedding IS NOT NULL",
            "1 - (embedding <=> CAST(:embedding AS vector)) >= :min_sim",
        ]
        params: Dict[str, Any] = {
            "embedding": embed_literal,
            "min_sim": min_similarity,
            "lim": limit,
        }

        if session_id:
            where_parts.append("session_id = :session_id")
            params["session_id"] = session_id

        where_sql = " AND ".join(where_parts)

        stmt = text(f"""
            SELECT
                id,
                session_id,
                agent,
                event_type,
                content,
                metadata,
                created_at,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM episodic_memory
            WHERE {where_sql}
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :lim
        """)

        rows = (await self._session.execute(stmt, params)).mappings().all()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Full-text fallback search
    # ------------------------------------------------------------------

    async def search_text(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """PostgreSQL full-text search fallback when embeddings are unavailable."""
        stmt = text("""
            SELECT
                id, session_id, agent, event_type, content, metadata, created_at,
                NULL::float AS similarity
            FROM episodic_memory
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :q)
            ORDER BY created_at DESC
            LIMIT :lim
        """)
        rows = (await self._session.execute(stmt, {"q": query, "lim": limit})).mappings().all()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    async def count_by_session(self, session_id: str) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(EpisodicMemoryRecord)
            .where(EpisodicMemoryRecord.session_id == session_id)
        )
        return result.scalar_one()
