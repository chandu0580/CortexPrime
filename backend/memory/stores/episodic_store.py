"""
Episodic Memory Store — PostgreSQL + pgvector.

Stores agent interaction events with optional vector embeddings for
semantic similarity retrieval.  Falls back to full-text search when
embeddings are not available (e.g. no OpenAI key).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.memory.db.postgres_client import postgres_client
from backend.memory.embedding_pipeline import embedding_pipeline, pgvector_str
from backend.memory.models import EpisodicEntry

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# SQL
# ------------------------------------------------------------------

_INSERT = """
INSERT INTO episodic_memory
    (id, session_id, agent, event_type, content, embedding, metadata, created_at)
VALUES ($1, $2, $3, $4, $5, $6::vector, $7::jsonb, $8)
"""

_INSERT_NO_EMBED = """
INSERT INTO episodic_memory
    (id, session_id, agent, event_type, content, metadata, created_at)
VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
"""

_SELECT_SESSION = """
SELECT id, session_id, agent, event_type, content, metadata, created_at
FROM episodic_memory
WHERE session_id = $1
ORDER BY created_at DESC
LIMIT $2
"""

_SEARCH_VECTOR = """
SELECT id, session_id, agent, event_type, content, metadata, created_at,
       1 - (embedding <=> $1::vector) AS relevance
FROM episodic_memory
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1::vector
LIMIT $2
"""

_SEARCH_FTS = """
SELECT id, session_id, agent, event_type, content, metadata, created_at,
       NULL::float AS relevance
FROM episodic_memory
WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
ORDER BY created_at DESC
LIMIT $2
"""


class EpisodicStore:
    """
    Episodic memory backed by PostgreSQL.

    Each entry represents one agent interaction event.  Embeddings are stored
    when the embedding pipeline produces 1536-dim vectors (OpenAI); otherwise
    text-only entries are stored and full-text search is used as fallback.
    """

    async def store(
        self,
        session_id: str,
        agent:      str,
        event_type: str,
        content:    str,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist an episodic event. Returns the new memory ID."""
        entry_id   = str(uuid4())
        embedding  = await embedding_pipeline.embed(content)
        embed_str  = pgvector_str(embedding)
        created_at = datetime.utcnow()
        meta_json  = json.dumps(metadata or {})

        if embed_str:
            await postgres_client.execute(
                _INSERT,
                entry_id, session_id, agent, event_type,
                content, embed_str, meta_json, created_at,
            )
        else:
            await postgres_client.execute(
                _INSERT_NO_EMBED,
                entry_id, session_id, agent, event_type,
                content, meta_json, created_at,
            )

        return entry_id

    async def get_session(
        self,
        session_id: str,
        limit:      int = 50,
    ) -> List[EpisodicEntry]:
        """Return recent episodic events for a session, newest first."""
        rows = await postgres_client.fetch(_SELECT_SESSION, session_id, limit)
        return [self._row(r) for r in rows]

    async def search_similar(
        self,
        query: str,
        limit: int = 10,
    ) -> List[EpisodicEntry]:
        """Vector similarity search; falls back to full-text if no embedding."""
        embedding = await embedding_pipeline.embed(query)
        embed_str = pgvector_str(embedding)

        if embed_str:
            rows = await postgres_client.fetch(_SEARCH_VECTOR, embed_str, limit)
        else:
            rows = await postgres_client.fetch(_SEARCH_FTS, query, limit)

        return [self._row(r, r.get("relevance")) for r in rows]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row(row: Any, relevance: Optional[float] = None) -> EpisodicEntry:
        meta = row["metadata"] or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        return EpisodicEntry(
            id         = str(row["id"]),
            session_id = str(row["session_id"]),
            agent      = row["agent"],
            event_type = row["event_type"],
            content    = row["content"],
            metadata   = meta,
            relevance  = float(relevance) if relevance is not None else None,
            created_at = row["created_at"],
        )


episodic_store = EpisodicStore()
