from __future__ import annotations

import asyncio
import pytest

from backend.ai.invoker import RuntimeInvoker
from backend.ai.models import PlanStep, PlanStepStatus, RuntimeTarget


@pytest.fixture
def invoker():
    return RuntimeInvoker()


@pytest.mark.asyncio
async def test_invoke_step_success(invoker):
    step = PlanStep(
        name="test step",
        runtime=RuntimeTarget.KNOWLEDGE,
        action="search",
        timeout_seconds=5.0,
    )
    result = await invoker.invoke_step(step)
    assert result["runtime"] == "knowledge"
    assert step.status == PlanStepStatus.COMPLETED


@pytest.mark.asyncio
async def test_invoke_step_timeout(invoker):
    async def slow_handler(step):
        await asyncio.sleep(10)
        return {"done": True}

    invoker.register_handler(RuntimeTarget.KNOWLEDGE, slow_handler)
    step = PlanStep(
        name="slow step",
        runtime=RuntimeTarget.KNOWLEDGE,
        timeout_seconds=0.1,
    )
    result = await invoker.invoke_step(step)
    assert "error" in result
    assert "timed out" in result["error"].lower()
    assert step.status == PlanStepStatus.FAILED


@pytest.mark.asyncio
async def test_invoke_step_error(invoker):
    async def failing_handler(step):
        raise ValueError("handler error")

    invoker.register_handler(RuntimeTarget.EXECUTION, failing_handler)
    step = PlanStep(
        name="failing step",
        runtime=RuntimeTarget.EXECUTION,
        timeout_seconds=5.0,
    )
    result = await invoker.invoke_step(step)
    assert "error" in result
    assert step.status == PlanStepStatus.FAILED


@pytest.mark.asyncio
async def test_invoke_sequential(invoker):
    steps = [
        PlanStep(name="step1", runtime=RuntimeTarget.KNOWLEDGE, order=1, timeout_seconds=5.0),
        PlanStep(name="step2", runtime=RuntimeTarget.LEARNING, order=2, timeout_seconds=5.0),
    ]
    results = await invoker.invoke_sequential(steps)
    assert len(results) == 2
    assert all(s.status == PlanStepStatus.COMPLETED for s in steps)


@pytest.mark.asyncio
async def test_invoke_sequential_stops_on_failure(invoker):
    async def fail_handler(step):
        raise RuntimeError("step failed")

    invoker.register_handler(RuntimeTarget.EXECUTION, fail_handler)
    steps = [
        PlanStep(name="step1", runtime=RuntimeTarget.KNOWLEDGE, order=1, timeout_seconds=5.0),
        PlanStep(name="step2", runtime=RuntimeTarget.EXECUTION, order=2, timeout_seconds=5.0),
        PlanStep(name="step3", runtime=RuntimeTarget.LEARNING, order=3, timeout_seconds=5.0),
    ]
    results = await invoker.invoke_sequential(steps)
    assert len(results) == 2
    assert steps[0].status == PlanStepStatus.COMPLETED
    assert steps[1].status == PlanStepStatus.FAILED
    assert steps[2].status == PlanStepStatus.PENDING


@pytest.mark.asyncio
async def test_invoke_parallel(invoker):
    steps = [
        PlanStep(name="p1", runtime=RuntimeTarget.KNOWLEDGE, order=1, timeout_seconds=5.0),
        PlanStep(name="p2", runtime=RuntimeTarget.LEARNING, order=2, timeout_seconds=5.0),
        PlanStep(name="p3", runtime=RuntimeTarget.MISSION, order=3, timeout_seconds=5.0),
    ]
    results = await invoker.invoke_parallel(steps)
    assert len(results) == 3
    assert all(s.status == PlanStepStatus.COMPLETED for s in steps)


@pytest.mark.asyncio
async def test_cancel_step(invoker):
    step = PlanStep(name="cancel test", runtime=RuntimeTarget.AI, timeout_seconds=5.0)
    assert step.status == PlanStepStatus.PENDING
    await invoker.cancel_step(step)
    assert step.status == PlanStepStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_running_step(invoker):
    step = PlanStep(name="running step", runtime=RuntimeTarget.AI, timeout_seconds=5.0)
    step.status = PlanStepStatus.RUNNING
    await invoker.cancel_step(step)
    assert step.status == PlanStepStatus.CANCELLED


@pytest.mark.asyncio
async def test_all_runtimes_have_default_handlers(invoker):
    for rt in RuntimeTarget:
        step = PlanStep(name=f"test {rt.value}", runtime=rt, timeout_seconds=5.0)
        result = await invoker.invoke_step(step)
        short_name = rt.value.replace("_runtime", "")
        assert result["runtime"] == short_name
        assert step.status == PlanStepStatus.COMPLETED


@pytest.mark.asyncio
async def test_custom_handler_registration(invoker):
    async def custom_handler(step):
        return {"custom": True, "value": 42}

    invoker.register_handler(RuntimeTarget.AI, custom_handler)
    step = PlanStep(name="custom", runtime=RuntimeTarget.AI, timeout_seconds=5.0)
    result = await invoker.invoke_step(step)
    assert result["custom"] is True
    assert result["value"] == 42
