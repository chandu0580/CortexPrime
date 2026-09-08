"""The cost_tracking WRITE path, against a real migration-built PostgreSQL database.

Phase 10.20, ADR-114. Until this test existed, nothing in the suite asserted
that a cost record was ever persisted: the alias test exercises the pure
``estimate_cost`` function and the anomaly-monitor test mocks the read path.
Meanwhile ``cost_engine.record()`` -- the only writer -- had been failing on
every migrated database with ``UndefinedColumn "extra_data"``, catching the
exception, logging a warning, and returning ``None`` exactly as it does on
success. Every cost record was silently lost and no test could tell.

What this test refuses to do
----------------------------
* It does not mock the repository, the session, or the engine. ``record()``
  runs unmodified, through the real ``AsyncSessionLocal`` sessionmaker, bound
  to a database that ``alembic upgrade head`` built moments earlier.
* It does not read the row back through the code under test. Verification is
  an independent psycopg2 connection issuing plain SQL.
* It does not pass vacuously. If the database is unreachable the test SKIPS,
  visibly; when it runs, the core assertion is a row count that must rise.

How the real path is bound to the test database
-----------------------------------------------
``backend.database.engine`` builds its async engine at import time from
``POSTGRES_URL``. ``record()`` looks ``AsyncSessionLocal`` up on that module at
call time, so pointing that one attribute at a real ``async_sessionmaker`` over
a real ``create_async_engine`` for the migration-built database runs the
genuine write path against the genuine schema. Nothing is faked; only the
address is chosen.

Environment
-----------
``CORTEX_TEST_PG_ADMIN_DSN`` -- a psycopg2 DSN with CREATE DATABASE rights.
Defaults to the disposable phase instance this repository's harnesses use.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import date

import pytest

ADMIN_DSN = os.getenv(
    "CORTEX_TEST_PG_ADMIN_DSN",
    "postgresql+psycopg2://cortex:cortex@127.0.0.1:55437/postgres",
)


def _reachable() -> bool:
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


pytestmark = pytest.mark.skipif(
    not _reachable(),
    reason="no reachable PostgreSQL with CREATE DATABASE rights "
           "(set CORTEX_TEST_PG_ADMIN_DSN)",
)


@pytest.fixture(scope="module")
def migrated_db():
    """A brand-new database, migrated to head by Alembic, dropped afterwards."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    name = f"cortex_test_cost_{uuid.uuid4().hex[:8]}"
    admin = sa.create_engine(ADMIN_DSN, future=True, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(sa.text(f"CREATE DATABASE {name}"))

    base = ADMIN_DSN.rsplit("/", 1)[0]
    sync_dsn = f"{base}/{name}"
    plain_dsn = sync_dsn.replace("postgresql+psycopg2://", "postgresql://", 1)

    # migrations/env.py builds its own async DSN from POSTGRES_URL.
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


@pytest.fixture
def real_write_path(migrated_db, monkeypatch):
    """Bind the REAL AsyncSessionLocal to the migration-built database."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import sys

    import backend.database.engine  # noqa: F401 - ensure the submodule is loaded

    # ``backend/database/__init__.py`` does ``from backend.database.engine import
    # engine``, which shadows the SUBMODULE name with the AsyncEngine object, so
    # ``import backend.database.engine as m`` binds the engine, not the module.
    # tests/conftest.py documents the same trap and uses sys.modules for it.
    engine_module = sys.modules["backend.database.engine"]

    async_dsn = migrated_db["plain"].replace("postgresql://", "postgresql+asyncpg://", 1)
    # NullPool: every test drives record() through its own asyncio.run() loop,
    # and a pooled asyncpg connection is bound to the loop that opened it.
    # Production runs in one loop; the test must not leak connections across
    # several. Nothing about the write path changes -- only pooling.
    engine = create_async_engine(async_dsn, future=True, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(engine_module, "AsyncSessionLocal", maker)
    yield
    asyncio.run(engine.dispose())


def _count(migrated_db) -> int:
    import sqlalchemy as sa

    eng = sa.create_engine(migrated_db["sync"], future=True)
    with eng.connect() as c:
        n = c.execute(sa.text("SELECT count(*) FROM cost_tracking")).scalar()
    eng.dispose()
    return int(n)


def _rows(migrated_db, mission_id: str):
    import sqlalchemy as sa

    eng = sa.create_engine(migrated_db["sync"], future=True)
    with eng.connect() as c:
        rows = c.execute(sa.text(
            "SELECT provider, service, model, prompt_tokens, completion_tokens, "
            "total_tokens, cost_usd, report_date, extra, mission_id "
            "FROM cost_tracking WHERE mission_id = :m ORDER BY created_at"),
            {"m": mission_id}).mappings().all()
    eng.dispose()
    return rows


@pytest.mark.usefixtures("real_write_path")
def test_record_persists_a_row_readable_independently(migrated_db):
    """The canary. If persistence silently disappears again, this fails."""
    from backend.analytics.cost_engine import cost_engine

    before = _count(migrated_db)
    mission = f"m-{uuid.uuid4().hex[:8]}"
    result = asyncio.run(cost_engine.record(
        provider="anthropic", service="chat_completion", model="claude-sonnet-5",
        prompt_tokens=120, completion_tokens=30, mission_id=mission,
        extra={"objective": "write-path test", "confidence": 0.75},
    ))
    assert result is None                       # the documented return
    assert _count(migrated_db) == before + 1    # a row exists -- read by plain SQL

    (row,) = _rows(migrated_db, mission)
    assert row["provider"] == "anthropic"
    assert row["service"] == "chat_completion"
    assert row["model"] == "claude-sonnet-5"
    assert row["prompt_tokens"] == 120 and row["completion_tokens"] == 30
    assert row["total_tokens"] == 150
    assert row["report_date"] == date.today()
    assert row["cost_usd"] > 0.0               # estimated from the built-in table
    # The payload lands in the column migration 0004 created -- ``extra`` --
    # and round-trips as JSON.
    assert row["extra"] == {"objective": "write-path test", "confidence": 0.75}


@pytest.mark.usefixtures("real_write_path")
def test_repeated_calls_each_persist(migrated_db):
    from backend.analytics.cost_engine import cost_engine

    before = _count(migrated_db)
    mission = f"m-{uuid.uuid4().hex[:8]}"
    async def three_calls():
        for i in range(3):
            await cost_engine.record(
                provider="openai", service="embedding", model="text-embedding-3-small",
                prompt_tokens=10 * (i + 1), mission_id=mission, extra=None,
            )

    asyncio.run(three_calls())   # one loop, three sequential writes -- as production runs
    assert _count(migrated_db) == before + 3
    rows = _rows(migrated_db, mission)
    assert [r["prompt_tokens"] for r in rows] == [10, 20, 30]
    assert all(r["extra"] is None for r in rows)


@pytest.mark.usefixtures("real_write_path")
def test_a_failing_write_rolls_back_and_is_reported_not_raised(migrated_db, caplog):
    """The error semantics as they ARE: swallowed and logged. Documented, not changed.

    ``provider`` is NOT NULL in 0004. Passing None reaches the database and is
    refused there, so this exercises a real rolled-back transaction, not a
    Python-side validation. ``record()`` must not raise (every caller is
    fire-and-forget and relies on that), must log the failure, and must persist
    nothing -- a partial or phantom row would be worse than the old silence.
    """
    from backend.analytics.cost_engine import cost_engine

    before = _count(migrated_db)
    with caplog.at_level(logging.WARNING, logger="backend.analytics.cost_engine"):
        result = asyncio.run(cost_engine.record(
            provider=None, service="chat_completion", model="x",  # type: ignore[arg-type]
            prompt_tokens=1, completion_tokens=1, mission_id="m-must-not-persist",
        ))
    assert result is None
    assert _count(migrated_db) == before
    assert _rows(migrated_db, "m-must-not-persist") == []
    assert any("cost_engine.record failed" in r.getMessage() for r in caplog.records), \
        "a persistence failure must at least be logged; silence is the defect this test guards"


@pytest.mark.usefixtures("real_write_path")
def test_model_matches_the_migrated_table(migrated_db):
    """The model's contract is the migration's. Every column, by name and type."""
    import sqlalchemy as sa

    from backend.database.models.cost_tracking import CostRecord

    eng = sa.create_engine(migrated_db["sync"], future=True)
    reflected = sa.Table("cost_tracking", sa.MetaData(), autoload_with=eng)
    model = CostRecord.__table__

    # Same column SET (declaration order is a class-layout detail -- the mixin
    # columns sit last -- not a schema contract; INSERTs are by name).
    assert {c.name for c in model.columns} == {c.name for c in reflected.columns}
    for c in model.columns:
        r = reflected.columns[c.name]
        # Type by AFFINITY, the way Alembic compares: 0004 declares sa.Float(),
        # which PostgreSQL stores and reflects as DOUBLE PRECISION -- a Float
        # subclass. A compiled-string compare would call that a mismatch and
        # would be wrong, because the migration itself is the source of it.
        assert c.type._type_affinity is r.type._type_affinity, (c.name, c.type, r.type)
        if getattr(c.type, "length", None) is not None:
            assert c.type.length == r.type.length, c.name
        assert c.nullable == r.nullable, c.name
    assert "extra" in model.columns and "extra_data" not in model.columns
    assert {i.name for i in model.indexes} == {
        i["name"] for i in sa.inspect(eng).get_indexes("cost_tracking")}
    eng.dispose()
