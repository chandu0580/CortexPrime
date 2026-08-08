"""The mission timeline: append-only, gapless, and the thing replay reads.

Every movement a mission makes lands here, in order, with the reason it
happened. Constitution S4 -- *no state is exited without recording why* -- is
enforced at construction rather than checked later, so a reasonless entry cannot
be persisted and then discovered during an audit.

Why the timeline is the aggregate's spine rather than a log beside it
----------------------------------------------------------------------
A mission's status could be stored as a field and the history kept separately.
Then the two can disagree, and when they do there is no way to tell which is
wrong. Here the status is *derived* from the timeline on replay and asserted to
match the stored one, so a disagreement is a test failure rather than a support
ticket.

Sequences are gapless and monotonic. A gap makes replay ambiguous -- it cannot
tell a lost entry from one that never existed -- and an ambiguous audit trail is
not an audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.mission import MissionState
from backend.contexts.mission.domain.errors import TimelineOutOfOrder
from backend.contexts.mission.domain.status import MissionStatus

__all__ = ["TimelineEntryKind", "MissionTimelineEntry", "MissionTimeline"]


class TimelineEntryKind(str, Enum):
    """What kind of thing happened.

    Status and execution transitions are kept as *different kinds* rather than
    one, because they belong to the two different lifecycles this context
    maintains (ADR-025). Merging them would make "what state was the mission in"
    ambiguous in exactly the place it must not be.
    """

    STATUS = "status_transition"
    EXECUTION = "execution_transition"
    CHECKPOINT = "checkpoint"
    NOTE = "note"

    @property
    def moves_the_mission(self) -> bool:
        return self in (TimelineEntryKind.STATUS, TimelineEntryKind.EXECUTION)


@dataclass(frozen=True)
class MissionTimelineEntry(Contract):
    """One thing that happened to a mission, and why."""

    CONTRACT_NAME = "cortexprime.mission.timeline_entry"

    sequence: int
    kind: TimelineEntryKind
    reason: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "mission-runtime"

    from_status: Optional[MissionStatus] = None
    to_status: Optional[MissionStatus] = None
    from_execution_state: Optional[MissionState] = None
    to_execution_state: Optional[MissionState] = None
    checkpoint_id: Optional[str] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ContractViolation("sequence must be a positive integer starting at 1")
        if not isinstance(self.kind, TimelineEntryKind):
            raise ContractViolation("kind must be a TimelineEntryKind")

        # Constitution S4: no state is exited without recording why.
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ContractViolation(
                "every timeline entry records why it happened; a movement with no "
                "reason cannot be audited and cannot be explained to whoever asks"
            )
        if not isinstance(self.actor, str) or not self.actor.strip():
            raise ContractViolation("every timeline entry names who caused it")
        if self.occurred_at.tzinfo is None:
            raise ContractViolation("occurred_at must be timezone-aware")

        if self.kind is TimelineEntryKind.STATUS:
            if self.to_status is None:
                raise ContractViolation("a status entry must record the status reached")
            if self.from_status is None:
                raise ContractViolation("a status entry must record where it came from")
            if self.from_status is self.to_status:
                raise ContractViolation(
                    f"a status entry must record a movement; {self.to_status.value} "
                    "to itself is not one"
                )
        elif self.kind is TimelineEntryKind.EXECUTION:
            if self.to_execution_state is None or self.from_execution_state is None:
                raise ContractViolation(
                    "an execution entry must record both states it moved between"
                )
        elif self.kind is TimelineEntryKind.CHECKPOINT:
            if not (self.checkpoint_id and self.checkpoint_id.strip()):
                raise ContractViolation("a checkpoint entry must name its checkpoint")


@dataclass(frozen=True)
class MissionTimeline:
    """The ordered record. Append-only."""

    entries: tuple = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise ContractViolation("entries must be a tuple")
        for index, entry in enumerate(self.entries, start=1):
            if not isinstance(entry, MissionTimelineEntry):
                raise ContractViolation(
                    f"timeline entry {index} is not a MissionTimelineEntry"
                )
            if entry.sequence != index:
                raise TimelineOutOfOrder(expected=index, received=entry.sequence)

    # -- queries -------------------------------------------------------

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    @property
    def next_sequence(self) -> int:
        return len(self.entries) + 1

    @property
    def is_empty(self) -> bool:
        return not self.entries

    @property
    def last(self) -> Optional[MissionTimelineEntry]:
        return self.entries[-1] if self.entries else None

    def of_kind(self, kind: TimelineEntryKind) -> tuple:
        return tuple(e for e in self.entries if e.kind is kind)

    @property
    def status_transitions(self) -> tuple:
        return self.of_kind(TimelineEntryKind.STATUS)

    @property
    def execution_transitions(self) -> tuple:
        return self.of_kind(TimelineEntryKind.EXECUTION)

    @property
    def checkpoints_reached(self) -> tuple:
        return self.of_kind(TimelineEntryKind.CHECKPOINT)

    # -- append --------------------------------------------------------

    def append(self, entry: MissionTimelineEntry) -> "MissionTimeline":
        """Add an entry. Refuses anything that would break the sequence."""
        if not isinstance(entry, MissionTimelineEntry):
            raise ContractViolation("entry must be a MissionTimelineEntry")
        if entry.sequence != self.next_sequence:
            raise TimelineOutOfOrder(
                expected=self.next_sequence, received=entry.sequence
            )
        return MissionTimeline(entries=self.entries + (entry,))

    # -- replay --------------------------------------------------------

    def replay_status(self, initial: MissionStatus = MissionStatus.DRAFT) -> MissionStatus:
        """Rebuild the mission's status by walking the timeline.

        The aggregate stores its status *and* derives it here, and a test asserts
        the two agree. That is what makes the timeline authoritative rather than
        decorative: if they ever disagree, one of them is a bug, and the test
        says so before an auditor does.
        """
        status = initial
        for entry in self.entries:
            if entry.kind is TimelineEntryKind.STATUS and entry.to_status is not None:
                status = entry.to_status
        return status

    def replay_execution_state(
        self, initial: MissionState = MissionState.RECEIVED
    ) -> MissionState:
        """Rebuild the execution state by walking the timeline."""
        state = initial
        for entry in self.entries:
            if (
                entry.kind is TimelineEntryKind.EXECUTION
                and entry.to_execution_state is not None
            ):
                state = entry.to_execution_state
        return state
