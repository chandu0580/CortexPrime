from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class OperationalReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_reports"
    __table_args__ = (
        Index("idx_opreport_type", "report_type"),
        Index("idx_opreport_status", "status"),
        Index("idx_opreport_period_start", "period_start"),
    )

    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_end: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")
    summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=None)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    generated_by: Mapped[Optional[str]] = mapped_column(String(128), default=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "report_type": self.report_type,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
            "error_message": self.error_message,
            "generated_by": self.generated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
