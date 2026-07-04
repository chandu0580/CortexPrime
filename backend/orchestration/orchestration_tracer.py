from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger(__name__)


# =========================================================
# SPAN
# =========================================================

@dataclass
class TraceSpan:
    """A single recorded segment of execution."""

    span_id:      str = field(default_factory=lambda: str(uuid4()))
    execution_id: str = ""
    agent:        str = ""
    stage:        str = ""
    status:       str = "running"
    started_at:   float = field(default_factory=time.monotonic)
    ended_at:     Optional[float] = None
    duration_ms:  Optional[float] = None
    metadata:     Dict[str, Any] = field(default_factory=dict)
    error:        Optional[str] = None

    def finish(self, status: str = "completed", error: Optional[str] = None) -> None:
        self.ended_at    = time.monotonic()
        self.duration_ms = (self.ended_at - self.started_at) * 1000
        self.status      = status
        self.error       = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id":      self.span_id,
            "execution_id": self.execution_id,
            "agent":        self.agent,
            "stage":        self.stage,
            "status":       self.status,
            "duration_ms":  self.duration_ms,
            "error":        self.error,
            "metadata":     self.metadata,
        }


# =========================================================
# ORCHESTRATION TRACER
# =========================================================

class OrchestrationTracer:
    """
    Distributed-style tracing for the cognitive pipeline.

    Captures every span (agent + stage), stores per execution,
    and optionally writes to Redis for cross-process visibility.
    """

    def __init__(self):
        # execution_id → list of spans
        self._traces: Dict[str, List[TraceSpan]] = {}

    # ---------------------------------------------------------
    # START SPAN
    # ---------------------------------------------------------

    def start_span(
        self,
        execution_id: str,
        agent:        str,
        stage:        str,
        metadata:     Dict[str, Any] = {},
    ) -> TraceSpan:
        span = TraceSpan(
            execution_id=execution_id,
            agent=agent,
            stage=stage,
            metadata=metadata,
        )

        if execution_id not in self._traces:
            self._traces[execution_id] = []
        self._traces[execution_id].append(span)

        log.debug(
            "▶ Span started: exec=%s agent=%s stage=%s",
            execution_id, agent, stage,
        )
        return span

    # ---------------------------------------------------------
    # FINISH SPAN
    # ---------------------------------------------------------

    def finish_span(
        self,
        span:   TraceSpan,
        status: str = "completed",
        error:  Optional[str] = None,
    ) -> None:
        span.finish(status=status, error=error)
        log.debug(
            "■ Span done: agent=%s stage=%s status=%s duration_ms=%.1f",
            span.agent, span.stage, status, span.duration_ms or 0,
        )

    # ---------------------------------------------------------
    # GET TRACE
    # ---------------------------------------------------------

    def get_trace(self, execution_id: str) -> List[Dict[str, Any]]:
        spans = self._traces.get(execution_id, [])
        return [s.to_dict() for s in spans]

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    def summary(self, execution_id: str) -> Dict[str, Any]:
        spans = self._traces.get(execution_id, [])
        if not spans:
            return {}

        total_ms = sum(
            s.duration_ms for s in spans if s.duration_ms is not None
        )
        failed   = [s for s in spans if s.status == "failed"]

        return {
            "execution_id": execution_id,
            "total_spans":  len(spans),
            "total_ms":     round(total_ms, 2),
            "failed_spans": len(failed),
            "stages":       [s.stage for s in spans],
        }

    # ---------------------------------------------------------
    # PERSIST TO REDIS
    # ---------------------------------------------------------

    async def persist(self, execution_id: str) -> None:
        try:
            from backend.infrastructure.redis.runtime_cache import redis_cache
            trace = self.get_trace(execution_id)
            for span_dict in trace:
                await redis_cache.append_cognition_log(execution_id, span_dict)
        except Exception as exc:
            log.warning("Tracer persist failed: %s", exc)


# =========================================================
# SINGLETON
# =========================================================

orchestration_tracer = OrchestrationTracer()
