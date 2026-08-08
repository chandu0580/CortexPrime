"""Commands and queries for the Mission Runtime context.

Frozen values naming one intent each, carrying primitives rather than domain
objects so a command can be serialised, queued, and replayed without dragging the
domain across the wire.

Every command that moves a mission carries a ``reason`` and an ``actor``.
Constitution S4 -- *no state is exited without recording why* -- is enforced at
the aggregate, but requiring it here means a caller is refused before the
transition is attempted rather than after.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "CreateMission",
    "RecordPlan",
    "DeclarePrecondition",
    "SatisfyPrecondition",
    "TransitionMission",
    "StartMission",
    "PauseMission",
    "ResumeMission",
    "AdvanceExecution",
    "RecordCheckpoint",
    "CompleteMission",
    "FailMission",
    "CancelMission",
    "ArchiveMission",
    "GetMission",
    "GetTimeline",
    "ListMissions",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


def _require_movement(reason: str, actor: str) -> None:
    _require(
        bool(reason and reason.strip()),
        "a reason is required; Constitution S4 forbids exiting a state without "
        "recording why",
    )
    _require(bool(actor and actor.strip()), "an actor is required; every movement names who caused it")


@dataclass(frozen=True)
class CreateMission:
    stated_goal: str
    title: str
    kind: str
    priority: str = "routine"
    target: Optional[str] = None
    tags: tuple = ()
    preconditions: tuple = ()

    def __post_init__(self) -> None:
        _require(
            bool(self.stated_goal and self.stated_goal.strip()),
            "stated_goal is required; the requester's own words are what makes it "
            "auditable whether the mission solved the stated problem",
        )
        _require(bool(self.title and self.title.strip()), "title is required")
        _require(bool(self.kind), "kind is required")


@dataclass(frozen=True)
class RecordPlan:
    mission_id: str
    plan_id: str
    produced_by: str = "planner"
    revision: Optional[str] = None
    reason: str = "a plan was produced"
    actor: str = "planner"

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require(
            bool(self.plan_id and self.plan_id.strip()),
            "plan_id is required; Mission Runtime does not plan, so it records "
            "where the plan lives",
        )
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class DeclarePrecondition:
    mission_id: str
    key: str
    description: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require(bool(self.key and self.key.strip()), "a precondition needs a key")


@dataclass(frozen=True)
class SatisfyPrecondition:
    mission_id: str
    key: str
    satisfied_by: str
    note: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require(bool(self.key), "key is required")
        _require(
            bool(self.satisfied_by and self.satisfied_by.strip()),
            "satisfying a precondition must say who did so; an unattributed "
            "clearance has nobody accountable for it",
        )


@dataclass(frozen=True)
class TransitionMission:
    """A generic move. Used for ``planned`` and ``ready``.

    The moves with side effects -- starting, pausing, resuming, finishing --
    have their own commands, because each does something beyond changing a
    status and a generic command would hide it.
    """

    mission_id: str
    to_status: str
    reason: str
    actor: str

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require(bool(self.to_status), "to_status is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class StartMission:
    mission_id: str
    reason: str = "cleared to run"
    actor: str = "orchestrator"
    executor_ref: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class PauseMission:
    mission_id: str
    reason: str
    actor: str = "operator"

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class ResumeMission:
    mission_id: str
    reason: str = "resuming"
    actor: str = "operator"
    from_checkpoint: Optional[str] = None
    executor_ref: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class AdvanceExecution:
    """Move the Constitution S4 execution state.

    Mission Runtime does not decide these -- Execution and Verification do. This
    records the movement they report.
    """

    mission_id: str
    to_state: str
    reason: str
    actor: str = "execution"

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require(bool(self.to_state), "to_state is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class RecordCheckpoint:
    mission_id: str
    label: str
    payload_ref: Optional[str] = None
    payload_digest: Optional[str] = None
    actor: str = "execution"

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require(
            bool(self.label and self.label.strip()),
            "a checkpoint must be labelled; an unlabelled resumption point tells "
            "whoever resumes nothing about what they are resuming into",
        )


@dataclass(frozen=True)
class CompleteMission:
    mission_id: str
    reason: str = "objective achieved"
    actor: str = "orchestrator"

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class FailMission:
    mission_id: str
    reason: str
    actor: str = "orchestrator"

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class CancelMission:
    mission_id: str
    reason: str
    actor: str

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class ArchiveMission:
    mission_id: str
    reason: str = "record sealed"
    actor: str = "operator"

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require_movement(self.reason, self.actor)


@dataclass(frozen=True)
class GetMission:
    mission_id: str


@dataclass(frozen=True)
class GetTimeline:
    mission_id: str


@dataclass(frozen=True)
class ListMissions:
    status: Optional[str] = None
    kind: Optional[str] = None
    priority: Optional[str] = None
    live_only: bool = False
