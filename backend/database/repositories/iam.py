from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import Boolean, ForeignKey, Index, String, or_, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from backend.database.repositories.base import BaseRepository


class UserModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "iam_users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active")
    is_sso: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sso_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sso_subject: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_iam_users_email", "email"),
        Index("idx_iam_users_status", "status"),
        Index("idx_iam_users_sso", "sso_provider", "sso_subject"),
    )


class RoleModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "iam_roles"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    __table_args__ = (Index("idx_iam_roles_name", "name"),)


class ApiKeyModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "iam_api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    last_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    expires_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        Index("idx_iam_ak_user", "user_id"),
        Index("idx_iam_ak_hash", "key_hash"),
    )


class UserRepository(BaseRepository[UserModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UserModel, session)

    async def get_by_email(self, email: str) -> Optional[UserModel]:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self, query: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> list[UserModel]:
        stmt = select(UserModel)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(or_(UserModel.email.ilike(like), UserModel.display_name.ilike(like)))
        if status:
            stmt = stmt.where(UserModel.status == status)
        stmt = stmt.order_by(UserModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_sso(self, provider: str, subject: str) -> Optional[UserModel]:
        stmt = select(UserModel).where(
            UserModel.sso_provider == provider, UserModel.sso_subject == subject
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class RoleRepository(BaseRepository[RoleModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RoleModel, session)

    async def get_by_name(self, name: str) -> Optional[RoleModel]:
        stmt = select(RoleModel).where(RoleModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class ApiKeyRepository(BaseRepository[ApiKeyModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ApiKeyModel, session)

    async def get_by_hash(self, key_hash: str) -> Optional[ApiKeyModel]:
        stmt = select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[ApiKeyModel]:
        stmt = select(ApiKeyModel).where(ApiKeyModel.user_id == user_id).order_by(ApiKeyModel.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
