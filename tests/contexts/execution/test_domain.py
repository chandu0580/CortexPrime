"""The Execution domain: states, leases, attempts, the aggregate.

These tests are about the things that go wrong at three in the morning: two
workers holding one node, a result arriving from somebody who no longer holds
the lease, a retry that applies a destructive action twice, a run reporting
success over work that never finished.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionResult, ExecutionStatus, SideEffectClass
from backend.contexts.execution import (
    AmbiguousRetry,
    AttemptsExhausted,
    CheckpointAhead,
    DependenciesUnsatisfied,
    Execution,
    ExecutionFinished,
    ExecutionId,
    ExecutionLease,
    ExecutionState,
    IllegalExecutionTransition,
    IncompleteExecution,
    LeaseExpired,
    LeaseId,
    LeaseNotHeld,
    NoCheckpoint,
    NodeAlreadyLeased,
    NodeNotRunning,
    NodeRun,
    NodeSpec,
    NodeState,
    UnknownNode,
    WorkerCannotRun,
    WorkerKind,
    WorkerRegistration,
    execution_permitted_from,
    is_legal_execution_transition,
    published_status_of,
)

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


def _spec(node_id="audit", **overrides) -> NodeSpec:
    fields = dict(node_id=node_id, worker_kind=WorkerKind.SHELL)
    fields.update(overrides)
    return NodeSpec(**fields)


def _worker(worker_id="w-1", kinds=(WorkerKind.SHELL,), **overrides) -> WorkerRegistration:
    return WorkerRegistration(worker_id=worker_id, kinds=frozenset(kinds), **overrides)


def _execution(*specs, **overrides) -> Execution:
    fields = dict(
        workflow_id="W-1",
        workflow_digest="deadbeef",
        mission_id="M-1",
        nodes=specs or (_spec(),),
    )
    fields.update(overrides)
    return Execution.of(**fields)


def _running(*specs, **overrides) -> Execution:
    return _execution(*specs, **overrides).start()


def _result(key="k-1", status=ExecutionStatus.SUCCEEDED) -> ExecutionResult:
    return ExecutionResult(
        execution_key=key, status=status, started_at=NOW, completed_at=NOW
    )


# ----------------------------------------------------------------------
# State machines
# ----------------------------------------------------------------------


class TestExecutionState:
    def test_a_run_starts_pending_and_may_only_run_or_be_called_off(self) -> None:
        permitted = set(execution_permitted_from(ExecutionState.PENDING))
        # No completing, no failing: a run that never started cannot have an
        # outcome. It may run, be called off, or hit its deadline waiting.
        assert permitted == {"running", "cancelled", "timed_out"}

    def test_terminal_states_permit_nothing(self) -> None:
        for state in (
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.TIMED_OUT,
        ):
            assert state.is_terminal
            assert execution_permitted_from(state) == ()

    def test_a_paused_run_may_resume_or_be_abandoned_but_not_complete(self) -> None:
        assert is_legal_execution_transition(
            ExecutionState.PAUSED, ExecutionState.RUNNING
        )
        assert not is_legal_execution_transition(
            ExecutionState.PAUSED, ExecutionState.COMPLETED
        )


class TestNodeState:
    def test_unknown_is_terminal_but_not_finished(self) -> None:
        # The whole point of UNKNOWN: the attempt is over, but nobody may treat
        # its outcome as settled.
        assert NodeState.UNKNOWN.is_terminal
        assert not NodeState.UNKNOWN.is_finished

    def test_only_success_and_deliberate_skip_satisfy_a_dependent(self) -> None:
        satisfying = {s for s in NodeState if s.satisfies_dependents}
        assert satisfying == {NodeState.SUCCEEDED, NodeState.SKIPPED}

    def test_unknown_publishes_as_failed_and_that_loses_information(self) -> None:
        # The published contract has no word for "we do not know", so UNKNOWN
        # degrades to FAILED. Safe direction, but a real loss -- pinned so it is
        # never mistaken for an accident.
        assert published_status_of(NodeState.UNKNOWN) is ExecutionStatus.FAILED
        assert published_status_of(NodeState.SUCCEEDED) is ExecutionStatus.SUCCEEDED


# ----------------------------------------------------------------------
# Leases
# ----------------------------------------------------------------------


class TestExecutionLease:
    def _lease(self, **overrides) -> ExecutionLease:
        fields = dict(
            lease_id=LeaseId.new(),
            node_id="audit",
            worker_id="w-1",
            granted_at=NOW,
            expires_at=NOW + timedelta(seconds=300),
        )
        fields.update(overrides)
        return ExecutionLease(**fields)

    def test_a_lease_that_never_expires_is_refused(self) -> None:
        with pytest.raises(ContractViolation):
            self._lease(expires_at=NOW)

    def test_expiry_is_the_only_thing_that_makes_a_lease_reclaimable(self) -> None:
        lease = self._lease()
        assert lease.is_live_at(NOW + timedelta(seconds=299))
        assert lease.has_expired_at(NOW + timedelta(seconds=301))

    def test_renewal_extends_from_now_not_from_the_old_expiry(self) -> None:
        # Extending from the old expiry would let a worker that stalled for an
        # hour renew into a lease that is already long stale.
        renewed = self._lease().renewed(60, now=NOW + timedelta(seconds=280))
        assert renewed.expires_at == NOW + timedelta(seconds=340)

    def test_a_released_lease_is_not_live(self) -> None:
        released = self._lease().released(now=NOW + timedelta(seconds=10))
        assert released.is_released
        assert not released.is_live_at(NOW + timedelta(seconds=11))

    def test_held_by_is_exact(self) -> None:
        lease = self._lease()
        assert lease.held_by("w-1")
        assert not lease.held_by("w-2")


class TestNodeRun:
    def test_a_result_from_a_worker_that_does_not_hold_the_lease_is_refused(self) -> None:
        run = NodeRun(spec=_spec()).become_ready().leased_to("w-1", 300, now=NOW)
        with pytest.raises(LeaseNotHeld):
            run.assert_held_by("w-2", now=NOW)

    def test_a_result_arriving_after_the_lease_lapsed_is_refused(self) -> None:
        run = NodeRun(spec=_spec()).become_ready().leased_to("w-1", 300, now=NOW)
        with pytest.raises(LeaseExpired):
            run.assert_held_by("w-1", now=NOW + timedelta(seconds=301))

    def test_a_result_for_a_node_nobody_leased_is_refused(self) -> None:
        run = NodeRun(spec=_spec()).become_ready()
        with pytest.raises(NodeNotRunning):
            run.assert_held_by("w-1", now=NOW)

    def test_abandoning_a_run_leaves_it_unknown_not_failed(self) -> None:
        run = NodeRun(spec=_spec()).become_ready().leased_to("w-1", 300, now=NOW)
        abandoned = run.abandoned(now=NOW + timedelta(seconds=400))
        assert abandoned.state is NodeState.UNKNOWN
        assert abandoned.held_by == ""

    def test_attempts_are_counted_and_bounded(self) -> None:
        spec = _spec(max_attempts=2)
        run = NodeRun(spec=spec).become_ready().leased_to("w-1", 300, now=NOW)
        run = run.concluded(NodeState.FAILED, "w-1", failure_reason="boom", now=NOW)
        assert run.attempt_count == 1
        assert run.attempts_remaining == 1
        run = run.retried().leased_to("w-1", 300, now=NOW)
        run = run.concluded(NodeState.FAILED, "w-1", failure_reason="boom", now=NOW)
        assert run.attempts_remaining == 0
        with pytest.raises(AttemptsExhausted):
            run.retried()

    def test_a_retryable_read_needs_no_idempotency_key(self) -> None:
        _spec(max_attempts=3).assert_retryable_after(NodeState.FAILED)

    def test_retrying_an_ambiguous_mutation_without_a_key_is_refused(self) -> None:
        spec = _spec(
            max_attempts=2,
            side_effect=SideEffectClass.IRREVERSIBLE_WRITE,
            idempotency_key="k",
        )
        spec.assert_retryable_after(NodeState.FAILED)
        with pytest.raises(AmbiguousRetry):
            NodeSpec(
                node_id="pay",
                worker_kind=WorkerKind.HTTP,
                max_attempts=2,
                side_effect=SideEffectClass.IRREVERSIBLE_WRITE,
            ).assert_retryable_after(NodeState.UNKNOWN)

    def test_a_mutating_node_declares_itself(self) -> None:
        assert not _spec().mutates
        assert _spec(side_effect=SideEffectClass.DESTRUCTIVE).mutates

    def test_a_compensation_node_names_what_it_walks_back(self) -> None:
        spec = _spec(
            "restore",
            compensates="resize",
            side_effect=SideEffectClass.REVERSIBLE_WRITE,
        )
        assert spec.is_compensation


# ----------------------------------------------------------------------
# The aggregate
# ----------------------------------------------------------------------


class TestExecutionLifecycle:
    def test_a_run_with_no_nodes_is_refused(self) -> None:
        # Refused by the aggregate, not only by the command: a record loaded from
        # storage takes this path too, and a run with nothing in it has nothing
        # outstanding, so it would complete instantly reporting success.
        with pytest.raises(ContractViolation):
            _execution(nodes=())

    def test_a_run_that_cannot_name_its_graph_is_refused(self) -> None:
        with pytest.raises(ContractViolation):
            _execution(workflow_digest="  ")

    def test_starting_promotes_only_nodes_whose_dependencies_are_met(self) -> None:
        execution = _running(_spec("audit"), _spec("resize", depends_on=("audit",)))
        assert execution.ready_nodes() == ("audit",)
        assert execution.run_for("resize").state is NodeState.WAITING

    def test_a_dependent_becomes_ready_only_when_its_dependency_succeeds(self) -> None:
        execution = _running(_spec("audit"), _spec("resize", depends_on=("audit",)))
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_result("audit", "w-1", _result(), now=NOW)
        assert execution.ready_nodes() == ("resize",)

    def test_a_failed_dependency_leaves_the_dependent_blocked_forever(self) -> None:
        execution = _running(_spec("audit"), _spec("resize", depends_on=("audit",)))
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_failure("audit", "w-1", "no credentials", now=NOW)
        assert execution.ready_nodes() == ()
        assert execution.blocked_nodes() == ("resize",)

    def test_a_deliberate_skip_unblocks_dependents_but_a_failure_does_not(self) -> None:
        execution = _running(_spec("audit"), _spec("resize", depends_on=("audit",)))
        execution = execution.skip("audit", "already rightsized last week")
        assert execution.ready_nodes() == ("resize",)

    def test_progress_counts_finished_over_total(self) -> None:
        execution = _running(_spec("audit"), _spec("resize"))
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_result("audit", "w-1", _result(), now=NOW)
        assert execution.progress == (1, 2)

    def test_a_finished_run_refuses_further_moves(self) -> None:
        execution = _running().cancel("operator called it off")
        assert execution.state is ExecutionState.CANCELLED
        with pytest.raises(ExecutionFinished):
            execution.pause("too late")

    def test_an_illegal_move_names_what_was_permitted(self) -> None:
        # All work finished, but the run is paused. Completing from PAUSED would
        # skip the moment somebody decides it is safe to carry on.
        execution = _running().assign("audit", _worker(), now=NOW)
        execution = execution.record_result("audit", "w-1", _result(), now=NOW)
        execution = execution.pause("holding for the change window")
        with pytest.raises(IllegalExecutionTransition) as caught:
            execution.complete()
        assert "running" in caught.value.permitted

    def test_completing_with_outstanding_work_is_refused(self) -> None:
        execution = _running(_spec("audit"), _spec("resize"))
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_result("audit", "w-1", _result(), now=NOW)
        with pytest.raises(IncompleteExecution) as caught:
            execution.complete()
        assert caught.value.outstanding == ("resize",)

    def test_a_completed_run_carries_a_digest_and_verifies(self) -> None:
        execution = _running()
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_result("audit", "w-1", _result(), now=NOW)
        execution = execution.complete()
        assert execution.state is ExecutionState.COMPLETED
        assert execution.digest
        execution.verify_digest()

    def test_a_failed_run_says_why(self) -> None:
        execution = _running().fail("worker pool went away")
        assert execution.outcome_note == "worker pool went away"
        assert execution.state is ExecutionState.FAILED

    def test_a_timed_out_run_records_the_deadline_as_the_reason(self) -> None:
        execution = _running().time_out()
        assert execution.state is ExecutionState.TIMED_OUT
        assert execution.outcome_note

    def test_unknown_nodes_are_named_not_ignored(self) -> None:
        with pytest.raises(UnknownNode):
            _running().skip("nope", "reason")


class TestAssignment:
    def test_a_worker_that_cannot_run_the_kind_is_refused(self) -> None:
        execution = _running(_spec("audit", worker_kind=WorkerKind.KUBERNETES))
        with pytest.raises(WorkerCannotRun) as caught:
            execution.assign("audit", _worker(kinds=(WorkerKind.SHELL,)), now=NOW)
        assert caught.value.needs == "kubernetes"

    def test_a_node_whose_dependencies_are_unmet_cannot_be_dispatched(self) -> None:
        execution = _running(_spec("audit"), _spec("resize", depends_on=("audit",)))
        with pytest.raises(DependenciesUnsatisfied) as caught:
            execution.assign("resize", _worker(), now=NOW)
        assert caught.value.waiting_on == ("audit",)

    def test_a_second_worker_cannot_take_a_leased_node(self) -> None:
        execution = _running().assign("audit", _worker("w-1"), now=NOW)
        with pytest.raises(NodeAlreadyLeased) as caught:
            execution.assign("audit", _worker("w-2"), now=NOW)
        assert caught.value.held_by == "w-1"

    def test_a_result_from_the_wrong_worker_is_refused(self) -> None:
        execution = _running().assign("audit", _worker("w-1"), now=NOW)
        with pytest.raises(LeaseNotHeld):
            execution.record_result("audit", "w-2", _result(), now=NOW)

    def test_a_result_after_the_lease_lapsed_is_refused(self) -> None:
        execution = _running().assign("audit", _worker("w-1"), now=NOW)
        with pytest.raises(LeaseExpired):
            execution.record_result(
                "audit", "w-1", _result(), now=NOW + timedelta(hours=2)
            )

    def test_reclaiming_a_lapsed_lease_leaves_the_node_unknown(self) -> None:
        execution = _running().assign("audit", _worker("w-1"), now=NOW)
        reclaimed = execution.reclaim("audit", now=NOW + timedelta(hours=2))
        assert reclaimed.run_for("audit").state is NodeState.UNKNOWN
        assert reclaimed.ambiguous_nodes == ("audit",)

    def test_a_live_lease_cannot_be_reclaimed_out_from_under_a_worker(self) -> None:
        execution = _running().assign("audit", _worker("w-1"), now=NOW)
        with pytest.raises(ContractViolation, match="has not expired"):
            execution.reclaim("audit", now=NOW + timedelta(seconds=1))


class TestRetryAndAmbiguity:
    def test_a_failed_retryable_node_returns_to_ready(self) -> None:
        execution = _running(_spec("audit", max_attempts=2))
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_failure("audit", "w-1", "transient", now=NOW)
        execution = execution.retry("audit")
        assert execution.ready_nodes() == ("audit",)

    def test_retrying_an_unknown_non_idempotent_mutation_is_refused(self) -> None:
        spec = _spec(
            "delete-bucket",
            side_effect=SideEffectClass.DESTRUCTIVE,
            max_attempts=2,
            worker_kind=WorkerKind.SHELL,
        )
        execution = _running(spec).assign("delete-bucket", _worker(), now=NOW)
        execution = execution.reclaim("delete-bucket", now=NOW + timedelta(hours=2))
        with pytest.raises(AmbiguousRetry):
            execution.retry("delete-bucket")

    def test_an_ambiguous_node_may_be_skipped_or_compensated_deliberately(self) -> None:
        spec = _spec(
            "delete-bucket", side_effect=SideEffectClass.DESTRUCTIVE, max_attempts=2
        )
        execution = _running(spec).assign("delete-bucket", _worker(), now=NOW)
        execution = execution.reclaim("delete-bucket", now=NOW + timedelta(hours=2))
        compensated = execution.compensate("delete-bucket")
        assert compensated.run_for("delete-bucket").state is NodeState.COMPENSATED
        assert compensated.ambiguous_nodes == ()
        skipped = execution.skip("delete-bucket", "verified by hand: bucket is gone")
        assert skipped.run_for("delete-bucket").state is NodeState.SKIPPED

    def test_exhausting_attempts_is_refused_rather_than_looping(self) -> None:
        execution = _running(_spec("audit", max_attempts=1))
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_failure("audit", "w-1", "boom", now=NOW)
        with pytest.raises(AttemptsExhausted):
            execution.retry("audit")

    def test_a_mutating_node_that_succeeded_is_recorded_as_having_changed_things(
        self,
    ) -> None:
        spec = _spec("resize", side_effect=SideEffectClass.REVERSIBLE_WRITE)
        execution = _running(spec).assign("resize", _worker(), now=NOW)
        execution = execution.record_result("resize", "w-1", _result(), now=NOW)
        assert execution.mutated_nodes == ("resize",)


class TestCheckpointsAndResume:
    def _at_checkpoint(self) -> Execution:
        execution = _running(_spec("audit"), _spec("resize", depends_on=("audit",)))
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_result("audit", "w-1", _result(), now=NOW)
        return execution.checkpoint("audit complete")

    def test_a_checkpoint_captures_what_had_finished(self) -> None:
        execution = self._at_checkpoint()
        checkpoint = execution.latest_checkpoint
        assert checkpoint.finished_nodes == frozenset({"audit"})
        assert checkpoint.resume_from == ("resize",)
        assert checkpoint.digest

    def test_checkpoints_are_sequenced(self) -> None:
        execution = self._at_checkpoint().checkpoint("second")
        assert [c.sequence for c in execution.checkpoints] == [1, 2]

    def test_pausing_says_why_and_resuming_returns_to_running(self) -> None:
        paused = self._at_checkpoint().pause("waiting for the change window")
        assert paused.state is ExecutionState.PAUSED
        assert paused.outcome_note == "waiting for the change window"
        resumed = paused.resume()
        assert resumed.state is ExecutionState.RUNNING
        assert resumed.outcome_note is None

    def test_resuming_from_a_named_checkpoint_records_which_one(self) -> None:
        paused = self._at_checkpoint().pause("change window")
        checkpoint_id = str(paused.latest_checkpoint.checkpoint_id)
        resumed = paused.resume(checkpoint_id)
        assert resumed.resumed_from == checkpoint_id

    def test_resuming_from_a_checkpoint_that_does_not_exist_is_refused(self) -> None:
        paused = self._at_checkpoint().pause("change window")
        with pytest.raises(NoCheckpoint):
            paused.resume("01JZZZZZZZZZZZZZZZZZZZZZZZ")

    def test_resuming_a_run_with_no_checkpoints_is_permitted(self) -> None:
        # Resuming to the beginning is legitimate; only naming a missing one is not.
        paused = _running().pause("hold")
        assert paused.resume().state is ExecutionState.RUNNING

    def test_resuming_into_a_checkpoint_ahead_of_the_run_is_refused(self) -> None:
        # Rewind the run behind its own checkpoint. The checkpoint now claims
        # work the run cannot show -- exactly the corruption that would let a
        # resume skip real work and call it already done.
        paused = self._at_checkpoint().pause("change window")
        ahead = paused.latest_checkpoint
        rewound = Execution(
            execution_id=paused.execution_id,
            workflow_id=paused.workflow_id,
            workflow_digest=paused.workflow_digest,
            mission_id=paused.mission_id,
            state=ExecutionState.PAUSED,
            runs=tuple(NodeRun(spec=r.spec) for r in paused.runs),
            checkpoints=(ahead,),
            started_at=paused.started_at,
            outcome_note=paused.outcome_note,
        )
        with pytest.raises(CheckpointAhead) as caught:
            rewound.resume(str(ahead.checkpoint_id))
        assert caught.value.disputed == ("audit",)


class TestDigest:
    def test_the_digest_covers_what_actually_happened(self) -> None:
        execution = _running()
        execution = execution.assign("audit", _worker(), now=NOW)
        execution = execution.record_result("audit", "w-1", _result(), now=NOW)
        sealed = execution.complete()
        payload = sealed.digest_payload()
        assert payload["workflow_digest"] == "deadbeef"
        assert any(node["node_id"] == "audit" for node in payload["nodes"])

    def test_two_runs_of_the_same_work_hash_the_same(self) -> None:
        def build() -> Execution:
            execution = _execution().start()
            execution = execution.assign("audit", _worker(), now=NOW)
            return execution.record_result("audit", "w-1", _result(), now=NOW)

        first, second = build(), build()
        assert first.digest_payload()["nodes"] == second.digest_payload()["nodes"]
