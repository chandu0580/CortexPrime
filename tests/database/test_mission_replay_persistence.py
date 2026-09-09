"""Phase 10.26 (ADR-118) -- mission replay's durable layer, driven through the real path.

What this proves, with nothing mocked on the persistence path:

* A real ``CognitionEvent`` published through ``event_bus.publish`` (the supported
  application path; the store's docstring names it) lands as a row in
  ``mission_replay_events`` -- read back through an INDEPENDENT psycopg2
  connection, not through the store.
* The Redis hot layer holds the same event with the same store-assigned
  ``sequence``; deleting the Redis keys (the 72-hour window expiring) leaves the
  PostgreSQL rows untouched, and the real readers -- ``replay_store.get_events``
  / ``get_summary`` / ``get_timeline`` and the mounted ``/api/mission-replay``
  and ``/api/enterprise-replay`` routes -- serve the historical replay from
  PostgreSQL, ordered by sequence, payload and timestamp intact.
* When the PostgreSQL write fails, the event path is unaffected (fire-and-forget
  is the store's design) and the loss is explicit: a WARNING, not a DEBUG line.

Environment: a reachable PostgreSQL with CREATE DATABASE rights
(``CORTEX_TEST_PG_ADMIN_DSN``) and a reachable Redis (``CORTEX_TEST_REDIS_URL``,
default ``redis://127.0.0.1:55379/15`` -- database 15 so the test can empty its
own replay namespace without touching anyone else's window). Either being
unreachable SKIPS with a reason; a skip is DEFERRED, never a pass.

Loop discipline: every scenario runs inside one ``asyncio.run`` with a NullPool
engine bound to the migration-built database and a Redis client connected in
that same loop -- the pooled-connection-across-loops trap ``tests/conftest.py``
documents.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid

import pytest

ADMIN_DSN = os.getenv(
    "CORTEX_TEST_PG_ADMIN_DSN",
    "postgresql+psycopg2://cortex:cortex@127.0.0.1:55437/postgres",
)
TEST_REDIS_URL = os.getenv("CORTEX_TEST_REDIS_URL", "redis://127.0.0.1:55379/15")


def _pg_reachable() -> bool:
    if os.getenv("SKIP_DB_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        return False
    try:
        import sqlalchemy as sa

        eng = sa.create_engine(ADMIN_DSN, future=True, connect_args={"connect_timeout": 3})
        with eng.connect() as c:
            c.execute(sa.text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:  # noqa: BLE001 - unreachable is a skip, not a failure
        return False


def _redis_reachable() -> bool:
    try:
        import redis

        r = redis.Redis.from_url(TEST_REDIS_URL, socket_connect_timeout=2)
        ok = bool(r.ping())
        r.close()
        return ok
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.skipif(not _pg_reachable(), reason="DEFERRED: no reachable PostgreSQL with CREATE DATABASE rights (CORTEX_TEST_PG_ADMIN_DSN)"),
    pytest.mark.skipif(not _redis_reachable(), reason="DEFERRED: no reachable Redis for the hot layer (CORTEX_TEST_REDIS_URL)"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def migrated_db():
    """A brand-new database, migrated to head by Alembic, dropped afterwards."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    name = f"cortex_test_replay_{uuid.uuid4().hex[:8]}"
    admin = sa.create_engine(ADMIN_DSN, future=True, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(sa.text(f"CREATE DATABASE {name}"))

    base = ADMIN_DSN.rsplit("/", 1)[0]
    sync_dsn = f"{base}/{name}"
    plain_dsn = sync_dsn.replace("postgresql+psycopg2://", "postgresql://", 1)

    previous = os.environ.get("POSTGRES_URL")
    os.environ["POSTGRES_URL"] = plain_dsn
    try:
        cfg = Config()
        cfg.set_main_option("script_location", "backend/database/migrations")
        command.upgrade(cfg, "head")
    finally:
        if previous is None:
            os.environ.pop("POSTGRES_URL", None)
        else:
            os.environ["POSTGRES_URL"] = previous

    yield {"name": name, "sync": sync_dsn, "plain": plain_dsn}

    with admin.connect() as c:
        c.execute(sa.text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{name}' AND pid <> pg_backend_pid()"))
        c.execute(sa.text(f"DROP DATABASE IF EXISTS {name}"))
    admin.dispose()


def _bind_session_factory(monkeypatch, plain_dsn: str):
    """Point the REAL ``AsyncSessionLocal`` (looked up on the engine module by the
    store at call time) at *plain_dsn* with a NullPool engine."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import backend.database.engine  # noqa: F401 - ensure the submodule is loaded

    engine_module = sys.modules["backend.database.engine"]
    async_dsn = plain_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(async_dsn, future=True, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(engine_module, "AsyncSessionLocal", maker)
    return engine


@pytest.fixture
def real_persistence(migrated_db, monkeypatch):
    """The real store, the real bus, the real session factory on the migrated DB,
    the real Redis on an isolated database index. Yields helpers for independent
    SQL inspection."""
    import sqlalchemy as sa

    monkeypatch.setenv("REDIS_URL", TEST_REDIS_URL)
    for key in ("JWT_SECRET_KEY", "JWT_REFRESH_SECRET_KEY", "SECRET_KEY"):
        if not os.getenv(key):
            monkeypatch.setenv(key, "t" * 40)

    engine = _bind_session_factory(monkeypatch, migrated_db["plain"])
    sync = sa.create_engine(migrated_db["sync"], future=True)

    def rows(execution_id: str):
        with sync.connect() as c:
            return c.execute(sa.text(
                "SELECT sequence, event_type, agent, status, message, event_ts, latency_ms, payload "
                "FROM mission_replay_events WHERE execution_id = :e ORDER BY sequence"
            ), {"e": execution_id}).mappings().all()

    yield {"rows": rows, "engine": engine, "sync": sync, "db": migrated_db}

    asyncio.run(engine.dispose())
    sync.dispose()


# ---------------------------------------------------------------------------
# Helpers that run INSIDE a scenario's loop
# ---------------------------------------------------------------------------

async def _redis_open():
    from backend.infrastructure.redis.connection import redis_connection

    await redis_connection.close()          # a client from an earlier loop is unusable here
    # The singleton captures its URL when it is constructed -- in a full test run
    # that happened in an earlier module, with whatever REDIS_URL was set then.
    # Point it at the isolated test index for this scenario and clear any
    # circuit-breaker count those earlier attempts left behind.
    redis_connection._p1026_saved_url = redis_connection._url
    redis_connection._url = TEST_REDIS_URL
    redis_connection.reset_circuit_breaker()
    assert await redis_connection.connect(), f"Redis test database must be reachable ({TEST_REDIS_URL})"
    return redis_connection


async def _redis_close(conn):
    await conn.close()
    conn._url = conn._p1026_saved_url


async def _flush_replay_namespace(conn):
    """Only this test's namespace, only on the isolated test database index."""
    keys = await conn.client.keys("cx:replay:*")
    if keys:
        await conn.client.delete(*keys)


async def _publish_three(execution_id: str):
    """Three real events through the supported application path."""
    from backend.events.event_bus import event_bus, publish_event
    from backend.events.event_models import CognitionEvent

    e1 = CognitionEvent(agent="planner", event_type="execution_started", status="running",
                        execution_id=execution_id, message="mission begins",
                        payload={"k": "v1", "n": 1})
    await event_bus.publish(e1)
    await publish_event(agent="researcher", execution_id=execution_id, event_type="tool_called",
                        status="running", phase="research", message="calling search",
                        payload={"tool": "search", "args": {"q": "x"}})
    e3 = CognitionEvent(agent="planner", event_type="execution_completed", status="completed",
                        execution_id=execution_id, message="mission done",
                        payload={"k": "v3", "nested": {"a": [1, 2]}}, latency_ms=12.5)
    await event_bus.publish(e3)
    # publish() schedules record() as background tasks -- let them finish, and
    # surface any exception a task raised (the store must never raise).
    results = await _settle_bus_tasks()
    assert not [r for r in results if isinstance(r, Exception)], results
    return [e1, e3]


async def _settle_bus_tasks():
    """Await the bus's background tasks that belong to THIS loop. The bus is a
    process-wide singleton and, in a full test run, still holds pending tasks
    from other modules' (closed) event loops; awaiting those raises."""
    from backend.events.event_bus import event_bus

    loop = asyncio.get_running_loop()
    mine = [t for t in list(event_bus._background_tasks) if t.get_loop() is loop]
    return await asyncio.gather(*mine, return_exceptions=True)


def _mounted_app():
    """The two replay routers, included exactly as router_registry includes them."""
    from fastapi import FastAPI

    import backend.api.enterprise_replay_routes as ent_r
    import backend.api.mission_replay_routes as replay_r

    app = FastAPI()
    app.include_router(replay_r.router, prefix="/api")
    app.include_router(ent_r.router)
    return app


def _auth():
    from backend.auth.jwt_handler import create_access_token

    return {"Authorization": "Bearer " + create_access_token("replay-test@cortexprime.test", role="operator")}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_real_event_persists_and_survives_redis_loss(real_persistence):
    """The brief's durability sequence, end to end, on the real path."""
    import httpx

    from backend.services import mission_replay_store as mrs
    from backend.services.mission_replay_store import replay_store

    execution_id = f"replay-test-{uuid.uuid4().hex[:8]}"
    rows = real_persistence["rows"]

    async def scenario():
        conn = await _redis_open()
        try:
            await _flush_replay_namespace(conn)
            published = await _publish_three(execution_id)

            # 1-2. PostgreSQL, independently.
            pg = rows(execution_id)
            assert len(pg) == 3
            assert [r["sequence"] for r in pg] == [1, 2, 3]
            assert {r["event_type"] for r in pg} == {"mission_started", "tool_called", "mission_completed"}
            by_type = {r["event_type"]: r for r in pg}
            assert by_type["mission_completed"]["payload"] == {"k": "v3", "nested": {"a": [1, 2]}}
            assert by_type["mission_completed"]["latency_ms"] == 12.5
            assert by_type["tool_called"]["payload"] == {"tool": "search", "args": {"q": "x"}}
            assert by_type["mission_started"]["event_ts"] == published[0].timestamp
            assert by_type["mission_completed"]["event_ts"] == published[1].timestamp

            # 3. Redis holds the same events with the same store-assigned sequence.
            raw = [__import__("json").loads(x) for x in await conn.client.lrange(mrs._list_key(execution_id), 0, -1)]
            assert len(raw) == 3
            assert sorted(e["sequence"] for e in raw) == [1, 2, 3]
            redis_seq_by_type = {e["event_type"]: e["sequence"] for e in raw}
            assert redis_seq_by_type == {r["event_type"]: r["sequence"] for r in pg}
            assert {e["event_id"] for e in raw} >= {published[0].event_id, published[1].event_id}

            # 4. The window expires.
            deleted = await conn.client.delete(mrs._list_key(execution_id), mrs._seq_key(execution_id), mrs._meta_key(execution_id))
            assert deleted >= 1
            assert await conn.client.llen(mrs._list_key(execution_id)) == 0

            # 5. PostgreSQL is unaffected.
            assert [dict(r) for r in rows(execution_id)] == [dict(r) for r in pg]

            # 6-7. The real readers now answer from PostgreSQL.
            events = await replay_store.get_events(execution_id)
            assert [e["sequence"] for e in events] == [1, 2, 3]
            assert [e["event_type"] for e in events] == [r["event_type"] for r in pg]
            assert [e["payload"] for e in events] == [r["payload"] for r in pg]
            assert all(e["timestamp"] == e["event_ts"] == r["event_ts"] for e, r in zip(events, pg))
            summary = await replay_store.get_summary(execution_id)
            assert summary["found"] is True and summary["total_events"] == 3
            assert summary["first_ts"] is not None and summary["duration_ms"] is not None
            assert summary["is_complete"] is True
            timeline = await replay_store.get_timeline(execution_id)
            assert [t["offset_ms"] for t in timeline][0] == 0.0
            assert all(t["offset_ms"] is not None for t in timeline)

            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_mounted_app()), base_url="http://t") as client:
                r = await client.get(f"/api/mission-replay/{execution_id}", headers=_auth())
                assert r.status_code == 200, r.text
                body = r.json()
                assert [e["sequence"] for e in body["events"]] == [1, 2, 3]
                assert body["events"][-1]["payload"] == events[-1]["payload"]
                assert all(e["timestamp"] is not None for e in body["events"])
                assert body["summary"]["duration_ms"] is not None
                r = await client.get(f"/api/mission-replay/{execution_id}/graph", headers=_auth())
                assert r.status_code == 200 and r.json()["total_steps"] == 3
                r = await client.get(f"/api/enterprise-replay/events/{execution_id}", headers=_auth())
                assert r.status_code == 200 and len(r.json()["events"]) == 3
                # The hot window is empty on this isolated index, so the listing
                # must consult the durable store.
                r = await client.get("/api/mission-replay/?limit=50", headers=_auth())
                assert r.status_code == 200
                assert execution_id in r.json()["executions"]
        finally:
            await _flush_replay_namespace(conn)
            await _redis_close(conn)

    asyncio.run(scenario())


def test_db_write_failure_is_explicit_and_leaves_the_event_path_intact(real_persistence, monkeypatch, caplog):
    """The store's design swallows a failed PostgreSQL write -- the bus must never
    block on persistence -- but the loss must be visible at WARNING."""
    from backend.services import mission_replay_store as mrs

    # A database with no mission_replay_events table: the admin database.
    plain_admin = ADMIN_DSN.replace("postgresql+psycopg2://", "postgresql://", 1)
    _bind_session_factory(monkeypatch, plain_admin)

    execution_id = f"replay-fail-{uuid.uuid4().hex[:8]}"
    seen = []

    async def scenario():
        from backend.events.event_bus import event_bus
        from backend.events.event_models import CognitionEvent

        conn = await _redis_open()
        try:
            await _flush_replay_namespace(conn)
            event_bus.subscribe(seen.append)
            try:
                with caplog.at_level(logging.DEBUG, logger="backend.services.mission_replay_store"):
                    ev = CognitionEvent(agent="planner", event_type="execution_started", status="running",
                                        execution_id=execution_id, message="will not reach postgres")
                    await event_bus.publish(ev)
                    results = await _settle_bus_tasks()
            finally:
                event_bus.unsubscribe(seen.append)
            assert not [r for r in results if isinstance(r, Exception)], "record() must never raise into the bus"
            assert seen and seen[0].event_id == ev.event_id, "subscribers still receive the event"
            assert await conn.client.llen(mrs._list_key(execution_id)) == 1, "the hot layer still has it"
            skipped = [r for r in caplog.records if "replay_store DB write skipped" in r.getMessage()]
            assert skipped, "a lost durable copy must be logged"
            assert all(r.levelno >= logging.WARNING for r in skipped), "…at WARNING, not DEBUG"
            assert execution_id in skipped[0].getMessage()
        finally:
            await _flush_replay_namespace(conn)
            await _redis_close(conn)

    asyncio.run(scenario())


def test_migration_table_matches_the_model(real_persistence):
    """The migrated table and the ORM table agree column for column and index for index
    -- production schema (Alembic) and development metadata (create_all) are the same thing."""
    import sqlalchemy as sa

    from backend.database.models.mission_replay import MissionReplayEvent

    insp = sa.inspect(real_persistence["sync"])
    cols = {c["name"]: c for c in insp.get_columns("mission_replay_events")}
    model = MissionReplayEvent.__table__
    assert set(cols) == {c.name for c in model.columns}
    for c in model.columns:
        assert cols[c.name]["nullable"] == c.nullable, c.name
    assert cols["id"]["default"] and "gen_random_uuid" in cols["id"]["default"]
    assert cols["created_at"]["default"] and "now()" in cols["created_at"]["default"].lower()
    assert cols["sequence"]["default"] is None and cols["status"]["default"] is None
    got = {ix["name"]: list(ix["column_names"]) for ix in insp.get_indexes("mission_replay_events")}
    want = {ix.name: [c.name for c in ix.columns] for ix in model.indexes}
    assert got == want
    assert insp.get_pk_constraint("mission_replay_events")["constrained_columns"] == ["id"]
    assert insp.get_foreign_keys("mission_replay_events") == []
