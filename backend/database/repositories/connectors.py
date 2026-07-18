from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Boolean, Index, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class ConnectorConfigModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connector_configs"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0", server_default="1.0")
    endpoint: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    auth_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="REGISTERED", server_default="REGISTERED")
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_connector_configs_type", "connector_type"),
        Index("idx_connector_configs_active", "is_active"),
    )


class ConnectorActivityModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connector_activity_bc"

    connector_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", server_default="success")
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    request_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_connector_activity_name", "connector_name", "created_at"),
        Index("idx_connector_activity_status", "status"),
    )


class ConnectorConfigRepository(BaseRepository[ConnectorConfigModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ConnectorConfigModel, session)

    async def get_by_name(self, name: str) -> Optional[ConnectorConfigModel]:
        stmt = select(ConnectorConfigModel).where(ConnectorConfigModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_type(self, connector_type: str) -> list[ConnectorConfigModel]:
        stmt = select(ConnectorConfigModel).where(ConnectorConfigModel.connector_type == connector_type)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ConnectorActivityRepository(BaseRepository[ConnectorActivityModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ConnectorActivityModel, session)

    async def list_for_connector(self, connector_name: str, limit: int = 100, offset: int = 0) -> list[ConnectorActivityModel]:
        stmt = (
            select(ConnectorActivityModel)
            .where(ConnectorActivityModel.connector_name == connector_name)
            .order_by(ConnectorActivityModel.created_at.desc())
            .limit(limit).offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
