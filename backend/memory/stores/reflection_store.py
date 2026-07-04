"""
Reflection Memory Store — PostgreSQL (reflection_history).

Single source of truth: all reads and writes target ``reflection_history``,
the Alembic-managed, ORM-backed table.

The legacy ``reflection_log`` table was consolidated into ``reflection_history``
by migration 0003_consolidate_reflection_tables.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.memory.db.postgres_client import postgres_client
from backend.memory.embedding_pipeline import embedding_pipeline, pgvector_str
from backend.memory.models import ReflectionEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL — all targeting reflection_history
# ---------------------------------------------------------------------------

_INSERT = """
INSERT INTO reflection_history
    (id, mission_id, agent, reflection, embedding, score, metadata, created_at)
VALUES ($1, $2::uuid, $3, $4, $5::vector, $6, $7::jsonb, $8)
"""

_INSERT_NO_EMBED = """
INSERT INTO reflection_history
    (id, mission_id, agent, reflection, score, metadata, created_at)
VALUES ($1, $2::uuid, $3, $4, $5, $6::jsonb, $7)
"""

_BY_MISSION = """
SELECT id, mission_id, agent, reflection, score, metadata, created_at
FROM reflection_history
WHERE mission_id = $1::uuid
ORDER BY created_at DESC
"""

_BY_AGENT = """
SELECT id, mission_id, agent, reflection, score, metadata, created_at
FROM reflection_history
WHERE agent = $1
ORDER BY created_at DESC
LIMIT $2
"""

_RECENT = """
SELECT id, mission_id, agent, reflection, score, metadata, created_at
FROM reflection_history
ORDER BY created_at DESC
LIMIT $1
"""

_SEARCH_VECTOR = """
SELECT id, mission_id, agent, reflection, score, metadata, created_at,
       1 - (embedding <=> $1::vector) AS similarity
FROM reflection_history
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1::vector
LIMIT $2
"""

_SEARCH_FTS = """
SELECT id, mission_id, agent, reflection, score, metadata, created_at,
       NULL::float AS similarity
FROM reflection_history
WHERE to_tsvector('english', reflection) @@ plainto_tsquery('english', $1)
ORDER BY created_at DESC
LIMIT $2
"""


class ReflectionStore:
    """
    Reflection memory backed by PostgreSQL — ``reflection_history`` table only.

    All reads and writes use a single table.  The ORM-based
    ``ReflectionRepository`` reads the same table, so there is no split path.
    """

    async def store(
        self,
        agent:      str,
        reflection: str,
        mission_id: Optional[str]            = None,
        score:      Optional[float]          = None,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist a reflection entry. Returns the new memory ID."""
        entry_id   = str(uuid4())
        embedding  = await embedding_pipeline.embed(reflection)
        embed_str  = pgvector_str(embedding)
        created_at = datetime.utcnow()
        meta_json  = json.dumps(metadata or {})

        if embed_str:
            await postgres_client.execute(
                _INSERT,
                entry_id, mission_id, agent, reflection,
                embed_str, score, meta_json, created_at,
            )
        else:
            await postgres_client.execute(
                _INSERT_NO_EMBED,
                entry_id, mission_id, agent, reflection,
                score, meta_json, created_at,
            )

        logger.debug("Reflection stored id=%s agent=%s", entry_id[:8], agent)
        return entry_id

    async def get_by_mission(self, mission_id: str) -> List[ReflectionEntry]:
        rows = await postgres_client.fetch(_BY_MISSION, mission_id)
        return [self._row(r) for r in rows]

    async def get_by_agent(self, agent: str, limit: int = 20) -> List[ReflectionEntry]:
        rows = await postgres_client.fetch(_BY_AGENT, agent, limit)
        return [self._row(r) for r in rows]

    async def get_recent(self, limit: int = 10) -> List[ReflectionEntry]:
        rows = await postgres_client.fetch(_RECENT, limit)
        return [self._row(r) for r in rows]

    async def search_similar(
        self,
        query: str,
        limit: int = 10,
    ) -> List[ReflectionEntry]:
        """
        Vector similarity search over reflections.

        Falls back to PostgreSQL full-text search when embeddings are
        not available (e.g. no OPENAI_API_KEY set).
        """
        embedding = await embedding_pipeline.embed(query)
        embed_str = pgvector_str(embedding)

        if embed_str:
            rows = await postgres_client.fetch(_SEARCH_VECTOR, embed_str, limit)
        else:
            rows = await postgres_client.fetch(_SEARCH_FTS, query, limit)

        return [self._row(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row(row: Any) -> ReflectionEntry:
        meta = row["metadata"] or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        return ReflectionEntry(
            id         = str(row["id"]),
            mission_id = str(row["mission_id"]) if row.get("mission_id") else None,
            agent      = row["agent"],
            reflection = row["reflection"],
            score      = float(row["score"]) if row.get("score") is not None else None,
            metadata   = meta,
            created_at = row["created_at"],
        )


reflection_store = ReflectionStore()
