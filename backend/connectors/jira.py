from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Dict, Optional

import httpx

from backend.connectors.base import BaseConnector
from backend.connectors.effects import guard_raw_request

log = logging.getLogger(__name__)

JIRA_BASE_URL_ENV = "JIRA_BASE_URL"
JIRA_EMAIL_ENV = "JIRA_EMAIL"
JIRA_TOKEN_ENV = "JIRA_API_TOKEN"
MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

RETRYABLE_STATUSES = {429, 502, 503, 504}


class JiraConnector(BaseConnector):
    connector_name = "Jira"
    connector_type = "jira"

    def __init__(self) -> None:
        self._base_url: str = ""
        self._email: str = ""
        self._token: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._available: bool = False

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        self._base_url = credentials.get("baseUrl", self._base_url)
        self._email = credentials.get("email", self._email)
        self._token = credentials.get("token", self._token)

    async def initialize(self) -> bool:
        creds = self._load_credentials()
        self._base_url = (self._base_url or creds.get("baseUrl", "")
                          or "https://chandu-ai.atlassian.net").rstrip("/")
        self._email = self._email or creds.get("email", "")
        self._token = self._token or creds.get("token", "")
        if not self._email or not self._token:
            log.warning("JIRA_EMAIL or JIRA_API_TOKEN not set — Jira connector in degraded mode")
            self._available = False
            return False
        encoded = base64.b64encode(f"{self._email}:{self._token}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Basic {encoded}",
                "Accept": "application/json",
                "User-Agent": "CortexPrime-JiraConnector/1.0",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        try:
            resp = await self._client.get("/rest/api/3/myself")
            if resp.status_code == 200:
                self._available = True
                display_name = resp.json().get("displayName", "unknown")
                log.info("Jira connector initialized — authenticated as %s", display_name)
                return True
            else:
                log.warning("Jira auth check failed: HTTP %d", resp.status_code)
                self._available = False
                return False
        except httpx.RequestError as e:
            log.warning("Jira API unreachable: %s", e)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("Jira connector shut down")
        return True

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "available" if self._available else "unavailable",
            "connector": self.connector_type,
            "authenticated": bool(self._token),
        }

    async def check_credential(self) -> Dict[str, Any]:
        """Atlassian API tokens have no introspection endpoint for expiry —
        this is failure-detection only. A healthy result means "still
        authenticates right now," not "won't expire soon"."""
        try:
            await self._execute("check_credential", "auth", self._request, "GET", "/rest/api/3/myself")
            return {"valid": True, "expires_at": None, "expires_at_source": None, "error": None}
        except PermissionError as exc:
            return {"valid": False, "expires_at": None, "expires_at_source": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Public API — each method delegates to _execute() for auto-recording
    # ------------------------------------------------------------------

    async def get_issue(self, issue_key: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("get_issue", "issues", self._request, "GET", f"/rest/api/3/issue/{issue_key}")

    async def create_issue(self, project_key: str, issue_type: str, title: str, description: str = "", reporter_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        return await self._execute("create_issue", "issues", self._request, "POST", "/rest/api/3/issue", json={
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type.capitalize()},
                "summary": title,
                "description": self._build_description_doc(description),
                **({"reporter": {"id": reporter_id}} if reporter_id else {}),
                **kwargs,
            },
        })

    async def update_issue(self, issue_key: str, **fields) -> Dict[str, Any]:
        return await self._execute("update_issue", "issues", self._request, "PUT", f"/rest/api/3/issue/{issue_key}", json={"fields": fields})

    async def transition_issue(self, issue_key: str, transition_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("transition_issue", "issues", self._request, "POST", f"/rest/api/3/issue/{issue_key}/transitions", json={"transition": {"id": transition_id}})

    async def assign_issue(self, issue_key: str, account_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("assign_issue", "issues", self._request, "PUT", f"/rest/api/3/issue/{issue_key}/assignee", json={"accountId": account_id})

    async def complete_sprint(self, sprint_id: str, **kwargs) -> Dict[str, Any]:
        return await self._execute("complete_sprint", "sprints", self._request, "POST", f"/rest/agile/1.0/sprint/{sprint_id}", json={"state": "closed"})

    async def add_comment(self, issue_key: str, body: str) -> Dict[str, Any]:
        return await self._execute("add_comment", "issues", self._request, "POST", f"/rest/api/3/issue/{issue_key}/comment", json={
            "body": self._build_description_doc(body),
        })

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry + error handling
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        # Audit S-1: a state-changing raw request outside an admitted _execute
        # operation is an unnamed write and meets the effect gate.
        guard_raw_request(self.connector_type, method)
        if not self._client:
            raise RuntimeError("Jira connector not initialized")
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code == 401:
                    raise PermissionError("Jira API: 401 Unauthorized — check JIRA_EMAIL / JIRA_API_TOKEN")
                if resp.status_code == 403:
                    body = resp.json()
                    raise PermissionError(f"Jira API: 403 Forbidden — {body.get('message', '')}")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Jira API: 404 Not Found — {path}")
                if resp.status_code == 409:
                    raise RuntimeError(f"Jira API: 409 Conflict — {resp.json().get('message', '')}")
                if resp.status_code == 422:
                    body = resp.json()
                    errors = body.get("errors", {})
                    detail = "; ".join(f"{k}: {v}" for k, v in errors.items()) or body.get("message", "")
                    raise ValueError(f"Jira API: 422 Unprocessable — {detail}")
                if resp.status_code in RETRYABLE_STATUSES or 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES:
                        backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                        log.warning("Jira API HTTP %d — retrying in %.1fs (attempt %d/%d)", resp.status_code, backoff, attempt + 1, MAX_RETRIES)
                        await asyncio.sleep(backoff)
                        continue
                    raise RuntimeError(f"Jira API: HTTP {resp.status_code} after {MAX_RETRIES} retries")
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = min(BASE_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                    log.warning("Jira API request failed: %s — retrying in %.1fs (attempt %d/%d)", e, backoff, attempt + 1, MAX_RETRIES)
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"Jira API request failed after {MAX_RETRIES} retries: {last_error}") from last_error
        raise RuntimeError(f"Jira API request failed after {MAX_RETRIES} retries: {last_error}")

    @staticmethod
    def _build_description_doc(text: str) -> Dict[str, Any]:
        if not text:
            return {"type": "doc", "version": 1, "content": []}
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]},
            ],
        }
