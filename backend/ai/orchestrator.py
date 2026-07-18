from __future__ import annotations

import logging
import time
from typing import Any, Optional

from backend.ai.client import RuntimeInvocationClient
from backend.ai.context import ContextPropagator, RuntimeContext
from backend.ai.correlation import correlation_events
from backend.ai.events import AIEventPublisher, ai_event_publisher
from backend.ai.failure import FailureHandler
from backend.ai.intent import IntentClassifier
from backend.ai.invoker import RuntimeInvoker
from backend.ai.models import (
    AIContext,
    AIExecutionPlan,
    AIReasoningTrace,
    AIRequest,
    AIRequestStatus,
    AIResponse,
    ExecutionMode,
    IntentType,
    PlanStepStatus,
)
from backend.ai.planner import AIRulePlanner
from backend.ai.router import RuntimeRouter

log = logging.getLogger(__name__)


class AIOrchestrator:
    def __init__(
        self,
        classifier: Optional[IntentClassifier] = None,
        router: Optional[RuntimeRouter] = None,
        planner: Optional[AIRulePlanner] = None,
        invoker: Optional[RuntimeInvoker] = None,
        events: Optional[AIEventPublisher] = None,
        propagator: Optional[ContextPropagator] = None,
        client: Optional[RuntimeInvocationClient] = None,
        failure_handler: Optional[FailureHandler] = None,
    ) -> None:
        self._classifier = classifier or IntentClassifier()
        self._router = router or RuntimeRouter()
        self._planner = planner or AIRulePlanner(router=self._router)
        self._propagator = propagator or ContextPropagator()
        self._failure_handler = failure_handler or FailureHandler()
        self._client = client or RuntimeInvocationClient(
            failure_handler=self._failure_handler,
            correlator=correlation_events,
            propagator=self._propagator,
        )
        self._invoker = invoker or RuntimeInvoker(
            client=self._client,
            propagator=self._propagator,
            failure_handler=self._failure_handler,
        )
        self._events = events or ai_event_publisher

    async def handle_request(
        self,
        prompt: str,
        context: Optional[AIContext] = None,
    ) -> AIResponse:
        start = time.monotonic()
        trace = AIReasoningTrace()
        runtime_ctx = self._propagator.build(context)

        trace.add_step("receive", f"Processing request: {prompt[:100]}")

        request = AIRequest(
            prompt=prompt,
            context=context or AIContext(),
        )
        trace.request_id = request.id
        await self._events.publish_requested(request.id, request.intent, prompt)

        intent = await self._classify(request, trace)
        request.intent = intent
        trace.add_step("classify", f"Intent classified as {intent.value}", {"intent": intent.value})

        await self._events.publish_reasoning(trace.request_id, "Intent Classification",
                                              f"Request classified as {intent.value}")

        routes = self._router.route(intent)
        trace.add_step("route", f"Routed to {len(routes)} runtime(s)", {
            "routes": [r.runtime.value for r in routes],
        })
        for r in routes:
            await self._events.publish_runtime_selected(request.id, r.runtime, r.reason)

        plan = await self._plan(request, trace)

        result = await self._execute(plan, trace, runtime_ctx)

        duration_ms = (time.monotonic() - start) * 1000

        response = AIResponse(
            request_id=request.id,
            status=AIRequestStatus.COMPLETED if result.get("success", True) else AIRequestStatus.FAILED,
            intent=intent,
            plan=plan,
            trace=trace,
            result=result,
            summary=result.get("summary", f"Processed {len(plan.steps)} step(s)"),
            duration_ms=duration_ms,
        )
        response.error = result.get("error")
        response.status = AIRequestStatus.FAILED if response.error else AIRequestStatus.COMPLETED

        if response.error:
            await self._events.publish_failed(request.id, response.error)
        else:
            await self._events.publish_completed(request.id, response.summary)

        return response

    async def process_plan(
        self,
        plan: AIExecutionPlan,
        context: Optional[AIContext] = None,
    ) -> AIResponse:
        start = time.monotonic()
        runtime_ctx = self._propagator.build(context)
        ai_request = AIRequest(id=plan.request_id, prompt="", intent=IntentType.CONVERSATION)
        ai_request.intent = IntentType.CONVERSATION

        self._router.route_summary(IntentType.CONVERSATION)
        trace = AIReasoningTrace(request_id=plan.request_id)
        trace.add_step("plan_execution", f"Executing plan {plan.plan_id} with {len(plan.steps)} steps")

        result = await self._execute(plan, trace, runtime_ctx)
        duration_ms = (time.monotonic() - start) * 1000

        return AIResponse(
            request_id=plan.request_id,
            status=AIRequestStatus.COMPLETED if not result.get("error") else AIRequestStatus.FAILED,
            plan=plan,
            trace=trace,
            result=result,
            summary=result.get("summary", f"Executed {len(plan.steps)} step(s)"),
            duration_ms=duration_ms,
            error=result.get("error"),
        )

    async def _classify(self, request: AIRequest, trace: AIReasoningTrace) -> IntentType:
        intent, confidence = self._classifier.classify_with_confidence(request.prompt)
        trace.add_step("classify", f"Classified as {intent.value} (confidence={confidence:.2f})",
                       {"confidence": confidence})
        return intent

    async def _plan(self, request: AIRequest, trace: AIReasoningTrace) -> AIExecutionPlan:
        plan = await self._planner.create_plan(request)
        trace.add_step("plan", f"Created plan with {len(plan.steps)} step(s)",
                       {"step_count": len(plan.steps), "mode": plan.mode.value})
        await self._events.publish_planned(request.id, plan.plan_id, len(plan.steps))
        return plan

    async def _execute(
        self,
        plan: AIExecutionPlan,
        trace: AIReasoningTrace,
        ctx: RuntimeContext,
    ) -> dict[str, Any]:
        plan.status = AIRequestStatus.ROUTED

        if plan.mode == ExecutionMode.PARALLEL:
            trace.add_step("execute", f"Executing {len(plan.steps)} step(s) in parallel")
            results = await self._invoker.invoke_parallel(plan.steps, ctx)
        else:
            trace.add_step("execute", f"Executing {len(plan.steps)} step(s) sequentially")
            results = await self._invoker.invoke_sequential(plan.steps, ctx)

        plan.updated_at = _now()

        success = all(s.status == PlanStepStatus.COMPLETED for s in plan.steps)
        if success:
            plan.status = AIRequestStatus.COMPLETED
        elif plan.is_cancelled:
            plan.status = AIRequestStatus.CANCELLED
        else:
            plan.status = AIRequestStatus.FAILED

        summary = self._build_summary(plan)
        step_results = list(results) if isinstance(results, (list, tuple)) else []
        return {
            "success": success,
            "summary": summary,
            "step_results": step_results,
            "error": None if success else plan.steps[-1].error if plan.steps else "Unknown error",
        }

    def _build_summary(self, plan: AIExecutionPlan) -> str:
        completed = sum(1 for s in plan.steps if s.status == PlanStepStatus.COMPLETED)
        failed = sum(1 for s in plan.steps if s.status == PlanStepStatus.FAILED)
        parts = [f"{completed}/{len(plan.steps)} steps completed"]
        if failed:
            parts.append(f"{failed} failed")
        parts.append(f"mode={plan.mode.value}")
        return "; ".join(parts)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
