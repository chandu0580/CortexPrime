"""Mission vocabulary.

Owner: BC-1 Intent & Mission.

Constitution S4 defines the mission lifecycle and its rules. This module encodes
the state machine as data so that legal transitions are a single, testable
declaration rather than conditionals scattered across the codebase.

The rules encoded here, each from Constitution S4:

* ``AWAITING_DECISION`` is reachable from any active state -- new evidence can
  raise risk mid-execution.
* ``EXECUTING`` never reaches ``CONCLUDED`` directly; verification is mandatory.
* ``COMPENSATING`` is a first-class path, not a failure state.
* No state is exited without recording why.

This module contains vocabulary and legality checks only. Persisting missions,
running them, and recovering them belong to BC-1. See ADR-002.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.identity import SecurityContext

__all__ = [
    "MissionState",
    "MissionRef",
    "MissionIntent",
    "MissionTransition",
    "TaskState",
    "TaskRef",
    "LEGAL_TRANSITIONS",
    "is_legal_transition",
]


class MissionState(str, Enum):
    """Every state a mission can occupy (Constitution S4)."""

    RECEIVED = "received"
    INTERPRETED = "interpreted"
    GATHERING = "gathering"
    REASONING = "reasoning"
    PLANNED = "planned"
    AWAITING_DECISION = "awaiting_decision"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPENSATING = "compensating"
    CONCLUDED = "concluded"
    BLOCKED = "blocked"
    ABANDONED = "abandoned"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_STATES

    @property
    def is_active(self) -> bool:
        return not self.is_terminal


_TERMINAL_STATES = frozenset(
    {
        MissionState.CONCLUDED,
        MissionState.ABANDONED,
        MissionState.FAILED,
    }
)

#: The complete transition table. Any transition absent here is illegal.
#:
#: ``BLOCKED`` is non-terminal: a blocked mission awaits a human and resumes.
#: That is an acceptable outcome under Constitution S6 ("prefer blocked over
#: wrong"), so it must be able to return to the flow.
LEGAL_TRANSITIONS: Mapping[MissionState, frozenset[MissionState]] = {
    MissionState.RECEIVED: frozenset({MissionState.INTERPRETED, MissionState.ABANDONED}),
    MissionState.INTERPRETED: frozenset({MissionState.GATHERING, MissionState.ABANDONED}),
    MissionState.GATHERING: frozenset(
        {MissionState.REASONING, MissionState.BLOCKED, MissionState.FAILED}
    ),
    MissionState.REASONING: frozenset(
        {MissionState.PLANNED, MissionState.GATHERING, MissionState.BLOCKED, MissionState.FAILED}
    ),
    MissionState.PLANNED: frozenset(
        {
            MissionState.AWAITING_DECISION,
            MissionState.EXECUTING,
            MissionState.BLOCKED,
            MissionState.ABANDONED,
        }
    ),
    MissionState.AWAITING_DECISION: frozenset(
        {MissionState.EXECUTING, MissionState.BLOCKED, MissionState.ABANDONED}
    ),
    # Execution never reaches CONCLUDED directly -- verification is mandatory.
    MissionState.EXECUTING: frozenset(
        {
            MissionState.VERIFYING,
            MissionState.COMPENSATING,
            MissionState.AWAITING_DECISION,
            MissionState.FAILED,
        }
    ),
    MissionState.VERIFYING: frozenset(
        {
            MissionState.CONCLUDED,
            MissionState.COMPENSATING,
            MissionState.REASONING,
            MissionState.BLOCKED,
            MissionState.FAILED,
        }
    ),
    MissionState.COMPENSATING: frozenset(
        {MissionState.CONCLUDED, MissionState.BLOCKED, MissionState.FAILED}
    ),
    MissionState.BLOCKED: frozenset(
        {
            MissionState.GATHERING,
            MissionState.REASONING,
            MissionState.PLANNED,
            MissionState.AWAITING_DECISION,
            MissionState.EXECUTING,
            MissionState.ABANDONED,
        }
    ),
    MissionState.CONCLUDED: frozenset(),
    MissionState.ABANDONED: frozenset(),
    MissionState.FAILED: frozenset(),
}


def is_legal_transition(source: MissionState, target: MissionState) -> bool:
    """Whether a mission may move from ``source`` to ``target``."""
    if not isinstance(source, MissionState) or not isinstance(target, MissionState):
        raise ContractViolation("both states must be MissionState members")
    return target in LEGAL_TRANSITIONS[source]


class TaskState(str, Enum):
    """State of one node in a mission's task graph."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    COMPENSATED = "compensated"

    @property
    def is_terminal(self) -> bool:
        return self in {
            TaskState.SUCCEEDED,
            TaskState.FAILED,
            TaskState.SKIPPED,
            TaskState.COMPENSATED,
        }


@dataclass(frozen=True)
class MissionRef(Contract):
    """A stable reference to a mission."""

    CONTRACT_NAME = "cortexprime.mission.ref"

    mission_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise ContractViolation("mission_id must be a non-blank string")


@dataclass(frozen=True)
class MissionIntent(Contract):
    """The goal a mission exists to achieve, as stated by its requester.

    ``stated_goal`` preserves the requester's own words verbatim. Storing only
    an interpretation would make it impossible to audit whether CortexPrime
    solved the problem it was actually asked to solve.
    """

    CONTRACT_NAME = "cortexprime.mission.intent"

    stated_goal: str
    requested_by: SecurityContext
    requested_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.stated_goal, str) or not self.stated_goal.strip():
            raise ContractViolation("stated_goal must be non-blank")
        if self.requested_at.tzinfo is None:
            raise ContractViolation("requested_at must be timezone-aware")


@dataclass(frozen=True)
class MissionTransition(Contract):
    """One recorded movement between mission states.

    Constitution S4: "No state may be exited without recording why." ``reason``
    is therefore mandatory, and legality is checked at construction so an
    illegal transition cannot be persisted and later replayed.
    """

    CONTRACT_NAME = "cortexprime.mission.transition"

    mission: MissionRef
    from_state: MissionState
    to_state: MissionState
    reason: str
    occurred_at: datetime
    sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.from_state, MissionState) or not isinstance(
            self.to_state, MissionState
        ):
            raise ContractViolation("transition states must be MissionState members")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ContractViolation(
                "reason must be recorded; no state is exited without recording why"
            )
        if self.occurred_at.tzinfo is None:
            raise ContractViolation("occurred_at must be timezone-aware")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise ContractViolation("sequence must be a non-negative integer")
        if not is_legal_transition(self.from_state, self.to_state):
            raise ContractViolation(
                f"illegal mission transition: {self.from_state.value} -> {self.to_state.value}"
            )


@dataclass(frozen=True)
class TaskRef(Contract):
    """A node in a mission's task graph.

    ``depends_on`` names other tasks within the same mission. Cycles are
    forbidden by Constitution S4; detecting them requires the whole graph, so
    that check belongs to BC-1. What is enforced here is local: a task cannot
    depend on itself.
    """

    CONTRACT_NAME = "cortexprime.mission.task_ref"

    mission: MissionRef
    task_id: str
    purpose: str
    state: TaskState
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    execution_key: Optional[str] = None

    def __post_init__(self) -> None:
        for label, value in (("task_id", self.task_id), ("purpose", self.purpose)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")
        if not isinstance(self.state, TaskState):
            raise ContractViolation("state must be a TaskState")
        if not isinstance(self.depends_on, tuple):
            raise ContractViolation("depends_on must be a tuple (contracts are immutable)")
        if self.task_id in self.depends_on:
            raise ContractViolation("a task must not depend on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ContractViolation("depends_on must not contain duplicates")
