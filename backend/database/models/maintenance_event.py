from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MaintenanceEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "maintenance_events"
    __table_args__ = (
        Index("idx_maintenance_action", "action"),
        Index("idx_maintenance_created_at", "created_at"),
    )

    action: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    banner_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "action": self.action,
            "enabled": self.enabled,
            "banner_message": self.banner_message,
            "triggered_by": self.triggered_by,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
