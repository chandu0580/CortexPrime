from __future__ import annotations

from typing import Dict, List

from backend.orchestrator.models import MissionLifecycleState, OrchestratorStatus


class MissionStateMachine:
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        MissionLifecycleState.RECEIVED.value: [
            MissionLifecycleState.ANALYZED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.ANALYZED.value: [
            MissionLifecycleState.PLANNED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.PLANNED.value: [
            MissionLifecycleState.KNOWLEDGE_RETRIEVED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.KNOWLEDGE_RETRIEVED.value: [
            MissionLifecycleState.LEARNING_RETRIEVED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.LEARNING_RETRIEVED.value: [
            MissionLifecycleState.GOVERNANCE_EVALUATED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.GOVERNANCE_EVALUATED.value: [
            MissionLifecycleState.EXECUTION_PLANNED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.EXECUTION_PLANNED.value: [
            MissionLifecycleState.EXECUTION_STARTED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.EXECUTION_STARTED.value: [
            MissionLifecycleState.EXECUTION_COMPLETED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.EXECUTION_COMPLETED.value: [
            MissionLifecycleState.VERIFIED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.VERIFIED.value: [
            MissionLifecycleState.KNOWLEDGE_UPDATED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.KNOWLEDGE_UPDATED.value: [
            MissionLifecycleState.LEARNING_UPDATED.value,
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.LEARNING_UPDATED.value: [
            MissionLifecycleState.ARCHIVED.value,
        ],
        MissionLifecycleState.ARCHIVED.value: [],
    }

    STATUS_TRANSITIONS: Dict[str, List[str]] = {
        OrchestratorStatus.PENDING.value: [
            OrchestratorStatus.RUNNING.value,
            OrchestratorStatus.CANCELLED.value,
            OrchestratorStatus.FAILED.value,
        ],
        OrchestratorStatus.RUNNING.value: [
            OrchestratorStatus.PAUSED.value,
            OrchestratorStatus.CANCELLED.value,
            OrchestratorStatus.FAILED.value,
            OrchestratorStatus.COMPLETED.value,
        ],
        OrchestratorStatus.PAUSED.value: [
            OrchestratorStatus.RUNNING.value,
            OrchestratorStatus.CANCELLED.value,
            OrchestratorStatus.FAILED.value,
        ],
        OrchestratorStatus.CANCELLED.value: [],
        OrchestratorStatus.COMPLETED.value: [],
        OrchestratorStatus.FAILED.value: [
            OrchestratorStatus.RUNNING.value,
        ],
    }

    SEQUENTIAL_ORDER: List[str] = [
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

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.VALID_TRANSITIONS.get(current, [])

    @classmethod
    def can_change_status(cls, current: str, target: str) -> bool:
        return target in cls.STATUS_TRANSITIONS.get(current, [])

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        return state == MissionLifecycleState.ARCHIVED.value

    @classmethod
    def next_state(cls, current: str) -> str:
        try:
            idx = cls.SEQUENTIAL_ORDER.index(current)
            if idx + 1 < len(cls.SEQUENTIAL_ORDER):
                return cls.SEQUENTIAL_ORDER[idx + 1]
            return current
        except ValueError:
            return current
