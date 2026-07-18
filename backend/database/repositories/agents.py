from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Boolean, Index, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class AgentConfigModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_configs"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="openai", server_default="openai")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="gpt-4o", server_default="gpt-4o")
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capabilities: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True, default=list)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    max_retries: Mapped[int] = mapped_column(nullable=False, default=3, server_default="3")
    timeout_seconds: Mapped[int] = mapped_column(nullable=False, default=120, server_default="120")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_agent_configs_type", "agent_type"),
        Index("idx_agent_configs_active", "is_active"),
    )


class AgentStateModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_states"

    agent_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle", server_default="idle", index=True)
    current_mission: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    current_execution: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_heartbeat: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    memory_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("idx_agent_states_status", "status"),)


class AgentConfigRepository(BaseRepository[AgentConfigModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AgentConfigModel, session)

    async def get_by_name(self, name: str) -> Optional[AgentConfigModel]:
        stmt = select(AgentConfigModel).where(AgentConfigModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_type(self, agent_type: str) -> list[AgentConfigModel]:
        stmt = select(AgentConfigModel).where(AgentConfigModel.agent_type == agent_type).order_by(AgentConfigModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active(self) -> list[AgentConfigModel]:
        stmt = select(AgentConfigModel).where(AgentConfigModel.is_active is True).order_by(AgentConfigModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class AgentStateRepository(BaseRepository[AgentStateModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AgentStateModel, session)

    async def get_by_agent_name(self, agent_name: str) -> Optional[AgentStateModel]:
        stmt = select(AgentStateModel).where(AgentStateModel.agent_name == agent_name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
