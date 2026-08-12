"""Phase 7.4 — World Query, freshness, and authority (STEP W matrix).

Read-only, deterministic, explainable queries over the Phase 7.3 fact ledger:
the four temporal queries (no regression), the freshness overlay (fresh/stale/
unknown, STALE != FALSE), and the authority overlay (recency != authority,
conflict preserved). In-memory readers are backed by the REAL derivation and a
real observation store, so the versions and their sources are genuine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.world import (
    EpistemicStatus,
    Observation,
    ObservationInstant,
    ObservationSource,
    ObservationSourceKind,
    ProvenanceRef,
    SourceAuthority,
)
from backend.world.application import (
    AuthorityPolicy,
    AuthorityRule,
    AuthorityStatus,
    FactDerivation,
    FactVersion,
    FreshnessPolicy,
    FreshnessRule,
    FreshnessState,
    WorldQuery,
)

ACME = TenantRef(tenant_id="acme")
OTHER = TenantRef(tenant_id="other")


def _utc(h, m):
    return datetime(2026, 8, 12, h, m, tzinfo=timezone.utc)


class MemFactRepo:
    def __init__(self):
        self.by_version = {}

    def record(self, fact, *, version_digest, semantic_identity, value_digest):
        if version_digest in self.by_version:
            return False
        self.by_version[version_digest] = FactVersion(
            fact_id=fact.record_id, semantic_identity=semantic_identity,
            tenant_id=fact.tenant.tenant_id, subject_ref=fact.subject_ref,
            predicate=fact.predicate, value=fact.value, value_digest=value_digest,
            valid_from=fact.validity.valid_from, recorded_at=fact.recorded_at,
            status=fact.status, authority=fact.authority.value,
            observation_ref=fact.provenance.observation_ref,
            parent_claim_ref=fact.provenance.parent_claim_ref)
        return True

    def versions_for(self, *, tenant_id, semantic_identity):
        return tuple(v for v in self.by_version.values()
                     if v.tenant_id == tenant_id and v.semantic_identity == semantic_identity)


class MemObsStore:
    def __init__(self):
        self.by_id = {}

    def put(self, obs):
        self.by_id[obs.record_id] = obs

    def get_observation(self, *, tenant_id, observation_id):
        obs = self.by_id.get(observation_id)
        if obs is None or obs.tenant.tenant_id != tenant_id:  # tenant fail-closed
            return None
        return obs


class World:
    """A tiny in-memory World Plane: ingests observations and derives facts,
    then answers queries — everything the SQL stack does, without a database."""

    def __init__(self, *, freshness=None, authority=None):
        self.facts = MemFactRepo()
        self.obs = MemObsStore()
        self.derivation = FactDerivation(repository=self.facts)
        self.query = WorldQuery(facts=self.facts, observations=self.obs,
                                freshness_policy=freshness, authority_policy=authority)
        self._n = 0

    def observe(self, *, tenant=ACME, subject="deployment/payments",
                predicate="spec.replicas", value, observed_at, source_ref="connector:kubernetes",
                recorded_at=None, exec_ref="ex-1"):
        self._n += 1
        obs = Observation(
            record_id=f"obs-{self._n}", tenant=tenant, recorded_at=observed_at,
            provenance=ProvenanceRef(produced_by=source_ref, execution_ref=exec_ref,
                                     source_ref=source_ref, trace_ref="corr-1"),
            source=ObservationSource(kind=ObservationSourceKind.CONNECTOR, source_ref=source_ref),
            subject_ref=subject, predicate=predicate, value=value,
            status=SourceStatus.RETURNED_DATA,
            instant=ObservationInstant(observed_at=observed_at, retrieved_at=observed_at))
        self.obs.put(obs)
        self.derivation.derive(tenant=tenant, observation=obs,
                               recorded_at=recorded_at or observed_at)
        return obs


# ======================================================================
# Temporal queries through WorldQuery — the 7.3 load-bearing example, no regression
# ======================================================================

class TestTemporalNoRegression:
    def _world(self):
        w = World()
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), recorded_at=_utc(10, 4))
        w.observe(value={"replicas": 3}, observed_at=_utc(9, 58), recorded_at=_utc(10, 10))
        return w

    def test_world_at_0959_is_3(self):
        w = self._world()
        r = w.query.as_of_valid(tenant=ACME, subject_ref="deployment/payments",
                                predicate="spec.replicas", at_valid=_utc(9, 59), now=_utc(10, 20))
        assert r.temporal.value == {"replicas": 3}

    def test_world_at_1002_is_5(self):
        w = self._world()
        r = w.query.as_of_valid(tenant=ACME, subject_ref="deployment/payments",
                                predicate="spec.replicas", at_valid=_utc(10, 2), now=_utc(10, 20))
        assert r.temporal.value == {"replicas": 5}

    def test_known_at_1000_is_unknown(self):
        w = self._world()
        r = w.query.as_known(tenant=ACME, subject_ref="deployment/payments",
                             predicate="spec.replicas", known_at=_utc(10, 0))
        assert r.temporal.status is EpistemicStatus.UNKNOWN

    def test_known_at_1005_is_5(self):
        w = self._world()
        r = w.query.as_known(tenant=ACME, subject_ref="deployment/payments",
                             predicate="spec.replicas", known_at=_utc(10, 5))
        assert r.temporal.value == {"replicas": 5}

    def test_current_is_5(self):
        w = self._world()
        r = w.query.current(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(10, 20))
        assert r.temporal.value == {"replicas": 5}

    def test_history_has_both_versions(self):
        w = self._world()
        h = w.query.history(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas")
        assert [e.value for e in h] == [{"replicas": 5}, {"replicas": 3}]


# ======================================================================
# Evidence
# ======================================================================

class TestEvidence:
    def test_evidence_exposes_supporting_observations_and_source(self):
        w = World()
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
        ev = w.query.evidence_for(tenant=ACME, subject_ref="deployment/payments",
                                  predicate="spec.replicas")
        assert len(ev) == 1
        assert ev[0].source_ref == "connector:kubernetes"
        assert ev[0].value == {"replicas": 5}
        assert ev[0].observed_at == _utc(10, 0)
        assert ev[0].execution_ref == "ex-1"

    def test_result_to_dict_is_explainable(self):
        w = World()
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
        d = w.query.current(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(10, 1)).to_dict()
        for key in ("what", "status", "when_valid", "why", "fresh", "conflicted",
                    "evidence", "tenant"):
            assert key in d
        assert d["tenant"] == "acme"
        assert d["what"]["value"] == {"replicas": 5}


# ======================================================================
# Freshness — explicit policy, STALE != FALSE, UNKNOWN default
# ======================================================================

class TestFreshness:
    def test_no_policy_means_unknown_not_stale(self):
        w = World()  # no freshness policy
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
        r = w.query.current(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(11, 0))
        assert r.freshness.state is FreshnessState.UNKNOWN  # not STALE by default

    def test_fresh_within_horizon(self):
        policy = FreshnessPolicy(rules=(FreshnessRule(
            horizon_seconds=600, predicate="spec.replicas", name="k8s-replicas"),))
        w = World(freshness=policy)
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
        r = w.query.current(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(10, 5))  # 5 min < 10 min
        assert r.freshness.state is FreshnessState.FRESH

    def test_stale_beyond_horizon_but_value_unchanged(self):
        policy = FreshnessPolicy(rules=(FreshnessRule(
            horizon_seconds=600, predicate="spec.replicas"),))
        w = World(freshness=policy)
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
        r = w.query.current(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(10, 30))  # 30 min > 10 min
        assert r.freshness.state is FreshnessState.STALE
        # STALE != FALSE: the value is still 5, not 0, not false
        assert r.effective_value == {"replicas": 5}
        assert r.effective_status is EpistemicStatus.AFFIRMED


# ======================================================================
# Authority — recency != authority, conflict preserved
# ======================================================================

K8S = "connector:kubernetes"
CACHE = "connector:stale-cache"


def _authority_policy():
    return AuthorityPolicy(rules=(
        AuthorityRule(tier=SourceAuthority.AUTHORITATIVE, source_ref=K8S),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref=CACHE),
    ))


class TestAuthority:
    def test_recency_does_not_override_authority(self):
        # K8s API says 5 at 10:00 (authoritative); stale cache says 3 at 10:05 (newer).
        w = World(authority=_authority_policy())
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
        w.observe(value={"replicas": 3}, observed_at=_utc(10, 5), source_ref=CACHE,
                  recorded_at=_utc(10, 6))
        r = w.query.current(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(10, 10))
        # temporal projection would pick the newer cache value...
        assert r.temporal.value == {"replicas": 3}
        # ...but authority resolves to the authoritative K8s value, with the cache
        # preserved as a lower-tier alternative.
        assert r.authority.status is AuthorityStatus.RESOLVED
        assert r.authority.value == {"replicas": 5}
        assert r.authority.source_ref == K8S
        assert r.effective_value == {"replicas": 5}
        assert any(a.value == {"replicas": 3} and a.source_ref == CACHE
                   for a in r.authority.alternatives)

    def test_equal_authority_disagreement_stays_conflicted(self):
        # Two authoritative sources disagree at the SAME valid instant.
        w = World(authority=AuthorityPolicy(rules=(
            AuthorityRule(tier=SourceAuthority.AUTHORITATIVE, source_kind="connector"),)))
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref="connector:a")
        w.observe(value={"replicas": 3}, observed_at=_utc(10, 0), source_ref="connector:b",
                  recorded_at=_utc(10, 6))
        r = w.query.current(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(10, 10))
        assert r.authority.status is AuthorityStatus.CONFLICTED
        assert r.effective_status is EpistemicStatus.CONFLICTED
        assert len(r.authority.alternatives) == 2  # both preserved

    def test_no_authority_policy_is_ungoverned(self):
        w = World()  # no authority policy
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
        r = w.query.current(tenant=ACME, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(10, 1))
        assert r.authority.status is AuthorityStatus.UNGOVERNED
        # ungoverned -> the temporal projection stands
        assert r.effective_value == {"replicas": 5}

    def test_unknown_when_nothing_covers_the_instant(self):
        w = World(authority=_authority_policy())
        r = w.query.as_of_valid(tenant=ACME, subject_ref="deployment/payments",
                                predicate="spec.replicas", at_valid=_utc(8, 0), now=_utc(10, 0))
        assert r.authority.status is AuthorityStatus.UNKNOWN
        assert r.effective_status is EpistemicStatus.UNKNOWN


# ======================================================================
# Tenant isolation
# ======================================================================

class TestTenant:
    def test_cross_tenant_query_fails_closed(self):
        w = World()
        w.observe(tenant=ACME, value={"replicas": 5}, observed_at=_utc(10, 0))
        # OTHER tenant asking the same subject/predicate sees nothing
        r = w.query.current(tenant=OTHER, subject_ref="deployment/payments",
                            predicate="spec.replicas", now=_utc(10, 1))
        assert r.temporal.status is EpistemicStatus.UNKNOWN
        assert r.evidence == ()

    def test_non_tenantref_is_refused(self):
        w = World()
        with pytest.raises(TypeError):
            w.query.current(tenant="acme", subject_ref="d", predicate="p", now=_utc(10, 0))
