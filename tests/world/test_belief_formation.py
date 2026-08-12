"""Phase 7.5 — corroboration & belief formation (STEP S matrix, S1-S17).

Belief is a deterministic derived projection over facts + observations +
authority + freshness + corroboration. In-memory readers are backed by the REAL
derivation and a real observation store, so versions, sources, and evidence are
genuine. No belief table exists — a belief reconstructs from the ledgers.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.evidence import SourceStatus
from backend.contracts.knowledge import KnowledgeAuthority
from backend.contracts.tenant import TenantRef
from backend.contracts.world import (
    Belief,
    CalibrationState,
    ClaimConfidence,
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
    BeliefFormation,
    CorroborationLevel,
    FactDerivation,
    FactVersion,
    FreshnessPolicy,
    FreshnessRule,
    WorldQuery,
)

ACME = TenantRef(tenant_id="acme")
OTHER = TenantRef(tenant_id="other")
K8S, PROM, CACHE = "connector:kubernetes", "connector:prometheus", "connector:cache"


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


class MemObs:
    def __init__(self):
        self.items = []

    def put(self, obs):
        self.items.append(obs)

    def get_observation(self, *, tenant_id, observation_id):
        for o in self.items:
            if o.record_id == observation_id and o.tenant.tenant_id == tenant_id:
                return o
        return None

    def list_for_subject(self, *, tenant_id, subject_ref, predicate):
        return tuple(sorted(
            (o for o in self.items if o.tenant.tenant_id == tenant_id
             and o.subject_ref == subject_ref and o.predicate == predicate),
            key=lambda o: o.instant.observed_at))


class World:
    def __init__(self, *, freshness=None, authority=None):
        self.facts = MemFactRepo()
        self.obs = MemObs()
        self.derivation = FactDerivation(repository=self.facts)
        self.query = WorldQuery(facts=self.facts, observations=self.obs,
                                freshness_policy=freshness, authority_policy=authority)
        self.beliefs = BeliefFormation(query=self.query, observations=self.obs,
                                       authority_policy=authority)
        self._n = 0

    def observe(self, *, tenant=ACME, subject="deployment/payments",
                predicate="spec.replicas", value, observed_at, source_ref=K8S,
                recorded_at=None):
        self._n += 1
        obs = Observation(
            record_id=f"obs-{self._n}", tenant=tenant, recorded_at=recorded_at or observed_at,
            provenance=ProvenanceRef(produced_by=source_ref, execution_ref="ex-1",
                                     source_ref=source_ref, trace_ref="corr-1"),
            source=ObservationSource(kind=ObservationSourceKind.CONNECTOR, source_ref=source_ref),
            subject_ref=subject, predicate=predicate, value=value,
            status=SourceStatus.RETURNED_DATA,
            instant=ObservationInstant(observed_at=observed_at, retrieved_at=observed_at))
        self.obs.put(obs)
        self.derivation.derive(tenant=tenant, observation=obs, recorded_at=recorded_at or observed_at)
        return obs

    def believe(self, **kw):
        kw.setdefault("subject_ref", "deployment/payments")
        kw.setdefault("predicate", "spec.replicas")
        return self.beliefs.form_current(tenant=kw.pop("tenant", ACME), now=kw.pop("now", _utc(10, 20)),
                                         **kw)


def _auth():
    return AuthorityPolicy(rules=(
        AuthorityRule(tier=SourceAuthority.AUTHORITATIVE, source_ref=K8S),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref=PROM),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref=CACHE),
    ))


# S1 — single authoritative source supports belief
def test_s1_single_authoritative_source_supports_belief():
    w = World(authority=_auth())
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    b = w.believe()
    assert b.status is EpistemicStatus.AFFIRMED
    assert b.value == {"replicas": 5}
    assert b.corroboration.level is CorroborationLevel.SINGLE
    assert isinstance(b.belief, Belief)


# S2 — secondary corroborating source supports belief (independent agreement)
def test_s2_secondary_corroborating_source():
    w = World()  # ungoverned: corroboration decides
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 1), source_ref=PROM)
    b = w.believe()
    assert b.status is EpistemicStatus.AFFIRMED
    assert b.corroboration.level is CorroborationLevel.INDEPENDENT
    assert set(b.corroboration.independent_sources) == {K8S, PROM}


# S3 — same-provider duplicate does NOT count as independent corroboration
def test_s3_same_provider_duplicate_is_correlated_not_independent():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 1), source_ref=K8S)  # same source
    b = w.believe()
    assert b.corroboration.level is CorroborationLevel.SINGLE   # not INDEPENDENT
    assert b.corroboration.independent_sources == (K8S,)
    assert b.corroboration.correlated_count == 1                # the duplicate


# S4 — independent sources agree
def test_s4_independent_sources_agree():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=PROM)
    assert w.believe().corroboration.level is CorroborationLevel.INDEPENDENT


# S5 — independent sources disagree (ungoverned) -> CONFLICTED, not resolved
def test_s5_independent_sources_disagree():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 3}, observed_at=_utc(10, 0), source_ref=PROM,
              recorded_at=_utc(10, 1))
    b = w.believe()
    assert b.status is EpistemicStatus.CONFLICTED
    assert b.corroboration.level is CorroborationLevel.CONTRADICTED


# S6 — equal-authority disagreement remains CONFLICTED
def test_s6_equal_authority_disagreement_conflicted():
    w = World(authority=AuthorityPolicy(rules=(
        AuthorityRule(tier=SourceAuthority.AUTHORITATIVE, source_kind="connector"),)))
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref="connector:a")
    w.observe(value={"replicas": 3}, observed_at=_utc(10, 0), source_ref="connector:b",
              recorded_at=_utc(10, 1))
    b = w.believe()
    assert b.status is EpistemicStatus.CONFLICTED
    # both evidence paths preserved
    assert len(b.corroboration.contradicting) + len(b.corroboration.supporting) == 2


# S7 — stale evidence does not become FALSE
def test_s7_stale_is_not_false():
    policy = FreshnessPolicy(rules=(FreshnessRule(horizon_seconds=600, predicate="spec.replicas"),))
    w = World(freshness=policy)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
    b = w.beliefs.form_current(tenant=ACME, subject_ref="deployment/payments",
                               predicate="spec.replicas", now=_utc(10, 30))  # 30m old
    assert b.status is EpistemicStatus.STALE       # not AFFIRMED, not FALSE
    assert b.value == {"replicas": 5}              # value intact


# S8 — UNKNOWN does not become FALSE
def test_s8_unknown_is_not_false():
    w = World(authority=_auth())
    b = w.believe()  # no observations
    assert b.status is EpistemicStatus.UNKNOWN
    assert b.value is None
    assert b.belief is None
    assert b.corroboration.level is CorroborationLevel.INSUFFICIENT


# S9 — authority beats mere recency
def test_s9_authority_beats_recency():
    w = World(authority=_auth())
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)      # authoritative
    w.observe(value={"replicas": 3}, observed_at=_utc(10, 5), source_ref=CACHE,    # newer, lower
              recorded_at=_utc(10, 6))
    b = w.believe(now=_utc(10, 10))
    assert b.value == {"replicas": 5}              # authority, not the newer cache
    assert b.status is EpistemicStatus.AFFIRMED


# S10 — corroboration does not erase contradictory evidence
def test_s10_contradictory_evidence_retained():
    w = World(authority=_auth())
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 3}, observed_at=_utc(10, 5), source_ref=CACHE,
              recorded_at=_utc(10, 6))
    b = w.believe(now=_utc(10, 10))
    assert any(e.value == {"replicas": 3} and e.source_ref == CACHE
               for e in b.corroboration.contradicting)


# S11 — belief preserves complete evidence provenance
def test_s11_belief_provenance_queryable():
    w = World(authority=_auth())
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    b = w.believe()
    d = b.to_dict()
    for key in ("what", "status", "confidence", "authority", "freshness",
                "corroboration", "conflicted", "tenant"):
        assert key in d
    assert b.belief.provenance.observation_ref == b.corroboration.supporting[0].observation_id


# S12 — tenant isolation
def test_s12_tenant_isolation():
    w = World(authority=_auth())
    w.observe(tenant=ACME, value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    b = w.beliefs.form_current(tenant=OTHER, subject_ref="deployment/payments",
                               predicate="spec.replicas", now=_utc(10, 20))
    assert b.status is EpistemicStatus.UNKNOWN
    assert b.corroboration.supporting == ()


# S13 — historical belief at world time T
def test_s13_belief_at_world_time():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), recorded_at=_utc(10, 4))
    w.observe(value={"replicas": 3}, observed_at=_utc(9, 58), recorded_at=_utc(10, 10))
    b_early = w.beliefs.form_as_of_valid(tenant=ACME, subject_ref="deployment/payments",
                                         predicate="spec.replicas", at_valid=_utc(9, 59),
                                         now=_utc(10, 20))
    b_late = w.beliefs.form_as_of_valid(tenant=ACME, subject_ref="deployment/payments",
                                        predicate="spec.replicas", at_valid=_utc(10, 2),
                                        now=_utc(10, 20))
    assert b_early.value == {"replicas": 3}
    assert b_late.value == {"replicas": 5}


# S14 — knowledge-time belief at recorded time T
def test_s14_belief_at_knowledge_time():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), recorded_at=_utc(10, 4))
    w.observe(value={"replicas": 3}, observed_at=_utc(9, 58), recorded_at=_utc(10, 10))
    # known at 10:00 -> nothing recorded yet -> UNKNOWN (does not see the future)
    assert w.beliefs.form_as_known(tenant=ACME, subject_ref="deployment/payments",
                                   predicate="spec.replicas", known_at=_utc(10, 0)).status \
        is EpistemicStatus.UNKNOWN
    # known at 10:05 -> only the 5 was recorded
    assert w.beliefs.form_as_known(tenant=ACME, subject_ref="deployment/payments",
                                   predicate="spec.replicas", known_at=_utc(10, 5)).value \
        == {"replicas": 5}


# S16 — model output cannot create Belief (structural)
def test_s16_model_cannot_create_belief():
    from backend.contracts.world import ModelProposal
    assert not hasattr(ModelProposal, "to_belief")
    assert not hasattr(ModelProposal, "to_fact")
    # a Belief requires structured evidence basis or grounding provenance —
    # a bare producer label with no anchor and no basis is refused (so model
    # text cannot mint a belief from nothing).
    with pytest.raises(Exception):
        Belief(record_id="b", tenant=ACME, recorded_at=_utc(10, 0),
               provenance=ProvenanceRef(produced_by="model"),  # no anchor
               subject_ref="s", predicate="p", value=1,
               confidence=ClaimConfidence.uncalibrated(),
               status=EpistemicStatus.AFFIRMED, basis=())  # no basis, no grounding


# Confidence stays UNCALIBRATED (Part I)
def test_confidence_is_uncalibrated_never_a_number():
    w = World(authority=_auth())
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    b = w.believe()
    assert b.confidence.state is CalibrationState.UNCALIBRATED
    assert b.confidence.value is None
    assert b.belief.confidence.value is None


# Determinism (Part P)
def test_determinism_same_inputs_same_belief():
    def build():
        w = World(authority=_auth())
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
        w.observe(value={"replicas": 3}, observed_at=_utc(10, 5), source_ref=CACHE,
                  recorded_at=_utc(10, 6))
        return w.believe(now=_utc(10, 10)).to_dict()
    a, b = build(), build()
    # strip the non-deterministic record_id inside belief (it uses a counter, stable here)
    assert a["what"] == b["what"] and a["status"] == b["status"]
    assert a["corroboration"]["level"] == b["corroboration"]["level"]
