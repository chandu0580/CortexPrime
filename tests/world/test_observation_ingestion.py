"""Phase 7.2 — observation ingestion boundary tests (Parts L, T, K, Q, I, J).

Unit-level: the ingestion service, its refusals, idempotency, the model firewall,
and the append-only port contract, against an in-memory repository. Real
PostgreSQL crash/recovery/replay is the separate harness (Parts M/N)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.world import Observation, ObservationSourceKind
from backend.world.application import (
    ObservationIngestion,
    ObservationRejected,
    ReadObservation,
    observation_identity,
)

NOW = datetime.now(timezone.utc)
ACME = TenantRef(tenant_id="acme")
OTHER = TenantRef(tenant_id="other")


class MemRepo:
    """An in-memory ObservationRepository. Append-only by construction — it has
    no update/delete, and dedupes on identity."""

    def __init__(self):
        self.by_identity: dict = {}
        self.record_calls = 0

    def record(self, observation: Observation, *, identity_digest: str) -> bool:
        self.record_calls += 1
        if identity_digest in self.by_identity:
            return False
        self.by_identity[identity_digest] = observation
        return True


def _read(**over):
    kw = dict(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:grafana",
        subject_ref="folder:p61", predicate="exists", value={"uid": "p61"},
        status=SourceStatus.RETURNED_DATA, observed_at=NOW, retrieved_at=NOW,
        produced_by="connector:grafana", execution_ref="ex-1")
    kw.update(over)
    return ReadObservation(**kw)


def _ingest(repo, tenant=ACME, read=None, recorded_at=NOW):
    return ObservationIngestion(repository=repo).ingest(
        tenant=tenant, read=read or _read(), recorded_at=recorded_at)


# ======================================================================
# Happy path + provenance + temporal (Parts C, E, F)
# ======================================================================

class TestHappyPath:
    def test_governed_read_becomes_an_observation(self):
        repo = MemRepo()
        obs, newly = _ingest(repo)
        assert newly
        assert isinstance(obs, Observation)
        assert obs.tenant.tenant_id == "acme"
        assert obs.source.kind is ObservationSourceKind.CONNECTOR
        assert obs.provenance.execution_ref == "ex-1"

    def test_observed_at_and_recorded_at_are_distinct(self):
        repo = MemRepo()
        observed = NOW - timedelta(minutes=4)
        obs, _ = _ingest(repo, read=_read(observed_at=observed, retrieved_at=NOW),
                         recorded_at=NOW + timedelta(seconds=1))
        assert obs.instant.observed_at == observed
        assert obs.recorded_at != obs.instant.observed_at
        assert obs.recorded_at > obs.instant.retrieved_at

    def test_source_status_empty_is_preserved_not_collapsed(self):
        repo = MemRepo()
        obs, _ = _ingest(repo, read=_read(status=SourceStatus.RETURNED_EMPTY, value=None))
        assert obs.status is SourceStatus.RETURNED_EMPTY  # not a generic failure


# ======================================================================
# Tenant isolation (Part D) — tenant from context, fail closed
# ======================================================================

class TestTenant:
    def test_tenant_comes_from_context_not_the_read(self):
        # The read carries no tenant; the ingestion service is told the tenant.
        repo = MemRepo()
        obs, _ = _ingest(repo, tenant=ACME)
        assert obs.tenant.tenant_id == "acme"
        assert not hasattr(_read(), "tenant")  # ReadObservation has no tenant field

    def test_non_tenantref_is_refused(self):
        with pytest.raises(ObservationRejected):
            _ingest(MemRepo(), tenant="acme")  # a bare string

    def test_different_tenants_produce_different_identities(self):
        repo = MemRepo()
        a, _ = _ingest(repo, tenant=ACME)
        b, _ = _ingest(repo, tenant=OTHER)
        assert observation_identity(a) != observation_identity(b)


# ======================================================================
# Model firewall (Part I) — model output cannot become an Observation
# ======================================================================

class TestModelFirewall:
    def test_no_model_source_kind(self):
        assert not any(k.name == "MODEL" for k in ObservationSourceKind)

    def test_observation_has_no_from_model_constructor(self):
        assert not hasattr(Observation, "from_model")
        assert not hasattr(Observation, "from_text")
        assert not hasattr(Observation, "from_llm")

    def test_read_observation_source_cannot_be_a_model(self):
        # ReadObservation.source_kind is an ObservationSourceKind; there is no
        # model member to supply, so a model-origin read cannot be constructed.
        with pytest.raises((TypeError, ValueError, AttributeError, KeyError)):
            ObservationSourceKind("model")  # not a member


# ======================================================================
# Secret firewall (Part Q) — field-aware, nested
# ======================================================================

class TestSecretFirewall:
    @pytest.mark.parametrize("value", [
        {"token": "ghp_ABCDEFGHIJKLMNOP1234567890"},
        {"nested": {"deep": {"authorization": "Bearer sk-abcdef1234567890"}}},
        {"items": ["ok", "password=supersecretvalue"]},
        "sk-abcdef1234567890abcdef1234567890",
    ])
    def test_secret_bearing_value_is_refused(self, value):
        with pytest.raises(ObservationRejected):
            _ingest(MemRepo(), read=_read(value=value))

    def test_safe_references_are_allowed(self):
        # credential_ref / authorization_digest / provider ids are NOT secrets.
        repo = MemRepo()
        obs, _ = _ingest(repo, read=_read(value={
            "credential_ref": "cred://vault/grafana",
            "authorization_digest": "abc123",
            "provider": "grafana", "operation": "folder.get"}))
        assert obs is not None

    def test_secret_refused_before_repository_touched(self):
        repo = MemRepo()
        with pytest.raises(ObservationRejected):
            _ingest(repo, read=_read(value={"api_key": "sk-abcdef1234567890abcdef"}))
        assert repo.record_calls == 0  # nothing recorded


# ======================================================================
# Idempotency (Part J) — deterministic identity, at-least-once dedupe
# ======================================================================

class TestIdempotency:
    def test_identical_delivery_dedupes(self):
        repo = MemRepo()
        _, first = _ingest(repo)
        _, second = _ingest(repo)
        assert first is True
        assert second is False  # deduped, not a new row
        assert len(repo.by_identity) == 1

    def test_identity_is_deterministic(self):
        a, _ = _ingest(MemRepo())
        b, _ = _ingest(MemRepo())
        assert observation_identity(a) == observation_identity(b)

    def test_a_new_value_is_a_new_observation(self):
        repo = MemRepo()
        _ingest(repo, read=_read(value={"uid": "p61"}))
        _ingest(repo, read=_read(value={"uid": "p62"}))
        assert len(repo.by_identity) == 2

    def test_a_later_observed_at_is_a_new_observation(self):
        repo = MemRepo()
        _ingest(repo, read=_read(observed_at=NOW - timedelta(minutes=5)))
        _ingest(repo, read=_read(observed_at=NOW))
        assert len(repo.by_identity) == 2


# ======================================================================
# Append-only port (Part K) — no mutation surface
# ======================================================================

class TestAppendOnly:
    def test_repository_port_has_no_update_or_delete(self):
        from backend.world.application import ObservationRepository
        for banned in ("update", "delete", "remove", "overwrite", "mutate"):
            assert not hasattr(ObservationRepository, banned)

    def test_sql_repository_has_no_update_or_delete(self):
        from backend.world.infrastructure import SqlObservationRepository
        for banned in ("update", "delete", "remove", "overwrite"):
            assert not hasattr(SqlObservationRepository, banned)


# ======================================================================
# Failure semantics (Part L) — refusals before any provider access
# ======================================================================

class TestRefusals:
    def test_malformed_timestamps_refused(self):
        with pytest.raises(ObservationRejected):
            _ingest(MemRepo(),
                    read=_read(observed_at=NOW, retrieved_at=NOW - timedelta(minutes=1)))

    def test_absence_with_a_value_refused(self):
        with pytest.raises(ObservationRejected):
            _ingest(MemRepo(),
                    read=_read(status=SourceStatus.UNAVAILABLE, value={"x": 1}))
