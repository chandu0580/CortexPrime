from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.connector_activity import ConnectorActivityModel
from backend.database.repositories.base import BaseRepository


class ConnectorActivityRepository(BaseRepository[ConnectorActivityModel]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ConnectorActivityModel, session)

    async def search(
        self,
        connector: Optional[str] = None,
        connector_type: Optional[str] = None,
        operation: Optional[str] = None,
        status: Optional[str] = None,
        initiated_by: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConnectorActivityModel]:
        stmt = select(ConnectorActivityModel)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    ConnectorActivityModel.connector_name.ilike(like),
                    ConnectorActivityModel.message.ilike(like),
                    ConnectorActivityModel.resource.ilike(like),
                )
            )

        if connector is not None:
            stmt = stmt.where(ConnectorActivityModel.connector_name == connector)

        if connector_type is not None:
            stmt = stmt.where(ConnectorActivityModel.connector_type == connector_type)

        if operation is not None:
            stmt = stmt.where(ConnectorActivityModel.operation == operation)

        if status is not None:
            stmt = stmt.where(ConnectorActivityModel.status == status)

        if initiated_by is not None:
            stmt = stmt.where(ConnectorActivityModel.initiated_by == initiated_by)

        if start_date is not None:
            stmt = stmt.where(ConnectorActivityModel.created_at >= start_date)

        if end_date is not None:
            stmt = stmt.where(ConnectorActivityModel.created_at <= end_date)

        sort_col = getattr(ConnectorActivityModel, sort_by, ConnectorActivityModel.created_at)
        order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        connector: Optional[str] = None,
        connector_type: Optional[str] = None,
        operation: Optional[str] = None,
        status: Optional[str] = None,
        initiated_by: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(ConnectorActivityModel)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    ConnectorActivityModel.connector_name.ilike(like),
                    ConnectorActivityModel.message.ilike(like),
                    ConnectorActivityModel.resource.ilike(like),
                )
            )

        if connector is not None:
            stmt = stmt.where(ConnectorActivityModel.connector_name == connector)

        if connector_type is not None:
            stmt = stmt.where(ConnectorActivityModel.connector_type == connector_type)

        if operation is not None:
            stmt = stmt.where(ConnectorActivityModel.operation == operation)

        if status is not None:
            stmt = stmt.where(ConnectorActivityModel.status == status)

        if initiated_by is not None:
            stmt = stmt.where(ConnectorActivityModel.initiated_by == initiated_by)

        if start_date is not None:
            stmt = stmt.where(ConnectorActivityModel.created_at >= start_date)

        if end_date is not None:
            stmt = stmt.where(ConnectorActivityModel.created_at <= end_date)

        result = await self._session.execute(stmt)
        return result.scalar_one()
