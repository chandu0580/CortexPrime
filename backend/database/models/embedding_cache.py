"""
ORM model: embedding_cache

Caches computed embeddings keyed by SHA-256 of the input text so that
identical strings are never embedded twice (supplementing the Redis TTL
cache for cross-restart persistence).
"""
from __future__ import annotations

import hashlib
from typing import List

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

_EMBED_DIM = 1536


class EmbeddingCacheRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per unique (text, model) pair that has been embedded.

    Columns
    -------
    text_hash  : SHA-256 of (model + ":" + text) — unique lookup key
    model      : embedding model identifier (e.g. "text-embedding-3-small")
    text_preview : first 512 chars of the source text (for debugging)
    embedding  : the actual vector
    """

    __tablename__ = "embedding_cache"

    text_hash:    Mapped[str]        = mapped_column(String(64),      nullable=False)
    model:        Mapped[str]        = mapped_column(String(128),     nullable=False)
    text_preview: Mapped[str]        = mapped_column(Text,            nullable=False)
    embedding:    Mapped[List[float]] = mapped_column(Vector(_EMBED_DIM), nullable=False)

    __table_args__ = (
        # Phase 10.31 (ADR-120): migrated indexes declared by their migrated names;
        # unmigrated index=True markers removed (ADR-114 pattern). No DB change.
        UniqueConstraint("text_hash", name="embedding_cache_text_hash_key"),
        Index("idx_emb_cache_hash", "text_hash", unique=True),
    )

    @staticmethod
    def make_hash(model: str, text: str) -> str:
        return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()
