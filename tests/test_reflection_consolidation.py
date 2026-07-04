"""
Reflection Memory Consolidation Tests.

Verifies the single-table invariant: every write via ReflectionStore
must be immediately readable via ReflectionRepository (and vice versa),
since both now target ``reflection_history``.

Tests:
  1. write_then_read_same_record  — store via ReflectionStore, read via ReflectionRepository
  2. store_read_by_mission        — store two entries, read by mission_id
  3. store_read_by_agent          — store two entries, read by agent
  4. store_read_recent            — recent() returns latest entry first
  5. no_reflection_log_table      — reflection_log must not exist after migration
  6. reflection_store_endpoint    — POST /api/memory/reflect, GET /api/vector/reflection/agent/{agent}
  7. critic_injection_flow        — simulate the critic memory injection path

All tests are skipped when PostgreSQL is unavailable.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional

import pytest

# ---------------------------------------------------------------------------
# Skip the whole module without a live database
# ---------------------------------------------------------------------------

def _db_reachable() -> bool:
    if os.getenv("SKIP_DB_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        return False
    try:
        from backend.database.migrator import _sync_db_reachable
        return _sync_db_reachable()
    except Exception:
        return False


_SKIP_REASON = "PostgreSQL unavailable or SKIP_DB_MIGRATIONS=true"
pytestmark = pytest.mark.skipif(not _db_reachable(), reason=_SKIP_REASON)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_pg_pool():
    """Synchronously obtain the asyncpg pool (or None)."""
    import asyncio
    from backend.memory.db.postgres_client import postgres_client

    async def _inner():
        return await postgres_client.pool()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_inner())
    finally:
        loop.close()


async def _table_exists_async(table_name: str) -> bool:
    from backend.memory.db.postgres_client import postgres_client
    pool = await postgres_client.pool()
    if pool is None:
        return False
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=$1",
            table_name,
        )
    return result > 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def unique_mission_id() -> str:
    """Return a fresh UUID string for test isolation."""
    return str(uuid.uuid4())


@pytest.fixture
async def unique_agent() -> str:
    """Return a unique agent name so tests don't collide on shared DB."""
    return f"test_agent_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Test 1 — write via ReflectionStore, read via ReflectionRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_then_read_same_record(unique_mission_id, unique_agent):
    """
    Core single-table invariant:
      ReflectionStore.store() → reflection_history
      ReflectionRepository.get_by_agent() ← reflection_history
    Both must see the same row.
    """
    from backend.memory.stores.reflection_store import ReflectionStore
    from backend.database.repositories.reflection_repository import ReflectionRepository
    from backend.database.engine import AsyncSessionLocal

    store = ReflectionStore()
    text  = f"Test reflection written at {uuid.uuid4()}"
    score = 0.91

    # Write via asyncpg store
    mem_id = await store.store(
        agent      = unique_agent,
        reflection = text,
        mission_id = unique_mission_id,
        score      = score,
        metadata   = {"test": True},
    )

    assert mem_id, "store() must return a non-empty ID"

    # Read back via ORM repository
    async with AsyncSessionLocal() as session:
        repo    = ReflectionRepository(session)
        records = await repo.get_by_agent(unique_agent, limit=5)

    assert records, (
        "ReflectionRepository.get_by_agent() returned no rows — "
        "write path may still target reflection_log instead of reflection_history"
    )

    ids = [str(r.id) for r in records]
    assert mem_id in ids, (
        f"Written ID {mem_id[:8]} not found in ORM read results {[i[:8] for i in ids]}"
    )

    # Verify field integrity
    record = next(r for r in records if str(r.id) == mem_id)
    assert record.reflection == text
    assert record.agent      == unique_agent
    assert abs(record.score - score) < 1e-6


# ---------------------------------------------------------------------------
# Test 2 — store and read by mission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_read_by_mission(unique_mission_id, unique_agent):
    """Both reflections stored for a mission must be retrievable by mission_id."""
    from backend.memory.stores.reflection_store import ReflectionStore
    import uuid as _uuid

    store = ReflectionStore()

    id1 = await store.store(
        agent="critic", reflection="First reflection", mission_id=unique_mission_id
    )
    id2 = await store.store(
        agent="optimizer", reflection="Second reflection", mission_id=unique_mission_id
    )

    entries = await store.get_by_mission(unique_mission_id)
    stored_ids = {e.id for e in entries}

    assert id1 in stored_ids, f"id1 {id1[:8]} missing from get_by_mission()"
    assert id2 in stored_ids, f"id2 {id2[:8]} missing from get_by_mission()"


# ---------------------------------------------------------------------------
# Test 3 — store and read by agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_read_by_agent(unique_agent):
    """Entries stored for a given agent must be returned by get_by_agent."""
    from backend.memory.stores.reflection_store import ReflectionStore

    store = ReflectionStore()

    stored_ids = set()
    for i in range(3):
        mem_id = await store.store(
            agent      = unique_agent,
            reflection = f"Agent reflection #{i}",
            score      = 0.7 + i * 0.05,
        )
        stored_ids.add(mem_id)

    entries = await store.get_by_agent(unique_agent, limit=10)
    returned_ids = {e.id for e in entries}

    assert stored_ids.issubset(returned_ids), (
        f"Missing IDs: {stored_ids - returned_ids}"
    )


# ---------------------------------------------------------------------------
# Test 4 — get_recent returns latest first
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recent_returns_latest_first(unique_agent):
    """get_recent() must return newest entries first."""
    from backend.memory.stores.reflection_store import ReflectionStore

    store = ReflectionStore()
    ids = []
    for i in range(3):
        mem_id = await store.store(
            agent      = unique_agent,
            reflection = f"Ordered reflection {i}",
        )
        ids.append(mem_id)

    recent = await store.get_recent(limit=10)
    # The last stored ID should appear before the first stored ID in the result
    returned_ids = [e.id for e in recent]
    last_pos  = next((i for i, e_id in enumerate(returned_ids) if e_id == ids[-1]), None)
    first_pos = next((i for i, e_id in enumerate(returned_ids) if e_id == ids[0]),  None)

    assert last_pos is not None, "Most recent entry not found in get_recent()"
    assert first_pos is not None, "First entry not found in get_recent()"
    assert last_pos <= first_pos, (
        "get_recent() is not returning newest entries first"
    )


# ---------------------------------------------------------------------------
# Test 5 — reflection_log table must not exist after migration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reflection_log_table_removed():
    """
    After migration 0003, the reflection_log table must be absent.
    Its existence would indicate the migration did not run or was rolled back.
    """
    exists = await _table_exists_async("reflection_log")
    assert not exists, (
        "reflection_log still exists — migration 0003_consolidate_reflection_tables "
        "may not have run yet. Run: alembic upgrade head"
    )


# ---------------------------------------------------------------------------
# Test 6 — HTTP API round-trip (POST /api/memory/reflect → GET /api/vector/…)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reflection_api_round_trip(unique_agent):
    """
    POST /api/memory/reflect stores a reflection.
    GET  /api/vector/reflection/agent/{agent} must return it.
    """
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    text  = f"API round-trip test {uuid.uuid4()}"
    token = "test-token"  # auth uses JWT — mock a valid token

    # Build a valid JWT so auth passes
    from backend.auth.jwt_handler import create_access_token
    valid_token = create_access_token({"sub": "test_user", "role": "admin"})

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers = {"Authorization": f"Bearer {valid_token}"}

        # POST — store reflection
        resp = await client.post(
            "/api/memory/reflect",
            json={"agent": unique_agent, "reflection": text, "score": 0.85},
            headers=headers,
        )

        # Accept 201 (created) or 200 (ok); treat 422/500 as test failures
        assert resp.status_code in (200, 201), (
            f"POST /api/memory/reflect returned {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "memory_id" in body or "id" in body, (
            f"Unexpected response shape: {body}"
        )

        # GET — retrieve by agent
        resp2 = await client.get(
            f"/api/vector/reflection/agent/{unique_agent}",
            headers=headers,
        )
        assert resp2.status_code == 200, (
            f"GET /api/vector/reflection/agent returned {resp2.status_code}"
        )
        entries = resp2.json()
        reflections = [e.get("reflection", "") for e in entries]
        assert any(text in r for r in reflections), (
            "Stored reflection text not found in GET response — "
            "API may still be reading from a different table"
        )


# ---------------------------------------------------------------------------
# Test 7 — critic_injection_flow (MemoryOrchestrator end-to-end)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_critic_injection_flow(unique_mission_id, unique_agent):
    """
    Simulate the critic memory injection path used in mission_runtime.py:

      1. Store a reflection via MemoryOrchestrator.store_reflection()
      2. Retrieve recent reflections via RetrievalEngine.retrieve()
      3. Assert the stored reflection appears in ctx.reflections

    This proves the full path: store → reflect_history → retrieve → inject.
    """
    from backend.memory.memory_orchestrator import MemoryOrchestrator
    from backend.memory.retrieval.retrieval_engine import RetrievalEngine, RetrievalConfig

    orch    = MemoryOrchestrator()
    engine  = RetrievalEngine()

    lesson  = f"Key lesson: always validate input at boundaries. ({uuid.uuid4()})"
    mem_id  = await orch.store_reflection(
        agent      = unique_agent,
        reflection = lesson,
        mission_id = unique_mission_id,
        score      = 0.95,
        metadata   = {"test": "critic_injection"},
    )

    assert mem_id, "MemoryOrchestrator.store_reflection() returned no ID"

    # Retrieve with n_reflections=5 to make sure our entry is included
    ctx = await engine.retrieve(
        query      = lesson[:80],
        session_id = unique_mission_id,
        config     = RetrievalConfig(n_reflections=5, n_episodic=0, n_semantic=0),
    )

    assert ctx.reflections, (
        "RetrievalEngine returned no reflections — "
        "reflection may not have been written to reflection_history"
    )

    ids = [r.id for r in ctx.reflections]
    assert mem_id in ids, (
        f"Stored reflection {mem_id[:8]} not found in retrieved context. "
        f"Got: {[i[:8] for i in ids]}"
    )

    # Verify the text survived the round-trip
    entry = next(r for r in ctx.reflections if r.id == mem_id)
    assert entry.reflection == lesson
