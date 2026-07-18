from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Boolean, Float, Index, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class InfrastructureModelModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digital_twin_models"

    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    region: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True, default=list)
    properties: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_dt_model_type", "resource_type", "provider"),
        Index("idx_dt_model_status", "status"),
        Index("idx_dt_model_active", "is_active"),
    )


class InfrastructureRelationshipModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digital_twin_relationships"

    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    properties: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_dt_rel_source", "source_id", "relationship_type"),
        Index("idx_dt_rel_target", "target_id", "relationship_type"),
    )


class InfrastructureMetricModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digital_twin_metrics"

    resource_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    tags: Mapped[Optional[dict[str, str]]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("idx_dt_metrics_resource", "resource_id", "metric_name", "created_at"),)


class InfrastructureModelRepository(BaseRepository[InfrastructureModelModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(InfrastructureModelModel, session)

    async def search(
        self,
        resource_type: Optional[str] = None,
        provider: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InfrastructureModelModel]:
        stmt = select(InfrastructureModelModel)
        if resource_type:
            stmt = stmt.where(InfrastructureModelModel.resource_type == resource_type)
        if provider:
            stmt = stmt.where(InfrastructureModelModel.provider == provider)
        if status:
            stmt = stmt.where(InfrastructureModelModel.status == status)
        stmt = stmt.order_by(InfrastructureModelModel.name).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class InfrastructureRelationshipRepository(BaseRepository[InfrastructureRelationshipModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(InfrastructureRelationshipModel, session)

    async def get_neighbors(self, resource_id: str) -> list[InfrastructureRelationshipModel]:
        stmt = select(InfrastructureRelationshipModel).where(
            (InfrastructureRelationshipModel.source_id == resource_id)
            | (InfrastructureRelationshipModel.target_id == resource_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class InfrastructureMetricRepository(BaseRepository[InfrastructureMetricModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(InfrastructureMetricModel, session)

    async def list_for_resource(self, resource_id: str, limit: int = 100) -> list[InfrastructureMetricModel]:
        stmt = (
            select(InfrastructureMetricModel)
            .where(InfrastructureMetricModel.resource_id == resource_id)
            .order_by(InfrastructureMetricModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
