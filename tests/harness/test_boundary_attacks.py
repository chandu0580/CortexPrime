"""Phase 6.3 — model-boundary (Part H), tool-boundary extras (Part I),
budget integration (Part J), and loop-level failure injection (Part L).

The live-path versions run in scripts/phase63_integration_harness.py; these
pin the semantics deterministically at the loop level."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from backend.harness.llm_boundary import (
    GovernedModelBoundary, ModelInvocation, TokenUsage,
)
from backend.harness.loop import (
    ActionOutcome, HarnessLoop, LoopBudget, Observation, StopReason,
)
from backend.harness.tool_exposure import (
    ArgKind, ArgSpec, ExposedTool, ResolvedTool, ToolExposurePolicy, ToolProposal,
)
from backend.harness.trace import InMemoryTraceRecorder
from backend.harness.version import CURRENT_HARNESS_VERSION


POLICY = ToolExposurePolicy((
    ExposedTool(name="do_it", provider="controlled", operation="widget.create",
                arguments=(ArgSpec("name", ArgKind.STRING, required=True),)),
))
DO_IT = '{"tool": "do_it", "arguments": {"name": "w"}}'


class ScriptedPort:
    def __init__(self, outputs):
        self._outputs = list(outputs)

    async def generate(self, *, system_prompt: str, prompt: str) -> ModelInvocation:
        content = self._outputs.pop(0) if self._outputs else DO_IT
        return ModelInvocation(content=content, provider="scripted",
                               model="scripted-1", latency_ms=1.0,
                               usage=TokenUsage(10, 10))


def _loop(outputs, *, action, observation, completion, budget=None,
          tool_exposure=POLICY, schema=ToolProposal):
    recorder = InMemoryTraceRecorder()
    boundary = GovernedModelBoundary(
        model_port=ScriptedPort(outputs), recorder=recorder,
        harness_version=CURRENT_HARNESS_VERSION)
    loop = HarnessLoop(
        boundary=boundary, action_port=action, observation_port=observation,
        completion_port=completion, recorder=recorder,
        harness_version=CURRENT_HARNESS_VERSION, budget=budget or LoopBudget(),
        proposal_schema=schema, tool_exposure=tool_exposure)
    return loop, recorder


async def _run(loop, mission_id="m"):
    return await loop.run(mission_id=mission_id, system_prompt="s",
                          build_prompt=lambda i, obs: "p",
                          correlation_id="c", trace_id="t", span_id="sp")


class PerformedAction:
    async def execute(self, x):
        return ActionOutcome(performed=True, refused=False)


class NotPerformedAction:
    """The provider evidence is absent: the action did not perform."""
    async def execute(self, x):
        return ActionOutcome(performed=False, refused=False, failure="no_effect")


class ObserveYes:
    async def observe(self, p, o):
        return Observation(observed=True, detail={})


class ObserveNo:
    async def observe(self, p, o):
        return Observation(observed=False, detail={}, failure="not_observed")


class CompleteIfObserved:
    def is_complete(self, obs):
        return obs.observed


# ======================================================================
# Part H — model success claims are non-authoritative
# ======================================================================

class TestModelClaimsNonAuthoritative:
    @pytest.mark.anyio
    async def test_success_claim_but_provider_evidence_absent_is_not_success(self):
        """Model says success, but the action did not perform → NOT SUCCESS."""
        payload = '{"tool": "do_it", "arguments": {"name": "w"}, "success": true, "status": "completed"}'
        loop, _ = _loop([payload], action=NotPerformedAction(),
                        observation=ObserveYes(), completion=CompleteIfObserved())
        result = await _run(loop)
        assert not result.completed
        assert result.stop_reason == StopReason.ACTION_FAILED

    @pytest.mark.anyio
    async def test_verification_claim_but_observation_absent_is_not_verified(self):
        """Model says verification passed, but observation is absent → not
        complete (only the deterministic port reading a real observation can)."""
        payload = '{"tool": "do_it", "arguments": {"name": "w"}, "verification": "passed"}'
        loop, _ = _loop([payload] * 3, action=PerformedAction(),
                        observation=ObserveNo(), completion=CompleteIfObserved(),
                        budget=LoopBudget(max_iterations=3))
        result = await _run(loop)
        assert not result.completed
        assert result.stop_reason == StopReason.MAX_ITERATIONS

    @pytest.mark.anyio
    async def test_rollback_claim_but_observation_absent_is_not_verified(self):
        payload = '{"tool": "do_it", "arguments": {"name": "w"}, "rollback": "successful"}'
        loop, _ = _loop([payload] * 2, action=PerformedAction(),
                        observation=ObserveNo(), completion=CompleteIfObserved(),
                        budget=LoopBudget(max_iterations=2))
        result = await _run(loop)
        assert not result.completed


# ======================================================================
# Part I — tool-boundary: credential/tenant/capability fields are ignored
# ======================================================================

class TestToolBoundaryExtras:
    @pytest.mark.anyio
    async def test_credential_tenant_capability_fields_are_ignored(self):
        """A model output carrying credential/tenant/capability top-level keys
        resolves to the registry values; those keys are not in ToolProposal and
        never reach a provider selection."""
        captured = {}

        class Capturing:
            async def execute(self, resolved):
                captured["provider"] = resolved.provider
                captured["operation"] = resolved.operation
                captured["args"] = dict(resolved.arguments)
                return ActionOutcome(performed=True, refused=False)

        payload = (
            '{"tool": "do_it", "arguments": {"name": "w"}, '
            '"credential": "ghp_secret_leak", "tenant": "other-tenant", '
            '"capability": "platform.admin"}'
        )
        loop, recorder = _loop([payload], action=Capturing(),
                               observation=ObserveYes(), completion=CompleteIfObserved())
        await _run(loop, mission_id="m-extras")
        # Resolved to the deployment's values; the smuggled fields vanished.
        assert captured["provider"] == "controlled"
        assert captured["operation"] == "widget.create"
        assert "credential" not in captured["args"]
        assert "tenant" not in captured["args"]
        # And the credential string never reached the resolved arguments.
        assert "ghp_secret_leak" not in str(captured["args"])

    @pytest.mark.anyio
    async def test_hidden_operation_field_in_arguments_is_refused(self):
        payload = '{"tool": "do_it", "arguments": {"name": "w", "operation": "delete_all"}}'
        loop, _ = _loop([payload], action=PerformedAction(),
                        observation=ObserveYes(), completion=CompleteIfObserved())
        result = await _run(loop)
        assert result.stop_reason == StopReason.TOOL_REFUSED


# ======================================================================
# Part J — budget is hard across the whole loop
# ======================================================================

class TestBudgetIntegration:
    @pytest.mark.anyio
    async def test_repeated_actions_cannot_reset_the_loop_budget(self):
        """Every iteration performs, never completes; the iteration ceiling
        holds regardless of how many actions ran."""
        loop, _ = _loop([DO_IT] * 10, action=PerformedAction(),
                        observation=ObserveNo(), completion=CompleteIfObserved(),
                        budget=LoopBudget(max_iterations=3, max_tool_calls=10))
        result = await _run(loop)
        assert result.stop_reason == StopReason.MAX_ITERATIONS
        assert result.iterations_run == 3

    @pytest.mark.anyio
    async def test_token_budget_holds_across_iterations(self):
        loop, _ = _loop([DO_IT] * 10, action=PerformedAction(),
                        observation=ObserveNo(), completion=CompleteIfObserved(),
                        budget=LoopBudget(max_iterations=10, max_total_tokens=60))
        result = await _run(loop)
        # 20 tokens/iter; 60 allows exactly 3 before the pre-spend check stops.
        assert result.stop_reason == StopReason.TOKEN_BUDGET_EXHAUSTED
        assert result.tokens_spent <= 60 + 20  # never overspends past one iter


# ======================================================================
# Part L — loop-level failure injection (execution-level is the gateway's)
# ======================================================================

class TestFailureInjection:
    @pytest.mark.anyio
    async def test_model_validation_failure(self):
        loop, _ = _loop(["not json"], action=PerformedAction(),
                        observation=ObserveYes(), completion=CompleteIfObserved())
        result = await _run(loop)
        assert result.stop_reason == StopReason.INVALID_MODEL_OUTPUT

    @pytest.mark.anyio
    async def test_unknown_tool(self):
        loop, _ = _loop(['{"tool": "ghost", "arguments": {}}'],
                        action=PerformedAction(), observation=ObserveYes(),
                        completion=CompleteIfObserved())
        result = await _run(loop)
        assert result.stop_reason == StopReason.TOOL_REFUSED

    @pytest.mark.anyio
    async def test_governance_refusal(self):
        class Refuse:
            async def execute(self, x):
                return ActionOutcome(performed=False, refused=True,
                                     refusal_stage="authorization")
        loop, _ = _loop([DO_IT], action=Refuse(), observation=ObserveYes(),
                        completion=CompleteIfObserved())
        result = await _run(loop)
        assert result.stop_reason == StopReason.GOVERNANCE_REFUSED

    @pytest.mark.anyio
    async def test_trace_failure_is_fail_closed_before_action(self):
        class FailingRecorder:
            def record(self, span):
                raise RuntimeError("trace down")

        boundary = GovernedModelBoundary(
            model_port=ScriptedPort([DO_IT]), recorder=FailingRecorder(),
            harness_version=CURRENT_HARNESS_VERSION)
        ran = []

        class Watch:
            async def execute(self, x):
                ran.append(True)
                return ActionOutcome(performed=True, refused=False)

        loop = HarnessLoop(
            boundary=boundary, action_port=Watch(), observation_port=ObserveYes(),
            completion_port=CompleteIfObserved(), recorder=FailingRecorder(),
            harness_version=CURRENT_HARNESS_VERSION, budget=LoopBudget(),
            proposal_schema=ToolProposal, tool_exposure=POLICY)
        result = await _run(loop)
        assert result.stop_reason == StopReason.TRACE_WRITE_FAILED
        assert ran == []  # nothing acted — no side effect on a failure

    @pytest.mark.anyio
    async def test_no_failure_is_silently_converted_to_success(self):
        """Across every injected failure, completed is never True."""
        for outputs, action, obs in [
            (["bad"], PerformedAction(), ObserveYes()),
            (['{"tool": "x", "arguments": {}}'], PerformedAction(), ObserveYes()),
            ([DO_IT], NotPerformedAction(), ObserveYes()),
        ]:
            loop, _ = _loop(outputs, action=action, observation=obs,
                            completion=CompleteIfObserved(),
                            budget=LoopBudget(max_iterations=1))
            result = await _run(loop)
            assert not result.completed


def test_a_provider_failure_leaves_a_span_with_its_cause_and_still_raises():
    """Phase 11.4 run 9 (F-10): an unavailable provider raised before any span
    was built, so the one call that could not be made left no durable trace.
    The failure span carries the scrubbed cause and no output; the error still
    propagates, so a failed call never becomes a proposal."""
    import asyncio

    class Unavailable:
        _provider, _model = "openai-compatible", "glm-5.2"

        async def generate(self, *, system_prompt, prompt):
            raise RuntimeError("model call failed: upstream 502 api_key=sk-live-SHOULDNOTLEAK123456")

    recorder = InMemoryTraceRecorder()
    boundary = GovernedModelBoundary(model_port=Unavailable(), recorder=recorder,
                                     harness_version=CURRENT_HARNESS_VERSION)
    with pytest.raises(RuntimeError):
        asyncio.run(boundary.propose(schema=ToolProposal, system_prompt="s", prompt="p", mission_id="m",
                                     iteration=0, step_id="st", correlation_id="c", trace_id="t",
                                     trace_span_id="sp"))
    (span,) = recorder.spans
    reason = span.to_dict().get("stop_or_failure_reason") if hasattr(span, "to_dict") else span.stop_or_failure_reason
    assert "provider call failed" in reason and "upstream 502" in reason
    assert "SHOULDNOTLEAK" not in repr(span)
    assert span.model_provider == "openai-compatible"
