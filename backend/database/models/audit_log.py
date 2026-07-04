"""
ORM model: audit_logs

Durable audit trail for every governance decision, mission lifecycle event,
browser/computer agent action, and approval workflow outcome.

This table is the authoritative, persistent record — it survives server
restarts, Docker restarts, and deployments.

Migration note
--------------
  The table is created via ``init_db()`` on startup using
  CREATE TABLE IF NOT EXISTS semantics.  For production, generate an
  Alembic migration from this model.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per auditable event in the CortexPrime runtime.

    Columns
    -------
    execution_id  : mission / task execution identifier
    user_id       : authenticated user or "system" / "agent"
    agent         : agent that performed the action
    action        : human-readable action name (e.g. "visit_url", "emergency_stop")
    risk_level    : low | medium | high | critical
    outcome       : allowed | blocked | approved | rejected | pending
                    | started | completed | failed | stopped
    reason        : why this outcome was recorded
    metadata      : arbitrary JSON payload for context-specific fields
                    (e.g. URL visited, desktop coordinates, approval request ID)
    session_id    : optional session correlation key
    request_id    : optional approval request correlation key
    """

    __tablename__ = "audit_logs"

    execution_id: Mapped[str]                    = mapped_column(String(128), nullable=False, index=True)
    user_id:      Mapped[str]                    = mapped_column(String(128), nullable=False, default="system", server_default="system")
    agent:        Mapped[str]                    = mapped_column(String(128), nullable=False, index=True)
    action:       Mapped[str]                    = mapped_column(String(256), nullable=False)
    risk_level:   Mapped[str]                    = mapped_column(String(32),  nullable=False, default="low",    server_default="low",    index=True)
    outcome:      Mapped[str]                    = mapped_column(String(32),  nullable=False, default="allowed", server_default="allowed", index=True)
    reason:       Mapped[str]                    = mapped_column(Text,        nullable=False, default="",       server_default="")
    metadata_:    Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True, default=dict)
    session_id:   Mapped[Optional[str]]          = mapped_column(String(128), nullable=True,  index=True)
    request_id:   Mapped[Optional[str]]          = mapped_column(String(128), nullable=True,  index=True)

    # Indexes for common query patterns
    __table_args__ = (
        Index("idx_audit_execution_created",  "execution_id",  "created_at"),
        Index("idx_audit_outcome_created",    "outcome",       "created_at"),
        Index("idx_audit_risk_created",       "risk_level",    "created_at"),
        Index("idx_audit_agent_created",      "agent",         "created_at"),
        Index("idx_audit_created",            "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":           str(self.id),
            "execution_id": self.execution_id,
            "user_id":      self.user_id,
            "agent":        self.agent,
            "action":       self.action,
            "risk_level":   self.risk_level,
            "outcome":      self.outcome,
            "reason":       self.reason,
            "metadata":     self.metadata_ or {},
            "session_id":   self.session_id,
            "request_id":   self.request_id,
            "timestamp":    self.created_at.isoformat() if self.created_at else None,
        }
