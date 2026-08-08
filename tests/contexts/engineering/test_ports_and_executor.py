"""Ports, phase vocabulary, and the transition validator.

The first test is the most important in this PR. The runtime keeps its own copy
of the lifecycle so it never imports the WorkOrder context; that decoupling is
only safe if the two copies provably agree. This turns a duplication risk into a
checked invariant — and it is the one place where importing the other context is
correct, because comparing them *is* the test.
"""

from __future__ import annotations

import pytest

from backend.contexts.engineering import (
    PHASE_TRANSITIONS,
    TERMINAL_PHASES,
    GOVERNED_PHASES,
    IllegalTransition,
    PhaseUnknown,
    PreconditionFailed,
    TransitionValidator,
    WorkOrderPhase,
    WorkOrderSnapshot,
    coerce_phase,
)

# The one deliberate cross-context import in this package's tests. Comparing the
# two vocabularies is the entire purpose.
from backend.contexts.workorder.domain.states import (
    ALLOWED as WORKORDER_ALLOWED,
    GOVERNED_STATES,
    TERMINAL_STATES,
    WorkOrderState,
)


def _snapshot(phase: WorkOrderPhase, **overrides) -> WorkOrderSnapshot:
    fields = dict(
        work_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        version=1,
        phase=phase,
        digest="digest-abc",
        priority="p1",
        intent="a stated outcome",
    )
    fields.update(overrides)
    return WorkOrderSnapshot(**fields)


# ----------------------------------------------------------------------
# Drift
# ----------------------------------------------------------------------


def test_phase_vocabulary_matches_the_workorder_context():
    """Same states, same names. If this fails the two copies have diverged."""
    assert {p.value for p in WorkOrderPhase} == {s.value for s in WorkOrderState}


def test_transition_table_matches_the_workorder_context():
    """Every edge, in both directions of comparison."""
    runtime_edges = {
        (source.value, target.value)
        for source, targets in PHASE_TRANSITIONS.items()
        for target in targets
    }
    workorder_edges = {
        (source.value, target.value)
        for source, targets in WORKORDER_ALLOWED.items()
        for target in targets
    }
    assert runtime_edges == workorder_edges


def test_terminal_phases_match():
    assert {p.value for p in TERMINAL_PHASES} == {s.value for s in TERMINAL_STATES}


def test_governed_phases_match():
    assert {p.value for p in GOVERNED_PHASES} == {s.value for s in GOVERNED_STATES}


# ----------------------------------------------------------------------
# Coercion
# ----------------------------------------------------------------------


def test_coerce_accepts_a_phase_and_a_string():
    assert coerce_phase(WorkOrderPhase.REVIEW) is WorkOrderPhase.REVIEW
    assert coerce_phase("review") is WorkOrderPhase.REVIEW


@pytest.mark.parametrize("bad", ["shipped", "", None, 7, object()])
def test_coerce_refuses_anything_else(bad):
    with pytest.raises(PhaseUnknown):
        coerce_phase(bad)


def test_phase_unknown_lists_the_valid_phases():
    with pytest.raises(PhaseUnknown) as caught:
        coerce_phase("shipped")
    assert "draft" in str(caught.value) and "merged" in str(caught.value)


# ----------------------------------------------------------------------
# Legality
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "current,target",
    [
        (WorkOrderPhase.DRAFT, WorkOrderPhase.APPROVED),
        (WorkOrderPhase.APPROVED, WorkOrderPhase.ASSIGNED),
        (WorkOrderPhase.ASSIGNED, WorkOrderPhase.SPEC_TESTS),
        (WorkOrderPhase.SPEC_TESTS, WorkOrderPhase.IMPLEMENTATION),
        (WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.REVIEW),
        (WorkOrderPhase.REVIEW, WorkOrderPhase.VERIFICATION),
        (WorkOrderPhase.VERIFICATION, WorkOrderPhase.READY),
        (WorkOrderPhase.READY, WorkOrderPhase.MERGED),
        (WorkOrderPhase.MERGED, WorkOrderPhase.CLOSED),
        (WorkOrderPhase.REVIEW, WorkOrderPhase.IMPLEMENTATION),
        (WorkOrderPhase.VERIFICATION, WorkOrderPhase.IMPLEMENTATION),
        (WorkOrderPhase.READY, WorkOrderPhase.VERIFICATION),
    ],
)
def test_legal_transitions(current, target):
    assert TransitionValidator.is_legal(current, target)
    assert TransitionValidator.refusal_reason(current, target) is None


@pytest.mark.parametrize(
    "current,target,fragment",
    [
        (WorkOrderPhase.DRAFT, WorkOrderPhase.ASSIGNED, "blast-radius lock"),
        (WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.SPEC_TESTS, "what the code does"),
        (WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.VERIFICATION, "adversarial"),
        (WorkOrderPhase.REVIEW, WorkOrderPhase.READY, "not a reproduction"),
        (WorkOrderPhase.VERIFICATION, WorkOrderPhase.MERGED, "human gate"),
        (WorkOrderPhase.ASSIGNED, WorkOrderPhase.IMPLEMENTATION, "spec tests are authored"),
    ],
)
def test_forbidden_transitions_carry_their_argument(current, target, fragment):
    """A generic refusal teaches nothing; these are attempted in good faith."""
    reason = TransitionValidator.refusal_reason(current, target)
    assert reason is not None and fragment in reason


@pytest.mark.parametrize("terminal", sorted(TERMINAL_PHASES, key=lambda p: p.value))
def test_nothing_leaves_a_terminal_phase(terminal):
    for target in WorkOrderPhase:
        if target is terminal:
            continue
        assert not TransitionValidator.is_legal(terminal, target)
        assert "terminal" in TransitionValidator.refusal_reason(terminal, target)


def test_reapproval_is_refused_with_the_digest_argument():
    reason = TransitionValidator.refusal_reason(WorkOrderPhase.REVIEW, WorkOrderPhase.APPROVED)
    assert "single-use" in reason


def test_validate_raises_on_an_illegal_move():
    with pytest.raises(IllegalTransition) as caught:
        TransitionValidator.validate(
            _snapshot(WorkOrderPhase.DRAFT), WorkOrderPhase.ASSIGNED
        )
    assert caught.value.current == "draft"
    assert caught.value.requested == "assigned"


# ----------------------------------------------------------------------
# Optimistic concurrency
# ----------------------------------------------------------------------


def test_a_matching_precondition_passes():
    TransitionValidator.validate(
        _snapshot(WorkOrderPhase.APPROVED),
        WorkOrderPhase.ASSIGNED,
        expected_phase=WorkOrderPhase.APPROVED,
    )


def test_a_stale_precondition_is_refused():
    """A command composed against a stale read must not be applied blindly."""
    with pytest.raises(PreconditionFailed) as caught:
        TransitionValidator.validate(
            _snapshot(WorkOrderPhase.REVIEW),
            WorkOrderPhase.VERIFICATION,
            expected_phase=WorkOrderPhase.IMPLEMENTATION,
        )
    assert caught.value.expected == "implementation"
    assert caught.value.actual == "review"


def test_the_precondition_is_checked_before_legality():
    """Otherwise a stale caller gets told its move is illegal, which is misleading.

    The move it asked for may be perfectly legal from the phase it believed the
    WorkOrder was in. The useful answer is 'it moved', not 'that is illegal'.
    """
    with pytest.raises(PreconditionFailed):
        TransitionValidator.validate(
            _snapshot(WorkOrderPhase.MERGED),
            WorkOrderPhase.ASSIGNED,
            expected_phase=WorkOrderPhase.APPROVED,
        )


# ----------------------------------------------------------------------
# Snapshot
# ----------------------------------------------------------------------


def test_snapshot_reports_terminality():
    assert _snapshot(WorkOrderPhase.CLOSED).is_terminal
    assert not _snapshot(WorkOrderPhase.REVIEW).is_terminal


def test_review_outcome_passes_only_without_blocking_findings():
    from backend.contexts.engineering import ReviewOutcome

    assert ReviewOutcome(work_id="w", round=1, lens="correctness", verdict="pass").passed
    assert not ReviewOutcome(
        work_id="w", round=1, lens="correctness", verdict="pass", blocking_findings=1
    ).passed


def test_verification_outcome_is_complete_only_when_nothing_failed():
    from backend.contexts.engineering import VerificationOutcome

    assert VerificationOutcome(work_id="w", attempt=1, status="complete").complete
    assert not VerificationOutcome(
        work_id="w", attempt=1, status="complete", claims_contradicted=1
    ).complete
    assert not VerificationOutcome(
        work_id="w", attempt=1, status="complete", claims_unreproducible=1
    ).complete
