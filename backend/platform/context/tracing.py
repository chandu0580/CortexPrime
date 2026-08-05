"""Trace and correlation context.

Three identifiers with genuinely different jobs, routinely conflated:

``trace_id``
    Spans one distributed request across process boundaries. What an APM tool
    joins on.

``correlation_id``
    Spans one *causal chain* — a whole incident, a whole mission — which may
    outlive many requests. What you filter a log by when investigating.

``causation_id``
    The single operation that directly caused this one. Following these
    backwards reconstructs the exact path; correlation alone tells you only
    which chain you are in, not where.

The same distinction ``EventMetadata`` draws (ADR-012), applied to operations
rather than events, so an event emitted mid-operation inherits a causal position
that already exists rather than inventing one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts import ContractViolation
from backend.platform.identity import monotonic_ulid, new_ulid

__all__ = ["TraceContext", "CorrelationContext"]


@dataclass(frozen=True)
class CorrelationContext:
    """Causal position: which chain, and where in it."""

    correlation_id: str
    causation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.correlation_id, str) or not self.correlation_id.strip():
            raise ContractViolation("correlation_id must be a non-blank string")
        if self.causation_id is not None:
            if not isinstance(self.causation_id, str) or not self.causation_id.strip():
                raise ContractViolation("causation_id must be non-blank when present")
            if self.causation_id == self.correlation_id:
                raise ContractViolation(
                    "causation_id must not equal correlation_id; they answer different "
                    "questions and equal values usually mean one was copied by mistake"
                )

    @classmethod
    def new_chain(cls) -> "CorrelationContext":
        """Begin a new causal chain.

        Monotonic so chains started in the same millisecond stay orderable,
        which matters when reconstructing what ran first during an incident.
        """
        return cls(correlation_id=monotonic_ulid())

    @classmethod
    def join(cls, correlation_id: str, causation_id: Optional[str] = None) -> "CorrelationContext":
        """Join an existing chain, optionally naming the direct cause."""
        return cls(correlation_id=correlation_id, causation_id=causation_id)

    @property
    def is_chain_origin(self) -> bool:
        return self.causation_id is None

    def caused_by(self, operation_id: str) -> "CorrelationContext":
        """Return a context for work caused by ``operation_id``.

        Correlation is preserved; only causation moves. Building a chain by hand
        invites a missing link, and a chain with a missing link cannot be traced.
        """
        return CorrelationContext(
            correlation_id=self.correlation_id, causation_id=operation_id
        )


@dataclass(frozen=True)
class TraceContext:
    """Distributed-trace position.

    ``span_id`` identifies this operation; ``parent_span_id`` its caller.
    Deliberately compatible in shape with W3C Trace Context so an inbound
    ``traceparent`` header can populate it without translation, but not
    format-validated here — rejecting a malformed upstream header at the context
    layer would drop a request over telemetry.
    """

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    sampled: bool = True

    def __post_init__(self) -> None:
        for label, value in (("trace_id", self.trace_id), ("span_id", self.span_id)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")
        if self.parent_span_id is not None and self.parent_span_id == self.span_id:
            raise ContractViolation("span_id must differ from parent_span_id")

    @classmethod
    def new_trace(cls, *, sampled: bool = True) -> "TraceContext":
        return cls(trace_id=new_ulid(), span_id=new_ulid(), sampled=sampled)

    @classmethod
    def continue_trace(
        cls, trace_id: str, parent_span_id: Optional[str] = None, *, sampled: bool = True
    ) -> "TraceContext":
        """Continue an inbound trace with a fresh span."""
        return cls(
            trace_id=trace_id,
            span_id=new_ulid(),
            parent_span_id=parent_span_id,
            sampled=sampled,
        )

    def child_span(self) -> "TraceContext":
        """A child span within the same trace."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=new_ulid(),
            parent_span_id=self.span_id,
            sampled=self.sampled,
        )
