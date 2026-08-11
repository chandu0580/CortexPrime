"""Production-lifecycle facts that no existing event already states.

The test each one had to pass
-------------------------------
"Is this a fact some existing event already records?" Most candidates failed it
and are absent:

``NodeReady`` — derivable from the graph plus recorded outcomes, and emitted per
node per cycle it would bury everything else in a stream an operator reads during
an incident. Replay computes readiness from what is here.

``DispatchRefused`` — the ordinary state of a healthy run is "most nodes are not
dispatchable yet". An event per refusal per cycle is a metric wearing an event's
clothes, and the metrics seam is where it belongs.

``RetryStarted`` — ``ExecutionRetried`` (ADR-031) already says a node returned to
the ready pool, and ``ExecutionAssigned`` says the new attempt began. A third
event between them would describe the gap rather than a fact.

The five below survived, each because nothing else says it
------------------------------------------------------------
``RecoveryPlanned``       — a decision was reached about a stopped run. The
                            record that says *why* the next thing happened.
``CompensationStarted``   — a rollback was dispatched. Distinct from an ordinary
                            assignment: it means the forward path already failed.
``CompensationConcluded`` — a rollback ended, and **whether it worked**, which is
                            not the same question as whether it ran.
``PartiallyRecovered``    — some changes were walked back and some were not. The
                            state the platform must be able to express, because
                            the alternative is calling it success or calling it
                            failure and erasing the half that is true.
``LateResultDiscarded``   — a worker answered too late and the answer was kept as
                            history rather than applied. Auditable because an
                            external effect may have landed after the run closed.

Every one describes something that already happened
-----------------------------------------------------
No event here commands the aggregate. ``CompensationConcluded`` is emitted after
the compensation result exists, never to request one; ``RecoveryPlanned`` records
a decision already made. An event that arrives before its fact is a lie the log
tells consistently.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "ExecutionRecoveryPlanned",
    "NodeCompensationConcluded",
    "ExecutionPartiallyRecovered",
    "LateResultDiscarded",
    "LIFECYCLE_EVENT_TYPES",
]


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class ExecutionRecoveryPlanned(DomainEvent):
    """A recovery decision was reached for a run that stopped badly.

    Carries the decision *and its evidence*. During an incident the question is
    never only "what did it decide" but "on what basis" — and reconstructing the
    basis later from a bare action name is guesswork.
    """

    EVENT_TYPE = "execution.runtime.recovery_planned"

    execution_id: str = ""
    action: str = ""
    trigger: str = ""
    reason: str = ""
    from_checkpoint: str = ""
    subject_nodes: tuple = ()
    ambiguous_nodes: tuple = ()
    automatic: bool = False
    """Whether the runtime may act on this unasked. ``WAIT_FOR_HUMAN`` and
    ``RECONCILE_EXTERNAL_STATE`` are false, and that is the field that decides
    whether anything happens next without a person."""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("action", self.action)
        _require_text("reason", self.reason)


# ``NodeCompensationStarted`` was removed in Phase 5.3, and its absence is the
# honest state rather than an oversight.
#
# It declared that "a compensating action was dispatched for a node that had
# succeeded", and required a ``compensating_node_id`` -- the node running the
# undo. **Nothing in this platform dispatches one.** ``Execution.compensate``
# marks a node ``COMPENSATED``; it does not run a compensating action, because
# no compensating action exists to run. So the event could never be constructed
# with a truthful ``compensating_node_id``, and it never was: it had zero
# construction sites anywhere in the codebase.
#
# An operator subscribing to ``execution.runtime.compensation_started`` would
# have waited forever while believing they had compensation observability. That
# is worse than having none, which is why the class is gone rather than
# documented as unemitted. When something genuinely dispatches a compensating
# node, this comes back with the field it needs.


@dataclass(frozen=True)
class NodeCompensationConcluded(DomainEvent):
    """A compensating action ended, and whether the change was actually undone.

    ``outcome`` and ``change_remains`` are two different questions. A
    compensation that ran and failed leaves the change in place; a compensation
    whose outcome is unknown *may* leave it in place, and that is not the same as
    knowing it does. Reporting "rollback completed" for either is the failure
    this event exists to make impossible.
    """

    EVENT_TYPE = "execution.runtime.compensation_concluded"

    execution_id: str = ""
    node_id: str = ""
    compensating_node_id: str = ""
    outcome: str = ""
    change_remains: bool = True
    """Whether the original change is still out there. Defaults to ``True``:
    assuming a rollback worked is exactly the assumption that leaves a production
    change standing while the record says it was undone."""

    outcome_known: bool = False
    failure_class: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("node_id", self.node_id)
        _require_text("outcome", self.outcome)
        if self.outcome_known is False and self.change_remains is False:
            raise ContractViolation(
                "a compensation whose outcome is unknown cannot assert the change "
                "was removed; not knowing is precisely not knowing that"
            )


@dataclass(frozen=True)
class ExecutionPartiallyRecovered(DomainEvent):
    """Some changes were walked back and some were not.

    The state the platform must be able to express. Calling this success hides
    a live production change; calling it failure erases the rollbacks that did
    work. Both are worse than saying what is true.
    """

    EVENT_TYPE = "execution.runtime.partially_recovered"

    execution_id: str = ""
    compensated_nodes: tuple = ()
    outstanding_nodes: tuple = ()
    ambiguous_nodes: tuple = ()
    original_failure: str = ""
    """Preserved deliberately. A partial recovery that lost the reason the
    recovery began is a record of half an incident."""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        if not self.outstanding_nodes and not self.ambiguous_nodes:
            raise ContractViolation(
                "a partial recovery must name what is still outstanding; one with "
                "nothing left is a complete recovery and should say so"
            )


@dataclass(frozen=True)
class LateResultDiscarded(DomainEvent):
    """A worker answered after its answer stopped being the current one.

    Kept as history and not applied. ``kind`` distinguishes the merely noisy
    (a duplicate) from the serious (an effect that may have landed after the run
    was declared over), and ``may_have_mutated`` is the field an operator reads
    first.
    """

    EVENT_TYPE = "execution.runtime.late_result_discarded"

    execution_id: str = ""
    node_id: str = ""
    attempt_id: str = ""
    worker_id: str = ""
    kind: str = ""
    reported_outcome: str = ""
    may_have_mutated: bool = False
    operationally_serious: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("node_id", self.node_id)
        _require_text("kind", self.kind)


LIFECYCLE_EVENT_TYPES = (
    ExecutionRecoveryPlanned,
    NodeCompensationConcluded,
    ExecutionPartiallyRecovered,
    LateResultDiscarded,
)
