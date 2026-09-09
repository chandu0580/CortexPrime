"""
ORM model: reflection_history

Stores self-reflective cognitive entries produced during agent review
cycles (critic / optimizer passes).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

_EMBED_DIM = 1536


class ReflectionHistoryRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per reflection produced during a cognitive review cycle.

    Columns
    -------
    mission_id : optional FK to missions table (nullable — global reflections)
    agent      : agent that produced the reflection
    reflection : full text of the reflection
    embedding  : 1536-dim vector for similarity search
    score      : optional quality/importance score (0–1)
    metadata   : arbitrary JSON payload
    """

    __tablename__ = "reflection_history"

    mission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent:      Mapped[str]                      = mapped_column(String(128), nullable=False)
    reflection: Mapped[str]                      = mapped_column(Text,        nullable=False)
    embedding:  Mapped[Optional[list]]           = mapped_column(Vector(_EMBED_DIM), nullable=True)
    score:      Mapped[Optional[float]]          = mapped_column(Float,       nullable=True)
    meta:       Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    __table_args__ = (
        # Phase 10.31 (ADR-120): migrated indexes declared by their migrated names;
        # unmigrated index=True markers removed (ADR-114 pattern). No DB change.
        Index("idx_refl_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}, postgresql_with={"lists": 50}),
        Index("idx_refl_agent_created",   "agent",      "created_at"),
        Index("idx_refl_mission_created", "mission_id", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":         str(self.id),
            "mission_id": str(self.mission_id) if self.mission_id else None,
            "agent":      self.agent,
            "reflection": self.reflection,
            "score":      self.score,
            "metadata":   self.meta or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
