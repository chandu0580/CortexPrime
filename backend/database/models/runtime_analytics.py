"""
ORM model: runtime_analytics

Captures per-agent, per-mission performance metrics for the analytics
dashboard and operational telemetry.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy                     import BigInteger, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm                 import Mapped, mapped_column

from backend.database.base          import Base
from backend.database.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class RuntimeAnalyticsRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per analytics event / metric snapshot.

    Columns
    -------
    mission_id     : optional FK to missions table
    session_id     : runtime session scope
    agent          : agent name
    event_type     : category of the metric (e.g. "llm_call", "tool_use")
    model          : LLM model identifier (e.g. "gpt-4o")
    prompt_tokens  : tokens consumed in the prompt
    output_tokens  : tokens produced in the response
    latency_ms     : wall-clock latency of the operation in milliseconds
    cost_usd       : estimated cost in USD (nullable — computed asynchronously)
    success        : whether the operation succeeded
    error_message  : error detail when success=False
    payload        : arbitrary JSON for extended telemetry
    """

    __tablename__ = "runtime_analytics"

    mission_id:    Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id:    Mapped[Optional[str]]            = mapped_column(String(255), nullable=True, index=True)
    agent:         Mapped[str]                      = mapped_column(String(128), nullable=False, index=True)
    event_type:    Mapped[str]                      = mapped_column(String(64),  nullable=False)
    model:         Mapped[Optional[str]]            = mapped_column(String(128), nullable=True)
    prompt_tokens: Mapped[Optional[int]]            = mapped_column(Integer,     nullable=True)
    output_tokens: Mapped[Optional[int]]            = mapped_column(Integer,     nullable=True)
    latency_ms:    Mapped[Optional[float]]          = mapped_column(Float,       nullable=True)
    cost_usd:      Mapped[Optional[float]]          = mapped_column(Float,       nullable=True)
    success:       Mapped[bool]                     = mapped_column(nullable=False, default=True, server_default="true")
    error_message: Mapped[Optional[str]]            = mapped_column(Text,        nullable=True)
    payload:       Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB,       nullable=True, default=dict)

    __table_args__ = (
        Index("idx_analytics_agent_created",   "agent",      "created_at"),
        Index("idx_analytics_mission_created", "mission_id", "created_at"),
        Index("idx_analytics_event_type",      "event_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":            str(self.id),
            "mission_id":    str(self.mission_id) if self.mission_id else None,
            "session_id":    self.session_id,
            "agent":         self.agent,
            "event_type":    self.event_type,
            "model":         self.model,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms":    self.latency_ms,
            "cost_usd":      self.cost_usd,
            "success":       self.success,
            "error_message": self.error_message,
            "payload":       self.payload or {},
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }
