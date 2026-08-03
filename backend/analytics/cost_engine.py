"""
backend/analytics/cost_engine.py

Mission Cost Engine — tracks LLM, voice, and search costs per call and
provides aggregated summaries by mission / user / day / month.

Usage
-----
    from backend.analytics.cost_engine import cost_engine

    await cost_engine.record(
        provider="openai",
        service="chat_completion",
        model="gpt-4o",
        prompt_tokens=800,
        completion_tokens=200,
        cost_usd=0.0042,
        mission_id=str(mission_id),
        user_id=user_id,
    )

    summary = await cost_engine.daily_summary()
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select

log = logging.getLogger(__name__)

# ── Provider cost tables (USD per 1 000 tokens, updated June 2026) ───────────
# Format: { provider: { model: (prompt_per_1k, completion_per_1k) } }
_COST_TABLE: Dict[str, Dict[str, tuple]] = {
    "openai": {
        "gpt-4o":               (0.005,   0.015),
        "gpt-4o-mini":          (0.00015, 0.0006),
        "gpt-4-turbo":          (0.01,    0.03),
        "gpt-4":                (0.03,    0.06),
        "gpt-3.5-turbo":        (0.0005,  0.0015),
        "text-embedding-3-small":(0.00002, 0.0),
        "text-embedding-3-large":(0.00013, 0.0),
        "tts-1":                (0.015,   0.0),   # per 1K chars
        "tts-1-hd":             (0.03,    0.0),
        "whisper-1":            (0.006,   0.0),   # per minute
    },
    "anthropic": {
        "claude-3-5-sonnet":    (0.003,   0.015),
        "claude-3-5-haiku":     (0.0008,  0.004),
        "claude-3-opus":        (0.015,   0.075),
        "claude-3-haiku":       (0.00025, 0.00125),
    },
    "azure_openai": {
        "gpt-4o":               (0.005,   0.015),
        "gpt-4o-mini":          (0.000165,0.00066),
        "gpt-4":                (0.03,    0.06),
    },
    "google": {
        "gemini-1.5-pro":       (0.00125, 0.005),
        "gemini-1.5-flash":     (0.000075,0.0003),
        "gemini-2.0-flash":     (0.0001,  0.0004),
    },
    "search": {
        "tavily":               (0.0,     0.0),   # free tier, override if paid
    },
    "voice": {
        "edge-tts":             (0.0,     0.0),   # free
        "whisper":              (0.006,   0.0),   # per minute
    },
}


# llm_router.py's internal provider keys ("claude", "azure", "gemini")
# don't match _COST_TABLE's keys ("anthropic", "azure_openai", "google") —
# only "openai"/"ollama"/"groq" happen to line up. Without this alias,
# every real Claude/Azure/Gemini call silently estimates to $0.00.
_PROVIDER_ALIASES: Dict[str, str] = {
    "claude": "anthropic",
    "azure": "azure_openai",
    "gemini": "google",
}


def estimate_cost(
    provider: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    units: float = 0.0,
) -> float:
    """
    Estimate cost in USD using the built-in cost table.
    Returns 0.0 if provider/model not in table (no error).
    """
    provider = _PROVIDER_ALIASES.get(provider.lower(), provider.lower())
    p = _COST_TABLE.get(provider, {})
    # Try exact match then prefix match
    rates = p.get(model) or next(
        (v for k, v in p.items() if model.startswith(k) or k.startswith(model.split("-")[0])),
        None
    )
    if rates is None:
        return 0.0
    prompt_rate, completion_rate = rates
    total = (prompt_tokens / 1000) * prompt_rate + (completion_tokens / 1000) * completion_rate
    if units and completion_tokens == 0 and prompt_tokens == 0:
        total = (units / 1000) * prompt_rate
    return round(total, 8)


class CostEngine:
    """Async cost tracking engine backed by PostgreSQL."""

    async def record(
        self,
        provider: str,
        service: str,
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        units: float = 0.0,
        cost_usd: Optional[float] = None,
        mission_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        extra: Optional[Dict] = None,
    ) -> None:
        """
        Record one billable API call.
        If cost_usd is None, it is estimated from the built-in cost table.
        """
        try:
            from datetime import date as _date

            from backend.database.engine import AsyncSessionLocal as async_session
            from backend.database.models.cost_tracking import CostRecord

            if cost_usd is None:
                cost_usd = estimate_cost(
                    provider, model, prompt_tokens, completion_tokens, units
                )

            async with async_session() as session:
                record = CostRecord(
                    provider=provider,
                    service=service,
                    model=model or None,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    units=units,
                    cost_usd=cost_usd,
                    mission_id=mission_id,
                    user_id=user_id,
                    session_id=session_id,
                    report_date=_date.today(),
                    extra=extra,
                )
                session.add(record)
                await session.commit()

            # Mirror to Prometheus
            try:
                from backend.observability.prometheus_metrics import metrics
                metrics.llm_cost_usd.labels(
                    provider=provider, model=model or service
                ).inc(cost_usd)
            except Exception:
                pass

        except Exception as exc:
            log.warning("cost_engine.record failed: %s", exc)

    # ── Aggregated summaries ──────────────────────────────────────────────────

    async def daily_summary(self, days: int = 30) -> List[Dict]:
        """Returns per-day cost totals for the last N days."""
        try:
            from backend.database.engine import AsyncSessionLocal as async_session
            from backend.database.models.cost_tracking import CostRecord

            since = date.today() - timedelta(days=days)
            async with async_session() as session:
                rows = await session.execute(
                    select(
                        CostRecord.report_date,
                        func.sum(CostRecord.cost_usd).label("total_cost"),
                        func.count().label("calls"),
                        func.sum(CostRecord.total_tokens).label("total_tokens"),
                    )
                    .where(CostRecord.report_date >= since)
                    .group_by(CostRecord.report_date)
                    .order_by(CostRecord.report_date)
                )
                return [
                    {
                        "date":         str(r.report_date),
                        "total_cost":   round(float(r.total_cost or 0), 4),
                        "calls":        int(r.calls),
                        "total_tokens": int(r.total_tokens or 0),
                    }
                    for r in rows
                ]
        except Exception as exc:
            log.warning("daily_summary failed: %s", exc)
            return []

    async def provider_breakdown(self, days: int = 30) -> List[Dict]:
        """Returns cost broken down by provider for the last N days."""
        try:
            from backend.database.engine import AsyncSessionLocal as async_session
            from backend.database.models.cost_tracking import CostRecord

            since = date.today() - timedelta(days=days)
            async with async_session() as session:
                rows = await session.execute(
                    select(
                        CostRecord.provider,
                        func.sum(CostRecord.cost_usd).label("total_cost"),
                        func.count().label("calls"),
                    )
                    .where(CostRecord.report_date >= since)
                    .group_by(CostRecord.provider)
                    .order_by(func.sum(CostRecord.cost_usd).desc())
                )
                return [
                    {
                        "provider":   r.provider,
                        "total_cost": round(float(r.total_cost or 0), 4),
                        "calls":      int(r.calls),
                    }
                    for r in rows
                ]
        except Exception as exc:
            log.warning("provider_breakdown failed: %s", exc)
            return []

    async def mission_cost(self, mission_id: str) -> Dict:
        """Returns total cost and breakdown for a specific mission."""
        try:
            from backend.database.engine import AsyncSessionLocal as async_session
            from backend.database.models.cost_tracking import CostRecord

            async with async_session() as session:
                totals = await session.execute(
                    select(
                        func.sum(CostRecord.cost_usd).label("total_cost"),
                        func.sum(CostRecord.total_tokens).label("total_tokens"),
                        func.count().label("calls"),
                    ).where(CostRecord.mission_id == mission_id)
                )
                row = totals.one()

                by_provider = await session.execute(
                    select(
                        CostRecord.provider,
                        CostRecord.model,
                        func.sum(CostRecord.cost_usd).label("cost"),
                        func.count().label("calls"),
                    )
                    .where(CostRecord.mission_id == mission_id)
                    .group_by(CostRecord.provider, CostRecord.model)
                )

            return {
                "mission_id":   mission_id,
                "total_cost":   round(float(row.total_cost or 0), 6),
                "total_tokens": int(row.total_tokens or 0),
                "calls":        int(row.calls),
                "breakdown":    [
                    {
                        "provider": r.provider,
                        "model":    r.model,
                        "cost":     round(float(r.cost or 0), 6),
                        "calls":    int(r.calls),
                    }
                    for r in by_provider
                ],
            }
        except Exception as exc:
            log.warning("mission_cost failed: %s", exc)
            return {"mission_id": mission_id, "total_cost": 0.0, "error": str(exc)}

    async def user_cost(self, user_id: str, days: int = 30) -> Dict:
        """Returns cost for a specific user over the last N days."""
        try:
            from backend.database.engine import AsyncSessionLocal as async_session
            from backend.database.models.cost_tracking import CostRecord

            since = date.today() - timedelta(days=days)
            async with async_session() as session:
                rows = await session.execute(
                    select(
                        func.sum(CostRecord.cost_usd).label("total_cost"),
                        func.sum(CostRecord.total_tokens).label("total_tokens"),
                        func.count().label("calls"),
                    ).where(
                        CostRecord.user_id == user_id,
                        CostRecord.report_date >= since,
                    )
                )
                row = rows.one()
            return {
                "user_id":      user_id,
                "days":         days,
                "total_cost":   round(float(row.total_cost or 0), 4),
                "total_tokens": int(row.total_tokens or 0),
                "calls":        int(row.calls),
            }
        except Exception as exc:
            log.warning("user_cost failed: %s", exc)
            return {"user_id": user_id, "total_cost": 0.0, "error": str(exc)}

    async def executive_summary(self) -> Dict:
        """
        Returns the executive-level cost snapshot:
        - today's spend
        - this month's spend
        - top 5 most expensive missions
        - provider breakdown (30 days)
        - daily trend (30 days)
        """
        try:
            from backend.database.engine import AsyncSessionLocal as async_session
            from backend.database.models.cost_tracking import CostRecord

            today = date.today()
            month_start = today.replace(day=1)

            async with async_session() as session:
                # Today's spend
                r_today = (await session.execute(
                    select(func.sum(CostRecord.cost_usd))
                    .where(CostRecord.report_date == today)
                )).scalar() or 0.0

                # This month's spend
                r_month = (await session.execute(
                    select(func.sum(CostRecord.cost_usd))
                    .where(CostRecord.report_date >= month_start)
                )).scalar() or 0.0

                # Top 5 missions by cost
                top_missions_rows = await session.execute(
                    select(
                        CostRecord.mission_id,
                        func.sum(CostRecord.cost_usd).label("cost"),
                        func.count().label("calls"),
                    )
                    .where(CostRecord.mission_id.isnot(None))
                    .group_by(CostRecord.mission_id)
                    .order_by(func.sum(CostRecord.cost_usd).desc())
                    .limit(5)
                )
                top_missions = [
                    {"mission_id": r.mission_id, "cost": round(float(r.cost), 4), "calls": int(r.calls)}
                    for r in top_missions_rows
                ]

            daily  = await self.daily_summary(30)
            by_prov = await self.provider_breakdown(30)

            return {
                "today_spend":   round(float(r_today), 4),
                "month_spend":   round(float(r_month), 4),
                "top_missions":  top_missions,
                "by_provider":   by_prov,
                "daily_trend":   daily,
            }
        except Exception as exc:
            log.warning("executive_summary failed: %s", exc)
            return {
                "today_spend":  0.0,
                "month_spend":  0.0,
                "top_missions": [],
                "by_provider":  [],
                "daily_trend":  [],
                "error":        str(exc),
            }


# Module singleton
cost_engine = CostEngine()
