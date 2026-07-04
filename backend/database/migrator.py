"""Automatic database migration runner.

Wraps Alembic programmatically so that ``alembic upgrade head`` runs
automatically on every CortexPrime startup, keeping the schema always
synchronised with the ORM models.

Usage
-----
Called from ``backend.main.startup()`` before any application code
accesses the database::

    from backend.database.migrator import run_migrations, get_migration_status
    result = await run_migrations()

Design
------
* ``run_migrations()`` and status queries are ``async`` â€” safe to await
  from a FastAPI startup event.
* Internally, Alembic's ``command.upgrade()`` is run in a **thread pool**
  because ``env.py`` uses ``asyncio.run()`` internally, which cannot be
  called from an already-running event loop.
* Connectivity is probed **before** attempting the migration so that the
  failure message is clear.
* Nothing in this module ever raises â€” callers must inspect
  ``MigrationResult.status``.

Environment variables
---------------------
SKIP_DB_MIGRATIONS
    Skip migration entirely (test / CI environments without PostgreSQL).
    Default: false.

BLOCK_ON_MIGRATION_FAILURE
    Raise an exception (blocking startup) when migration fails.
    Default: false (warn only).
    Set to ``"true"`` in production deployments.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Absolute path to alembic.ini â€” sibling of this file's parent directory
_ALEMBIC_INI = Path(__file__).parent / "migrations" / "alembic.ini"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MigrationResult:
    """Returned by :func:`run_migrations`."""

    status: str
    """``"success"`` | ``"skipped"`` | ``"failed"``"""

    revision: Optional[str] = None
    """Current head revision after upgrade (or ``None`` when skipped/failed)."""

    error: Optional[str] = None
    """Error message when *status* is ``"failed"``."""


# ---------------------------------------------------------------------------
# Sync helpers (executed inside a ThreadPoolExecutor)
# ---------------------------------------------------------------------------

def _build_alembic_config():
    """Return an Alembic ``Config`` object pointing at this project's ini."""
    from alembic.config import Config
    return Config(str(_ALEMBIC_INI))


def _sync_upgrade() -> None:
    """
    Run ``alembic upgrade head`` synchronously.

    **Must** be called from a thread pool so that ``asyncio.run()`` inside
    ``env.py`` can safely create a new event loop.
    """
    from alembic import command
    command.upgrade(_build_alembic_config(), "head")


def _sync_get_current_revisions() -> List[str]:
    """Query ``alembic_version`` with a synchronous psycopg2 connection."""
    from sqlalchemy import create_engine, text
    from backend.database.engine import _build_dsn

    # Strip the asyncpg driver â€” psycopg2 is used for sync access
    dsn = _build_dsn().replace("postgresql+asyncpg://", "postgresql://", 1)
    try:
        engine = create_engine(
            dsn,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchall()
        engine.dispose()
        return [row[0] for row in rows]
    except Exception:
        return []


def _sync_get_head_revisions() -> List[str]:
    """Return revision IDs that are currently ``heads`` in the script tree."""
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_build_alembic_config())
    return [rev.revision for rev in script.get_revisions("heads")]


def _sync_db_reachable() -> bool:
    """
    Return ``True`` if PostgreSQL accepts a connection.

    Uses a **5-second connect timeout** â€” never hangs the startup event.
    """
    from sqlalchemy import create_engine, text
    from backend.database.engine import _build_dsn

    dsn = _build_dsn().replace("postgresql+asyncpg://", "postgresql://", 1)
    try:
        engine = create_engine(
            dsn,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def run_migrations() -> MigrationResult:
    """
    Run ``alembic upgrade head`` in a background thread and return a
    :class:`MigrationResult`.

    Steps
    -----
    1. Honour ``SKIP_DB_MIGRATIONS`` â€” return immediately if set.
    2. Probe PostgreSQL connectivity (5-second timeout).
    3. Run ``alembic upgrade head`` in a thread pool.
    4. Query the current revision and return it in the result.

    Never raises â€” all errors are captured and returned.
    """
    # â”€â”€ Skip flag (test / CI environments) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _runtime_env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development").lower()
    _skip_flag = os.getenv("SKIP_DB_MIGRATIONS", "").lower() in ("1", "true", "yes")
    _run_migrations_default = "true" if _runtime_env == "production" else "false"
    _run_migrations = os.getenv(
        "STARTUP_DB_MIGRATIONS",
        _run_migrations_default,
    ).lower() in ("1", "true", "yes")
    if _skip_flag or not _run_migrations:
        if _skip_flag:
            logger.info("ℹ️  SKIP_DB_MIGRATIONS=true — skipping Alembic migration")
        else:
            logger.info(
                "Skipping startup database migrations in %s environment "
                "(set STARTUP_DB_MIGRATIONS=true to enable)",
                _runtime_env,
            )
        return MigrationResult(status="skipped")

    logger.info("ðŸ”„ Running database migrations (alembic upgrade head)â€¦")
    loop = asyncio.get_event_loop()

    # â”€â”€ Connectivity probe â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    reachable = await loop.run_in_executor(None, _sync_db_reachable)
    if not reachable:
        msg = "Database unreachable â€” cannot run migrations"
        logger.warning("âš ï¸  %s", msg)
        return MigrationResult(status="failed", error=msg)

    # â”€â”€ Run upgrade â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        await loop.run_in_executor(None, _sync_upgrade)
        current = await loop.run_in_executor(None, _sync_get_current_revisions)
        revision = current[0] if current else "unknown"
        logger.info("âœ… Database migration complete â€” revision: %s", revision)
        return MigrationResult(status="success", revision=revision)
    except Exception as exc:
        logger.error("âŒ Database migration failed: %s", exc, exc_info=True)
        return MigrationResult(status="failed", error=str(exc))


async def get_migration_status() -> Dict[str, Any]:
    """
    Return the current migration state **without running** any migrations.

    Returns
    -------
    ::

        {
            "current_revision": str | list | None,
            "latest_revision":  str | list | None,
            "up_to_date":       bool | None,
            "pending":          bool | None,
            "error":            str,          # only present on error
        }
    """
    try:
        loop = asyncio.get_event_loop()
        current = await loop.run_in_executor(None, _sync_get_current_revisions)
        heads   = await loop.run_in_executor(None, _sync_get_head_revisions)

        def _canonical(revision: str) -> str:
            return revision.split("_", 1)[0]

        current_rev: Any = (
            current[0] if len(current) == 1 else (current if current else None)
        )
        head_rev: Any = (
            heads[0] if len(heads) == 1 else (heads if heads else None)
        )
        current_set = set(current)
        head_set = set(heads)
        canonical_current = {_canonical(revision) for revision in current}
        canonical_heads = {_canonical(revision) for revision in heads}
        up_to_date = bool(current) and (
            current_set == head_set or canonical_current == canonical_heads
        )

        return {
            "current_revision": current_rev,
            "latest_revision":  head_rev,
            "up_to_date":       up_to_date,
            "pending":          not up_to_date,
        }
    except Exception as exc:
        logger.warning("Cannot determine migration status: %s", exc)
        return {
            "current_revision": None,
            "latest_revision":  None,
            "up_to_date":       None,
            "pending":          None,
            "error":            str(exc),
        }
