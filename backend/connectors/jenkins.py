from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

JENKINS_URL_ENV = "JENKINS_URL"
JENKINS_USER_ENV = "JENKINS_USER"
JENKINS_PASS_ENV = "JENKINS_PASS"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0
RETRYABLE_STATUSES = {429, 502, 503, 504}


class JenkinsConnector(BaseConnector):
    connector_name = "Jenkins"
    connector_type = "jenkins"

    def __init__(self) -> None:
        self._url: str = ""
        self._user: str = ""
        self._pass: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._url = credentials.get("url", self._url)
        self._user = credentials.get("user", self._user)
        self._pass = credentials.get("pass", self._pass)

    async def initialize(self) -> bool:
        self._url = self._url or os.getenv(JENKINS_URL_ENV, "")
        self._user = self._user or os.getenv(JENKINS_USER_ENV, "")
        self._pass = self._pass or os.getenv(JENKINS_PASS_ENV, "")
        if not self._url or not self._pass:
            log.warning("JENKINS_URL or JENKINS_PASS not set — Jenkins connector in degraded mode")
            self._available = False
            return False

        self._url = self._url.rstrip("/")
        encoded = base64.b64encode(f"{self._user}:{self._pass}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=self._url,
            headers={
                "Authorization": f"Basic {encoded}",
                "Accept": "application/json",
                "User-Agent": "CortexPrime-JenkinsConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        try:
            resp = await self._client.get("/api/json?tree=nodeName")
            if resp.status_code == 200:
                self._available = True
                log.info("Jenkins connector initialized — connected to %s", self._url)
                return True
            else:
                log.warning("Jenkins auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("Jenkins API unreachable: %s", e)
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
            "authenticated": bool(self._user) and bool(self._pass),
        }

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self._client:
            raise RuntimeError("Jenkins connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 401:
                    raise PermissionError("Jenkins API: 401 Unauthorized")
                if resp.status_code == 403:
                    raise PermissionError("Jenkins API: 403 Forbidden")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Jenkins API: 404 Not Found — {path}")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"Jenkins API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    return resp.json()
                return resp.text
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Jenkins request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"Jenkins request failed after {MAX_RETRIES} retries: {last_error}")

    # ---- Jobs ----

    async def list_jobs(self, folder: str = "") -> List[Dict[str, Any]]:
        base = f"/job/{folder}" if folder else ""
        data = await self._execute("list_jobs", "jobs", self._request, "GET", f"{base}/api/json?tree=jobs[name,url,color,_class,description]")
        if isinstance(data, dict):
            return data.get("jobs", [])
        return []

    async def get_job(self, job_name: str) -> Dict[str, Any]:
        return await self._execute("get_job", "jobs", self._request, "GET", f"/job/{job_name}/api/json?tree=displayName,description,url,buildable,inQueue,nextBuildNumber,healthReport,jobs[name]")

    async def get_job_config(self, job_name: str) -> str:
        return await self._execute("get_job_config", "jobs", self._request, "GET", f"/job/{job_name}/config.xml")

    # ---- Builds ----

    async def list_builds(self, job_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        data = await self._execute("list_builds", "builds", self._request, "GET", f"/job/{job_name}/api/json?tree=builds[number,url,result,timestamp,duration,displayName,estimatedDuration,builtOn]&depth=1")
        if isinstance(data, dict):
            return data.get("builds", [])[:limit]
        return []

    async def get_build(self, job_name: str, build_number: int) -> Dict[str, Any]:
        return await self._execute("get_build", "builds", self._request, "GET", f"/job/{job_name}/{build_number}/api/json?tree=number,url,result,timestamp,duration,displayName,estimatedDuration,builtOn,description,id,fullDisplayName,changeSet,artifacts")

    async def get_build_log(self, job_name: str, build_number: int, start: int = 0) -> str:
        return await self._execute("get_build_log", "builds", self._request, "GET", f"/job/{job_name}/{build_number}/logText/progressiveText?start={start}")

    async def get_build_stages(self, job_name: str, build_number: int) -> List[Dict[str, Any]]:
        try:
            data = await self._request("GET", f"/job/{job_name}/{build_number}/wfapi/describe")
            if isinstance(data, dict):
                stages = data.get("stages", [])
                return [{
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "status": s.get("status"),
                    "durationMillis": s.get("durationMillis"),
                    "startTimeMillis": s.get("startTimeMillis"),
                    "pauseDurationMillis": s.get("pauseDurationMillis"),
                } for s in stages]
        except Exception:
            pass
        return []

    async def build_job(self, job_name: str, parameters: Optional[Dict[str, str]] = None) -> int:
        if parameters:
            await self._execute("build_job", "builds", self._request, "POST", f"/job/{job_name}/buildWithParameters", params=parameters)
        else:
            await self._execute("build_job", "builds", self._request, "POST", f"/job/{job_name}/build")
        queue_item = await self._request("GET", f"/job/{job_name}/api/json?tree=nextBuildNumber")
        if isinstance(queue_item, dict):
            return queue_item.get("nextBuildNumber", 0) - 1
        return 0

    async def stop_build(self, job_name: str, build_number: int) -> bool:
        try:
            await self._execute("stop_build", "builds", self._request, "POST", f"/job/{job_name}/{build_number}/stop")
            return True
        except Exception:
            return False

    # ---- Queue ----

    async def get_queue(self) -> List[Dict[str, Any]]:
        data = await self._execute("get_queue", "queue", self._request, "GET", "/queue/api/json?tree=items[id,url,task[name,url],why,params,blocked,buildable,stuck,inQueueSince,timestamp]")
        if isinstance(data, dict):
            return data.get("items", [])
        return []

    async def cancel_queue_item(self, item_id: int) -> bool:
        try:
            await self._execute("cancel_queue_item", "queue", self._request, "POST", f"/queue/cancelItem?id={item_id}")
            return True
        except Exception:
            return False

    # ---- Agents ----

    async def list_agents(self) -> List[Dict[str, Any]]:
        data = await self._execute("list_agents", "agents", self._request, "GET", "/computer/api/json?tree=computer[displayName,offline,idle,numExecutors,temporarilyOffline,monitorData]")
        if isinstance(data, dict):
            return data.get("computer", [])
        return []

    # ---- Folders ----

    async def list_folders(self) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/api/json?tree=jobs[name,url,_class]")
        if isinstance(data, dict):
            return [j for j in data.get("jobs", []) if "Folder" in j.get("_class", "")]
        return []

    # ---- Pipelines (Blue Ocean / Pipeline Plugin) ----

    async def list_pipelines(self) -> List[Dict[str, Any]]:
        jobs = await self.list_jobs()
        pipelines = []
        for job in jobs:
            try:
                desc = await self._request("GET", f"/job/{job['name']}/api/json?tree=displayName,description,_class,color,buildable")
                if isinstance(desc, dict):
                    pipelines.append(desc)
            except Exception:
                pipelines.append(job)
        return pipelines

    # ---- Health ----

    async def get_health(self) -> Dict[str, Any]:
        try:
            data = await self._request("GET", "/overallLoad/api/json")
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"status": "unknown"}
