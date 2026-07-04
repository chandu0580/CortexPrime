from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


# =========================================================
# EXECUTION CONTEXT
# =========================================================

@dataclass
class ExecutionContext:
    """
    Immutable execution identity + mutable pipeline state.

    Carries all information through the cognition pipeline:
    Orchestrator → Planner → Research → Critic → Optimizer → Reflection → Memory
    """

    # -------------------------
    # IDENTITY
    # -------------------------
    execution_id:        str = field(default_factory=lambda: str(uuid4()))
    parent_execution_id: Optional[str] = None
    session_id:          Optional[str] = None

    # -------------------------
    # MISSION
    # -------------------------
    objective:     str = ""
    priority:      int = 5          # 1 (highest) – 10 (lowest)
    max_depth:     int = 5          # max recursive reasoning depth
    current_depth: int = 0

    # -------------------------
    # PIPELINE STAGE OUTPUTS
    # -------------------------
    plan:            Optional[Dict[str, Any]] = None
    research_result: Optional[Dict[str, Any]] = None
    critic_result:   Optional[Dict[str, Any]] = None
    optimizer_result: Optional[Dict[str, Any]] = None
    reflection_result: Optional[Dict[str, Any]] = None
    memory_result:   Optional[Dict[str, Any]] = None
    final_response:  Optional[str]            = None

    # -------------------------
    # PIPELINE STATE
    # -------------------------
    current_stage:    str = "initializing"
    completed_stages: List[str] = field(default_factory=list)
    failed_stages:    List[str] = field(default_factory=list)
    stage_timings:    Dict[str, float] = field(default_factory=dict)  # stage → ms

    # -------------------------
    # RETRY
    # -------------------------
    retry_count:      int = 0
    max_retries:      int = 2

    # -------------------------
    # STATUS
    # -------------------------
    status:     str = "pending"      # pending / running / completed / failed
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at:   Optional[str] = None

    # -------------------------
    # ACCUMULATED ERRORS
    # -------------------------
    errors: List[str] = field(default_factory=list)

    # =========================================================
    # HELPERS
    # =========================================================

    def mark_stage_complete(self, stage: str) -> None:
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)

    def mark_stage_failed(self, stage: str, error: str) -> None:
        if stage not in self.failed_stages:
            self.failed_stages.append(stage)
        self.errors.append(f"[{stage}] {error}")

    def record_stage_timing(self, stage: str, duration_ms: float) -> None:
        self.stage_timings[stage] = duration_ms

    def is_complete(self) -> bool:
        return self.status in ("completed", "failed")

    def should_retry(self) -> bool:
        return (
            self.status == "failed"
            and self.retry_count < self.max_retries
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id":         self.execution_id,
            "parent_execution_id":  self.parent_execution_id,
            "session_id":           self.session_id,
            "objective":            self.objective,
            "priority":             self.priority,
            "current_stage":        self.current_stage,
            "completed_stages":     self.completed_stages,
            "failed_stages":        self.failed_stages,
            "stage_timings":        self.stage_timings,
            "retry_count":          self.retry_count,
            "status":               self.status,
            "started_at":           self.started_at,
            "ended_at":             self.ended_at,
            "errors":               self.errors,
            "current_depth":        self.current_depth,
            "final_response":       self.final_response,
        }


# =========================================================
# EXECUTION CONTEXT MANAGER
# =========================================================

class ExecutionContextManager:
    """
    Creates, stores, retrieves, and persists ExecutionContext objects.

    Redis is the canonical store.  The local ``_contexts`` dict is a
    write-through cache — on a cache miss, ``get()`` transparently
    loads from Redis so that state survives backend restarts.
    """

    def __init__(self):
        self._contexts: Dict[str, ExecutionContext] = {}

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    async def create(
        self,
        objective: str,
        priority: int = 5,
        parent_execution_id: Optional[str] = None,
        session_id: Optional[str] = None,
        max_depth: int = 5,
    ) -> ExecutionContext:
        ctx = ExecutionContext(
            objective=objective,
            priority=priority,
            parent_execution_id=parent_execution_id,
            session_id=session_id,
            max_depth=max_depth,
        )
        await self.save(ctx)
        return ctx

    # ---------------------------------------------------------
    # SAVE  (write-through: local dict + Redis)
    # ---------------------------------------------------------

    async def save(self, ctx: ExecutionContext) -> None:
        self._contexts[ctx.execution_id] = ctx

        try:
            from backend.infrastructure.redis.runtime_cache import redis_cache
            await redis_cache.set_pipeline_context(
                ctx.execution_id, ctx.to_dict()
            )
        except Exception:
            pass

        # Also persist to the new canonical runtime_state_store
        try:
            from backend.runtime.runtime_state_store import runtime_state_store
            if ctx.status in ("completed", "failed", "cancelled"):
                await runtime_state_store.complete(
                    ctx.execution_id,
                    status=ctx.status,
                    final_response=ctx.final_response or "",
                    failure_reason=ctx.errors[-1] if ctx.errors else "",
                )
            else:
                await runtime_state_store.update(
                    ctx.execution_id,
                    status=ctx.status,
                    current_step=ctx.current_stage,
                )
        except Exception:
            pass

    # ---------------------------------------------------------
    # GET  (cache-first, then Redis)
    # ---------------------------------------------------------

    async def get(self, execution_id: str) -> Optional[ExecutionContext]:
        # 1. Warm cache hit
        if execution_id in self._contexts:
            return self._contexts[execution_id]

        # 2. Try Redis pipeline context (written by save())
        try:
            from backend.infrastructure.redis.runtime_cache import redis_cache
            data = await redis_cache.get_pipeline_context(execution_id)
            if data:
                ctx = _dict_to_context(data)
                self._contexts[execution_id] = ctx
                return ctx
        except Exception:
            pass

        return None

    # ---------------------------------------------------------
    # LIST ACTIVE  (Redis-backed, with in-memory fallback)
    # ---------------------------------------------------------

    async def list_active(self) -> List[Dict[str, Any]]:
        # Attempt Redis-backed listing via runtime_state_store
        try:
            from backend.runtime.runtime_state_store import runtime_state_store
            active = await runtime_state_store.list_active()
            if active:
                return active
        except Exception:
            pass

        # In-memory fallback
        return [
            ctx.to_dict()
            for ctx in self._contexts.values()
            if not ctx.is_complete()
        ]

    # ---------------------------------------------------------
    # LIST ALL  (cache + history from Redis)
    # ---------------------------------------------------------

    async def list_all(self) -> List[Dict[str, Any]]:
        # Merge in-memory and Redis history
        seen: Dict[str, Any] = {
            ctx.execution_id: ctx.to_dict()
            for ctx in self._contexts.values()
        }
        try:
            from backend.runtime.runtime_state_store import runtime_state_store
            history = await runtime_state_store.list_history(limit=500)
            for rec in history:
                eid = rec.get("execution_id")
                if eid and eid not in seen:
                    seen[eid] = rec
        except Exception:
            pass
        return list(seen.values())

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    async def delete(self, execution_id: str) -> None:
        self._contexts.pop(execution_id, None)


# =========================================================
# SINGLETON
# =========================================================

execution_context_manager = ExecutionContextManager()


# =========================================================
# HELPER: reconstruct ExecutionContext from a plain dict
# =========================================================

def _dict_to_context(data: Dict[str, Any]) -> "ExecutionContext":
    """
    Reconstruct an ExecutionContext dataclass from a serialised dict.
    Used when loading from Redis after a restart.
    """
    ctx = ExecutionContext(
        execution_id=data.get("execution_id", ""),
        parent_execution_id=data.get("parent_execution_id"),
        session_id=data.get("session_id"),
        objective=data.get("objective", ""),
        priority=int(data.get("priority", 5)),
        max_depth=int(data.get("max_depth", 5)),
        current_depth=int(data.get("current_depth", 0)),
    )
    ctx.current_stage     = data.get("current_stage", "initializing")
    ctx.completed_stages  = data.get("completed_stages") or []
    ctx.failed_stages     = data.get("failed_stages") or []
    ctx.stage_timings     = data.get("stage_timings") or {}
    ctx.retry_count       = int(data.get("retry_count", 0))
    ctx.status            = data.get("status", "pending")
    ctx.started_at        = data.get("started_at", ctx.started_at)
    ctx.ended_at          = data.get("ended_at")
    ctx.errors            = data.get("errors") or []
    ctx.final_response    = data.get("final_response")
    ctx.plan              = data.get("plan")
    ctx.research_result   = data.get("research_result")
    ctx.critic_result     = data.get("critic_result")
    ctx.optimizer_result  = data.get("optimizer_result")
    ctx.reflection_result = data.get("reflection_result")
    return ctx

