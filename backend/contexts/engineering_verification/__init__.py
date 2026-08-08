"""The Verification bounded context.

Independently validates engineering claims. It never trusts an implementation
summary, a review summary, or a test summary -- it reproduces.

The central rule is expressed in the type system rather than in a check: what the
implementer points at (``AssertedEvidenceRef``) and what the verifier produces
(``VerifiedEvidence``) are different types with no conversion between them. A
``ClaimResult`` requires the latter, so "verification" that re-points at the
implementer's artifact does not type-check.

    domain/          pure -- claims, evidence, results, policy
    application/     commands, queries, the service
    infrastructure/  repository, record mapping

Named ``engineering_verification`` rather than ``verification`` because
``verification`` is already one of the product's nine bounded contexts (BC-4,
"did the fix actually work?"). Squatting that namespace would leave BC-4 nowhere
to go. See ADR-021.

This context imports ``contracts/`` and ``platform/`` and nothing else.
"""

from backend.contexts.engineering_verification.application import (
    AddEvidence, ClaimInput, CloseVerification, CommandResult, GetOutcome, GetVerification,
    ListVerifications, MarkStale, RecordClaimResult, RequestVerification, StartVerification,
    SupersedeVerification, VerificationService,
)
from backend.contexts.engineering_verification.domain import (
    AssertedEvidenceRef, Claim, ClaimId, ClaimResult, ClaimType, ClaimVerdict, Determinism,
    EvidenceId, EvidenceKind, PolicyFinding, PolicyReport, ReproductionMethod,
    ReproductionStep, Severity, TrustLevel, VERIFICATION_EVENT_TYPES, VerificationError,
    VerificationEvidenceAdded, VerificationFailed, VerificationId, VerificationPolicy,
    VerificationRecord, VerificationRequest, VerificationRequested, VerificationStarted,
    VerificationStatus, VerificationSucceeded, VerificationSuperseded, VerifiedEvidence,
    BorrowedEvidence, ClaimAlreadyResolved, ClaimNotRequested, DuplicateVerification,
    ReproductionInadequate, VerificationAlreadyClosed, VerificationNotFound,
    VerificationNotStarted, claim, contradicted, default_policy, evidence, reproduced,
    reproduction, request_verification,
)
from backend.contexts.engineering_verification.infrastructure import (
    InMemoryVerificationRepository, VerificationRepository,
)

__all__ = [
    "VerificationService", "CommandResult",
    "VerificationRecord", "VerificationRequest", "VerificationStatus", "VerificationId",
    "Claim", "ClaimId", "ClaimType", "ClaimResult", "ClaimVerdict",
    "ReproductionStep", "ReproductionMethod", "Determinism",
    "VerifiedEvidence", "AssertedEvidenceRef", "EvidenceKind", "TrustLevel", "EvidenceId",
    "VerificationPolicy", "PolicyReport", "PolicyFinding", "Severity", "default_policy",
    "claim", "evidence", "reproduction", "request_verification", "reproduced", "contradicted",
    "ClaimInput", "RequestVerification", "StartVerification", "RecordClaimResult",
    "AddEvidence", "CloseVerification", "SupersedeVerification", "MarkStale",
    "GetVerification", "ListVerifications", "GetOutcome",
    "VerificationRepository", "InMemoryVerificationRepository",
    "VerificationRequested", "VerificationStarted", "VerificationSucceeded",
    "VerificationFailed", "VerificationEvidenceAdded", "VerificationSuperseded",
    "VERIFICATION_EVENT_TYPES",
    "VerificationError", "BorrowedEvidence", "ClaimNotRequested", "ClaimAlreadyResolved",
    "ReproductionInadequate", "VerificationNotStarted", "VerificationAlreadyClosed",
    "VerificationNotFound", "DuplicateVerification",
]
