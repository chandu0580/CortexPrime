"""Governed signal ingress — Phase 11.2 (ADR-122).

``POST /api/signals/alertmanager``: the Alertmanager webhook receiver.

Where it sits
-------------
Behind Prompt 1's boundary and nowhere else: the perimeter authenticates the
token (Alertmanager's ``webhook_configs[].http_config.authorization`` carries
a CortexPrime access token minted for the tenant's signal principal), the
ingress boundary establishes the principal and tenant from that token, bounds
the body, and audits every decision. This router adds only the mapping from
Alertmanager's payload to World observations, and the World Plane's own
ingestion (identity, dedupe, secret refusal, tenant fail-closed) records them.

Tenant identity is the token's. There is no header, query or payload field
that can name a tenant here; a token without a tenant is refused, because the
World ledger is tenant-scoped and an unscoped observation cannot exist.

This is a governed, tenant-aware surface, so it is exempt from the V1
single-tenant fence (like ``/api/tenants``) and keeps the perimeter's
authentication.

Delivery: Alertmanager retries on non-2xx and re-notifies on
``repeat_interval``; both are at-least-once and both collapse on identity
(``fingerprint`` + ``startsAt`` + the notification's value). A persistence
failure answers 503 so Alertmanager retries -- a signal is never acknowledged
that was not durably recorded.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from backend.auth.dependencies import require_user
from backend.safety.ingress_boundary import (
    IngressEnvelope,
    IngressPrincipal,
    audit_ingress,
    bound_body,
    require_governed_ingest_principal,
)
from backend.signal.alertmanager import AlertmanagerPayload, normalise_alertmanager

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/signals",
    tags=["CortexPrime Signal Ingress"],
    dependencies=[Depends(require_user)],
)

SOURCE = "alertmanager.webhook"
PRODUCED_BY = "signal:alertmanager-ingress/1"


def _observation_repository(request: Request):
    """The durable observation ledger of this process's governed runtime.

    ``backend.main`` composes the governed runtime on boot and keeps it on
    ``app.state.governed``; the product engine is a different process. Both
    reach the same ``cw_observation`` table through the same DurableStore.
    """
    runtime = getattr(request.app.state, "governed", None)
    store = getattr(getattr(runtime, "persistence", None), "store", None)
    if store is None:
        return None
    from backend.world.infrastructure import SqlObservationRepository

    return SqlObservationRepository(store)


def _metrics():
    try:
        from backend.observability.prometheus_metrics import metrics
        return metrics
    except Exception:  # noqa: BLE001 - metrics are never on the decision path
        return None


@router.post("/alertmanager")
async def receive_alertmanager(
    request: Request,
    principal: IngressPrincipal = Depends(require_governed_ingest_principal),
) -> dict[str, Any]:
    started = time.perf_counter()
    m = _metrics()
    body = await bound_body(request, source=SOURCE, principal=principal)
    if m:
        m.signal_events_received.labels("alertmanager", "notification").inc()

    try:
        payload = AlertmanagerPayload.model_validate_json(body)
    except ValidationError as exc:
        malformed = any(e.get("type") == "json_invalid" for e in exc.errors())
        reason = ("payload is not JSON" if malformed else
                  f"payload does not match the Alertmanager v4 webhook schema ({exc.error_count()} error(s))")
        await audit_ingress(request, outcome="rejected", source=SOURCE, principal=principal, reason=reason)
        if m:
            m.signal_events_rejected.labels("alertmanager", "malformed" if malformed else "schema").inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if malformed else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=reason)

    repository = _observation_repository(request)
    if repository is None:
        await audit_ingress(request, outcome="rejected", source=SOURCE, principal=principal,
                            reason="the durable observation ledger is not composed in this process")
        if m:
            m.signal_events_rejected.labels("alertmanager", "ledger_unavailable").inc()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="signal ledger unavailable; retry")

    from backend.contracts.tenant import TenantRef
    from backend.world.application import ObservationIngestion, ObservationRejected
    from backend.world.infrastructure.sql_observation import ObservationPersistenceError

    now = datetime.now(timezone.utc)
    tenant = TenantRef(tenant_id=principal.tenant_id)
    ingestion = ObservationIngestion(repository=repository)
    results: list = []
    recorded = deduped = rejected = 0
    trace_ref = getattr(request.state, "request_id", None)
    for alert in normalise_alertmanager(payload, received_at=now):
        read = alert.to_read(retrieved_at=now, produced_by=PRODUCED_BY, trace_ref=trace_ref)
        try:
            t0 = time.perf_counter()
            observation, newly = ingestion.ingest(tenant=tenant, read=read, recorded_at=now)
            if m:
                m.signal_persist_seconds.labels("alertmanager").observe(time.perf_counter() - t0)
        except ObservationRejected as exc:
            rejected += 1
            results.append({"fingerprint": alert.fingerprint, "outcome": "rejected",
                            "reason": str(exc)[:160]})
            if m:
                m.signal_events_rejected.labels("alertmanager", "observation_refused").inc()
            continue
        except ObservationPersistenceError as exc:
            # Nothing is acknowledged that was not durably recorded: 503 makes
            # Alertmanager retry the whole notification, and the alerts already
            # recorded in it collide on identity when it comes back.
            await audit_ingress(request, outcome="rejected", source=SOURCE, principal=principal,
                                reason=f"durable persistence failed after {recorded} recorded: "
                                       f"{type(exc).__name__}")
            if m:
                m.signal_events_rejected.labels("alertmanager", "persistence").inc()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="signal ledger write failed; retry") from exc
        if newly:
            recorded += 1
            if m:
                m.signal_events_persisted.labels("alertmanager").inc()
                m.signal_event_lag_seconds.labels("alertmanager").observe(
                    max(0.0, (now - observation.instant.observed_at).total_seconds()))
        else:
            deduped += 1
            if m:
                m.signal_events_deduplicated.labels("alertmanager").inc()
        results.append({"fingerprint": alert.fingerprint, "status": alert.value["status"],
                        "observation_id": observation.record_id,
                        "outcome": "recorded" if newly else "deduplicated"})

    envelope = IngressEnvelope.build(
        source=SOURCE, event_type=payload.status,
        payload={"groupKey": payload.groupKey, "receiver": payload.receiver,
                 "alerts": [{"fingerprint": a.fingerprint, "status": a.status,
                             "startsAt": a.startsAt} for a in payload.alerts]},
        principal=principal,
        event_id=f"{payload.groupKey}|{payload.status}|{len(payload.alerts)}" if payload.groupKey else "",
    )
    await audit_ingress(request, outcome="accepted", source=SOURCE, principal=principal,
                        envelope=envelope,
                        reason=f"recorded={recorded} deduplicated={deduped} rejected={rejected}")
    if m:
        m.signal_ingest_seconds.labels("alertmanager").observe(time.perf_counter() - started)
    return {
        "status": "accepted",
        "tenant_id": principal.tenant_id,
        "recorded": recorded,
        "deduplicated": deduped,
        "rejected": rejected,
        "alerts": results,
        "ingress": envelope.to_dict(),
        "delivery": "at-least-once; effectively-once per alert lifecycle state",
    }
