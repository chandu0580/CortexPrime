"""
ReflectionRepository — async CRUD + vector similarity search for reflection_history.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.reflection_history import ReflectionHistoryRecord
from backend.database.repositories.base import BaseRepository


class ReflectionRepository(BaseRepository[ReflectionHistoryRecord]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ReflectionHistoryRecord, session)

    # ------------------------------------------------------------------
    # Domain reads
    # ------------------------------------------------------------------

    async def get_by_mission(
        self,
        mission_id: uuid.UUID,
    ) -> List[ReflectionHistoryRecord]:
        result = await self._session.execute(
            select(ReflectionHistoryRecord)
            .where(ReflectionHistoryRecord.mission_id == mission_id)
            .order_by(ReflectionHistoryRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_agent(
        self,
        agent: str,
        limit: int = 20,
    ) -> List[ReflectionHistoryRecord]:
        result = await self._session.execute(
            select(ReflectionHistoryRecord)
            .where(ReflectionHistoryRecord.agent == agent)
            .order_by(ReflectionHistoryRecord.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_top_scored(
        self,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> List[ReflectionHistoryRecord]:
        """Return highest-scored reflections across all agents."""
        result = await self._session.execute(
            select(ReflectionHistoryRecord)
            .where(ReflectionHistoryRecord.score >= min_score)
            .order_by(ReflectionHistoryRecord.score.desc())
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
        agent: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Cosine similarity search over reflection embeddings."""
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

        if agent:
            where_parts.append("agent = :agent")
            params["agent"] = agent

        where_sql = " AND ".join(where_parts)

        stmt = text(f"""
            SELECT
                id, mission_id, agent, reflection, score, metadata, created_at,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM reflection_history
            WHERE {where_sql}
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :lim
        """)

        rows = (await self._session.execute(stmt, params)).mappings().all()
        return [dict(r) for r in rows]
