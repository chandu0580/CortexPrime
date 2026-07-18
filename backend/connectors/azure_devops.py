from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

AZURE_DEVOPS_API_BASE = "https://dev.azure.com"
AZURE_DEVOPS_ORG_ENV = "AZURE_DEVOPS_ORG"
AZURE_DEVOPS_PROJECT_ENV = "AZURE_DEVOPS_PROJECT"
AZURE_DEVOPS_PAT_ENV = "AZURE_DEVOPS_PAT"
API_VERSION = "7.1"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class AzureDevOpsConnector(BaseConnector):
    connector_name = "Azure DevOps"
    connector_type = "azure_devops"

    def __init__(self) -> None:
        self._org: str = ""
        self._project: str = ""
        self._pat: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._org = credentials.get("organization", self._org)
        self._project = credentials.get("project", self._project)
        self._pat = credentials.get("pat", self._pat)

    async def initialize(self) -> bool:
        self._org = self._org or os.getenv(AZURE_DEVOPS_ORG_ENV, "")
        self._project = self._project or os.getenv(AZURE_DEVOPS_PROJECT_ENV, "")
        self._pat = self._pat or os.getenv(AZURE_DEVOPS_PAT_ENV, "")
        if not self._org or not self._pat:
            log.warning("AZURE_DEVOPS_ORG or AZURE_DEVOPS_PAT not set — Azure DevOps connector in degraded mode")
            self._available = False
            return False

        # Basic Auth with empty username — PAT is the password
        encoded = base64.b64encode(f":{self._pat}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=f"{AZURE_DEVOPS_API_BASE}/{self._org}",
            headers={
                "Authorization": f"Basic {encoded}",
                "Accept": "application/json",
                "User-Agent": "CortexPrime-AzureDevOpsConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        try:
            # Validate auth by listing projects
            resp = await self._client.get("/_apis/projects", params={"api-version": API_VERSION})
            if resp.status_code == 200:
                self._available = True
                user = resp.json().get("displayName", "unknown")
                log.info("Azure DevOps connector initialized — authenticated as %s in org %s", user, self._org)

                # Resolve project if not provided
                if not self._project:
                    self._project = await self._resolve_default_project()
                    if not self._project:
                        log.warning("Azure DevOps: no project found in org %s", self._org)
                        self._available = False
                        return False
                    log.info("Azure DevOps connector resolved project: %s", self._project)

                return True
            else:
                log.warning("Azure DevOps auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("Azure DevOps API unreachable: %s", e)
            self._available = False
            return False

    async def _resolve_default_project(self) -> str:
        try:
            resp = await self._client.get("/_apis/projects", params={"api-version": API_VERSION})
            if resp.status_code == 200:
                body = resp.json()
                projects = body.get("value", [])
                if projects:
                    return projects[0]["name"]
        except Exception:
            pass
        return ""

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("Azure DevOps connector shut down")
        return True

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "available" if self._available else "unavailable",
            "connector": self.connector_type,
            "authenticated": bool(self._pat),
            "organization": self._org,
            "project": self._project,
        }

    # ------------------------------------------------------------------
    # Public API — each method delegates to _execute() for auto-recording
    # ------------------------------------------------------------------

    async def list_projects(self, **kwargs) -> List[Dict[str, Any]]:
        """List all projects in the Azure DevOps organization."""
        params = {"api-version": API_VERSION, **kwargs}
        return await self._execute("list_projects", "projects", self._request_list, "GET",
            "/_apis/projects", params)

    async def list_repositories(self, project_id: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """List Git repositories for a given project (or the default project)."""
        project = project_id or self._project
        params = {"api-version": API_VERSION, **kwargs}
        return await self._execute("list_repositories", "repositories", self._request_list, "GET",
            f"/{project}/_apis/git/repositories", params)

    async def get_pull_requests(self, repo_id: str, **kwargs) -> List[Dict[str, Any]]:
        """List pull requests for a given repository."""
        params = {"api-version": API_VERSION, "searchCriteria.status": "active", **kwargs}
        return await self._execute("get_pull_requests", "pull_requests", self._request_list, "GET",
            f"/{self._project}/_apis/git/repositories/{repo_id}/pullrequests", params)

    async def queue_pipeline(self, pipeline_id: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("queue_pipeline", "pipelines", self._request, "POST",
            f"/{self._project}/_apis/pipelines/{pipeline_id}/runs",
            params={"api-version": API_VERSION},
            json=kwargs or {},
        )

    async def create_work_item(self, title: str, type: str = "Task", description: str = "", **kwargs) -> Dict[str, Any]:
        doc = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
        ]
        if description:
            doc.append({"op": "add", "path": "/fields/System.Description", "value": description})
        return await self._execute("create_work_item", "work_items", self._request, "POST",
            f"/{self._project}/_apis/wit/workitems/${type}",
            params={"api-version": API_VERSION},
            json=doc,
            headers={"Content-Type": "application/json-patch+json"},
        )

    async def update_work_item(self, work_item_id: int, **fields) -> Dict[str, Any]:
        doc = [{"op": "add", "path": f"/fields/{k}", "value": v} for k, v in fields.items()]
        return await self._execute("update_work_item", "work_items", self._request, "PATCH",
            f"/{self._project}/_apis/wit/workitems/{work_item_id}",
            params={"api-version": API_VERSION},
            json=doc,
            headers={"Content-Type": "application/json-patch+json"},
        )

    async def get_work_item(self, work_item_id: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_work_item", "work_items", self._request, "GET",
            f"/{self._project}/_apis/wit/workitems/{work_item_id}",
            params={"api-version": API_VERSION, **kwargs},
        )

    async def list_work_items(self, query: str = "", **kwargs) -> Dict[str, Any]:
        if not query:
            query = f"SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.TeamProject] = '{self._project}' ORDER BY [System.Id]"
        return await self._execute("list_work_items", "work_items", self._request, "POST",
            f"/{self._project}/_apis/wit/wiql",
            params={"api-version": API_VERSION, **kwargs},
            json={"query": query},
        )

    async def list_pipelines(self, **kwargs) -> List[Dict[str, Any]]:
        return await self._execute("list_pipelines", "pipelines", self._request_list, "GET",
            f"/{self._project}/_apis/pipelines",
            {"api-version": API_VERSION, **kwargs},
        )

    async def get_pipeline_run(self, pipeline_id: int, run_id: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_pipeline_run", "pipelines", self._request, "GET",
            f"/{self._project}/_apis/pipelines/{pipeline_id}/runs/{run_id}",
            params={"api-version": API_VERSION, **kwargs},
        )

    async def cancel_pipeline(self, pipeline_id: int, run_id: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("cancel_pipeline", "pipelines", self._request, "PATCH",
            f"/{self._project}/_apis/pipelines/{pipeline_id}/runs/{run_id}",
            params={"api-version": API_VERSION},
            json={"state": "cancelling", **kwargs},
        )

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry + error handling
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("Azure DevOps connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 400:
                    body = self._safe_json(resp)
                    raise ValueError(f"Azure DevOps API: 400 Bad Request — {body.get('message', resp.text[:200])}")
                if resp.status_code == 401:
                    raise PermissionError("Azure DevOps API: 401 Unauthorized — check AZURE_DEVOPS_PAT")
                if resp.status_code == 403:
                    body = self._safe_json(resp)
                    raise PermissionError(f"Azure DevOps API: 403 Forbidden — {body.get('message', resp.text[:200])}")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Azure DevOps API: 404 Not Found — {path}")
                if resp.status_code == 409:
                    body = self._safe_json(resp)
                    raise RuntimeError(f"Azure DevOps API: 409 Conflict — {body.get('message', resp.text[:200])}")
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    if attempt < MAX_RETRIES:
                        log.warning("Azure DevOps API HTTP 429 — waiting %ds (attempt %d/%d)", retry_after, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(retry_after)
                        continue
                    raise RuntimeError(f"Azure DevOps API: HTTP 429 after {MAX_RETRIES} retries")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning("Azure DevOps API HTTP %d — retrying in %.1fs (attempt %d/%d)", resp.status_code, backoff, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"Azure DevOps API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    log.warning("Azure DevOps API request failed: %s — retrying in %.1fs (attempt %d/%d)", e, backoff, attempt + 1, MAX_RETRIES)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Azure DevOps API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"Azure DevOps API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _request_list(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("value", "items", "data", "results", "entries", "workItems"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Dict[str, Any]:
        try:
            return resp.json()
        except Exception:
            return {"message": resp.text[:500]}
