"""The workflow lifecycle.

Four gates rather than the three Plan and Intent use, because compilation is a
real step here and not a synonym for validation:

* ``VALIDATED`` -- the graph is well-formed. Acyclic, fully reachable, every plan
  task covered, every branch defaulted, every parallel group independent.
* ``COMPILED`` -- the *derived* form is frozen: execution order, compensation
  order, the critical path. Execution reads those rather than recomputing them,
  which is what makes two runs of one workflow provably the same shape.
* ``APPROVED`` -- somebody accepted what it will do.

Separating validation from compilation earns its keep at the third state:
recomputing an execution order at run time means two executors can disagree about
a graph both consider valid. Freezing it means they cannot.

Editing sends the workflow back to ``DRAFT`` from either ``VALIDATED`` or
``COMPILED`` -- a compiled order is a statement about a particular graph, and
adding a node makes it a statement about a graph that no longer exists.
"""

from __future__ import annotations

from enum import Enum
from typing import Final, Mapping

__all__ = [
    "WorkflowStatus",
    "STATUS_TRANSITIONS",
    "TERMINAL_STATUSES",
    "is_legal_transition",
    "permitted_from",
    "refusal_reason",
]


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    COMPILED = "compiled"
    APPROVED = "approved"
    SUPERSEDED = "superseded"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STATUSES

    @property
    def is_open(self) -> bool:
        """Whether the graph may still be edited."""
        return self in (
            WorkflowStatus.DRAFT,
            WorkflowStatus.VALIDATED,
            WorkflowStatus.COMPILED,
        )

    @property
    def is_executable(self) -> bool:
        """Whether execution may run this. One status only."""
        return self is WorkflowStatus.APPROVED

    @property
    def has_frozen_order(self) -> bool:
        """Whether the derived execution order is bound and may be relied on."""
        return self in (WorkflowStatus.COMPILED, WorkflowStatus.APPROVED)


TERMINAL_STATUSES: Final[frozenset] = frozenset({WorkflowStatus.SUPERSEDED})


STATUS_TRANSITIONS: Final[Mapping[WorkflowStatus, frozenset]] = {
    WorkflowStatus.DRAFT: frozenset({WorkflowStatus.VALIDATED, WorkflowStatus.SUPERSEDED}),
    WorkflowStatus.VALIDATED: frozenset(
        {WorkflowStatus.COMPILED, WorkflowStatus.DRAFT, WorkflowStatus.SUPERSEDED}
    ),
    WorkflowStatus.COMPILED: frozenset(
        {WorkflowStatus.APPROVED, WorkflowStatus.DRAFT, WorkflowStatus.SUPERSEDED}
    ),
    WorkflowStatus.APPROVED: frozenset({WorkflowStatus.SUPERSEDED}),
    WorkflowStatus.SUPERSEDED: frozenset(),
}


FORBIDDEN_REASONS: Final[Mapping[tuple, str]] = {
    (WorkflowStatus.DRAFT, WorkflowStatus.COMPILED): (
        "a workflow is validated before it is compiled; compiling an unchecked graph "
        "freezes an execution order derived from a cycle or an unreachable node"
    ),
    (WorkflowStatus.DRAFT, WorkflowStatus.APPROVED): (
        "a workflow is validated and compiled before it is approved; approving an "
        "uncompiled graph authorises an execution order nobody has seen"
    ),
    (WorkflowStatus.VALIDATED, WorkflowStatus.APPROVED): (
        "the execution order is frozen at compilation; approving before it would "
        "authorise a graph without authorising the order it runs in"
    ),
    (WorkflowStatus.APPROVED, WorkflowStatus.DRAFT): (
        "an approved workflow is what execution runs; reopening it would mean work "
        "ran against something nobody approved. Revise it into a new version"
    ),
}


def is_legal_transition(source: WorkflowStatus, target: WorkflowStatus) -> bool:
    return target in STATUS_TRANSITIONS.get(source, frozenset())


def permitted_from(source: WorkflowStatus) -> tuple:
    return tuple(sorted(s.value for s in STATUS_TRANSITIONS.get(source, frozenset())))


def refusal_reason(source: WorkflowStatus, target: WorkflowStatus):
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
