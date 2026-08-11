from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"
SLACK_TOKEN_ENV = "SLACK_BOT_TOKEN"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class SlackConnector(BaseConnector):
    connector_name = "Slack"
    connector_type = "slack"

    def __init__(self) -> None:
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False
        self._bot_user_id: str = ""

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._token = credentials.get("botToken", self._token)

    async def initialize(self) -> bool:
        self._token = self._token or self._load_credentials().get("botToken", "")
        if not self._token:
            log.warning("SLACK_BOT_TOKEN not set — Slack connector in degraded mode")
            self._available = False
            return False
        self._client = httpx.AsyncClient(
            base_url=SLACK_API_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "CortexPrime-SlackConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        try:
            resp = await self._client.get("/auth.test")
            body = resp.json()
            if resp.status_code == 200 and body.get("ok"):
                self._available = True
                self._bot_user_id = body.get("user_id", "")
                bot_name = body.get("user", "unknown")
                log.info("Slack connector initialized — authenticated as %s (%s)", bot_name, self._bot_user_id)
                return True
            else:
                error = body.get("error", "unknown")
                log.warning("Slack auth check failed: %s", error)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("Slack API unreachable: %s", e)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("Slack connector shut down")
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

    async def send_message(self, channel: str, text: str, thread_ts: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts is not None:
            payload["thread_ts"] = thread_ts
        payload.update(kwargs)
        return await self._execute("send_message", "messages", self._request, "POST", "/chat.postMessage", json=payload)

    async def create_channel(self, name: str, is_private: bool = False, **kwargs) -> Dict[str, Any]:
        return await self._execute("create_channel", "channels", self._request, "POST", "/conversations.create", json={"name": name, "is_private": is_private, **kwargs})

    async def list_channels(self, exclude_archived: bool = True, limit: int = 200, **kwargs) -> List[Dict[str, Any]]:
        return await self._execute("list_channels", "channels", self._request_list, "GET", "/conversations.list", {"exclude_archived": exclude_archived, "limit": limit, **kwargs})

    async def invite_user(self, channel: str, users: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("invite_user", "channels", self._request, "POST", "/conversations.invite", json={"channel": channel, "users": users, **kwargs})

    async def upload_file(self, channels: str, content: str, filename: str, initial_comment: str = "", **kwargs) -> Dict[str, Any]:
        return await self._execute("upload_file", "files", self._request, "POST", "/files.upload", json={"channels": channels, "content": content, "filename": filename, "initial_comment": initial_comment, **kwargs})

    async def list_messages(self, channel: str, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return await self._execute("list_messages", "messages", self._request_list, "GET", "/conversations.history", {"channel": channel, "limit": limit, **kwargs})

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry + error handling
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("Slack connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                body = resp.json()

                # Slack always returns 200 with {"ok": false, "error": "..."} for biz errors
                if resp.status_code == 200 and not body.get("ok"):
                    error = body.get("error", "unknown_error")
                    if error in ("not_authed", "invalid_auth", "account_inactive"):
                        raise PermissionError(f"Slack API: auth failed — {error}")
                    if error in ("channel_not_found", "is_archived", "name_taken"):
                        raise FileNotFoundError(f"Slack API: {error}")
                    if error in ("no_permission", "restricted_action"):
                        raise PermissionError(f"Slack API: {error}")
                    if error == "invalid_arguments":
                        raise ValueError(f"Slack API: invalid arguments — {body.get('response_metadata', {})}")
                    if error in ("ratelimited", "too_many_requests"):
                        retry_after = int(resp.headers.get("Retry-After", 5))
                        if attempt < MAX_RETRIES:
                            log.warning("Slack rate limited — waiting %ds (attempt %d/%d)", retry_after, attempt + 1, MAX_RETRIES)
                            await asyncio.sleep(retry_after)
                            continue
                        raise RuntimeError(f"Slack API: rate limited after {MAX_RETRIES} retries")
                    raise RuntimeError(f"Slack API: {error}")

                if resp.status_code == 204:
                    return {}
                if resp.status_code == 401:
                    raise PermissionError("Slack API: 401 Unauthorized — check SLACK_BOT_TOKEN")
                if resp.status_code == 403:
                    raise PermissionError(f"Slack API: 403 Forbidden — {body.get('error', '')}")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Slack API: 404 Not Found — {path}")
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    if attempt < MAX_RETRIES:
                        log.warning("Slack API HTTP 429 — waiting %ds (attempt %d/%d)", retry_after, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(retry_after)
                        continue
                    raise RuntimeError(f"Slack API: HTTP 429 after {MAX_RETRIES} retries")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning("Slack API HTTP %d — retrying in %.1fs (attempt %d/%d)", resp.status_code, backoff, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"Slack API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return body
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    log.warning("Slack API request failed: %s — retrying in %.1fs (attempt %d/%d)", e, backoff, attempt + 1, MAX_RETRIES)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Slack API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"Slack API request failed after {MAX_RETRIES} retries: {last_error}")

    async def _request_list(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("channels", "messages", "files", "members", "items", "data", "results", "entries"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []
