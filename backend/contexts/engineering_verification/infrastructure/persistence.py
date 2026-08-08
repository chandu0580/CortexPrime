"""Mapping between the VerificationRecord aggregate and a storable record.

Storage-agnostic: a record here is a plain mapping of primitives, carrying no SQL
and no document-store idiom. Whichever store eventually holds these maps from
this shape rather than from the aggregate.

Every invariant is re-checked on the way in. A record read back from storage is
untrusted input, and "it was valid when written" assumes the store was never
edited by anything but this code -- the assumption the product's own audit chain
exists because nobody should make. In a context whose entire purpose is refusing
to take things on trust, exempting its own storage would be absurd.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contexts.engineering_verification.domain.claim import (
    Claim,
    ClaimType,
    Determinism,
    ReproductionMethod,
    ReproductionStep,
)
from backend.contexts.engineering_verification.domain.evidence import (
    AssertedEvidenceRef,
    EvidenceKind,
    TrustLevel,
    VerifiedEvidence,
)
from backend.contexts.engineering_verification.domain.identifiers import (
    ClaimId,
    EvidenceId,
    VerificationId,
)
from backend.contexts.engineering_verification.domain.record import (
    VerificationRecord,
    VerificationRequest,
    VerificationStatus,
)
from backend.contexts.engineering_verification.domain.results import (
    ClaimResult,
    ClaimVerdict,
)

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def _evidence_record(evidence: VerifiedEvidence) -> dict:
    return {
        "evidence_id": str(evidence.evidence_id),
        "kind": evidence.kind.value,
        "trust": evidence.trust.value,
        "summary": evidence.summary,
        "collected_by": evidence.collected_by,
        "base_commit": evidence.base_commit,
        "detail": evidence.detail,
        "collected_at": evidence.collected_at.isoformat(),
    }


def _evidence_from(data: Optional[Mapping[str, Any]]) -> Optional[VerifiedEvidence]:
    if not data:
        return None
    return VerifiedEvidence(
        evidence_id=EvidenceId(data["evidence_id"]),
        kind=EvidenceKind(data["kind"]),
        trust=TrustLevel(data["trust"]),
        summary=data["summary"],
        collected_by=data["collected_by"],
        base_commit=data.get("base_commit"),
        detail=data.get("detail"),
        collected_at=datetime.fromisoformat(data["collected_at"]),
    )


def _claim_record(claim: Claim) -> dict:
    return {
        "claim_id": str(claim.claim_id),
        "statement": claim.statement,
        "claim_type": claim.claim_type.value,
        "asserted_evidence": sorted(str(e) for e in claim.asserted_evidence),
        "reproduction_hint": claim.reproduction_hint,
    }


def _claim_from(data: Mapping[str, Any]) -> Claim:
    return Claim(
        claim_id=ClaimId(data["claim_id"]),
        statement=data["statement"],
        claim_type=ClaimType(data["claim_type"]),
        asserted_evidence=frozenset(
            AssertedEvidenceRef(e) for e in data["asserted_evidence"]
        ),
        reproduction_hint=data.get("reproduction_hint"),
    )


def _result_record(result: ClaimResult) -> dict:
    return {
        "claim": _claim_record(result.claim),
        "reproduction": {
            "method": result.reproduction.method.value,
            "specification": result.reproduction.specification,
            "determinism": result.reproduction.determinism.value,
            "runs": result.reproduction.runs,
        },
        "observed": result.observed,
        "verdict": result.verdict.value,
        "verdict_evidence": (
            _evidence_record(result.verdict_evidence) if result.verdict_evidence else None
        ),
        "note": result.note,
    }


def _result_from(data: Mapping[str, Any]) -> ClaimResult:
    reproduction = data["reproduction"]
    return ClaimResult(
        claim=_claim_from(data["claim"]),
        reproduction=ReproductionStep(
            method=ReproductionMethod(reproduction["method"]),
            specification=reproduction["specification"],
            determinism=Determinism(reproduction["determinism"]),
            runs=reproduction["runs"],
        ),
        observed=data["observed"],
        verdict=ClaimVerdict(data["verdict"]),
        verdict_evidence=_evidence_from(data.get("verdict_evidence")),
        note=data.get("note"),
    )


def to_record(record: VerificationRecord, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation("tenant_id must be non-blank; it is derived from the context")

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "verification_id": str(record.verification_id),
        "work_id": record.work_id,
        "attempt": record.attempt,
        "base_commit": record.base_commit,
        "requested_by": record.request.requested_by,
        "claims": [_claim_record(c) for c in record.request.claims],
        "status": record.status.value,
        "results": [_result_record(r) for r in record.results],
        "extra_evidence": [_evidence_record(e) for e in record.extra_evidence],
        "verifier": record.verifier,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "closed_at": record.closed_at.isoformat() if record.closed_at else None,
        "closing_note": record.closing_note,
        "superseded_by": str(record.superseded_by) if record.superseded_by else None,
        "created_at": record.created_at.isoformat(),
    }


def from_record(data: Mapping[str, Any]) -> VerificationRecord:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    return VerificationRecord(
        verification_id=VerificationId(data["verification_id"]),
        request=VerificationRequest(
            work_id=data["work_id"],
            attempt=data["attempt"],
            claims=tuple(_claim_from(c) for c in data["claims"]),
            base_commit=data["base_commit"],
            requested_by=data["requested_by"],
        ),
        status=VerificationStatus(data["status"]),
        results=tuple(_result_from(r) for r in data["results"]),
        extra_evidence=tuple(_evidence_from(e) for e in data["extra_evidence"]),
        verifier=data.get("verifier"),
        started_at=(
            datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
        ),
        closed_at=(
            datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None
        ),
        closing_note=data.get("closing_note"),
        superseded_by=(
            VerificationId(data["superseded_by"]) if data.get("superseded_by") else None
        ),
        created_at=datetime.fromisoformat(data["created_at"]),
    )
