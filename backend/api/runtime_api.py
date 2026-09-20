"""
CortexPrime Runtime API Routes
================================
All orchestration, execution, and runtime management endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from backend.api.legacy_execution_boundary import guard_legacy_execution
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_user
from backend.orchestration.lifecycle_manager import agent_lifecycle_manager
from backend.orchestration.orchestration_tracer import orchestration_tracer
from backend.orchestration.priority_queue import execution_priority_queue
from backend.orchestration.task_decomposer import task_decomposer
from backend.runtime.agent_registry import agent_registry
from backend.runtime.execution_manager import execution_manager

router = APIRouter(prefix="/api/runtime", tags=["Runtime"], dependencies=[Depends(require_user)])


# =========================================================
# REQUEST MODELS
# =========================================================

class ExecuteRequest(BaseModel):
    objective:  str  = Field(..., description="The mission objective")
    priority:   int  = Field(5, ge=1, le=10, description="Priority 1=highest 10=lowest")
    async_mode: bool = Field(False, description="Fire-and-forget mode")
    stages:     Optional[List[str]] = Field(
        None,
        description="Optional list of stages to run (omit for all)",
    )
    session_id: Optional[str] = None


class AutonomousLoopRequest(BaseModel):
    goal:           str = Field(..., description="Overarching goal for the autonomous loop")
    max_iterations: int = Field(3, ge=1, le=10)
    priority:       int = Field(5, ge=1, le=10)


class DecomposeRequest(BaseModel):
    objective: str
    priority:  int = 5
    use_llm:   bool = False


# =========================================================
# EXECUTE MISSION
# =========================================================

@router.post(
    "/execute",
    # V1 strangler boundary (ADR-039). Privileged, and bypasses the
    # invocation gateway entirely. Disabled unless the migration flag is set.
    dependencies=[Depends(guard_legacy_execution("POST /api/runtime/execute"))],
)
async def execute_mission(request: ExecuteRequest) -> Dict[str, Any]:
    """
    Launch a full cognition pipeline execution for the given objective.

    - async_mode=false → waits for pipeline to complete, returns full result
    - async_mode=true  → returns execution_id immediately, pipeline runs in background
    """
    if request.async_mode:
        execution_id = await execution_manager.launch_async(
            objective=request.objective,
            priority=request.priority,
            session_id=request.session_id,
        )
        return {
            "accepted":     True,
            "execution_id": execution_id,
            "status":       "queued",
            "message":      f"Execution queued: {execution_id}",
        }

    ctx = await execution_manager.launch(
        objective=request.objective,
        priority=request.priority,
        session_id=request.session_id,
        stages=request.stages,
    )

    return {
        "execution_id":     ctx.execution_id,
        "status":           ctx.status,
        "objective":        ctx.objective,
        "completed_stages": ctx.completed_stages,
        "failed_stages":    ctx.failed_stages,
        "stage_timings":    ctx.stage_timings,
        "final_response":   ctx.final_response,
        "errors":           ctx.errors,
        "started_at":       ctx.started_at,
        "ended_at":         ctx.ended_at,
    }


# =========================================================
# AUTONOMOUS LOOP
# =========================================================

@router.post(
    "/autonomous-loop",
    # Audit S-1/S-2 (Phase 11.1-K): a V1 surface that reaches an external
    # write or an ungoverned model/tool loop; quarantined like its siblings.
    dependencies=[Depends(guard_legacy_execution("POST /api/runtime/autonomous-loop"))],
)
async def start_autonomous_loop(
    request: AutonomousLoopRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Start an autonomous cognition loop that iterates over sub-goals,
    building on previous execution results using reflection-driven adaptation.
    """
    # Run synchronously for small iterations, async for longer ones
    if request.max_iterations <= 2:
        result = await execution_manager.start_autonomous_loop(
            goal=request.goal,
            max_iterations=request.max_iterations,
            priority=request.priority,
        )
        return result

    # Async loop for longer runs
    loop_id = f"loop-{request.goal[:20].replace(' ', '-')}"
    background_tasks.add_task(
        execution_manager.start_autonomous_loop,
        goal=request.goal,
        max_iterations=request.max_iterations,
        priority=request.priority,
    )
    return {
        "accepted":   True,
        "loop_id":    loop_id,
        "goal":       request.goal,
        "iterations": request.max_iterations,
        "status":     "started",
    }


# =========================================================
# EXECUTION STATE
# =========================================================

@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str) -> Dict[str, Any]:
    """Get full state of a specific execution."""
    result = await execution_manager.get_execution(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


@router.get("/executions")
async def list_executions(
    active_only: bool = Query(False, description="Return only active executions"),
) -> Dict[str, Any]:
    """List executions (all or active only)."""
    if active_only:
        executions = await execution_manager.list_active()
    else:
        executions = await execution_manager.list_all()
    return {"executions": executions, "count": len(executions)}


@router.delete("/executions/{execution_id}")
async def cancel_execution(execution_id: str) -> Dict[str, Any]:
    """Cancel a running execution."""
    cancelled = await execution_manager.cancel(execution_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"execution_id": execution_id, "cancelled": True}


# =========================================================
# PRIORITY QUEUE
# =========================================================

@router.get("/queue")
async def get_queue() -> Dict[str, Any]:
    """Snapshot of the current execution priority queue."""
    tasks = await execution_priority_queue.snapshot()
    return {
        "queued_tasks": tasks,
        "queue_size":   execution_priority_queue.size,
    }


# =========================================================
# AGENT REGISTRY
# =========================================================

@router.get("/agents")
async def get_agents() -> Dict[str, Any]:
    """All registered agents with their metadata and lifecycle status."""
    registry_meta = agent_registry.get_all_metadata()
    lifecycle_info = agent_lifecycle_manager.list_all()

    # Merge lifecycle into registry metadata
    lifecycle_by_name = {r["agent_name"]: r for r in lifecycle_info}
    merged = {}
    for name, meta in registry_meta.items():
        merged[name] = {**meta, **lifecycle_by_name.get(name, {})}

    return {
        "agents":        merged,
        "total":         len(merged),
        "active_agents": agent_lifecycle_manager.list_active(),
    }


# =========================================================
# TRACES
# =========================================================

@router.get("/traces/{execution_id}")
async def get_trace(execution_id: str) -> Dict[str, Any]:
    """Execution trace (all spans) for a specific execution."""
    trace   = orchestration_tracer.get_trace(execution_id)
    summary = orchestration_tracer.summary(execution_id)
    return {"execution_id": execution_id, "spans": trace, "summary": summary}


# =========================================================
# TASK DECOMPOSITION
# =========================================================

@router.post("/decompose")
async def decompose_task(request: DecomposeRequest) -> Dict[str, Any]:
    """
    Decompose an objective into pipeline sub-tasks without executing them.
    Useful for previewing the planned execution before launching.
    """
    from uuid import uuid4
    preview_id = str(uuid4())

    tasks = await task_decomposer.decompose(
        execution_id=preview_id,
        objective=request.objective,
        priority=request.priority,
        use_llm=request.use_llm,
    )

    return {
        "preview_execution_id": preview_id,
        "objective":            request.objective,
        "tasks":                [t.to_dict() for t in tasks],
        "stage_count":          len(tasks),
    }


# =========================================================
# INFRASTRUCTURE STATUS
# =========================================================

@router.get("/infrastructure")
async def infrastructure_status() -> Dict[str, Any]:
    """Live status of all infrastructure components."""
    status: Dict[str, Any] = {}

    # RabbitMQ
    try:
        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
        status["rabbitmq"] = {
            "available": rabbitmq_connection.is_available,
            "status":    "connected" if rabbitmq_connection.is_available else "disconnected",
        }
    except Exception:
        status["rabbitmq"] = {"available": False, "status": "error"}

    # Redis
    try:
        from backend.infrastructure.redis.connection import redis_connection
        status["redis"] = {
            "available": redis_connection.is_available,
            "status":    "connected" if redis_connection.is_available else "disconnected",
        }
    except Exception:
        status["redis"] = {"available": False, "status": "error"}

    # Neo4j
    try:
        from backend.infrastructure.neo4j.connection import neo4j_connection
        status["neo4j"] = {
            "available": neo4j_connection.is_available,
            "status":    "connected" if neo4j_connection.is_available else "disconnected",
        }
    except Exception:
        status["neo4j"] = {"available": False, "status": "error"}

    status["event_bus"]      = "active"
    status["websocket"]      = "active"
    status["agent_registry"] = len(agent_registry.list_agents())

    return status


# =========================================================
# COGNITION GRAPH (Neo4j)
# =========================================================

@router.get("/cognition-graph")
async def cognition_graph() -> Dict[str, Any]:
    """Agent cognition relationship graph from Neo4j."""
    try:
        from backend.infrastructure.neo4j.graph_manager import neo4j_graph
        return await neo4j_graph.get_agent_graph()
    except Exception as exc:
        return {
            "agents": [],
            "edges":  [],
            "note":   f"Neo4j unavailable: {exc}",
        }
