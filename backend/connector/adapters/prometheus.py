from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

import httpx

from backend.connector.adapter.interfaces import AdapterHealthStatus, AdapterResult, ConnectorAdapter
from backend.connector.models import Capability

log = logging.getLogger(__name__)

PROMETHEUS_URL_ENV = "PROMETHEUS_URL"
PROMETHEUS_DEFAULT_URL = "http://localhost:9090"
DEFAULT_TIMEOUT = 30


class PrometheusAdapter(ConnectorAdapter):

    @property
    def connector_type(self) -> str:
        return "prometheus"

    @property
    def connector_name(self) -> str:
        return "Prometheus"

    @property
    def adapter_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        self._base_url: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized: bool = False

    async def initialize(self) -> bool:
        self._base_url = (os.getenv(PROMETHEUS_URL_ENV, PROMETHEUS_DEFAULT_URL)).rstrip("/")
        try:
            headers = {"Accept": "application/json"}
            token = os.getenv("PROMETHEUS_TOKEN", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(DEFAULT_TIMEOUT),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers=headers,
            )
            resp = await self._client.get("/api/v1/status/buildinfo")
            if resp.is_success:
                data = resp.json()
                version = data.get("data", {}).get("version", "unknown")
                log.info("Prometheus adapter initialized — version %s at %s", version, self._base_url)
            else:
                log.warning("Prometheus at %s returned HTTP %d", self._base_url, resp.status_code)
            self._initialized = True
            return True
        except Exception as exc:
            log.debug("Prometheus adapter not available (%s): %s", self._base_url, exc)
            return False

    async def health_check(self) -> AdapterHealthStatus:
        if not self._initialized or not self._client:
            return AdapterHealthStatus.UNHEALTHY
        try:
            resp = await self._client.get("/api/v1/status/buildinfo")
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
            return await self._query(inputs, start)
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
        log.info("Prometheus adapter shut down")

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not self._client:
            return {"status": "error", "error": "adapter not initialized"}
        try:
            resp = await self._client.get(path, params=params)
            if not resp.is_success:
                return {"status": "error", "error": f"HTTP {resp.status_code}"}
            data = resp.json()
            if data.get("status") == "error":
                return {"status": "error", "error": data.get("error", "unknown")}
            return data
        except httpx.TimeoutException:
            return {"status": "error", "error": "timeout"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def _query(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        promql = inputs.get("query", inputs.get("promql", ""))
        if not promql:
            return AdapterResult(success=False, error="Missing 'query'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            data = await self._get("/api/v1/query", params={"query": promql})
            if data.get("status") == "error":
                return AdapterResult(success=False, error=data.get("error", "query failed"), duration_ms=(time.monotonic() - start) * 1000)
            result = data.get("data", {})
            return AdapterResult(success=True, outputs={"result_type": result.get("resultType", ""), "results": result.get("result", [])}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _search(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        try:
            data = await self._get("/api/v1/labels")
            if data.get("status") == "error":
                return AdapterResult(success=False, error=data.get("error", "labels query failed"), duration_ms=(time.monotonic() - start) * 1000)
            labels = data.get("data", [])
            return AdapterResult(success=True, outputs={"labels": labels, "label_count": len(labels)}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)
