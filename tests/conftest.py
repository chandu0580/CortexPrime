"""
pytest configuration for CortexPrime integration tests.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Must be set before any module imports that validate JWT_SECRET_KEY
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-pytest-suite-do-not-use-in-prod")
os.environ.setdefault("AUTH_DISABLED", "false")

# Prevent real Azure OpenAI API calls during tests.
# Must start before any module-level AzureOpenAI() instantiations.
patch("openai.AzureOpenAI").start()

# Use asyncio event loop for all async tests in this test suite
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(autouse=True)
def _isolate_alert_correlator_store():
    # enterprise_alert_correlator sits between three detectors (deploy-
    # regression, flaky-test, rollback) and its own real, file-backed
    # incident_history_store singleton persists across the whole test
    # session. Without this, whichever test happens to run first for a
    # given service name "wins" the real incident, and every later test
    # using the same service (in this file or any other) gets routed down
    # the "duplicate signal" path instead of the fresh-signal path it
    # actually expects — non-deterministic depending on collection order.
    # Global, not per-file, because the correlator is cross-cutting by
    # design: any future detector wired into it inherits this same risk.
    from backend.services.enterprise_alert_correlator import IncidentHistoryStore
    with tempfile.TemporaryDirectory() as tmpdir:
        test_store = IncidentHistoryStore(file_path=Path(tmpdir) / "incidents.json")
        with patch("backend.services.enterprise_alert_correlator.incident_history_store", test_store):
            yield


@pytest.fixture(autouse=True)
def _reap_stale_postgres_backends():
    # Correction to the "harmless test-only churn" assumption in
    # _reset_postgres_pool/_reset_sqlalchemy_engine below: orphaned asyncpg
    # connections whose owning event loop is gone are NOT harmless — a
    # full-suite run proved it. If one was mid-transaction when its loop
    # closed, Postgres keeps that transaction (and its locks) open until
    # the dead TCP connection is noticed, which can take far longer than
    # any test run's patience. That single stale idle-in-transaction
    # connection is enough to hang a later DDL statement (e.g.
    # test_migrations.py's downgrade dropping bounded-context tables)
    # forever waiting on a lock. Reap them with a plain sync psycopg2
    # connection (no event loop involved at all) before every test — safe
    # because tests run sequentially, so anything idle-in-transaction at
    # the start of a new test is guaranteed to be leftover from a
    # finished one, never a legitimately in-flight operation.
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "cortex"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            dbname=os.getenv("POSTGRES_DB", "cortexdb"),
            connect_timeout=3,
        )
    except Exception:
        yield
        return
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                "AND state IN ('idle in transaction', 'idle in transaction (aborted)')"
            )
    except Exception:
        pass
    finally:
        conn.close()
    yield


@pytest.fixture(autouse=True)
def _reset_postgres_pool():
    # postgres_client is a module-level singleton whose asyncpg pool is
    # lazily created and cached against whichever event loop existed at
    # creation time. pytest-asyncio gives each test function its own event
    # loop, so any test after the first Postgres-touching one inherits a
    # pool bound to an already-closed loop, raising "RuntimeError: Event
    # loop is closed" deep inside asyncpg. Reset before every test so
    # pool() lazily recreates against the CURRENT loop instead. Not
    # closing the stale pool here — its loop is already gone by the time
    # we'd try, so close() would hit the identical hang; any lock those
    # orphaned connections were holding is now handled by
    # _reap_stale_postgres_backends above.
    from backend.memory.db.postgres_client import postgres_client
    postgres_client._pool = None
    yield


@pytest.fixture(autouse=True)
def _reset_sqlalchemy_engine():
    # Same event-loop-crossing issue as postgres_client above, in a
    # second, separate pool: backend.database.engine's async engine +
    # sessionmaker are created once at module-import time and bound to
    # whichever event loop existed then (used by ReflectionRepository and
    # friends). Recreate both fresh before each test so they bind to the
    # CURRENT loop instead of whatever stale one they started on. Not
    # disposing the old engine here for the same reason as postgres_client
    # — its loop is already gone by the time we'd try; any lock it was
    # holding is handled by _reap_stale_postgres_backends above.
    # Must fetch the submodule via sys.modules, not `import
    # backend.database.engine as db_engine`: backend/database/__init__.py
    # does `from backend.database.engine import engine`, which shadows the
    # submodule name `engine` inside the `backend.database` package
    # namespace with the AsyncEngine *instance* once that package has been
    # imported, so a plain dotted import can silently resolve to the
    # instance instead of the module.
    import sys
    import backend.database.engine  # ensure it's been imported at least once
    db_engine = sys.modules["backend.database.engine"]
    db_engine.engine = db_engine._create_engine()
    db_engine.AsyncSessionLocal = db_engine.async_sessionmaker(
        bind=db_engine.engine,
        class_=db_engine.AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    yield
