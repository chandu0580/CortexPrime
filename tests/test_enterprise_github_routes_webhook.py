"""
Tests for the real /api/github/webhook route — specifically that the
signing secret is server-side configuration (an env var), never read
from the incoming request. A genuine GitHub webhook delivery proves it
knows the secret via the X-Hub-Signature-256 HMAC; it never transmits
the secret itself, so trusting a client-supplied secret header would
make signature verification meaningless.

Phase 11.1 (ADR-121) changed the contract: an unverifiable delivery is
REFUSED (401), and a deployment with no secret configured refuses every
delivery (503) instead of accepting it as "unverified". Before this phase
both cases returned 200 with ``verified: false`` and the delivery was
recorded and emitted anyway.

Uses a minimal standalone app mounting just the webhook router, avoiding
the full backend.main lifespan (heavy, and irrelevant to this route).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_github_routes import webhook_router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(webhook_router)
    return TestClient(app)


def _signed_body(secret: str, payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, sig


@pytest.fixture(autouse=True)
def _quiet_audit():
    with patch("backend.safety.audit_logger.audit_logger.log"):
        yield


class TestWebhookSecretIsServerSide:
    def test_no_server_secret_refuses_every_delivery(self, monkeypatch):
        # No real secret configured server-side: the deployment cannot verify,
        # so it must not accept -- whatever the caller signed with.
        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        body, sig = _signed_body("attacker-supplied-secret", {"repository": {"full_name": "org/repo"}, "sender": {}})

        client = _make_client()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": sig,
                # An attacker who controls the request can set whatever
                # header they like -- it must never be trusted as the secret.
                "x-hub-secret": "attacker-supplied-secret",
            },
        )
        assert resp.status_code == 503

    def test_verifies_using_server_side_env_secret(self, monkeypatch):
        real_secret = "the-real-server-side-secret"
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", real_secret)
        body, sig = _signed_body(real_secret, {"repository": {"full_name": "org/repo"}, "sender": {}})

        client = _make_client()
        with patch("backend.services.enterprise_github_integration.github_integration.receive_webhook",
                   new_callable=AsyncMock,
                   return_value={"delivery_id": "d", "event_type": "push", "verified": True,
                                 "parsed": {"raw": {}}}):
            resp = client.post(
                "/api/github/webhook",
                content=body,
                headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 200
        assert resp.json()["verified"] is True
        assert resp.json()["ingress"]["auth_kind"] == "github_hmac"

    def test_wrong_signature_against_real_server_secret_is_refused(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "the-real-server-side-secret")
        body, _ = _signed_body("the-real-server-side-secret", {"repository": {"full_name": "org/repo"}, "sender": {}})

        client = _make_client()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=not-the-real-signature"},
        )
        assert resp.status_code == 401

    def test_client_supplied_secret_cannot_forge_verification(self, monkeypatch):
        # Server has a real secret; an attacker who picks their own secret AND
        # signs with it must still fail, because the server never adopts a
        # client-supplied secret to verify against.
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "the-real-server-side-secret")
        forged_secret = "whatever-i-want"
        body, sig = _signed_body(forged_secret, {"repository": {"full_name": "org/repo"}, "sender": {}})

        client = _make_client()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": sig,
                "x-hub-secret": forged_secret,
            },
        )
        assert resp.status_code == 401

    def test_unverified_delivery_is_never_processed(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "the-real-server-side-secret")
        body, _ = _signed_body("other", {"repository": {"full_name": "org/repo"}, "sender": {}})
        with patch("backend.services.enterprise_github_integration.github_integration.receive_webhook",
                   new_callable=AsyncMock) as receive:
            _make_client().post("/api/github/webhook", content=body,
                                headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=00"})
        receive.assert_not_awaited()
