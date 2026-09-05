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

Derived values (Phase 10.2)
---------------------------
Three things in this module are computed rather than read back: ``settle()``,
``analyze_gaps()`` and ``BeliefFormation``. All three are the platform's own
deterministic functions of already-persisted state, called here rather than
reimplemented. That distinction is the point: this module may *call* the
engine's reasoning, and may never *contain* any.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from backend.api.product.context import ProductContext, product_context
from backend.api.product.schemas import (
    AssuranceList,
    AuthorityAlternativeView,
    AuthorityView,
    CorroborationView,
    ErrorResponse,
    EvidenceRef,
    FreshnessView,
    HypothesisView,
    InvestigationDetail,
    InvestigationList,
    InvestigationSummary,
    SourceLineageView,
    TimelineEvent,
    TimelineView,
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
MAX_EVENTS = 500
#: How many observation references one investigation projection will resolve.
#: Each resolution is a row read, so an investigation citing thousands of
#: observations must not turn one page load into thousands of queries.
MAX_EVIDENCE = 50

_ERRORS = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "No tenant, or tenant inactive"},
    404: {"model": ErrorResponse, "description": "Not found for this tenant"},
}

_TERMINAL = ("completed", "failed", "abandoned")

#: Payload keys that may appear in a timeline entry. An allow-list, not a
#: denial-list: the payload is written by the engine and may grow, and a new key
#: must not become a new disclosure just because nobody thought to exclude it.
_SAFE_PAYLOAD_KEYS = (
    "question_ref", "hypothesis_ref", "test_ref", "prediction_ref",
    "verification_ref", "observation_ref", "execution_ref", "cause", "kind",
)


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
# Projections shared by several endpoints
# ----------------------------------------------------------------------

def _lineage_view(engine, *, source_kind: Optional[str],
                  source_ref: Optional[str]) -> Optional[SourceLineageView]:
    """Where this source's data comes from, or nothing if lineage is unknown.

    An unmatched source is UNKNOWN, never assumed distinct. That default is what
    keeps two agreeing instruments from being reported as independent when
    nobody has established that they are.
    """
    policy = getattr(engine, "lineage_policy", None)
    if policy is None or not source_ref:
        return None
    try:
        lineage = policy.lineage_of(
            source_kind=source_kind or "", source_ref=source_ref)
    except Exception:  # noqa: BLE001
        return None
    return SourceLineageView(
        source_kind=_text(lineage.source_kind) or "",
        source_ref=_text(lineage.source_ref) or "",
        origin_id=_text(lineage.origin_id),
        relation=_text(lineage.relation),
        origin_known=bool(lineage.is_known),
    )


def _observation_view(engine, observation, *, observation_id: str) -> EvidenceRef:
    """One observation, with both of its clocks and its source's standing."""
    source = getattr(observation, "source", None)
    instant = getattr(observation, "instant", None)
    provenance = getattr(observation, "provenance", None)
    source_kind = _text(getattr(source, "kind", None))
    source_ref = _text(getattr(source, "source_ref", None))
    return EvidenceRef(
        observation_id=observation_id,
        subject_ref=_text(getattr(observation, "subject_ref", None)) or "",
        predicate=_text(getattr(observation, "predicate", None)) or "",
        value=_text(getattr(observation, "value", None)),
        # RETURNED_DATA / RETURNED_EMPTY / UNAVAILABLE / NOT_CONFIGURED.
        # Empty is not unavailable and neither is false, so the source's own
        # word is carried rather than reduced to "no data".
        status=_text(getattr(observation, "status", None)),
        source_ref=source_ref,
        source_kind=source_kind,
        lineage=_lineage_view(engine, source_kind=source_kind, source_ref=source_ref),
        observed_at=_text(getattr(instant, "observed_at", None)),
        retrieved_at=_text(getattr(instant, "retrieved_at", None)),
        execution_ref=_text(getattr(provenance, "execution_ref", None)),
        trace_ref=_text(getattr(provenance, "trace_ref", None)),
        resolved=True,
    )


def _resolve_evidence(engine, ctx: ProductContext,
                      refs: tuple) -> tuple[EvidenceRef, ...]:
    """Turn observation references into the observations themselves.

    A reference that cannot be resolved is returned marked ``resolved=False``
    rather than dropped. Silently omitting it would shrink the evidence list
    without saying so, which reads as "there was less evidence" instead of
    "something could not be read".
    """
    observations = getattr(engine, "observations", None)
    out: list[EvidenceRef] = []
    for ref in list(refs)[:MAX_EVIDENCE]:
        ref_text = _text(ref) or ""
        record = None
        if observations is not None and ref_text:
            try:
                record = observations.get_observation(
                    tenant_id=ctx.tenant_id, observation_id=ref_text)
            except Exception:  # noqa: BLE001 - one bad row must not fail the page
                log.warning("observation read failed", exc_info=True)
                record = None
        if record is None:
            out.append(EvidenceRef(
                observation_id=ref_text, subject_ref="", predicate="",
                resolved=False))
            continue
        out.append(_observation_view(engine, record, observation_id=ref_text))
    return tuple(out)


def _freshness_view(result) -> FreshnessView:
    fresh = getattr(result, "freshness", None)
    if fresh is None:
        return FreshnessView()
    return FreshnessView(
        state=_text(getattr(fresh, "state", None)) or "unknown",
        age_seconds=getattr(fresh, "age_seconds", None),
        horizon_seconds=getattr(fresh, "horizon_seconds", None),
        reason=_text(getattr(fresh, "reason", None)) or "",
    )


def _authority_view(result) -> AuthorityView:
    authority = getattr(result, "authority", None)
    if authority is None:
        return AuthorityView()
    return AuthorityView(
        status=_text(getattr(authority, "status", None)) or "ungoverned",
        reason=_text(getattr(authority, "reason", None)) or "",
        source_ref=_text(getattr(authority, "source_ref", None)),
        source_kind=_text(getattr(authority, "source_kind", None)),
        tier=_text(getattr(authority, "tier", None)),
        # Every competing value is preserved. A CONFLICTED answer that showed
        # only the winner would be indistinguishable from a settled one.
        alternatives=tuple(
            AuthorityAlternativeView(
                value=_text(getattr(a, "value", None)),
                source_ref=_text(getattr(a, "source_ref", None)),
                tier=_text(getattr(a, "tier", None)),
                observation_ref=_text(getattr(a, "observation_ref", None)),
            )
            for a in (getattr(authority, "alternatives", ()) or ())
        ),
    )


def _corroboration_view(assessment) -> Optional[CorroborationView]:
    if assessment is None:
        return None
    return CorroborationView(
        # independent / correlated / indeterminate / single / contradicted.
        # CORRELATED is carried as itself so a client cannot present two
        # same-origin sources as independent confirmation.
        level=_text(getattr(assessment, "level", None)) or "insufficient",
        independent_sources=tuple(
            _text(s) or "" for s in (getattr(assessment, "independent_sources", ()) or ())),
        independent_origins=tuple(
            _text(o) or "" for o in (getattr(assessment, "independent_origins", ()) or ())),
        lineage=tuple(
            SourceLineageView(
                source_kind=_text(getattr(lg, "source_kind", None)) or "",
                source_ref=_text(getattr(lg, "source_ref", None)) or "",
                origin_id=_text(getattr(lg, "origin_id", None)),
                relation=_text(getattr(lg, "relation", None)),
                origin_known=bool(getattr(lg, "is_known", False)),
            )
            for lg in (getattr(assessment, "lineage", ()) or ())
        ),
        correlated_count=int(getattr(assessment, "correlated_count", 0) or 0),
        supporting_count=len(getattr(assessment, "supporting", ()) or ()),
        contradicting_count=len(getattr(assessment, "contradicting", ()) or ()),
        reason=_text(getattr(assessment, "reason", None)) or "",
    )


def _summary(row: dict) -> InvestigationSummary:
    """One row of the investigation list, from a stored aggregate snapshot."""
    conclusion = row.get("conclusion")
    # ``conclusion`` is an InvestigationConclusion value -- a conclusion KIND,
    # not a diagnosis. Phase 10.1 projected it into a field named ``diagnosis``,
    # which named it as something it is not; it is now carried under its own
    # name and no diagnosis is claimed.
    status_value = _text(row.get("status")) or "unknown"
    return InvestigationSummary(
        investigation_ref=_text(row.get("investigation_ref")) or "",
        status=status_value,
        incident_ref=_text(row.get("incident_ref")),
        subject_ref=_text(row.get("incident_ref")),
        autonomy_level=_text(row.get("autonomy_level")),
        conclusion_kind=(_text(conclusion.get("kind")) if isinstance(conclusion, dict)
                         else _text(conclusion)),
        opened_at=_text(row.get("created_at")),
        last_event_at=_text(row.get("updated_at")),
        is_terminal=status_value in _TERMINAL,
    )


# ----------------------------------------------------------------------
# Investigations
# ----------------------------------------------------------------------

@router.get("/investigations", response_model=InvestigationList, responses=_ERRORS,
            summary="Investigations for the authenticated tenant")
def list_investigations(
    ctx: ProductContext = Depends(product_context),
    limit: int = Query(DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    state: str = Query("all", pattern="^(all|active|completed)$"),
) -> InvestigationList:
    """Active, completed, or both.

    Phase 10.1 could list only terminal investigations, which made the list an
    archive of finished work: the investigation a responder most needs is the
    one still running. ``list_active`` is the same tenant-scoped query with the
    status filter inverted -- no new store and no new state.
    """
    engine = get_engine()
    bounded = max(1, min(int(limit), MAX_PAGE))
    repository = engine.investigation_repository

    rows: list[dict] = []
    if state in ("all", "active"):
        rows.extend(r for r in repository.list_active(
            tenant_id=ctx.tenant_id, limit=bounded) if isinstance(r, dict))
    if state in ("all", "completed"):
        rows.extend(r for r in repository.list_terminal(
            tenant_id=ctx.tenant_id, limit=bounded) if isinstance(r, dict))

    items = tuple(_summary(row) for row in rows[:bounded])
    note = ("Active investigations first, then completed ones."
            if state == "all" else
            "In-progress investigations only." if state == "active" else
            "Completed investigations only.")
    return InvestigationList(items=items, count=len(items), limit=bounded,
                             state=state, note=note)


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


def _gaps_by_ref(investigation) -> dict:
    """The platform's own gap analysis, keyed by hypothesis.

    ``analyze_gaps`` is deterministic and reads only the persisted differential.
    Calling it is reuse of the engine's reasoning; writing an equivalent here
    would be a second opinion about why a hypothesis is unresolved.
    """
    try:
        from backend.intelligence.application.differential import analyze_gaps

        return {g.hypothesis_ref: g for g in analyze_gaps(investigation)}
    except Exception:  # noqa: BLE001
        log.warning("gap analysis unavailable", exc_info=True)
        return {}


def _hypotheses(investigation) -> tuple:
    gaps = _gaps_by_ref(investigation)
    out = []
    for h in getattr(investigation, "differential", ()) or ():
        ref = _text(getattr(h, "hypothesis_ref", "")) or ""
        gap = gaps.get(ref)
        out.append(HypothesisView(
            hypothesis_id=ref,
            statement=_text(getattr(h, "proposition", "")) or "",
            subject_ref=_text(getattr(h, "subject_ref", None)),
            status=_status_of(h),
            temporal_fit=_text(getattr(h, "temporal_fit", None)),
            evidence_for=tuple(
                _text(e) or "" for e in (getattr(h, "evidence_for", ()) or ())),
            evidence_against=tuple(
                _text(e) or "" for e in (getattr(h, "evidence_against", ()) or ())),
            missing_evidence=tuple(
                _text(e) or "" for e in (getattr(h, "missing_evidence", ()) or ())),
            contradiction_refs=tuple(
                _text(e) or "" for e in (getattr(h, "contradiction_refs", ()) or ())),
            lineage_origins=tuple(
                _text(e) or "" for e in (getattr(h, "lineage_origins", ()) or ())),
            authority=_text(getattr(h, "authority", None)),
            created_by=_text(getattr(h, "created_by", None)),
            unresolved_reason=_text(getattr(gap, "unresolved_reason", None)),
            would_support=_text(getattr(gap, "would_support", None)),
            would_contradict=_text(getattr(gap, "would_contradict", None)),
            discriminates_from=tuple(
                _text(d) or "" for d in (getattr(gap, "discriminates_from", ()) or ())),
        ))
    return tuple(out)


def _settled(investigation):
    """The platform's honest terminal read of the differential.

    ``settle()`` is a pure function of the persisted hypotheses. Phase 10.1
    tried to read ``conclusion.diagnosis`` and ``conclusion.residual_uncertainty``
    off an ``InvestigationConclusion``, which is a plain string enum with
    neither attribute -- so residual uncertainty was always empty. This calls
    the function that actually produces it.
    """
    try:
        from backend.intelligence.application.differential import settle

        return settle(investigation)
    except Exception:  # noqa: BLE001
        log.warning("settle unavailable", exc_info=True)
        return None


@router.get("/investigations/{investigation_ref}", response_model=InvestigationDetail,
            responses=_ERRORS, summary="One investigation, with its standing intact")
def get_investigation(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> InvestigationDetail:
    engine = get_engine()
    investigation = _load(ctx, investigation_ref)
    settled = _settled(investigation)
    conclusion = getattr(investigation, "conclusion", None)

    residual: tuple[str, ...] = ()
    if settled is not None and getattr(settled, "residual_uncertainty", None):
        residual = (settled.residual_uncertainty,)

    return InvestigationDetail(
        investigation_ref=_text(investigation.investigation_ref) or "",
        status=_status_of(investigation),
        incident_ref=_text(getattr(investigation, "incident_ref", None)),
        subject_ref=_text(getattr(investigation, "incident_ref", None)),
        # Platform-set. Reported so a human can see the ceiling the platform
        # applied; there is no way to change it through this API.
        autonomy_level=_text(getattr(investigation, "autonomy_level", None)),
        opened_at=_text(getattr(investigation, "created_at", None)),
        last_event_at=_text(getattr(investigation, "updated_at", None)),
        conclusion_kind=_text(conclusion),
        hypotheses=_hypotheses(investigation),
        evidence=_resolve_evidence(
            engine, ctx, getattr(investigation, "evidence_refs", ()) or ()),
        residual_uncertainty=residual,
        supported=tuple(_text(s) or "" for s in (getattr(settled, "supported", ()) or ())),
        eliminated=tuple(_text(s) or "" for s in (getattr(settled, "eliminated", ()) or ())),
        still_open=tuple(_text(s) or "" for s in (getattr(settled, "open_", ()) or ())),
        # False unless Assurance says otherwise. A supported hypothesis is not a
        # verified one, and this field exists so a UI cannot imply that it is.
        assurance_verified=bool(getattr(settled, "verified", False)),
        verification_refs=tuple(
            _text(v) or "" for v in (getattr(investigation, "verification_refs", ()) or ())),
        steps_taken=int(getattr(investigation, "steps_taken", 0) or 0),
        reads_taken=int(getattr(investigation, "reads_taken", 0) or 0),
        read_at=_now().isoformat(),
    )


@router.get("/investigations/{investigation_ref}/hypotheses",
            response_model=tuple[HypothesisView, ...], responses=_ERRORS,
            summary="The differential, with OPEN and REFUTED both preserved")
def get_hypotheses(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> tuple:
    return _hypotheses(_load(ctx, investigation_ref))


@router.get("/investigations/{investigation_ref}/evidence",
            response_model=tuple[EvidenceRef, ...], responses=_ERRORS,
            summary="The evidence this investigation rests on, resolved")
def get_evidence(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> tuple:
    engine = get_engine()
    investigation = _load(ctx, investigation_ref)
    return _resolve_evidence(
        engine, ctx, getattr(investigation, "evidence_refs", ()) or ())


@router.get("/investigations/{investigation_ref}/timeline",
            response_model=TimelineView, responses=_ERRORS,
            summary="What was recorded, in order. Nothing between events is inferred.")
def get_timeline(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
    limit: int = Query(MAX_EVENTS, ge=1, le=MAX_EVENTS),
) -> TimelineView:
    """The append-only event ledger for one investigation.

    ``_load`` runs first so a cross-tenant reference is refused by the service
    before any ledger read happens -- the timeline is not a second door to an
    investigation the detail endpoint would not have shown.
    """
    engine = get_engine()
    _load(ctx, investigation_ref)
    try:
        rows = engine.investigation_repository.list_events(
            tenant_id=ctx.tenant_id, investigation_id=investigation_ref,
            limit=max(1, min(int(limit), MAX_EVENTS)))
    except Exception:  # noqa: BLE001
        log.warning("timeline read failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="the timeline could not be read") from None

    events = []
    for row in rows:
        payload = row.get("payload") or {}
        detail = None
        if isinstance(payload, dict):
            parts = [f"{k}={_text(payload[k])}"
                     for k in _SAFE_PAYLOAD_KEYS if payload.get(k)]
            detail = "; ".join(parts)[:500] or None
        events.append(TimelineEvent(
            seq=int(row.get("seq", 0) or 0),
            event_kind=_text(row.get("event_kind")) or "unknown",
            from_status=_text(row.get("from_status")),
            to_status=_text(row.get("to_status")) or "unknown",
            autonomy_level=_text(row.get("autonomy_level")),
            # A ledger time, under its own name. It is not the moment the world
            # changed, and it is never relabelled as one.
            recorded_at=_text(row.get("recorded_at")),
            detail=detail,
        ))
    return TimelineView(investigation_ref=investigation_ref,
                        events=tuple(events), count=len(events))


@router.get("/investigations/{investigation_ref}/assurance",
            response_model=AssuranceList, responses=_ERRORS,
            summary="Independent verification of this investigation, if any")
def get_investigation_assurance(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> AssuranceList:
    """The verifications this investigation references.

    An empty list means Assurance has not verified anything yet. It does not
    mean the investigation was refuted, and the response says so rather than
    leaving a client to read absence as a negative verdict.
    """
    engine = get_engine()
    investigation = _load(ctx, investigation_ref)
    items = []
    for ref in (getattr(investigation, "verification_refs", ()) or ())[:MAX_PAGE]:
        ref_text = _text(ref) or ""
        if not ref_text:
            continue
        try:
            record = engine.verifications.get(
                tenant_id=ctx.tenant_id, verification_id=ref_text)
        except Exception:  # noqa: BLE001
            log.warning("verification read failed", exc_info=True)
            continue
        if record is not None:
            items.append(_verification_view(record, ref_text))
    return AssuranceList(investigation_ref=investigation_ref,
                         items=tuple(items), count=len(items))


# ----------------------------------------------------------------------
# World
# ----------------------------------------------------------------------

@router.get("/world/state", response_model=WorldStateView, responses=_ERRORS,
            summary="What the World Plane represents, with epistemic status intact")
def get_world_state(
    subject_ref: str = Query(min_length=1, max_length=400),
    predicate: str = Query(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
    corroboration: bool = Query(
        True, description="Include the lineage-aware corroboration assessment."),
) -> WorldStateView:
    """``subject_ref`` and ``predicate`` name a resource; neither names a tenant.

    The tenant handed to ``WorldQuery`` is the authenticated one, so a caller
    cannot read another tenant's world by choosing a subject.
    """
    engine = get_engine()
    now = _now()
    try:
        result = engine.world_query.current(
            tenant=ctx.tenant, subject_ref=subject_ref, predicate=predicate, now=now)
    except Exception:  # noqa: BLE001
        log.warning("world read failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="the world state could not be read") from None

    assessment = None
    if corroboration and getattr(engine, "beliefs", None) is not None:
        try:
            belief = engine.beliefs.form_current(
                tenant=ctx.tenant, subject_ref=subject_ref,
                predicate=predicate, now=now)
            assessment = getattr(belief, "corroboration", None)
        except Exception:  # noqa: BLE001 - corroboration is additive, not required
            log.warning("corroboration unavailable", exc_info=True)
            assessment = None

    evidence = tuple(
        EvidenceRef(
            observation_id=_text(getattr(e, "observation_id", "")) or "",
            subject_ref=subject_ref,
            predicate=predicate,
            value=_text(getattr(e, "value", None)),
            status=_text(getattr(e, "status", None)),
            source_ref=_text(getattr(e, "source_ref", None)),
            source_kind=_text(getattr(e, "source_kind", None)),
            authority_tier=_text(getattr(e, "tier", None)),
            lineage=_lineage_view(
                engine,
                source_kind=_text(getattr(e, "source_kind", None)),
                source_ref=_text(getattr(e, "source_ref", None))),
            observed_at=_text(getattr(e, "observed_at", None)),
            retrieved_at=_text(getattr(e, "retrieved_at", None)),
            execution_ref=_text(getattr(e, "execution_ref", None)),
            trace_ref=_text(getattr(e, "trace_ref", None)),
        )
        for e in (getattr(result, "evidence", ()) or ())
    )
    observed_at = next((e.observed_at for e in evidence if e.observed_at), None)
    return WorldStateView(
        subject_ref=subject_ref,
        predicate=predicate,
        # Carried as its own value. UNKNOWN, STALE and CONFLICTED are answers,
        # not absences, and none of them is rendered as false here.
        epistemic_status=_text(getattr(result, "effective_status", None)) or "unknown",
        value=_text(getattr(result, "effective_value", None)),
        queried_valid_at=_text(getattr(result, "queried_valid_at", None)),
        as_known_at=_text(getattr(result, "as_known_at", None)),
        observed_at=observed_at,
        read_at=now.isoformat(),
        freshness=_freshness_view(result),
        authority=_authority_view(result),
        corroboration=_corroboration_view(assessment),
        evidence=evidence,
        evidence_count=len(evidence),
    )


# ----------------------------------------------------------------------
# Assurance
# ----------------------------------------------------------------------

def _verification_view(record, fallback_id: str) -> VerificationView:
    """One ``WorldVerification``, projected from the fields it actually has.

    Phase 10.1 reached for a ``record.procedure`` object and a ``predicate``
    attribute; ``WorldVerification`` has neither -- it carries ``procedure_ref``
    and a ``VerifierIdentity``. So both fields were silently empty. The verifier
    identity in particular matters: independence is proven by the verifier's
    reasoning path differing from the producer's, and a UI that cannot show who
    verified cannot show that.
    """
    verifier = getattr(record, "verifier", None)
    return VerificationView(
        verification_id=_text(getattr(record, "record_id", fallback_id)) or fallback_id,
        # SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE, unmapped.
        verdict=_text(getattr(record, "verdict", None)) or "unknown",
        subject_ref=_text(getattr(record, "subject_ref", None)) or "",
        procedure_ref=_text(getattr(record, "procedure_ref", None)),
        verifier_ref=_text(getattr(verifier, "verifier_id", None)),
        verifier_reasoning_path=_text(getattr(verifier, "reasoning_path_id", None)),
        rationale=_text(getattr(record, "rationale", None)),
        verified_at=_text(getattr(record, "recorded_at", None)),
        evidence_refs=tuple(
            _text(r) or "" for r in (getattr(record, "evidence_refs", ()) or ())),
    )


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
    return _verification_view(record, verification_id)
