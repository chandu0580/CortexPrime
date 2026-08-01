"""
Enterprise GitLab CI Integration — Deploy Regression Wiring.

Deliberately narrow: this is NOT a GitLab equivalent of the full GitHub
integration (no PR/issue/branch tracking). It exists for one purpose —
prove the deploy-regression detection pipeline built for GitHub actually
generalizes to a second CI/CD provider, by reusing the exact same
detector/reasoner/ticketing/history path
(backend.services.enterprise_github_integration._check_deploy_regression)
rather than building a parallel one.

Wired from: POST /api/gitlab/webhook, on a "deployment" event whose
status is "success".

GitLab's webhook model differs from GitHub's in two ways worth noting:
  - Signing: a plain shared-secret string sent verbatim in the
    X-Gitlab-Token header (constant-time compared), not an HMAC signature
    — GitLab does send the secret itself, unlike GitHub's proof-of-knowledge
    scheme, so this must never be logged or echoed back.
  - Root-cause reasoning (backend.services.enterprise_deploy_root_cause_reasoner)
    fetches the deployed diff via the GitHub connector specifically, so it
    has nothing to fetch for a GitLab-sourced deployment and returns None —
    detection and ticketing still run fully; only the LLM hypothesis step
    is unavailable until a GitLab-diff path is added.
"""
from __future__ import annotations

import hmac
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from backend.services.enterprise_github_integration import (
    WebhookDeliveryStore,
    _check_deploy_regression,
    _now,
)

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_GITLAB_WEBHOOK_DELIVERIES_FILE = _DATA_DIR / "gitlab_webhook_deliveries.json"

# Server-side configuration only — GitLab sends this value verbatim in
# X-Gitlab-Token (unlike GitHub's HMAC scheme), so it's compared against
# our own environment, never echoed or logged.
GITLAB_WEBHOOK_SECRET_ENV = "GITLAB_WEBHOOK_SECRET"


class GitLabWebhookReceiver:
    """Verify GitLab webhook tokens, handle replay protection, and parse deployment events."""

    def __init__(self) -> None:
        self._delivery_store = WebhookDeliveryStore(file_path=_GITLAB_WEBHOOK_DELIVERIES_FILE)

    def verify_token(self, token_header: str, secret: str) -> bool:
        if not token_header or not secret:
            return False
        return hmac.compare_digest(token_header, secret)

    @staticmethod
    def _header(headers: Dict[str, str], name: str) -> str:
        """Case-insensitive header lookup — see WebhookReceiver._header for why
        this matters (ASGI/Starlette lowercases header names in dict(request.headers))."""
        target = name.lower()
        for key, value in headers.items():
            if key.lower() == target:
                return value
        return ""

    def extract_delivery_id(self, headers: Dict[str, str]) -> str:
        return self._header(headers, "X-Gitlab-Event-UUID") or uuid.uuid4().hex[:12]

    def extract_event_type(self, headers: Dict[str, str]) -> str:
        return self._header(headers, "X-Gitlab-Event") or "unknown"

    def extract_token(self, headers: Dict[str, str]) -> str:
        return self._header(headers, "X-Gitlab-Token")

    def is_replay(self, delivery_id: str) -> bool:
        return self._delivery_store.is_duplicate(delivery_id)

    def get_recent_deliveries(self, limit: int = 20):
        return self._delivery_store.get_deliveries(limit)

    async def receive(self, body: bytes, headers: Dict[str, str], secret: str) -> Dict[str, Any]:
        import json

        delivery_id = self.extract_delivery_id(headers)
        event_type = self.extract_event_type(headers)
        token = self.extract_token(headers)

        if self.is_replay(delivery_id):
            log.warning("Duplicate GitLab webhook delivery detected: %s", delivery_id)
            return {"delivery_id": delivery_id, "status": "duplicate", "event_type": event_type}

        verified = self.verify_token(token, secret)
        payload = json.loads(body)
        repository = payload.get("project", {}).get("path_with_namespace", "")

        self._delivery_store.record_delivery(
            delivery_id=delivery_id,
            event_type=event_type,
            repository=repository,
            verified=verified,
        )

        if not verified:
            log.warning("GitLab webhook token verification failed for delivery %s", delivery_id)
            self._delivery_store.update_delivery(delivery_id, "signature_failed")
            return {"delivery_id": delivery_id, "event_type": event_type, "verified": False, "payload": payload}

        if verified and payload.get("object_kind") == "deployment":
            await _process_deployment_event(payload)

        return {"delivery_id": delivery_id, "event_type": event_type, "verified": True, "payload": payload}


async def _process_deployment_event(payload: Dict[str, Any]) -> None:
    """Translate a GitLab "Deployment Hook" payload into the same ctx shape
    the GitHub-sourced path produces, and hand it to the shared detector."""
    repo_full_name = payload.get("project", {}).get("path_with_namespace", "")
    deployment_id = payload.get("deployment_id", "")
    status = payload.get("status", "")

    if not repo_full_name or not deployment_id:
        return

    if status != "success":
        return

    ctx = {
        "source": "gitlab_webhook",
        "event_type": "deployment",
        "timestamp": _now(),
        "repo_url": payload.get("project", {}).get("web_url", ""),
        "repo_full_name": repo_full_name,
        "sender": payload.get("user", {}).get("username", ""),
        "deployment_id": deployment_id,
        "environment": payload.get("environment", ""),
        "deployment_state": status,
        "deployment_description": payload.get("commit_title", ""),
        "deployment_log_url": payload.get("deployable_url", ""),
    }

    await _check_deploy_regression(ctx)


gitlab_webhook_receiver = GitLabWebhookReceiver()
