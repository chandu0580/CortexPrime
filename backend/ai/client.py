from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from backend.ai.context import ContextPropagator, RuntimeContext
from backend.ai.correlation import CorrelationEvent, EventCorrelator, correlation_events
from backend.ai.failure import FailureHandler
from backend.ai.integration import RuntimeIntegrationFactory
from backend.ai.models import PlanStep, PlanStepStatus
from backend.ai.result import RuntimeResult

log = logging.getLogger(__name__)


class RuntimeInvocationClient:
    def __init__(
        self,
        integration_factory: Optional[RuntimeIntegrationFactory] = None,
        failure_handler: Optional[FailureHandler] = None,
        correlator: Optional[EventCorrelator] = None,
        propagator: Optional[ContextPropagator] = None,
    ) -> None:
        self._factory = integration_factory or RuntimeIntegrationFactory()
        self._failure = failure_handler or FailureHandler()
        self._correlator = correlator or correlation_events
        self._propagator = propagator or ContextPropagator()

    async def invoke_step(
        self,
        step: PlanStep,
        ctx: RuntimeContext,
    ) -> RuntimeResult:
        handler = self._factory.get_handler(step.runtime)
        if not handler:
            return RuntimeResult(
                runtime=step.runtime,
                step_id=step.step_id,
                status="failed",
                error=f"No handler registered for {step.runtime.value}",
                correlation_id=ctx.correlation_id,
            )

        if not self._failure.check_circuit_breaker(step.runtime):
            log.warning("Circuit breaker open for %s, step %s skipped", step.runtime.value, step.step_id)
            return RuntimeResult(
                runtime=step.runtime,
                step_id=step.step_id,
                status="failed",
                error=f"Circuit breaker open for {step.runtime.value}",
                correlation_id=ctx.correlation_id,
            )

        step.status = PlanStepStatus.RUNNING
        step.started_at = _now()

        await self._correlator.record(
            ctx.correlation_id, step.runtime.value, "step.started",
            message=f"Step {step.step_id} ({step.name}) started on {step.runtime.value}",
            payload={"step_id": step.step_id, "action": step.action},
        )

        async def invoke(_step: PlanStep) -> dict[str, Any]:
            result = await asyncio.wait_for(
                handler(step, ctx),
                timeout=step.timeout_seconds,
            )
            return _result_to_dict(result)

        start = time.monotonic()
        try:
            raw = await self._failure.with_retry(step, invoke)
            duration = (time.monotonic() - start) * 1000

            if raw.get("error"):
                step.status = PlanStepStatus.FAILED
                step.error = raw["error"]
                result = RuntimeResult(
                    runtime=step.runtime,
                    step_id=step.step_id,
                    status="failed",
                    error=raw["error"],
                    duration_ms=duration,
                    correlation_id=ctx.correlation_id,
                )
            else:
                step.status = PlanStepStatus.COMPLETED
                step.result = raw
                result_data = raw.get("data", raw)
                if isinstance(result_data, dict) and "runtime" in result_data:
                    result_data = result_data
                result = RuntimeResult(
                    runtime=step.runtime,
                    step_id=step.step_id,
                    status="success",
                    data=result_data if isinstance(result_data, dict) else {"result": result_data},
                    duration_ms=duration,
                    correlation_id=ctx.correlation_id,
                )

            step.completed_at = _now()
            await self._correlator.record(
                ctx.correlation_id, step.runtime.value, "step.completed",
                status="success" if result.is_success else "failed",
                message=f"Step {step.step_id} completed with status {result.status}",
                payload={"step_id": step.step_id, "status": result.status, "duration_ms": duration},
            )
            return result

        except asyncio.TimeoutError:
            step.status = PlanStepStatus.FAILED
            step.error = f"Step timed out after {step.timeout_seconds}s"
            step.completed_at = _now()
            log.warning("Step %s timed out (%s)", step.step_id, step.name)
            await self._correlator.record(
                ctx.correlation_id, step.runtime.value, "step.timeout",
                status="failed",
                message=f"Step {step.step_id} timed out",
                payload={"step_id": step.step_id, "timeout": step.timeout_seconds},
            )
            return RuntimeResult(
                runtime=step.runtime,
                step_id=step.step_id,
                status="failed",
                error=step.error,
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
        except Exception as exc:
            step.status = PlanStepStatus.FAILED
            step.error = str(exc)
            step.completed_at = _now()
            log.warning("Step %s failed: %s", step.step_id, exc)
            await self._correlator.record(
                ctx.correlation_id, step.runtime.value, "step.error",
                status="failed",
                message=f"Step {step.step_id} error: {exc}",
                payload={"step_id": step.step_id, "error": str(exc)},
            )
            return RuntimeResult(
                runtime=step.runtime,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )

    async def invoke_parallel(
        self,
        steps: list[PlanStep],
        ctx: RuntimeContext,
    ) -> list[RuntimeResult]:
        tasks = [self.invoke_step(s, ctx) for s in steps]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def invoke_sequential(
        self,
        steps: list[PlanStep],
        ctx: RuntimeContext,
    ) -> list[RuntimeResult]:
        results: list[RuntimeResult] = []
        completed: list[PlanStep] = []
        for step in steps:
            result = await self.invoke_step(step, ctx)
            results.append(result)
            if result.is_failure:
                log.warning("Sequential execution stopped at step %s due to failure", step.step_id)
                await self._failure.compensate(completed)
                for remaining in steps[len(completed) + 1:]:
                    remaining.status = PlanStepStatus.SKIPPED
                    results.append(RuntimeResult(
                        runtime=remaining.runtime,
                        step_id=remaining.step_id,
                        status="cancelled",
                        error="Previous step failed",
                        correlation_id=ctx.correlation_id,
                    ))
                break
            completed.append(step)
        return results

    async def cancel_step(self, step: PlanStep, ctx: RuntimeContext) -> None:
        if step.status in (PlanStepStatus.PENDING, PlanStepStatus.RUNNING):
            step.status = PlanStepStatus.CANCELLED
            step.error = "Cancelled by user"
            await self._correlator.record(
                ctx.correlation_id, step.runtime.value, "step.cancelled",
                message=f"Step {step.step_id} cancelled",
                payload={"step_id": step.step_id},
            )

    async def get_timeline(self, correlation_id: str) -> list[CorrelationEvent]:
        return self._correlator.get_timeline(correlation_id)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _result_to_dict(r: Any) -> dict[str, Any]:
    if hasattr(r, "__dict__"):
        return {k: v for k, v in r.__dict__.items() if not k.startswith("_")}
    if isinstance(r, (list, tuple)):
        return {"items": [_result_to_dict(i) for i in r]}
    if isinstance(r, dict):
        return r
    return {"value": r}
