"""Phase 6.1 harness spine — unit evidence (Levels 2 + 4).

Proves: budgets stop the loop *before* spending; every stop reason is typed;
invalid model output cannot reach execution; governance refusal stops the
loop; the model cannot declare completion; traces are redacted and carry the
harness version; changing a harness policy changes the version identity.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from backend.harness.llm_boundary import (
    GovernedModelBoundary,
    InvalidModelOutput,
    ModelInvocation,
    TokenUsage,
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


class RestartProposal(BaseModel):
    action: str
    container: str
    reason: str


class ScriptedPort:
    """A scripted model port. Every span it produces names it as the provider,
    so scripted evidence cannot masquerade as a real model run."""

    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = 0

    async def generate(self, *, system_prompt: str, prompt: str) -> ModelInvocation:
        self.calls += 1
        if not self._outputs:
            raise AssertionError("scripted port exhausted")
        content = self._outputs.pop(0)
        return ModelInvocation(
            content=content,
            provider="scripted",
            model="scripted-1",
            latency_ms=1.0,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50),
        )


VALID = '{"action": "restart_container", "container": "scratch", "reason": "test"}'


def make_boundary(outputs, recorder=None):
    recorder = recorder or InMemoryTraceRecorder()
    port = ScriptedPort(outputs)
    boundary = GovernedModelBoundary(
        model_port=port,
        recorder=recorder,
        harness_version=CURRENT_HARNESS_VERSION,
    )
    return boundary, recorder, port


class AllowActions:
    def __init__(self):
        self.executed = []

    async def execute(self, proposal):
        self.executed.append(proposal)
        return ActionOutcome(performed=True, refused=False)


class RefuseActions:
    async def execute(self, proposal):
        return ActionOutcome(
            performed=False, refused=True, refusal_stage="authorization"
        )


class ObserveRunning:
    def __init__(self, complete_after: int = 1):
        self.calls = 0
        self._complete_after = complete_after

    async def observe(self, proposal, outcome):
        self.calls += 1
        return Observation(
            observed=True,
            detail={"status": "running", "call": self.calls},
        )


class CompleteAfter:
    def __init__(self, n: int):
        self.n = n
        self.checks = 0

    def is_complete(self, observation) -> bool:
        self.checks += 1
        return self.checks >= self.n


def make_loop(boundary, recorder, *, actions=None, observations=None,
              completion=None, budget=None):
    return HarnessLoop(
        boundary=boundary,
        action_port=actions or AllowActions(),
        observation_port=observations or ObserveRunning(),
        completion_port=completion or CompleteAfter(1),
        recorder=recorder,
        harness_version=CURRENT_HARNESS_VERSION,
        budget=budget or LoopBudget(),
        proposal_schema=RestartProposal,
    )


async def run_loop(loop, mission_id="m-test"):
    return await loop.run(
        mission_id=mission_id,
        system_prompt="You restart containers.",
        build_prompt=lambda i, obs: f"iteration {i}",
        correlation_id="corr-1",
        trace_id="trace-1",
        span_id="span-1",
    )


class TestSchemaValidation:
    @pytest.mark.anyio
    async def test_valid_output_parses(self):
        boundary, recorder, _ = make_boundary([VALID])
        proposal, span = await boundary.propose(
            schema=RestartProposal, system_prompt="s", prompt="p",
            mission_id="m", iteration=1, step_id="st",
            correlation_id="c", trace_id="t", trace_span_id="sp",
        )
        assert proposal.container == "scratch"
        assert span.harness_version == CURRENT_HARNESS_VERSION.identity

    @pytest.mark.anyio
    async def test_non_json_is_explicit_failure(self):
        boundary, recorder, _ = make_boundary(["I think we should restart it."])
        with pytest.raises(InvalidModelOutput):
            await boundary.propose(
                schema=RestartProposal, system_prompt="s", prompt="p",
                mission_id="m", iteration=1, step_id="st",
                correlation_id="c", trace_id="t", trace_span_id="sp",
            )
        # The failure is on the trace, not swallowed.
        assert recorder.spans[-1].stop_or_failure_reason is not None

    @pytest.mark.anyio
    async def test_schema_mismatch_is_explicit_failure(self):
        boundary, _, _ = make_boundary(['{"action": "restart_container"}'])
        with pytest.raises(InvalidModelOutput) as exc:
            await boundary.propose(
                schema=RestartProposal, system_prompt="s", prompt="p",
                mission_id="m", iteration=1, step_id="st",
                correlation_id="c", trace_id="t", trace_span_id="sp",
            )
        assert "RestartProposal" in exc.value.reason

    @pytest.mark.anyio
    async def test_fenced_json_unwraps_deterministically(self):
        boundary, _, _ = make_boundary([f"```json\n{VALID}\n```"])
        proposal, _ = await boundary.propose(
            schema=RestartProposal, system_prompt="s", prompt="p",
            mission_id="m", iteration=1, step_id="st",
            correlation_id="c", trace_id="t", trace_span_id="sp",
        )
        assert proposal.action == "restart_container"

    @pytest.mark.anyio
    async def test_two_json_objects_fail_rather_than_guess(self):
        boundary, _, _ = make_boundary([VALID + "\n" + VALID])
        with pytest.raises(InvalidModelOutput):
            await boundary.propose(
                schema=RestartProposal, system_prompt="s", prompt="p",
                mission_id="m", iteration=1, step_id="st",
                correlation_id="c", trace_id="t", trace_span_id="sp",
            )


class TestLoopStopReasons:
    @pytest.mark.anyio
    async def test_completes_via_deterministic_check(self):
        boundary, recorder, _ = make_boundary([VALID])
        loop = make_loop(boundary, recorder, completion=CompleteAfter(1))
        result = await run_loop(loop)
        assert result.stop_reason == StopReason.COMPLETED
        assert result.completed

    @pytest.mark.anyio
    async def test_model_cannot_declare_completion(self):
        """A proposal claiming success does not end the mission; only the
        completion port does — here it never passes, so iterations exhaust."""
        done_claim = '{"action": "restart_container", "container": "scratch", "reason": "ALL DONE, mission successful!"}'
        boundary, recorder, _ = make_boundary([done_claim] * 3)
        loop = make_loop(
            boundary, recorder,
            completion=CompleteAfter(999),
            budget=LoopBudget(max_iterations=3, max_tool_calls=10),
        )
        result = await run_loop(loop)
        assert result.stop_reason == StopReason.MAX_ITERATIONS
        assert not result.completed

    @pytest.mark.anyio
    async def test_invalid_output_stops_and_never_executes(self):
        boundary, recorder, _ = make_boundary(["not json"])
        actions = AllowActions()
        loop = make_loop(boundary, recorder, actions=actions)
        result = await run_loop(loop)
        assert result.stop_reason == StopReason.INVALID_MODEL_OUTPUT
        assert actions.executed == []

    @pytest.mark.anyio
    async def test_governance_refusal_stops(self):
        boundary, recorder, _ = make_boundary([VALID])
        loop = make_loop(boundary, recorder, actions=RefuseActions())
        result = await run_loop(loop)
        assert result.stop_reason == StopReason.GOVERNANCE_REFUSED
        assert result.failure == "authorization"

    @pytest.mark.anyio
    async def test_iteration_budget_stops_before_model_call(self):
        boundary, recorder, port = make_boundary([VALID] * 10)
        loop = make_loop(
            boundary, recorder,
            completion=CompleteAfter(999),
            budget=LoopBudget(max_iterations=2, max_tool_calls=10),
        )
        result = await run_loop(loop)
        assert result.stop_reason == StopReason.MAX_ITERATIONS
        assert result.iterations_run == 2
        assert port.calls == 2  # the third model call never happened

    @pytest.mark.anyio
    async def test_token_budget_stops_before_next_iteration(self):
        boundary, recorder, port = make_boundary([VALID] * 10)
        # Each scripted call spends 150 tokens; budget of 150 allows exactly one.
        loop = make_loop(
            boundary, recorder,
            completion=CompleteAfter(999),
            budget=LoopBudget(max_iterations=10, max_total_tokens=150),
        )
        result = await run_loop(loop)
        assert result.stop_reason == StopReason.TOKEN_BUDGET_EXHAUSTED
        assert port.calls == 1

    @pytest.mark.anyio
    async def test_wall_clock_budget(self):
        boundary, recorder, _ = make_boundary([VALID] * 10)
        loop = make_loop(
            boundary, recorder,
            completion=CompleteAfter(999),
            budget=LoopBudget(max_iterations=10, max_wall_clock_seconds=0.0),
        )
        result = await run_loop(loop)
        assert result.stop_reason == StopReason.WALL_CLOCK_EXHAUSTED

    @pytest.mark.anyio
    async def test_every_run_leaves_a_loop_state_span(self):
        boundary, recorder, _ = make_boundary(["not json"])
        loop = make_loop(boundary, recorder)
        await run_loop(loop, mission_id="m-state")
        kinds = [s.kind for s in recorder.spans_for_mission("m-state")]
        assert "loop_state" in kinds


class TestTraceEvidence:
    @pytest.mark.anyio
    async def test_secret_in_model_output_is_scrubbed(self):
        leaky = (
            '{"action": "restart_container", "container": "scratch", '
            '"reason": "token ghp_abcdefghijklmnopqrstuvwxyz012345 leaked"}'
        )
        boundary, recorder, _ = make_boundary([leaky])
        await boundary.propose(
            schema=RestartProposal, system_prompt="s", prompt="p",
            mission_id="m", iteration=1, step_id="st",
            correlation_id="c", trace_id="t", trace_span_id="sp",
        )
        span = recorder.spans[-1]
        assert "ghp_abcdefghijklmnopqrstuvwxyz012345" not in (span.output_redacted or "")

    @pytest.mark.anyio
    async def test_secret_in_prompt_never_reaches_port_or_trace(self):
        secret = "Authorization: Bearer sk-abcdef1234567890abcdef1234567890"
        captured = {}

        class CapturingPort(ScriptedPort):
            async def generate(self, *, system_prompt: str, prompt: str):
                captured["prompt"] = prompt
                return await super().generate(
                    system_prompt=system_prompt, prompt=prompt
                )

        recorder = InMemoryTraceRecorder()
        boundary = GovernedModelBoundary(
            model_port=CapturingPort([VALID]),
            recorder=recorder,
            harness_version=CURRENT_HARNESS_VERSION,
        )
        await boundary.propose(
            schema=RestartProposal, system_prompt="s",
            prompt=f"context: {secret}",
            mission_id="m", iteration=1, step_id="st",
            correlation_id="c", trace_id="t", trace_span_id="sp",
        )
        assert "sk-abcdef1234567890abcdef1234567890" not in captured["prompt"]
        assert "sk-abcdef1234567890abcdef1234567890" not in (
            recorder.spans[-1].prompt_redacted or ""
        )

    @pytest.mark.anyio
    async def test_spans_carry_version_and_correlation(self):
        boundary, recorder, _ = make_boundary([VALID])
        loop = make_loop(boundary, recorder)
        await run_loop(loop, mission_id="m-corr")
        for span in recorder.spans_for_mission("m-corr"):
            assert span.harness_version == CURRENT_HARNESS_VERSION.identity
            assert span.correlation_id == "corr-1"

    @pytest.mark.anyio
    async def test_replayability_is_not_overclaimed(self):
        boundary, recorder, _ = make_boundary([VALID])
        await boundary.propose(
            schema=RestartProposal, system_prompt="s", prompt="p",
            mission_id="m", iteration=1, step_id="st",
            correlation_id="c", trace_id="t", trace_span_id="sp",
        )
        assert recorder.spans[-1].context_reconstructable is False


class TestHarnessVersion:
    def test_identity_is_stable(self):
        a = CURRENT_HARNESS_VERSION.identity
        b = CURRENT_HARNESS_VERSION.identity
        assert a == b

    def test_policy_change_changes_identity(self):
        changed = HarnessVersion(
            release=CURRENT_HARNESS_VERSION.release,
            loop_policy="loop/budgeted-stop-reasons/2",
            schema_policy=CURRENT_HARNESS_VERSION.schema_policy,
            context_policy=CURRENT_HARNESS_VERSION.context_policy,
            tool_exposure_policy=CURRENT_HARNESS_VERSION.tool_exposure_policy,
            budget_policy=CURRENT_HARNESS_VERSION.budget_policy,
        )
        assert changed.identity != CURRENT_HARNESS_VERSION.identity

    def test_version_is_immutable(self):
        with pytest.raises(Exception):
            CURRENT_HARNESS_VERSION.release = "evil"  # type: ignore[misc]
