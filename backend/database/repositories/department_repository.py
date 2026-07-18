from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.department import DepartmentModel
from backend.database.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[DepartmentModel]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DepartmentModel, session)

    async def search(
        self,
        query: Optional[str] = None,
        is_active: Optional[bool] = None,
        organization_id: Optional[uuid.UUID] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> List[DepartmentModel]:
        stmt = select(DepartmentModel)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    DepartmentModel.name.ilike(like),
                    DepartmentModel.description.ilike(like),
                )
            )

        if is_active is not None:
            stmt = stmt.where(DepartmentModel.is_active == is_active)

        if organization_id is not None:
            stmt = stmt.where(DepartmentModel.organization_id == organization_id)

        sort_col = getattr(DepartmentModel, sort_by, DepartmentModel.created_at)
        order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        query: Optional[str] = None,
        is_active: Optional[bool] = None,
        organization_id: Optional[uuid.UUID] = None,
    ) -> int:
        stmt = select(func.count()).select_from(DepartmentModel)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    DepartmentModel.name.ilike(like),
                    DepartmentModel.description.ilike(like),
                )
            )

        if is_active is not None:
            stmt = stmt.where(DepartmentModel.is_active == is_active)

        if organization_id is not None:
            stmt = stmt.where(DepartmentModel.organization_id == organization_id)

        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_organization(
        self, organization_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[DepartmentModel]:
        stmt = (
            select(DepartmentModel)
            .where(DepartmentModel.organization_id == organization_id)
            .order_by(DepartmentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_organization(self, organization_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(DepartmentModel)
            .where(DepartmentModel.organization_id == organization_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
