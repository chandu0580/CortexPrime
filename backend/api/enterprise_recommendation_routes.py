"""
Enterprise Recommendation Routes — REST API for the Executive Recommendation Center.

Endpoints:
  GET    /api/recommendations              — list active recommendations
  GET    /api/recommendations/dashboard     — summary dashboard
  GET    /api/recommendations/categories    — recommendations grouped by category
  GET    /api/recommendations/{id}          — single recommendation detail
  POST   /api/recommendations/{id}/dismiss  — dismiss a recommendation
  POST   /api/recommendations/{id}/execute  — execute a recommendation action
  GET    /api/recommendations/history       — historical recommendations
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.services.enterprise_recommendation_engine import (
    enterprise_recommendation_engine,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["Enterprise Recommendations"])


@router.get("")
async def list_recommendations(
    category: Optional[str] = Query(None, description="Filter by category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
):
    """List active recommendations with optional filters."""
    return {
        "recommendations": enterprise_recommendation_engine.get_active(
            category=category, priority=priority,
        ),
        "total": len(enterprise_recommendation_engine.get_active(
            category=category, priority=priority,
        )),
    }


@router.get("/dashboard")
async def recommendation_dashboard():
    """Get recommendation dashboard summary."""
    return enterprise_recommendation_engine.get_dashboard()


@router.get("/categories")
async def recommendation_categories():
    """Get recommendations grouped by category."""
    return {
        "categories": enterprise_recommendation_engine.get_categories(),
        "total_categories": len(enterprise_recommendation_engine.get_categories()),
    }


@router.get("/{rec_id}")
async def get_recommendation(rec_id: str):
    """Get a single recommendation by ID."""
    rec = enterprise_recommendation_engine.get_by_id(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/{rec_id}/dismiss")
async def dismiss_recommendation(rec_id: str):
    """Dismiss a recommendation."""
    ok = enterprise_recommendation_engine.dismiss(rec_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Recommendation not found or already dismissed")
    return {"status": "dismissed", "id": rec_id}


@router.post("/{rec_id}/execute")
async def execute_recommendation(rec_id: str):
    """Mark a recommendation as executed."""
    ok = enterprise_recommendation_engine.mark_executed(rec_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Recommendation not found or already executed")
    return {"status": "executed", "id": rec_id}


@router.get("/history")
async def recommendation_history(limit: int = Query(100, ge=1, le=500)):
    """Get historical (dismissed/executed) recommendations."""
    return {
        "history": enterprise_recommendation_engine.get_history(limit=limit),
        "total": len(enterprise_recommendation_engine.get_history(limit=limit)),
    }
