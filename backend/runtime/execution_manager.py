from __future__ import annotations

"""
Execution Manager
=================
Bridges the public API to the CognitionPipeline runtime.
Accepts a goal/objective, creates an ExecutionContext, launches
the pipeline, and returns the result.

Also manages:
- Autonomous execution loops (run pipeline repeatedly)
- Execution cancellation
- Execution state queries
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger(__name__)

from backend.orchestration.execution_context import (
    ExecutionContext,
    execution_context_manager,
)
from backend.orchestration.cognition_pipeline import cognition_pipeline
from backend.orchestration.priority_queue import execution_priority_queue
from backend.orchestration.lifecycle_manager import agent_lifecycle_manager
from backend.runtime.runtime_state import runtime_state
from backend.runtime.runtime_state_store import runtime_state_store


# =========================================================
# EXECUTION MANAGER
# =========================================================

class ExecutionManager:
    """
    High-level orchestration entry point.
    All REST API routes call this instead of touching agents directly.
    """

    def __init__(self):
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._loop_active:  bool = False

    # ---------------------------------------------------------
    # LAUNCH EXECUTION
    # ---------------------------------------------------------

    async def launch(
        self,
        objective:           str,
        priority:            int = 5,
        parent_execution_id: Optional[str] = None,
        session_id:          Optional[str] = None,
        stages:              Optional[List[str]] = None,
    ) -> ExecutionContext:
        """
        Create an ExecutionContext and run the full cognition pipeline.
        Returns the completed context.
        """
        ctx = await execution_context_manager.create(
            objective=objective,
            priority=priority,
            parent_execution_id=parent_execution_id,
            session_id=session_id,
        )

        # Track in legacy in-memory runtime state
        runtime_state.start_execution(ctx.execution_id, objective)

        # Track in Redis-backed canonical store
        await runtime_state_store.start(
            execution_id = ctx.execution_id,
            objective    = objective,
            session_id   = session_id,
            mission_type = _classify_mission(objective),
            priority     = priority,
        )

        try:
            ctx = await cognition_pipeline.run(ctx, stages=stages)
        except Exception as exc:
            ctx.status   = "failed"
            ctx.ended_at = datetime.utcnow().isoformat()
            ctx.errors.append(str(exc))
            log.error("Execution %s failed: %s", ctx.execution_id, exc)
            await execution_context_manager.save(ctx)

        # Update legacy runtime state
        if ctx.status == "completed":
            runtime_state.complete_execution(ctx.execution_id)

        # Update canonical Redis store
        await runtime_state_store.complete(
            ctx.execution_id,
            status         = ctx.status,
            final_response = ctx.final_response or "",
            failure_reason = ctx.errors[-1] if ctx.errors else "",
        )

        return ctx

    # ---------------------------------------------------------
    # LAUNCH ASYNC (fire-and-forget, returns immediately)
    # ---------------------------------------------------------

    async def launch_async(
        self,
        objective:           str,
        priority:            int = 5,
        parent_execution_id: Optional[str] = None,
        session_id:          Optional[str] = None,
    ) -> str:
        """
        Enqueue the execution and return the execution_id immediately.
        The pipeline runs in the background.
        """
        # Create context first to get a stable execution_id
        ctx = await execution_context_manager.create(
            objective=objective,
            priority=priority,
            parent_execution_id=parent_execution_id,
            session_id=session_id,
        )

        execution_id = ctx.execution_id

        # Register in Redis-backed store immediately (so state survives restart)
        await runtime_state_store.start(
            execution_id = execution_id,
            objective    = objective,
            session_id   = session_id,
            mission_type = _classify_mission(objective),
            priority     = priority,
        )

        # Push to priority queue
        await execution_priority_queue.push(
            task_id=str(uuid4()),
            execution_id=execution_id,
            agent="orchestrator",
            task_data={"objective": objective},
            priority=priority,
        )

        # Also create and track an asyncio Task
        task = asyncio.create_task(
            self._run_in_background(ctx),
            name=f"execution-{execution_id}",
        )
        self._active_tasks[execution_id] = task
        task.add_done_callback(
            lambda t: self._active_tasks.pop(execution_id, None)
        )

        log.info("🚀 Async execution launched: %s", execution_id)
        return execution_id

    async def _run_in_background(self, ctx: ExecutionContext) -> None:
        try:
            await cognition_pipeline.run(ctx)
            if ctx.status == "completed":
                runtime_state.complete_execution(ctx.execution_id)
            await runtime_state_store.complete(
                ctx.execution_id,
                status         = ctx.status,
                final_response = ctx.final_response or "",
                failure_reason = ctx.errors[-1] if ctx.errors else "",
            )
        except Exception as exc:
            log.error("Background execution %s error: %s", ctx.execution_id, exc)
            try:
                await runtime_state_store.complete(
                    ctx.execution_id,
                    status         = "failed",
                    failure_reason = str(exc),
                )
            except Exception:
                pass

    # ---------------------------------------------------------
    # AUTONOMOUS LOOP
    # ---------------------------------------------------------

    async def start_autonomous_loop(
        self,
        goal:            str,
        max_iterations:  int = 5,
        priority:        int = 5,
    ) -> Dict[str, Any]:
        """
        Runs the cognition pipeline repeatedly for evolving sub-goals,
        building on previous execution results.
        """
        loop_id    = str(uuid4())
        results    = []
        current_goal = goal
        parent_id: Optional[str] = None

        for iteration in range(max_iterations):
            log.info(
                "Autonomous loop %s iteration %d/%d",
                loop_id, iteration + 1, max_iterations,
            )

            ctx = await self.launch(
                objective=current_goal,
                priority=priority,
                parent_execution_id=parent_id,
            )

            results.append({
                "iteration":    iteration + 1,
                "execution_id": ctx.execution_id,
                "objective":    current_goal,
                "status":       ctx.status,
            })

            parent_id = ctx.execution_id

            if ctx.status == "failed":
                log.warning("Autonomous loop stopped — iteration failed")
                break

            # Use reflection result to evolve goal (if available)
            if ctx.reflection_result:
                recs = ctx.reflection_result.get("recommendations", [])
                if recs:
                    current_goal = f"{goal} — incorporating: {recs[0]}"

            # Brief pause between iterations
            await asyncio.sleep(0.1)

        return {
            "loop_id":    loop_id,
            "goal":       goal,
            "iterations": len(results),
            "results":    results,
        }

    # ---------------------------------------------------------
    # CANCEL EXECUTION
    # ---------------------------------------------------------

    async def cancel(self, execution_id: str) -> bool:
        task = self._active_tasks.get(execution_id)
        if task and not task.done():
            task.cancel()
            log.info("Cancelled execution: %s", execution_id)
            return True

        ctx = await execution_context_manager.get(execution_id)
        if ctx:
            ctx.status = "cancelled"
            await execution_context_manager.save(ctx)
            return True

        return False

    # ---------------------------------------------------------
    # QUERY
    # ---------------------------------------------------------

    async def get_execution(
        self, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        ctx = await execution_context_manager.get(execution_id)
        if ctx:
            return ctx.to_dict()
        return None

    async def list_active(self) -> List[Dict[str, Any]]:
        return await execution_context_manager.list_active()

    async def list_all(self) -> List[Dict[str, Any]]:
        return await execution_context_manager.list_all()

    async def queue_snapshot(self) -> List[Dict[str, Any]]:
        return await execution_priority_queue.snapshot()


# =========================================================
# SINGLETON
# =========================================================

execution_manager = ExecutionManager()


# =========================================================
# HELPERS
# =========================================================

def _classify_mission(objective: str) -> str:
    """Classify an objective string into a broad mission_type bucket."""
    obj = objective.lower()
    if any(w in obj for w in ("research", "find", "search", "look up")):
        return "research"
    if any(w in obj for w in ("code", "write", "implement", "build", "create")):
        return "development"
    if any(w in obj for w in ("analyze", "analyse", "review", "evaluate")):
        return "analysis"
    if any(w in obj for w in ("plan", "design", "architect", "outline")):
        return "planning"
    return "general"
