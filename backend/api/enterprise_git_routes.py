"""
Enterprise Git Operations & Pull Request Automation — REST API.

Endpoints:
  GET    /api/git/branches                    — List branches
  POST   /api/git/branches                    — Create branch
  POST   /api/git/commit                      — Create commit
  POST   /api/git/pull-request                — Create PR
  POST   /api/git/pull-request/{id}/merge     — Merge PR
  POST   /api/git/issues/sync                 — Sync issue
  GET    /api/git/history                     — Get operation history
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.api.legacy_execution_boundary import guard_legacy_execution

from backend.services.enterprise_git_operations import git_operations

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/git", tags=["Enterprise Git Operations"])

# ── Schemas ─────────────────────────────────────────────────────────────────

class CreateBranchRequest(BaseModel):
    repo_url: str
    branch_name: str
    source_branch: str = "main"
    workspace_id: str = ""

class CommitRequest(BaseModel):
    repo_url: str
    branch: str
    description: str
    files: List[Dict[str, Any]]
    commit_type: str = "fix"
    scope: Optional[str] = None
    breaking: bool = False
    author: Optional[Dict[str, str]] = None
    patch_candidate_id: str = ""
    mission_id: str = ""

class CreatePRRequest(BaseModel):
    repo_url: str
    title: str
    head: str
    base: str = "main"
    body: str = ""
    reviewers: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    milestone: Optional[int] = None
    mission_id: str = ""
    patch_plan_id: str = ""
    patch_candidate_id: str = ""
    workspace_id: str = ""
    files_changed: Optional[List[str]] = None
    auto_context: bool = True

class MergePRRequest(BaseModel):
    repo_url: str
    pr_number: int
    merge_method: str = "merge"
    commit_title: Optional[str] = None
    commit_message: Optional[str] = None
    require_approval: bool = True

class SyncIssueRequest(BaseModel):
    repo_url: str = ""
    pr_number: int = 0
    issue_number: int = 0
    issue_key: str = ""
    work_item_id: int = 0
    provider: str = "github"
    action: str = "link"
    comment: str = ""
    labels: Optional[List[str]] = None
    status: Optional[str] = None
    state: Optional[str] = None


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/branches")
async def list_branches(repo_url: str = Query(..., description="Repository URL")):
    """List all branches for a repository."""
    try:
        branches = await git_operations.list_branches(repo_url)
        return {"branches": branches, "repo_url": repo_url}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/branches",
    # Audit S-1/S-2 (Phase 11.1-K): a V1 surface that reaches an external
    # write or an ungoverned model/tool loop; quarantined like its siblings.
    dependencies=[Depends(guard_legacy_execution("POST /api/git/branches"))],
)
async def create_branch(req: CreateBranchRequest):
    """Create a new branch from a source branch."""
    try:
        result = await git_operations.create_branch(
            repo_url=req.repo_url,
            branch_name=req.branch_name,
            source_branch=req.source_branch,
            workspace_id=req.workspace_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/commit",
    # Audit S-1/S-2 (Phase 11.1-K): a V1 surface that reaches an external
    # write or an ungoverned model/tool loop; quarantined like its siblings.
    dependencies=[Depends(guard_legacy_execution("POST /api/git/commit"))],
)
async def create_commit(req: CommitRequest):
    """Create a commit on a branch with staged files."""
    try:
        result = await git_operations.commit(
            repo_url=req.repo_url,
            branch=req.branch,
            description=req.description,
            files=req.files,
            commit_type=req.commit_type,
            scope=req.scope,
            breaking=req.breaking,
            author=req.author,
            patch_candidate_id=req.patch_candidate_id,
            mission_id=req.mission_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/pull-request",
    # Audit S-1/S-2 (Phase 11.1-K): a V1 surface that reaches an external
    # write or an ungoverned model/tool loop; quarantined like its siblings.
    dependencies=[Depends(guard_legacy_execution("POST /api/git/pull-request"))],
)
async def create_pull_request(req: CreatePRRequest):
    """Create a pull request with engineering context."""
    try:
        result = await git_operations.create_pull_request(
            repo_url=req.repo_url,
            title=req.title,
            head=req.head,
            base=req.base,
            body=req.body,
            reviewers=req.reviewers,
            labels=req.labels,
            milestone=req.milestone,
            mission_id=req.mission_id,
            patch_plan_id=req.patch_plan_id,
            patch_candidate_id=req.patch_candidate_id,
            workspace_id=req.workspace_id,
            files_changed=req.files_changed,
            auto_context=req.auto_context,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/pull-request/{pr_number}/merge",
    # Audit S-1/S-2 (Phase 11.1-K): a V1 surface that reaches an external
    # write or an ungoverned model/tool loop; quarantined like its siblings.
    dependencies=[Depends(guard_legacy_execution("POST /api/git/pull-request/{pr_number}/merge"))],
)
async def merge_pull_request(pr_number: int, req: MergePRRequest):
    """Merge a pull request."""
    try:
        result = await git_operations.merge_pull_request(
            repo_url=req.repo_url,
            pr_number=pr_number,
            merge_method=req.merge_method,
            commit_title=req.commit_title,
            commit_message=req.commit_message,
            require_approval=req.require_approval,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/issues/sync",
    # Audit S-1/S-2 (Phase 11.1-K): a V1 surface that reaches an external
    # write or an ungoverned model/tool loop; quarantined like its siblings.
    dependencies=[Depends(guard_legacy_execution("POST /api/git/issues/sync"))],
)
async def sync_issue(req: SyncIssueRequest):
    """Sync an issue across GitHub, Jira, or Azure DevOps."""
    try:
        result = await git_operations.sync_issue(
            repo_url=req.repo_url,
            pr_number=req.pr_number,
            issue_number=req.issue_number,
            issue_key=req.issue_key,
            work_item_id=req.work_item_id,
            provider=req.provider,
            action=req.action,
            comment=req.comment,
            labels=req.labels,
            status=req.status,
            state=req.state,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/history")
async def get_history(limit: int = Query(50, description="Max history entries")):
    """Get git operations history."""
    history = await git_operations.get_history(limit=limit)
    return {"history": history, "total": len(history)}


@router.get("/pull-requests")
async def list_pull_requests(
    repo_url: str = Query(..., description="Repository URL"),
    state: str = Query("open", description="PR state filter"),
):
    """List open or closed pull requests."""
    try:
        prs = await git_operations.list_pull_requests(repo_url, state=state)
        return {"pull_requests": prs, "repo_url": repo_url, "state": state}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/pull-requests/summary")
async def pr_summary():
    """Get summary of tracked open PRs."""
    try:
        return await git_operations.get_open_prs_summary()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/context")
async def generate_context(
    mission_id: str = Query(""),
    patch_plan_id: str = Query(""),
    patch_candidate_id: str = Query(""),
    repo_url: str = Query(""),
    workspace_id: str = Query(""),
    files_changed: str = Query(""),
):
    """Generate engineering context for a PR."""
    files_list = [f.strip() for f in files_changed.split(",") if f.strip()] if files_changed else None
    context = await git_operations.generate_context(
        mission_id=mission_id,
        patch_plan_id=patch_plan_id,
        patch_candidate_id=patch_candidate_id,
        repo_url=repo_url,
        workspace_id=workspace_id,
        files_changed=files_list,
    )
    body = await git_operations.format_context(context)
    return {"context": context, "formatted_body": body}
