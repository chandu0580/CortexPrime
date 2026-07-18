from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProjectModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active", server_default="active", index=True)
    owner: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    __table_args__ = (
        Index("idx_project_organization", "organization_id"),
        Index("idx_project_department", "department_id"),
        Index("idx_project_status", "status"),
        Index("idx_project_owner", "owner"),
        Index("idx_project_created", "created_at"),
        Index("idx_project_org_name", "organization_id", "name", unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "department_id": str(self.department_id) if self.department_id else None,
            "name": self.name,
            "key": self.key,
            "description": self.description,
            "status": self.status,
            "owner": self.owner,
            "tags": self.tags or [],
            "is_active": self.is_active,
            "metadata": self.metadata_ or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
