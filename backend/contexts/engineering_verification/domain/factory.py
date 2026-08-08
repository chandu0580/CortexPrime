"""Construction helpers.

The aggregate's constructor takes strongly-typed values and enforces every
invariant, which is correct and verbose. These are the ergonomic paths in, and
they exist so the common cases cannot be built wrong: a claim always gets its
type, evidence always gets its collection method, and a request always gets a
base commit.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from backend.contexts.engineering_verification.domain.claim import (
    Claim,
    ClaimType,
    Determinism,
    ReproductionMethod,
    ReproductionStep,
)
from backend.contexts.engineering_verification.domain.evidence import (
    EvidenceKind,
    TrustLevel,
    VerifiedEvidence,
)
from backend.contexts.engineering_verification.domain.identifiers import VerificationId
from backend.contexts.engineering_verification.domain.record import (
    VerificationRecord,
    VerificationRequest,
)
from backend.contexts.engineering_verification.domain.results import ClaimResult, ClaimVerdict

__all__ = ["claim", "evidence", "reproduction", "request_verification", "reproduced", "contradicted"]


def claim(
    statement: str,
    claim_type: ClaimType = ClaimType.BEHAVIOUR,
    *,
    asserted_evidence: Sequence[str] = (),
    hint: Optional[str] = None,
) -> Claim:
    return Claim.create(
        statement,
        claim_type,
        asserted_evidence=tuple(asserted_evidence),
        reproduction_hint=hint,
    )


def evidence(
    summary: str,
    *,
    kind: EvidenceKind = EvidenceKind.COMMAND,
    trust: TrustLevel = TrustLevel.ENVIRONMENTAL,
    base_commit: Optional[str] = None,
    collected_by: str = "verifier",
    detail: Optional[str] = None,
) -> VerifiedEvidence:
    return VerifiedEvidence.create(
        kind, trust, summary, collected_by=collected_by, base_commit=base_commit, detail=detail
    )


def reproduction(
    specification: str,
    method: ReproductionMethod = ReproductionMethod.COMMAND_EXECUTION,
    *,
    determinism: Determinism = Determinism.DETERMINISTIC,
    runs: int = 1,
) -> ReproductionStep:
    return ReproductionStep(
        method=method, specification=specification, determinism=determinism, runs=runs
    )


def request_verification(
    work_id: str,
    claims: Iterable[Claim],
    *,
    attempt: int = 1,
    base_commit: str,
    requested_by: str = "engineering-runtime",
) -> VerificationRecord:
    """A fresh record in REQUESTED status."""
    return VerificationRecord(
        verification_id=VerificationId.new(),
        request=VerificationRequest(
            work_id=work_id,
            attempt=attempt,
            claims=tuple(claims),
            base_commit=base_commit,
            requested_by=requested_by,
        ),
    )


def reproduced(
    target: Claim,
    step: ReproductionStep,
    observed: str,
    verdict_evidence: VerifiedEvidence,
) -> ClaimResult:
    return ClaimResult(
        claim=target,
        reproduction=step,
        observed=observed,
        verdict=ClaimVerdict.REPRODUCED,
        verdict_evidence=verdict_evidence,
    )


def contradicted(
    target: Claim,
    step: ReproductionStep,
    observed: str,
    verdict_evidence: VerifiedEvidence,
) -> ClaimResult:
    return ClaimResult(
        claim=target,
        reproduction=step,
        observed=observed,
        verdict=ClaimVerdict.CONTRADICTED,
        verdict_evidence=verdict_evidence,
    )
