"""
Enterprise Alert Incident Correlation — REST API.

Provider-neutral on purpose: incidents are correlated from whichever
detector's signal fires first (deploy-regression, flaky-test, rollback —
see backend.services.enterprise_alert_correlator), so this lives at its
own path rather than under /api/github or /api/gitlab.

Endpoints:
  GET /api/incidents  — recent correlated incidents (each with its
                         suppressed-duplicate count and linked ticket)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/incidents", tags=["Enterprise Alert Incident Correlation"])


@router.get("")
async def list_incidents(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_alert_correlator import incident_history_store
        return {"recent": incident_history_store.list_recent(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))
