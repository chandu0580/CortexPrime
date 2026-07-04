"""
RabbitMQ Channel Pool
---------------------
Provides a fixed-size pool of aio-pika channels so that concurrent
publishers never block each other waiting for a single shared channel.

Usage
-----
    async with channel_pool.acquire() as ch:
        await exchange.publish(message, routing_key="...")

The pool is backed by the shared ``rabbitmq_connection`` singleton and
creates new channels lazily.  When a channel is checked back in it is
validated; a closed channel is discarded and replaced on next ``acquire()``.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional

log = logging.getLogger(__name__)

try:
    import aio_pika
    _AIO_PIKA_AVAILABLE = True
except ImportError:
    _AIO_PIKA_AVAILABLE = False


# =========================================================
# CHANNEL POOL
# =========================================================

class ChannelPool:
    """
    Async context-manager-based channel pool.

    Pool size is controlled by the ``RABBITMQ_CHANNEL_POOL_SIZE``
    environment variable (default 10).
    """

    def __init__(self, size: int = 0) -> None:
        self._size:      int             = size or int(os.getenv("RABBITMQ_CHANNEL_POOL_SIZE", "10"))
        self._pool:      asyncio.Queue   = asyncio.Queue(maxsize=self._size)
        self._lock:      asyncio.Lock    = asyncio.Lock()
        self._count:     int             = 0    # channels created so far

    # ---------------------------------------------------------
    # ACQUIRE  (async context manager)
    # ---------------------------------------------------------

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator:
        """
        Yield a live aio-pika channel.  When the context exits, the
        channel is returned to the pool (or discarded if closed).

        Falls back to a throw-away channel if the pool cannot supply
        one within 5 s — this keeps publishers non-blocking under
        burst load.
        """
        channel = await self._get_channel()
        try:
            yield channel
        finally:
            await self._return_channel(channel)

    # ---------------------------------------------------------
    # INTERNAL
    # ---------------------------------------------------------

    async def _get_channel(self):
        """Return a healthy channel: pool → create → fallback."""
        # 1. Try pool first (non-blocking)
        try:
            channel = self._pool.get_nowait()
            if await self._is_healthy(channel):
                return channel
            # else: channel closed — fall through to create
        except asyncio.QueueEmpty:
            pass

        # 2. Create a new channel if below pool size
        async with self._lock:
            if self._count < self._size:
                channel = await self._create_channel()
                if channel:
                    self._count += 1
                    return channel

        # 3. Wait for a pooled channel (timeout 5 s) then fallback
        try:
            channel = await asyncio.wait_for(self._pool.get(), timeout=5.0)
            if await self._is_healthy(channel):
                return channel
        except asyncio.TimeoutError:
            pass

        # 4. Create a throw-away channel (not counted toward pool size)
        return await self._create_channel()

    async def _return_channel(self, channel) -> None:
        if channel is None:
            return
        if not await self._is_healthy(channel):
            async with self._lock:
                self._count = max(0, self._count - 1)
            return
        try:
            self._pool.put_nowait(channel)
        except asyncio.QueueFull:
            # Pool full — just close the extra channel
            try:
                await channel.close()
            except Exception:
                pass
            async with self._lock:
                self._count = max(0, self._count - 1)

    async def _create_channel(self):
        if not _AIO_PIKA_AVAILABLE:
            return None
        try:
            from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
            if not rabbitmq_connection.is_available:
                return None
            ch = await rabbitmq_connection.new_channel()
            return ch
        except Exception as exc:
            log.warning("ChannelPool: failed to create channel: %s", exc)
            return None

    @staticmethod
    async def _is_healthy(channel) -> bool:
        if channel is None:
            return False
        try:
            return not channel.is_closed
        except Exception:
            return False

    # ---------------------------------------------------------
    # CLOSE ALL
    # ---------------------------------------------------------

    async def close(self) -> None:
        while not self._pool.empty():
            try:
                ch = self._pool.get_nowait()
                try:
                    await ch.close()
                except Exception:
                    pass
            except asyncio.QueueEmpty:
                break
        self._count = 0
        log.info("ChannelPool: closed")


# =========================================================
# SINGLETON
# =========================================================

channel_pool = ChannelPool()
