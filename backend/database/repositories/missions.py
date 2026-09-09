from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class MissionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "missions_bc"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    execution_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    context: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_missions_bc_status", "status", "created_at"),
        Index("idx_missions_bc_category", "category"),
        Index("idx_missions_bc_owner", "owner"),
    )


class MissionStepModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mission_steps"

    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missions_bc.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    agent: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    input_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_mission_steps_mission", "mission_id", "step_order"),
        Index("idx_mission_steps_status", "status"),
    )


class MissionRepository(BaseRepository[MissionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MissionModel, session)

    async def search(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MissionModel]:
        stmt = select(MissionModel)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(or_(MissionModel.title.ilike(like), MissionModel.objective.ilike(like)))
        if status:
            stmt = stmt.where(MissionModel.status == status)
        if category:
            stmt = stmt.where(MissionModel.category == category)
        if owner:
            stmt = stmt.where(MissionModel.owner == owner)
        stmt = stmt.order_by(MissionModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        stmt = select(MissionModel.status, func.count()).group_by(MissionModel.status)
        result = await self._session.execute(stmt)
        return dict(result.all())


class MissionStepRepository(BaseRepository[MissionStepModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MissionStepModel, session)

    async def list_for_mission(self, mission_id: uuid.UUID) -> list[MissionStepModel]:
        stmt = (
            select(MissionStepModel)
            .where(MissionStepModel.mission_id == mission_id)
            .order_by(MissionStepModel.step_order)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
