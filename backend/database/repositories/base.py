"""
Generic async repository base class.

All domain repositories extend BaseRepository[T] and inherit:
  - get(id)          : fetch by primary key
  - create(obj)      : insert and return
  - update(obj)      : merge and return
  - delete(id)       : hard-delete by pk
  - count()          : total row count
  - list(limit, offset): paginated fetch
"""
from __future__ import annotations

import uuid
from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Type-safe async repository with basic CRUD operations.

    Sub-classes pass their model class via the constructor:

        class EpisodicRepository(BaseRepository[EpisodicMemoryRecord]):
            def __init__(self, session):
                super().__init__(EpisodicMemoryRecord, session)
    """

    def __init__(self, model: Type[T], session: AsyncSession) -> None:
        self._model   = model
        self._session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, pk: uuid.UUID) -> Optional[T]:
        return await self._session.get(self._model, pk)

    async def list(self, limit: int = 50, offset: int = 0) -> List[T]:
        result = await self._session.execute(
            select(self._model)
            .order_by(self._model.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(self._model)
        )
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, obj: T) -> T:
        self._session.add(obj)
        await self._session.flush()   # get server-generated defaults (id, timestamps)
        await self._session.refresh(obj)
        return obj

    async def update(self, obj: T) -> T:
        merged = await self._session.merge(obj)
        await self._session.flush()
        await self._session.refresh(merged)
        return merged

    async def delete(self, pk: uuid.UUID) -> bool:
        obj = await self.get(pk)
        if obj is None:
            return False
        await self._session.delete(obj)
        await self._session.flush()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _execute(self, stmt: Any):
        return await self._session.execute(stmt)
