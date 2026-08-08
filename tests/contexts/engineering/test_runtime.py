"""The Engineering Runtime: orchestration, rollback, policy, concurrency.

The rollback and concurrency tests are the ones worth reading. Both exercise
failure modes that cannot be produced by a real collaborator on demand, which is
why the ports exist as ports.
"""

from __future__ import annotations

import threading

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.engineering import (
    CollaboratorUnavailable,
    ConcurrentModification,
    EngineeringRuntime,
    GetLifecycleCapability,
    GetRuntimeState,
    IllegalTransition,
    ImplementationCompleted,
    ImplementationStarted,
    PolicyRefused,
    PreconditionFailed,
    ReviewCompleted,
    ReviewOutcome,
    ReviewRequested,
    TransitionRolledBack,
    VerificationCompleted,
    VerificationRequested,
    WorkOrderPhase,
    WorkOrderUnknown,
    Collaborators,
    default_policy,
)

from tests.contexts.engineering.conftest import drive

WORK_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
TO_IMPLEMENTATION = ("assigned", "spec_tests", "implementation")


# ----------------------------------------------------------------------
# Legality
# ----------------------------------------------------------------------


def test_a_legal_transition_moves_the_work_order(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    result = full_runtime.transition(context, WORK_ID, "assigned", actor="orchestrator")
    assert result.snapshot.phase is WorkOrderPhase.ASSIGNED


def test_an_illegal_transition_is_refused_before_the_port_is_called(
    full_runtime, work_order_port, context
):
    """Nothing to roll back from a refusal that happened before anything began."""
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    with pytest.raises(IllegalTransition):
        full_runtime.transition(context, WORK_ID, "review", actor="x")
    assert work_order_port.transition_calls == []


def test_an_unknown_phase_is_refused(full_runtime, work_order_port, context):
    from backend.contexts.engineering import PhaseUnknown

    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    with pytest.raises(PhaseUnknown):
        full_runtime.transition(context, WORK_ID, "shipped", actor="x")


def test_an_unknown_work_order_is_refused(full_runtime, context):
    with pytest.raises(WorkOrderUnknown):
        full_runtime.transition(context, "01ARZ3NDEKTSV4RRFFQ69G5FAW", "assigned", actor="x")


def test_an_actor_is_required(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    with pytest.raises(ContractViolation):
        full_runtime.transition(context, WORK_ID, "assigned", actor="   ")


def test_a_terminal_work_order_cannot_move(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.CLOSED)
    with pytest.raises(IllegalTransition) as caught:
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")
    assert "terminal" in caught.value.reason


# ----------------------------------------------------------------------
# Collaborators
# ----------------------------------------------------------------------


def test_a_phase_with_no_collaborator_is_refused(bare_runtime, work_order_port, context):
    """Proceeding unorchestrated produces an unreviewed merge that looks reviewed."""
    work_order_port.add(WORK_ID, WorkOrderPhase.IMPLEMENTATION)
    with pytest.raises(CollaboratorUnavailable) as caught:
        bare_runtime.transition(context, WORK_ID, "review", actor="x")
    assert caught.value.port == "review"


def test_the_work_order_is_not_moved_when_a_collaborator_is_missing(
    bare_runtime, work_order_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.IMPLEMENTATION)
    with pytest.raises(CollaboratorUnavailable):
        bare_runtime.transition(context, WORK_ID, "review", actor="x")
    assert work_order_port.transition_calls == []


def test_capability_reports_what_is_wired(bare_runtime):
    from backend.contexts.engineering import EngineeringRuntimeQueries

    capability = EngineeringRuntimeQueries(bare_runtime).capability(GetLifecycleCapability())
    assert capability["wired"] == ["work_order"]
    assert set(capability["missing"]) == {"context", "review", "verification"}
    assert "review" not in capability["reachable_phases"]


def test_a_runtime_without_a_work_order_port_cannot_be_built():
    with pytest.raises(CollaboratorUnavailable):
        Collaborators(work_order=None)  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# Events
# ----------------------------------------------------------------------


def test_entering_implementation_emits_started_with_a_bundle(
    full_runtime, work_order_port, context_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    result = drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION)

    assert result.event_types == (ImplementationStarted.EVENT_TYPE,)
    assert result.events[0].context_bundle == f"manifest-{WORK_ID}"
    assert context_port.assembled == [(WORK_ID, 1)]


def test_entering_review_emits_completed_and_requested(
    full_runtime, work_order_port, review_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION)
    result = full_runtime.transition(context, WORK_ID, "review", actor="implementer")

    assert result.event_types == (
        ImplementationCompleted.EVENT_TYPE,
        ReviewRequested.EVENT_TYPE,
    )
    requested = result.events[1]
    assert requested.lenses == ("correctness", "security")
    assert review_port.requests == [(WORK_ID, 1, ("correctness", "security"))]


def test_a_review_request_must_name_its_lenses(full_runtime, work_order_port, review_port, context):
    """A request for 'review' with no lens cannot be shown to have covered anything."""
    review_port._lenses = ()  # noqa: SLF001
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION)

    with pytest.raises(TransitionRolledBack):
        full_runtime.transition(context, WORK_ID, "review", actor="x")


def test_entering_verification_emits_review_completed_and_verification_requested(
    full_runtime, work_order_port, verification_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION + ("review",))
    result = full_runtime.transition(context, WORK_ID, "verification", actor="reviewer")

    assert result.event_types == (
        ReviewCompleted.EVENT_TYPE,
        VerificationRequested.EVENT_TYPE,
    )
    completed = result.events[0]
    assert completed.lenses_reported == ("correctness", "security")
    assert completed.passed is True
    assert verification_port.requests == [(WORK_ID, 1)]


def test_review_completed_reports_blocking_findings_and_does_not_pass(
    full_runtime, work_order_port, review_port, context
):
    review_port.outcome_map[(WORK_ID, 1)] = (
        ReviewOutcome(
            work_id=WORK_ID, round=1, lens="security", verdict="changes_required",
            blocking_findings=2,
        ),
    )
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION + ("review",))
    result = full_runtime.transition(context, WORK_ID, "verification", actor="reviewer")

    completed = result.events[0]
    assert completed.blocking_findings == 2
    assert completed.passed is False


def test_entering_ready_emits_verification_completed(
    full_runtime, work_order_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION + ("review", "verification"))
    result = full_runtime.transition(context, WORK_ID, "ready", actor="verifier")

    assert result.event_types == (VerificationCompleted.EVENT_TYPE,)
    assert result.events[0].status == "complete"


def test_a_second_implementation_round_increments_from_the_log(
    full_runtime, work_order_port, context
):
    """Round is derived from the log, not counted in memory."""
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION + ("review",))
    result = full_runtime.transition(context, WORK_ID, "implementation", actor="reviewer")

    assert result.events[0].round == 2


def test_every_transition_that_emits_records_to_the_log(
    full_runtime, work_order_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION + ("review", "verification", "ready"))

    recorded = full_runtime.log.for_work_order(WORK_ID)
    assert [e.event_type.rsplit(".", 1)[-1] for e in recorded] == [
        "implementation_started",
        "implementation_completed",
        "review_requested",
        "review_completed",
        "verification_requested",
        "verification_completed",
    ]


def test_the_log_stays_intact_across_a_full_lifecycle(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(
        full_runtime, context, WORK_ID,
        TO_IMPLEMENTATION + ("review", "verification", "ready", "merged", "closed"),
    )
    assert full_runtime.log.verify() == ()


# ----------------------------------------------------------------------
# Policy
# ----------------------------------------------------------------------


def test_policy_refuses_a_governed_work_order_with_no_digest(
    full_runtime, work_order_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED, digest=None)
    with pytest.raises(PolicyRefused) as caught:
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")
    assert any(f.check == "digest-binds" for f in caught.value.failures)


def test_policy_refuses_a_superseded_work_order(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED, superseded_by="other")
    with pytest.raises(PolicyRefused) as caught:
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")
    assert any(f.check == "not-superseded" for f in caught.value.failures)


def test_policy_refuses_review_on_a_contradicted_assumption(
    full_runtime, work_order_port, context
):
    """The correct outcome is a PREMISE_FALSE rejection, not a review."""
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED, blocking_assumptions=1)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION)

    with pytest.raises(PolicyRefused) as caught:
        full_runtime.transition(context, WORK_ID, "review", actor="x")
    assert any(f.check == "assumptions-hold" for f in caught.value.failures)


def test_policy_refuses_review_on_an_unchecked_assumption(
    full_runtime, work_order_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED, unresolved_assumptions=2)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION)
    with pytest.raises(PolicyRefused) as caught:
        full_runtime.transition(context, WORK_ID, "review", actor="x")
    assert any(f.check == "assumptions-checked" for f in caught.value.failures)


def test_policy_returns_every_failure_not_just_the_first(
    full_runtime, work_order_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED, digest=None, superseded_by="other")
    with pytest.raises(PolicyRefused) as caught:
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")
    assert len(caught.value.failures) == 2


def test_a_policy_refusal_does_not_move_the_work_order(
    full_runtime, work_order_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED, digest=None)
    with pytest.raises(PolicyRefused):
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")
    assert work_order_port.transition_calls == []
    assert len(full_runtime.log) == 0


def test_advisory_findings_do_not_refuse(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED, dependencies=("dep-1",))
    result = full_runtime.transition(context, WORK_ID, "assigned", actor="x")
    assert result.snapshot.phase is WorkOrderPhase.ASSIGNED
    assert any(f.check == "dependencies-declared" for f in result.advisory)


def test_a_stale_constraint_refuses_the_ready_gate(work_order_port, context):
    """A constraint whose rule was deleted since approval is prose."""
    runtime = EngineeringRuntime(
        Collaborators(work_order=work_order_port), policy=default_policy()
    )
    work_order_port.add(WORK_ID, WorkOrderPhase.VERIFICATION, constraints=("NOT-A-REAL-RULE",))
    with pytest.raises(PolicyRefused) as caught:
        runtime.transition(context, WORK_ID, "ready", actor="verifier")
    assert any(f.check == "constraints-enforceable" for f in caught.value.failures)


def test_a_live_constraint_passes_the_ready_gate(work_order_port, context):
    runtime = EngineeringRuntime(
        Collaborators(work_order=work_order_port), policy=default_policy()
    )
    work_order_port.add(WORK_ID, WorkOrderPhase.VERIFICATION, constraints=("I6",))
    result = runtime.transition(context, WORK_ID, "ready", actor="verifier")
    assert result.snapshot.phase is WorkOrderPhase.READY


# ----------------------------------------------------------------------
# Rollback
# ----------------------------------------------------------------------


def test_a_failing_port_rolls_the_transition_back(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    work_order_port.fail_on = WorkOrderPhase.ASSIGNED

    with pytest.raises(TransitionRolledBack) as caught:
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")

    assert isinstance(caught.value.cause, RuntimeError)
    assert caught.value.transition == "approved -> assigned"


def test_a_rollback_leaves_the_phase_unchanged(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    work_order_port.fail_on = WorkOrderPhase.ASSIGNED

    with pytest.raises(TransitionRolledBack):
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")

    assert work_order_port.snapshot(context, WORK_ID).phase is WorkOrderPhase.APPROVED


def test_a_rollback_after_a_collaborator_started_is_recorded(
    full_runtime, work_order_port, review_port, context
):
    """The collaborator was told to start work that will not happen. Say so."""
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION)
    before = len(full_runtime.log)

    work_order_port.fail_on = WorkOrderPhase.REVIEW
    with pytest.raises(TransitionRolledBack):
        full_runtime.transition(context, WORK_ID, "review", actor="x")

    assert review_port.requests, "the collaborator was never asked to start"
    assert len(full_runtime.log) > before, "the rollback left no trace"


def test_the_original_cause_survives_the_rollback(full_runtime, work_order_port, context):
    """A rollback whose reason is lost is the least actionable message possible."""
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    work_order_port.fail_on = WorkOrderPhase.ASSIGNED

    with pytest.raises(TransitionRolledBack) as caught:
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")

    assert "refuses to move to assigned" in str(caught.value.cause)
    assert caught.value.__cause__ is caught.value.cause


def test_a_port_reporting_the_wrong_phase_is_a_concurrent_modification(
    full_runtime, work_order_port, context
):
    """Should be impossible under the lock, which is why it matters if it happens."""
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)

    original = work_order_port.transition

    def lying(ctx, wid, to_phase, actor):
        original(ctx, wid, to_phase, actor)
        return work_order_port.add(wid, WorkOrderPhase.BLOCKED)

    work_order_port.transition = lying
    with pytest.raises(ConcurrentModification):
        full_runtime.transition(context, WORK_ID, "assigned", actor="x")


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_only_one_of_two_racing_transitions_succeeds(
    full_runtime, work_order_port, context
):
    """The lock serialises them; the machine refuses the loser's now-illegal move."""
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    outcomes: list = []
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        try:
            full_runtime.transition(context, WORK_ID, "assigned", actor="racer")
            outcomes.append("ok")
        except Exception as exc:  # noqa: BLE001
            outcomes.append(type(exc).__name__)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("ok") == 1, outcomes
    assert "IllegalTransition" in outcomes


def test_a_stale_precondition_is_refused_by_the_runtime(
    full_runtime, work_order_port, context
):
    work_order_port.add(WORK_ID, WorkOrderPhase.ASSIGNED)
    with pytest.raises(PreconditionFailed):
        full_runtime.transition(
            context, WORK_ID, "spec_tests", actor="x", expected_phase="approved"
        )


def test_a_matching_precondition_proceeds(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    result = full_runtime.transition(
        context, WORK_ID, "assigned", actor="x", expected_phase="approved"
    )
    assert result.snapshot.phase is WorkOrderPhase.ASSIGNED


def test_concurrent_transitions_on_distinct_work_orders_do_not_block_each_other(
    full_runtime, work_order_port, context
):
    ids = [f"01ARZ3NDEKTSV4RRFFQ69G5F{i:02X}" for i in range(10)]
    for work_id in ids:
        work_order_port.add(work_id, WorkOrderPhase.APPROVED)

    errors: list = []

    def advance(work_id: str) -> None:
        try:
            full_runtime.transition(context, work_id, "assigned", actor="x")
        except Exception as exc:  # noqa: BLE001
            errors.append((work_id, exc))

    threads = [threading.Thread(target=advance, args=(w,)) for w in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert full_runtime.log.verify() == ()


# ----------------------------------------------------------------------
# Rejection routing
# ----------------------------------------------------------------------


def test_a_rejection_goes_through_the_same_validator(
    full_runtime, work_order_port, context
):
    """Rejection is not an escape hatch from the machine."""
    work_order_port.add(WORK_ID, WorkOrderPhase.ASSIGNED)
    with pytest.raises(IllegalTransition):
        full_runtime.reject(
            context, WORK_ID, rejection_type="premise_false",
            detail="grep returned nothing", raised_by="implementer",
        )


def test_a_rejection_from_a_permitted_phase_routes(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, ("assigned", "spec_tests"))

    result = full_runtime.reject(
        context, WORK_ID, rejection_type="premise_false",
        detail="grep tenant_id backend/database/models/ returned nothing",
        raised_by="implementer",
    )
    assert result.snapshot.phase is WorkOrderPhase.REJECTED
    assert work_order_port.reject_calls[0][1] == "premise_false"


# ----------------------------------------------------------------------
# Replay
# ----------------------------------------------------------------------


def test_replay_returns_the_recorded_sequence(full_runtime, work_order_port, context):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION + ("review",))

    replayed = full_runtime.replay(WORK_ID)
    assert [e.sequence for e in replayed] == sorted(e.sequence for e in replayed)
    assert len(replayed) == 3


def test_replay_of_an_unknown_work_order_is_empty(full_runtime):
    assert full_runtime.replay("01ARZ3NDEKTSV4RRFFQ69G5FZZ") == ()


def test_round_and_attempt_are_recoverable_from_the_log_alone(
    full_runtime, work_order_port, context
):
    """A fresh runtime over the same log must agree about where things are."""
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION + ("review", "implementation"))

    rebuilt = EngineeringRuntime(
        Collaborators(work_order=work_order_port), log=full_runtime.log
    )
    assert rebuilt.round_number(WORK_ID) == full_runtime.round_number(WORK_ID)
    assert rebuilt.attempt_number(WORK_ID) == full_runtime.attempt_number(WORK_ID)


# ----------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------


def test_state_separates_legal_from_reachable(bare_runtime, work_order_port, context):
    """'The Constitution forbids this' and 'nothing is listening' differ."""
    from backend.contexts.engineering import EngineeringRuntimeQueries

    work_order_port.add(WORK_ID, WorkOrderPhase.ASSIGNED)
    state = EngineeringRuntimeQueries(bare_runtime).state(
        context, GetRuntimeState(work_id=WORK_ID)
    )
    assert state.legal_next == ("spec_tests",)
    assert state.reachable_next == ()
    assert state.blocked_next == ("spec_tests",)


def test_state_reports_the_round_and_attempt_in_flight(
    full_runtime, work_order_port, context, queries
):
    """Current, not next. One completed implementation round *is* round 1.

    The distinction is not pedantry: reporting the next round would make a
    WorkOrder in its first review look like it was on its second attempt at
    everything.
    """
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(full_runtime, context, WORK_ID, TO_IMPLEMENTATION + ("review", "verification"))

    state = queries.state(context, GetRuntimeState(work_id=WORK_ID))
    assert state.round == 1
    assert state.attempt == 1
    assert full_runtime.next_round(WORK_ID) == 2
    assert full_runtime.next_attempt(WORK_ID) == 2


def test_a_second_round_reports_as_round_two(full_runtime, work_order_port, context, queries):
    work_order_port.add(WORK_ID, WorkOrderPhase.APPROVED)
    drive(
        full_runtime, context, WORK_ID,
        TO_IMPLEMENTATION + ("review", "implementation"),
    )
    state = queries.state(context, GetRuntimeState(work_id=WORK_ID))
    assert state.round == 2
