"""Phase 8.1 — the investigation state machine (Part U unit matrix).

An investigation is a durable, tenant-scoped, append-only state machine. The
model proposes; the platform decides. Invalid transitions refuse; autonomy is
platform-set and never model-promotable; secret-bearing artifacts are refused;
snapshots are immutable. In-memory repository; real-Postgres crash/recovery is the
phase81 harness.
"""

from __future__ import annotations

from datetime import datetime, timezone

import dataclasses
import pytest

from backend.contracts.tenant import TenantRef
from backend.contracts.world import HypothesisStatus
from backend.contracts.intelligence import (
    AutonomyLevel,
    DifferentialHypothesis,
    HumanEvent,
    HumanEventKind,
    Investigation,
    InvestigationStatus,
    InvestigationTest,
    TemporalFit,
    is_legal_transition,
    is_terminal_status,
)
from backend.contracts.world import ProvenanceRef
from backend.intelligence.application import (
    AutonomyRefused,
    InvestigationNotFound,
    InvestigationRejected,
    InvestigationService,
    InvestigationTransitionRefused,
)

ACME = TenantRef(tenant_id="acme")
OTHER = TenantRef(tenant_id="other")
NOW = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


class MemRepo:
    """In-memory append-only event ledger, tenant-scoped, optimistic concurrency."""

    def __init__(self):
        self.by_identity = {}
        self.events = []  # (investigation_id, tenant_id, seq, state)

    def append(self, *, event_id, identity_digest, investigation_id, tenant_id,
               incident_ref, seq, event_kind, from_status, to_status,
               autonomy_level, state, payload, recorded_at):
        if identity_digest in self.by_identity:
            return False
        self.by_identity[identity_digest] = True
        self.events.append((investigation_id, tenant_id, seq, state))
        return True

    def latest_state(self, *, tenant_id, investigation_id):
        rows = [e for e in self.events
                if e[0] == investigation_id and e[1] == tenant_id]
        if not rows:
            return None
        return max(rows, key=lambda e: e[2])[3]


def _svc():
    return InvestigationService(repository=MemRepo())


def _open(svc, *, tenant=ACME, autonomy=AutonomyLevel.A1_INVESTIGATE):
    inv = svc.create(tenant=tenant, incident_ref="incident:pay-5xx", policy_ref="pol/1",
                     harness_version="h/1", now=NOW, autonomy_level=autonomy)
    return svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                          cause="triage", now=_t(1))


def _hyp(ref="h1", value="rollout", status=HypothesisStatus.OPEN, created_by="model:gpt"):
    return DifferentialHypothesis(
        hypothesis_ref=ref, subject_ref="deployment/payments", proposition=value,
        status=status, temporal_fit=TemporalFit.CONSISTENT, created_by=created_by,
        evidence_for=("wfact-1",))


# ======================================================================
# Contract + state machine
# ======================================================================

class TestStateMachine:
    def test_created_then_investigating(self):
        svc = _svc()
        inv = svc.create(tenant=ACME, incident_ref="i", policy_ref="p", harness_version="h", now=NOW)
        assert inv.status is InvestigationStatus.CREATED and inv.seq == 0
        moved = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                               cause="x", now=_t(1))
        assert moved.status is InvestigationStatus.INVESTIGATING and moved.seq == 1

    def test_illegal_transition_refused(self):
        svc = _svc()
        inv = svc.create(tenant=ACME, incident_ref="i", policy_ref="p", harness_version="h", now=NOW)
        with pytest.raises(InvestigationTransitionRefused):
            svc.transition(investigation=inv, to_status=InvestigationStatus.COMPLETED,
                           cause="skip", now=_t(1))  # CREATED -> COMPLETED illegal

    def test_terminal_refuses_further_transition(self):
        svc = _svc()
        inv = _open(svc)
        done = svc.transition(investigation=inv, to_status=InvestigationStatus.ABANDONED,
                              cause="stop", now=_t(2))
        assert is_terminal_status(done.status)
        with pytest.raises(InvestigationTransitionRefused):
            svc.transition(investigation=done, to_status=InvestigationStatus.INVESTIGATING,
                           cause="resume", now=_t(3))

    def test_verifying_can_return_to_investigating_not_skip(self):
        # UNKNOWN/INSUFFICIENT verification must not become COMPLETED by skipping
        assert is_legal_transition(InvestigationStatus.VERIFYING, InvestigationStatus.INVESTIGATING)
        assert is_legal_transition(InvestigationStatus.VERIFYING, InvestigationStatus.COMPLETED)
        assert not is_legal_transition(InvestigationStatus.EXECUTING, InvestigationStatus.COMPLETED)


# ======================================================================
# Autonomy — platform-set, never model-promotable
# ======================================================================

class TestAutonomy:
    def test_default_is_a1(self):
        svc = _svc()
        inv = svc.create(tenant=ACME, incident_ref="i", policy_ref="p", harness_version="h", now=NOW)
        assert inv.autonomy_level is AutonomyLevel.A1_INVESTIGATE

    def test_a1_cannot_execute(self):
        svc = _svc()
        inv = _open(svc, autonomy=AutonomyLevel.A1_INVESTIGATE)
        ready = svc.transition(investigation=inv, to_status=InvestigationStatus.READY_FOR_ACTION,
                               cause="diagnosed", now=_t(2))
        with pytest.raises(AutonomyRefused):
            svc.transition(investigation=ready, to_status=InvestigationStatus.EXECUTING,
                           cause="act", now=_t(3))

    def test_a3_requires_human_approval_to_execute(self):
        svc = _svc()
        inv = _open(svc, autonomy=AutonomyLevel.A3_APPROVED_ACTION)
        ready = svc.transition(investigation=inv, to_status=InvestigationStatus.READY_FOR_ACTION,
                               cause="diagnosed", now=_t(2))
        with pytest.raises(AutonomyRefused):  # no human approval
            svc.transition(investigation=ready, to_status=InvestigationStatus.EXECUTING,
                           cause="act", now=_t(3))
        approval = HumanEvent(kind=HumanEventKind.APPROVED, actor_ref="approval:req-1",
                              reason="rollback authorized")
        executing = svc.transition(investigation=ready, to_status=InvestigationStatus.EXECUTING,
                                   cause="act", now=_t(4), human_event=approval)
        assert executing.status is InvestigationStatus.EXECUTING

    def test_model_cannot_promote_autonomy(self):
        # a hypothesis (model proposal) carrying an "autonomy" claim has no effect
        svc = _svc()
        inv = _open(svc, autonomy=AutonomyLevel.A1_INVESTIGATE)
        updated = svc.upsert_hypothesis(investigation=inv, hypothesis=_hyp(), now=_t(2))
        assert updated.autonomy_level is AutonomyLevel.A1_INVESTIGATE  # unchanged
        # and there is no service method to raise autonomy
        assert not hasattr(svc, "promote_autonomy")
        assert not hasattr(svc, "set_autonomy")


# ======================================================================
# Differential diagnosis — a SET, no numeric confidence
# ======================================================================

class TestDifferential:
    def test_hypothesis_set_supports_multiple_candidates(self):
        svc = _svc()
        inv = _open(svc)
        inv = svc.upsert_hypothesis(investigation=inv, hypothesis=_hyp("h1", "rollout"), now=_t(2))
        inv = svc.upsert_hypothesis(investigation=inv, hypothesis=_hyp("h2", "db-saturation"), now=_t(3))
        assert {h.hypothesis_ref for h in inv.differential} == {"h1", "h2"}

    def test_upsert_replaces_by_ref(self):
        svc = _svc()
        inv = _open(svc)
        inv = svc.upsert_hypothesis(investigation=inv, hypothesis=_hyp("h1", status=HypothesisStatus.OPEN), now=_t(2))
        inv = svc.upsert_hypothesis(investigation=inv,
                                    hypothesis=_hyp("h1", status=HypothesisStatus.REFUTED), now=_t(3))
        assert len(inv.differential) == 1
        assert inv.differential[0].status is HypothesisStatus.REFUTED

    def test_no_numeric_confidence_field(self):
        h = _hyp()
        assert not hasattr(h, "confidence")


# ======================================================================
# Tenant isolation — fail closed
# ======================================================================

class TestTenant:
    def test_reconstruct_is_tenant_scoped(self):
        repo = MemRepo()
        svc = InvestigationService(repository=repo)
        inv = svc.create(tenant=ACME, incident_ref="i", policy_ref="p", harness_version="h", now=NOW)
        # ACME reconstructs; OTHER fails closed
        assert svc.reconstruct(tenant=ACME, investigation_ref=inv.investigation_ref).status \
            is InvestigationStatus.CREATED
        with pytest.raises(InvestigationNotFound):
            svc.reconstruct(tenant=OTHER, investigation_ref=inv.investigation_ref)

    def test_non_tenantref_refused(self):
        svc = _svc()
        with pytest.raises(InvestigationRejected):
            svc.create(tenant="acme", incident_ref="i", policy_ref="p", harness_version="h", now=NOW)


# ======================================================================
# Secret firewall
# ======================================================================

class TestSecretFirewall:
    def test_secret_bearing_hypothesis_refused(self):
        svc = _svc()
        inv = _open(svc)
        bad = DifferentialHypothesis(
            hypothesis_ref="h", subject_ref="s", proposition="token=ghp_ABCDEFabcdef0123456789",
            status=HypothesisStatus.OPEN, temporal_fit=TemporalFit.UNKNOWN, created_by="model")
        with pytest.raises(InvestigationRejected):
            svc.upsert_hypothesis(investigation=inv, hypothesis=bad, now=_t(2))


# ======================================================================
# Immutability of the aggregate + model boundary discipline
# ======================================================================

class TestImmutabilityAndBoundary:
    def test_investigation_is_frozen(self):
        svc = _svc()
        inv = _open(svc)
        with pytest.raises(dataclasses.FrozenInstanceError):
            inv.status = InvestigationStatus.COMPLETED  # type: ignore[misc]

    def test_seq_advances_and_snapshots_round_trip(self):
        svc = _svc()
        inv = _open(svc)
        inv2 = svc.upsert_hypothesis(investigation=inv, hypothesis=_hyp(), now=_t(2))
        assert inv2.seq == inv.seq + 1
        # snapshot round-trips through the contract envelope
        assert Investigation.from_dict(inv2.to_dict()) == inv2

    def test_human_event_actor_must_be_namespaced_identity(self):
        with pytest.raises(Exception):
            HumanEvent(kind=HumanEventKind.APPROVED, actor_ref="John", reason="ok")  # bare name
        ok = HumanEvent(kind=HumanEventKind.APPROVED, actor_ref="approval:req-9", reason="ok")
        assert ok.actor_ref == "approval:req-9"

    def test_investigation_test_has_falsifiable_fields(self):
        t = InvestigationTest(
            test_ref="t1", investigation_ref="winv-1", tenant=ACME,
            discriminates_hypothesis="h1", evidence_expected="deploy history for payments",
            supports_if="deploy at incident time", contradicts_if="no deploy in window",
            residual_uncertainty="still could be db", created_by="model:gpt",
            provenance=ProvenanceRef(produced_by="model:gpt", parent_claim_ref="winv-1"))
        assert t.discriminates_hypothesis == "h1" and t.contradicts_if
