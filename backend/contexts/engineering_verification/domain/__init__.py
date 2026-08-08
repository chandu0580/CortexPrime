"""Verification domain: claims, evidence, results, and the record that holds them.

Pure. No I/O, no persistence, no framework.
"""

from backend.contexts.engineering_verification.domain.claim import (
    Claim, ClaimType, Determinism, ReproductionMethod, ReproductionStep,
)
from backend.contexts.engineering_verification.domain.errors import (
    BorrowedEvidence, ClaimAlreadyResolved, ClaimNotRequested, DuplicateVerification,
    EvidenceNotAdmissible, InvalidIdentifier, PolicyRefused, ReproductionInadequate,
    StaleBaseCommit, VerificationAlreadyClosed, VerificationError, VerificationNotFound,
    VerificationNotStarted,
)
from backend.contexts.engineering_verification.domain.events import (
    VERIFICATION_EVENT_TYPES, VerificationEvidenceAdded, VerificationFailed,
    VerificationRequested, VerificationStarted, VerificationSucceeded, VerificationSuperseded,
)
from backend.contexts.engineering_verification.domain.evidence import (
    AssertedEvidenceRef, EvidenceKind, TrustLevel, VerifiedEvidence,
)
from backend.contexts.engineering_verification.domain.factory import (
    claim, contradicted, evidence, reproduced, reproduction, request_verification,
)
from backend.contexts.engineering_verification.domain.identifiers import (
    ClaimId, EvidenceId, VerificationId,
)
from backend.contexts.engineering_verification.domain.policy import (
    PolicyFinding, PolicyReport, Severity, VerificationPolicy, default_policy,
)
from backend.contexts.engineering_verification.domain.record import (
    VerificationRecord, VerificationRequest, VerificationStatus,
)
from backend.contexts.engineering_verification.domain.results import ClaimResult, ClaimVerdict

__all__ = [
    "VerificationRecord", "VerificationRequest", "VerificationStatus",
    "Claim", "ClaimType", "ClaimId", "ClaimResult", "ClaimVerdict",
    "ReproductionStep", "ReproductionMethod", "Determinism",
    "VerifiedEvidence", "AssertedEvidenceRef", "EvidenceKind", "TrustLevel", "EvidenceId",
    "VerificationId", "VerificationPolicy", "PolicyReport", "PolicyFinding", "Severity",
    "default_policy",
    "claim", "evidence", "reproduction", "request_verification", "reproduced", "contradicted",
    "VerificationRequested", "VerificationStarted", "VerificationSucceeded",
    "VerificationFailed", "VerificationEvidenceAdded", "VerificationSuperseded",
    "VERIFICATION_EVENT_TYPES",
    "VerificationError", "InvalidIdentifier", "EvidenceNotAdmissible", "BorrowedEvidence",
    "ClaimNotRequested", "ClaimAlreadyResolved", "ReproductionInadequate",
    "VerificationNotStarted", "VerificationAlreadyClosed", "PolicyRefused",
    "VerificationNotFound", "DuplicateVerification", "StaleBaseCommit",
]
