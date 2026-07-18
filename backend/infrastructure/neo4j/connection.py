from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Optional

log = logging.getLogger(__name__)

try:
    from neo4j import AsyncGraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False


# =========================================================
# NEO4J CONNECTION MANAGER
# =========================================================

class Neo4jConnection:
    """
    Async Neo4j connection with graceful degradation and background
    reconnect loop with exponential back-off.
    """

    def __init__(self):
        self._driver:        Optional[object] = None
        self._available:     bool = False
        self._connecting:    bool = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_max: int = int(os.getenv("NEO4J_RECONNECT_MAX", "60"))

    # ---------------------------------------------------------
    # CONNECT
    # ---------------------------------------------------------

    async def connect(self) -> bool:
        if not _NEO4J_AVAILABLE:
            log.warning("neo4j driver not installed — Neo4j disabled")
            return False

        if self._available:
            return True

        if self._connecting:
            return False

        self._connecting = True
        uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
        user     = os.getenv("NEO4J_USER",     "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")

        try:
            self._driver = AsyncGraphDatabase.driver(
                uri,
                auth=(user, password),
                connection_timeout=5,
                max_connection_pool_size=10,
            )
            # Verify
            async with self._driver.session() as session:
                await session.run("RETURN 1")

            self._available = True
            log.info("✅ Neo4j connected: %s", uri)
            return True

        except Exception as exc:
            log.warning("⚠️  Neo4j unavailable: %s", exc)
            self._available = False
            self._start_reconnect_loop()
            return False

        finally:
            self._connecting = False

    # ---------------------------------------------------------
    # RECONNECT LOOP  (exponential back-off)
    # ---------------------------------------------------------

    def _start_reconnect_loop(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        try:
            loop = asyncio.get_event_loop()
            self._reconnect_task = loop.create_task(self._reconnect_loop())
        except RuntimeError:
            pass

    async def _reconnect_loop(self) -> None:
        delay = 1.0
        while not self._available:
            await asyncio.sleep(delay + random.uniform(0, delay * 0.3))
            delay = min(delay * 2, self._reconnect_max)
            log.info("Neo4j reconnect attempt (next delay %.1fs)…", delay)
            await self.connect()

    # ---------------------------------------------------------
    # ENSURE CONNECTED
    # ---------------------------------------------------------

    async def ensure_connected(self) -> bool:
        if self._available:
            return True
        return await self.connect()

    @property
    def driver(self):
        return self._driver

    @property
    def is_available(self) -> bool:
        return self._available

    async def close(self) -> None:
        self._available = False
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        try:
            if self._driver:
                await self._driver.close()
        except Exception:
            pass


# =========================================================
# SINGLETON
# =========================================================

neo4j_connection = Neo4jConnection()
