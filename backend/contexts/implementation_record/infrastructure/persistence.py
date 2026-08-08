"""Mapping between the ImplementationRecord aggregate and a storable record.

Storage-agnostic: a plain mapping of primitives.

Every invariant is re-checked on the way in, and the digest is **restored, not
recomputed**. Recomputing would make it always match — a check that cannot fail —
and this is the one artifact where that check is the whole point: it is how a
reviewer knows the record under review is the one that was submitted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.errors import ContractViolation
from backend.contexts.implementation_record.domain.changes import (
    ChangedFile,
    ChangeKind,
    CodeChangeSet,
)
from backend.contexts.implementation_record.domain.claims import (
    AssumptionOutcome,
    AssumptionResolution,
    Claim,
    ClaimType,
    CriterionCoverage,
    EvidenceRef,
    RiskDeclaration,
    RiskLevel,
)
from backend.contexts.implementation_record.domain.identifiers import (
    ClaimId,
    ImplementationId,
    RiskId,
)
from backend.contexts.implementation_record.domain.outcomes import (
    BuildResult,
    ExecutionStatus,
    TestExecution,
)
from backend.contexts.implementation_record.domain.paths import (
    BlastRadiusScope,
    PathPattern,
)
from backend.contexts.implementation_record.domain.record import (
    ImplementationRecord,
    ImplementationStatus,
)

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def to_record(record: ImplementationRecord, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation("tenant_id must be non-blank; it is derived from the context")

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "implementation_id": str(record.implementation_id),
        "work_id": record.work_id,
        "round": record.round,
        "context_bundle_id": record.context_bundle_id,
        "context_bundle_version": record.context_bundle_version,
        "revision": record.revision,
        "adr_references": sorted(record.adr_references),
        "blast_radius": {
            "allowed": sorted(str(p) for p in record.blast_radius.allowed),
            "forbidden": sorted(str(p) for p in record.blast_radius.forbidden),
            "read_only": sorted(str(p) for p in record.blast_radius.read_only),
        },
        "changes": {
            "revision": record.changes.revision,
            "base_revision": record.changes.base_revision,
            "files": [
                {
                    "path": f.path,
                    "kind": f.kind.value,
                    "content_digest": f.content_digest,
                    "previous_path": f.previous_path,
                    "lines_added": f.lines_added,
                    "lines_removed": f.lines_removed,
                }
                for f in record.changes.files
            ],
        },
        "claims": [
            {
                "claim_id": str(c.claim_id),
                "statement": c.statement,
                "claim_type": c.claim_type.value,
                "evidence": list(c.evidence_ids),
                "reproduction_hint": c.reproduction_hint,
            }
            for c in record.claims
        ],
        "assumption_resolutions": [
            {
                "assumption_id": r.assumption_id,
                "statement": r.statement,
                "outcome": r.outcome.value,
                "evidence": sorted(str(e) for e in r.evidence),
                "note": r.note,
                "resolved_at": r.resolved_at.isoformat(),
            }
            for r in record.assumption_resolutions
        ],
        "risks": [
            {
                "risk_id": str(r.risk_id),
                "statement": r.statement,
                "level": r.level.value,
                "mitigation": r.mitigation,
                "affected_paths": list(r.affected_paths),
            }
            for r in record.risks
        ],
        "criterion_coverage": [
            {
                "criterion": c.criterion,
                "covering_tests": list(c.covering_tests),
                "negative_check": c.negative_check,
            }
            for c in record.criterion_coverage
        ],
        "test_executions": [
            {
                "command": t.command,
                "status": t.status.value,
                "revision": t.revision,
                "passed": t.passed,
                "failed": t.failed,
                "skipped": t.skipped,
                "errors": t.errors,
                "duration_seconds": t.duration_seconds,
                "suite": t.suite,
                "output_digest": t.output_digest,
                "executed_at": t.executed_at.isoformat(),
            }
            for t in record.test_executions
        ],
        "build_results": [
            {
                "name": b.name,
                "command": b.command,
                "status": b.status.value,
                "revision": b.revision,
                "output_digest": b.output_digest,
                "detail": b.detail,
                "executed_at": b.executed_at.isoformat(),
            }
            for b in record.build_results
        ],
        "deviations": list(record.deviations),
        "status": record.status.value,
        "digest": record.digest,
        "implementer": record.implementer,
        "expected_assumptions": sorted(record.expected_assumptions),
        "started_at": record.started_at.isoformat(),
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "closing_note": record.closing_note,
        "superseded_by": str(record.superseded_by) if record.superseded_by else None,
    }


def from_record(data: Mapping[str, Any]) -> ImplementationRecord:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    radius = data["blast_radius"]
    changes = data["changes"]

    return ImplementationRecord(
        implementation_id=ImplementationId(data["implementation_id"]),
        work_id=data["work_id"],
        round=data["round"],
        context_bundle_id=data["context_bundle_id"],
        context_bundle_version=data["context_bundle_version"],
        revision=data["revision"],
        blast_radius=BlastRadiusScope(
            allowed=frozenset(PathPattern(p) for p in radius["allowed"]),
            forbidden=frozenset(PathPattern(p) for p in radius["forbidden"]),
            read_only=frozenset(PathPattern(p) for p in radius["read_only"]),
        ),
        adr_references=frozenset(data["adr_references"]),
        changes=CodeChangeSet(
            revision=changes["revision"],
            base_revision=changes.get("base_revision"),
            files=tuple(
                ChangedFile(
                    path=f["path"],
                    kind=ChangeKind(f["kind"]),
                    content_digest=f.get("content_digest"),
                    previous_path=f.get("previous_path"),
                    lines_added=f["lines_added"],
                    lines_removed=f["lines_removed"],
                )
                for f in changes["files"]
            ),
        ),
        claims=tuple(
            Claim(
                claim_id=ClaimId(c["claim_id"]),
                statement=c["statement"],
                claim_type=ClaimType(c["claim_type"]),
                evidence=frozenset(EvidenceRef(e) for e in c["evidence"]),
                reproduction_hint=c.get("reproduction_hint"),
            )
            for c in data["claims"]
        ),
        assumption_resolutions=tuple(
            AssumptionResolution(
                assumption_id=r["assumption_id"],
                statement=r["statement"],
                outcome=AssumptionOutcome(r["outcome"]),
                evidence=frozenset(EvidenceRef(e) for e in r["evidence"]),
                note=r.get("note"),
                resolved_at=datetime.fromisoformat(r["resolved_at"]),
            )
            for r in data["assumption_resolutions"]
        ),
        risks=tuple(
            RiskDeclaration(
                risk_id=RiskId(r["risk_id"]),
                statement=r["statement"],
                level=RiskLevel(r["level"]),
                mitigation=r.get("mitigation"),
                affected_paths=tuple(r["affected_paths"]),
            )
            for r in data["risks"]
        ),
        criterion_coverage=tuple(
            CriterionCoverage(
                criterion=c["criterion"],
                covering_tests=tuple(c["covering_tests"]),
                negative_check=c.get("negative_check"),
            )
            for c in data["criterion_coverage"]
        ),
        test_executions=tuple(
            TestExecution(
                command=t["command"],
                status=ExecutionStatus(t["status"]),
                revision=t["revision"],
                passed=t["passed"],
                failed=t["failed"],
                skipped=t["skipped"],
                errors=t["errors"],
                duration_seconds=t.get("duration_seconds"),
                suite=t.get("suite"),
                output_digest=t.get("output_digest"),
                executed_at=datetime.fromisoformat(t["executed_at"]),
            )
            for t in data["test_executions"]
        ),
        build_results=tuple(
            BuildResult(
                name=b["name"],
                command=b["command"],
                status=ExecutionStatus(b["status"]),
                revision=b["revision"],
                output_digest=b.get("output_digest"),
                detail=b.get("detail"),
                executed_at=datetime.fromisoformat(b["executed_at"]),
            )
            for b in data["build_results"]
        ),
        deviations=tuple(data["deviations"]),
        status=ImplementationStatus(data["status"]),
        digest=data.get("digest"),
        implementer=data["implementer"],
        expected_assumptions=frozenset(data["expected_assumptions"]),
        started_at=datetime.fromisoformat(data["started_at"]),
        completed_at=(
            datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        ),
        closing_note=data.get("closing_note"),
        superseded_by=(
            ImplementationId(data["superseded_by"]) if data.get("superseded_by") else None
        ),
    )
