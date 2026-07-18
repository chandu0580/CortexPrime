from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from typing import Any, Optional

import httpx

from backend.connector.adapter.interfaces import AdapterHealthStatus, AdapterResult, ConnectorAdapter
from backend.connector.models import Capability

log = logging.getLogger(__name__)

JIRA_BASE_URL_ENV = "JIRA_BASE_URL"
JIRA_EMAIL_ENV = "JIRA_EMAIL"
JIRA_TOKEN_ENV = "JIRA_API_TOKEN"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class JiraAdapter(ConnectorAdapter):

    @property
    def connector_type(self) -> str:
        return "jira"

    @property
    def connector_name(self) -> str:
        return "Jira"

    @property
    def adapter_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        self._base_url: str = ""
        self._email: str = ""
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized: bool = False
        self._authenticated_user: str = ""

    async def initialize(self) -> bool:
        self._base_url = os.getenv(JIRA_BASE_URL_ENV, "https://chandu-ai.atlassian.net").rstrip("/")
        self._email = os.getenv(JIRA_EMAIL_ENV, "")
        self._token = os.getenv(JIRA_TOKEN_ENV, "")
        if not self._email or not self._token:
            log.warning("JIRA_EMAIL or JIRA_API_TOKEN not set — Jira adapter in degraded mode")
            return False
        encoded = base64.b64encode(f"{self._email}:{self._token}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Basic {encoded}",
                "Accept": "application/json",
                "User-Agent": "CortexPrime-JiraAdapter/1.0",
            },
            timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=10.0),
        )
        try:
            resp = await self._client.get("/rest/api/3/myself")
            if resp.status_code == 200:
                self._initialized = True
                self._authenticated_user = resp.json().get("displayName", "unknown")
                log.info("Jira adapter initialized — authenticated as %s", self._authenticated_user)
                return True
            log.warning("Jira auth check failed: HTTP %d", resp.status_code)
            return False
        except httpx.RequestError as e:
            log.warning("Jira API unreachable: %s", e)
            return False

    async def health_check(self) -> AdapterHealthStatus:
        if not self._initialized or not self._client:
            return AdapterHealthStatus.UNHEALTHY
        try:
            resp = await self._client.get("/rest/api/3/myself")
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
            Capability.NOTIFY,
        ]

    async def execute(self, capability: Capability, inputs: dict[str, Any],
                      timeout_seconds: Optional[int] = None) -> AdapterResult:
        timeout = timeout_seconds or DEFAULT_TIMEOUT
        start = time.monotonic()

        if capability == Capability.SEARCH:
            return await self._search_issues(inputs, start)
        if capability == Capability.EXECUTE:
            return await self._create_or_update_issue(inputs, start)
        if capability == Capability.NOTIFY:
            return await self._notify(inputs, start)

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
        log.info("Jira adapter shut down")

    async def metadata(self) -> dict[str, Any]:
        base = await super().metadata()
        base["authenticated_user"] = self._authenticated_user
        base["base_url"] = self._base_url
        return base

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self._client:
            raise RuntimeError("Jira adapter not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 401:
                    raise PermissionError("Jira API: 401 Unauthorized")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"Jira API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Jira API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"Jira API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _search_issues(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        jql = inputs.get("jql", inputs.get("query", ""))
        if not jql:
            return AdapterResult(success=False, error="Missing 'jql' or 'query' input", duration_ms=(time.monotonic() - start) * 1000)
        try:
            data = await self._request("GET", "/rest/api/3/search", params={"jql": jql, "maxResults": inputs.get("max_results", 20)})
            issues = [{"key": i["key"], "summary": i["fields"].get("summary", ""), "status": i["fields"].get("status", {}).get("name", ""), "assignee": i["fields"].get("assignee", {}).get("displayName", "") if i["fields"].get("assignee") else None} for i in data.get("issues", [])]
            return AdapterResult(success=True, outputs={"issues": issues, "total": data.get("total", 0)}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _create_or_update_issue(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        project_key = inputs.get("project_key")
        summary = inputs.get("summary", inputs.get("title", ""))
        issue_type = inputs.get("issue_type", "Task")
        description = inputs.get("description", "")
        issue_key = inputs.get("issue_key")
        if not project_key and not issue_key:
            return AdapterResult(success=False, error="Missing 'project_key' or 'issue_key'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            if issue_key:
                fields = {k: v for k, v in inputs.items() if k in ("summary", "description")}
                if fields:
                    await self._request("PUT", f"/rest/api/3/issue/{issue_key}", json={"fields": fields})
                return AdapterResult(success=True, outputs={"issue_key": issue_key, "action": "updated"}, duration_ms=(time.monotonic() - start) * 1000)
            data = await self._request("POST", "/rest/api/3/issue", json={"fields": {"project": {"key": project_key}, "issuetype": {"name": issue_type}, "summary": summary, "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]}}})
            return AdapterResult(success=True, outputs={"issue_key": data.get("key"), "id": data.get("id")}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _notify(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        issue_key = inputs.get("issue_key")
        comment = inputs.get("comment", inputs.get("message", ""))
        if not issue_key:
            return AdapterResult(success=False, error="Missing 'issue_key'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            await self._request("POST", f"/rest/api/3/issue/{issue_key}/comment", json={"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]}})
            return AdapterResult(success=True, outputs={"issue_key": issue_key, "action": "commented"}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)
