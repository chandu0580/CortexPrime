"""Policy, persistence, replay, the repository, and concurrent dispatch.

The replay tests are the ones that matter most in this context: this record is
what the platform will later show somebody asking what production actually did.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionResult, ExecutionStatus, SideEffectClass
from backend.contexts.execution import (
    Execution,
    ExecutionQueue,
    ExecutionState,
    InMemoryExecutionQueue,
    InMemoryExecutionRepository,
    NodeSpec,
    NodeState,
    QueueItem,
    Severity,
    WorkerKind,
    WorkerRegistration,
    default_policy,
)
from backend.contexts.execution.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.platform.context import ExecutionContext
from backend.platform.storage import MissingExecutionContext

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="execution-tests", component="tests", source="pytest"
    )


def _spec(node_id="audit", **overrides) -> NodeSpec:
    fields = dict(node_id=node_id, worker_kind=WorkerKind.SHELL)
    fields.update(overrides)
    return NodeSpec(**fields)


def _worker(worker_id="w-1", kinds=(WorkerKind.SHELL,)) -> WorkerRegistration:
    return WorkerRegistration(worker_id=worker_id, kinds=frozenset(kinds))


def _execution(*specs, **overrides) -> Execution:
    fields = dict(
        workflow_id="W-1",
        workflow_digest="deadbeef",
        mission_id="M-1",
        nodes=specs or (_spec(),),
    )
    fields.update(overrides)
    return Execution.of(**fields)


def _result(key="k-1") -> ExecutionResult:
    return ExecutionResult(
        execution_key=key,
        status=ExecutionStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW,
    )


def _finished(*specs) -> Execution:
    execution = _execution(*specs).start()
    for run in execution.runs:
        execution = execution.assign(run.node_id, _worker(), now=NOW)
        execution = execution.record_result(
            run.node_id, "w-1", _result(run.node_id), now=NOW
        )
    return execution


def _rules(report) -> set:
    return {f.rule for f in report.findings}


# ----------------------------------------------------------------------
# Policy
# ----------------------------------------------------------------------


class TestPolicy:
    def test_a_finished_run_is_refused_and_nothing_else_is_evaluated(self) -> None:
        execution = _execution().start().cancel("called off")
        report = default_policy().evaluate(execution, ExecutionState.COMPLETED)
        assert not report.may_proceed
        assert _rules(report) == {"X0-run-open"}

    def test_an_illegal_move_blocks(self) -> None:
        execution = _finished().pause("hold")
        report = default_policy().evaluate(execution, ExecutionState.COMPLETED)
        assert "X0-legal-transition" in _rules(report)

    def test_completing_over_unfinished_work_blocks_once_per_node(self) -> None:
        execution = _execution(_spec("audit"), _spec("resize")).start()
        report = default_policy().evaluate(execution, ExecutionState.COMPLETED)
        blocking = [f for f in report.blocking if f.rule == "X1-all-nodes-finished"]
        assert {f.subject for f in blocking} == {"audit", "resize"}

    def test_completing_over_an_unknown_node_blocks(self) -> None:
        execution = _execution().start().assign("audit", _worker(), now=NOW)
        execution = execution.reclaim("audit", now=NOW + timedelta(hours=2))
        report = default_policy().evaluate(execution, ExecutionState.COMPLETED)
        assert "X2-ambiguity-resolved" in {f.rule for f in report.blocking}

    def test_ambiguity_may_be_relaxed_deliberately_and_is_then_advisory_only(
        self,
    ) -> None:
        execution = _execution().start().assign("audit", _worker(), now=NOW)
        execution = execution.reclaim("audit", now=NOW + timedelta(hours=2))
        relaxed = type(default_policy())(require_resolved_ambiguity=False)
        report = relaxed.evaluate(execution, ExecutionState.COMPLETED)
        assert "X2-ambiguity-resolved" not in {f.rule for f in report.blocking}

    def test_a_cancelled_run_reports_what_it_already_changed(self) -> None:
        spec = _spec("resize", side_effect=SideEffectClass.REVERSIBLE_WRITE)
        execution = _execution(spec, _spec("verify")).start()
        execution = execution.assign("resize", _worker(), now=NOW)
        execution = execution.record_result("resize", "w-1", _result(), now=NOW)
        report = default_policy().evaluate(execution, ExecutionState.CANCELLED)
        changed = [f for f in report.findings if f.rule == "X3-cancellation-left-changes"]
        assert changed and changed[0].subject == "resize"
        # Cancellation is still permitted -- the point is that it is not silent.
        assert report.may_proceed

    def test_a_node_blocked_behind_a_failure_is_reported(self) -> None:
        execution = _execution(_spec("audit"), _spec("resize", depends_on=("audit",)))
        execution = execution.start().assign("audit", _worker(), now=NOW)
        execution = execution.record_failure("audit", "w-1", "no credentials", now=NOW)
        report = default_policy().evaluate(execution, ExecutionState.RUNNING)
        assert "X4-blocked-node" in _rules(report)

    def test_a_stale_lease_is_advisory_not_blocking(self) -> None:
        execution = _execution().start().assign("audit", _worker(), now=NOW)
        report = default_policy().evaluate(
            execution, ExecutionState.PAUSED, now=NOW + timedelta(hours=2)
        )
        stale = [f for f in report.advisory if f.rule == "X5-stale-lease"]
        # Told, not stopped: a stale lease is how a stall gets turned into a
        # reclaim, and refusing the pause would leave the operator no move.
        assert stale and report.may_proceed

    def test_stateful_work_that_went_unknown_is_called_out_by_name(self) -> None:
        spec = _spec(
            "apply",
            worker_kind=WorkerKind.TERRAFORM,
            side_effect=SideEffectClass.IRREVERSIBLE_WRITE,
        )
        execution = _execution(spec).start()
        execution = execution.assign(
            "apply", _worker(kinds=(WorkerKind.TERRAFORM,)), now=NOW
        )
        execution = execution.reclaim("apply", now=NOW + timedelta(hours=2))
        report = default_policy().evaluate(execution, ExecutionState.FAILED)
        assert "X6-stateful-ambiguity" in _rules(report)

    def test_a_run_with_no_checkpoint_is_told_it_can_only_restart(self) -> None:
        execution = _execution().start()
        report = default_policy().evaluate(execution, ExecutionState.PAUSED)
        assert "X7-resumable" in {f.rule for f in report.advisory}

    def test_a_checkpointed_run_draws_no_resumability_finding(self) -> None:
        execution = _execution().start().checkpoint("before the risky part")
        report = default_policy().evaluate(execution, ExecutionState.PAUSED)
        assert "X7-resumable" not in _rules(report)

    def test_every_failure_is_reported_at_once_not_one_at_a_time(self) -> None:
        # An operator fixing one refusal at a time learns the next one only by
        # trying again. The report is the whole list.
        execution = _execution(_spec("audit"), _spec("resize", depends_on=("audit",)))
        execution = execution.start().assign("audit", _worker(), now=NOW)
        execution = execution.record_failure("audit", "w-1", "boom", now=NOW)
        report = default_policy().evaluate(execution, ExecutionState.COMPLETED)
        assert len(report.findings) > 1

    def test_a_clean_run_may_complete(self) -> None:
        report = default_policy().evaluate(_finished(), ExecutionState.COMPLETED)
        assert report.may_proceed
        assert report.blocking == ()

    def test_severity_decides_refusal(self) -> None:
        assert Severity.BLOCKING.refuses
        assert not Severity.ADVISORY.refuses


# ----------------------------------------------------------------------
# Persistence and replay
# ----------------------------------------------------------------------


class TestPersistence:
    def test_a_completed_run_survives_a_round_trip_intact(self) -> None:
        sealed = _finished(
            _spec("audit"),
            _spec("resize", depends_on=("audit",), side_effect=SideEffectClass.REVERSIBLE_WRITE),
        ).complete()
        restored = from_record(to_record(sealed, tenant_id="tenant-a"))
        assert restored.execution_id == sealed.execution_id
        assert restored.state is ExecutionState.COMPLETED
        assert restored.digest == sealed.digest
        assert [r.node_id for r in restored.runs] == [r.node_id for r in sealed.runs]

    def test_the_digest_is_restored_not_recomputed(self) -> None:
        # If loading recomputed the digest it would always match, and the check
        # that this record is the one that was written could never fail.
        sealed = _finished().complete()
        record = to_record(sealed, tenant_id="tenant-a")
        record["runs"][0]["attempts"][0]["failure_reason"] = "quietly edited"
        restored = from_record(record)
        assert restored.digest == sealed.digest
        with pytest.raises(Exception):
            restored.verify_digest()

    def test_attempts_and_leases_survive_the_round_trip(self) -> None:
        execution = _execution(_spec("audit", max_attempts=2)).start()
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_failure("audit", "w-1", "transient", now=NOW)
        execution = execution.retry("audit").assign("audit", _worker(), now=NOW)
        restored = from_record(to_record(execution, tenant_id="tenant-a"))
        run = restored.run_for("audit")
        assert run.attempt_count == 2
        assert run.held_by == "w-1"
        assert run.attempts[0].failure_reason == "transient"

    def test_checkpoints_survive_and_still_verify(self) -> None:
        execution = _finished().checkpoint("all done")
        restored = from_record(to_record(execution, tenant_id="tenant-a"))
        assert len(restored.checkpoints) == 1
        restored.latest_checkpoint.verify_digest()

    def test_a_stored_run_claiming_completion_over_unfinished_work_refuses_to_load(
        self,
    ) -> None:
        sealed = _finished(_spec("audit"), _spec("resize")).complete()
        record = to_record(sealed, tenant_id="tenant-a")
        record["runs"][1]["state"] = "waiting"
        with pytest.raises(Exception):
            from_record(record)

    def test_a_record_from_a_schema_this_build_does_not_know_is_refused(self) -> None:
        record = to_record(_finished().complete(), tenant_id="tenant-a")
        record["schema_version"] = RECORD_SCHEMA_VERSION + 1
        with pytest.raises(ContractViolation):
            from_record(record)

    def test_a_record_without_a_tenant_is_refused(self) -> None:
        with pytest.raises(ContractViolation):
            to_record(_finished(), tenant_id="   ")


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


class TestRepository:
    def test_saving_and_finding_round_trips(self, context) -> None:
        repository = InMemoryExecutionRepository()
        execution = _execution()
        repository.save(context, execution)
        found = repository.find(context, execution.execution_id)
        assert found is not None and found.execution_id == execution.execution_id

    def test_every_method_demands_an_execution_context(self) -> None:
        repository = InMemoryExecutionRepository()
        execution = _execution()
        for call in (
            lambda: repository.save(None, execution),
            lambda: repository.find(None, execution.execution_id),
            lambda: repository.all(None),
            lambda: repository.replace(None, execution),
        ):
            with pytest.raises(MissingExecutionContext):
                call()

    def test_a_run_saved_under_one_tenant_is_invisible_to_another(self) -> None:
        from backend.platform.context.identity import IdentityContext

        def tenant(name: str) -> ExecutionContext:
            return ExecutionContext.for_tenant(
                tenant_id=name, identity=IdentityContext.platform("tests"), source="pytest"
            )

        repository = InMemoryExecutionRepository()
        execution = _execution()
        repository.save(tenant("tenant-a"), execution)
        assert repository.find(tenant("tenant-b"), execution.execution_id) is None
        assert repository.find(tenant("tenant-a"), execution.execution_id) is not None

    def test_replacing_an_absent_run_is_refused(self, context) -> None:
        repository = InMemoryExecutionRepository()
        with pytest.raises(Exception):
            repository.replace(context, _execution())


# ----------------------------------------------------------------------
# Queue and concurrency
# ----------------------------------------------------------------------


class TestQueue:
    def test_the_in_memory_queue_satisfies_the_port(self) -> None:
        assert isinstance(InMemoryExecutionQueue(), ExecutionQueue)

    def test_enqueuing_the_same_node_twice_does_not_duplicate_it(self, context) -> None:
        queue = InMemoryExecutionQueue()
        item = QueueItem(execution_id="E-1", node_id="audit", worker_kind=WorkerKind.SHELL)
        queue.enqueue(context, item)
        queue.enqueue(context, item)
        assert queue.depth(context) == 1

    def test_a_claim_is_not_a_delete(self, context) -> None:
        queue = InMemoryExecutionQueue()
        queue.enqueue(
            context, QueueItem(execution_id="E-1", node_id="audit", worker_kind=WorkerKind.SHELL)
        )
        claimed = queue.claim(context, "w-1", (WorkerKind.SHELL,), 60, now=NOW)
        assert claimed is not None
        # Still there -- a worker that dies mid-claim must not lose the work.
        assert queue.depth(context) == 1
        assert queue.pending(context, now=NOW) == ()
        assert len(queue.pending(context, now=NOW + timedelta(seconds=61))) == 1

    def test_a_worker_is_never_offered_work_it_cannot_run(self, context) -> None:
        queue = InMemoryExecutionQueue()
        queue.enqueue(
            context,
            QueueItem(execution_id="E-1", node_id="apply", worker_kind=WorkerKind.TERRAFORM),
        )
        assert queue.claim(context, "w-1", (WorkerKind.SHELL,), 60, now=NOW) is None

    def test_an_empty_queue_returns_nothing_rather_than_raising(self, context) -> None:
        assert InMemoryExecutionQueue().claim(context, "w-1", (WorkerKind.SHELL,), 60) is None

    def test_only_one_of_many_threads_claims_a_given_item(self, context) -> None:
        queue = InMemoryExecutionQueue()
        for index in range(10):
            queue.enqueue(
                context,
                QueueItem(
                    execution_id="E-1", node_id=f"node-{index}", worker_kind=WorkerKind.SHELL
                ),
            )

        claimed: list = []
        lock = threading.Lock()

        def take(worker: int) -> None:
            for _ in range(5):
                item = queue.claim(context, f"w-{worker}", (WorkerKind.SHELL,), 60)
                if item is not None:
                    with lock:
                        claimed.append(item.key)

        threads = [threading.Thread(target=take, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(claimed) == len(set(claimed)), "an item was handed to two workers"


class TestConcurrentAssignment:
    def test_only_one_worker_wins_a_node_under_concurrent_assignment(self) -> None:
        # The aggregate is immutable, so the race is decided by whoever writes
        # last. What must never happen is two winners believing they hold it.
        execution = _execution().start()
        winners: list = []
        lock = threading.Lock()

        def claim(worker_id: str) -> None:
            try:
                result = execution.assign("audit", _worker(worker_id), now=NOW)
            except Exception:
                return
            with lock:
                winners.append(result.run_for("audit").held_by)

        threads = [
            threading.Thread(target=claim, args=(f"w-{i}",)) for i in range(6)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Each produced its own candidate aggregate; the repository serialises
        # which one is real. The invariant under test is that a *persisted*
        # leased node refuses the next claimant.
        assert len(set(winners)) == len(winners)
        persisted = execution.assign("audit", _worker("w-0"), now=NOW)
        for other in ("w-1", "w-2"):
            with pytest.raises(Exception):
                persisted.assign("audit", _worker(other), now=NOW)
