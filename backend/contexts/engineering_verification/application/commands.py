"""Commands and queries for the Verification context.

Frozen values naming one intent each. Objects rather than argument lists, because
a command is what an orchestrator queues, logs, retries and replays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "ClaimInput",
    "RequestVerification",
    "StartVerification",
    "RecordClaimResult",
    "AddEvidence",
    "CloseVerification",
    "SupersedeVerification",
    "MarkStale",
    "GetVerification",
    "ListVerifications",
    "GetOutcome",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class ClaimInput:
    """A claim as it arrives from outside, before it becomes a domain object."""

    statement: str
    claim_type: str = "behaviour"
    asserted_evidence: tuple = ()
    hint: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.statement and self.statement.strip()), "a claim must state something")


@dataclass(frozen=True)
class RequestVerification:
    work_id: str
    claims: tuple
    base_commit: str
    attempt: int = 1
    requested_by: str = "engineering-runtime"

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(
            bool(self.base_commit and self.base_commit.strip()),
            "base_commit is required; evidence naming no tree cannot be checked for staleness",
        )
        _require(
            bool(self.claims),
            "at least one claim is required; verifying nothing would report complete "
            "having established nothing",
        )
        for item in self.claims:
            _require(isinstance(item, ClaimInput), "claims must be ClaimInput values")


@dataclass(frozen=True)
class StartVerification:
    verification_id: str
    verifier: str

    def __post_init__(self) -> None:
        _require(bool(self.verification_id), "verification_id is required")
        _require(
            bool(self.verifier and self.verifier.strip()),
            "a verifier must be named; a verdict has an author",
        )


@dataclass(frozen=True)
class RecordClaimResult:
    """One verdict, with the reproduction and the evidence the verifier produced."""

    verification_id: str
    claim_id: str
    verdict: str
    observed: str
    method: str = "command_execution"
    specification: str = ""
    determinism: str = "deterministic"
    runs: int = 1
    evidence_summary: str = ""
    evidence_kind: str = "command"
    evidence_trust: str = "environmental"
    evidence_base_commit: Optional[str] = None
    note: Optional[str] = None
    collected_by: str = "verifier"

    def __post_init__(self) -> None:
        _require(bool(self.verification_id), "verification_id is required")
        _require(bool(self.claim_id), "claim_id is required")
        _require(
            bool(self.observed and self.observed.strip()),
            "observed must state what actually happened; a verdict with no observation "
            "is an opinion",
        )
        if self.verdict != "out_of_scope":
            _require(
                bool(self.specification and self.specification.strip()),
                "a reproduction must state exactly what was run, inspected, or constructed",
            )
            _require(
                bool(self.evidence_summary and self.evidence_summary.strip()),
                "a verdict must carry the evidence the verifier produced reaching it",
            )
        else:
            _require(
                bool(self.note and self.note.strip()),
                "an out-of-scope verdict must say why the claim is outside this "
                "verification's coverage",
            )


@dataclass(frozen=True)
class AddEvidence:
    """Evidence supporting the verification as a whole rather than one claim."""

    verification_id: str
    summary: str
    kind: str = "command"
    trust: str = "environmental"
    base_commit: Optional[str] = None
    detail: Optional[str] = None
    collected_by: str = "verifier"

    def __post_init__(self) -> None:
        _require(bool(self.verification_id), "verification_id is required")
        _require(bool(self.summary and self.summary.strip()), "summary is required")
        _require(
            self.trust != "asserted",
            "asserted names the absence of evidence and cannot be added as any",
        )


@dataclass(frozen=True)
class CloseVerification:
    """Close with the outcome policy has determined.

    ``force_outcome`` exists for the one legitimate case policy cannot see: an
    approved premise turned out false, which invalidates the verification
    regardless of how the individual claims went.
    """

    verification_id: str
    current_commit: Optional[str] = None
    force_outcome: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.verification_id), "verification_id is required")
        if self.force_outcome is not None:
            _require(
                self.force_outcome == "invalidated",
                "the only outcome that may be forced is 'invalidated'; every other "
                "outcome is derived from the results",
            )
            _require(
                bool(self.note and self.note.strip()),
                "invalidating a verification must say which premise failed",
            )


@dataclass(frozen=True)
class SupersedeVerification:
    verification_id: str
    successor_id: str
    reason: str = "a later attempt replaces this one"

    def __post_init__(self) -> None:
        _require(bool(self.verification_id), "verification_id is required")
        _require(bool(self.successor_id), "successor_id is required")
        _require(
            self.verification_id != self.successor_id,
            "a verification cannot supersede itself",
        )


@dataclass(frozen=True)
class MarkStale:
    verification_id: str
    current_commit: str

    def __post_init__(self) -> None:
        _require(bool(self.verification_id), "verification_id is required")
        _require(bool(self.current_commit), "current_commit is required")


@dataclass(frozen=True)
class GetVerification:
    verification_id: str


@dataclass(frozen=True)
class ListVerifications:
    work_id: Optional[str] = None
    status: Optional[str] = None
    open_only: bool = False


@dataclass(frozen=True)
class GetOutcome:
    """The latest outcome for a WorkOrder attempt, as the runtime needs it."""

    work_id: str
    attempt: int
