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

class SchemaBootstrapRefused(RuntimeError):
    """``init_db`` was called in production. Refused, loudly.

    Not a warning and not a fallback. See ``init_db`` for why.
    """


def _is_production() -> bool:
    """Whether this process believes it is production.

    Reads the same variables the rest of the platform reads, and treats
    *unset* as production. That default is the point: an environment nobody
    configured is more likely to be a container somebody deployed than a
    laptop, and the failure modes are not symmetric — refusing on a laptop
    prints an error, permitting in production silently forks the schema.
    """
    raw = (
        os.getenv("CORTEXPRIME_ENVIRONMENT")
        or os.getenv("ENVIRONMENT")
        or os.getenv("APP_ENV")
        or ""
    ).strip().lower()
    if not raw:
        return os.getenv("CORTEXPRIME_ALLOW_SCHEMA_BOOTSTRAP", "").strip().lower() not in (
            "1", "true", "yes",
        )
    return raw in ("prod", "production", "staging", "live")


async def init_db(*, allow_non_production: bool = False) -> None:
    """Create every table on ``Base.metadata``. **Refused in production.**

    Why this is gated rather than merely discouraged
    -------------------------------------------------
    ``create_all`` and Alembic are two ways to arrive at a schema, and running
    both means neither is authoritative. Concretely, before this gate existed,
    ``backend/main.py`` called this **as the fallback when migration failed** —
    so a production deployment whose migration errored would create the tables
    from the current models instead, start cleanly, and log a warning. The
    result is a database that no migration ever produced: ``alembic_version``
    stuck at whatever last succeeded, columns present that no revision added,
    and the next migration failing against a schema it cannot reason about.

    That is a silent divergence, discovered later, in production, by a query.
    So this refuses instead. ``SchemaBootstrapRefused`` is deliberately not
    caught by the callers: a production process that cannot establish its
    schema through migrations must not start.

    ``allow_non_production=True`` is the caller stating that it knows this path
    is for development. It still checks the environment — the flag permits, it
    does not override.

    Note also that this creates tables from **``Base.metadata`` only**. The
    Phase 5.1 durable tables live on ``DURABLE_METADATA`` and are not visible to
    it, so even in development this has never been able to produce a complete
    schema; ``verify_durability`` is what checks that one.
    """
    if _is_production() or not allow_non_production:
        raise SchemaBootstrapRefused(
            "init_db() creates tables outside Alembic and is refused here. "
            "A schema produced by create_all is one no migration authored: "
            "alembic_version does not describe it, and the next migration will "
            "run against a database it cannot reason about. Run "
            "'alembic upgrade head'. Development callers must pass "
            "allow_non_production=True and set CORTEXPRIME_ENVIRONMENT to a "
            "non-production value."
        )
    logger.warning(
        "init_db() is creating tables with create_all outside Alembic. This is "
        "a development path; the resulting schema is not one any migration "
        "authored and must never be promoted."
    )
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
