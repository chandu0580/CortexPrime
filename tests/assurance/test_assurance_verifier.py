"""Phase 7.7 — independent assurance verification (STEP U matrix, U1-U20).

The Assurance Plane adjudicates a claim against evidence it obtains itself from
the World Plane. A model can never mint a verification, verifier failure is never
success, and UNKNOWN/STALE/CONFLICTED evidence never returns SUPPORTED. In-memory
readers are backed by the REAL derivation + observation store, so the evidence
the verifier queries is genuine.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.verification import Verdict, VerifierIdentity
from backend.contracts.world import (
    Observation,
    ObservationInstant,
    ObservationSource,
    ObservationSourceKind,
    ProvenanceRef,
    SourceAuthority,
    WorldVerification,
)
from backend.assurance.application import (
    AssurancePolicy,
    AssuranceRefused,
    AssuranceVerifier,
    DEFAULT_VERIFIER_IDENTITY,
    VerificationProcedure,
    VerificationProcedureKind,
)
from backend.world.application import (
    AuthorityPolicy,
    AuthorityRule,
    FactDerivation,
    FactVersion,
    FreshnessPolicy,
    FreshnessRule,
    LineagePolicy,
    LineageRelation,
    LineageRule,
    WorldQuery,
)

ACME, OTHER = TenantRef(tenant_id="acme"), TenantRef(tenant_id="other")
K8S = "connector:kubernetes"
MODEL_PATH = "model:gpt/turn-1"


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
        return tuple(o for o in self.items if o.tenant.tenant_id == tenant_id
                     and o.subject_ref == subject_ref and o.predicate == predicate)


class World:
    def __init__(self, *, authority=None, freshness=None, lineage=None, policy=None):
        self.facts, self.obs = MemFactRepo(), MemObs()
        self.derivation = FactDerivation(repository=self.facts)
        self.query = WorldQuery(facts=self.facts, observations=self.obs,
                                authority_policy=authority, freshness_policy=freshness)
        self.verifier = AssuranceVerifier(query=self.query, policy=policy, lineage_policy=lineage)
        self._n = 0

    def observe(self, *, value, observed_at, source_ref=K8S,
                subject="deployment/payments", predicate="spec.replicas", tenant=ACME):
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

    def verify(self, expected, *, now=_utc(10, 5), tenant=ACME, at_valid=None,
               producer=MODEL_PATH, verifier=DEFAULT_VERIFIER_IDENTITY):
        proc = VerificationProcedure(
            kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
            subject_ref="deployment/payments", predicate="spec.replicas",
            expected=expected, at_valid=at_valid)
        return self.verifier.verify(tenant=tenant, procedure=proc, producer_reasoning_path=producer,
                                    verified_at=now, verifier=verifier)


# U7 — independent evidence can verify
def test_independent_evidence_supports():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
    r = w.verify({"replicas": 5})
    assert r.verdict is Verdict.SUPPORTED
    assert isinstance(r.verification, WorldVerification)
    assert r.verification.evidence_refs  # SUPPORTED cites evidence


def test_contradicting_world_state_is_unsupported():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
    assert w.verify({"replicas": 3}).verdict is Verdict.UNSUPPORTED  # not FALSE, not SUPPORTED


# U1 — model cannot create verification (structural, at construction)
def test_model_cannot_construct_verification_without_procedure():
    with pytest.raises(Exception):
        WorldVerification(record_id="v", tenant=ACME, recorded_at=_utc(10, 0),
                          provenance=ProvenanceRef(produced_by="model", observation_ref="o"),
                          subject_ref="s", procedure_ref="",  # no procedure
                          verifier=DEFAULT_VERIFIER_IDENTITY, verdict=Verdict.SUPPORTED,
                          evidence_refs=("o",))


# U1/G — self-verification refused (verifier shares producer reasoning path)
def test_self_verification_is_refused():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
    dependent = VerifierIdentity(verifier_id="model", reasoning_path_id=MODEL_PATH,
                                 model_identifier="gpt")  # same path as producer
    with pytest.raises(AssuranceRefused):
        w.verify({"replicas": 5}, verifier=dependent, producer=MODEL_PATH)


# U2 — model confidence cannot become verification (no such input path)
def test_verifier_ignores_any_model_claim_uses_world_only():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
    # the "claim" is only the expected value; the verdict comes from world state,
    # never from a model-asserted success. Claiming 3 when the world says 5 -> UNSUPPORTED.
    assert w.verify({"replicas": 3}).verdict is Verdict.UNSUPPORTED


# U3 — missing evidence cannot verify
def test_missing_evidence_is_insufficient():
    w = World()  # no observations
    assert w.verify({"replicas": 5}).verdict is Verdict.INSUFFICIENT_EVIDENCE


# U5 — UNKNOWN world state cannot verify
def test_unknown_world_state_is_insufficient():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
    # verify at a valid time before any observation -> UNKNOWN
    assert w.verify({"replicas": 5}, at_valid=_utc(9, 0)).verdict is Verdict.INSUFFICIENT_EVIDENCE


# U4 — stale evidence cannot verify (policy requires fresh)
def test_stale_evidence_is_insufficient():
    freshness = FreshnessPolicy(rules=(FreshnessRule(horizon_seconds=600, predicate="spec.replicas"),))
    w = World(freshness=freshness, policy=AssurancePolicy(require_fresh=True))
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
    r = w.verify({"replicas": 5}, now=_utc(10, 30))  # 30m old
    assert r.verdict is Verdict.INSUFFICIENT_EVIDENCE  # stale != verified


# U6 — conflicted evidence cannot verify
def test_conflicted_evidence_is_insufficient():
    authority = AuthorityPolicy(rules=(AuthorityRule(tier=SourceAuthority.AUTHORITATIVE,
                                                     source_kind="connector"),))
    w = World(authority=authority)
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref="connector:a")
    w.observe(value={"replicas": 3}, observed_at=_utc(10, 0), source_ref="connector:b")
    assert w.verify({"replicas": 5}, now=_utc(10, 10)).verdict is Verdict.INSUFFICIENT_EVIDENCE


# U8 — same-lineage evidence cannot be claimed independent (require_known_lineage)
def test_unknown_lineage_cannot_prove_independence():
    w = World(lineage=LineagePolicy.none(), policy=AssurancePolicy(require_known_lineage=True))
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    # lineage unknown -> cannot prove independence -> INSUFFICIENT (no false independence)
    assert w.verify({"replicas": 5}).verdict is Verdict.INSUFFICIENT_EVIDENCE


def test_known_lineage_permits_verification():
    lineage = LineagePolicy(rules=(LineageRule(origin_id="cp", relation=LineageRelation.DIRECT,
                                               source_ref=K8S),))
    w = World(lineage=lineage, policy=AssurancePolicy(require_known_lineage=True))
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), source_ref=K8S)
    assert w.verify({"replicas": 5}).verdict is Verdict.SUPPORTED


# U9 — tenant A cannot use tenant B evidence
def test_tenant_isolation():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0), tenant=ACME)
    # OTHER tenant verifying the same subject sees no evidence
    assert w.verify({"replicas": 5}, tenant=OTHER).verdict is Verdict.INSUFFICIENT_EVIDENCE


# U10/U11 — verification carries explicit procedure + verifier identity
def test_verification_carries_procedure_and_verifier():
    w = World()
    w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
    r = w.verify({"replicas": 5})
    assert r.verification.procedure_ref.startswith("procedure:compare_world_state")
    assert r.verification.verifier.model_identifier is None  # deterministic verifier
    assert r.verification.verifier.reasoning_path_id != MODEL_PATH  # independent of producer


# U14 — future evidence cannot leak backward (knowledge time)
def test_future_evidence_does_not_leak_backward():
    w = World()
    # value observed at 10:00 but recorded (knowledge) at 10:10 via a late-arriving obs.
    # verify as known at 10:05 -> not yet known -> INSUFFICIENT.
    o = Observation(
        record_id="late", tenant=ACME, recorded_at=_utc(10, 10),
        provenance=ProvenanceRef(produced_by=K8S, execution_ref="ex-1", source_ref=K8S),
        source=ObservationSource(kind=ObservationSourceKind.CONNECTOR, source_ref=K8S),
        subject_ref="deployment/payments", predicate="spec.replicas", value={"replicas": 5},
        status=SourceStatus.RETURNED_DATA,
        instant=ObservationInstant(observed_at=_utc(10, 0), retrieved_at=_utc(10, 10)))
    w.obs.put(o)
    w.derivation.derive(tenant=ACME, observation=o, recorded_at=_utc(10, 10))
    proc = VerificationProcedure(kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
                                 subject_ref="deployment/payments", predicate="spec.replicas",
                                 expected={"replicas": 5}, at_valid=_utc(10, 5))
    r = w.verifier.verify(tenant=ACME, procedure=proc, producer_reasoning_path=MODEL_PATH,
                          verified_at=_utc(10, 5), known_at=_utc(10, 5))
    assert r.verdict is Verdict.INSUFFICIENT_EVIDENCE  # the 10:10 recording is invisible at 10:05


# U19 — no model-generated verifier code: procedure kinds are a closed enum
def test_procedure_kinds_are_a_closed_enum():
    assert set(k.value for k in VerificationProcedureKind) == {
        "compare_world_state", "compare_prediction_outcome", "inspect_execution_result"}


# U20 — deterministic repeated evaluation
def test_deterministic_repeated_evaluation():
    def run():
        w = World()
        w.observe(value={"replicas": 5}, observed_at=_utc(10, 0))
        return w.verify({"replicas": 5}).to_dict()
    a, b = run(), run()
    assert a["verdict"] == b["verdict"] and a["what"] == b["what"]
    assert a["procedure_ref"] == b["procedure_ref"]


# non-tenantref refused
def test_non_tenantref_refused():
    w = World()
    with pytest.raises(AssuranceRefused):
        w.verify({"replicas": 5}, tenant="acme")
