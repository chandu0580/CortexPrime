"""
Enterprise Context Intelligence Routes — REST API for engineering context.

Endpoints:
  POST /api/engineering/context/snapshot  — Build a full context snapshot
  GET  /api/engineering/context/snapshot  — Build and return context snapshot
  GET  /api/engineering/context/health    — Health check for context sources
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_context_intelligence import enterprise_context_intelligence

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engineering/context", tags=["Enterprise Engineering Context"])


class SnapshotRequest(BaseModel):
    repository: str = ""
    branch: str = "main"
    commit: str = ""
    service: str = ""
    execution_id: str = ""
    environment: str = ""
    include_historical: bool = True
    include_operational: bool = True
    include_dependency: bool = True
    include_business: bool = True


@router.post("/snapshot")
async def build_context_snapshot(req: SnapshotRequest) -> Dict[str, Any]:
    """Build a complete ContextSnapshot by aggregating all subsystems."""
    try:
        snapshot = await enterprise_context_intelligence.build_snapshot(
            repository=req.repository,
            branch=req.branch,
            commit=req.commit,
            service=req.service,
            execution_id=req.execution_id,
            environment=req.environment,
            include_historical=req.include_historical,
            include_operational=req.include_operational,
            include_dependency=req.include_dependency,
            include_business=req.include_business,
        )
        return snapshot.to_dict()
    except Exception as exc:
        log.error("Context snapshot build failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/snapshot")
async def get_context_snapshot(
    repository: str = Query(default=""),
    branch: str = Query(default="main"),
    commit: str = Query(default=""),
    execution_id: str = Query(default=""),
    environment: str = Query(default=""),
) -> Dict[str, Any]:
    """Build and return a context snapshot via GET (simpler interface)."""
    try:
        snapshot = await enterprise_context_intelligence.build_snapshot(
            repository=repository,
            branch=branch,
            commit=commit,
            execution_id=execution_id,
            environment=environment,
        )
        return snapshot.to_dict()
    except Exception as exc:
        log.error("Context snapshot build failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health")
async def context_health_check() -> Dict[str, Any]:
    """Check availability of context sources."""
    sources = {
        "RuntimeStore": False,
        "CodeIntelligence": False,
        "KnowledgeGraph": False,
        "PrometheusIntelligence": False,
        "LokiIntelligence": False,
        "InfrastructureIntelligence": False,
        "ArgoCDIntelligence": False,
        "GitHubIntegration": False,
        "CICDIntelligence": False,
        "TerraformIntelligence": False,
        "LearningService": False,
        "RecommendationEngine": False,
        "RCA": False,
        "ReplayStore": False,
    }

    try:
        from backend.services.enterprise_runtime_store import runtime_store
        sources["RuntimeStore"] = hasattr(runtime_store, "get_execution")
    except Exception:
        pass

    try:
        from backend.services.enterprise_code_intelligence import code_intelligence
        sources["CodeIntelligence"] = hasattr(code_intelligence, "get_graph")
    except Exception:
        pass

    try:
        from backend.services.enterprise_graph_service import enterprise_graph
        sources["KnowledgeGraph"] = hasattr(enterprise_graph, "get_mission_graph")
    except Exception:
        pass

    try:
        from backend.services.enterprise_prometheus_intelligence import prometheus_intelligence
        sources["PrometheusIntelligence"] = hasattr(prometheus_intelligence, "get_alerts")
    except Exception:
        pass

    try:
        from backend.services.enterprise_loki_intelligence import loki_intelligence
        sources["LokiIntelligence"] = hasattr(loki_intelligence, "list_labels")
    except Exception:
        pass

    try:
        from backend.services.enterprise_infrastructure_intelligence import infra_intelligence
        sources["InfrastructureIntelligence"] = hasattr(infra_intelligence, "sync_from_kubernetes")
    except Exception:
        pass

    try:
        from backend.services.enterprise_argocd_intelligence import argocd_intelligence
        sources["ArgoCDIntelligence"] = hasattr(argocd_intelligence, "discover_all")
    except Exception:
        pass

    try:
        from backend.services.enterprise_github_integration import github_integration
        sources["GitHubIntegration"] = hasattr(github_integration, "get_recent_activity")
    except Exception:
        pass

    try:
        from backend.services.enterprise_cicd_intelligence import cicd_intelligence
        sources["CICDIntelligence"] = hasattr(cicd_intelligence, "get_dashboard")
    except Exception:
        pass

    try:
        from backend.services.enterprise_terraform_intelligence import terraform_intelligence
        sources["TerraformIntelligence"] = hasattr(terraform_intelligence, "discover_all")
    except Exception:
        pass

    try:
        from backend.services.enterprise_learning_service import enterprise_learning
        sources["LearningService"] = hasattr(enterprise_learning, "get_dashboard")
    except Exception:
        pass

    try:
        from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
        sources["RecommendationEngine"] = hasattr(enterprise_recommendation_engine, "get_active")
    except Exception:
        pass

    try:
        from backend.services.enterprise_root_cause_analysis import root_cause_analysis
        sources["RCA"] = hasattr(root_cause_analysis, "list_analyses")
    except Exception:
        pass

    try:
        from backend.services.mission_replay_store import replay_store
        sources["ReplayStore"] = hasattr(replay_store, "get_events")
    except Exception:
        pass

    available = sum(1 for v in sources.values() if v)
    total = len(sources)

    return {
        "status": "healthy" if available == total else "degraded",
        "available_sources": available,
        "total_sources": total,
        "sources": sources,
    }
