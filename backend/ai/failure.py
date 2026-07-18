from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Optional

from backend.ai.models import PlanStep, PlanStepStatus, RuntimeTarget

log = logging.getLogger(__name__)

RetryHandler = Callable[[PlanStep], "asyncio.Future[dict[str, Any]]"]


class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        max_backoff: float = 30.0,
        retryable_statuses: Optional[list[str]] = None,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.retryable_statuses = retryable_statuses or ["failed", "timeout"]

    def get_delay(self, attempt: int) -> float:
        delay = min(self.backoff_factor * (2 ** attempt), self.max_backoff)
        return delay

    def should_retry(self, attempt: int, error: Optional[str] = None) -> bool:
        if attempt >= self.max_retries:
            return False
        if error and any(s in error.lower() for s in ("not found", "invalid", "bad request")):
            return False
        return True


class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


CircuitState = CircuitBreakerState


class CircuitBreaker:
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0

    def record_success(self) -> None:
        if self.state == CircuitBreakerState.HALF_OPEN:
            log.info("Circuit breaker %s: half-open -> closed (success)", self.name)
            self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.state == CircuitBreakerState.HALF_OPEN:
            log.warning("Circuit breaker %s: half-open -> open (failure)", self.name)
            self.state = CircuitBreakerState.OPEN
        elif self.failure_count >= self.failure_threshold and self.state == CircuitBreakerState.CLOSED:
            log.warning("Circuit breaker %s: closed -> open (threshold=%d)", self.name, self.failure_threshold)
            self.state = CircuitBreakerState.OPEN

    def allow_request(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True
        if self.state == CircuitBreakerState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                log.info("Circuit breaker %s: open -> half-open (recovery timeout)", self.name)
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        return True

    def reset(self) -> None:
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0


class FailureHandler:
    def __init__(
        self,
        retry_policy: Optional[RetryPolicy] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.retry_policy = retry_policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker

    async def with_retry(
        self,
        step: PlanStep,
        handler: RetryHandler,
    ) -> dict[str, Any]:
        last_error: Optional[str] = None
        for attempt in range(self.retry_policy.max_retries + 1):
            if attempt > 0:
                delay = self.retry_policy.get_delay(attempt - 1)
                log.info("Retrying step %s (attempt %d/%d, delay=%.1fs)", step.step_id, attempt, self.retry_policy.max_retries, delay)
                await asyncio.sleep(delay)
            try:
                result = await handler(step)
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                return result
            except asyncio.TimeoutError:
                last_error = f"Timeout on attempt {attempt + 1}"
                log.warning("Step %s timeout (attempt %d)", step.step_id, attempt + 1)
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()
                if not self.retry_policy.should_retry(attempt, "timeout"):
                    break
            except Exception as exc:
                last_error = str(exc)
                log.warning("Step %s failed (attempt %d): %s", step.step_id, attempt + 1, exc)
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()
                if not self.retry_policy.should_retry(attempt, last_error):
                    break
        step.status = PlanStepStatus.FAILED
        step.error = last_error
        return {"error": last_error, "step_id": step.step_id, "runtime": step.runtime.value}

    def check_circuit_breaker(self, runtime: RuntimeTarget) -> bool:
        if self.circuit_breaker:
            return self.circuit_breaker.allow_request()
        return True

    async def compensate(self, completed_steps: list[PlanStep]) -> list[dict[str, Any]]:
        compensation_results: list[dict[str, Any]] = []
        for step in reversed(completed_steps):
            if step.status == PlanStepStatus.COMPLETED:
                log.info("Compensating step %s (%s)", step.step_id, step.name)
                compensation_results.append({
                    "step_id": step.step_id,
                    "compensation": "applied",
                    "runtime": step.runtime.value,
                })
        return compensation_results
