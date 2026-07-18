from __future__ import annotations

import asyncio
import time

import pytest

from backend.ai.failure import (
    CircuitBreaker,
    CircuitBreakerState,
    FailureHandler,
    RetryPolicy,
)
from backend.ai.models import PlanStep, PlanStepStatus, RuntimeTarget


class TestRetryPolicy:
    def test_defaults(self):
        rp = RetryPolicy()
        assert rp.max_retries == 3
        assert rp.backoff_factor == 1.0
        assert rp.max_backoff == 30.0

    def test_get_delay(self):
        rp = RetryPolicy(backoff_factor=1.0)
        assert rp.get_delay(0) == 1.0
        assert rp.get_delay(1) == 2.0
        assert rp.get_delay(2) == 4.0

    def test_max_backoff_clamp(self):
        rp = RetryPolicy(backoff_factor=10.0, max_backoff=5.0)
        assert rp.get_delay(3) == 5.0

    def test_should_retry_under_limit(self):
        rp = RetryPolicy(max_retries=3)
        assert rp.should_retry(0)
        assert rp.should_retry(1)
        assert rp.should_retry(2)
        assert not rp.should_retry(3)

    def test_should_retry_non_retryable_error(self):
        rp = RetryPolicy(max_retries=3)
        assert not rp.should_retry(0, "not found")
        assert not rp.should_retry(0, "invalid request")


class TestCircuitBreaker:
    def test_default_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_allow_request_when_closed(self):
        cb = CircuitBreaker()
        assert cb.allow_request()

    def test_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        assert cb.allow_request()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_open_rejects_requests(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert not cb.allow_request()

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        time.sleep(0.02)
        assert cb.allow_request()
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_success_closes_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.allow_request()
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.allow_request()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0


class TestFailureHandler:
    @pytest.mark.asyncio
    async def test_with_retry_success_first_try(self):
        handler = FailureHandler()
        step = PlanStep(name="test", runtime=RuntimeTarget.KNOWLEDGE)

        async def ok_handler(s):
            return {"result": "ok"}

        result = await handler.with_retry(step, ok_handler)
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_with_retry_success_after_retry(self):
        handler = FailureHandler(retry_policy=RetryPolicy(max_retries=3, backoff_factor=0.01))
        step = PlanStep(name="test", runtime=RuntimeTarget.EXECUTION)
        attempt_count = 0

        async def flaky_handler(s):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("flaky")
            return {"result": "ok"}

        result = await handler.with_retry(step, flaky_handler)
        assert result["result"] == "ok"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_with_retry_exhausted(self):
        handler = FailureHandler(retry_policy=RetryPolicy(max_retries=2, backoff_factor=0.01))
        step = PlanStep(name="test", runtime=RuntimeTarget.EXECUTION)

        async def always_fail(s):
            raise ValueError("always fails")

        result = await handler.with_retry(step, always_fail)
        assert "error" in result
        assert step.status == PlanStepStatus.FAILED
        assert step.error is not None

    @pytest.mark.asyncio
    async def test_with_retry_circuit_breaker(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        handler = FailureHandler(
            retry_policy=RetryPolicy(max_retries=1, backoff_factor=0.01),
            circuit_breaker=cb,
        )
        step = PlanStep(name="test", runtime=RuntimeTarget.EXECUTION)

        async def fail(s):
            raise ValueError("fail")

        await handler.with_retry(step, fail)
        assert cb.state == CircuitBreakerState.CLOSED
        await handler.with_retry(step, fail)
        assert cb.state == CircuitBreakerState.CLOSED
        await handler.with_retry(step, fail)
        assert cb.state == CircuitBreakerState.OPEN
        assert not handler.check_circuit_breaker(RuntimeTarget.EXECUTION)

    @pytest.mark.asyncio
    async def test_compensate(self):
        handler = FailureHandler()
        completed_step = PlanStep(
            name="step1", runtime=RuntimeTarget.EXECUTION,
            status=PlanStepStatus.COMPLETED,
        )
        failed_step = PlanStep(
            name="step2", runtime=RuntimeTarget.KNOWLEDGE,
            status=PlanStepStatus.FAILED,
        )
        pending_step = PlanStep(
            name="step3", runtime=RuntimeTarget.LEARNING,
            status=PlanStepStatus.PENDING,
        )
        results = await handler.compensate([completed_step, failed_step, pending_step])
        assert len(results) == 1
        assert results[0]["step_id"] == completed_step.step_id
        assert results[0]["compensation"] == "applied"
