"""ArgoCD HTTP API connector.

Connects to a running ArgoCD instance via its HTTP API and provides:
  - Applications         (GET /api/v1/applications)
  - Projects             (GET /api/v1/projects)
  - Repositories         (GET /api/v1/repositories)
  - Clusters             (GET /api/v1/clusters)
  - Sync                 (POST /api/v1/applications/{name}/sync)
  - Refresh              (POST /api/v1/applications/{name}/refresh)
  - Rollback             (POST /api/v1/applications/{name}/rollback)
  - History              (GET /api/v1/applications/{name}/revisions)
  - Resources            (GET /api/v1/applications/{name}/resource-tree)

Follows BaseConnector pattern with graceful degradation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

_ARGOCD_DEFAULT_URL = "http://localhost:8080"
_ARGOCD_TIMEOUT = 30.0


class ArgoCDConnector(BaseConnector):
    """ArgoCD HTTP API connector — real GitOps from a running ArgoCD.

    Wraps the ArgoCD v1 HTTP API:
      GET    /api/v1/applications              — list applications
      GET    /api/v1/applications/{name}       — get application
      POST   /api/v1/applications/{name}/sync  — sync application
      POST   /api/v1/applications/{name}/rollback — rollback
      GET    /api/v1/applications/{name}/revisions/{id}/metadata — revision metadata
      GET    /api/v1/applications/{name}/resource-tree — resource tree
      GET    /api/v1/applications/{name}/events — events
      GET    /api/v1/projects                  — list projects
      GET    /api/v1/repositories              — list repos
      GET    /api/v1/clusters                  — list clusters
      POST   /api/v1/session                   — authenticate
    """

    connector_name = "ArgoCD"
    connector_type = "argocd"

    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        timeout: float = _ARGOCD_TIMEOUT,
    ) -> None:
        self._base_url = (base_url or _ARGOCD_DEFAULT_URL).rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._ready = False

    async def initialize(self) -> bool:
        try:
            headers = {"Accept": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers=headers,
            )
            resp = await self._client.get("/api/v1/applications", params={"limit": 1})
            if resp.is_success:
                log.info("ArgoCD connector active at %s", self._base_url)
            else:
                log.warning("ArgoCD at %s returned HTTP %d", self._base_url, resp.status_code)
            self._ready = True
            return True
        except Exception as exc:
            log.debug("ArgoCD connector not available (%s): %s", self._base_url, exc)
            self._ready = False
            return False

    @property
    def is_ready(self) -> bool:
        return self._ready and self._client is not None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._ready = False

    async def shutdown(self) -> bool:
        await self.close()
        return True

    async def health(self) -> Dict[str, Any]:
        reachable = await self.health_check()
        return {"connector": self.connector_type, "ready": self.is_ready, "reachable": reachable}

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "error": "connector not initialized"}
        try:
            resp = await self._client.get(path, params=params)
            if not resp.is_success:
                return {"status": "error", "error": f"HTTP {resp.status_code}", "body": resp.text}
            return {"status": "success", "data": resp.json()}
        except httpx.TimeoutException:
            return {"status": "error", "error": "timeout"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def _post(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "error": "connector not initialized"}
        try:
            resp = await self._client.post(path, json=json_body or {})
            if not resp.is_success:
                return {"status": "error", "error": f"HTTP {resp.status_code}", "body": resp.text}
            return {"status": "success", "data": resp.json()}
        except httpx.TimeoutException:
            return {"status": "error", "error": "timeout"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def list_applications(self, limit: int = 100) -> Dict[str, Any]:
        return await self._get("/api/v1/applications", params={"limit": limit})

    async def get_application(self, name: str) -> Dict[str, Any]:
        return await self._get(f"/api/v1/applications/{name}")

    async def sync_application(self, name: str, revision: str = "", prune: bool = True) -> Dict[str, Any]:
        body: Dict[str, Any] = {"prune": prune}
        if revision:
            body["revision"] = revision
        return await self._post(f"/api/v1/applications/{name}/sync", json_body=body)

    async def refresh_application(self, name: str) -> Dict[str, Any]:
        return await self._post(f"/api/v1/applications/{name}/refresh")

    async def rollback_application(self, name: str, revision_id: int) -> Dict[str, Any]:
        return await self._post(f"/api/v1/applications/{name}/rollback", json_body={"id": revision_id})

    async def get_application_resource_tree(self, name: str) -> Dict[str, Any]:
        return await self._get(f"/api/v1/applications/{name}/resource-tree")

    async def get_application_revisions(self, name: str) -> Dict[str, Any]:
        return await self._get(f"/api/v1/applications/{name}/revisions")

    async def get_revision_metadata(self, name: str, revision_id: str) -> Dict[str, Any]:
        return await self._get(f"/api/v1/applications/{name}/revisions/{revision_id}/metadata")

    async def list_projects(self) -> Dict[str, Any]:
        return await self._get("/api/v1/projects")

    async def list_repositories(self) -> Dict[str, Any]:
        return await self._get("/api/v1/repositories")

    async def list_clusters(self) -> Dict[str, Any]:
        return await self._get("/api/v1/clusters")

    async def get_application_events(self, name: str) -> Dict[str, Any]:
        return await self._get(f"/api/v1/applications/{name}/events")

    async def health_check(self) -> bool:
        try:
            result = await self._get("/api/v1/applications", params={"limit": 1})
            return result.get("status") == "success"
        except Exception:
            return False


argocd_connector = ArgoCDConnector()
