from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.audit_log import AuditLog
from backend.database.repositories.base import BaseRepository


class EnterpriseAuditRepository(BaseRepository[AuditLog]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AuditLog, session)

    async def search(
        self,
        category: Optional[str] = None,
        actor: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> List[AuditLog]:
        stmt = select(AuditLog)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    AuditLog.action.ilike(like),
                    AuditLog.reason.ilike(like),
                    AuditLog.agent.ilike(like),
                    AuditLog.user_id.ilike(like),
                    AuditLog.execution_id.ilike(like),
                )
            )

        if category is not None:
            stmt = stmt.where(AuditLog.agent == category)

        if actor is not None:
            stmt = stmt.where(AuditLog.user_id == actor)

        if status is not None:
            stmt = stmt.where(AuditLog.outcome == status)

        if severity is not None:
            stmt = stmt.where(AuditLog.risk_level == severity)

        if resource_type is not None:
            stmt = stmt.where(AuditLog.execution_id.ilike(f"{resource_type}%"))

        if resource_id is not None:
            stmt = stmt.where(AuditLog.execution_id == resource_id)

        if start_date is not None:
            stmt = stmt.where(AuditLog.created_at >= start_date)

        if end_date is not None:
            stmt = stmt.where(AuditLog.created_at <= end_date)

        sort_col = getattr(AuditLog, sort_by, AuditLog.created_at)
        order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        category: Optional[str] = None,
        actor: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(AuditLog)

        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    AuditLog.action.ilike(like),
                    AuditLog.reason.ilike(like),
                    AuditLog.agent.ilike(like),
                    AuditLog.user_id.ilike(like),
                    AuditLog.execution_id.ilike(like),
                )
            )

        if category is not None:
            stmt = stmt.where(AuditLog.agent == category)

        if actor is not None:
            stmt = stmt.where(AuditLog.user_id == actor)

        if status is not None:
            stmt = stmt.where(AuditLog.outcome == status)

        if severity is not None:
            stmt = stmt.where(AuditLog.risk_level == severity)

        if resource_type is not None:
            stmt = stmt.where(AuditLog.execution_id.ilike(f"{resource_type}%"))

        if resource_id is not None:
            stmt = stmt.where(AuditLog.execution_id == resource_id)

        if start_date is not None:
            stmt = stmt.where(AuditLog.created_at >= start_date)

        if end_date is not None:
            stmt = stmt.where(AuditLog.created_at <= end_date)

        result = await self._session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def to_enterprise_dict(record: AuditLog) -> Dict[str, Any]:
        d = record.to_dict()
        d["category"] = d.pop("agent", None)
        d["actor"] = d.pop("user_id", None)
        d["status"] = d.pop("outcome", None)
        d["severity"] = d.pop("risk_level", None)
        d["resource_type"] = None
        d["resource_id"] = d.get("execution_id")
        d["correlation_id"] = d.pop("session_id", None)
        d["actor_type"] = "system" if d.get("actor") == "system" else "user"
        d["ip_address"] = None
        d["user_agent"] = None
        return d
