from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Callable, Dict, Generic, List, Optional, TypeVar

import httpx

log = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreaker:
    """Circuit breaker pattern to prevent repeated calls to failing services."""

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = self.STATE_CLOSED
        self._last_failure_time = 0.0

    @property
    def state(self) -> str:
        if self._state == self.STATE_OPEN:
            if time.time() - self._last_failure_time >= self._recovery_timeout:
                self._state = self.STATE_HALF_OPEN
        return self._state

    def call(self, fn: Callable[[], T]) -> T:
        if self.state == self.STATE_OPEN:
            raise RuntimeError(f"Circuit breaker is OPEN for {self._failure_threshold} failures")
        try:
            result = fn()
            self._failures = 0
            self._state = self.STATE_CLOSED
            return result
        except Exception as exc:
            self._failures += 1
            self._last_failure_time = time.time()
            if self._failures >= self._failure_threshold:
                self._state = self.STATE_OPEN
            raise exc


class TokenManager:
    """Manages OAuth token refresh for connector authentication."""

    def __init__(self, client_id: str, client_secret: str, token_url: str,
                 scopes: Optional[List[str]] = None):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._scopes = scopes or []
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.time() >= self._expires_at - 60  # 60s buffer

    @property
    def valid_token(self) -> Optional[str]:
        if self.is_expired:
            self._refresh()
        return self._access_token

    def set_tokens(self, access_token: str, refresh_token: Optional[str] = None,
                   expires_in: int = 3600):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = time.time() + expires_in

    def _refresh(self):
        if not self._refresh_token:
            return
        try:
            resp = httpx.post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=10,
            )
            if resp.is_success:
                data = resp.json()
                self.set_tokens(
                    access_token=data.get("access_token", ""),
                    refresh_token=data.get("refresh_token", self._refresh_token),
                    expires_in=data.get("expires_in", 3600),
                )
        except Exception as exc:
            log.warning("Token refresh failed: %s", exc)


class PaginatedResponse(Generic[T]):
    """Generic paginated response helper."""

    def __init__(self, items: List[T], next_page_token: Optional[str] = None,
                 has_more: bool = False, total: Optional[int] = None):
        self.items = items
        self.next_page_token = next_page_token
        self.has_more = has_more
        self.total = total


class BaseConnector(ABC):
    """Abstract base connector with common infrastructure."""

    def __init__(self, name: str, base_url: str, timeout: float = 30.0,
                 max_connections: int = 10):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._circuit_breaker = CircuitBreaker()
        self._token_manager: Optional[TokenManager] = None
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_connections),
            event_hooks={
                "response": [self._on_response],
            },
        )

    async def _on_response(self, response: httpx.Response):
        """Hook for response logging and error handling."""
        if response.status_code >= 400:
            log.warning("[%s] HTTP %d: %s", self.name, response.status_code, response.url)

    def set_auth(self, client_id: str, client_secret: str, token_url: str,
                 scopes: Optional[List[str]] = None):
        self._token_manager = TokenManager(client_id, client_secret, token_url, scopes)

    async def _get_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token_manager and self._token_manager.valid_token:
            headers["Authorization"] = f"Bearer {self._token_manager.valid_token}"
        return headers

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an HTTP request with circuit breaker protection."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        headers.update(await self._get_headers())

        async def _do_request():
            return await self._client.request(method, url, headers=headers, **kwargs)

        try:
            return self._circuit_breaker.call(_do_request)
        except Exception as exc:
            log.error("[%s] Request failed: %s %s - %s", self.name, method, url, exc)
            raise

    async def get_paginated(self, path: str, page_size: int = 100,
                            page_param: str = "page",
                            next_token_param: str = "next_token",
                            **kwargs) -> PaginatedResponse[Dict]:
        """Helper for paginated GET requests."""
        params = kwargs.pop("params", {})
        params[page_param if page_param == "page" else next_token_param] = 1
        params["per_page"] = page_size
        resp = await self.request("GET", path, params=params, **kwargs)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", data.get("items", []))
        next_token = data.get("next_page_token") if isinstance(data, dict) else None
        has_more = bool(next_token)
        total = data.get("total") if isinstance(data, dict) else None
        return PaginatedResponse(
            items=items, next_page_token=next_token,
            has_more=has_more, total=total,
        )

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the connector service is healthy."""
        ...

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
