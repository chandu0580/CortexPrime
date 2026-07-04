"""
Semantic Memory Store — PostgreSQL + pgvector.

Stores factual knowledge / concepts with vector embeddings.
Supports both vector similarity search and full-text search.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.memory.db.postgres_client import postgres_client
from backend.memory.embedding_pipeline import embedding_pipeline, pgvector_str
from backend.memory.models import SemanticEntry

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# SQL
# ------------------------------------------------------------------

_INSERT = """
INSERT INTO semantic_memory
    (id, concept, content, embedding, source, confidence, metadata, created_at)
VALUES ($1, $2, $3, $4::vector, $5, $6, $7::jsonb, $8)
"""

_INSERT_NO_EMBED = """
INSERT INTO semantic_memory
    (id, concept, content, source, confidence, metadata, created_at)
VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
"""

_SEARCH_VECTOR = """
SELECT id, concept, content, source, confidence, metadata, created_at,
       1 - (embedding <=> $1::vector) AS relevance
FROM semantic_memory
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1::vector
LIMIT $2
"""

_SEARCH_FTS = """
SELECT id, concept, content, source, confidence, metadata, created_at,
       NULL::float AS relevance
FROM semantic_memory
WHERE to_tsvector('english', concept || ' ' || content)
      @@ plainto_tsquery('english', $1)
ORDER BY confidence DESC
LIMIT $2
"""

_GET_BY_CONCEPT = """
SELECT id, concept, content, source, confidence, metadata, created_at
FROM semantic_memory
WHERE concept ILIKE $1
ORDER BY confidence DESC
LIMIT $2
"""


class SemanticStore:
    """
    Semantic memory backed by PostgreSQL + pgvector.

    Stores factual, encyclopaedic knowledge.  Entries are retrieved via
    vector similarity when 1536-dim embeddings are available, otherwise via
    PostgreSQL full-text search.
    """

    async def store(
        self,
        concept:    str,
        content:    str,
        source:     Optional[str]            = None,
        confidence: float                    = 1.0,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist a semantic knowledge entry. Returns the new memory ID."""
        entry_id   = str(uuid4())
        embedding  = await embedding_pipeline.embed(f"{concept}: {content}")
        embed_str  = pgvector_str(embedding)
        created_at = datetime.utcnow()
        meta_json  = json.dumps(metadata or {})

        if embed_str:
            await postgres_client.execute(
                _INSERT,
                entry_id, concept, content, embed_str,
                source, confidence, meta_json, created_at,
            )
        else:
            await postgres_client.execute(
                _INSERT_NO_EMBED,
                entry_id, concept, content,
                source, confidence, meta_json, created_at,
            )

        return entry_id

    async def search(
        self,
        query:         str,
        limit:         int   = 10,
        min_relevance: float = 0.0,
    ) -> List[SemanticEntry]:
        """Semantic search; filters by min_relevance when using vector search."""
        embedding = await embedding_pipeline.embed(query)
        embed_str = pgvector_str(embedding)

        if embed_str:
            rows    = await postgres_client.fetch(_SEARCH_VECTOR, embed_str, limit * 2)
            entries = [self._row(r, r.get("relevance")) for r in rows]
            return [e for e in entries if (e.relevance or 0) >= min_relevance][:limit]

        rows = await postgres_client.fetch(_SEARCH_FTS, query, limit)
        return [self._row(r) for r in rows]

    async def get_by_concept(
        self,
        concept: str,
        limit:   int = 5,
    ) -> List[SemanticEntry]:
        """Exact / ILIKE concept lookup."""
        rows = await postgres_client.fetch(_GET_BY_CONCEPT, f"%{concept}%", limit)
        return [self._row(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row(row: Any, relevance: Optional[float] = None) -> SemanticEntry:
        meta = row["metadata"] or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        return SemanticEntry(
            id         = str(row["id"]),
            concept    = row["concept"],
            content    = row["content"],
            source     = row.get("source"),
            confidence = float(row.get("confidence") or 1.0),
            metadata   = meta,
            relevance  = float(relevance) if relevance is not None else None,
            created_at = row["created_at"],
        )


semantic_store = SemanticStore()
