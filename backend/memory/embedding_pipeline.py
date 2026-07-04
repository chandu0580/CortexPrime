"""
CortexPrime Embedding Pipeline.

Priority order:
  1. OpenAI text-embedding-3-small  (1536 dims) — requires OPENAI_API_KEY
  2. ChromaDB SentenceTransformer   (384 dims)  — local, no API needed

Embeddings are cached in Redis (24h TTL) to avoid redundant API calls.

PostgreSQL pgvector columns are defined as vector(1536), so only 1536-dim
embeddings are stored there.  384-dim embeddings from the local fallback are
NOT stored in pgvector — dimension mismatches are now observable (logged at
CRITICAL, audit event fired, health endpoint updated) instead of silent.

Environment variables:
  EMBED_DIM                    — expected pgvector column width (default: 1536)
  STRICT_EMBEDDING_VALIDATION  — if "true", startup aborts on dimension mismatch
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OPENAI_DIM      = 1536      # text-embedding-3-small
EMBED_DIM       = int(os.getenv("EMBED_DIM", str(OPENAI_DIM)))
EMBED_CACHE_TTL = 86400     # 24 h in seconds

# Embedding status values
STATUS_HEALTHY  = "healthy"
STATUS_DEGRADED = "degraded"
STATUS_FAILED   = "failed"


class EmbeddingPipeline:
    """
    Async embedding generation with Redis caching, multi-backend support,
    and full observability (telemetry counters + audit events on mismatch).
    """

    def __init__(self) -> None:
        self._openai_client  = None
        self._local_ef       = None
        self._use_openai: bool = bool(os.getenv("OPENAI_API_KEY"))

        # ── Telemetry counters ──────────────────────────────
        self._cache_hits     = 0
        self._cache_misses   = 0
        self._openai_calls   = 0
        self._local_calls    = 0
        self._failures       = 0
        self._mismatch_count = 0

        # ── Status ──────────────────────────────────────────
        # Updated by _generate() and _record_mismatch(); never set back to
        # healthy automatically — that requires an explicit validate_dimensions().
        self._status: str = STATUS_HEALTHY

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed(self, text: str, use_cache: bool = True) -> Optional[List[float]]:
        """Return embedding for *text*, or None on failure."""
        if not text or not text.strip():
            return None

        if use_cache:
            cached = await self._get_cached(text)
            if cached is not None:
                self._cache_hits += 1
                return cached
            self._cache_misses += 1

        embedding = await self._generate(text)

        if embedding and use_cache:
            await self._set_cached(text, embedding)

        return embedding

    async def embed_batch(
        self, texts: List[str], use_cache: bool = True
    ) -> List[Optional[List[float]]]:
        """Embed multiple texts concurrently."""
        return list(
            await asyncio.gather(*[self.embed(t, use_cache) for t in texts])
        )

    @property
    def native_dim(self) -> int:
        """Dimension produced by the currently active embedding backend."""
        return OPENAI_DIM if self._use_openai else 384

    @property
    def backend(self) -> str:
        return "openai" if self._use_openai else "local"

    @property
    def embedding_status(self) -> str:
        """'healthy' | 'degraded' | 'failed'"""
        return self._status

    def get_telemetry(self) -> Dict[str, Any]:
        """
        Return a snapshot of all embedding metrics.

        Used by ``GET /health/embeddings`` and startup validation.
        """
        return {
            "active_model":       (
                "text-embedding-3-small" if self._use_openai else "all-MiniLM-L6-v2"
            ),
            "expected_dimension": EMBED_DIM,
            "actual_dimension":   self.native_dim,
            "embedding_status":   self._status,
            "degraded_mode":      not self._use_openai,
            "cache_hits":         self._cache_hits,
            "cache_misses":       self._cache_misses,
            "openai_calls":       self._openai_calls,
            "local_calls":        self._local_calls,
            "failures":           self._failures,
            "mismatch_count":     self._mismatch_count,
        }

    async def validate_dimensions(self) -> Dict[str, Any]:
        """
        Generate a test embedding and compare its dimension against EMBED_DIM.

        Called during startup.  Returns::

            {
                "ok": bool,
                "expected": int,
                "actual": int,
                "model": str,
                "error": str | None   # only present on generation failure
            }
        """
        try:
            vec = await self._generate("dimension validation probe")
        except Exception as exc:
            self._status = STATUS_FAILED
            return {
                "ok":       False,
                "expected": EMBED_DIM,
                "actual":   0,
                "model":    self.backend,
                "error":    str(exc),
            }

        if vec is None:
            self._status = STATUS_FAILED
            return {
                "ok":       False,
                "expected": EMBED_DIM,
                "actual":   0,
                "model":    self.backend,
                "error":    "generation returned None",
            }

        actual = len(vec)
        ok     = (actual == EMBED_DIM)
        if ok and self._status == STATUS_HEALTHY:
            pass  # stay healthy
        elif not ok:
            self._status = STATUS_DEGRADED

        return {
            "ok":       ok,
            "expected": EMBED_DIM,
            "actual":   actual,
            "model":    self.backend,
        }

    # ------------------------------------------------------------------
    # Observability — dimension mismatch
    # ------------------------------------------------------------------

    def _record_mismatch(
        self,
        actual_dim:  int,
        model:       str,
        text_length: int,
    ) -> None:
        """
        Called by ``pgvector_str`` whenever a dimension mismatch is detected.

        - Increments mismatch counter.
        - Sets status to 'degraded'.
        - Logs at CRITICAL level.
        - Fires a fire-and-forget audit event.
        """
        self._mismatch_count += 1
        self._status = STATUS_DEGRADED

        logger.critical(
            "EMBEDDING_DIMENSION_MISMATCH | expected=%d actual=%d "
            "model=%s text_length=%d | vector discarded — pgvector row stored without embedding",
            EMBED_DIM, actual_dim, model, text_length,
        )

        try:
            from backend.safety.audit_logger import audit_logger
            audit_logger.log(
                execution_id = "embedding_pipeline",
                agent        = "embedding_pipeline",
                action       = "embedding_dimension_mismatch",
                target       = f"pgvector(dim={EMBED_DIM})",
                risk_level   = "high",
                outcome      = "rejected",
                reason       = (
                    f"Embedding dim {actual_dim} != expected {EMBED_DIM}; "
                    "vector discarded — row stored without embedding"
                ),
                metadata     = {
                    "event":        "embedding_dimension_mismatch",
                    "expected_dim": EMBED_DIM,
                    "actual_dim":   actual_dim,
                    "model":        model,
                    "text_length":  text_length,
                },
            )
        except Exception as exc:
            logger.error("Failed to fire audit event for embedding mismatch: %s", exc)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def _generate(self, text: str) -> Optional[List[float]]:
        if self._use_openai:
            result = await self._openai_embed(text)
            if result is not None:
                self._openai_calls += 1
                return result
            # OpenAI failed — switch to local (degraded mode)
            self._status = STATUS_DEGRADED

        result = await asyncio.to_thread(self._local_embed, text)
        if result is not None:
            self._local_calls += 1
        else:
            self._failures += 1
            self._status = STATUS_FAILED
        return result

    async def _openai_embed(self, text: str) -> Optional[List[float]]:
        try:
            client   = self._get_openai_client()
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8191],
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.warning("OpenAI embedding failed, switching to local fallback: %s", exc)
            self._use_openai = False
            return None

    def _local_embed(self, text: str) -> Optional[List[float]]:
        try:
            ef     = self._get_local_ef()
            result = ef([text])
            return list(result[0])
        except Exception as exc:
            logger.error("Local embedding failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Client accessors (lazy)
    # ------------------------------------------------------------------

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )
        return self._openai_client

    def _get_local_ef(self):
        if self._local_ef is None:
            from chromadb.utils.embedding_functions import (
                SentenceTransformerEmbeddingFunction,
            )
            self._local_ef = SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        return self._local_ef

    # ------------------------------------------------------------------
    # Redis cache
    # ------------------------------------------------------------------

    async def _get_cached(self, text: str) -> Optional[List[float]]:
        try:
            from backend.memory.db.redis_client import redis_client
            key  = f"emb:{self._hash(text)}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def _set_cached(self, text: str, embedding: List[float]) -> None:
        try:
            from backend.memory.db.redis_client import redis_client
            key = f"emb:{self._hash(text)}"
            await redis_client.set(key, json.dumps(embedding), ex=EMBED_CACHE_TTL)
        except Exception:
            pass

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:32]


# =========================================================
# SINGLETON
# =========================================================

embedding_pipeline = EmbeddingPipeline()


# =========================================================
# HELPER — format embedding for pgvector
# =========================================================

def pgvector_str(
    embedding:    Optional[List[float]],
    expected_dim: int = EMBED_DIM,
) -> Optional[str]:
    """
    Return the embedding formatted as a pgvector literal string, or ``None``
    if the dimension doesn't match the PostgreSQL column definition.

    When a mismatch occurs:
    - Logs at CRITICAL level.
    - Fires a fire-and-forget audit event via ``embedding_pipeline._record_mismatch()``.
    - Returns ``None`` (caller stores the row without an embedding vector).

    This makes embedding degradation **observable** instead of silent.
    """
    if not embedding:
        return None

    actual = len(embedding)
    if actual == expected_dim:
        return f"[{','.join(str(v) for v in embedding)}]"

    # Dimension mismatch — never silently discard; fire observability event
    embedding_pipeline._record_mismatch(
        actual_dim  = actual,
        model       = embedding_pipeline.backend,
        text_length = 0,   # text not available at this call site
    )
    return None
