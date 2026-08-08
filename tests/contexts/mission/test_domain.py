"""The Mission aggregate: creation, lifecycle, checkpoints, the gate, and archival.

The rule this file exists to pin is the **verification gate**: a mission cannot
be reported complete over work nobody verified. It is asserted from both
directions -- through the transition and on a mission assembled from storage --
because the second path bypasses the first.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.mission import MissionState
from backend.contexts.mission import (
    ARTIFACT_KIND,
    CheckpointId,
    DigestMismatch,
    DigestNotComputed,
    ExecutionAlreadyOpen,
    ExecutionOutcome,
    GOVERNED_FIELDS,
    IllegalExecutionTransition,
    IllegalStatusTransition,
    Mission,
    MissionArchivedError,
    MissionKind,
    MissionPriority,
    MissionStatus,
    NoOpenExecution,
    NoPlanRecorded,
    PreconditionsUnmet,
    UnknownCheckpoint,
    VerificationNotReached,
    draft_mission,
    plan_ref,
    precondition,
)
from backend.platform.context import ExecutionContext

CONTEXT = ExecutionContext.platform_internal(
    reason="mission-domain-tests", component="tests", source="pytest"
)

#: The S4 path from a fresh run to a verified conclusion. Constitution S4 forbids
#: shortcuts, so every test that needs a verified mission walks this.
TO_CONCLUDED = (
    MissionState.INTERPRETED,
    MissionState.GATHERING,
    MissionState.REASONING,
    MissionState.PLANNED,
    MissionState.EXECUTING,
    MissionState.VERIFYING,
    MissionState.CONCLUDED,
)


def _drafted(**overrides) -> Mission:
    fields = dict(
        stated_goal="Investigate sustained high CPU on prod-api",
        requested_by=CONTEXT.security_context,
        title="High CPU incident",
        kind=MissionKind.INVESTIGATE,
        priority=MissionPriority.URGENT,
        target="prod-api",
    )
    fields.update(overrides)
    return draft_mission(**fields)


def _ready(**overrides) -> Mission:
    mission = _drafted(**overrides).record_plan(
        plan_ref("PLAN-1"), reason="planner produced a plan", actor="planner"
    )
    mission = mission.transition(
        MissionStatus.PLANNED, reason="plan recorded", actor="orchestrator"
    )
    return mission.transition(
        MissionStatus.READY, reason="nothing outstanding", actor="orchestrator"
    )


def _running(**overrides) -> Mission:
    mission = _ready(**overrides).open_execution(
        reason="starting attempt 1", actor="orchestrator"
    )
    return mission.transition(
        MissionStatus.RUNNING, reason="execution opened", actor="orchestrator"
    )


def _verified(**overrides) -> Mission:
    mission = _running(**overrides)
    for state in TO_CONCLUDED:
        mission = mission.advance_execution(
            state, reason=f"moved to {state.value}", actor="execution"
        )
    return mission


# ----------------------------------------------------------------------
# Creation
# ----------------------------------------------------------------------


def test_a_mission_preserves_the_requesters_own_words() -> None:
    """Storing only an interpretation makes it impossible to audit whether the
    mission solved the problem it was actually asked to solve."""
    mission = _drafted()
    assert mission.stated_goal == "Investigate sustained high CPU on prod-api"
    assert mission.status is MissionStatus.DRAFT
    assert mission.execution_state is MissionState.RECEIVED


def test_a_mission_carries_a_tenant_scoped_security_context() -> None:
    """BC-9: every cross-context message carries one. Non-negotiable."""
    mission = _drafted()
    assert mission.intent.requested_by.scope is not None
    assert mission.intent.requested_by.principal is not None


def test_a_mission_without_a_goal_is_refused() -> None:
    with pytest.raises(ContractViolation):
        _drafted(stated_goal="   ")


def test_a_mission_without_a_title_is_refused() -> None:
    with pytest.raises(ContractViolation):
        _drafted(title="  ")


def test_a_fresh_mission_has_an_empty_timeline_that_agrees_with_it() -> None:
    mission = _drafted()
    assert mission.timeline.is_empty
    assert mission.timeline_agrees()


# ----------------------------------------------------------------------
# Scoping: plan and preconditions
# ----------------------------------------------------------------------


def test_planning_without_a_plan_reference_is_refused() -> None:
    """Mission Runtime does not plan, so it records where the plan lives."""
    with pytest.raises(NoPlanRecorded):
        _drafted().transition(
            MissionStatus.PLANNED, reason="planned", actor="orchestrator"
        )


def test_recording_a_plan_leaves_a_reference_not_a_plan() -> None:
    mission = _drafted().record_plan(
        plan_ref("PLAN-7", produced_by="planner-v2"), reason="planned", actor="planner"
    )
    assert str(mission.plan_ref) == "PLAN-7"
    assert not hasattr(mission.plan_ref, "steps")


def test_a_plan_reference_must_name_a_plan() -> None:
    with pytest.raises(ContractViolation):
        plan_ref("  ")


def test_readiness_is_refused_while_a_precondition_is_outstanding() -> None:
    mission = _drafted(kind=MissionKind.MONITOR).declare_precondition(
        precondition("access.prod-cluster", "read access to the cluster")
    )
    mission = mission.record_plan(plan_ref("PLAN-1"), reason="planned", actor="planner")
    mission = mission.transition(
        MissionStatus.PLANNED, reason="planned", actor="orchestrator"
    )
    with pytest.raises(PreconditionsUnmet) as caught:
        mission.transition(MissionStatus.READY, reason="ready", actor="orchestrator")
    assert caught.value.outstanding == ("access.prod-cluster",)


def test_satisfying_a_precondition_names_who_cleared_it() -> None:
    mission = _drafted().declare_precondition(precondition("access.prod-cluster"))
    cleared = mission.satisfy_precondition("access.prod-cluster", by="sre-oncall")
    assert cleared.outstanding_preconditions == ()
    assert cleared.preconditions[0].satisfied_by == "sre-oncall"


def test_a_precondition_cannot_be_satisfied_twice() -> None:
    mission = _drafted().declare_precondition(precondition("k"))
    once = mission.satisfy_precondition("k", by="a")
    with pytest.raises(ContractViolation):
        once.satisfy_precondition("k", by="b")


def test_an_unknown_precondition_cannot_be_satisfied() -> None:
    with pytest.raises(ContractViolation):
        _drafted().satisfy_precondition("nope", by="a")


def test_a_precondition_cannot_be_declared_twice() -> None:
    mission = _drafted().declare_precondition(precondition("k"))
    with pytest.raises(ContractViolation):
        mission.declare_precondition(precondition("k"))


def test_a_satisfied_precondition_must_name_somebody() -> None:
    from backend.contexts.mission import Precondition

    with pytest.raises(ContractViolation):
        Precondition(key="k", satisfied=True)


# ----------------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------------


def test_an_illegal_transition_names_what_is_permitted_instead() -> None:
    with pytest.raises(IllegalStatusTransition) as caught:
        _drafted().transition(
            MissionStatus.RUNNING, reason="go", actor="orchestrator"
        )
    assert set(caught.value.permitted) == {"planned", "cancelled"}


def test_every_transition_lands_on_the_timeline_with_its_reason() -> None:
    mission = _ready()
    reasons = [e.reason for e in mission.timeline.status_transitions]
    assert reasons == ["plan recorded", "nothing outstanding"]


def test_a_transition_without_a_reason_is_refused() -> None:
    with pytest.raises(ContractViolation):
        _drafted().record_plan(plan_ref("P"), reason="  ", actor="planner")


def test_the_timeline_always_agrees_with_the_aggregate() -> None:
    """The check that makes the timeline authoritative rather than decorative."""
    assert _verified().timeline_agrees()


# ----------------------------------------------------------------------
# Executions
# ----------------------------------------------------------------------


def test_a_second_concurrent_execution_is_refused() -> None:
    """Two runs of one objective produce two answers."""
    mission = _running()
    with pytest.raises(ExecutionAlreadyOpen):
        mission.open_execution(reason="again", actor="orchestrator")


def test_advancing_without_an_open_execution_is_refused() -> None:
    with pytest.raises(NoOpenExecution):
        _ready().advance_execution(
            MissionState.INTERPRETED, reason="go", actor="execution"
        )


def test_the_execution_state_follows_constitution_s4() -> None:
    """The table is not this context's to redefine, so the contract enforces it."""
    mission = _running()
    with pytest.raises(IllegalExecutionTransition) as caught:
        mission.advance_execution(
            MissionState.CONCLUDED, reason="skip ahead", actor="execution"
        )
    assert caught.value.source == "received"
    assert caught.value.target == "concluded"


def test_execution_never_reaches_concluded_without_verifying() -> None:
    """Constitution S4's central rule, exercised through the aggregate."""
    mission = _running()
    for state in (
        MissionState.INTERPRETED,
        MissionState.GATHERING,
        MissionState.REASONING,
        MissionState.PLANNED,
        MissionState.EXECUTING,
    ):
        mission = mission.advance_execution(state, reason="onward", actor="execution")

    with pytest.raises(IllegalExecutionTransition):
        mission.advance_execution(
            MissionState.CONCLUDED, reason="declare victory", actor="execution"
        )

    verified = mission.advance_execution(
        MissionState.VERIFYING, reason="verifying", actor="verification"
    ).advance_execution(MissionState.CONCLUDED, reason="verified", actor="verification")
    assert verified.is_verified


def test_closing_an_execution_as_succeeded_requires_a_concluded_state() -> None:
    mission = _running()
    with pytest.raises(ContractViolation):
        mission.close_execution(
            ExecutionOutcome.SUCCEEDED, reason="done", actor="execution"
        )


def test_attempts_are_numbered_and_countable() -> None:
    mission = _running()
    mission = mission.close_execution(
        ExecutionOutcome.SUSPENDED, reason="pausing", actor="operator"
    )
    mission = mission.transition(
        MissionStatus.PAUSED, reason="pausing", actor="operator"
    )
    mission = mission.open_execution(reason="resuming", actor="operator")
    assert [e.attempt for e in mission.executions] == [1, 2]
    assert mission.current_execution.attempt == 2


def test_only_a_suspended_run_is_resumable() -> None:
    assert ExecutionOutcome.SUSPENDED.is_resumable
    for other in (
        ExecutionOutcome.FAILED,
        ExecutionOutcome.ABANDONED,
        ExecutionOutcome.SUCCEEDED,
    ):
        assert not other.is_resumable


# ----------------------------------------------------------------------
# The verification gate
# ----------------------------------------------------------------------


def test_completion_is_refused_while_the_execution_is_unverified() -> None:
    """The rule this context exists to make unbreakable."""
    mission = _running()
    for state in (
        MissionState.INTERPRETED,
        MissionState.GATHERING,
        MissionState.REASONING,
        MissionState.PLANNED,
        MissionState.EXECUTING,
    ):
        mission = mission.advance_execution(state, reason="onward", actor="execution")

    with pytest.raises(VerificationNotReached) as caught:
        mission.transition(
            MissionStatus.COMPLETED, reason="looks done", actor="orchestrator"
        )
    assert caught.value.execution_state == "executing"


def test_completion_is_permitted_once_verified() -> None:
    completed = _verified().transition(
        MissionStatus.COMPLETED, reason="objective achieved", actor="orchestrator"
    )
    assert completed.status is MissionStatus.COMPLETED


def test_an_unverified_completion_cannot_be_assembled_from_storage() -> None:
    """The gate holds for a mission built directly, which is the path replay takes."""
    completed = _verified().transition(
        MissionStatus.COMPLETED, reason="done", actor="orchestrator"
    )
    with pytest.raises(VerificationNotReached):
        dataclasses.replace(completed, execution_state=MissionState.EXECUTING)


# ----------------------------------------------------------------------
# Checkpoints
# ----------------------------------------------------------------------


def test_a_checkpoint_is_sealed_with_a_digest() -> None:
    mission = _running().advance_execution(
        MissionState.INTERPRETED, reason="interpreted", actor="execution"
    )
    mission = mission.record_checkpoint("intent understood", actor="execution")
    checkpoint = mission.latest_checkpoint
    assert checkpoint.digest
    checkpoint.verify_digest()


def test_a_checkpoint_records_the_state_it_was_taken_at() -> None:
    """Resuming into a different phase is how a mission silently redoes work."""
    mission = _running()
    for state in (MissionState.INTERPRETED, MissionState.GATHERING):
        mission = mission.advance_execution(state, reason="onward", actor="execution")
    mission = mission.record_checkpoint("evidence gathered", actor="execution")
    assert mission.latest_checkpoint.execution_state is MissionState.GATHERING


def test_checkpoints_are_only_taken_while_running() -> None:
    """A checkpoint records progress, so there has to be progress to record."""
    with pytest.raises(ContractViolation):
        _ready().record_checkpoint("nothing yet", actor="x")


def test_a_checkpoint_cannot_be_taken_at_a_terminal_execution_state() -> None:
    from backend.contexts.mission import MissionCheckpoint

    with pytest.raises(ContractViolation):
        MissionCheckpoint.create(
            sequence=1,
            label="too late",
            execution_state=MissionState.CONCLUDED,
            execution_id="EX-1",
        )


def test_an_unlabelled_checkpoint_is_refused() -> None:
    with pytest.raises(ContractViolation):
        _running().record_checkpoint("   ", actor="x")


def test_checkpoints_are_sequenced() -> None:
    mission = _running().advance_execution(
        MissionState.INTERPRETED, reason="i", actor="e"
    )
    mission = mission.record_checkpoint("first", actor="e")
    mission = mission.record_checkpoint("second", actor="e")
    assert [c.sequence for c in mission.checkpoints] == [1, 2]


def test_a_checkpoint_holds_a_reference_not_the_payload() -> None:
    """A runtime that held the gathered evidence would be a knowledge store."""
    mission = _running().advance_execution(
        MissionState.INTERPRETED, reason="i", actor="e"
    )
    mission = mission.record_checkpoint(
        "evidence", actor="e", payload_ref="s3://bucket/evidence.json"
    )
    checkpoint = mission.latest_checkpoint
    assert checkpoint.payload_ref == "s3://bucket/evidence.json"
    assert not hasattr(checkpoint, "payload")


def test_tampering_with_a_checkpoint_is_caught() -> None:
    mission = _running().advance_execution(
        MissionState.INTERPRETED, reason="i", actor="e"
    )
    checkpoint = mission.record_checkpoint("evidence", actor="e").latest_checkpoint
    tampered = dataclasses.replace(checkpoint, label="something else")
    with pytest.raises(DigestMismatch):
        tampered.verify_digest()


# ----------------------------------------------------------------------
# Resuming
# ----------------------------------------------------------------------


def test_resuming_from_a_checkpoint_restores_the_state_it_captured() -> None:
    """Without this, checkpoints are decorative."""
    mission = _running()
    for state in (
        MissionState.INTERPRETED,
        MissionState.GATHERING,
        MissionState.REASONING,
        MissionState.PLANNED,
        MissionState.EXECUTING,
    ):
        mission = mission.advance_execution(state, reason="onward", actor="execution")
    mission = mission.record_checkpoint("mid-execution", actor="execution")
    checkpoint_id = mission.latest_checkpoint.checkpoint_id

    mission = mission.close_execution(
        ExecutionOutcome.SUSPENDED, reason="pausing", actor="operator"
    ).transition(MissionStatus.PAUSED, reason="pausing", actor="operator")

    resumed = mission.open_execution(
        reason="resuming", actor="operator", resumed_from=checkpoint_id
    )
    assert resumed.execution_state is MissionState.EXECUTING
    assert resumed.current_execution.state is MissionState.EXECUTING
    assert resumed.current_execution.resumed_from_checkpoint == str(checkpoint_id)
    assert resumed.timeline_agrees()


def test_resuming_without_a_checkpoint_restarts_the_run() -> None:
    """Honest rather than convenient: a run with nothing to resume from starts over."""
    mission = _running().advance_execution(
        MissionState.INTERPRETED, reason="i", actor="e"
    )
    mission = mission.close_execution(
        ExecutionOutcome.SUSPENDED, reason="pausing", actor="operator"
    ).transition(MissionStatus.PAUSED, reason="pausing", actor="operator")

    resumed = mission.open_execution(reason="resuming", actor="operator")
    assert resumed.execution_state is MissionState.RECEIVED
    assert resumed.timeline_agrees()


def test_resuming_from_an_unknown_checkpoint_is_refused() -> None:
    mission = _running().close_execution(
        ExecutionOutcome.SUSPENDED, reason="p", actor="o"
    ).transition(MissionStatus.PAUSED, reason="p", actor="o")
    with pytest.raises(UnknownCheckpoint):
        mission.open_execution(
            reason="resuming", actor="o", resumed_from=CheckpointId.new()
        )


# ----------------------------------------------------------------------
# Archival and immutability
# ----------------------------------------------------------------------


def _completed() -> Mission:
    return _verified().transition(
        MissionStatus.COMPLETED, reason="objective achieved", actor="orchestrator"
    )


def test_archiving_seals_the_mission_and_binds_a_digest() -> None:
    archived = _completed().archive(reason="sealed", actor="operator")
    assert archived.status is MissionStatus.ARCHIVED
    assert archived.digest
    archived.verify_digest()


def test_archiving_a_live_mission_is_refused() -> None:
    with pytest.raises(IllegalStatusTransition):
        _running().archive(reason="too early", actor="operator")


_MUTATIONS = {
    "transition": lambda m: m.transition(
        MissionStatus.RUNNING, reason="again", actor="x"
    ),
    "record_plan": lambda m: m.record_plan(plan_ref("P-2"), reason="r", actor="x"),
    "declare_precondition": lambda m: m.declare_precondition(precondition("k")),
    "satisfy_precondition": lambda m: m.satisfy_precondition("k", by="x"),
    "open_execution": lambda m: m.open_execution(reason="r", actor="x"),
    "advance_execution": lambda m: m.advance_execution(
        MissionState.INTERPRETED, reason="r", actor="x"
    ),
    "close_execution": lambda m: m.close_execution(
        ExecutionOutcome.FAILED, reason="r", actor="x"
    ),
    "record_checkpoint": lambda m: m.record_checkpoint("late", actor="x"),
    "archive": lambda m: m.archive(reason="again", actor="x"),
}


@pytest.mark.parametrize("name", sorted(_MUTATIONS))
def test_every_mutation_refuses_on_an_archived_mission(name: str) -> None:
    archived = _completed().archive(reason="sealed", actor="operator")
    with pytest.raises(MissionArchivedError):
        _MUTATIONS[name](archived)


def test_every_mutation_is_covered_by_the_immutability_test() -> None:
    """Fails if a mutation is added to the aggregate without an entry above."""
    exposed = {
        name
        for name in dir(Mission)
        if not name.startswith("_")
        and callable(getattr(Mission, name))
        and name
        not in {
            "compute_digest",
            "digest_payload",
            "verify_digest",
            "checkpoint",
            "permitted_transitions",
            "replayed_status",
            "replayed_execution_state",
            "timeline_agrees",
            "to_dict",
            "from_dict",
            "contract_name",
            "contract_version",
        }
    }
    assert exposed == set(_MUTATIONS), exposed.symmetric_difference(set(_MUTATIONS))


# ----------------------------------------------------------------------
# Digest
# ----------------------------------------------------------------------


def test_an_archived_mission_without_a_digest_cannot_exist() -> None:
    archived = _completed().archive(reason="sealed", actor="operator")
    with pytest.raises(ContractViolation):
        dataclasses.replace(archived, digest=None)


def test_verifying_an_unarchived_mission_says_so_rather_than_passing() -> None:
    with pytest.raises(DigestNotComputed):
        _running().verify_digest()


def test_tampering_with_the_timeline_is_caught() -> None:
    archived = _completed().archive(reason="sealed", actor="operator")
    tampered = dataclasses.replace(
        archived, timeline=archived.timeline.__class__(entries=archived.timeline.entries[:-1])
    )
    with pytest.raises(DigestMismatch):
        tampered.verify_digest()


def test_the_digest_covers_the_governed_fields_and_nothing_else() -> None:
    payload = _completed().archive(reason="sealed", actor="operator").digest_payload()
    covered = set(payload) - {"__artifact__", "__canonical_form__"}
    assert covered == set(GOVERNED_FIELDS)


def test_the_artifact_kind_is_named_in_the_payload() -> None:
    payload = _completed().archive(reason="sealed", actor="operator").digest_payload()
    assert payload["__artifact__"] == ARTIFACT_KIND


def test_two_missions_do_not_collide() -> None:
    first = _completed().archive(reason="sealed", actor="operator")
    second = _completed().archive(reason="sealed", actor="operator")
    assert first.digest != second.digest


# ----------------------------------------------------------------------
# Failure and cancellation
# ----------------------------------------------------------------------


def test_a_failed_mission_must_say_why() -> None:
    mission = _running()
    with pytest.raises(ContractViolation):
        dataclasses.replace(mission, status=MissionStatus.FAILED, outcome_note=None)


def test_a_cancelled_mission_must_say_why() -> None:
    mission = _running()
    with pytest.raises(ContractViolation):
        dataclasses.replace(mission, status=MissionStatus.CANCELLED, outcome_note=None)


def test_a_mission_past_draft_must_reference_a_plan() -> None:
    mission = _ready()
    with pytest.raises(ContractViolation):
        dataclasses.replace(mission, plan_ref=None)


def test_a_cancelled_mission_needs_no_plan() -> None:
    """A mission called off before planning was never planned."""
    cancelled = _drafted().transition(
        MissionStatus.CANCELLED, reason="no longer needed", actor="operator"
    )
    assert dataclasses.replace(cancelled, outcome_note="no longer needed").plan_ref is None
