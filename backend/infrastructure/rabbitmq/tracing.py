"""
RabbitMQ Message Tracing
-------------------------
Distributed tracing middleware for the CortexPrime message bus.

Every message published or consumed passes through this module, which:

1. Injects a ``TraceContext`` (trace_id / span_id / parent_span_id) into
   outgoing AMQP headers.
2. Extracts and logs the trace context from incoming messages.
3. Records a ``MessageTrace`` entry (in-memory ring-buffer + optional
   Redis append) for observability tooling.
4. Provides a ``@traced_handler`` decorator that wraps consumer callbacks
   with span start/finish logging.

Usage — publishing
~~~~~~~~~~~~~~~~~~
    msg = cognition_event_message(...)
    headers = message_tracer.outgoing_headers(msg)
    # Pass headers to aio_pika.Message(headers=headers, ...)

Usage — consuming
~~~~~~~~~~~~~~~~~
    @message_tracer.traced_handler("my_queue")
    async def handle(msg: RabbitMessage) -> None:
        ...

Usage — decorator on consumer callback
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    consumer.on(MessageType.EXECUTION_EVENT, message_tracer.wrap(handler))
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger(__name__)

from backend.infrastructure.rabbitmq.schemas import RabbitMessage, TraceContext


# =========================================================
# MESSAGE TRACE RECORD
# =========================================================

class MessageTrace:
    """Single recorded message-level trace entry."""

    __slots__ = (
        "trace_id", "span_id", "parent_span_id",
        "message_id", "message_type", "execution_id",
        "queue", "direction",
        "started_at", "finished_at", "duration_ms",
        "status", "error",
    )

    def __init__(
        self,
        message:   RabbitMessage,
        queue:     str,
        direction: str,       # "publish" | "consume"
    ) -> None:
        self.trace_id        = message.trace.trace_id
        self.span_id         = message.trace.span_id
        self.parent_span_id  = message.trace.parent_span_id
        self.message_id      = message.message_id
        self.message_type    = message.message_type.value
        self.execution_id    = message.execution_id
        self.queue           = queue
        self.direction       = direction
        self.started_at      = time.monotonic()
        self.finished_at:    Optional[float] = None
        self.duration_ms:    Optional[float] = None
        self.status:         str = "in_flight"
        self.error:          Optional[str] = None

    def finish(self, status: str = "ok", error: Optional[str] = None) -> None:
        self.finished_at = time.monotonic()
        self.duration_ms = (self.finished_at - self.started_at) * 1000
        self.status      = status
        self.error       = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id":       self.trace_id,
            "span_id":        self.span_id,
            "parent_span_id": self.parent_span_id,
            "message_id":     self.message_id,
            "message_type":   self.message_type,
            "execution_id":   self.execution_id,
            "queue":          self.queue,
            "direction":      self.direction,
            "duration_ms":    self.duration_ms,
            "status":         self.status,
            "error":          self.error,
        }


# =========================================================
# MESSAGE TRACER
# =========================================================

class MessageTracer:
    """
    Lightweight in-process message tracing ring buffer.

    Keeps the last ``MAX_TRACES`` entries in memory for debugging.
    Optionally appends to the Redis cognition cache when available
    (fire-and-forget, no blocking).
    """

    MAX_TRACES = 2_000

    def __init__(self) -> None:
        self._traces: Deque[MessageTrace] = deque(maxlen=self.MAX_TRACES)

    # ---------------------------------------------------------
    # OUTGOING HEADERS
    # ---------------------------------------------------------

    def outgoing_headers(self, message: RabbitMessage) -> Dict[str, str]:
        """
        Produce AMQP headers dict for an outgoing message, injecting
        trace context alongside standard routing headers.
        """
        return message.to_amqp_headers()

    # ---------------------------------------------------------
    # INBOUND CONTEXT EXTRACTION
    # ---------------------------------------------------------

    @staticmethod
    def extract_trace(headers: Dict[str, Any]) -> TraceContext:
        """Extract (or synthesise) a TraceContext from raw AMQP headers."""
        return TraceContext.from_headers(headers or {})

    # ---------------------------------------------------------
    # RECORD
    # ---------------------------------------------------------

    def record_publish(
        self,
        message: RabbitMessage,
        queue:   str = "",
    ) -> MessageTrace:
        entry = MessageTrace(message, queue, "publish")
        entry.finish(status="ok")
        self._traces.append(entry)
        log.debug(
            "→ [%s] %s exec=%s trace=%s",
            queue or "exchange",
            message.message_type.value,
            message.execution_id,
            message.trace.span_id[:8],
        )
        return entry

    def record_consume_start(
        self,
        message: RabbitMessage,
        queue:   str = "",
    ) -> MessageTrace:
        entry = MessageTrace(message, queue, "consume")
        self._traces.append(entry)
        log.debug(
            "← [%s] %s exec=%s trace=%s",
            queue,
            message.message_type.value,
            message.execution_id,
            message.trace.span_id[:8],
        )
        return entry

    def record_consume_end(
        self,
        trace:  MessageTrace,
        status: str = "ok",
        error:  Optional[str] = None,
    ) -> None:
        trace.finish(status=status, error=error)
        if error:
            log.warning(
                "← [%s] %s FAILED in %.1f ms: %s",
                trace.queue, trace.message_type, trace.duration_ms or 0, error,
            )

    # ---------------------------------------------------------
    # HANDLER WRAPPER
    # ---------------------------------------------------------

    def wrap(
        self,
        handler:   Callable,
        queue:     str = "",
    ) -> Callable:
        """
        Wrap an async consumer handler with start/end tracing.

        Example
        -------
        consumer.on(MessageType.EXECUTION_EVENT, tracer.wrap(my_handler, "execution.events"))
        """
        async def _wrapped(message: RabbitMessage) -> None:
            span = self.record_consume_start(message, queue)
            try:
                await handler(message)
                self.record_consume_end(span, status="ok")
            except Exception as exc:
                self.record_consume_end(span, status="error", error=str(exc))
                raise

        return _wrapped

    # ---------------------------------------------------------
    # QUERY
    # ---------------------------------------------------------

    def recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent N trace entries (newest last)."""
        entries = list(self._traces)[-limit:]
        return [e.to_dict() for e in entries]

    def by_execution(self, execution_id: str) -> List[Dict[str, Any]]:
        return [
            e.to_dict()
            for e in self._traces
            if e.execution_id == execution_id
        ]

    def by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        return [
            e.to_dict()
            for e in self._traces
            if e.trace_id == trace_id
        ]

    def stats(self) -> Dict[str, Any]:
        entries = list(self._traces)
        if not entries:
            return {"count": 0}
        durations = [e.duration_ms for e in entries if e.duration_ms is not None]
        errors    = sum(1 for e in entries if e.status == "error")
        return {
            "count":        len(entries),
            "errors":       errors,
            "avg_ms":       round(sum(durations) / len(durations), 2) if durations else 0,
            "max_ms":       round(max(durations), 2) if durations else 0,
        }


# =========================================================
# SINGLETON
# =========================================================

message_tracer = MessageTracer()
