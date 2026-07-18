from __future__ import annotations

import asyncio
import pytest

from backend.ai.client import RuntimeInvocationClient
from backend.ai.context import RuntimeContext
from backend.ai.failure import FailureHandler, RetryPolicy
from backend.ai.integration import RuntimeIntegrationFactory
from backend.ai.models import PlanStep, PlanStepStatus, RuntimeTarget
from backend.ai.result import RuntimeResult


class TestRuntimeInvocationClient:
    @pytest.fixture
    def client(self):
        return RuntimeInvocationClient()

    @pytest.fixture
    def ctx(self):
        return RuntimeContext(tenant_id="test-tenant", user_id="test-user", correlation_id="test-corr")

    @pytest.mark.asyncio
    async def test_invoke_step_success(self, client, ctx):
        step = PlanStep(
            name="test step",
            runtime=RuntimeTarget.KNOWLEDGE,
            action="search",
            timeout_seconds=5.0,
        )
        result = await client.invoke_step(step, ctx)
        assert isinstance(result, RuntimeResult)
        assert result.runtime == RuntimeTarget.KNOWLEDGE
        assert result.is_success

    @pytest.mark.asyncio
    async def test_invoke_step_no_handler(self, client, ctx):
        step = PlanStep(
            name="unknown",
            runtime=RuntimeTarget.KNOWLEDGE,
            timeout_seconds=5.0,
        )
        result = await client.invoke_step(step, ctx)
        assert isinstance(result, RuntimeResult)

    @pytest.mark.asyncio
    async def test_invoke_parallel(self, client, ctx):
        steps = [
            PlanStep(name="p1", runtime=RuntimeTarget.KNOWLEDGE, order=1, timeout_seconds=5.0),
            PlanStep(name="p2", runtime=RuntimeTarget.LEARNING, order=2, timeout_seconds=5.0),
        ]
        results = await client.invoke_parallel(steps, ctx)
        assert len(results) == 2
        assert all(isinstance(r, RuntimeResult) for r in results)

    @pytest.mark.asyncio
    async def test_invoke_sequential(self, client, ctx):
        steps = [
            PlanStep(name="s1", runtime=RuntimeTarget.KNOWLEDGE, order=1, timeout_seconds=5.0),
            PlanStep(name="s2", runtime=RuntimeTarget.LEARNING, order=2, timeout_seconds=5.0),
        ]
        results = await client.invoke_sequential(steps, ctx)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_cancel_step(self, client, ctx):
        step = PlanStep(name="cancel test", runtime=RuntimeTarget.AI, timeout_seconds=5.0)
        assert step.status == PlanStepStatus.PENDING
        await client.cancel_step(step, ctx)
        assert step.status == PlanStepStatus.CANCELLED


class TestRuntimeInvocationClientWithFailure:
    @pytest.fixture
    def client(self):
        return RuntimeInvocationClient()

    @pytest.fixture
    def retry_client(self):
        return RuntimeInvocationClient(
            failure_handler=FailureHandler(
                retry_policy=RetryPolicy(max_retries=2, backoff_factor=0.01),
            ),
        )

    @pytest.fixture
    def ctx(self):
        return RuntimeContext(correlation_id="retry-test")

    @pytest.mark.asyncio
    async def test_invoke_step_retry_then_succeed(self, retry_client, ctx):
        step = PlanStep(
            name="flaky step",
            runtime=RuntimeTarget.KNOWLEDGE,
            timeout_seconds=5.0,
        )
        result = await retry_client.invoke_step(step, ctx)
        assert isinstance(result, RuntimeResult)

    @pytest.mark.asyncio
    async def test_get_timeline(self, client, ctx):
        step = PlanStep(
            name="timeline test",
            runtime=RuntimeTarget.KNOWLEDGE,
            timeout_seconds=5.0,
        )
        await client.invoke_step(step, ctx)
        timeline = await client.get_timeline(ctx.correlation_id)
        assert len(timeline) >= 1
        assert timeline[0].correlation_id == ctx.correlation_id
