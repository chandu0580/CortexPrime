"""The aggregate, the completion policy, and the digest.

Three rules carry this context, and each has a test that fails if the rule is
removed rather than a test that passes because the rule happens to hold:

* immutable after completion -- every mutation refuses,
* every claim cites evidence -- refused at construction (see ``test_claims.py``),
* changed files stay inside the blast radius -- refused at recording *and* at
  completion, because a radius can be narrowed by re-approval after a file was
  already recorded.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from backend.contexts.implementation_record.domain.changes import (
    ChangedFile,
    ChangeKind,
    CodeChangeSet,
)
from backend.contexts.implementation_record.domain.claims import (
    AssumptionOutcome,
    ClaimType,
    RiskLevel,
)
from backend.contexts.implementation_record.domain.errors import (
    AssumptionAlreadyResolved,
    DigestMismatch,
    DigestNotComputed,
    DuplicateClaim,
    OutsideBlastRadius,
    RecordCompleted,
    RecordSuperseded,
    UnknownAssumption,
)
from backend.contexts.implementation_record.domain.factory import (
    build,
    changed,
    claim,
    coverage,
    resolution,
    risk,
    start_implementation,
    test_run,
)
from backend.contexts.implementation_record.domain.identifiers import ImplementationId
from backend.contexts.implementation_record.domain.outcomes import (
    BuildResult,
    ExecutionStatus,
    TestExecution,
)
from backend.contexts.implementation_record.domain.policy import (
    Severity,
    default_policy,
)
from backend.contexts.implementation_record.domain.record import (
    GOVERNED_FIELDS,
    ImplementationRecord,
    ImplementationStatus,
)
from backend.contracts.errors import ContractViolation


REVISION = "a1b2c3d4"


def open_record(**overrides) -> ImplementationRecord:
    defaults = dict(
        work_id="WO-1",
        context_bundle_id="CB-1",
        revision=REVISION,
        blast_radius=["backend/contexts/implementation_record/**"],
        adr_references=["ADR-023"],
    )
    defaults.update(overrides)
    return start_implementation(**defaults)


def submittable(**overrides) -> ImplementationRecord:
    """A record the policy will accept, so a test can remove one thing at a time."""
    record = open_record(**overrides)
    record = record.record_file(
        changed("backend/contexts/implementation_record/domain/record.py", added=600)
    )
    record = record.add_claim(
        claim("the record is immutable after completion", ClaimType.BEHAVIOUR, ["EV-1"])
    )
    record = record.record_tests(
        test_run("python -m pytest tests/contexts/implementation_record -q", REVISION, passed=49)
    )
    return record


# ----------------------------------------------------------------------
# The four mandatory references
# ----------------------------------------------------------------------


def test_every_record_carries_the_four_references_it_is_asked_about() -> None:
    """WorkOrder, ContextBundle, ADRs, revision -- four different reviewer questions.

    What authorised this, what did the implementer see, what governs it, what
    tree is it against. A record missing any one cannot answer that question.
    """
    record = open_record()
    assert record.work_id == "WO-1"
    assert record.context_bundle_id == "CB-1"
    assert record.context_bundle_version == 1
    assert record.adr_references == frozenset({"ADR-023"})
    assert record.revision == REVISION
    assert record.digest is None  # the fifth, bound at completion


@pytest.mark.parametrize(
    "field", ["work_id", "context_bundle_id", "revision"]
)
def test_a_record_missing_a_mandatory_reference_is_refused(field: str) -> None:
    for blank in ("", "   "):
        with pytest.raises(ContractViolation):
            open_record(**{field: blank})


def test_a_record_against_a_different_tree_than_its_changes_is_refused() -> None:
    """Two revisions in one record leaves a reviewer unable to say which is under review."""
    record = open_record()
    with pytest.raises(ContractViolation, match="could not say which is under review"):
        replace(
            record,
            changes=CodeChangeSet(
                revision="deadbeef",
                files=(changed("backend/contexts/implementation_record/x.py"),),
            ),
        )


def test_round_and_bundle_version_start_at_one() -> None:
    for bad in (0, -1):
        with pytest.raises(ContractViolation, match="positive integer"):
            open_record(round=bad)
        with pytest.raises(ContractViolation, match="positive integer"):
            open_record(context_bundle_version=bad)


# ----------------------------------------------------------------------
# Blast radius containment
# ----------------------------------------------------------------------


def test_a_file_outside_the_radius_is_refused_at_recording() -> None:
    """Refused while the implementer still remembers why it touched the file."""
    record = open_record()
    with pytest.raises(OutsideBlastRadius) as caught:
        record.record_file(changed("frontend/app/page.tsx"))
    assert caught.value.path == "frontend/app/page.tsx"
    assert "outside the declared blast radius" in caught.value.reason


def test_a_forbidden_path_is_refused_with_a_different_reason() -> None:
    record = open_record(
        blast_radius=["backend/**"], forbidden=["backend/database/**"]
    )
    with pytest.raises(OutsideBlastRadius) as caught:
        record.record_file(changed("backend/database/models.py"))
    assert "explicitly forbidden" in caught.value.reason


def test_a_rename_is_checked_at_both_ends() -> None:
    """Moving a file *out* of the radius escapes it just as surely as editing one.

    A rename that only checked its destination would let an implementer move a
    governed file anywhere it liked.
    """
    record = open_record(blast_radius=["backend/**"])
    with pytest.raises(OutsideBlastRadius) as caught:
        record.record_file(
            changed(
                "frontend/moved.py",
                ChangeKind.RENAMED,
                previous_path="backend/original.py",
            )
        )
    assert caught.value.path == "frontend/moved.py"

    with pytest.raises(OutsideBlastRadius) as caught:
        record.record_file(
            changed(
                "backend/moved.py",
                ChangeKind.RENAMED,
                previous_path="frontend/original.py",
            )
        )
    assert caught.value.path == "frontend/original.py"


def test_completion_rechecks_containment_because_a_radius_can_narrow() -> None:
    """The one path a recording-time check alone would miss.

    A file recorded legally, then the radius narrowed by re-approval. The file is
    now outside a scope it was inside when recorded, and only a completion-time
    check catches it.
    """
    record = submittable(blast_radius=["backend/**"])
    narrowed = replace(
        record,
        blast_radius=type(record.blast_radius).of(["backend/api/**"]),
    )
    report = default_policy().evaluate(narrowed)
    assert not report.may_complete
    assert any(f.rule == "C2-within-blast-radius" for f in report.blocking)


def test_an_over_claimed_radius_is_advisory_not_blocking() -> None:
    """It weakens conflict detection for other WorkOrders, but this one is fine."""
    record = submittable(blast_radius=["backend/**", "docs/**"])
    report = default_policy().evaluate(record)
    assert report.may_complete
    assert any(f.rule == "C2-radius-not-fully-used" for f in report.advisory)


# ----------------------------------------------------------------------
# Claims and assumptions
# ----------------------------------------------------------------------


def test_the_same_claim_twice_is_refused() -> None:
    record = open_record().add_claim(claim("it retries", ClaimType.BEHAVIOUR, ["EV-1"]))
    with pytest.raises(DuplicateClaim):
        record.add_claim(claim("it retries", ClaimType.BEHAVIOUR, ["EV-2"]))


def test_resolving_an_assumption_the_workorder_never_declared_is_refused() -> None:
    record = open_record(expected_assumptions=["A1"])
    with pytest.raises(UnknownAssumption):
        record.resolve_assumption(
            resolution("A2", "invented", AssumptionOutcome.CONFIRMED, ["EV-1"])
        )


def test_the_same_assumption_cannot_be_resolved_twice() -> None:
    """Two answers means one of them is wrong."""
    record = open_record(expected_assumptions=["A1"]).resolve_assumption(
        resolution("A1", "holds", AssumptionOutcome.CONFIRMED, ["EV-1"])
    )
    with pytest.raises(AssumptionAlreadyResolved):
        record.resolve_assumption(
            resolution("A1", "holds", AssumptionOutcome.CONTRADICTED, ["EV-2"])
        )


def test_an_unresolved_assumption_blocks_completion() -> None:
    record = submittable(expected_assumptions=["A1", "A2"]).resolve_assumption(
        resolution("A1", "holds", AssumptionOutcome.CONFIRMED, ["EV-1"])
    )
    assert record.unresolved_assumptions == ("A2",)
    report = default_policy().evaluate(record)
    assert not report.may_complete
    assert [f.subject for f in report.blocking if f.rule == "C3-assumptions-resolved"] == ["A2"]


def test_a_contradicted_assumption_blocks_and_names_the_right_response() -> None:
    record = submittable(expected_assumptions=["A1"]).resolve_assumption(
        resolution("A1", "the store is append-only", AssumptionOutcome.CONTRADICTED, ["EV-1"])
    )
    report = default_policy().evaluate(record)
    assert not report.may_complete
    failure = next(f for f in report.blocking if f.rule == "C4-no-false-premise")
    assert "PREMISE_FALSE" in failure.detail


def test_an_unverifiable_assumption_blocks_too() -> None:
    """Proceeding on a belief nobody could check carries the same risk as one
    found false, minus the knowledge that it was."""
    record = submittable(expected_assumptions=["A1"]).resolve_assumption(
        resolution("A1", "no other caller exists", AssumptionOutcome.UNVERIFIABLE, ["EV-1"])
    )
    report = default_policy().evaluate(record)
    assert not report.may_complete
    assert any(f.rule == "C4-no-unverifiable-premise" for f in report.blocking)


def test_all_evidence_ids_spans_claims_and_resolutions() -> None:
    """Verification refuses to reuse any of these, so it needs the whole set."""
    record = (
        open_record(expected_assumptions=["A1"])
        .add_claim(claim("a", ClaimType.BEHAVIOUR, ["EV-1", "EV-2"]))
        .resolve_assumption(
            resolution("A1", "holds", AssumptionOutcome.CONFIRMED, ["EV-3"])
        )
    )
    assert record.all_evidence_ids == ("EV-1", "EV-2", "EV-3")


# ----------------------------------------------------------------------
# Test and build outcomes
# ----------------------------------------------------------------------


def test_a_status_that_contradicts_its_counts_is_refused() -> None:
    """``passed`` with failures recorded is the shape of a mis-parsed summary."""
    with pytest.raises(ContractViolation):
        TestExecution(
            command="pytest", status=ExecutionStatus.PASSED, revision=REVISION, failed=3
        )
    with pytest.raises(ContractViolation):
        TestExecution(
            command="pytest", status=ExecutionStatus.PASSED, revision=REVISION, errors=1
        )


def test_not_run_is_distinguished_from_failed() -> None:
    """The first says nothing about the work; the second says it is wrong."""
    assert not ExecutionStatus.NOT_RUN.was_attempted
    assert ExecutionStatus.FAILED.was_attempted
    assert not ExecutionStatus.NOT_RUN.is_green
    assert not ExecutionStatus.FAILED.is_green


def test_no_test_run_at_all_blocks_completion() -> None:
    record = open_record()
    record = record.record_file(
        changed("backend/contexts/implementation_record/domain/record.py")
    )
    record = record.add_claim(claim("it works", ClaimType.BEHAVIOUR, ["EV-1"]))
    report = default_policy().evaluate(record)
    assert not report.may_complete
    assert any(f.rule == "C6-tests-run" for f in report.blocking)


def test_a_failing_build_blocks_completion() -> None:
    record = submittable().record_build(
        build(
            "architecture gate",
            "python -m backend.platform.architecture",
            REVISION,
            status=ExecutionStatus.FAILED,
            detail="TENANT-REPOSITORY-CONTEXT violated",
        )
    )
    report = default_policy().evaluate(record)
    assert not report.may_complete
    assert any(f.rule == "C7-builds-green" for f in report.blocking)


def test_an_unmitigated_risk_above_low_cannot_reach_the_record() -> None:
    """Enforced by the value object, so the policy rule is a second net."""
    with pytest.raises(ContractViolation):
        risk("the migration may lock the table", RiskLevel.HIGH)


# ----------------------------------------------------------------------
# Completion policy as a whole
# ----------------------------------------------------------------------


def test_the_policy_reports_every_failure_not_the_first() -> None:
    """A completion refusing one reason at a time takes six attempts, and the
    sixth is made by someone who has stopped reading the refusals."""
    empty = open_record(expected_assumptions=["A1"])
    report = default_policy().evaluate(empty)
    rules = {f.rule for f in report.blocking}
    assert {
        "C1-something-changed",
        "C3-assumptions-resolved",
        "C5-at-least-one-claim",
        "C6-tests-run",
    } <= rules


def test_an_absence_claim_is_flagged_advisory_not_blocked() -> None:
    """Settling it requires constructing the violation, not observing green."""
    record = submittable().add_claim(
        claim("no repository bypasses the guard", ClaimType.ABSENCE, ["EV-2"])
    )
    report = default_policy().evaluate(record)
    assert report.may_complete
    assert any(f.rule == "C9-absence-claim-declared" for f in report.advisory)


def test_severity_decides_refusal() -> None:
    assert Severity.BLOCKING.refuses
    assert not Severity.ADVISORY.refuses


def test_a_completed_record_cannot_be_completed_again() -> None:
    report = default_policy().evaluate(submittable().complete())
    assert not report.may_complete
    assert any(f.rule == "C0-open" for f in report.blocking)


# ----------------------------------------------------------------------
# Digest
# ----------------------------------------------------------------------


def test_completion_binds_a_digest_and_it_verifies() -> None:
    sealed = submittable().complete()
    assert sealed.status is ImplementationStatus.COMPLETED
    assert sealed.digest
    assert sealed.completed_at is not None
    sealed.verify_digest()  # raises if it does not


def test_a_completed_record_without_a_digest_cannot_exist() -> None:
    sealed = submittable().complete()
    with pytest.raises(ContractViolation, match="must carry the digest"):
        replace(sealed, digest=None)


def test_verifying_an_uncompleted_record_says_so_rather_than_passing() -> None:
    with pytest.raises(DigestNotComputed):
        submittable().verify_digest()


def test_tampering_with_a_governed_field_is_caught() -> None:
    """Storage restores the digest rather than recomputing it, so this is the
    check that catches a record edited behind the aggregate's back."""
    sealed = submittable().complete()
    tampered = replace(sealed, deviations=("a note nobody wrote",))
    with pytest.raises(DigestMismatch) as caught:
        tampered.verify_digest()
    assert caught.value.recorded == sealed.digest
    assert caught.value.recomputed != sealed.digest


def test_tampering_with_the_revision_trips_an_invariant_before_the_digest() -> None:
    """The revision is governed, but it is also cross-checked against the change
    set, so an edited revision never gets as far as failing verification."""
    sealed = submittable().complete()
    with pytest.raises(ContractViolation, match="could not say which is under review"):
        replace(sealed, revision="a-different-tree")


def test_the_digest_covers_the_governed_fields_and_nothing_else() -> None:
    """``status`` in particular is excluded -- including it would invalidate the
    digest on the first legal transition, and superseding is legal."""
    payload = submittable().complete().digest_payload()
    covered = set(payload) - {"__artifact__", "__canonical_form__"}
    assert covered == set(GOVERNED_FIELDS)
    assert "status" not in payload
    assert "digest" not in payload
    assert "started_at" not in payload


def test_the_digest_is_stable_across_the_order_things_were_recorded() -> None:
    """Two records with the same content must hash the same regardless of the
    order the implementer happened to record it in."""
    first = open_record()
    first = first.record_file(changed("backend/contexts/implementation_record/a.py"))
    first = first.record_file(changed("backend/contexts/implementation_record/b.py"))
    first = first.record_tests(test_run("pytest", REVISION, passed=1))

    second = open_record()
    second = second.record_file(changed("backend/contexts/implementation_record/b.py"))
    second = second.record_file(changed("backend/contexts/implementation_record/a.py"))
    second = second.record_tests(test_run("pytest", REVISION, passed=1))

    assert first.compute_digest().value == second.compute_digest().value


def test_the_digest_changes_when_a_claim_changes() -> None:
    base = submittable()
    altered = base.add_claim(claim("and it is fast", ClaimType.PERFORMANCE, ["EV-2"]))
    assert base.compute_digest().value != altered.compute_digest().value


def test_two_records_for_different_workorders_do_not_collide() -> None:
    assert (
        submittable(work_id="WO-1").compute_digest().value
        != submittable(work_id="WO-2").compute_digest().value
    )


# ----------------------------------------------------------------------
# Immutability after completion
# ----------------------------------------------------------------------


COMPLETED_MUTATIONS = {
    "record_file": lambda r: r.record_file(
        changed("backend/contexts/implementation_record/late.py")
    ),
    "add_claim": lambda r: r.add_claim(claim("late", ClaimType.BEHAVIOUR, ["EV-9"])),
    "resolve_assumption": lambda r: r.resolve_assumption(
        resolution("A9", "late", AssumptionOutcome.CONFIRMED, ["EV-9"])
    ),
    "declare_risk": lambda r: r.declare_risk(risk("late", RiskLevel.LOW)),
    "record_tests": lambda r: r.record_tests(test_run("pytest", REVISION, passed=1)),
    "record_build": lambda r: r.record_build(build("gate", "make", REVISION)),
    "record_coverage": lambda r: r.record_coverage(coverage("late", ["t"])),
    "note_deviation": lambda r: r.note_deviation("late"),
    "complete": lambda r: r.complete(),
    "abandon": lambda r: r.abandon("late"),
}


@pytest.mark.parametrize("name", sorted(COMPLETED_MUTATIONS))
def test_every_mutation_refuses_on_a_completed_record(name: str) -> None:
    """Enumerated rather than spot-checked.

    A record that changed after Review and Verification read it would make every
    finding they produced a statement about a document that no longer exists. A
    test covering three of ten mutations leaves seven ways to do exactly that.
    """
    sealed = submittable().complete()
    with pytest.raises(RecordCompleted):
        COMPLETED_MUTATIONS[name](sealed)


def test_every_mutation_is_covered_by_the_immutability_test() -> None:
    """The enumeration above must not fall behind the aggregate.

    A mutation added later without a matching entry would be immutable-by-luck
    until someone noticed.
    """
    #: Declared on the aggregate itself, so inherited ``Contract`` serialisation
    #: does not have to be enumerated here -- and so a mutation added to the
    #: aggregate later cannot hide behind an inherited name.
    declared = {
        name
        for name, member in vars(ImplementationRecord).items()
        if not name.startswith("_")
        and callable(member)
        and not isinstance(member, (property, classmethod, staticmethod))
    }
    not_a_mutation = {
        "supersede",  # deliberately permitted on a completed record
        "verify_digest",
        "compute_digest",
        "digest_payload",
        "claim",  # a lookup, not a mutation
    }
    uncovered = declared - not_a_mutation - set(COMPLETED_MUTATIONS)
    assert not uncovered, (
        f"these aggregate methods are not covered by the immutability test: "
        f"{sorted(uncovered)}"
    )


def test_superseding_is_permitted_on_a_completed_record() -> None:
    """It does not change what the record says, only whether it is current."""
    sealed = submittable().complete()
    superseded = sealed.supersede(ImplementationId.new())
    assert superseded.status is ImplementationStatus.SUPERSEDED
    assert superseded.digest == sealed.digest
    superseded.verify_digest()


def test_a_superseded_record_refuses_mutations_with_its_own_error() -> None:
    """Distinguished from completion: the caller should go to the successor."""
    superseded = submittable().complete().supersede(ImplementationId.new())
    with pytest.raises(RecordSuperseded):
        superseded.note_deviation("late")


def test_a_record_cannot_supersede_itself() -> None:
    sealed = submittable().complete()
    with pytest.raises(ContractViolation, match="cannot supersede itself"):
        sealed.supersede(sealed.implementation_id)


def test_a_record_cannot_be_superseded_twice() -> None:
    superseded = submittable().complete().supersede(ImplementationId.new())
    with pytest.raises(ContractViolation, match="already superseded"):
        superseded.supersede(ImplementationId.new())


def test_abandoning_must_say_why() -> None:
    with pytest.raises(ContractViolation, match="must say why"):
        open_record().abandon("   ")


def test_an_abandoned_record_is_immutable_too() -> None:
    abandoned = open_record().abandon("the premise was false")
    assert abandoned.status.is_immutable
    with pytest.raises(RecordCompleted):
        abandoned.note_deviation("late")


def test_only_completed_is_submittable_to_review() -> None:
    """An in-progress record is work in flight; reviewing it would mean reviewing
    something that can still change."""
    assert ImplementationStatus.COMPLETED.is_submittable
    for other in (
        ImplementationStatus.IN_PROGRESS,
        ImplementationStatus.ABANDONED,
        ImplementationStatus.SUPERSEDED,
    ):
        assert not other.is_submittable


# ----------------------------------------------------------------------
# Change set arithmetic
# ----------------------------------------------------------------------


def test_a_deleted_file_needs_no_content_digest_and_an_added_one_does() -> None:
    assert not ChangeKind.DELETED.requires_content_digest
    assert ChangeKind.ADDED.requires_content_digest
    with pytest.raises(ContractViolation):
        ChangedFile(path="a.py", kind=ChangeKind.ADDED, content_digest=None)


def test_a_rename_must_name_where_it_came_from() -> None:
    assert ChangeKind.RENAMED.requires_previous_path
    with pytest.raises(ContractViolation):
        ChangedFile(
            path="b.py",
            kind=ChangeKind.RENAMED,
            content_digest="d",
            previous_path=None,
        )


def test_line_counts_sum_across_the_change_set() -> None:
    record = open_record()
    record = record.record_file(
        changed("backend/contexts/implementation_record/a.py", added=10, removed=2)
    )
    record = record.record_file(
        changed("backend/contexts/implementation_record/b.py", added=5, removed=1)
    )
    assert record.changes.lines_added == 15
    assert record.changes.lines_removed == 3
    assert not record.changes.is_empty


def test_assert_within_names_the_offending_path() -> None:
    scope = type(open_record().blast_radius).of(["backend/**"])
    changes = CodeChangeSet(
        revision=REVISION, files=(changed("frontend/page.tsx"),)
    )
    assert changes.outside(scope) == ("frontend/page.tsx",)
    with pytest.raises(OutsideBlastRadius):
        changes.assert_within(scope)


def test_a_build_result_that_says_passed_with_no_command_is_refused() -> None:
    with pytest.raises(ContractViolation):
        BuildResult(name="gate", command="  ", status=ExecutionStatus.PASSED, revision=REVISION)
