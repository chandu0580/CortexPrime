"""
ORM model: episodic_memory

Stores every agent interaction event with an optional pgvector embedding
for semantic similarity retrieval.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text, text
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

    session_id: Mapped[str]                  = mapped_column(String(255), nullable=False)
    agent:      Mapped[str]                  = mapped_column(String(128), nullable=False)
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
        # Phase 10.31 (ADR-120): migrated indexes declared by their migrated names;
        # unmigrated index=True markers removed (ADR-114 pattern). No DB change.
        Index("idx_ep_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}, postgresql_with={"lists": 100}),
        Index("idx_ep_content_fts", text("to_tsvector('english'::regconfig, content)"), postgresql_using="gin"),
        Index("idx_ep_session_created", "session_id", "created_at"),
        Index("idx_ep_agent_created",   "agent",      "created_at"),
        # The IVFFlat and GIN indexes are created by migration 0001 and mirrored here
        # exactly (ADR-120) so autogenerate can never propose dropping them.
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
