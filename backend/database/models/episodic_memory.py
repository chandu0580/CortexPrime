"""
ORM model: episodic_memory

Stores every agent interaction event with an optional pgvector embedding
for semantic similarity retrieval.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

_EMBED_DIM = 1536  # OpenAI text-embedding-3-small


class EpisodicMemoryRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per agent interaction event.

    Columns
    -------
    session_id  : logical session scope (user/mission context key)
    agent       : agent name that produced this event
    event_type  : e.g. "thought", "action", "observation", "result"
    content     : full text of the event
    embedding   : 1536-dim vector (NULL when no API key is available)
    metadata    : arbitrary JSON payload
    """

    __tablename__ = "episodic_memory"

    session_id: Mapped[str]                  = mapped_column(String(255), nullable=False, index=True)
    agent:      Mapped[str]                  = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str]                  = mapped_column(String(64),  nullable=False)
    content:    Mapped[str]                  = mapped_column(Text,        nullable=False)
    embedding:  Mapped[Optional[list]]       = mapped_column(Vector(_EMBED_DIM), nullable=True)
    # Column is named "metadata" in the DB; Python attr is "meta" to avoid
    # conflicting with SQLAlchemy DeclarativeBase.metadata (reserved name).
    meta:       Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    # -----------------------------------------------------------------------
    # Composite + vector indexes
    # -----------------------------------------------------------------------
    __table_args__ = (
        Index("idx_ep_session_created", "session_id", "created_at"),
        Index("idx_ep_agent_created",   "agent",      "created_at"),
        # IVFFlat index is created via Alembic / init.sql — not expressible in DDL here
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":         str(self.id),
            "session_id": self.session_id,
            "agent":      self.agent,
            "event_type": self.event_type,
            "content":    self.content,
            "metadata":   self.meta or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
