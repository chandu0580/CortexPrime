"""Failures raised by the Execution Runtime.

Every one is a refusal to let a run reach a state nobody can describe afterwards.

The failures here are different in kind from the earlier contexts'. Intent, Plan
and Workflow refuse *documents* that are wrong. This refuses *actions* that are
wrong while work is in flight -- a second worker taking a node the first already
holds, a result written by nobody's authority, a completion declared while a node
is still running. Those are the failures whose cost is a change in the world that
the record does not match.
"""

from __future__ import annotations

from typing import Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "ExecutionError",
    "InvalidIdentifier",
    "IllegalExecutionTransition",
    "IllegalNodeTransition",
    "ExecutionFinished",
    "UnknownNode",
    "DependenciesUnsatisfied",
    "NodeNotRunning",
    "LeaseNotHeld",
    "LeaseExpired",
    "NodeAlreadyLeased",
    "AttemptsExhausted",
    "AmbiguousRetry",
    "RetryRefused",
    "IncompleteExecution",
    "NoCheckpoint",
    "CheckpointAhead",
    "UnknownWorker",
    "WorkerCannotRun",
    "ExecutionRefused",
    "DigestMismatch",
    "DigestNotComputed",
    "ExecutionNotFound",
    "DuplicateExecution",
]


class ExecutionError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(ExecutionError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class IllegalExecutionTransition(ExecutionError):
    def __init__(
        self, *, execution_id: str, source: str, target: str, permitted: Sequence[str]
    ) -> None:
        allowed = ", ".join(sorted(permitted)) or "(nothing -- this state is terminal)"
        super().__init__(
            f"execution {execution_id} cannot move {source} -> {target}; {source} may "
            f"only move to: {allowed}"
        )
        self.execution_id = execution_id
        self.source = source
        self.target = target
        self.permitted = tuple(permitted)


class IllegalNodeTransition(ExecutionError):
    def __init__(
        self, *, node_id: str, source: str, target: str, permitted: Sequence[str]
    ) -> None:
        allowed = ", ".join(sorted(permitted)) or "(nothing)"
        super().__init__(
            f"node {node_id!r} cannot move {source} -> {target}; {source} may only "
            f"move to: {allowed}"
        )
        self.node_id = node_id
        self.source = source
        self.target = target
        self.permitted = tuple(permitted)


class ExecutionFinished(ExecutionError):
    """The run is over and may not be driven further."""

    def __init__(self, *, execution_id: str, state: str, operation: str) -> None:
        super().__init__(
            f"execution {execution_id} is {state}; {operation} would change a run that "
            "has already reported its outcome"
        )
        self.execution_id = execution_id
        self.state = state
        self.operation = operation


class RetryRefused(ExecutionError):
    """A retry was asked for and the runtime declined to run it.

    Distinct from ``AttemptsExhausted``: that one means there is no budget left,
    this one means the runtime decided a further attempt is not safe or not
    worthwhile. The verdict says which.
    """

    def __init__(
        self, *, execution_id: str, node_id: str, verdict: str, reason: str
    ) -> None:
        super().__init__(
            f"retry of {node_id!r} in execution {execution_id} was refused "
            f"({verdict}): {reason}"
        )
        self.execution_id = execution_id
        self.node_id = node_id
        self.verdict = verdict
        self.reason = reason


class UnknownNode(ExecutionError):
    def __init__(self, *, execution_id: str, node_id: str) -> None:
        super().__init__(
            f"execution {execution_id} was not given a node {node_id!r}; the workflow "
            "it is running does not contain one"
        )
        self.execution_id = execution_id
        self.node_id = node_id


class DependenciesUnsatisfied(ExecutionError):
    """A node was dispatched before what it waits for finished.

    The scheduling invariant. Running a node whose inputs are not ready produces
    a result computed from state that does not exist yet, and nothing downstream
    can tell that from a real one.
    """

    def __init__(self, *, node_id: str, waiting_on: Sequence[str]) -> None:
        listed = ", ".join(sorted(waiting_on))
        super().__init__(
            f"node {node_id!r} still waits for {listed}; dispatching it now would "
            "compute a result from state that does not exist yet"
        )
        self.node_id = node_id
        self.waiting_on = tuple(waiting_on)


class NodeNotRunning(ExecutionError):
    def __init__(self, *, node_id: str, state: str) -> None:
        super().__init__(
            f"node {node_id!r} is {state}, not running; only a node in flight can "
            "report a result"
        )
        self.node_id = node_id
        self.state = state


class LeaseNotHeld(ExecutionError):
    """A result was offered by a worker that does not hold the node.

    The rule this context exists to make unbreakable. Two workers running one
    node is the failure with no honest recovery: the action happened twice, the
    record shows once, and nothing in the system can tell which result describes
    the world.
    """

    def __init__(self, *, node_id: str, offered: str, held_by: str) -> None:
        holder = f"held by {held_by}" if held_by else "not leased at all"
        super().__init__(
            f"worker {offered!r} offered a result for {node_id!r}, which is {holder}. "
            "A result written without the lease is a result nobody authorised, and "
            "two workers on one node is a change that happened twice and was "
            "recorded once"
        )
        self.node_id = node_id
        self.offered = offered
        self.held_by = held_by


class LeaseExpired(ExecutionError):
    """The lease ran out before the result arrived.

    Not a failure of the worker -- a statement about what is knowable. The node
    may have completed, may be half-done, may never have started. Recorded as
    ``UNKNOWN`` rather than guessed.
    """

    def __init__(self, *, node_id: str, worker_id: str) -> None:
        super().__init__(
            f"the lease {worker_id!r} held on {node_id!r} expired before a result "
            "arrived; whether the work happened is not knowable from here"
        )
        self.node_id = node_id
        self.worker_id = worker_id


class NodeAlreadyLeased(ExecutionError):
    def __init__(self, *, node_id: str, held_by: str) -> None:
        super().__init__(
            f"node {node_id!r} is already leased to {held_by!r}; a second lease would "
            "put two workers on one node"
        )
        self.node_id = node_id
        self.held_by = held_by


class AttemptsExhausted(ExecutionError):
    def __init__(self, *, node_id: str, attempts: int) -> None:
        super().__init__(
            f"node {node_id!r} has used all {attempts} of its attempts; retrying past "
            "the declared limit would make the limit advisory"
        )
        self.node_id = node_id
        self.attempts = attempts


class AmbiguousRetry(ExecutionError):
    """Retrying work whose outcome is unknown, without an idempotency key.

    Constitution P2's operational half. A lease that expired without a result
    means the action may have applied. Retrying it may apply it twice, and the
    second application is the one nobody planned. The workflow already refuses
    this at compile time for declared retries; this is the same rule at the
    moment it actually matters.
    """

    def __init__(self, *, node_id: str, side_effect: str) -> None:
        super().__init__(
            f"node {node_id!r} is {side_effect!r} and its last attempt ended unknown; "
            "retrying without an idempotency key may apply the action twice, and "
            "nothing downstream would know"
        )
        self.node_id = node_id
        self.side_effect = side_effect


class IncompleteExecution(ExecutionError):
    """Completion was declared while nodes were still outstanding.

    The failure every context in this codebase refuses in its own vocabulary:
    reporting success for work that never happened.
    """

    def __init__(self, *, execution_id: str, outstanding: Sequence[str]) -> None:
        listed = ", ".join(sorted(outstanding)[:5])
        more = f" (+{len(outstanding) - 5} more)" if len(outstanding) > 5 else ""
        super().__init__(
            f"execution {execution_id} cannot complete with {len(outstanding)} node(s) "
            f"not finished: {listed}{more}. Reporting success now would report success "
            "for work that never happened"
        )
        self.execution_id = execution_id
        self.outstanding = tuple(outstanding)


class NoCheckpoint(ExecutionError):
    def __init__(self, execution_id: str) -> None:
        super().__init__(
            f"execution {execution_id} has no checkpoint to resume from; resuming "
            "would restart it over a world that has already changed"
        )
        self.execution_id = execution_id


class CheckpointAhead(ExecutionError):
    """A checkpoint claiming nodes finished that the record says did not."""

    def __init__(self, *, checkpoint_id: str, disputed: Sequence[str]) -> None:
        listed = ", ".join(sorted(disputed))
        super().__init__(
            f"checkpoint {checkpoint_id} claims {listed} finished, but the execution "
            "does not; resuming from it would skip work the record says is undone"
        )
        self.checkpoint_id = checkpoint_id
        self.disputed = tuple(disputed)


class UnknownWorker(ExecutionError):
    def __init__(self, worker_id: str) -> None:
        super().__init__(f"no worker registered as {worker_id!r}")
        self.worker_id = worker_id


class WorkerCannotRun(ExecutionError):
    """A worker was offered a node it does not have the capability to run."""

    def __init__(self, *, worker_id: str, node_id: str, needs: str, has: Sequence[str]) -> None:
        listed = ", ".join(sorted(has)) or "(nothing)"
        super().__init__(
            f"worker {worker_id!r} cannot run {node_id!r}: it needs {needs!r} and the "
            f"worker offers {listed}"
        )
        self.worker_id = worker_id
        self.node_id = node_id
        self.needs = needs
        self.has = tuple(has)


class ExecutionRefused(ExecutionError):
    """Policy refused, with every reason at once."""

    def __init__(self, *, execution_id: str, target: str, failures: Sequence) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in list(failures)[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(
            f"execution {execution_id} cannot be {target} -- {summary}{more}"
        )
        self.execution_id = execution_id
        self.target = target
        self.failures = tuple(failures)


class DigestMismatch(ExecutionError):
    def __init__(self, *, execution_id: str, recorded: str, recomputed: str) -> None:
        super().__init__(
            f"execution {execution_id}: sealed with digest {recorded} but content now "
            f"hashes to {recomputed}; the record of what ran is not the one sealed"
        )
        self.execution_id = execution_id
        self.recorded = recorded
        self.recomputed = recomputed


class DigestNotComputed(ExecutionError):
    def __init__(self, execution_id: str) -> None:
        super().__init__(
            f"execution {execution_id} has no digest; digests are computed when the "
            "run reaches an outcome"
        )
        self.execution_id = execution_id


class ExecutionNotFound(ExecutionError):
    def __init__(self, execution_id: str) -> None:
        super().__init__(f"no execution with id {execution_id}")
        self.execution_id = execution_id


class DuplicateExecution(ExecutionError):
    def __init__(self, execution_id: str) -> None:
        super().__init__(f"execution {execution_id} already exists")
        self.execution_id = execution_id
