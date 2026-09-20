from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector
from backend.connectors.effects import guard_raw_request

log = logging.getLogger(__name__)

CIRCLECI_API_BASE = "https://circleci.com/api/v2"
CIRCLECI_TOKEN_ENV = "CIRCLECI_TOKEN"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0
RETRYABLE_STATUSES = {429, 502, 503, 504}


class CircleCIConnector(BaseConnector):
    connector_name = "CircleCI"
    connector_type = "circleci"

    def __init__(self) -> None:
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._token = credentials.get("token", self._token)

    async def initialize(self) -> bool:
        self._token = self._token or self._load_credentials().get("token", "")
        if not self._token:
            log.warning("CIRCLECI_TOKEN not set — CircleCI connector in degraded mode")
            self._available = False
            return False

        self._client = httpx.AsyncClient(
            base_url=CIRCLECI_API_BASE,
            headers={
                "Circle-Token": self._token,
                "Accept": "application/json",
                "User-Agent": "CortexPrime-CircleCIConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        try:
            resp = await self._client.get("/me")
            if resp.status_code == 200:
                self._available = True
                user = resp.json().get("name", "unknown")
                log.info("CircleCI connector initialized — authenticated as %s", user)
                return True
            else:
                log.warning("CircleCI auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("CircleCI API unreachable: %s", e)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        return True

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "available" if self._available else "unavailable",
            "connector": self.connector_type,
            "authenticated": bool(self._token),
        }

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        # Audit S-1: a state-changing raw request outside an admitted _execute
        # operation is an unnamed write and meets the effect gate.
        guard_raw_request(self.connector_type, method)
        if not self._client:
            raise RuntimeError("CircleCI connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 401:
                    raise PermissionError("CircleCI API: 401 Unauthorized")
                if resp.status_code == 403:
                    raise PermissionError("CircleCI API: 403 Forbidden")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"CircleCI API: 404 Not Found — {path}")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"CircleCI API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"CircleCI request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"CircleCI request failed after {MAX_RETRIES} retries: {last_error}")

    async def _request_list(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("items", "data", "results"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []

    # ---- Projects ----

    async def list_projects(self) -> List[Dict[str, Any]]:
        return await self._execute("list_projects", "projects", self._request_list, "GET", "/projects")

    async def get_project(self, project_slug: str) -> Dict[str, Any]:
        return await self._execute("get_project", "projects", self._request, "GET", f"/project/{project_slug}")

    # ---- Pipelines ----

    async def list_pipelines(self, project_slug: str, **kwargs) -> List[Dict[str, Any]]:
        params = {"page-size": 100, **kwargs}
        return await self._execute("list_pipelines", "pipelines", self._request_list, "GET", f"/project/{project_slug}/pipeline", params=params)

    async def get_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        return await self._execute("get_pipeline", "pipelines", self._request, "GET", f"/pipeline/{pipeline_id}")

    async def trigger_pipeline(self, project_slug: str, branch: str = "main", parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        json_data: Dict[str, Any] = {"branch": branch}
        if parameters:
            json_data["parameters"] = parameters
        return await self._execute("trigger_pipeline", "pipelines", self._request, "POST", f"/project/{project_slug}/pipeline", json=json_data)

    async def cancel_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        return await self._execute("cancel_pipeline", "pipelines", self._request, "POST", f"/pipeline/{pipeline_id}/cancel")

    # ---- Workflows ----

    async def list_workflows(self, pipeline_id: str) -> List[Dict[str, Any]]:
        return await self._execute("list_workflows", "workflows", self._request_list, "GET", f"/pipeline/{pipeline_id}/workflow")

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        return await self._execute("get_workflow", "workflows", self._request, "GET", f"/workflow/{workflow_id}")

    async def rerun_workflow(self, workflow_id: str, from_failed: bool = False) -> Dict[str, Any]:
        json_data = {"from_failed": from_failed}
        return await self._execute("rerun_workflow", "workflows", self._request, "POST", f"/workflow/{workflow_id}/rerun", json=json_data)

    async def cancel_workflow(self, workflow_id: str) -> Dict[str, Any]:
        return await self._execute("cancel_workflow", "workflows", self._request, "POST", f"/workflow/{workflow_id}/cancel")

    async def approve_workflow(self, workflow_id: str, approval_id: str) -> Dict[str, Any]:
        return await self._execute("approve_workflow", "workflows", self._request, "POST", f"/workflow/{workflow_id}/approve/{approval_id}")

    # ---- Jobs ----

    async def list_jobs(self, pipeline_id: str) -> List[Dict[str, Any]]:
        workflows = await self.list_workflows(pipeline_id)
        all_jobs: List[Dict[str, Any]] = []
        for wf in workflows:
            wf_id = wf.get("id", "")
            if wf_id:
                try:
                    jobs = await self._execute("list_jobs", "jobs", self._request_list, "GET", f"/workflow/{wf_id}/job")
                    for j in jobs:
                        j["workflow_id"] = wf_id
                        j["workflow_name"] = wf.get("name", "")
                    all_jobs.extend(jobs)
                except Exception:
                    pass
        return all_jobs

    async def get_job(self, job_number: int, project_slug: str) -> Dict[str, Any]:
        return await self._execute("get_job", "jobs", self._request, "GET", f"/project/{project_slug}/job/{job_number}")

    async def get_job_artifacts(self, job_number: int, project_slug: str) -> List[Dict[str, Any]]:
        return await self._execute("get_job_artifacts", "artifacts", self._request_list, "GET", f"/project/{project_slug}/{job_number}/artifacts")

    async def get_job_details(self, job_number: int, project_slug: str) -> Dict[str, Any]:
        return await self._execute("get_job_details", "jobs", self._request, "GET", f"/project/{project_slug}/job/{job_number}/details")

    # ---- Insights ----

    async def get_project_insights(self, project_slug: str, branch: str = "main") -> Dict[str, Any]:
        return await self._execute("get_project_insights", "insights", self._request, "GET", f"/insights/{project_slug}/workflows", params={"branch": branch, "all-branches": "false"})

    async def get_workflow_insights(self, project_slug: str, workflow_name: str, branch: str = "main") -> Dict[str, Any]:
        return await self._execute("get_workflow_insights", "insights", self._request, "GET", f"/insights/{project_slug}/workflows/{workflow_name}", params={"branch": branch})

    async def get_workflow_summary(self, project_slug: str, workflow_name: str) -> Dict[str, Any]:
        return await self._execute("get_workflow_summary", "insights", self._request, "GET", f"/insights/{project_slug}/workflows/{workflow_name}/summary")
