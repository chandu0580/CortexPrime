from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx

from backend.connector.adapter.interfaces import AdapterHealthStatus, AdapterResult, ConnectorAdapter
from backend.connector.models import Capability

log = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"
SLACK_TOKEN_ENV = "SLACK_BOT_TOKEN"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class SlackAdapter(ConnectorAdapter):

    @property
    def connector_type(self) -> str:
        return "slack"

    @property
    def connector_name(self) -> str:
        return "Slack"

    @property
    def adapter_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized: bool = False
        self._bot_user_id: str = ""

    async def initialize(self) -> bool:
        self._token = os.getenv(SLACK_TOKEN_ENV, "")
        if not self._token:
            log.warning("SLACK_BOT_TOKEN not set — Slack adapter in degraded mode")
            return False
        self._client = httpx.AsyncClient(
            base_url=SLACK_API_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "CortexPrime-SlackAdapter/1.0",
            },
            timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=10.0),
        )
        try:
            resp = await self._client.get("/auth.test")
            body = resp.json()
            if resp.status_code == 200 and body.get("ok"):
                self._initialized = True
                self._bot_user_id = body.get("user_id", "")
                log.info("Slack adapter initialized — authenticated as %s", body.get("user", "unknown"))
                return True
            log.warning("Slack auth check failed: %s", body.get("error", "unknown"))
            return False
        except httpx.RequestError as e:
            log.warning("Slack API unreachable: %s", e)
            return False

    async def health_check(self) -> AdapterHealthStatus:
        if not self._initialized or not self._client:
            return AdapterHealthStatus.UNHEALTHY
        try:
            resp = await self._client.get("/auth.test")
            body = resp.json()
            if resp.status_code == 200 and body.get("ok"):
                return AdapterHealthStatus.HEALTHY
            return AdapterHealthStatus.DEGRADED
        except httpx.RequestError:
            return AdapterHealthStatus.UNHEALTHY

    async def capabilities(self) -> list[Capability]:
        return [
            Capability.NOTIFY,
            Capability.SEARCH,
            Capability.EXECUTE,
        ]

    async def execute(self, capability: Capability, inputs: dict[str, Any],
                      timeout_seconds: Optional[int] = None) -> AdapterResult:
        start = time.monotonic()

        if capability == Capability.NOTIFY:
            return await self._send_message(inputs, start)
        if capability == Capability.SEARCH:
            return await self._search_messages(inputs, start)
        if capability == Capability.EXECUTE:
            return await self._execute_action(inputs, start)

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
        log.info("Slack adapter shut down")

    async def metadata(self) -> dict[str, Any]:
        base = await super().metadata()
        base["bot_user_id"] = self._bot_user_id
        return base

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self._client:
            raise RuntimeError("Slack adapter not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                body = resp.json()

                if resp.status_code == 200 and not body.get("ok"):
                    error = body.get("error", "unknown_error")
                    if error in ("ratelimited", "too_many_requests"):
                        retry_after = int(resp.headers.get("Retry-After", 5))
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(retry_after)
                            continue
                        raise RuntimeError(f"Slack API: rate limited after {MAX_RETRIES} retries")
                    if error in ("not_authed", "invalid_auth", "account_inactive"):
                        raise PermissionError(f"Slack API: auth failed — {error}")
                    raise RuntimeError(f"Slack API: {error}")

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(retry_after)
                        continue
                    raise RuntimeError(f"Slack API: HTTP 429 after {MAX_RETRIES} retries")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"Slack API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return body
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Slack API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"Slack API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _send_message(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        channel = inputs.get("channel")
        text = inputs.get("text", inputs.get("message", ""))
        if not channel or not text:
            return AdapterResult(success=False, error="Missing 'channel' or 'text'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            payload: dict[str, Any] = {"channel": channel, "text": text}
            if "thread_ts" in inputs:
                payload["thread_ts"] = inputs["thread_ts"]
            data = await self._request("POST", "/chat.postMessage", json=payload)
            return AdapterResult(success=True, outputs={"channel": channel, "ts": data.get("ts"), "message": data.get("message", {})}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _search_messages(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        channel = inputs.get("channel")
        limit = inputs.get("limit", 10)
        if not channel:
            return AdapterResult(success=False, error="Missing 'channel'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            data = await self._request("GET", "/conversations.history", params={"channel": channel, "limit": limit})
            return AdapterResult(success=True, outputs={"messages": data.get("messages", []), "channel": channel}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _execute_action(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        channel = inputs.get("channel")
        if not channel:
            return AdapterResult(success=False, error="Missing 'channel'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            data = await self._request("GET", "/conversations.info", params={"channel": channel})
            return AdapterResult(success=True, outputs={"channel": data.get("channel", {})}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)
