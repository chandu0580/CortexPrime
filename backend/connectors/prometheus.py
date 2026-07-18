"""Prometheus HTTP API connector.

Connects to a running Prometheus server via its HTTP API and provides:
  - Instant queries   (/api/v1/query)
  - Range queries     (/api/v1/query_range)
  - Label discovery   (/api/v1/labels)
  - Series discovery  (/api/v1/series)
  - Targets           (/api/v1/targets)
  - Rules             (/api/v1/rules)
  - Alerts            (/api/v1/alerts)

Follows BaseConnector pattern with graceful degradation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

_PROM_DEFAULT_URL = "http://localhost:9090"
_PROM_TIMEOUT = 30.0


class PrometheusConnector:
    """Prometheus HTTP API connector — real metrics from a running Prometheus.

    Wraps the standard Prometheus HTTP API:
      GET /api/v1/query?query=<promql>
      GET /api/v1/query_range?query=<promql>&start=<>&end=<>&step=<>
      GET /api/v1/labels
      GET /api/v1/<label>/values
      GET /api/v1/series?match[]=<>
      GET /api/v1/targets
      GET /api/v1/rules
      GET /api/v1/alerts
    """

    def __init__(self, base_url: str = "", timeout: float = _PROM_TIMEOUT) -> None:
        self._base_url = (base_url or _PROM_DEFAULT_URL).rstrip("/")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._ready = False

    async def initialize(self) -> bool:
        try:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
            resp = await self._client.get("/api/v1/status/buildinfo")
            if resp.is_success:
                data = resp.json()
                version = data.get("data", {}).get("version", "unknown")
                log.info("Prometheus connector active — version %s at %s", version, self._base_url)
            else:
                log.warning("Prometheus at %s returned HTTP %d", self._base_url, resp.status_code)
            self._ready = True
            return True
        except Exception as exc:
            log.debug("Prometheus connector not available (%s): %s", self._base_url, exc)
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

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "error": "connector not initialized"}
        try:
            resp = await self._client.get(path, params=params)
            if not resp.is_success:
                return {"status": "error", "error": f"HTTP {resp.status_code}", "body": resp.text}
            data = resp.json()
            if data.get("status") == "error":
                return {"status": "error", "error": data.get("error", "unknown")}
            return data
        except httpx.TimeoutException:
            return {"status": "error", "error": "timeout"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def query(self, query: str, time: Optional[str] = None) -> Dict[str, Any]:
        """Instant query — GET /api/v1/query?query=<promql>."""
        params: Dict[str, Any] = {"query": query}
        if time:
            params["time"] = time
        return await self._get("/api/v1/query", params=params)

    async def query_range(
        self, query: str, start: str, end: str, step: str = "15s",
    ) -> Dict[str, Any]:
        """Range query — GET /api/v1/query_range."""
        params = {"query": query, "start": start, "end": end, "step": step}
        return await self._get("/api/v1/query_range", params=params)

    async def labels(self) -> Dict[str, Any]:
        """List label names — GET /api/v1/labels."""
        return await self._get("/api/v1/labels")

    async def label_values(self, label: str) -> Dict[str, Any]:
        """List values for a label — GET /api/v1/{label}/values."""
        return await self._get(f"/api/v1/label/{label}/values")

    async def series(self, match: List[str]) -> Dict[str, Any]:
        """Find series by matcher — GET /api/v1/series."""
        params = {"match[]": match}
        return await self._get("/api/v1/series", params=params)

    async def targets(self) -> Dict[str, Any]:
        """List scrape targets — GET /api/v1/targets."""
        return await self._get("/api/v1/targets")

    async def rules(self) -> Dict[str, Any]:
        """List recording & alert rules — GET /api/v1/rules."""
        return await self._get("/api/v1/rules")

    async def alerts(self) -> Dict[str, Any]:
        """List active alerts — GET /api/v1/alerts."""
        return await self._get("/api/v1/alerts")

    async def health_check(self) -> bool:
        """Check if Prometheus is reachable."""
        try:
            resp = await self._get("/api/v1/status/buildinfo")
            return resp.get("status") == "success"
        except Exception:
            return False
