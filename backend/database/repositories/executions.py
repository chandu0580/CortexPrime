from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class ExecutionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "executions"

    mission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missions_bc.id", ondelete="SET NULL"), nullable=True, index=True
    )
    execution_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending", index=True)
    agent: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    trigger: Mapped[str] = mapped_column(String(64), nullable=False, default="manual", server_default="manual")
    context: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_exec_mission", "mission_id"),
        Index("idx_exec_status", "status", "created_at"),
        Index("idx_exec_agent", "agent"),
        Index("idx_exec_trigger", "trigger"),
    )


class ExecutionEventModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "execution_events"

    execution_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    agent: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_exec_events_exec", "execution_id", "timestamp"),
        Index("idx_exec_events_type", "event_type"),
    )


class ExecutionRepository(BaseRepository[ExecutionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExecutionModel, session)

    async def get_by_execution_id(self, execution_id: str) -> Optional[ExecutionModel]:
        stmt = select(ExecutionModel).where(ExecutionModel.execution_id == execution_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        status: Optional[str] = None,
        agent: Optional[str] = None,
        trigger: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionModel]:
        stmt = select(ExecutionModel)
        if status:
            stmt = stmt.where(ExecutionModel.status == status)
        if agent:
            stmt = stmt.where(ExecutionModel.agent == agent)
        if trigger:
            stmt = stmt.where(ExecutionModel.trigger == trigger)
        stmt = stmt.order_by(ExecutionModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        stmt = select(ExecutionModel.status, func.count()).group_by(ExecutionModel.status)
        result = await self._session.execute(stmt)
        return dict(result.all())

    async def count_by_agent(self) -> dict[str, int]:
        stmt = select(ExecutionModel.agent, func.count()).group_by(ExecutionModel.agent)
        result = await self._session.execute(stmt)
        return dict(result.all())

    async def search_by_mission(self, mission_id: str, limit: int = 50, offset: int = 0) -> list[ExecutionModel]:
        import uuid
        try:
            uid = uuid.UUID(mission_id)
        except ValueError:
            return []
        stmt = (
            select(ExecutionModel)
            .where(ExecutionModel.mission_id == uid)
            .order_by(ExecutionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ExecutionEventRepository(BaseRepository[ExecutionEventModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExecutionEventModel, session)

    async def list_for_execution(self, execution_id: str, limit: int = 200, offset: int = 0) -> list[ExecutionEventModel]:
        stmt = (
            select(ExecutionEventModel)
            .where(ExecutionEventModel.execution_id == execution_id)
            .order_by(ExecutionEventModel.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
