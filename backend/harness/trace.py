"""Attribution-grade harness trace spans (L14).

One span per governed model invocation or governed action attempt, carrying
what failure attribution needs and nothing it must not:

* mission / iteration / step identity, and the correlation + trace identifiers
  the platform ``ExecutionContext`` already stamps into audit events — so a
  span and its audit records join on ``correlation_id`` with no new mechanism.
* model identity and configuration, harness version, prompts and outputs
  **redacted at construction**: a span object never exists in unredacted form,
  so no recorder implementation can leak what the constructor already removed.
  Redaction is deterministic code (``scrub_text`` / ``redact_mapping``), never
  model judgment.
* an honest replay marker: ``context_reconstructable`` is ``False`` unless the
  recipe genuinely reconstructs the exact model input. Phase 6.1 persists the
  scrubbed rendered prompt plus a recipe; scrubbing is lossy, so spans say so
  rather than claiming replayability the evidence cannot support.

This store is **not** the audit chain and never will be: the audit runtime
explicitly bans traces from the chain (platform/audit/runtime.py). Governance
facts live there; explanation evidence lives here; ``correlation_id`` joins
them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, Sequence

from backend.platform.credentials.redaction import redact_mapping, scrub_text
from backend.platform.identity.generators import prefixed_id

__all__ = [
    "HarnessSpan",
    "TraceRecorder",
    "InMemoryTraceRecorder",
    "build_model_span",
    "build_action_span",
    "SCRUB_MAX_CHARS",
]

#: Prompts and outputs are scrubbed, not truncated to the redaction module's
#: conservative default — attribution needs the text. Bounded all the same so
#: a provider returning megabytes cannot turn one span into a memory event.
SCRUB_MAX_CHARS = 200_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class HarnessSpan:
    """One recorded harness step. Immutable; redacted before construction."""

    span_record_id: str
    kind: str  # "model_proposal" | "governed_action" | "observation" | "loop_state"
    mission_id: str
    iteration: int
    step_id: str
    harness_version: str
    correlation_id: str
    trace_id: str
    trace_span_id: str
    started_at: str
    finished_at: str
    latency_ms: Optional[float] = None
    model_provider: Optional[str] = None
    model_id: Optional[str] = None
    model_config: Optional[Mapping[str, Any]] = None
    prompt_redacted: Optional[str] = None
    context_recipe: Optional[Mapping[str, Any]] = None
    context_reconstructable: bool = False
    output_redacted: Optional[str] = None
    tool_call: Optional[Mapping[str, Any]] = None
    gate_decisions: tuple = ()
    token_usage: Optional[Mapping[str, Any]] = None
    stop_or_failure_reason: Optional[str] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        """A JSON-serializable projection for any recorder backend."""
        return {
            "span_record_id": self.span_record_id,
            "kind": self.kind,
            "mission_id": self.mission_id,
            "iteration": self.iteration,
            "step_id": self.step_id,
            "harness_version": self.harness_version,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "trace_span_id": self.trace_span_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "latency_ms": self.latency_ms,
            "model_provider": self.model_provider,
            "model_id": self.model_id,
            "model_config": dict(self.model_config) if self.model_config else None,
            "prompt_redacted": self.prompt_redacted,
            "context_recipe": dict(self.context_recipe) if self.context_recipe else None,
            "context_reconstructable": self.context_reconstructable,
            "output_redacted": self.output_redacted,
            "tool_call": dict(self.tool_call) if self.tool_call else None,
            "gate_decisions": list(self.gate_decisions),
            "token_usage": dict(self.token_usage) if self.token_usage else None,
            "stop_or_failure_reason": self.stop_or_failure_reason,
            "detail": dict(self.detail),
        }


class TraceRecorder(Protocol):
    """Where spans go. Append-only by contract: no recorder exposes update,
    delete, or replace — a trace that can be edited is not evidence."""

    def record(self, span: HarnessSpan) -> None: ...


class InMemoryTraceRecorder:
    """Append-only in-memory recorder for tests and non-durable runs."""

    def __init__(self) -> None:
        self._spans: list[HarnessSpan] = []

    def record(self, span: HarnessSpan) -> None:
        self._spans.append(span)

    @property
    def spans(self) -> tuple[HarnessSpan, ...]:
        return tuple(self._spans)

    def spans_for_mission(self, mission_id: str) -> tuple[HarnessSpan, ...]:
        return tuple(s for s in self._spans if s.mission_id == mission_id)


def _scrub(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return scrub_text(text, max_length=SCRUB_MAX_CHARS)


def _redact_map(data: Optional[Mapping[str, Any]]) -> Optional[dict[str, Any]]:
    if data is None:
        return None
    redacted = redact_mapping(dict(data))
    # Belt over braces: scrub string values too, so a token in a *value* under
    # an innocuous key still cannot survive into the record.
    return json.loads(scrub_text(json.dumps(redacted, default=str), max_length=SCRUB_MAX_CHARS))


def build_model_span(
    *,
    mission_id: str,
    iteration: int,
    step_id: str,
    harness_version: str,
    correlation_id: str,
    trace_id: str,
    trace_span_id: str,
    started_at: str,
    model_provider: str,
    model_id: str,
    model_config: Optional[Mapping[str, Any]],
    prompt: str,
    context_recipe: Optional[Mapping[str, Any]],
    context_reconstructable: bool,
    output: Optional[str],
    token_usage: Optional[Mapping[str, Any]],
    latency_ms: Optional[float],
    stop_or_failure_reason: Optional[str] = None,
    gate_decisions: Sequence[str] = (),
) -> HarnessSpan:
    """A model-invocation span, redacted at construction (L14)."""
    return HarnessSpan(
        span_record_id=prefixed_id("hspan"),
        kind="model_proposal",
        mission_id=mission_id,
        iteration=iteration,
        step_id=step_id,
        harness_version=harness_version,
        correlation_id=correlation_id,
        trace_id=trace_id,
        trace_span_id=trace_span_id,
        started_at=started_at,
        finished_at=_now(),
        latency_ms=latency_ms,
        model_provider=model_provider,
        model_id=model_id,
        model_config=_redact_map(model_config),
        prompt_redacted=_scrub(prompt),
        context_recipe=_redact_map(context_recipe),
        context_reconstructable=context_reconstructable,
        output_redacted=_scrub(output),
        token_usage=dict(token_usage) if token_usage else None,
        stop_or_failure_reason=stop_or_failure_reason,
        gate_decisions=tuple(gate_decisions),
    )


def build_action_span(
    *,
    kind: str,
    mission_id: str,
    iteration: int,
    step_id: str,
    harness_version: str,
    correlation_id: str,
    trace_id: str,
    trace_span_id: str,
    started_at: str,
    tool_call: Optional[Mapping[str, Any]] = None,
    gate_decisions: Sequence[str] = (),
    stop_or_failure_reason: Optional[str] = None,
    latency_ms: Optional[float] = None,
    detail: Optional[Mapping[str, Any]] = None,
) -> HarnessSpan:
    """A governed-action / observation / loop-state span."""
    return HarnessSpan(
        span_record_id=prefixed_id("hspan"),
        kind=kind,
        mission_id=mission_id,
        iteration=iteration,
        step_id=step_id,
        harness_version=harness_version,
        correlation_id=correlation_id,
        trace_id=trace_id,
        trace_span_id=trace_span_id,
        started_at=started_at,
        finished_at=_now(),
        latency_ms=latency_ms,
        tool_call=_redact_map(tool_call),
        gate_decisions=tuple(gate_decisions),
        stop_or_failure_reason=stop_or_failure_reason,
        detail=_redact_map(detail) or {},
    )
