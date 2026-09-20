from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.connectors.base import BaseConnector
from backend.connectors.effects import guard_raw_request

log = logging.getLogger(__name__)

TEAMS_API_BASE = "https://graph.microsoft.com/v1.0"
TEAMS_TOKEN_ENV = "TEAMS_ACCESS_TOKEN"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class TeamsConnector(BaseConnector):
    connector_name = "Microsoft Teams"
    connector_type = "teams"

    def __init__(self) -> None:
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False
        self._authenticated_user_id: str = ""

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._token = credentials.get("accessToken", self._token)

    async def initialize(self) -> bool:
        self._token = self._token or self._load_credentials().get("accessToken", "")
        if not self._token:
            log.warning("TEAMS_ACCESS_TOKEN not set — Teams connector in degraded mode")
            self._available = False
            return False
        self._client = httpx.AsyncClient(
            base_url=TEAMS_API_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "User-Agent": "CortexPrime-TeamsConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        try:
            resp = await self._client.get("/me")
            if resp.status_code == 200:
                self._available = True
                body = resp.json()
                self._authenticated_user_id = body.get("id", "")
                display_name = body.get("displayName", "unknown")
                log.info(
                    "Teams connector initialized — authenticated as %s (%s)",
                    display_name, self._authenticated_user_id,
                )
                return True
            else:
                log.warning("Teams auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("Graph API unreachable: %s", e)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("Teams connector shut down")
        return True

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "available" if self._available else "unavailable",
            "connector": self.connector_type,
            "authenticated": bool(self._token),
            "user_id": self._authenticated_user_id,
        }

    # ------------------------------------------------------------------
    # Public API — each method delegates to _execute() for auto-recording
    # ------------------------------------------------------------------

    async def list_teams(self, **kwargs) -> List[Dict[str, Any]]:
        return await self._execute(
            "list_teams", "teams", self._request_list, "GET",
            "/groups?$filter=resourceProvisioningOptions/Any(x:x eq 'Team')"
            "&$select=id,displayName,description,visibility,createdDateTime",
        )

    async def get_team(self, team_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute(
            "get_team", "teams", self._request, "GET",
            f"/teams/{team_id}",
        )

    async def list_channels(self, team_id: str, **kwargs) -> List[Dict[str, Any]]:
        return await self._execute(
            "list_channels", "channels", self._request_list, "GET",
            f"/teams/{team_id}/channels",
        )

    async def get_channel(self, team_id: str, channel_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute(
            "get_channel", "channels", self._request, "GET",
            f"/teams/{team_id}/channels/{channel_id}",
        )

    async def create_channel(
        self, team_id: str, display_name: str,
        description: str = "", membership_type: str = "standard",
        **kwargs,
    ) -> Dict[str, Any]:
        return await self._execute(
            "create_channel", "channels", self._request, "POST",
            f"/teams/{team_id}/channels",
            json={
                "displayName": display_name,
                "description": description,
                "membershipType": membership_type,
                **kwargs,
            },
        )

    async def list_messages(
        self, team_id: str, channel_id: str,
        top: int = 50, **kwargs,
    ) -> List[Dict[str, Any]]:
        params = {"$top": top, **kwargs}
        return await self._execute(
            "list_messages", "messages", self._request_list, "GET",
            f"/teams/{team_id}/channels/{channel_id}/messages",
            params,
        )

    async def send_message(
        self, team_id: str, channel_id: str,
        body: str, subject: str = "", **kwargs,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "body": {"contentType": "html", "content": body},
        }
        if subject:
            payload["subject"] = subject
        payload.update(kwargs)
        return await self._execute(
            "send_message", "messages", self._request, "POST",
            f"/teams/{team_id}/channels/{channel_id}/messages",
            json=payload,
        )

    async def reply_to_message(
        self, team_id: str, channel_id: str,
        message_id: str, body: str, **kwargs,
    ) -> Dict[str, Any]:
        return await self._execute(
            "reply_to_message", "messages", self._request, "POST",
            f"/teams/{team_id}/channels/{channel_id}"
            f"/messages/{message_id}/replies",
            json={
                "body": {"contentType": "html", "content": body},
                **kwargs,
            },
        )

    async def create_meeting(
        self, subject: str,
        start_date_time: str, end_date_time: str,
        description: str = "", user_id: str = "me",
        **kwargs,
    ) -> Dict[str, Any]:
        return await self._execute(
            "create_meeting", "meetings", self._request, "POST",
            f"/users/{user_id}/onlineMeetings",
            json={
                "subject": subject,
                "startDateTime": start_date_time,
                "endDateTime": end_date_time,
                "description": description,
                **kwargs,
            },
        )

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry + error handling
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        # Audit S-1: a state-changing raw request outside an admitted _execute
        # operation is an unnamed write and meets the effect gate.
        guard_raw_request(self.connector_type, method)
        if not self._client:
            raise RuntimeError("Teams connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 400:
                    body = self._safe_json(resp)
                    msg = body.get("error", {}).get("message", resp.text[:200])
                    raise ValueError(f"Graph API: 400 Bad Request — {msg}")
                if resp.status_code == 401:
                    raise PermissionError(
                        "Graph API: 401 Unauthorized — check TEAMS_ACCESS_TOKEN"
                    )
                if resp.status_code == 403:
                    body = self._safe_json(resp)
                    msg = body.get("error", {}).get("message", resp.text[:200])
                    raise PermissionError(f"Graph API: 403 Forbidden — {msg}")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Graph API: 404 Not Found — {path}")
                if resp.status_code == 409:
                    body = self._safe_json(resp)
                    msg = body.get("error", {}).get("message", resp.text[:200])
                    raise RuntimeError(f"Graph API: 409 Conflict — {msg}")
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    if attempt < MAX_RETRIES:
                        log.warning(
                            "Graph API HTTP 429 — waiting %ds (attempt %d/%d)",
                            retry_after, attempt + 1, MAX_RETRIES,
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    raise RuntimeError(
                        f"Graph API: HTTP 429 after {MAX_RETRIES} retries"
                    )
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning(
                            "Graph API HTTP %d — retrying in %.1fs (attempt %d/%d)",
                            resp.status_code, backoff, attempt + 1, MAX_RETRIES,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(
                        f"Graph API: HTTP {resp.status_code} "
                        f"after {MAX_RETRIES} retries"
                    )
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    log.warning(
                        "Graph API request failed: %s — retrying in %.1fs "
                        "(attempt %d/%d)",
                        e, backoff, attempt + 1, MAX_RETRIES,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(
                    f"Graph API request failed after {MAX_RETRIES} retries: "
                    f"{last_error}"
                ) from last_error
        raise RuntimeError(
            f"Graph API request failed after {MAX_RETRIES} retries: {last_error}"
        )

    async def _request_list(
        self, method: str, path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        result = await self._request(method, path, params=params or {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("value", "items", "data", "results", "entries"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Dict[str, Any]:
        try:
            return resp.json()
        except Exception:
            return {"error": {"message": resp.text[:500]}}
