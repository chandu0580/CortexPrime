"""Phase 8.5 — prediction -> governed action -> outcome -> assurance.

The model proposes a falsifiable prediction (firewall rejects self-declared
outcome/success/confidence); the platform validates it, governs the action,
derives the outcome from reality (never model text), evaluates deterministically,
and asks the INDEPENDENT Assurance Plane to verify — a self-verification is
refused, and UNKNOWN/STALE/CONFLICTED never become FALSE. In-memory scripted
ports; the real-Postgres lifecycle + crash/replay is the phase85 harness.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.contracts.tenant import TenantRef
from backend.contracts.verification import Verdict, VerifierIdentity
from backend.contracts.world import (
    HypothesisStatus, Outcome, ProvenanceRef,
)
from backend.contracts.intelligence import (
    DifferentialHypothesis, InvestigationStatus, TemporalFit,
)
from backend.assurance.application import AssuranceRefused, AssuranceVerifier
from backend.assurance.application.procedures import (
    VerificationProcedure, VerificationProcedureKind,
)
from backend.world.application import WorldQuery
from backend.intelligence.application import (
    ContextAssembler, InvestigationService, PredictionLifecycle, PredictionPolicy,
    PredictionProposalSchema, PredictionRejected, PredictionSupport, ProposedPrediction,
    OutcomeResolution, VerificationView,
)

ACME = TenantRef(tenant_id="acme")
EXPECTED = {"dependency_latency": "elevated"}
SUBJECT, PREDICATE = "dependency/stripe", "latency"


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


# ======================================================================
# The prediction-proposal firewall (Part C / T)
# ======================================================================

class TestPredictionFirewall:
    @pytest.mark.parametrize("bad", [
        {"outcome": {"ok": True}}, {"verified": True}, {"success": True},
        {"confidence": 0.93}, {"autonomy": "A4"}, {"provider": "openai"},
        {"model": "gpt-x"}, {"url": "http://x"}, {"command": "kubectl delete"},
        {"fact": {"v": 1}}, {"belief": {"v": 1}}, {"prediction": True},
    ])
    def test_smuggled_authority_field_rejected(self, bad):
        payload = {"hypothesis_ref": "h4", "subject_ref": SUBJECT, "predicate": PREDICATE,
                   "expected": EXPECTED, **bad}
        with pytest.raises(ValidationError):
            PredictionProposalSchema.model_validate(payload)

    def test_valid_minimal_parses(self):
        ok = PredictionProposalSchema.model_validate(
            {"hypothesis_ref": "h4", "subject_ref": SUBJECT, "predicate": PREDICATE,
             "expected": EXPECTED})
        assert ok.evaluation_window_seconds == 300 and ok.expected == EXPECTED


# ======================================================================
# Prediction policy (Part B / D)
# ======================================================================

def _diff(status=HypothesisStatus.SUPPORTED):
    return type("Inv", (), {"differential": (
        DifferentialHypothesis(hypothesis_ref="h4", subject_ref=SUBJECT, proposition="dependency",
                               status=status, temporal_fit=TemporalFit.CONSISTENT,
                               created_by="scripted:model"),), "evidence_refs": ()})()


def _proposed(**over):
    base = dict(hypothesis_ref="h4", subject_ref=SUBJECT, predicate=PREDICATE, expected=EXPECTED,
                expected_condition="dependency latency stays elevated", evaluation_window_seconds=300)
    base.update(over)
    return ProposedPrediction(**base)


class TestPredictionPolicy:
    def test_valid_prediction_passes(self):
        v = PredictionPolicy().validate(proposed=_proposed(), investigation=_diff())
        assert v.hypothesis_ref == "h4" and v.expected == EXPECTED

    def test_unknown_hypothesis_refused(self):
        with pytest.raises(PredictionRejected):
            PredictionPolicy().validate(proposed=_proposed(hypothesis_ref="hZ"), investigation=_diff())

    def test_missing_expected_refused(self):
        with pytest.raises(PredictionRejected):
            PredictionPolicy().validate(proposed=_proposed(expected=None), investigation=_diff())

    def test_url_subject_refused(self):
        with pytest.raises(PredictionRejected):
            PredictionPolicy().validate(proposed=_proposed(subject_ref="https://evil/x"),
                                        investigation=_diff())

    def test_nonpositive_window_refused(self):
        with pytest.raises(PredictionRejected):
            PredictionPolicy().validate(proposed=_proposed(evaluation_window_seconds=0),
                                        investigation=_diff())


# ======================================================================
# The lifecycle orchestrator (Part E/F/J/L)
# ======================================================================

class MemRepo:
    def __init__(self):
        self.by_identity, self.events = {}, []
    def append(self, *, event_id, identity_digest, investigation_id, tenant_id, incident_ref,
               seq, event_kind, from_status, to_status, autonomy_level, state, payload, recorded_at):
        if identity_digest in self.by_identity:
            return False
        self.by_identity[identity_digest] = True
        self.events.append((investigation_id, tenant_id, seq, state))
        return True
    def latest_state(self, *, tenant_id, investigation_id):
        rows = [e for e in self.events if e[0] == investigation_id and e[1] == tenant_id]
        return max(rows, key=lambda e: e[2])[3] if rows else None


class StubProposal:
    def propose_prediction(self, *, context, investigation, hypothesis_ref, now):
        return _proposed(hypothesis_ref=hypothesis_ref, provider="scripted")


class StubOutcome:
    """A governed action that returns a REAL Outcome built from a real execution_ref
    and the observed world value — NOT model text. ``observed`` is configurable."""
    def __init__(self, observed=EXPECTED, ok=True):
        self._observed, self._ok = observed, ok
        self.calls = 0
    def resolve(self, *, tenant, prediction_ref, subject_ref, predicate, expected, now):
        self.calls += 1
        if not self._ok:
            return OutcomeResolution(ok=False, reason="governed action blocked")
        if self._observed is None:
            return OutcomeResolution(ok=True, execution_ref="exec-1", observed_value=None,
                                     outcome=None, reason="no observation")
        outcome = Outcome(
            record_id="oc-1", tenant=tenant, recorded_at=now,
            provenance=ProvenanceRef(produced_by="platform", execution_ref="exec-1"),
            execution_ref="exec-1", observed=self._observed, observation_ref="wobs-1",
            prediction_ref=prediction_ref)
        return OutcomeResolution(ok=True, execution_ref="exec-1", observation_ref="wobs-1",
                                 observed_value=self._observed, outcome=outcome)


class StubVerifier:
    def __init__(self, verdict="supported", refs=("wobs-1",)):
        self._verdict, self._refs = verdict, refs
        self.calls = 0
    def verify_prediction(self, *, tenant, subject_ref, predicate, expected, execution_ref,
                          producer_reasoning_path, verified_at):
        self.calls += 1
        return VerificationView(verdict=self._verdict, verification_ref="wverif-1",
                                evidence_refs=self._refs, rationale="independent world check")


class StubLedger:
    def __init__(self):
        self.predictions, self.evaluations = [], []
    def record_prediction(self, *, tenant, prediction, recorded_at, harness_version=None):
        self.predictions.append(prediction)
        return ("wreason-p", True)
    def record_evaluation(self, *, tenant, subject_ref, evaluation, recorded_at, predicate=None):
        self.evaluations.append(evaluation)
        return ("wreason-e", True)


def _lifecycle(outcome=None, verifier=None, ledger=None):
    svc = InvestigationService(repository=MemRepo())
    life = PredictionLifecycle(
        service=svc, assembler=ContextAssembler(), proposal_port=StubProposal(),
        outcome_port=outcome or StubOutcome(), verifier_port=verifier or StubVerifier(),
        reasoning_ledger=ledger or StubLedger(), harness_version="h/1",
        available_tools=("metrics.window",))
    return svc, life


def _supported_inv(svc):
    inv = svc.create(tenant=ACME, incident_ref="incident:latency", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0))
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    return svc.upsert_hypothesis(investigation=inv, now=_t(2), hypothesis=DifferentialHypothesis(
        hypothesis_ref="h4", subject_ref=SUBJECT, proposition="dependency degradation",
        status=HypothesisStatus.SUPPORTED, temporal_fit=TemporalFit.CONSISTENT,
        created_by="scripted:model", evidence_for=("wobs-0",)))


class TestLifecycle:
    def test_full_lifecycle_distinguishes_three_judgements(self):
        svc, life = _lifecycle()
        inv = _supported_inv(svc)
        res = life.resolve(investigation=inv, hypothesis_ref="h4", now=_t(3))
        # diagnostic support (differential) vs prediction support (evaluation) vs
        # independent verification (assurance) — all distinct fields.
        assert res.diagnostic_support == "supported"
        assert res.prediction_support == PredictionSupport.SUPPORTED.value
        assert res.independent_verification == "supported"
        assert res.execution_ref == "exec-1" and res.verification_ref == "wverif-1"
        assert res.prediction_ref in {p.record_id for p in life._ledger.predictions}

    def test_outcome_comes_from_reality_not_model(self):
        # the world observed something OTHER than expected -> UNSUPPORTED, regardless
        # of any model wish. The outcome carried a real execution_ref.
        svc, life = _lifecycle(outcome=StubOutcome(observed={"dependency_latency": "normal"}))
        inv = _supported_inv(svc)
        res = life.resolve(investigation=inv, hypothesis_ref="h4", now=_t(3))
        assert res.prediction_support == PredictionSupport.UNSUPPORTED.value
        assert res.calibration["observed"] == {"dependency_latency": "normal"}
        assert res.execution_ref == "exec-1"

    def test_no_observation_is_insufficient_not_failure(self):
        svc, life = _lifecycle(outcome=StubOutcome(observed=None))
        inv = _supported_inv(svc)
        res = life.resolve(investigation=inv, hypothesis_ref="h4", now=_t(3))
        assert res.prediction_support == PredictionSupport.INSUFFICIENT_EVIDENCE.value
        assert res.prediction_support != PredictionSupport.UNSUPPORTED.value  # silence != wrong

    def test_blocked_action_is_insufficient(self):
        svc, life = _lifecycle(outcome=StubOutcome(ok=False))
        inv = _supported_inv(svc)
        res = life.resolve(investigation=inv, hypothesis_ref="h4", now=_t(3))
        assert res.prediction_support == PredictionSupport.INSUFFICIENT_EVIDENCE.value

    def test_calibration_bundle_captured(self):
        svc, life = _lifecycle()
        inv = _supported_inv(svc)
        res = life.resolve(investigation=inv, hypothesis_ref="h4", now=_t(3))
        cal = res.calibration
        for key in ("prediction_ref", "predicted_at", "hypothesis_ref", "expected", "observed",
                    "prediction_support", "independent_verification", "execution_ref",
                    "model_ref", "harness_version", "investigation_ref"):
            assert key in cal
        assert cal["model_ref"] == "scripted"  # calibration-ready, no calibration score


# ======================================================================
# Independent Assurance (Part I / K) — the REAL verifier
# ======================================================================

class _NoFacts:
    def versions_for(self, *, tenant_id, semantic_identity):
        return ()


class _NoObs:
    def get_observation(self, *, tenant_id, observation_id):
        return None


class TestSelfVerificationDefense:
    def _verifier(self):
        return AssuranceVerifier(query=WorldQuery(facts=_NoFacts(), observations=_NoObs()))

    def _proc(self):
        return VerificationProcedure(kind=VerificationProcedureKind.COMPARE_PREDICTION_OUTCOME,
                                     subject_ref=SUBJECT, predicate=PREDICATE, expected=EXPECTED,
                                     execution_ref="exec-1")

    def test_self_verification_is_refused(self):
        v = self._verifier()
        shared = VerifierIdentity(verifier_id="model-verifier",
                                  reasoning_path_id="model:gpt/turn-1")
        with pytest.raises(AssuranceRefused):
            v.verify(tenant=ACME, procedure=self._proc(),
                     producer_reasoning_path="model:gpt/turn-1", verified_at=_t(5), verifier=shared)

    def test_independent_verifier_on_unknown_world_is_insufficient_not_false(self):
        # the default deterministic verifier is independent; with no world evidence
        # the verdict is INSUFFICIENT_EVIDENCE — never UNSUPPORTED/FALSE (Part K).
        v = self._verifier()
        res = v.verify(tenant=ACME, procedure=self._proc(),
                       producer_reasoning_path="model:gpt/turn-1", verified_at=_t(5))
        assert res.verdict is Verdict.INSUFFICIENT_EVIDENCE
        assert res.verdict is not Verdict.UNSUPPORTED


# ======================================================================
# Outcome/Verification are fenced OUT of intelligence (Part F / U)
# ======================================================================

class TestOutcomeFencedInIntelligence:
    """Part U: the invariant 'intelligence cannot mint an Outcome/Verification' is
    ALREADY enforced by BND-MODEL-CANNOT-CREATE-FACT (Outcome ∈ grounded symbols,
    backend.intelligence ∈ model roots) — no new rule is added. Proven here."""

    def test_current_tree_passes(self):
        from backend.platform.architecture.boundary_rules import ModelCannotCreateFactRule
        from backend.platform.architecture.rules import ModuleGraph
        from pathlib import Path
        graph = ModuleGraph.build(Path(__file__).resolve().parents[2] / "backend")
        assert ModelCannotCreateFactRule().evaluate(graph).passed

    def test_synthetic_intelligence_constructing_outcome_fails(self, tmp_path):
        import textwrap
        from backend.platform.architecture.boundary_rules import ModelCannotCreateFactRule
        from backend.platform.architecture.rules import ModuleGraph
        root = tmp_path / "backend"
        (root / "intelligence" / "application").mkdir(parents=True)
        (root / "intelligence" / "application" / "rogue.py").write_text(
            textwrap.dedent("from backend.contracts.world.epistemic import Outcome\n"), encoding="utf-8")
        graph = ModuleGraph.build(root, package_root=root.name)
        assert not ModelCannotCreateFactRule().evaluate(graph).passed
