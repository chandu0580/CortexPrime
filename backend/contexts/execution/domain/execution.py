"""The Execution aggregate: one run of one compiled workflow.

Workflow said *when, under what conditions, and what happens when it goes wrong*.
This runs it -- and runs nothing itself, because every worker is a Protocol
implemented somewhere this context cannot see.

What this aggregate owns that no earlier context did
------------------------------------------------------
Runtime state. Everything before this describes work that has not happened;
this is the first context whose record is a claim about the world *right now*,
while it is changing. That difference is where its rules come from.

The rule the context exists for
---------------------------------
**Only the worker holding the lease may record a result.** Two workers on one
node is the failure with no honest recovery: the action happened twice, the
record shows once, and nothing in the system can say which result describes the
world. Every path that writes an outcome goes through ``assert_held_by``.

Unknown is a first-class outcome
----------------------------------
A lease that lapses without a result does not mean failure. It means nothing is
known -- the work may have completed, may be half-applied, may never have
started. Recording ``UNKNOWN`` honestly is what makes the retry rule enforceable:
re-running an ambiguous mutation requires an idempotency key, because the retry
is exactly what the ambiguity is about.

What this aggregate refuses to be
-----------------------------------
It holds no plan, no goals, no workflow structure beyond the projection it was
handed, and no execution *output* -- results carry the published
``ExecutionResult``, and payloads live behind opaque references. It never edits
the workflow it runs, and it cannot: it has the graph as data and no path back to
the context that owns it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Final, Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionResult
from backend.contexts.execution.domain.checkpoint import ExecutionCheckpoint
from backend.contexts.execution.domain.errors import (
    CheckpointAhead,
    DependenciesUnsatisfied,
    DigestMismatch,
    DigestNotComputed,
    ExecutionFinished,
    IllegalExecutionTransition,
    IncompleteExecution,
    NoCheckpoint,
    UnknownNode,
)
from backend.contexts.execution.domain.identifiers import ExecutionId
from backend.contexts.execution.domain.lease import NodeRun, NodeSpec
from backend.contexts.execution.domain.state import (
    ExecutionState,
    NodeState,
    execution_permitted_from,
    is_legal_execution_transition,
    published_status_of,
)
from backend.contexts.execution.domain.worker import WorkerRegistration
from backend.platform.hashing import compute_digest, digests_match

__all__ = [
    "Execution",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
]

ARTIFACT_KIND: Final[str] = "cortexprime.execution.execution"
CANONICAL_FORM_VERSION: Final[int] = 1

#: What the outcome digest covers. Excludes the live state and the wall-clock
#: fields -- the digest is sealed when the run reaches an outcome, and it is a
#: statement about *what happened*, not about when the record was written.
GOVERNED_FIELDS: Final[tuple] = (
    "execution_id",
    "workflow_id",
    "workflow_digest",
    "mission_id",
    "attempt",
    "nodes",
    "checkpoints",
    "state",
    "outcome_note",
)


@dataclass(frozen=True)
class Execution(Contract):
    """One run of one compiled workflow."""

    CONTRACT_NAME = "cortexprime.execution.execution_aggregate"

    execution_id: ExecutionId
    workflow_id: str
    workflow_digest: str
    mission_id: str

    attempt: int = 1
    runs: tuple = ()
    checkpoints: tuple = ()
    state: ExecutionState = ExecutionState.PENDING
    outcome_note: Optional[str] = None
    digest: Optional[str] = None

    resumed_from: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requested_by: str = "mission-runtime"

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, ExecutionId):
            raise ContractViolation("execution_id must be an ExecutionId")

        for label, value in (
            ("workflow_id", self.workflow_id),
            ("workflow_digest", self.workflow_digest),
            ("mission_id", self.mission_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a run that cannot say which "
                    "workflow it is running is not a run of anything"
                )

        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ContractViolation("attempt starts at 1")

        for label, items, expected in (
            ("runs", self.runs, NodeRun),
            ("checkpoints", self.checkpoints, ExecutionCheckpoint),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        if not self.runs:
            raise ContractViolation(
                "a run needs at least one node; one with none has nothing "
                "outstanding, so it would complete immediately and report success "
                "for work that was never in it"
            )

        node_ids = [r.node_id for r in self.runs]
        if len(set(node_ids)) != len(node_ids):
            raise ContractViolation("runs contains duplicate node ids")

        # Every dependency names a node this run was given.
        known = set(node_ids)
        for run in self.runs:
            missing = [d for d in run.spec.depends_on if d not in known]
            if missing:
                raise UnknownNode(
                    execution_id=str(self.execution_id), node_id=", ".join(sorted(missing))
                )

        sequences = [c.sequence for c in self.checkpoints]
        if sequences != sorted(sequences) or len(set(sequences)) != len(sequences):
            raise ContractViolation(
                "checkpoints must be sequenced without gaps or repeats; resuming "
                "depends on knowing which is latest"
            )

        if not isinstance(self.state, ExecutionState):
            raise ContractViolation("state must be an ExecutionState")

        # Only one worker may hold a node, and the state must agree with the lease.
        for run in self.runs:
            if run.state is NodeState.LEASED and not run.held_by:
                raise ContractViolation(
                    f"node {run.node_id!r} is leased but names no holder"
                )

        # Completion is a statement that every node finished.
        if self.state is ExecutionState.COMPLETED:
            outstanding = [r.node_id for r in self.runs if not r.is_finished]
            if outstanding:
                raise IncompleteExecution(
                    execution_id=str(self.execution_id), outstanding=outstanding
                )

        if self.state.is_terminal:
            if self.ended_at is None:
                raise ContractViolation(
                    f"an execution that is {self.state.value} must record when it ended"
                )
            if not self.digest:
                raise ContractViolation(
                    "a finished execution must carry the digest sealed at its outcome; "
                    "without it the record of what ran cannot be shown to be the one "
                    "the run produced"
                )

        if self.state in (ExecutionState.FAILED, ExecutionState.CANCELLED) and not (
            self.outcome_note and self.outcome_note.strip()
        ):
            raise ContractViolation(
                f"a {self.state.value} execution must say why; an unexplained outcome "
                "tells the next attempt nothing"
            )

        if self.state is not ExecutionState.PENDING and self.started_at is None:
            raise ContractViolation("a run past pending must record when it started")

        for label in ("created_at", "started_at", "ended_at"):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def node_ids(self) -> tuple:
        return tuple(sorted(r.node_id for r in self.runs))

    def run_for(self, node_id: str) -> Optional[NodeRun]:
        for candidate in self.runs:
            if candidate.node_id == node_id:
                return candidate
        return None

    def _require_node(self, node_id: str) -> NodeRun:
        run = self.run_for(node_id)
        if run is None:
            raise UnknownNode(execution_id=str(self.execution_id), node_id=node_id)
        return run

    @property
    def is_open(self) -> bool:
        return self.state.is_open

    @property
    def finished_nodes(self) -> tuple:
        return tuple(sorted(r.node_id for r in self.runs if r.is_finished))

    @property
    def outstanding_nodes(self) -> tuple:
        return tuple(sorted(r.node_id for r in self.runs if not r.is_finished))

    @property
    def leased_nodes(self) -> tuple:
        return tuple(sorted(r.node_id for r in self.runs if r.state is NodeState.LEASED))

    @property
    def ambiguous_nodes(self) -> tuple:
        """Nodes whose outcome nobody can state. What blocks a clean completion."""
        return tuple(sorted(r.node_id for r in self.runs if r.state.is_ambiguous))

    @property
    def failed_nodes(self) -> tuple:
        return tuple(sorted(r.node_id for r in self.runs if r.state is NodeState.FAILED))

    @property
    def mutated_nodes(self) -> tuple:
        """Nodes that ran and changed something. What cancellation has to answer for."""
        return tuple(
            sorted(
                r.node_id
                for r in self.runs
                if r.spec.mutates and r.state in (NodeState.SUCCEEDED, NodeState.UNKNOWN)
            )
        )

    def ready_nodes(self) -> tuple:
        """Nodes whose dependencies are satisfied and which nobody holds.

        Derived rather than stored. A stored ready-set drifts from the graph the
        moment a dependency's outcome changes, and the drift is invisible until
        something dispatches work that should have waited.
        """
        satisfied = {r.node_id for r in self.runs if r.satisfies_dependents}
        return tuple(
            sorted(
                r.node_id
                for r in self.runs
                if r.state is NodeState.READY and set(r.spec.depends_on) <= satisfied
            )
        )

    def blocked_nodes(self) -> tuple:
        """Nodes that can never become ready, because something they need failed."""
        blocked: list = []
        unusable = {
            r.node_id
            for r in self.runs
            if r.state.is_terminal and not r.satisfies_dependents
        }
        for run in self.runs:
            if run.state.is_terminal:
                continue
            if set(run.spec.depends_on) & unusable:
                blocked.append(run.node_id)
        return tuple(sorted(blocked))

    @property
    def latest_checkpoint(self) -> Optional[ExecutionCheckpoint]:
        return self.checkpoints[-1] if self.checkpoints else None

    @property
    def progress(self) -> tuple:
        """``(finished, total)``. What a stream reports."""
        return (len(self.finished_nodes), len(self.runs))

    def published_results(self) -> tuple:
        """Every node's outcome in the published vocabulary.

        What leaves this context. ``UNKNOWN`` projects onto ``FAILED`` and the
        loss is deliberate -- see ``state.py``.
        """
        return tuple(
            (r.node_id, published_status_of(r.state)) for r in sorted(self.runs, key=lambda r: r.node_id)
        )

    def permitted_transitions(self) -> tuple:
        return execution_permitted_from(self.state)

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        return {
            "__artifact__": ARTIFACT_KIND,
            "__canonical_form__": CANONICAL_FORM_VERSION,
            "execution_id": str(self.execution_id),
            "workflow_id": self.workflow_id,
            "workflow_digest": self.workflow_digest,
            "mission_id": self.mission_id,
            "attempt": self.attempt,
            "state": self.state.value,
            "outcome_note": self.outcome_note,
            "nodes": sorted(
                (
                    {
                        "node_id": r.node_id,
                        "state": r.state.value,
                        "worker_kind": r.spec.worker_kind.value,
                        "side_effect": r.spec.side_effect.value,
                        "attempts": [
                            {
                                "number": a.number,
                                "worker_id": a.worker_id,
                                "outcome": a.outcome.value,
                                "failure_reason": a.failure_reason,
                            }
                            for a in r.attempts
                        ],
                        "skipped_reason": r.skipped_reason,
                    }
                    for r in self.runs
                ),
                key=lambda item: item["node_id"],
            ),
            "checkpoints": sorted(
                (
                    {
                        "checkpoint_id": str(c.checkpoint_id),
                        "sequence": c.sequence,
                        "label": c.label,
                        "finished_nodes": sorted(c.finished_nodes),
                        "digest": c.digest,
                    }
                    for c in self.checkpoints
                ),
                key=lambda item: item["sequence"],
            ),
        }

    def compute_digest(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def verify_digest(self) -> None:
        if not self.digest:
            raise DigestNotComputed(str(self.execution_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                execution_id=str(self.execution_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _require_open(self, operation: str) -> None:
        if self.state.is_terminal:
            raise ExecutionFinished(
                execution_id=str(self.execution_id),
                state=self.state.value,
                operation=operation,
            )

    def _with_run(self, updated: NodeRun, **changes: Any) -> "Execution":
        """Replace one node's run and let dependents become ready."""
        runs = tuple(
            updated if r.node_id == updated.node_id else r for r in self.runs
        )
        return replace(self, runs=self._promote_ready(runs), **changes)

    @staticmethod
    def _promote_ready(runs: tuple) -> tuple:
        """Move waiting nodes to ready once everything they need is satisfied.

        Derived from the graph rather than signalled by the node that finished:
        a node with three dependencies becomes ready when the *last* of them
        lands, and asking each finisher to work that out is how one of them gets
        it wrong.
        """
        satisfied = {r.node_id for r in runs if r.satisfies_dependents}
        promoted: list = []
        for run in runs:
            if run.state is NodeState.WAITING and set(run.spec.depends_on) <= satisfied:
                promoted.append(run.become_ready())
            else:
                promoted.append(run)
        return tuple(promoted)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _transition(self, to_state: ExecutionState, **changes: Any) -> "Execution":
        if not is_legal_execution_transition(self.state, to_state):
            raise IllegalExecutionTransition(
                execution_id=str(self.execution_id),
                source=self.state.value,
                target=to_state.value,
                permitted=execution_permitted_from(self.state),
            )
        return replace(self, state=to_state, **changes)

    def _sealed(self, to_state: ExecutionState, **changes: Any) -> "Execution":
        """Reach an outcome and bind the digest in one construction.

        The payload is assembled directly rather than by building an intermediate
        that would violate one invariant to satisfy the other -- a terminal state
        requires a digest, and the digest covers the terminal state.
        """
        moment = datetime.now(timezone.utc)
        pending = replace(self, ended_at=moment, **changes)
        payload = pending.digest_payload()
        payload["state"] = to_state.value
        digest = compute_digest(payload).value
        return pending._transition(to_state, digest=digest)

    def start(self) -> "Execution":
        self._require_open("starting")
        return self._transition(
            ExecutionState.RUNNING, started_at=datetime.now(timezone.utc)
        )

    def pause(self, reason: str) -> "Execution":
        """Stop handing out work. Nodes already leased keep running.

        Deliberate: a pause that killed work in flight would make pausing more
        dangerous than continuing, and operators would stop using it.
        """
        self._require_open("pausing")
        if not reason or not reason.strip():
            raise ContractViolation("pausing must say why")
        return self._transition(ExecutionState.PAUSED, outcome_note=reason.strip())

    def resume(self, checkpoint_id: Optional[str] = None) -> "Execution":
        """Continue, optionally from a checkpoint.

        A checkpoint claiming nodes finished that the record says did not is
        refused: resuming from it would skip work the run believes is undone.
        """
        self._require_open("resuming")
        checkpoint = None
        if checkpoint_id is not None:
            checkpoint = next(
                (c for c in self.checkpoints if str(c.checkpoint_id) == checkpoint_id),
                None,
            )
            if checkpoint is None:
                raise NoCheckpoint(str(self.execution_id))
            checkpoint.verify_digest()
            disputed = sorted(set(checkpoint.finished_nodes) - set(self.finished_nodes))
            if disputed:
                raise CheckpointAhead(
                    checkpoint_id=checkpoint_id, disputed=disputed
                )

        return self._transition(
            ExecutionState.RUNNING,
            outcome_note=None,
            resumed_from=checkpoint_id or self.resumed_from,
        )

    def complete(self) -> "Execution":
        """Report success. Refuses while anything is outstanding."""
        self._require_open("completing")
        outstanding = self.outstanding_nodes
        if outstanding:
            raise IncompleteExecution(
                execution_id=str(self.execution_id), outstanding=outstanding
            )
        return self._sealed(ExecutionState.COMPLETED)

    def fail(self, reason: str) -> "Execution":
        self._require_open("failing")
        if not reason or not reason.strip():
            raise ContractViolation("a failed run must say why")
        return self._sealed(ExecutionState.FAILED, outcome_note=reason.strip())

    def cancel(self, reason: str) -> "Execution":
        """Stop the run. Nodes already leased are recorded as they stand.

        Cancellation does not pretend the world is unchanged: whatever ran, ran.
        ``mutated_nodes`` is what an operator reads next, and compensation is a
        decision made against that list rather than something this method
        performs.
        """
        self._require_open("cancelling")
        if not reason or not reason.strip():
            raise ContractViolation("cancelling must say why")
        return self._sealed(ExecutionState.CANCELLED, outcome_note=reason.strip())

    def time_out(self) -> "Execution":
        self._require_open("timing out")
        return self._sealed(
            ExecutionState.TIMED_OUT,
            outcome_note="the run exceeded its deadline",
        )

    # ------------------------------------------------------------------
    # Dispatch and results
    # ------------------------------------------------------------------

    def assign(
        self,
        node_id: str,
        worker: WorkerRegistration,
        *,
        now: Optional[datetime] = None,
    ) -> "Execution":
        """Lease a node to a worker.

        Three refusals stack here, in the order that costs least: the run must be
        dispatching, the node's dependencies must be satisfied, and the worker
        must be able to run it. Only then is a lease issued -- a lease held by
        something that cannot do the work blocks every other worker until it
        lapses.
        """
        self._require_open("assigning work")
        if not self.state.accepts_dispatch:
            raise ExecutionFinished(
                execution_id=str(self.execution_id),
                state=self.state.value,
                operation="assigning work",
            )

        run = self._require_node(node_id)
        satisfied = {r.node_id for r in self.runs if r.satisfies_dependents}
        waiting_on = sorted(set(run.spec.depends_on) - satisfied)
        if waiting_on:
            raise DependenciesUnsatisfied(node_id=node_id, waiting_on=waiting_on)

        worker.assert_can_run(node_id, run.spec.worker_kind)
        leased = run.leased_to(worker.worker_id, worker.lease_seconds, now=now)
        return self._with_run(leased)

    def record_result(
        self,
        node_id: str,
        worker_id: str,
        result: ExecutionResult,
        *,
        now: Optional[datetime] = None,
    ) -> "Execution":
        """Record success from the worker holding the lease."""
        self._require_open("recording a result")
        run = self._require_node(node_id)
        return self._with_run(
            run.concluded(NodeState.SUCCEEDED, worker_id, result=result, now=now)
        )

    def record_failure(
        self,
        node_id: str,
        worker_id: str,
        reason: str,
        *,
        result: Optional[ExecutionResult] = None,
        now: Optional[datetime] = None,
        failure: Optional[Any] = None,
    ) -> "Execution":
        self._require_open("recording a failure")
        if not reason or not reason.strip():
            raise ContractViolation("a failed attempt must say why")
        run = self._require_node(node_id)
        return self._with_run(
            run.concluded(
                NodeState.FAILED,
                worker_id,
                result=result,
                failure_reason=reason.strip(),
                now=now,
                failure=failure,
            )
        )

    def reclaim(self, node_id: str, *, now: Optional[datetime] = None) -> "Execution":
        """Take back a node whose lease lapsed. Records ``UNKNOWN``, not failure."""
        self._require_open("reclaiming a node")
        run = self._require_node(node_id)
        return self._with_run(run.abandoned(now=now))

    def retry(self, node_id: str) -> "Execution":
        """Return a failed or unknown node to the ready pool.

        Refuses an ambiguous mutation with no idempotency key -- the retry is
        exactly what the ambiguity is about.
        """
        self._require_open("retrying a node")
        run = self._require_node(node_id)
        return self._with_run(run.retried())

    def skip(self, node_id: str, reason: str) -> "Execution":
        self._require_open("skipping a node")
        run = self._require_node(node_id)
        return self._with_run(run.skipped(reason))

    def compensate(self, node_id: str) -> "Execution":
        self._require_open("compensating a node")
        run = self._require_node(node_id)
        return self._with_run(run.compensated())

    # ------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------

    def checkpoint(
        self, label: str, *, payload_ref: Optional[str] = None, recorded_by: str = "execution-runtime"
    ) -> "Execution":
        """Record a resumable position from what has actually finished."""
        self._require_open("checkpointing")
        if self.state is ExecutionState.PENDING:
            raise ContractViolation(
                "a run that has not started has no progress to checkpoint"
            )
        checkpoint = ExecutionCheckpoint.create(
            sequence=len(self.checkpoints) + 1,
            label=label,
            finished_nodes=self.finished_nodes,
            resume_from=self.ready_nodes(),
            payload_ref=payload_ref,
            recorded_by=recorded_by,
        )
        return replace(self, checkpoints=self.checkpoints + (checkpoint,))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def of(
        cls,
        *,
        workflow_id: str,
        workflow_digest: str,
        mission_id: str,
        nodes: Sequence[NodeSpec],
        attempt: int = 1,
        requested_by: str = "mission-runtime",
    ) -> "Execution":
        """A pending run over the projection of a compiled workflow."""
        runs = tuple(NodeRun.of(spec) for spec in nodes)
        return cls(
            execution_id=ExecutionId.new(),
            workflow_id=workflow_id,
            workflow_digest=workflow_digest,
            mission_id=mission_id,
            attempt=attempt,
            runs=Execution._promote_ready(runs),
            requested_by=requested_by,
        )
