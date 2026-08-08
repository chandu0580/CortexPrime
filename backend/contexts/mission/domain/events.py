"""Mission lifecycle events.

Namespaced ``mission.runtime.*``. ``CONTRACT_NAME`` is globally unique and a
clash raises at import time.

Every event that reports a movement carries its **reason**, because Constitution
S4 requires that no state is exited without recording why -- and an event stream
that dropped the reason would be a worse record than the aggregate it describes.

These events describe *lifecycle*, never work. There is no ``MissionExecuted``,
no ``FindingProduced``, no ``PlanGenerated``: Mission Runtime orchestrates work
and performs none, so it has nothing to say about what the work found.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "MissionCreated",
    "MissionStarted",
    "MissionPaused",
    "MissionResumed",
    "MissionCheckpointReached",
    "MissionCompleted",
    "MissionFailed",
    "MissionCancelled",
    "MissionArchived",
    "MISSION_EVENT_TYPES",
]

AGGREGATE_TYPE = "mission"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class MissionCreated(DomainEvent):
    """A mission was drafted, carrying the requester's own words."""

    EVENT_TYPE = "mission.runtime.created"

    mission_id: str = ""
    title: str = ""
    kind: str = ""
    priority: str = ""
    stated_goal: str = ""
    requested_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text("title", self.title)
        _require_text("kind", self.kind)
        _require_text(
            "stated_goal",
            self.stated_goal,
        )


@dataclass(frozen=True)
class MissionStarted(DomainEvent):
    """The mission began running, on a specific execution attempt."""

    EVENT_TYPE = "mission.runtime.started"

    mission_id: str = ""
    execution_id: str = ""
    attempt: int = 1
    reason: str = ""
    actor: str = ""
    resumed_from_checkpoint: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text("execution_id", self.execution_id)
        _require_text("reason", self.reason)
        if self.attempt < 1:
            raise ContractViolation("attempt starts at 1")


@dataclass(frozen=True)
class MissionPaused(DomainEvent):
    """Running was suspended.

    ``resumable_from`` is empty when no checkpoint exists, which means resuming
    restarts the run. Carried explicitly rather than omitted, because the absence
    is the operationally interesting half.
    """

    EVENT_TYPE = "mission.runtime.paused"

    mission_id: str = ""
    reason: str = ""
    actor: str = ""
    resumable_from: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class MissionResumed(DomainEvent):
    EVENT_TYPE = "mission.runtime.resumed"

    mission_id: str = ""
    execution_id: str = ""
    attempt: int = 1
    reason: str = ""
    actor: str = ""
    resumed_from_checkpoint: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class MissionCheckpointReached(DomainEvent):
    """A recoverable position was recorded."""

    EVENT_TYPE = "mission.runtime.checkpoint_reached"

    mission_id: str = ""
    checkpoint_id: str = ""
    sequence: int = 1
    label: str = ""
    execution_state: str = ""
    digest: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text("checkpoint_id", self.checkpoint_id)
        _require_text("label", self.label)
        _require_text("execution_state", self.execution_state)
        _require_text("digest", self.digest)
        if self.sequence < 1:
            raise ContractViolation("checkpoint sequence starts at 1")


@dataclass(frozen=True)
class MissionCompleted(DomainEvent):
    """The mission achieved its objective, on verified work.

    Refuses construction unless the execution state is ``concluded``. Since
    Constitution S4 forbids ``EXECUTING -> CONCLUDED`` directly, an event
    reporting completion is also evidence that verification ran. An event that
    could describe an unverified completion would make the log a worse record
    than the aggregate.
    """

    EVENT_TYPE = "mission.runtime.completed"

    mission_id: str = ""
    execution_state: str = ""
    executions: int = 1
    checkpoints: int = 0
    reason: str = ""
    actor: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text("reason", self.reason)
        if self.execution_state != "concluded":
            raise ContractViolation(
                f"a mission cannot be reported complete with its execution "
                f"{self.execution_state!r}; Constitution S4 requires verification "
                "before an execution concludes"
            )


@dataclass(frozen=True)
class MissionFailed(DomainEvent):
    """The mission ran and did not achieve its objective."""

    EVENT_TYPE = "mission.runtime.failed"

    mission_id: str = ""
    reason: str = ""
    actor: str = ""
    execution_state: str = ""
    attempts: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text(
            "reason",
            self.reason,
        )
        if self.attempts < 1:
            raise ContractViolation(
                "a failed mission ran at least once; one that never ran was cancelled"
            )


@dataclass(frozen=True)
class MissionCancelled(DomainEvent):
    """The mission was called off before it produced an answer."""

    EVENT_TYPE = "mission.runtime.cancelled"

    mission_id: str = ""
    reason: str = ""
    actor: str = ""
    cancelled_from: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text("reason", self.reason)
        _require_text("actor", self.actor)


@dataclass(frozen=True)
class MissionArchived(DomainEvent):
    """The record was sealed. What follows is bound to this digest."""

    EVENT_TYPE = "mission.runtime.archived"

    mission_id: str = ""
    digest: str = ""
    final_status: str = ""
    timeline_entries: int = 0
    reason: str = ""
    actor: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("mission_id", self.mission_id)
        _require_text("digest", self.digest)
        _require_text("final_status", self.final_status)
        if self.timeline_entries < 1:
            raise ContractViolation(
                "an archived mission has a timeline; one with no entries records "
                "nothing that happened"
            )


MISSION_EVENT_TYPES = (
    MissionCreated,
    MissionStarted,
    MissionPaused,
    MissionResumed,
    MissionCheckpointReached,
    MissionCompleted,
    MissionFailed,
    MissionCancelled,
    MissionArchived,
)
