"""
Async PostgreSQL connection pool — lazy-initialized singleton.
Gracefully degrades when PostgreSQL is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# asyncpg is optional; if not installed the client stays offline
try:
    import asyncpg
    _ASYNCPG_AVAILABLE = True
except ImportError:
    _ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg not installed — PostgreSQL memory store disabled")


class PostgresClient:
    """Async PostgreSQL connection pool with lazy initialization."""

    def __init__(self) -> None:
        self._pool: Any = None
        self._available: bool = _ASYNCPG_AVAILABLE

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def pool(self):
        if self._pool is not None:
            return self._pool
        if not self._available:
            return None
        await self._connect()
        return self._pool

    async def _connect(self) -> None:
        dsn = os.getenv("POSTGRES_URL") or (
            "postgresql://{user}:{pw}@{host}:{port}/{db}".format(
                user=os.getenv("POSTGRES_USER",     "cortex"),
                pw  =os.getenv("POSTGRES_PASSWORD", ""),
                host=os.getenv("POSTGRES_HOST",     "localhost"),
                port=os.getenv("POSTGRES_PORT",     "5432"),
                db  =os.getenv("POSTGRES_DB",       "cortexdb"),
            )
        )
        try:
            self._pool = await asyncpg.create_pool(
                dsn,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            logger.info("PostgreSQL pool connected")
        except Exception as exc:
            logger.warning(f"PostgreSQL unavailable: {exc}")
            self._available = False

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    async def execute(self, query: str, *args) -> Optional[str]:
        p = await self.pool()
        if p is None:
            return None
        async with p.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> List[Any]:
        p = await self.pool()
        if p is None:
            return []
        async with p.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[Any]:
        p = await self.pool()
        if p is None:
            return None
        async with p.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def is_available(self) -> bool:
        return self._available


postgres_client = PostgresClient()
