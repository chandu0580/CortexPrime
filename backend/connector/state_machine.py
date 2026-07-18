from __future__ import annotations

from backend.connector.models import ConnectorStatus


TRANSITIONS: dict[ConnectorStatus, set[ConnectorStatus]] = {
    ConnectorStatus.REGISTERED: {ConnectorStatus.INITIALIZING, ConnectorStatus.DISABLED},
    ConnectorStatus.INITIALIZING: {ConnectorStatus.READY, ConnectorStatus.FAILED},
    ConnectorStatus.READY: {
        ConnectorStatus.DEGRADED, ConnectorStatus.UPDATING,
        ConnectorStatus.DISABLED,
    },
    ConnectorStatus.DEGRADED: {
        ConnectorStatus.READY, ConnectorStatus.UNAVAILABLE,
        ConnectorStatus.UPDATING, ConnectorStatus.DISABLED,
        ConnectorStatus.FAILED,
    },
    ConnectorStatus.UNAVAILABLE: {ConnectorStatus.REGISTERED, ConnectorStatus.FAILED},
    ConnectorStatus.UPDATING: {ConnectorStatus.READY, ConnectorStatus.FAILED},
    ConnectorStatus.DISABLED: {ConnectorStatus.REGISTERED},
    ConnectorStatus.FAILED: {ConnectorStatus.REGISTERED, ConnectorStatus.DISABLED},
}

TERMINAL = {
    ConnectorStatus.FAILED,
    ConnectorStatus.DISABLED,
}

DEGRADED = {
    ConnectorStatus.DEGRADED,
    ConnectorStatus.UNAVAILABLE,
}


def is_valid_transition(current: ConnectorStatus, target: ConnectorStatus) -> bool:
    return target in TRANSITIONS.get(current, set())


def is_terminal(status: ConnectorStatus) -> bool:
    return status in TERMINAL


def is_degraded(status: ConnectorStatus) -> bool:
    return status in DEGRADED


def validate_transition(current: ConnectorStatus, target: ConnectorStatus) -> None:
    if not is_valid_transition(current, target):
        raise ValueError(
            f"Invalid connector transition: {current.value} -> {target.value}"
        )
