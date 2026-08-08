"""The two lifecycles, the table between them, and the timeline that records both.

The state machine is asserted as *data* rather than by walking one happy path.
A transition table checked only by the paths someone remembered to test is a
table with untested entries, and the untested entries are where the illegal move
gets through.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.mission import LEGAL_TRANSITIONS, MissionState
from backend.contexts.mission import (
    MissionStatus,
    MissionTimeline,
    MissionTimelineEntry,
    OUTCOME_STATUSES,
    STATUS_TRANSITIONS,
    TERMINAL_STATUSES,
    TimelineEntryKind,
    TimelineOutOfOrder,
    is_legal_status_transition,
    permitted_from,
    refusal_reason,
)


# ----------------------------------------------------------------------
# The operational table
# ----------------------------------------------------------------------


def test_every_status_appears_in_the_transition_table() -> None:
    """A status missing from the table is one whose legal moves are undefined."""
    assert set(STATUS_TRANSITIONS) == set(MissionStatus)


def test_every_target_in_the_table_is_a_real_status() -> None:
    for source, targets in STATUS_TRANSITIONS.items():
        for target in targets:
            assert isinstance(target, MissionStatus), (source, target)


def test_the_spec_lifecycle_is_walkable_end_to_end() -> None:
    """Draft -> Planned -> Ready -> Running -> Paused -> Running -> Completed -> Archived."""
    walk = [
        MissionStatus.DRAFT,
        MissionStatus.PLANNED,
        MissionStatus.READY,
        MissionStatus.RUNNING,
        MissionStatus.PAUSED,
        MissionStatus.RUNNING,
        MissionStatus.COMPLETED,
        MissionStatus.ARCHIVED,
    ]
    for source, target in zip(walk, walk[1:]):
        assert is_legal_status_transition(source, target), f"{source} -> {target}"


@pytest.mark.parametrize(
    "outcome", [MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED]
)
def test_every_outcome_leads_to_archived_and_nowhere_else(outcome: MissionStatus) -> None:
    assert STATUS_TRANSITIONS[outcome] == frozenset({MissionStatus.ARCHIVED})


def test_only_archived_is_terminal() -> None:
    """An outcome is not the end -- archival is where the record is sealed."""
    assert TERMINAL_STATUSES == frozenset({MissionStatus.ARCHIVED})
    assert not STATUS_TRANSITIONS[MissionStatus.ARCHIVED]
    for outcome in OUTCOME_STATUSES:
        assert outcome.is_outcome
        assert not outcome.is_terminal


def test_cancellation_is_reachable_from_every_pre_outcome_state() -> None:
    """A mission can be called off at any point before it has an answer."""
    for source in (
        MissionStatus.DRAFT,
        MissionStatus.PLANNED,
        MissionStatus.READY,
        MissionStatus.RUNNING,
        MissionStatus.PAUSED,
    ):
        assert is_legal_status_transition(source, MissionStatus.CANCELLED), source


@pytest.mark.parametrize(
    "source", [MissionStatus.DRAFT, MissionStatus.PLANNED, MissionStatus.READY]
)
def test_a_mission_that_never_ran_cannot_fail(source: MissionStatus) -> None:
    """Recording it as a failure would corrupt every failure-rate figure."""
    assert not is_legal_status_transition(source, MissionStatus.FAILED)
    assert "cancel it instead" in refusal_reason(source, MissionStatus.FAILED)


def test_failure_is_reachable_only_from_a_run() -> None:
    failing = {
        source
        for source, targets in STATUS_TRANSITIONS.items()
        if MissionStatus.FAILED in targets
    }
    assert failing == {MissionStatus.RUNNING, MissionStatus.PAUSED}


def test_running_cannot_be_reached_without_being_cleared() -> None:
    assert not is_legal_status_transition(MissionStatus.DRAFT, MissionStatus.RUNNING)
    assert not is_legal_status_transition(MissionStatus.PLANNED, MissionStatus.RUNNING)
    assert is_legal_status_transition(MissionStatus.READY, MissionStatus.RUNNING)


def test_replanning_is_permitted() -> None:
    """Forcing a new mission for a revised plan would lose the objective's history."""
    assert is_legal_status_transition(MissionStatus.PLANNED, MissionStatus.DRAFT)
    assert is_legal_status_transition(MissionStatus.READY, MissionStatus.PLANNED)


def test_an_archived_mission_goes_nowhere() -> None:
    assert permitted_from(MissionStatus.ARCHIVED) == ()

    # The named reason wins over the generic one, because reopening an archived
    # mission is a thing people attempt in good faith and deserves the argument.
    named = refusal_reason(MissionStatus.ARCHIVED, MissionStatus.RUNNING)
    assert "sealed" in named and "new mission" in named

    # Anything not named falls back to the generic terminal explanation.
    assert "terminal" in refusal_reason(MissionStatus.ARCHIVED, MissionStatus.PLANNED)


def test_a_refusal_names_what_is_permitted_instead() -> None:
    """The useful question after a refusal is never 'was that legal'."""
    reason = refusal_reason(MissionStatus.DRAFT, MissionStatus.COMPLETED)
    assert "planned" in reason and "cancelled" in reason


def test_a_legal_transition_has_no_refusal_reason() -> None:
    assert refusal_reason(MissionStatus.DRAFT, MissionStatus.PLANNED) is None


def test_only_running_accepts_checkpoints() -> None:
    for status in MissionStatus:
        assert status.accepts_checkpoints is (status is MissionStatus.RUNNING)


def test_live_means_running_or_paused() -> None:
    live = {s for s in MissionStatus if s.is_live}
    assert live == {MissionStatus.RUNNING, MissionStatus.PAUSED}


# ----------------------------------------------------------------------
# The two lifecycles are genuinely different
# ----------------------------------------------------------------------


def test_the_operational_and_execution_vocabularies_are_distinct() -> None:
    """ADR-025's premise, asserted rather than described.

    If these ever became the same set of names, the two-layer design would have
    collapsed into one machine wearing two hats -- and whichever rule the other
    machine was carrying would have been quietly dropped.
    """
    operational = {s.value for s in MissionStatus}
    execution = {s.value for s in MissionState}
    assert operational != execution
    # 'planned' and 'failed' are the only names both use, and they mean
    # different things: one is "a plan exists", the other is "this run failed".
    assert operational & execution == {"planned", "failed"}


def test_constitution_s4_still_forbids_concluding_without_verifying() -> None:
    """The rule the operational gate exists to protect.

    If S4's table ever permitted EXECUTING -> CONCLUDED directly, the mission
    gate would still pass but would no longer mean verification ran. This fails
    first, and names why.
    """
    assert MissionState.CONCLUDED not in LEGAL_TRANSITIONS[MissionState.EXECUTING]
    assert MissionState.CONCLUDED in LEGAL_TRANSITIONS[MissionState.VERIFYING]


# ----------------------------------------------------------------------
# Timeline
# ----------------------------------------------------------------------


def _status_entry(sequence: int, source, target, reason="because") -> MissionTimelineEntry:
    return MissionTimelineEntry(
        sequence=sequence,
        kind=TimelineEntryKind.STATUS,
        reason=reason,
        actor="tester",
        from_status=source,
        to_status=target,
    )


def test_a_timeline_entry_must_record_why() -> None:
    """Constitution S4: no state is exited without recording why."""
    with pytest.raises(ContractViolation):
        _status_entry(1, MissionStatus.DRAFT, MissionStatus.PLANNED, reason="  ")


def test_a_timeline_entry_must_name_who() -> None:
    with pytest.raises(ContractViolation):
        MissionTimelineEntry(
            sequence=1,
            kind=TimelineEntryKind.NOTE,
            reason="something",
            actor="   ",
        )


def test_a_status_entry_must_record_a_real_movement() -> None:
    with pytest.raises(ContractViolation):
        _status_entry(1, MissionStatus.DRAFT, MissionStatus.DRAFT)


def test_a_status_entry_must_record_where_it_came_from() -> None:
    with pytest.raises(ContractViolation):
        MissionTimelineEntry(
            sequence=1,
            kind=TimelineEntryKind.STATUS,
            reason="moved",
            actor="tester",
            to_status=MissionStatus.PLANNED,
        )


def test_a_checkpoint_entry_must_name_its_checkpoint() -> None:
    with pytest.raises(ContractViolation):
        MissionTimelineEntry(
            sequence=1, kind=TimelineEntryKind.CHECKPOINT, reason="reached", actor="x"
        )


def test_the_timeline_is_gapless() -> None:
    """A gap makes replay ambiguous, and an ambiguous audit trail is not one."""
    timeline = MissionTimeline().append(
        _status_entry(1, MissionStatus.DRAFT, MissionStatus.PLANNED)
    )
    with pytest.raises(TimelineOutOfOrder):
        timeline.append(_status_entry(3, MissionStatus.PLANNED, MissionStatus.READY))


def test_the_timeline_refuses_a_repeated_sequence() -> None:
    timeline = MissionTimeline().append(
        _status_entry(1, MissionStatus.DRAFT, MissionStatus.PLANNED)
    )
    with pytest.raises(TimelineOutOfOrder):
        timeline.append(_status_entry(1, MissionStatus.PLANNED, MissionStatus.READY))


def test_a_timeline_constructed_out_of_order_is_refused() -> None:
    with pytest.raises(TimelineOutOfOrder):
        MissionTimeline(
            entries=(
                _status_entry(1, MissionStatus.DRAFT, MissionStatus.PLANNED),
                _status_entry(3, MissionStatus.PLANNED, MissionStatus.READY),
            )
        )


def test_appending_is_the_only_way_forward() -> None:
    timeline = MissionTimeline()
    assert timeline.is_empty and timeline.next_sequence == 1
    grown = timeline.append(_status_entry(1, MissionStatus.DRAFT, MissionStatus.PLANNED))
    assert len(grown) == 1
    assert len(timeline) == 0, "append must not mutate the original"


def test_replay_rebuilds_the_status_from_the_record() -> None:
    timeline = (
        MissionTimeline()
        .append(_status_entry(1, MissionStatus.DRAFT, MissionStatus.PLANNED))
        .append(_status_entry(2, MissionStatus.PLANNED, MissionStatus.READY))
        .append(_status_entry(3, MissionStatus.READY, MissionStatus.RUNNING))
    )
    assert timeline.replay_status() is MissionStatus.RUNNING


def test_replay_of_an_empty_timeline_is_the_initial_status() -> None:
    assert MissionTimeline().replay_status() is MissionStatus.DRAFT


def test_replay_rebuilds_the_execution_state_too() -> None:
    timeline = MissionTimeline().append(
        MissionTimelineEntry(
            sequence=1,
            kind=TimelineEntryKind.EXECUTION,
            reason="interpreted",
            actor="execution",
            from_execution_state=MissionState.RECEIVED,
            to_execution_state=MissionState.INTERPRETED,
        )
    )
    assert timeline.replay_execution_state() is MissionState.INTERPRETED


def test_notes_and_checkpoints_do_not_move_the_status() -> None:
    timeline = (
        MissionTimeline()
        .append(_status_entry(1, MissionStatus.DRAFT, MissionStatus.PLANNED))
        .append(
            MissionTimelineEntry(
                sequence=2,
                kind=TimelineEntryKind.CHECKPOINT,
                reason="reached",
                actor="x",
                checkpoint_id="CP-1",
            )
        )
    )
    assert timeline.replay_status() is MissionStatus.PLANNED


def test_entries_can_be_filtered_by_kind() -> None:
    timeline = (
        MissionTimeline()
        .append(_status_entry(1, MissionStatus.DRAFT, MissionStatus.PLANNED))
        .append(
            MissionTimelineEntry(
                sequence=2, kind=TimelineEntryKind.NOTE, reason="noted", actor="x"
            )
        )
    )
    assert len(timeline.status_transitions) == 1
    assert len(timeline.of_kind(TimelineEntryKind.NOTE)) == 1
    assert timeline.last.kind is TimelineEntryKind.NOTE


def test_only_transitions_move_the_mission() -> None:
    assert TimelineEntryKind.STATUS.moves_the_mission
    assert TimelineEntryKind.EXECUTION.moves_the_mission
    assert not TimelineEntryKind.NOTE.moves_the_mission
    assert not TimelineEntryKind.CHECKPOINT.moves_the_mission
