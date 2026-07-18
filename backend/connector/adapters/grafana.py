from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

import httpx

from backend.connector.adapter.interfaces import AdapterHealthStatus, AdapterResult, ConnectorAdapter
from backend.connector.models import Capability

log = logging.getLogger(__name__)

GRAFANA_URL_ENV = "GRAFANA_URL"
GRAFANA_TOKEN_ENV = "GRAFANA_API_TOKEN"
GRAFANA_DEFAULT_URL = "http://localhost:3000"
DEFAULT_TIMEOUT = 30


class GrafanaAdapter(ConnectorAdapter):

    @property
    def connector_type(self) -> str:
        return "grafana"

    @property
    def connector_name(self) -> str:
        return "Grafana"

    @property
    def adapter_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        self._base_url: str = ""
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized: bool = False
        self._org_name: str = ""

    async def initialize(self) -> bool:
        self._base_url = (os.getenv(GRAFANA_URL_ENV, GRAFANA_DEFAULT_URL)).rstrip("/")
        self._token = os.getenv(GRAFANA_TOKEN_ENV, "")
        try:
            headers = {"Accept": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(DEFAULT_TIMEOUT),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers=headers,
            )
            resp = await self._client.get("/api/health")
            if resp.is_success:
                log.info("Grafana adapter initialized at %s", self._base_url)
            else:
                log.warning("Grafana at %s returned HTTP %d", self._base_url, resp.status_code)
            try:
                org_resp = await self._client.get("/api/org")
                if org_resp.is_success:
                    self._org_name = org_resp.json().get("name", "unknown")
            except Exception:
                pass
            self._initialized = True
            return True
        except Exception as exc:
            log.debug("Grafana adapter not available (%s): %s", self._base_url, exc)
            return False

    async def health_check(self) -> AdapterHealthStatus:
        if not self._initialized or not self._client:
            return AdapterHealthStatus.UNHEALTHY
        try:
            resp = await self._client.get("/api/health")
            if resp.is_success:
                return AdapterHealthStatus.HEALTHY
            return AdapterHealthStatus.DEGRADED
        except httpx.RequestError:
            return AdapterHealthStatus.UNHEALTHY

    async def capabilities(self) -> list[Capability]:
        return [
            Capability.OBSERVE,
            Capability.SEARCH,
        ]

    async def execute(self, capability: Capability, inputs: dict[str, Any],
                      timeout_seconds: Optional[int] = None) -> AdapterResult:
        start = time.monotonic()

        if capability == Capability.OBSERVE:
            return await self._observe(inputs, start)
        if capability == Capability.SEARCH:
            return await self._search(inputs, start)

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
        log.info("Grafana adapter shut down")

    async def metadata(self) -> dict[str, Any]:
        base = await super().metadata()
        base["org_name"] = self._org_name
        base["base_url"] = self._base_url
        return base

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not self._client:
            return {"status": "error", "error": "adapter not initialized"}
        try:
            resp = await self._client.get(path, params=params)
            if not resp.is_success:
                return {"status": "error", "error": f"HTTP {resp.status_code}"}
            return {"status": "success", "data": resp.json()}
        except httpx.TimeoutException:
            return {"status": "error", "error": "timeout"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def _observe(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        try:
            health = await self._get("/api/health")
            org = await self._get("/api/org")
            datasources = await self._get("/api/datasources")
            dashboards = await self._get("/api/search", params={"limit": inputs.get("limit", 20)})
            return AdapterResult(success=True, outputs={
                "health": health.get("data", health),
                "org": org.get("data", org),
                "datasources": datasources.get("data", []),
                "dashboards": dashboards.get("data", []),
            }, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _search(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        query = inputs.get("query", "")
        limit = inputs.get("limit", 50)
        try:
            params: dict[str, Any] = {"limit": limit}
            if query:
                params["query"] = query
            data = await self._get("/api/search", params=params)
            results = data.get("data", [])
            if isinstance(results, list):
                items = [{"uid": r.get("uid", ""), "title": r.get("title", ""), "type": r.get("type", ""), "url": r.get("url", "")} for r in results]
            else:
                items = []
            return AdapterResult(success=True, outputs={"dashboards": items, "total": len(items)}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)
