from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.database.models.department import DepartmentModel


class OrganizationModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    domain: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    departments: Mapped[List["DepartmentModel"]] = relationship(
        "DepartmentModel",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_organization_name", "name"),
        Index("idx_organization_domain", "domain"),
        Index("idx_organization_active", "is_active"),
        Index("idx_organization_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "is_active": self.is_active,
            "metadata": self.metadata_ or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
