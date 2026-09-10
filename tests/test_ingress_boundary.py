"""Phase 11.1 (ADR-121): the ingestion trust boundary.

Webhooks are verified before they are parsed (401 wrong, 503 unconfigured);
token-authenticated ingestion establishes tenant from the token, bounds the
body, stamps a canonical event identity and audits every decision without the
payload; provider-mutating V1 routes sit behind the legacy execution guard.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-pytest-suite-do-not-use-in-prod")

from backend.api.legacy_execution_boundary import LEGACY_EXECUTION_FLAG  # noqa: E402
from backend.auth.jwt_handler import create_access_token  # noqa: E402
from backend.safety.auth_perimeter import V1_TENANT_ENV  # noqa: E402
from backend.safety.ingress_boundary import (  # noqa: E402
    INGRESS_MAX_BODY_ENV,
    TRUST_UNTRUSTED_EXTERNAL,
    IngressEnvelope,
    IngressPrincipal,
)


@pytest.fixture(autouse=True)
def _no_blacklist():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with patch("backend.auth.token_blacklist.TokenBlacklist._get_redis",
               new_callable=AsyncMock, return_value=mock_redis):
        yield


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(V1_TENANT_ENV, raising=False)
    monkeypatch.delenv(INGRESS_MAX_BODY_ENV, raising=False)
    monkeypatch.delenv(LEGACY_EXECUTION_FLAG, raising=False)
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)


@pytest.fixture
def audit():
    with patch("backend.safety.audit_logger.audit_logger.log") as alog:
        yield alog


@pytest.fixture
def live_tenants():
    # require_user asks the durable tenant store whether a token's tenant is
    # live; here every tenant named by a token is live, so refusals are the
    # boundary's and nothing else's.
    with patch("backend.auth.tenants.resolve_tenant", return_value=(object(), None)):
        yield


def _bearer(user: str, tenant: str | None = None) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id=user, role='operator', tenant_id=tenant)}"}


def _actions(alog: AsyncMock) -> list:
    return [c.kwargs["action"] for c in alog.call_args_list]


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

class TestEnvelope:
    P = IngressPrincipal(principal_id="svc", tenant_id="t-a", auth_kind="jwt", source="x")

    def test_identity_is_canonical_and_trust_is_fixed(self):
        a = IngressEnvelope.build(source="s", event_type="pod", payload={"b": 1, "a": 2},
                                  principal=self.P, event_id="e1")
        b = IngressEnvelope.build(source="s", event_type="pod", payload={"a": 2, "b": 1},
                                  principal=self.P, event_id="e1")
        assert a.identity == b.identity and a.payload_digest == b.payload_digest
        assert a.trust == TRUST_UNTRUSTED_EXTERNAL
        assert a.to_dict()["delivery"] == "at-least-once"

    def test_modified_redelivery_is_distinguishable(self):
        a = IngressEnvelope.build(source="s", event_type="pod", payload={"a": 1}, principal=self.P, event_id="e1")
        b = IngressEnvelope.build(source="s", event_type="pod", payload={"a": 2}, principal=self.P, event_id="e1")
        assert a.identity == b.identity and a.payload_digest != b.payload_digest

    def test_tenant_comes_from_the_principal_never_the_payload(self):
        env = IngressEnvelope.build(source="s", event_type="pod",
                                    payload={"tenant_id": "t-evil", "approved": True, "role": "admin"},
                                    principal=self.P)
        assert env.tenant_id == "t-a"
        assert "approved" not in env.to_dict() and "role" not in env.to_dict()

    def test_missing_event_id_falls_back_to_payload_digest(self):
        env = IngressEnvelope.build(source="s", event_type="pod", payload={"a": 1}, principal=self.P)
        assert env.event_id == env.payload_digest[:32]


# ---------------------------------------------------------------------------
# GitHub webhook
# ---------------------------------------------------------------------------

def _github_app() -> TestClient:
    from backend.api.enterprise_github_routes import router, webhook_router

    app = FastAPI()
    app.include_router(webhook_router)
    app.include_router(router)
    return TestClient(app)


def _signed(secret: str, payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    return body, "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestGitHubWebhook:
    PAYLOAD = {"repository": {"full_name": "org/repo"}, "sender": {"login": "x"}, "ref": "refs/heads/main"}

    def test_unconfigured_secret_refuses_503_and_never_processes(self, audit):
        body, sig = _signed("anything", self.PAYLOAD)
        with patch("backend.services.enterprise_github_integration.github_integration.receive_webhook",
                   new_callable=AsyncMock) as receive:
            r = _github_app().post("/api/github/webhook", content=body,
                                   headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig,
                                            "X-GitHub-Delivery": "d-1"})
        assert r.status_code == 503
        receive.assert_not_awaited()
        assert _actions(audit) == ["ingress.rejected"]
        meta = audit.call_args.kwargs["metadata"]
        assert meta["event_id"] == "d-1" and "org/repo" not in json.dumps(meta)

    def test_missing_signature_is_401(self, monkeypatch, audit):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "real")
        with patch("backend.services.enterprise_github_integration.github_integration.receive_webhook",
                   new_callable=AsyncMock) as receive:
            r = _github_app().post("/api/github/webhook", content=json.dumps(self.PAYLOAD).encode(),
                                   headers={"X-GitHub-Event": "push"})
        assert r.status_code == 401
        receive.assert_not_awaited()

    def test_wrong_signature_is_401(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "real")
        body, _ = _signed("real", self.PAYLOAD)
        r = _github_app().post("/api/github/webhook", content=body,
                               headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=deadbeef"})
        assert r.status_code == 401

    def test_client_chosen_secret_cannot_verify(self, monkeypatch):
        # Signs with a secret of its own choosing and announces it in a header.
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "real")
        body, sig = _signed("attacker", self.PAYLOAD)
        r = _github_app().post("/api/github/webhook", content=body,
                               headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig,
                                        "x-hub-secret": "attacker"})
        assert r.status_code == 401

    def test_altered_payload_with_original_signature_is_401(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "real")
        _, sig = _signed("real", self.PAYLOAD)
        altered = json.dumps({**self.PAYLOAD, "ref": "refs/heads/evil"}).encode()
        r = _github_app().post("/api/github/webhook", content=altered,
                               headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig})
        assert r.status_code == 401

    def test_body_supplied_secret_route_is_gone(self):
        r = _github_app().post("/api/github/webhook/payload",
                               json={"payload": {}, "secret": "x", "signature": "y"})
        assert r.status_code in (404, 405, 401)

    def test_verified_delivery_is_accepted_with_envelope_and_audited(self, monkeypatch, audit):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "real")
        monkeypatch.setenv(V1_TENANT_ENV, "tenant-a")
        body, sig = _signed("real", self.PAYLOAD)
        with patch("backend.services.enterprise_github_integration.github_integration.receive_webhook",
                   new_callable=AsyncMock,
                   return_value={"delivery_id": "d-9", "event_type": "push", "verified": True,
                                 "parsed": {"raw": self.PAYLOAD}}):
            r = _github_app().post("/api/github/webhook", content=body,
                                   headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig,
                                            "X-GitHub-Delivery": "d-9"})
        assert r.status_code == 200
        ingress = r.json()["ingress"]
        assert ingress["tenant_id"] == "tenant-a" and ingress["auth_kind"] == "github_hmac"
        assert ingress["event_id"] == "d-9" and ingress["trust"] == "untrusted_external"
        assert _actions(audit) == ["ingress.accepted"]
        assert "org/repo" not in json.dumps(audit.call_args.kwargs["metadata"])

    def test_webhook_tenant_is_unbound_when_undeclared_not_invented(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "real")
        body, sig = _signed("real", self.PAYLOAD)
        with patch("backend.services.enterprise_github_integration.github_integration.receive_webhook",
                   new_callable=AsyncMock, return_value={"delivery_id": "d", "event_type": "push",
                                                         "verified": True, "parsed": {"raw": {}}}):
            r = _github_app().post("/api/github/webhook", content=body,
                                   headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig})
        assert r.json()["ingress"]["tenant_id"] == "single-tenant-unbound"

    def test_replayed_delivery_is_deduplicated_by_the_receiver(self, monkeypatch, tmp_path):
        from backend.services.enterprise_github_integration import WebhookDeliveryStore, WebhookReceiver

        receiver = WebhookReceiver()
        receiver._delivery_store = WebhookDeliveryStore(file_path=tmp_path / "d.json")
        body, sig = _signed("real", self.PAYLOAD)
        headers = {"X-GitHub-Event": "push", "X-Hub-Signature-256": sig, "X-GitHub-Delivery": "same"}
        import asyncio

        loop = asyncio.new_event_loop()
        with patch("backend.services.enterprise_github_integration._emit", new_callable=AsyncMock):
            first = loop.run_until_complete(receiver.receive(body, headers, "real"))
            second = loop.run_until_complete(receiver.receive(body, headers, "real"))
        assert first["verified"] is True and second["status"] == "duplicate"

    def test_operator_routes_require_a_token(self):
        assert _github_app().get("/api/github/webhooks").status_code == 401
        assert _github_app().post("/api/github/launch-mission",
                                  json={"event_type": "push", "payload": {}}).status_code == 401

    def test_mission_launch_is_behind_the_legacy_guard(self):
        r = _github_app().post("/api/github/launch-mission", json={"event_type": "push", "payload": {}},
                               headers=_bearer("op"))
        assert r.status_code == 503 and "V1 execution surface" in r.json()["detail"]


# ---------------------------------------------------------------------------
# GitLab webhook
# ---------------------------------------------------------------------------

def _gitlab_app() -> TestClient:
    from backend.api.enterprise_gitlab_routes import router, webhook_router

    app = FastAPI()
    app.include_router(webhook_router)
    app.include_router(router)
    return TestClient(app)


class TestGitLabWebhook:
    def test_unconfigured_is_503(self):
        r = _gitlab_app().post("/api/gitlab/webhook", json={"object_kind": "push"},
                               headers={"X-Gitlab-Token": "anything"})
        assert r.status_code == 503

    def test_wrong_or_missing_token_is_401(self, monkeypatch):
        monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "real")
        c = _gitlab_app()
        assert c.post("/api/gitlab/webhook", json={"object_kind": "push"},
                      headers={"X-Gitlab-Token": "wrong"}).status_code == 401
        assert c.post("/api/gitlab/webhook", json={"object_kind": "push"}).status_code == 401

    def test_verified_is_accepted(self, monkeypatch, audit):
        monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "real")
        with patch("backend.api.enterprise_gitlab_routes.gitlab_webhook_receiver.receive",
                   new_callable=AsyncMock, return_value={"delivery_id": "u-1", "event_type": "Push Hook",
                                                         "verified": True, "payload": {}}):
            r = _gitlab_app().post("/api/gitlab/webhook", json={"object_kind": "push"},
                                   headers={"X-Gitlab-Token": "real", "X-Gitlab-Event-UUID": "u-1"})
        assert r.status_code == 200 and r.json()["ingress"]["auth_kind"] == "gitlab_token"
        assert _actions(audit) == ["ingress.accepted"]

    def test_history_requires_a_token(self):
        assert _gitlab_app().get("/api/gitlab/webhooks").status_code == 401


# ---------------------------------------------------------------------------
# Token-authenticated ingestion (infrastructure)
# ---------------------------------------------------------------------------

def _infra_app() -> TestClient:
    from backend.api.enterprise_infrastructure_routes import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestInfrastructureIngestion:
    def test_unauthenticated_ingest_is_401(self):
        c = _infra_app()
        assert c.post("/api/infrastructure/ingest/pod", json={"payload": {"name": "p"}}).status_code == 401
        assert c.post("/api/infrastructure/webhook/kubernetes", json={"kind": "Pod"}).status_code == 401
        assert c.post("/api/infrastructure/otel/v1/traces", content=b"{}").status_code == 401
        assert c.get("/api/infrastructure/pods").status_code == 401

    def test_single_operator_ingest_is_accepted_with_envelope(self, audit):
        with patch("backend.api.enterprise_infrastructure_routes.infrastructure_intelligence.ingest_pod_event",
                   new_callable=AsyncMock, return_value={"id": "p-1"}):
            r = _infra_app().post("/api/infrastructure/ingest/pod",
                                  json={"payload": {"id": "p-1", "name": "p"}}, headers=_bearer("collector"))
        assert r.status_code == 200
        ingress = r.json()["ingress"]
        assert ingress["principal_id"] == "collector" and ingress["tenant_id"] is None
        assert ingress["event_id"] == "p-1" and ingress["source"] == "infrastructure.ingest"
        assert _actions(audit) == ["ingress.accepted"]
        assert "name" not in json.dumps(audit.call_args.kwargs["metadata"]).replace("event_type", "")

    def test_tenant_bearing_token_is_refused_when_undeclared(self, live_tenants, audit):
        r = _infra_app().post("/api/infrastructure/ingest/pod", json={"payload": {}},
                              headers=_bearer("collector", "tenant-a"))
        assert r.status_code == 403 and V1_TENANT_ENV in r.json()["detail"]
        assert _actions(audit) == ["ingress.rejected"]

    def test_foreign_tenant_is_refused_when_declared(self, monkeypatch, live_tenants, audit):
        monkeypatch.setenv(V1_TENANT_ENV, "tenant-a")
        c = _infra_app()
        with patch("backend.api.enterprise_infrastructure_routes.infrastructure_intelligence.ingest_pod_event",
                   new_callable=AsyncMock, return_value={}):
            own = c.post("/api/infrastructure/ingest/pod", json={"payload": {}}, headers=_bearer("a", "tenant-a"))
            other = c.post("/api/infrastructure/ingest/pod", json={"payload": {}}, headers=_bearer("b", "tenant-b"))
        assert own.status_code == 200 and own.json()["ingress"]["tenant_id"] == "tenant-a"
        assert other.status_code == 403
        assert _actions(audit) == ["ingress.accepted", "ingress.rejected"]

    def test_oversized_payload_is_413(self, monkeypatch, audit):
        monkeypatch.setenv(INGRESS_MAX_BODY_ENV, "64")
        big = {"payload": {"blob": "x" * 200}}
        r = _infra_app().post("/api/infrastructure/ingest/pod", json=big, headers=_bearer("collector"))
        assert r.status_code == 413
        assert _actions(audit) == ["ingress.rejected"]
        raw = _infra_app().post("/api/infrastructure/otel/v1/traces", content=b"x" * 200,
                                headers={**_bearer("collector"), "content-type": "application/json"})
        assert raw.status_code == 413

    def test_payload_schema_is_enforced(self):
        r = _infra_app().post("/api/infrastructure/ingest/pod", json={"payload": "not-an-object"},
                              headers=_bearer("collector"))
        assert r.status_code == 422

    def test_provider_mutations_are_behind_the_legacy_guard(self):
        c = _infra_app()
        h = _bearer("op")
        for path, body in [
            ("/api/infrastructure/terraform/apply", {"plan_id": "p"}),
            ("/api/infrastructure/terraform/destroy", {}),
            ("/api/infrastructure/terraform/init", {}),
            ("/api/infrastructure/terraform/plan", {}),
            ("/api/infrastructure/terraform/workspaces/select", {"name": "prod"}),
            ("/api/infrastructure/argocd/applications/app/sync", {}),
            ("/api/infrastructure/argocd/applications/app/rollback", {"revision_id": 3}),
            ("/api/infrastructure/argocd/applications/app/refresh", {}),
        ]:
            r = c.post(path, json=body, headers=h)
            assert r.status_code == 503, (path, r.status_code, r.text)
            assert "V1 execution surface" in r.json()["detail"]
            assert c.post(path, json=body).status_code == 401, path

    def test_legacy_surfaces_are_inventoried(self):
        from backend.api.legacy_execution_boundary import LEGACY_EXECUTION_SURFACES

        routes = " ".join(s.route for s in LEGACY_EXECUTION_SURFACES)
        for needle in ("terraform", "argocd", "launch-mission", "approval-center"):
            assert needle in routes
        assert all(s.gated for s in LEGACY_EXECUTION_SURFACES)


# ---------------------------------------------------------------------------
# Other fenced V1 surfaces
# ---------------------------------------------------------------------------

class TestOtherSurfaces:
    def test_triggers_and_incidents_require_a_token(self):
        from backend.api.autonomous_trigger_routes import router as triggers
        from backend.api.enterprise_incidents_routes import router as incidents

        app = FastAPI()
        app.include_router(triggers)
        app.include_router(incidents)
        c = TestClient(app)
        assert c.get("/api/triggers").status_code == 401
        assert c.post("/api/triggers/policies", json={"name": "p"}).status_code == 401
        assert c.post("/api/triggers/simulate", json={}).status_code == 401
        assert c.get("/api/incidents").status_code == 401

    def test_approval_centre_mutations_are_fenced_and_identity_bound(self, monkeypatch):
        from backend.api.approval_center_routes import router

        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)
        h = _bearer("alice")
        # Reads: authenticated only.
        assert c.get("/api/approval-center/policies").status_code == 401
        assert c.get("/api/approval-center/policies", headers=h).status_code == 200
        # Mutations refuse by default (second approval authority, ADR-121).
        r = c.post("/api/approval-center/workflows/w1/approve?role=admin&approver=alice", headers=h)
        assert r.status_code == 503
        # With the migration flag set, the approver is the authenticated principal, never a parameter.
        monkeypatch.setenv(LEGACY_EXECUTION_FLAG, "1")
        r = c.post("/api/approval-center/workflows/w1/approve?role=admin&approver=bob", headers=h)
        assert r.status_code == 403 and "authenticated principal" in r.json()["detail"]
        r = c.post("/api/approval-center/workflows/w1/break-glass?role=admin&reason=x&overridden_by=bob", headers=h)
        assert r.status_code == 403
        # As alice, the engine is reached (and refuses an unknown workflow with 400).
        r = c.post("/api/approval-center/workflows/w1/approve?role=admin&approver=alice", headers=h)
        assert r.status_code == 400
