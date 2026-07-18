from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Boolean, Index, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class FeatureFlagModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_feature_flags"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (Index("idx_platform_ff_enabled", "enabled"),)


class PlatformSettingModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general", server_default="general", index=True)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    __table_args__ = (Index("idx_platform_settings_category", "category"),)


class FeatureFlagRepository(BaseRepository[FeatureFlagModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(FeatureFlagModel, session)

    async def get_by_name(self, name: str) -> Optional[FeatureFlagModel]:
        stmt = select(FeatureFlagModel).where(FeatureFlagModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_enabled(self) -> list[FeatureFlagModel]:
        stmt = select(FeatureFlagModel).where(FeatureFlagModel.enabled == True)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PlatformSettingRepository(BaseRepository[PlatformSettingModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PlatformSettingModel, session)

    async def get_by_key(self, key: str) -> Optional[PlatformSettingModel]:
        stmt = select(PlatformSettingModel).where(PlatformSettingModel.key == key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_category(self, category: str) -> list[PlatformSettingModel]:
        stmt = select(PlatformSettingModel).where(PlatformSettingModel.category == category)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
