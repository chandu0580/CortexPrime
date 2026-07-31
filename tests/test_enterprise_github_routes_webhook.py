"""
Tests for the real /api/github/webhook route — specifically that the
signing secret is server-side configuration (an env var), never read
from the incoming request. A genuine GitHub webhook delivery proves it
knows the secret via the X-Hub-Signature-256 HMAC; it never transmits
the secret itself, so trusting a client-supplied secret header would
make signature verification meaningless.

Uses a minimal standalone app mounting just this router, avoiding the
full backend.main lifespan (heavy, and irrelevant to this route).
"""
from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.enterprise_github_routes import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _signed_body(secret: str, payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, sig


class TestWebhookSecretIsServerSide:
    def test_ignores_secret_supplied_in_request_header(self, monkeypatch):
        # No real secret configured server-side.
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
                # header they like — it must never be trusted as the secret.
                "x-hub-secret": "attacker-supplied-secret",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["verified"] is False

    def test_verifies_using_server_side_env_secret(self, monkeypatch):
        real_secret = "the-real-server-side-secret"
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", real_secret)
        body, sig = _signed_body(real_secret, {"repository": {"full_name": "org/repo"}, "sender": {}})

        client = _make_client()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        assert resp.json()["verified"] is True

    def test_wrong_signature_against_real_server_secret_fails(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "the-real-server-side-secret")
        body, _ = _signed_body("the-real-server-side-secret", {"repository": {"full_name": "org/repo"}, "sender": {}})

        client = _make_client()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=not-the-real-signature"},
        )
        assert resp.status_code == 200
        assert resp.json()["verified"] is False

    def test_client_supplied_secret_cannot_forge_verification(self, monkeypatch):
        # Server has no real secret configured — an attacker who both picks
        # their own secret AND signs with it must still fail, because the
        # server must never adopt a client-supplied secret to verify against.
        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
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
        assert resp.status_code == 200
        assert resp.json()["verified"] is False
