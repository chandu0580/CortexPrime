from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.ai.models import (
    AIContext,
    AIExecutionPlan,
    AIRequest,
    AIResponse,
    AIRequestStatus,
    ExecutionMode,
    IntentType,
    PlanStep,
    PlanStepStatus,
    RuntimeTarget,
)
from backend.ai.orchestrator import AIOrchestrator


@pytest.fixture
def mock_classifier():
    c = MagicMock()
    c.classify_with_confidence = MagicMock(return_value=(IntentType.QUESTION, 0.8))
    return c


@pytest.fixture
def mock_router():
    r = MagicMock()
    r.route = MagicMock(return_value=[])
    r.route_summary = MagicMock(return_value=[])
    return r


@pytest.fixture
def mock_planner():
    p = MagicMock()
    p.create_plan = AsyncMock(return_value=AIExecutionPlan(
        plan_id="plan-test",
        request_id="ai-test",
        mode=ExecutionMode.SEQUENTIAL,
        steps=[
            PlanStep(name="step1", runtime=RuntimeTarget.KNOWLEDGE, action="search", timeout_seconds=10.0),
        ],
    ))
    return p


@pytest.fixture
def mock_invoker():
    i = MagicMock()
    i.invoke_sequential = AsyncMock(return_value=[{"runtime": "knowledge", "status": "simulated"}])
    i.invoke_parallel = AsyncMock(return_value=[{"runtime": "knowledge", "status": "simulated"}])
    return i


@pytest.fixture
def mock_events():
    e = MagicMock()
    e.publish_requested = AsyncMock()
    e.publish_planned = AsyncMock()
    e.publish_runtime_selected = AsyncMock()
    e.publish_completed = AsyncMock()
    e.publish_failed = AsyncMock()
    e.publish_cancelled = AsyncMock()
    e.publish_reasoning = AsyncMock()
    return e


@pytest.fixture
def orchestrator(mock_classifier, mock_router, mock_planner, mock_invoker, mock_events):
    return AIOrchestrator(
        classifier=mock_classifier,
        router=mock_router,
        planner=mock_planner,
        invoker=mock_invoker,
        events=mock_events,
    )


@pytest.mark.asyncio
async def test_handle_request_success(orchestrator, mock_events):
    response = await orchestrator.handle_request("what is the status?", AIContext())
    assert isinstance(response, AIResponse)
    assert response.status in (AIRequestStatus.COMPLETED, AIRequestStatus.COMPLETED.value)
    assert response.intent == IntentType.QUESTION
    assert mock_events.publish_requested.called
    assert mock_events.publish_reasoning.called
    assert mock_events.publish_completed.called


@pytest.mark.asyncio
async def test_handle_request_with_fallback(orchestrator, mock_router, mock_planner):
    mock_router.route.return_value = []
    mock_planner.create_plan.return_value = AIExecutionPlan(
        plan_id="plan-fallback",
        request_id="ai-fallback",
        steps=[],
    )
    response = await orchestrator.handle_request("gibberish xyzzy", AIContext())
    assert isinstance(response, AIResponse)
    assert response.status in (AIRequestStatus.COMPLETED, AIRequestStatus.COMPLETED.value)


@pytest.mark.asyncio
async def test_process_plan(orchestrator, mock_invoker):
    plan = AIExecutionPlan(
        plan_id="plan-proc",
        request_id="ai-proc",
        steps=[
            PlanStep(name="s1", runtime=RuntimeTarget.KNOWLEDGE, action="search", timeout_seconds=10.0),
        ],
    )
    response = await orchestrator.process_plan(plan)
    assert isinstance(response, AIResponse)
    assert mock_invoker.invoke_sequential.called


@pytest.mark.asyncio
async def test_execute_sequential_mode(orchestrator, mock_planner):
    mock_planner.create_plan.return_value = AIExecutionPlan(
        plan_id="plan-seq",
        request_id="ai-seq",
        mode=ExecutionMode.SEQUENTIAL,
        steps=[
            PlanStep(name="s1", runtime=RuntimeTarget.KNOWLEDGE, timeout_seconds=10.0),
            PlanStep(name="s2", runtime=RuntimeTarget.LEARNING, timeout_seconds=10.0),
        ],
    )
    response = await orchestrator.handle_request("analyze this")
    assert response.status in (AIRequestStatus.COMPLETED, AIRequestStatus.COMPLETED.value)


@pytest.mark.asyncio
async def test_execute_parallel_mode(orchestrator, mock_planner, mock_invoker):
    mock_planner.create_plan.return_value = AIExecutionPlan(
        plan_id="plan-par",
        request_id="ai-par",
        mode=ExecutionMode.PARALLEL,
        steps=[
            PlanStep(name="p1", runtime=RuntimeTarget.KNOWLEDGE, timeout_seconds=10.0),
            PlanStep(name="p2", runtime=RuntimeTarget.LEARNING, timeout_seconds=10.0),
        ],
    )
    response = await orchestrator.handle_request("analyze this")
    assert response.status in (AIRequestStatus.COMPLETED, AIRequestStatus.COMPLETED.value)


@pytest.mark.asyncio
async def test_handle_request_failure(orchestrator, mock_invoker):
    mock_invoker.invoke_sequential.return_value = [{"error": "runtime failure"}]
    mock_invoker.invoke_sequential.side_effect = None

    class FailingStep(PlanStep):
        pass

    step = PlanStep(
        name="fail step",
        runtime=RuntimeTarget.EXECUTION,
        timeout_seconds=5.0,
    )
    step.status = PlanStepStatus.FAILED
    step.error = "runtime failure"

    orchestrator._planner.create_plan.return_value = AIExecutionPlan(
        plan_id="plan-fail",
        request_id="ai-fail",
        steps=[step],
    )
    response = await orchestrator.handle_request("execute this mission")
    assert response.status == AIRequestStatus.FAILED or response.error is not None


@pytest.mark.asyncio
async def test_classify_called(orchestrator, mock_classifier):
    await orchestrator.handle_request("what is the status?")
    mock_classifier.classify_with_confidence.assert_called_once()


@pytest.mark.asyncio
async def test_route_called(orchestrator, mock_router, mock_classifier):
    mock_classifier.classify_with_confidence.return_value = (IntentType.MISSION_REQUEST, 0.9)
    mock_router.route.return_value = []
    await orchestrator.handle_request("create a mission")
    mock_router.route.assert_called_once_with(IntentType.MISSION_REQUEST)


@pytest.mark.asyncio
async def test_plan_contains_trace(orchestrator):
    response = await orchestrator.handle_request("analyze the system", AIContext())
    assert response.trace is not None
    assert len(response.trace.steps) >= 1
    assert response.trace.request_id == response.request_id


@pytest.mark.asyncio
async def test_events_published(orchestrator, mock_events):
    await orchestrator.handle_request("recommend improvements", AIContext())
    assert mock_events.publish_requested.called
    assert mock_events.publish_reasoning.called
