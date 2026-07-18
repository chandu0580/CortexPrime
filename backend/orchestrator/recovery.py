from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.orchestrator.models import (
    FailureCategory,
    MissionLifecycleState,
    StageResult,
)

log = logging.getLogger(__name__)


class RecoveryStrategy(str, Enum):
    RETRY = "retry"
    COMPENSATE = "compensate"
    SKIP = "skip"
    ABORT = "abort"


_RUNTIME_STRATEGIES: dict[str, RecoveryStrategy] = {
    "MissionIntelligenceService": RecoveryStrategy.RETRY,
    "KnowledgeService": RecoveryStrategy.SKIP,
    "LearningService": RecoveryStrategy.SKIP,
    "GovernanceService": RecoveryStrategy.COMPENSATE,
    "ExecutionService": RecoveryStrategy.RETRY,
    "ConnectorService": RecoveryStrategy.RETRY,
}

_RUNTIME_CATEGORIES: dict[str, FailureCategory] = {
    "GovernanceService": FailureCategory.POLICY,
    "ConnectorService": FailureCategory.CONNECTOR,
}


class FailureClassifier:
    @classmethod
    def classify(cls, error: str, stage: str, runtime: str = "", metadata: Optional[Dict[str, Any]] = None) -> Tuple[FailureCategory, RecoveryStrategy]:
        err_lower = error.lower()
        default_cat = FailureCategory.UNKNOWN
        default_strategy = RecoveryStrategy.RETRY

        if runtime:
            default_cat = _RUNTIME_CATEGORIES.get(runtime, FailureCategory.UNKNOWN)
            default_strategy = _RUNTIME_STRATEGIES.get(runtime, RecoveryStrategy.RETRY)

        if any(kw in err_lower for kw in ("timeout", "timed out", "deadline")):
            return FailureCategory.TIMEOUT, RecoveryStrategy.RETRY
        if any(kw in err_lower for kw in ("connector", "connection", "network", "disconnect")):
            return FailureCategory.CONNECTOR, RecoveryStrategy.RETRY
        if any(kw in err_lower for kw in ("policy", "compliance", "governance", "approval", "denied")):
            return FailureCategory.POLICY, RecoveryStrategy.COMPENSATE
        if any(kw in err_lower for kw in ("runtime", "internal", "unexpected")):
            return FailureCategory.RUNTIME, RecoveryStrategy.ABORT

        if runtime:
            return default_cat, default_strategy
        return FailureCategory.UNKNOWN, RecoveryStrategy.RETRY


class CompensationHook:
    def __init__(self, name: str, handler: Callable, states: Optional[List[MissionLifecycleState]] = None) -> None:
        self.name = name
        self.handler = handler
        self.states = states or []


class RecoveryManager:
    def __init__(self) -> None:
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._max_retries: int = 3
        self._compensation_hooks: List[CompensationHook] = []
        self._rollback_handlers: Dict[str, Callable] = {}

    def set_max_retries(self, max_retries: int) -> None:
        self._max_retries = max_retries

    def register_compensation_hook(self, hook: CompensationHook) -> None:
        self._compensation_hooks.append(hook)

    def register_rollback_handler(self, state: str, handler: Callable) -> None:
        self._rollback_handlers[state] = handler

    def save_checkpoint(
        self,
        mission_id: str,
        state: MissionLifecycleState,
        context_snapshot: Dict[str, Any],
    ) -> None:
        self._checkpoints[mission_id] = {
            "state": state.value,
            "context": context_snapshot,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_checkpoint(self, mission_id: str) -> Optional[Dict[str, Any]]:
        return self._checkpoints.get(mission_id)

    def get_last_successful_state(self, mission_id: str, stage_results: Dict[str, StageResult]) -> Optional[str]:
        ordered = [
            MissionLifecycleState.RECEIVED.value,
            MissionLifecycleState.ANALYZED.value,
            MissionLifecycleState.PLANNED.value,
            MissionLifecycleState.KNOWLEDGE_RETRIEVED.value,
            MissionLifecycleState.LEARNING_RETRIEVED.value,
            MissionLifecycleState.GOVERNANCE_EVALUATED.value,
            MissionLifecycleState.EXECUTION_PLANNED.value,
            MissionLifecycleState.EXECUTION_STARTED.value,
            MissionLifecycleState.EXECUTION_COMPLETED.value,
            MissionLifecycleState.VERIFIED.value,
            MissionLifecycleState.KNOWLEDGE_UPDATED.value,
            MissionLifecycleState.LEARNING_UPDATED.value,
            MissionLifecycleState.ARCHIVED.value,
        ]
        last_success = None
        for state in ordered:
            result = stage_results.get(state)
            if result and result.success:
                last_success = state
        return last_success

    def should_retry(self, mission_id: str, state: str, failure_count: int) -> bool:
        checkpoint = self._checkpoints.get(mission_id, {})
        retry_count = checkpoint.get("retry_count", {}).get(state, 0)
        return retry_count < self._max_retries and failure_count < self._max_retries

    def record_retry(self, mission_id: str, state: str) -> None:
        if mission_id not in self._checkpoints:
            self._checkpoints[mission_id] = {}
        retry_map = self._checkpoints[mission_id].setdefault("retry_count", {})
        retry_map[state] = retry_map.get(state, 0) + 1

    def execute_compensation(self, mission_id: str, state: MissionLifecycleState, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for hook in self._compensation_hooks:
            if not hook.states or state in hook.states:
                try:
                    result = hook.handler(mission_id, state, context)
                    results.append({"hook": hook.name, "success": True, "result": result})
                except Exception as exc:
                    results.append({"hook": hook.name, "success": False, "error": str(exc)})
        return results

    def execute_rollback(self, mission_id: str, state: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        handler = self._rollback_handlers.get(state)
        if handler:
            try:
                return handler(mission_id, state, context)
            except Exception as exc:
                log.warning("Rollback handler failed for %s: %s", state, exc)
                return {"error": str(exc)}
        return None


recovery_manager = RecoveryManager()
