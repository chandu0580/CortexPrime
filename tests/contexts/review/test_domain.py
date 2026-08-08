"""The ReviewRecord aggregate: creation, finding lifecycle, decisions, digest.

The two rules this file exists to pin are the ones that make an unreviewed change
look reviewed: **approving over an open blocker**, and **approving without having
examined the change set**. Both are held in the aggregate as well as the policy,
because a record assembled from storage bypasses the service.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.contexts.review import (
    ApprovalWithOpenBlockers,
    FindingCategory,
    GOVERNED_FIELDS,
    Resolution,
    ReviewDecided,
    ReviewDecision,
    ReviewIsSuperseded,
    ReviewId,
    ReviewLens,
    ReviewNotStarted,
    ReviewRecord,
    ReviewSeverity,
    ReviewStatus,
    UnexaminedFiles,
    UnknownFinding,
    comment,
    finding,
    location,
    request_review,
)
from backend.contracts.errors import ContractViolation

WORK = "WO-1"
IMPL = "IMP-1"
DIGEST = "9f2c1a7b3e4d5c6a"
REVISION = "a1b2c3d4"
FILES = ("backend/a.py", "backend/b.py")


def _requested(**overrides) -> ReviewRecord:
    fields = dict(
        work_id=WORK,
        round=1,
        lens=ReviewLens.CORRECTNESS,
        implementation_id=IMPL,
        implementation_digest=DIGEST,
        revision=REVISION,
        files_under_review=FILES,
        adr_references=("ADR-024",),
    )
    fields.update(overrides)
    return request_review(**fields)


def _started(**overrides) -> ReviewRecord:
    return _requested(**overrides).start("alice")


def _blocker(**overrides):
    fields = dict(
        work_id=WORK,
        implementation_id=IMPL,
        summary="tenant is read from the payload",
        severity=ReviewSeverity.BLOCKING,
        category=FindingCategory.SECURITY,
        at=location("backend/a.py", 20),
        required_change="derive the tenant from the execution context",
    )
    fields.update(overrides)
    return finding(**fields)


def _approvable(**overrides) -> ReviewRecord:
    return _started(**overrides).examine(*FILES)


# ----------------------------------------------------------------------
# Creation
# ----------------------------------------------------------------------


def test_a_review_names_the_artifact_it_reads() -> None:
    review = _requested()
    assert review.work_id == WORK
    assert review.implementation_id == IMPL
    assert review.implementation_digest == DIGEST
    assert review.revision == REVISION
    assert review.lens is ReviewLens.CORRECTNESS
    assert review.status is ReviewStatus.REQUESTED


@pytest.mark.parametrize(
    "blank", ["work_id", "implementation_id", "implementation_digest", "revision"]
)
def test_a_review_missing_a_mandatory_reference_is_refused(blank: str) -> None:
    with pytest.raises(ContractViolation):
        _requested(**{blank: "   "})


def test_the_round_starts_at_one() -> None:
    with pytest.raises(ContractViolation):
        _requested(round=0)


def test_a_review_carries_the_change_set_an_approval_must_cover() -> None:
    assert _requested().files_under_review == tuple(sorted(FILES))
    assert _requested().unexamined_files == tuple(sorted(FILES))


def test_the_change_set_is_deduplicated_and_ordered() -> None:
    review = _requested(files_under_review=("b.py", "a.py", "b.py"))
    assert review.files_under_review == ("a.py", "b.py")


# ----------------------------------------------------------------------
# Starting
# ----------------------------------------------------------------------


def test_a_finding_cannot_be_raised_before_a_reviewer_takes_the_review_up() -> None:
    """An unattributed finding is an assertion with nobody behind it."""
    with pytest.raises(ReviewNotStarted):
        _requested().add_finding(_blocker())


def test_starting_names_the_reviewer() -> None:
    review = _started()
    assert review.status is ReviewStatus.IN_PROGRESS
    assert review.reviewer == "alice"
    assert review.started_at is not None


def test_starting_without_a_reviewer_is_refused() -> None:
    with pytest.raises(ContractViolation):
        _requested().start("   ")


def test_a_review_cannot_be_started_twice() -> None:
    with pytest.raises(ContractViolation):
        _started().start("bob")


def test_examining_nothing_records_nothing() -> None:
    with pytest.raises(ContractViolation):
        _started().examine()


def test_reading_beyond_the_change_set_is_recorded_not_refused() -> None:
    """Reading a caller to understand what a change breaks is review."""
    review = _started().examine("backend/unrelated_caller.py")
    assert "backend/unrelated_caller.py" in review.files_examined
    assert review.unexamined_files == tuple(sorted(FILES))


# ----------------------------------------------------------------------
# Finding lifecycle
# ----------------------------------------------------------------------


def test_a_finding_about_another_workorder_cannot_be_attached() -> None:
    review = _started()
    with pytest.raises(ContractViolation):
        review.add_finding(_blocker(work_id="WO-OTHER"))


def test_a_finding_about_another_implementation_cannot_be_attached() -> None:
    review = _started()
    with pytest.raises(ContractViolation):
        review.add_finding(_blocker(implementation_id="IMP-OTHER"))


def test_open_blockers_are_distinct_from_every_blocker_raised() -> None:
    """A blocker raised and fixed inside the round is a fact about the round."""
    raised = _blocker()
    review = _started().add_finding(raised)
    assert len(review.open_blockers) == 1

    resolved = review.resolve_finding(raised.finding_id, Resolution.FIXED)
    assert resolved.open_blockers == ()
    assert len(resolved.blocking_findings) == 1


def test_resolving_an_unknown_finding_is_refused() -> None:
    from backend.contexts.review import FindingId

    with pytest.raises(UnknownFinding):
        _started().resolve_finding(FindingId.new(), Resolution.FIXED)


def test_a_comment_replying_to_an_unknown_finding_is_refused() -> None:
    from backend.contexts.review import FindingId

    with pytest.raises(UnknownFinding):
        _started().add_comment(comment("about that", in_reply_to=FindingId.new()))


def test_a_comment_can_reply_to_a_real_finding() -> None:
    raised = _blocker()
    review = _started().add_finding(raised)
    replied = review.add_comment(comment("agreed", in_reply_to=raised.finding_id))
    assert replied.comments[0].in_reply_to == raised.finding_id


def test_accepted_risks_are_surfaced_separately() -> None:
    raised = finding(
        work_id=WORK,
        implementation_id=IMPL,
        summary="the retry has no jitter",
        severity=ReviewSeverity.MAJOR,
        category=FindingCategory.PERFORMANCE,
        at=location("backend/a.py", 5),
    )
    review = _approvable().add_finding(raised)
    accepted = review.resolve_finding(
        raised.finding_id, Resolution.ACCEPTED_RISK, note="the path is behind a flag"
    )
    assert len(accepted.accepted_risks) == 1


# ----------------------------------------------------------------------
# Approval refusals -- the two that matter
# ----------------------------------------------------------------------


def test_approving_over_an_open_blocker_is_refused() -> None:
    review = _approvable().add_finding(_blocker())
    with pytest.raises(ApprovalWithOpenBlockers) as caught:
        review.decide(ReviewDecision.APPROVED)
    assert len(caught.value.open_findings) == 1


def test_approving_without_examining_the_change_set_is_refused() -> None:
    """The rubber stamp. An approval covering one of two files reports like both."""
    review = _started().examine("backend/a.py")
    with pytest.raises(UnexaminedFiles) as caught:
        review.decide(ReviewDecision.APPROVED)
    assert caught.value.unexamined == ("backend/b.py",)


def test_a_fixed_blocker_no_longer_refuses_the_approval() -> None:
    raised = _blocker()
    review = _approvable().add_finding(raised)
    cleared = review.resolve_finding(raised.finding_id, Resolution.FIXED)
    assert cleared.decide(ReviewDecision.APPROVED).decision is ReviewDecision.APPROVED


def test_changes_requested_may_carry_open_blockers() -> None:
    """The decision exists to carry blockers outward; refusing it for having them
    would leave a reviewer who found a real defect with no way to report it."""
    review = _started().add_finding(_blocker())
    decided = review.decide(
        ReviewDecision.CHANGES_REQUESTED, rationale="the tenancy hole must close first"
    )
    assert decided.decision is ReviewDecision.CHANGES_REQUESTED
    assert len(decided.open_blockers) == 1


def test_rejection_may_carry_open_blockers_too() -> None:
    review = _started().add_finding(_blocker())
    decided = review.decide(
        ReviewDecision.REJECTED, rationale="the WorkOrder's premise does not hold"
    )
    assert decided.decision is ReviewDecision.REJECTED


def test_a_refusal_must_say_why() -> None:
    review = _started().add_finding(_blocker())
    with pytest.raises(ContractViolation):
        review.decide(ReviewDecision.CHANGES_REQUESTED)


def test_an_approval_needs_no_rationale() -> None:
    assert _approvable().decide(ReviewDecision.APPROVED).decision_rationale is None


def test_deciding_before_starting_is_refused() -> None:
    with pytest.raises(ReviewNotStarted):
        _requested().decide(ReviewDecision.APPROVED)


# ----------------------------------------------------------------------
# Immutability after the decision
# ----------------------------------------------------------------------


#: Every mutation the aggregate exposes, with a call that would succeed on an
#: open review. ``test_every_mutation_is_covered`` fails if one is added without
#: an entry here, so this list cannot silently fall behind the aggregate.
_MUTATIONS = {
    "start": lambda r: r.start("bob"),
    "examine": lambda r: r.examine("backend/a.py"),
    "add_finding": lambda r: r.add_finding(_blocker()),
    "resolve_finding": lambda r: r.resolve_finding(
        r.findings[0].finding_id if r.findings else __import__(
            "backend.contexts.review", fromlist=["FindingId"]
        ).FindingId.new(),
        Resolution.FIXED,
    ),
    "add_comment": lambda r: r.add_comment(comment("late thought")),
    "decide": lambda r: r.decide(ReviewDecision.APPROVED),
}


@pytest.mark.parametrize("name", sorted(_MUTATIONS))
def test_every_mutation_refuses_on_a_decided_review(name: str) -> None:
    decided = _approvable().decide(ReviewDecision.APPROVED)
    with pytest.raises(ReviewDecided):
        _MUTATIONS[name](decided)


def test_every_mutation_is_covered_by_the_immutability_test() -> None:
    """Fails if a mutation is added to the aggregate without an entry above.

    Enumerating the mutations by hand is what makes the immutability rule hold
    as the aggregate grows, rather than only for the methods that existed when
    the rule was written.
    """
    exposed = {
        name
        for name in dir(ReviewRecord)
        if not name.startswith("_")
        and callable(getattr(ReviewRecord, name))
        and name not in {
            "compute_digest",
            "digest_payload",
            "verify_digest",
            "finding",
            "supersede",
            "to_dict",
            "from_dict",
            "contract_name",
            "contract_version",
        }
    }
    assert exposed == set(_MUTATIONS), exposed.symmetric_difference(set(_MUTATIONS))


def test_superseding_is_permitted_on_a_decided_review() -> None:
    """The one exception: it changes whether the review is current, not what it said."""
    decided = _approvable().decide(ReviewDecision.APPROVED)
    successor = ReviewId.new()
    superseded = decided.supersede(successor)

    assert superseded.status is ReviewStatus.SUPERSEDED
    assert superseded.superseded_by == successor
    superseded.verify_digest()


def test_a_superseded_review_refuses_mutations_with_its_own_error() -> None:
    superseded = _started().supersede(ReviewId.new())
    with pytest.raises(ReviewIsSuperseded):
        superseded.add_finding(_blocker())


def test_a_review_cannot_supersede_itself() -> None:
    review = _started()
    with pytest.raises(ContractViolation):
        review.supersede(review.review_id)


def test_a_review_cannot_be_superseded_twice() -> None:
    superseded = _started().supersede(ReviewId.new())
    with pytest.raises(ContractViolation):
        superseded.supersede(ReviewId.new())


# ----------------------------------------------------------------------
# Digest
# ----------------------------------------------------------------------


def test_the_decision_binds_a_digest_and_it_verifies() -> None:
    decided = _approvable().decide(ReviewDecision.APPROVED)
    assert decided.digest
    decided.verify_digest()


def test_a_decided_review_without_a_digest_cannot_exist() -> None:
    decided = _approvable().decide(ReviewDecision.APPROVED)
    with pytest.raises(ContractViolation):
        dataclasses.replace(decided, digest=None)


def test_a_decided_review_must_name_its_reviewer() -> None:
    decided = _approvable().decide(ReviewDecision.APPROVED)
    with pytest.raises(ContractViolation):
        dataclasses.replace(decided, reviewer=None)


def test_only_a_decided_review_carries_a_decision() -> None:
    with pytest.raises(ContractViolation):
        dataclasses.replace(_started(), decision=ReviewDecision.APPROVED)


def test_an_approval_with_open_blockers_cannot_be_assembled_from_storage() -> None:
    """The invariant holds for a record built directly, not only one built by
    ``decide`` -- which is the path persistence takes."""
    decided = _approvable().decide(ReviewDecision.APPROVED)
    with pytest.raises(ContractViolation):
        dataclasses.replace(decided, findings=(_blocker(),))


def test_tampering_with_a_governed_field_is_caught() -> None:
    from backend.contexts.review import DigestMismatch

    decided = _approvable().decide(ReviewDecision.APPROVED)
    tampered = dataclasses.replace(decided, files_examined=("backend/a.py",))
    with pytest.raises(DigestMismatch):
        tampered.verify_digest()


def test_verifying_an_undecided_review_says_so_rather_than_passing() -> None:
    from backend.contexts.review import DigestNotComputed

    with pytest.raises(DigestNotComputed):
        _started().verify_digest()


def test_the_digest_covers_the_governed_fields_and_nothing_else() -> None:
    payload = _approvable().decide(ReviewDecision.APPROVED).digest_payload()
    covered = set(payload) - {"__artifact__", "__canonical_form__"}
    assert covered == set(GOVERNED_FIELDS)


def test_status_and_timestamps_are_not_governed() -> None:
    """Superseding a decided review is legal and must not invalidate the digest."""
    for excluded in ("status", "digest", "decided_at", "requested_at", "started_at"):
        assert excluded not in GOVERNED_FIELDS


def test_the_digest_changes_when_a_finding_changes() -> None:
    raised = _blocker()
    base = _approvable().add_finding(raised)
    cleared = base.resolve_finding(raised.finding_id, Resolution.FIXED)

    approved = cleared.decide(ReviewDecision.APPROVED)
    other = _approvable().decide(ReviewDecision.APPROVED)
    assert approved.digest != other.digest


def test_the_digest_is_stable_across_the_order_things_were_recorded() -> None:
    first = _started().examine("backend/a.py").examine("backend/b.py")
    second = _started().examine("backend/b.py").examine("backend/a.py")
    assert (
        first.decide(ReviewDecision.APPROVED).digest
        == second.decide(ReviewDecision.APPROVED).digest
    )


def test_two_lenses_on_one_round_do_not_collide() -> None:
    correctness = _approvable(lens=ReviewLens.CORRECTNESS).decide(ReviewDecision.APPROVED)
    security = _approvable(lens=ReviewLens.SECURITY).decide(ReviewDecision.APPROVED)
    assert correctness.digest != security.digest


# ----------------------------------------------------------------------
# Coverage reporting
# ----------------------------------------------------------------------


def test_coverage_is_one_when_nothing_is_under_review() -> None:
    """A review with no change set has nothing to skip."""
    assert _requested(files_under_review=()).coverage_ratio == 1.0


def test_coverage_reports_the_fraction_actually_read() -> None:
    assert _started().examine("backend/a.py").coverage_ratio == 0.5
    assert _approvable().coverage_ratio == 1.0


def test_all_evidence_ids_span_every_finding() -> None:
    review = (
        _started()
        .add_finding(_blocker(at=None, evidence=("EV-1",)))
        .add_finding(
            finding(
                work_id=WORK,
                implementation_id=IMPL,
                summary="second",
                at=None,
                evidence=("EV-2",),
            )
        )
    )
    assert review.all_evidence_ids == ("EV-1", "EV-2")


def test_only_decided_is_reportable_to_the_runtime() -> None:
    assert ReviewStatus.DECIDED.is_reportable
    for other in (ReviewStatus.REQUESTED, ReviewStatus.IN_PROGRESS, ReviewStatus.SUPERSEDED):
        assert not other.is_reportable
