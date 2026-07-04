"""
ORM model: semantic_memory

Stores factual knowledge / concepts with vector embeddings.
Supports both vector similarity search and full-text search via pg_trgm.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pgvector.sqlalchemy            import Vector
from sqlalchemy                     import Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm                 import Mapped, mapped_column

from backend.database.base          import Base
from backend.database.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin

_EMBED_DIM = 1536


class SemanticMemoryRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per factual knowledge concept.

    Columns
    -------
    concept    : short human-readable label (e.g. "Python async/await")
    content    : full elaboration of the concept
    embedding  : 1536-dim vector for similarity search
    source     : origin of the knowledge (agent name, URL, document, …)
    confidence : 0–1 quality/certainty score
    metadata   : arbitrary JSON payload
    """

    __tablename__ = "semantic_memory"

    concept:    Mapped[str]                      = mapped_column(Text,         nullable=False)
    content:    Mapped[str]                      = mapped_column(Text,         nullable=False)
    embedding:  Mapped[Optional[list]]           = mapped_column(Vector(_EMBED_DIM), nullable=True)
    source:     Mapped[Optional[str]]            = mapped_column(String(512),  nullable=True)
    confidence: Mapped[float]                    = mapped_column(Float,        nullable=False, default=1.0, server_default="1.0")
    meta:       Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    __table_args__ = (
        Index("idx_sem_confidence", "confidence"),
        # GIN full-text index and IVFFlat vector index are in Alembic / init.sql
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":         str(self.id),
            "concept":    self.concept,
            "content":    self.content,
            "source":     self.source,
            "confidence": self.confidence,
            "metadata":   self.meta or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
