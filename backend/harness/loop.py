"""The harness loop (Part C): MISSION → ITERATION → PROPOSAL → VALIDATION →
GOVERNANCE → EXECUTION → OBSERVATION → VERIFICATION BOUNDARY → CONTINUE/STOP.

Ownership is the design (Phase 6.0 §21): the model proposes; the harness
decides structural validity, budgets, and continuation; governance decides
authorization; execution performs; observation reads the world back. The model
cannot end the mission — a proposal that claims completion routes through the
deterministic completion check, and only the check's verdict counts.

Verification boundary (Part H, honest): Phase 6.1 has no independent assurance
plane. What the loop records after an action is an **observation** — a fresh
read of the provider — and the deterministic completion check over it. Spans
mark the result ``observed_complete``, never ``VERIFIED``: minting verified
truth is Phase 8's job, and pretending otherwise here would recreate the
self-report defect this phase exists to quarantine.

Budgets are enforced *before* spending, not after: an exhausted budget stops
the loop at the top of the iteration, so "budget exhaustion cannot execute
another step" is a property of control flow, not of bookkeeping.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Type

from pydantic import BaseModel

from backend.harness.llm_boundary import (
    GovernedModelBoundary,
    InvalidModelOutput,
    TokenUsage,
    TraceEvidenceMissing,
)
from backend.harness.trace import TraceRecorder, build_action_span
from backend.harness.tool_exposure import (
    ResolvedTool,
    ToolExposurePolicy,
    ToolProposal,
    ToolRefused,
)
from backend.harness.version import HarnessVersion
from backend.platform.identity.generators import prefixed_id

__all__ = [
    "StopReason",
    "LoopBudget",
    "ActionOutcome",
    "Observation",
    "ActionPort",
    "ObservationPort",
    "CompletionPort",
    "LoopResult",
    "HarnessLoop",
]


class StopReason(str, Enum):
    COMPLETED = "completed"                      # deterministic check passed
    MAX_ITERATIONS = "max_iterations"
    MAX_TOOL_CALLS = "max_tool_calls"
    WALL_CLOCK_EXHAUSTED = "wall_clock_exhausted"
    TOKEN_BUDGET_EXHAUSTED = "token_budget_exhausted"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    TOOL_REFUSED = "tool_refused"  # named tool not exposed / bad args — pre-governance
    TRACE_WRITE_FAILED = "trace_write_failed"  # pre-action evidence unpersistable
    GOVERNANCE_REFUSED = "governance_refused"
    ACTION_FAILED = "action_failed"
    INTERRUPTED = "interrupted"
    MODEL_ERROR = "model_error"


@dataclass(frozen=True)
class LoopBudget:
    """Hard ceilings, checked before spending."""

    max_iterations: int = 5
    max_tool_calls: int = 10
    max_wall_clock_seconds: float = 300.0
    max_total_tokens: Optional[int] = None


@dataclass(frozen=True)
class ActionOutcome:
    """What the governed execution leg reported. ``refused`` and ``failed``
    are different facts; ``detail`` is provider-shaped but redacted at the
    span, not here."""

    performed: bool
    refused: bool
    refusal_stage: Optional[str] = None
    failure: Optional[str] = None
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Observation:
    """A fresh read of the world after an action. Facts, not verdicts."""

    observed: bool
    detail: Mapping[str, Any] = field(default_factory=dict)
    failure: Optional[str] = None


class ActionPort(Protocol):
    """The governed execution leg. Implementations MUST route every side
    effect through the governed invocation gateway — the harness cannot check
    that from here, which is exactly why BND-EFFECT-GATE and BND-PROCESS-SPAWN
    exist at the fitness layer."""

    async def execute(self, proposal: BaseModel) -> ActionOutcome: ...


class ObservationPort(Protocol):
    async def observe(self, proposal: BaseModel, outcome: ActionOutcome) -> Observation: ...


class CompletionPort(Protocol):
    """Deterministic: does the observed world satisfy the mission? The model's
    opinion is not an input."""

    def is_complete(self, observation: Observation) -> bool: ...


@dataclass
class LoopResult:
    mission_id: str
    stop_reason: StopReason
    iterations_run: int
    tool_calls_made: int
    tokens_spent: int
    completed: bool
    failure: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""


class HarnessLoop:
    """One mission's deterministic loop. Single-writer: one loop instance
    drives one mission; there is no concurrent proposal path."""

    def __init__(
        self,
        *,
        boundary: GovernedModelBoundary,
        action_port: ActionPort,
        observation_port: ObservationPort,
        completion_port: CompletionPort,
        recorder: TraceRecorder,
        harness_version: HarnessVersion,
        budget: LoopBudget,
        proposal_schema: Type[BaseModel],
        tool_exposure: Optional[ToolExposurePolicy] = None,
    ) -> None:
        self._boundary = boundary
        self._actions = action_port
        self._observations = observation_port
        self._completion = completion_port
        self._recorder = recorder
        self._version = harness_version
        self._budget = budget
        # Under a tool exposure policy the model proposes a ToolProposal
        # (tool + arguments), and the loop resolves it against the frozen
        # allowlist BEFORE governance. Without one, the schema is used as-is
        # and the action port receives the raw proposal (the 6.1 mode).
        self._tool_exposure = tool_exposure
        self._schema = ToolProposal if tool_exposure is not None else proposal_schema

    async def run(
        self,
        *,
        mission_id: str,
        system_prompt: str,
        build_prompt,  # (iteration: int, last_observation: Observation | None) -> str
        correlation_id: str,
        trace_id: str,
        span_id: str,
    ) -> LoopResult:
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        tool_calls = 0
        tokens = 0
        iterations = 0
        last_observation: Optional[Observation] = None
        trace_degraded: list = []

        def _safe_record(span) -> None:
            """Best-effort recording for POST-action and loop-state spans (Part
            E). Their authoritative outcome already lives in the fenced audit
            chain and the durable execution aggregate; a trace-store failure
            after the fact must not roll back a side effect that already
            happened, nor stop the loop from returning a deterministic result.
            It is recorded loudly — never silently swallowed."""
            try:
                self._recorder.record(span)
            except Exception as exc:
                trace_degraded.append(f"{span.kind}:{type(exc).__name__}")

        def _result(reason: StopReason, *, completed: bool = False,
                    failure: Optional[str] = None) -> LoopResult:
            result = LoopResult(
                mission_id=mission_id,
                stop_reason=reason,
                iterations_run=iterations,
                tool_calls_made=tool_calls,
                tokens_spent=tokens,
                completed=completed,
                failure=failure,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            # The loop-state span is the recovery hook: a fresh process reads
            # the last state span for the mission and knows where things stood.
            _safe_record(
                build_action_span(
                    kind="loop_state",
                    mission_id=mission_id,
                    iteration=iterations,
                    step_id=prefixed_id("lstate"),
                    harness_version=self._version.identity,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    trace_span_id=span_id,
                    started_at=started_at,
                    stop_or_failure_reason=reason.value,
                    detail={
                        "completed": completed,
                        "failure": failure,
                        "iterations_run": iterations,
                        "tool_calls_made": tool_calls,
                        "tokens_spent": tokens,
                        "trace_degraded": list(trace_degraded),
                    },
                )
            )
            return result

        try:
            while True:
                # -- budgets, before any spend this iteration ----------------
                if iterations >= self._budget.max_iterations:
                    return _result(StopReason.MAX_ITERATIONS)
                if time.monotonic() - started >= self._budget.max_wall_clock_seconds:
                    return _result(StopReason.WALL_CLOCK_EXHAUSTED)
                if (self._budget.max_total_tokens is not None
                        and tokens >= self._budget.max_total_tokens):
                    return _result(StopReason.TOKEN_BUDGET_EXHAUSTED)

                iterations += 1
                step_id = prefixed_id("step")
                exposed = (
                    tuple(sorted(self._tool_exposure.exposed_names))
                    if self._tool_exposure is not None
                    else None
                )

                # -- model proposes (untrusted) ------------------------------
                try:
                    proposal, model_span = await self._boundary.propose(
                        schema=self._schema,
                        system_prompt=system_prompt,
                        prompt=build_prompt(iterations, last_observation),
                        mission_id=mission_id,
                        iteration=iterations,
                        step_id=step_id,
                        correlation_id=correlation_id,
                        trace_id=trace_id,
                        trace_span_id=span_id,
                        tools_available=exposed,
                    )
                except TraceEvidenceMissing as exc:
                    # Pre-action evidence could not be persisted; the boundary
                    # returned no proposal, so nothing was acted on. Fail-closed
                    # (Part E). This is deterministic, not a model failure.
                    return _result(
                        StopReason.TRACE_WRITE_FAILED, failure=exc.reason
                    )
                except InvalidModelOutput as exc:
                    return _result(
                        StopReason.INVALID_MODEL_OUTPUT, failure=exc.reason
                    )
                except Exception as exc:  # provider/transport failure
                    return _result(
                        StopReason.MODEL_ERROR, failure=f"{type(exc).__name__}: {exc}"
                    )
                if model_span.token_usage:
                    tokens += int(model_span.token_usage.get("total_tokens", 0))

                # -- tool resolution (deterministic, BEFORE governance) ------
                # The model named a tool; the harness resolves it against the
                # frozen allowlist. An unknown tool, an undeclared/malformed
                # argument, or a smuggled provider/operation/URL is refused
                # here — nothing governed runs, and provider/operation come
                # from the deployment's registry, never the model (Part I).
                action_input: Any = proposal
                if self._tool_exposure is not None:
                    resolution = self._tool_exposure.resolve({
                        "tool": proposal.tool,
                        "arguments": proposal.arguments,
                    })
                    if isinstance(resolution, ToolRefused):
                        _safe_record(
                            build_action_span(
                                kind="governed_action",
                                mission_id=mission_id, iteration=iterations,
                                step_id=step_id,
                                harness_version=self._version.identity,
                                correlation_id=correlation_id, trace_id=trace_id,
                                trace_span_id=span_id, started_at=started_at,
                                tool_call={
                                    "requested_tool": resolution.tool_name,
                                    "tools_available": list(exposed or ()),
                                    "resolved": False,
                                },
                                gate_decisions=(f"tool_refused:{resolution.reason.value}",),
                                stop_or_failure_reason=resolution.reason.value,
                            )
                        )
                        return _result(
                            StopReason.TOOL_REFUSED, failure=resolution.reason.value)
                    action_input = resolution

                # -- governed action -----------------------------------------
                if tool_calls >= self._budget.max_tool_calls:
                    return _result(StopReason.MAX_TOOL_CALLS)
                tool_calls += 1
                action_started = datetime.now(timezone.utc).isoformat()
                outcome = await self._actions.execute(action_input)
                _safe_record(
                    build_action_span(
                        kind="governed_action",
                        mission_id=mission_id,
                        iteration=iterations,
                        step_id=step_id,
                        harness_version=self._version.identity,
                        correlation_id=correlation_id,
                        trace_id=trace_id,
                        trace_span_id=span_id,
                        started_at=action_started,
                        tool_call={
                            "proposal": proposal.model_dump(),
                            # When resolved through the exposure policy, record
                            # the DEPLOYMENT's provider/operation — the model
                            # supplied neither (Part I/E lineage).
                            "resolved_provider": (
                                action_input.provider
                                if isinstance(action_input, ResolvedTool) else None
                            ),
                            "resolved_operation": (
                                action_input.operation
                                if isinstance(action_input, ResolvedTool) else None
                            ),
                            "performed": outcome.performed,
                            "refused": outcome.refused,
                            "refusal_stage": outcome.refusal_stage,
                            "failure": outcome.failure,
                            "detail": dict(outcome.detail),
                        },
                        gate_decisions=(
                            (f"refused:{outcome.refusal_stage}",)
                            if outcome.refused
                            else ("admitted",)
                        ),
                        stop_or_failure_reason=outcome.failure,
                    )
                )
                if outcome.refused:
                    return _result(
                        StopReason.GOVERNANCE_REFUSED,
                        failure=outcome.refusal_stage,
                    )
                if not outcome.performed:
                    return _result(StopReason.ACTION_FAILED, failure=outcome.failure)

                # -- observation (facts) + deterministic completion ----------
                obs_started = datetime.now(timezone.utc).isoformat()
                last_observation = await self._observations.observe(proposal, outcome)
                complete = (
                    last_observation.observed
                    and self._completion.is_complete(last_observation)
                )
                _safe_record(
                    build_action_span(
                        kind="observation",
                        mission_id=mission_id,
                        iteration=iterations,
                        step_id=step_id,
                        harness_version=self._version.identity,
                        correlation_id=correlation_id,
                        trace_id=trace_id,
                        trace_span_id=span_id,
                        started_at=obs_started,
                        detail={
                            "observed": last_observation.observed,
                            "observation": dict(last_observation.detail),
                            "observed_complete": complete,
                            # Part H boundary, stated on every record: this is
                            # an observation + deterministic check, not an
                            # independent verification. Phase 8 owns VERIFIED.
                            "verification": "BOUNDARY_UNVERIFIED",
                        },
                        stop_or_failure_reason=last_observation.failure,
                    )
                )
                if complete:
                    return _result(StopReason.COMPLETED, completed=True)
        except BaseException as exc:
            # Interruption (cancellation, shutdown, KeyboardInterrupt) leaves a
            # durable loop-state span behind, then propagates: the harness
            # never swallows a cancellation.
            _result(StopReason.INTERRUPTED, failure=f"{type(exc).__name__}")
            raise
