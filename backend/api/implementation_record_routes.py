"""ImplementationRecord REST API.

Translation only. Every rule lives in the ImplementationRecord context.

Mounted at ``/api/v1/engineering/implementation``.

Status codes:

``409`` — the record is complete or superseded, the claim or assumption is
already recorded. The request was well-formed and conflicts with what exists.

``422`` — completion refused by policy, or a file outside the blast radius.
Findings travel in the body; a client told only "refused" has to guess.

``400`` — a malformed value.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.implementation_record import (
    AbandonImplementation,
    AddClaim,
    AssumptionAlreadyResolved,
    ClaimWithoutEvidence,
    CompleteImplementation,
    DeclareRisk,
    DuplicateClaim,
    GetImplementation,
    ImplementationRecordService,
    IncompleteRecord,
    InMemoryImplementationRepository,
    ListImplementations,
    NoteDeviation,
    OutsideBlastRadius,
    RecordBuild,
    RecordCompleted,
    RecordCoverage,
    RecordFile,
    RecordNotFound,
    RecordSuperseded,
    RecordTests,
    ResolveAssumption,
    StartImplementation,
    SupersedeImplementation,
    UnknownAssumption,
)
from backend.platform.context import ExecutionContext

router = APIRouter(
    prefix="/api/v1/engineering/implementation", tags=["Engineering — ImplementationRecord"]
)

_service = ImplementationRecordService(repository=InMemoryImplementationRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="engineering-implementation-api",
        component="implementation-record-api",
        source="http",
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


class StartIn(BaseModel):
    work_id: str
    context_bundle_id: str = Field(..., description="What the implementer was given to see")
    revision: str = Field(..., description="The tree this change is against")
    blast_radius_allowed: List[str] = Field(..., min_length=1)
    round: int = Field(1, ge=1)
    context_bundle_version: int = Field(1, ge=1)
    blast_radius_forbidden: List[str] = Field(default_factory=list)
    blast_radius_read_only: List[str] = Field(default_factory=list)
    adr_references: List[str] = Field(default_factory=list)
    expected_assumptions: List[str] = Field(
        default_factory=list, description="Assumption ids the WorkOrder declared"
    )
    implementer: str = "implementer"


class FileIn(BaseModel):
    path: str
    kind: str = Field("modified", pattern="^(added|modified|deleted|renamed)$")
    content_digest: Optional[str] = None
    previous_path: Optional[str] = None
    lines_added: int = Field(0, ge=0)
    lines_removed: int = Field(0, ge=0)


class ClaimIn(BaseModel):
    statement: str
    claim_type: str = Field(
        "behaviour", pattern="^(count|behaviour|absence|equivalence|performance)$"
    )
    evidence: List[str] = Field(
        ..., min_length=1, description="A claim a verifier cannot attack is taken on trust"
    )
    reproduction_hint: Optional[str] = None


class AssumptionIn(BaseModel):
    assumption_id: str
    statement: str
    outcome: str = Field(..., pattern="^(confirmed|contradicted|unverifiable)$")
    evidence: List[str] = Field(..., min_length=1)
    note: Optional[str] = None


class RiskIn(BaseModel):
    statement: str
    level: str = Field("low", pattern="^(low|medium|high)$")
    mitigation: Optional[str] = None
    affected_paths: List[str] = Field(default_factory=list)


class TestsIn(BaseModel):
    command: str = Field(..., description="The exact command a verifier can re-run")
    status: str = Field("passed", pattern="^(passed|failed|errored|not_run)$")
    revision: Optional[str] = None
    passed: int = Field(0, ge=0)
    failed: int = Field(0, ge=0)
    skipped: int = Field(0, ge=0)
    errors: int = Field(0, ge=0)
    suite: Optional[str] = None


class BuildIn(BaseModel):
    name: str
    command: str
    status: str = Field("passed", pattern="^(passed|failed|errored|not_run)$")
    revision: Optional[str] = None
    detail: Optional[str] = None


class CoverageIn(BaseModel):
    criterion: str
    covering_tests: List[str] = Field(..., min_length=1)
    negative_check: Optional[str] = None


class DeviationIn(BaseModel):
    deviation: str


class AbandonIn(BaseModel):
    reason: str


class SupersedeIn(BaseModel):
    successor_id: str
    reason: str = "a later round replaces this one"


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(record) -> dict:
    return {
        "implementation_id": str(record.implementation_id),
        "work_id": record.work_id,
        "round": record.round,
        "status": record.status.value,
        "revision": record.revision,
        "context_bundle_id": record.context_bundle_id,
        "context_bundle_version": record.context_bundle_version,
        "adr_references": sorted(record.adr_references),
        "digest": record.digest,
        "implementer": record.implementer,
        "blast_radius": {"allowed": list(record.blast_radius.allowed_patterns)},
        "changes": {
            "revision": record.changes.revision,
            "files": [
                {
                    "path": f.path,
                    "kind": f.kind.value,
                    "lines_added": f.lines_added,
                    "lines_removed": f.lines_removed,
                }
                for f in record.changes.files
            ],
            "lines_added": record.changes.lines_added,
            "lines_removed": record.changes.lines_removed,
        },
        "claims": [
            {
                "claim_id": str(c.claim_id),
                "statement": c.statement,
                "claim_type": c.claim_type.value,
                "evidence": list(c.evidence_ids),
                "needs_adversarial_verification": c.claim_type.needs_adversarial_verification,
            }
            for c in record.claims
        ],
        "assumption_resolutions": [
            {
                "assumption_id": r.assumption_id,
                "outcome": r.outcome.value,
                "evidence": sorted(str(e) for e in r.evidence),
            }
            for r in record.assumption_resolutions
        ],
        "unresolved_assumptions": list(record.unresolved_assumptions),
        "risks": [
            {
                "risk_id": str(r.risk_id),
                "statement": r.statement,
                "level": r.level.value,
                "mitigation": r.mitigation,
            }
            for r in record.risks
        ],
        "criterion_coverage": [
            {
                "criterion": c.criterion,
                "covering_tests": list(c.covering_tests),
                "has_negative_check": c.has_negative_check,
            }
            for c in record.criterion_coverage
        ],
        "test_executions": [
            {
                "command": t.command,
                "status": t.status.value,
                "passed": t.passed,
                "failed": t.failed,
                "skipped": t.skipped,
                "errors": t.errors,
            }
            for t in record.test_executions
        ],
        "build_results": [
            {"name": b.name, "status": b.status.value, "detail": b.detail}
            for b in record.build_results
        ],
        "deviations": list(record.deviations),
        "paths_outside_radius": list(record.paths_outside_radius),
        "superseded_by": str(record.superseded_by) if record.superseded_by else None,
        "closing_note": record.closing_note,
    }


def _handle(operation):
    try:
        return operation()
    except RecordNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except UnknownAssumption as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except IncompleteRecord as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "incomplete_record",
                "message": str(exc),
                "failures": [
                    {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                    for f in exc.failures
                ],
            },
        ) from exc
    except OutsideBlastRadius as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "outside_blast_radius",
                "message": str(exc),
                "path": exc.path,
                "reason": exc.reason,
                "allowed": list(exc.allowed),
            },
        ) from exc
    except (RecordCompleted, RecordSuperseded, DuplicateClaim, AssumptionAlreadyResolved) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ClaimWithoutEvidence as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Open an implementation record")
async def start_route(payload: StartIn):
    def run():
        result = _service.start(
            _context(),
            StartImplementation(
                work_id=payload.work_id,
                context_bundle_id=payload.context_bundle_id,
                revision=payload.revision,
                blast_radius_allowed=tuple(payload.blast_radius_allowed),
                round=payload.round,
                context_bundle_version=payload.context_bundle_version,
                blast_radius_forbidden=tuple(payload.blast_radius_forbidden),
                blast_radius_read_only=tuple(payload.blast_radius_read_only),
                adr_references=tuple(payload.adr_references),
                expected_assumptions=tuple(payload.expected_assumptions),
                implementer=payload.implementer,
            ),
        )
        return {"implementation": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.get("", summary="List implementation records")
async def list_route(
    work_id: Optional[str] = Query(None),
    record_status: Optional[str] = Query(None, alias="status"),
):
    def run():
        found = _service.list(
            _context(), ListImplementations(work_id=work_id, status=record_status)
        )
        return {"count": len(found), "implementations": [_render(r) for r in found]}

    return _handle(run)


@router.get("/{implementation_id}", summary="Fetch a record")
async def get_route(implementation_id: str = Path(...)):
    return _handle(
        lambda: _render(
            _service.get(
                _context(), GetImplementation(implementation_id=implementation_id)
            )
        )
    )


@router.get("/{implementation_id}/policy", summary="Run completion policy without completing")
async def policy_route(implementation_id: str = Path(...)):
    def run():
        report = _service.evaluate(_context(), implementation_id)
        return {
            "may_complete": report.may_complete,
            "blocking": [
                {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                for f in report.blocking
            ],
            "advisory": [
                {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                for f in report.advisory
            ],
        }

    return _handle(run)


@router.post("/{implementation_id}/files", summary="Record a changed file")
async def record_file_route(payload: FileIn, implementation_id: str = Path(...)):
    def run():
        result = _service.record_file(
            _context(),
            RecordFile(
                implementation_id=implementation_id,
                path=payload.path,
                kind=payload.kind,
                content_digest=payload.content_digest,
                previous_path=payload.previous_path,
                lines_added=payload.lines_added,
                lines_removed=payload.lines_removed,
            ),
        )
        return {"implementation": _render(result.record)}

    return _handle(run)


@router.post("/{implementation_id}/claims", summary="Add a claim with its evidence")
async def add_claim_route(payload: ClaimIn, implementation_id: str = Path(...)):
    def run():
        result = _service.add_claim(
            _context(),
            AddClaim(
                implementation_id=implementation_id,
                statement=payload.statement,
                claim_type=payload.claim_type,
                evidence=tuple(payload.evidence),
                reproduction_hint=payload.reproduction_hint,
            ),
        )
        return {"implementation": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{implementation_id}/assumptions", summary="Resolve a WorkOrder assumption")
async def resolve_assumption_route(payload: AssumptionIn, implementation_id: str = Path(...)):
    def run():
        result = _service.resolve_assumption(
            _context(),
            ResolveAssumption(
                implementation_id=implementation_id,
                assumption_id=payload.assumption_id,
                statement=payload.statement,
                outcome=payload.outcome,
                evidence=tuple(payload.evidence),
                note=payload.note,
            ),
        )
        return {"implementation": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{implementation_id}/risks", summary="Declare a risk")
async def declare_risk_route(payload: RiskIn, implementation_id: str = Path(...)):
    def run():
        result = _service.declare_risk(
            _context(),
            DeclareRisk(
                implementation_id=implementation_id,
                statement=payload.statement,
                level=payload.level,
                mitigation=payload.mitigation,
                affected_paths=tuple(payload.affected_paths),
            ),
        )
        return {"implementation": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{implementation_id}/tests", summary="Record a test run")
async def record_tests_route(payload: TestsIn, implementation_id: str = Path(...)):
    def run():
        result = _service.record_tests(
            _context(),
            RecordTests(
                implementation_id=implementation_id,
                command=payload.command,
                status=payload.status,
                revision=payload.revision,
                passed=payload.passed,
                failed=payload.failed,
                skipped=payload.skipped,
                errors=payload.errors,
                suite=payload.suite,
            ),
        )
        return {"implementation": _render(result.record)}

    return _handle(run)


@router.post("/{implementation_id}/builds", summary="Record a build or gate result")
async def record_build_route(payload: BuildIn, implementation_id: str = Path(...)):
    def run():
        result = _service.record_build(
            _context(),
            RecordBuild(
                implementation_id=implementation_id,
                name=payload.name,
                command=payload.command,
                status=payload.status,
                revision=payload.revision,
                detail=payload.detail,
            ),
        )
        return {"implementation": _render(result.record)}

    return _handle(run)


@router.post("/{implementation_id}/coverage", summary="Map an acceptance criterion to tests")
async def record_coverage_route(payload: CoverageIn, implementation_id: str = Path(...)):
    def run():
        result = _service.record_coverage(
            _context(),
            RecordCoverage(
                implementation_id=implementation_id,
                criterion=payload.criterion,
                covering_tests=tuple(payload.covering_tests),
                negative_check=payload.negative_check,
            ),
        )
        return {"implementation": _render(result.record)}

    return _handle(run)


@router.post("/{implementation_id}/deviations", summary="Note a departure from the spec")
async def note_deviation_route(payload: DeviationIn, implementation_id: str = Path(...)):
    def run():
        result = _service.note_deviation(
            _context(),
            NoteDeviation(
                implementation_id=implementation_id, deviation=payload.deviation
            ),
        )
        return {"implementation": _render(result.record)}

    return _handle(run)


@router.post("/{implementation_id}/complete", summary="Seal the record and bind its digest")
async def complete_route(implementation_id: str = Path(...)):
    def run():
        result = _service.complete(
            _context(), CompleteImplementation(implementation_id=implementation_id)
        )
        return {"implementation": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{implementation_id}/abandon", summary="Close without submitting")
async def abandon_route(payload: AbandonIn, implementation_id: str = Path(...)):
    def run():
        result = _service.abandon(
            _context(),
            AbandonImplementation(
                implementation_id=implementation_id, reason=payload.reason
            ),
        )
        return {"implementation": _render(result.record)}

    return _handle(run)


@router.post("/{implementation_id}/supersede", summary="Replace with a later round")
async def supersede_route(payload: SupersedeIn, implementation_id: str = Path(...)):
    def run():
        result = _service.supersede(
            _context(),
            SupersedeImplementation(
                implementation_id=implementation_id,
                successor_id=payload.successor_id,
                reason=payload.reason,
            ),
        )
        return {"implementation": _render(result.record), "events": list(result.event_types)}

    return _handle(run)
