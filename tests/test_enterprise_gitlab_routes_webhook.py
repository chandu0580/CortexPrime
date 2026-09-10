"""
Tests for the real /api/gitlab/webhook route — specifically that the
webhook token is server-side configuration (an env var), never read
from the incoming request. Unlike GitHub's HMAC proof-of-knowledge
scheme, GitLab sends the token itself in X-Gitlab-Token, so trusting a
client-supplied token header would make verification meaningless in a
different way: an attacker could just supply whatever value the server
happens to check against unless that value only ever comes from our own
environment.

Phase 11.1 (ADR-121): an unverifiable delivery is REFUSED (401) and a
deployment with no token configured refuses every delivery (503); the
delivery-history read needs a verified access token.

Uses a minimal standalone app mounting just these routers, avoiding the
full backend.main lifespan (heavy, and irrelevant to this route). Each
test gets its own isolated delivery-store file so it never touches the
real dev data.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-pytest-suite-do-not-use-in-prod")

from backend.api.enterprise_gitlab_routes import router, webhook_router  # noqa: E402
from backend.auth.jwt_handler import create_access_token  # noqa: E402
from backend.services.enterprise_gitlab_integration import GitLabWebhookReceiver  # noqa: E402


@pytest.fixture
def isolated_receiver():
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "gitlab_webhook_deliveries.json"
        receiver = GitLabWebhookReceiver()
        receiver._delivery_store = receiver._delivery_store.__class__(file_path=temp_path)
        with patch("backend.api.enterprise_gitlab_routes.gitlab_webhook_receiver", receiver):
            yield receiver


@pytest.fixture(autouse=True)
def _quiet_audit_and_blacklist():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with patch("backend.safety.audit_logger.audit_logger.log"), \
         patch("backend.auth.token_blacklist.TokenBlacklist._get_redis",
               new_callable=AsyncMock, return_value=mock_redis):
        yield


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(webhook_router)
    app.include_router(router)
    return TestClient(app)


def _body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id='op', role='operator')}"}


class TestWebhookTokenIsServerSide:
    def test_no_server_token_refuses_every_delivery(self, monkeypatch, isolated_receiver):
        monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)
        payload = {"object_kind": "deployment", "status": "running", "project": {"path_with_namespace": "group/proj"}}

        client = _make_client()
        resp = client.post(
            "/api/gitlab/webhook",
            content=_body(payload),
            headers={"X-Gitlab-Event": "Deployment Hook", "X-Gitlab-Token": "attacker-supplied-token"},
        )
        assert resp.status_code == 503
        assert isolated_receiver.get_recent_deliveries(10) == []

    def test_verifies_using_server_side_env_token(self, monkeypatch, isolated_receiver):
        real_secret = "the-real-server-side-token"
        monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", real_secret)
        payload = {"object_kind": "deployment", "status": "running", "project": {"path_with_namespace": "group/proj"}}

        client = _make_client()
        resp = client.post(
            "/api/gitlab/webhook",
            content=_body(payload),
            headers={"X-Gitlab-Event": "Deployment Hook", "X-Gitlab-Token": real_secret},
        )
        assert resp.status_code == 200
        assert resp.json()["verified"] is True
        assert resp.json()["ingress"]["auth_kind"] == "gitlab_token"

    def test_wrong_token_against_real_server_secret_is_refused(self, monkeypatch, isolated_receiver):
        monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "the-real-server-side-token")
        payload = {"object_kind": "deployment", "status": "running", "project": {"path_with_namespace": "group/proj"}}

        client = _make_client()
        resp = client.post(
            "/api/gitlab/webhook",
            content=_body(payload),
            headers={"X-Gitlab-Event": "Deployment Hook", "X-Gitlab-Token": "not-the-real-token"},
        )
        assert resp.status_code == 401
        # Refused before the receiver saw it: nothing recorded.
        assert isolated_receiver.get_recent_deliveries(10) == []


class TestWebhookDeliveryHistory:
    def test_list_webhooks_returns_recorded_deliveries(self, monkeypatch, isolated_receiver):
        monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "s3cr3t")
        payload = {"object_kind": "deployment", "status": "running", "project": {"path_with_namespace": "group/proj"}}
        client = _make_client()
        client.post(
            "/api/gitlab/webhook",
            content=_body(payload),
            headers={"X-Gitlab-Event": "Deployment Hook", "X-Gitlab-Token": "s3cr3t"},
        )

        assert client.get("/api/gitlab/webhooks").status_code == 401
        resp = client.get("/api/gitlab/webhooks", headers=_auth())
        assert resp.status_code == 200
        webhooks = resp.json()["webhooks"]
        assert len(webhooks) == 1
        assert webhooks[0]["repository"] == "group/proj"
        assert webhooks[0]["verified"] is True

    def test_duplicate_delivery_id_is_deduplicated(self, monkeypatch, isolated_receiver):
        monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "s3cr3t")
        payload = {"object_kind": "deployment", "status": "running", "project": {"path_with_namespace": "group/proj"}}
        client = _make_client()
        headers = {
            "X-Gitlab-Event": "Deployment Hook",
            "X-Gitlab-Token": "s3cr3t",
            "X-Gitlab-Event-UUID": "same-delivery-id",
        }
        first = client.post("/api/gitlab/webhook", content=_body(payload), headers=headers)
        second = client.post("/api/gitlab/webhook", content=_body(payload), headers=headers)

        assert first.json()["verified"] is True
        assert second.json()["status"] == "duplicate"
