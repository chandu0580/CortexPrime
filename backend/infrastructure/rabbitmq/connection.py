"""
RabbitMQ Connection Manager
----------------------------
Robust async RabbitMQ connection built on ``aio-pika``.

Features
--------
* ``connect_robust`` — automatic low-level reconnection by aio-pika
* Background reconnect loop with exponential back-off (1 s → 60 s)
* ``new_channel()`` — create a fresh channel for the channel pool
* ``declare_topology()`` moved to ``topology.py`` (called after connect)
* Graceful degradation: every caller checks ``is_available``

Environment variables
---------------------
RABBITMQ_URL          — full amqp:// DSN (overrides all below)
RABBITMQ_HOST         — default: localhost
RABBITMQ_PORT         — default: 5672
RABBITMQ_USER         — default: cortex
RABBITMQ_PASSWORD     — default: cortexmq
RABBITMQ_VHOST        — default: cortex
RABBITMQ_PREFETCH     — channel QoS prefetch count (default: 10)
RABBITMQ_TIMEOUT      — connect timeout seconds (default: 5)
RABBITMQ_RECONNECT_MAX — max back-off seconds (default: 60)
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Optional

log = logging.getLogger(__name__)

try:
    import aio_pika
    _AIO_PIKA_AVAILABLE = True
except ImportError:
    _AIO_PIKA_AVAILABLE = False


# =========================================================
# RABBITMQ CONNECTION MANAGER
# =========================================================

class RabbitMQConnection:
    """
    Singleton async RabbitMQ connection.

    Uses ``connect_robust`` for transparent reconnection at the
    AMQP level.  A background ``_reconnect_loop`` handles the
    higher-level application state (is_available flag, topology
    re-declaration, consumer restart) after a broker restart.
    """

    def __init__(self) -> None:
        self._connection:       Optional[object] = None
        self._channel:          Optional[object] = None   # shared / legacy
        self._available:        bool = False
        self._connecting:       bool = False
        self._reconnect_task:   Optional[asyncio.Task] = None
        self._url:              str  = self._build_url()
        self._prefetch:         int  = int(os.getenv("RABBITMQ_PREFETCH", "10"))
        self._timeout:          int  = int(os.getenv("RABBITMQ_TIMEOUT", "5"))
        self._reconnect_max:    int  = int(os.getenv("RABBITMQ_RECONNECT_MAX", "60"))

    # ---------------------------------------------------------
    # URL BUILDER
    # ---------------------------------------------------------

    def _build_url(self) -> str:
        url = os.getenv("RABBITMQ_URL")
        if url:
            return url
        host     = os.getenv("RABBITMQ_HOST",     "localhost")
        port     = os.getenv("RABBITMQ_PORT",     "5672")
        user     = os.getenv("RABBITMQ_USER",     "cortex")
        password = os.getenv("RABBITMQ_PASSWORD", "")
        vhost    = os.getenv("RABBITMQ_VHOST",    "cortex")
        return f"amqp://{user}:{password}@{host}:{port}/{vhost}"

    # ---------------------------------------------------------
    # CONNECT
    # ---------------------------------------------------------

    async def connect(self) -> bool:
        if not _AIO_PIKA_AVAILABLE:
            log.warning("aio-pika not installed — RabbitMQ disabled")
            return False

        if self._available:
            return True

        if self._connecting:
            return False

        self._connecting = True
        try:
            self._connection = await aio_pika.connect_robust(
                self._url,
                timeout=self._timeout,
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self._prefetch)
            self._available = True

            # Register connection-lost callback for background reconnect
            self._register_callbacks()

            log.info("✅ RabbitMQ connected: %s", self._url.split("@")[-1])
            return True

        except Exception as exc:
            log.warning("⚠️  RabbitMQ unavailable: %s", exc)
            self._available = False
            self._start_reconnect_loop()
            return False

        finally:
            self._connecting = False

    def _register_callbacks(self) -> None:
        """Support both old and new aio-pika robust callback APIs."""
        if self._connection is None:
            return

        reconnect_callbacks = getattr(self._connection, "reconnect_callbacks", None)
        if reconnect_callbacks is not None and hasattr(reconnect_callbacks, "add"):
            reconnect_callbacks.add(self._on_reconnect)
        elif hasattr(self._connection, "add_reconnect_callback"):
            self._connection.add_reconnect_callback(self._on_reconnect)

        close_callbacks = getattr(self._connection, "close_callbacks", None)
        if close_callbacks is not None and hasattr(close_callbacks, "add"):
            close_callbacks.add(self._on_close)
        elif hasattr(self._connection, "add_close_callback"):
            self._connection.add_close_callback(self._on_close)

    # ---------------------------------------------------------
    # RECONNECT CALLBACKS
    # ---------------------------------------------------------

    def _on_reconnect(self, *_) -> None:
        """Called by aio-pika when the robust connection re-establishes."""
        log.info("🔄 RabbitMQ reconnected (robust)")
        asyncio.get_event_loop().create_task(self._post_reconnect())

    def _on_close(self, *_) -> None:
        """Called when the connection closes unexpectedly."""
        log.warning("⚠️  RabbitMQ connection closed")
        self._available = False
        self._start_reconnect_loop()

    async def _post_reconnect(self) -> None:
        """Re-declare topology and restart consumers after reconnect."""
        try:
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self._prefetch)
            self._available = True

            from backend.infrastructure.rabbitmq.topology import topology
            await topology.declare(self._channel)

            from backend.infrastructure.rabbitmq.consumer import rabbitmq_consumer
            await rabbitmq_consumer.restart()

        except Exception as exc:
            log.warning("RabbitMQ post-reconnect setup failed: %s", exc)

    # ---------------------------------------------------------
    # RECONNECT LOOP  (application-level back-off)
    # ---------------------------------------------------------

    def _start_reconnect_loop(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        try:
            loop = asyncio.get_event_loop()
            self._reconnect_task = loop.create_task(self._reconnect_loop())
        except RuntimeError:
            pass  # no running event loop yet

    async def _reconnect_loop(self) -> None:
        delay = 1.0
        while not self._available:
            await asyncio.sleep(delay + random.uniform(0, delay * 0.3))
            delay = min(delay * 2, self._reconnect_max)
            log.info("RabbitMQ reconnect attempt (next delay %.1fs)…", delay)
            await self.connect()

    # ---------------------------------------------------------
    # ENSURE CONNECTED
    # ---------------------------------------------------------

    async def ensure_connected(self) -> bool:
        if self._available:
            return True
        return await self.connect()

    # ---------------------------------------------------------
    # NEW CHANNEL  (for channel pool)
    # ---------------------------------------------------------

    async def new_channel(self):
        """Create and return a fresh aio-pika channel."""
        if not self._available or self._connection is None:
            return None
        ch = await self._connection.channel()
        await ch.set_qos(prefetch_count=self._prefetch)
        return ch

    # ---------------------------------------------------------
    # PROPERTIES
    # ---------------------------------------------------------

    @property
    def channel(self):
        """Shared legacy channel — prefer channel_pool for publishers."""
        return self._channel

    @property
    def is_available(self) -> bool:
        return self._available

    # ---------------------------------------------------------
    # DECLARE TOPOLOGY  (delegates to topology module)
    # ---------------------------------------------------------

    async def declare_topology(self) -> None:
        """Declare all exchanges, queues, and bindings."""
        if not await self.ensure_connected():
            return
        try:
            from backend.infrastructure.rabbitmq.topology import topology
            await topology.declare(self._channel)
        except Exception as exc:
            log.warning("RabbitMQ topology declaration failed: %s", exc)

    # ---------------------------------------------------------
    # CLOSE
    # ---------------------------------------------------------

    async def close(self) -> None:
        self._available = False
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        try:
            if self._connection:
                await self._connection.close()
        except Exception:
            pass
        log.info("RabbitMQ connection closed")


# =========================================================
# SINGLETON
# =========================================================

rabbitmq_connection = RabbitMQConnection()
