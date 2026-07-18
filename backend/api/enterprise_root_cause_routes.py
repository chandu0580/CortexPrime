"""
Enterprise Root Cause Analysis Intelligence — REST API.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_root_cause_analysis import (
    RCA_EVENTS,
    ConfidenceCalculator,
    CorrelationEngine,
    EvidenceCollector,
    ImpactAnalyzer,
    RootCauseBuilder,
    TimelineCorrelator,
    root_cause_analysis,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rca", tags=["Enterprise Root Cause Analysis"])


# ---- Request schemas ----

class RunAnalysisRequest(BaseModel):
    incident_id: str = ""
    problem: str = ""
    hours_back: int = 24


# ---- Analysis ----

@router.post("/analyze")
async def run_analysis(body: RunAnalysisRequest):
    try:
        result = await root_cause_analysis.run_analysis(
            incident_id=body.incident_id,
            problem=body.problem,
            hours_back=body.hours_back,
        )
        return result
    except Exception as exc:
        raise HTTPException(502, f"RCA analysis failed: {exc}")


@router.get("/analyses")
async def list_analyses(limit: int = Query(50, ge=1, le=200)):
    try:
        return {"analyses": root_cause_analysis.list_analyses(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str):
    a = root_cause_analysis.get_analysis(analysis_id)
    if a is None:
        raise HTTPException(404, "Analysis not found")
    return a


# ---- Incidents ----

@router.get("/incidents")
async def list_incidents(limit: int = Query(50, ge=1, le=200)):
    try:
        return {"incidents": root_cause_analysis.list_incidents(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    i = root_cause_analysis.get_incident(incident_id)
    if i is None:
        raise HTTPException(404, "Incident not found")
    return i


# ---- Dashboard ----

@router.get("/dashboard")
async def dashboard():
    try:
        return root_cause_analysis.get_dashboard()
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Timeline Correlator ----

@router.post("/timeline/build")
async def build_timeline(
    hours_back: int = Query(24, ge=1, le=168),
    github_events: Optional[List[Dict[str, Any]]] = None,
    cicd_events: Optional[List[Dict[str, Any]]] = None,
    infra_events: Optional[List[Dict[str, Any]]] = None,
    log_analyses: Optional[List[Dict[str, Any]]] = None,
    traces: Optional[List[Dict[str, Any]]] = None,
    network_failures: Optional[List[Dict[str, Any]]] = None,
    prometheus_alerts: Optional[List[Dict[str, Any]]] = None,
):
    try:
        timeline = TimelineCorrelator.build_timeline(
            hours_back=hours_back,
            github_events=github_events or [],
            cicd_events=cicd_events or [],
            infra_events=infra_events or [],
            log_analyses=log_analyses or [],
            traces=traces or [],
            network_failures=network_failures or [],
            prometheus_alerts=prometheus_alerts or [],
        )
        return {"timeline": timeline}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/timeline/errors")
async def error_events(timeline_json: Optional[str] = Query(None)):
    try:
        import json as _json
        timeline = _json.loads(timeline_json) if timeline_json else []
        errors = TimelineCorrelator.extract_error_events(timeline)
        return {"error_events": errors}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Hypotheses ----

@router.post("/hypotheses/build")
async def build_hypotheses(data: List[Dict[str, Any]]):
    try:
        hypotheses = RootCauseBuilder.build_hypotheses(data)
        return {"hypotheses": hypotheses}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/hypotheses/rank")
async def rank_hypotheses(data: Dict[str, Any]):
    try:
        ranked = ConfidenceCalculator.rank_hypotheses(
            data.get("hypotheses", []),
            data.get("timeline", []),
        )
        return {"ranked": ranked}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Impact ----

@router.post("/impact/analyze")
async def analyze_impact(data: List[Dict[str, Any]]):
    try:
        impact = ImpactAnalyzer.analyze(data)
        return {"impact": impact}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Correlations ----

@router.post("/correlate/time")
async def correlate_time(
    data: List[Dict[str, Any]],
    time_window_seconds: int = Query(300, ge=60, le=3600),
):
    try:
        groups = CorrelationEngine.correlate_by_time(data, time_window_seconds)
        return {"correlations": groups}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/correlate/entity")
async def correlate_entity(data: List[Dict[str, Any]]):
    try:
        groups = CorrelationEngine.correlate_by_entity(data)
        return {"correlations": groups}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Evidence ----

@router.get("/evidence/collect")
async def collect_evidence():
    try:
        evidence = EvidenceCollector.collect_all_subsystem_evidence()
        return {"evidence": evidence}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Story ----

@router.post("/story/generate")
async def generate_story(data: Dict[str, Any]):
    try:
        from backend.services.enterprise_root_cause_analysis import EngineeringStoryGenerator
        story = EngineeringStoryGenerator.generate(
            problem=data.get("problem", ""),
            timeline=data.get("timeline", []),
            top_hypothesis=data.get("top_hypothesis"),
            impact=data.get("impact", {}),
            confidence=data.get("confidence", 0.0),
            evidence_summary=data.get("evidence_summary", {}),
        )
        return {"story": story}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Events ----

@router.get("/events")
async def list_events():
    return {"events": RCA_EVENTS}
