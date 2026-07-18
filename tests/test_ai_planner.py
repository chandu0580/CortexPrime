from __future__ import annotations

import pytest

from backend.ai.models import AIRequest, AIRequestStatus, ExecutionMode, IntentType, PlanStepStatus, RuntimeTarget
from backend.ai.planner import AIRulePlanner
from backend.ai.router import RuntimeRouter


@pytest.fixture
def planner():
    return AIRulePlanner(router=RuntimeRouter())


@pytest.mark.asyncio
async def test_create_plan_mission_request(planner):
    request = AIRequest(prompt="create a new mission to deploy the app", intent=IntentType.MISSION_REQUEST)
    plan = await planner.create_plan(request)
    assert plan.request_id == request.id
    assert len(plan.steps) >= 1
    assert plan.status == AIRequestStatus.PLANNED
    assert plan.steps[0].runtime == RuntimeTarget.MISSION


@pytest.mark.asyncio
async def test_create_plan_question(planner):
    request = AIRequest(prompt="what is the system status?", intent=IntentType.QUESTION)
    plan = await planner.create_plan(request)
    assert len(plan.steps) >= 1
    assert plan.steps[0].runtime == RuntimeTarget.KNOWLEDGE


@pytest.mark.asyncio
async def test_create_plan_analysis(planner):
    request = AIRequest(prompt="analyze the failure rate", intent=IntentType.ANALYSIS)
    plan = await planner.create_plan(request)
    assert len(plan.steps) >= 1
    assert plan.steps[0].runtime == RuntimeTarget.KNOWLEDGE


@pytest.mark.asyncio
async def test_create_plan_investigation(planner):
    request = AIRequest(prompt="investigate why it failed", intent=IntentType.INVESTIGATION)
    plan = await planner.create_plan(request)
    assert len(plan.steps) >= 1
    assert plan.steps[0].runtime == RuntimeTarget.EXECUTION


@pytest.mark.asyncio
async def test_create_plan_automation(planner):
    request = AIRequest(prompt="automate the backup process", intent=IntentType.AUTOMATION)
    plan = await planner.create_plan(request)
    assert len(plan.steps) >= 1
    assert plan.steps[0].runtime == RuntimeTarget.CONNECTOR


@pytest.mark.asyncio
async def test_create_plan_recommendation(planner):
    request = AIRequest(prompt="recommend improvements", intent=IntentType.RECOMMENDATION)
    plan = await planner.create_plan(request)
    assert len(plan.steps) >= 1
    assert plan.steps[0].runtime == RuntimeTarget.LEARNING


@pytest.mark.asyncio
async def test_create_plan_conversation(planner):
    request = AIRequest(prompt="hello", intent=IntentType.CONVERSATION)
    plan = await planner.create_plan(request)
    assert len(plan.steps) >= 1


@pytest.mark.asyncio
async def test_create_plan_tool_invocation(planner):
    request = AIRequest(prompt="call the github api", intent=IntentType.TOOL_INVOCATION)
    plan = await planner.create_plan(request)
    assert len(plan.steps) >= 1
    assert plan.steps[0].runtime == RuntimeTarget.CONNECTOR


@pytest.mark.asyncio
async def test_plan_dependency_ordering(planner):
    request = AIRequest(prompt="analyze mission performance", intent=IntentType.ANALYSIS)
    plan = await planner.create_plan(request)
    for i in range(1, len(plan.steps)):
        assert plan.steps[i].depends_on == [plan.steps[i - 1].step_id]


@pytest.mark.asyncio
async def test_plan_mode_analysis_is_parallel(planner):
    request = AIRequest(prompt="analyze the system", intent=IntentType.ANALYSIS)
    plan = await planner.create_plan(request)
    assert plan.mode == ExecutionMode.PARALLEL


@pytest.mark.asyncio
async def test_plan_mode_mission_is_sequential(planner):
    request = AIRequest(prompt="create a mission", intent=IntentType.MISSION_REQUEST)
    plan = await planner.create_plan(request)
    assert plan.mode == ExecutionMode.SEQUENTIAL


@pytest.mark.asyncio
async def test_plan_steps_have_timeouts(planner):
    request = AIRequest(prompt="investigate the issue", intent=IntentType.INVESTIGATION)
    plan = await planner.create_plan(request)
    for step in plan.steps:
        assert step.timeout_seconds > 0


@pytest.mark.asyncio
async def test_plan_steps_have_actions(planner):
    request = AIRequest(prompt="create a new mission", intent=IntentType.MISSION_REQUEST)
    plan = await planner.create_plan(request)
    for step in plan.steps:
        assert step.action is not None
        assert step.action != ""
