"""Grafana HTTP API connector.

Connects to a running Grafana instance via its HTTP API and provides:
  - Dashboard discovery   (GET /api/search, /api/dashboards/uid/:uid)
  - Folder management     (GET /api/folders)
  - Datasource tracking   (GET /api/datasources)
  - Annotations           (GET /api/annotations)
  - Alert rules           (GET /api/alerts, /api/ruler)
  - Health / Org          (GET /api/health, /api/org)

Follows BaseConnector pattern with graceful degradation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

_GRAFANA_DEFAULT_URL = "http://localhost:3000"
_GRAFANA_TIMEOUT = 30.0


class GrafanaConnector:
    """Grafana HTTP API connector — real dashboards from a running Grafana.

    Wraps key Grafana HTTP API endpoints:
      GET /api/search                    — search dashboards
      GET /api/dashboards/uid/:uid       — get dashboard by UID
      GET /api/folders                   — list folders
      GET /api/datasources               — list datasources
      GET /api/datasources/:id           — get datasource
      GET /api/datasources/name/:name    — get datasource by name
      GET /api/annotations               — list annotations
      GET /api/alerts                    — list alert rules
      GET /api/ruler/grafana/api/v1/rules — ruler rules
      GET /api/org                       — org info
      GET /api/health                    — health check
      GET /api/frontend/settings          — frontend settings
    """

    def __init__(
        self,
        base_url: str = "",
        api_token: str = "",
        timeout: float = _GRAFANA_TIMEOUT,
    ) -> None:
        self._base_url = (base_url or _GRAFANA_DEFAULT_URL).rstrip("/")
        self._api_token = api_token
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._ready = False
        self._org_name: str = ""

    async def initialize(self) -> bool:
        try:
            headers = {"Accept": "application/json"}
            if self._api_token:
                headers["Authorization"] = f"Bearer {self._api_token}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers=headers,
            )
            resp = await self._client.get("/api/health")
            if resp.is_success:
                resp.json()
                log.info("Grafana connector active at %s", self._base_url)
            else:
                log.warning("Grafana at %s returned HTTP %d", self._base_url, resp.status_code)
            # Try to get org name
            try:
                org_resp = await self._client.get("/api/org")
                if org_resp.is_success:
                    self._org_name = org_resp.json().get("name", "unknown")
            except Exception:
                pass
            self._ready = True
            return True
        except Exception as exc:
            log.debug("Grafana connector not available (%s): %s", self._base_url, exc)
            self._ready = False
            return False

    @property
    def is_ready(self) -> bool:
        return self._ready and self._client is not None

    @property
    def org_name(self) -> str:
        return self._org_name

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._ready = False

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

    async def _get_raw(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if not self._client:
            return None
        try:
            resp = await self._client.get(path, params=params)
            if resp.is_success:
                return resp.json()
            return None
        except Exception:
            return None

    async def health(self) -> Dict[str, Any]:
        """GET /api/health."""
        return await self._get("/api/health")

    async def org(self) -> Dict[str, Any]:
        """GET /api/org."""
        return await self._get("/api/org")

    async def search_dashboards(self, query: str = "", limit: int = 100) -> Dict[str, Any]:
        """GET /api/search — find dashboards."""
        params: Dict[str, Any] = {"limit": limit}
        if query:
            params["query"] = query
        return await self._get("/api/search", params=params)

    async def get_dashboard(self, uid: str) -> Dict[str, Any]:
        """GET /api/dashboards/uid/:uid."""
        return await self._get(f"/api/dashboards/uid/{uid}")

    async def list_folders(self) -> Dict[str, Any]:
        """GET /api/folders."""
        return await self._get("/api/folders")

    async def list_datasources(self) -> Dict[str, Any]:
        """GET /api/datasources."""
        return await self._get("/api/datasources")

    async def get_datasource(self, ds_id: int) -> Dict[str, Any]:
        """GET /api/datasources/:id."""
        return await self._get(f"/api/datasources/{ds_id}")

    async def get_datasource_by_name(self, name: str) -> Dict[str, Any]:
        """GET /api/datasources/name/:name."""
        return await self._get(f"/api/datasources/name/{name}")

    async def list_annotations(
        self, from_epoch: Optional[int] = None, to_epoch: Optional[int] = None,
        limit: int = 100, tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """GET /api/annotations."""
        params: Dict[str, Any] = {"limit": limit}
        if from_epoch:
            params["from"] = from_epoch
        if to_epoch:
            params["to"] = to_epoch
        if tags:
            params["tags"] = tags
        return await self._get("/api/annotations", params=params)

    async def list_alerts(self, limit: int = 100) -> Dict[str, Any]:
        """GET /api/alerts."""
        return await self._get("/api/alerts", params={"limit": limit})

    async def ruler_rules(self) -> Dict[str, Any]:
        """GET /api/ruler/grafana/api/v1/rules."""
        return await self._get("/api/ruler/grafana/api/v1/rules")

    async def frontend_settings(self) -> Dict[str, Any]:
        """GET /api/frontend/settings."""
        return await self._get("/api/frontend/settings")

    async def health_check(self) -> bool:
        try:
            result = await self._get("/api/health")
            return result.get("status") == "success"
        except Exception:
            return False


grafana_connector = GrafanaConnector()
