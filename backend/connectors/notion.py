from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector
from backend.connectors.effects import guard_raw_request

log = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_TOKEN_ENV = "NOTION_API_KEY"
NOTION_VERSION_ENV = "NOTION_VERSION"
NOTION_VERSION_DEFAULT = "2022-06-28"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class NotionConnector(BaseConnector):
    connector_name = "Notion"
    connector_type = "notion"

    def __init__(self) -> None:
        self._token: str = ""
        self._version: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False
        self._bot_name: str = ""
        self._bot_id: str = ""

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._token = credentials.get("integrationToken", self._token)
        self._version = credentials.get("notionVersion", self._version)

    async def initialize(self) -> bool:
        creds = self._load_credentials()
        self._token = self._token or creds.get("integrationToken", "")
        if not self._token:
            log.warning("NOTION_API_KEY not set — Notion connector in degraded mode")
            self._available = False
            return False
        self._version = self._version or creds.get("notionVersion", "") or NOTION_VERSION_DEFAULT
        self._client = httpx.AsyncClient(
            base_url=NOTION_API_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Notion-Version": self._version,
                "Accept": "application/json",
                "User-Agent": "CortexPrime-NotionConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        try:
            resp = await self._client.get("/users/me")
            if resp.status_code == 200:
                self._available = True
                body = resp.json()
                self._bot_name = body.get("name", "unknown")
                self._bot_id = body.get("id", "")
                log.info(
                    "Notion connector initialized — authenticated as %s (%s)",
                    self._bot_name, self._bot_id,
                )
                return True
            else:
                log.warning("Notion auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("Notion API unreachable: %s", e)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("Notion connector shut down")
        return True

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "available" if self._available else "unavailable",
            "connector": self.connector_type,
            "authenticated": bool(self._token),
            "bot_name": self._bot_name,
            "bot_id": self._bot_id,
        }

    # ------------------------------------------------------------------
    # Public API — each method delegates to _execute() for auto-recording
    # ------------------------------------------------------------------

    async def list_pages(self, query: str = "", page_size: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """List pages via the Notion search API, optionally filtered by a query string."""
        payload: Dict[str, Any] = {
            "page_size": page_size,
            "filter": {"value": "page", "property": "object"},
        }
        if query:
            payload["query"] = query
        payload.update(kwargs)
        result = await self._execute("list_pages", "pages", self._request, "POST", "/search", json=payload)
        if isinstance(result, dict):
            for key in ("results", "value", "items", "data"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []

    async def create_page(self, parent: Dict[str, Any], properties: Optional[Dict[str, Any]] = None, children: Optional[List[Dict[str, Any]]] = None, icon: Optional[Dict[str, Any]] = None, cover: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"parent": parent}
        if properties is not None:
            payload["properties"] = properties
        if children is not None:
            payload["children"] = children
        if icon is not None:
            payload["icon"] = icon
        if cover is not None:
            payload["cover"] = cover
        payload.update(kwargs)
        return await self._execute("create_page", "pages", self._request, "POST", "/pages", json=payload)

    async def get_page(self, page_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_page", "pages", self._request, "GET", f"/pages/{page_id}")

    async def update_page(self, page_id: str, properties: Optional[Dict[str, Any]] = None, archived: Optional[bool] = None, icon: Optional[Dict[str, Any]] = None, cover: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if properties is not None:
            payload["properties"] = properties
        if archived is not None:
            payload["archived"] = archived
        if icon is not None:
            payload["icon"] = icon
        if cover is not None:
            payload["cover"] = cover
        payload.update(kwargs)
        return await self._execute("update_page", "pages", self._request, "PATCH", f"/pages/{page_id}", json=payload)

    async def archive_page(self, page_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("archive_page", "pages", self._request, "PATCH", f"/pages/{page_id}", json={"archived": True, **kwargs})

    async def list_users(self, **kwargs) -> List[Dict[str, Any]]:
        return await self._execute("list_users", "users", self._request_list, "GET", "/users")

    async def search(self, query: str = "", sort: Optional[Dict[str, Any]] = None, filter_obj: Optional[Dict[str, Any]] = None, page_size: int = 100, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"page_size": page_size}
        if query:
            payload["query"] = query
        if sort is not None:
            payload["sort"] = sort
        if filter_obj is not None:
            payload["filter"] = filter_obj
        payload.update(kwargs)
        return await self._execute("search", "search", self._request, "POST", "/search", json=payload)

    async def query_database(self, database_id: str, filter_obj: Optional[Dict[str, Any]] = None, sorts: Optional[List[Dict[str, Any]]] = None, page_size: int = 100, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"page_size": page_size}
        if filter_obj is not None:
            payload["filter"] = filter_obj
        if sorts is not None:
            payload["sorts"] = sorts
        payload.update(kwargs)
        return await self._execute("query_database", "databases", self._request, "POST", f"/databases/{database_id}/query", json=payload)

    async def create_database(self, parent: Dict[str, Any], title: Optional[List[Dict[str, Any]]] = None, properties: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"parent": parent}
        if title is not None:
            payload["title"] = title
        if properties is not None:
            payload["properties"] = properties
        payload.update(kwargs)
        return await self._execute("create_database", "databases", self._request, "POST", "/databases", json=payload)

    async def append_blocks(self, block_id: str, children: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        return await self._execute("append_blocks", "blocks", self._request, "PATCH", f"/blocks/{block_id}/children", json={"children": children, **kwargs})

    async def list_blocks(self, block_id: str, page_size: int = 100, **kwargs) -> List[Dict[str, Any]]:
        params = {"page_size": page_size, **kwargs}
        return await self._execute("list_blocks", "blocks", self._request_list, "GET", f"/blocks/{block_id}/children", params)

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry + error handling
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        # Audit S-1: a state-changing raw request outside an admitted _execute
        # operation is an unnamed write and meets the effect gate.
        guard_raw_request(self.connector_type, method)
        if not self._client:
            raise RuntimeError("Notion connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 400:
                    body = self._safe_json(resp)
                    msg = body.get("message", resp.text[:200])
                    raise ValueError(f"Notion API: 400 Bad Request — {msg}")
                if resp.status_code == 401:
                    raise PermissionError("Notion API: 401 Unauthorized — check NOTION_API_KEY")
                if resp.status_code == 403:
                    body = self._safe_json(resp)
                    msg = body.get("message", resp.text[:200])
                    raise PermissionError(f"Notion API: 403 Forbidden — {msg}")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Notion API: 404 Not Found — {path}")
                if resp.status_code == 409:
                    body = self._safe_json(resp)
                    msg = body.get("message", resp.text[:200])
                    raise RuntimeError(f"Notion API: 409 Conflict — {msg}")
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    if attempt < MAX_RETRIES:
                        log.warning("Notion API HTTP 429 — waiting %ds (attempt %d/%d)", retry_after, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(retry_after)
                        continue
                    raise RuntimeError(f"Notion API: HTTP 429 after {MAX_RETRIES} retries")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning("Notion API HTTP %d — retrying in %.1fs (attempt %d/%d)", resp.status_code, backoff, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"Notion API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    log.warning("Notion API request failed: %s — retrying in %.1fs (attempt %d/%d)", e, backoff, attempt + 1, MAX_RETRIES)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Notion API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"Notion API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _request_list(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("results", "value", "items", "data", "entries"):
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
