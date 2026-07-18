"""
AnalyticsRepository — async CRUD + aggregation for runtime_analytics.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.runtime_analytics import RuntimeAnalyticsRecord
from backend.database.repositories.base import BaseRepository


class AnalyticsRepository(BaseRepository[RuntimeAnalyticsRecord]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RuntimeAnalyticsRecord, session)

    # ------------------------------------------------------------------
    # Domain reads
    # ------------------------------------------------------------------

    async def get_by_mission(
        self,
        mission_id: uuid.UUID,
        limit: int = 200,
    ) -> List[RuntimeAnalyticsRecord]:
        result = await self._session.execute(
            select(RuntimeAnalyticsRecord)
            .where(RuntimeAnalyticsRecord.mission_id == mission_id)
            .order_by(RuntimeAnalyticsRecord.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_agent(
        self,
        agent: str,
        limit: int = 100,
    ) -> List[RuntimeAnalyticsRecord]:
        result = await self._session.execute(
            select(RuntimeAnalyticsRecord)
            .where(RuntimeAnalyticsRecord.agent == agent)
            .order_by(RuntimeAnalyticsRecord.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_errors(
        self,
        limit: int = 50,
    ) -> List[RuntimeAnalyticsRecord]:
        result = await self._session.execute(
            select(RuntimeAnalyticsRecord)
            .where(RuntimeAnalyticsRecord.success == False)  # noqa: E712
            .order_by(RuntimeAnalyticsRecord.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Aggregations
    # ------------------------------------------------------------------

    async def agent_summary(self, agent: str) -> Dict[str, Any]:
        """Return aggregated stats for one agent."""
        result = await self._session.execute(
            select(
                func.count().label("total_calls"),
                func.sum(
                    func.cast(RuntimeAnalyticsRecord.success, _Integer := __import__("sqlalchemy", fromlist=["Integer"]).Integer)
                ).label("successful_calls"),
                func.avg(RuntimeAnalyticsRecord.latency_ms).label("avg_latency_ms"),
                func.sum(RuntimeAnalyticsRecord.prompt_tokens).label("total_prompt_tokens"),
                func.sum(RuntimeAnalyticsRecord.output_tokens).label("total_output_tokens"),
                func.sum(RuntimeAnalyticsRecord.cost_usd).label("total_cost_usd"),
            )
            .where(RuntimeAnalyticsRecord.agent == agent)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return {}
        return dict(row)

    async def hourly_call_volume(
        self,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Return call counts bucketed by hour for the last *hours* hours."""
        stmt = text("""
            SELECT
                date_trunc('hour', created_at) AS hour,
                agent,
                COUNT(*) AS call_count,
                AVG(latency_ms) AS avg_latency_ms,
                SUM(CASE WHEN success THEN 0 ELSE 1 END) AS error_count
            FROM runtime_analytics
            WHERE created_at >= NOW() - INTERVAL '1 hour' * :hours
            GROUP BY 1, 2
            ORDER BY 1 ASC, 2 ASC
        """)
        rows = (await self._session.execute(stmt, {"hours": hours})).mappings().all()
        return [dict(r) for r in rows]

    async def model_usage_stats(self) -> List[Dict[str, Any]]:
        """Aggregate token consumption and cost grouped by model."""
        stmt = text("""
            SELECT
                model,
                COUNT(*) AS call_count,
                SUM(prompt_tokens)  AS total_prompt_tokens,
                SUM(output_tokens)  AS total_output_tokens,
                SUM(cost_usd)       AS total_cost_usd,
                AVG(latency_ms)     AS avg_latency_ms
            FROM runtime_analytics
            WHERE model IS NOT NULL
            GROUP BY model
            ORDER BY call_count DESC
        """)
        rows = (await self._session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]
