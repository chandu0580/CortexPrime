"""Review REST API.

Translation only. Every rule lives in the Review context.

Mounted at ``/api/v1/engineering/review``.

Status codes:

``409`` — the review is decided or superseded, the lens already has a review for
this round, the finding is already resolved. The request was well-formed and
conflicts with what exists.

``422`` — the decision was refused by policy, an approval was attempted over an
open blocker or an unexamined change set, or a blocking finding was waived.
Findings travel in the body; a client told only "refused" has to guess.

``400`` — a malformed value.

``404`` — no such review, or no such finding on it.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.review import (
    AddComment,
    AddFinding,
    ApprovalWithOpenBlockers,
    BlockingFindingCannotBeWaived,
    BlockingFindingWithoutRemedy,
    DecideReview,
    DecisionRefused,
    DuplicateReview,
    ExamineFiles,
    FindingAlreadyResolved,
    FindingWithoutAnchor,
    GetReview,
    InMemoryReviewRepository,
    ListReviews,
    RequestReview,
    ResolveFinding,
    ReviewDecided,
    ReviewIsSuperseded,
    ReviewNotFound,
    ReviewNotStarted,
    ReviewService,
    StartReview,
    SupersedeReview,
    UnexaminedFiles,
    UnknownFinding,
    UnknownLens,
    required_lens_values,
)
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/engineering/review", tags=["Engineering — Review"])

_service = ReviewService(repository=InMemoryReviewRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="engineering-review-api",
        component="review-api",
        source="http",
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

_LENS_PATTERN = "^(correctness|architecture|security|testing|performance)$"
_SEVERITY_PATTERN = "^(blocking|major|minor|nit)$"
_CATEGORY_PATTERN = (
    "^(correctness|architecture|security|testing|performance|maintainability|constitution)$"
)


class RequestIn(BaseModel):
    work_id: str
    lens: str = Field(..., pattern=_LENS_PATTERN)
    implementation_id: str = Field(..., description="The artifact under review")
    implementation_digest: str = Field(
        ..., description="Binds the review to the exact artifact that was submitted"
    )
    revision: str = Field(..., description="The tree being read")
    round: int = Field(1, ge=1)
    files_under_review: List[str] = Field(
        default_factory=list, description="The change set an approval must cover"
    )
    adr_references: List[str] = Field(default_factory=list)
    requested_by: str = "engineering-runtime"


class StartIn(BaseModel):
    reviewer: str = Field(..., description="Everything recorded is attributed to them")


class ExamineIn(BaseModel):
    paths: List[str] = Field(..., min_length=1)


class FindingIn(BaseModel):
    summary: str
    severity: str = Field("minor", pattern=_SEVERITY_PATTERN)
    category: str = Field("correctness", pattern=_CATEGORY_PATTERN)
    detail: str = ""
    path: Optional[str] = None
    line: Optional[int] = Field(None, ge=1)
    end_line: Optional[int] = Field(None, ge=1)
    evidence: List[str] = Field(default_factory=list)
    required_change: Optional[str] = Field(
        None, description="Required for a blocking finding: what would clear it"
    )
    raised_by: Optional[str] = None


class ResolveIn(BaseModel):
    resolution: str = Field("fixed", pattern="^(fixed|withdrawn|accepted_risk)$")
    note: Optional[str] = None
    resolved_by: Optional[str] = None


class CommentIn(BaseModel):
    body: str
    author: Optional[str] = None
    path: Optional[str] = None
    line: Optional[int] = Field(None, ge=1)
    in_reply_to: Optional[str] = None


class DecideIn(BaseModel):
    decision: str = Field(..., pattern="^(approved|changes_requested|rejected)$")
    rationale: Optional[str] = None
    decided_by: Optional[str] = None


class SupersedeIn(BaseModel):
    successor_id: str
    reason: str = "a later round replaces this one"


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render_finding(f) -> dict:
    return {
        "finding_id": str(f.finding_id),
        "work_id": f.work_id,
        "implementation_id": f.implementation_id,
        "summary": f.summary,
        "detail": f.detail,
        "severity": f.severity.value,
        "category": f.category.value,
        "blocking": f.severity.blocks_approval,
        "location": str(f.location) if f.location else None,
        "evidence": list(f.evidence_ids),
        "required_change": f.required_change,
        "state": f.state.value,
        "resolution": f.resolution.value if f.resolution else None,
        "resolution_note": f.resolution_note,
        "raised_by": f.raised_by,
        "resolved_by": f.resolved_by,
    }


def _render(review) -> dict:
    return {
        "review_id": str(review.review_id),
        "work_id": review.work_id,
        "round": review.round,
        "lens": review.lens.value,
        "lens_mandate": review.lens.mandate,
        "status": review.status.value,
        "decision": review.decision.value if review.decision else None,
        "decision_rationale": review.decision_rationale,
        "implementation_id": review.implementation_id,
        "implementation_digest": review.implementation_digest,
        "revision": review.revision,
        "adr_references": sorted(review.adr_references),
        "digest": review.digest,
        "requested_by": review.requested_by,
        "reviewer": review.reviewer,
        "files_under_review": list(review.files_under_review),
        "files_examined": list(review.files_examined),
        "unexamined_files": list(review.unexamined_files),
        "coverage_ratio": round(review.coverage_ratio, 4),
        "findings": [_render_finding(f) for f in review.findings],
        "open_blocking_findings": len(review.open_blockers),
        "advisory_findings": len(review.advisory_findings),
        "accepted_risks": [str(f.finding_id) for f in review.accepted_risks],
        "comments": [
            {
                "comment_id": str(c.comment_id),
                "body": c.body,
                "author": c.author,
                "location": str(c.location) if c.location else None,
                "in_reply_to": str(c.in_reply_to) if c.in_reply_to else None,
            }
            for c in review.comments
        ],
        "superseded_by": str(review.superseded_by) if review.superseded_by else None,
    }


def _handle(operation):
    try:
        return operation()
    except (ReviewNotFound, UnknownFinding) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except DecisionRefused as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "decision_refused",
                "message": str(exc),
                "decision": exc.decision,
                "failures": [
                    {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                    for f in exc.failures
                ],
            },
        ) from exc
    except ApprovalWithOpenBlockers as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "approval_with_open_blockers",
                "message": str(exc),
                "open_findings": [
                    {"finding_id": str(f.finding_id), "summary": f.summary, "anchor": f.anchor}
                    for f in exc.open_findings
                ],
            },
        ) from exc
    except UnexaminedFiles as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "unexamined_files",
                "message": str(exc),
                "unexamined": list(exc.unexamined),
            },
        ) from exc
    except BlockingFindingCannotBeWaived as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "blocking_finding_cannot_be_waived",
                "message": str(exc),
                "finding_id": exc.finding_id,
            },
        ) from exc
    except (ReviewDecided, ReviewIsSuperseded, DuplicateReview, FindingAlreadyResolved) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ReviewNotStarted as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except (FindingWithoutAnchor, BlockingFindingWithoutRemedy, UnknownLens) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/lenses", summary="The lenses a round must be read through")
async def lenses_route():
    from backend.contexts.review import ReviewLens

    return {
        "required": list(required_lens_values()),
        "all": [
            {"lens": lens.value, "required": lens.is_required, "mandate": lens.mandate}
            for lens in ReviewLens
        ],
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Open a review for one lens")
async def request_route(payload: RequestIn):
    def run():
        result = _service.request(
            _context(),
            RequestReview(
                work_id=payload.work_id,
                lens=payload.lens,
                implementation_id=payload.implementation_id,
                implementation_digest=payload.implementation_digest,
                revision=payload.revision,
                round=payload.round,
                files_under_review=tuple(payload.files_under_review),
                adr_references=tuple(payload.adr_references),
                requested_by=payload.requested_by,
            ),
        )
        return {"review": _render(result.review), "events": list(result.event_types)}

    return _handle(run)


@router.get("", summary="List reviews")
async def list_route(
    work_id: Optional[str] = Query(None),
    round: Optional[int] = Query(None, ge=1),
    lens: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None, alias="status"),
):
    def run():
        found = _service.list(
            _context(),
            ListReviews(work_id=work_id, round=round, lens=lens, status=review_status),
        )
        return {"count": len(found), "reviews": [_render(r) for r in found]}

    return _handle(run)


@router.get("/coverage", summary="Which required lenses have reported on a round")
async def coverage_route(work_id: str = Query(...), round: int = Query(1, ge=1)):
    def run():
        coverage = _service.lens_coverage(_context(), work_id, round)
        return {
            "work_id": coverage.work_id,
            "round": coverage.round,
            "required": list(coverage.required),
            "decided": list(coverage.decided),
            "approved": list(coverage.approved),
            "missing": list(coverage.missing),
            "complete": coverage.complete,
            "fully_approved": coverage.fully_approved,
        }

    return _handle(run)


@router.get("/{review_id}", summary="Fetch a review")
async def get_route(review_id: str = Path(...)):
    return _handle(
        lambda: _render(_service.get(_context(), GetReview(review_id=review_id)))
    )


@router.get("/{review_id}/policy", summary="Run the review policy without deciding")
async def policy_route(
    review_id: str = Path(...),
    decision: str = Query("approved", pattern="^(approved|changes_requested|rejected)$"),
):
    def run():
        report = _service.evaluate(_context(), review_id, decision)
        return {
            "decision": decision,
            "may_decide": report.may_decide,
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


@router.post("/{review_id}/start", summary="Take up the review")
async def start_route(payload: StartIn, review_id: str = Path(...)):
    def run():
        result = _service.start(
            _context(), StartReview(review_id=review_id, reviewer=payload.reviewer)
        )
        return {"review": _render(result.review), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{review_id}/examine", summary="Record files that were read")
async def examine_route(payload: ExamineIn, review_id: str = Path(...)):
    def run():
        result = _service.examine(
            _context(), ExamineFiles(review_id=review_id, paths=tuple(payload.paths))
        )
        return {"review": _render(result.review)}

    return _handle(run)


@router.post("/{review_id}/findings", summary="Raise a finding")
async def add_finding_route(payload: FindingIn, review_id: str = Path(...)):
    def run():
        result = _service.add_finding(
            _context(),
            AddFinding(
                review_id=review_id,
                summary=payload.summary,
                severity=payload.severity,
                category=payload.category,
                detail=payload.detail,
                path=payload.path,
                line=payload.line,
                end_line=payload.end_line,
                evidence=tuple(payload.evidence),
                required_change=payload.required_change,
                raised_by=payload.raised_by,
            ),
        )
        return {"review": _render(result.review), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{review_id}/findings/{finding_id}/resolve", summary="Resolve a finding")
async def resolve_finding_route(
    payload: ResolveIn, review_id: str = Path(...), finding_id: str = Path(...)
):
    def run():
        result = _service.resolve_finding(
            _context(),
            ResolveFinding(
                review_id=review_id,
                finding_id=finding_id,
                resolution=payload.resolution,
                note=payload.note,
                resolved_by=payload.resolved_by,
            ),
        )
        return {"review": _render(result.review), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{review_id}/comments", summary="Add a comment")
async def add_comment_route(payload: CommentIn, review_id: str = Path(...)):
    def run():
        result = _service.add_comment(
            _context(),
            AddComment(
                review_id=review_id,
                body=payload.body,
                author=payload.author,
                path=payload.path,
                line=payload.line,
                in_reply_to=payload.in_reply_to,
            ),
        )
        return {"review": _render(result.review)}

    return _handle(run)


@router.post("/{review_id}/decide", summary="Conclude the review and bind its digest")
async def decide_route(payload: DecideIn, review_id: str = Path(...)):
    def run():
        result = _service.decide(
            _context(),
            DecideReview(
                review_id=review_id,
                decision=payload.decision,
                rationale=payload.rationale,
                decided_by=payload.decided_by,
            ),
        )
        return {"review": _render(result.review), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{review_id}/supersede", summary="Replace with a later review")
async def supersede_route(payload: SupersedeIn, review_id: str = Path(...)):
    def run():
        result = _service.supersede(
            _context(),
            SupersedeReview(
                review_id=review_id,
                successor_id=payload.successor_id,
                reason=payload.reason,
            ),
        )
        return {"review": _render(result.review), "events": list(result.event_types)}

    return _handle(run)
