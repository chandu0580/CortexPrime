from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from backend.agents.base import (
    AgentContext,
    AgentResult,
    AgentStatus,
    AgentTask,
    BaseAgent,
    CollaborationMode,
    TaskPriority,
)
from backend.agents.registry import AgentRegistry, agent_registry
from backend.agents.shared_memory import CognitiveMemoryBridge, cognitive_memory_bridge

log = logging.getLogger(__name__)


VoteFn = Callable[[List[AgentResult]], AgentResult]


class AgentCoordinator:
    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        memory: Optional[CognitiveMemoryBridge] = None,
    ) -> None:
        self._registry = registry or agent_registry
        self._memory = memory or cognitive_memory_bridge
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._voting_hooks: Dict[str, VoteFn] = {}

    def register_voting_hook(self, name: str, fn: VoteFn) -> None:
        self._voting_hooks[name] = fn

    async def run_mission(
        self,
        goal: str,
        tasks: List[AgentTask],
        ctx: AgentContext,
        mode: CollaborationMode = CollaborationMode.DEPENDENCY,
    ) -> List[AgentResult]:
        self._memory.ensure_context(ctx.mission_id, {
            "user_id": ctx.user_id, "tenant_id": ctx.tenant_id,
            "trace_id": ctx.trace_id, "correlation_id": ctx.correlation_id,
            "goal": goal, "name": f"multi_agent_{ctx.mission_id}",
            "category": "multi_agent",
        })
        session = {
            "goal": goal,
            "ctx": ctx,
            "mode": mode,
            "tasks": {t.task_id: t for t in tasks},
            "results": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self._active_sessions[ctx.mission_id] = session

        self._memory.add_reasoning_step(
            ctx.mission_id, "coordinator",
            f"Mission started: {goal}",
            decision=f"mode={mode.value}, tasks={len(tasks)}",
            critical=False,
        )

        if mode == CollaborationMode.SEQUENTIAL:
            results = await self._run_sequential(tasks, ctx)
        elif mode == CollaborationMode.PARALLEL:
            results = await self._run_parallel(tasks, ctx)
        elif mode == CollaborationMode.VOTING:
            results = await self._run_voting(tasks, ctx)
        else:
            results = await self._run_dependency(tasks, ctx)

        session["results"] = {r.task_id: r for r in results}
        session["completed_at"] = datetime.now(timezone.utc).isoformat()

        self._memory.add_reasoning_step(
            ctx.mission_id, "coordinator",
            f"Mission completed: {sum(1 for r in results if r.success)}/{len(results)} tasks succeeded",
            decision=f"completed",
            critical=False,
        )
        return results

    async def _run_sequential(self, tasks: List[AgentTask], ctx: AgentContext) -> List[AgentResult]:
        results: List[AgentResult] = []
        for task in tasks:
            result = await self._execute_with_retry(task, ctx)
            results.append(result)
            if not result.success:
                if not await self._handle_failure(task, result, ctx, results):
                    break
        return results

    async def _run_parallel(self, tasks: List[AgentTask], ctx: AgentContext) -> List[AgentResult]:
        coros = [self._execute_with_retry(task, ctx) for task in tasks]
        return await asyncio.gather(*coros)

    async def _run_dependency(self, tasks: List[AgentTask], ctx: AgentContext) -> List[AgentResult]:
        task_map = {t.task_id: t for t in tasks}
        in_degree: Dict[str, int] = {}
        dependents: Dict[str, List[str]] = defaultdict(list)
        for t in tasks:
            in_degree[t.task_id] = len(t.dependencies)
            for dep_id in t.dependencies:
                dependents[dep_id].append(t.task_id)

        queue: deque[str] = deque(t for t, d in in_degree.items() if d == 0)
        results: Dict[str, AgentResult] = {}
        pending: Dict[str, asyncio.Task] = {}

        async def run_and_collect(tid: str) -> AgentResult:
            task = task_map[tid]
            result = await self._execute_with_retry(task, ctx)
            results[tid] = result
            for child in dependents.get(tid, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
            return result

        while queue:
            batch = list(queue)
            queue.clear()
            batch_coros = [run_and_collect(tid) for tid in batch]
            await asyncio.gather(*batch_coros)

        return [results[t.task_id] for t in tasks if t.task_id in results]

    async def _run_voting(self, tasks: List[AgentTask], ctx: AgentContext) -> List[AgentResult]:
        results: List[AgentResult] = []
        for task in tasks:
            agents = self._registry.find_by_capability(task.description) or self._registry.get_by_type(task.agent_type)
            if not agents:
                results.append(AgentResult(
                    task_id=task.task_id, agent_id="", agent_type="",
                    success=False, error="No agents available for voting",
                ))
                continue
            coros = []
            for agent in agents[:5]:
                sub_task = AgentTask(
                    task_id=f"{task.task_id}_{agent.agent_id}",
                    agent_type=agent.agent_type,
                    description=task.description,
                    input_data=dict(task.input_data),
                    timeout_seconds=task.timeout_seconds,
                    metadata={"parent_task": task.task_id, "vote": True},
                )
                coros.append(self._execute_with_retry(sub_task, ctx, force_agent=agent))
            vote_results = await asyncio.gather(*coros)
            merged = self._merge_votes(vote_results, task.task_id)
            results.append(merged)
        return results

    def _merge_votes(self, vote_results: List[AgentResult], task_id: str) -> AgentResult:
        hook_name = f"vote_{task_id}"
        if hook_name in self._voting_hooks:
            return self._voting_hooks[hook_name](vote_results)
        successes = [r for r in vote_results if r.success]
        if not successes:
            return AgentResult(
                task_id=task_id, agent_id="coordinator", agent_type="coordinator",
                success=False, error=f"All {len(vote_results)} votes failed",
                voting_results={"total": len(vote_results), "successful": 0, "votes": [r.error for r in vote_results]},
            )
        majority = len(successes) > len(vote_results) / 2
        primary = successes[0]
        return AgentResult(
            task_id=task_id, agent_id=primary.agent_id, agent_type=primary.agent_type,
            success=majority, output_data=primary.output_data,
            voting_results={
                "total": len(vote_results), "successful": len(successes),
                "majority": majority, "votes": [
                    {"agent": r.agent_type, "success": r.success, "error": r.error}
                    for r in vote_results
                ],
            },
        )

    async def _execute_with_retry(
        self, task: AgentTask, ctx: AgentContext,
        force_agent: Optional[BaseAgent] = None,
    ) -> AgentResult:
        agent = force_agent or self._registry.assign(task)
        if not agent:
            return AgentResult(
                task_id=task.task_id, agent_id="", agent_type="",
                success=False, error=f"No available agent for task: {task.description}",
            )
        task.assigned_agent = agent.agent_id
        task.status = AgentStatus.RUNNING

        agent_ctx = AgentContext(
            mission_id=ctx.mission_id,
            agent_id=agent.agent_id,
            agent_type=agent.agent_type,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            trace_id=ctx.trace_id,
            correlation_id=ctx.correlation_id,
            permissions=list(ctx.permissions),
        )

        self._memory.add_reasoning_step(
            ctx.mission_id, agent.agent_type,
            f"Task assigned: {task.description[:80]}",
            decision=f"task_id={task.task_id}", critical=False,
        )

        last_error = ""
        for attempt in range(task.max_retries + 1):
            try:
                if task.timeout_seconds > 0:
                    result = await asyncio.wait_for(
                        agent.execute(task, agent_ctx), timeout=task.timeout_seconds,
                    )
                else:
                    result = await agent.execute(task, agent_ctx)
            except asyncio.TimeoutError:
                last_error = f"Timeout after {task.timeout_seconds}s"
                result = AgentResult(
                    task_id=task.task_id, agent_id=agent.agent_id,
                    agent_type=agent.agent_type, success=False,
                    error=last_error,
                )
            except Exception as exc:
                last_error = str(exc)
                result = AgentResult(
                    task_id=task.task_id, agent_id=agent.agent_id,
                    agent_type=agent.agent_type, success=False,
                    error=last_error,
                )

            if result.success:
                task.status = AgentStatus.COMPLETED
                self._memory.add_reasoning_step(
                    ctx.mission_id, agent.agent_type,
                    f"Task completed: {task.description[:80]}",
                    decision=f"success", confidence=1.0, critical=False,
                )
                if result.output_data:
                    self._memory.add_artifact(
                        ctx.mission_id, agent.agent_type,
                        name=f"{task.task_id}_output",
                        artifact_type="task_result",
                        data=result.output_data,
                    )
                agent._result_history.append(result)
                return result

            last_error = result.error
            log.info("Attempt %d/%d failed for %s: %s",
                      attempt + 1, task.max_retries + 1, task.task_id, last_error)
            if attempt < task.max_retries:
                self._memory.add_reasoning_step(
                    ctx.mission_id, agent.agent_type,
                    f"Retry {attempt + 1}/{task.max_retries} for {task.description[:60]}",
                    decision=f"retry", confidence=0.0, critical=True,
                )

        task.status = AgentStatus.FAILED
        agent.status = AgentStatus.FAILED
        self._memory.add_reasoning_step(
            ctx.mission_id, agent.agent_type,
            f"Task failed after {task.max_retries + 1} attempts: {task.description[:60]}",
            decision=f"failed: {last_error}", confidence=0.0, critical=True,
        )

        if task.escalation_agent:
            return await self._escalate(task, ctx, last_error)
        return AgentResult(
            task_id=task.task_id, agent_id=agent.agent_id,
            agent_type=agent.agent_type, success=False,
            error=last_error,
            delegation_chain=[agent.agent_id],
        )

    async def _handle_failure(self, task: AgentTask, result: AgentResult,
                              ctx: AgentContext, all_results: List[AgentResult]) -> bool:
        if task.escalation_agent:
            replacement = await self._escalate(task, ctx, result.error)
            all_results.append(replacement)
            return replacement.success
        return False

    async def _escalate(self, task: AgentTask, ctx: AgentContext, error: str) -> AgentResult:
        escalation_agents = self._registry.get_by_type(task.escalation_agent)
        if not escalation_agents:
            return AgentResult(
                task_id=task.task_id, agent_id="", agent_type="",
                success=False, error=f"Escalation agent {task.escalation_agent} not found. Original error: {error}",
            )
        agent = escalation_agents[0]
        agent.status = type(agent.status).ASSIGNED
        task.assigned_agent = agent.agent_id
        task.status = AgentStatus.RUNNING

        self._memory.add_reasoning_step(
            ctx.mission_id, agent.agent_type,
            f"Escalated: {task.description[:60]}",
            decision=f"escalated_from={task.escalation_agent}", critical=True,
        )

        agent_ctx = AgentContext(
            mission_id=ctx.mission_id, agent_id=agent.agent_id,
            agent_type=agent.agent_type, tenant_id=ctx.tenant_id,
            user_id=ctx.user_id, trace_id=ctx.trace_id,
            correlation_id=ctx.correlation_id,
        )
        result = await agent.execute(task, agent_ctx)
        result.delegation_chain = [task.escalation_agent, agent.agent_id]
        return result

    async def delegate(self, task: AgentTask, ctx: AgentContext,
                       target_agent_type: str) -> AgentResult:
        task.agent_type = target_agent_type
        return await self._execute_with_retry(task, ctx)

    def get_session(self, mission_id: str) -> Optional[Dict[str, Any]]:
        return self._active_sessions.get(mission_id)

    def get_agent_history(self, agent_id: str) -> List[AgentResult]:
        agent = self._registry.get(agent_id)
        if agent:
            return list(agent._result_history)
        return []

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "active_sessions": len(self._active_sessions),
            "registered_agents": self._registry.agent_count,
        }


coordinator = AgentCoordinator()
