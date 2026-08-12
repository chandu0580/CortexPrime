"""Phase 7.1 — World Plane epistemic contract tests (Part T).

Contracts and invariants only. Every negative test proves the *refusal*
(a raised ContractViolation), not a boolean. No persistence, no execution.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.evidence import SourceStatus
from backend.contracts.knowledge import KnowledgeAuthority
from backend.contracts.tenant import TenantRef
from backend.contracts.verification import Verdict, VerifierIdentity
from backend.contracts.world import (
    Belief,
    CalibrationState,
    ClaimConfidence,
    EpistemicStatus,
    Fact,
    Hypothesis,
    HypothesisStatus,
    ModelProposal,
    ModelStatedConfidence,
    Observation,
    ObservationInstant,
    ObservationSource,
    ObservationSourceKind,
    Outcome,
    Prediction,
    ProvenanceRef,
    SecretInProvenance,
    SourceAuthority,
    ValidityInterval,
    WorldVerification,
)

NOW = datetime.now(timezone.utc)
T = TenantRef(tenant_id="acme")
PROV = ProvenanceRef(produced_by="connector:grafana", source_ref="connector:grafana")
GROUNDED = ProvenanceRef(produced_by="derivation:x", observation_ref="o1")
INSTANT = ObservationInstant(observed_at=NOW, retrieved_at=NOW)
SRC = ObservationSource(kind=ObservationSourceKind.CONNECTOR, source_ref="connector:grafana")


def _obs(**over):
    kw = dict(record_id="o1", tenant=T, recorded_at=NOW, provenance=PROV, source=SRC,
              subject_ref="deploy:x", predicate="replicas", value=3,
              status=SourceStatus.RETURNED_DATA, instant=INSTANT)
    kw.update(over)
    return Observation(**kw)


# ======================================================================
# 1. Every object requires tenant scope (Part M)
# ======================================================================

class TestTenantScope:
    def test_observation_requires_tenant_ref(self):
        with pytest.raises(ContractViolation):
            _obs(tenant="acme")  # a bare string, not a TenantRef

    def test_fact_requires_tenant_ref(self):
        with pytest.raises(ContractViolation):
            Fact(record_id="f1", tenant=None, recorded_at=NOW, provenance=GROUNDED,
                 subject_ref="s", predicate="p", value=1,
                 validity=ValidityInterval(valid_from=NOW),
                 authority=KnowledgeAuthority.ADVISORY, status=EpistemicStatus.AFFIRMED)

    def test_every_type_has_a_tenant_field(self):
        for typ in (Observation, Fact, Belief, Hypothesis, Prediction, Outcome,
                    WorldVerification, ModelProposal):
            assert "tenant" in {f for f in typ.__dataclass_fields__}


# ======================================================================
# 2 + 3. Observation is not a Fact; model output cannot instantiate a Fact
# ======================================================================

class TestObservationVsFact:
    def test_observation_is_not_a_fact_type(self):
        assert not issubclass(Observation, Fact)
        assert not issubclass(Fact, Observation)

    def test_fact_cannot_be_built_from_arbitrary_text(self):
        # There is no Fact.from_text / from_model / from_string.
        assert not hasattr(Fact, "from_text")
        assert not hasattr(Fact, "from_model")
        assert not hasattr(Fact, "from_string")

    def test_fact_from_observations_requires_real_observations(self):
        with pytest.raises(ContractViolation):
            Fact.from_observations(
                record_id="f1", tenant=T, recorded_at=NOW,
                observations=("not an observation",),  # a string, refused
                subject_ref="s", predicate="p", value=1,
                validity=ValidityInterval(valid_from=NOW),
                produced_by="derivation:x")

    def test_fact_from_observations_rejects_empty(self):
        with pytest.raises(ContractViolation):
            Fact.from_observations(
                record_id="f1", tenant=T, recorded_at=NOW, observations=(),
                subject_ref="s", predicate="p", value=1,
                validity=ValidityInterval(valid_from=NOW), produced_by="d")

    def test_fact_from_real_observation_succeeds(self):
        fact = Fact.from_observations(
            record_id="f1", tenant=T, recorded_at=NOW, observations=(_obs(),),
            subject_ref="deploy:x", predicate="replicas", value=3,
            validity=ValidityInterval(valid_from=NOW), produced_by="derivation:x")
        assert fact.provenance.observation_ref == "o1"

    def test_ungrounded_fact_is_refused(self):
        with pytest.raises(ContractViolation):
            Fact(record_id="f1", tenant=T, recorded_at=NOW,
                 provenance=ProvenanceRef(produced_by="model:gpt"),  # no anchor
                 subject_ref="s", predicate="p", value=1,
                 validity=ValidityInterval(valid_from=NOW),
                 authority=KnowledgeAuthority.ADVISORY, status=EpistemicStatus.AFFIRMED)

    def test_model_proposal_has_no_conversion_to_fact(self):
        mp = ModelProposal(record_id="m1", tenant=T, recorded_at=NOW,
                           provenance=PROV, content="replicas=3", proposed_by="gpt")
        assert not hasattr(mp, "to_fact")
        assert not hasattr(mp, "to_belief")
        assert not hasattr(mp, "as_fact")

    def test_observation_source_has_no_model_kind(self):
        # Model output cannot even be an observation.
        assert not any(m.name == "MODEL" for m in ObservationSourceKind)


# ======================================================================
# 4. Hypothesis cannot be a Fact/Belief; no VERIFIED status
# ======================================================================

class TestHypothesis:
    def test_hypothesis_is_a_distinct_type(self):
        assert not issubclass(Hypothesis, Fact)
        assert not issubclass(Hypothesis, Belief)

    def test_hypothesis_status_has_no_verified(self):
        assert not any(s.name == "VERIFIED" for s in HypothesisStatus)

    def test_hypothesis_from_model_is_still_a_hypothesis(self):
        h = Hypothesis(record_id="h1", tenant=T, recorded_at=NOW, provenance=PROV,
                       claim="latency caused by pool exhaustion", origin="model:gpt",
                       status=HypothesisStatus.OPEN)
        assert isinstance(h, Hypothesis)
        assert not isinstance(h, Fact)


# ======================================================================
# 5. Prediction cannot become Outcome
# ======================================================================

class TestPredictionOutcome:
    def test_distinct_types(self):
        assert not issubclass(Prediction, Outcome)
        assert not issubclass(Outcome, Prediction)

    def test_prediction_has_no_conversion_to_outcome(self):
        p = Prediction(record_id="p1", tenant=T, recorded_at=NOW, provenance=PROV,
                       subject_ref="deploy:x", expected=5, predicted_at=NOW)
        assert not hasattr(p, "to_outcome")
        assert not hasattr(p, "as_outcome")

    def test_outcome_requires_execution_ref(self):
        with pytest.raises(ContractViolation):
            Outcome(record_id="oc1", tenant=T, recorded_at=NOW, provenance=PROV,
                    execution_ref="", observed=4)

    def test_outcome_with_execution_ref_succeeds(self):
        oc = Outcome(record_id="oc1", tenant=T, recorded_at=NOW,
                     provenance=ProvenanceRef(produced_by="exec", execution_ref="ex-1"),
                     execution_ref="ex-1", observed=4)
        assert oc.execution_ref == "ex-1"


# ======================================================================
# 6. Verification cannot be a model self-report
# ======================================================================

class TestVerification:
    def _verifier(self):
        return VerifierIdentity(verifier_id="assurance-1", reasoning_path_id="path-B")

    def test_verification_requires_a_procedure(self):
        with pytest.raises(ContractViolation):
            WorldVerification(record_id="v1", tenant=T, recorded_at=NOW, provenance=PROV,
                              subject_ref="s", procedure_ref="",  # no procedure
                              verifier=self._verifier(), verdict=Verdict.SUPPORTED,
                              evidence_refs=("e1",))

    def test_supported_verdict_requires_evidence(self):
        with pytest.raises(ContractViolation):
            WorldVerification(record_id="v1", tenant=T, recorded_at=NOW, provenance=PROV,
                              subject_ref="s", procedure_ref="check:replicas",
                              verifier=self._verifier(), verdict=Verdict.SUPPORTED,
                              evidence_refs=())  # unevidenced support = self-report

    def test_valid_verification_succeeds(self):
        v = WorldVerification(record_id="v1", tenant=T, recorded_at=NOW, provenance=PROV,
                              subject_ref="s", procedure_ref="check:replicas",
                              verifier=self._verifier(), verdict=Verdict.SUPPORTED,
                              evidence_refs=("e1",))
        assert v.verdict is Verdict.SUPPORTED

    def test_verification_reuses_honest_three_answer_verdict(self):
        # 'we don't know' is distinct from 'it's wrong'
        assert not Verdict.INSUFFICIENT_EVIDENCE.permits_autonomous_action
        assert not Verdict.UNSUPPORTED.permits_autonomous_action


# ======================================================================
# 7. World contracts expose no execution capability (Part R)
# ======================================================================

class TestNoExecutionCapability:
    def test_no_type_has_execution_methods(self):
        banned = ("execute", "invoke", "run", "dispatch", "call_tool",
                  "connect", "authorize", "grant")
        for typ in (Observation, Fact, Belief, Hypothesis, Prediction, Outcome,
                    WorldVerification, ModelProposal, ProvenanceRef):
            for name in banned:
                assert not hasattr(typ, name), f"{typ.__name__}.{name} must not exist"

    def test_world_module_imports_no_execution(self):
        import backend.contracts.world as w
        src = ""
        import pathlib
        for path in pathlib.Path(w.__path__[0]).glob("*.py"):
            src += path.read_text(encoding="utf-8")
        for forbidden in ("backend.connectors", "backend.contexts.execution",
                          "invocation_gateway", "platform.transport",
                          "platform.credentials", "backend.database"):
            assert forbidden not in src, f"world contracts import {forbidden}"


# ======================================================================
# 8. Provenance holds references, never credentials (Part L)
# ======================================================================

class TestProvenanceSecrets:
    @pytest.mark.parametrize("secret", [
        "Bearer sk-abcdef1234567890abcdef",
        "Authorization: Bearer xyz",
        "ghp_ABCDEFGHIJKLMNOP1234567890",
        "token=supersecretvalue123",
    ])
    def test_secretish_provenance_is_refused(self, secret):
        with pytest.raises(SecretInProvenance):
            ProvenanceRef(produced_by="connector:x", source_ref=secret)

    def test_reference_provenance_is_accepted(self):
        p = ProvenanceRef(produced_by="connector:grafana",
                          observation_ref="o1", execution_ref="ex-1",
                          trace_ref="corr-1")
        assert p.grounds_a_claim
        assert p.anchors == ("o1", "ex-1", "corr-1")

    def test_provenance_requires_a_producer(self):
        with pytest.raises(ContractViolation):
            ProvenanceRef(produced_by="")


# ======================================================================
# 9. Temporal fields keep distinct meanings (Part K)
# ======================================================================

class TestTemporal:
    def test_observed_at_and_retrieved_at_are_distinct(self):
        past = NOW - timedelta(minutes=4)
        inst = ObservationInstant(observed_at=past, retrieved_at=NOW)
        assert inst.observed_at != inst.retrieved_at
        assert inst.age_at(NOW) == pytest.approx(240, abs=1)

    def test_retrieved_before_observed_is_refused(self):
        with pytest.raises(ContractViolation):
            ObservationInstant(observed_at=NOW, retrieved_at=NOW - timedelta(minutes=1))

    def test_naive_timestamp_is_refused(self):
        with pytest.raises(ContractViolation):
            ObservationInstant(observed_at=datetime(2026, 1, 1), retrieved_at=NOW)

    def test_valid_interval_covers_valid_time_not_recording_time(self):
        # The Phase 7.0 example: valid_from 09:58, recorded later.
        vfrom = NOW - timedelta(minutes=12)
        interval = ValidityInterval(valid_from=vfrom)
        assert interval.covers(NOW)          # still true now
        assert not interval.covers(vfrom - timedelta(minutes=1))  # not before it began
        assert interval.is_open

    def test_closed_interval_is_half_open(self):
        vfrom = NOW - timedelta(minutes=10)
        vto = NOW - timedelta(minutes=5)
        interval = ValidityInterval(valid_from=vfrom, valid_to=vto)
        assert interval.covers(vfrom)
        assert not interval.covers(vto)      # half-open [from, to)
        assert not interval.covers(NOW)

    def test_valid_to_before_from_is_refused(self):
        with pytest.raises(ContractViolation):
            ValidityInterval(valid_from=NOW, valid_to=NOW - timedelta(minutes=1))


# ======================================================================
# 10. Contradiction states are representable without becoming FALSE (Part P)
# ======================================================================

class TestContradictionStates:
    def test_epistemic_status_has_the_honest_states(self):
        names = {s.name for s in EpistemicStatus}
        assert {"AFFIRMED", "STALE", "CONFLICTED", "UNKNOWN", "RETRACTED"} <= names
        # And crucially, no "FALSE" collapse.
        assert "FALSE" not in names

    def test_a_fact_can_be_conflicted_without_being_false(self):
        f = Fact.from_observations(
            record_id="f1", tenant=T, recorded_at=NOW, observations=(_obs(),),
            subject_ref="deploy:x", predicate="replicas", value=3,
            validity=ValidityInterval(valid_from=NOW),
            status=EpistemicStatus.CONFLICTED, produced_by="d")
        assert f.status is EpistemicStatus.CONFLICTED

    def test_stale_is_distinct_from_retracted(self):
        assert EpistemicStatus.STALE is not EpistemicStatus.RETRACTED


# ======================================================================
# 11. Immutability (Part N)
# ======================================================================

class TestImmutability:
    def test_records_are_frozen(self):
        obs = _obs()
        with pytest.raises(FrozenInstanceError):
            obs.value = 999  # type: ignore[misc]

    def test_provenance_is_frozen(self):
        with pytest.raises(FrozenInstanceError):
            PROV.produced_by = "evil"  # type: ignore[misc]

    def test_confidence_is_frozen(self):
        c = ClaimConfidence.uncalibrated()
        with pytest.raises(FrozenInstanceError):
            c.value = 0.9  # type: ignore[misc]


# ======================================================================
# 12. Schema versions are explicit; confidence semantics
# ======================================================================

class TestSchemaAndConfidence:
    def test_every_world_type_declares_a_contract_name_and_version(self):
        for typ in (Observation, Fact, Belief, Hypothesis, Prediction, Outcome,
                    WorldVerification, ModelProposal, ProvenanceRef,
                    ClaimConfidence, ModelStatedConfidence, ObservationInstant,
                    ValidityInterval, ObservationSource):
            assert isinstance(typ.CONTRACT_NAME, str) and typ.CONTRACT_NAME
            assert isinstance(typ.CONTRACT_VERSION, int)

    def test_uncalibrated_confidence_has_no_value(self):
        c = ClaimConfidence.uncalibrated()
        assert c.state is CalibrationState.UNCALIBRATED
        assert c.value is None

    def test_uncalibrated_with_a_value_is_refused(self):
        with pytest.raises(ContractViolation):
            ClaimConfidence(state=CalibrationState.UNCALIBRATED, value=0.95)

    def test_calibrated_requires_a_value_in_range(self):
        assert ClaimConfidence.calibrated(0.8).value == 0.8
        with pytest.raises(ContractViolation):
            ClaimConfidence(state=CalibrationState.CALIBRATED, value=None)
        with pytest.raises(ContractViolation):
            ClaimConfidence.calibrated(1.5)

    def test_model_stated_confidence_cannot_become_claim_confidence(self):
        m = ModelStatedConfidence(stated_value=0.95, stated_by="gpt")
        # Different type; no conversion; not usable where ClaimConfidence is.
        assert not isinstance(m, ClaimConfidence)
        assert not hasattr(m, "to_claim_confidence")
        assert not hasattr(m, "as_claim_confidence")

    def test_source_authority_is_a_tier_not_a_float(self):
        assert SourceAuthority.AUTHORITATIVE.at_least(SourceAuthority.CORROBORATED)
        assert not SourceAuthority.UNVERIFIED.at_least(SourceAuthority.SINGLE_SOURCE)


# ======================================================================
# Bonus: the salvaged dead contracts now have a live importer
# ======================================================================

class TestSalvage:
    def test_world_plane_imports_evidence_source_status(self):
        # contracts/evidence.py had zero live importers before 7.1.
        obs = _obs(status=SourceStatus.RETURNED_EMPTY, value=None)
        assert obs.status is SourceStatus.RETURNED_EMPTY

    def test_returned_empty_is_not_returned_data(self):
        # empty ≠ unavailable ≠ not-configured, salvaged and enforced
        with pytest.raises(ContractViolation):
            _obs(status=SourceStatus.UNAVAILABLE, value=5)  # absence carries no value
