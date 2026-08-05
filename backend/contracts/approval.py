"""Approval vocabulary.

Owner: BC-6 Governance.

Encodes Constitution I2 and P3: *the approval boundary is cryptographic, not
visual*. What a human approved and what the system executes are the same
artifact, proven by content hash -- not by a rendered summary that happens to
describe it.

Scope boundary
--------------
This module defines the *shape* of that binding. It does not compute hashes.
Canonical hashing is platform infrastructure delivered by PR-02
(``backend/platform/hashing.py``); a vocabulary package that computed digests
would be doing work, which contracts are forbidden from doing.

``ApprovalArtifact.matches`` therefore takes an already-computed digest and
compares. The comparison is constant-time to avoid leaking digest content
through timing, which costs nothing and removes a whole class of question at
review time.

See ADR-007.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionContract
from backend.contracts.identity import PrincipalRef
from backend.contracts.tenant import TenantScope

__all__ = [
    "HashAlgorithm",
    "ApprovalOutcome",
    "PayloadDigest",
    "ApprovalArtifact",
    "ApprovalRequest",
    "ApprovalDecision",
]


class HashAlgorithm(str, Enum):
    """Algorithms permitted for approval binding.

    Enumerated rather than free-form so that a downgrade to a weak algorithm is
    impossible to express. Adding an algorithm is an additive change; removing
    one is breaking and requires a contract version bump.
    """

    SHA256 = "sha256"
    SHA512 = "sha512"


class ApprovalOutcome(str, Enum):
    """How an approval request concluded."""

    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"

    @property
    def authorizes_execution(self) -> bool:
        return self is ApprovalOutcome.GRANTED


@dataclass(frozen=True)
class PayloadDigest(Contract):
    """A content digest over a serialized execution contract.

    Carries its algorithm alongside the value so that verification never has to
    guess, and so that an algorithm migration is detectable rather than silent.
    """

    CONTRACT_NAME = "cortexprime.approval.digest"

    algorithm: HashAlgorithm
    value: str
    """Lowercase hexadecimal digest."""

    _EXPECTED_LENGTHS = {HashAlgorithm.SHA256: 64, HashAlgorithm.SHA512: 128}

    def __post_init__(self) -> None:
        if not isinstance(self.algorithm, HashAlgorithm):
            raise ContractViolation("algorithm must be a HashAlgorithm")
        if not isinstance(self.value, str):
            raise ContractViolation("digest value must be a string")
        expected = self._EXPECTED_LENGTHS[self.algorithm]
        if len(self.value) != expected:
            raise ContractViolation(
                f"{self.algorithm.value} digest must be {expected} hex characters, "
                f"received {len(self.value)}"
            )
        if self.value != self.value.lower():
            raise ContractViolation("digest value must be lowercase hexadecimal")
        try:
            int(self.value, 16)
        except ValueError as exc:
            raise ContractViolation("digest value must be hexadecimal") from exc

    def matches(self, other: "PayloadDigest") -> bool:
        """Constant-time comparison against another digest."""
        if not isinstance(other, PayloadDigest):
            raise ContractViolation("can only compare against another PayloadDigest")
        if self.algorithm is not other.algorithm:
            return False
        return hmac.compare_digest(self.value, other.value)


@dataclass(frozen=True)
class ApprovalArtifact(Contract):
    """The immutable thing a human approves.

    An artifact binds three things together: the execution contract that will
    run, a digest of that contract, and the scope it runs in. Dispatch
    recomputes the digest from the stored contract and refuses to proceed on
    mismatch (I2).

    The rendering shown to a human MUST be derived from ``execution`` and never
    supplied alongside it. A separately-supplied summary is precisely the
    attack that defeated human-in-the-loop review in published penetration
    testing -- which is why this contract has no ``summary`` field.
    """

    CONTRACT_NAME = "cortexprime.approval.artifact"

    artifact_id: str
    execution: ExecutionContract
    digest: PayloadDigest
    scope: TenantScope
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, str) or not self.artifact_id.strip():
            raise ContractViolation("artifact_id must be a non-blank string")
        if self.created_at.tzinfo is None:
            raise ContractViolation("created_at must be timezone-aware")

    def verify(self, recomputed: PayloadDigest) -> bool:
        """Return whether a freshly computed digest matches the bound one.

        Callers must treat ``False`` as a refusal to execute, not a warning.
        The refusal itself is an auditable event (see ``contracts.audit``).
        """
        return self.digest.matches(recomputed)


@dataclass(frozen=True)
class ApprovalRequest(Contract):
    """A request for a human to authorize an artifact.

    ``expires_at`` is mandatory. An approval that never expires is a standing
    grant, and standing grants defeat the purpose of the gate.
    """

    CONTRACT_NAME = "cortexprime.approval.request"

    request_id: str
    artifact: ApprovalArtifact
    requested_at: datetime
    expires_at: datetime
    required_capability: Optional[str] = None
    justification: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ContractViolation("request_id must be a non-blank string")
        if self.requested_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ContractViolation("approval timestamps must be timezone-aware")
        if self.expires_at <= self.requested_at:
            raise ContractViolation("expires_at must be after requested_at")

    def is_expired_at(self, moment: datetime) -> bool:
        if moment.tzinfo is None:
            raise ContractViolation("moment must be timezone-aware")
        return moment >= self.expires_at


@dataclass(frozen=True)
class ApprovalDecision(Contract):
    """The recorded conclusion of an approval request.

    Only a human principal may grant (Constitution: ``PrincipalRef.can_approve``).
    A platform principal granting its own approval is the definition of a system
    authorizing itself, which the Constitution names as one of two catastrophic
    failure modes -- so it is rejected here at construction.
    """

    CONTRACT_NAME = "cortexprime.approval.decision"

    request_id: str
    artifact_id: str
    outcome: ApprovalOutcome
    decided_at: datetime
    decided_by: Optional[PrincipalRef] = None
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ApprovalOutcome):
            raise ContractViolation("outcome must be an ApprovalOutcome")
        if self.decided_at.tzinfo is None:
            raise ContractViolation("decided_at must be timezone-aware")

        if self.outcome is ApprovalOutcome.GRANTED:
            if self.decided_by is None:
                raise ContractViolation("a granted approval must record who granted it")
            if not self.decided_by.can_approve:
                raise ContractViolation(
                    f"a {self.decided_by.kind.value} principal cannot grant approval; "
                    "the platform must never authorize itself"
                )
        if self.outcome is ApprovalOutcome.DENIED and not (self.reason or "").strip():
            raise ContractViolation("a denied approval must record a reason")
