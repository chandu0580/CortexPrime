"""
Enterprise GitHub Integration — REST API (Production-Grade).

Webhook receiver with signature verification + CRUD for all GitHub
intelligence subsystems via the real GitHub connector.

Endpoints:
  POST   /api/github/webhook              — Receive and verify GitHub webhook
  GET    /api/github/webhooks              — List webhook delivery history
  POST   /api/github/translate             — Translate and process an event
  POST   /api/github/launch-mission        — Launch mission from webhook event
  GET    /api/github/dashboard             — Dashboard stats
  GET    /api/github/activity              — Recent activity
  GET    /api/github/workflow-runs         — List workflow runs
  GET    /api/github/workflow-runs/{id}    — Get workflow run
  GET    /api/github/workflows             — List workflows
  GET    /api/github/pull-requests         — List PRs
  GET    /api/github/pull-requests/{num}   — Get PR with status + checks + reviews
  GET    /api/github/pull-requests/{num}/reviews  — List PR reviews
  GET    /api/github/issues                — List issues
  GET    /api/github/issues/{num}          — Get issue
  GET    /api/github/releases              — List releases
  GET    /api/github/releases/{tag}        — Get release
  GET    /api/github/releases/latest       — Get latest release
  GET    /api/github/deployments           — List deployments
  GET    /api/github/deployments/{id}      — Get deployment
  GET    /api/github/branches              — List branches
  GET    /api/github/branches/{name}/protection  — Get branch protection
  GET    /api/github/commits/{ref}/status  — Get combined commit status
  POST   /api/github/sync                  — Sync repositories
  GET    /api/github/deploy-checks         — Recent + in-flight deploy-regression checks
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.api.legacy_execution_boundary import guard_legacy_execution
from backend.auth.dependencies import require_user
from backend.safety.ingress_boundary import (
    IngressEnvelope,
    audit_ingress,
    bound_body,
    verify_github_delivery,
)
from backend.services.enterprise_github_integration import (
    GITHUB_WEBHOOK_SECRET_ENV,
    BranchIntelligence,
    DeploymentIntelligence,
    IssueIntelligence,
    PRIntelligence,
    ReleaseIntelligence,
    WorkflowRunManager,
    github_integration,
)

log = logging.getLogger(__name__)

# Phase 11.1 (ADR-121): two routers on one prefix, because they authenticate
# differently. ``router`` is the operator surface -- every route needs a
# verified access token. ``webhook_router`` is machine ingress: GitHub cannot
# hold a token, so it proves knowledge of the shared secret with an HMAC, and
# the ingress boundary refuses anything it cannot verify. Both are registered
# by ``router_registry``.
router = APIRouter(
    prefix="/api/github",
    tags=["Enterprise GitHub Integration"],
    dependencies=[Depends(require_user)],
)
webhook_router = APIRouter(prefix="/api/github", tags=["Enterprise GitHub Integration"])


# ---- Request/Response schemas ----

class TranslatePayload(BaseModel):
    event_type: str
    payload: Dict[str, Any]


class LaunchMissionPayload(BaseModel):
    event_type: str
    payload: Dict[str, Any]


class SyncRequest(BaseModel):
    owner: str
    repos: Optional[List[str]] = None


# ---- Webhooks ----

@webhook_router.post("/webhook")
async def receive_webhook(request: Request):
    """Receive one GitHub delivery. Verified before it is parsed.

    Phase 11.1: the HMAC is checked by the ingress boundary first; a missing
    or wrong signature is 401 and an unconfigured secret is 503. Until this
    phase an unverified delivery was accepted, recorded, emitted onto the
    event bus and answered 200 with ``verified: false``.

    The former ``POST /webhook/payload`` route, which accepted the *secret in
    the request body* and so could verify anything a caller chose to sign, is
    removed rather than fenced: a verification the caller controls is not one.
    """
    body = await bound_body(request, source="github.webhook")
    principal = await verify_github_delivery(request, body)
    headers = dict(request.headers)
    secret = os.getenv(GITHUB_WEBHOOK_SECRET_ENV, "")
    try:
        result = await github_integration.receive_webhook(body, headers, secret)
    except Exception as exc:
        await audit_ingress(request, outcome="rejected", source="github.webhook",
                            principal=principal,
                            event_id=headers.get("x-github-delivery"),
                            reason=f"delivery could not be processed: {type(exc).__name__}")
        raise HTTPException(502, "Webhook processing failed")
    envelope = IngressEnvelope.build(
        source="github.webhook",
        event_type=str(result.get("event_type") or headers.get("x-github-event") or "push"),
        payload=result.get("parsed", {}).get("raw", {}) if isinstance(result.get("parsed"), dict) else {},
        principal=principal,
        event_id=str(result.get("delivery_id") or ""),
    )
    await audit_ingress(request, outcome="accepted", source="github.webhook",
                        principal=principal, envelope=envelope,
                        reason=str(result.get("status") or "verified"))
    result["ingress"] = envelope.to_dict()
    return result


@router.get("/webhooks")
async def list_webhooks(limit: int = Query(20, ge=1, le=100)):
    try:
        return {"webhooks": github_integration.get_recent_webhooks(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Translate ----

@router.post("/translate",
             dependencies=[Depends(guard_legacy_execution("POST /api/github/translate"))])
async def translate_event(body: TranslatePayload):
    try:
        result = await github_integration.process_and_wire(body.event_type, body.payload)
        return result
    except Exception as exc:
        raise HTTPException(502, f"Translation failed: {exc}")


# ---- Mission ----

@router.post("/launch-mission",
             dependencies=[Depends(guard_legacy_execution("POST /api/github/launch-mission"))])
async def launch_mission(body: LaunchMissionPayload):
    try:
        result = await github_integration.launch_mission_from_webhook(body.event_type, body.payload)
        if result is None:
            raise HTTPException(502, "Mission launch failed — check Engineering Executive availability")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Mission launch failed: {exc}")


# ---- Dashboard ----

@router.get("/dashboard")
async def dashboard_stats(owner: str = Query(""), repo: str = Query("")):
    try:
        stats = await github_integration.get_dashboard_stats(owner, repo)
        activity = await github_integration.get_recent_activity(owner, repo, 20)
        return {**stats, "recent_activity": activity}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Activity ----

@router.get("/activity")
async def recent_activity(
    owner: str = Query(""),
    repo: str = Query(""),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        activity = await github_integration.get_recent_activity(owner, repo, limit)
        return {"activity": activity}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Workflow Runs ----

@router.get("/workflow-runs")
async def list_workflow_runs(
    owner: str = Query(...),
    repo: str = Query(...),
    status: Optional[str] = Query(None),
    branch: Optional[str] = Query(None),
):
    try:
        if status:
            runs = await WorkflowRunManager.list_by_status(owner, repo, status)
        elif branch:
            runs = await WorkflowRunManager.list_by_branch(owner, repo, branch)
        else:
            runs = await WorkflowRunManager.list_runs(owner, repo)
        return {"workflow_runs": runs}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/workflow-runs/{run_id}")
async def get_workflow_run(owner: str = Query(...), repo: str = Query(...), run_id: int = 0):
    if run_id <= 0:
        raise HTTPException(400, "Invalid run_id")
    try:
        run = await WorkflowRunManager.get_run(owner, repo, run_id)
        return run
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Workflows ----

@router.get("/workflows")
async def list_workflows(owner: str = Query(...), repo: str = Query(...)):
    try:
        workflows = await WorkflowRunManager.list_workflows(owner, repo)
        return {"workflows": workflows}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Pull Requests ----

@router.get("/pull-requests")
async def list_pull_requests(
    owner: str = Query(...),
    repo: str = Query(...),
    state: str = Query("open"),
):
    try:
        prs = await PRIntelligence.list_prs(owner, repo, state)
        return {"pull_requests": prs}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/pull-requests/{pr_number}")
async def get_pull_request(owner: str = Query(...), repo: str = Query(...), pr_number: int = 0):
    if pr_number <= 0:
        raise HTTPException(400, "Invalid PR number")
    try:
        pr = await PRIntelligence.get_pr_with_status(owner, repo, pr_number)
        return pr
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/pull-requests/{pr_number}/reviews")
async def list_pr_reviews(owner: str = Query(...), repo: str = Query(...), pr_number: int = 0):
    if pr_number <= 0:
        raise HTTPException(400, "Invalid PR number")
    try:
        reviews = await PRIntelligence.list_reviews(owner, repo, pr_number)
        return {"reviews": reviews}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Issues ----

@router.get("/issues")
async def list_issues(owner: str = Query(...), repo: str = Query(...), state: str = Query("open")):
    try:
        issues = await IssueIntelligence.list_issues(owner, repo, state)
        return {"issues": issues}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/issues/{issue_number}")
async def get_issue(owner: str = Query(...), repo: str = Query(...), issue_number: int = 0):
    if issue_number <= 0:
        raise HTTPException(400, "Invalid issue number")
    try:
        issue = await IssueIntelligence.get_issue(owner, repo, issue_number)
        return issue
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Releases ----

@router.get("/releases")
async def list_releases(owner: str = Query(...), repo: str = Query(...)):
    try:
        releases = await ReleaseIntelligence.list_releases(owner, repo)
        return {"releases": releases}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/releases/latest")
async def get_latest_release(owner: str = Query(...), repo: str = Query(...)):
    try:
        release = await ReleaseIntelligence.get_latest(owner, repo)
        return release
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/releases/{tag}")
async def get_release(owner: str = Query(...), repo: str = Query(...), tag: str = ""):
    try:
        release = await ReleaseIntelligence.get_release(owner, repo, tag)
        return release
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Deployments ----

@router.get("/deployments")
async def list_deployments(
    owner: str = Query(...),
    repo: str = Query(...),
    environment: Optional[str] = Query(None),
):
    try:
        deployments = await DeploymentIntelligence.list_deployments(owner, repo, environment)
        return {"deployments": deployments}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/deployments/{deployment_id}")
async def get_deployment(owner: str = Query(...), repo: str = Query(...), deployment_id: int = 0):
    if deployment_id <= 0:
        raise HTTPException(400, "Invalid deployment ID")
    try:
        dep = await DeploymentIntelligence.get_deployment(owner, repo, deployment_id)
        return dep
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Branches ----

@router.get("/branches")
async def list_branches(owner: str = Query(...), repo: str = Query(...)):
    try:
        branches = await BranchIntelligence.list_branches(owner, repo)
        return {"branches": branches}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/branches/{branch_name}/protection")
async def get_branch_protection(owner: str = Query(...), repo: str = Query(...), branch_name: str = ""):
    try:
        protection = await BranchIntelligence.get_branch_protection(owner, repo, branch_name)
        if protection is None:
            raise HTTPException(404, "No branch protection found")
        return protection
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Commit Status ----

@router.get("/commits/{ref}/status")
async def get_commit_status(owner: str = Query(...), repo: str = Query(...), ref: str = ""):
    try:
        status = await BranchIntelligence.get_combined_status(owner, repo, ref)
        return status
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Sync ----

@router.post("/sync")
async def sync_repositories(body: SyncRequest):
    try:
        result = await github_integration.sync_engine.sync_all(body.owner, body.repos)
        return {"synced": result}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Deploy Regression Checks ----

@router.get("/deploy-checks")
async def list_deploy_checks(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_github_integration import (
            deploy_check_history_store,
            pending_deploy_check_store,
        )
        return {
            "pending": pending_deploy_check_store.list_pending(),
            "recent": deploy_check_history_store.list_recent(limit),
        }
    except Exception as exc:
        raise HTTPException(502, str(exc))
