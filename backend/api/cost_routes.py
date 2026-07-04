"""
/api/costs/* — Mission Cost Engine REST API.

Endpoints
---------
GET /api/costs/summary          Executive cost summary (today / month / trends)
GET /api/costs/daily            Daily cost totals (last 30 days)
GET /api/costs/providers        Provider breakdown (last 30 days)
GET /api/costs/mission/{id}     Cost for a specific mission
GET /api/costs/user/{id}        Cost for a specific user
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.analytics.cost_engine import cost_engine
from backend.auth.dependencies import require_user

router = APIRouter(
    prefix="/api/costs",
    tags=["Cost Engine"],
    dependencies=[Depends(require_user)],
)


@router.get("/summary")
async def cost_summary():
    """Executive cost summary — today, this month, top missions, trends."""
    return await cost_engine.executive_summary()


@router.get("/daily")
async def cost_daily(days: int = Query(30, ge=1, le=365)):
    """Daily cost totals for the last N days."""
    return {"daily": await cost_engine.daily_summary(days=days), "days": days}


@router.get("/providers")
async def cost_providers(days: int = Query(30, ge=1, le=365)):
    """Provider cost breakdown for the last N days."""
    return {"providers": await cost_engine.provider_breakdown(days=days), "days": days}


@router.get("/mission/{mission_id}")
async def cost_by_mission(mission_id: str):
    """Total cost and provider breakdown for a specific mission."""
    return await cost_engine.mission_cost(mission_id)


@router.get("/user/{user_id}")
async def cost_by_user(user_id: str, days: int = Query(30, ge=1, le=365)):
    """Cost breakdown for a specific user over the last N days."""
    return await cost_engine.user_cost(user_id, days=days)
