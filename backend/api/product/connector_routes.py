"""Connectors in the product API -- read-only, tenant-scoped (Phase 11.1-K).

``GET /api/v1/connectors``              every connector this deployment ships,
                                        with its health for the caller's tenant
``GET /api/v1/connectors/{connector}``  one connector: health checks and every
                                        capability's contract (progressive
                                        disclosure: what it does, what it
                                        needs, how it is governed)

Nothing here configures, connects, refreshes or invokes anything. A connection
is deployment configuration (the Helm values), not a form a caller submits,
and a capability is invoked only through the governed engine. The caller's
tenant comes from ``product_context`` and nowhere else: a connection that
belongs to another tenant is reported to this caller as not connected, with no
detail about the other tenant.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.product.context import ProductContext, product_context

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["CortexPrime Connectors"])


def _runtime() -> Any:
    from backend.api.product.app import current_engine

    engine = current_engine()
    runtime = getattr(engine, "runtime", None) if engine is not None else None
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="the governed engine is not composed in this process")
    return runtime


def _health_for(runtime: Any, connector_id: str, tenant_id: str) -> dict:
    monitor = getattr(runtime, "connector_health", None)
    latest = monitor.latest().get(connector_id) if monitor is not None else None
    if latest is None:
        return {"state": "UNKNOWN", "summary": "health has not been checked in this process"}
    if latest.tenant_id not in (None, tenant_id):
        return {"state": "DISABLED", "summary": "your tenant has no connection for this connector"}
    return latest.to_dict()


def _capability_view(capability: Any, catalogs: dict) -> dict:
    from backend.api.connector_schema import input_schema_for

    profile = capability.profile
    catalog = catalogs.get(capability.provider)
    spec = catalog.get(capability.operation) if catalog is not None else None
    return {
        "id": capability.capability_id,
        "version": capability.version,
        "description": capability.description,
        "category": capability.category,
        "effect": "write" if capability.mutates else "read",
        "risk": profile.risk.level.value,
        "reversible": profile.reversible,
        "compensation": getattr(profile, "compensation", None),
        "autonomy_ceiling": profile.autonomy_ceiling.value,
        "verification": profile.verification_requirement.value,
        "retry": capability.retry.value,
        "timeout_seconds": profile.timeout_seconds,
        "required_permissions": list(capability.required_permissions),
        "input_schema": input_schema_for(spec) if spec is not None else None,
        "composed": spec is not None,
    }


@router.get("/connectors")
def list_connectors(ctx: ProductContext = Depends(product_context)) -> dict:
    runtime = _runtime()
    connectors = []
    for manifest in getattr(runtime, "manifests", ()):
        health = _health_for(runtime, manifest.connector_id, ctx.tenant_id)
        connectors.append({
            "id": manifest.connector_id, "name": manifest.display_name,
            "version": manifest.version, "description": manifest.description,
            "state": health.get("state"), "summary": health.get("summary"),
            "capabilities": len(manifest.capabilities),
        })
    return {"tenant_id": ctx.tenant_id, "connectors": connectors}


@router.get("/connectors/{connector_id}")
def get_connector(connector_id: str, ctx: ProductContext = Depends(product_context)) -> dict:
    runtime = _runtime()
    manifest = next((m for m in getattr(runtime, "manifests", ())
                     if m.connector_id == connector_id), None)
    if manifest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such connector")
    catalogs = dict(getattr(runtime.connectivity, "catalogs", {}) or {})
    report = getattr(runtime, "connector_reports", {}).get(connector_id)
    return {
        "id": manifest.connector_id, "name": manifest.display_name, "version": manifest.version,
        "description": manifest.description,
        "health": _health_for(runtime, connector_id, ctx.tenant_id),
        "commissioning": report.to_dict() if report is not None else None,
        "capabilities": [_capability_view(c, catalogs) for c in manifest.capabilities],
    }
