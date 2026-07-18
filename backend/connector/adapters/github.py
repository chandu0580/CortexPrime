from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx

from backend.connector.adapter.interfaces import AdapterHealthStatus, AdapterResult, ConnectorAdapter
from backend.connector.models import Capability

log = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class GitHubAdapter(ConnectorAdapter):

    @property
    def connector_type(self) -> str:
        return "github"

    @property
    def connector_name(self) -> str:
        return "GitHub"

    @property
    def adapter_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized: bool = False
        self._rate_limit_remaining: int = 5000
        self._rate_limit_reset: int = 0

    async def initialize(self) -> bool:
        self._token = os.getenv(GITHUB_TOKEN_ENV, "")
        if not self._token:
            log.warning("GITHUB_TOKEN not set — GitHub adapter in degraded mode")
            return False
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "CortexPrime-GitHubAdapter/1.0",
            },
            timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=10.0),
            event_hooks={"response": [self._on_response]},
        )
        try:
            resp = await self._client.get("/rate_limit")
            if resp.status_code == 200:
                self._initialized = True
                data = resp.json()
                core = data.get("resources", {}).get("core", {})
                self._rate_limit_remaining = core.get("remaining", 5000)
                self._rate_limit_reset = core.get("reset", 0)
                log.info("GitHub adapter initialized — rate limit: %d remaining", self._rate_limit_remaining)
                return True
            log.warning("GitHub auth check failed: HTTP %d", resp.status_code)
            return False
        except httpx.RequestError as e:
            log.warning("GitHub API unreachable: %s", e)
            return False

    async def health_check(self) -> AdapterHealthStatus:
        if not self._initialized or not self._client:
            return AdapterHealthStatus.UNHEALTHY
        try:
            resp = await self._client.get("/rate_limit")
            if resp.status_code == 200:
                return AdapterHealthStatus.HEALTHY
            if resp.status_code in (401, 403):
                return AdapterHealthStatus.DEGRADED
            return AdapterHealthStatus.DEGRADED
        except httpx.RequestError:
            return AdapterHealthStatus.UNHEALTHY

    async def capabilities(self) -> list[Capability]:
        return [
            Capability.SEARCH,
            Capability.EXECUTE,
            Capability.BUILD,
            Capability.DEPLOY,
            Capability.OBSERVE,
        ]

    async def execute(self, capability: Capability, inputs: dict[str, Any],
                      timeout_seconds: Optional[int] = None) -> AdapterResult:
        timeout = timeout_seconds or DEFAULT_TIMEOUT
        start = time.monotonic()

        if capability == Capability.SEARCH:
            return await self._search_repos(inputs, start)
        if capability == Capability.BUILD:
            return await self._dispatch_workflow(inputs, start)
        if capability == Capability.DEPLOY:
            return await self._create_deployment(inputs, start)
        if capability == Capability.EXECUTE:
            return await self._execute_action(inputs, start)
        if capability == Capability.OBSERVE:
            return await self._observe_repo(inputs, start)

        return AdapterResult(
            success=False,
            error=f"Unsupported capability: {capability.value}",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def shutdown(self) -> None:
        self._initialized = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("GitHub adapter shut down")

    async def metadata(self) -> dict[str, Any]:
        base = await super().metadata()
        base["rate_limit_remaining"] = self._rate_limit_remaining
        return base

    async def _on_response(self, response: httpx.Response) -> None:
        if "X-RateLimit-Remaining" in response.headers:
            self._rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        if "X-RateLimit-Reset" in response.headers:
            self._rate_limit_reset = int(response.headers["X-RateLimit-Reset"])
        if response.status_code >= 400:
            log.warning("[GitHub] HTTP %d: %s", response.status_code, response.url)

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self._client:
            raise RuntimeError("GitHub adapter not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 401:
                    raise PermissionError("GitHub API: 401 Unauthorized")
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
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning("GitHub API HTTP %d — retrying in %.1fs (attempt %d/%d)", resp.status_code, backoff, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"GitHub API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"GitHub API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"GitHub API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _search_repos(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        query = inputs.get("query", "")
        if not query:
            return AdapterResult(success=False, error="Missing 'query' input", duration_ms=(time.monotonic() - start) * 1000)
        try:
            data = await self._request("GET", "/search/repositories", params={"q": query})
            items = data.get("items", [])
            repos = [{"name": r["full_name"], "url": r["html_url"], "stars": r.get("stargazers_count", 0), "description": r.get("description")} for r in items[:20]]
            return AdapterResult(success=True, outputs={"repositories": repos, "total_count": data.get("total_count", 0)}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _dispatch_workflow(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        owner = inputs.get("owner")
        repo = inputs.get("repo")
        workflow_id = inputs.get("workflow_id")
        ref = inputs.get("ref", "main")
        if not all([owner, repo, workflow_id]):
            return AdapterResult(success=False, error="Missing 'owner', 'repo', or 'workflow_id'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            await self._request("POST", f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches", json={"ref": ref, "inputs": inputs.get("inputs", {})})
            return AdapterResult(success=True, outputs={"message": f"Workflow {workflow_id} dispatched on {ref}"}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _create_deployment(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        owner = inputs.get("owner")
        repo = inputs.get("repo")
        ref = inputs.get("ref", "main")
        environment = inputs.get("environment", "production")
        if not all([owner, repo]):
            return AdapterResult(success=False, error="Missing 'owner' or 'repo'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            data = await self._request("POST", f"/repos/{owner}/{repo}/deployments", json={"ref": ref, "environment": environment})
            return AdapterResult(success=True, outputs={"deployment_id": data.get("id"), "url": data.get("html_url")}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _execute_action(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        owner = inputs.get("owner")
        repo = inputs.get("repo")
        if not all([owner, repo]):
            return AdapterResult(success=False, error="Missing 'owner' or 'repo'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            data = await self._request("GET", f"/repos/{owner}/{repo}")
            return AdapterResult(success=True, outputs={"repo": data.get("full_name"), "language": data.get("language"), "stars": data.get("stargazers_count"), "forks": data.get("forks_count")}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _observe_repo(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        owner = inputs.get("owner")
        repo = inputs.get("repo")
        if not all([owner, repo]):
            return AdapterResult(success=False, error="Missing 'owner' or 'repo'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            commits = await self._request("GET", f"/repos/{owner}/{repo}/commits", params={"per_page": 10})
            workflows = await self._request("GET", f"/repos/{owner}/{repo}/actions/workflows", params={"per_page": 5})
            return AdapterResult(success=True, outputs={"commits": [{"sha": c["sha"], "message": c["commit"]["message"], "author": c["commit"]["author"]["name"]} for c in commits], "workflows": [{"id": w["id"], "name": w["name"], "state": w["state"]} for w in workflows.get("workflows", [])]}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)
