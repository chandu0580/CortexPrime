from __future__ import annotations

from typing import Any, Optional

from backend.ai.models import IntentType, RuntimeTarget


class RuntimeRoute:
    def __init__(
        self,
        runtime: RuntimeTarget,
        priority: int,
        reason: str,
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        self.runtime = runtime
        self.priority = priority
        self.reason = reason
        self.params = params or {}


class RuntimeRouter:
    ROUTING_TABLE: dict[IntentType, list[RuntimeRoute]] = {
        IntentType.MISSION_REQUEST: [
            RuntimeRoute(RuntimeTarget.MISSION, 1, "Mission creation and planning"),
            RuntimeRoute(RuntimeTarget.GOVERNANCE, 2, "Policy validation for new mission"),
            RuntimeRoute(RuntimeTarget.EXECUTION, 3, "Mission step execution"),
        ],
        IntentType.QUESTION: [
            RuntimeRoute(RuntimeTarget.KNOWLEDGE, 1, "Knowledge base search"),
            RuntimeRoute(RuntimeTarget.LEARNING, 2, "Pattern-based insights"),
        ],
        IntentType.ANALYSIS: [
            RuntimeRoute(RuntimeTarget.KNOWLEDGE, 1, "Knowledge base retrieval"),
            RuntimeRoute(RuntimeTarget.LEARNING, 2, "Pattern detection and analysis"),
            RuntimeRoute(RuntimeTarget.MISSION, 3, "Mission history analysis"),
        ],
        IntentType.INVESTIGATION: [
            RuntimeRoute(RuntimeTarget.EXECUTION, 1, "Execution history inspection"),
            RuntimeRoute(RuntimeTarget.KNOWLEDGE, 2, "Related knowledge retrieval"),
            RuntimeRoute(RuntimeTarget.LEARNING, 3, "Pattern-based root cause"),
        ],
        IntentType.AUTOMATION: [
            RuntimeRoute(RuntimeTarget.CONNECTOR, 1, "Connector configuration"),
            RuntimeRoute(RuntimeTarget.MISSION, 2, "Automated mission setup"),
            RuntimeRoute(RuntimeTarget.GOVERNANCE, 3, "Automation policy check"),
            RuntimeRoute(RuntimeTarget.EXECUTION, 4, "Scheduled execution"),
        ],
        IntentType.RECOMMENDATION: [
            RuntimeRoute(RuntimeTarget.LEARNING, 1, "Pattern-based recommendations"),
            RuntimeRoute(RuntimeTarget.KNOWLEDGE, 2, "Similar case retrieval"),
        ],
        IntentType.CONVERSATION: [
            RuntimeRoute(RuntimeTarget.KNOWLEDGE, 1, "General knowledge retrieval"),
            RuntimeRoute(RuntimeTarget.LEARNING, 2, "Contextual pattern insights"),
        ],
        IntentType.TOOL_INVOCATION: [
            RuntimeRoute(RuntimeTarget.CONNECTOR, 1, "Connector tool execution"),
            RuntimeRoute(RuntimeTarget.EXECUTION, 2, "Execution wrapper"),
            RuntimeRoute(RuntimeTarget.GOVERNANCE, 3, "Tool usage policy check"),
        ],
    }

    @classmethod
    def route(cls, intent: IntentType) -> list[RuntimeRoute]:
        return cls.ROUTING_TABLE.get(intent, [])

    @classmethod
    def primary_runtime(cls, intent: IntentType) -> Optional[RuntimeTarget]:
        routes = cls.route(intent)
        return routes[0].runtime if routes else None

    @classmethod
    def route_summary(cls, intent: IntentType) -> list[dict[str, Any]]:
        return [
            {"runtime": r.runtime.value, "priority": r.priority, "reason": r.reason}
            for r in cls.route(intent)
        ]
