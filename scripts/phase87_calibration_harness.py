"""Phase 8.7 real-Postgres evidence: empirical calibration & reliability.

Run:  python -m scripts.phase87_calibration_harness

Generates REAL prediction outcomes against a fresh cortex_p87 — each cycle runs a
governed read (real execution_ref), ingests an Observation, derives a Fact,
records a Prediction + a deterministic PredictionEvaluation (cw_reasoning), and an
INDEPENDENT Assurance verdict (cw_verification). Then it CALIBRATES from those real
records: empirical class reliability with a Wilson interval, reproducible dataset
digest, temporal-leakage defence, drift detection, tenant isolation, and inert
replay. No model-stated confidence is ever used. Real LLM BLOCKED; provider="scripted".

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

from scripts.phase72_observation_harness import _governed_read_evidence, _commission, _store
from scripts.phase62_recovery_harness import TENANT, _tenant_ctx
from scripts.phase84_differential_harness import _world

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
EXPECTED = {"latency_class": "elevated"}
MODEL_PATH = "model:scripted/turn-1"


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:160]}" if detail else ""))
    return bool(ok)


def bail(code, why):
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


class VerifAdapter:
    """Maps the real SqlVerificationRepository to the calibrator's VerdictView
    (so the intelligence plane never imports WorldVerification)."""
    def __init__(self, repo):
        self._repo = repo
    def list_for_subject(self, *, tenant_id, subject_ref, predicate, known_at=None):
        from backend.intelligence.application import VerdictView
        rows = self._repo.list_for_subject(tenant_id=tenant_id, subject_ref=subject_ref,
                                           predicate=predicate, known_at=known_at)
        return tuple(VerdictView(verdict=v.verdict.value, verified_at=v.recorded_at,
                                      verification_ref=v.record_id) for v in rows)


def _cycle(*, runtime, defs, tenant_ctx, tenant, ingestion, derivation, query, ledger, verifier,
           subject, supported, at):
    """One real prediction lifecycle -> durable prediction + evaluation + verification."""
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import (
        ObservationSourceKind, Outcome, Prediction, ProvenanceRef)
    from backend.platform.identity.generators import prefixed_id
    from backend.world.application import ReadObservation, evaluate_prediction
    from backend.assurance.application.procedures import (
        VerificationProcedure, VerificationProcedureKind)
    predicate = "latency"
    value = {"latency_class": "elevated"} if supported else {"latency_class": "normal"}
    exec_id, _n, _s, _e = _governed_read_evidence(runtime, tenant_ctx, defs)
    read = ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
        subject_ref=subject, predicate=predicate, value=value, status=SourceStatus.RETURNED_DATA,
        observed_at=at, retrieved_at=at, produced_by="connector:kubernetes", execution_ref=exec_id)
    obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=at)
    derivation.derive(tenant=tenant, observation=obs, recorded_at=at)
    pred = Prediction(record_id=prefixed_id("wpred"), tenant=tenant, recorded_at=at,
                      provenance=ProvenanceRef(produced_by="scripted:model", parent_claim_ref="h4"),
                      subject_ref=subject, expected=EXPECTED, predicted_at=at,
                      deadline=at + timedelta(minutes=30), model_ref="scripted",
                      predicate=predicate, hypothesis_ref="h4")
    ledger.record_prediction(tenant=tenant, prediction=pred, recorded_at=at, harness_version="h/1")
    observed = query.current(tenant=tenant, subject_ref=subject, predicate=predicate, now=at).effective_value
    outcome = Outcome(record_id=prefixed_id("oc"), tenant=tenant, recorded_at=at,
                      provenance=ProvenanceRef(produced_by="platform", execution_ref=exec_id),
                      execution_ref=exec_id, observed=observed, observation_ref=obs.record_id,
                      prediction_ref=pred.record_id)
    ev = evaluate_prediction(prediction=pred, outcome=outcome, observed_at=at)
    ledger.record_evaluation(tenant=tenant, subject_ref=subject, evaluation=ev, recorded_at=at,
                             predicate=predicate)
    proc = VerificationProcedure(kind=VerificationProcedureKind.COMPARE_PREDICTION_OUTCOME,
                                 subject_ref=subject, predicate=predicate, expected=EXPECTED,
                                 execution_ref=exec_id)
    verifier.verify(tenant=tenant, procedure=proc, producer_reasoning_path=MODEL_PATH, verified_at=at)
    return pred.record_id


def main():  # noqa: PLR0912, PLR0915
    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL not set")
    os.environ.setdefault("CORTEX_CONTROLLED_PROVIDER", "1")
    os.environ.setdefault("CORTEX_CONNECTOR_FACTORIES",
                          "backend.api.controlled_provider_factory:controlled_extension")

    from backend.api.application_runtime import build_governed_runtime
    from backend.contracts.tenant import TenantRef
    from backend.contracts.intelligence import (
        CalibrationPolicy, CalibrationStatus, DriftStatus, PredictionClass)
    from backend.platform.context import ExecutionContext
    from backend.assurance.application import AssuranceVerifier
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.world.application import FactDerivation, ObservationIngestion, ReasoningLedger
    from backend.world.infrastructure import SqlReasoningRepository
    from backend.intelligence.application import (
        CalibrationDatasetBuilder, DriftDetector, ReliabilityEstimator)
    from backend.intelligence.application.calibration import hash_dataset, hash_result

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p87 calibration", component="calibration-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    obs_repo, fact_repo, query = _world(runtime.persistence)
    reason_repo = SqlReasoningRepository(runtime.persistence.store)
    verif_repo = SqlVerificationRepository(runtime.persistence.store)
    ledger = ReasoningLedger(repository=reason_repo)
    verifier = AssuranceVerifier(query=query, repository=verif_repo)
    ingestion = ObservationIngestion(repository=obs_repo)
    derivation = FactDerivation(repository=fact_repo)

    def cyc(subject, supported, at):
        return _cycle(runtime=runtime, defs=defs, tenant_ctx=tenant_ctx, tenant=tenant,
                      ingestion=ingestion, derivation=derivation, query=query, ledger=ledger,
                      verifier=verifier, subject=subject, supported=supported, at=at)

    # ---- generate REAL outcomes: batch A (window 10:10..) 9 supported / 1 unsupported ----
    print("[gen] real prediction outcomes (batch A: 9 supported, 1 unsupported)")
    for i in range(10):
        cyc(f"dependency/a{i}", supported=(i < 9), at=_t(10) + timedelta(seconds=i))
    check("real predictions + evaluations durable in cw_reasoning",
          len(reason_repo.list_by_kind(tenant_id=TENANT, kind="prediction")) == 10
          and len(reason_repo.list_by_kind(tenant_id=TENANT, kind="prediction_evaluation")) == 10)
    check("real independent verifications durable in cw_verification", verif_repo.count_all() >= 10)

    builder = CalibrationDatasetBuilder(prediction_port=reason_repo,
                                        verification_port=VerifAdapter(verif_repo))
    estimator = ReliabilityEstimator()
    policy = CalibrationPolicy(min_decided_samples=8)
    pc = PredictionClass("dependency", "latency", "unknown", "scripted", "h/1")

    # ---- calibrate from real outcomes ----
    print("[C] empirical calibration from real outcomes")
    t0 = time.perf_counter()
    ds = builder.build(tenant=tenant, policy=policy, now=_t(50))
    build_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    est = estimator.estimate(dataset=ds, prediction_class=pc, policy=policy, now=_t(50))
    est_ms = (time.perf_counter() - t1) * 1000
    check("status CALIBRATED (enough decided + assurance coverage)",
          est.status is CalibrationStatus.CALIBRATED, est.status.value)
    check("empirical rate = 9/10 supported (from reality, not model confidence)",
          est.decided_count == 10 and est.supported_count == 9 and est.support_rate == 0.9, est.support_rate)
    check("reports a Wilson interval (uncertainty about the estimate)",
          est.interval is not None and est.interval.lower < 0.9 < est.interval.upper, est.interval.to_dict())
    check("assurance coverage 1.0 (every decided outcome independently verified)",
          est.assurance_coverage == 1.0)
    check("ClaimConfidence CALIBRATED with the empirical value (fulfils 7.1 contract)",
          est.confidence.state.value == "calibrated" and est.confidence.value == 0.9)

    # ---- [U] reproducibility ----
    print("[U] reproducibility")
    ds2 = builder.build(tenant=tenant, policy=policy, now=_t(51))
    est2 = estimator.estimate(dataset=ds2, prediction_class=pc, policy=policy, now=_t(50))
    check("same ledgers + policy => same dataset digest", hash_dataset(ds) == hash_dataset(ds2))
    check("same dataset + algorithm => same result digest", hash_result(est) == hash_result(est2))

    # ---- [G] temporal leakage defence ----
    print("[G] temporal safety (as-known cut)")
    asknown = builder.build(tenant=tenant, policy=policy, now=_t(50), known_at=_t(5))
    check("as-known-10:05 sees no outcomes (future evaluations did not leak backward)",
          all(s.outcome_label.value == "pending" for s in asknown.samples) or not asknown.samples)

    # ---- [V] drift ----
    print("[V] drift detection (batch B: 1 supported, 9 unsupported)")
    for i in range(10):
        cyc(f"dependency/b{i}", supported=(i < 1), at=_t(30) + timedelta(seconds=i))
    ds_before = builder.build(tenant=tenant, policy=policy, now=_t(50), time_from=_t(9), time_to=_t(20))
    ds_after = builder.build(tenant=tenant, policy=policy, now=_t(50), time_from=_t(29), time_to=_t(40))
    drift = DriftDetector().compare(before=ds_before, after=ds_after, prediction_class=pc,
                                    policy=policy, now=_t(50))
    check("distribution change detected between windows (non-overlapping intervals)",
          drift is DriftStatus.DRIFT_DETECTED, drift.value)
    thin_policy = CalibrationPolicy(min_decided_samples=50)
    unknown = DriftDetector().compare(before=ds_before, after=ds_after, prediction_class=pc,
                                      policy=thin_policy, now=_t(50))
    check("insufficient data => UNKNOWN_DRIFT_STATUS (no fabricated verdict)",
          unknown is DriftStatus.UNKNOWN_DRIFT_STATUS, unknown.value)

    # ---- [I/J] insufficient data => INSUFFICIENT_DATA (no fake precision) ----
    print("[J] insufficient data")
    sparse = PredictionClass("network", "health", "unknown", "scripted", "h/1")  # no samples
    est_sparse = estimator.estimate(dataset=ds, prediction_class=sparse, policy=policy, now=_t(50),
                                    allow_fallback=False)
    check("unknown class => INSUFFICIENT_DATA, no rate, uncalibrated",
          est_sparse.status is CalibrationStatus.INSUFFICIENT_DATA and est_sparse.support_rate is None
          and est_sparse.confidence.state.value == "uncalibrated")

    # ---- [L] version isolation ----
    print("[L] version isolation")
    other_ver = PredictionClass("dependency", "latency", "unknown", "scripted", "h/2")
    est_v = estimator.estimate(dataset=ds, prediction_class=other_ver, policy=policy, now=_t(50),
                               allow_fallback=False)
    check("a different harness version sees none of h/1's samples (never merged)",
          est_v.sample_count == 0)

    # ---- [X] replay inert (calibration is pure read) ----
    print("[X] replay inert (calibration performs no writes)")
    ref = estimator.estimate(dataset=builder.build(tenant=tenant, policy=policy, now=_t(52)),
                             prediction_class=pc, policy=policy, now=_t(52))
    reason_b, verif_b, fact_b, calls_b = (reason_repo.count_all(), verif_repo.count_all(),
                                          fact_repo.count_all(), len(adapter.calls))
    replays = [hash_result(estimator.estimate(
        dataset=builder.build(tenant=tenant, policy=policy, now=_t(52)),
        prediction_class=pc, policy=policy, now=_t(52))) for _ in range(5)]
    check("calibration created 0 reasoning/verification/world records, 0 provider calls",
          reason_repo.count_all() == reason_b and verif_repo.count_all() == verif_b
          and fact_repo.count_all() == fact_b and len(adapter.calls) == calls_b)
    check("replay reproduces the same result (no partial artifact becomes authoritative)",
          all(r == hash_result(ref) for r in replays))

    # ---- [P-tenant] tenant isolation ----
    print("[tenant] isolation (fail closed)")
    ds_other = builder.build(tenant=other, policy=policy, now=_t(50))
    check("cross-tenant calibration sees no samples", ds_other.samples == ())

    # ---- [W] performance ----
    print("[W] performance (measured)")
    REPORT["performance_ms"] = {"dataset_construction": round(build_ms, 1),
                                "estimation": round(est_ms, 2)}
    check("performance measured", build_ms >= 0 and est_ms >= 0)

    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"predictions": len(reason_repo.list_by_kind(tenant_id=TENANT, kind="prediction")),
                        "verifications": verif_repo.count_all(), "provider_calls": len(adapter.calls)}
    REPORT["calibration"] = est.to_dict()
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "empirical calibration verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
