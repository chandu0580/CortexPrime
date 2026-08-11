"""Dispatch decisions: what may move, in what order, and what to do with a late answer.

Pure, and therefore replayable
--------------------------------
Nothing here acquires a lease, invokes a worker, or writes an aggregate. Every
function is a decision *about* an execution, computed from the execution and a
clock reading. The dispatcher performs; this module decides, and the split is
what lets a recovery run be reasoned about without a running system.

Ordering is a correctness property, not a preference
------------------------------------------------------
Two dispatchers reading the same execution must consider work in the same order,
or a race that would have been won cleanly becomes a race that is won differently
each time and is therefore untestable. So ordering here is total and derived from
stated facts — never from ``dict`` insertion order, ``set`` iteration, object
identity, ``random``, or the accident of when a wall clock was read.

Late answers are the interesting case
---------------------------------------
A worker can return after its lease lapsed, after the node was reassigned, after
the run was cancelled, and after the run finished. In every one of those the
answer is *real* — something did happen out there — but it is no longer the
answer to the question currently being asked. Discarding it silently loses
evidence; applying it lets a dead worker resurrect a finished run. So it is
classified, recorded, and not applied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.state import ExecutionState, NodeState

__all__ = [
    "DispatchRefusal",
    "DispatchCandidate",
    "LateResultKind",
    "RecoveryUrgency",
    "dispatchable_nodes",
    "classify_result_arrival",
    "recovery_priority",
    "compensation_order",
]


class DispatchRefusal(str, Enum):
    """Why a node was not dispatched on this cycle. Never an error, always a fact."""

    EXECUTION_TERMINAL = "execution_terminal"
    EXECUTION_NOT_RUNNING = "execution_not_running"
    EXECUTION_DEADLINE_EXPIRED = "execution_deadline_expired"
    DEPENDENCIES_UNSATISFIED = "dependencies_unsatisfied"
    NODE_TERMINAL = "node_terminal"
    NODE_LEASED = "node_leased"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"
    COMPENSATION_NODE = "compensation_node"
    """A compensation node is never success-path work. It runs only when recovery
    asks for it, which is why the ordinary dispatch sweep must skip it rather
    than treat its dependencies as satisfied."""

    BLOCKED_BY_FAILURE = "blocked_by_failure"
    AWAITING_RECOVERY = "awaiting_recovery"
    """Something in this run is unresolved. Starting *more* work while an earlier
    node's outcome is unknown widens the blast radius of a situation nobody has
    established yet."""


class LateResultKind(str, Enum):
    """What kind of late answer arrived.

    Four distinct situations, because the operational response differs. A
    duplicate is noise; a result for a cancelled run means an external effect
    landed after somebody called it off, and that is an incident.
    """

    CURRENT = "current"
    """Not late at all. The holder of the live lease answering its open attempt."""

    DUPLICATE = "duplicate"
    """The same attempt answering twice. First valid answer already won."""

    SUPERSEDED_ATTEMPT = "superseded_attempt"
    """An earlier attempt answering after a later one began. The node has moved
    on; this describes a question that is no longer being asked."""

    LEASE_LOST = "lease_lost"
    """The lease lapsed or was reclaimed before the answer arrived. Whether the
    effect landed is exactly what nobody knows."""

    EXECUTION_CLOSED = "execution_closed"
    """The run completed, failed, or was cancelled first. The most serious: an
    external effect may have landed after the run was declared over."""

    @property
    def may_be_applied(self) -> bool:
        """Only a current answer may move state. Everything else is history."""
        return self is LateResultKind.CURRENT

    @property
    def is_operationally_serious(self) -> bool:
        """Whether somebody should look at this rather than merely count it."""
        return self in {
            LateResultKind.EXECUTION_CLOSED,
            LateResultKind.LEASE_LOST,
        }


class RecoveryUrgency(int, Enum):
    """How soon a run needs attention. Lower sorts first.

    Explicit integers because the ordering *is* the contract: an execution
    holding an unresolved mutation outranks one that merely stalled, and that
    must not depend on where an enum member happens to sit in a class body.
    """

    AMBIGUOUS_MUTATION = 0
    """Something may have changed production and nobody can say. Nothing outranks
    this."""

    COMPENSATION_OUTSTANDING = 1
    """A rollback is owed. Every moment it waits, the partial change stands."""

    EXPIRED_LEASE = 2
    DEADLINE_PASSED = 3
    STALLED = 4


@dataclass(frozen=True)
class DispatchCandidate:
    """One node that may be dispatched, and the facts that say so."""

    execution_id: str
    node_id: str
    tenant_id: str
    attempt_number: int
    worker_kind: str
    mutates: bool
    remaining_seconds: Optional[int] = None
    depends_on: tuple = ()
    input: Mapping[str, Any] = field(default_factory=dict)
    """The node's declared arguments, carried from the aggregate.

    A candidate is a *fact* about what may be dispatched, and what a node
    would be dispatched with is part of that fact. Re-reading it later from
    somewhere else would let the dispatched action differ from the one the
    aggregate holds."""

    def __post_init__(self) -> None:
        for label in ("execution_id", "node_id", "tenant_id"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        if self.attempt_number < 1:
            raise ContractViolation("attempt numbers start at 1")

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "tenant_id": self.tenant_id,
            "attempt_number": self.attempt_number,
            "worker_kind": self.worker_kind,
            "mutates": self.mutates,
            "remaining_seconds": self.remaining_seconds,
        }


def dispatchable_nodes(
    execution: Any,
    *,
    tenant_id: str,
    now: datetime,
    deadline_at: Optional[datetime] = None,
) -> tuple:
    """Which nodes may be dispatched, in a stable order, with reasons for the rest.

    Returns ``(candidates, refusals)`` where refusals map node id to the first
    reason that stopped it. Both are ordered by node id, so two dispatchers
    reading the same execution see the same list in the same order.

    The aggregate's ``ready_nodes`` already answers "dependencies satisfied and
    nobody holds it" from the graph. This adds what dispatch additionally needs
    to know — the run's own state, its deadline, its unresolved nodes, and the
    compensation distinction — without restating the dependency rule, which would
    give the platform two answers to one question.

    ``tenant_id`` and ``deadline_at`` are parameters rather than fields read off
    the aggregate, because the aggregate has neither. Tenancy travels on the
    ``ExecutionContext`` (ADR-017) and reading it from anywhere else would be the
    ambient tenancy that decision exists to prevent; the deadline belongs to the
    caller's authority window (ADR-038). Guessing either with ``getattr`` would
    silently produce ``None`` and disable the check it was supposed to perform.
    """
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation(
            "dispatch requires the tenant from the ExecutionContext; there is no "
            "ambient tenant and an unattributed dispatch is not dispatchable"
        )
    refusals: dict = {}

    if execution.state.is_terminal:
        return (), {n: DispatchRefusal.EXECUTION_TERMINAL for n in execution.node_ids}
    if execution.state is not ExecutionState.RUNNING:
        return (), {n: DispatchRefusal.EXECUTION_NOT_RUNNING for n in execution.node_ids}
    if deadline_at is not None and now >= deadline_at:
        # Refuse to *start* more work. Work already running keeps its own
        # outcome -- a deadline says we may not begin, never that what began
        # did not happen.
        return (), {
            n: DispatchRefusal.EXECUTION_DEADLINE_EXPIRED
            for n in execution.node_ids
            if not (run := execution.run_for(n)) or not run.state.is_terminal
        }

    # An unresolved node stops the sweep. Dispatching more work beside an outcome
    # nobody can state widens the blast radius of a situation still unexplained.
    if execution.ambiguous_nodes:
        return (), {
            n: DispatchRefusal.AWAITING_RECOVERY
            for n in execution.node_ids
            if (run := execution.run_for(n)) and not run.state.is_terminal
        }

    ready = set(execution.ready_nodes())
    blocked = set(execution.blocked_nodes())
    candidates: list = []

    for node_id in sorted(execution.node_ids):
        run = execution.run_for(node_id)
        if run is None:
            continue
        reason = _node_refusal(run, node_id, ready, blocked)
        if reason is not None:
            refusals[node_id] = reason
            continue
        candidates.append(
            DispatchCandidate(
                execution_id=str(execution.execution_id),
                node_id=node_id,
                tenant_id=tenant_id,
                attempt_number=run.attempt_count + 1,
                worker_kind=run.spec.worker_kind.value,
                mutates=run.spec.mutates,
                # Carried, not re-derived. The dispatcher must hand the gateway
                # the input the *aggregate* holds, so what is validated and
                # digested is what the run was created with.
                input=dict(run.spec.input),
                remaining_seconds=(
                    int((deadline_at - now).total_seconds())
                    if deadline_at is not None
                    else None
                ),
                depends_on=tuple(sorted(run.spec.depends_on)),
            )
        )

    return tuple(candidates), refusals


def _node_refusal(
    run: Any, node_id: str, ready: set, blocked: set
) -> Optional[DispatchRefusal]:
    """The first reason this node may not be dispatched, or None."""
    if run.state.is_terminal:
        return DispatchRefusal.NODE_TERMINAL
    if run.state is NodeState.LEASED:
        return DispatchRefusal.NODE_LEASED
    if run.spec.is_compensation:
        # Never on the success path. Recovery dispatches these explicitly.
        return DispatchRefusal.COMPENSATION_NODE
    if node_id in blocked:
        return DispatchRefusal.BLOCKED_BY_FAILURE
    if node_id not in ready:
        return DispatchRefusal.DEPENDENCIES_UNSATISFIED
    if run.attempts_remaining < 1:
        return DispatchRefusal.ATTEMPTS_EXHAUSTED
    return None


def classify_result_arrival(
    execution: Any,
    *,
    node_id: str,
    attempt_id: str,
    worker_id: str,
    now: datetime,
) -> LateResultKind:
    """Whether this answer is still the answer to the question being asked.

    Checked before anything is applied. Every non-``CURRENT`` verdict means the
    result is recorded as history and **not** used to move state — a worker that
    returns after the run was declared over must not be able to reopen it.
    """
    if not execution.is_open:
        return LateResultKind.EXECUTION_CLOSED

    run = execution.run_for(node_id)
    if run is None:
        return LateResultKind.EXECUTION_CLOSED

    known = {str(a.attempt_id) for a in run.attempts}
    if attempt_id not in known:
        # An attempt this run never had. Treated as superseded rather than
        # rejected outright: the likeliest cause is a reclaim that rewrote
        # history the worker had not seen.
        return LateResultKind.SUPERSEDED_ATTEMPT

    current = run.current_attempt
    if current is None or str(current.attempt_id) != attempt_id:
        for attempt in run.attempts:
            if str(attempt.attempt_id) == attempt_id and not attempt.is_open:
                return LateResultKind.DUPLICATE
        return LateResultKind.SUPERSEDED_ATTEMPT

    lease = run.lease
    if lease is None or lease.is_released or not lease.is_live_at(now):
        return LateResultKind.LEASE_LOST
    if lease.worker_id != worker_id:
        return LateResultKind.SUPERSEDED_ATTEMPT
    return LateResultKind.CURRENT


def recovery_priority(
    execution: Any, *, now: datetime, deadline_at: Optional[datetime] = None
) -> tuple:
    """A total, stated ordering key for recovery. Never accidental.

    ``(urgency, deadline_epoch, execution_id)`` — worst first, then soonest
    deadline, then a stable id as the final tiebreak so the order is total. The
    id is last on purpose: it decides nothing except which of two otherwise
    identical runs is looked at first, and something has to.

    ``execution_id`` is a ULID, so the final tiebreak is creation order rather
    than an arbitrary string comparison — the oldest unattended run goes first,
    which is also the fairness property callers expect.
    """
    if execution.ambiguous_nodes:
        urgency = RecoveryUrgency.AMBIGUOUS_MUTATION
    elif execution.mutated_nodes and execution.state is ExecutionState.FAILED:
        urgency = RecoveryUrgency.COMPENSATION_OUTSTANDING
    elif any(
        (run.lease is not None and not run.lease.is_released and not run.lease.is_live_at(now))
        for run in execution.runs
    ):
        urgency = RecoveryUrgency.EXPIRED_LEASE
    elif execution.state is ExecutionState.TIMED_OUT:
        urgency = RecoveryUrgency.DEADLINE_PASSED
    else:
        urgency = RecoveryUrgency.STALLED

    return (
        int(urgency),
        deadline_at.timestamp() if deadline_at is not None else float("inf"),
        str(execution.execution_id),
    )


def compensation_order(execution: Any) -> tuple:
    """Which nodes to walk back, newest change first.

    Reverse order of completion, which is the only order that respects
    dependencies: if B was built on A, undoing A before B leaves B referring to
    something that no longer exists. Completion time is read from the attempts,
    and the node id breaks ties so the order is total.
    """
    completed: list = []
    for run in execution.runs:
        if run.state is not NodeState.SUCCEEDED or not run.spec.mutates:
            continue
        last = run.last_attempt
        ended = getattr(last, "ended_at", None) if last else None
        completed.append(
            (ended.timestamp() if isinstance(ended, datetime) else 0.0, run.node_id)
        )
    return tuple(node_id for _, node_id in sorted(completed, reverse=True))
