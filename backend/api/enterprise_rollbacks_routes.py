"""
Enterprise Deploy Rollback Automation — REST API.

Provider-neutral on purpose: rollback attempts are recorded by the same
shared history store regardless of whether they came from a GitHub
deployment_status webhook or a GitLab deployment webhook (see
backend.services.enterprise_deploy_rollback_executor), so this lives at
its own path rather than under /api/github or /api/gitlab.

Endpoints:
  GET /api/rollbacks  — recent automated rollback attempts
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/rollbacks", tags=["Enterprise Deploy Rollback Automation"])


@router.get("")
async def list_rollbacks(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_deploy_rollback_store import rollback_history_store
        return {"recent": rollback_history_store.list_recent(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))
