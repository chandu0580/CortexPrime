"""
Database health check utility.

Returns a structured dict suitable for inclusion in /health responses.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import text

from backend.database.engine import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def check_database_health() -> Dict[str, Any]:
    """
    Probe PostgreSQL connectivity and return a health dict.

    Returns
    -------
    {
        "status":    "healthy" | "degraded" | "offline",
        "latency_ms": float,
        "pgvector":  bool,
        "detail":    str | None
    }
    """
    import time

    start = time.monotonic()
    try:
        async with AsyncSessionLocal() as session:
            # Basic connectivity
            await session.execute(text("SELECT 1"))

            # Check pgvector extension
            result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
                )
            )
            pgvector_installed = result.scalar_one() > 0

        latency_ms = (time.monotonic() - start) * 1000
        return {
            "status":     "healthy",
            "latency_ms": round(latency_ms, 2),
            "pgvector":   pgvector_installed,
            "detail":     None,
        }

    except Exception as exc:
        latency_ms = (time.monotonic() - start) * 1000
        logger.warning("Database health check failed: %s", exc)
        return {
            "status":     "offline",
            "latency_ms": round(latency_ms, 2),
            "pgvector":   False,
            "detail":     str(exc),
        }
