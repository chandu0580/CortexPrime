from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BackupRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "backup_records"
    __table_args__ = (
        Index("idx_backup_status", "status"),
        Index("idx_backup_type", "backup_type"),
        Index("idx_backup_created_at", "created_at"),
    )

    backup_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    entities: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=None)
    total_bytes: Mapped[Optional[int]] = mapped_column(default=None)
    integrity_hash: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    file_path: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    completed_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "backup_type": self.backup_type,
            "status": self.status,
            "entities": self.entities,
            "total_bytes": self.total_bytes,
            "integrity_hash": self.integrity_hash,
            "file_path": self.file_path,
            "error_message": self.error_message,
            "triggered_by": self.triggered_by,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
