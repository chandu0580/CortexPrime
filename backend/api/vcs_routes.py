from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from backend.auth.dependencies import require_user

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/vcs",
    tags=["VCS"],
    dependencies=[Depends(require_user)],
)


@router.get("/repositories")
async def list_vcs_repositories() -> Dict[str, Any]:
    try:
        from backend.services.enterprise_code_intelligence import code_intelligence
        repos = await code_intelligence.list_repositories()
        return {"repositories": repos, "total": len(repos)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/issues")
async def list_vcs_issues(
    owner: str = Query("", description="Repository owner"),
    repo: str = Query("", description="Repository name"),
    state: str = Query("open", description="Issue state filter"),
) -> Dict[str, Any]:
    try:
        from backend.services.enterprise_github_integration import IssueIntelligence
        issues = await IssueIntelligence.list_issues(owner, repo, state)
        return {"issues": issues, "total": len(issues)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
