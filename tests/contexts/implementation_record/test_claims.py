"""Claims, assumption resolutions, risks, coverage -- and the vocabulary drift test.

The central rule of this file: **a claim with no evidence cannot be
constructed.** Not "is flagged", not "fails policy" -- refused at the
constructor, so no code path anywhere can produce one. A claim a verifier cannot
attack can only be taken on trust, which is the one thing verification exists not
to do.

The drift test guards the second deliberate duplication in this PR: ``ClaimType``
mirrors the Verification context's five values without importing them, because S2
forbids one bounded context importing another. A vocabulary that silently gained
a sixth value on one side would let an implementer make a claim the verifier has
no rule for.
"""

from __future__ import annotations

import pytest

from backend.contexts.engineering_verification.domain.claim import (
    ClaimType as VerificationClaimType,
)
from backend.contexts.implementation_record.domain.claims import (
    AssumptionOutcome,
    AssumptionResolution,
    Claim,
    ClaimType,
    CriterionCoverage,
    EvidenceRef,
    RiskDeclaration,
    RiskLevel,
)
from backend.contexts.implementation_record.domain.errors import ClaimWithoutEvidence
from backend.contracts.errors import ContractViolation


# ----------------------------------------------------------------------
# The drift test
# ----------------------------------------------------------------------


def test_claim_type_vocabulary_matches_the_verification_context() -> None:
    """The two enums must carry exactly the same values.

    Duplication with a checked invariant beats duplication without one. If either
    side gains, loses, or renames a value, this fails and the other side has to
    be updated deliberately rather than discovered in production.
    """
    ours = {member.value for member in ClaimType}
    theirs = {member.value for member in VerificationClaimType}
    assert ours == theirs, (
        "ClaimType vocabularies have drifted: implementation_record has "
        f"{sorted(ours - theirs)} that Verification does not, and Verification has "
        f"{sorted(theirs - ours)} that implementation_record does not"
    )


def test_every_claim_type_survives_the_round_trip_to_verification() -> None:
    """Not just equal sets -- each value must construct on the other side.

    Equal ``.value`` sets could still fail if the member names diverged and
    something reconstructed by name.
    """
    for member in ClaimType:
        assert VerificationClaimType(member.value).value == member.value
        assert VerificationClaimType[member.name].value == member.value


def test_the_two_contexts_agree_on_which_claim_needs_adversarial_work() -> None:
    """``ABSENCE`` on both sides, or the flag means different things.

    This context flags it so the implementer knows what it is asking for;
    Verification enforces it. Disagreement would let a claim be flagged as easy
    here and refused as adversarial there.
    """
    ours = {m.value for m in ClaimType if m.needs_adversarial_verification}
    theirs = {m.value for m in VerificationClaimType if m.required_method is not None}
    assert ours == theirs == {"absence"}


def test_the_two_contexts_agree_on_which_claim_is_easily_wrong() -> None:
    ours = {m.value for m in ClaimType if m.is_easily_wrong}
    theirs = {
        m.value for m in VerificationClaimType if m.demands_independent_measurement
    }
    assert ours == theirs == {"count"}


# ----------------------------------------------------------------------
# Claim
# ----------------------------------------------------------------------


def test_a_claim_without_evidence_cannot_be_constructed() -> None:
    with pytest.raises(ClaimWithoutEvidence):
        Claim.create("the router retries on 429", ClaimType.BEHAVIOUR, [])


def test_a_claim_without_evidence_cannot_be_smuggled_past_the_factory() -> None:
    """The constructor refuses too, not only the ``create`` helper.

    A rule enforced only at the convenience path is enforced only for callers who
    use it.
    """
    from backend.contexts.implementation_record.domain.identifiers import ClaimId

    with pytest.raises(ClaimWithoutEvidence):
        Claim(
            claim_id=ClaimId.new(),
            statement="the router retries on 429",
            claim_type=ClaimType.BEHAVIOUR,
            evidence=frozenset(),
        )


def test_a_claim_with_evidence_records_the_references_sorted() -> None:
    made = Claim.create("counts nine detectors", ClaimType.COUNT, ["EV-9", "EV-1"])
    assert made.evidence_ids == ("EV-1", "EV-9")
    assert made.claim_type is ClaimType.COUNT


def test_evidence_references_are_opaque_and_carry_no_trust() -> None:
    """``EvidenceRef`` has one field. That is the point.

    A trust level here would be the implementer grading its own evidence.
    Verification produces its own ``VerifiedEvidence`` and there is no conversion
    (ADR-021).
    """
    ref = EvidenceRef("EV-1")
    assert [f for f in ref.__dataclass_fields__] == ["value"]
    assert str(ref) == "EV-1"


@pytest.mark.parametrize("bad", ["", "   ", " EV-1", "EV-1 "])
def test_blank_or_padded_evidence_references_are_refused(bad: str) -> None:
    with pytest.raises(ContractViolation):
        EvidenceRef(bad)


def test_a_claim_must_state_something() -> None:
    for blank in ("", "   "):
        with pytest.raises(ContractViolation, match="must state something"):
            Claim.create(blank, ClaimType.BEHAVIOUR, ["EV-1"])


# ----------------------------------------------------------------------
# Assumption resolutions
# ----------------------------------------------------------------------


def test_only_confirmed_permits_completion() -> None:
    assert AssumptionOutcome.CONFIRMED.permits_completion
    assert not AssumptionOutcome.CONTRADICTED.permits_completion
    assert not AssumptionOutcome.UNVERIFIABLE.permits_completion


def test_only_contradicted_implies_a_premise_false_rejection() -> None:
    """``UNVERIFIABLE`` blocks but does not imply the premise was false.

    They call for different responses: a contradicted premise means reject the
    WorkOrder; an unverifiable one means go find out.
    """
    assert AssumptionOutcome.CONTRADICTED.implies_rejection
    assert not AssumptionOutcome.UNVERIFIABLE.implies_rejection


def test_unverifiable_must_still_cite_what_was_tried() -> None:
    """Otherwise it is indistinguishable from not having looked."""
    with pytest.raises(ContractViolation, match="must cite what was checked"):
        AssumptionResolution.create(
            "A1", "the store is append-only", AssumptionOutcome.UNVERIFIABLE, []
        )


def test_a_resolution_records_its_evidence_and_outcome() -> None:
    resolved = AssumptionResolution.create(
        "A1", "the store is append-only", AssumptionOutcome.CONFIRMED, ["EV-3"]
    )
    assert resolved.permits_completion
    assert {str(e) for e in resolved.evidence} == {"EV-3"}
    assert resolved.resolved_at.tzinfo is not None


# ----------------------------------------------------------------------
# Risks
# ----------------------------------------------------------------------


def test_a_risk_above_low_must_state_its_mitigation() -> None:
    """A risk declared and left unaddressed is a note, not a decision."""
    for level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
        with pytest.raises(ContractViolation, match="must state its mitigation"):
            RiskDeclaration.create("the migration may lock the table", level)


def test_a_low_risk_needs_no_mitigation() -> None:
    declared = RiskDeclaration.create("log volume rises slightly", RiskLevel.LOW)
    assert declared.mitigation is None
    assert not declared.level.requires_mitigation


def test_risk_levels_rank_in_the_order_they_read() -> None:
    assert RiskLevel.LOW.rank < RiskLevel.MEDIUM.rank < RiskLevel.HIGH.rank


# ----------------------------------------------------------------------
# Criterion coverage
# ----------------------------------------------------------------------


def test_coverage_claiming_no_test_is_refused() -> None:
    """An uncovered criterion recorded as covered is worse than one left out."""
    with pytest.raises(ContractViolation, match="names no test"):
        CriterionCoverage(criterion="records are immutable after completion")


def test_the_absence_of_a_negative_check_is_visible_rather_than_assumed() -> None:
    without = CriterionCoverage(
        criterion="claims cite evidence", covering_tests=("test_claims.py",)
    )
    with_check = CriterionCoverage(
        criterion="claims cite evidence",
        covering_tests=("test_claims.py",),
        negative_check="fails on the pre-change tree",
    )
    assert not without.has_negative_check
    assert with_check.has_negative_check
