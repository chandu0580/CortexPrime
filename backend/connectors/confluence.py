from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

CONFLUENCE_BASE_URL_ENV = "CONFLUENCE_BASE_URL"
CONFLUENCE_EMAIL_ENV = "CONFLUENCE_EMAIL"
CONFLUENCE_TOKEN_ENV = "CONFLUENCE_API_TOKEN"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class ConfluenceConnector(BaseConnector):
    connector_name = "Confluence"
    connector_type = "confluence"

    def __init__(self) -> None:
        self._base_url: str = ""
        self._email: str = ""
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._base_url = credentials.get("siteUrl", self._base_url)
        self._email = credentials.get("email", self._email)
        self._token = credentials.get("token", self._token)

    async def initialize(self) -> bool:
        creds = self._load_credentials()
        self._base_url = (self._base_url or creds.get("siteUrl", "")).rstrip("/")
        self._email = self._email or creds.get("email", "")
        self._token = self._token or creds.get("token", "")
        if not self._base_url or not self._email or not self._token:
            log.warning("CONFLUENCE_BASE_URL, CONFLUENCE_EMAIL, or CONFLUENCE_API_TOKEN not set — Confluence connector in degraded mode")
            self._available = False
            return False

        encoded = base64.b64encode(f"{self._email}:{self._token}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Basic {encoded}",
                "Accept": "application/json",
                "User-Agent": "CortexPrime-ConfluenceConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        try:
            resp = await self._client.get("/api/v2/spaces", params={"limit": 1})
            if resp.status_code == 200:
                self._available = True
                log.info("Confluence connector initialized — authenticated to %s", self._base_url)
                return True
            else:
                log.warning("Confluence auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("Confluence API unreachable: %s", e)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("Confluence connector shut down")
        return True

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "available" if self._available else "unavailable",
            "connector": self.connector_type,
            "authenticated": bool(self._token),
        }

    # ------------------------------------------------------------------
    # Public API — each method delegates to _execute() for auto-recording
    # ------------------------------------------------------------------

    async def create_page(self, space_id: str, title: str, body: str = "", parent_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "spaceId": space_id,
            "title": title,
            "body": {
                "representation": "storage",
                "value": body or f"<p>{title}</p>",
            },
        }
        if parent_id:
            payload["parentId"] = parent_id
        payload.update(kwargs)
        return await self._execute("create_page", "pages", self._request, "POST", "/api/v2/pages", json=payload)

    async def get_page(self, page_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_page", "pages", self._request, "GET", f"/api/v2/pages/{page_id}")

    async def update_page(self, page_id: str, title: str, body: str, version: int, **kwargs) -> Dict[str, Any]:
        return await self._execute("update_page", "pages", self._request, "PUT", f"/api/v2/pages/{page_id}", json={
            "id": page_id,
            "status": "current",
            "title": title,
            "body": {
                "representation": "storage",
                "value": body,
            },
            "version": {"number": version + 1, "message": kwargs.pop("message", "Updated by CortexPrime")},
            **kwargs,
        })

    async def delete_page(self, page_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("delete_page", "pages", self._request, "DELETE", f"/api/v2/pages/{page_id}")

    async def list_pages(self, space_id: Optional[str] = None, limit: int = 50, **kwargs) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit, **kwargs}
        if space_id:
            params["spaceId"] = space_id
        return await self._execute("list_pages", "pages", self._request_list, "GET", "/api/v2/pages", params)

    async def search_pages(self, cql: str, limit: int = 25, **kwargs) -> Dict[str, Any]:
        params: Dict[str, Any] = {"cql": cql, "limit": limit, **kwargs}
        return await self._execute("search_pages", "pages", self._request, "GET", "/rest/api/search", params=params)

    async def create_comment(self, page_id: str, body: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("create_comment", "comments", self._request, "POST", "/api/v2/footer-comments", json={
            "body": {
                "representation": "storage",
                "value": body,
            },
            "pageId": page_id,
            "type": "footer",
            **kwargs,
        })

    async def get_space(self, space_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_space", "spaces", self._request, "GET", f"/api/v2/spaces/{space_id}")

    async def list_spaces(self, limit: int = 50, **kwargs) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit, **kwargs}
        return await self._execute("list_spaces", "spaces", self._request_list, "GET", "/api/v2/spaces", params)

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry + error handling
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("Confluence connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 400:
                    body = self._safe_json(resp)
                    raise ValueError(f"Confluence API: 400 Bad Request — {body.get('message', resp.text[:200])}")
                if resp.status_code == 401:
                    raise PermissionError("Confluence API: 401 Unauthorized — check CONFLUENCE_EMAIL / CONFLUENCE_API_TOKEN")
                if resp.status_code == 403:
                    body = self._safe_json(resp)
                    raise PermissionError(f"Confluence API: 403 Forbidden — {body.get('message', resp.text[:200])}")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Confluence API: 404 Not Found — {path}")
                if resp.status_code == 409:
                    body = self._safe_json(resp)
                    raise RuntimeError(f"Confluence API: 409 Conflict — {body.get('message', resp.text[:200])}")
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    if attempt < MAX_RETRIES:
                        log.warning("Confluence API HTTP 429 — waiting %ds (attempt %d/%d)", retry_after, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(retry_after)
                        continue
                    raise RuntimeError(f"Confluence API: HTTP 429 after {MAX_RETRIES} retries")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning("Confluence API HTTP %d — retrying in %.1fs (attempt %d/%d)", resp.status_code, backoff, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"Confluence API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    log.warning("Confluence API request failed: %s — retrying in %.1fs (attempt %d/%d)", e, backoff, attempt + 1, MAX_RETRIES)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Confluence API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"Confluence API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _request_list(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("results", "value", "items", "data", "records", "entries"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Dict[str, Any]:
        try:
            return resp.json()
        except Exception:
            return {"message": resp.text[:500]}
