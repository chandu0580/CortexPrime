"""Loki HTTP API connector.

Connects to a running Grafana Loki server via its HTTP API and provides:
  - Instant queries       (GET /loki/api/v1/query)
  - Range queries         (GET /loki/api/v1/query_range)
  - Label discovery       (GET /loki/api/v1/labels)
  - Label values          (GET /loki/api/v1/label/{name}/values)
  - Series discovery      (GET /loki/api/v1/series)
  - Tail / live streaming (via query_range with tail param)

Follows BaseConnector pattern with graceful degradation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

_LOKI_DEFAULT_URL = "http://localhost:3100"
_LOKI_TIMEOUT = 30.0


class LokiConnector(BaseConnector):
    """Loki HTTP API connector — real logs from a running Loki.

    Wraps the standard Loki HTTP API:
      GET /loki/api/v1/query?query=<logql>
      GET /loki/api/v1/query_range?query=<logql>&start=<>&end=<>&step=<>
      GET /loki/api/v1/labels
      GET /loki/api/v1/label/<name>/values
      GET /loki/api/v1/series?match[]=<>
    """

    connector_name = "Loki"
    connector_type = "loki"

    def __init__(self, base_url: str = "", timeout: float = _LOKI_TIMEOUT) -> None:
        self._base_url = (base_url or _LOKI_DEFAULT_URL).rstrip("/")
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
            resp = await self._client.get("/loki/api/v1/labels")
            if resp.is_success:
                resp.json()
                log.info("Loki connector active at %s", self._base_url)
            else:
                log.warning("Loki at %s returned HTTP %d", self._base_url, resp.status_code)
            self._ready = True
            return True
        except Exception as exc:
            log.debug("Loki connector not available (%s): %s", self._base_url, exc)
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
            return resp.json()
        except httpx.TimeoutException:
            return {"status": "error", "error": "timeout"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def _post(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "error": "connector not initialized"}
        try:
            resp = await self._client.post(path, params=params)
            if not resp.is_success:
                return {"status": "error", "error": f"HTTP {resp.status_code}", "body": resp.text}
            return resp.json()
        except httpx.TimeoutException:
            return {"status": "error", "error": "timeout"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def query(self, query: str, time: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Instant query — GET /loki/api/v1/query?query=<logql>."""
        params: Dict[str, Any] = {"query": query, "limit": limit}
        if time:
            params["time"] = time
        return await self._get("/loki/api/v1/query", params=params)

    async def query_range(
        self, query: str, start: str, end: str, step: str = "1m", limit: int = 1000,
    ) -> Dict[str, Any]:
        """Range query — GET /loki/api/v1/query_range."""
        params = {"query": query, "start": start, "end": end, "step": step, "limit": limit}
        return await self._get("/loki/api/v1/query_range", params=params)

    async def labels(self) -> Dict[str, Any]:
        """List label names — GET /loki/api/v1/labels."""
        return await self._get("/loki/api/v1/labels")

    async def label_values(self, label: str) -> Dict[str, Any]:
        """List values for a label — GET /loki/api/v1/label/{name}/values."""
        return await self._get(f"/loki/api/v1/label/{label}/values")

    async def series(self, match: List[str]) -> Dict[str, Any]:
        """Find log streams by matcher — GET /loki/api/v1/series."""
        params = {"match[]": match}
        return await self._get("/loki/api/v1/series", params=params)

    async def tail(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Simulate tail by querying recent logs — uses query_range with short window."""
        import time
        now_ns = time.time_ns()
        one_min_ago_ns = now_ns - 60_000_000_000
        return await self.query_range(query, str(one_min_ago_ns), str(now_ns), step="1s", limit=limit)

    async def health_check(self) -> bool:
        """Check if Loki is reachable."""
        try:
            resp = await self._get("/loki/api/v1/labels")
            return resp.get("status") == "success"
        except Exception:
            return False


loki_connector = LokiConnector()
