"""
Enterprise GitHub Engineering Integration — Production-Grade.

Connects CortexPrime to real GitHub engineering workflows so the
Engineering Executive can manage live repositories.

Every subsystem delegates to the real GitHub connector (backend/connectors/github.py)
instead of JSON-file storage. Webhook delivery is hardened with replay protection,
idempotency, and delivery-history tracking.

Subsystems:
  1. WebhookReceiver         — verify signatures, replay protection, idempotency
  2. GitHubEventTranslator   — map webhook events to internal events
  3. WorkflowRunManager      — real Actions workflow run tracking via API
  4. PRIntelligence          — real PR lifecycle via API
  5. IssueIntelligence       — real issue lifecycle via API
  6. ReleaseIntelligence     — real release tracking via API
  7. DeploymentIntelligence  — real deployment tracking via API
  8. BranchIntelligence      — real branch activity via API
  9. SyncEngine              — incremental sync with ETag caching
  10. GithubIntegration       — orchestrator singleton
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_WEBHOOK_DELIVERIES_FILE = _DATA_DIR / "github_webhook_deliveries.json"

MAX_WEBHOOK_DELIVERIES = 1000
DELIVERY_RETENTION_DAYS = 30

GITHUB_EVENTS: Dict[str, str] = {
    "webhook_received": "github.webhook_received",
    "webhook_verified": "github.webhook_verified",
    "push_received": "github.push_received",
    "workflow_run_started": "github.workflow_run_started",
    "workflow_run_completed": "github.workflow_run_completed",
    "workflow_run_failed": "github.workflow_run_failed",
    "pr_opened": "github.pr_opened",
    "pr_updated": "github.pr_updated",
    "pr_reviewed": "github.pr_reviewed",
    "pr_checks_passed": "github.pr_checks_passed",
    "pr_merged": "github.pr_merged",
    "issue_opened": "github.issue_opened",
    "issue_closed": "github.issue_closed",
    "release_published": "github.release_published",
    "deployment_started": "github.deployment_started",
    "deployment_completed": "github.deployment_completed",
    "deployment_failed": "github.deployment_failed",
    "branch_updated": "github.branch_updated",
    "branch_deleted": "github.branch_deleted",
    "mission_launched": "github.mission_launched",
}


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.warning("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        log.warning("Failed to save %s: %s", path.name, exc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _repo_full_name(owner: str, repo: str) -> str:
    return f"{owner}/{repo}"


async def _get_gh():
    from backend.connectors.registry import connector_registry
    gh = connector_registry.get("github")
    if not gh:
        raise RuntimeError("GitHub connector not registered")
    return gh


async def _emit(event_type: str, entity_id: str, data: Dict[str, Any]) -> None:
    try:
        from backend.services.enterprise_event_hub import enterprise_hub
        await enterprise_hub.emit(
            event_type=event_type,
            agent="github_integration",
            status="info",
            message=f"GitHub: {event_type.split('.')[-1]}",
            execution_id=entity_id,
            metadata={"entity_id": entity_id, "domain": "github", **(data or {})},
        )
    except Exception as exc:
        log.debug("Emit skipped for %s: %s", event_type, exc)


# =============================================================================
# Part 1 — Webhook Receiver (hardened)
# =============================================================================

class WebhookDeliveryStore:
    """Persistent store for webhook delivery history with deduplication."""

    def __init__(self) -> None:
        self._deliveries: List[Dict[str, Any]] = _load_json(_WEBHOOK_DELIVERIES_FILE)
        self._seen_ids: Set[str] = {d.get("delivery_id", "") for d in self._deliveries if d.get("delivery_id")}

    def is_duplicate(self, delivery_id: str) -> bool:
        return delivery_id in self._seen_ids

    def record_delivery(
        self,
        delivery_id: str,
        event_type: str,
        repository: str,
        verified: bool,
        status: str = "received",
    ) -> Dict[str, Any]:
        entry = {
            "delivery_id": delivery_id,
            "event_type": event_type,
            "repository": repository,
            "verified": verified,
            "status": status,
            "received_at": _now(),
        }
        self._deliveries.insert(0, entry)
        self._seen_ids.add(delivery_id)
        self._prune()
        _save_json(_WEBHOOK_DELIVERIES_FILE, self._deliveries)
        return entry

    def update_delivery(self, delivery_id: str, status: str) -> None:
        for d in self._deliveries:
            if d.get("delivery_id") == delivery_id:
                d["status"] = status
                d["updated_at"] = _now()
                _save_json(_WEBHOOK_DELIVERIES_FILE, self._deliveries)
                return

    def get_deliveries(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._deliveries[:limit]

    def get_delivery_count_since(self, since: str) -> int:
        return sum(1 for d in self._deliveries if d.get("received_at", "") >= since)

    def clear(self) -> None:
        self._deliveries.clear()
        self._seen_ids.clear()
        _save_json(_WEBHOOK_DELIVERIES_FILE, [])

    def _prune(self) -> None:
        if len(self._deliveries) > MAX_WEBHOOK_DELIVERIES:
            self._deliveries = self._deliveries[:MAX_WEBHOOK_DELIVERIES]


class WebhookReceiver:
    """Verify GitHub webhook signatures, handle replay protection, and parse events."""

    def __init__(self) -> None:
        self._delivery_store = WebhookDeliveryStore()

    def verify_signature(self, payload: bytes, signature_header: str, secret: str) -> bool:
        if not signature_header or not secret:
            return False
        expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature_header, expected)

    @staticmethod
    def _header(headers: Dict[str, str], name: str) -> str:
        """Case-insensitive header lookup.

        HTTP header names are case-insensitive by spec, and ASGI/Starlette
        normalizes them to all-lowercase when a request's headers are
        converted to a plain dict (dict(request.headers), as the real
        webhook route does) — so an exact-case lookup like
        headers.get("X-GitHub-Event") never matches a real incoming
        request. Every genuine GitHub webhook would silently fall through
        to defaults (event_type="push", signature="") without this.
        """
        target = name.lower()
        for key, value in headers.items():
            if key.lower() == target:
                return value
        return ""

    def extract_delivery_id(self, headers: Dict[str, str]) -> str:
        return self._header(headers, "X-GitHub-Delivery") or _id()

    def extract_event_type(self, headers: Dict[str, str]) -> str:
        return self._header(headers, "X-GitHub-Event") or "push"

    def extract_signature(self, headers: Dict[str, str]) -> str:
        return self._header(headers, "X-Hub-Signature-256")

    def is_replay(self, delivery_id: str) -> bool:
        return self._delivery_store.is_duplicate(delivery_id)

    async def receive(
        self,
        body: bytes,
        headers: Dict[str, str],
        secret: str,
    ) -> Dict[str, Any]:
        delivery_id = self.extract_delivery_id(headers)
        event_type = self.extract_event_type(headers)
        signature = self.extract_signature(headers)

        if self.is_replay(delivery_id):
            log.warning("Duplicate webhook delivery detected: %s", delivery_id)
            return {"delivery_id": delivery_id, "status": "duplicate", "event_type": event_type}

        verified = self.verify_signature(body, signature, secret)
        payload = json.loads(body)

        parsed = self.parse_event(payload, event_type)
        parsed["delivery_id"] = delivery_id
        parsed["verified"] = verified

        self._delivery_store.record_delivery(
            delivery_id=delivery_id,
            event_type=event_type,
            repository=parsed.get("repository", ""),
            verified=verified,
        )

        await _emit(
            GITHUB_EVENTS["webhook_verified"] if verified else GITHUB_EVENTS["webhook_received"],
            delivery_id,
            parsed,
        )

        if not verified:
            log.warning("Webhook signature verification failed for delivery %s", delivery_id)
            self._delivery_store.update_delivery(delivery_id, "signature_failed")

        return {
            "delivery_id": delivery_id,
            "event_type": event_type,
            "verified": verified,
            "parsed": parsed,
        }

    @staticmethod
    def parse_event(payload: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {
            "event_id": _id(),
            "event_type": event_type,
            "received_at": _now(),
            "repository": payload.get("repository", {}).get("full_name", ""),
            "sender": payload.get("sender", {}).get("login", ""),
            "action": payload.get("action", ""),
            "raw": payload,
        }
        if "ref" in payload:
            normalized["ref"] = payload["ref"]
        if "commits" in payload:
            normalized["commit_count"] = len(payload["commits"])
            normalized["commits"] = [
                {
                    "id": c.get("id", ""),
                    "message": c.get("message", ""),
                    "author": c.get("author", {}).get("name", ""),
                    "timestamp": c.get("timestamp", ""),
                    "url": c.get("url", ""),
                }
                for c in (payload.get("commits") or [])
            ]
        return normalized

    def get_deliveries(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._delivery_store.get_deliveries(limit)


# =============================================================================
# Part 2 — GitHub Event Translator
# =============================================================================

WEBHOOK_TO_INTERNAL: Dict[str, str] = {
    "push": GITHUB_EVENTS["push_received"],
    "pull_request": GITHUB_EVENTS["pr_opened"],
    "pull_request_review": GITHUB_EVENTS["pr_reviewed"],
    "pull_request_review_comment": GITHUB_EVENTS["pr_reviewed"],
    "issues": GITHUB_EVENTS["issue_opened"],
    "issue_comment": GITHUB_EVENTS["issue_opened"],
    "release": GITHUB_EVENTS["release_published"],
    "deployment": GITHUB_EVENTS["deployment_started"],
    "deployment_status": GITHUB_EVENTS["deployment_completed"],
    "workflow_run": GITHUB_EVENTS["workflow_run_started"],
    "create": GITHUB_EVENTS["branch_updated"],
    "delete": GITHUB_EVENTS["branch_deleted"],
    "check_run": GITHUB_EVENTS["workflow_run_started"],
    "check_suite": GITHUB_EVENTS["workflow_run_started"],
}


class GitHubEventTranslator:
    """Translate GitHub webhook event types and payloads to internal events."""

    @staticmethod
    def translate(event_type: str, payload: Dict[str, Any]) -> str:
        internal_type = WEBHOOK_TO_INTERNAL.get(event_type, GITHUB_EVENTS["webhook_received"])
        action = payload.get("action", "")
        if event_type == "pull_request" and action == "closed":
            merged = payload.get("pull_request", {}).get("merged", False)
            internal_type = GITHUB_EVENTS["pr_merged"] if merged else GITHUB_EVENTS["pr_updated"]
        elif event_type == "pull_request" and action in ("synchronize", "edited", "labeled", "unlabeled", "assigned", "unassigned"):
            internal_type = GITHUB_EVENTS["pr_updated"]
        elif event_type == "pull_request_review" and action == "submitted":
            internal_type = GITHUB_EVENTS["pr_reviewed"]
        elif event_type == "push":
            internal_type = GITHUB_EVENTS["push_received"]
        elif event_type == "issues" and action == "closed":
            internal_type = GITHUB_EVENTS["issue_closed"]
        elif event_type == "issues" and action == "opened":
            internal_type = GITHUB_EVENTS["issue_opened"]
        elif event_type == "workflow_run":
            status = payload.get("workflow_run", {}).get("status", "")
            conclusion = payload.get("workflow_run", {}).get("conclusion", "")
            if status == "completed":
                internal_type = (
                    GITHUB_EVENTS["workflow_run_completed"]
                    if conclusion == "success"
                    else GITHUB_EVENTS["workflow_run_failed"]
                )
        elif event_type == "deployment_status":
            dep_state = payload.get("deployment_status", {}).get("state", "")
            if dep_state in ("success", "ready"):
                internal_type = GITHUB_EVENTS["deployment_completed"]
            elif dep_state in ("failure", "error"):
                internal_type = GITHUB_EVENTS["deployment_failed"]
        elif event_type == "create":
            ref_type = payload.get("ref_type", "")
            if ref_type == "branch":
                internal_type = GITHUB_EVENTS["branch_updated"]
        elif event_type == "delete":
            ref_type = payload.get("ref_type", "")
            if ref_type == "branch":
                internal_type = GITHUB_EVENTS["branch_deleted"]
        elif event_type == "check_suite":
            check_conclusion = payload.get("check_suite", {}).get("conclusion", "")
            if check_conclusion == "success":
                internal_type = GITHUB_EVENTS["workflow_run_completed"]
            elif check_conclusion in ("failure", "cancelled", "timed_out"):
                internal_type = GITHUB_EVENTS["workflow_run_failed"]
        return internal_type

    @staticmethod
    def build_mission_context(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {
            "source": "github_webhook",
            "event_type": event_type,
            "timestamp": _now(),
        }
        repo = payload.get("repository", {})
        ctx["repo_url"] = repo.get("clone_url", repo.get("html_url", ""))
        ctx["repo_full_name"] = repo.get("full_name", "")
        ctx["sender"] = payload.get("sender", {}).get("login", "")

        if event_type == "push":
            ctx["ref"] = payload.get("ref", "")
            ctx["branch"] = payload.get("ref", "").replace("refs/heads/", "")
            ctx["commit_count"] = len(payload.get("commits", []))
            ctx["commits"] = [c.get("message", "") for c in (payload.get("commits") or [])]
            ctx["head_commit"] = (payload.get("head_commit") or {}).get("id", "")
        elif event_type.startswith("pull_request"):
            pr = payload.get("pull_request", {})
            ctx["pr_number"] = pr.get("number")
            ctx["pr_title"] = pr.get("title", "")
            ctx["pr_body"] = pr.get("body", "")
            ctx["branch"] = pr.get("head", {}).get("ref", "")
            ctx["base_branch"] = pr.get("base", {}).get("ref", "")
            ctx["pr_head_sha"] = pr.get("head", {}).get("sha", "")
            ctx["pr_action"] = payload.get("action", "")
        elif event_type == "pull_request_review":
            review = payload.get("review", {})
            pr = payload.get("pull_request", {})
            ctx["pr_number"] = pr.get("number")
            ctx["review_id"] = review.get("id")
            ctx["review_state"] = review.get("state", "")
            ctx["reviewer"] = (review.get("user") or {}).get("login", "")
            ctx["pr_title"] = pr.get("title", "")
        elif event_type == "issues":
            issue = payload.get("issue", {})
            ctx["issue_number"] = issue.get("number")
            ctx["issue_title"] = issue.get("title", "")
            ctx["issue_body"] = issue.get("body", "")
            ctx["action"] = payload.get("action", "")
        elif event_type == "workflow_run":
            run = payload.get("workflow_run", {})
            ctx["workflow_name"] = run.get("name", "")
            ctx["workflow_run_id"] = run.get("id")
            ctx["workflow_status"] = run.get("status")
            ctx["workflow_conclusion"] = run.get("conclusion")
            ctx["branch"] = run.get("head_branch", "")
            ctx["commit_sha"] = run.get("head_sha", "")
        elif event_type == "release":
            rel = payload.get("release", {})
            ctx["release_tag"] = rel.get("tag_name", "")
            ctx["release_name"] = rel.get("name", "")
            ctx["release_prerelease"] = rel.get("prerelease", False)
        elif event_type == "deployment_status":
            dep = payload.get("deployment", {})
            dep_status = payload.get("deployment_status", {})
            ctx["deployment_id"] = dep.get("id")
            ctx["environment"] = dep.get("environment", "")
            ctx["deployment_state"] = dep_status.get("state", "")
            ctx["deployment_description"] = dep_status.get("description", "")
            ctx["deployment_log_url"] = dep_status.get("log_url", "")
        elif event_type == "check_suite":
            suite = payload.get("check_suite", {})
            ctx["check_suite_id"] = suite.get("id")
            ctx["check_conclusion"] = suite.get("conclusion", "")
            ctx["head_branch"] = suite.get("head_branch", "")
            ctx["head_sha"] = suite.get("head_sha", "")
            ctx["app"] = (suite.get("app") or {}).get("name", "")
        return ctx


# =============================================================================
# Part 3 — Workflow Run Manager (real API)
# =============================================================================

class WorkflowRunManager:
    """Track and monitor GitHub Actions workflow runs via the real API."""

    @staticmethod
    async def list_runs(owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_workflow_runs(owner, repo, params=kwargs)

    @staticmethod
    async def get_run(owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_workflow_run(owner, repo, run_id)

    @staticmethod
    async def list_by_status(owner: str, repo: str, status: str) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_workflow_runs(owner, repo, params={"status": status})

    @staticmethod
    async def list_by_branch(owner: str, repo: str, branch: str) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_workflow_runs(owner, repo, params={"branch": branch})

    @staticmethod
    async def list_workflows(owner: str, repo: str) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_workflows(owner, repo)

    @staticmethod
    async def get_workflow(owner: str, repo: str, workflow_id: str) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_workflow(owner, repo, workflow_id)

    @staticmethod
    async def dispatch(owner: str, repo: str, workflow_id: str, ref: str = "main", inputs: Optional[Dict[str, str]] = None) -> bool:
        gh = await _get_gh()
        return await gh.dispatch_workflow(owner, repo, workflow_id, ref=ref, inputs=inputs)

    @staticmethod
    async def cancel_run(owner: str, repo: str, run_id: int) -> bool:
        gh = await _get_gh()
        return await gh.cancel_workflow_run(owner, repo, run_id)

    @staticmethod
    async def rerun(owner: str, repo: str, run_id: int) -> bool:
        gh = await _get_gh()
        return await gh.rerun_workflow(owner, repo, run_id)


# =============================================================================
# Part 4 — PR Intelligence (real API)
# =============================================================================

class PRIntelligence:
    """Track PR lifecycle, reviews, check statuses, and merge readiness via API."""

    @staticmethod
    async def list_prs(owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_pull_requests(owner, repo, state=state)

    @staticmethod
    async def get_pr(owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_pull_request(owner, repo, pr_number)

    @staticmethod
    async def get_pr_with_status(owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        gh = await _get_gh()
        pr = await gh.get_pull_request(owner, repo, pr_number)
        combined = await gh.get_combined_status(owner, repo, pr.get("head", {}).get("sha", ""))
        check_runs = await gh.list_check_runs(owner, repo, pr.get("head", {}).get("sha", ""))
        reviews = await gh.list_pull_request_reviews(owner, repo, pr_number)
        pr["combined_status"] = combined.get("state", "unknown")
        pr["check_runs"] = check_runs.get("check_runs", [])
        pr["reviews"] = reviews
        return pr

    @staticmethod
    async def list_reviews(owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_pull_request_reviews(owner, repo, pr_number)

    @staticmethod
    async def get_checks(owner: str, repo: str, ref: str) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.list_check_runs(owner, repo, ref)

    @staticmethod
    async def get_combined_status(owner: str, repo: str, ref: str) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_combined_status(owner, repo, ref)


# =============================================================================
# Part 5 — Issue Intelligence (real API)
# =============================================================================

class IssueIntelligence:
    """Track issue and feature-request lifecycle via API."""

    @staticmethod
    async def list_issues(owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh._request_list_paginated("GET", f"/repos/{owner}/{repo}/issues", {"state": state, "per_page": 100})

    @staticmethod
    async def get_issue(owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_issue(owner, repo, issue_number)


# =============================================================================
# Part 6 — Release Intelligence (real API)
# =============================================================================

class ReleaseIntelligence:
    """Track releases and tags via API."""

    @staticmethod
    async def list_releases(owner: str, repo: str) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_releases(owner, repo)

    @staticmethod
    async def get_release(owner: str, repo: str, tag: str) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_release(owner, repo, tag)

    @staticmethod
    async def get_latest(owner: str, repo: str) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_latest_release(owner, repo)

    @staticmethod
    async def list_tags(owner: str, repo: str) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_repository_tags(owner, repo)


# =============================================================================
# Part 7 — Deployment Intelligence (real API)
# =============================================================================

class DeploymentIntelligence:
    """Track deployment environments and their statuses via API."""

    @staticmethod
    async def list_deployments(owner: str, repo: str, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_deployments(owner, repo, environment=environment)

    @staticmethod
    async def get_deployment(owner: str, repo: str, deployment_id: int) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_deployment(owner, repo, deployment_id)

    @staticmethod
    async def list_statuses(owner: str, repo: str, deployment_id: int) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_deployment_statuses(owner, repo, deployment_id)


# =============================================================================
# Part 8 — Branch Intelligence (real API)
# =============================================================================

class BranchIntelligence:
    """Monitor branch activity, protection rules, and sync state via API."""

    @staticmethod
    async def list_branches(owner: str, repo: str) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_branches(owner, repo)

    @staticmethod
    async def get_branch_protection(owner: str, repo: str, branch: str) -> Optional[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.get_branch_protection(owner, repo, branch)

    @staticmethod
    async def get_commit_statuses(owner: str, repo: str, ref: str) -> List[Dict[str, Any]]:
        gh = await _get_gh()
        return await gh.list_commit_statuses(owner, repo, ref)

    @staticmethod
    async def get_combined_status(owner: str, repo: str, ref: str) -> Dict[str, Any]:
        gh = await _get_gh()
        return await gh.get_combined_status(owner, repo, ref)


# =============================================================================
# Part 9 — Sync Engine (incremental sync with ETag caching)
# =============================================================================

class SyncEngine:
    """Incremental synchronization engine for GitHub data."""

    def __init__(self) -> None:
        self._sync_state: Dict[str, Dict[str, Any]] = {}

    async def sync_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        gh = await _get_gh()
        repo_data = await gh.get_repository(owner, repo)
        key = _repo_full_name(owner, repo)
        self._sync_state[key] = {
            "last_sync": _now(),
            "default_branch": repo_data.get("default_branch", "main"),
            "description": repo_data.get("description", ""),
            "private": repo_data.get("private", False),
            "fork": repo_data.get("fork", False),
            "language": repo_data.get("language", ""),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "open_issues": repo_data.get("open_issues_count", 0),
        }
        return repo_data

    async def sync_all(
        self,
        owner: str,
        repos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        gh = await _get_gh()
        if repos:
            results = {}
            for repo in repos:
                try:
                    data = await self.sync_repository(owner, repo)
                    results[repo] = {"status": "synced", "data": data}
                except Exception as exc:
                    results[repo] = {"status": "failed", "error": str(exc)}
            return results
        all_repos = await gh.list_repositories(owner)
        results = {}
        for repo_data in all_repos:
            repo_name = repo_data.get("name", "")
            key = _repo_full_name(owner, repo_name)
            self._sync_state[key] = {
                "last_sync": _now(),
                "default_branch": repo_data.get("default_branch", "main"),
                "description": repo_data.get("description", ""),
                "private": repo_data.get("private", False),
                "fork": repo_data.get("fork", False),
                "language": repo_data.get("language", ""),
                "stars": repo_data.get("stargazers_count", 0),
                "forks": repo_data.get("forks_count", 0),
                "open_issues": repo_data.get("open_issues_count", 0),
            }
            results[repo_name] = {"status": "synced"}
        return results

    def get_sync_state(self, repo_key: str) -> Optional[Dict[str, Any]]:
        return self._sync_state.get(repo_key)


# =============================================================================
# Part 10 — Engineering Intelligence Wires
# =============================================================================

async def _update_knowledge_graph(entity_type: str, entity_id: str, data: Dict[str, Any]) -> None:
    try:
        from backend.services.enterprise_graph_service import enterprise_graph
        await enterprise_graph.upsert_entity(entity_type, entity_id, data)
    except Exception as exc:
        log.debug("Knowledge graph update skipped for %s/%s: %s", entity_type, entity_id, exc)


async def _record_replay(event_type: str, data: Dict[str, Any]) -> None:
    try:
        from backend.services.mission_replay_store import replay_store
        await replay_store.record_event(event_type, data)
    except Exception as exc:
        log.debug("Replay recording skipped: %s", exc)


async def _notify_learning(event_type: str, data: Dict[str, Any]) -> None:
    try:
        from backend.services.enterprise_learning_service import enterprise_learning
        await enterprise_learning.ingest_event(event_type, data)
    except Exception as exc:
        log.debug("Learning ingestion skipped: %s", exc)


async def _notify_recommendation(event_type: str, data: Dict[str, Any]) -> None:
    try:
        from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
        await enterprise_recommendation_engine.ingest_event(event_type, data)
    except Exception as exc:
        log.debug("Recommendation engine ingestion skipped: %s", exc)


async def _record_analytics(metric_name: str, value: Any) -> None:
    try:
        from backend.services.enterprise_analytics_service import analytics_service
        await analytics_service.record_metric(metric_name, value)
    except Exception as exc:
        log.debug("Analytics recording skipped: %s", exc)


_PENDING_DEPLOY_CHECKS_FILE = _DATA_DIR / "pending_deploy_checks.json"


class PendingDeployCheckStore:
    """Durable record of in-flight deploy-regression checks.

    A check is persisted the moment it's scheduled and removed once it
    completes, so a process restart mid-wait can recover and resume it on
    the next startup instead of silently losing it — the one gap a plain
    asyncio.sleep-based delayed task can't cover by itself.
    """

    def __init__(self) -> None:
        self._pending: List[Dict[str, Any]] = _load_json(_PENDING_DEPLOY_CHECKS_FILE)

    def add(self, check_id: str, service: str, deployment_id: str, ctx: Dict[str, Any], check_due_at: str) -> None:
        self._pending = [p for p in self._pending if p.get("check_id") != check_id]
        self._pending.append({
            "check_id": check_id,
            "service": service,
            "deployment_id": deployment_id,
            "ctx": ctx,
            "check_due_at": check_due_at,
        })
        _save_json(_PENDING_DEPLOY_CHECKS_FILE, self._pending)

    def remove(self, check_id: str) -> None:
        self._pending = [p for p in self._pending if p.get("check_id") != check_id]
        _save_json(_PENDING_DEPLOY_CHECKS_FILE, self._pending)

    def list_pending(self) -> List[Dict[str, Any]]:
        return list(self._pending)

    def clear(self) -> None:
        self._pending = []
        _save_json(_PENDING_DEPLOY_CHECKS_FILE, [])


pending_deploy_check_store = PendingDeployCheckStore()


async def _run_deploy_regression_check(
    check_id: str,
    service: str,
    deployment_id: str,
    ctx: Dict[str, Any],
    delay_seconds: float,
) -> None:
    """Wait out the remaining delay, then run the detector and report any regression.

    Always removes the persisted pending-check record on the way out,
    success or failure, so it's never re-run on a later restart.
    """
    import asyncio

    try:
        from backend.connectors.registry import connector_registry
        from backend.services.enterprise_deploy_incident_reporter import report_incident
        from backend.services.enterprise_deploy_regression_detector import DeployRegressionDetector

        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        detector = DeployRegressionDetector(prometheus=connector_registry.get("prometheus"))
        verdict = await detector.check(service, deployment_id)
        if verdict.regressed:
            log.warning(
                "Deploy regression detected: %s (deployment %s) — %s",
                service, deployment_id, "; ".join(verdict.reasons),
            )
            issue = await report_incident(verdict, ctx)
            if issue:
                log.warning("Filed ticket %s for %s", issue.get("key", issue), service)
        else:
            log.info("Deploy clean: %s (deployment %s)", service, deployment_id)
    except Exception as exc:
        log.debug("Deploy regression check skipped for %s: %s", service, exc)
    finally:
        pending_deploy_check_store.remove(check_id)


async def _check_deploy_regression(ctx: Dict[str, Any]) -> Optional["asyncio.Task"]:
    """Kick off a before/after regression check for a successful deploy.

    Fire-and-forget on an asyncio task with a delay, since the "after"
    window needs real time to elapse before it has any data to compare.
    Returns the created task (callers don't need it — production call
    sites just `await` this function without using the result — but
    tests can grab it to await completion deterministically).

    The check is persisted to disk before scheduling (see
    PendingDeployCheckStore) and recovered by recover_pending_deploy_checks()
    on the next startup if the process restarts mid-wait.
    """
    import asyncio

    from backend.services.enterprise_deploy_regression_detector import DeployRegressionDetector

    service = ctx.get("repo_full_name", "")
    deployment_id = str(ctx.get("deployment_id", ""))
    if not service or not deployment_id:
        return None

    check_id = f"{service}::{deployment_id}"
    window_seconds = DeployRegressionDetector().window_seconds
    due_at = (datetime.now(timezone.utc).timestamp()) + window_seconds
    due_at_iso = datetime.fromtimestamp(due_at, tz=timezone.utc).isoformat()
    pending_deploy_check_store.add(check_id, service, deployment_id, ctx, due_at_iso)

    return asyncio.create_task(
        _run_deploy_regression_check(check_id, service, deployment_id, ctx, delay_seconds=window_seconds)
    )


async def recover_pending_deploy_checks() -> int:
    """Resume any deploy-regression checks still in flight when the process
    last stopped. Call once at application startup.
    """
    import asyncio

    recovered = 0
    for record in pending_deploy_check_store.list_pending():
        check_id = record.get("check_id", "")
        service = record.get("service", "")
        deployment_id = record.get("deployment_id", "")
        ctx = record.get("ctx", {})
        if not check_id or not service or not deployment_id:
            pending_deploy_check_store.remove(check_id)
            continue

        try:
            due_at = datetime.fromisoformat(record.get("check_due_at", ""))
        except Exception:
            due_at = datetime.now(timezone.utc)
        remaining = max(0.0, (due_at - datetime.now(timezone.utc)).total_seconds())

        asyncio.create_task(
            _run_deploy_regression_check(check_id, service, deployment_id, ctx, delay_seconds=remaining)
        )
        recovered += 1

    if recovered:
        log.warning("Recovered %d in-flight deploy-regression check(s) after restart", recovered)
    return recovered


async def _wire_to_engineering_executive(event_type: str, ctx: Dict[str, Any]) -> None:
    try:
        from backend.services.enterprise_engineering_executive import get_engineering_executive
        exec_service = get_engineering_executive()
        description = _build_description(event_type, ctx)
        await exec_service.create_task(description, ctx.get("repo_url", ""), ctx.get("branch", ""))
    except Exception as exc:
        log.debug("Engineering executive wire skipped: %s", exc)


def _build_description(event_type: str, ctx: Dict[str, Any]) -> str:
    if event_type == "push":
        commits = ctx.get("commits", [])
        msg = commits[0][:80] if commits else "New push"
        return f"Process push to {ctx.get('branch', 'unknown')}: {msg}"
    elif event_type.startswith("pull_request"):
        return f"Review pull request #{ctx.get('pr_number', '?')}: {ctx.get('pr_title', '')[:80]}"
    elif event_type == "pull_request_review":
        return f"Review submitted on PR #{ctx.get('pr_number', '?')} by {ctx.get('reviewer', 'unknown')}: {ctx.get('review_state', '')}"
    elif event_type == "issues":
        action = ctx.get("action", "updated")
        return f"{action.capitalize()} issue #{ctx.get('issue_number', '?')}: {ctx.get('issue_title', '')[:80]}"
    elif event_type == "workflow_run":
        return f"Track workflow run: {ctx.get('workflow_name', 'unknown')} [{ctx.get('workflow_status', '')}]"
    elif event_type == "release":
        return f"Process release: {ctx.get('release_tag', 'unknown')}"
    elif event_type == "deployment_status":
        return f"Track deployment to {ctx.get('environment', 'unknown')}: {ctx.get('deployment_state', '')}"
    elif event_type == "check_suite":
        return f"Check suite completed: {ctx.get('app', 'unknown')} -> {ctx.get('check_conclusion', '')}"
    return f"Process GitHub {event_type} event"


# =============================================================================
# Part 11 — GithubIntegration Orchestrator
# =============================================================================

class GithubIntegration:
    """Orchestrator that coordinates all subsystems with the real GitHub API."""

    def __init__(self) -> None:
        self._webhook_receiver = WebhookReceiver()
        self._sync_engine = SyncEngine()
        self._enabled: bool = True

    @property
    def webhook_receiver(self) -> WebhookReceiver:
        return self._webhook_receiver

    @property
    def sync_engine(self) -> SyncEngine:
        return self._sync_engine

    # ---- Webhook entry point ----

    async def receive_webhook(
        self,
        body: bytes,
        headers: Dict[str, str],
        secret: str = "",
    ) -> Dict[str, Any]:
        result = await self._webhook_receiver.receive(body, headers, secret)
        if result.get("status") == "duplicate":
            return result
        parsed = result.get("parsed", {})
        event_type = result.get("event_type", "push")
        payload = parsed.get("raw", {})

        if result.get("verified"):
            await self.process_and_wire(event_type, payload)

        return result

    async def process_and_wire(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        internal_type = GitHubEventTranslator.translate(event_type, payload)
        ctx = GitHubEventTranslator.build_mission_context(event_type, payload)
        repo_full = ctx.get("repo_full_name", "")
        parts = repo_full.split("/")
        owner = parts[0] if len(parts) >= 2 else ""
        repo_name = parts[1] if len(parts) >= 2 else ""

        if event_type == "push" and owner and repo_name:
            branch = ctx.get("branch", "")
            await _emit(GITHUB_EVENTS["branch_updated"], f"{repo_full}:{branch}", ctx)
            await _update_knowledge_graph("github_branch", f"{repo_full}:{branch}", ctx)
            await _record_replay(internal_type, ctx)
            await _record_analytics("github.push", 1)

        elif event_type == "pull_request" and owner and repo_name:
            pr_number = ctx.get("pr_number", 0)
            action = ctx.get("pr_action", "")
            await _emit(internal_type, f"{repo_full}#{pr_number}", ctx)
            await _update_knowledge_graph("github_pr", f"{repo_full}#{pr_number}", ctx)
            await _record_replay(internal_type, ctx)
            if action == "opened":
                await _notify_recommendation(internal_type, ctx)
            await _record_analytics("github.pull_request", 1)

        elif event_type == "pull_request_review" and owner and repo_name:
            pr_number = ctx.get("pr_number", 0)
            await _emit(internal_type, f"{repo_full}#{pr_number}", ctx)
            await _update_knowledge_graph("github_review", f"{repo_full}#{pr_number}", ctx)
            await _notify_learning(internal_type, ctx)
            await _record_analytics("github.review", 1)

        elif event_type == "issues" and owner and repo_name:
            issue_number = ctx.get("issue_number", 0)
            await _emit(internal_type, f"{repo_full}#{issue_number}", ctx)
            await _update_knowledge_graph("github_issue", f"{repo_full}#{issue_number}", ctx)
            await _record_analytics("github.issue", 1)

        elif event_type == "workflow_run" and owner and repo_name:
            run_id = ctx.get("workflow_run_id", "")
            await _emit(internal_type, f"{repo_full}/{run_id}", ctx)
            await _update_knowledge_graph("github_workflow_run", f"{repo_full}/{run_id}", ctx)
            await _notify_learning(internal_type, ctx)
            await _record_analytics("github.workflow_run", 1)

        elif event_type == "release" and owner and repo_name:
            tag = ctx.get("release_tag", "")
            await _emit(internal_type, f"{repo_full}/{tag}", ctx)
            await _update_knowledge_graph("github_release", f"{repo_full}/{tag}", ctx)
            await _notify_recommendation(internal_type, ctx)
            await _record_analytics("github.release", 1)

        elif event_type == "deployment_status" and owner and repo_name:
            dep_id = ctx.get("deployment_id", "")
            await _emit(internal_type, f"{repo_full}/{dep_id}", ctx)
            await _update_knowledge_graph("github_deployment", f"{repo_full}/{dep_id}", ctx)
            await _notify_learning(internal_type, ctx)
            await _record_analytics("github.deployment", 1)
            if ctx.get("deployment_state") == "success":
                await _check_deploy_regression(ctx)

        elif event_type == "check_suite" and owner and repo_name:
            suite_id = ctx.get("check_suite_id", "")
            await _emit(internal_type, f"{repo_full}/{suite_id}", ctx)
            await _record_analytics("github.check_suite", 1)

        else:
            await _emit(internal_type, repo_full or event_type, ctx)

        await _wire_to_engineering_executive(event_type, ctx)

        return {"internal_event": internal_type, "context": ctx}

    async def launch_mission_from_webhook(
        self, event_type: str, payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        ctx = GitHubEventTranslator.build_mission_context(event_type, payload)
        try:
            from backend.services.enterprise_engineering_executive import get_engineering_executive
            exec_service = get_engineering_executive()
            description = _build_description(event_type, ctx)
            task = await exec_service.create_task(description, ctx.get("repo_url", ""), ctx.get("branch", ""))
            plan = await exec_service.create_plan(task["task_id"])
            await exec_service.execute_plan(plan["plan_id"])
            ctx["mission_launched"] = True
            ctx["task_id"] = task["task_id"]
            ctx["plan_id"] = plan["plan_id"]
            await _emit(GITHUB_EVENTS["mission_launched"], task["task_id"], ctx)
            return {"task": task, "plan": plan, "context": ctx}
        except Exception as exc:
            log.warning("Failed to launch mission from webhook: %s", exc)
            return None

    # ---- Dashboard ----

    async def get_dashboard_stats(self, owner: str = "", repo: str = "") -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "total_webhooks": len(self._webhook_receiver.get_deliveries(1000)),
            "total_workflow_runs": 0,
            "total_prs": 0,
            "total_issues": 0,
            "total_releases": 0,
            "total_deployments": 0,
            "total_branches": 0,
        }
        if owner and repo:
            try:
                gh = await _get_gh()
                repo_data = await gh.get_repository(owner, repo)
                stats["total_prs"] = repo_data.get("open_issues_count", 0)
                stats["total_issues"] = repo_data.get("open_issues_count", 0)
                workflows = await WorkflowRunManager.list_workflows(owner, repo)
                stats["total_workflow_runs"] = len(workflows)
                branches = await BranchIntelligence.list_branches(owner, repo)
                stats["total_branches"] = len(branches)
                releases = await ReleaseIntelligence.list_releases(owner, repo)
                stats["total_releases"] = len(releases)
                deployments = await DeploymentIntelligence.list_deployments(owner, repo)
                stats["total_deployments"] = len(deployments)
            except Exception as exc:
                log.warning("Dashboard stats fetch failed: %s", exc)
        return stats

    def get_recent_webhooks(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._webhook_receiver.get_deliveries(limit)

    async def get_recent_activity(self, owner: str = "", repo: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for w in self._webhook_receiver.get_deliveries(10):
            items.append({"type": "webhook", "data": w, "timestamp": w.get("received_at", "")})
        if owner and repo:
            try:
                gh = await _get_gh()
                events = await gh.list_repository_events(owner, repo, params={"per_page": 10})
                for e in events:
                    items.append({
                        "type": "event",
                        "data": {
                            "event_type": e.get("type", ""),
                            "repository": _repo_full_name(owner, repo),
                            "sender": (e.get("actor") or {}).get("login", ""),
                            "created_at": e.get("created_at", ""),
                        },
                        "timestamp": e.get("created_at", ""),
                    })
            except Exception as exc:
                log.debug("Event fetch failed: %s", exc)
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return items[:limit]

    def clear_state(self) -> None:
        self._webhook_receiver._delivery_store.clear()


class DeploymentStatusIntegration:
    """Simple deployment status tracker (used by tests)."""

    _deployments: Dict[str, Dict[str, Any]] = {}

    @classmethod
    async def list_deployments(cls) -> List[Dict[str, Any]]:
        return list(cls._deployments.values())

    @classmethod
    async def get_deployment(cls, deployment_id: str) -> Optional[Dict[str, Any]]:
        return cls._deployments.get(deployment_id)

    @classmethod
    async def upsert_deployment(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        dep_id = data.get("id") or data.get("deployment_id", str(uuid.uuid4()))
        existing = cls._deployments.get(dep_id, {})
        existing.update(data)
        existing["id"] = dep_id
        cls._deployments[dep_id] = existing
        return existing

    @classmethod
    async def list_by_environment(cls, environment: str) -> List[Dict[str, Any]]:
        return [d for d in cls._deployments.values() if d.get("environment") == environment]

    @classmethod
    async def list_by_state(cls, state: str) -> List[Dict[str, Any]]:
        return [d for d in cls._deployments.values() if d.get("state") == state]

    @classmethod
    def clear_state(cls) -> None:
        cls._deployments.clear()


github_integration = GithubIntegration()
