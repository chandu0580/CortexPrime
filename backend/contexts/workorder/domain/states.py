"""The WorkOrder lifecycle, as data.

Engineering Constitution §3 is normative. This module encodes it so that an
invalid transition is impossible rather than merely discouraged.

Two tables, and the second is the one that earns its keep:

:data:`ALLOWED` is what may happen. :data:`FORBIDDEN` is what may *not*, with
the reason attached. A transition absent from both is rejected with a generic
message; a transition in ``FORBIDDEN`` is rejected with the specific reason it
was ruled out.

That distinction matters because the forbidden transitions are the ones people
attempt in good faith. ``Implementation -> SpecTests`` looks like a harmless
reordering, and refusing it with "not allowed" teaches nothing. Refusing it with
*"tests written after seeing the implementation test what the code does, not what
it should do"* teaches the rule.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping, Optional

__all__ = [
    "WorkOrderState",
    "ALLOWED",
    "FORBIDDEN",
    "TERMINAL_STATES",
    "GOVERNED_STATES",
    "transition_reason",
    "is_allowed",
]


class WorkOrderState(str, Enum):
    """Where a WorkOrder is in its life.

    ``str``-valued so a state survives serialization without a lookup table and
    reads correctly in a log line.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    BLOCKED = "blocked"
    ASSIGNED = "assigned"
    SPEC_TESTS = "spec_tests"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    VERIFICATION = "verification"
    READY = "ready"
    MERGED = "merged"
    CLOSED = "closed"
    REJECTED = "rejected"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STATES

    @property
    def is_governed(self) -> bool:
        """Whether the approval digest binds in this state.

        True from ``APPROVED`` onward. Before approval a WorkOrder is still
        being composed and has no digest to bind.
        """
        return self in GOVERNED_STATES


TERMINAL_STATES = frozenset({WorkOrderState.CLOSED, WorkOrderState.REJECTED})

GOVERNED_STATES = frozenset(
    {
        WorkOrderState.APPROVED,
        WorkOrderState.BLOCKED,
        WorkOrderState.ASSIGNED,
        WorkOrderState.SPEC_TESTS,
        WorkOrderState.IMPLEMENTATION,
        WorkOrderState.REVIEW,
        WorkOrderState.VERIFICATION,
        WorkOrderState.READY,
        WorkOrderState.MERGED,
        WorkOrderState.CLOSED,
    }
)


#: Every permitted transition. Engineering Constitution §3.2.
ALLOWED: Mapping[WorkOrderState, frozenset] = {
    WorkOrderState.DRAFT: frozenset({WorkOrderState.APPROVED, WorkOrderState.REJECTED}),
    WorkOrderState.APPROVED: frozenset({WorkOrderState.BLOCKED, WorkOrderState.ASSIGNED}),
    WorkOrderState.BLOCKED: frozenset({WorkOrderState.APPROVED}),
    WorkOrderState.ASSIGNED: frozenset({WorkOrderState.SPEC_TESTS}),
    WorkOrderState.SPEC_TESTS: frozenset(
        {WorkOrderState.IMPLEMENTATION, WorkOrderState.REJECTED}
    ),
    WorkOrderState.IMPLEMENTATION: frozenset({WorkOrderState.REVIEW, WorkOrderState.REJECTED}),
    WorkOrderState.REVIEW: frozenset(
        {WorkOrderState.VERIFICATION, WorkOrderState.IMPLEMENTATION, WorkOrderState.REJECTED}
    ),
    WorkOrderState.VERIFICATION: frozenset(
        {WorkOrderState.READY, WorkOrderState.IMPLEMENTATION, WorkOrderState.REJECTED}
    ),
    WorkOrderState.READY: frozenset({WorkOrderState.MERGED, WorkOrderState.VERIFICATION}),
    WorkOrderState.MERGED: frozenset({WorkOrderState.CLOSED}),
    WorkOrderState.CLOSED: frozenset(),
    WorkOrderState.REJECTED: frozenset(),
}


#: Transitions ruled out on purpose, each with the reason. §3.3.
FORBIDDEN: Mapping[tuple, str] = {
    (WorkOrderState.DRAFT, WorkOrderState.ASSIGNED): (
        "unapproved work would consume a blast-radius lock and block approved work"
    ),
    (WorkOrderState.IMPLEMENTATION, WorkOrderState.SPEC_TESTS): (
        "tests written after seeing the implementation test what the code does, "
        "not what it should do"
    ),
    (WorkOrderState.IMPLEMENTATION, WorkOrderState.VERIFICATION): (
        "skipping review leaves the party that must reproduce claims as the only "
        "adversarial read, collapsing two independent stances into one"
    ),
    (WorkOrderState.REVIEW, WorkOrderState.READY): (
        "review reads the diff; it does not re-run the evidence. A green review "
        "is not a reproduction"
    ),
    (WorkOrderState.VERIFICATION, WorkOrderState.MERGED): (
        "no agent may merge; merge is the human gate"
    ),
    (WorkOrderState.ASSIGNED, WorkOrderState.IMPLEMENTATION): (
        "spec tests are authored before implementation begins"
    ),
    (WorkOrderState.APPROVED, WorkOrderState.IMPLEMENTATION): (
        "spec tests are authored before implementation begins"
    ),
    (WorkOrderState.READY, WorkOrderState.CLOSED): (
        "a WorkOrder closes after merging, not instead of it"
    ),
}

# Re-entering APPROVED from anywhere other than BLOCKED is forbidden from every
# governed state: approval is single-use and bound to a digest. A changed
# WorkOrder is a new WorkOrder, not a re-approved one.
_REAPPROVAL_REASON = (
    "approval is single-use and bound to a digest; a changed WorkOrder is a new "
    "WorkOrder with a new id, not a re-approval"
)
for _state in WorkOrderState:
    if _state in (WorkOrderState.DRAFT, WorkOrderState.BLOCKED, WorkOrderState.APPROVED):
        continue
    FORBIDDEN.setdefault((_state, WorkOrderState.APPROVED), _REAPPROVAL_REASON)  # type: ignore[attr-defined]

# Nothing leaves a terminal state.
_TERMINAL_REASON = (
    "terminal; answer it with a new WorkOrder that cites this one rather than "
    "reopening a decision that was already recorded"
)
for _terminal in TERMINAL_STATES:
    for _target in WorkOrderState:
        if _target is _terminal:
            continue
        FORBIDDEN.setdefault((_terminal, _target), _TERMINAL_REASON)  # type: ignore[attr-defined]

del _state, _terminal, _target


def is_allowed(current: WorkOrderState, requested: WorkOrderState) -> bool:
    """Whether the machine permits this move."""
    return requested in ALLOWED.get(current, frozenset())


def transition_reason(current: WorkOrderState, requested: WorkOrderState) -> Optional[str]:
    """Why a transition is refused, or ``None`` if it is permitted.

    A named reason where one exists; a generic message otherwise. Callers use
    this to build the refusal, so the specific reasons reach the person who
    attempted the transition rather than sitting unread in this module.
    """
    if is_allowed(current, requested):
        return None
    named = FORBIDDEN.get((current, requested))
    if named is not None:
        return named
    permitted = sorted(s.value for s in ALLOWED.get(current, frozenset()))
    if not permitted:
        return f"{current.value} is terminal"
    return f"{current.value} may only move to: {', '.join(permitted)}"
