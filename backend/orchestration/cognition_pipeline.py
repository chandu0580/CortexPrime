"""
CortexPrime Cognition Pipeline
==============================

The central orchestration engine that drives every autonomous execution:

    Orchestrator → Planner → Research → Critic → Optimizer → Reflection → Memory

Each stage:
  1. Activates the agent in the lifecycle manager
  2. Emits a start event over the WebSocket + EventBus
  3. Dispatches the agent task (RabbitMQ when available, inline otherwise)
  4. Records a trace span
  5. Persists stage output into the ExecutionContext
  6. Updates Redis pipeline context
  7. Builds the Neo4j cognition-flow edge
  8. Emits a completion event
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent, EventTypes
from backend.orchestration.execution_context import (
    ExecutionContext,
    execution_context_manager,
)
from backend.orchestration.lifecycle_manager import agent_lifecycle_manager
from backend.orchestration.orchestration_tracer import orchestration_tracer

log = logging.getLogger(__name__)


# =========================================================
# COGNITION PIPELINE
# =========================================================

class CognitionPipeline:
    """
    Runs the full Orchestrator → Memory pipeline for a given
    ExecutionContext.  Each stage is an async coroutine that
    writes its output back into the context object.
    """

    # ---------------------------------------------------------
    # EVENT HELPER
    # ---------------------------------------------------------

    async def _emit(
        self,
        agent:        str,
        event_type:   str,
        status:       str,
        message:      str,
        execution_id: str,
        phase:        str = "",
        payload:      Dict[str, Any] = {},
    ) -> None:
        await event_bus.publish(
            CognitionEvent(
                agent=agent,
                event_type=event_type,
                status=status,
                message=message,
                execution_id=execution_id,
                phase=phase,
                payload=payload,
            )
        )

        # Also push to RabbitMQ (fire-and-forget)
        try:
            from backend.infrastructure.rabbitmq.publisher import rabbitmq_publisher
            asyncio.ensure_future(
                rabbitmq_publisher.emit_execution_event(
                    execution_id=execution_id,
                    agent=agent,
                    event_type=event_type,
                    status=status,
                    message=message,
                    payload=payload,
                )
            )
        except Exception:
            pass

    # ---------------------------------------------------------
    # STAGE RUNNER
    # ---------------------------------------------------------

    async def _run_stage(
        self,
        ctx:        ExecutionContext,
        stage:      str,
        agent_name: str,
        task:       Dict[str, Any],
        priority:   int = 5,
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a single pipeline stage.
        Returns the agent result dict, or None on failure.
        """
        span = orchestration_tracer.start_span(
            execution_id=ctx.execution_id,
            agent=agent_name,
            stage=stage,
        )

        ctx.current_stage = stage

        # ── Lifecycle: activate ──────────────────────────────
        await agent_lifecycle_manager.activate(agent_name)

        await self._emit(
            agent=agent_name,
            event_type=f"{agent_name}.{stage}.started",
            status="running",
            message=f"{agent_name.title()} {stage} started…",
            execution_id=ctx.execution_id,
            phase=stage,
            payload={"objective": ctx.objective},
        )

        # ── Record Neo4j flow ────────────────────────────────
        if ctx.completed_stages:
            try:
                from backend.infrastructure.neo4j.graph_manager import neo4j_graph
                asyncio.ensure_future(
                    neo4j_graph.record_cognition_flow(
                        from_agent=ctx.completed_stages[-1].split(".")[-1],
                        to_agent=agent_name,
                        execution_id=ctx.execution_id,
                    )
                )
            except Exception:
                pass

        # ── Execute agent ────────────────────────────────────
        result: Optional[Dict[str, Any]] = None
        error:  Optional[str] = None

        try:
            from backend.runtime.agent_registry import agent_registry
            agent = agent_registry.get_agent(agent_name)

            if agent:
                result = await agent.execute(task)
            else:
                # Agent not in registry — attempt inline fallback
                result = await self._inline_fallback(agent_name, task)

        except Exception as exc:
            error = str(exc)
            log.error("Stage %s failed: %s", stage, exc)

        # ── Lifecycle: deactivate ────────────────────────────
        if error:
            await agent_lifecycle_manager.fail(agent_name, error)
            orchestration_tracer.finish_span(span, status="failed", error=error)
            ctx.mark_stage_failed(stage, error)

            await self._emit(
                agent=agent_name,
                event_type=f"{agent_name}.{stage}.failed",
                status="failed",
                message=f"{agent_name.title()} {stage} failed: {error}",
                execution_id=ctx.execution_id,
                phase=stage,
                payload={"error": error},
            )
        else:
            await agent_lifecycle_manager.deactivate(agent_name)
            orchestration_tracer.finish_span(span, status="completed")
            ctx.mark_stage_complete(stage)
            ctx.record_stage_timing(stage, span.duration_ms or 0)

            # ── Neo4j record agent execution ─────────────────
            try:
                from backend.infrastructure.neo4j.graph_manager import neo4j_graph
                asyncio.ensure_future(
                    neo4j_graph.record_agent_execution(
                        execution_id=ctx.execution_id,
                        agent_name=agent_name,
                        stage=stage,
                        duration_ms=span.duration_ms,
                    )
                )
            except Exception:
                pass

            await self._emit(
                agent=agent_name,
                event_type=f"{agent_name}.{stage}.completed",
                status="completed",
                message=f"{agent_name.title()} {stage} completed",
                execution_id=ctx.execution_id,
                phase=stage,
                payload=result or {},
            )

        # ── Persist context to Redis ─────────────────────────
        await execution_context_manager.save(ctx)

        return result

    # ---------------------------------------------------------
    # INLINE FALLBACK (when agent not registered)
    # ---------------------------------------------------------

    async def _inline_fallback(
        self,
        agent_name: str,
        task:       Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Lightweight inline execution when an agent class is not registered.
        Uses the LLM gateway directly.
        """
        objective = (
            task.get("objective")
            or task.get("query")
            or task.get("content")
            or task.get("response")
            or "No objective provided"
        )

        try:
            from backend.llm.llm_gateway import llm_gateway
            response = await llm_gateway.complete(
                prompt=f"You are the {agent_name} agent. Perform your role for: {objective}",
                system=f"You are {agent_name}, a specialized AI agent in the CortexPrime cognitive runtime.",
                max_tokens=500,
            )
            return {
                "agent":    agent_name,
                "status":   "completed",
                "response": response.get("content", ""),
                "fallback": True,
            }
        except Exception as exc:
            return {
                "agent":  agent_name,
                "status": "completed",
                "note":   f"inline fallback without LLM: {exc}",
            }

    # =========================================================
    # PIPELINE STAGES
    # =========================================================

    # ---------------------------------------------------------
    # STAGE 1: PLANNER
    # ---------------------------------------------------------

    async def stage_planner(self, ctx: ExecutionContext) -> None:
        result = await self._run_stage(
            ctx=ctx,
            stage="planning",
            agent_name="planner",
            task={"objective": ctx.objective},
            priority=3,
        )
        ctx.plan = result

    # ---------------------------------------------------------
    # STAGE 2: RESEARCH
    # ---------------------------------------------------------

    async def stage_research(self, ctx: ExecutionContext) -> None:
        result = await self._run_stage(
            ctx=ctx,
            stage="research",
            agent_name="research",
            task={
                "query":     ctx.objective,
                "objective": ctx.objective,
                "plan":      ctx.plan,
            },
            priority=5,
        )
        ctx.research_result = result

    # ---------------------------------------------------------
    # STAGE 3: CRITIC
    # ---------------------------------------------------------

    async def stage_critic(self, ctx: ExecutionContext) -> None:
        response_text = ""
        if ctx.research_result:
            response_text = (
                ctx.research_result.get("synthesis")
                or ctx.research_result.get("response")
                or str(ctx.research_result)
            )

        result = await self._run_stage(
            ctx=ctx,
            stage="critique",
            agent_name="critic",
            task={
                "response":  response_text,
                "objective": ctx.objective,
                "plan":      ctx.plan,
            },
            priority=5,
        )
        ctx.critic_result = result

    # ---------------------------------------------------------
    # STAGE 4: OPTIMIZER
    # ---------------------------------------------------------

    async def stage_optimizer(self, ctx: ExecutionContext) -> None:
        content = ""
        if ctx.research_result:
            content = (
                ctx.research_result.get("synthesis")
                or ctx.research_result.get("response")
                or ""
            )

        result = await self._run_stage(
            ctx=ctx,
            stage="optimization",
            agent_name="optimizer",
            task={
                "content":      content,
                "objective":    ctx.objective,
                "critic_notes": ctx.critic_result,
            },
            priority=5,
        )
        ctx.optimizer_result = result

    # ---------------------------------------------------------
    # STAGE 5: REFLECTION
    # ---------------------------------------------------------

    async def stage_reflection(self, ctx: ExecutionContext) -> None:
        result = await self._run_stage(
            ctx=ctx,
            stage="reflection",
            agent_name="reflection",
            task={
                "execution_id":    ctx.execution_id,
                "objective":       ctx.objective,
                "plan":            ctx.plan,
                "research_result": ctx.research_result,
                "critic_result":   ctx.critic_result,
                "optimizer_result": ctx.optimizer_result,
                "completed_stages": ctx.completed_stages,
                "stage_timings":   ctx.stage_timings,
            },
            priority=7,
        )
        ctx.reflection_result = result

    # ---------------------------------------------------------
    # STAGE 6: MEMORY
    # ---------------------------------------------------------

    async def stage_memory(self, ctx: ExecutionContext) -> None:
        final_content = (
            (ctx.optimizer_result or {}).get("optimized_response")
            or (ctx.optimizer_result or {}).get("response")
            or (ctx.research_result or {}).get("synthesis")
            or ctx.objective
        )

        result = await self._run_stage(
            ctx=ctx,
            stage="memory_storage",
            agent_name="memory",
            task={
                "content":         final_content,
                "objective":       ctx.objective,
                "execution_id":    ctx.execution_id,
                "execution_trace": ctx.to_dict(),
            },
            priority=7,
        )
        ctx.memory_result = result

    # ---------------------------------------------------------
    # BUILD FINAL RESPONSE
    # ---------------------------------------------------------

    def _build_final_response(self, ctx: ExecutionContext) -> str:
        # Try to extract the most useful text from stage outputs
        if ctx.optimizer_result:
            for key in ("optimized_response", "response", "result", "content"):
                val = ctx.optimizer_result.get(key)
                if val and isinstance(val, str):
                    return val

        if ctx.research_result:
            for key in ("synthesis", "response", "result", "content"):
                val = ctx.research_result.get(key)
                if val and isinstance(val, str):
                    return val

        if ctx.plan:
            for key in ("plan_summary", "response", "result"):
                val = ctx.plan.get(key)
                if val and isinstance(val, str):
                    return val

        return f"Execution completed for: {ctx.objective}"

    # =========================================================
    # MAIN ENTRY POINT
    # =========================================================

    async def run(
        self,
        ctx:        ExecutionContext,
        stages:     Optional[List[str]] = None,
    ) -> ExecutionContext:
        """
        Run the full (or partial) cognition pipeline for an ExecutionContext.

        stages: optional list of stage names to run (default = all)
        """
        ctx.status = "running"

        await execution_context_manager.save(ctx)

        # ── Neo4j: create execution node ─────────────────────
        try:
            from backend.infrastructure.neo4j.graph_manager import neo4j_graph
            asyncio.ensure_future(
                neo4j_graph.create_execution(
                    execution_id=ctx.execution_id,
                    objective=ctx.objective,
                    priority=ctx.priority,
                    parent_execution_id=ctx.parent_execution_id,
                )
            )
        except Exception:
            pass

        # ── Redis: mark execution active ─────────────────────
        try:
            from backend.infrastructure.redis.runtime_cache import redis_cache
            await redis_cache.set_execution_state(
                ctx.execution_id,
                ctx.to_dict(),
            )
        except Exception:
            pass

        # ── ORCHESTRATOR start event ─────────────────────────
        await self._emit(
            agent="orchestrator",
            event_type=EventTypes.ORCHESTRATION_STARTED,
            status="running",
            message=f"Orchestrator activated for: {ctx.objective}",
            execution_id=ctx.execution_id,
            phase="orchestrating",
            payload={"objective": ctx.objective, "priority": ctx.priority},
        )

        all_stages = [
            ("planning",   self.stage_planner),
            ("research",   self.stage_research),
            ("critique",   self.stage_critic),
            ("optimization", self.stage_optimizer),
            ("reflection", self.stage_reflection),
            ("memory_storage", self.stage_memory),
        ]

        run_stages = all_stages
        if stages:
            run_stages = [(n, fn) for n, fn in all_stages if n in stages]

        for stage_name, stage_fn in run_stages:
            if ctx.status == "failed" and not ctx.should_retry():
                break
            try:
                await stage_fn(ctx)
            except Exception as exc:
                log.error("Pipeline stage %s unhandled exception: %s", stage_name, exc)
                ctx.mark_stage_failed(stage_name, str(exc))

        # ── Build final response ─────────────────────────────
        ctx.final_response = self._build_final_response(ctx)

        # ── Close out ────────────────────────────────────────
        if ctx.failed_stages and not ctx.completed_stages:
            ctx.status = "failed"
        else:
            ctx.status = "completed"

        ctx.ended_at = datetime.utcnow().isoformat()

        await execution_context_manager.save(ctx)

        # ── Tracer persist ───────────────────────────────────
        asyncio.ensure_future(
            orchestration_tracer.persist(ctx.execution_id)
        )

        # ── Neo4j: complete execution ─────────────────────────
        try:
            from backend.infrastructure.neo4j.graph_manager import neo4j_graph
            asyncio.ensure_future(
                neo4j_graph.complete_execution(ctx.execution_id, ctx.status)
            )
        except Exception:
            pass

        # ── Redis: clear active state ─────────────────────────
        try:
            from backend.infrastructure.redis.runtime_cache import redis_cache
            await redis_cache.delete_execution_state(ctx.execution_id)
        except Exception:
            pass

        # ── Final event ──────────────────────────────────────
        await self._emit(
            agent="orchestrator",
            event_type=(
                EventTypes.ORCHESTRATION_COMPLETED
                if ctx.status == "completed"
                else EventTypes.ORCHESTRATION_FAILED
            ),
            status=ctx.status,
            message=(
                f"Execution {ctx.status}: {ctx.objective}"
            ),
            execution_id=ctx.execution_id,
            phase="complete",
            payload={
                "execution_id":      ctx.execution_id,
                "completed_stages":  ctx.completed_stages,
                "failed_stages":     ctx.failed_stages,
                "stage_timings":     ctx.stage_timings,
                "final_response":    ctx.final_response,
            },
        )

        return ctx


# =========================================================
# SINGLETON
# =========================================================

cognition_pipeline = CognitionPipeline()
