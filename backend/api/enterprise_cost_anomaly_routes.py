"""
Enterprise Cost Anomaly Monitoring — REST API.

Covers every provider with real spend today (see
backend.services.enterprise_cost_anomaly_monitor), so this lives at its
own path rather than under the existing /api/costs read-only dashboard
routes.

Endpoints:
  GET  /api/cost-anomaly/status  — latest check per provider
  POST /api/cost-anomaly/check   — trigger an on-demand check right now
                                     (no recurring background loop exists
                                     — this and the startup check are the
                                     only two trigger points, matching
                                     branch-protection/vulnerability)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/cost-anomaly", tags=["Enterprise Cost Anomaly Monitoring"])


@router.get("/status")
async def get_cost_anomaly_status(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_cost_anomaly_monitor import cost_anomaly_history_store
        return {"recent": cost_anomaly_history_store.list_recent(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/check")
async def trigger_cost_anomaly_check():
    try:
        from backend.services.enterprise_cost_anomaly_monitor import check_all_providers
        results = await check_all_providers()
        return {"checked": results}
    except Exception as exc:
        raise HTTPException(502, str(exc))
