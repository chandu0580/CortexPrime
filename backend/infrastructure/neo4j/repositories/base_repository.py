"""
Base Repository
===============
Generic async Cypher executor base class.

Every repository opens its own session per operation — no shared
session state, no connection leaks.  All methods return empty
defaults ([], {}, None) when Neo4j is unavailable.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.connection import neo4j_connection

log = logging.getLogger(__name__)


class BaseRepository:
    """
    Thin async Cypher execution helper.

    Subclasses call ``self._run(query, **params)`` to execute a
    statement that returns rows, or ``self._execute(query, **params)``
    for write-only statements where the return value is not needed.
    """

    # ------------------------------------------------------------------
    # Connection guard
    # ------------------------------------------------------------------

    async def _connected(self) -> bool:
        """Return True if Neo4j is reachable, False otherwise."""
        return await neo4j_connection.ensure_connected()

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def _run(
        self,
        query: str,
        **params: Any,
    ) -> List[Dict[str, Any]]:
        """
        Run a Cypher query and return all records as a list of dicts.
        Returns [] when Neo4j is unavailable.
        """
        if not await self._connected():
            return []
        try:
            async with neo4j_connection.driver.session() as session:
                result = await session.run(query, **params)
                return [record.data() async for record in result]
        except Exception as exc:
            log.warning("%s._run failed: %s", self.__class__.__name__, exc)
            return []

    async def _run_single(
        self,
        query: str,
        **params: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Run a Cypher query and return the first record, or None.
        """
        rows = await self._run(query, **params)
        return rows[0] if rows else None

    async def _run_scalar(
        self,
        query: str,
        key: str,
        **params: Any,
    ) -> Any:
        """
        Run a Cypher query and return a single scalar value by *key*.
        Returns None when unavailable or no rows.
        """
        row = await self._run_single(query, **params)
        return row.get(key) if row else None

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    async def _execute(
        self,
        query: str,
        **params: Any,
    ) -> None:
        """
        Execute a write Cypher statement; discard the result.
        Logs a warning on failure; does not raise.
        """
        if not await self._connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(query, **params)
        except Exception as exc:
            log.warning("%s._execute failed: %s", self.__class__.__name__, exc)

    async def _execute_in_tx(
        self,
        *queries: tuple,  # each element: (cypher_str, params_dict)
    ) -> bool:
        """
        Execute multiple write statements in a single write transaction.
        Rolls back atomically on any failure.
        Returns True on success, False on failure.
        """
        if not await self._connected():
            return False
        try:
            async with neo4j_connection.driver.session() as session:
                async with await session.begin_transaction() as tx:
                    for cypher, params in queries:
                        await tx.run(cypher, **params)
                    await tx.commit()
            return True
        except Exception as exc:
            log.warning(
                "%s._execute_in_tx failed: %s", self.__class__.__name__, exc
            )
            return False
