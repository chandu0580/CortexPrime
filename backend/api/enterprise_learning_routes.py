"""
Enterprise Learning Routes — REST API for the Enterprise Learning Engine.

Endpoints
---------
  GET  /api/enterprise/learning/lessons        — lessons learned
  GET  /api/enterprise/learning/best-practices — best practices
  GET  /api/enterprise/learning/failure-patterns — failure patterns
  GET  /api/enterprise/learning/recovery-patterns — recovery patterns
  GET  /api/enterprise/learning/recommendations — recommendations
  GET  /api/enterprise/learning/dashboard       — aggregated dashboard
  GET  /api/enterprise/learning/confidence-trends — confidence trends
  POST /api/enterprise/learning/analyze         — trigger on-demand analysis
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.services.enterprise_learning_service import enterprise_learning

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enterprise/learning", tags=["Enterprise Learning"])


@router.get("/lessons")
async def get_lessons(
    limit: int = Query(50, ge=1, le=500),
    domain: Optional[str] = None,
    lesson_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Get lessons learned from enterprise missions."""
    lessons = await enterprise_learning.get_lessons(
        limit=limit, domain=domain, lesson_type=lesson_type,
    )
    return {"lessons": lessons, "total": len(lessons)}


@router.get("/best-practices")
async def get_best_practices(
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Get discovered best practices."""
    practices = await enterprise_learning.get_best_practices(limit=limit)
    return {"practices": practices, "total": len(practices)}


@router.get("/failure-patterns")
async def get_failure_patterns(
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Get failure patterns sorted by frequency."""
    patterns = await enterprise_learning.get_failure_patterns(limit=limit)
    return {"patterns": patterns, "total": len(patterns)}


@router.get("/recovery-patterns")
async def get_recovery_patterns() -> Dict[str, Any]:
    """Get recovery strategy patterns."""
    patterns = await enterprise_learning.get_recovery_patterns()
    return {"patterns": patterns, "total": len(patterns)}


@router.get("/recommendations")
async def get_recommendations(
    limit: int = Query(20, ge=1, le=100),
    priority: Optional[str] = None,
) -> Dict[str, Any]:
    """Get actionable recommendations."""
    recommendations = await enterprise_learning.recommend(
        limit=limit, priority=priority,
    )
    return {
        "recommendations": recommendations,
        "total": len(recommendations),
    }


@router.get("/dashboard")
async def get_learning_dashboard() -> Dict[str, Any]:
    """Get aggregated learning dashboard data."""
    dashboard = await enterprise_learning.get_dashboard()
    return dashboard


@router.get("/confidence-trends")
async def get_confidence_trends() -> Dict[str, Any]:
    """Get confidence trends over accumulated intelligence."""
    trends = await enterprise_learning.get_confidence_trends()
    return trends


@router.post("/analyze")
async def trigger_analysis(
    execution_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Trigger on-demand analysis. If execution_id is provided, analyze a
    specific mission; otherwise analyze recent missions."""
    try:
        if execution_id:
            result = await enterprise_learning.analyze_mission(execution_id)
        else:
            result = await enterprise_learning.analyze_all(limit=limit)
        return {
            "status": "completed",
            "result": result,
        }
    except Exception as exc:
        log.error("Learning analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
