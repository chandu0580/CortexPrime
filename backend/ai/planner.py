from __future__ import annotations

import uuid
from typing import Any, Optional

from backend.ai.models import (
    AIExecutionPlan,
    AIRequest,
    AIRequestStatus,
    ExecutionMode,
    IntentType,
    PlanStep,
    RuntimeTarget,
)
from backend.ai.router import RuntimeRouter


class AIRulePlanner:
    def __init__(self, router: Optional[RuntimeRouter] = None) -> None:
        self._router = router or RuntimeRouter()

    async def create_plan(self, request: AIRequest) -> AIExecutionPlan:
        intent = request.intent
        routes = self._router.route(intent)

        steps: list[PlanStep] = []
        for idx, route in enumerate(routes):
            step = PlanStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                order=idx + 1,
                name=f"{route.runtime.value}: {route.reason}",
                description=route.reason,
                runtime=route.runtime,
                action=self._resolve_action(intent, route.runtime),
                params=self._build_params(request, route),
                timeout_seconds=self._resolve_timeout(route.runtime),
            )
            steps.append(step)

        if not steps:
            steps.append(self._fallback_step(intent))

        for i in range(1, len(steps)):
            steps[i].depends_on = [steps[i - 1].step_id]

        mode = self._resolve_mode(intent)
        return AIExecutionPlan(
            request_id=request.id,
            steps=steps,
            mode=mode,
            status=AIRequestStatus.PLANNED,
        )

    def _resolve_action(self, intent: IntentType, runtime: RuntimeTarget) -> str:
        action_map: dict[IntentType, dict[RuntimeTarget, str]] = {
            IntentType.MISSION_REQUEST: {
                RuntimeTarget.MISSION: "create_mission",
                RuntimeTarget.GOVERNANCE: "check_policy",
                RuntimeTarget.EXECUTION: "execute_mission_steps",
            },
            IntentType.QUESTION: {
                RuntimeTarget.KNOWLEDGE: "search_knowledge",
                RuntimeTarget.LEARNING: "get_pattern_insights",
            },
            IntentType.ANALYSIS: {
                RuntimeTarget.KNOWLEDGE: "search_knowledge",
                RuntimeTarget.LEARNING: "analyze_patterns",
                RuntimeTarget.MISSION: "list_mission_history",
            },
            IntentType.INVESTIGATION: {
                RuntimeTarget.EXECUTION: "inspect_executions",
                RuntimeTarget.KNOWLEDGE: "search_knowledge",
                RuntimeTarget.LEARNING: "detect_anomalies",
            },
            IntentType.AUTOMATION: {
                RuntimeTarget.CONNECTOR: "configure_connector",
                RuntimeTarget.MISSION: "create_mission",
                RuntimeTarget.GOVERNANCE: "check_policy",
                RuntimeTarget.EXECUTION: "schedule_execution",
            },
            IntentType.RECOMMENDATION: {
                RuntimeTarget.LEARNING: "get_recommendations",
                RuntimeTarget.KNOWLEDGE: "find_similar_cases",
            },
            IntentType.CONVERSATION: {
                RuntimeTarget.KNOWLEDGE: "search_knowledge",
                RuntimeTarget.LEARNING: "get_contextual_insights",
            },
            IntentType.TOOL_INVOCATION: {
                RuntimeTarget.CONNECTOR: "invoke_connector",
                RuntimeTarget.EXECUTION: "execute_tool",
                RuntimeTarget.GOVERNANCE: "check_tool_policy",
            },
        }
        return action_map.get(intent, {}).get(runtime, "default_action")

    def _build_params(self, request: AIRequest, route: Any) -> dict[str, Any]:
        return {
            "prompt": request.prompt,
            "intent": request.intent.value,
            "runtime_target": route.runtime.value,
            **request.constraints,
        }

    def _resolve_timeout(self, runtime: RuntimeTarget) -> float:
        timeout_map = {
            RuntimeTarget.IDENTITY: 10.0,
            RuntimeTarget.MISSION: 60.0,
            RuntimeTarget.GOVERNANCE: 15.0,
            RuntimeTarget.KNOWLEDGE: 20.0,
            RuntimeTarget.LEARNING: 30.0,
            RuntimeTarget.EXECUTION: 120.0,
            RuntimeTarget.CONNECTOR: 30.0,
            RuntimeTarget.AI: 30.0,
        }
        return timeout_map.get(runtime, 30.0)

    def _resolve_mode(self, intent: IntentType) -> ExecutionMode:
        if intent in (IntentType.ANALYSIS, IntentType.INVESTIGATION):
            return ExecutionMode.PARALLEL
        return ExecutionMode.SEQUENTIAL

    def _fallback_step(self, intent: IntentType) -> PlanStep:
        return PlanStep(
            name=f"fallback: {intent.value}",
            description=f"No runtime routes configured for {intent.value}.",
            runtime=RuntimeTarget.AI,
            action="fallback",
            params={"intent": intent.value},
        )
