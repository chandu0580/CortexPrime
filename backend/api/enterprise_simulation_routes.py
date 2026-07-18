"""
Enterprise Predictive Simulation Routes — REST API for simulation/prediction.

Endpoints:
  POST /api/engineering/simulation/simulate     — Run full simulation
  GET  /api/engineering/simulation/predictions  — List predictions
  GET  /api/engineering/simulation/prediction/{id} — Get prediction detail
  GET  /api/engineering/simulation/report/{id}  — Get executive report
  POST /api/engineering/simulation/feedback     — Record prediction feedback
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.enterprise_predictive_simulation import enterprise_predictive_simulation

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engineering/simulation", tags=["Enterprise Predictive Simulation"])


class SimulateRequest(BaseModel):
    repository: str = ""
    branch: str = "main"
    commit_sha: str = ""
    execution_id: str = ""
    service: str = ""
    environment: str = ""
    changed_files: Optional[List[str]] = None
    changed_services: Optional[List[str]] = None
    change_categories: Optional[List[str]] = None


class FeedbackRequest(BaseModel):
    prediction_id: str
    execution_id: str = ""
    repository: str = ""
    actual_outcome: str = "unknown"
    predicted_success_probability: float = 0.5
    predicted_strategy: str = ""
    actual_strategy: str = ""
    duration_seconds: float = 0.0
    predicted_duration: float = 0.0


@router.post("/simulate")
async def run_simulation(req: SimulateRequest) -> Dict[str, Any]:
    """Run full predictive simulation — predicts outcomes before execution."""
    try:
        result = await enterprise_predictive_simulation.simulate(
            repository=req.repository,
            branch=req.branch,
            commit_sha=req.commit_sha,
            execution_id=req.execution_id,
            service=req.service,
            environment=req.environment,
            changed_files=req.changed_files,
            changed_services=req.changed_services,
            change_categories=req.change_categories,
        )
        return result
    except Exception as exc:
        log.error("Simulation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/predictions")
async def list_predictions() -> List[Dict[str, Any]]:
    """List all cached predictions."""
    try:
        return await enterprise_predictive_simulation.list_predictions()
    except Exception as exc:
        log.error("Failed to list predictions: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/prediction/{prediction_id}")
async def get_prediction(prediction_id: str) -> Dict[str, Any]:
    """Get detailed prediction by ID."""
    try:
        result = await enterprise_predictive_simulation.get_prediction(prediction_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Prediction {prediction_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to get prediction: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/report/{prediction_id}")
async def get_prediction_report(prediction_id: str) -> Dict[str, Any]:
    """Get executive prediction report by prediction ID."""
    try:
        report = await enterprise_predictive_simulation.get_report(prediction_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Report for {prediction_id} not found")
        return report
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to get report: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/feedback")
async def record_feedback(req: FeedbackRequest) -> Dict[str, Any]:
    """Record prediction feedback — compare prediction vs reality."""
    try:
        feedback = await enterprise_predictive_simulation.feedback(
            prediction_id=req.prediction_id,
            execution_id=req.execution_id,
            repository=req.repository,
            actual_outcome=req.actual_outcome,
            predicted_success_probability=req.predicted_success_probability,
            predicted_strategy=req.predicted_strategy,
            actual_strategy=req.actual_strategy,
            duration_seconds=req.duration_seconds,
            predicted_duration=req.predicted_duration,
        )
        return {
            "prediction_id": feedback.prediction_id,
            "execution_id": feedback.execution_id,
            "actual_outcome": feedback.actual_outcome,
            "predicted_success": feedback.predicted_success,
            "actual_success": feedback.actual_success,
            "accuracy": feedback.accuracy,
            "confidence_adjustment": feedback.confidence_adjustment,
        }
    except Exception as exc:
        log.error("Feedback recording failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
