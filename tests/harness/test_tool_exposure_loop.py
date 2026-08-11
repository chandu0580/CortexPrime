"""Phase 6.3 — the loop under a tool exposure policy: attribution completeness
(Part E, tools-available on the model span) and tool-boundary enforcement
(Part I, resolution before governance)."""

from __future__ import annotations

import pytest

from backend.harness.llm_boundary import (
    GovernedModelBoundary,
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
from backend.harness.tool_exposure import (
    ArgKind,
    ArgSpec,
    ExposedTool,
    ResolvedTool,
    ToolExposurePolicy,
    ToolProposal,
)
from backend.harness.trace import InMemoryTraceRecorder
from backend.harness.version import CURRENT_HARNESS_VERSION


POLICY = ToolExposurePolicy((
    ExposedTool(
        name="create_widget", provider="controlled", operation="widget.create",
        arguments=(ArgSpec("name", ArgKind.STRING, required=True, max_length=80),),
    ),
    ExposedTool(
        name="get_widget", provider="controlled", operation="widget.get",
        arguments=(ArgSpec("widget_id", ArgKind.STRING, required=True, max_length=40),),
    ),
))


class ScriptedPort:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = 0

    async def generate(self, *, system_prompt: str, prompt: str) -> ModelInvocation:
        self.calls += 1
        content = self._outputs.pop(0) if self._outputs else "{}"
        return ModelInvocation(content=content, provider="scripted",
                               model="scripted-1", latency_ms=1.0,
                               usage=TokenUsage(10, 10))


class RecordingAction:
    def __init__(self):
        self.seen = []

    async def execute(self, action_input):
        self.seen.append(action_input)
        return ActionOutcome(performed=True, refused=False,
                             detail={"provider": getattr(action_input, "provider", None),
                                     "operation": getattr(action_input, "operation", None)})


class ObserveComplete:
    async def observe(self, proposal, outcome):
        return Observation(observed=True, detail={"ok": True})


class Complete:
    def is_complete(self, observation) -> bool:
        return True


class NeverComplete:
    def is_complete(self, observation) -> bool:
        return False


def _loop(outputs, action=None, completion=None, budget=None, recorder=None):
    recorder = recorder or InMemoryTraceRecorder()
    boundary = GovernedModelBoundary(
        model_port=ScriptedPort(outputs), recorder=recorder,
        harness_version=CURRENT_HARNESS_VERSION,
    )
    loop = HarnessLoop(
        boundary=boundary, action_port=action or RecordingAction(),
        observation_port=ObserveComplete(), completion_port=completion or Complete(),
        recorder=recorder, harness_version=CURRENT_HARNESS_VERSION,
        budget=budget or LoopBudget(),
        proposal_schema=ToolProposal, tool_exposure=POLICY,
    )
    return loop, recorder


async def _run(loop, mission_id="m"):
    return await loop.run(
        mission_id=mission_id, system_prompt="s",
        build_prompt=lambda i, obs: f"iter {i}",
        correlation_id="c", trace_id="t", span_id="sp",
    )


CREATE = '{"tool": "create_widget", "arguments": {"name": "w"}, "reason": "make it"}'


class TestAttributionToolsAvailable:
    @pytest.mark.anyio
    async def test_model_span_records_tools_available(self):
        loop, recorder = _loop([CREATE])
        await _run(loop, mission_id="m-tools")
        model_spans = [s for s in recorder.spans_for_mission("m-tools")
                       if s.kind == "model_proposal"]
        assert model_spans
        assert model_spans[0].tools_available == ("create_widget", "get_widget")

    @pytest.mark.anyio
    async def test_governed_action_records_resolved_provider_operation(self):
        action = RecordingAction()
        loop, recorder = _loop([CREATE], action=action)
        await _run(loop, mission_id="m-res")
        # The action port received a ResolvedTool with the DEPLOYMENT's values.
        assert len(action.seen) == 1
        assert isinstance(action.seen[0], ResolvedTool)
        assert action.seen[0].provider == "controlled"
        assert action.seen[0].operation == "widget.create"
        ga = [s for s in recorder.spans_for_mission("m-res")
              if s.kind == "governed_action"][0]
        assert ga.tool_call["resolved_provider"] == "controlled"
        assert ga.tool_call["resolved_operation"] == "widget.create"


class TestToolBoundaryInLoop:
    @pytest.mark.anyio
    async def test_unknown_tool_refused_before_action(self):
        action = RecordingAction()
        loop, recorder = _loop(
            ['{"tool": "delete_everything", "arguments": {}, "reason": "x"}'],
            action=action)
        result = await _run(loop)
        assert result.stop_reason == StopReason.TOOL_REFUSED
        assert action.seen == []  # nothing governed ran

    @pytest.mark.anyio
    async def test_smuggled_provider_operation_ignored(self):
        """A model naming its own provider/operation is ignored — the resolved
        values come from the registry."""
        action = RecordingAction()
        loop, _ = _loop(
            ['{"tool": "create_widget", "provider": "aws", '
             '"operation": "iam.create_admin", "arguments": {"name": "w"}}'],
            action=action)
        await _run(loop)
        assert action.seen[0].provider == "controlled"  # not aws
        assert action.seen[0].operation == "widget.create"

    @pytest.mark.anyio
    async def test_undeclared_argument_refused(self):
        action = RecordingAction()
        loop, _ = _loop(
            ['{"tool": "get_widget", "arguments": {"widget_id": "w1", '
             '"sql": "DROP TABLE"}, "reason": "x"}'], action=action)
        result = await _run(loop)
        assert result.stop_reason == StopReason.TOOL_REFUSED
        assert action.seen == []

    @pytest.mark.anyio
    async def test_shell_and_url_and_code_are_just_unknown_tools(self):
        for payload in (
            '{"tool": "bash", "arguments": {"cmd": "rm -rf /"}}',
            '{"tool": "http://evil.example/x", "arguments": {}}',
            '{"tool": "importlib.import_module", "arguments": {}}',
            '{"tool": "__import__", "arguments": {}}',
        ):
            action = RecordingAction()
            loop, _ = _loop([payload], action=action)
            result = await _run(loop)
            assert result.stop_reason == StopReason.TOOL_REFUSED, payload
            assert action.seen == [], payload

    @pytest.mark.anyio
    async def test_missing_required_argument_refused(self):
        action = RecordingAction()
        loop, _ = _loop(['{"tool": "get_widget", "arguments": {}}'], action=action)
        result = await _run(loop)
        assert result.stop_reason == StopReason.TOOL_REFUSED
        assert action.seen == []

    @pytest.mark.anyio
    async def test_non_json_still_invalid_output(self):
        action = RecordingAction()
        loop, _ = _loop(["not json at all"], action=action)
        result = await _run(loop)
        assert result.stop_reason == StopReason.INVALID_MODEL_OUTPUT
        assert action.seen == []

    @pytest.mark.anyio
    async def test_tool_refusal_recorded_on_span(self):
        loop, recorder = _loop(
            ['{"tool": "nope", "arguments": {}}'])
        await _run(loop, mission_id="m-ref")
        ga = [s for s in recorder.spans_for_mission("m-ref")
              if s.kind == "governed_action"]
        assert ga and ga[0].tool_call["resolved"] is False
        assert any("tool_refused" in d for d in ga[0].gate_decisions)
