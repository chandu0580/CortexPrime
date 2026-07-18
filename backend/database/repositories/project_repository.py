from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.project import ProjectModel
from backend.database.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[ProjectModel]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ProjectModel, session)

    async def search(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[uuid.UUID] = None,
        department_id: Optional[uuid.UUID] = None,
        is_active: Optional[bool] = None,
        owner: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> List[ProjectModel]:
        stmt = select(ProjectModel)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    ProjectModel.name.ilike(like),
                    ProjectModel.key.ilike(like),
                    ProjectModel.description.ilike(like),
                )
            )

        if status is not None:
            stmt = stmt.where(ProjectModel.status == status)

        if organization_id is not None:
            stmt = stmt.where(ProjectModel.organization_id == organization_id)

        if department_id is not None:
            stmt = stmt.where(ProjectModel.department_id == department_id)

        if is_active is not None:
            stmt = stmt.where(ProjectModel.is_active == is_active)

        if owner is not None:
            stmt = stmt.where(ProjectModel.owner == owner)

        sort_col = getattr(ProjectModel, sort_by, ProjectModel.created_at)
        order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[uuid.UUID] = None,
        department_id: Optional[uuid.UUID] = None,
        is_active: Optional[bool] = None,
        owner: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(ProjectModel)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    ProjectModel.name.ilike(like),
                    ProjectModel.key.ilike(like),
                    ProjectModel.description.ilike(like),
                )
            )

        if status is not None:
            stmt = stmt.where(ProjectModel.status == status)

        if organization_id is not None:
            stmt = stmt.where(ProjectModel.organization_id == organization_id)

        if department_id is not None:
            stmt = stmt.where(ProjectModel.department_id == department_id)

        if is_active is not None:
            stmt = stmt.where(ProjectModel.is_active == is_active)

        if owner is not None:
            stmt = stmt.where(ProjectModel.owner == owner)

        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_key(self, key: str) -> Optional[ProjectModel]:
        stmt = select(ProjectModel).where(ProjectModel.key == key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name_in_org(self, name: str, organization_id: uuid.UUID) -> Optional[ProjectModel]:
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.name == name)
            .where(ProjectModel.organization_id == organization_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_organization(
        self, organization_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[ProjectModel]:
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.organization_id == organization_id)
            .order_by(ProjectModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_organization(self, organization_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ProjectModel)
            .where(ProjectModel.organization_id == organization_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
