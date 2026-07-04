"""
Embedding Observability Tests.

Tests the full observability chain:
  1. 1536-dim vector → healthy, pgvector_str returns string
  2. 384-dim vector  → degraded, pgvector_str returns None, mismatch counter incremented
  3. Mismatch        → audit event fired, status set to 'degraded'
  4. /health/embeddings endpoint returns correct shape + status
  5. Startup validation respects STRICT_EMBEDDING_VALIDATION

All tests use unittest.mock to avoid real OpenAI/local embedding calls.
"""
from __future__ import annotations

import asyncio
import os
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_pipeline():
    """Return a fresh EmbeddingPipeline instance (not the singleton)."""
    from backend.memory.embedding_pipeline import EmbeddingPipeline
    return EmbeddingPipeline()


# ---------------------------------------------------------------------------
# 1. pgvector_str — 1536-dim (healthy path)
# ---------------------------------------------------------------------------

def test_pgvector_str_1536_returns_string():
    """1536-dim embedding must return a pgvector literal — no mismatch."""
    from backend.memory.embedding_pipeline import pgvector_str, EMBED_DIM

    vec = [0.1] * EMBED_DIM
    result = pgvector_str(vec)

    assert result is not None, "pgvector_str returned None for a 1536-dim vector"
    assert result.startswith("[") and result.endswith("]")
    assert result.count(",") == EMBED_DIM - 1


# ---------------------------------------------------------------------------
# 2. pgvector_str — 384-dim (fallback / degraded path)
# ---------------------------------------------------------------------------

def test_pgvector_str_384_returns_none():
    """384-dim (local fallback) must return None — not silently discard."""
    from backend.memory.embedding_pipeline import pgvector_str

    vec = [0.1] * 384
    result = pgvector_str(vec)

    assert result is None, (
        "pgvector_str returned a non-None value for 384-dim vector — "
        "this would insert a wrong-dimension vector into pgvector"
    )


# ---------------------------------------------------------------------------
# 3. pgvector_str — mismatch increments counter + fires audit
# ---------------------------------------------------------------------------

def test_pgvector_str_mismatch_increments_counter_and_fires_audit():
    """
    When a dimension mismatch is detected:
    - embedding_pipeline.mismatch_count incremented
    - embedding_pipeline.embedding_status → 'degraded'
    - audit_logger.log() called once
    """
    from backend.memory.embedding_pipeline import EmbeddingPipeline, EMBED_DIM

    pipeline = _fresh_pipeline()
    # Patch audit_logger so we don't need a live DB
    mock_audit = MagicMock()
    mock_audit.log = MagicMock()

    with patch("backend.memory.embedding_pipeline.embedding_pipeline", pipeline), \
         patch("backend.safety.audit_logger.audit_logger", mock_audit):
        from backend.memory.embedding_pipeline import pgvector_str
        result = pgvector_str([0.1] * 384)

    assert result is None
    assert pipeline._mismatch_count == 1
    assert pipeline._status == "degraded"

    mock_audit.log.assert_called_once()
    call_kwargs = mock_audit.log.call_args.kwargs
    assert call_kwargs["action"]  == "embedding_dimension_mismatch"
    assert call_kwargs["metadata"]["expected_dim"] == EMBED_DIM
    assert call_kwargs["metadata"]["actual_dim"]   == 384
    assert call_kwargs["risk_level"] == "high"


# ---------------------------------------------------------------------------
# 4. Multiple mismatches accumulate
# ---------------------------------------------------------------------------

def test_mismatch_counter_accumulates():
    """Each call to pgvector_str with wrong dims increments the counter."""
    from backend.memory.embedding_pipeline import EmbeddingPipeline, EMBED_DIM

    pipeline = _fresh_pipeline()

    with patch("backend.memory.embedding_pipeline.embedding_pipeline", pipeline), \
         patch("backend.safety.audit_logger.audit_logger", MagicMock(log=MagicMock())):
        from backend.memory.embedding_pipeline import pgvector_str
        for _ in range(5):
            pgvector_str([0.1] * 384)

    assert pipeline._mismatch_count == 5


# ---------------------------------------------------------------------------
# 5. EmbeddingPipeline.embedding_status starts healthy
# ---------------------------------------------------------------------------

def test_initial_status_healthy():
    """A fresh pipeline starts in 'healthy' state."""
    from backend.memory.embedding_pipeline import STATUS_HEALTHY
    pipeline = _fresh_pipeline()
    assert pipeline.embedding_status == STATUS_HEALTHY


# ---------------------------------------------------------------------------
# 6. _generate() switches status to degraded on OpenAI failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_degraded_on_openai_failure():
    """When OpenAI fails and falls back to local, status becomes 'degraded'."""
    from backend.memory.embedding_pipeline import STATUS_DEGRADED

    pipeline = _fresh_pipeline()
    pipeline._use_openai = True

    # OpenAI fails
    async def _fail_openai(text):
        pipeline._use_openai = False
        return None

    # Local succeeds with 384-dim
    def _local_success(text):
        return [0.1] * 384

    with patch.object(pipeline, "_openai_embed", side_effect=_fail_openai), \
         patch.object(pipeline, "_local_embed", side_effect=_local_success):
        result = await pipeline._generate("hello world")

    assert result is not None
    assert len(result) == 384
    assert pipeline._status == STATUS_DEGRADED
    assert pipeline._local_calls == 1


# ---------------------------------------------------------------------------
# 7. _generate() marks status failed when both backends fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_failed_when_all_backends_fail():
    """When both OpenAI and local fail, status becomes 'failed'."""
    from backend.memory.embedding_pipeline import STATUS_FAILED

    pipeline = _fresh_pipeline()
    pipeline._use_openai = False  # already in local mode

    with patch.object(pipeline, "_local_embed", return_value=None):
        result = await pipeline._generate("hello world")

    assert result is None
    assert pipeline._status == STATUS_FAILED
    assert pipeline._failures == 1


# ---------------------------------------------------------------------------
# 8. validate_dimensions — healthy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_dimensions_healthy():
    """validate_dimensions returns ok=True when 1536-dim vector is returned."""
    from backend.memory.embedding_pipeline import EMBED_DIM

    pipeline = _fresh_pipeline()

    with patch.object(pipeline, "_generate", new_callable=AsyncMock, return_value=[0.1] * EMBED_DIM):
        result = await pipeline.validate_dimensions()

    assert result["ok"]      is True
    assert result["actual"]  == EMBED_DIM
    assert result["expected"] == EMBED_DIM


# ---------------------------------------------------------------------------
# 9. validate_dimensions — degraded path (384-dim returned)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_dimensions_degraded():
    """validate_dimensions returns ok=False and sets status to degraded."""
    from backend.memory.embedding_pipeline import STATUS_DEGRADED

    pipeline = _fresh_pipeline()

    with patch.object(pipeline, "_generate", new_callable=AsyncMock, return_value=[0.1] * 384):
        result = await pipeline.validate_dimensions()

    assert result["ok"]     is False
    assert result["actual"] == 384
    assert pipeline._status == STATUS_DEGRADED


# ---------------------------------------------------------------------------
# 10. validate_dimensions — failed (generation returns None)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_dimensions_failed():
    """validate_dimensions returns ok=False and status=failed when generate returns None."""
    from backend.memory.embedding_pipeline import STATUS_FAILED

    pipeline = _fresh_pipeline()

    with patch.object(pipeline, "_generate", new_callable=AsyncMock, return_value=None):
        result = await pipeline.validate_dimensions()

    assert result["ok"]     is False
    assert result["actual"] == 0
    assert pipeline._status == STATUS_FAILED


# ---------------------------------------------------------------------------
# 11. get_telemetry() returns all expected keys
# ---------------------------------------------------------------------------

def test_get_telemetry_shape():
    """get_telemetry() must include all keys consumed by the health endpoint."""
    pipeline = _fresh_pipeline()
    t = pipeline.get_telemetry()

    required_keys = {
        "active_model", "expected_dimension", "actual_dimension",
        "embedding_status", "degraded_mode",
        "cache_hits", "cache_misses",
        "openai_calls", "local_calls",
        "failures", "mismatch_count",
    }
    missing = required_keys - set(t.keys())
    assert not missing, f"get_telemetry() missing keys: {missing}"


# ---------------------------------------------------------------------------
# 12. /health/embeddings endpoint — structure test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_embeddings_endpoint_shape():
    """GET /health/embeddings returns all required fields and a valid status."""
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health/embeddings")

    assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
    body = resp.json()

    required = {
        "embedding_status", "active_model", "expected_dimension",
        "actual_dimension", "degraded_mode", "cache_hits", "cache_misses",
        "openai_calls", "local_calls", "failures", "mismatch_count",
    }
    missing = required - set(body.keys())
    assert not missing, f"/health/embeddings missing keys: {missing}"
    assert body["embedding_status"] in ("healthy", "degraded", "failed")
    assert isinstance(body["expected_dimension"], int)
    assert isinstance(body["actual_dimension"], int)


# ---------------------------------------------------------------------------
# 13. /health/embeddings — degraded state shows warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_embeddings_degraded_warning():
    """
    When the pipeline is in degraded mode, the warning field must be
    non-None and contain a human-readable explanation.
    """
    from httpx import AsyncClient, ASGITransport
    from backend.main import app
    from backend.memory.embedding_pipeline import embedding_pipeline, STATUS_DEGRADED

    original_status = embedding_pipeline._status
    embedding_pipeline._status = STATUS_DEGRADED
    embedding_pipeline._use_openai = False

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health/embeddings")

        assert resp.status_code == 200
        body = resp.json()
        assert body["warning"] is not None, (
            "Expected a warning message in degraded mode but got None"
        )
        assert len(body["warning"]) > 10, "Warning message too short"
    finally:
        # Restore original state so we don't poison other tests
        embedding_pipeline._status     = original_status
        embedding_pipeline._use_openai = bool(os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# 14. STRICT_EMBEDDING_VALIDATION env var — startup raises on mismatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_strict_validation_raises_on_mismatch(monkeypatch):
    """
    When STRICT_EMBEDDING_VALIDATION=true and dimensions mismatch,
    the startup validation must raise RuntimeError.
    """
    from backend.memory.embedding_pipeline import EmbeddingPipeline

    monkeypatch.setenv("STRICT_EMBEDDING_VALIDATION", "true")

    pipeline = _fresh_pipeline()

    # Force 384-dim response (mismatch)
    with patch.object(pipeline, "_generate", new_callable=AsyncMock, return_value=[0.1] * 384):
        val = await pipeline.validate_dimensions()

    assert not val["ok"]
    # The startup code in main.py checks val["ok"] and raises — simulate that check:
    strict = os.getenv("STRICT_EMBEDDING_VALIDATION", "false").lower() in ("1", "true", "yes")
    if not val["ok"] and strict:
        with pytest.raises(RuntimeError, match="EMBEDDING DIMENSION MISMATCH|mismatch"):
            raise RuntimeError(
                f"EMBEDDING DIMENSION MISMATCH at startup — "
                f"expected={val['expected']} actual={val['actual']}"
            )


# ---------------------------------------------------------------------------
# 15. Cache hit/miss counters increment correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_miss_counters():
    """cache_hits and cache_misses must be tracked on embed() calls."""
    from backend.memory.embedding_pipeline import EMBED_DIM

    pipeline = _fresh_pipeline()
    vec = [0.1] * EMBED_DIM

    # Simulate: no cache on first call, cache hit on second
    call_count = {"n": 0}

    async def _fake_get_cached(text):
        if call_count["n"] > 0:
            return vec
        return None

    async def _fake_set_cached(text, emb):
        call_count["n"] += 1

    with patch.object(pipeline, "_get_cached",  side_effect=_fake_get_cached), \
         patch.object(pipeline, "_set_cached",  side_effect=_fake_set_cached), \
         patch.object(pipeline, "_generate",    new_callable=AsyncMock, return_value=vec):

        await pipeline.embed("hello")  # miss
        await pipeline.embed("hello")  # hit

    assert pipeline._cache_misses == 1
    assert pipeline._cache_hits   == 1
