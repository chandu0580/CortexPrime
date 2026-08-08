"""The plan lifecycle.

Deliberately the same shape as Intent's, because it answers the same question at
the next stage: is this thing coherent, and has somebody accepted it. Two
lifecycles that mean the same thing and are spelled differently cost more than
the duplication saves.

Revision creates a new version, it does not reopen
---------------------------------------------------
An approved plan is what execution acts on. Reopening it would mean work was
authorised against something nobody approved. So a change to an approved plan
produces a **new version** that supersedes it, and both stay on record -- which
is also what makes "what changed between v2 and v3" answerable at all.

A validated plan may still be edited, and editing sends it back to ``DRAFT``:
``VALIDATED`` is a statement about a particular graph, and adding a task makes it
a statement about a graph that no longer exists.
"""

from __future__ import annotations

from enum import Enum
from typing import Final, Mapping

__all__ = [
    "PlanStatus",
    "STATUS_TRANSITIONS",
    "TERMINAL_STATUSES",
    "is_legal_transition",
    "permitted_from",
    "refusal_reason",
]


class PlanStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STATUSES

    @property
    def is_open(self) -> bool:
        """Whether the plan may still be edited."""
        return self in (PlanStatus.DRAFT, PlanStatus.VALIDATED)

    @property
    def is_executable(self) -> bool:
        """Whether execution may act on this. One status only.

        A validated plan is sound but unauthorised; only approval says somebody
        accepted what it will do.
        """
        return self is PlanStatus.APPROVED


TERMINAL_STATUSES: Final[frozenset] = frozenset({PlanStatus.SUPERSEDED})


STATUS_TRANSITIONS: Final[Mapping[PlanStatus, frozenset]] = {
    PlanStatus.DRAFT: frozenset(
        {PlanStatus.VALIDATED, PlanStatus.REJECTED, PlanStatus.SUPERSEDED}
    ),
    PlanStatus.VALIDATED: frozenset(
        {
            PlanStatus.APPROVED,
            PlanStatus.DRAFT,
            PlanStatus.REJECTED,
            PlanStatus.SUPERSEDED,
        }
    ),
    PlanStatus.APPROVED: frozenset({PlanStatus.SUPERSEDED}),
    PlanStatus.REJECTED: frozenset({PlanStatus.SUPERSEDED}),
    PlanStatus.SUPERSEDED: frozenset(),
}


FORBIDDEN_REASONS: Final[Mapping[tuple, str]] = {
    (PlanStatus.DRAFT, PlanStatus.APPROVED): (
        "a plan is validated before it is approved; approving an unchecked graph is "
        "how a cycle or an unreachable task reaches an executor"
    ),
    (PlanStatus.APPROVED, PlanStatus.DRAFT): (
        "an approved plan is what execution acts on; reopening it would mean work "
        "was authorised against something nobody approved. Revise it into a new "
        "version instead -- both stay on record"
    ),
    (PlanStatus.APPROVED, PlanStatus.REJECTED): (
        "an approved plan is refused by superseding it, not by retracting an "
        "approval execution may already have relied on"
    ),
    (PlanStatus.REJECTED, PlanStatus.DRAFT): (
        "a refused plan is answered with a new version that cites it, so the refusal "
        "and what replaced it both stay on record"
    ),
}


def is_legal_transition(source: PlanStatus, target: PlanStatus) -> bool:
    return target in STATUS_TRANSITIONS.get(source, frozenset())


def permitted_from(source: PlanStatus) -> tuple:
    return tuple(sorted(s.value for s in STATUS_TRANSITIONS.get(source, frozenset())))


def refusal_reason(source: PlanStatus, target: PlanStatus):
    """Why a move is refused, or ``None`` if it is legal."""
    if is_legal_transition(source, target):
        return None
    named = FORBIDDEN_REASONS.get((source, target))
    if named is not None:
        return named
    if source.is_terminal:
        return (
            f"{source.value} is terminal; answer it with a new version that cites "
            "this one"
        )
    permitted = permitted_from(source)
    return f"{source.value} may only move to: {', '.join(permitted) or '(nothing)'}"
