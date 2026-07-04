"""
EmbeddingCacheRepository — async CRUD for the persistent embedding cache.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.embedding_cache import EmbeddingCacheRecord
from backend.database.repositories.base      import BaseRepository


class EmbeddingCacheRepository(BaseRepository[EmbeddingCacheRecord]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(EmbeddingCacheRecord, session)

    async def get_by_hash(self, text_hash: str) -> Optional[EmbeddingCacheRecord]:
        result = await self._session.execute(
            select(EmbeddingCacheRecord)
            .where(EmbeddingCacheRecord.text_hash == text_hash)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        model: str,
        text: str,
        embedding: List[float],
    ) -> str:
        """
        Insert or ignore an embedding cache entry.
        Returns the text_hash key.
        """
        text_hash    = EmbeddingCacheRecord.make_hash(model, text)
        text_preview = text[:512]

        stmt = (
            pg_insert(EmbeddingCacheRecord)
            .values(
                text_hash    = text_hash,
                model        = model,
                text_preview = text_preview,
                embedding    = embedding,
            )
            .on_conflict_do_nothing(index_elements=["text_hash"])
        )
        await self._session.execute(stmt)
        return text_hash
