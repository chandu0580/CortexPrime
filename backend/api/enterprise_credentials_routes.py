"""
Enterprise Credential Monitoring — REST API.

Provider-neutral: covers whichever connectors are registered (GitHub,
GitLab CI, Jira today — see backend.services.enterprise_credential_monitor
.MONITORED_CONNECTORS), so this lives at its own path rather than under
/api/github or /api/gitlab.

Endpoints:
  GET  /api/credentials/status  — latest check per monitored connector,
                                   plus recent check history
  POST /api/credentials/check   — trigger an on-demand check of every
                                   monitored connector right now (no
                                   recurring background loop exists —
                                   this and the startup check are the
                                   only two trigger points)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/credentials", tags=["Enterprise Credential Monitoring"])


@router.get("/status")
async def get_credential_status(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_credential_monitor import credential_history_store
        return {
            "latest": credential_history_store.list_latest_per_connector(),
            "recent": credential_history_store.list_recent(limit),
        }
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/check")
async def trigger_credential_check():
    try:
        from backend.services.enterprise_credential_monitor import check_all_credentials
        results = await check_all_credentials()
        return {"checked": results}
    except Exception as exc:
        raise HTTPException(502, str(exc))
