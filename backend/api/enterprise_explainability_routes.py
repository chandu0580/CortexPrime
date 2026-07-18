"""
Enterprise Explainability Routes — REST API for decision intelligence.

Endpoints
---------
  GET /api/explainability/missions                — list missions
  GET /api/explainability/missions/{id}           — full explanation
  GET /api/explainability/missions/{id}/timeline  — mission timeline
  GET /api/explainability/missions/{id}/reasoning — reasoning chain
  GET /api/explainability/missions/{id}/evidence  — evidence used
  GET /api/explainability/missions/{id}/alternatives — alternatives
  GET /api/explainability/missions/{id}/policies  — policy evaluations
  GET /api/explainability/missions/{id}/verification — verification results
  GET /api/explainability/missions/{id}/confidence — confidence analysis
  GET /api/explainability/dashboard               — aggregated dashboard
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.services.enterprise_explainability_service import enterprise_explainability

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/explainability", tags=["Enterprise Explainability"])


@router.get("/missions")
async def list_explainable_missions(
    limit: int = Query(50, ge=1, le=200),
):
    """List missions available for explainability analysis."""
    missions = await enterprise_explainability.list_missions(limit=limit)
    return {"missions": missions, "total": len(missions)}


@router.get("/missions/{execution_id}")
async def get_mission_explanation(execution_id: str):
    """Full decision explanation for a mission."""
    try:
        explanation = await enterprise_explainability.get_mission_explanation(execution_id)
        if not explanation.get("summary", {}).get("mission_objective"):
            raise HTTPException(
                status_code=404,
                detail=f"No data found for execution {execution_id}",
            )
        return explanation
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Explainability fetch failed for %s: %s", execution_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions/{execution_id}/timeline")
async def get_mission_timeline(execution_id: str):
    """Get the mission timeline from replay + audit data."""
    try:
        return await enterprise_explainability.get_timeline(execution_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions/{execution_id}/reasoning")
async def get_mission_reasoning(execution_id: str):
    """Get the reasoning chain for a mission."""
    try:
        return await enterprise_explainability.get_reasoning(execution_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions/{execution_id}/evidence")
async def get_mission_evidence(execution_id: str):
    """Get all evidence used during a mission."""
    try:
        return await enterprise_explainability.get_evidence(execution_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions/{execution_id}/alternatives")
async def get_mission_alternatives(execution_id: str):
    """Get alternatives considered during a mission."""
    try:
        return await enterprise_explainability.get_alternatives(execution_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions/{execution_id}/policies")
async def get_mission_policies(execution_id: str):
    """Get policies evaluated during a mission."""
    try:
        return await enterprise_explainability.get_policies(execution_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions/{execution_id}/verification")
async def get_mission_verification(execution_id: str):
    """Get verification results for a mission."""
    try:
        return await enterprise_explainability.get_verification(execution_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/missions/{execution_id}/confidence")
async def get_mission_confidence(execution_id: str):
    """Get confidence analysis for a mission."""
    try:
        return await enterprise_explainability.get_confidence(execution_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dashboard")
async def get_explainability_dashboard():
    """Aggregated explainability dashboard."""
    try:
        return await enterprise_explainability.get_dashboard()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
