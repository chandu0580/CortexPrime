"""
CortexPrime Redis connection pool manager.

Provides a single production-grade async connection pool shared by all
Redis services.  Key features:

  - ``redis.asyncio`` connection pool with configurable pool size, keep-alive,
    and health-check interval
  - Exponential back-off reconnect with jitter (max 60 s) and circuit-breaker
    that stops retrying after ``MAX_CONSECUTIVE_FAILURES`` consecutive errors
  - Separate ``pub_client`` for blocking Pub/Sub (Pub/Sub mandates its own
    connection that cannot multiplex other commands)
  - Graceful degradation: all callers check ``redis_connection.is_available``
    and fall back to in-memory mode; the pool never raises to callers

Environment variables (same names used throughout the project)
--------------------------------------------------------------
  REDIS_URL        full URL (overrides individual vars below)
  REDIS_HOST       default: localhost
  REDIS_PORT       default: 6379
  REDIS_PASSWORD   default: (empty)
  REDIS_DB         default: 0
  REDIS_POOL_SIZE  default: 20  (max_connections)
  REDIS_TIMEOUT    default: 5   (socket connect + command timeout, seconds)
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Any, Optional

log = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    log.warning("redis[asyncio] not installed — all Redis services disabled")

# Circuit-breaker threshold
MAX_CONSECUTIVE_FAILURES = 5
_BACKOFF_BASE  = 1.0    # seconds
_BACKOFF_MAX   = 60.0   # seconds
_BACKOFF_JITTER = 0.3   # ± fraction


def _build_url() -> str:
    if url := os.getenv("REDIS_URL"):
        return url
    host = os.getenv("REDIS_HOST",     "localhost")
    port = os.getenv("REDIS_PORT",     "6379")
    pw   = os.getenv("REDIS_PASSWORD", "")
    db   = os.getenv("REDIS_DB",       "0")
    if pw:
        return f"redis://:{pw}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


def _jittered_backoff(attempt: int) -> float:
    """Exponential back-off with ±30 % jitter."""
    delay = min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_MAX)
    jitter = delay * _BACKOFF_JITTER * (random.random() * 2 - 1)
    return max(0.1, delay + jitter)


def _use_ssl() -> bool:
    return os.getenv("REDIS_USE_SSL", "false").lower() in ("true", "1", "yes")


# ===========================================================================
# POOL MANAGER
# ===========================================================================

class RedisConnectionPool:
    """
    Production-grade async Redis connection pool.

    Usage
    -----
    Await ``redis_connection.connect()`` on app startup.  All services then
    call ``redis_connection.client`` (may be None if Redis is offline).

    The pool manager self-heals: ``ensure_connected()`` is called automatically
    before every operation by the service helpers and retries with back-off
    up to the circuit-breaker threshold.
    """

    def __init__(self) -> None:
        self._client:     Optional[Any] = None
        self._pub_client: Optional[Any] = None   # dedicated pub/sub connection
        self._available:  bool          = False
        self._url:        str           = _build_url()
        self._failures:   int           = 0
        self._reconnect_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pool_kwargs(self) -> dict:
        pool_size = int(os.getenv("REDIS_POOL_SIZE", "20"))
        timeout   = int(os.getenv("REDIS_TIMEOUT",   "5"))
        kwargs = dict(
            encoding               = "utf-8",
            decode_responses       = True,
            max_connections        = pool_size,
            socket_connect_timeout = timeout,
            socket_timeout         = timeout,
            socket_keepalive       = True,
            socket_keepalive_options = {},
            health_check_interval  = 30,   # seconds between background pings
            retry_on_timeout       = True,
        )
        # redis-py's plain Connection class (used for a redis:// URL) doesn't
        # accept an `ssl` kwarg at all — only SSLConnection (rediss:// URL)
        # does. Passing ssl=False unconditionally broke every connection
        # attempt with "AbstractConnection.__init__() got an unexpected
        # keyword argument 'ssl'", so only include it when actually wanted.
        if _use_ssl():
            kwargs["ssl"] = True
        return kwargs

    async def _try_connect(self) -> bool:
        if not _REDIS_AVAILABLE:
            return False
        try:
            client = aioredis.from_url(self._url, **self._pool_kwargs())
            await client.ping()

            # Separate connection for pub/sub (blocking reads need own socket)
            pub_client = aioredis.from_url(self._url, **self._pool_kwargs())

            self._client     = client
            self._pub_client = pub_client
            self._available  = True
            self._failures   = 0
            log.info("✅ Redis pool ready (%s)", self._url.split("@")[-1])
            return True
        except Exception as exc:
            self._available = False
            self._failures += 1
            log.warning("⚠️  Redis connect attempt failed (failure #%d): %s", self._failures, exc)
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Attempt initial connection; start background reconnect if it fails."""
        if self._available:
            return True
        connected = await self._try_connect()
        if not connected:
            self._schedule_reconnect()
        return connected

    async def ensure_connected(self) -> bool:
        """
        Called before every Redis operation.  Returns True when the pool is
        live.  Triggers a reconnect attempt if the pool is down, subject to
        the circuit-breaker.
        """
        if self._available:
            return True
        if self._failures >= MAX_CONSECUTIVE_FAILURES:
            return False   # circuit open — don't hammer Redis
        return await self._try_connect()

    def _schedule_reconnect(self) -> None:
        """Launch a background task that retries the connection with back-off."""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._reconnect_task = loop.create_task(self._reconnect_loop())
        except RuntimeError:
            pass  # no running event loop at import time

    async def _reconnect_loop(self) -> None:
        attempt = 0
        while not self._available and self._failures < MAX_CONSECUTIVE_FAILURES:
            delay = _jittered_backoff(attempt)
            log.info("🔄 Redis reconnect in %.1fs (attempt %d)", delay, attempt + 1)
            await asyncio.sleep(delay)
            await self._try_connect()
            attempt += 1
        if self._available:
            log.info("✅ Redis reconnected after %d attempt(s)", attempt)
        else:
            log.error(
                "🚫 Redis circuit breaker open after %d failures — "
                "restart the service or call redis_connection.reset() to retry.",
                self._failures,
            )

    def reset_circuit_breaker(self) -> None:
        """Manually re-arm the circuit breaker and allow reconnect attempts."""
        self._failures = 0
        log.info("Circuit breaker reset — Redis reconnect will resume")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def client(self) -> Optional[Any]:
        """The main Redis client (pooled).  May be None if Redis is offline."""
        return self._client

    @property
    def pub_client(self) -> Optional[Any]:
        """Dedicated client for pub/sub operations."""
        return self._pub_client

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def failure_count(self) -> int:
        return self._failures

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------

    async def close(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        for c in (self._client, self._pub_client):
            if c:
                try:
                    await c.aclose()
                except Exception:
                    pass
        self._client     = None
        self._pub_client = None
        self._available  = False
        log.info("Redis pool closed")

    # ------------------------------------------------------------------
    # Health probe
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Lightweight health check; does NOT reconnect."""
        if not self._available or self._client is None:
            return False
        try:
            return await self._client.ping()
        except Exception:
            self._available = False
            return False


# ===========================================================================
# SINGLETON
# ===========================================================================

redis_connection = RedisConnectionPool()

