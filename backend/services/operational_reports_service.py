from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.operational_report import OperationalReport

log = logging.getLogger(__name__)


class OperationalReportsService:
    async def generate_daily_report(self, db: AsyncSession, generated_by: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=1)

        summary = await self._collect_mission_stats(period_start, period_end)
        summary["report_type"] = "daily"
        summary["period"] = {"start": period_start.isoformat(), "end": period_end.isoformat()}

        return await self._save_report(db, "daily", period_start, period_end, summary, generated_by)

    async def generate_weekly_report(self, db: AsyncSession, generated_by: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        period_end = now
        period_start = now - timedelta(days=7)

        summary = await self._collect_mission_stats(period_start, period_end)
        summary["report_type"] = "weekly"
        summary["period"] = {"start": period_start.isoformat(), "end": period_end.isoformat()}

        connector_util = await self._get_connector_utilization()
        workflow_util = await self._get_workflow_utilization()
        approval_stats = await self._get_approval_statistics()
        cost_metrics = await self._get_cost_metrics()

        summary["connector_utilization"] = connector_util
        summary["workflow_utilization"] = workflow_util
        summary["approval_statistics"] = approval_stats
        summary["cost_metrics"] = cost_metrics

        return await self._save_report(db, "weekly", period_start, period_end, summary, generated_by)

    async def generate_monthly_report(self, db: AsyncSession, generated_by: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        period_end = now
        period_start = now - timedelta(days=30)

        summary = await self._collect_mission_stats(period_start, period_end)
        summary["report_type"] = "monthly"
        summary["period"] = {"start": period_start.isoformat(), "end": period_end.isoformat()}

        connector_util = await self._get_connector_utilization()
        workflow_util = await self._get_workflow_utilization()
        approval_stats = await self._get_approval_statistics()
        cost_metrics = await self._get_cost_metrics()

        summary["connector_utilization"] = connector_util
        summary["workflow_utilization"] = workflow_util
        summary["approval_statistics"] = approval_stats
        summary["cost_metrics"] = cost_metrics

        return await self._save_report(db, "monthly", period_start, period_end, summary, generated_by)

    async def generate_report(
        self,
        report_type: str,
        db: AsyncSession,
        generated_by: Optional[str] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if report_type == "daily":
            return await self.generate_daily_report(db, generated_by)
        elif report_type == "weekly":
            return await self.generate_weekly_report(db, generated_by)
        elif report_type == "monthly":
            return await self.generate_monthly_report(db, generated_by)
        else:
            raise ValueError(f"Unknown report type: {report_type}")

    async def list_reports(
        self,
        db: AsyncSession,
        report_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        from sqlalchemy import select

        query = select(OperationalReport).order_by(OperationalReport.created_at.desc())
        if report_type:
            query = query.where(OperationalReport.report_type == report_type)

        result = await db.execute(query.limit(limit))
        return [r.to_dict() for r in result.scalars().all()]

    async def get_report(self, db: AsyncSession, report_id: str) -> Optional[Dict[str, Any]]:
        from uuid import UUID

        from sqlalchemy import select

        try:
            result = await db.execute(select(OperationalReport).where(OperationalReport.id == UUID(report_id)))
            report = result.scalar_one_or_none()
            return report.to_dict() if report else None
        except Exception:
            return None

    async def _save_report(
        self,
        db: AsyncSession,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
        summary: Dict[str, Any],
        generated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        record = OperationalReport(
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            status="generated",
            summary=summary,
            generated_by=generated_by or "system",
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record.to_dict()

    async def _collect_mission_stats(self, start: datetime, end: datetime) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "mission_counts": {"total": 0, "completed": 0, "failed": 0, "in_progress": 0},
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "average_latency_ms": 0,
            "top_failures": [],
        }

        try:
            from backend.runtime.runtime_metrics import runtime_metrics
            metrics = runtime_metrics.export_metrics() if hasattr(runtime_metrics, "export_metrics") else {}
            total = metrics.get("total_executions", 0)
            completed = metrics.get("completed_executions", 0)
            failed = metrics.get("failed_executions", 0)

            stats["mission_counts"] = {
                "total": total,
                "completed": completed,
                "failed": failed,
                "in_progress": total - completed - failed,
            }
            stats["success_rate"] = round((completed / total * 100) if total > 0 else 0, 1)
            stats["failure_rate"] = round((failed / total * 100) if total > 0 else 0, 1)
        except Exception as exc:
            log.warning("Failed to collect mission stats: %s", exc)

        return stats

    async def _get_connector_utilization(self) -> Dict[str, Any]:
        try:
            from backend.connectors.registry import connector_registry
            count = connector_registry.count() if hasattr(connector_registry, "count") else 0
            return {"connector_count": count, "utilization_pct": 0}
        except Exception as exc:
            return {"error": str(exc)[:200]}

    async def _get_workflow_utilization(self) -> Dict[str, Any]:
        try:
            from backend.safety.approval_queue import approval_queue
            qsize = len(getattr(approval_queue, "_requests", {}))
            return {"pending_approvals": qsize}
        except Exception as exc:
            return {"error": str(exc)[:200]}

    async def _get_approval_statistics(self) -> Dict[str, Any]:
        try:
            from backend.safety.approval_queue import approval_queue
            qsize = len(getattr(approval_queue, "_requests", {}))
            return {"pending": qsize, "approved": 0, "rejected": 0, "timed_out": 0}
        except Exception as exc:
            return {"error": str(exc)[:200]}

    async def _get_cost_metrics(self) -> Dict[str, Any]:
        try:
            return {"total_cost_usd": 0, "daily_cost_usd": 0}
        except Exception as exc:
            return {"error": str(exc)[:200]}


operational_reports_service = OperationalReportsService()
