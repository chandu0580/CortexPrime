"""The intent lifecycle.

An intent is a mandate under construction. It starts as somebody's sentence,
gains structure, is checked, and is either approved -- becoming the canonical
input to planning -- or refused.

Why expansion sends a validated intent back to draft
-----------------------------------------------------
``VALIDATED`` is a statement about a *particular* intent: these constraints, this
scope, these criteria were checked and hold together. Adding a constraint or
widening the scope afterwards makes that statement about a document that no
longer exists.

Rather than let a validated intent quietly drift, expansion returns it to
``DRAFT`` and re-validation is required. That is the expensive-looking option and
the cheap one in practice: the alternative is an intent marked validated whose
current content nobody checked, which is worse than one honestly marked draft.

Why approval is the end of the line
------------------------------------
An approved intent is what planning acts on. If it could change afterwards, the
plan would be built from something nobody approved, and the approval would be
evidence for a mandate that no longer exists. So ``APPROVED`` accepts only
supersession -- which does not change what the intent *said*, only whether it is
current.
"""

from __future__ import annotations

from enum import Enum
from typing import Final, Mapping

__all__ = [
    "IntentStatus",
    "STATUS_TRANSITIONS",
    "TERMINAL_STATUSES",
    "is_legal_transition",
    "permitted_from",
    "refusal_reason",
]


class IntentStatus(str, Enum):
    """Where an intent is in its journey from sentence to mandate."""

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
        """Whether the intent may still be edited."""
        return self in (IntentStatus.DRAFT, IntentStatus.VALIDATED)

    @property
    def is_planable(self) -> bool:
        """Whether planning may consume this. One status only.

        A validated intent is coherent but unauthorised; only approval says
        somebody accepted the mandate.
        """
        return self is IntentStatus.APPROVED


TERMINAL_STATUSES: Final[frozenset] = frozenset({IntentStatus.SUPERSEDED})


#: The complete transition table. Any transition absent here is illegal.
#:
#: * ``VALIDATED -> DRAFT`` is how expansion works: changing a validated intent
#:   invalidates the validation rather than silently keeping it.
#: * ``APPROVED`` accepts only supersession -- see the module docstring.
#: * ``REJECTED -> SUPERSEDED`` exists because a revised intent legitimately
#:   replaces a refused one, and the link is worth keeping.
STATUS_TRANSITIONS: Final[Mapping[IntentStatus, frozenset]] = {
    IntentStatus.DRAFT: frozenset(
        {IntentStatus.VALIDATED, IntentStatus.REJECTED, IntentStatus.SUPERSEDED}
    ),
    IntentStatus.VALIDATED: frozenset(
        {
            IntentStatus.APPROVED,
            IntentStatus.DRAFT,
            IntentStatus.REJECTED,
            IntentStatus.SUPERSEDED,
        }
    ),
    IntentStatus.APPROVED: frozenset({IntentStatus.SUPERSEDED}),
    IntentStatus.REJECTED: frozenset({IntentStatus.SUPERSEDED}),
    IntentStatus.SUPERSEDED: frozenset(),
}


#: Transitions ruled out with a stated reason. These are the ones attempted in
#: good faith, and a refusal that only says "illegal" teaches nobody anything.
FORBIDDEN_REASONS: Final[Mapping[tuple, str]] = {
    (IntentStatus.DRAFT, IntentStatus.APPROVED): (
        "an intent is validated before it is approved; approving an unchecked "
        "mandate is how an under-specified goal becomes an expensive plan"
    ),
    (IntentStatus.APPROVED, IntentStatus.DRAFT): (
        "an approved intent is what planning acts on; reopening it would mean the "
        "plan was built from something nobody approved. Supersede it with a "
        "revised intent instead"
    ),
    (IntentStatus.APPROVED, IntentStatus.REJECTED): (
        "an approved mandate is refused by superseding it, not by retracting the "
        "approval that planning already relied on"
    ),
    (IntentStatus.REJECTED, IntentStatus.DRAFT): (
        "a refused intent is answered with a new one that cites it, so the refusal "
        "and what replaced it both stay on record"
    ),
}


def is_legal_transition(source: IntentStatus, target: IntentStatus) -> bool:
    return target in STATUS_TRANSITIONS.get(source, frozenset())


def permitted_from(source: IntentStatus) -> tuple:
    """What ``source`` may move to, sorted. What a refusal should report."""
    return tuple(sorted(s.value for s in STATUS_TRANSITIONS.get(source, frozenset())))


def refusal_reason(source: IntentStatus, target: IntentStatus):
    """Why a move is refused, or ``None`` if it is legal."""
    if is_legal_transition(source, target):
        return None
    named = FORBIDDEN_REASONS.get((source, target))
    if named is not None:
        return named
    if source.is_terminal:
        return (
            f"{source.value} is terminal; answer it with a new intent that cites "
            "this one"
        )
    permitted = permitted_from(source)
    return f"{source.value} may only move to: {', '.join(permitted) or '(nothing)'}"
