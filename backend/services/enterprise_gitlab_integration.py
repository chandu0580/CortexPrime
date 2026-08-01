"""
Enterprise GitLab CI Integration — Deploy Regression + Flaky Test Wiring.

Deliberately narrow: this is NOT a GitLab equivalent of the full GitHub
integration (no PR/issue/branch tracking). It exists to prove the
deploy-regression and flaky-test detection pipelines built for GitHub
actually generalize to a second CI/CD provider, by reusing the exact same
detector/reasoner/ticketing/history paths
(backend.services.enterprise_github_integration._check_deploy_regression,
backend.services.enterprise_flaky_test_detector.handle_ci_completion)
rather than building parallel ones.

Wired from: POST /api/gitlab/webhook, on:
  - a "deployment" event whose status is "success" -> deploy regression
  - a "pipeline" event (any status change) -> flaky test detection

GitLab's webhook model differs from GitHub's in one way worth noting:
Signing is a plain shared-secret string sent verbatim in the
X-Gitlab-Token header (constant-time compared), not an HMAC signature —
GitLab does send the secret itself, unlike GitHub's proof-of-knowledge
scheme, so this must never be logged or echoed back.

Root-cause reasoning (backend.services.enterprise_deploy_root_cause_reasoner)
dispatches its diff-fetch by ctx["source"], so a gitlab_webhook-sourced ctx
fetches via GitLabCIConnector.get_commit_with_diff (backend/connectors/gitlab_ci.py)
instead of GitHub's connector — full parity with the GitHub path, not a
degraded fallback.

Flaky-test granularity note: GitLab pipelines don't have a "name" the way
GitHub Actions workflows do (a pipeline is just "this project's CI run",
defined by .gitlab-ci.yml) — workflow_name is the fixed string "pipeline"
for every GitLab-sourced occurrence, unlike GitHub's real per-workflow
names. GitLab jobs also don't have GitHub's per-step breakdown, so
evidence is job-level only (no failed_steps).
"""
from __future__ import annotations

import hmac
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        elif verified and payload.get("object_kind") == "pipeline":
            await _process_pipeline_event(payload)

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
        "project_id": payload.get("project", {}).get("id"),
        "sender": payload.get("user", {}).get("username", ""),
        "deployment_id": deployment_id,
        "environment": payload.get("environment", ""),
        "deployment_state": status,
        "deployment_description": payload.get("commit_title", ""),
        "deployment_log_url": payload.get("deployable_url", ""),
        "commit_sha": payload.get("short_sha", ""),
    }

    await _check_deploy_regression(ctx)


async def _process_pipeline_event(payload: Dict[str, Any]) -> Optional["asyncio.Task"]:
    """Translate a GitLab "Pipeline Hook" payload and hand it to the
    shared, provider-agnostic flaky-test state machine
    (enterprise_flaky_test_detector.handle_ci_completion).

    Runs as a background task rather than being awaited inline — same
    reasoning as GitHub's _check_flaky_test: the retry-completion path can
    involve an LLM call plus a Jira API call, either of which can exceed
    GitLab's webhook delivery timeout on its own.
    """
    import asyncio

    from backend.services.enterprise_flaky_test_detector import handle_ci_completion

    project = payload.get("project", {})
    repo_full_name = project.get("path_with_namespace", "")
    project_id = project.get("id")
    attrs = payload.get("object_attributes", {})
    pipeline_id = attrs.get("id")
    status = attrs.get("status", "")

    if not repo_full_name or not project_id or not pipeline_id:
        return None

    conclusion = {"success": "success", "failed": "failure"}.get(status, status)
    if conclusion not in ("success", "failure"):
        return None

    workflow_name = "pipeline"  # see module docstring — GitLab pipelines aren't named like GitHub workflows
    run_key = f"gl:{repo_full_name}:{pipeline_id}"
    ctx = {
        "source": "gitlab_webhook",
        "event_type": "pipeline",
        "timestamp": _now(),
        "repo_full_name": repo_full_name,
        "pipeline_id": pipeline_id,
    }

    def _gitlab_connector():
        from backend.connectors.registry import connector_registry
        return connector_registry.get("gitlab_ci")

    async def trigger_retry() -> bool:
        gl = _gitlab_connector()
        if gl is None:
            return False
        await gl.retry_pipeline(project_id, pipeline_id)
        return True

    async def fetch_evidence() -> List[Dict[str, Any]]:
        gl = _gitlab_connector()
        if gl is None:
            return []
        jobs = await gl.list_jobs(project_id, pipeline_id)
        return [
            {
                "attempt": 1,
                "job_name": job.get("name", "unknown"),
                "conclusion": {"success": "success", "failed": "failure"}.get(job.get("status"), job.get("status", "unknown")),
                "failed_steps": [],  # GitLab jobs have no per-step breakdown, unlike GitHub Actions
            }
            for job in jobs
            if job.get("status") in ("success", "failed")
        ]

    return asyncio.create_task(
        handle_ci_completion(repo_full_name, workflow_name, run_key, conclusion, ctx, trigger_retry, fetch_evidence)
    )


gitlab_webhook_receiver = GitLabWebhookReceiver()
