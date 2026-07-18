"""
Async SQLAlchemy engine and session factory.

Configuration is read from environment variables (same names used by
the legacy asyncpg postgres_client so both can share the same .env):

  POSTGRES_URL      full DSN (overrides all individual vars below)
  POSTGRES_USER     default: cortex
  POSTGRES_PASSWORD default: cortexpass
  POSTGRES_HOST     default: localhost
  POSTGRES_PORT     default: 5432
  POSTGRES_DB       default: cortexdb

Pool settings
-------------
  DB_POOL_SIZE      default: 10 (increased from 5 for production concurrency)
  DB_MAX_OVERFLOW   default: 20
  DB_POOL_TIMEOUT   default: 30   (seconds)
  DB_POOL_RECYCLE   default: 1800 (seconds — recycle idle connections every 30 min)
  DB_ECHO_SQL       default: false (set to "true" to log all SQL)
"""
from __future__ import annotations

import asyncio
import logging
import os
from functools import wraps
from typing import Any, Callable, TypeVar

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.database.base import Base

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_DB_RETRY_MAX = int(os.getenv("DB_RETRY_MAX", "3"))
_DB_RETRY_DELAY = float(os.getenv("DB_RETRY_DELAY", "0.5"))


def db_retry(max_retries: int = _DB_RETRY_MAX, delay: float = _DB_RETRY_DELAY):
    """Decorator that retries database operations on transient failures.

    Catches sqlalchemy.exc.OperationalError and retries with exponential back-off.
    """
    from sqlalchemy.exc import OperationalError

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        wait = delay * (2 ** (attempt - 1))
                        logger.warning(
                            "DB retry %d/%d after %.1fs: %s",
                            attempt, max_retries, wait, exc,
                        )
                        await asyncio.sleep(wait)
            raise last_exc  # type: ignore[union-attr]
        return wrapper  # type: ignore[return-value]
    return decorator

# ---------------------------------------------------------------------------
# DSN construction
# ---------------------------------------------------------------------------

def _build_dsn() -> str:
    """Return an asyncpg-compatible PostgreSQL DSN."""
    if url := os.getenv("POSTGRES_URL"):
        # Replace the scheme if the caller provided a plain postgres:// URL
        return url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
            "postgres://", "postgresql+asyncpg://", 1
        )
    user = os.getenv("POSTGRES_USER",     "cortex")
    pw   = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST",     "localhost")
    port = os.getenv("POSTGRES_PORT",     "5432")
    db   = os.getenv("POSTGRES_DB",       "cortexdb")
    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}"


# ---------------------------------------------------------------------------
# Engine singleton
# ---------------------------------------------------------------------------

def _create_engine() -> AsyncEngine:
    dsn = _build_dsn()
    return create_async_engine(
        dsn,
        pool_size      = int(os.getenv("DB_POOL_SIZE",    "10")),
        max_overflow   = int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_timeout   = int(os.getenv("DB_POOL_TIMEOUT", "30")),
        pool_recycle   = int(os.getenv("DB_POOL_RECYCLE", "1800")),
        pool_pre_ping  = True,                  # evict stale connections
        echo           = os.getenv("DB_ECHO_SQL", "").lower() == "true",
        future         = True,
    )


engine: AsyncEngine = _create_engine()

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind        = engine,
    class_      = AsyncSession,
    expire_on_commit = False,   # safe for async — prevents lazy-load after commit
    autoflush   = False,
    autocommit  = False,
)


# ---------------------------------------------------------------------------
# Table bootstrap (dev / test / migration-less environments)
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """
    Create all tables registered on Base.metadata.

    Safe to call on startup — uses CREATE TABLE IF NOT EXISTS semantics.
    In production, prefer Alembic migrations instead.
    """
    from backend.database.models import _ensure_bc_models
    _ensure_bc_models()
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "CREATE EXTENSION IF NOT EXISTS vector"
            )
        )
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised (create_all)")


async def dispose_engine() -> None:
    """Gracefully close all pooled connections. Call on app shutdown."""
    await engine.dispose()
    logger.info("Database engine disposed")
