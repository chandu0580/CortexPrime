"""Verification policy: when a verification may be closed, and as what.

The aggregate enforces per-claim invariants. This decides the outcome of the
whole, which is a separate question -- a record where every individual result is
well-formed can still be an inadequate verification.

The rules, and the failure each prevents
-----------------------------------------
**P1 every claim settled.** A verification that reports complete having examined
half the claims is worse than one that reports incomplete, because it looks like
success.

**P2 no contradiction.** Self-evident, and stated so the outcome is derived from
the results rather than chosen by whoever closes the record.

**P3 no unreproducible claim.** A claim nobody could check carries the same risk
as one checked and found false, minus the knowledge that it was.

**P4 evidence strong enough to stand alone.** ``OBSERVED`` evidence -- a real
external system, observed once -- is the most valuable evidence there is for
whether something works, and it cannot be re-established. It may support a claim;
it may not be the *only* support for a gate.

**P5 nothing stale.** Evidence is bound to a commit. When the base moves, what
was collected describes a tree nobody is merging.

**P6 absence claims constructed adversarially.** Enforced per-result by the
aggregate; re-checked here because a result can reach ``OUT_OF_SCOPE`` and then
be counted as covered.

**P7 not superseded.** A superseded verification's outcome is not the current
answer, whatever it says.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from backend.contexts.engineering_verification.domain.claim import ClaimType
from backend.contexts.engineering_verification.domain.evidence import TrustLevel
from backend.contexts.engineering_verification.domain.record import (
    VerificationRecord,
    VerificationStatus,
)
from backend.contexts.engineering_verification.domain.results import ClaimVerdict

__all__ = ["Severity", "PolicyFinding", "PolicyReport", "VerificationPolicy", "default_policy"]


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"

    @property
    def refuses(self) -> bool:
        return self is Severity.BLOCKING


@dataclass(frozen=True)
class PolicyFinding:
    rule: str
    severity: Severity
    detail: str
    subject: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class PolicyReport:
    findings: tuple = ()
    outcome: VerificationStatus = VerificationStatus.COMPLETE

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.refuses)

    @property
    def advisory(self) -> tuple:
        return tuple(f for f in self.findings if not f.severity.refuses)

    @property
    def may_complete(self) -> bool:
        return not self.blocking


class VerificationPolicy:
    """Decides the outcome of a verification from its results."""

    def __init__(self, *, minimum_trust: TrustLevel = TrustLevel.ENVIRONMENTAL) -> None:
        self._minimum_trust = minimum_trust

    @property
    def minimum_trust(self) -> TrustLevel:
        return self._minimum_trust

    def evaluate(
        self, record: VerificationRecord, *, current_commit: Optional[str] = None
    ) -> PolicyReport:
        """Every finding, plus the outcome the record has earned.

        Returns all findings rather than the first. A verifier fixing them one
        round-trip at a time is a verifier that stops bothering.
        """
        findings: list = []

        # P1 -- every claim settled.
        outstanding = record.outstanding_claims
        for claim in outstanding:
            findings.append(
                PolicyFinding(
                    rule="P1-every-claim-settled",
                    severity=Severity.BLOCKING,
                    detail=(
                        "claim was requested but never settled; a verification that "
                        "reports complete having examined only some claims looks "
                        "exactly like success"
                    ),
                    subject=str(claim.claim_id),
                )
            )

        # P2 -- no contradiction.
        for result in record.contradicted:
            findings.append(
                PolicyFinding(
                    rule="P2-no-contradiction",
                    severity=Severity.BLOCKING,
                    detail=f"claim was contradicted: {result.observed}",
                    subject=str(result.claim_id),
                )
            )

        # P3 -- nothing unreproducible.
        for result in record.unreproducible:
            findings.append(
                PolicyFinding(
                    rule="P3-nothing-unreproducible",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"claim could not be reproduced either way: {result.observed}; "
                        "a claim nobody could check carries the same risk as one checked "
                        "and found false"
                    ),
                    subject=str(result.claim_id),
                )
            )

        # P4 -- evidence strong enough to stand alone.
        for result in record.results:
            if result.verdict is ClaimVerdict.OUT_OF_SCOPE:
                continue
            if not result.trust.can_stand_alone:
                findings.append(
                    PolicyFinding(
                        rule="P4-evidence-can-stand-alone",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"the only support is {result.trust.value} evidence, which "
                            "cannot be re-established; it may support a claim but not "
                            "be the sole basis for a gate"
                        ),
                        subject=str(result.claim_id),
                    )
                )
            elif not result.trust.at_least(self._minimum_trust):
                findings.append(
                    PolicyFinding(
                        rule="P4-evidence-can-stand-alone",
                        severity=Severity.ADVISORY,
                        detail=(
                            f"evidence is {result.trust.value}, below the configured "
                            f"floor of {self._minimum_trust.value}"
                        ),
                        subject=str(result.claim_id),
                    )
                )

        # P5 -- nothing stale.
        for result in record.stale_results(current_commit):
            findings.append(
                PolicyFinding(
                    rule="P5-nothing-stale",
                    severity=Severity.BLOCKING,
                    detail=(
                        "evidence was collected against a commit that is no longer the "
                        "base; it describes a tree nobody is merging"
                    ),
                    subject=str(result.claim_id),
                )
            )

        # P6 -- absence claims must have been constructed adversarially, and an
        # absence claim declared out of scope is an absence claim not verified.
        for result in record.results:
            if result.claim.claim_type is not ClaimType.ABSENCE:
                continue
            if result.verdict is ClaimVerdict.OUT_OF_SCOPE:
                findings.append(
                    PolicyFinding(
                        rule="P6-absence-constructed",
                        severity=Severity.BLOCKING,
                        detail=(
                            "an absence claim was declared out of scope; the claim that "
                            "something cannot happen is exactly the one that must be "
                            "attacked rather than deferred"
                        ),
                        subject=str(result.claim_id),
                    )
                )

        # P7 -- not superseded.
        if record.superseded_by is not None:
            findings.append(
                PolicyFinding(
                    rule="P7-not-superseded",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"superseded by {record.superseded_by}; this outcome is not the "
                        "current answer whatever it says"
                    ),
                    subject=str(record.verification_id),
                )
            )

        return PolicyReport(findings=tuple(findings), outcome=self._outcome(record, findings))

    # ------------------------------------------------------------------

    @staticmethod
    def _outcome(record: VerificationRecord, findings: Sequence[PolicyFinding]) -> VerificationStatus:
        """The status this record has earned.

        Ordering matters and encodes what a reader most needs to know. A
        contradiction outranks an unreproducible claim, because "the work is
        wrong" is more actionable than "we could not tell". Both outrank an
        unsettled claim, because a known bad answer beats a missing one.
        """
        if record.contradicted:
            return VerificationStatus.FAILED
        if record.unreproducible:
            return VerificationStatus.INCOMPLETE
        if record.outstanding_claims:
            return VerificationStatus.INCOMPLETE
        if any(f.severity.refuses for f in findings):
            return VerificationStatus.INCOMPLETE
        return VerificationStatus.COMPLETE


def default_policy() -> VerificationPolicy:
    """The policy the Engineering Constitution defines."""
    return VerificationPolicy(minimum_trust=TrustLevel.ENVIRONMENTAL)
