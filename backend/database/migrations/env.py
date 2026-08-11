"""
Alembic environment file — async-aware.

Reads the database DSN from the same environment variables used by the
SQLAlchemy engine so that migrations always target the same database.
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Add project root to sys.path so ``backend.*`` imports resolve.
#
# ``parents[3]``, not ``parents[4]``. This file is at
# ``<root>/backend/database/migrations/env.py``, so the fourth parent is
# ``C:\projects`` -- one level above the repository -- and adding it puts
# nothing importable on the path. Migrations only ever worked because they were
# run from the repository root, where the current directory already provides
# ``backend``; running Alembic from the directory its own ``alembic.ini`` lives
# in failed with ``ModuleNotFoundError: No module named 'backend'``.
_root = Path(__file__).resolve().parents[3]  # .../cortexprime
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Load all ORM models so their metadata is registered
import backend.database.models  # noqa: F401 — side-effect import
backend.database.models._ensure_bc_models()  # load bounded context models

from backend.database.base   import Base
from backend.database.durable.tables import DURABLE_METADATA
from backend.database.engine import _build_dsn

# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Both metadata objects, and the second one is not optional.
#
# The Phase 5.1-5.3 durable state layer -- execution, outbox, leases,
# idempotency, workers, capabilities, bindings, authorizations, delegation,
# delegation requests, queue, leadership, connector configuration -- lives on
# ``DURABLE_METADATA``, which is deliberately separate from ``Base.metadata``:
# those tables are Core tables with no ORM mapping, and mixing them into the
# declarative registry would put persistence concerns back inside the domain.
#
# Alembic does not know that. With ``target_metadata = Base.metadata`` alone,
# autogenerate compares a live database containing 13 ``cp_*`` tables against a
# model that describes none of them, concludes they are surplus, and emits
# ``op.drop_table`` for **every one** -- a generated migration that deletes the
# durable state layer. Nobody had run autogenerate since Phase 5.1, which is the
# only reason this had not happened yet.
#
# Alembic accepts a sequence here and unions them, so both are described and a
# generated migration reflects the whole schema.
target_metadata = [Base.metadata, DURABLE_METADATA]


# ---------------------------------------------------------------------------
# Offline (SQL-script) mode
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to the database."""
    url = _build_dsn()
    context.configure(
        url               = url,
        target_metadata   = target_metadata,
        literal_binds     = True,
        dialect_opts      = {"paramstyle": "named"},
        compare_type      = True,
        include_schemas   = False,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online (direct connection) mode
# ---------------------------------------------------------------------------

#: Alembic creates ``alembic_version.version_num`` as ``VARCHAR(32)`` and offers
#: no supported way to widen it. Two of this project's revision identifiers are
#: longer than that:
#:
#:     0003_consolidate_reflection_tables   34 characters
#:     0009_consolidate_connector_activity  35 characters
#:
#: so ``alembic upgrade head`` against a **blank** database fails at 0003 with
#: ``StringDataRightTruncationError`` -- which is to say a new production
#: deployment could not build its schema at all. The existing development
#: database does not hit this only because its column is ``VARCHAR(64)``,
#: widened out of band by somebody who met the same wall and fixed it locally.
#:
#: The proper fix is revision identifiers under 32 characters, but renaming them
#: now would orphan every database already stamped with the long ones. So the
#: column is widened here instead, before Alembic touches it -- idempotent,
#: applied to both blank and existing databases, and doing nothing when the
#: column is already wide enough.
_VERSION_NUM_WIDTH = 128


def _ensure_version_table_width(connection) -> None:
    """Make ``alembic_version.version_num`` wide enough for this project's ids."""
    import sqlalchemy as sa

    if connection.dialect.name != "postgresql":
        # SQLite does not enforce ``VARCHAR`` lengths, so there is nothing to
        # widen and ``ALTER COLUMN ... TYPE`` is not supported there anyway.
        return
    connection.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS alembic_version ("
            f"version_num VARCHAR({_VERSION_NUM_WIDTH}) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
    )
    connection.execute(
        sa.text(
            "ALTER TABLE alembic_version ALTER COLUMN version_num "
            f"TYPE VARCHAR({_VERSION_NUM_WIDTH})"
        )
    )


def do_run_migrations(connection) -> None:
    _ensure_version_table_width(connection)
    context.configure(
        connection      = connection,
        target_metadata = target_metadata,
        compare_type    = True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Apply migrations, and **commit them**.

    ``engine.begin()``, not ``engine.connect()``. Under SQLAlchemy 2.0 a bare
    ``connect()`` is commit-as-you-go: the DDL runs inside an implicit
    transaction that is rolled back when the block exits, so
    ``alembic upgrade head`` printed a full, correct-looking list of applied
    revisions and left the database exactly as it found it. Verified directly --
    every revision logged as applied, and afterwards the target database had
    zero tables and no ``alembic_version`` row.

    That is the worst possible failure shape for a migration runner: silent,
    and indistinguishable from success in the log. ``begin()`` commits when the
    block exits normally and rolls back on an exception, which is the behaviour
    the log was already claiming.
    """
    engine = create_async_engine(_build_dsn(), future=True)

    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)

    await engine.dispose()


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
