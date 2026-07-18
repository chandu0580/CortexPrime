from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.organization import OrganizationModel
from backend.database.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[OrganizationModel]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OrganizationModel, session)

    async def search(
        self,
        query: Optional[str] = None,
        is_active: Optional[bool] = None,
        domain: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> List[OrganizationModel]:
        stmt = select(OrganizationModel)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    OrganizationModel.name.ilike(like),
                    OrganizationModel.description.ilike(like),
                    OrganizationModel.domain.ilike(like),
                )
            )

        if is_active is not None:
            stmt = stmt.where(OrganizationModel.is_active == is_active)

        if domain is not None:
            stmt = stmt.where(OrganizationModel.domain == domain)

        sort_col = getattr(OrganizationModel, sort_by, OrganizationModel.created_at)
        order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        query: Optional[str] = None,
        is_active: Optional[bool] = None,
        domain: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(OrganizationModel)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    OrganizationModel.name.ilike(like),
                    OrganizationModel.description.ilike(like),
                    OrganizationModel.domain.ilike(like),
                )
            )

        if is_active is not None:
            stmt = stmt.where(OrganizationModel.is_active == is_active)

        if domain is not None:
            stmt = stmt.where(OrganizationModel.domain == domain)

        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_domain(self, domain: str) -> Optional[OrganizationModel]:
        stmt = select(OrganizationModel).where(OrganizationModel.domain == domain)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[OrganizationModel]:
        stmt = select(OrganizationModel).where(OrganizationModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
