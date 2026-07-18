"""
Enterprise Engineering Decision Routes — REST API for the Decision Layer.

Endpoints:
  POST /api/engineering/decision/analyze     — Run full decision analysis
  GET  /api/engineering/decision/report/{id} — Fetch a decision report by ID
  GET  /api/engineering/decision/history     — List recent decision reports
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.engineering_decision_engine import (
    EngineeringDecisionEngine,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engineering/decision", tags=["Enterprise Engineering Decision"])

engine = EngineeringDecisionEngine()


class AnalyzeRequest(BaseModel):
    source: str = "api"
    event_type: str = "manual"
    payload: Dict[str, Any]
    repository: str = ""
    branch: str = "main"
    commit_sha: str = ""


@router.post("/analyze")
async def analyze_decision(req: AnalyzeRequest) -> Dict[str, Any]:
    """Run the full decision pipeline (Phases 1-11) on a payload."""
    try:
        report = await engine.analyze(
            source=req.source,
            event_type=req.event_type,
            payload=req.payload,
            repository=req.repository,
            branch=req.branch,
            commit_sha=req.commit_sha,
        )
        return report.to_dict()
    except Exception as exc:
        log.error("Decision analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/report/{report_id}")
async def get_decision_report(report_id: str) -> Dict[str, Any]:
    """Retrieve a decision report by ID from the runtime store."""
    try:
        from backend.services.enterprise_runtime_store import runtime_store
        execution = await runtime_store.get_execution(report_id)
        if not execution:
            raise HTTPException(status_code=404, detail=f"Decision report {report_id} not found")
        return execution
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to fetch decision report %s: %s", report_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/history")
async def list_decision_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """List recent decision reports."""
    try:
        from backend.services.enterprise_runtime_store import runtime_store
        executions = await runtime_store.list_executions(limit=limit, offset=offset)
        return {
            "executions": [dict(e) if hasattr(e, "items") else e for e in executions],
            "total": len(executions),
            "limit": limit,
            "offset": offset,
        }
    except Exception as exc:
        log.error("Failed to list decision history: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
