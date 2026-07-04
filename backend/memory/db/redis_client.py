"""
Async Redis client — lazy-initialized singleton.
Gracefully degrades when Redis is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    logger.warning("redis[hiredis] not installed — Redis memory store disabled")


class RedisClient:
    """Async Redis client with lazy initialization."""

    def __init__(self) -> None:
        self._client: Any = None
        self._available: bool = _REDIS_AVAILABLE

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def client(self) -> Optional[Any]:
        if self._client is not None:
            return self._client
        if not self._available:
            return None
        await self._connect()
        return self._client

    async def _connect(self) -> None:
        password = os.getenv("REDIS_PASSWORD", "")
        host     = os.getenv("REDIS_HOST",     "localhost")
        port     = os.getenv("REDIS_PORT",     "6379")

        # Build URL — omit password if empty to avoid "redis://:@host" issues
        if password:
            url = f"redis://:{password}@{host}:{port}/0"
        else:
            url = f"redis://{host}:{port}/0"

        # Allow full override via REDIS_URL
        url = os.getenv("REDIS_URL", url)

        try:
            c = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=5,
            )
            await c.ping()
            self._client = c
            logger.info("Redis client connected")
        except Exception as exc:
            logger.warning(f"Redis unavailable: {exc}")
            self._available = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        c = await self.client()
        if c is None:
            return None
        return await c.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        c = await self.client()
        if c is None:
            return
        await c.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> None:
        c = await self.client()
        if c is None:
            return
        await c.delete(*keys)

    async def hset(self, name: str, mapping: Dict[str, str]) -> None:
        c = await self.client()
        if c is None:
            return
        await c.hset(name, mapping=mapping)

    async def hgetall(self, name: str) -> Dict[str, str]:
        c = await self.client()
        if c is None:
            return {}
        return await c.hgetall(name) or {}

    async def lpush(self, key: str, *values: str) -> None:
        c = await self.client()
        if c is None:
            return
        await c.lpush(key, *values)

    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        c = await self.client()
        if c is None:
            return []
        return await c.lrange(key, start, end)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        c = await self.client()
        if c is None:
            return
        await c.ltrim(key, start, end)

    async def expire(self, key: str, seconds: int) -> None:
        c = await self.client()
        if c is None:
            return
        await c.expire(key, seconds)

    @property
    def is_available(self) -> bool:
        return self._available and self._client is not None


redis_client = RedisClient()
