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

# Add project root to sys.path so ``backend.*`` imports resolve
_root = Path(__file__).resolve().parents[4]  # .../cortexprime
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Load all ORM models so their metadata is registered
import backend.database.models  # noqa: F401 — side-effect import
backend.database.models._ensure_bc_models()  # load bounded context models

from backend.database.base   import Base
from backend.database.engine import _build_dsn

# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


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

def do_run_migrations(connection) -> None:
    context.configure(
        connection      = connection,
        target_metadata = target_metadata,
        compare_type    = True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_build_dsn(), future=True)

    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)

    await engine.dispose()


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
