"""Detection and investigation-assessment reads for the product API — Phase 11.3 (ADR-123).

``GET /api/v1/detections``                         the sustained detections the
                                                   platform recorded for this tenant
``GET /api/v1/investigations/{ref}/assessment``    the categorical confidence
                                                   assessment of an investigation:
                                                   outcome, root cause, basis,
                                                   contradictions, unknowns, next
                                                   step, recommendation candidate
``GET /api/v1/investigations/{ref}/cost``          what the investigation spent:
                                                   model calls, tokens, latency,
                                                   estimated USD, governed reads

Tenant comes from ``product_context`` and nowhere else. Every route reads;
nothing here opens, advances, approves or executes anything. Every document
carries ``authority: none`` because that is what it is.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from backend.api.product.context import ProductContext, product_context

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["CortexPrime Investigation Assessment"])


def _engine():
    from backend.api.product.app import current_engine

    engine = current_engine()
    if engine is None or getattr(engine, "reasoning", None) is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="the governed engine is not composed in this process")
    return engine


def _own_investigation(engine, ctx: ProductContext, investigation_ref: str):
    """Reconstruct under the AUTHENTICATED tenant; another tenant's ref is 404
    (the service cannot tell "not yours" from "does not exist", and neither
    should this API)."""
    from backend.intelligence.application.investigation_service import InvestigationNotFound

    try:
        return engine.investigations.reconstruct(tenant=ctx.tenant, investigation_ref=investigation_ref)
    except InvestigationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="no such investigation for this tenant") from exc


@router.get("/detections")
def list_detections(
    ctx: ProductContext = Depends(product_context),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    engine = _engine()
    records = engine.reasoning.list_by_kind(tenant_id=ctx.tenant.tenant_id, kind="detection")
    items = []
    for record in tuple(records)[-limit:][::-1]:
        document = dict(record.record or {})
        document["recorded_at"] = record.recorded_at.isoformat()
        document["reasoning_id"] = record.reasoning_id
        document["authority"] = "none"
        items.append(document)
    return {"tenant_id": ctx.tenant.tenant_id, "count": len(items), "detections": items,
            "note": "sustained conditions the detector recorded; each may have opened one investigation"}


@router.get("/investigations/{investigation_ref}/assessment")
def investigation_assessment(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> dict[str, Any]:
    engine = _engine()
    investigation = _own_investigation(engine, ctx, investigation_ref)
    records = [r for r in engine.reasoning.list_for_subject(
        tenant_id=ctx.tenant.tenant_id, subject_ref=investigation.investigation_ref)
        if getattr(r.kind, "value", r.kind) == "assessment"]
    if not records:
        return {"investigation_ref": investigation.investigation_ref,
                "incident_ref": investigation.incident_ref,
                "status": investigation.status.value,
                "conclusion": investigation.conclusion.value if investigation.conclusion else None,
                "assessment": None, "authority": "none",
                "note": "no assessment has been recorded yet (the investigation may still be running)"}
    latest = records[-1]
    document = dict(latest.record or {})
    document["authority"] = "none"
    return {"investigation_ref": investigation.investigation_ref,
            "incident_ref": investigation.incident_ref,
            "status": investigation.status.value,
            "conclusion": investigation.conclusion.value if investigation.conclusion else None,
            "assessment": document, "recorded_at": latest.recorded_at.isoformat(),
            "authority": "none"}


@router.get("/investigations/{investigation_ref}/cost")
def investigation_cost(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> dict[str, Any]:
    engine = _engine()
    investigation = _own_investigation(engine, ctx, investigation_ref)
    traces = getattr(engine, "traces", None)
    spans = ()
    if traces is not None:
        try:
            spans = traces.spans_for_mission(investigation.investigation_ref)
        except Exception as exc:  # noqa: BLE001
            log.warning("trace spans unreadable for %s: %s", investigation_ref, exc)
    prompt_tokens = completion_tokens = 0
    providers: dict = {}
    latency = 0.0
    calls = []
    for span in spans:
        if not isinstance(span, Mapping):
            continue
        usage = span.get("token_usage") if isinstance(span.get("token_usage"), Mapping) else {}
        provider = span.get("model_provider") or "unknown"
        providers[provider] = providers.get(provider, 0) + 1
        prompt_tokens += int(usage.get("prompt_tokens") or 0)
        completion_tokens += int(usage.get("completion_tokens") or 0)
        if isinstance(span.get("latency_ms"), (int, float)):
            latency += float(span["latency_ms"])
        calls.append({"step_id": span.get("step_id"), "provider": provider,
                      "model": span.get("model_id"), "latency_ms": span.get("latency_ms"),
                      "tokens": usage.get("total_tokens"),
                      "failure": span.get("stop_or_failure_reason")})
    assessment_cost: Optional[Mapping[str, Any]] = None
    for record in engine.reasoning.list_for_subject(tenant_id=ctx.tenant.tenant_id,
                                                    subject_ref=investigation.investigation_ref):
        if getattr(record.kind, "value", record.kind) == "assessment":
            assessment_cost = (record.record or {}).get("cost")
    return {
        "investigation_ref": investigation.investigation_ref,
        "model_calls": len(calls), "providers": providers,
        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "model_latency_ms": round(latency, 1),
        "estimated_usd": (assessment_cost or {}).get("estimated_usd", 0.0),
        "governed_reads": investigation.reads_taken, "steps": investigation.steps_taken,
        "wall_seconds": (assessment_cost or {}).get("wall_seconds"),
        "calls": calls[:50], "authority": "none",
        "note": "tokens and latency come from the durable model trace; USD is the static "
                "cost table's estimate (a local provider prices at zero)",
    }
