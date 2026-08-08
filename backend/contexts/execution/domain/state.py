"""Execution and node state machines.

Two levels, and they answer different questions
-------------------------------------------------
``ExecutionState`` is the run as a whole: is it queued, running, paused, or
finished. ``NodeState`` is one node within it.

They are separate because a running execution contains nodes in every state at
once, and an execution that is paused contains nodes that are *not* paused --
they are still running until they finish or their leases lapse. Collapsing the
two would make "is this execution running" unanswerable for exactly the
population that matters.

``UNKNOWN`` is a node state, and it is the important one
----------------------------------------------------------
A lease that expires without a result does not mean the node failed. It means
nothing is known: the work may have completed, may be half-applied, may never
have started. ``FAILED`` would be a lie that reads as information, and
``SUCCEEDED`` would be worse.

Recording ``UNKNOWN`` honestly is what lets the retry rule work -- a node in this
state may only be re-attempted if the action is idempotent, because a retry that
applies a second time is exactly what the unknown covers.

The published vocabulary
-------------------------
``contracts/execution.py`` publishes ``ExecutionStatus`` and this context is its
owner (BC-5). Node outcomes map onto it, and a drift test asserts the mapping
stays total -- a node state with no published equivalent would be a result this
context could record and nothing else could read.
"""

from __future__ import annotations

from enum import Enum
from typing import Final, Mapping

from backend.contracts.execution import ExecutionStatus

__all__ = [
    "ExecutionState",
    "NodeState",
    "EXECUTION_TRANSITIONS",
    "NODE_TRANSITIONS",
    "TERMINAL_STATES",
    "is_legal_execution_transition",
    "is_legal_node_transition",
    "execution_permitted_from",
    "node_permitted_from",
    "execution_refusal_reason",
    "published_status_of",
]


class ExecutionState(str, Enum):
    """Where a run is."""

    PENDING = "pending"
    """Accepted, nothing dispatched yet."""

    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STATES

    @property
    def is_live(self) -> bool:
        """Whether work may be in flight under this run right now."""
        return self in (ExecutionState.RUNNING, ExecutionState.PAUSED)

    @property
    def accepts_dispatch(self) -> bool:
        """Only a running execution hands out work.

        A paused one deliberately does not: pausing that kept dispatching would
        be a pause nobody could rely on.
        """
        return self is ExecutionState.RUNNING

    @property
    def is_open(self) -> bool:
        return not self.is_terminal


TERMINAL_STATES: Final[frozenset] = frozenset(
    {
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
        ExecutionState.TIMED_OUT,
    }
)


class NodeState(str, Enum):
    """Where one node within a run is."""

    WAITING = "waiting"
    """Dependencies not yet satisfied."""

    READY = "ready"
    """Dependencies satisfied, nothing has taken it."""

    LEASED = "leased"
    """A worker holds it and is running it."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    """The lease lapsed without a result. Whether it ran is not knowable."""

    SKIPPED = "skipped"
    """A branch went the other way, or the run stopped before reaching it."""

    COMPENSATED = "compensated"
    """It ran and has since been walked back."""

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_NODE_STATES

    @property
    def is_finished(self) -> bool:
        """Whether the execution may complete with this node in this state.

        ``UNKNOWN`` is terminal but **not** finished. A run cannot report success
        over a node nobody can say ran, so it must be resolved -- retried,
        skipped deliberately, or compensated -- before completion.
        """
        return self in (
            NodeState.SUCCEEDED,
            NodeState.SKIPPED,
            NodeState.COMPENSATED,
        )

    @property
    def satisfies_dependents(self) -> bool:
        """Whether nodes waiting on this one may now proceed.

        Only success and a deliberate skip. A failure, an unknown or a
        compensation all mean the thing downstream nodes needed did not happen.
        """
        return self in (NodeState.SUCCEEDED, NodeState.SKIPPED)

    @property
    def is_retryable(self) -> bool:
        return self in (NodeState.FAILED, NodeState.UNKNOWN)

    @property
    def is_ambiguous(self) -> bool:
        """Whether the world may have changed without the record saying so."""
        return self is NodeState.UNKNOWN


_TERMINAL_NODE_STATES: Final[frozenset] = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.UNKNOWN,
        NodeState.SKIPPED,
        NodeState.COMPENSATED,
    }
)


#: The run's transition table.
#:
#: ``PAUSED -> COMPLETED`` is absent deliberately: a paused run is resumed and
#: then completes, so that "completed" always follows a moment when the run was
#: actually working. ``TIMED_OUT`` is reachable from ``PAUSED`` because a
#: deadline does not stop applying while a run is suspended.
EXECUTION_TRANSITIONS: Final[Mapping[ExecutionState, frozenset]] = {
    ExecutionState.PENDING: frozenset(
        {ExecutionState.RUNNING, ExecutionState.CANCELLED, ExecutionState.TIMED_OUT}
    ),
    ExecutionState.RUNNING: frozenset(
        {
            ExecutionState.PAUSED,
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.TIMED_OUT,
        }
    ),
    ExecutionState.PAUSED: frozenset(
        {
            ExecutionState.RUNNING,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.TIMED_OUT,
        }
    ),
    ExecutionState.COMPLETED: frozenset(),
    ExecutionState.FAILED: frozenset(),
    ExecutionState.CANCELLED: frozenset(),
    ExecutionState.TIMED_OUT: frozenset(),
}


#: One node's transition table.
#:
#: ``LEASED -> READY`` is the reclaim path: a lease that lapsed with no result
#: sends the node to ``UNKNOWN``, not back to ready, because "we do not know"
#: must be recorded before anything decides what to do about it.
NODE_TRANSITIONS: Final[Mapping[NodeState, frozenset]] = {
    NodeState.WAITING: frozenset({NodeState.READY, NodeState.SKIPPED}),
    NodeState.READY: frozenset({NodeState.LEASED, NodeState.SKIPPED}),
    NodeState.LEASED: frozenset(
        {
            NodeState.SUCCEEDED,
            NodeState.FAILED,
            NodeState.UNKNOWN,
        }
    ),
    NodeState.SUCCEEDED: frozenset({NodeState.COMPENSATED}),
    NodeState.FAILED: frozenset({NodeState.READY, NodeState.SKIPPED}),
    NodeState.UNKNOWN: frozenset(
        {NodeState.READY, NodeState.SKIPPED, NodeState.COMPENSATED}
    ),
    NodeState.SKIPPED: frozenset(),
    NodeState.COMPENSATED: frozenset(),
}


#: Node outcomes projected onto the published ``ExecutionStatus``.
#:
#: ``UNKNOWN`` maps to ``FAILED`` on the way out and the loss is deliberate and
#: stated: the published vocabulary has no "we cannot tell" and inventing one
#: here would fork a contract this context owns but does not get to change
#: unilaterally. Downstream sees a failure; the ambiguity stays in this context's
#: own record, where the retry rule can act on it.
_PUBLISHED_STATUS: Final[Mapping[NodeState, ExecutionStatus]] = {
    NodeState.WAITING: ExecutionStatus.PENDING,
    NodeState.READY: ExecutionStatus.PENDING,
    NodeState.LEASED: ExecutionStatus.RUNNING,
    NodeState.SUCCEEDED: ExecutionStatus.SUCCEEDED,
    NodeState.FAILED: ExecutionStatus.FAILED,
    NodeState.UNKNOWN: ExecutionStatus.FAILED,
    NodeState.SKIPPED: ExecutionStatus.REFUSED,
    NodeState.COMPENSATED: ExecutionStatus.COMPENSATED,
}


def published_status_of(state: NodeState) -> ExecutionStatus:
    """Project a node state onto the published vocabulary.

    Total by construction; a drift test asserts every member is covered, so a
    new node state cannot ship as a result nothing else can read.
    """
    return _PUBLISHED_STATUS[state]


def is_legal_execution_transition(source: ExecutionState, target: ExecutionState) -> bool:
    return target in EXECUTION_TRANSITIONS.get(source, frozenset())


def is_legal_node_transition(source: NodeState, target: NodeState) -> bool:
    return target in NODE_TRANSITIONS.get(source, frozenset())


def execution_permitted_from(source: ExecutionState) -> tuple:
    return tuple(sorted(s.value for s in EXECUTION_TRANSITIONS.get(source, frozenset())))


def node_permitted_from(source: NodeState) -> tuple:
    return tuple(sorted(s.value for s in NODE_TRANSITIONS.get(source, frozenset())))


FORBIDDEN_REASONS: Final[Mapping[tuple, str]] = {
    (ExecutionState.PAUSED, ExecutionState.COMPLETED): (
        "a paused run is resumed and then completes, so that 'completed' always "
        "follows a moment when the run was actually working"
    ),
    (ExecutionState.PENDING, ExecutionState.COMPLETED): (
        "a run that never started completed nothing; cancel it instead, or every "
        "success-rate figure computed from this table is wrong"
    ),
    (ExecutionState.PENDING, ExecutionState.FAILED): (
        "a run that never started did not fail; cancel it instead"
    ),
}


def execution_refusal_reason(source: ExecutionState, target: ExecutionState):
    """Why a move is refused, or ``None`` if it is legal."""
    if is_legal_execution_transition(source, target):
        return None
    named = FORBIDDEN_REASONS.get((source, target))
    if named is not None:
        return named
    if source.is_terminal:
        return (
            f"{source.value} is terminal; a finished run is answered with a new "
            "execution that cites this one"
        )
    permitted = execution_permitted_from(source)
    return f"{source.value} may only move to: {', '.join(permitted) or '(nothing)'}"
