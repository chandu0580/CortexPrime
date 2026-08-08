"""Findings, comments, severities, and the lens vocabulary.

The rules under test here are the ones a reviewer meets first: a finding has to
point at something, a blocking finding has to say what would clear it, and a
blocking finding cannot be waived by the reviewer who raised it.
"""

from __future__ import annotations

import pytest

from backend.contexts.review import (
    BlockingFindingCannotBeWaived,
    BlockingFindingWithoutRemedy,
    CodeLocation,
    FindingAlreadyResolved,
    FindingCategory,
    FindingState,
    FindingWithoutAnchor,
    REQUIRED_LENSES,
    Resolution,
    ReviewComment,
    ReviewFinding,
    ReviewLens,
    ReviewSeverity,
    UnknownLens,
    coerce_lens,
    comment,
    finding,
    location,
    required_lens_values,
)
from backend.contracts.errors import ContractViolation

WORK = "WO-1"
IMPL = "IMP-1"


def _finding(**overrides) -> ReviewFinding:
    fields = dict(
        work_id=WORK,
        implementation_id=IMPL,
        summary="the tenant filter is derived from the payload",
        severity=ReviewSeverity.MINOR,
        category=FindingCategory.CORRECTNESS,
        at=location("backend/a.py", 12),
    )
    fields.update(overrides)
    return finding(**fields)


# ----------------------------------------------------------------------
# Anchoring
# ----------------------------------------------------------------------


def test_a_finding_that_points_at_nothing_is_refused() -> None:
    with pytest.raises(FindingWithoutAnchor):
        _finding(at=None, evidence=())


def test_a_location_alone_anchors_a_finding() -> None:
    assert _finding(at=location("backend/a.py"), evidence=()).anchor == "backend/a.py"


def test_evidence_alone_anchors_a_finding() -> None:
    raised = _finding(at=None, evidence=("EV-7",))
    assert raised.anchor == "EV-7"
    assert raised.evidence_ids == ("EV-7",)


def test_a_location_renders_its_range() -> None:
    assert str(location("a.py")) == "a.py"
    assert str(location("a.py", 3)) == "a.py:3"
    assert str(location("a.py", 3, 9)) == "a.py:3-9"


def test_a_range_that_ends_before_it_starts_is_refused() -> None:
    with pytest.raises(ContractViolation):
        location("a.py", 9, 3)


def test_an_end_line_without_a_start_names_no_range() -> None:
    with pytest.raises(ContractViolation):
        CodeLocation(path="a.py", end_line=9)


def test_a_blank_evidence_reference_is_refused() -> None:
    with pytest.raises(ContractViolation):
        _finding(at=None, evidence=("  ",))


# ----------------------------------------------------------------------
# Severity
# ----------------------------------------------------------------------


def test_only_blocking_blocks() -> None:
    assert ReviewSeverity.BLOCKING.blocks_approval
    for advisory in (ReviewSeverity.MAJOR, ReviewSeverity.MINOR, ReviewSeverity.NIT):
        assert advisory.is_advisory
        assert not advisory.blocks_approval


def test_severities_rank_in_the_order_they_read() -> None:
    ranks = [s.rank for s in (
        ReviewSeverity.NIT, ReviewSeverity.MINOR, ReviewSeverity.MAJOR, ReviewSeverity.BLOCKING
    )]
    assert ranks == sorted(ranks)


def test_a_blocking_finding_must_say_what_would_clear_it() -> None:
    with pytest.raises(BlockingFindingWithoutRemedy):
        _finding(severity=ReviewSeverity.BLOCKING)


def test_a_blocking_finding_with_a_remedy_is_accepted() -> None:
    raised = _finding(
        severity=ReviewSeverity.BLOCKING, required_change="derive tenant from the context"
    )
    assert raised.blocks_approval
    assert raised.required_change


def test_an_advisory_finding_needs_no_remedy() -> None:
    assert not _finding(severity=ReviewSeverity.NIT).blocks_approval


# ----------------------------------------------------------------------
# Resolution
# ----------------------------------------------------------------------


def test_resolving_a_finding_clears_it() -> None:
    raised = _finding()
    resolved = raised.resolve(Resolution.FIXED, by="alice")
    assert resolved.state is FindingState.RESOLVED
    assert resolved.resolution is Resolution.FIXED
    assert resolved.resolved_by == "alice"
    assert not resolved.is_open


def test_a_fixed_blocker_no_longer_blocks() -> None:
    raised = _finding(severity=ReviewSeverity.BLOCKING, required_change="fix it")
    assert raised.blocks_approval
    assert not raised.resolve(Resolution.FIXED).blocks_approval


def test_a_blocking_finding_cannot_be_waived_as_accepted_risk() -> None:
    """The rule that stops 'must change' becoming 'may ship' with nobody deciding."""
    raised = _finding(severity=ReviewSeverity.BLOCKING, required_change="fix it")
    with pytest.raises(BlockingFindingCannotBeWaived) as caught:
        raised.resolve(Resolution.ACCEPTED_RISK, note="we will do it later")
    assert caught.value.finding_id == str(raised.finding_id)


def test_an_advisory_finding_may_be_accepted_with_a_justification() -> None:
    resolved = _finding(severity=ReviewSeverity.MAJOR).resolve(
        Resolution.ACCEPTED_RISK, note="the path is behind a flag that is off"
    )
    assert resolved.resolution.leaves_hazard
    assert resolved.resolution_note


def test_accepting_a_risk_without_saying_why_is_refused() -> None:
    with pytest.raises(ContractViolation):
        _finding(severity=ReviewSeverity.MAJOR).resolve(Resolution.ACCEPTED_RISK)


def test_a_finding_cannot_be_resolved_twice() -> None:
    resolved = _finding().resolve(Resolution.FIXED)
    with pytest.raises(FindingAlreadyResolved):
        resolved.resolve(Resolution.WITHDRAWN)


def test_only_accepted_risk_leaves_a_hazard() -> None:
    assert Resolution.ACCEPTED_RISK.leaves_hazard
    assert not Resolution.FIXED.leaves_hazard
    assert not Resolution.WITHDRAWN.leaves_hazard


def test_only_accepted_risk_demands_a_justification() -> None:
    assert Resolution.ACCEPTED_RISK.requires_justification
    assert not Resolution.FIXED.requires_justification
    assert not Resolution.WITHDRAWN.requires_justification


def test_a_resolved_finding_must_say_how() -> None:
    raised = _finding()
    with pytest.raises(ContractViolation):
        ReviewFinding(
            finding_id=raised.finding_id,
            work_id=WORK,
            implementation_id=IMPL,
            summary=raised.summary,
            severity=raised.severity,
            category=raised.category,
            location=raised.location,
            state=FindingState.RESOLVED,
        )


def test_an_open_finding_cannot_carry_a_resolution() -> None:
    raised = _finding()
    with pytest.raises(ContractViolation):
        ReviewFinding(
            finding_id=raised.finding_id,
            work_id=WORK,
            implementation_id=IMPL,
            summary=raised.summary,
            severity=raised.severity,
            category=raised.category,
            location=raised.location,
            state=FindingState.OPEN,
            resolution=Resolution.FIXED,
        )


# ----------------------------------------------------------------------
# References
# ----------------------------------------------------------------------


def test_a_finding_carries_the_workorder_and_implementation_it_is_about() -> None:
    """So a finding quoted somewhere else can still say what it was about."""
    raised = _finding()
    assert raised.work_id == WORK
    assert raised.implementation_id == IMPL


def test_a_finding_must_state_something() -> None:
    with pytest.raises(ContractViolation):
        _finding(summary="   ")


def test_the_category_is_independent_of_the_lens_that_found_it() -> None:
    """A correctness reviewer who spots a tenancy hole records it as security."""
    raised = _finding(category=FindingCategory.SECURITY)
    assert raised.category is FindingCategory.SECURITY


# ----------------------------------------------------------------------
# Comments
# ----------------------------------------------------------------------


def test_a_comment_says_something_and_blocks_nothing() -> None:
    written = comment("why is this ordering significant?", author="bob")
    assert written.body
    assert not hasattr(written, "severity")


def test_an_empty_comment_is_refused() -> None:
    with pytest.raises(ContractViolation):
        comment("   ")


def test_a_comment_must_name_its_author() -> None:
    with pytest.raises(ContractViolation):
        ReviewComment.create("something", author="  ")


# ----------------------------------------------------------------------
# Lenses
# ----------------------------------------------------------------------


def test_the_required_lenses_are_the_ones_reported_to_the_runtime() -> None:
    assert set(required_lens_values()) == {lens.value for lens in REQUIRED_LENSES}


def test_performance_is_defined_but_not_required() -> None:
    """A lens that is routinely empty teaches reviewers to approve without reading."""
    assert ReviewLens.PERFORMANCE in ReviewLens
    assert not ReviewLens.PERFORMANCE.is_required
    assert ReviewLens.PERFORMANCE.value not in required_lens_values()


def test_every_lens_states_its_mandate() -> None:
    for lens in ReviewLens:
        assert lens.mandate.strip()


def test_an_unknown_lens_is_refused_rather_than_defaulted() -> None:
    """A misspelled lens quietly becoming 'correctness' reports a lens as covered
    that nobody read for."""
    with pytest.raises(UnknownLens) as caught:
        coerce_lens("corectness")
    assert "correctness" in caught.value.known


def test_coerce_accepts_a_lens_or_its_value() -> None:
    assert coerce_lens("security") is ReviewLens.SECURITY
    assert coerce_lens(ReviewLens.SECURITY) is ReviewLens.SECURITY


def test_the_runtimes_default_lens_is_a_real_lens() -> None:
    """The runtime falls back to ``("correctness",)`` when a request reports no
    lens. If this context ever renamed that lens, the fallback would name one
    that does not exist."""
    assert coerce_lens("correctness") is ReviewLens.CORRECTNESS
