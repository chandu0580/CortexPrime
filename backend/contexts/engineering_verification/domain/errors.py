"""Failures raised by the Verification context.

Every one is a refusal. Verification never downgrades a contradiction to a
warning, never accepts a claim it could not reproduce, and never fills a missing
result with a default. A verifier that can be talked into "probably fine" is not
a verifier.
"""

from __future__ import annotations

from typing import Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "VerificationError",
    "InvalidIdentifier",
    "EvidenceNotAdmissible",
    "BorrowedEvidence",
    "ClaimNotRequested",
    "ClaimAlreadyResolved",
    "ReproductionInadequate",
    "VerificationNotStarted",
    "VerificationAlreadyClosed",
    "PolicyRefused",
    "VerificationNotFound",
    "DuplicateVerification",
    "StaleBaseCommit",
]


class VerificationError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(VerificationError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class EvidenceNotAdmissible(VerificationError):
    """Evidence too weak to support the claim resting on it.

    The trust level of the weakest supporting evidence bounds the strength of any
    claim built on it. ``ASSERTED`` -- no evidence collected -- is never
    admissible anywhere.
    """

    def __init__(self, *, evidence_id: str, trust: str, required: str, reason: str) -> None:
        super().__init__(
            f"evidence {evidence_id} is {trust} but {required} is required: {reason}"
        )
        self.evidence_id = evidence_id
        self.trust = trust
        self.required = required


class BorrowedEvidence(VerificationError):
    """The verifier reused the implementer's evidence instead of producing its own.

    This is not verification; it is agreement. Reproducing a claim means
    generating new evidence that the claim holds -- pointing at the same artifact
    the implementer pointed at demonstrates only that the pointer still resolves.
    """

    def __init__(self, *, claim_id: str, evidence_id: str) -> None:
        super().__init__(
            f"claim {claim_id}: verdict evidence {evidence_id} is the implementer's own "
            "asserted evidence; verification must produce its own"
        )
        self.claim_id = claim_id
        self.evidence_id = evidence_id


class ClaimNotRequested(VerificationError):
    def __init__(self, *, claim_id: str, verification_id: str) -> None:
        super().__init__(
            f"claim {claim_id} was not part of verification {verification_id}; "
            "a result for an unrequested claim verifies nothing"
        )
        self.claim_id = claim_id


class ClaimAlreadyResolved(VerificationError):
    """A second verdict on a settled claim.

    Refused rather than overwritten. Two answers to the same question means one
    is wrong, and silently keeping the later one destroys the evidence of the
    first.
    """

    def __init__(self, *, claim_id: str, verdict: str) -> None:
        super().__init__(
            f"claim {claim_id} is already {verdict}; a second verdict would overwrite "
            "the first"
        )
        self.claim_id = claim_id
        self.verdict = verdict


class ReproductionInadequate(VerificationError):
    """The method used cannot establish what the claim asserts.

    An absence claim is the clear case: running the suite and seeing green does
    not show that something is impossible. Only constructing the violation and
    observing refusal does.
    """

    def __init__(self, *, claim_id: str, claim_type: str, method: str, required: str) -> None:
        super().__init__(
            f"claim {claim_id} is a {claim_type} claim reproduced by {method}; "
            f"{required} is required -- the method used cannot establish what the "
            "claim asserts"
        )
        self.claim_id = claim_id
        self.claim_type = claim_type
        self.method = method
        self.required = required


class VerificationNotStarted(VerificationError):
    def __init__(self, verification_id: str) -> None:
        super().__init__(
            f"verification {verification_id} has not started; results cannot be "
            "recorded against a request nobody has begun"
        )
        self.verification_id = verification_id


class VerificationAlreadyClosed(VerificationError):
    def __init__(self, *, verification_id: str, status: str) -> None:
        super().__init__(
            f"verification {verification_id} is {status}, which is terminal; "
            "re-verify by requesting a new attempt"
        )
        self.verification_id = verification_id
        self.status = status


class PolicyRefused(VerificationError):
    """Verification cannot be closed as complete while policy objects."""

    def __init__(self, *, verification_id: str, failures: Sequence) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in list(failures)[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(f"verification {verification_id} refused -- {summary}{more}")
        self.verification_id = verification_id
        self.failures = tuple(failures)


class VerificationNotFound(VerificationError):
    def __init__(self, verification_id: str) -> None:
        super().__init__(f"no verification with id {verification_id}")
        self.verification_id = verification_id


class DuplicateVerification(VerificationError):
    def __init__(self, *, work_id: str, attempt: int) -> None:
        super().__init__(f"attempt {attempt} for WorkOrder {work_id} already exists")
        self.work_id = work_id
        self.attempt = attempt


class StaleBaseCommit(VerificationError):
    """The tree moved while verification was running.

    Evidence is bound to a commit. When the base moves, everything collected
    against the old one describes a tree that is no longer being merged -- it was
    true then, and it is inadmissible now.
    """

    def __init__(self, *, verification_id: str, verified_at: str, current: str) -> None:
        super().__init__(
            f"verification {verification_id} ran against {verified_at} but the base is "
            f"now {current}; every claim must be reproduced against the tree being merged"
        )
        self.verification_id = verification_id
        self.verified_at = verified_at
        self.current = current
