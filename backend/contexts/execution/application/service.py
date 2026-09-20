"""The Execution Runtime application service.

Where the aggregate's invariants meet execution policy, the worker pool, and the
repository's facts. Events are returned, never published -- this context owns no
bus, the same arrangement as every other context in this codebase.

What this service does that the earlier ones did not
------------------------------------------------------
It holds a **worker pool** and hands out **leases**. That is the only mutable
shared resource anywhere in this codebase's product layer, and it is why the
lease check lives in the aggregate rather than here: a guard in the service is a
guard a second caller can go around.

The dispatch loop is not here either
--------------------------------------
There is no ``run()`` that drives a workflow to completion. ``ready_nodes`` says
what *could* be dispatched and ``assign`` hands one node to one worker; deciding
how fast to go, how many workers to use, and when to give up is the caller's.
A service that owned the loop would own the concurrency policy too, and that is a
deployment decision rather than a domain one.

What this service deliberately cannot do
-----------------------------------------
It cannot plan, compile a workflow, or touch a mission. It cannot *run* anything:
every worker is a Protocol, and this module never calls one -- the caller holds
the worker and reports back through ``record_success``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Optional

from backend.contracts.execution import ExecutionResult, ExecutionStatus, SideEffectClass
from backend.contexts.execution.application.commands import (
    AssignNode,
    Heartbeat,
    PlanRecovery,
    ReplayExecution,
    CancelExecution,
    CompensateNode,
    CompleteExecution,
    CreateCheckpoint,
    FailExecution,
    GetExecution,
    GetReadyNodes,
    ListExecutions,
    PauseExecution,
    ReclaimNode,
    RecordFailure,
    RecordSuccess,
    RegisterWorker,
    ResumeExecution,
    RetryNode,
    SkipNode,
    StartExecution,
    TimeOutExecution,
)
from backend.contexts.execution.domain.errors import (
    ExecutionFinished,
    ExecutionNotFound,
    ExecutionRefused,
    RetryRefused,
    UnknownNode,
    UnknownWorker,
)
from backend.contexts.execution.domain.events import (
    AGGREGATE_TYPE,
    ExecutionAssigned,
    ExecutionCancelled,
    ExecutionCheckpointCreated,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionPaused,
    ExecutionResumed,
    ExecutionRetried,
    ExecutionStarted,
    ExecutionTimedOut,
)
from backend.contexts.execution.domain.lifecycle_events import (
    NodeCompensationConcluded,
)
from backend.contexts.execution.application.instrumentation import NullObserver, SafeObserver
from backend.contexts.execution.application.replay import ExecutionReplayer
from backend.contexts.execution.domain.compensation import CompensationRecord
from backend.contexts.execution.domain.effects import profile_for
from backend.contexts.execution.domain.execution import Execution
from backend.contexts.execution.domain.failure import FailureClass, FailureRecord
from backend.contexts.execution.domain.recovery import (
    RecoveryTrigger,
    plan_recovery as plan_recovery_for,
)
from backend.contexts.execution.domain.retry import (
    DEFAULT_RETRY_POLICY,
    RetryDecision,
    RetryVerdict,
    decide_retry,
)
from backend.contexts.execution.domain.factory import node_spec, start_run, worker as make_worker
from backend.contexts.execution.domain.identifiers import ExecutionId
from backend.contexts.execution.domain.policy import ExecutionPolicy, default_policy
from backend.contexts.execution.domain.state import ExecutionState, NodeState
from backend.contexts.execution.domain.worker import (
    RunContext,
    WorkerKind,
    WorkerRegistration,
)
from backend.platform.events import EventMetadata

__all__ = ["ExecutionService", "CommandResult", "WorkerPool"]


@dataclass(frozen=True)
class CommandResult:
    execution: Execution
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class WorkerPool:
    """The workers currently offering themselves. **Capacity, never authority.**

    Two registries, and they are not duplicates
    ---------------------------------------------
    A worker must be present in both this pool and ``WorkerDirectory`` before it
    can run anything, which reads like duplication until you name what each one
    answers. Phase 5.5 hit ``UnknownWorker`` at claim time by registering in one
    and not the other, so the distinction is written down here rather than
    rediscovered:

        WorkerDirectory  answers **"may this worker be selected?"** -- the
                         governance question. Lifecycle (REGISTERED ->
                         VALIDATED -> ENABLED), trust, availability, tenant
                         visibility, isolation tier, which providers and
                         operations the implementation advertises, and the
                         implementation digest. It is durable
                         (``SqlWorkerDirectory``), because a worker's
                         commissioning must survive a restart -- otherwise
                         "is this worker trusted" is answered from whatever
                         the current process happened to be told.

        WorkerPool       answers **"how much can this worker take right now?"**
                         -- the capacity question. Kinds offered, concurrency
                         ceiling, lease duration. The execution aggregate reads
                         it to decide whether a lease may be issued at all.

    Neither can answer the other's question, and collapsing them would produce a
    single registry where revoking trust silently changed concurrency, or where
    a worker at its concurrency ceiling looked untrusted. They are separate
    invariants that happen to be keyed by the same id.

    In-memory and per-process, which is honest about what it is: capacity is a
    property of *this* process's live workers, and a durable copy would describe
    a fleet nobody in this process can lease from. That is also why losing it on
    restart is correct rather than a gap -- a restarted process has no
    outstanding leases to account for.
    """

    def __init__(self) -> None:
        self._workers: dict = {}

    def register(self, registration: WorkerRegistration) -> WorkerRegistration:
        self._workers[registration.worker_id] = registration
        return registration

    def get(self, worker_id: str) -> WorkerRegistration:
        found = self._workers.get(worker_id)
        if found is None:
            raise UnknownWorker(worker_id)
        return found

    def deregister(self, worker_id: str) -> None:
        self._workers.pop(worker_id, None)

    def available_for(self, kind: WorkerKind) -> tuple:
        return tuple(
            sorted(
                (w for w in self._workers.values() if w.accepts_work and w.can_run(kind)),
                key=lambda w: w.worker_id,
            )
        )

    def all(self) -> tuple:
        return tuple(sorted(self._workers.values(), key=lambda w: w.worker_id))

    def __len__(self) -> int:
        return len(self._workers)


class ExecutionService:
    def __init__(
        self,
        repository: Any,
        *,
        policy: Optional[ExecutionPolicy] = None,
        pool: Optional[WorkerPool] = None,
        observer: Optional[Any] = None,
        outbox: Optional[Any] = None,
        retry_policy: Any = DEFAULT_RETRY_POLICY,
    ) -> None:
        self._repository = repository
        self._policy = policy or default_policy()
        self._pool = pool or WorkerPool()
        # Wrapped so a misbehaving watcher can never affect a production run.
        self._observer = SafeObserver(observer or NullObserver())
        self._outbox = outbox
        self._retry_policy = retry_policy
        self._replayer = ExecutionReplayer()

    @property
    def policy(self) -> ExecutionPolicy:
        return self._policy

    @property
    def pool(self) -> WorkerPool:
        return self._pool

    @property
    def observer(self) -> Any:
        return self._observer

    @property
    def outbox(self) -> Any:
        return self._outbox

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, execution: Execution) -> EventMetadata:
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(execution.execution_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
        )

    def _load(self, context: Any, execution_id: str) -> Execution:
        found = self._repository.find(context, ExecutionId(execution_id))
        if found is None:
            raise ExecutionNotFound(execution_id)
        return found

    def _load_with_revision(self, context: Any, execution_id: str) -> tuple:
        """The run and the revision it was read at, read together.

        Two statements would be a race: a writer landing between them leaves a
        stale aggregate beside a fresh revision, and the compare-and-swap that
        follows then matches on a decision it never saw. A repository too old to
        answer both at once falls back to the pair, which is no worse than the
        behaviour it replaces and no better -- it is not silently treated as
        safe.
        """
        together = getattr(self._repository, "find_with_revision", None)
        if together is None:
            execution = self._load(context, execution_id)
            return execution, self._repository.revision_of(
                context, execution.execution_id
            )
        found, revision = together(context, ExecutionId(execution_id))
        if found is None:
            raise ExecutionNotFound(execution_id)
        return found, revision

    def _saved_checked(
        self, context: Any, execution: Execution, expected_revision, events: tuple = ()
    ) -> CommandResult:
        """``_saved``, but only if nothing has written since the caller read.

        **Which outcomes this protects, and why it is not every write.** Once the
        claim is fenced, exactly one worker holds a node -- but it is not the
        only writer. A reclaimer deciding at T-e that the lease had lapsed, and
        the holder recording success at T, both write. Unguarded, whichever
        lands last wins: a reclaim landing after a success erases it, the node
        reads UNKNOWN, and recovery is entitled to try again. That is a
        *duplicate provider action* produced by a lost update rather than by a
        lost race, and it is exactly the harm this phase exists to remove
        (ADR-127 F-8).

        A conflict raises ``ConcurrentExecutionUpdate`` rather than overwriting.
        Losing this race must mean "somebody else already recorded what happened
        to this node", which is information, not an error to paper over.
        """
        if expected_revision is None:
            return self._saved(context, execution, events)
        self._repository.compare_and_swap(
            context, execution, expected_revision=expected_revision
        )
        if self._outbox is not None and events:
            self._outbox.record(context, str(execution.execution_id), events)
        return CommandResult(execution=execution, events=events)

    def _saved(self, context: Any, execution: Execution, events: tuple = ()) -> CommandResult:
        self._repository.replace(context, execution)
        # Recorded next to the state change, not published here. Publication is
        # somebody else's job precisely so a failure to publish cannot roll back
        # -- or silently accompany -- a state change that really happened.
        if self._outbox is not None and events:
            self._outbox.record(context, str(execution.execution_id), events)
        return CommandResult(execution=execution, events=events)

    def _gated(self, execution: Execution, to_state: ExecutionState) -> None:
        # A run that has already reported its outcome is a conflict about the
        # state of the thing, not a policy judgement about the move. Routing it
        # through the policy would answer "unprocessable" to a caller whose real
        # problem is that somebody else finished the run first.
        if execution.state.is_terminal:
            raise ExecutionFinished(
                execution_id=str(execution.execution_id),
                state=execution.state.value,
                operation=f"moving to {to_state.value}",
            )

        report = self._policy.evaluate(execution, to_state)
        if not report.may_proceed:
            raise ExecutionRefused(
                execution_id=str(execution.execution_id),
                target=to_state.value,
                failures=report.blocking,
            )

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def register_worker(self, command: RegisterWorker) -> WorkerRegistration:
        """Record what a worker offers. A claim, not a credential."""
        return self._pool.register(
            make_worker(
                command.worker_id,
                tuple(WorkerKind(k) for k in command.kinds),
                max_concurrent=command.max_concurrent,
                lease_seconds=command.lease_seconds,
                labels=tuple(command.labels),
            )
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, context: Any, command: StartExecution) -> CommandResult:
        """Open a run over the projection of a compiled workflow."""
        specs = tuple(
            node_spec(
                node["node_id"],
                WorkerKind(node["worker_kind"]),
                depends_on=tuple(node.get("depends_on", ())),
                side_effect=SideEffectClass(node.get("side_effect", "read")),
                max_attempts=node.get("max_attempts", 1),
                timeout_seconds=node.get("timeout_seconds"),
                idempotency_key=node.get("idempotency_key"),
                compensates=node.get("compensates"),
                cancellable=node.get("cancellable", True),
                execution_key=node.get("execution_key"),
                input=node.get("input") or {},
            )
            for node in command.nodes
        )
        execution = start_run(
            workflow_id=command.workflow_id,
            workflow_digest=command.workflow_digest,
            mission_id=command.mission_id,
            nodes=specs,
            attempt=command.attempt,
            requested_by=command.requested_by,
        ).start()
        self._repository.save(context, execution)

        started = (
            ExecutionStarted(
                metadata=self._metadata(context, execution),
                execution_id=str(execution.execution_id),
                workflow_id=execution.workflow_id,
                workflow_digest=execution.workflow_digest,
                mission_id=execution.mission_id,
                attempt=execution.attempt,
                nodes=len(execution.runs),
            ),
        )
        # Recorded here too, not only in ``_saved``: a run whose opening event
        # never reached the outbox would have no history to replay from, and its
        # first recorded fact would be whatever happened next.
        if self._outbox is not None:
            self._outbox.record(context, str(execution.execution_id), started)
        self._observer.execution_started(
            str(execution.execution_id),
            {
                "workflow_id": execution.workflow_id,
                "workflow_digest": execution.workflow_digest,
                "mission_id": execution.mission_id,
                "nodes": len(execution.runs),
            },
        )
        return CommandResult(execution=execution, events=started)

    def pause(self, context: Any, command: PauseExecution) -> CommandResult:
        """Stop dispatching. Nodes already leased keep running."""
        execution = self._load(context, command.execution_id)
        self._gated(execution, ExecutionState.PAUSED)
        paused = execution.pause(command.reason)
        self._repository.replace(context, paused)

        latest = paused.latest_checkpoint
        return CommandResult(
            execution=paused,
            events=(
                ExecutionPaused(
                    metadata=self._metadata(context, paused),
                    execution_id=str(paused.execution_id),
                    reason=command.reason,
                    leased_nodes=len(paused.leased_nodes),
                    finished_nodes=len(paused.finished_nodes),
                    resumable_from=str(latest.checkpoint_id) if latest else "",
                ),
            ),
        )

    def resume(self, context: Any, command: ResumeExecution) -> CommandResult:
        execution = self._load(context, command.execution_id)
        self._gated(execution, ExecutionState.RUNNING)
        resumed = execution.resume(command.from_checkpoint)
        self._repository.replace(context, resumed)

        return CommandResult(
            execution=resumed,
            events=(
                ExecutionResumed(
                    metadata=self._metadata(context, resumed),
                    execution_id=str(resumed.execution_id),
                    resumed_from_checkpoint=command.from_checkpoint or "",
                    skipped_nodes=len(resumed.finished_nodes),
                    ready_nodes=len(resumed.ready_nodes()),
                ),
            ),
        )

    def complete(self, context: Any, command: CompleteExecution) -> CommandResult:
        """Report success. Refuses while anything is outstanding or ambiguous."""
        execution = self._load(context, command.execution_id)
        self._gated(execution, ExecutionState.COMPLETED)
        completed = execution.complete()
        self._repository.replace(context, completed)

        by_state = lambda state: sum(1 for r in completed.runs if r.state is state)
        return CommandResult(
            execution=completed,
            events=(
                ExecutionCompleted(
                    metadata=self._metadata(context, completed),
                    execution_id=str(completed.execution_id),
                    workflow_id=completed.workflow_id,
                    digest=completed.digest or "",
                    nodes=len(completed.runs),
                    succeeded=by_state(NodeState.SUCCEEDED),
                    skipped=by_state(NodeState.SKIPPED),
                    compensated=by_state(NodeState.COMPENSATED),
                    outstanding=len(completed.outstanding_nodes),
                    ambiguous=len(completed.ambiguous_nodes),
                ),
            ),
        )

    def fail(self, context: Any, command: FailExecution) -> CommandResult:
        execution = self._load(context, command.execution_id)
        self._gated(execution, ExecutionState.FAILED)
        failed = execution.fail(command.reason)
        self._repository.replace(context, failed)

        return CommandResult(
            execution=failed,
            events=(
                ExecutionFailed(
                    metadata=self._metadata(context, failed),
                    execution_id=str(failed.execution_id),
                    reason=command.reason,
                    digest=failed.digest or "",
                    failed_nodes=len(failed.failed_nodes),
                    ambiguous_nodes=len(failed.ambiguous_nodes),
                    mutated_nodes=len(failed.mutated_nodes),
                ),
            ),
        )

    def cancel(self, context: Any, command: CancelExecution) -> CommandResult:
        """Call the run off. What already ran, ran."""
        execution = self._load(context, command.execution_id)
        self._gated(execution, ExecutionState.CANCELLED)
        cancelled = execution.cancel(command.reason)
        self._repository.replace(context, cancelled)

        return CommandResult(
            execution=cancelled,
            events=(
                ExecutionCancelled(
                    metadata=self._metadata(context, cancelled),
                    execution_id=str(cancelled.execution_id),
                    reason=command.reason,
                    cancelled_by=command.cancelled_by,
                    digest=cancelled.digest or "",
                    mutated_nodes=len(cancelled.mutated_nodes),
                    leased_nodes=len(cancelled.leased_nodes),
                ),
            ),
        )

    def time_out(self, context: Any, command: TimeOutExecution) -> CommandResult:
        execution = self._load(context, command.execution_id)
        self._gated(execution, ExecutionState.TIMED_OUT)
        timed_out = execution.time_out()
        self._repository.replace(context, timed_out)

        return CommandResult(
            execution=timed_out,
            events=(
                ExecutionTimedOut(
                    metadata=self._metadata(context, timed_out),
                    execution_id=str(timed_out.execution_id),
                    digest=timed_out.digest or "",
                    deadline_seconds=command.deadline_seconds,
                    finished_nodes=len(timed_out.finished_nodes),
                    leased_nodes=len(timed_out.leased_nodes),
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def assign(self, context: Any, command: AssignNode) -> CommandResult:
        """Lease one node to one worker. **The write is revision-checked.**

        The aggregate refuses a second holder, but it refuses it against the copy
        *this* caller loaded, and an unguarded ``replace`` would let two callers
        who both loaded an unleased node both write — the second silently erasing
        the first's lease while both believed they owned the node. That is not
        hypothetical: it was reproduced against PostgreSQL with two services on
        separate connections, and both won (Phase 11.3).

        It did not matter while exactly one process dispatched, which is the only
        reason the unguarded write survived this long. It matters the moment a
        second dispatcher exists, so the fence goes in *before* the callers do.
        ``compare_and_swap`` makes the compare and the swap one statement, so the
        loser is refused rather than overwritten, and the dispatcher already
        classifies that refusal as ``NODE_LEASED``.
        """
        execution, revision = self._load_with_revision(context, command.execution_id)
        registration = self._pool.get(command.worker_id)
        assigned = execution.assign(command.node_id, registration)
        if revision is None:
            from backend.contexts.execution.domain.errors import ExecutionNotFound

            raise ExecutionNotFound(str(execution.execution_id))
        self._repository.compare_and_swap(
            context, assigned, expected_revision=revision
        )

        run = assigned.run_for(command.node_id)
        return CommandResult(
            execution=assigned,
            events=(
                ExecutionAssigned(
                    metadata=self._metadata(context, assigned),
                    execution_id=str(assigned.execution_id),
                    node_id=command.node_id,
                    worker_id=command.worker_id,
                    lease_id=str(run.lease.lease_id),
                    attempt=run.attempt_count,
                    worker_kind=run.spec.worker_kind.value,
                    lease_seconds=registration.lease_seconds,
                ),
            ),
        )

    def run_context_for(self, context: Any, execution_id: str, node_id: str) -> RunContext:
        """What a worker is handed. Built, never invoked -- the caller runs it."""
        execution = self._load(context, execution_id)
        run = execution.run_for(node_id)
        if run is None:
            from backend.contexts.execution.domain.errors import UnknownNode

            raise UnknownNode(execution_id=execution_id, node_id=node_id)
        return RunContext(
            execution_id=execution_id,
            node_id=node_id,
            attempt=max(run.attempt_count, 1),
            worker_kind=run.spec.worker_kind,
            side_effect=run.spec.side_effect,
            execution_key=run.spec.execution_key,
            idempotency_key=run.spec.idempotency_key,
            deadline_seconds=run.spec.timeout_seconds,
        )

    def record_success(self, context: Any, command: RecordSuccess) -> CommandResult:
        """Record a result from the worker holding the lease."""
        execution, revision = self._load_with_revision(context, command.execution_id)
        moment = datetime.now(timezone.utc)
        result = ExecutionResult(
            execution_key=command.execution_key,
            status=ExecutionStatus.SUCCEEDED,
            started_at=moment,
            completed_at=moment,
            detail=command.detail or {},
        )
        recorded = execution.record_result(
            command.node_id, command.worker_id, result, now=moment
        )
        return self._saved_checked(context, self._sealed_if_done(recorded), revision)

    def record_failure(self, context: Any, command: RecordFailure) -> CommandResult:
        execution, revision = self._load_with_revision(context, command.execution_id)
        moment = datetime.now(timezone.utc)
        result = None
        if command.execution_key:
            result = ExecutionResult(
                execution_key=command.execution_key,
                status=ExecutionStatus.FAILED,
                started_at=moment,
                completed_at=moment,
                failure_reason=command.reason,
            )
        failure = FailureRecord(
            failure_class=FailureClass(command.failure_class),
            reason=command.reason,
            occurred_at=moment,
            source=command.failure_source,
        )
        updated = execution.record_failure(
            command.node_id,
            command.worker_id,
            command.reason,
            result=result,
            now=moment,
            failure=failure,
        )
        self._observer.attempt_failed(
            str(updated.execution_id), command.node_id, failure.to_dict()
        )
        if not failure.outcome_known:
            # The most important thing this runtime can say out loud: we do not
            # know whether the change was applied.
            self._observer.outcome_unknown(
                str(updated.execution_id), command.node_id, failure.to_dict()
            )
        return self._saved_checked(context, updated, revision)

    def reclaim(self, context: Any, command: ReclaimNode) -> CommandResult:
        """Take back a node whose lease lapsed. Records ``UNKNOWN``.

        Revision-checked: a reclaim that lands after the holder recorded its
        outcome must lose, not overwrite (ADR-127 F-8).
        """
        execution, revision = self._load_with_revision(context, command.execution_id)
        return self._saved_checked(context, execution.reclaim(command.node_id), revision)

    def heartbeat(self, context: Any, command: Heartbeat) -> dict:
        """A worker reporting it is still alive. Does not extend the lease.

        Separate from renewal on purpose: a stuck worker must not be able to
        hold a node indefinitely by doing nothing but breathing.
        """
        execution = self._load(context, command.execution_id)
        run = execution.run_for(command.node_id)
        if run is None:
            raise UnknownNode(
                execution_id=command.execution_id, node_id=command.node_id
            )
        moment = datetime.now(timezone.utc)
        run.assert_held_by(command.worker_id, now=moment)
        beating = run.lease.beating(now=moment)
        updated = execution._with_run(replace(run, lease=beating))
        self._repository.replace(context, updated)
        return {
            "node_id": command.node_id,
            "worker_id": command.worker_id,
            "heartbeat_at": beating.heartbeat_at.isoformat(),
            "expires_at": beating.expires_at.isoformat(),
            "seconds_remaining": max(
                0, int((beating.expires_at - moment).total_seconds())
            ),
        }

    def silent_workers(
        self, context: Any, execution_id: str, *, silence_seconds: int = 60
    ) -> tuple:
        """Leases whose holders have gone quiet but have not yet lapsed.

        Evidence a worker is gone, not proof. Only expiry entitles anyone else
        to the node -- acting on the evidence alone is how two workers end up
        holding one lease.
        """
        execution = self._load(context, execution_id)
        moment = datetime.now(timezone.utc)
        return tuple(
            {
                "node_id": run.node_id,
                "worker_id": run.lease.worker_id,
                "silent_for_seconds": run.lease.silent_for(moment),
            }
            for run in execution.runs
            if run.lease is not None
            and run.state is NodeState.LEASED
            and run.lease.is_stale_at(moment, silence_seconds=silence_seconds)
        )

    def plan_recovery(self, context: Any, command: PlanRecovery):
        """Decide what to do with a run that stopped badly. Never acts."""
        execution = self._load(context, command.execution_id)
        retryable = tuple(
            node_id
            for node_id in execution.failed_nodes
            if self.plan_retry(context, command.execution_id, node_id).may_run_again
        )
        decision = plan_recovery_for(
            execution,
            RecoveryTrigger(command.trigger),
            retryable_nodes=retryable,
        )
        self._observer.recovery_decided(
            str(execution.execution_id), decision.to_dict()
        )
        return decision

    def history(self, context: Any, execution_id: str) -> tuple:
        """The recorded events for a run, oldest first.

        Read from the outbox, which retains published entries. When the event
        store arrives with the database migration this reads from there instead
        and no caller changes.
        """
        if self._outbox is None:
            return ()
        entries = getattr(self._outbox, "entries_for", None)
        if entries is None:
            return ()
        return tuple(entry.event for entry in entries(context, execution_id))

    def replay(self, context: Any, command: ReplayExecution):
        """Reconstruct what the run's state was. Executes nothing.

        The replayer holds no repository, no pool and no queue, so there is
        nothing here that could touch an external system even by accident.
        """
        events = self.history(context, command.execution_id)
        if not events:
            raise ExecutionNotFound(command.execution_id)
        # The id the caller asked for, as a hint only: the events win if they
        # name one, so a projection can never be relabelled (ADR-092).
        return self._replayer.replay(events, execution_id=command.execution_id)

    def plan_retry(self, context: Any, execution_id: str, node_id: str) -> RetryDecision:
        """Decide whether a node may run again. Pure, and safe to ask twice.

        Exposed as a query so an operator can see the decision -- and the reason
        behind it -- before anything acts on it.
        """
        execution = self._load(context, execution_id)
        run = execution.run_for(node_id)
        if run is None:
            raise UnknownNode(execution_id=execution_id, node_id=node_id)
        last = run.last_attempt
        return decide_retry(
            node_id=node_id,
            attempts_spent=run.attempt_count,
            attempts_allowed=run.spec.max_attempts,
            effect=profile_for(run.spec),
            failure=getattr(last, "failure", None) if last else None,
            policy=self._retry_policy,
        )

    def retry(self, context: Any, command: RetryNode) -> CommandResult:
        execution = self._load(context, command.execution_id)
        run = execution.run_for(command.node_id)
        after = run.state.value if run else "unknown"

        # No silent retry. The decision is computed, recorded, and must permit
        # the retry before the aggregate is even asked -- so a node whose last
        # outcome is unknown and whose effect is not repeatable cannot be run
        # again by anyone calling this, however they got here.
        decision = self.plan_retry(context, command.execution_id, command.node_id)
        self._observer.retry_decided(str(execution.execution_id), decision.to_dict())
        if not decision.may_run_again:
            raise RetryRefused(
                execution_id=command.execution_id,
                node_id=command.node_id,
                verdict=decision.verdict.value,
                reason=decision.reason,
            )

        retried = execution.retry(command.node_id)
        self._repository.replace(context, retried)

        updated = retried.run_for(command.node_id)
        return CommandResult(
            execution=retried,
            events=(
                ExecutionRetried(
                    metadata=self._metadata(context, retried),
                    execution_id=str(retried.execution_id),
                    node_id=command.node_id,
                    after=after,
                    attempt=updated.attempt_count,
                    attempts_remaining=updated.attempts_remaining,
                    idempotent=updated.spec.is_idempotent,
                ),
            ),
        )

    def skip(self, context: Any, command: SkipNode) -> CommandResult:
        execution = self._load(context, command.execution_id)
        return self._saved(context, execution.skip(command.node_id, command.reason))

    def compensate(self, context: Any, command: CompensateNode) -> CommandResult:
        """Record that a node was compensated. **The platform did not do it.**

        This marks a node ``COMPENSATED``; nothing dispatches a compensating
        action, because no compensating action exists to dispatch. So the event
        this emits says exactly that: the outcome is **not known** and the
        original change is assumed to **still be out there**.

        Those two field values are the whole reason this emits at all. Before
        Phase 5.3 the compensation events were declared and never constructed —
        an operator subscribing to ``execution.runtime.compensation_concluded``
        would have waited forever while believing they had compensation
        observability, which is worse than having none. Emitting a truthful
        "somebody asserted this was compensated and the platform cannot confirm
        it" is strictly better than emitting nothing, and far better than
        emitting ``change_remains=False`` for something nobody verified.
        """
        execution = self._load(context, command.execution_id)
        compensated = execution.compensate(command.node_id)
        return self._saved(
            context,
            compensated,
            (
                NodeCompensationConcluded(
                    metadata=self._metadata(context, compensated),
                    execution_id=str(compensated.execution_id),
                    node_id=command.node_id,
                    # The node is its own compensation subject: there is no
                    # separate compensating node, and naming a fictional one
                    # would be the dishonesty this event was rewritten to avoid.
                    compensating_node_id=command.node_id,
                    outcome="recorded",
                    change_remains=True,
                    outcome_known=False,
                    reason=(
                        "the node was marked compensated by command; this "
                        "platform dispatches no compensating action, so whether "
                        "the original change was actually undone is unknown"
                    ),
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------

    def checkpoint(self, context: Any, command: CreateCheckpoint) -> CommandResult:
        execution = self._load(context, command.execution_id)
        checkpointed = execution.checkpoint(
            command.label,
            payload_ref=command.payload_ref,
            recorded_by=command.recorded_by,
        )
        self._repository.replace(context, checkpointed)

        checkpoint = checkpointed.latest_checkpoint
        return CommandResult(
            execution=checkpointed,
            events=(
                ExecutionCheckpointCreated(
                    metadata=self._metadata(context, checkpointed),
                    execution_id=str(checkpointed.execution_id),
                    checkpoint_id=str(checkpoint.checkpoint_id),
                    sequence=checkpoint.sequence,
                    label=checkpoint.label,
                    finished_nodes=len(checkpoint.finished_nodes),
                    digest=checkpoint.digest or "",
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetExecution) -> Execution:
        return self._load(context, query.execution_id)

    def ready_nodes(self, context: Any, query: GetReadyNodes) -> tuple:
        """What could be dispatched now.

        The scheduling decision -- how many, how fast, to which workers -- is the
        caller's. A service that made it would own the concurrency policy, and
        that is a deployment decision rather than a domain one.
        """
        return self._load(context, query.execution_id).ready_nodes()

    def evaluate(self, context: Any, execution_id: str, to_state: str):
        """Run the policy without moving. What an operator reads during an incident."""
        return self._policy.evaluate(
            self._load(context, execution_id), ExecutionState(to_state)
        )

    def stream_state(self, context: Any, execution_id: str) -> dict:
        """A snapshot shaped for streaming to a watcher.

        Deliberately a *snapshot* rather than a subscription: this context owns no
        transport. Whatever streams it decides how often to ask, and gets an
        answer that is true at the moment it asked.
        """
        execution = self._load(context, execution_id)
        finished, total = execution.progress
        return {
            "execution_id": str(execution.execution_id),
            "state": execution.state.value,
            "progress": {"finished": finished, "total": total},
            "ready": list(execution.ready_nodes()),
            "leased": list(execution.leased_nodes),
            "ambiguous": list(execution.ambiguous_nodes),
            "blocked": list(execution.blocked_nodes()),
            "nodes": [
                {"node_id": r.node_id, "state": r.state.value, "attempts": r.attempt_count}
                for r in sorted(execution.runs, key=lambda r: r.node_id)
            ],
        }

    def list(self, context: Any, query: ListExecutions) -> tuple:
        found = self._repository.all(context)
        if query.mission_id:
            found = tuple(e for e in found if e.mission_id == query.mission_id)
        if query.workflow_id:
            found = tuple(e for e in found if e.workflow_id == query.workflow_id)
        if query.state:
            wanted = ExecutionState(query.state)
            found = tuple(e for e in found if e.state is wanted)
        if query.live_only:
            found = tuple(e for e in found if e.state.is_live)
        return tuple(found)

    @staticmethod
    def _sealed_if_done(execution: Execution) -> Execution:
        """Close a run whose work is finished. **The root of three findings.**

        A governed read's node succeeds and its run stays ``RUNNING`` forever,
        because nothing ever completed it. That is not cosmetic: ``RUNNING`` is
        the state dispatch discovery, startup recovery and the scheduler's
        target set all key on, so every finished read stayed in the set of
        things they had to consider. A live store reached 2213 of them, and the
        consequences were a discovery window full of dead rows (F-10), a
        recovery scan seeding hundreds of targets (F-14), and a dispatch loop
        too slow to come back and record a result it had just leased.

        Conservative on purpose: it seals only when every node **succeeded or
        was skipped**. A run with a failed or ambiguous node is not finished
        being decided about, and sealing it COMPLETED would be asserting an
        outcome nobody established.
        """
        if execution.state is not ExecutionState.RUNNING:
            return execution
        states = {run.state for run in execution.runs}
        if not states or not states <= {NodeState.SUCCEEDED, NodeState.SKIPPED}:
            return execution
        try:
            return execution.complete()
        except Exception:  # noqa: BLE001 - the aggregate's refusal is the answer
            return execution

    def dispatchable(self, context: Any, *, limit: int = 100) -> tuple:
        """Execution ids the **durable store** says may be dispatched right now.

        The query a scheduler needs and did not have. Dispatch targets lived in
        a process-local list, so a run started by any other process was never
        dispatched by anybody — the limitation ADR-126 called F-3 (and the
        signal-fabric report called F-1). Asking the store instead is what makes
        dispatch survive the process that started it.

        Bounded and tenant-narrowed by the repository, exactly as
        ``find_by_state`` already was: under a tenant's context it returns that
        tenant's runs, and under the platform's it returns every tenant's — which
        is discovery, not authority. Being *found* here permits nothing; the
        dispatcher still rebuilds the tenant context from each node's sealed
        binding and the gateway still re-decides every stage.

        ``RUNNING`` alone, because ``accepts_dispatch`` is ``RUNNING`` alone. A
        repository without the query answers nothing rather than everything.
        """
        finder = getattr(self._repository, "find_by_state", None)
        if finder is None:
            return ()
        try:
            found = finder(
                context, (ExecutionState.RUNNING.value,),
                limit=limit, newest_first=True,
            )
        except TypeError:
            # A repository that predates the ordering argument. Correct, just
            # more likely to hand back a window of finished work.
            found = finder(context, (ExecutionState.RUNNING.value,), limit=limit)
        # **Only runs with something to dispatch.** ``RUNNING`` is not the same
        # question: a governed read's node succeeds while its run stays RUNNING,
        # so most of this table is work that is already over. Returning those
        # would spend every sweep re-loading executions nobody can act on, and
        # crowd out the ones somebody is waiting for (F-10).
        return tuple(
            str(execution.execution_id)
            for execution in found
            if tuple(execution.ready_nodes())
        )

    def reclaimable(self, context: Any, execution_id: str, *, now: Optional[datetime] = None) -> tuple:
        """Nodes whose leases have lapsed. What a sweeper asks for."""
        moment = now or datetime.now(timezone.utc)
        execution = self._load(context, execution_id)
        return tuple(
            sorted(
                r.node_id
                for r in execution.runs
                if r.state is NodeState.LEASED
                and r.lease is not None
                and r.lease.has_expired_at(moment)
            )
        )
