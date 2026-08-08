"""Verification REST API.

Translation only. Every rule lives in the Verification context.

Mounted at ``/api/v1/engineering/verification``, beside the WorkOrder and Runtime
APIs. Three paths rather than one, because a client that could close a
verification through the WorkOrder API would be doing exactly what this context
exists to prevent.

Status codes:

``409`` — the record is closed, the claim is already settled, or the reproduction
cannot establish what the claim asserts. All mean the request was well-formed and
conflicts with what is already recorded.

``422`` — policy refuses completion. Findings travel in the body.

``400`` — a malformed value, including borrowed evidence.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.engineering_verification import (
    AddEvidence,
    BorrowedEvidence,
    ClaimAlreadyResolved,
    ClaimInput,
    ClaimNotRequested,
    CloseVerification,
    GetVerification,
    InMemoryVerificationRepository,
    ListVerifications,
    MarkStale,
    RecordClaimResult,
    ReproductionInadequate,
    RequestVerification,
    StartVerification,
    SupersedeVerification,
    VerificationAlreadyClosed,
    VerificationNotFound,
    VerificationNotStarted,
    VerificationService,
)
from backend.platform.context import ExecutionContext

router = APIRouter(
    prefix="/api/v1/engineering/verification", tags=["Engineering — Verification"]
)

_service = VerificationService(repository=InMemoryVerificationRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="engineering-verification-api", component="verification-api", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


class ClaimIn(BaseModel):
    statement: str = Field(..., description="The assertion under verification")
    claim_type: str = Field(
        "behaviour", pattern="^(count|behaviour|absence|equivalence|performance)$"
    )
    asserted_evidence: List[str] = Field(
        default_factory=list,
        description="The implementer's evidence references. Recorded so they cannot be reused.",
    )
    hint: Optional[str] = None


class RequestIn(BaseModel):
    work_id: str
    base_commit: str = Field(..., description="The tree every claim must be reproduced against")
    claims: List[ClaimIn] = Field(..., min_length=1)
    attempt: int = Field(1, ge=1)
    requested_by: str = "engineering-runtime"


class StartIn(BaseModel):
    verifier: str = Field(..., description="A verdict has an author")


class ResultIn(BaseModel):
    claim_id: str
    verdict: str = Field(..., pattern="^(reproduced|contradicted|unreproducible|out_of_scope)$")
    observed: str = Field(..., description="What actually happened")
    method: str = Field(
        "command_execution",
        pattern="^(command_execution|source_inspection|adversarial_construction|negative_check)$",
    )
    specification: str = Field("", description="Exactly what was run, inspected, or constructed")
    determinism: str = Field(
        "deterministic", pattern="^(deterministic|environment_dependent|nondeterministic)$"
    )
    runs: int = Field(1, ge=1)
    evidence_summary: str = Field("", description="The evidence the verifier produced")
    evidence_kind: str = Field(
        "command", pattern="^(repository|command|adr|test|external|absence)$"
    )
    evidence_trust: str = Field(
        "environmental", pattern="^(deterministic|environmental|observed)$"
    )
    evidence_base_commit: Optional[str] = None
    note: Optional[str] = None


class EvidenceIn(BaseModel):
    summary: str
    kind: str = Field("command", pattern="^(repository|command|adr|test|external|absence)$")
    trust: str = Field("environmental", pattern="^(deterministic|environmental|observed)$")
    base_commit: Optional[str] = None
    detail: Optional[str] = None


class CloseIn(BaseModel):
    current_commit: Optional[str] = Field(
        None, description="If supplied, evidence collected elsewhere is refused as stale"
    )
    force_outcome: Optional[str] = Field(
        None, pattern="^invalidated$",
        description="Only 'invalidated' may be forced; every other outcome is derived",
    )
    note: Optional[str] = None


class SupersedeIn(BaseModel):
    successor_id: str
    reason: str = "a later attempt replaces this one"


class StaleIn(BaseModel):
    current_commit: str


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(record) -> dict:
    weakest = record.weakest_trust
    return {
        "verification_id": str(record.verification_id),
        "work_id": record.work_id,
        "attempt": record.attempt,
        "base_commit": record.base_commit,
        "status": record.status.value,
        "verifier": record.verifier,
        "claims": [
            {
                "claim_id": str(c.claim_id),
                "statement": c.statement,
                "claim_type": c.claim_type.value,
                "asserted_evidence": sorted(str(e) for e in c.asserted_evidence),
            }
            for c in record.request.claims
        ],
        "results": [
            {
                "claim_id": str(r.claim_id),
                "verdict": r.verdict.value,
                "observed": r.observed,
                "method": r.reproduction.method.value,
                "determinism": r.reproduction.determinism.value,
                "evidence": (
                    {
                        "evidence_id": str(r.verdict_evidence.evidence_id),
                        "kind": r.verdict_evidence.kind.value,
                        "trust": r.verdict_evidence.trust.value,
                        "summary": r.verdict_evidence.summary,
                    }
                    if r.verdict_evidence
                    else None
                ),
                "note": r.note,
            }
            for r in record.results
        ],
        "outstanding_claims": [str(c.claim_id) for c in record.outstanding_claims],
        "weakest_trust": weakest.value if weakest else None,
        "closing_note": record.closing_note,
        "superseded_by": str(record.superseded_by) if record.superseded_by else None,
    }


def _handle(operation):
    try:
        return operation()
    except VerificationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (
        VerificationAlreadyClosed,
        ClaimAlreadyResolved,
        ReproductionInadequate,
        VerificationNotStarted,
    ) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ClaimNotRequested as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except BorrowedEvidence as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "borrowed_evidence",
                "message": str(exc),
                "claim_id": exc.claim_id,
                "evidence_id": exc.evidence_id,
            },
        ) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Request a verification")
async def request_route(payload: RequestIn):
    def run():
        result = _service.request(
            _context(),
            RequestVerification(
                work_id=payload.work_id,
                base_commit=payload.base_commit,
                attempt=payload.attempt,
                requested_by=payload.requested_by,
                claims=tuple(
                    ClaimInput(
                        statement=c.statement,
                        claim_type=c.claim_type,
                        asserted_evidence=tuple(c.asserted_evidence),
                        hint=c.hint,
                    )
                    for c in payload.claims
                ),
            ),
        )
        return {
            "verification": _render(result.record),
            "events": list(result.event_types),
        }

    return _handle(run)


@router.get("", summary="List verifications")
async def list_route(
    work_id: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None, alias="status"),
    open_only: bool = Query(False),
):
    def run():
        found = _service.list(
            _context(),
            ListVerifications(
                work_id=work_id, status=verification_status, open_only=open_only
            ),
        )
        return {"count": len(found), "verifications": [_render(r) for r in found]}

    return _handle(run)


@router.get("/{verification_id}", summary="Fetch a verification")
async def get_route(verification_id: str = Path(...)):
    return _handle(
        lambda: _render(
            _service.get(_context(), GetVerification(verification_id=verification_id))
        )
    )


@router.get("/{verification_id}/policy", summary="Run policy without closing")
async def policy_route(
    verification_id: str = Path(...), current_commit: Optional[str] = Query(None)
):
    def run():
        report = _service.evaluate(_context(), verification_id, current_commit)
        return {
            "may_complete": report.may_complete,
            "outcome": report.outcome.value,
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


@router.post("/{verification_id}/start", summary="Claim the verification")
async def start_route(payload: StartIn, verification_id: str = Path(...)):
    def run():
        result = _service.start(
            _context(),
            StartVerification(verification_id=verification_id, verifier=payload.verifier),
        )
        return {"verification": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{verification_id}/results", summary="Record a verdict on one claim")
async def record_result_route(payload: ResultIn, verification_id: str = Path(...)):
    def run():
        result = _service.record_result(
            _context(),
            RecordClaimResult(
                verification_id=verification_id,
                claim_id=payload.claim_id,
                verdict=payload.verdict,
                observed=payload.observed,
                method=payload.method,
                specification=payload.specification,
                determinism=payload.determinism,
                runs=payload.runs,
                evidence_summary=payload.evidence_summary,
                evidence_kind=payload.evidence_kind,
                evidence_trust=payload.evidence_trust,
                evidence_base_commit=payload.evidence_base_commit,
                note=payload.note,
            ),
        )
        return {"verification": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{verification_id}/evidence", summary="Attach run-wide evidence")
async def add_evidence_route(payload: EvidenceIn, verification_id: str = Path(...)):
    def run():
        result = _service.add_evidence(
            _context(),
            AddEvidence(
                verification_id=verification_id,
                summary=payload.summary,
                kind=payload.kind,
                trust=payload.trust,
                base_commit=payload.base_commit,
                detail=payload.detail,
            ),
        )
        return {"verification": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{verification_id}/close", summary="Close with the outcome policy determined")
async def close_route(payload: CloseIn, verification_id: str = Path(...)):
    def run():
        result = _service.close(
            _context(),
            CloseVerification(
                verification_id=verification_id,
                current_commit=payload.current_commit,
                force_outcome=payload.force_outcome,
                note=payload.note,
            ),
        )
        return {"verification": _render(result.record), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{verification_id}/stale", summary="Mark stale after the base moved")
async def stale_route(payload: StaleIn, verification_id: str = Path(...)):
    def run():
        result = _service.mark_stale(
            _context(),
            MarkStale(verification_id=verification_id, current_commit=payload.current_commit),
        )
        return {"verification": _render(result.record)}

    return _handle(run)


@router.post("/{verification_id}/supersede", summary="Replace with a later attempt")
async def supersede_route(payload: SupersedeIn, verification_id: str = Path(...)):
    def run():
        result = _service.supersede(
            _context(),
            SupersedeVerification(
                verification_id=verification_id,
                successor_id=payload.successor_id,
                reason=payload.reason,
            ),
        )
        return {"verification": _render(result.record), "events": list(result.event_types)}

    return _handle(run)
