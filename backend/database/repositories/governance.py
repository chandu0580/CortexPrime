from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Boolean, Index, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class PolicyModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "governance_policies"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium", server_default="medium")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    conditions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    actions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        # Phase 10.31 (ADR-120): migrated indexes declared by their migrated names;
        # unmigrated index=True markers removed (ADR-114 pattern). No DB change.
        Index("idx_gov_policies_name", "name", unique=True),
        Index("idx_gov_policies_category", "category"),
        Index("idx_gov_policies_enabled", "enabled"),
    )


class ComplianceRuleModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "governance_compliance_rules"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    framework: Mapped[str] = mapped_column(String(64), nullable=False)
    control_id: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium", server_default="medium")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    check_type: Mapped[str] = mapped_column(String(64), nullable=False)
    check_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_gov_compliance_framework", "framework", "control_id"),
        Index("idx_gov_compliance_enabled", "enabled"),
    )


class ApprovalRequestModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "governance_approval_requests"

    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requester: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    reviewers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    approved_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    approved_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        # Phase 10.31 (ADR-120): migrated indexes declared by their migrated names;
        # unmigrated index=True markers removed (ADR-114 pattern). No DB change.
        Index("idx_gov_approval_rid", "request_id", unique=True),
        Index("idx_gov_approval_status", "status", "created_at"),)


class PolicyRepository(BaseRepository[PolicyModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PolicyModel, session)

    async def get_by_name(self, name: str) -> Optional[PolicyModel]:
        stmt = select(PolicyModel).where(PolicyModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_category(self, category: str) -> list[PolicyModel]:
        stmt = select(PolicyModel).where(PolicyModel.category == category).order_by(PolicyModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_enabled(self) -> list[PolicyModel]:
        stmt = select(PolicyModel).where(PolicyModel.enabled is True).order_by(PolicyModel.category, PolicyModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ComplianceRuleRepository(BaseRepository[ComplianceRuleModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ComplianceRuleModel, session)

    async def list_by_framework(self, framework: str) -> list[ComplianceRuleModel]:
        stmt = select(ComplianceRuleModel).where(ComplianceRuleModel.framework == framework)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ApprovalRequestRepository(BaseRepository[ApprovalRequestModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ApprovalRequestModel, session)

    async def get_by_request_id(self, request_id: str) -> Optional[ApprovalRequestModel]:
        stmt = select(ApprovalRequestModel).where(ApprovalRequestModel.request_id == request_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_status(self, status: str, limit: int = 50, offset: int = 0) -> list[ApprovalRequestModel]:
        stmt = (
            select(ApprovalRequestModel)
            .where(ApprovalRequestModel.status == status)
            .order_by(ApprovalRequestModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
