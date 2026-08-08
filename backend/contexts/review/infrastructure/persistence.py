"""Mapping between the ReviewRecord aggregate and a storable record.

Storage-agnostic: a plain mapping of primitives.

Every invariant is re-checked on the way in, and the digest is **restored, not
recomputed**. Recomputing would make it always match -- a check that cannot fail
-- and this is one of the two artifacts where that check is the whole point: it
is how a reader knows the judgement on record is the one that was issued.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.errors import ContractViolation
from backend.contexts.review.domain.decision import ReviewDecision
from backend.contexts.review.domain.findings import (
    CodeLocation,
    EvidenceRef,
    FindingCategory,
    FindingState,
    Resolution,
    ReviewComment,
    ReviewFinding,
    ReviewSeverity,
)
from backend.contexts.review.domain.identifiers import CommentId, FindingId, ReviewId
from backend.contexts.review.domain.lenses import ReviewLens
from backend.contexts.review.domain.record import ReviewRecord, ReviewStatus

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def _location_to(location) -> Any:
    if location is None:
        return None
    return {"path": location.path, "line": location.line, "end_line": location.end_line}


def _location_from(data) -> Any:
    if not data:
        return None
    return CodeLocation(
        path=data["path"], line=data.get("line"), end_line=data.get("end_line")
    )


def to_record(review: ReviewRecord, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation(
            "tenant_id must be non-blank; it is derived from the context"
        )

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "review_id": str(review.review_id),
        "work_id": review.work_id,
        "round": review.round,
        "lens": review.lens.value,
        "implementation_id": review.implementation_id,
        "implementation_digest": review.implementation_digest,
        "revision": review.revision,
        "adr_references": sorted(review.adr_references),
        "files_under_review": list(review.files_under_review),
        "files_examined": list(review.files_examined),
        "findings": [
            {
                "finding_id": str(f.finding_id),
                "work_id": f.work_id,
                "implementation_id": f.implementation_id,
                "summary": f.summary,
                "severity": f.severity.value,
                "category": f.category.value,
                "detail": f.detail,
                "location": _location_to(f.location),
                "evidence": list(f.evidence_ids),
                "required_change": f.required_change,
                "raised_by": f.raised_by,
                "raised_at": f.raised_at.isoformat(),
                "state": f.state.value,
                "resolution": f.resolution.value if f.resolution else None,
                "resolution_note": f.resolution_note,
                "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
                "resolved_by": f.resolved_by,
            }
            for f in review.findings
        ],
        "comments": [
            {
                "comment_id": str(c.comment_id),
                "body": c.body,
                "author": c.author,
                "location": _location_to(c.location),
                "in_reply_to": str(c.in_reply_to) if c.in_reply_to else None,
                "written_at": c.written_at.isoformat(),
            }
            for c in review.comments
        ],
        "status": review.status.value,
        "decision": review.decision.value if review.decision else None,
        "decision_rationale": review.decision_rationale,
        "digest": review.digest,
        "requested_by": review.requested_by,
        "reviewer": review.reviewer,
        "requested_at": review.requested_at.isoformat(),
        "started_at": review.started_at.isoformat() if review.started_at else None,
        "decided_at": review.decided_at.isoformat() if review.decided_at else None,
        "superseded_by": str(review.superseded_by) if review.superseded_by else None,
    }


def from_record(data: Mapping[str, Any]) -> ReviewRecord:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    return ReviewRecord(
        review_id=ReviewId(data["review_id"]),
        work_id=data["work_id"],
        round=data["round"],
        lens=ReviewLens(data["lens"]),
        implementation_id=data["implementation_id"],
        implementation_digest=data["implementation_digest"],
        revision=data["revision"],
        adr_references=frozenset(data["adr_references"]),
        files_under_review=tuple(data["files_under_review"]),
        files_examined=tuple(data["files_examined"]),
        findings=tuple(
            ReviewFinding(
                finding_id=FindingId(f["finding_id"]),
                work_id=f["work_id"],
                implementation_id=f["implementation_id"],
                summary=f["summary"],
                severity=ReviewSeverity(f["severity"]),
                category=FindingCategory(f["category"]),
                detail=f.get("detail", ""),
                location=_location_from(f.get("location")),
                evidence=frozenset(EvidenceRef(e) for e in f["evidence"]),
                required_change=f.get("required_change"),
                raised_by=f["raised_by"],
                raised_at=datetime.fromisoformat(f["raised_at"]),
                state=FindingState(f["state"]),
                resolution=Resolution(f["resolution"]) if f.get("resolution") else None,
                resolution_note=f.get("resolution_note"),
                resolved_at=(
                    datetime.fromisoformat(f["resolved_at"])
                    if f.get("resolved_at")
                    else None
                ),
                resolved_by=f.get("resolved_by"),
            )
            for f in data["findings"]
        ),
        comments=tuple(
            ReviewComment(
                comment_id=CommentId(c["comment_id"]),
                body=c["body"],
                author=c["author"],
                location=_location_from(c.get("location")),
                in_reply_to=FindingId(c["in_reply_to"]) if c.get("in_reply_to") else None,
                written_at=datetime.fromisoformat(c["written_at"]),
            )
            for c in data["comments"]
        ),
        status=ReviewStatus(data["status"]),
        decision=ReviewDecision(data["decision"]) if data.get("decision") else None,
        decision_rationale=data.get("decision_rationale"),
        digest=data.get("digest"),
        requested_by=data["requested_by"],
        reviewer=data.get("reviewer"),
        requested_at=datetime.fromisoformat(data["requested_at"]),
        started_at=(
            datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
        ),
        decided_at=(
            datetime.fromisoformat(data["decided_at"]) if data.get("decided_at") else None
        ),
        superseded_by=ReviewId(data["superseded_by"]) if data.get("superseded_by") else None,
    )
