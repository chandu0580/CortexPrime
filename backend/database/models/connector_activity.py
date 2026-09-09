from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ConnectorActivityModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connector_activity"

    connector_name: Mapped[str] = mapped_column(String(256), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", server_default="success")
    initiated_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    __table_args__ = (
        # Phase 10.31 (ADR-120): migrated indexes declared by their migrated names;
        # unmigrated index=True markers removed (ADR-114 pattern). No DB change.
        Index("idx_ca_connector_name", "connector_name"),
        Index("idx_ca_request_id", "request_id"),
        Index("idx_ca_correlation_id", "correlation_id"),
        Index("idx_ca_connector_type_created", "connector_type", "created_at"),
        Index("idx_ca_status_created", "status", "created_at"),
        Index("idx_ca_operation_created", "operation", "created_at"),
        Index("idx_ca_initiated_by", "initiated_by"),
        Index("idx_ca_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "connector_name": self.connector_name,
            "connector_type": self.connector_type,
            "operation": self.operation,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "status": self.status,
            "initiated_by": self.initiated_by,
            "duration_ms": self.duration_ms,
            "request_id": str(self.request_id) if self.request_id else None,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "message": self.message,
            "metadata": self.metadata_ or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
