"""The governed product API. Read-only, tenant-scoped, and holding no authority.

What this is
------------
A presentation adapter over the Phase 7-9 engine. Every endpoint reads an
existing application service through its existing contract and projects the
result into an explicit schema. Nothing here decides, authorizes, approves,
executes or persists.

What it may not become
----------------------
The services these routes call also expose mutation methods --
``InvestigationService`` alone has a dozen. **None is reachable from here.** The
API is not a command bus with read-only manners; it is a module that never calls
a mutating method at all, which is a property a reviewer can check by reading it.

Tenant
------
Every route depends on :func:`product_context`, which resolves the tenant from
the verified JWT. No route reads a tenant from a body, query, header or path.
Where a path names a resource, the service is asked for it **under the
authenticated tenant**, so another tenant's resource is simply not found.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from backend.api.product.context import ProductContext, product_context
from backend.api.product.schemas import (
    ErrorResponse,
    EvidenceRef,
    HypothesisView,
    InvestigationDetail,
    InvestigationList,
    InvestigationSummary,
    VerificationView,
    WorldStateView,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["CortexPrime Product API"])

#: The most rows any list endpoint will return, whatever a caller asks for. A
#: client-supplied limit is validated by FastAPI (1..MAX) and then clamped again
#: here, because a bound that lives only in a decorator is a bound somebody
#: removes while refactoring.
MAX_PAGE = 100
DEFAULT_PAGE = 25

_ERRORS = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "No tenant, or tenant inactive"},
    404: {"model": ErrorResponse, "description": "Not found for this tenant"},
}


# ----------------------------------------------------------------------
# Engine access. Composed once, never per request.
# ----------------------------------------------------------------------

class EngineUnavailable(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the governed engine is not composed in this process",
        )


def get_engine(request_scope: Any = None):
    """The composed governed runtime, from application state.

    Deliberately a lookup rather than a builder: composing the runtime takes
    seconds and opens durable connections, so a per-request build would be both
    slow and a connection leak. The application factory composes it once.
    """
    from backend.api.product.app import current_engine

    engine = current_engine()
    if engine is None:
        raise EngineUnavailable()
    return engine


def _text(value: Any) -> Optional[str]:
    """Render a value as text without leaking structure.

    Domain values can be mappings, enums or datetimes. A response schema that
    accepted them raw would be the ``dict[str, Any]`` pass-through this API
    exists to avoid, so everything becomes a bounded string or nothing.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value") and isinstance(getattr(value, "value"), str):
        return value.value
    return str(value)[:2000]


def _status_of(obj: Any) -> str:
    status_value = getattr(obj, "status", None)
    return _text(status_value) or "unknown"


# ----------------------------------------------------------------------
# Liveness
# ----------------------------------------------------------------------

@router.get("/healthz", summary="Liveness. No tenant data, no authentication.")
def healthz() -> dict:
    # Deliberately returns nothing about any tenant, any engine state, or any
    # configuration -- a liveness probe that leaked either would be a
    # reconnaissance endpoint.
    return {"status": "ok"}


# ----------------------------------------------------------------------
# Investigations
# ----------------------------------------------------------------------

@router.get("/investigations", response_model=InvestigationList, responses=_ERRORS,
            summary="Completed investigations for the authenticated tenant")
def list_investigations(
    ctx: ProductContext = Depends(product_context),
    limit: int = Query(DEFAULT_PAGE, ge=1, le=MAX_PAGE),
) -> InvestigationList:
    """Terminal investigations only.

    The engine exposes ``list_terminal`` and no tenant-scoped listing of
    in-progress investigations. Rather than invent one, this says what it is:
    the response carries a ``note`` so a client is not left inferring that an
    empty list means nothing is happening.
    """
    engine = get_engine()
    bounded = max(1, min(int(limit), MAX_PAGE))
    repository = engine.investigation_repository
    rows = repository.list_terminal(tenant_id=ctx.tenant_id, limit=bounded)

    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        conclusion = row.get("conclusion") or {}
        items.append(InvestigationSummary(
            investigation_ref=_text(row.get("investigation_ref")) or "",
            status=_text(row.get("status")) or "unknown",
            subject_ref=_text(row.get("incident_ref")),
            opened_at=_text(row.get("created_at")),
            concluded_at=_text(row.get("updated_at")),
            diagnosis=_text(conclusion.get("diagnosis")
                            if isinstance(conclusion, dict) else conclusion),
        ))
    return InvestigationList(items=tuple(items), count=len(items), limit=bounded)


def _load(ctx: ProductContext, investigation_ref: str):
    """One investigation, under the AUTHENTICATED tenant.

    The tenant is never the one in the path -- there is no tenant in the path.
    Another tenant's investigation raises ``InvestigationNotFound`` inside the
    service, which becomes a 404 here. See the implementation map for why this
    is 404 rather than 403: the service genuinely cannot distinguish "not yours"
    from "not there", and teaching the API that difference would create the
    disclosure the 404 avoids.
    """
    from backend.intelligence.application.investigation_service import (
        InvestigationNotFound,
    )

    engine = get_engine()
    try:
        return engine.investigations.reconstruct(
            tenant=ctx.tenant, investigation_ref=investigation_ref)
    except InvestigationNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no such investigation for this tenant") from None
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - never surface internal detail
        log.warning("investigation read failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="the investigation could not be read") from None


def _hypotheses(investigation) -> tuple:
    out = []
    for h in getattr(investigation, "differential", ()) or ():
        out.append(HypothesisView(
            hypothesis_id=_text(getattr(h, "hypothesis_ref", "")) or "",
            statement=_text(getattr(h, "proposition", "")) or "",
            status=_status_of(h),
            temporal_fit=_text(getattr(h, "temporal_fit", None)),
            evidence_refs=tuple(
                _text(e) or "" for e in (getattr(h, "evidence_for", ()) or ())),
        ))
    return tuple(out)


def _evidence(investigation) -> tuple:
    return tuple(
        EvidenceRef(
            observation_id=_text(ref) or "",
            subject_ref=_text(getattr(investigation, "incident_ref", "")) or "",
            predicate="",
        )
        for ref in (getattr(investigation, "evidence_refs", ()) or ())
    )


@router.get("/investigations/{investigation_ref}", response_model=InvestigationDetail,
            responses=_ERRORS, summary="One investigation, with its standing intact")
def get_investigation(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> InvestigationDetail:
    investigation = _load(ctx, investigation_ref)
    conclusion = getattr(investigation, "conclusion", None)
    diagnosis = residual = kind = None
    if conclusion is not None:
        diagnosis = _text(getattr(conclusion, "diagnosis", None))
        kind = _text(getattr(conclusion, "kind", None) or conclusion)
        residual = getattr(conclusion, "residual_uncertainty", ()) or ()

    return InvestigationDetail(
        investigation_ref=_text(investigation.investigation_ref) or "",
        status=_status_of(investigation),
        subject_ref=_text(getattr(investigation, "incident_ref", None)),
        opened_at=_text(getattr(investigation, "created_at", None)),
        concluded_at=_text(getattr(investigation, "updated_at", None)),
        diagnosis=diagnosis,
        hypotheses=_hypotheses(investigation),
        evidence=_evidence(investigation),
        residual_uncertainty=tuple(_text(r) or "" for r in (residual or ())),
        conclusion_kind=kind,
    )


@router.get("/investigations/{investigation_ref}/hypotheses",
            response_model=tuple[HypothesisView, ...], responses=_ERRORS,
            summary="The differential, with OPEN and ELIMINATED both preserved")
def get_hypotheses(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> tuple:
    return _hypotheses(_load(ctx, investigation_ref))


@router.get("/investigations/{investigation_ref}/evidence",
            response_model=tuple[EvidenceRef, ...], responses=_ERRORS,
            summary="Evidence references this investigation rests on")
def get_evidence(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> tuple:
    return _evidence(_load(ctx, investigation_ref))


# ----------------------------------------------------------------------
# World
# ----------------------------------------------------------------------

@router.get("/world/state", response_model=WorldStateView, responses=_ERRORS,
            summary="What the World Plane represents, with epistemic status intact")
def get_world_state(
    subject_ref: str = Query(min_length=1, max_length=400),
    predicate: str = Query(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> WorldStateView:
    """``subject_ref`` and ``predicate`` name a resource; neither names a tenant.

    The tenant handed to ``WorldQuery`` is the authenticated one, so a caller
    cannot read another tenant's world by choosing a subject.
    """
    engine = get_engine()
    now = datetime.now(timezone.utc)
    try:
        result = engine.world_query.current(
            tenant=ctx.tenant, subject_ref=subject_ref, predicate=predicate, now=now)
    except Exception:  # noqa: BLE001
        log.warning("world read failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="the world state could not be read") from None

    evidence = tuple(
        EvidenceRef(
            observation_id=_text(getattr(e, "observation_id", "")) or "",
            subject_ref=subject_ref,
            predicate=predicate,
            source_ref=_text(getattr(e, "source_ref", None)),
            observed_at=_text(getattr(e, "observed_at", None)),
            retrieved_at=_text(getattr(e, "retrieved_at", None)),
        )
        for e in (getattr(result, "evidence", ()) or ())
    )
    return WorldStateView(
        subject_ref=subject_ref,
        predicate=predicate,
        # Carried as its own value. UNKNOWN, STALE and CONFLICTED are answers,
        # not absences, and none of them is rendered as false here.
        epistemic_status=_text(getattr(result, "effective_status", None)) or "unknown",
        value=_text(getattr(result, "effective_value", None)),
        observed_at=_text(getattr(result, "queried_valid_at", None)),
        evidence=evidence,
        evidence_count=len(evidence),
    )


# ----------------------------------------------------------------------
# Assurance
# ----------------------------------------------------------------------

@router.get("/verifications/{verification_id}", response_model=VerificationView,
            responses=_ERRORS, summary="An Assurance verdict, as Assurance recorded it")
def get_verification(
    verification_id: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> VerificationView:
    engine = get_engine()
    try:
        record = engine.verifications.get(
            tenant_id=ctx.tenant_id, verification_id=verification_id)
    except Exception:  # noqa: BLE001
        log.warning("verification read failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="the verification could not be read") from None
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no such verification for this tenant")

    procedure = getattr(record, "procedure", None)
    return VerificationView(
        verification_id=_text(getattr(record, "record_id", verification_id)) or "",
        # SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE, unmapped.
        verdict=_text(getattr(record, "verdict", None)) or "unknown",
        subject_ref=_text(getattr(procedure, "subject_ref", None)
                          or getattr(record, "subject_ref", None)) or "",
        predicate=_text(getattr(procedure, "predicate", None)
                        or getattr(record, "predicate", None)) or "",
        rationale=_text(getattr(record, "rationale", None)),
        verified_at=_text(getattr(record, "recorded_at", None)),
        evidence_refs=tuple(
            _text(r) or "" for r in (getattr(record, "evidence_refs", ()) or ())),
    )
