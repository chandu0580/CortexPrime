"""The state machine executor and transition validator.

Two responsibilities, kept separate because they fail differently:

:class:`TransitionValidator` decides whether a move is *legal*. Pure, cheap, and
answerable without touching anything -- it reads the transition table and the
caller's stated precondition.

:class:`StateMachineExecutor` decides whether a legal move is *permitted right
now*. That needs policy, which needs a snapshot, which needs the port.

The order is load-bearing. Legality is checked first, before any collaborator is
called, because an orchestrator that discovers a move is illegal by attempting it
has already started it -- and the half-done work is what has to be undone. There
is nothing to roll back from a refusal that happened before anything began.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contexts.engineering.errors import (
    IllegalTransition,
    PhaseUnknown,
    PolicyRefused,
    PreconditionFailed,
)
from backend.contexts.engineering.policy import EngineeringPolicy, PolicyResult
from backend.contexts.engineering.ports import (
    PHASE_TRANSITIONS,
    WorkOrderPhase,
    WorkOrderSnapshot,
)

__all__ = ["TransitionValidator", "StateMachineExecutor", "TransitionDecision", "coerce_phase"]


#: Transitions ruled out with a stated reason, mirroring Engineering
#: Constitution §3.3. A move absent from both this and PHASE_TRANSITIONS is
#: refused generically; one named here is refused with the argument, because
#: these are the ones attempted in good faith.
_FORBIDDEN_REASONS = {
    (WorkOrderPhase.DRAFT, WorkOrderPhase.ASSIGNED): (
        "unapproved work would consume a blast-radius lock and block approved work"
    ),
    (WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.SPEC_TESTS): (
        "tests written after seeing the implementation test what the code does, "
        "not what it should do"
    ),
    (WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.VERIFICATION): (
        "skipping review leaves the party that must reproduce claims as the only "
        "adversarial read, collapsing two independent stances into one"
    ),
    (WorkOrderPhase.REVIEW, WorkOrderPhase.READY): (
        "review reads the diff; it does not re-run the evidence. A green review is "
        "not a reproduction"
    ),
    (WorkOrderPhase.VERIFICATION, WorkOrderPhase.MERGED): (
        "no agent may merge; merge is the human gate"
    ),
    (WorkOrderPhase.ASSIGNED, WorkOrderPhase.IMPLEMENTATION): (
        "spec tests are authored before implementation begins"
    ),
    (WorkOrderPhase.APPROVED, WorkOrderPhase.IMPLEMENTATION): (
        "spec tests are authored before implementation begins"
    ),
}


def coerce_phase(value: Any) -> WorkOrderPhase:
    """Turn a string or phase into a phase, refusing anything else."""
    if isinstance(value, WorkOrderPhase):
        return value
    try:
        return WorkOrderPhase(value)
    except (ValueError, TypeError) as exc:
        raise PhaseUnknown(value, [p.value for p in WorkOrderPhase]) from exc


@dataclass(frozen=True)
class TransitionDecision:
    """The outcome of asking whether a transition may proceed."""

    snapshot: WorkOrderSnapshot
    to_phase: WorkOrderPhase
    policy: PolicyResult

    @property
    def transition(self) -> tuple:
        return (self.snapshot.phase, self.to_phase)

    @property
    def label(self) -> str:
        return f"{self.snapshot.phase.value} -> {self.to_phase.value}"


class TransitionValidator:
    """Decides legality. Pure -- no ports, no policy, no I/O."""

    @staticmethod
    def is_legal(current: WorkOrderPhase, requested: WorkOrderPhase) -> bool:
        return requested in PHASE_TRANSITIONS.get(current, frozenset())

    @staticmethod
    def refusal_reason(current: WorkOrderPhase, requested: WorkOrderPhase) -> Optional[str]:
        """Why a move is refused, or ``None`` if it is legal."""
        if TransitionValidator.is_legal(current, requested):
            return None
        named = _FORBIDDEN_REASONS.get((current, requested))
        if named is not None:
            return named
        if current.is_terminal:
            return (
                f"{current.value} is terminal; answer it with a new WorkOrder that cites "
                "this one rather than reopening a decision already recorded"
            )
        if requested is WorkOrderPhase.APPROVED and current is not WorkOrderPhase.BLOCKED:
            return (
                "approval is single-use and bound to a digest; a changed WorkOrder is a "
                "new WorkOrder, not a re-approval"
            )
        permitted = sorted(p.value for p in PHASE_TRANSITIONS.get(current, frozenset()))
        return f"{current.value} may only move to: {', '.join(permitted) or '(nothing)'}"

    @staticmethod
    def validate(
        snapshot: WorkOrderSnapshot,
        requested: WorkOrderPhase,
        *,
        expected_phase: Optional[WorkOrderPhase] = None,
    ) -> None:
        """Raise unless the move is legal from the observed phase.

        ``expected_phase`` is optimistic concurrency. A caller that states what
        it believed the phase was gets refused when something moved it in
        between, rather than having its command applied to a state its author
        never saw.
        """
        if expected_phase is not None and snapshot.phase is not expected_phase:
            raise PreconditionFailed(
                work_id=snapshot.work_id,
                expected=expected_phase.value,
                actual=snapshot.phase.value,
            )

        reason = TransitionValidator.refusal_reason(snapshot.phase, requested)
        if reason is not None:
            raise IllegalTransition(
                work_id=snapshot.work_id,
                current=snapshot.phase.value,
                requested=requested.value,
                reason=reason,
            )


class StateMachineExecutor:
    """Validates legality, then policy. Decides; does not act.

    Deliberately returns a decision rather than performing the transition. The
    runtime performs it, because performing it means writing to the log and
    calling the port -- and an executor that did those could not be tested
    without both.
    """

    def __init__(self, policy: EngineeringPolicy) -> None:
        self._policy = policy

    @property
    def policy(self) -> EngineeringPolicy:
        return self._policy

    def decide(
        self,
        snapshot: WorkOrderSnapshot,
        requested: Any,
        context: Any,
        *,
        expected_phase: Optional[Any] = None,
    ) -> TransitionDecision:
        """Whether this transition may proceed, and what policy found.

        Order: phase parsing, then legality, then policy. Policy is last because
        it is the only expensive step, and an illegal transition should not pay
        for it.
        """
        to_phase = coerce_phase(requested)
        expected = coerce_phase(expected_phase) if expected_phase is not None else None

        TransitionValidator.validate(snapshot, to_phase, expected_phase=expected)

        result = self._policy.evaluate(snapshot, to_phase, context)
        if not result.permitted:
            raise PolicyRefused(
                work_id=snapshot.work_id,
                transition=f"{snapshot.phase.value} -> {to_phase.value}",
                failures=result.blocking,
            )

        return TransitionDecision(snapshot=snapshot, to_phase=to_phase, policy=result)
