from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import UUIDPrimaryKeyMixin


class HealthStatusSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "health_status_snapshots"
    __table_args__ = (
        Index("idx_health_status", "overall_status"),
        Index("idx_health_captured_at", "captured_at"),
    )

    overall_status: Mapped[str] = mapped_column(String(32), nullable=False)
    component_count: Mapped[int] = mapped_column(Integer, default=0)
    healthy_count: Mapped[int] = mapped_column(Integer, default=0)
    degraded_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=None)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    triggered_by: Mapped[Optional[str]] = mapped_column(String(128), default=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "overall_status": self.overall_status,
            "component_count": self.component_count,
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "critical_count": self.critical_count,
            "details": self.details,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "triggered_by": self.triggered_by,
        }
