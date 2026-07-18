from __future__ import annotations

from backend.execution.models import ExecutionStatus


TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.CREATED: {ExecutionStatus.QUEUED, ExecutionStatus.CANCELLED},
    ExecutionStatus.QUEUED: {ExecutionStatus.STARTING, ExecutionStatus.CANCELLED},
    ExecutionStatus.STARTING: {ExecutionStatus.RUNNING, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED},
    ExecutionStatus.RUNNING: {
        ExecutionStatus.PAUSED, ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED, ExecutionStatus.CANCELLED,
        ExecutionStatus.RETRYING, ExecutionStatus.TIMED_OUT,
    },
    ExecutionStatus.PAUSED: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
    ExecutionStatus.RETRYING: {ExecutionStatus.QUEUED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED},
    ExecutionStatus.SUCCEEDED: set(),
    ExecutionStatus.FAILED: {ExecutionStatus.RETRYING, ExecutionStatus.QUEUED, ExecutionStatus.CANCELLED},
    ExecutionStatus.CANCELLED: set(),
    ExecutionStatus.TIMED_OUT: {ExecutionStatus.RETRYING, ExecutionStatus.QUEUED, ExecutionStatus.CANCELLED},
}

TERMINAL = {
    ExecutionStatus.SUCCEEDED,
    ExecutionStatus.FAILED,
    ExecutionStatus.CANCELLED,
    ExecutionStatus.TIMED_OUT,
}


def is_valid_transition(current: ExecutionStatus, target: ExecutionStatus) -> bool:
    return target in TRANSITIONS.get(current, set())


def is_terminal(status: ExecutionStatus) -> bool:
    return status in TERMINAL


def validate_transition(current: ExecutionStatus, target: ExecutionStatus) -> None:
    if not is_valid_transition(current, target):
        raise ValueError(
            f"Invalid execution transition: {current.value} -> {target.value}"
        )
