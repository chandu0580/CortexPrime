"""
Enterprise Verification Intelligence Routes — REST API for verification.

Endpoints:
  POST /api/engineering/verification/verify       — Run full verification
  GET  /api/engineering/verification/list         — List verifications
  GET  /api/engineering/verification/{id}         — Get verification detail
  GET  /api/engineering/verification/report/{id}  — Get verification report
  GET  /api/engineering/verification/scorecards   — Get scorecards
  GET  /api/engineering/verification/dashboard    — Get executive dashboard
  GET  /api/engineering/verification/suggestions  — Get improvement suggestions
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_verification_intelligence import enterprise_verification_intelligence

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engineering/verification", tags=["Enterprise Verification Intelligence"])


class VerifyRequest(BaseModel):
    execution_id: str
    prediction_id: str = ""
    repository: str = ""
    team: str = ""
    service: str = ""
    environment: str = ""
    predicted_success: float = 0.5
    actual_success: bool = False
    predicted_duration_seconds: float = 600.0
    actual_duration_seconds: float = 0.0
    predicted_rollback_probability: float = 0.1
    actual_rolled_back: bool = False
    predicted_risk_score: float = 0.3
    actual_risk_score: float = 0.0
    predicted_cost_increase: float = 0.0
    actual_cost_increase: float = 0.0
    predicted_strategy: str = ""
    actual_strategy: str = ""
    actual_outcome: str = ""
    actual_failure_reason: str = ""
    change_categories: Optional[List[str]] = None
    changed_services: Optional[List[str]] = None
    has_db_migrations: bool = False
    has_infrastructure_changes: bool = False
    decision_accuracy: float = 0.0


@router.post("/verify")
async def run_verification(req: VerifyRequest) -> Dict[str, Any]:
    """Run full verification — compare prediction vs reality, generate report, adjust confidence."""
    try:
        result = await enterprise_verification_intelligence.verify(
            execution_id=req.execution_id,
            prediction_id=req.prediction_id,
            repository=req.repository,
            team=req.team,
            service=req.service,
            environment=req.environment,
            predicted_success=req.predicted_success,
            actual_success=req.actual_success,
            predicted_duration_seconds=req.predicted_duration_seconds,
            actual_duration_seconds=req.actual_duration_seconds,
            predicted_rollback_probability=req.predicted_rollback_probability,
            actual_rolled_back=req.actual_rolled_back,
            predicted_risk_score=req.predicted_risk_score,
            actual_risk_score=req.actual_risk_score,
            predicted_cost_increase=req.predicted_cost_increase,
            actual_cost_increase=req.actual_cost_increase,
            predicted_strategy=req.predicted_strategy,
            actual_strategy=req.actual_strategy,
            actual_outcome=req.actual_outcome,
            actual_failure_reason=req.actual_failure_reason,
            change_categories=req.change_categories,
            changed_services=req.changed_services,
            has_db_migrations=req.has_db_migrations,
            has_infrastructure_changes=req.has_infrastructure_changes,
            decision_accuracy=req.decision_accuracy,
        )
        return result
    except Exception as exc:
        log.error("Verification failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/list")
async def list_verifications() -> List[Dict[str, Any]]:
    """List all verifications."""
    try:
        return await enterprise_verification_intelligence.list_verifications()
    except Exception as exc:
        log.error("Failed to list verifications: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{verification_id}")
async def get_verification(verification_id: str) -> Dict[str, Any]:
    """Get verification detail by ID."""
    try:
        result = await enterprise_verification_intelligence.get_verification(verification_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Verification {verification_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to get verification: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/report/{report_id}")
async def get_verification_report(report_id: str) -> Dict[str, Any]:
    """Get verification report by ID."""
    try:
        report = await enterprise_verification_intelligence.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        return report
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to get report: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/scorecards/list")
async def get_scorecards(
    dimension: str = Query(default=""),
    entity: str = Query(default=""),
) -> List[Dict[str, Any]]:
    """Get engineering scorecards."""
    try:
        return await enterprise_verification_intelligence.get_scorecards(dimension, entity)
    except Exception as exc:
        log.error("Failed to get scorecards: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/scorecards/summary")
async def get_scorecard_summary() -> Dict[str, Any]:
    """Get scorecard summary."""
    try:
        return await enterprise_verification_intelligence.get_scorecard_summary()
    except Exception as exc:
        log.error("Failed to get scorecard summary: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dashboard/executive")
async def get_executive_dashboard() -> Dict[str, Any]:
    """Get executive dashboard with accuracy metrics and trends."""
    try:
        return await enterprise_verification_intelligence.get_dashboard()
    except Exception as exc:
        log.error("Failed to get dashboard: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/suggestions")
async def get_improvement_suggestions() -> List[Dict[str, Any]]:
    """Get continuous improvement suggestions."""
    try:
        return await enterprise_verification_intelligence.get_improvement_suggestions()
    except Exception as exc:
        log.error("Failed to get suggestions: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
