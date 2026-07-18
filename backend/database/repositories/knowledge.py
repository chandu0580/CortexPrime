from __future__ import annotations

from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, Index, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository

_EMBED_DIM = 1536


class KnowledgeEntryModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_entries"

    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True, default=list)
    source: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    embedding: Mapped[Optional[list]] = mapped_column(Vector(_EMBED_DIM), nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_knowledge_category", "category"),
        Index("idx_knowledge_confidence", "confidence"),
        Index("idx_knowledge_created", "created_at"),
    )


class KnowledgeRelationshipModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_relationships"

    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_knowledge_rel_source", "source_id", "relationship_type"),
        Index("idx_knowledge_rel_target", "target_id", "relationship_type"),
    )


class KnowledgeEntryRepository(BaseRepository[KnowledgeEntryModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(KnowledgeEntryModel, session)

    async def search(
        self, query: str, category: Optional[str] = None, limit: int = 20, offset: int = 0
    ) -> list[KnowledgeEntryModel]:
        stmt = select(KnowledgeEntryModel)
        like = f"%{query}%"
        stmt = stmt.where(
            KnowledgeEntryModel.title.ilike(like) | KnowledgeEntryModel.content.ilike(like)
        )
        if category:
            stmt = stmt.where(KnowledgeEntryModel.category == category)
        stmt = stmt.order_by(KnowledgeEntryModel.confidence.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_similar(
        self, embedding: list[float], category: Optional[str] = None, limit: int = 10
    ) -> list[KnowledgeEntryModel]:
        stmt = select(KnowledgeEntryModel).order_by(
            KnowledgeEntryModel.embedding.cosine_distance(embedding)
        ).limit(limit)
        if category:
            stmt = stmt.where(KnowledgeEntryModel.category == category)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_category(self) -> dict[str, int]:
        stmt = select(KnowledgeEntryModel.category, func.count()).group_by(KnowledgeEntryModel.category)
        result = await self._session.execute(stmt)
        return dict(result.all())

    async def list_by_category(self, category: str, limit: int = 50, offset: int = 0) -> list[KnowledgeEntryModel]:
        stmt = (
            select(KnowledgeEntryModel)
            .where(KnowledgeEntryModel.category == category)
            .order_by(KnowledgeEntryModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class KnowledgeRelationshipRepository(BaseRepository[KnowledgeRelationshipModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(KnowledgeRelationshipModel, session)

    async def list_for_source(self, source_id: str) -> list[KnowledgeRelationshipModel]:
        stmt = select(KnowledgeRelationshipModel).where(KnowledgeRelationshipModel.source_id == source_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
