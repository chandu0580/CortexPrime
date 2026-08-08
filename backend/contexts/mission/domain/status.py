"""The operational lifecycle Mission Runtime owns.

Two lifecycles, and the distinction is the whole design
--------------------------------------------------------
A mission has two state machines, and conflating them was the alternative this
context deliberately rejected (ADR-025).

:class:`MissionStatus` -- **this module** -- is *operational*: is this mission
drafted, cleared to run, running, paused, or finished? It governs the mission as
a managed thing, and Mission Runtime owns it.

``contracts.mission.MissionState`` -- **already published**, Constitution S4 --
is *execution*: has this mission's current run been interpreted, gathered,
reasoned, planned, executed, verified? It governs one cognitive pass, and the
Execution and Verification contexts drive it. Mission Runtime records it and
gates on it; it does not advance it.

They are genuinely different questions. "Monitor Production Kubernetes Cluster"
is ``RUNNING`` for months while its execution state cycles through gathering,
reasoning and verifying many times over. A single machine would have to be
either the operational one (losing mandatory verification) or the cognitive one
(unable to express *paused*).

The gate that keeps them honest
--------------------------------
``RUNNING -> COMPLETED`` is refused unless the execution state has reached
``CONCLUDED``. Constitution S4 already forbids ``EXECUTING -> CONCLUDED``
directly, so verification cannot be skipped on either side. Without that gate the
operational machine would let a mission report success over work nobody checked,
which is the exact failure S4 exists to prevent.
"""

from __future__ import annotations

from enum import Enum
from typing import Final, Mapping

__all__ = [
    "MissionStatus",
    "STATUS_TRANSITIONS",
    "TERMINAL_STATUSES",
    "OUTCOME_STATUSES",
    "is_legal_status_transition",
    "permitted_from",
]


class MissionStatus(str, Enum):
    """Where a mission is as a managed objective."""

    DRAFT = "draft"
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"

    @property
    def is_terminal(self) -> bool:
        """Nothing follows. Only ``ARCHIVED`` -- an outcome is not the end.

        ``COMPLETED``, ``FAILED`` and ``CANCELLED`` are *outcomes*; each still
        has archival ahead of it, which is where the record is sealed.
        """
        return self is MissionStatus.ARCHIVED

    @property
    def is_outcome(self) -> bool:
        """Whether the mission has stopped, however it stopped."""
        return self in OUTCOME_STATUSES

    @property
    def is_live(self) -> bool:
        """Whether work may be happening under this mission right now."""
        return self in (MissionStatus.RUNNING, MissionStatus.PAUSED)

    @property
    def accepts_checkpoints(self) -> bool:
        """A checkpoint records progress, so there must be progress to record."""
        return self is MissionStatus.RUNNING

    @property
    def is_open(self) -> bool:
        """Whether the mission may still be driven."""
        return not self.is_terminal


#: Outcomes: the mission stopped. Archival still follows.
OUTCOME_STATUSES: Final[frozenset] = frozenset(
    {MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED}
)

#: Terminal: nothing follows at all.
TERMINAL_STATUSES: Final[frozenset] = frozenset({MissionStatus.ARCHIVED})


#: The complete transition table. Any transition absent here is illegal.
#:
#: Notes on the non-obvious entries:
#:
#: * ``CANCELLED`` is reachable from every pre-outcome state. A mission can be
#:   called off at any point before it has an answer, and a lifecycle that forced
#:   a mission to run to completion in order to stop it would be worse than one
#:   that permits cancellation.
#: * ``FAILED`` is reachable only from ``RUNNING`` and ``PAUSED``. A mission that
#:   never ran did not fail -- it was cancelled, and recording it as a failure
#:   would corrupt every failure-rate figure computed from this table.
#: * ``PLANNED -> DRAFT`` exists: replanning is normal, and forcing a new mission
#:   for a revised plan would lose the objective's history.
#: * ``READY -> PLANNED`` exists for the same reason -- a precondition can lapse
#:   after readiness was declared.
#: * Every outcome leads to ``ARCHIVED`` and nowhere else.
STATUS_TRANSITIONS: Final[Mapping[MissionStatus, frozenset]] = {
    MissionStatus.DRAFT: frozenset({MissionStatus.PLANNED, MissionStatus.CANCELLED}),
    MissionStatus.PLANNED: frozenset(
        {MissionStatus.READY, MissionStatus.DRAFT, MissionStatus.CANCELLED}
    ),
    MissionStatus.READY: frozenset(
        {MissionStatus.RUNNING, MissionStatus.PLANNED, MissionStatus.CANCELLED}
    ),
    MissionStatus.RUNNING: frozenset(
        {
            MissionStatus.PAUSED,
            MissionStatus.COMPLETED,
            MissionStatus.FAILED,
            MissionStatus.CANCELLED,
        }
    ),
    MissionStatus.PAUSED: frozenset(
        {MissionStatus.RUNNING, MissionStatus.FAILED, MissionStatus.CANCELLED}
    ),
    MissionStatus.COMPLETED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.FAILED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.CANCELLED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.ARCHIVED: frozenset(),
}


#: Transitions ruled out with a stated reason. A move absent from both this and
#: :data:`STATUS_TRANSITIONS` is refused generically; one named here is refused
#: with the argument, because these are the ones attempted in good faith.
FORBIDDEN_REASONS: Final[Mapping[tuple, str]] = {
    (MissionStatus.DRAFT, MissionStatus.RUNNING): (
        "a mission cannot run before it is planned and cleared; starting from draft "
        "would execute an objective nobody scoped"
    ),
    (MissionStatus.DRAFT, MissionStatus.READY): (
        "readiness is a statement about a plan, and no plan has been recorded"
    ),
    (MissionStatus.PLANNED, MissionStatus.RUNNING): (
        "a planned mission still has to be cleared to run; skipping readiness "
        "skips the precondition check"
    ),
    (MissionStatus.READY, MissionStatus.COMPLETED): (
        "a mission that never ran has not completed anything"
    ),
    (MissionStatus.DRAFT, MissionStatus.FAILED): (
        "a mission that never ran did not fail; cancel it instead, or every "
        "failure-rate figure computed from this lifecycle is wrong"
    ),
    (MissionStatus.READY, MissionStatus.FAILED): (
        "a mission that never ran did not fail; cancel it instead"
    ),
    (MissionStatus.PLANNED, MissionStatus.FAILED): (
        "a mission that never ran did not fail; cancel it instead"
    ),
    (MissionStatus.ARCHIVED, MissionStatus.RUNNING): (
        "an archived mission is sealed; answer it with a new mission that cites "
        "this one rather than reopening a record whose digest is published"
    ),
}


def is_legal_status_transition(source: MissionStatus, target: MissionStatus) -> bool:
    """Whether a mission may move from ``source`` to ``target``."""
    return target in STATUS_TRANSITIONS.get(source, frozenset())


def permitted_from(source: MissionStatus) -> tuple:
    """What ``source`` may move to, sorted. What a refusal should report."""
    return tuple(sorted(s.value for s in STATUS_TRANSITIONS.get(source, frozenset())))


def refusal_reason(source: MissionStatus, target: MissionStatus):
    """Why a move is refused, or ``None`` if it is legal."""
    if is_legal_status_transition(source, target):
        return None
    named = FORBIDDEN_REASONS.get((source, target))
    if named is not None:
        return named
    if source.is_terminal:
        return (
            f"{source.value} is terminal; answer it with a new mission that cites "
            "this one rather than reopening a record already sealed"
        )
    permitted = permitted_from(source)
    return f"{source.value} may only move to: {', '.join(permitted) or '(nothing)'}"
