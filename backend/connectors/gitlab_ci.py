from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

GITLAB_API_BASE = "https://gitlab.com/api/v4"
GITLAB_URL_ENV = "GITLAB_URL"
GITLAB_TOKEN_ENV = "GITLAB_TOKEN"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0
RETRYABLE_STATUSES = {429, 502, 503, 504}


class GitLabCIConnector(BaseConnector):
    connector_name = "GitLab CI"
    connector_type = "gitlab_ci"

    def __init__(self) -> None:
        self._url: str = ""
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._url = credentials.get("url", self._url)
        self._token = credentials.get("token", self._token)

    async def initialize(self) -> bool:
        self._url = (self._url or os.getenv(GITLAB_URL_ENV, "")).rstrip("/") or GITLAB_API_BASE
        self._token = self._token or os.getenv(GITLAB_TOKEN_ENV, "")
        if not self._token:
            log.warning("GITLAB_TOKEN not set — GitLab CI connector in degraded mode")
            self._available = False
            return False

        self._client = httpx.AsyncClient(
            base_url=self._url,
            headers={
                "PRIVATE-TOKEN": self._token,
                "Accept": "application/json",
                "User-Agent": "CortexPrime-GitLabCIConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        try:
            resp = await self._client.get("/version")
            if resp.status_code == 200:
                self._available = True
                log.info("GitLab CI connector initialized — %s", resp.json().get("version", ""))
                return True
            else:
                log.warning("GitLab CI auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("GitLab CI API unreachable: %s", e)
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
            "url": self._url,
            "authenticated": bool(self._token),
        }

    async def check_credential(self) -> Dict[str, Any]:
        """GET /personal_access_tokens/self — real token introspection,
        including expires_at (null for non-expiring tokens). This is the
        one provider of the three with a genuine expiry-lookup endpoint,
        unlike GitHub (advisory header only) or Jira (no capability)."""
        try:
            token_info = await self._execute("check_credential", "tokens", self._request, "GET", "/personal_access_tokens/self")
            return {
                "valid": True,
                "expires_at": token_info.get("expires_at") if isinstance(token_info, dict) else None,
                "expires_at_source": "api",
                "error": None,
            }
        except PermissionError as exc:
            return {"valid": False, "expires_at": None, "expires_at_source": None, "error": str(exc)}

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self._client:
            raise RuntimeError("GitLab CI connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 401:
                    raise PermissionError("GitLab CI: 401 Unauthorized")
                if resp.status_code == 403:
                    raise PermissionError("GitLab CI: 403 Forbidden")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"GitLab CI: 404 Not Found — {path}")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"GitLab CI: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"GitLab CI request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"GitLab CI request failed after {MAX_RETRIES} retries: {last_error}")

    async def _request_list(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("data", "items", "results"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []

    # ---- Projects ----

    async def list_projects(self, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, "membership": "true", **kwargs}
        return await self._execute("list_projects", "projects", self._request_list, "GET", "/projects", params=params)

    async def get_project(self, project_id: int) -> Dict[str, Any]:
        return await self._execute("get_project", "projects", self._request, "GET", f"/projects/{project_id}")

    # ---- Pipelines ----

    async def list_pipelines(self, project_id: int, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs}
        return await self._execute("list_pipelines", "pipelines", self._request_list, "GET", f"/projects/{project_id}/pipelines", params=params)

    async def get_pipeline(self, project_id: int, pipeline_id: int) -> Dict[str, Any]:
        return await self._execute("get_pipeline", "pipelines", self._request, "GET", f"/projects/{project_id}/pipelines/{pipeline_id}")

    async def create_pipeline(self, project_id: int, ref: str, variables: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        json_data: Dict[str, Any] = {"ref": ref}
        if variables:
            json_data["variables"] = [{"key": k, "value": v} for k, v in variables.items()]
        return await self._execute("create_pipeline", "pipelines", self._request, "POST", f"/projects/{project_id}/pipeline", json=json_data)

    async def retry_pipeline(self, project_id: int, pipeline_id: int) -> Dict[str, Any]:
        return await self._execute("retry_pipeline", "pipelines", self._request, "POST", f"/projects/{project_id}/pipelines/{pipeline_id}/retry")

    async def cancel_pipeline(self, project_id: int, pipeline_id: int) -> Dict[str, Any]:
        return await self._execute("cancel_pipeline", "pipelines", self._request, "POST", f"/projects/{project_id}/pipelines/{pipeline_id}/cancel")

    # ---- Deployments ----

    async def list_deployments(self, project_id: int, environment: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, "order_by": "finished_at", "sort": "desc", **kwargs}
        if environment:
            params["environment"] = environment
        return await self._execute("list_deployments", "deployments", self._request_list, "GET", f"/projects/{project_id}/deployments", params=params)

    async def get_last_successful_deployment(self, project_id: int, environment: str, before_deployment_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Most recent successful deployment for an environment, excluding
        before_deployment_id itself. Used to find the rollback target when a
        regression is confirmed."""
        deployments = await self.list_deployments(project_id, environment=environment, status="success")
        for deployment in deployments:
            if before_deployment_id is not None and deployment.get("id") == before_deployment_id:
                continue
            return deployment
        return None

    # ---- Jobs ----

    async def list_jobs(self, project_id: int, pipeline_id: int, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs}
        return await self._execute("list_jobs", "jobs", self._request_list, "GET", f"/projects/{project_id}/pipelines/{pipeline_id}/jobs", params=params)

    async def get_job(self, project_id: int, job_id: int) -> Dict[str, Any]:
        return await self._execute("get_job", "jobs", self._request, "GET", f"/projects/{project_id}/jobs/{job_id}")

    async def get_job_log(self, project_id: int, job_id: int) -> str:
        result = await self._execute("get_job_log", "jobs", self._request, "GET", f"/projects/{project_id}/jobs/{job_id}/trace")
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return result.get("trace", str(result))
        return str(result)

    async def retry_job(self, project_id: int, job_id: int) -> Dict[str, Any]:
        return await self._execute("retry_job", "jobs", self._request, "POST", f"/projects/{project_id}/jobs/{job_id}/retry")

    async def cancel_job(self, project_id: int, job_id: int) -> Dict[str, Any]:
        return await self._execute("cancel_job", "jobs", self._request, "POST", f"/projects/{project_id}/jobs/{job_id}/cancel")

    async def play_job(self, project_id: int, job_id: int) -> Dict[str, Any]:
        return await self._execute("play_job", "jobs", self._request, "POST", f"/projects/{project_id}/jobs/{job_id}/play")

    # ---- Artifacts ----

    async def list_job_artifacts(self, project_id: int, job_id: int) -> List[Dict[str, Any]]:
        job = await self.get_job(project_id, job_id)
        if isinstance(job, dict):
            artifacts = job.get("artifacts", [])
            return [{
                "file_name": a.get("filename", a.get("file_name", "")),
                "file_size": a.get("size", a.get("file_size", 0)),
                "file_type": a.get("file_type", ""),
                "url": f"/projects/{project_id}/jobs/{job_id}/artifacts/{a.get('filename', a.get('file_name', ''))}",
            } for a in (artifacts or [])]
        return []

    async def download_artifact(self, project_id: int, job_id: int, artifact_path: str) -> bytes:
        result = await self._request("GET", f"/projects/{project_id}/jobs/{job_id}/artifacts/{artifact_path}")
        if isinstance(result, bytes):
            return result
        if isinstance(result, str):
            return result.encode()
        return str(result).encode()

    # ---- Runners ----

    async def list_runners(self, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs}
        return await self._execute("list_runners", "runners", self._request_list, "GET", "/runners", params=params)

    async def get_runner(self, runner_id: int) -> Dict[str, Any]:
        return await self._execute("get_runner", "runners", self._request, "GET", f"/runners/{runner_id}")

    async def enable_project_runner(self, project_id: int, runner_id: int) -> Dict[str, Any]:
        return await self._execute("enable_project_runner", "runners", self._request, "POST", f"/projects/{project_id}/runners", json={"runner_id": runner_id})

    # ---- Repository (commits/diffs) ----

    async def get_commit(self, project_id: str, sha: str) -> Dict[str, Any]:
        """Raw GitLab commit metadata. project_id accepts either a numeric ID
        or a URL-encoded path_with_namespace (GitLab's API treats both as
        valid :id values)."""
        return await self._execute("get_commit", "repository", self._request, "GET", f"/projects/{project_id}/repository/commits/{sha}")

    async def get_commit_diff(self, project_id: str, sha: str) -> List[Dict[str, Any]]:
        """Raw GitLab per-file diff list for a commit."""
        return await self._execute("get_commit_diff", "repository", self._request_list, "GET", f"/projects/{project_id}/repository/commits/{sha}/diff")

    async def get_commit_with_diff(self, project_id: str, sha: str) -> Dict[str, Any]:
        """Commit message + diff, normalized into the same shape
        enterprise_deploy_root_cause_reasoner._build_diff_summary already
        expects from GitHub (commit.commit.message / commit.files[].{filename,status,patch}),
        so that function stays provider-agnostic instead of forking per source.
        """
        commit = await self.get_commit(project_id, sha)
        diff = await self.get_commit_diff(project_id, sha)

        def _status(f: Dict[str, Any]) -> str:
            if f.get("new_file"):
                return "added"
            if f.get("deleted_file"):
                return "removed"
            if f.get("renamed_file"):
                return "renamed"
            return "modified"

        return {
            "commit": {"message": commit.get("message", "")},
            "files": [
                {
                    "filename": f.get("new_path") or f.get("old_path") or "unknown",
                    "status": _status(f),
                    "patch": f.get("diff", ""),
                }
                for f in diff
            ],
        }

    # ---- Merge Request Pipelines ----

    async def list_merge_request_pipelines(self, project_id: int, mr_iid: int) -> List[Dict[str, Any]]:
        return await self._execute("list_merge_request_pipelines", "pipelines", self._request_list, "GET", f"/projects/{project_id}/merge_requests/{mr_iid}/pipelines")

    # ---- Variables ----

    async def list_variables(self, project_id: int, **kwargs) -> List[Dict[str, Any]]:
        params = {"per_page": 100, **kwargs}
        return await self._execute("list_variables", "variables", self._request_list, "GET", f"/projects/{project_id}/variables", params=params)

    async def create_variable(self, project_id: int, key: str, value: str, masked: bool = False, protected: bool = False) -> Dict[str, Any]:
        return await self._execute("create_variable", "variables", self._request, "POST", f"/projects/{project_id}/variables", json={"key": key, "value": value, "masked": masked, "protected": protected})

    async def update_variable(self, project_id: int, key: str, value: str) -> Dict[str, Any]:
        return await self._execute("update_variable", "variables", self._request, "PUT", f"/projects/{project_id}/variables/{key}", json={"value": value})

    # ---- Stages ----

    async def get_pipeline_stages(self, project_id: int, pipeline_id: int) -> List[str]:
        jobs = await self.list_jobs(project_id, pipeline_id)
        stages: List[str] = []
        seen: set = set()
        for job in jobs:
            stage = job.get("stage", "")
            if stage and stage not in seen:
                stages.append(stage)
                seen.add(stage)
        return stages
