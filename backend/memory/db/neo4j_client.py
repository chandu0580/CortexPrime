"""
Async Neo4j driver — lazy-initialized singleton.
Gracefully degrades when Neo4j is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from neo4j import AsyncGraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    logger.warning("neo4j driver not installed — cognitive graph disabled")


class Neo4jClient:
    """Async Neo4j driver with lazy initialization."""

    def __init__(self) -> None:
        self._driver: Any = None
        self._available: bool = _NEO4J_AVAILABLE

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def driver(self) -> Optional[Any]:
        if self._driver is not None:
            return self._driver
        if not self._available:
            return None
        await self._connect()
        return self._driver

    async def _connect(self) -> None:
        uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
        user     = os.getenv("NEO4J_USER",     "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "cortexgraph")
        try:
            drv = AsyncGraphDatabase.driver(
                uri,
                auth=(user, password),
                connection_timeout=5,
                max_connection_lifetime=3600,
            )
            await drv.verify_connectivity()
            self._driver = drv
            logger.info("Neo4j driver connected")
        except Exception as exc:
            logger.warning(f"Neo4j unavailable: {exc}")
            self._available = False

    # ------------------------------------------------------------------
    # Query helper
    # ------------------------------------------------------------------

    async def run(self, query: str, **params) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return list of record dicts."""
        drv = await self.driver()
        if drv is None:
            return []
        try:
            async with drv.session() as session:
                result = await session.run(query, **params)
                return [record.data() async for record in result]
        except Exception as exc:
            logger.warning(f"Neo4j query failed: {exc}")
            return []

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    @property
    def is_available(self) -> bool:
        return self._available and self._driver is not None


neo4j_client = Neo4jClient()
