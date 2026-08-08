"""Deterministic recovery: what to do with a run that stopped badly.

The rule this module exists to enforce is "no silent recovery". A runtime that
reacts to an odd-looking state by starting again is worse than one that stops,
because it acts on a guess at the exact moment its information is worst.

So recovery produces a **decision** -- a named action, a reason, and the
checkpoint it would resume from -- and something else carries it out. The
decision can be computed, shown to a human, logged, and recomputed later from
the same history to check it was right.

Determinism
-------------
``plan_recovery`` is a pure function of the run's own state. Same run, same plan,
every time. That is what makes it reviewable: an operator can ask "what will it
do?" before letting it do anything, and an incident review can ask "what did it
decide, and would it decide that again?"

Ordering
----------
The checks run from most-dangerous to least. Ambiguity outranks everything: a run
holding an operation whose outcome nobody knows must not be resumed, retried, or
compensated automatically, because all three assume a fact that is not in
evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "RecoveryAction",
    "RecoveryTrigger",
    "RecoveryDecision",
    "plan_recovery",
]


class RecoveryTrigger(str, Enum):
    """Why recovery is being considered at all."""

    PROCESS_RESTART = "process_restart"
    LEASE_EXPIRED = "lease_expired"
    WORKER_LOST = "worker_lost"
    TIMEOUT = "timeout"
    OPERATOR_REQUEST = "operator_request"
    RESUME_REQUEST = "resume_request"


class RecoveryAction(str, Enum):
    """The named things recovery is allowed to conclude."""

    RESUME_FROM_CHECKPOINT = "resume_from_checkpoint"
    """Nothing is in doubt. Carry on from the last authoritative boundary."""

    RETRY_ATTEMPT = "retry_attempt"
    """A node failed knowably and may be attempted again."""

    RECONCILE_EXTERNAL_STATE = "reconcile_external_state"
    """Something may or may not have happened out there. Go and look before
    doing anything else. This is the answer to a lost response."""

    COMPENSATE = "compensate"
    """Changes were applied and must be walked back."""

    WAIT_FOR_HUMAN = "wait_for_human"
    """The safe move is not derivable. Stop and say so."""

    FAIL_EXECUTION = "fail_execution"
    """Nothing is recoverable and nothing was left behind. Report it."""

    @property
    def is_automatic(self) -> bool:
        """Whether the runtime may act on this without being asked."""
        return self in {
            RecoveryAction.RESUME_FROM_CHECKPOINT,
            RecoveryAction.RETRY_ATTEMPT,
        }

    @property
    def needs_a_human(self) -> bool:
        return self in {
            RecoveryAction.WAIT_FOR_HUMAN,
            RecoveryAction.RECONCILE_EXTERNAL_STATE,
        }


@dataclass(frozen=True)
class RecoveryDecision:
    """One recovery conclusion, with the evidence behind it."""

    action: RecoveryAction
    trigger: RecoveryTrigger
    reason: str
    execution_id: str
    from_checkpoint: Optional[str] = None
    subject_nodes: tuple = ()
    ambiguous_nodes: tuple = ()

    def __post_init__(self) -> None:
        if not isinstance(self.action, RecoveryAction):
            raise ContractViolation("action must be a RecoveryAction")
        if not self.reason.strip():
            raise ContractViolation(
                "a recovery decision must say why; an unexplained recovery is a "
                "guess with a formal name"
            )
        if (
            self.action is RecoveryAction.RESUME_FROM_CHECKPOINT
            and self.ambiguous_nodes
        ):
            raise ContractViolation(
                "a run holding an unknown outcome cannot simply resume; resuming "
                "past it asserts the work did not happen, which is exactly what "
                "nobody knows"
            )

    @property
    def is_automatic(self) -> bool:
        return self.action.is_automatic

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "trigger": self.trigger.value,
            "reason": self.reason,
            "execution_id": self.execution_id,
            "from_checkpoint": self.from_checkpoint,
            "subject_nodes": list(self.subject_nodes),
            "ambiguous_nodes": list(self.ambiguous_nodes),
        }


def plan_recovery(
    execution,
    trigger: RecoveryTrigger,
    *,
    retryable_nodes: Sequence[str] = (),
) -> RecoveryDecision:
    """Decide what to do with a run that stopped badly. Pure and replayable."""
    execution_id = str(execution.execution_id)
    checkpoint = execution.latest_checkpoint
    checkpoint_id = str(checkpoint.checkpoint_id) if checkpoint else None
    mutated = tuple(execution.mutated_nodes)

    # Ambiguity has two sources and both count.
    #
    # ``ambiguous_nodes`` covers nodes left UNKNOWN by a lapsed lease. But a node
    # marked FAILED can be just as ambiguous: a network failure or a timeout ends
    # the attempt without ever establishing what the far side did. Reading only
    # the node state would let recovery resume straight past a delete that may
    # well have happened -- which is the precise failure this module exists to
    # prevent, wearing a different state name.
    ambiguous = tuple(
        sorted(
            set(execution.ambiguous_nodes)
            | {
                run.node_id
                for run in execution.runs
                if (last := run.last_attempt) is not None
                and getattr(last, "failure", None) is not None
                and last.failure.failure_class.is_ambiguous
            }
        )
    )

    # 1. Ambiguity outranks everything. Nobody may act on a fact not in evidence.
    if ambiguous:
        return RecoveryDecision(
            action=RecoveryAction.RECONCILE_EXTERNAL_STATE,
            trigger=trigger,
            reason=(
                f"{len(ambiguous)} node(s) ended with an unknown outcome "
                f"({', '.join(ambiguous)}); whether the change was applied is not "
                "recorded anywhere, so the external state must be read before the "
                "run does anything else"
            ),
            execution_id=execution_id,
            from_checkpoint=checkpoint_id,
            subject_nodes=ambiguous,
            ambiguous_nodes=ambiguous,
        )

    # 2. A finished run is not a recovery subject.
    if execution.state.is_terminal:
        return RecoveryDecision(
            action=RecoveryAction.WAIT_FOR_HUMAN,
            trigger=trigger,
            reason=(
                f"the run is already {execution.state.value}; recovering a run that "
                "has reported its outcome would rewrite the outcome"
            ),
            execution_id=execution_id,
            from_checkpoint=checkpoint_id,
        )

    # 3. Nodes that failed knowably and may be attempted again.
    if retryable_nodes:
        return RecoveryDecision(
            action=RecoveryAction.RETRY_ATTEMPT,
            trigger=trigger,
            reason=(
                f"{len(retryable_nodes)} node(s) failed knowably with attempts "
                "remaining; the outcome is not in doubt, so another attempt is safe"
            ),
            execution_id=execution_id,
            from_checkpoint=checkpoint_id,
            subject_nodes=tuple(retryable_nodes),
        )

    # 4. Nodes stuck behind a failure, with changes already applied.
    blocked = tuple(execution.blocked_nodes())
    if blocked and mutated:
        return RecoveryDecision(
            action=RecoveryAction.COMPENSATE,
            trigger=trigger,
            reason=(
                f"{len(blocked)} node(s) can never become ready and "
                f"{len(mutated)} node(s) already changed things; the run cannot "
                "finish and what it applied should be walked back"
            ),
            execution_id=execution_id,
            from_checkpoint=checkpoint_id,
            subject_nodes=mutated,
        )

    if blocked:
        return RecoveryDecision(
            action=RecoveryAction.FAIL_EXECUTION,
            trigger=trigger,
            reason=(
                f"{len(blocked)} node(s) can never become ready and nothing was "
                "changed; there is nothing to walk back and nothing left to run"
            ),
            execution_id=execution_id,
            from_checkpoint=checkpoint_id,
            subject_nodes=blocked,
        )

    # 5. Nothing outstanding and nothing in doubt.
    if not execution.outstanding_nodes:
        return RecoveryDecision(
            action=RecoveryAction.WAIT_FOR_HUMAN,
            trigger=trigger,
            reason=(
                "every node has finished but the run has not reported an outcome; "
                "completing it automatically during recovery would report success "
                "that no policy evaluation stands behind"
            ),
            execution_id=execution_id,
            from_checkpoint=checkpoint_id,
        )

    # 6. Ordinary interruption. This is the only fully automatic path.
    return RecoveryDecision(
        action=RecoveryAction.RESUME_FROM_CHECKPOINT,
        trigger=trigger,
        reason=(
            "no node is in doubt and work remains; the run can continue from "
            + (f"checkpoint {checkpoint.label!r}" if checkpoint else "the beginning")
        ),
        execution_id=execution_id,
        from_checkpoint=checkpoint_id,
        subject_nodes=tuple(execution.ready_nodes()),
    )
