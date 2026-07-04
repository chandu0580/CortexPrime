"""
Telemetry API
=============
Exposes real-time runtime metrics and execution history.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from backend.auth.dependencies import require_user
from backend.runtime.runtime_state import runtime_state

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"], dependencies=[Depends(require_user)])


# =========================================================
# GET /api/telemetry/runtime
# =========================================================

@router.get("/runtime")
async def get_runtime_metrics() -> Dict[str, Any]:
    """Return current runtime state: active executions, agent states, history."""
    state = runtime_state.get_state()

    active: Dict[str, Any] = state.get("active_executions", {})
    agents: Dict[str, Any] = state.get("agent_states", {})
    history: List[Any]     = state.get("execution_history", [])

    # Derive summary stats
    completed = [e for e in history if isinstance(e, dict) and e.get("status") == "completed"]
    failed    = [e for e in history if isinstance(e, dict) and e.get("status") == "failed"]

    return {
        "timestamp":          datetime.now(timezone.utc).isoformat(),
        "active_executions":  len(active),
        "active_agents":      sum(1 for s in agents.values() if s == "running"),
        "total_completed":    len(completed),
        "total_failed":       len(failed),
        "agents":             agents,
        "recent_executions":  history[-20:],   # last 20
        "queue_depth":        len(active),
    }


# =========================================================
# GET /api/telemetry/health
# =========================================================

@router.get("/health")
async def get_telemetry_health() -> Dict[str, Any]:
    """Lightweight health endpoint for monitoring."""
    return {
        "status":    "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
