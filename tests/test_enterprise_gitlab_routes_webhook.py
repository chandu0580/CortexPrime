"""
Tests for the real /api/gitlab/webhook route — specifically that the
webhook token is server-side configuration (an env var), never read
from the incoming request. Unlike GitHub's HMAC proof-of-knowledge
scheme, GitLab sends the token itself in X-Gitlab-Token, so trusting a
client-supplied token header would make verification meaningless in a
different way: an attacker could just supply whatever value the server
happens to check against unless that value only ever comes from our own
environment.

Uses a minimal standalone app mounting just this router, avoiding the
full backend.main lifespan (heavy, and irrelevant to this route). Each
test gets its own isolated delivery-store file so it never touches the
real dev data.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_gitlab_routes import router
from backend.services.enterprise_gitlab_integration import GitLabWebhookReceiver


@pytest.fixture
def isolated_receiver():
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "gitlab_webhook_deliveries.json"
        receiver = GitLabWebhookReceiver()
        receiver._delivery_store = receiver._delivery_store.__class__(file_path=temp_path)
        with patch("backend.api.enterprise_gitlab_routes.gitlab_webhook_receiver", receiver):
            yield receiver


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


class TestWebhookTokenIsServerSide:
    def test_ignores_token_when_none_configured_server_side(self, monkeypatch, isolated_receiver):
        monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)
        payload = {"object_kind": "deployment", "status": "running", "project": {"path_with_namespace": "group/proj"}}

        client = _make_client()
        resp = client.post(
            "/api/gitlab/webhook",
            content=_body(payload),
            headers={"X-Gitlab-Event": "Deployment Hook", "X-Gitlab-Token": "attacker-supplied-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["verified"] is False

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

    def test_wrong_token_against_real_server_secret_fails(self, monkeypatch, isolated_receiver):
        monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "the-real-server-side-token")
        payload = {"object_kind": "deployment", "status": "running", "project": {"path_with_namespace": "group/proj"}}

        client = _make_client()
        resp = client.post(
            "/api/gitlab/webhook",
            content=_body(payload),
            headers={"X-Gitlab-Event": "Deployment Hook", "X-Gitlab-Token": "not-the-real-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["verified"] is False


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

        resp = client.get("/api/gitlab/webhooks")
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
