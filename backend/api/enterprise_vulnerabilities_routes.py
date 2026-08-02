"""
Enterprise Vulnerability Monitoring — REST API.

Covers repos configured via VULNERABILITY_MONITORED_REPOS (see
backend.services.enterprise_vulnerability_monitor), so this lives at its
own path rather than under /api/github.

Endpoints:
  GET  /api/vulnerabilities/status  — latest per-alert snapshot, plus
                                        recent check history
  POST /api/vulnerabilities/check   — trigger an on-demand check of every
                                        configured repo right now (no
                                        recurring background loop exists —
                                        this and the startup check are the
                                        only two trigger points)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/vulnerabilities", tags=["Enterprise Vulnerability Monitoring"])


@router.get("/status")
async def get_vulnerability_status(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_vulnerability_monitor import vulnerability_history_store
        return {
            "latest": vulnerability_history_store.list_latest_per_alert(),
            "recent": vulnerability_history_store.list_recent(limit),
        }
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/check")
async def trigger_vulnerability_check():
    try:
        from backend.services.enterprise_vulnerability_monitor import check_vulnerabilities
        results = await check_vulnerabilities()
        return {"checked": results}
    except Exception as exc:
        raise HTTPException(502, str(exc))
