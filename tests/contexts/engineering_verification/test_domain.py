"""Domain invariants.

The tests that matter most are the ones asserting a refusal. A verifier whose
tests only demonstrate successful verification has not been shown to verify
anything.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.engineering_verification import (
    AssertedEvidenceRef,
    BorrowedEvidence,
    ClaimAlreadyResolved,
    ClaimNotRequested,
    ClaimResult,
    ClaimType,
    ClaimVerdict,
    Determinism,
    EvidenceKind,
    ReproductionInadequate,
    ReproductionMethod,
    ReproductionStep,
    TrustLevel,
    VerificationAlreadyClosed,
    VerificationId,
    VerificationNotStarted,
    VerificationStatus,
    VerifiedEvidence,
    claim,
    contradicted,
    evidence,
    reproduced,
    reproduction,
    request_verification,
)

from tests.contexts.engineering_verification.conftest import (
    BASE,
    adversarial_step,
    command_step,
    running,
)


# ----------------------------------------------------------------------
# Trust levels
# ----------------------------------------------------------------------


def test_asserted_is_never_admissible():
    """It names the absence of evidence and exists only to be refused."""
    assert not TrustLevel.ASSERTED.is_admissible
    assert all(t.is_admissible for t in TrustLevel if t is not TrustLevel.ASSERTED)


def test_observed_may_support_but_not_stand_alone():
    """The most valuable evidence there is, and it cannot be re-established."""
    assert TrustLevel.OBSERVED.is_admissible
    assert not TrustLevel.OBSERVED.can_stand_alone
    assert TrustLevel.ENVIRONMENTAL.can_stand_alone
    assert TrustLevel.DETERMINISTIC.can_stand_alone


def test_trust_levels_are_ordered():
    order = [TrustLevel.ASSERTED, TrustLevel.OBSERVED, TrustLevel.ENVIRONMENTAL, TrustLevel.DETERMINISTIC]
    assert [t.rank for t in order] == sorted(t.rank for t in order)


# ----------------------------------------------------------------------
# Evidence
# ----------------------------------------------------------------------


def test_verified_evidence_cannot_be_asserted():
    with pytest.raises(ContractViolation) as caught:
        evidence("nothing was checked", trust=TrustLevel.ASSERTED)
    assert "absence of evidence" in str(caught.value)


def test_evidence_bound_to_a_tree_must_name_the_commit():
    for kind in (EvidenceKind.REPOSITORY, EvidenceKind.COMMAND, EvidenceKind.TEST):
        with pytest.raises(ContractViolation):
            evidence("something", kind=kind, base_commit=None)


def test_external_evidence_cannot_claim_reproducibility():
    """The external system has moved on; nobody can re-establish what it said."""
    with pytest.raises(ContractViolation) as caught:
        evidence("Jira issue SCRUM-24 exists", kind=EvidenceKind.EXTERNAL, trust=TrustLevel.DETERMINISTIC)
    assert "moved on" in str(caught.value)


def test_external_evidence_at_observed_is_fine():
    item = evidence("Jira SCRUM-24 exists", kind=EvidenceKind.EXTERNAL, trust=TrustLevel.OBSERVED)
    assert item.trust is TrustLevel.OBSERVED


def test_evidence_staleness_is_commit_bound():
    item = evidence("ran the suite", kind=EvidenceKind.COMMAND, base_commit="aaa")
    assert item.stale_against("bbb")
    assert not item.stale_against("aaa")
    assert not item.stale_against(None)


def test_evidence_not_bound_to_a_tree_is_never_stale():
    """An ADR citation does not stop being true because the tree moved."""
    item = evidence("ADR-018 says organizations are not an isolation boundary", kind=EvidenceKind.ADR)
    assert not item.stale_against("anything")


def test_evidence_must_say_who_collected_it_and_what_was_seen():
    with pytest.raises(ContractViolation):
        evidence("   ", base_commit=BASE)


# ----------------------------------------------------------------------
# The type separation
# ----------------------------------------------------------------------


def test_the_implementers_reference_is_a_different_type():
    """No conversion exists, so a result cannot be built from one."""
    reference = AssertedEvidenceRef("EV-implementer-1")
    assert not isinstance(reference, VerifiedEvidence)


def test_a_result_refuses_an_implementers_reference():
    target = claim("x holds", ClaimType.BEHAVIOUR)
    with pytest.raises(ContractViolation):
        ClaimResult(
            claim=target,
            reproduction=command_step(),
            observed="looked fine",
            verdict=ClaimVerdict.REPRODUCED,
            verdict_evidence=AssertedEvidenceRef("EV-1"),  # type: ignore[arg-type]
        )


def test_wrapping_the_implementers_id_in_new_evidence_is_refused():
    """The obvious way around the type separation, so it is checked explicitly."""
    borrowed_id = VerificationId.new().value
    target = claim("x holds", ClaimType.BEHAVIOUR, asserted_evidence=(borrowed_id,))

    from backend.contexts.engineering_verification.domain.identifiers import EvidenceId

    laundered = VerifiedEvidence(
        evidence_id=EvidenceId(borrowed_id),
        kind=EvidenceKind.COMMAND,
        trust=TrustLevel.ENVIRONMENTAL,
        summary="pretending to have collected this",
        collected_by="verifier",
        base_commit=BASE,
    )
    with pytest.raises(BorrowedEvidence):
        reproduced(target, command_step(), "looked fine", laundered)


# ----------------------------------------------------------------------
# Reproduction adequacy
# ----------------------------------------------------------------------


def test_an_absence_claim_cannot_be_settled_by_a_green_suite():
    """Running the suite shows nothing tried; it says nothing about what could."""
    target = claim("no cross-tenant read is possible", ClaimType.ABSENCE)
    item = evidence("pytest tests/ -q -> 312 passed", base_commit=BASE)

    with pytest.raises(ReproductionInadequate) as caught:
        reproduced(target, command_step("pytest tests/ -q"), "all green", item)
    assert "adversarial_construction" in str(caught.value)


def test_an_absence_claim_settled_by_construction_is_accepted():
    target = claim("no cross-tenant read is possible", ClaimType.ABSENCE)
    item = evidence("built a foreign-tenant row; CrossTenantAccess raised", base_commit=BASE)
    result = reproduced(target, adversarial_step(), "raised CrossTenantAccess", item)
    assert result.verdict is ClaimVerdict.REPRODUCED


def test_a_behaviour_claim_may_be_settled_several_ways():
    """Forcing one method where several work is how rules get worked around."""
    target = claim("the guard refuses an uncontexted read", ClaimType.BEHAVIOUR)
    item = evidence("ran it", base_commit=BASE)
    for method in ReproductionMethod:
        step = reproduction("did the thing", method)
        assert reproduced(target, step, "it refused", item).verdict is ClaimVerdict.REPRODUCED


def test_a_nondeterministic_reproduction_cannot_prove_a_claim():
    """A flaky proof is not a proof."""
    target = claim("x holds", ClaimType.BEHAVIOUR)
    item = evidence("ran it five times, three agreed", base_commit=BASE)
    flaky = reproduction("pytest -k flaky", ReproductionMethod.COMMAND_EXECUTION,
                         determinism=Determinism.NONDETERMINISTIC, runs=5)

    with pytest.raises(ContractViolation) as caught:
        reproduced(target, flaky, "sometimes passes", item)
    assert "repeated runs disagreed" in str(caught.value)


def test_a_nondeterministic_reproduction_may_report_unreproducible():
    """Which is the honest verdict for it."""
    target = claim("x holds", ClaimType.BEHAVIOUR)
    item = evidence("ran it five times, three agreed", base_commit=BASE)
    flaky = reproduction("pytest -k flaky", determinism=Determinism.NONDETERMINISTIC, runs=5)

    result = ClaimResult(
        claim=target, reproduction=flaky, observed="results disagreed",
        verdict=ClaimVerdict.UNREPRODUCIBLE, verdict_evidence=item,
    )
    assert result.verdict is ClaimVerdict.UNREPRODUCIBLE


def test_a_reproduction_must_state_what_was_done():
    with pytest.raises(ContractViolation) as caught:
        reproduction("   ")
    assert "not a reproduction" in str(caught.value)


# ----------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------


def test_a_verdict_must_carry_evidence():
    target = claim("x holds", ClaimType.BEHAVIOUR)
    with pytest.raises(ContractViolation):
        ClaimResult(
            claim=target, reproduction=command_step(), observed="fine",
            verdict=ClaimVerdict.REPRODUCED,
        )


def test_a_verdict_must_state_what_was_observed():
    target = claim("x holds", ClaimType.BEHAVIOUR)
    with pytest.raises(ContractViolation) as caught:
        reproduced(target, command_step(), "   ", evidence("ran it", base_commit=BASE))
    assert "is an opinion" in str(caught.value)


def test_out_of_scope_needs_a_reason_and_no_evidence():
    target = claim("x holds", ClaimType.BEHAVIOUR)
    with pytest.raises(ContractViolation):
        ClaimResult(
            claim=target, reproduction=command_step(), observed="not examined",
            verdict=ClaimVerdict.OUT_OF_SCOPE,
        )

    fine = ClaimResult(
        claim=target, reproduction=command_step(), observed="not examined",
        verdict=ClaimVerdict.OUT_OF_SCOPE, note="belongs to the Review context",
    )
    assert fine.verdict_evidence is None


def test_unreproducible_does_not_permit_completion():
    """Same risk as a contradiction, minus the knowledge that it was."""
    assert not ClaimVerdict.UNREPRODUCIBLE.permits_completion
    assert not ClaimVerdict.CONTRADICTED.permits_completion
    assert ClaimVerdict.REPRODUCED.permits_completion
    assert ClaimVerdict.OUT_OF_SCOPE.permits_completion


# ----------------------------------------------------------------------
# The aggregate
# ----------------------------------------------------------------------


def test_a_request_with_no_claims_is_refused():
    """Verifying nothing would report complete having established nothing."""
    with pytest.raises(ContractViolation) as caught:
        request_verification("WO-1", [], base_commit=BASE)
    assert "established nothing" in str(caught.value)


def test_a_request_requires_a_base_commit():
    with pytest.raises(ContractViolation):
        request_verification("WO-1", [claim("x", ClaimType.BEHAVIOUR)], base_commit="  ")


def test_results_cannot_be_recorded_before_starting():
    record = request_verification("WO-1", [claim("x", ClaimType.BEHAVIOUR)], base_commit=BASE)
    target = record.request.claims[0]
    with pytest.raises(VerificationNotStarted):
        record.record(reproduced(target, command_step(), "ok", evidence("ran", base_commit=BASE)))


def test_a_verifier_must_be_named():
    record = request_verification("WO-1", [claim("x", ClaimType.BEHAVIOUR)], base_commit=BASE)
    with pytest.raises(ContractViolation):
        record.start("   ")


def test_a_result_for_an_unrequested_claim_is_refused():
    target = claim("in the request", ClaimType.BEHAVIOUR)
    stranger = claim("never requested", ClaimType.BEHAVIOUR)
    record = running(target)

    with pytest.raises(ClaimNotRequested):
        record.record(reproduced(stranger, command_step(), "ok", evidence("ran", base_commit=BASE)))


def test_a_second_verdict_on_a_settled_claim_is_refused():
    """Two answers means one is wrong; keeping the later destroys the first."""
    target = claim("x holds", ClaimType.BEHAVIOUR)
    item = evidence("ran it", base_commit=BASE)
    record = running(target).record(reproduced(target, command_step(), "ok", item))

    with pytest.raises(ClaimAlreadyResolved):
        record.record(contradicted(target, command_step(), "actually not", evidence("ran again", base_commit=BASE)))


def test_a_closed_verification_accepts_nothing_further():
    target = claim("x holds", ClaimType.BEHAVIOUR)
    item = evidence("ran it", base_commit=BASE)
    record = running(target).record(reproduced(target, command_step(), "ok", item))
    closed = record.close(VerificationStatus.COMPLETE)

    with pytest.raises(VerificationAlreadyClosed):
        closed.record(reproduced(target, command_step(), "ok", item))
    with pytest.raises(VerificationAlreadyClosed):
        closed.start("someone else")


def test_closing_as_anything_but_complete_must_say_why():
    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target)
    with pytest.raises(ContractViolation) as caught:
        record.close(VerificationStatus.FAILED)
    assert "must say why" in str(caught.value)


def test_a_non_closing_status_cannot_close():
    record = running(claim("x", ClaimType.BEHAVIOUR))
    with pytest.raises(ContractViolation):
        record.close(VerificationStatus.RUNNING)


def test_outstanding_claims_are_tracked():
    first = claim("one", ClaimType.BEHAVIOUR)
    second = claim("two", ClaimType.BEHAVIOUR)
    record = running(first, second)
    assert len(record.outstanding_claims) == 2

    record = record.record(reproduced(first, command_step(), "ok", evidence("ran", base_commit=BASE)))
    assert [str(c.claim_id) for c in record.outstanding_claims] == [str(second.claim_id)]


def test_weakest_trust_is_the_floor():
    strong = claim("one", ClaimType.BEHAVIOUR)
    weak = claim("two", ClaimType.BEHAVIOUR)
    record = (
        running(strong, weak)
        .record(reproduced(strong, command_step(), "ok",
                           evidence("ran", trust=TrustLevel.DETERMINISTIC, base_commit=BASE)))
        .record(reproduced(weak, command_step(), "ok",
                           evidence("saw it once", kind=EvidenceKind.EXTERNAL, trust=TrustLevel.OBSERVED)))
    )
    assert record.weakest_trust is TrustLevel.OBSERVED


def test_out_of_scope_results_are_excluded_from_the_trust_floor():
    """They carry no evidence because nothing was examined."""
    examined = claim("one", ClaimType.BEHAVIOUR)
    skipped = claim("two", ClaimType.BEHAVIOUR)
    record = (
        running(examined, skipped)
        .record(reproduced(examined, command_step(), "ok",
                           evidence("ran", trust=TrustLevel.DETERMINISTIC, base_commit=BASE)))
        .record(ClaimResult(claim=skipped, reproduction=command_step(), observed="not examined",
                            verdict=ClaimVerdict.OUT_OF_SCOPE, note="belongs to Review"))
    )
    assert record.weakest_trust is TrustLevel.DETERMINISTIC


def test_marking_stale_is_not_terminal():
    """Stale means 'ask again', not 'the answer was no'."""
    record = running(claim("x", ClaimType.BEHAVIOUR)).mark_stale("newcommit")
    assert record.status is VerificationStatus.STALE
    assert not record.status.is_terminal
    assert "must be reproduced" in record.closing_note


def test_only_complete_permits_ready():
    assert VerificationStatus.COMPLETE.permits_ready
    for status in VerificationStatus:
        if status is not VerificationStatus.COMPLETE:
            assert not status.permits_ready


def test_supersede_refuses_self_and_a_second_successor():
    record = running(claim("x", ClaimType.BEHAVIOUR))
    with pytest.raises(ContractViolation):
        record.supersede(record.verification_id)

    superseded = record.supersede(VerificationId.new())
    with pytest.raises(ContractViolation):
        superseded.supersede(VerificationId.new())


def test_transitions_return_new_instances():
    record = request_verification("WO-1", [claim("x", ClaimType.BEHAVIOUR)], base_commit=BASE)
    started = record.start("verifier-1")
    assert record.status is VerificationStatus.REQUESTED
    assert started.status is VerificationStatus.RUNNING
    assert record is not started
