"""Verification lifecycle events.

Event types are namespaced ``engineering.verification.*``. That is not
decoration: ``CONTRACT_NAME`` is globally unique and a clash raises at import
time, and PR-E2's Engineering Runtime already owns
``engineering.runtime.verification_requested``.

The two are genuinely different facts and both are worth having. The runtime's
event says *the orchestrator asked for verification*; this one says *the
Verification context accepted the request*. They coincide today and will not once
requests are queued -- and the gap between them is exactly where a dropped
request would hide.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "VerificationRequested",
    "VerificationStarted",
    "VerificationSucceeded",
    "VerificationFailed",
    "VerificationEvidenceAdded",
    "VerificationSuperseded",
    "VERIFICATION_EVENT_TYPES",
]

AGGREGATE_TYPE = "verification"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class VerificationRequested(DomainEvent):
    """The Verification context accepted a request and created a record."""

    EVENT_TYPE = "engineering.verification.requested"

    verification_id: str = ""
    work_id: str = ""
    attempt: int = 1
    claim_count: int = 0
    base_commit: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("verification_id", self.verification_id)
        _require_text("work_id", self.work_id)
        _require_text("base_commit", self.base_commit)
        if self.claim_count < 1:
            raise ContractViolation(
                "a verification request carries at least one claim; verifying nothing "
                "would report complete having established nothing"
            )


@dataclass(frozen=True)
class VerificationStarted(DomainEvent):
    """A named verifier claimed the work. A verdict has an author."""

    EVENT_TYPE = "engineering.verification.started"

    verification_id: str = ""
    work_id: str = ""
    attempt: int = 1
    verifier: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("verification_id", self.verification_id)
        _require_text("work_id", self.work_id)
        _require_text("verifier", self.verifier)


@dataclass(frozen=True)
class VerificationSucceeded(DomainEvent):
    """Every claim reproduced against the tree being merged."""

    EVENT_TYPE = "engineering.verification.succeeded"

    verification_id: str = ""
    work_id: str = ""
    attempt: int = 1
    claims_reproduced: int = 0
    claims_out_of_scope: int = 0
    weakest_trust: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("verification_id", self.verification_id)
        _require_text("work_id", self.work_id)
        if self.claims_reproduced < 1:
            raise ContractViolation(
                "a successful verification reproduced at least one claim; success with "
                "nothing reproduced is the most dangerous outcome available"
            )


@dataclass(frozen=True)
class VerificationFailed(DomainEvent):
    """Verification closed without establishing the claims.

    Carries the outcome rather than only 'failed', because ``failed`` and
    ``incomplete`` mean different things to whoever reads it: the first says the
    work is wrong, the second says the verifier could not tell.
    """

    EVENT_TYPE = "engineering.verification.failed"

    verification_id: str = ""
    work_id: str = ""
    attempt: int = 1
    outcome: str = ""
    contradicted: int = 0
    unreproducible: int = 0
    outstanding: int = 0
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("verification_id", self.verification_id)
        _require_text("work_id", self.work_id)
        _require_text("outcome", self.outcome)
        _require_text("reason", self.reason)
        if not (self.contradicted or self.unreproducible or self.outstanding):
            raise ContractViolation(
                "a failed verification must name what went wrong; nothing contradicted, "
                "nothing unreproducible and nothing outstanding is a success"
            )


@dataclass(frozen=True)
class VerificationEvidenceAdded(DomainEvent):
    """The verifier produced evidence, for a claim or for the run as a whole."""

    EVENT_TYPE = "engineering.verification.evidence_added"

    verification_id: str = ""
    work_id: str = ""
    evidence_id: str = ""
    kind: str = ""
    trust: str = ""
    claim_id: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("verification_id", self.verification_id)
        _require_text("evidence_id", self.evidence_id)
        _require_text("kind", self.kind)
        _require_text("trust", self.trust)
        if self.trust == "asserted":
            raise ContractViolation(
                "asserted names the absence of evidence and cannot be added as any"
            )


@dataclass(frozen=True)
class VerificationSuperseded(DomainEvent):
    """A later attempt replaces this one."""

    EVENT_TYPE = "engineering.verification.superseded"

    verification_id: str = ""
    work_id: str = ""
    superseded_by: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("verification_id", self.verification_id)
        _require_text("superseded_by", self.superseded_by)
        if self.verification_id == self.superseded_by:
            raise ContractViolation("a verification cannot supersede itself")


VERIFICATION_EVENT_TYPES = (
    VerificationRequested,
    VerificationStarted,
    VerificationSucceeded,
    VerificationFailed,
    VerificationEvidenceAdded,
    VerificationSuperseded,
)
