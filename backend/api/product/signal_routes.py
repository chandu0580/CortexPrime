"""Signal fabric reads for the product API — Phase 11.2 (ADR-122).

Two read-only, tenant-scoped views over the durable signal ledger:

``GET /api/v1/signals/recent``      the latest canonical signals this tenant's
                                    fabric recorded (World observations viewed
                                    through the signal contract)
``GET /api/v1/signals/candidates``  the incident candidates currently projected
                                    for the detection boundary

Tenant comes from ``product_context`` and nowhere else. Both routes read;
neither can open an investigation, approve, execute or change anything --
the candidates are the handoff Prompt 3 consumes, shown so an operator can see
what detection would see.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.product.context import ProductContext, product_context
from backend.signal.contract import (
    PREDICATE_ALERT,
    PREDICATE_STATE,
    SUBJECT_ALERTMANAGER_ALERT,
    SUBJECT_KUBERNETES_POD,
    canonical_signal,
)
from backend.signal.correlation import project_candidates

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["CortexPrime Signals"])

_PREFIXES = {
    "kubernetes": SUBJECT_KUBERNETES_POD,
    "alertmanager": SUBJECT_ALERTMANAGER_ALERT,
}


def _engine():
    from backend.api.product.app import current_engine

    engine = current_engine()
    if engine is None or getattr(engine, "observations", None) is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="the governed engine is not composed in this process")
    return engine


@router.get("/signals/recent")
def recent_signals(
    ctx: ProductContext = Depends(product_context),
    source: Optional[str] = Query(None, pattern="^(kubernetes|alertmanager)$"),
    minutes: int = Query(60, ge=1, le=24 * 60),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    engine = _engine()
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    observations = engine.observations.list_recent(
        tenant_id=ctx.tenant_id, since=since,
        subject_prefix=_PREFIXES.get(source or "", None), limit=limit)
    signals = [canonical_signal(o).to_dict() for o in observations]
    return {"tenant_id": ctx.tenant_id, "since": since.isoformat(), "count": len(signals),
            "signals": signals, "delivery": "at-least-once", "authority": "none"}


@router.get("/signals/candidates")
def incident_candidates(ctx: ProductContext = Depends(product_context)) -> dict[str, Any]:
    engine = _engine()
    latest = list(engine.observations.latest_by_subject_prefix(
        tenant_id=ctx.tenant_id, subject_prefix=SUBJECT_KUBERNETES_POD,
        predicate=PREDICATE_STATE))
    latest += list(engine.observations.latest_by_subject_prefix(
        tenant_id=ctx.tenant_id, subject_prefix=SUBJECT_ALERTMANAGER_ALERT,
        predicate=PREDICATE_ALERT))
    candidates = project_candidates(latest, tenant_id=ctx.tenant_id)
    return {"tenant_id": ctx.tenant_id, "count": len(candidates),
            "candidates": [c.to_dict() for c in candidates],
            "handoff": "detection boundary (Prompt 3); nothing here opens an investigation",
            "authority": "none"}
