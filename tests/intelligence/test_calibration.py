"""Phase 8.7 — empirical calibration & reliability.

Reliability is derived from REAL prediction outcomes (matched/within_horizon +
independent verdict), never model-stated confidence. Eligibility is deterministic;
censored cases are preserved (UNKNOWN/STALE/CONFLICTED never become failure);
datasets are reproducible; drift is the non-overlapping-interval policy; too-small
samples return INSUFFICIENT_DATA (no fake precision); versions never merge. In-memory
ports; the real-Postgres calibration over 8.5 outcomes is the phase87 harness.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.tenant import TenantRef
from backend.contracts.world import CalibrationState
from backend.contracts.intelligence import (
    CalibrationEligibility, CalibrationPolicy, CalibrationStatus, DriftStatus,
    OutcomeLabel, PredictionClass, ReliabilityEstimate,
)
from backend.intelligence.application import (
    CalibrationDatasetBuilder, DriftDetector, ReliabilityEstimator, VerdictView,
    wilson_interval,
)
from backend.intelligence.application.calibration import hash_dataset, hash_result

ACME, OTHER = TenantRef(tenant_id="acme"), TenantRef(tenant_id="other")
PC = PredictionClass("dependency", "latency", "unknown", "scripted", "h/1")


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


class _Rec:
    def __init__(self, record, refs, recorded_at, predicate=None):
        self.record, self.refs, self.recorded_at, self.predicate = record, refs, recorded_at, predicate


def _rows(specs, hv="h/1", predicated=_t(1), evaluated=_t(2)):
    """specs: list of (pid_suffix, matched, within_horizon, has_eval). subject distinct."""
    out = []
    for suffix, matched, within, has_eval in specs:
        pid = f"wpred-{hv}-{suffix}"
        subj = f"dependency/svc-{suffix}"
        out.append(("prediction", _Rec(
            {"record_id": pid, "subject_ref": subj, "predicate": "latency",
             "predicted_at": _t(0).isoformat(), "deadline": _t(30).isoformat(), "model_ref": "scripted"},
            {"harness_version": hv}, predicated)))
        if has_eval:
            out.append(("prediction_evaluation", _Rec(
                {"prediction_ref": pid, "matched": matched, "within_horizon": within,
                 "execution_ref": f"exec-{suffix}"},
                {"prediction_ref": pid, "execution_ref": f"exec-{suffix}"}, evaluated)))
    return out


class PredPort:
    def __init__(self, rows):
        self._rows = rows
    def list_by_kind(self, *, tenant_id, kind, known_at=None):
        return tuple(r for k, r in self._rows if k == kind and (known_at is None or r.recorded_at <= known_at))


class VerPort:
    """Returns a verdict per subject (composition maps real WorldVerifications)."""
    def __init__(self, by_subject=None, verified_at=_t(5)):
        self._by = by_subject or {}
        self._at = verified_at
    def list_for_subject(self, *, tenant_id, subject_ref, predicate, known_at=None):
        v = self._by.get(subject_ref)
        if v is None or (known_at is not None and self._at > known_at):
            return ()
        return (VerdictView(verdict=v, verified_at=self._at, verification_ref=f"wv-{subject_ref}"),)


def _dataset(specs, verdicts=None, tenant=ACME, hv="h/1", policy=None, **kw):
    b = CalibrationDatasetBuilder(prediction_port=PredPort(_rows(specs, hv=hv)),
                                  verification_port=VerPort(verdicts or {}))
    return b.build(tenant=tenant, policy=policy or CalibrationPolicy(), now=_t(9), **kw)


# ======================================================================
# Wilson interval
# ======================================================================

class TestWilson:
    def test_interval_widens_for_small_n(self):
        wide = wilson_interval(1, 1)
        narrow = wilson_interval(80, 100)
        assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])

    def test_deterministic(self):
        assert wilson_interval(8, 10) == wilson_interval(8, 10)


# ======================================================================
# Eligibility (Part D) — deterministic, censored preserved
# ======================================================================

class TestEligibility:
    def test_no_evaluation_is_pending_outcome(self):
        ds = _dataset([("a", None, None, False)])
        s = ds.samples[0]
        assert s.eligibility is CalibrationEligibility.PENDING_OUTCOME
        assert s.outcome_label is OutcomeLabel.PENDING

    def test_out_of_horizon_is_insufficient_not_failure(self):
        ds = _dataset([("a", True, False, True)])  # matched but out of horizon
        s = ds.samples[0]
        assert s.eligibility is CalibrationEligibility.INSUFFICIENT_EVIDENCE
        assert s.outcome_label is not OutcomeLabel.UNSUPPORTED  # STALE != FALSE

    def test_verified_is_eligible_assured(self):
        ds = _dataset([("a", True, True, True)], verdicts={"dependency/svc-a": "supported"})
        s = ds.samples[0]
        assert s.eligibility is CalibrationEligibility.ELIGIBLE
        assert s.outcome_label is OutcomeLabel.SUPPORTED
        assert s.assurance_tier.value == "assured_outcome"

    def test_unverified_is_eligible_unassured(self):
        ds = _dataset([("a", True, True, True)])  # no verdict for the subject
        s = ds.samples[0]
        assert s.eligibility is CalibrationEligibility.ELIGIBLE
        assert s.assurance_tier.value in ("supported_outcome", "unassured_outcome")
        assert s.verification_ref is None

    def test_insufficient_verdict_is_censored_not_failure(self):
        ds = _dataset([("a", True, True, True)], verdicts={"dependency/svc-a": "insufficient_evidence"})
        s = ds.samples[0]
        assert s.eligibility is CalibrationEligibility.INSUFFICIENT_EVIDENCE
        assert s.outcome_label is OutcomeLabel.INSUFFICIENT_EVIDENCE  # never UNSUPPORTED


# ======================================================================
# No model confidence anywhere (Part B / T#1)
# ======================================================================

class TestNoModelConfidence:
    def test_sample_carries_no_confidence_field(self):
        ds = _dataset([("a", True, True, True)], verdicts={"dependency/svc-a": "supported"})
        d = ds.samples[0].to_dict()
        assert not any("confidence" in k for k in d)

    def test_estimate_confidence_is_measured_not_stated(self):
        # 10 verified-supported -> a CALIBRATED ClaimConfidence fitted from outcomes
        specs = [(str(i), True, True, True) for i in range(10)]
        verdicts = {f"dependency/svc-{i}": "supported" for i in range(10)}
        est = ReliabilityEstimator().estimate(
            dataset=_dataset(specs, verdicts=verdicts), prediction_class=PC,
            policy=CalibrationPolicy(), now=_t(9))
        assert est.confidence.state is CalibrationState.CALIBRATED
        assert est.confidence.value == est.support_rate  # empirical, not model-stated


# ======================================================================
# Estimation, INSUFFICIENT_DATA, fallback (Part I/J/K)
# ======================================================================

class TestEstimation:
    def _mix(self, supported, unsupported, hv="h/1"):
        specs, verdicts = [], {}
        for i in range(supported):
            specs.append((f"s{i}", True, True, True)); verdicts[f"dependency/svc-s{i}"] = "supported"
        for i in range(unsupported):
            specs.append((f"u{i}", False, True, True)); verdicts[f"dependency/svc-u{i}"] = "unsupported"
        return _dataset(specs, verdicts=verdicts, hv=hv), verdicts

    def test_calibrated_reports_counts_and_interval(self):
        ds, _ = self._mix(7, 3)
        est = ReliabilityEstimator().estimate(dataset=ds, prediction_class=PC,
                                              policy=CalibrationPolicy(), now=_t(9))
        assert est.status is CalibrationStatus.CALIBRATED
        assert est.decided_count == 10 and est.supported_count == 7
        assert est.support_rate == 0.7 and est.interval is not None
        assert est.assurance_coverage == 1.0

    def test_insufficient_data_no_fake_precision(self):
        ds, _ = self._mix(2, 1)  # 3 < min_decided_samples (8)
        est = ReliabilityEstimator().estimate(dataset=ds, prediction_class=PC,
                                              policy=CalibrationPolicy(), now=_t(9), allow_fallback=False)
        assert est.status is CalibrationStatus.INSUFFICIENT_DATA
        assert est.support_rate is None and est.interval is None
        assert est.confidence.state is CalibrationState.UNCALIBRATED

    def test_fallback_broadens_explicitly(self):
        ds, _ = self._mix(6, 4)  # 10 decided under environment "unknown"
        # ask for a MORE specific environment that has no samples -> fallback to "unknown"
        specific = PredictionClass("dependency", "latency", "production", "scripted", "h/1")
        est = ReliabilityEstimator().estimate(dataset=ds, prediction_class=specific,
                                              policy=CalibrationPolicy(), now=_t(9))
        assert est.status is not CalibrationStatus.INSUFFICIENT_DATA
        assert est.fallback_applied and est.fallback_from["environment"] == "production"

    def test_low_assurance_coverage_is_limited(self):
        # decided by evaluation only (no verdicts) -> coverage 0 -> WITH_LIMITATIONS
        specs = [(str(i), i < 7, True, True) for i in range(10)]
        est = ReliabilityEstimator().estimate(dataset=_dataset(specs), prediction_class=PC,
                                              policy=CalibrationPolicy(), now=_t(9))
        assert est.status is CalibrationStatus.CALIBRATED_WITH_LIMITATIONS
        assert est.assurance_coverage == 0.0


# ======================================================================
# Reproducibility (Part U) + temporal safety (Part G)
# ======================================================================

class TestReproducibility:
    def test_same_inputs_same_digest(self):
        specs = [(str(i), True, True, True) for i in range(5)]
        a = _dataset(specs)
        b = _dataset(specs)
        assert hash_dataset(a) == hash_dataset(b)

    def test_changed_input_changes_digest(self):
        a = _dataset([(str(i), True, True, True) for i in range(5)])
        b = _dataset([(str(i), i != 0, True, True) for i in range(5)])  # one flipped
        assert hash_dataset(a) != hash_dataset(b)

    def test_result_digest_stable(self):
        specs = [(str(i), i < 7, True, True) for i in range(10)]
        est1 = ReliabilityEstimator().estimate(dataset=_dataset(specs), prediction_class=PC,
                                               policy=CalibrationPolicy(), now=_t(9))
        est2 = ReliabilityEstimator().estimate(dataset=_dataset(specs), prediction_class=PC,
                                               policy=CalibrationPolicy(), now=_t(9))
        assert hash_result(est1) == hash_result(est2)


class TestTemporalSafety:
    def test_known_at_excludes_future_records(self):
        # predictions predicated at 10:01, evaluated at 10:20 (future vs a 10:05 cut)
        rows = _rows([(str(i), True, True, True) for i in range(10)], predicated=_t(1), evaluated=_t(20))
        b = CalibrationDatasetBuilder(prediction_port=PredPort(rows), verification_port=VerPort())
        ds_final = b.build(tenant=ACME, policy=CalibrationPolicy(), now=_t(30))
        ds_asknown = b.build(tenant=ACME, policy=CalibrationPolicy(), now=_t(30), known_at=_t(5))
        # final view sees the evaluations; as-known-10:05 view sees predictions but not the 10:20 outcomes
        final_decided = sum(1 for s in ds_final.samples if s.is_decided)
        asknown_pending = sum(1 for s in ds_asknown.samples
                              if s.eligibility is CalibrationEligibility.PENDING_OUTCOME)
        assert final_decided == 10 and asknown_pending == 10  # future outcomes did not leak backward


# ======================================================================
# Drift (Part V)
# ======================================================================

class TestDrift:
    def _ev(self, matched_count, hv="h/1"):
        specs = [(str(i), i < matched_count, True, True) for i in range(10)]
        return _dataset(specs, hv=hv)  # unassured -> evaluation drives the outcome

    def test_distribution_change_detected(self):
        before = self._ev(9)   # 90% supported
        after = self._ev(1)    # 10% supported
        d = DriftDetector().compare(before=before, after=after, prediction_class=PC,
                                    policy=CalibrationPolicy(), now=_t(9))
        assert d is DriftStatus.DRIFT_DETECTED

    def test_stable_is_no_drift(self):
        d = DriftDetector().compare(before=self._ev(7), after=self._ev(7), prediction_class=PC,
                                    policy=CalibrationPolicy(), now=_t(9))
        assert d is DriftStatus.NO_DRIFT

    def test_insufficient_is_unknown_drift(self):
        thin = _dataset([(str(i), True, True, True) for i in range(3)])
        d = DriftDetector().compare(before=thin, after=thin, prediction_class=PC,
                                    policy=CalibrationPolicy(), now=_t(9))
        assert d is DriftStatus.UNKNOWN_DRIFT_STATUS


# ======================================================================
# Adversarial (Part T)
# ======================================================================

class TestAdversarial:
    def test_duplicate_predictions_do_not_inflate(self):
        rows = _rows([("a", True, True, True)])
        rows = rows + rows  # duplicate the same prediction row
        b = CalibrationDatasetBuilder(prediction_port=PredPort(rows), verification_port=VerPort())
        ds = b.build(tenant=ACME, policy=CalibrationPolicy(), now=_t(9))
        assert len(ds.samples) == 1  # deduped by prediction_ref (T#4)

    def test_version_not_merged_by_fallback(self):
        # samples from harness h/1 AND h/2; an h/1 estimate never counts h/2 samples,
        # and broadening keeps harness fixed (T#10).
        rows = _rows([(str(i), True, True, True) for i in range(6)], hv="h/1") \
            + _rows([(str(i), True, True, True) for i in range(6)], hv="h/2")
        b = CalibrationDatasetBuilder(prediction_port=PredPort(rows), verification_port=VerPort())
        ds = b.build(tenant=ACME, policy=CalibrationPolicy(min_decided_samples=6), now=_t(9))
        est = ReliabilityEstimator().estimate(dataset=ds, prediction_class=PC,
                                              policy=CalibrationPolicy(min_decided_samples=6), now=_t(9))
        assert est.decided_count == 6  # only h/1, never merged with h/2

    def test_estimate_is_immutable(self):
        est = ReliabilityEstimator().estimate(
            dataset=_dataset([(str(i), True, True, True) for i in range(10)],
                             verdicts={f"dependency/svc-{i}": "supported" for i in range(10)}),
            prediction_class=PC, policy=CalibrationPolicy(), now=_t(9))
        with pytest.raises(Exception):
            est.support_rate = 0.0  # frozen — the model cannot rewrite calibration (T#15)

    def test_insufficient_data_cannot_carry_rate(self):
        from backend.contracts.intelligence import ReliabilityEstimate
        from backend.contracts.errors import ContractViolation
        with pytest.raises(ContractViolation):
            ReliabilityEstimate(
                prediction_class=PC, status=CalibrationStatus.INSUFFICIENT_DATA, sample_count=2,
                decided_count=2, supported_count=2, unsupported_count=0, insufficient_count=0,
                conflicted_count=0, pending_count=0, assured_count=0, dataset_digest="d",
                policy_digest="p", confidence=None, generated_at=_t(9), support_rate=1.0)  # no fake precision


# ======================================================================
# Calibration cannot authorize / write (Part R / Z) — proven by fitness
# ======================================================================

class TestCalibrationFenced:
    def test_calibration_module_cannot_import_a_connector(self, tmp_path):
        import textwrap
        from backend.platform.architecture.boundary_rules import IntelligenceCannotExecuteRule
        from backend.platform.architecture.rules import ModuleGraph
        root = tmp_path / "backend"
        (root / "intelligence" / "application").mkdir(parents=True)
        (root / "intelligence" / "application" / "calibration.py").write_text(
            textwrap.dedent("from backend.connectors.kubernetes import KubernetesConnector\n"),
            encoding="utf-8")
        graph = ModuleGraph.build(root, package_root=root.name)
        # calibration is auto-covered by BND-INTELLIGENCE-CANNOT-EXECUTE (no new rule needed)
        assert not IntelligenceCannotExecuteRule().evaluate(graph).passed

    def test_current_calibration_module_passes_all_intelligence_rules(self):
        from pathlib import Path
        from backend.platform.architecture.boundary_rules import (
            IntelligenceCannotExecuteRule, ModelCannotCreateFactRule, IntelligenceCannotBypassWorldRule)
        from backend.platform.architecture.rules import ModuleGraph
        graph = ModuleGraph.build(Path(__file__).resolve().parents[2] / "backend")
        assert IntelligenceCannotExecuteRule().evaluate(graph).passed
        assert ModelCannotCreateFactRule().evaluate(graph).passed
        assert IntelligenceCannotBypassWorldRule().evaluate(graph).passed
