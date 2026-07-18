from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_GRAPHQL_BASE = "https://api.github.com/graphql"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0
MAX_PAGES = 10

RETRYABLE_STATUSES = {429, 502, 503, 504}


class GitHubConnector(BaseConnector):
    connector_name = "GitHub"
    connector_type = "github"

    def __init__(self) -> None:
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False
        self._authenticated_user: str = ""
        self._rate_limit_remaining: int = 5000
        self._rate_limit_reset: int = 0
        self._etag_cache: Dict[str, Tuple[str, Any]] = {}

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._token = credentials.get("token", self._token)

    async def initialize(self) -> bool:
        self._token = self._token or os.getenv(GITHUB_TOKEN_ENV, "")
        if not self._token:
            log.warning("GITHUB_TOKEN not set — GitHub connector in degraded mode")
            self._available = False
            return False
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "CortexPrime-GitHubConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            event_hooks={
                "response": [self._on_response],
            },
        )
        try:
            resp = await self._client.get("/rate_limit")
            if resp.status_code == 200:
                self._available = True
                data = resp.json()
                core = data.get("resources", {}).get("core", {})
                self._rate_limit_remaining = core.get("remaining", 5000)
                self._rate_limit_reset = core.get("reset", 0)
                login = data.get("resources", {}).get("rate", {}).get("table", "unknown")
                self._authenticated_user = login
                log.info("GitHub connector initialized — rate limit: %d remaining", self._rate_limit_remaining)
                return True
            else:
                log.warning("GitHub auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("GitHub API unreachable: %s", e)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("GitHub connector shut down")
        return True

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "available" if self._available else "unavailable",
            "connector": self.connector_type,
            "authenticated": bool(self._token),
            "rate_limit_remaining": self._rate_limit_remaining,
        }

    async def _on_response(self, response: httpx.Response) -> None:
        if "X-RateLimit-Remaining" in response.headers:
            self._rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        if "X-RateLimit-Reset" in response.headers:
            self._rate_limit_reset = int(response.headers["X-RateLimit-Reset"])
        if response.status_code >= 400:
            log.warning("[GitHub] HTTP %d: %s", response.status_code, response.url)

    # ------------------------------------------------------------------
    # GraphQL API
    # ------------------------------------------------------------------

    async def graphql_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("GitHub connector not initialized")
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = await self._client.post(
            GITHUB_GRAPHQL_BASE,
            json=payload,
        )
        if resp.status_code == 200:
            data = resp.json()
            if "errors" in data:
                raise RuntimeError(f"GraphQL errors: {data['errors']}")
            return data.get("data", {})
        if resp.status_code == 401:
            raise PermissionError("GitHub API: 401 Unauthorized")
        raise RuntimeError(f"GraphQL request failed: HTTP {resp.status_code}")

    # ------------------------------------------------------------------
    # Public API — each method delegates to _execute() for auto-recording
    # ------------------------------------------------------------------

    async def create_repository(self, owner: str, name: str, description: str = "", visibility: str = "private", **kwargs) -> Dict[str, Any]:
        return await self._execute("create_repository", "repository", self._request, "POST", f"/orgs/{owner}/repos" if owner != self._authenticated_user else "/user/repos", json={"name": name, "description": description, "private": visibility == "private", **kwargs})

    async def get_repository(self, owner: str, repo: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_repository", "repository", self._request, "GET", f"/repos/{owner}/{repo}")

    async def list_repositories(self, owner: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        return await self._execute("list_repositories", "repository", self._request_list, "GET", f"/orgs/{owner}/repos" if owner else "/user/repos", kwargs.get("params", {}))

    async def archive_repository(self, owner: str, repo: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("archive_repository", "repository", self._request, "PATCH", f"/repos/{owner}/{repo}", json={"archived": True})

    async def create_issue(self, owner: str, repo: str, title: str, body: str = "", labels: Optional[List[str]] = None, assignees: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        return await self._execute("create_issue", "issues", self._request, "POST", f"/repos/{owner}/{repo}/issues", json={"title": title, "body": body, "labels": labels or [], "assignees": assignees or [], **kwargs})

    async def get_issue(self, owner: str, repo: str, issue_number: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_issue", "issues", self._request, "GET", f"/repos/{owner}/{repo}/issues/{issue_number}")

    async def update_issue(self, owner: str, repo: str, issue_number: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("update_issue", "issues", self._request, "PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", json=kwargs)

    async def create_pull_request(self, owner: str, repo: str, title: str, body: str = "", head: str = "", base: str = "main", **kwargs) -> Dict[str, Any]:
        return await self._execute("create_pull_request", "pull_requests", self._request, "POST", f"/repos/{owner}/{repo}/pulls", json={"title": title, "body": body, "head": head, "base": base, **kwargs})

    async def merge_pull_request(self, owner: str, repo: str, pr_number: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("merge_pull_request", "pull_requests", self._request, "PUT", f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", json=kwargs)

    async def list_pull_requests(self, owner: str, repo: str, state: str = "open", **kwargs) -> List[Dict[str, Any]]:
        params = {"state": state, "per_page": 100, **kwargs.get("params", {})}
        return await self._execute("list_pull_requests", "pull_requests", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/pulls", params)

    async def dispatch_workflow(self, owner: str, repo: str, workflow_id: str, ref: str = "main", inputs: Optional[Dict[str, str]] = None, **kwargs) -> bool:
        await self._execute("dispatch_workflow", "workflows", self._request, "POST", f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches", json={"ref": ref, "inputs": inputs or {}})
        return True

    async def list_branches(self, owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        return await self._execute("list_branches", "branches", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/branches", params)

    async def create_branch(self, owner: str, repo: str, branch_name: str, source_branch: str = "main", **kwargs) -> Dict[str, Any]:
        ref_resp = await self._request("GET", f"/repos/{owner}/{repo}/git/refs/heads/{source_branch}")
        sha = ref_resp["object"]["sha"]
        return await self._execute("create_branch", "branches", self._request, "POST", f"/repos/{owner}/{repo}/git/refs", json={"ref": f"refs/heads/{branch_name}", "sha": sha, **kwargs})

    async def create_release(self, owner: str, repo: str, tag_name: str, name: str = "", body: str = "", draft: bool = False, prerelease: bool = False, **kwargs) -> Dict[str, Any]:
        return await self._execute("create_release", "releases", self._request, "POST", f"/repos/{owner}/{repo}/releases", json={"tag_name": tag_name, "name": name or tag_name, "body": body, "draft": draft, "prerelease": prerelease, **kwargs})

    async def get_release(self, owner: str, repo: str, tag: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_release", "releases", self._request, "GET", f"/repos/{owner}/{repo}/releases/tags/{tag}")

    async def get_pull_request(self, owner: str, repo: str, pull_number: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_pull_request", "pull_requests", self._request, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}")

    async def get_workflow_runs(self, owner: str, repo: str, workflow_id: str, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        return await self._execute("get_workflow_runs", "workflows", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs", params)

    # ------------------------------------------------------------------
    # Checks API
    # ------------------------------------------------------------------

    async def list_check_runs(self, owner: str, repo: str, ref: str, **kwargs) -> Dict[str, Any]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        result = await self._execute("list_check_runs", "checks", self._request, "GET", f"/repos/{owner}/{repo}/commits/{ref}/check-runs", params=params)
        if isinstance(result, dict) and "check_runs" in result:
            return result
        return {"check_runs": result if isinstance(result, list) else []}

    async def list_check_suites(self, owner: str, repo: str, ref: str, **kwargs) -> Dict[str, Any]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        result = await self._execute("list_check_suites", "checks", self._request, "GET", f"/repos/{owner}/{repo}/commits/{ref}/check-suites", params=params)
        if isinstance(result, dict) and "check_suites" in result:
            return result
        return {"check_suites": result if isinstance(result, list) else []}

    # ------------------------------------------------------------------
    # Commit Status API
    # ------------------------------------------------------------------

    async def create_commit_status(self, owner: str, repo: str, sha: str, state: str, description: str = "", context: str = "CortexPrime", target_url: str = "") -> Dict[str, Any]:
        return await self._execute("create_commit_status", "statuses", self._request, "POST", f"/repos/{owner}/{repo}/statuses/{sha}", json={"state": state, "description": description, "context": context, "target_url": target_url})

    async def list_commit_statuses(self, owner: str, repo: str, ref: str, **kwargs) -> List[Dict[str, Any]]:
        result = await self._execute("list_commit_statuses", "statuses", self._request, "GET", f"/repos/{owner}/{repo}/commits/{ref}/statuses", params=kwargs.get("params", {}))
        if isinstance(result, dict):
            return result.get("statuses", [result])
        return result if isinstance(result, list) else []

    async def get_combined_status(self, owner: str, repo: str, ref: str) -> Dict[str, Any]:
        result = await self._execute("get_combined_status", "statuses", self._request, "GET", f"/repos/{owner}/{repo}/commits/{ref}/status")
        if isinstance(result, dict) and "state" in result:
            return result
        return {"state": "unknown", "statuses": []}

    # ------------------------------------------------------------------
    # Deployments API
    # ------------------------------------------------------------------

    async def create_deployment(self, owner: str, repo: str, ref: str, environment: str = "production", task: str = "deploy", description: str = "", auto_merge: bool = False, required_contexts: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        return await self._execute("create_deployment", "deployments", self._request, "POST", f"/repos/{owner}/{repo}/deployments", json={"ref": ref, "environment": environment, "task": task, "description": description, "auto_merge": auto_merge, "required_contexts": required_contexts or [], **kwargs})

    async def list_deployments(self, owner: str, repo: str, environment: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        if environment:
            params["environment"] = environment
        return await self._execute("list_deployments", "deployments", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/deployments", params)

    async def get_deployment(self, owner: str, repo: str, deployment_id: int) -> Dict[str, Any]:
        return await self._execute("get_deployment", "deployments", self._request, "GET", f"/repos/{owner}/{repo}/deployments/{deployment_id}")

    async def create_deployment_status(self, owner: str, repo: str, deployment_id: int, state: str, description: str = "", log_url: str = "", environment_url: str = "", **kwargs) -> Dict[str, Any]:
        return await self._execute("create_deployment_status", "deployments", self._request, "POST", f"/repos/{owner}/{repo}/deployments/{deployment_id}/statuses", json={"state": state, "description": description, "log_url": log_url, "environment_url": environment_url, **kwargs})

    async def list_deployment_statuses(self, owner: str, repo: str, deployment_id: int, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        return await self._execute("list_deployment_statuses", "deployments", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/deployments/{deployment_id}/statuses", params)

    # ------------------------------------------------------------------
    # Reviews API
    # ------------------------------------------------------------------

    async def list_pull_request_reviews(self, owner: str, repo: str, pull_number: int, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        return await self._execute("list_pull_request_reviews", "reviews", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews", params)

    async def get_pull_request_review(self, owner: str, repo: str, pull_number: int, review_id: int) -> Dict[str, Any]:
        return await self._execute("get_pull_request_review", "reviews", self._request, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}")

    async def create_pull_request_review(self, owner: str, repo: str, pull_number: int, body: str = "", event: str = "COMMENT", comments: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Dict[str, Any]:
        return await self._execute("create_pull_request_review", "reviews", self._request, "POST", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews", json={"body": body, "event": event, "comments": comments or [], **kwargs})

    async def submit_pull_request_review(self, owner: str, repo: str, pull_number: int, review_id: int, body: str = "", event: str = "APPROVE") -> Dict[str, Any]:
        return await self._execute("submit_pull_request_review", "reviews", self._request, "POST", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/events", json={"body": body, "event": event})

    async def dismiss_pull_request_review(self, owner: str, repo: str, pull_number: int, review_id: int, message: str = "") -> Dict[str, Any]:
        return await self._execute("dismiss_pull_request_review", "reviews", self._request, "PUT", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/dismissals", json={"message": message})

    async def list_pull_request_reviewers(self, owner: str, repo: str, pull_number: int) -> List[Dict[str, Any]]:
        result = await self._execute("list_pull_request_reviewers", "reviews", self._request, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers")
        if isinstance(result, dict):
            return result.get("users", []) + result.get("teams", [])
        return result if isinstance(result, list) else []

    # ------------------------------------------------------------------
    # Branch Protection API
    # ------------------------------------------------------------------

    async def get_branch_protection(self, owner: str, repo: str, branch: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._execute("get_branch_protection", "branches", self._request, "GET", f"/repos/{owner}/{repo}/branches/{branch}/protection")
        except (FileNotFoundError, RuntimeError):
            return None

    async def update_branch_protection(self, owner: str, repo: str, branch: str, required_status_checks: Optional[Dict[str, Any]] = None, enforce_admins: bool = True, required_pull_request_reviews: Optional[Dict[str, Any]] = None, restrictions: Optional[Dict[str, Any]] = None, **kwargs) -> Optional[Dict[str, Any]]:
        return await self._execute("update_branch_protection", "branches", self._request, "PUT", f"/repos/{owner}/{repo}/branches/{branch}/protection", json={
            "required_status_checks": required_status_checks,
            "enforce_admins": enforce_admins,
            "required_pull_request_reviews": required_pull_request_reviews,
            "restrictions": restrictions,
            **kwargs,
        })

    async def remove_branch_protection(self, owner: str, repo: str, branch: str) -> bool:
        try:
            await self._execute("remove_branch_protection", "branches", self._request, "DELETE", f"/repos/{owner}/{repo}/branches/{branch}/protection")
            return True
        except Exception:
            return False

    async def get_admin_enforcement(self, owner: str, repo: str, branch: str) -> bool:
        try:
            result = await self._execute("get_admin_enforcement", "branches", self._request, "GET", f"/repos/{owner}/{repo}/branches/{branch}/protection/enforce_admins")
            if isinstance(result, dict):
                return result.get("enabled", False)
            return False
        except Exception:
            return False

    async def set_admin_enforcement(self, owner: str, repo: str, branch: str, enabled: bool = True) -> Optional[Dict[str, Any]]:
        method = "POST" if enabled else "DELETE"
        return await self._execute("set_admin_enforcement", "branches", self._request, method, f"/repos/{owner}/{repo}/branches/{branch}/protection/enforce_admins")

    # ------------------------------------------------------------------
    # Releases API extensions
    # ------------------------------------------------------------------

    async def list_releases(self, owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        return await self._execute("list_releases", "releases", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/releases", params)

    async def get_latest_release(self, owner: str, repo: str) -> Dict[str, Any]:
        return await self._execute("get_latest_release", "releases", self._request, "GET", f"/repos/{owner}/{repo}/releases/latest")

    async def delete_release(self, owner: str, repo: str, release_id: int) -> bool:
        try:
            await self._execute("delete_release", "releases", self._request, "DELETE", f"/repos/{owner}/{repo}/releases/{release_id}")
            return True
        except Exception:
            return False

    async def get_release_by_id(self, owner: str, repo: str, release_id: int) -> Dict[str, Any]:
        return await self._execute("get_release_by_id", "releases", self._request, "GET", f"/repos/{owner}/{repo}/releases/{release_id}")

    # ------------------------------------------------------------------
    # Workflow API extensions
    # ------------------------------------------------------------------

    async def list_workflows(self, owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        result = await self._execute("list_workflows", "workflows", self._request, "GET", f"/repos/{owner}/{repo}/actions/workflows", params=kwargs.get("params", {}))
        if isinstance(result, dict):
            return result.get("workflows", [])
        return result if isinstance(result, list) else []

    async def get_workflow(self, owner: str, repo: str, workflow_id: str) -> Dict[str, Any]:
        return await self._execute("get_workflow", "workflows", self._request, "GET", f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}")

    async def list_workflow_runs(self, owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        result = await self._execute("list_workflow_runs", "workflows", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/actions/runs", params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("workflow_runs", [result])
        return []

    async def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        return await self._execute("get_workflow_run", "workflows", self._request, "GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}")

    async def cancel_workflow_run(self, owner: str, repo: str, run_id: int) -> bool:
        try:
            await self._execute("cancel_workflow_run", "workflows", self._request, "POST", f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel")
            return True
        except Exception:
            return False

    async def rerun_workflow(self, owner: str, repo: str, run_id: int) -> bool:
        try:
            await self._execute("rerun_workflow", "workflows", self._request, "POST", f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Events API
    # ------------------------------------------------------------------

    async def list_repository_events(self, owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        return await self._execute("list_repository_events", "events", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/events", params)

    async def list_repository_tags(self, owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs.get("params", {})}
        return await self._execute("list_repository_tags", "tags", self._request_list_paginated, "GET", f"/repos/{owner}/{repo}/tags", params)

    # ------------------------------------------------------------------
    # Rate limit
    # ------------------------------------------------------------------

    async def get_rate_limit(self) -> Dict[str, Any]:
        return await self._execute("get_rate_limit", "rate", self._request, "GET", "/rate_limit")

    def get_rate_limit_remaining(self) -> int:
        return self._rate_limit_remaining

    async def wait_if_needed(self) -> None:
        if self._rate_limit_remaining < 10 and self._rate_limit_reset > 0:
            wait = max(self._rate_limit_reset - int(time.time()), 1)
            log.warning("Rate limit nearly exhausted (%d remaining) — waiting %ds", self._rate_limit_remaining, wait)
            await asyncio.sleep(wait)

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry + error handling
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("GitHub connector not initialized")
        await self.wait_if_needed()
        cache_key = f"{method}:{path}:{hashlib.md5(json.dumps(kwargs.get('params', {}), sort_keys=True).encode()).hexdigest()}"
        if method.upper() == "GET" and cache_key in self._etag_cache:
            etag, cached_data = self._etag_cache[cache_key]
            kwargs.setdefault("headers", {})["If-None-Match"] = etag
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 304:
                    _, cached = self._etag_cache.get(cache_key, (None, {}))
                    return cached
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 401:
                    raise PermissionError("GitHub API: 401 Unauthorized — check GITHUB_TOKEN")
                if resp.status_code == 403:
                    body = resp.json()
                    if "rate limit" in body.get("message", "").lower():
                        reset_at = body.get("reset", 0)
                        wait = max(int(reset_at) - int(time.time()), 1) if reset_at else 60
                        log.warning("GitHub rate limited — waiting %ds", wait)
                        await asyncio.sleep(wait)
                        continue
                    raise PermissionError(f"GitHub API: 403 Forbidden — {body.get('message', '')}")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"GitHub API: 404 Not Found — {path}")
                if resp.status_code == 409:
                    raise RuntimeError(f"GitHub API: 409 Conflict — {resp.json().get('message', '')}")
                if resp.status_code == 422:
                    body = resp.json()
                    errors = body.get("errors", [])
                    detail = "; ".join(e.get("message", "") for e in errors) or body.get("message", "")
                    raise ValueError(f"GitHub API: 422 Unprocessable — {detail}")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning("GitHub API HTTP %d — retrying in %.1fs (attempt %d/%d)", resp.status_code, backoff, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"GitHub API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                data = resp.json()
                etag = resp.headers.get("ETag")
                if method.upper() == "GET" and etag and isinstance(data, dict):
                    self._etag_cache[cache_key] = (etag, data)
                return data
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    log.warning("GitHub API request failed: %s — retrying in %.1fs (attempt %d/%d)", e, backoff, attempt + 1, MAX_RETRIES)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"GitHub API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"GitHub API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _request_list(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "workflow_runs" in result:
            return result["workflow_runs"]
        if isinstance(result, dict):
            for key in ("items", "data", "results", "entries"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []

    async def _request_list_paginated(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        all_items: List[Dict[str, Any]] = []
        page = 1
        while page <= MAX_PAGES:
            page_params = dict(params or {})
            page_params["per_page"] = 100
            page_params["page"] = page
            items = await self._request_list(method, path, params=page_params)
            if not items:
                break
            all_items.extend(items)
            if len(items) < 100:
                break
            page += 1
        return all_items
