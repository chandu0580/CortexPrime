"""Phase 7.6 — source lineage, governed belief policy, hypothesis/prediction
(STEP T matrix). Lineage-aware corroboration never fakes independence; the belief
support policy gates acceptance without numbers; the model can only propose a
hypothesis, and prediction/outcome/verification distinctions are structural.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.verification import Verdict, VerifierIdentity
from backend.contracts.world import (
    EpistemicStatus,
    HypothesisStatus,
    ModelHypothesisProposal,
    ModelProposal,
    Observation,
    ObservationInstant,
    ObservationSource,
    ObservationSourceKind,
    Outcome,
    Prediction,
    ProvenanceRef,
    SourceAuthority,
    WorldVerification,
)
from backend.world.application import (
    AuthorityPolicy,
    AuthorityRule,
    BeliefAcceptance,
    BeliefFormation,
    BeliefSupportPolicy,
    BeliefSupportRule,
    CorroborationLevel,
    FactDerivation,
    FactVersion,
    HypothesisEvidence,
    HypothesisFormation,
    HypothesisRejected,
    LineagePolicy,
    LineageRelation,
    LineageRule,
    SupportRequirement,
    WorldQuery,
    evaluate_prediction,
)

ACME, OTHER = TenantRef(tenant_id="acme"), TenantRef(tenant_id="other")
K8S, PROM, DATADOG = "connector:kubernetes", "connector:prometheus", "connector:datadog"
CP = "k8s-control-plane"


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

    def put(self, o):
        self.items.append(o)

    def get_observation(self, *, tenant_id, observation_id):
        return next((o for o in self.items if o.record_id == observation_id
                     and o.tenant.tenant_id == tenant_id), None)

    def list_for_subject(self, *, tenant_id, subject_ref, predicate):
        return tuple(sorted((o for o in self.items if o.tenant.tenant_id == tenant_id
                             and o.subject_ref == subject_ref and o.predicate == predicate),
                            key=lambda o: o.instant.observed_at))


class World:
    def __init__(self, *, authority=None, lineage=None, support=None):
        self.facts, self.obs = MemFactRepo(), MemObs()
        self.derivation = FactDerivation(repository=self.facts)
        self.query = WorldQuery(facts=self.facts, observations=self.obs, authority_policy=authority)
        self.beliefs = BeliefFormation(query=self.query, observations=self.obs,
                                       authority_policy=authority, lineage_policy=lineage,
                                       support_policy=support)
        self._n = 0

    def observe(self, *, value, observed_at, source_ref, subject="deployment/payments",
                predicate="spec.replicas", tenant=ACME):
        self._n += 1
        o = Observation(
            record_id=f"o-{self._n}", tenant=tenant, recorded_at=observed_at,
            provenance=ProvenanceRef(produced_by=source_ref, execution_ref="ex-1",
                                     source_ref=source_ref),
            source=ObservationSource(kind=ObservationSourceKind.CONNECTOR, source_ref=source_ref),
            subject_ref=subject, predicate=predicate, value=value,
            status=SourceStatus.RETURNED_DATA,
            instant=ObservationInstant(observed_at=observed_at, retrieved_at=observed_at))
        self.obs.put(o)
        self.derivation.derive(tenant=tenant, observation=o, recorded_at=observed_at)

    def believe(self, now=_utc(10, 20), tenant=ACME):
        return self.beliefs.form_current(tenant=tenant, subject_ref="deployment/payments",
                                         predicate="spec.replicas", now=now)


# ======================================================================
# Lineage-aware corroboration (T1-T4)
# ======================================================================

# T1/T2 — different source_ref but SAME lineage origin -> CORRELATED, not independent
def test_same_lineage_is_correlated_not_independent():
    lineage = LineagePolicy(rules=(
        LineageRule(origin_id=CP, relation=LineageRelation.DIRECT, source_ref=K8S),
        LineageRule(origin_id=CP, relation=LineageRelation.DERIVED, source_ref=PROM),
    ))
    w = World(lineage=lineage)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=PROM)  # derived from K8s
    b = w.believe()
    assert b.corroboration.level is CorroborationLevel.CORRELATED
    assert b.corroboration.independent_origins == (CP,)  # one shared origin


# T3 — unknown lineage -> INDETERMINATE (never fake independence)
def test_unknown_lineage_is_indeterminate():
    w = World(lineage=LineagePolicy.none())
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=DATADOG)
    assert w.believe().corroboration.level is CorroborationLevel.INDETERMINATE


# T4 — truly independent (distinct known origins) -> INDEPENDENT
def test_distinct_known_origins_are_independent():
    lineage = LineagePolicy(rules=(
        LineageRule(origin_id=CP, relation=LineageRelation.DIRECT, source_ref=K8S),
        LineageRule(origin_id="datadog-agent", relation=LineageRelation.DIRECT, source_ref=DATADOG),
    ))
    w = World(lineage=lineage)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=DATADOG)
    b = w.believe()
    assert b.corroboration.level is CorroborationLevel.INDEPENDENT
    assert set(b.corroboration.independent_origins) == {CP, "datadog-agent"}


# ======================================================================
# Authority stays separate from lineage & corroboration (T5-T7)
# ======================================================================

def test_authority_separate_from_lineage_and_recency():
    # K8s (authoritative) says 5@10:00; Prometheus (derived, secondary) says 3@10:05.
    lineage = LineagePolicy(rules=(
        LineageRule(origin_id=CP, relation=LineageRelation.DIRECT, source_ref=K8S),
        LineageRule(origin_id=CP, relation=LineageRelation.DERIVED, source_ref=PROM),
    ))
    authority = AuthorityPolicy(rules=(
        AuthorityRule(tier=SourceAuthority.AUTHORITATIVE, source_ref=K8S),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref=PROM),
    ))
    w = World(authority=authority, lineage=lineage)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 3}, observed_at=_utc(10, 5), source_ref=PROM)
    b = w.believe(now=_utc(10, 10))
    assert b.value == {"replicas": 5}                 # authority = Kubernetes
    assert any(e.source_ref == PROM for e in b.corroboration.contradicting)  # PROM preserved


# ======================================================================
# Governed belief support policy (no numbers)
# ======================================================================

def test_support_policy_independent_required_provisional_when_single():
    support = BeliefSupportPolicy(rules=(BeliefSupportRule(
        requirement=SupportRequirement.INDEPENDENT_REQUIRED),))
    authority = AuthorityPolicy(rules=(AuthorityRule(
        tier=SourceAuthority.AUTHORITATIVE, source_ref=K8S),))
    w = World(authority=authority, support=support)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    b = w.believe()
    # a single authoritative source, but independence required -> PROVISIONAL
    assert b.acceptance.acceptance is BeliefAcceptance.PROVISIONAL


def test_support_policy_accepted_with_independent_lineage():
    support = BeliefSupportPolicy(rules=(BeliefSupportRule(
        requirement=SupportRequirement.INDEPENDENT_REQUIRED),))
    lineage = LineagePolicy(rules=(
        LineageRule(origin_id=CP, relation=LineageRelation.DIRECT, source_ref=K8S),
        LineageRule(origin_id="datadog-agent", relation=LineageRelation.DIRECT, source_ref=DATADOG),
    ))
    w = World(lineage=lineage, support=support)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=DATADOG)
    assert w.believe().acceptance.acceptance is BeliefAcceptance.ACCEPTED


def test_support_policy_authoritative_accepts_single_authoritative():
    support = BeliefSupportPolicy(rules=(BeliefSupportRule(
        requirement=SupportRequirement.AUTHORITATIVE),))
    authority = AuthorityPolicy(rules=(AuthorityRule(
        tier=SourceAuthority.AUTHORITATIVE, source_ref=K8S),))
    w = World(authority=authority, support=support)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    assert w.believe().acceptance.acceptance is BeliefAcceptance.ACCEPTED


# ======================================================================
# Hypothesis: model proposes, platform grounds (T12)
# ======================================================================

def test_model_proposal_grounds_into_open_hypothesis():
    proposal = ModelHypothesisProposal(
        record_id="mp", tenant=ACME, recorded_at=_utc(10, 0),
        provenance=ProvenanceRef(produced_by="model", parent_claim_ref="turn-1"),
        claim="rollout caused the 5xx spike", proposed_by="model:gpt",
        subject_ref="deployment/payments", suggested_investigation="diff the rollout")
    h = HypothesisFormation().ground(
        tenant=ACME, proposal=proposal, recorded_at=_utc(10, 1),
        evidence=HypothesisEvidence(support_refs=("wfact-1",), contradiction_refs=("wfact-2",),
                                    falsifier="5xx persists after rollback"))
    assert h.status is HypothesisStatus.OPEN            # never VERIFIED
    assert h.support_refs == ("wfact-1",) and h.contradiction_refs == ("wfact-2",)
    assert h.provenance.parent_claim_ref == "mp"        # traces to the proposal


def test_ungrounded_proposal_is_refused():
    proposal = ModelHypothesisProposal(
        record_id="mp", tenant=ACME, recorded_at=_utc(10, 0),
        provenance=ProvenanceRef(produced_by="model", parent_claim_ref="t"),
        claim="something", proposed_by="model", subject_ref="deployment/x")
    with pytest.raises(HypothesisRejected):  # no evidence refs
        HypothesisFormation().ground(tenant=ACME, proposal=proposal, recorded_at=_utc(10, 1),
                                     evidence=HypothesisEvidence())


def test_model_hypothesis_proposal_has_no_conversion_methods():
    for banned in ("to_hypothesis", "to_fact", "to_belief", "to_verification"):
        assert not hasattr(ModelHypothesisProposal, banned)
        assert not hasattr(ModelProposal, banned)


# ======================================================================
# Prediction != Outcome != Verification (T13-T16)
# ======================================================================

def test_outcome_requires_execution_ref():
    with pytest.raises(Exception):
        Outcome(record_id="o", tenant=ACME, recorded_at=_utc(10, 0),
                provenance=ProvenanceRef(produced_by="x", execution_ref="ex-1"),
                execution_ref="", observed={"error_rate": 4.2})  # empty execution_ref


def test_prediction_horizon_enforced():
    with pytest.raises(Exception):
        Prediction(record_id="p", tenant=ACME, recorded_at=_utc(10, 0),
                   provenance=ProvenanceRef(produced_by="model", parent_claim_ref="h"),
                   subject_ref="deployment/payments", expected={"error_rate": "<1%"},
                   predicted_at=_utc(10, 0), deadline=_utc(9, 0))  # deadline before predicted_at


def test_prediction_evaluated_against_real_outcome():
    pred = Prediction(record_id="p", tenant=ACME, recorded_at=_utc(10, 0),
                      provenance=ProvenanceRef(produced_by="model", parent_claim_ref="h"),
                      subject_ref="deployment/payments", expected={"healthy": True},
                      predicted_at=_utc(10, 0), deadline=_utc(10, 5), hypothesis_ref="whyp-1")
    outcome = Outcome(record_id="oc", tenant=ACME, recorded_at=_utc(10, 4),
                      provenance=ProvenanceRef(produced_by="platform", execution_ref="ex-9"),
                      execution_ref="ex-9", observed={"healthy": False}, prediction_ref="p")
    ev = evaluate_prediction(prediction=pred, outcome=outcome, observed_at=_utc(10, 4))
    assert ev.matched is False                    # expected != observed
    assert ev.within_horizon is True              # observed before the deadline
    assert ev.execution_ref == "ex-9"             # tied to real execution


def test_verification_needs_procedure_and_independent_verifier():
    # a bare model verdict cannot construct a WorldVerification
    with pytest.raises(Exception):
        WorldVerification(record_id="v", tenant=ACME, recorded_at=_utc(10, 0),
                          provenance=ProvenanceRef(produced_by="model", observation_ref="o"),
                          subject_ref="deployment/payments", procedure_ref="",  # no procedure
                          verifier=VerifierIdentity(verifier_id="m", method="self"),
                          verdict=Verdict.SUPPORTED, evidence_refs=("o",))
