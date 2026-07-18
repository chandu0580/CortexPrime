from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from backend.agents.base import AgentContext, AgentStatus, AgentTask, CollaborationMode, TaskPriority
from backend.agents.coordinator import coordinator
from backend.agents.models import DelegateRequest, RunMissionRequest
from backend.agents.registry import agent_registry

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["Multi-Agent"])


@router.post("/run")
async def run_mission(body: Dict[str, Any]):
    goal = body.get("goal", "")
    if not goal:
        return {"status": "error", "detail": "goal is required"}
    req = RunMissionRequest(
        goal=goal,
        mission_id=body.get("mission_id", ""),
        tenant_id=body.get("tenant_id", ""),
        user_id=body.get("user_id", ""),
        permissions=body.get("permissions"),
        tasks=body.get("tasks", []),
        mode=body.get("mode", "dependency"),
        metadata=body.get("metadata"),
    )
    mode_map = {
        "sequential": CollaborationMode.SEQUENTIAL,
        "parallel": CollaborationMode.PARALLEL,
        "dependency": CollaborationMode.DEPENDENCY,
        "voting": CollaborationMode.VOTING,
    }
    mode = mode_map.get(req.mode, CollaborationMode.DEPENDENCY)

    ctx = AgentContext(
        mission_id=req.mission_id,
        tenant_id=req.tenant_id,
        user_id=req.user_id,
        permissions=list(req.permissions),
        metadata=dict(req.metadata or {}),
    )

    tasks = []
    for t in req.tasks:
        tasks.append(AgentTask(
            task_id=t.get("task_id", ""),
            agent_type=t.get("agent_type", ""),
            description=t.get("description", ""),
            input_data=t.get("input_data", {}),
            dependencies=t.get("dependencies", []),
            timeout_seconds=t.get("timeout_seconds", 300),
            max_retries=t.get("max_retries", 2),
            escalation_agent=t.get("escalation_agent", ""),
            priority=TaskPriority(t.get("priority", 1)),
        ))

    results = await coordinator.run_mission(goal, tasks, ctx, mode=mode)
    return {
        "mission_id": req.mission_id,
        "goal": goal,
        "mode": mode.value,
        "task_count": len(tasks),
        "results": [
            {
                "task_id": r.task_id,
                "agent_id": r.agent_id,
                "agent_type": r.agent_type,
                "success": r.success,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
                "voting_results": r.voting_results,
                "delegation_chain": r.delegation_chain,
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
        },
    }


@router.post("/delegate")
async def delegate_task(body: Dict[str, Any]):
    req = DelegateRequest(
        mission_id=body.get("mission_id", ""),
        task_id=body.get("task_id", ""),
        description=body.get("description", ""),
        target_agent_type=body.get("target_agent_type", ""),
        input_data=body.get("input_data", {}),
        tenant_id=body.get("tenant_id", ""),
        user_id=body.get("user_id", ""),
    )
    if not req.mission_id or not req.target_agent_type:
        return {"status": "error", "detail": "mission_id and target_agent_type are required"}

    task = AgentTask(
        task_id=req.task_id,
        description=req.description,
        input_data=req.input_data,
    )
    ctx = AgentContext(
        mission_id=req.mission_id,
        tenant_id=req.tenant_id,
        user_id=req.user_id,
    )
    result = await coordinator.delegate(task, ctx, req.target_agent_type)
    return {
        "task_id": result.task_id,
        "agent_id": result.agent_id,
        "agent_type": result.agent_type,
        "success": result.success,
        "error": result.error,
        "output_data": result.output_data,
        "duration_seconds": result.duration_seconds,
        "delegation_chain": result.delegation_chain,
    }


@router.get("/")
async def list_agents():
    return {"agents": agent_registry.list_agents(), "total": agent_registry.agent_count}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    agent = agent_registry.get(agent_id)
    if not agent:
        return {"status": "not_found", "agent_id": agent_id}
    return agent.info


@router.get("/{agent_id}/history")
async def get_agent_history(agent_id: str):
    history = coordinator.get_agent_history(agent_id)
    return {
        "agent_id": agent_id,
        "history": [
            {
                "task_id": r.task_id,
                "agent_type": r.agent_type,
                "success": r.success,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
            }
            for r in history
        ],
        "count": len(history),
    }


@router.get("/health")
async def agents_health():
    return coordinator.health()
