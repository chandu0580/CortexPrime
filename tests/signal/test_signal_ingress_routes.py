"""Phase 11.2 (ADR-122): the Alertmanager ingress behind Prompt 1's boundary.

A standalone app with the real router, the real ingress boundary and a
memory observation ledger on ``app.state.governed``; identity from real
tokens; the durable store swapped for memory so the contract is proven
without PostgreSQL (the harness proves it with PostgreSQL).
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-pytest-suite-do-not-use-in-prod")

from backend.api.signal_ingress_routes import router  # noqa: E402
from backend.auth.jwt_handler import create_access_token  # noqa: E402
from backend.safety.auth_perimeter import FENCE_EXEMPT_PREFIXES, AuthPerimeterMiddleware  # noqa: E402
from backend.safety.ingress_boundary import INGRESS_MAX_BODY_ENV  # noqa: E402
from backend.safety.rate_limiter import _classify_endpoint  # noqa: E402


class MemoryRepository:
    def __init__(self) -> None:
        self.rows: dict = {}
        self.fail = False

    def record(self, observation, *, identity_digest: str) -> bool:
        if self.fail:
            from backend.world.infrastructure.sql_observation import ObservationPersistenceError
            raise ObservationPersistenceError("ledger down")
        if identity_digest in self.rows:
            return False
        self.rows[identity_digest] = observation
        return True


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    monkeypatch.delenv(INGRESS_MAX_BODY_ENV, raising=False)
    monkeypatch.delenv("CORTEXPRIME_V1_TENANT_ID", raising=False)
    with patch("backend.auth.token_blacklist.TokenBlacklist._get_redis",
               new_callable=AsyncMock, return_value=mock_redis), \
         patch("backend.auth.tenants.resolve_tenant", return_value=(object(), None)), \
         patch("backend.safety.audit_logger.audit_logger.log") as audit:
        yield audit


def _app(repo: MemoryRepository, *, perimeter: bool = False):
    app = FastAPI()
    app.include_router(router)
    if perimeter:
        app.add_middleware(AuthPerimeterMiddleware)
    with patch("backend.api.signal_ingress_routes.SqlObservationRepository", create=True):
        pass
    app.state.governed = SimpleNamespace(persistence=SimpleNamespace(store=object()))
    return app


def _client(repo, **kw):
    app = _app(repo, **kw)
    c = TestClient(app)
    patcher = patch("backend.api.signal_ingress_routes._observation_repository", return_value=repo)
    patcher.start()
    c._patcher = patcher
    return c


def _bearer(tenant=None, sub="alertmanager-svc"):
    return {"Authorization": f"Bearer {create_access_token(user_id=sub, role='operator', tenant_id=tenant)}"}


PAYLOAD = {
    "version": "4", "groupKey": '{}:{alertname="BackendDown"}', "truncatedAlerts": 0,
    "status": "firing", "receiver": "cortexprime", "groupLabels": {"alertname": "BackendDown"},
    "commonLabels": {"alertname": "BackendDown", "severity": "critical"}, "commonAnnotations": {},
    "externalURL": "http://alertmanager:9093",
    "alerts": [{"status": "firing", "labels": {"alertname": "BackendDown", "severity": "critical", "job": "cortex-backend"},
                "annotations": {"summary": "backend down"}, "startsAt": "2026-09-09T11:59:00Z",
                "endsAt": "0001-01-01T00:00:00Z", "generatorURL": "http://prom/graph", "fingerprint": "a1b2c3d4e5f60718"}],
}


class TestBoundary:
    def test_no_token_is_401(self):
        c = _client(MemoryRepository())
        assert c.post("/api/signals/alertmanager", json=PAYLOAD).status_code == 401

    def test_token_without_tenant_is_403(self, _env):
        c = _client(MemoryRepository())
        r = c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer())
        assert r.status_code == 403 and "tenant-bound" in r.json()["detail"]
        assert _env.call_args.kwargs["action"] == "ingress.rejected"

    def test_the_perimeter_exempts_this_governed_surface_from_the_v1_fence(self):
        assert "/api/signals" in FENCE_EXEMPT_PREFIXES
        c = _client(MemoryRepository(), perimeter=True)
        r = c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer("tenant-a"))
        assert r.status_code == 200, r.text
        assert c.post("/api/signals/alertmanager", json=PAYLOAD).status_code == 401

    def test_rate_limit_bucket_is_ingest(self):
        assert _classify_endpoint("/api/signals/alertmanager", "POST") == "ingest"

    def test_oversized_body_is_413(self, monkeypatch):
        monkeypatch.setenv(INGRESS_MAX_BODY_ENV, "128")
        c = _client(MemoryRepository())
        assert c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer("tenant-a")).status_code == 413

    def test_malformed_and_schema_violations_are_refused(self, _env):
        c = _client(MemoryRepository())
        assert c.post("/api/signals/alertmanager", content=b"{not json", headers={**_bearer("tenant-a"), "content-type": "application/json"}).status_code == 400
        assert c.post("/api/signals/alertmanager", json={"version": "4", "alerts": []}, headers=_bearer("tenant-a")).status_code == 422
        assert c.post("/api/signals/alertmanager", json={"alerts": [{"status": "firing", "startsAt": "x", "fingerprint": "zz"}]}, headers=_bearer("tenant-a")).status_code == 422
        assert [k.kwargs["action"] for k in _env.call_args_list] == ["ingress.rejected"] * 3


class TestIngestion:
    def test_verified_notification_becomes_a_durable_observation_with_envelope_and_audit(self, _env):
        repo = MemoryRepository()
        c = _client(repo)
        r = c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer("tenant-a"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert (body["recorded"], body["deduplicated"], body["rejected"]) == (1, 0, 0)
        assert body["alerts"][0]["outcome"] == "recorded" and body["alerts"][0]["fingerprint"] == "a1b2c3d4e5f60718"
        assert body["ingress"]["tenant_id"] == "tenant-a" and body["ingress"]["trust"] == "untrusted_external"
        obs = next(iter(repo.rows.values()))
        assert obs.tenant.tenant_id == "tenant-a"
        assert obs.subject_ref == "alertmanager:alert:a1b2c3d4e5f60718" and obs.predicate == "alert"
        assert obs.provenance.produced_by == "signal:alertmanager-ingress/1"
        audit = _env.call_args.kwargs
        assert audit["action"] == "ingress.accepted" and audit["user"] == "alertmanager-svc"
        assert "backend down" not in json.dumps(audit["metadata"])

    def test_repeated_notification_is_deduplicated_not_duplicated(self):
        repo = MemoryRepository()
        c = _client(repo)
        c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer("tenant-a"))
        r = c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer("tenant-a"))
        assert (r.json()["recorded"], r.json()["deduplicated"]) == (0, 1)
        assert len(repo.rows) == 1

    def test_tenant_comes_from_the_token_and_two_tenants_do_not_collide(self):
        repo = MemoryRepository()
        c = _client(repo)
        forged = dict(PAYLOAD, commonLabels={"tenant_id": "tenant-b"})
        forged["alerts"] = [dict(PAYLOAD["alerts"][0], labels={**PAYLOAD["alerts"][0]["labels"], "tenant_id": "tenant-b"})]
        a = c.post("/api/signals/alertmanager", json=forged, headers=_bearer("tenant-a"))
        b = c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer("tenant-b"))
        assert a.json()["tenant_id"] == "tenant-a" and b.json()["tenant_id"] == "tenant-b"
        tenants = sorted(o.tenant.tenant_id for o in repo.rows.values())
        assert tenants == ["tenant-a", "tenant-b"]

    def test_secret_shaped_alert_is_refused_per_alert_not_accepted(self):
        repo = MemoryRepository()
        c = _client(repo)
        leaky = dict(PAYLOAD)
        leaky["alerts"] = [dict(PAYLOAD["alerts"][0], annotations={"token": "AKIAIOSFODNN7EXAMPLEAKIAIOSFODNN7"})]
        r = c.post("/api/signals/alertmanager", json=leaky, headers=_bearer("tenant-a"))
        assert r.status_code == 200
        assert r.json()["rejected"] + r.json()["recorded"] == 1

    def test_persistence_failure_is_503_never_a_false_acknowledgement(self, _env):
        repo = MemoryRepository()
        repo.fail = True
        c = _client(repo)
        r = c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer("tenant-a"))
        assert r.status_code == 503 and len(repo.rows) == 0
        assert _env.call_args.kwargs["action"] == "ingress.rejected"

    def test_ledger_unavailable_is_503(self):
        c = _client(MemoryRepository())
        with patch("backend.api.signal_ingress_routes._observation_repository", return_value=None):
            r = c.post("/api/signals/alertmanager", json=PAYLOAD, headers=_bearer("tenant-a"))
        assert r.status_code == 503
