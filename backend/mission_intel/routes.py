from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from backend.mission_intel.models import (
    CapabilityPlan,
    ExecutionPlan,
    GovernancePlan,
    KnowledgeInsight,
    LearningInsight,
    MissionAnalysis,
    MissionDecomposition,
    MissionTimeline,
    MissionVerification,
)
from backend.mission_intel.service import mission_intel_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mission-intel", tags=["Mission Intelligence"])


def _to_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        result: Dict[str, Any] = {}
        for f in obj.__dataclass_fields__:
            val = getattr(obj, f)
            if hasattr(val, "__dataclass_fields__"):
                result[f] = _to_dict(val)
            elif isinstance(val, list):
                result[f] = [_to_dict(v) if hasattr(v, "__dataclass_fields__") else v for v in val]
            elif isinstance(val, dict):
                result[f] = {k: _to_dict(v) if hasattr(v, "__dataclass_fields__") else v for k, v in val.items()}
            elif hasattr(val, "value"):
                result[f] = val.value
            else:
                result[f] = val
        return result
    if hasattr(obj, "value"):
        return {"value": obj.value}
    return {"value": str(obj)}


@router.post("/analyze")
async def analyze_goal(payload: Dict[str, Any]) -> Dict[str, Any]:
    goal = payload.get("goal", "")
    if not goal:
        raise HTTPException(status_code=400, detail="'goal' is required")
    context = payload.get("context")
    try:
        analysis = await mission_intel_service.analyze(goal, context)
        return {"status": "ok", "analysis": _to_dict(analysis)}
    except Exception as exc:
        log.error("Analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/decompose")
async def decompose_goal(payload: Dict[str, Any]) -> Dict[str, Any]:
    goal = payload.get("goal", "")
    if not goal:
        raise HTTPException(status_code=400, detail="'goal' is required")
    context = payload.get("context")
    try:
        analysis = await mission_intel_service.analyze(goal, context)
        decomposition = await mission_intel_service.decompose(analysis)
        return {"status": "ok", "analysis": _to_dict(analysis), "decomposition": _to_dict(decomposition)}
    except Exception as exc:
        log.error("Decomposition failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/full-pipeline")
async def run_full_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    goal = payload.get("goal", "")
    if not goal:
        raise HTTPException(status_code=400, detail="'goal' is required")
    context = payload.get("context")
    try:
        result = await mission_intel_service.run_full_pipeline(goal, context)
        return {
            "status": "ok",
            "analysis": _to_dict(result["analysis"]),
            "decomposition": _to_dict(result["decomposition"]),
            "capability_plan": _to_dict(result["capability_plan"]),
            "knowledge_insight": _to_dict(result["knowledge_insight"]),
            "learning_insight": _to_dict(result["learning_insight"]),
            "governance_plan": _to_dict(result["governance_plan"]),
            "execution_plan": _to_dict(result["execution_plan"]),
            "verification": _to_dict(result["verification"]),
            "timeline": _to_dict(result["timeline"]),
        }
    except Exception as exc:
        log.error("Full pipeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/plan")
async def plan_mission(payload: Dict[str, Any]) -> Dict[str, Any]:
    goal = payload.get("goal", "")
    if not goal:
        raise HTTPException(status_code=400, detail="'goal' is required")
    context = payload.get("context")
    try:
        analysis = await mission_intel_service.analyze(goal, context)
        decomposition = await mission_intel_service.decompose(analysis)
        capability_plan = await mission_intel_service.plan_capability(decomposition, None)
        knowledge_insight = await mission_intel_service.plan_knowledge(analysis)
        learning_insight = await mission_intel_service.plan_learning(analysis, knowledge_insight)
        governance_plan = await mission_intel_service.plan_governance(analysis, learning_insight)
        execution_plan = await mission_intel_service.plan_execution(decomposition, capability_plan, governance_plan)
        return {
            "status": "ok",
            "execution_plan": _to_dict(execution_plan),
            "governance_plan": _to_dict(governance_plan),
        }
    except Exception as exc:
        log.error("Planning failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "healthy", "service": "mission_intelligence"}
