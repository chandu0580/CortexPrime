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

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0", server_default="1.0")
    endpoint: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    auth_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="REGISTERED", server_default="REGISTERED")
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        # Phase 10.31 (ADR-120): migrated indexes declared by their migrated names;
        # unmigrated index=True markers removed (ADR-114 pattern). No DB change.
        Index("idx_connector_name", "name", unique=True),
        Index("idx_connector_status", "status"),
        Index("idx_connector_configs_type", "connector_type"),
        Index("idx_connector_configs_active", "is_active"),
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
