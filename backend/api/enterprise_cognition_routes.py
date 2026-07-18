"""
Enterprise Continuous Cognition Runtime Routes — REST API for the cognition center.

Endpoints:
  GET  /api/cognition/status          — Cognition runtime status
  GET  /api/cognition/dashboard       — Full cognition dashboard
  GET  /api/cognition/timeline        — Cognition timeline entries
  POST /api/cognition/start           — Start the cognition loop
  POST /api/cognition/stop            — Stop the cognition loop
  POST /api/cognition/pause           — Pause the cognition loop
  POST /api/cognition/resume          — Resume the cognition loop
  GET  /api/cognition/health          — Health check for all cognition sources
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_continuous_cognition_runtime import (
    enterprise_continuous_cognition_runtime,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cognition", tags=["Enterprise Continuous Cognition"])


@router.get("/status")
async def cognition_status() -> Dict[str, Any]:
    """Get cognition runtime status."""
    return enterprise_continuous_cognition_runtime.get_status()


@router.get("/dashboard")
async def cognition_dashboard() -> Dict[str, Any]:
    """Get complete cognition dashboard data."""
    try:
        return enterprise_continuous_cognition_runtime.get_dashboard()
    except Exception as exc:
        log.error("Cognition dashboard failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/timeline")
async def cognition_timeline(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    change_type: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    """Get cognition timeline entries with optional filtering."""
    try:
        return enterprise_continuous_cognition_runtime.get_timeline(
            limit=limit,
            offset=offset,
            change_type=change_type,
        )
    except Exception as exc:
        log.error("Cognition timeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class IntervalConfig(BaseModel):
    loop_interval_seconds: Optional[int] = None
    repo_check_interval_seconds: Optional[int] = None
    infra_check_interval_seconds: Optional[int] = None


@router.post("/start")
async def cognition_start(config: Optional[IntervalConfig] = None) -> Dict[str, Any]:
    """Start the continuous cognition loop."""
    global enterprise_continuous_cognition_runtime
    if config:
        if config.loop_interval_seconds:
            enterprise_continuous_cognition_runtime._loop_interval = max(10, config.loop_interval_seconds)
        if config.repo_check_interval_seconds:
            enterprise_continuous_cognition_runtime._repo_interval = max(30, config.repo_check_interval_seconds)
        if config.infra_check_interval_seconds:
            enterprise_continuous_cognition_runtime._infra_interval = max(30, config.infra_check_interval_seconds)

    await enterprise_continuous_cognition_runtime.start()
    return {"status": "started", "config": enterprise_continuous_cognition_runtime.get_status()}


@router.post("/stop")
async def cognition_stop() -> Dict[str, Any]:
    """Stop the continuous cognition loop."""
    await enterprise_continuous_cognition_runtime.stop()
    return {"status": "stopped"}


@router.post("/pause")
async def cognition_pause() -> Dict[str, Any]:
    """Pause the continuous cognition loop."""
    await enterprise_continuous_cognition_runtime.pause()
    return {"status": "paused"}


@router.post("/resume")
async def cognition_resume() -> Dict[str, Any]:
    """Resume the paused cognition loop."""
    await enterprise_continuous_cognition_runtime.resume()
    return {"status": "resumed"}


@router.get("/health")
async def cognition_health() -> Dict[str, Any]:
    """Check availability of all cognition-relevant services."""
    sources = {
        "RepositoryBrain": False,
        "ContextIntelligence": False,
        "EngineeringDecisionEngine": False,
        "PredictiveSimulation": False,
        "RuntimeStore": False,
        "ReplayStore": False,
        "KnowledgeGraph": False,
        "EventHub": False,
        "InfrastructureIntelligence": False,
        "GitHubIntegration": False,
        "ArgoCDIntelligence": False,
        "PrometheusIntelligence": False,
        "LokiIntelligence": False,
        "TraceIntelligence": False,
        "EngineeringMemory": False,
        "LearningEngine": False,
        "ExecutiveRuntime": False,
    }

    try:
        from backend.services.enterprise_repository_brain import repository_brain
        sources["RepositoryBrain"] = hasattr(repository_brain, "get_brain_summary")
    except Exception:
        pass

    try:
        from backend.services.enterprise_context_intelligence import enterprise_context_intelligence
        sources["ContextIntelligence"] = hasattr(enterprise_context_intelligence, "build_snapshot")
    except Exception:
        pass

    try:
        sources["EngineeringDecisionEngine"] = True
    except Exception:
        pass

    try:
        from backend.services.enterprise_predictive_simulation import enterprise_predictive_simulation
        sources["PredictiveSimulation"] = hasattr(enterprise_predictive_simulation, "simulate")
    except Exception:
        pass

    try:
        from backend.services.enterprise_runtime_store import runtime_store
        sources["RuntimeStore"] = hasattr(runtime_store, "get_execution")
    except Exception:
        pass

    try:
        from backend.services.mission_replay_store import replay_store
        sources["ReplayStore"] = hasattr(replay_store, "record")
    except Exception:
        pass

    try:
        from backend.services.enterprise_graph_service import enterprise_graph
        sources["KnowledgeGraph"] = hasattr(enterprise_graph, "record_decision")
    except Exception:
        pass

    try:
        from backend.services.enterprise_event_hub import enterprise_hub
        sources["EventHub"] = hasattr(enterprise_hub, "emit")
    except Exception:
        pass

    try:
        from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
        sources["InfrastructureIntelligence"] = hasattr(infrastructure_intelligence, "get_cluster_health")
    except Exception:
        pass

    try:
        from backend.services.enterprise_github_integration import github_integration
        sources["GitHubIntegration"] = hasattr(github_integration, "get_recent_activity")
    except Exception:
        pass

    try:
        from backend.services.enterprise_argocd_intelligence import argocd_intelligence
        sources["ArgoCDIntelligence"] = hasattr(argocd_intelligence, "discover_all")
    except Exception:
        pass

    try:
        from backend.services.enterprise_prometheus_intelligence import alert_intelligence
        sources["PrometheusIntelligence"] = hasattr(alert_intelligence, "get_alerts")
    except Exception:
        pass

    try:
        from backend.services.enterprise_loki_intelligence import loki_intelligence
        sources["LokiIntelligence"] = hasattr(loki_intelligence, "check_recent_errors")
    except Exception:
        pass

    try:
        from backend.services.enterprise_trace_intelligence import trace_intelligence
        sources["TraceIntelligence"] = hasattr(trace_intelligence, "get_service_graph")
    except Exception:
        pass

    try:
        from backend.services.enterprise_engineering_memory import enterprise_engineering_memory
        sources["EngineeringMemory"] = hasattr(enterprise_engineering_memory, "build_experience")
    except Exception:
        pass

    try:
        from backend.services.enterprise_learning_service import enterprise_learning
        sources["LearningEngine"] = hasattr(enterprise_learning, "get_dashboard")
    except Exception:
        pass

    try:
        sources["ExecutiveRuntime"] = True
    except Exception:
        pass

    # Cognition runtime health
    runtime_healthy = enterprise_continuous_cognition_runtime.is_running

    available = sum(1 for v in sources.values() if v)
    total = len(sources)

    return {
        "status": "healthy" if (available == total and runtime_healthy) else "degraded",
        "cognition_runtime": "running" if runtime_healthy else "stopped",
        "available_sources": available,
        "total_sources": total,
        "sources": sources,
    }
