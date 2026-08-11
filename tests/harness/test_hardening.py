"""Phase 6.2 harness hardening — Parts B, E, H, I, J, K.

Proves the spine resists failure rather than merely working:
  B  loop interruption leaves durable-authoritative state, never a fabricated
     success, and never a harness-performed side effect;
  E  trace failure is FAIL-CLOSED for the pre-action model span and BEST-EFFORT
     (loud) for post-action spans — derived from L14, not chosen;
  H  no model self-report string can establish authoritative success;
  I  budgets are hard ceilings the model/tool/retry cannot reset;
  J  every model invocation carries a deterministic context contract;
  K  harness identity moves with any policy change and cannot self-mutate.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from backend.harness.llm_boundary import (
    GovernedModelBoundary,
    ModelInvocation,
    TokenUsage,
    TraceEvidenceMissing,
    schema_identity,
)
from backend.harness.loop import (
    ActionOutcome,
    HarnessLoop,
    LoopBudget,
    Observation,
    StopReason,
)
from backend.harness.trace import InMemoryTraceRecorder
from backend.harness.version import CURRENT_HARNESS_VERSION, HarnessVersion


class Proposal(BaseModel):
    action: str
    target: str
    reason: str


VALID = '{"action": "act", "target": "scratch", "reason": "test"}'


class ScriptedPort:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = 0

    async def generate(self, *, system_prompt: str, prompt: str) -> ModelInvocation:
        self.calls += 1
        content = self._outputs.pop(0) if self._outputs else VALID
        return ModelInvocation(
            content=content, provider="scripted", model="scripted-1",
            latency_ms=1.0, usage=TokenUsage(100, 50),
        )


class AllowActions:
    def __init__(self):
        self.executed = []

    async def execute(self, proposal):
        self.executed.append(proposal)
        return ActionOutcome(performed=True, refused=False)


class ObserveRunning:
    async def observe(self, proposal, outcome):
        return Observation(observed=True, detail={"status": "running"})


class NeverComplete:
    def is_complete(self, observation) -> bool:
        return False


class CompleteOnce:
    def is_complete(self, observation) -> bool:
        return True


def _boundary(outputs, recorder=None):
    recorder = recorder or InMemoryTraceRecorder()
    port = ScriptedPort(outputs)
    return (
        GovernedModelBoundary(
            model_port=port, recorder=recorder,
            harness_version=CURRENT_HARNESS_VERSION,
        ),
        recorder,
        port,
    )


def _loop(boundary, recorder, *, actions=None, observations=None,
          completion=None, budget=None):
    return HarnessLoop(
        boundary=boundary,
        action_port=actions or AllowActions(),
        observation_port=observations or ObserveRunning(),
        completion_port=completion or CompleteOnce(),
        recorder=recorder,
        harness_version=CURRENT_HARNESS_VERSION,
        budget=budget or LoopBudget(),
        proposal_schema=Proposal,
    )


async def _run(loop, mission_id="m"):
    return await loop.run(
        mission_id=mission_id, system_prompt="s",
        build_prompt=lambda i, obs: f"iter {i}",
        correlation_id="c", trace_id="t", span_id="sp",
    )


# ======================================================================
# Part E — trace failure semantics (derived from L14)
# ======================================================================

class FailingRecorder:
    """A trace store that refuses to write. Models the trace_sql loud-raise."""

    def __init__(self):
        self.attempts = 0

    def record(self, span):
        self.attempts += 1
        raise RuntimeError("trace store unavailable")


class FailAfterModelRecorder(InMemoryTraceRecorder):
    """Records the model-proposal span, then fails every post-action write —
    the interesting case for the fail-closed vs best-effort split."""

    def record(self, span):
        if span.kind != "model_proposal":
            raise RuntimeError("trace store unavailable")
        super().record(span)


class TestTraceFailureSemantics:
    @pytest.mark.anyio
    async def test_model_span_failure_is_fail_closed_no_action(self):
        """L14: a step without its (pre-action) evidence record is a failed
        step. The proposal must not reach the action port."""
        boundary, _, _ = _boundary([VALID], recorder=FailingRecorder())
        actions = AllowActions()
        loop = _loop(boundary, FailingRecorder(), actions=actions)
        # The boundary's recorder is the fail-closed point.
        result = await _run(loop)
        assert result.stop_reason == StopReason.TRACE_WRITE_FAILED
        assert not result.completed
        assert actions.executed == []  # nothing crossed the boundary

    @pytest.mark.anyio
    async def test_boundary_raises_trace_evidence_missing(self):
        boundary, _, _ = _boundary([VALID], recorder=FailingRecorder())
        with pytest.raises(TraceEvidenceMissing):
            await boundary.propose(
                schema=Proposal, system_prompt="s", prompt="p",
                mission_id="m", iteration=1, step_id="st",
                correlation_id="c", trace_id="t", trace_span_id="sp",
            )

    @pytest.mark.anyio
    async def test_post_action_trace_failure_is_best_effort_loud(self):
        """The provider already acted; the authoritative outcome is elsewhere
        (audit chain). A post-action trace failure must NOT roll back or abort —
        it is recorded loudly in trace_degraded and the run still completes."""
        recorder = FailAfterModelRecorder()
        boundary = GovernedModelBoundary(
            model_port=ScriptedPort([VALID]), recorder=recorder,
            harness_version=CURRENT_HARNESS_VERSION,
        )
        actions = AllowActions()
        loop = _loop(boundary, recorder, actions=actions, completion=CompleteOnce())
        result = await _run(loop, mission_id="m-degraded")
        # The action DID happen (best-effort trace, authoritative outcome held).
        assert len(actions.executed) == 1
        assert result.completed
        assert result.stop_reason == StopReason.COMPLETED


# ======================================================================
# Part H — model success claims cannot establish outcome
# ======================================================================

class TestModelSuccessBoundary:
    @pytest.mark.parametrize("claim", [
        "success", "verified", "completed", "rollback successful",
        "provider accepted", "incident resolved",
    ])
    @pytest.mark.anyio
    async def test_model_claim_does_not_complete_mission(self, claim):
        """No model string transitions state to success. Only the deterministic
        completion port, reading an observation, may — and here it never does."""
        payload = f'{{"action": "act", "target": "scratch", "reason": "{claim}"}}'
        boundary, recorder, _ = _boundary([payload] * 3)
        loop = _loop(
            boundary, recorder,
            completion=NeverComplete(),
            budget=LoopBudget(max_iterations=3, max_tool_calls=10),
        )
        result = await _run(loop)
        assert not result.completed
        assert result.stop_reason == StopReason.MAX_ITERATIONS

    @pytest.mark.anyio
    async def test_completion_reads_observation_not_proposal(self):
        """The completion port is handed an Observation, never the proposal —
        so a model cannot smuggle a success signal into the decision."""
        seen = {}

        class Recorder:
            def is_complete(self, observation) -> bool:
                seen["type"] = type(observation).__name__
                seen["has_proposal_attr"] = hasattr(observation, "action")
                return True

        boundary, recorder, _ = _boundary([VALID])
        loop = _loop(boundary, recorder, completion=Recorder())
        await _run(loop)
        assert seen["type"] == "Observation"
        assert seen["has_proposal_attr"] is False


# ======================================================================
# Part I — budgets are hard ceilings nothing can reset
# ======================================================================

class BudgetProbingAction:
    """An action port that records everything it was handed, to prove it was
    never handed the loop's budget or the loop itself."""

    def __init__(self):
        self.executed = 0
        self.args_seen = []

    async def execute(self, proposal, *args, **kwargs):
        self.executed += 1
        self.args_seen.append((type(proposal).__name__, args, tuple(kwargs)))
        return ActionOutcome(performed=True, refused=False)


class TestBudgetHardening:
    def test_budget_is_frozen_to_ordinary_assignment(self):
        b = LoopBudget(max_iterations=3)
        with pytest.raises(Exception):
            b.max_iterations = 99  # type: ignore[misc]

    @pytest.mark.anyio
    async def test_action_port_never_receives_the_budget(self):
        """Isolation is the real defense: the loop owns its budget privately
        and hands the action only a proposal. A tool cannot reset a budget it
        cannot reference."""
        boundary, recorder, _ = _boundary([VALID] * 10)
        action = BudgetProbingAction()
        loop = _loop(boundary, recorder, actions=action,
                     completion=NeverComplete(),
                     budget=LoopBudget(max_iterations=2, max_tool_calls=10))
        result = await _run(loop)
        # The action only ever saw a proposal — no budget, no loop, no kwargs.
        assert all(seen == ("Proposal", (), ()) for seen in action.args_seen)
        # And the ceiling held regardless.
        assert result.stop_reason == StopReason.MAX_ITERATIONS
        assert result.iterations_run == 2

    @pytest.mark.anyio
    async def test_budget_reference_is_private(self):
        """The loop's budget is not reachable through its public surface."""
        boundary, recorder, _ = _boundary([VALID])
        budget = LoopBudget(max_iterations=1)
        loop = _loop(boundary, recorder, budget=budget)
        public = [a for a in dir(loop) if not a.startswith("_")]
        assert "budget" not in public
        assert "run" in public  # sanity: we're inspecting the right object

    @pytest.mark.anyio
    async def test_token_ceiling_stops_before_next_call(self):
        boundary, recorder, port = _boundary([VALID] * 10)
        loop = _loop(boundary, recorder, completion=NeverComplete(),
                     budget=LoopBudget(max_iterations=10, max_total_tokens=150))
        result = await _run(loop)
        assert result.stop_reason == StopReason.TOKEN_BUDGET_EXHAUSTED
        assert port.calls == 1  # 150 spent on call 1; no call 2

    @pytest.mark.anyio
    async def test_tool_call_ceiling_precedes_action(self):
        boundary, recorder, _ = _boundary([VALID] * 5)
        action = AllowActions()
        loop = _loop(boundary, recorder, actions=action, completion=NeverComplete(),
                     budget=LoopBudget(max_iterations=5, max_tool_calls=1))
        result = await _run(loop)
        assert result.stop_reason == StopReason.MAX_TOOL_CALLS
        assert len(action.executed) == 1  # the 2nd action never ran


# ======================================================================
# Part J — context contract on every model invocation
# ======================================================================

class TestContextContract:
    @pytest.mark.anyio
    async def test_model_span_carries_full_contract(self):
        boundary, recorder, _ = _boundary([VALID])
        _, span = await boundary.propose(
            schema=Proposal, system_prompt="s", prompt="p",
            mission_id="m-ctx", iteration=3, step_id="st-1",
            correlation_id="c-1", trace_id="t-1", trace_span_id="sp-1",
        )
        assert span.context_id  # present and non-empty
        assert span.schema_id and span.schema_id.startswith("Proposal+")
        assert span.harness_version == CURRENT_HARNESS_VERSION.identity
        assert span.mission_id == "m-ctx"
        assert span.iteration == 3
        assert span.step_id == "st-1"
        assert span.context_reconstructable is False  # not overclaimed

    @pytest.mark.anyio
    async def test_context_id_is_deterministic(self):
        """Same mission/iteration/step under the same harness version → same
        context id. Different iteration → different id."""
        b1, r1, _ = _boundary([VALID])
        _, s1 = await b1.propose(
            schema=Proposal, system_prompt="s", prompt="p",
            mission_id="m", iteration=1, step_id="st",
            correlation_id="c", trace_id="t", trace_span_id="sp",
        )
        b2, r2, _ = _boundary([VALID])
        _, s2 = await b2.propose(
            schema=Proposal, system_prompt="s", prompt="p",
            mission_id="m", iteration=1, step_id="st",
            correlation_id="c", trace_id="t", trace_span_id="sp",
        )
        b3, r3, _ = _boundary([VALID])
        _, s3 = await b3.propose(
            schema=Proposal, system_prompt="s", prompt="p",
            mission_id="m", iteration=2, step_id="st",
            correlation_id="c", trace_id="t", trace_span_id="sp",
        )
        assert s1.context_id == s2.context_id
        assert s1.context_id != s3.context_id

    def test_schema_identity_moves_with_the_schema(self):
        class A(BaseModel):
            x: str

        class B(BaseModel):
            x: str
            y: int

        assert schema_identity(A) != schema_identity(B)
        assert schema_identity(A) == schema_identity(A)


# ======================================================================
# Part K — harness identity integrity
# ======================================================================

class TestHarnessVersionIntegrity:
    @pytest.mark.parametrize("field", [
        "loop_policy", "schema_policy", "context_policy",
        "tool_exposure_policy", "budget_policy",
    ])
    def test_each_policy_change_changes_identity(self, field):
        base = CURRENT_HARNESS_VERSION
        changed = HarnessVersion(**{
            **{k: getattr(base, k) for k in (
                "release", "loop_policy", "schema_policy", "context_policy",
                "tool_exposure_policy", "budget_policy")},
            field: getattr(base, field) + "-mutated",
        })
        assert changed.identity != base.identity

    def test_version_is_immutable(self):
        with pytest.raises(Exception):
            CURRENT_HARNESS_VERSION.loop_policy = "evil"  # type: ignore[misc]

    def test_no_mutable_global_config(self):
        """The running harness carries exactly the version it was built with;
        there is no module-level setter to mutate."""
        import backend.harness.version as v

        assert not hasattr(v, "set_harness_version")
        assert not hasattr(v, "configure")

    @pytest.mark.anyio
    async def test_every_span_identifies_the_harness(self):
        boundary, recorder, _ = _boundary([VALID])
        loop = _loop(boundary, recorder)
        await _run(loop, mission_id="m-ver")
        for span in recorder.spans_for_mission("m-ver"):
            assert span.harness_version == CURRENT_HARNESS_VERSION.identity


# ======================================================================
# Part B — loop interruption (see also the crash/recovery real-process suite)
# ======================================================================

class InterruptingAction:
    """Raises CancelledError mid-iteration to simulate a graceful stop."""

    def __init__(self):
        self.executed = 0

    async def execute(self, proposal):
        self.executed += 1
        raise asyncio.CancelledError()


class TestLoopInterruption:
    @pytest.mark.anyio
    async def test_interruption_reraises_and_leaves_state_span(self):
        """Interruption is never swallowed: it re-raises, and a loop_state span
        is left behind for recovery (the harness performs no side effect of its
        own — the action port does, through the governed gateway)."""
        boundary, recorder, _ = _boundary([VALID])
        loop = _loop(boundary, recorder, actions=InterruptingAction())
        with pytest.raises(asyncio.CancelledError):
            await _run(loop, mission_id="m-int")
        kinds = [s.kind for s in recorder.spans_for_mission("m-int")]
        assert "loop_state" in kinds
        # No completion was fabricated.
        states = [s for s in recorder.spans_for_mission("m-int")
                  if s.kind == "loop_state"]
        assert states[-1].detail.get("completed") is False

    @pytest.mark.anyio
    async def test_interruption_before_model_call_performs_nothing(self):
        """A zero-iteration budget stops before the first model call — the
        cleanest 'interruption before model' case."""
        boundary, recorder, port = _boundary([VALID])
        loop = _loop(boundary, recorder,
                     budget=LoopBudget(max_iterations=0, max_tool_calls=0))
        result = await _run(loop)
        assert result.stop_reason == StopReason.MAX_ITERATIONS
        assert port.calls == 0
