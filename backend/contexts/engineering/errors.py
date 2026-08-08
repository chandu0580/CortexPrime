"""Failures raised by the Engineering Runtime.

Every one is a refusal. The runtime never repairs a bad transition, never
substitutes a legal move for an illegal one, and never proceeds past a failed
policy check. EP-6: ambiguity resolves to refusal.
"""

from __future__ import annotations

from typing import Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "EngineeringRuntimeError",
    "IllegalTransition",
    "PhaseUnknown",
    "PreconditionFailed",
    "PolicyRefused",
    "CollaboratorUnavailable",
    "ConcurrentModification",
    "WorkOrderUnknown",
    "TransitionRolledBack",
]


class EngineeringRuntimeError(ContractViolation):
    """Base for every runtime refusal."""


class IllegalTransition(EngineeringRuntimeError):
    """A move the Engineering Constitution's state machine does not permit.

    Refused before any collaborator is called. An orchestrator that discovers a
    move is illegal by attempting it has already started it, and the half-done
    work is what has to be undone.
    """

    def __init__(self, *, work_id: str, current: str, requested: str, reason: str) -> None:
        super().__init__(f"WorkOrder {work_id}: {current} -> {requested} refused. {reason}")
        self.work_id = work_id
        self.current = current
        self.requested = requested
        self.reason = reason


class PhaseUnknown(EngineeringRuntimeError):
    def __init__(self, value: object, permitted: Sequence[str]) -> None:
        super().__init__(
            f"{value!r} is not a WorkOrder phase; permitted: {', '.join(sorted(permitted))}"
        )
        self.value = value


class PreconditionFailed(EngineeringRuntimeError):
    """The caller's stated expectation about current state did not hold.

    Optimistic concurrency: a command may declare the phase it believes the
    WorkOrder is in. If something moved it in between, the command is refused
    rather than applied to a state its author never saw.
    """

    def __init__(self, *, work_id: str, expected: str, actual: str) -> None:
        super().__init__(
            f"WorkOrder {work_id}: expected phase {expected!r} but found {actual!r}; "
            "the WorkOrder moved after this command was composed"
        )
        self.work_id = work_id
        self.expected = expected
        self.actual = actual


class PolicyRefused(EngineeringRuntimeError):
    """One or more policy checks refused the transition.

    Carries every failure rather than the first: fixing them one round-trip at a
    time is how a transition takes six attempts to land.
    """

    def __init__(self, *, work_id: str, transition: str, failures: tuple) -> None:
        summary = "; ".join(f"{f.check}: {f.detail}" for f in failures[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(f"WorkOrder {work_id}: {transition} refused by policy -- {summary}{more}")
        self.work_id = work_id
        self.transition = transition
        self.failures = failures


class CollaboratorUnavailable(EngineeringRuntimeError):
    """A port the transition needs has no adapter wired.

    Raised rather than skipped. A phase that requires review and proceeds
    without one because nothing was listening is worse than a phase that stops:
    the first produces an unreviewed merge that looks reviewed.
    """

    def __init__(self, *, port: str, needed_for: str) -> None:
        super().__init__(
            f"{needed_for} requires the {port} port, which has no adapter wired; "
            "refusing rather than proceeding unorchestrated"
        )
        self.port = port
        self.needed_for = needed_for


class ConcurrentModification(EngineeringRuntimeError):
    """Two transitions raced on the same WorkOrder."""

    def __init__(self, *, work_id: str, detail: str) -> None:
        super().__init__(f"WorkOrder {work_id}: concurrent modification -- {detail}")
        self.work_id = work_id
        self.detail = detail


class WorkOrderUnknown(EngineeringRuntimeError):
    def __init__(self, work_id: str) -> None:
        super().__init__(f"the WorkOrder port knows no WorkOrder {work_id}")
        self.work_id = work_id


class TransitionRolledBack(EngineeringRuntimeError):
    """A transition failed after it began and was undone.

    The cause travels with it. A rollback whose reason is lost leaves an
    operator knowing only that something failed and was reversed, which is the
    least actionable message a system can produce.
    """

    def __init__(self, *, work_id: str, transition: str, cause: BaseException) -> None:
        super().__init__(
            f"WorkOrder {work_id}: {transition} was rolled back after "
            f"{type(cause).__name__}: {cause}"
        )
        self.work_id = work_id
        self.transition = transition
        self.cause = cause
