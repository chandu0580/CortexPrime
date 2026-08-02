"""
Enterprise Branch Protection Monitoring — REST API.

Covers repos configured via BRANCH_PROTECTION_MONITORED_REPOS (see
backend.services.enterprise_branch_protection_monitor), so this lives at
its own path rather than under /api/github.

Endpoints:
  GET  /api/branch-protection/status  — latest check per monitored repo
  POST /api/branch-protection/check   — trigger an on-demand check of every
                                          configured repo right now (no
                                          recurring background loop exists —
                                          this and the startup check are the
                                          only two trigger points)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/branch-protection", tags=["Enterprise Branch Protection Monitoring"])


@router.get("/status")
async def get_branch_protection_status(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_branch_protection_monitor import branch_protection_history_store
        return {"recent": branch_protection_history_store.list_recent(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/check")
async def trigger_branch_protection_check():
    try:
        from backend.services.enterprise_branch_protection_monitor import check_all_repos
        results = await check_all_repos()
        return {"checked": results}
    except Exception as exc:
        raise HTTPException(502, str(exc))
