from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from backend.ai.client import RuntimeInvocationClient
from backend.ai.context import ContextPropagator, RuntimeContext
from backend.ai.correlation import correlation_events
from backend.ai.failure import FailureHandler
from backend.ai.integration import RuntimeIntegrationFactory
from backend.ai.models import PlanStep, PlanStepStatus, RuntimeTarget

log = logging.getLogger(__name__)

RuntimeHandler = Callable[[PlanStep], "asyncio.Future[dict[str, Any]]"]


class RuntimeInvoker:
    def __init__(
        self,
        client: Optional[RuntimeInvocationClient] = None,
        propagator: Optional[ContextPropagator] = None,
        integration_factory: Optional[RuntimeIntegrationFactory] = None,
        failure_handler: Optional[FailureHandler] = None,
    ) -> None:
        self._propagator = propagator or ContextPropagator()
        self._client = client or RuntimeInvocationClient(
            integration_factory=integration_factory or RuntimeIntegrationFactory(
                context_propagator=self._propagator,
            ),
            failure_handler=failure_handler or FailureHandler(),
            correlator=correlation_events,
            propagator=self._propagator,
        )
        self._handlers: dict[RuntimeTarget, RuntimeHandler] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._handlers[RuntimeTarget.IDENTITY] = self._identity_default
        self._handlers[RuntimeTarget.MISSION] = self._mission_default
        self._handlers[RuntimeTarget.GOVERNANCE] = self._governance_default
        self._handlers[RuntimeTarget.KNOWLEDGE] = self._knowledge_default
        self._handlers[RuntimeTarget.LEARNING] = self._learning_default
        self._handlers[RuntimeTarget.EXECUTION] = self._execution_default
        self._handlers[RuntimeTarget.CONNECTOR] = self._connector_default
        self._handlers[RuntimeTarget.AI] = self._ai_default

    def register_handler(self, runtime: RuntimeTarget, handler: RuntimeHandler) -> None:
        self._handlers[runtime] = handler

    def use_real_handlers(self) -> None:
        for target in RuntimeTarget:
            integration_handler = self._client._factory.get_handler(target)
            if integration_handler:
                self._handlers[target] = self._make_integration_wrapper(target, integration_handler)

    def _make_integration_wrapper(
        self, target: RuntimeTarget, integration_handler: Any
    ) -> RuntimeHandler:
        async def wrapper(step: PlanStep) -> dict[str, Any]:
            ctx = self._propagator.build()
            try:
                result = await integration_handler(step, ctx)
                step.status = PlanStepStatus.COMPLETED
                return _result_to_dict(result)
            except Exception as exc:
                log.warning("Integration handler for %s failed: %s", target.value, exc)
                step.status = PlanStepStatus.FAILED
                step.error = str(exc)
                return {"runtime": target.value, "status": "failed", "error": str(exc)}
        return wrapper

    async def invoke_step(self, step: PlanStep, ctx: Optional[RuntimeContext] = None) -> dict[str, Any]:
        handler = self._handlers.get(step.runtime)
        if handler:
            step.status = PlanStepStatus.RUNNING
            step.started_at = _now()
            try:
                result = await asyncio.wait_for(
                    _run_handler(handler, step),
                    timeout=step.timeout_seconds,
                )
                step.status = PlanStepStatus.COMPLETED
                step.result = result
                return result
            except asyncio.TimeoutError:
                step.status = PlanStepStatus.FAILED
                step.error = f"Step timed out after {step.timeout_seconds}s"
                log.warning("Step %s timed out (%s)", step.step_id, step.name)
                return {"error": step.error, "step_id": step.step_id}
            except Exception as exc:
                step.status = PlanStepStatus.FAILED
                step.error = str(exc)
                log.warning("Step %s failed: %s", step.step_id, exc)
                return {"error": str(exc), "step_id": step.step_id}
            finally:
                step.completed_at = _now()
        else:
            runtime_ctx = ctx or self._propagator.build()
            result = await self._client.invoke_step(step, runtime_ctx)
            return _result_to_dict(result)

    async def invoke_parallel(
        self,
        steps: list[PlanStep],
        ctx: Optional[RuntimeContext] = None,
    ) -> list[dict[str, Any]]:
        if ctx:
            runtime_ctx = ctx
            results = await self._client.invoke_parallel(steps, runtime_ctx)
            return [_result_to_dict(r) for r in results]
        tasks = [self.invoke_step(s) for s in steps]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def invoke_sequential(
        self,
        steps: list[PlanStep],
        ctx: Optional[RuntimeContext] = None,
    ) -> list[dict[str, Any]]:
        if ctx:
            runtime_ctx = ctx
            results = await self._client.invoke_sequential(steps, runtime_ctx)
            return [_result_to_dict(r) for r in results]
        results: list[dict[str, Any]] = []
        for step in steps:
            result = await self.invoke_step(step)
            results.append(result)
            if step.status == PlanStepStatus.FAILED:
                break
        return results

    async def cancel_step(self, step: PlanStep, ctx: Optional[RuntimeContext] = None) -> None:
        if step.status in (PlanStepStatus.PENDING, PlanStepStatus.RUNNING):
            step.status = PlanStepStatus.CANCELLED
            step.error = "Cancelled by user"

    # ------------------------------------------------------------------
    # Default handlers (simulated, backward compatible)
    # ------------------------------------------------------------------

    async def _identity_default(self, step: PlanStep) -> dict[str, Any]:
        log.info("Identity Runtime invoked: %s", step.name)
        return {"runtime": "identity", "status": "simulated"}

    async def _mission_default(self, step: PlanStep) -> dict[str, Any]:
        log.info("Mission Runtime invoked: %s", step.name)
        return {"runtime": "mission", "status": "simulated"}

    async def _governance_default(self, step: PlanStep) -> dict[str, Any]:
        log.info("Governance Runtime invoked: %s", step.name)
        return {"runtime": "governance", "status": "simulated"}

    async def _knowledge_default(self, step: PlanStep) -> dict[str, Any]:
        log.info("Knowledge Runtime invoked: %s", step.name)
        return {"runtime": "knowledge", "status": "simulated"}

    async def _learning_default(self, step: PlanStep) -> dict[str, Any]:
        log.info("Learning Runtime invoked: %s", step.name)
        return {"runtime": "learning", "status": "simulated"}

    async def _execution_default(self, step: PlanStep) -> dict[str, Any]:
        log.info("Execution Runtime invoked: %s", step.name)
        return {"runtime": "execution", "status": "simulated"}

    async def _connector_default(self, step: PlanStep) -> dict[str, Any]:
        log.info("Connector Runtime invoked: %s", step.name)
        return {"runtime": "connector", "status": "simulated"}

    async def _ai_default(self, step: PlanStep) -> dict[str, Any]:
        log.info("AI Runtime self-invocation: %s", step.name)
        return {"runtime": "ai", "status": "simulated"}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def _run_handler(handler: RuntimeHandler, step: PlanStep) -> dict[str, Any]:
    if asyncio.iscoroutinefunction(handler):
        return await handler(step)
    return handler(step)


def _result_to_dict(r: Any) -> dict[str, Any]:
    if hasattr(r, "__dict__"):
        return {k: v for k, v in r.__dict__.items() if not k.startswith("_")}
    if isinstance(r, (list, tuple)):
        return {"items": [_result_to_dict(i) for i in r]}
    if isinstance(r, dict):
        return r
    return {"value": r}
