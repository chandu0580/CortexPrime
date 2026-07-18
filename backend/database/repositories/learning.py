from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Boolean, Float, Index, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class LearningSessionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_sessions"

    session_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    mission_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active", index=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    patterns_extracted: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)
    lessons_learned: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_learn_session_mission", "mission_type"),
        Index("idx_learn_session_status", "status"),
    )


class LearningPatternModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_patterns"

    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    occurrences: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    pattern_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        Index("idx_learn_patterns_category", "category"),
        Index("idx_learn_patterns_confidence", "confidence"),
    )


class LearningSessionRepository(BaseRepository[LearningSessionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(LearningSessionModel, session)

    async def list_by_mission_type(self, mission_type: str, limit: int = 50, offset: int = 0) -> list[LearningSessionModel]:
        stmt = (
            select(LearningSessionModel)
            .where(LearningSessionModel.mission_type == mission_type)
            .order_by(LearningSessionModel.created_at.desc())
            .limit(limit).offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class LearningPatternRepository(BaseRepository[LearningPatternModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(LearningPatternModel, session)

    async def get_by_name(self, name: str) -> Optional[LearningPatternModel]:
        stmt = select(LearningPatternModel).where(LearningPatternModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_category(self, category: str) -> list[LearningPatternModel]:
        stmt = (
            select(LearningPatternModel)
            .where(LearningPatternModel.category == category)
            .order_by(LearningPatternModel.confidence.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_high_confidence(self, min_confidence: float = 0.7, limit: int = 50) -> list[LearningPatternModel]:
        stmt = (
            select(LearningPatternModel)
            .where(LearningPatternModel.confidence >= min_confidence, LearningPatternModel.is_active == True)
            .order_by(LearningPatternModel.confidence.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
