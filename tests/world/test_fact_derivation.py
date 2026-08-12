"""Phase 7.3 — deterministic Observation -> Fact derivation (STEP 22 A/B/D/E/F/G/H/I).

Unit-level against an in-memory FactRepository: identity, succession vs conflict,
UNKNOWN, the confidence firewall, provenance chain, tenant scoping, idempotency.
The bitemporal query semantics and the load-bearing example are in
test_bitemporal_queries.py; real-Postgres crash/replay is the phase73 harness.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.evidence import SourceStatus
from backend.contracts.knowledge import KnowledgeAuthority
from backend.contracts.tenant import TenantRef
from backend.contracts.world import (
    ClaimConfidence,
    EpistemicStatus,
    Fact,
    ModelStatedConfidence,
    Observation,
    ObservationInstant,
    ObservationSource,
    ObservationSourceKind,
    ProvenanceRef,
)
from backend.world.application import (
    DerivationOutcome,
    FactDerivation,
    FactDerivationRejected,
    FactVersion,
    fact_semantic_identity,
    fact_version_identity,
)

ACME = TenantRef(tenant_id="acme")
OTHER = TenantRef(tenant_id="other")
T1000 = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)
T1002 = datetime(2026, 8, 12, 10, 2, tzinfo=timezone.utc)
REC = datetime(2026, 8, 12, 10, 4, tzinfo=timezone.utc)


class MemFactRepo:
    """In-memory FactRepository — append-only by construction (no update/delete),
    dedupes on version identity, reads tenant-scoped."""

    def __init__(self):
        self.by_version: dict[str, FactVersion] = {}
        self.record_calls = 0

    def record(self, fact, *, version_digest, semantic_identity, value_digest):
        self.record_calls += 1
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
                     if v.tenant_id == tenant_id
                     and v.semantic_identity == semantic_identity)


def _obs(value, observed_at=T1000, *, tenant=ACME, subject="deployment/payments",
         predicate="spec.replicas", status=SourceStatus.RETURNED_DATA,
         retrieved_at=None, exec_ref="ex-1", obs_id="obs-1"):
    retrieved_at = retrieved_at or (observed_at + timedelta(minutes=4))
    return Observation(
        record_id=obs_id, tenant=tenant, recorded_at=retrieved_at,
        provenance=ProvenanceRef(produced_by="connector:kubernetes",
                                 execution_ref=exec_ref, trace_ref="corr-1",
                                 source_ref="connector:kubernetes"),
        source=ObservationSource(kind=ObservationSourceKind.CONNECTOR,
                                 source_ref="connector:kubernetes"),
        subject_ref=subject, predicate=predicate, value=value, status=status,
        instant=ObservationInstant(observed_at=observed_at, retrieved_at=retrieved_at))


def _derive(repo, observation, tenant=ACME, recorded_at=REC):
    return FactDerivation(repository=repo).derive(
        tenant=tenant, observation=observation, recorded_at=recorded_at)


# ======================================================================
# A — the Observation -> Fact boundary
# ======================================================================

class TestBoundary:
    def test_a_real_observation_becomes_a_grounded_fact(self):
        repo = MemFactRepo()
        result = _derive(repo, _obs(5))
        assert result.outcome is DerivationOutcome.ASSERTED
        assert isinstance(result.fact, Fact)
        assert result.fact.subject_ref == "deployment/payments"
        assert result.fact.predicate == "spec.replicas"
        assert result.fact.value == 5  # structured value, not prose
        assert result.fact.status is EpistemicStatus.AFFIRMED

    def test_non_tenantref_is_refused(self):
        with pytest.raises(FactDerivationRejected):
            _derive(MemFactRepo(), _obs(5), tenant="acme")

    def test_observation_of_another_tenant_is_refused(self):
        # governed tenant ACME, observation belongs to OTHER -> fail closed
        with pytest.raises(FactDerivationRejected):
            _derive(MemFactRepo(), _obs(5, tenant=OTHER), tenant=ACME)

    def test_derive_requires_a_real_observation_object(self):
        with pytest.raises(FactDerivationRejected):
            FactDerivation(repository=MemFactRepo()).derive(
                tenant=ACME, observation={"value": 5}, recorded_at=REC)  # type: ignore[arg-type]

    def test_non_informative_observation_derives_no_fact(self):
        # empty read: no value to assert -> UNKNOWN, not FALSE, no fact
        repo = MemFactRepo()
        result = _derive(repo, _obs(None, status=SourceStatus.RETURNED_EMPTY))
        assert result.outcome is DerivationOutcome.SKIPPED_NON_INFORMATIVE
        assert result.fact is None
        assert repo.record_calls == 0


# ======================================================================
# B — semantic identity
# ======================================================================

class TestIdentity:
    def test_same_proposition_same_identity(self):
        a = fact_semantic_identity(ACME, "deployment/payments", "spec.replicas")
        b = fact_semantic_identity(ACME, "deployment/payments", "spec.replicas")
        assert a == b

    def test_different_predicate_or_subject_is_a_different_identity(self):
        base = fact_semantic_identity(ACME, "deployment/payments", "spec.replicas")
        assert base != fact_semantic_identity(ACME, "deployment/payments", "status.phase")
        assert base != fact_semantic_identity(ACME, "deployment/web", "spec.replicas")

    def test_tenant_is_part_of_identity(self):
        assert (fact_semantic_identity(ACME, "deployment/payments", "spec.replicas")
                != fact_semantic_identity(OTHER, "deployment/payments", "spec.replicas"))

    def test_version_identity_key_order_independent(self):
        sid = fact_semantic_identity(ACME, "d", "p")
        a = fact_version_identity(sid, {"a": 1, "b": 2}, T1000)
        b = fact_version_identity(sid, {"b": 2, "a": 1}, T1000)
        assert a == b

    def test_changed_value_is_a_new_version_identity(self):
        sid = fact_semantic_identity(ACME, "d", "p")
        assert fact_version_identity(sid, 5, T1000) != fact_version_identity(sid, 3, T1000)


# ======================================================================
# D — conflict: same valid instant, different value, no authority
# ======================================================================

class TestConflict:
    def test_same_valid_instant_different_value_is_conflicted(self):
        repo = MemFactRepo()
        _derive(repo, _obs(5, T1000, obs_id="o5"), recorded_at=REC)
        # different value, SAME valid_from, arriving later
        result = _derive(repo, _obs(3, T1000, obs_id="o3"),
                         recorded_at=REC + timedelta(minutes=6))
        assert result.outcome is DerivationOutcome.CONFLICTED
        assert result.fact.status is EpistemicStatus.CONFLICTED
        assert len(repo.by_version) == 2  # both retained

    def test_conflict_is_not_resolved_by_arrival_order(self):
        # deriving 3-then-5 and 5-then-3 must both end CONFLICTED, not "latest wins"
        r1 = MemFactRepo()
        _derive(r1, _obs(5, T1000, obs_id="a"))
        out1 = _derive(r1, _obs(3, T1000, obs_id="b"), recorded_at=REC + timedelta(minutes=1))
        r2 = MemFactRepo()
        _derive(r2, _obs(3, T1000, obs_id="c"))
        out2 = _derive(r2, _obs(5, T1000, obs_id="d"), recorded_at=REC + timedelta(minutes=1))
        assert out1.outcome is DerivationOutcome.CONFLICTED
        assert out2.outcome is DerivationOutcome.CONFLICTED

    def test_later_world_change_is_succession_not_conflict(self):
        repo = MemFactRepo()
        _derive(repo, _obs(5, T1000, obs_id="o5"))
        result = _derive(repo, _obs(3, T1002, obs_id="o3"),  # different valid_from
                         recorded_at=REC + timedelta(minutes=6))
        assert result.outcome is DerivationOutcome.ASSERTED
        assert result.fact.status is EpistemicStatus.AFFIRMED


# ======================================================================
# E — epistemic status is never FALSE from absence
# ======================================================================

class TestStatus:
    def test_epistemic_status_has_no_false_member(self):
        assert not any(s.name == "FALSE" for s in EpistemicStatus)

    def test_absence_derives_unknown_never_false(self):
        repo = MemFactRepo()
        result = _derive(repo, _obs(None, status=SourceStatus.UNAVAILABLE))
        assert result.outcome is DerivationOutcome.SKIPPED_NON_INFORMATIVE
        # nothing recorded -> the identity is UNKNOWN by projection, never FALSE
        assert repo.by_version == {}


# ======================================================================
# F — confidence firewall (STEP 10/12)
# ======================================================================

class TestConfidenceFirewall:
    def test_fact_carries_no_confidence(self):
        fact = _derive(MemFactRepo(), _obs(5)).fact
        assert not hasattr(fact, "confidence")

    def test_derived_fact_authority_is_advisory_not_a_number(self):
        fact = _derive(MemFactRepo(), _obs(5)).fact
        # a single uncorroborated source -> ADVISORY tier, never an invented float
        assert fact.authority is KnowledgeAuthority.ADVISORY

    def test_model_stated_confidence_cannot_become_claim_confidence(self):
        msc = ModelStatedConfidence(stated_value=0.95, stated_by="model")
        # separate, unconvertible types — no method turns one into the other
        assert not hasattr(msc, "to_claim_confidence")
        assert not isinstance(msc, ClaimConfidence)
        # the only permissible default remains UNCALIBRATED (no number)
        assert ClaimConfidence.uncalibrated().value is None


# ======================================================================
# G — provenance chain (STEP 11)
# ======================================================================

class TestProvenance:
    def test_fact_grounds_in_its_observation_and_execution(self):
        fact = _derive(MemFactRepo(), _obs(5, exec_ref="ex-42")).fact
        assert fact.provenance.observation_ref == "obs-1"
        assert fact.provenance.execution_ref == "ex-42"
        assert fact.provenance.trace_ref == "corr-1"

    def test_succession_records_parent_lineage(self):
        repo = MemFactRepo()
        first = _derive(repo, _obs(5, T1000, obs_id="o5")).fact
        second = _derive(repo, _obs(3, T1002, obs_id="o3"),
                         recorded_at=REC + timedelta(minutes=6)).fact
        assert second.provenance.parent_claim_ref == first.record_id


# ======================================================================
# H — tenant scoping
# ======================================================================

class TestTenant:
    def test_two_tenants_are_independent_state(self):
        repo = MemFactRepo()
        _derive(repo, _obs(5, tenant=ACME, obs_id="a"), tenant=ACME)
        _derive(repo, _obs(5, tenant=OTHER, obs_id="b"), tenant=OTHER)
        sid_acme = fact_semantic_identity(ACME, "deployment/payments", "spec.replicas")
        acme_versions = repo.versions_for(tenant_id="acme", semantic_identity=sid_acme)
        # ACME's identity read under ACME sees exactly its own version
        assert len(acme_versions) == 1
        assert acme_versions[0].tenant_id == "acme"
        # and reading OTHER's identity under ACME's semantic id sees nothing
        assert repo.versions_for(tenant_id="other", semantic_identity=sid_acme) == ()


# ======================================================================
# I — idempotency (STEP 15): repeated derivation, deterministic no-op
# ======================================================================

class TestIdempotency:
    def test_repeated_identical_observation_dedupes(self):
        repo = MemFactRepo()
        first = _derive(repo, _obs(5))
        again = _derive(repo, _obs(5))
        assert first.outcome is DerivationOutcome.ASSERTED
        assert again.outcome is DerivationOutcome.DEDUPED
        assert len(repo.by_version) == 1

    def test_same_value_later_valid_time_is_a_noop(self):
        repo = MemFactRepo()
        _derive(repo, _obs(5, T1000))
        again = _derive(repo, _obs(5, T1002))  # same value, later valid_from
        assert again.outcome is DerivationOutcome.DEDUPED
        assert len(repo.by_version) == 1
