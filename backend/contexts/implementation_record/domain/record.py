"""The ImplementationRecord aggregate and its digest.

The authoritative artifact Review and Verification consume. Until this context
existed, Verification received a placeholder claim because nothing carried what
the implementer actually asserted.

Immutable after completion
---------------------------
Every mutation refuses once the record is ``COMPLETED``. That is stricter than
the immutability elsewhere in this codebase, and it earns the strictness: a
record that changed after Review and Verification read it would make every
finding they produced a statement about a document that no longer exists.

The digest, computed at completion, is what makes that checkable rather than
merely promised.

What every record must reference
---------------------------------
WorkOrder, ContextBundle version, ADR references, repository revision, digest.
The first four are refused at construction; the digest is computed at completion.
Each is a different question a reviewer will ask -- *what authorised this, what
did the implementer see, what governs it, what tree is it against* -- and a
record missing any of them cannot answer one of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final, Iterable, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contexts.implementation_record.domain.changes import ChangedFile, CodeChangeSet
from backend.contexts.implementation_record.domain.claims import (
    AssumptionOutcome,
    AssumptionResolution,
    Claim,
    CriterionCoverage,
    RiskDeclaration,
)
from backend.contexts.implementation_record.domain.errors import (
    AssumptionAlreadyResolved,
    DigestMismatch,
    DigestNotComputed,
    DuplicateClaim,
    RecordCompleted,
    RecordNotStarted,
    RecordSuperseded,
    UnknownAssumption,
)
from backend.contexts.implementation_record.domain.identifiers import ClaimId, ImplementationId
from backend.contexts.implementation_record.domain.outcomes import BuildResult, TestExecution
from backend.contexts.implementation_record.domain.paths import BlastRadiusScope
from backend.platform.hashing import compute_digest, digests_match

__all__ = [
    "ImplementationStatus",
    "ImplementationRecord",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
]

ARTIFACT_KIND: Final[str] = "cortexprime.engineering.implementationrecord"
CANONICAL_FORM_VERSION: Final[int] = 1

#: What the digest covers. Excludes status, timestamps, and the digest itself --
#: including status would invalidate the digest on the first legal transition,
#: and a digest cannot cover itself.
GOVERNED_FIELDS: Final[tuple] = (
    "work_id",
    "round",
    "context_bundle_version",
    "context_bundle_id",
    "adr_references",
    "revision",
    "changes",
    "claims",
    "assumption_resolutions",
    "risks",
    "criterion_coverage",
    "test_executions",
    "build_results",
    "deviations",
)


class ImplementationStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"

    @property
    def is_open(self) -> bool:
        return self is ImplementationStatus.IN_PROGRESS

    @property
    def is_immutable(self) -> bool:
        """Everything except in-progress. Completion is the one that matters."""
        return self is not ImplementationStatus.IN_PROGRESS

    @property
    def is_submittable(self) -> bool:
        """Whether Review and Verification may consume this. Only one status."""
        return self is ImplementationStatus.COMPLETED


@dataclass(frozen=True)
class ImplementationRecord(Contract):
    """One implementation round for one WorkOrder."""

    CONTRACT_NAME = "cortexprime.engineering.implementation_record"

    implementation_id: ImplementationId
    work_id: str
    round: int
    context_bundle_id: str
    context_bundle_version: int
    revision: str
    blast_radius: BlastRadiusScope
    adr_references: frozenset = field(default_factory=frozenset)

    changes: CodeChangeSet = None  # type: ignore[assignment]
    claims: tuple = ()
    assumption_resolutions: tuple = ()
    risks: tuple = ()
    criterion_coverage: tuple = ()
    test_executions: tuple = ()
    build_results: tuple = ()
    deviations: tuple = ()

    status: ImplementationStatus = ImplementationStatus.IN_PROGRESS
    digest: Optional[str] = None
    implementer: str = "implementer"
    expected_assumptions: frozenset = field(default_factory=frozenset)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    closing_note: Optional[str] = None
    superseded_by: Optional[ImplementationId] = None

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.implementation_id, ImplementationId):
            raise ContractViolation("implementation_id must be an ImplementationId")

        for label, value in (
            ("work_id", self.work_id),
            ("context_bundle_id", self.context_bundle_id),
            ("revision", self.revision),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; every implementation must "
                    "reference what authorised it, what it saw, and the tree it is against"
                )

        for label, value in (
            ("round", self.round),
            ("context_bundle_version", self.context_bundle_version),
        ):
            if not isinstance(value, int) or value < 1:
                raise ContractViolation(f"{label} must be a positive integer starting at 1")

        if not isinstance(self.blast_radius, BlastRadiusScope):
            raise ContractViolation("blast_radius must be a BlastRadiusScope")

        if self.changes is None:
            object.__setattr__(self, "changes", CodeChangeSet.empty(self.revision))
        if not isinstance(self.changes, CodeChangeSet):
            raise ContractViolation("changes must be a CodeChangeSet")

        for label, items, expected in (
            ("claims", self.claims, Claim),
            ("assumption_resolutions", self.assumption_resolutions, AssumptionResolution),
            ("risks", self.risks, RiskDeclaration),
            ("criterion_coverage", self.criterion_coverage, CriterionCoverage),
            ("test_executions", self.test_executions, TestExecution),
            ("build_results", self.build_results, BuildResult),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        for label in ("adr_references", "expected_assumptions"):
            value = getattr(self, label)
            if not isinstance(value, (frozenset, set)):
                raise ContractViolation(f"{label} must be a set")
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    raise ContractViolation(f"{label} contains a blank entry")
            object.__setattr__(self, label, frozenset(v.strip() for v in value))

        if not isinstance(self.deviations, tuple):
            raise ContractViolation("deviations must be a tuple")

        claim_ids = [str(c.claim_id) for c in self.claims]
        if len(set(claim_ids)) != len(claim_ids):
            raise ContractViolation("claims contains duplicate claim ids")

        resolved = [r.assumption_id for r in self.assumption_resolutions]
        if len(set(resolved)) != len(resolved):
            raise ContractViolation(
                "the same assumption is resolved twice; two answers means one is wrong"
            )

        if not isinstance(self.status, ImplementationStatus):
            raise ContractViolation("status must be an ImplementationStatus")

        # Completion binds the digest. A completed record without one could not be
        # shown to be the artifact that was submitted.
        if self.status is ImplementationStatus.COMPLETED:
            if not self.digest:
                raise ContractViolation(
                    "a completed implementation must carry the digest computed at "
                    "completion; without it the artifact under review cannot be shown "
                    "to be the one submitted"
                )
            if self.completed_at is None:
                raise ContractViolation("a completed implementation must record when")

        if self.status is ImplementationStatus.SUPERSEDED and self.superseded_by is None:
            raise ContractViolation("a superseded implementation must name its successor")
        if self.status is ImplementationStatus.ABANDONED and not (
            self.closing_note and self.closing_note.strip()
        ):
            raise ContractViolation(
                "abandoning an implementation must say why; an unexplained abandonment "
                "tells the next round nothing"
            )

        if self.superseded_by is not None and not isinstance(
            self.superseded_by, ImplementationId
        ):
            raise ContractViolation("superseded_by must be an ImplementationId")

        for label, value in (
            ("started_at", self.started_at),
            ("completed_at", self.completed_at),
        ):
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

        # The change set describes the same tree the record does. Two revisions in
        # one record would leave a reviewer unable to say which is being reviewed.
        if self.changes.files and self.changes.revision != self.revision:
            raise ContractViolation(
                f"the change set is against {self.changes.revision!r} but the record is "
                f"against {self.revision!r}; a reviewer could not say which is under review"
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.status.is_open

    @property
    def paths_outside_radius(self) -> tuple:
        return self.changes.outside(self.blast_radius)

    @property
    def untouched_radius_patterns(self) -> tuple:
        return self.blast_radius.untouched_patterns(self.changes.all_paths_touched)

    @property
    def unresolved_assumptions(self) -> tuple:
        resolved = {r.assumption_id for r in self.assumption_resolutions}
        return tuple(sorted(self.expected_assumptions - resolved))

    @property
    def blocking_assumptions(self) -> tuple:
        return tuple(r for r in self.assumption_resolutions if not r.permits_completion)

    @property
    def contradicted_assumptions(self) -> tuple:
        return tuple(
            r for r in self.assumption_resolutions if r.outcome.implies_rejection
        )

    @property
    def failing_tests(self) -> tuple:
        return tuple(t for t in self.test_executions if not t.is_green)

    @property
    def failing_builds(self) -> tuple:
        return tuple(b for b in self.build_results if not b.is_green)

    @property
    def unmitigated_risks(self) -> tuple:
        return tuple(r for r in self.risks if r.level.requires_mitigation and not r.mitigation)

    def claim(self, claim_id: ClaimId) -> Optional[Claim]:
        for candidate in self.claims:
            if candidate.claim_id == claim_id:
                return candidate
        return None

    @property
    def all_evidence_ids(self) -> tuple:
        """Every identifier the implementer offered, across claims and resolutions.

        The Verification context refuses to reuse any of these when producing its
        own evidence (ADR-021), so it needs the full set rather than the per-claim
        one.
        """
        ids = {e for c in self.claims for e in c.evidence_ids}
        ids |= {str(e) for r in self.assumption_resolutions for e in r.evidence}
        return tuple(sorted(ids))

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        """The exact structure the digest covers.

        Exposed so a verifier can recompute it and name the member that diverged,
        rather than reporting only that two hex strings differ.
        """
        return {
            "__artifact__": ARTIFACT_KIND,
            "__canonical_form__": CANONICAL_FORM_VERSION,
            "work_id": self.work_id,
            "round": self.round,
            "context_bundle_id": self.context_bundle_id,
            "context_bundle_version": self.context_bundle_version,
            "adr_references": sorted(self.adr_references),
            "revision": self.revision,
            "changes": {
                "revision": self.changes.revision,
                "files": sorted(
                    (
                        {
                            "path": f.path,
                            "kind": f.kind.value,
                            "content_digest": f.content_digest,
                            "previous_path": f.previous_path,
                        }
                        for f in self.changes.files
                    ),
                    key=lambda item: item["path"],
                ),
            },
            "claims": sorted(
                (
                    {
                        "claim_id": str(c.claim_id),
                        "statement": c.statement,
                        "claim_type": c.claim_type.value,
                        "evidence": list(c.evidence_ids),
                    }
                    for c in self.claims
                ),
                key=lambda item: item["claim_id"],
            ),
            "assumption_resolutions": sorted(
                (
                    {
                        "assumption_id": r.assumption_id,
                        "outcome": r.outcome.value,
                        "evidence": sorted(str(e) for e in r.evidence),
                    }
                    for r in self.assumption_resolutions
                ),
                key=lambda item: item["assumption_id"],
            ),
            "risks": sorted(
                (
                    {
                        "risk_id": str(r.risk_id),
                        "statement": r.statement,
                        "level": r.level.value,
                        "mitigation": r.mitigation,
                    }
                    for r in self.risks
                ),
                key=lambda item: item["risk_id"],
            ),
            "criterion_coverage": sorted(
                (
                    {
                        "criterion": c.criterion,
                        "covering_tests": sorted(c.covering_tests),
                        "negative_check": c.negative_check,
                    }
                    for c in self.criterion_coverage
                ),
                key=lambda item: item["criterion"],
            ),
            "test_executions": sorted(
                (
                    {
                        "command": t.command,
                        "status": t.status.value,
                        "revision": t.revision,
                        "passed": t.passed,
                        "failed": t.failed,
                        "skipped": t.skipped,
                        "errors": t.errors,
                    }
                    for t in self.test_executions
                ),
                key=lambda item: item["command"],
            ),
            "build_results": sorted(
                (
                    {
                        "name": b.name,
                        "command": b.command,
                        "status": b.status.value,
                        "revision": b.revision,
                    }
                    for b in self.build_results
                ),
                key=lambda item: item["name"],
            ),
            "deviations": sorted(self.deviations),
        }

    def compute_digest(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def verify_digest(self) -> None:
        """Raise unless the record still hashes to the digest bound at completion."""
        if not self.digest:
            raise DigestNotComputed(str(self.implementation_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                record_id=str(self.implementation_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _require_open(self, operation: str) -> None:
        if self.status is ImplementationStatus.SUPERSEDED:
            raise RecordSuperseded(
                record_id=str(self.implementation_id), successor=str(self.superseded_by)
            )
        if self.status.is_immutable:
            raise RecordCompleted(
                record_id=str(self.implementation_id), operation=operation
            )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_file(self, changed: ChangedFile) -> "ImplementationRecord":
        """Add a changed file, refusing anything outside the declared radius.

        Checked here rather than at completion so the refusal arrives while the
        implementer still remembers why it touched the file.
        """
        self._require_open("recording a file")
        for path in changed.paths_touched:
            reason = self.blast_radius.refusal_reason(path)
            if reason is not None:
                from backend.contexts.implementation_record.domain.errors import (
                    OutsideBlastRadius,
                )

                raise OutsideBlastRadius(
                    path=path, reason=reason, allowed=self.blast_radius.allowed_patterns
                )
        return replace(self, changes=self.changes.with_file(changed))

    def add_claim(self, claim: Claim) -> "ImplementationRecord":
        self._require_open("adding a claim")
        if not isinstance(claim, Claim):
            raise ContractViolation("claim must be a Claim")
        if any(c.statement == claim.statement for c in self.claims):
            raise DuplicateClaim(claim.statement)
        return replace(self, claims=self.claims + (claim,))

    def resolve_assumption(self, resolution: AssumptionResolution) -> "ImplementationRecord":
        """Record the outcome of checking one of the WorkOrder's assumptions."""
        self._require_open("resolving an assumption")
        if not isinstance(resolution, AssumptionResolution):
            raise ContractViolation("resolution must be an AssumptionResolution")

        if (
            self.expected_assumptions
            and resolution.assumption_id not in self.expected_assumptions
        ):
            raise UnknownAssumption(
                record_id=str(self.implementation_id),
                assumption_id=resolution.assumption_id,
            )

        existing = next(
            (
                r
                for r in self.assumption_resolutions
                if r.assumption_id == resolution.assumption_id
            ),
            None,
        )
        if existing is not None:
            raise AssumptionAlreadyResolved(
                assumption_id=resolution.assumption_id, resolution=existing.outcome.value
            )
        return replace(
            self, assumption_resolutions=self.assumption_resolutions + (resolution,)
        )

    def declare_risk(self, risk: RiskDeclaration) -> "ImplementationRecord":
        self._require_open("declaring a risk")
        if not isinstance(risk, RiskDeclaration):
            raise ContractViolation("risk must be a RiskDeclaration")
        return replace(self, risks=self.risks + (risk,))

    def record_tests(self, execution: TestExecution) -> "ImplementationRecord":
        self._require_open("recording a test run")
        if not isinstance(execution, TestExecution):
            raise ContractViolation("execution must be a TestExecution")
        return replace(self, test_executions=self.test_executions + (execution,))

    def record_build(self, result: BuildResult) -> "ImplementationRecord":
        self._require_open("recording a build")
        if not isinstance(result, BuildResult):
            raise ContractViolation("result must be a BuildResult")
        return replace(self, build_results=self.build_results + (result,))

    def record_coverage(self, coverage: CriterionCoverage) -> "ImplementationRecord":
        self._require_open("recording criterion coverage")
        if not isinstance(coverage, CriterionCoverage):
            raise ContractViolation("coverage must be a CriterionCoverage")
        if any(c.criterion == coverage.criterion for c in self.criterion_coverage):
            raise ContractViolation(
                f"criterion {coverage.criterion[:50]!r} already has a coverage entry"
            )
        return replace(self, criterion_coverage=self.criterion_coverage + (coverage,))

    def note_deviation(self, deviation: str) -> "ImplementationRecord":
        """Record where the implementation departed from the obvious reading.

        Cheap to write and expensive to omit: a reviewer who finds an unexplained
        departure spends the rest of the review wondering what else is
        unexplained.
        """
        self._require_open("noting a deviation")
        if not deviation or not deviation.strip():
            raise ContractViolation("a deviation must say what it departed from")
        return replace(self, deviations=self.deviations + (deviation.strip(),))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def complete(self) -> "ImplementationRecord":
        """Seal the record and bind its digest.

        Policy decides *whether* a record may complete; this performs it. Keeping
        them apart means the aggregate holds no second copy of the completion
        rules, and the service can report every failure at once rather than one
        refusal at a time.
        """
        self._require_open("completing")
        sealed = replace(
            self,
            status=ImplementationStatus.IN_PROGRESS,
            completed_at=datetime.now(timezone.utc),
        )
        digest = sealed.compute_digest().value
        return replace(sealed, status=ImplementationStatus.COMPLETED, digest=digest)

    def abandon(self, reason: str) -> "ImplementationRecord":
        self._require_open("abandoning")
        if not reason or not reason.strip():
            raise ContractViolation("abandoning an implementation must say why")
        return replace(
            self,
            status=ImplementationStatus.ABANDONED,
            closing_note=reason.strip(),
            completed_at=datetime.now(timezone.utc),
        )

    def supersede(self, successor: ImplementationId) -> "ImplementationRecord":
        """Record that a later round replaces this one.

        Permitted on a completed record, unlike every other mutation: superseding
        does not change what the record *says*, only whether it is current. The
        digest still verifies afterwards, and a test asserts that.
        """
        if not isinstance(successor, ImplementationId):
            raise ContractViolation("successor must be an ImplementationId")
        if successor == self.implementation_id:
            raise ContractViolation("an implementation cannot supersede itself")
        if self.superseded_by is not None:
            raise ContractViolation(
                f"implementation {self.implementation_id} is already superseded by "
                f"{self.superseded_by}"
            )
        return replace(
            self, status=ImplementationStatus.SUPERSEDED, superseded_by=successor
        )
