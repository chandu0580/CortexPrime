"""
Migration test suite.

Tests cover:
  - fresh database   (all tables created from scratch)
  - existing database (upgrade is idempotent — already up to date)
  - schema upgrade    (new migration applied on top of prior state)
  - rollback          (downgrade to previous revision)
  - migrator helpers  (get_migration_status, MigrationResult)
  - /health/database  endpoint (FastAPI integration)

Requires a real PostgreSQL database.
All tests are skipped automatically when PostgreSQL is unavailable
(SKIP_DB_MIGRATIONS=true OR database unreachable).

Run only these tests:
    pytest tests/test_migrations.py -v

Run with a live DB (override env):
    POSTGRES_HOST=localhost pytest tests/test_migrations.py -v
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Skip the whole module if migrations are intentionally disabled or
# if no PostgreSQL is reachable
# ---------------------------------------------------------------------------

def _db_reachable() -> bool:
    """Best-effort check — return True only when PostgreSQL is live."""
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

def _run_alembic(cmd: str) -> None:
    """Run ``alembic <cmd>`` synchronously via the project's alembic.ini."""
    from backend.database.migrator import _build_alembic_config
    from alembic import command as alembic_command

    cfg = _build_alembic_config()
    if cmd == "upgrade head":
        alembic_command.upgrade(cfg, "head")
    elif cmd.startswith("downgrade "):
        target = cmd.split(" ", 1)[1]
        alembic_command.downgrade(cfg, target)
    else:
        raise ValueError(f"Unknown alembic command: {cmd}")


def _get_current_rev() -> list[str]:
    from backend.database.migrator import _sync_get_current_revisions
    return _sync_get_current_revisions()


def _get_head_revs() -> list[str]:
    from backend.database.migrator import _sync_get_head_revisions
    return _sync_get_head_revisions()


def _table_exists(table_name: str) -> bool:
    """Return True when *table_name* exists in the public schema."""
    from sqlalchemy import create_engine, text
    from backend.database.engine import _build_dsn

    dsn = _build_dsn().replace("postgresql+asyncpg://", "postgresql://", 1)
    engine = create_engine(dsn, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=:t"
                ),
                {"t": table_name},
            )
            return result.scalar_one() > 0
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Test: get_migration_status utility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_migration_status_returns_dict():
    """get_migration_status() always returns a valid dict."""
    from backend.database.migrator import get_migration_status

    status = await get_migration_status()
    assert isinstance(status, dict)
    assert "current_revision" in status
    assert "latest_revision"  in status
    assert "up_to_date"       in status
    assert "pending"          in status


# ---------------------------------------------------------------------------
# Test: fresh database — all tables created
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fresh_database_all_tables_created():
    """
    After ``alembic upgrade head`` on a fresh DB every migration table
    must exist: missions, episodic_memory, audit_logs, etc.
    """
    # Bring schema to head (idempotent if already there)
    _run_alembic("upgrade head")

    expected_tables = [
        "missions",
        "episodic_memory",
        "semantic_memory",
        "reflection_history",
        "runtime_analytics",
        "embedding_cache",
        "audit_logs",
        "alembic_version",
    ]
    for table in expected_tables:
        assert _table_exists(table), f"Table '{table}' missing after upgrade head"


# ---------------------------------------------------------------------------
# Test: upgrade is idempotent (existing database)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_existing_database_idempotent():
    """Running upgrade head a second time must succeed without errors."""
    _run_alembic("upgrade head")
    _run_alembic("upgrade head")  # second run — must be a no-op

    current = _get_current_rev()
    heads   = _get_head_revs()
    assert set(current) == set(heads), "Revisions mismatch after double upgrade"


# ---------------------------------------------------------------------------
# Test: schema upgrade — audit_logs migration applies cleanly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_schema_upgrade_audit_logs():
    """
    Downgrade to before the audit_logs migration, verify table is gone,
    then upgrade again and verify the table is recreated.
    """
    # Start from head
    _run_alembic("upgrade head")
    assert _table_exists("audit_logs"), "audit_logs must exist at head"

    # Downgrade by one step (removes audit_logs)
    _run_alembic("downgrade 0001_initial_schema")
    assert not _table_exists("audit_logs"), (
        "audit_logs must be dropped after downgrade to 0001_initial_schema"
    )

    # Upgrade back to head
    _run_alembic("upgrade head")
    assert _table_exists("audit_logs"), (
        "audit_logs must be recreated after upgrade head"
    )


# ---------------------------------------------------------------------------
# Test: rollback — downgrade to base removes all tables
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rollback_to_base():
    """
    Downgrading to ``base`` (no revisions applied) should remove all
    application tables created by the migrations.
    """
    _run_alembic("upgrade head")  # ensure we start from head

    _run_alembic("downgrade base")

    core_tables = [
        "missions",
        "episodic_memory",
        "semantic_memory",
        "reflection_history",
        "runtime_analytics",
        "embedding_cache",
        "audit_logs",
    ]
    for table in core_tables:
        assert not _table_exists(table), (
            f"Table '{table}' should be gone after downgrade base"
        )

    # Re-apply so subsequent tests are not broken
    _run_alembic("upgrade head")


# ---------------------------------------------------------------------------
# Test: run_migrations() async wrapper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_migrations_success():
    """run_migrations() returns MigrationResult with status='success'."""
    from backend.database.migrator import run_migrations, MigrationResult

    result = await run_migrations()
    assert isinstance(result, MigrationResult)
    assert result.status == "success"
    assert result.error is None
    assert result.revision is not None


@pytest.mark.asyncio
async def test_run_migrations_skip_flag(monkeypatch):
    """SKIP_DB_MIGRATIONS=true must short-circuit without touching DB."""
    monkeypatch.setenv("SKIP_DB_MIGRATIONS", "true")
    from backend.database.migrator import run_migrations

    result = await run_migrations()
    assert result.status == "skipped"


# ---------------------------------------------------------------------------
# Test: /health/database FastAPI endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_database_endpoint():
    """
    GET /health/database returns the expected keys and a non-offline status
    when PostgreSQL is reachable and all migrations are applied.
    """
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    # Ensure migrations are applied
    _run_alembic("upgrade head")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health/database")

    assert resp.status_code == 200
    body = resp.json()
    assert "status"       in body
    assert "connectivity" in body
    assert "migration"    in body
    assert body["status"] in ("healthy", "degraded")
    assert body["migration"]["up_to_date"] is True
    assert body["migration"]["pending"]    is False


# ---------------------------------------------------------------------------
# Test: /health/database shows pending when migration is not applied
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_database_shows_pending_when_behind():
    """
    After downgrading one step, GET /health/database must report
    ``pending=True`` and ``up_to_date=False``.
    """
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    _run_alembic("upgrade head")
    _run_alembic("downgrade 0001_initial_schema")  # one step behind

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health/database")

    body = resp.json()
    assert body["migration"]["pending"]    is True
    assert body["migration"]["up_to_date"] is False

    # Restore
    _run_alembic("upgrade head")
