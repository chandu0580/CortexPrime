"""Commands and queries for the ImplementationRecord context.

Frozen values naming one intent each, carrying primitives rather than domain
objects so a command can be serialised, queued, and replayed without dragging the
domain across the wire.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "StartImplementation",
    "RecordFile",
    "AddClaim",
    "ResolveAssumption",
    "DeclareRisk",
    "RecordTests",
    "RecordBuild",
    "RecordCoverage",
    "NoteDeviation",
    "CompleteImplementation",
    "AbandonImplementation",
    "SupersedeImplementation",
    "GetImplementation",
    "ListImplementations",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class StartImplementation:
    work_id: str
    context_bundle_id: str
    revision: str
    blast_radius_allowed: tuple
    round: int = 1
    context_bundle_version: int = 1
    blast_radius_forbidden: tuple = ()
    blast_radius_read_only: tuple = ()
    adr_references: tuple = ()
    expected_assumptions: tuple = ()
    implementer: str = "implementer"

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(
            bool(self.context_bundle_id),
            "context_bundle_id is required; every implementation references what it saw",
        )
        _require(
            bool(self.revision and self.revision.strip()),
            "revision is required; the same paths against a different commit describe "
            "a different change",
        )
        _require(
            bool(self.blast_radius_allowed),
            "a blast radius that allows nothing authorises nothing",
        )
        _require(self.round >= 1, "round starts at 1")


@dataclass(frozen=True)
class RecordFile:
    implementation_id: str
    path: str
    kind: str = "modified"
    content_digest: Optional[str] = None
    previous_path: Optional[str] = None
    lines_added: int = 0
    lines_removed: int = 0

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(bool(self.path), "path is required")


@dataclass(frozen=True)
class AddClaim:
    implementation_id: str
    statement: str
    claim_type: str = "behaviour"
    evidence: tuple = ()
    reproduction_hint: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(
            bool(self.statement and self.statement.strip()), "a claim must state something"
        )
        _require(
            bool(self.evidence),
            "a claim must cite evidence; one a verifier cannot attack can only be "
            "taken on trust",
        )


@dataclass(frozen=True)
class ResolveAssumption:
    implementation_id: str
    assumption_id: str
    statement: str
    outcome: str
    evidence: tuple = ()
    note: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(bool(self.assumption_id), "assumption_id is required")
        _require(
            bool(self.evidence),
            "every resolution must cite what was checked, including 'unverifiable'",
        )


@dataclass(frozen=True)
class DeclareRisk:
    implementation_id: str
    statement: str
    level: str = "low"
    mitigation: Optional[str] = None
    affected_paths: tuple = ()

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(
            bool(self.statement and self.statement.strip()),
            "a risk must state what could go wrong",
        )


@dataclass(frozen=True)
class RecordTests:
    implementation_id: str
    command: str
    status: str = "passed"
    revision: Optional[str] = None
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    suite: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(
            bool(self.command and self.command.strip()),
            "the exact command is required; 'tests pass' is not a command a verifier "
            "can re-run",
        )


@dataclass(frozen=True)
class RecordBuild:
    implementation_id: str
    name: str
    command: str
    status: str = "passed"
    revision: Optional[str] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(bool(self.name), "name is required")
        _require(bool(self.command), "command is required")


@dataclass(frozen=True)
class RecordCoverage:
    implementation_id: str
    criterion: str
    covering_tests: tuple = ()
    negative_check: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(bool(self.criterion), "criterion is required")
        _require(
            bool(self.covering_tests),
            "coverage must name a test; an uncovered criterion recorded as covered is "
            "worse than one left out",
        )


@dataclass(frozen=True)
class NoteDeviation:
    implementation_id: str
    deviation: str

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(
            bool(self.deviation and self.deviation.strip()),
            "a deviation must say what it departed from",
        )


@dataclass(frozen=True)
class CompleteImplementation:
    implementation_id: str

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")


@dataclass(frozen=True)
class AbandonImplementation:
    implementation_id: str
    reason: str

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(
            bool(self.reason and self.reason.strip()),
            "abandoning must say why; an unexplained abandonment tells the next round "
            "nothing",
        )


@dataclass(frozen=True)
class SupersedeImplementation:
    implementation_id: str
    successor_id: str
    reason: str = "a later round replaces this one"

    def __post_init__(self) -> None:
        _require(bool(self.implementation_id), "implementation_id is required")
        _require(bool(self.successor_id), "successor_id is required")
        _require(
            self.implementation_id != self.successor_id,
            "an implementation cannot supersede itself",
        )


@dataclass(frozen=True)
class GetImplementation:
    implementation_id: str


@dataclass(frozen=True)
class ListImplementations:
    work_id: Optional[str] = None
    status: Optional[str] = None
