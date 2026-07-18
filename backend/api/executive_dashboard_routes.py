"""
Executive Dashboard API - Aggregated endpoint for all dashboard panels.

Provides a single /api/executive/dashboard endpoint that gathers data
from every existing sub-system so the frontend can render all 5 panels
(Reasoning, Simulation, Adaptive Execution, Observation, Decision Memory)
with a single request.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from backend.auth.dependencies import require_user
from backend.connectors.registry import connector_registry
from backend.events.event_bus import event_bus
from backend.orchestration.execution_context import execution_context_manager
from backend.orchestration.orchestration_tracer import orchestration_tracer
from backend.runtime.runtime_metrics import runtime_metrics
from backend.runtime.runtime_state import runtime_state

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/executive",
    tags=["Executive Dashboard"],
    dependencies=[Depends(require_user)],
)


@router.get("/dashboard")
async def executive_dashboard() -> Dict[str, Any]:
    # ---- 1. Runtime Metrics ----
    metrics = runtime_metrics.export_metrics()

    # ---- 2. Active / Recent Executions ----
    active_execs = execution_context_manager.list_active()
    recent_execs = execution_context_manager.list_all()[:10]

    # ---- 3. Execution Traces (last 5 completed) ----
    traces: List[Dict[str, Any]] = []
    for ctx in recent_execs:
        if ctx.status == "completed":
            try:
                s = orchestration_tracer.summary(ctx.execution_id)
                if s:
                    traces.append(s)
            except Exception:
                pass
            if len(traces) >= 5:
                break

    # ---- 4. Event bus recent events ----
    list(event_bus._events[-50:]) if hasattr(event_bus, "_events") else []

    # ---- 5. Connector health ----
    connector_health = {}
    try:
        connector_health = await connector_registry.health_all()
    except Exception:
        pass

    # ---- 6. Runtime state ----
    runtime_state.get_state()

    # Build reasoning steps from active executions
    reasoning_sessions = []
    for ctx in active_execs:
        steps = []
        for stage_name in ctx.completed_stages:
            steps.append({
                "id": f"stage_{stage_name}",
                "type": _map_stage_to_reasoning_type(stage_name),
                "title": stage_name.replace("_", " ").title(),
                "description": f"Completed {stage_name} phase",
                "status": "completed",
                "confidence": _derive_confidence(stage_name, metrics),
            })
        if ctx.current_stage:
            steps.append({
                "id": f"stage_{ctx.current_stage}",
                "type": _map_stage_to_reasoning_type(ctx.current_stage),
                "title": ctx.current_stage.replace("_", " ").title(),
                "description": f"Executing {ctx.current_stage} phase",
                "status": "in_progress",
            })
        for stage_name in ctx.failed_stages:
            steps.append({
                "id": f"stage_{stage_name}_failed",
                "type": _map_stage_to_reasoning_type(stage_name),
                "title": stage_name.replace("_", " ").title(),
                "description": f"Failed during {stage_name}",
                "status": "failed",
            })

        reasoning_sessions.append({
            "id": ctx.execution_id,
            "missionId": ctx.execution_id,
            "goal": ctx.objective,
            "context": "",
            "constraints": [],
            "dependencies": [],
            "assumptions": [],
            "expectedOutcome": "",
            "strategies": _build_strategies(ctx),
            "overallConfidence": metrics.get("average_confidence_score", 0) or 0.5,
            "riskLevel": _assess_risk(metrics, len(ctx.failed_stages)),
            "recommendation": ctx.final_response or "In progress",
            "steps": steps,
            "status": "completed" if ctx.status == "completed" else "reasoning",
            "startedAt": ctx.started_at.isoformat() if ctx.started_at else None,
            "completedAt": ctx.ended_at.isoformat() if ctx.ended_at else None,
        })

    # Build simulation scenarios from execution traces
    simulation_scenarios = []
    for t in traces:
        simulation_scenarios.append({
            "id": t.get("execution_id", "unknown"),
            "name": f"Execution {t.get('total_spans', 0)} spans",
            "description": f"Completed in {t.get('total_ms', 0)}ms with {t.get('failed_spans', 0)} failed spans",
            "predictedOutcome": "failure" if t.get("failed_spans", 0) > 0 else "success",
            "confidence": max(0.1, 1.0 - (t.get("failed_spans", 0) / max(t.get("total_spans", 1), 1))),
            "metrics": [
                {"label": "Duration", "value": f"{t.get('total_ms', 0)}ms"},
                {"label": "Spans", "value": str(t.get("total_spans", 0))},
            ],
            "risks": [{"description": f"{t.get('failed_spans', 0)} failed spans", "severity": "high" if t.get("failed_spans", 0) > 0 else "low"}],
            "recommendation": "Review failed spans" if t.get("failed_spans", 0) > 0 else "Normal execution",
        })

    # Build adaptive execution data
    active_recoveries = []
    completed_recoveries = []
    failed_recoveries = []
    for ctx in active_execs:
        for fs in ctx.failed_stages:
            recovery = {
                "id": f"rec_{ctx.execution_id}_{fs}",
                "missionId": ctx.execution_id,
                "stepId": fs,
                "failureType": fs,
                "failureMessage": f"Stage {fs} failed",
                "attemptCount": ctx.retry_count + 1,
                "maxAttempts": ctx.max_retries,
                "strategy": "retry",
                "status": "recovering" if ctx.retry_count < ctx.max_retries else "failed",
                "startedAt": ctx.started_at.isoformat() if ctx.started_at else None,
            }
            if ctx.retry_count >= ctx.max_retries:
                failed_recoveries.append(recovery)
            else:
                active_recoveries.append(recovery)

    health_score = _compute_health_score(metrics)

    # Build observation metrics
    observation_categories = [
        {
            "id": "runtime_metrics",
            "label": "Runtime Metrics",
            "metrics": [
                {"label": "Total Executions", "value": metrics.get("total_executions", 0), "status": "healthy", "trend": "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
                {"label": "Active Executions", "value": metrics.get("active_executions", 0), "status": "healthy" if metrics.get("active_executions", 0) < 10 else "warning", "trend": "up" if metrics.get("active_executions", 0) > 0 else "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
                {"label": "Failed Executions", "value": metrics.get("failed_executions", 0), "status": "critical" if metrics.get("failed_executions", 0) > 5 else "healthy", "trend": "up" if metrics.get("failed_executions", 0) > 0 else "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
                {"label": "Avg Latency", "value": f"{metrics.get('average_latency_ms', 0):.0f}ms", "status": "healthy" if metrics.get("average_latency_ms", 0) < 5000 else "warning", "trend": "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
                {"label": "Active Agents", "value": metrics.get("active_agent_count", 0), "status": "healthy", "trend": "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
                {"label": "Total Tokens", "value": f"{(metrics.get('total_tokens', 0) / 1000):.0f}K", "status": "healthy", "trend": "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
            ],
            "alerts": _build_alerts(metrics),
        },
        {
            "id": "mission_progress",
            "label": "Mission Progress",
            "metrics": [
                {"label": "Completed", "value": metrics.get("completed_executions", 0), "status": "healthy", "trend": "up", "timestamp": datetime.now(timezone.utc).isoformat()},
                {"label": "Active", "value": len(active_execs), "status": "healthy" if len(active_execs) > 0 else "warning", "trend": "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
            ],
            "alerts": [],
        },
        {
            "id": "workflow_execution",
            "label": "Workflow Execution",
            "metrics": [
                {"label": "Queue Size", "value": len(active_execs), "status": "healthy", "trend": "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
            ],
            "alerts": [],
        },
        {
            "id": "connector_health",
            "label": "Connector Health",
            "metrics": [
                {"label": "Connected", "value": sum(1 for h in connector_health.values() if h.get("status") in ("available", "healthy")), "status": "healthy", "trend": "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
                {"label": "Total", "value": len(connector_health), "status": "healthy", "trend": "stable", "timestamp": datetime.now(timezone.utc).isoformat()},
            ],
            "alerts": [],
        },
    ]

    # Build decision memory from completed executions
    decisions = []
    for ctx in recent_execs:
        if ctx.status == "completed" and ctx.final_response:
            decisions.append({
                "id": ctx.execution_id,
                "missionId": ctx.execution_id,
                "decision": ctx.objective[:100],
                "rationale": ctx.final_response[:300],
                "alternatives": [],
                "outcome": "success" if ctx.status == "completed" else "failure",
                "confidence": metrics.get("average_confidence_score", 0) or 0.5,
                "riskLevel": _assess_risk(metrics, len(ctx.failed_stages)),
                "timestamp": ctx.ended_at.isoformat() if ctx.ended_at else datetime.now(timezone.utc).isoformat(),
                "metrics": {
                    "latency_ms": ctx.stage_timings.get("total", 0) if hasattr(ctx, "stage_timings") else 0,
                    "retries": ctx.retry_count,
                },
            })

    return {
        "reasoning": {
            "sessions": reasoning_sessions,
            "activeSessionId": reasoning_sessions[0]["id"] if reasoning_sessions else None,
            "isReasoning": any(s["status"] == "reasoning" for s in reasoning_sessions),
            "error": None,
        },
        "simulation": {
            "simulations": [{
                "id": "sim_latest",
                "missionId": t.get("execution_id", ""),
                "type": "execution",
                "status": "completed",
                "scenarios": simulation_scenarios,
                "startedAt": None,
                "completedAt": None,
            }] if simulation_scenarios else [],
            "activeSimulationId": "sim_latest" if simulation_scenarios else None,
            "isSimulating": False,
            "error": None,
        },
        "adaptiveExecution": {
            "missionId": active_execs[0].execution_id if active_execs else None,
            "activeRecoveries": active_recoveries,
            "completedRecoveries": completed_recoveries,
            "failedRecoveries": failed_recoveries,
            "adaptiveMode": True,
            "healthScore": health_score,
            "isHealing": len(active_recoveries) > 0,
        },
        "observation": {
            "categories": observation_categories,
            "metrics": observation_categories[0]["metrics"] if observation_categories else [],
            "alerts": _build_alerts(metrics),
            "isObserving": True,
            "lastUpdate": datetime.now(timezone.utc).isoformat(),
        },
        "decisionMemory": {
            "decisions": decisions,
            "isLoading": False,
            "error": None,
        },
        "runtimeMetrics": {
            "activeExecutions": len(active_execs),
            "completedExecutions": metrics.get("completed_executions", 0),
            "failedExecutions": metrics.get("failed_executions", 0),
            "activeAgents": metrics.get("active_agent_count", 0),
            "totalTokens": metrics.get("total_tokens", 0),
            "avgLatency": metrics.get("average_latency_ms", 0),
            "confidenceScore": metrics.get("average_confidence_score", 0),
            "healthScore": health_score,
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STAGE_REASONING_MAP: Dict[str, str] = {
    "INIT": "goal_analysis",
    "PLANNING": "strategy_formulation",
    "RESEARCHING": "context_evaluation",
    "REASONING": "outcome_projection",
    "VALIDATING": "confidence_assessment",
    "GENERATING": "recommendation",
    "MEMORY_UPDATE": "dependency_mapping",
    "COMPLETED": "recommendation",
}


def _map_stage_to_reasoning_type(stage: str) -> str:
    return _STAGE_REASONING_MAP.get(stage, "context_evaluation")


def _derive_confidence(stage: str, metrics: Dict[str, Any]) -> float:
    base = metrics.get("average_confidence_score", 0) or 0.5
    return min(1.0, base + 0.1)


def _assess_risk(metrics: Dict[str, Any], failed_count: int) -> str:
    if failed_count > 2:
        return "critical"
    if failed_count > 1:
        return "high"
    fail_rate = metrics.get("failed_executions", 0) / max(metrics.get("total_executions", 1), 1)
    if fail_rate > 0.3:
        return "high"
    if fail_rate > 0.1:
        return "medium"
    return "low"


def _compute_health_score(metrics: Dict[str, Any]) -> int:
    fail_rate = metrics.get("failed_executions", 0) / max(metrics.get("total_executions", 1), 1)
    latency = metrics.get("average_latency_ms", 0)
    score = 100
    if fail_rate > 0.3:
        score -= 30
    elif fail_rate > 0.1:
        score -= 15
    if latency > 10000:
        score -= 20
    elif latency > 5000:
        score -= 10
    return max(0, score)


def _build_alerts(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    alerts = []
    if metrics.get("failed_executions", 0) > 5:
        alerts.append({
            "id": "alert_high_failures",
            "severity": "critical",
            "source": "Runtime",
            "message": f"High failure rate: {metrics['failed_executions']} failed executions",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False,
        })
    if metrics.get("average_latency_ms", 0) > 10000:
        alerts.append({
            "id": "alert_high_latency",
            "severity": "warning",
            "source": "Runtime",
            "message": f"High latency: {metrics['average_latency_ms']:.0f}ms average",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False,
        })
    return alerts


def _build_strategies(ctx: Any) -> List[Dict[str, Any]]:
    return [{
        "name": stage_name.replace("_", " ").title(),
        "description": f"Completed {stage_name} phase",
        "confidence": 0.5,
        "risk": "low",
    } for stage_name in ctx.completed_stages]
