"""Phase 7.8 — the durable reasoning trail + the epistemic-firewall negative
matrix (Part U). The ledger persists only the non-reconstructable model-authored
artifacts, immutably, tenant-scoped, idempotently, and secret-free; the contracts
keep model output from becoming Fact/Belief/Outcome/Verification.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.tenant import TenantRef
from backend.contracts.verification import Verdict, VerifierIdentity
from backend.contracts.world import (
    Belief,
    ClaimConfidence,
    EpistemicStatus,
    Fact,
    Hypothesis,
    HypothesisStatus,
    ModelHypothesisProposal,
    Observation,
    Outcome,
    Prediction,
    ProvenanceRef,
    WorldVerification,
)
from backend.world.application import (
    HypothesisEvidence,
    HypothesisFormation,
    PredictionEvaluation,
    ReasoningKind,
    ReasoningLedger,
    ReasoningRejected,
    evaluate_prediction,
)

ACME, OTHER = TenantRef(tenant_id="acme"), TenantRef(tenant_id="other")


def _utc(h, m):
    return datetime(2026, 8, 12, h, m, tzinfo=timezone.utc)


class MemReasoningRepo:
    def __init__(self):
        self.by_identity = {}
        self.rows = []

    def record(self, *, reasoning_id, identity_digest, tenant_id, kind, subject_ref,
               predicate, record, refs, recorded_at):
        if identity_digest in self.by_identity:
            return False
        row = dict(reasoning_id=reasoning_id, tenant_id=tenant_id, kind=kind,
                   subject_ref=subject_ref, record=record, refs=refs)
        self.by_identity[identity_digest] = row
        self.rows.append(row)
        return True


def _ledger():
    n = {"i": 0}

    def _id():
        n["i"] += 1
        return f"wreason-{n['i']}"
    return ReasoningLedger(repository=MemReasoningRepo(), id_factory=_id)


def _hypothesis():
    proposal = ModelHypothesisProposal(
        record_id="mp", tenant=ACME, recorded_at=_utc(10, 0),
        provenance=ProvenanceRef(produced_by="model", parent_claim_ref="turn-1"),
        claim="rollout caused the 5xx spike", proposed_by="model:gpt",
        subject_ref="deployment/payments", suggested_investigation="diff the rollout")
    return HypothesisFormation().ground(
        tenant=ACME, proposal=proposal, recorded_at=_utc(10, 1),
        evidence=HypothesisEvidence(support_refs=("wfact-1",), falsifier="5xx persists"))


def _prediction(h):
    return Prediction(record_id="pr", tenant=ACME, recorded_at=_utc(10, 2),
                      provenance=ProvenanceRef(produced_by="model", parent_claim_ref=h.record_id),
                      subject_ref="deployment/payments", predicate="error_rate",
                      expected={"below": "1%"}, predicted_at=_utc(10, 2), deadline=_utc(10, 7),
                      hypothesis_ref=h.record_id, basis=("wfact-1",))


# ======================================================================
# The reasoning ledger
# ======================================================================

class TestReasoningLedger:
    def test_records_hypothesis_prediction_evaluation(self):
        led = _ledger()
        h = _hypothesis()
        p = _prediction(h)
        outcome = Outcome(record_id="oc", tenant=ACME, recorded_at=_utc(10, 6),
                          provenance=ProvenanceRef(produced_by="platform", execution_ref="ex-9"),
                          execution_ref="ex-9", observed={"below": "1%"}, prediction_ref="pr")
        ev = evaluate_prediction(prediction=p, outcome=outcome, observed_at=_utc(10, 6))
        _, n1 = led.record_hypothesis(tenant=ACME, subject_ref="deployment/payments", hypothesis=h, recorded_at=_utc(10, 1))
        _, n2 = led.record_prediction(tenant=ACME, prediction=p, recorded_at=_utc(10, 2))
        _, n3 = led.record_evaluation(tenant=ACME, subject_ref="deployment/payments",
                                      evaluation=ev, recorded_at=_utc(10, 6))
        assert n1 and n2 and n3
        kinds = {r["kind"] for r in led._repository.rows}
        assert kinds == {ReasoningKind.HYPOTHESIS.value, ReasoningKind.PREDICTION.value,
                         ReasoningKind.PREDICTION_EVALUATION.value}

    def test_idempotent(self):
        led = _ledger()
        p = _prediction(_hypothesis())
        _, first = led.record_prediction(tenant=ACME, prediction=p, recorded_at=_utc(10, 2))
        _, second = led.record_prediction(tenant=ACME, prediction=p, recorded_at=_utc(10, 2))
        assert first is True and second is False
        assert len(led._repository.rows) == 1

    def test_non_tenantref_refused(self):
        led = _ledger()
        with pytest.raises(ReasoningRejected):
            led.record_prediction(tenant="acme", prediction=_prediction(_hypothesis()),
                                  recorded_at=_utc(10, 2))

    def test_secret_bearing_reasoning_refused(self):
        # a prediction whose expected value smuggles a credential is refused
        led = _ledger()
        h = _hypothesis()
        bad = Prediction(record_id="pr", tenant=ACME, recorded_at=_utc(10, 2),
                         provenance=ProvenanceRef(produced_by="model", parent_claim_ref=h.record_id),
                         subject_ref="deployment/payments", expected={"token": "ghp_ABCDEFabcdef0123456789"},
                         predicted_at=_utc(10, 2), deadline=_utc(10, 7), hypothesis_ref=h.record_id)
        with pytest.raises(ReasoningRejected):
            led.record_prediction(tenant=ACME, prediction=bad, recorded_at=_utc(10, 2))

    def test_prediction_carries_the_provenance_graph_refs(self):
        led = _ledger()
        h = _hypothesis()
        led.record_prediction(tenant=ACME, prediction=_prediction(h), recorded_at=_utc(10, 2))
        refs = led._repository.rows[0]["refs"]
        assert refs["hypothesis_ref"] == h.record_id
        assert refs["deadline"] is not None


# ======================================================================
# Negative matrix — the model cannot manufacture epistemic state (Part U)
# ======================================================================

class TestNegativeMatrix:
    def test_model_proposal_has_no_conversion_to_grounded_types(self):
        for banned in ("to_fact", "to_belief", "to_outcome", "to_verification", "to_hypothesis"):
            assert not hasattr(ModelHypothesisProposal, banned)

    def test_outcome_requires_execution_ref(self):
        with pytest.raises(Exception):
            Outcome(record_id="o", tenant=ACME, recorded_at=_utc(10, 0),
                    provenance=ProvenanceRef(produced_by="model", execution_ref="ex"),
                    execution_ref="", observed={"x": 1})  # empty execution_ref

    def test_outcome_uses_actual_state_not_model_success(self):
        # even if a model claimed success, the Outcome is built from the observed
        # (actual) result tied to a real execution_ref
        model_claimed = {"succeeded": True}
        actual = {"succeeded": False, "error_rate": "4.2%"}
        outcome = Outcome(record_id="oc", tenant=ACME, recorded_at=_utc(10, 9),
                          provenance=ProvenanceRef(produced_by="platform", execution_ref="ex-9"),
                          execution_ref="ex-9", observed=actual, prediction_ref="pr")
        assert outcome.observed == actual and outcome.observed != model_claimed

    def test_verification_requires_procedure_and_verifier(self):
        with pytest.raises(Exception):
            WorldVerification(record_id="v", tenant=ACME, recorded_at=_utc(10, 0),
                              provenance=ProvenanceRef(produced_by="assurance", observation_ref="o"),
                              subject_ref="s", procedure_ref="",  # no procedure
                              verifier=VerifierIdentity(verifier_id="v", reasoning_path_id="p"),
                              verdict=Verdict.SUPPORTED, evidence_refs=("o",))

    def test_prediction_horizon_enforced(self):
        with pytest.raises(Exception):
            Prediction(record_id="p", tenant=ACME, recorded_at=_utc(10, 0),
                       provenance=ProvenanceRef(produced_by="model", parent_claim_ref="h"),
                       subject_ref="s", expected={"x": 1}, predicted_at=_utc(10, 0),
                       deadline=_utc(9, 0))  # deadline before predicted_at

    def test_hypothesis_status_never_verified(self):
        assert not any(s.name == "VERIFIED" for s in HypothesisStatus)

    def test_grounded_hypothesis_needs_real_evidence(self):
        # a proposal with no evidence cannot become a hypothesis (7.6, re-asserted)
        from backend.world.application import HypothesisRejected
        proposal = ModelHypothesisProposal(
            record_id="mp", tenant=ACME, recorded_at=_utc(10, 0),
            provenance=ProvenanceRef(produced_by="model", parent_claim_ref="t"),
            claim="x", proposed_by="model", subject_ref="deployment/x")
        with pytest.raises(HypothesisRejected):
            HypothesisFormation().ground(tenant=ACME, proposal=proposal, recorded_at=_utc(10, 1),
                                         evidence=HypothesisEvidence())

    def test_evaluate_prediction_refuses_cross_tenant(self):
        h = _hypothesis()
        p = _prediction(h)
        outcome = Outcome(record_id="oc", tenant=OTHER, recorded_at=_utc(10, 6),
                          provenance=ProvenanceRef(produced_by="platform", execution_ref="ex"),
                          execution_ref="ex", observed={"below": "1%"})
        with pytest.raises(Exception):
            evaluate_prediction(prediction=p, outcome=outcome, observed_at=_utc(10, 6))
