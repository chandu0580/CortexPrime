from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Float, Index, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class UsageRecordModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_usage_records"

    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    mission_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="requests", server_default="requests")
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_billing_usage_org", "organization_id", "created_at"),
        Index("idx_billing_usage_resource", "resource_type"),
    )


class InvoiceModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_invoices"

    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    period_start: Mapped[str] = mapped_column(String(32), nullable=False)
    period_end: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending", index=True)
    total_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD", server_default="USD")
    line_items: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_billing_invoices_org", "organization_id", "status"),
        Index("idx_billing_invoices_status", "status"),
    )


class UsageRecordRepository(BaseRepository[UsageRecordModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UsageRecordModel, session)

    async def sum_by_org(self, organization_id: str) -> float:
        stmt = select(func.sum(UsageRecordModel.cost_usd)).where(
            UsageRecordModel.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0.0

    async def sum_by_resource_type(self, organization_id: str) -> dict[str, float]:
        stmt = (
            select(UsageRecordModel.resource_type, func.sum(UsageRecordModel.cost_usd))
            .where(UsageRecordModel.organization_id == organization_id)
            .group_by(UsageRecordModel.resource_type)
        )
        result = await self._session.execute(stmt)
        return dict(result.all())


class InvoiceRepository(BaseRepository[InvoiceModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(InvoiceModel, session)

    async def list_by_org(self, organization_id: str, limit: int = 50, offset: int = 0) -> list[InvoiceModel]:
        stmt = (
            select(InvoiceModel)
            .where(InvoiceModel.organization_id == organization_id)
            .order_by(InvoiceModel.created_at.desc())
            .limit(limit).offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
