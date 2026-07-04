"""
FastAPI dependency: yields a transactional AsyncSession per request.

Usage
-----
    from backend.database.session import get_session
    from sqlalchemy.ext.asyncio   import AsyncSession

    @router.get("/example")
    async def my_endpoint(db: AsyncSession = Depends(get_session)):
        ...

The session is automatically committed on success and rolled back on any
unhandled exception, then closed in the finally block.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session; commit on success, rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
