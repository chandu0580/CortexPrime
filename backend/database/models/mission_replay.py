"""
ORM model: mission_replay_events

Persistent log of every replay-relevant event for a mission execution.
Feeds the Mission Replay Engine's timeline, graph, and playback API.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class MissionReplayEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per persisted replay event.

    Design
    ------
    - ``execution_id`` is the primary grouping key — every event that
      belongs to the same mission run shares the same execution_id.
    - ``sequence``     is a monotonically increasing integer per execution,
      assigned by the store so playback can trivially ORDER BY sequence.
    - ``event_type``   is the canonical event classification string
      (mission_started, agent_started, tool_called, …).
    - ``payload``      is a free JSONB column holding all extra context
      (tool args/result, memory chunks, token counts, confidence scores…).
    """

    __tablename__ = "mission_replay_events"

    # ── Core identity ──────────────────────────────────────────────────────
    execution_id:   Mapped[str]           = mapped_column(String(255), nullable=False, index=True)
    sequence:       Mapped[int]           = mapped_column(Integer,     nullable=False, default=0)

    # ── Event classification ───────────────────────────────────────────────
    event_type:     Mapped[str]           = mapped_column(String(64),  nullable=False)
    agent:          Mapped[str]           = mapped_column(String(128), nullable=False, index=True)
    status:         Mapped[str]           = mapped_column(String(32),  nullable=False, default="info")
    message:        Mapped[str]           = mapped_column(Text,        nullable=False, default="")

    # ── Timing ────────────────────────────────────────────────────────────
    # Wall-clock ISO timestamp when the event was emitted by the agent.
    # created_at (from TimestampMixin) is when the row was written to DB.
    event_ts:       Mapped[Optional[str]] = mapped_column(String(64),  nullable=True)

    # ── Performance ───────────────────────────────────────────────────────
    latency_ms:     Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Replay payload ────────────────────────────────────────────────────
    payload:        Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True, default=dict)

    __table_args__ = (
        Index("idx_replay_exec_seq",     "execution_id", "sequence"),
        Index("idx_replay_exec_type",    "execution_id", "event_type"),
        Index("idx_replay_exec_agent",   "execution_id", "agent"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":           str(self.id),
            "execution_id": self.execution_id,
            "sequence":     self.sequence,
            "event_type":   self.event_type,
            "agent":        self.agent,
            "status":       self.status,
            "message":      self.message,
            "event_ts":     self.event_ts,
            "latency_ms":   self.latency_ms,
            "payload":      self.payload or {},
            "created_at":   self.created_at.isoformat() if self.created_at else None,
        }
