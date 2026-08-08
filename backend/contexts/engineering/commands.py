"""Runtime commands and queries.

Frozen values naming one intent each. Objects rather than argument lists, because
a command is what an orchestrator queues, logs, retries and replays -- and none
of that works on an argument list.

``expected_phase`` appears on every mutating command. It is optional, and
supplying it is what turns a blind write into optimistic concurrency: a command
composed against a stale read is refused rather than applied to a state its
author never saw.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "AdvanceWorkOrder",
    "RejectWorkOrderCommand",
    "SupersedeWorkOrderCommand",
    "GetRuntimeState",
    "GetEventHistory",
    "GetLifecycleCapability",
    "ReplayWorkOrder",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class AdvanceWorkOrder:
    """Move a WorkOrder to a phase."""

    work_id: str
    to_phase: str
    actor: str
    expected_phase: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(bool(self.to_phase), "to_phase is required")
        _require(
            bool(self.actor and self.actor.strip()),
            "actor is required; a transition is an act by someone",
        )


@dataclass(frozen=True)
class RejectWorkOrderCommand:
    work_id: str
    rejection_type: str
    detail: str
    raised_by: str
    expected_phase: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(bool(self.rejection_type), "rejection_type is required")
        _require(
            bool(self.detail and self.detail.strip()),
            "a rejection must cite its evidence; one without it is refusal to work",
        )
        _require(bool(self.raised_by and self.raised_by.strip()), "raised_by is required")


@dataclass(frozen=True)
class SupersedeWorkOrderCommand:
    work_id: str
    successor_id: str
    actor: str

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(bool(self.successor_id), "successor_id is required")
        _require(self.work_id != self.successor_id, "a WorkOrder cannot supersede itself")


@dataclass(frozen=True)
class GetRuntimeState:
    work_id: str


@dataclass(frozen=True)
class GetEventHistory:
    work_id: Optional[str] = None
    since: int = 0


@dataclass(frozen=True)
class GetLifecycleCapability:
    """Which phases this runtime can currently drive a WorkOrder into."""


@dataclass(frozen=True)
class ReplayWorkOrder:
    work_id: Optional[str] = None
