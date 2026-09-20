from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector
from backend.connectors.effects import guard_raw_request

log = logging.getLogger(__name__)

SERVICENOW_INSTANCE_ENV = "SERVICENOW_INSTANCE"
SERVICENOW_USERNAME_ENV = "SERVICENOW_USERNAME"
SERVICENOW_PASSWORD_ENV = "SERVICENOW_PASSWORD"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}

INCIDENT_STATE_RESOLVED = 6
CHANGE_STATE_APPROVED = "approved"


class ServiceNowConnector(BaseConnector):
    connector_name = "ServiceNow"
    connector_type = "servicenow"

    def __init__(self) -> None:
        self._instance: str = ""
        self._username: str = ""
        self._password: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._instance = credentials.get("instanceUrl", self._instance)
        self._username = credentials.get("username", self._username)
        self._password = credentials.get("password", self._password)

    async def initialize(self) -> bool:
        creds = self._load_credentials()
        self._instance = self._instance or creds.get("instanceUrl", "")
        self._username = self._username or creds.get("username", "")
        self._password = self._password or creds.get("password", "")
        if not self._instance or not self._username or not self._password:
            log.warning("SERVICENOW_INSTANCE, SERVICENOW_USERNAME, or SERVICENOW_PASSWORD not set — ServiceNow connector in degraded mode")
            self._available = False
            return False

        encoded = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=f"https://{self._instance}.service-now.com",
            headers={
                "Authorization": f"Basic {encoded}",
                "Accept": "application/json",
                "User-Agent": "CortexPrime-ServiceNowConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        try:
            resp = await self._client.get("/api/now/table/incident", params={"sysparm_limit": 1})
            if resp.status_code == 200:
                self._available = True
                log.info("ServiceNow connector initialized — authenticated to %s.service-now.com", self._instance)
                return True
            else:
                log.warning("ServiceNow auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("ServiceNow API unreachable: %s", e)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("ServiceNow connector shut down")
        return True

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "available" if self._available else "unavailable",
            "connector": self.connector_type,
            "authenticated": bool(self._username),
            "instance": self._instance,
        }

    # ------------------------------------------------------------------
    # Public API — each method delegates to _execute() for auto-recording
    # ------------------------------------------------------------------

    async def create_incident(self, short_description: str, description: str = "", priority: str = "3", **kwargs) -> Dict[str, Any]:
        return await self._execute("create_incident", "incidents", self._request, "POST", "/api/now/table/incident", json={
            "short_description": short_description,
            "description": description,
            "priority": priority,
            **kwargs,
        })

    async def get_incident(self, sys_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_incident", "incidents", self._request, "GET", f"/api/now/table/incident/{sys_id}")

    async def update_incident(self, sys_id: str, **fields) -> Dict[str, Any]:
        return await self._execute("update_incident", "incidents", self._request, "PATCH", f"/api/now/table/incident/{sys_id}", json=fields)

    async def resolve_incident(self, sys_id: str, close_notes: str = "Resolved by CortexPrime", **kwargs) -> Dict[str, Any]:
        return await self._execute("resolve_incident", "incidents", self._request, "PATCH", f"/api/now/table/incident/{sys_id}", json={
            "state": INCIDENT_STATE_RESOLVED,
            "close_notes": close_notes,
            **kwargs,
        })

    async def list_incidents(self, **kwargs) -> List[Dict[str, Any]]:
        params = {"sysparm_limit": 100, **kwargs}
        return await self._execute("list_incidents", "incidents", self._request_list, "GET", "/api/now/table/incident", params)

    async def create_change_request(self, short_description: str, description: str = "", priority: str = "3", **kwargs) -> Dict[str, Any]:
        return await self._execute("create_change_request", "change_requests", self._request, "POST", "/api/now/table/change_request", json={
            "short_description": short_description,
            "description": description,
            "priority": priority,
            **kwargs,
        })

    async def approve_change_request(self, sys_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("approve_change_request", "change_requests", self._request, "PATCH", f"/api/now/table/change_request/{sys_id}", json={
            "approval": CHANGE_STATE_APPROVED,
            **kwargs,
        })

    async def list_change_requests(self, **kwargs) -> List[Dict[str, Any]]:
        params = {"sysparm_limit": 100, **kwargs}
        return await self._execute("list_change_requests", "change_requests", self._request_list, "GET", "/api/now/table/change_request", params)

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry + error handling
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        # Audit S-1: a state-changing raw request outside an admitted _execute
        # operation is an unnamed write and meets the effect gate.
        guard_raw_request(self.connector_type, method)
        if not self._client:
            raise RuntimeError("ServiceNow connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 400:
                    body = self._safe_json(resp)
                    raise ValueError(f"ServiceNow API: 400 Bad Request — {body.get('error', resp.text[:200])}")
                if resp.status_code == 401:
                    raise PermissionError("ServiceNow API: 401 Unauthorized — check SERVICENOW_USERNAME / SERVICENOW_PASSWORD")
                if resp.status_code == 403:
                    body = self._safe_json(resp)
                    raise PermissionError(f"ServiceNow API: 403 Forbidden — {body.get('error', resp.text[:200])}")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"ServiceNow API: 404 Not Found — {path}")
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    if attempt < MAX_RETRIES:
                        log.warning("ServiceNow API HTTP 429 — waiting %ds (attempt %d/%d)", retry_after, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(retry_after)
                        continue
                    raise RuntimeError(f"ServiceNow API: HTTP 429 after {MAX_RETRIES} retries")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning("ServiceNow API HTTP %d — retrying in %.1fs (attempt %d/%d)", resp.status_code, backoff, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"ServiceNow API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    log.warning("ServiceNow API request failed: %s — retrying in %.1fs (attempt %d/%d)", e, backoff, attempt + 1, MAX_RETRIES)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"ServiceNow API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"ServiceNow API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _request_list(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("result", "value", "items", "data", "records", "entries"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Dict[str, Any]:
        try:
            return resp.json()
        except Exception:
            return {"error": resp.text[:500]}
