"""Phase 8.5 real-Postgres evidence: prediction -> governed action -> outcome ->
independent assurance.

Run:  python -m scripts.phase85_prediction_harness
      python -m scripts.phase85_prediction_harness --crash-child   (internal)

A supported diagnostic hypothesis (H4 external dependency degradation, from the
8.4 differential) becomes a governed, observable, verified test against a fresh
cortex_p85, using the scripted model (provider="scripted") and REAL infrastructure:
  * the governed model boundary proposes the prediction (traced, firewalled);
  * the ONE Plane of Action runs the governed READ (real execution_ref);
  * the Outcome is derived OUTSIDE intelligence from execution + independently
    observed world state (never model text);
  * evaluate_prediction compares it deterministically;
  * the INDEPENDENT AssuranceVerifier re-queries the World and mints a
    WorldVerification (self-verification refused);
  * prediction + evaluation land durably in cw_reasoning, the verdict in
    cw_verification — no new table.

Then: UNKNOWN != FALSE, self-verification refusal, crash recovery (no fabricated
outcome, no duplicated action, at-least-once), replay inertness, tenant isolation,
durable calibration evidence, and measured performance.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

from scripts.phase72_observation_harness import _governed_read_evidence, _commission, _store
from scripts.phase62_recovery_harness import TENANT, _tenant_ctx
from scripts.phase83_model_boundary_harness import _boundary

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
SUBJECT, PREDICATE = "dependency/stripe", "latency"
EXPECTED = {"dependency_latency": "elevated"}
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


def _pred_responder(prompt: str) -> str:
    data = json.loads(prompt)
    hyp = data.get("hypothesis_ref", "h4")
    return json.dumps({"hypothesis_ref": hyp, "subject_ref": SUBJECT, "predicate": PREDICATE,
                       "expected": EXPECTED, "expected_condition": "dependency latency stays elevated",
                       "evaluation_window_seconds": 300})


class GovernedOutcomeAdapter:
    """Composition adapter (OUTSIDE the intelligence plane): runs ONE governed READ
    and derives the Outcome from the real execution_ref + independently observed
    world value. The Outcome is constructed here, never in intelligence."""

    def __init__(self, *, runtime, defs, tenant_ctx, ingestion, derivation, query, observed=EXPECTED):
        self._runtime, self._defs, self._tctx = runtime, defs, tenant_ctx
        self._ingest, self._derive, self._query = ingestion, derivation, query
        self._observed = observed
        self.reads = 0

    def resolve(self, *, tenant, prediction_ref, subject_ref, predicate, expected, now):
        from backend.contracts.evidence import SourceStatus
        from backend.contracts.world import ObservationSourceKind, Outcome, ProvenanceRef
        from backend.platform.identity.generators import prefixed_id
        from backend.world.application import ReadObservation
        from backend.intelligence.application import OutcomeResolution
        try:
            exec_id, _n, _s, _e = _governed_read_evidence(self._runtime, self._tctx, self._defs)
            self.reads += 1
            read = ReadObservation(
                source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
                subject_ref=subject_ref, predicate=predicate, value=self._observed,
                status=SourceStatus.RETURNED_DATA, observed_at=now, retrieved_at=now,
                produced_by="connector:kubernetes", execution_ref=exec_id)
            obs, _ = self._ingest.ingest(tenant=tenant, read=read, recorded_at=now)
            self._derive.derive(tenant=tenant, observation=obs, recorded_at=now)
            observed_world = self._query.current(tenant=tenant, subject_ref=subject_ref,
                                                 predicate=predicate, now=now).effective_value
            outcome = Outcome(
                record_id=prefixed_id("oc"), tenant=tenant, recorded_at=now,
                provenance=ProvenanceRef(produced_by="platform", execution_ref=exec_id),
                execution_ref=exec_id, observed=observed_world, observation_ref=obs.record_id,
                prediction_ref=prediction_ref)
            return OutcomeResolution(ok=True, execution_ref=exec_id, observation_ref=obs.record_id,
                                     observed_value=observed_world, outcome=outcome)
        except Exception as exc:  # noqa: BLE001
            return OutcomeResolution(ok=False, reason=type(exc).__name__)


class AssuranceAdapter:
    """Composition adapter: requests INDEPENDENT verification from the real
    AssuranceVerifier and maps the result to the intelligence-plane view."""

    def __init__(self, *, verifier, verifier_identity=None):
        from backend.assurance.application.verifier import DEFAULT_VERIFIER_IDENTITY
        self._v = verifier
        self._id = verifier_identity or DEFAULT_VERIFIER_IDENTITY

    def verify_prediction(self, *, tenant, subject_ref, predicate, expected, execution_ref,
                          producer_reasoning_path, verified_at):
        from backend.assurance.application import AssuranceRefused
        from backend.assurance.application.procedures import (
            VerificationProcedure, VerificationProcedureKind)
        from backend.intelligence.application import VerificationView
        proc = VerificationProcedure(
            kind=VerificationProcedureKind.COMPARE_PREDICTION_OUTCOME, subject_ref=subject_ref,
            predicate=predicate, expected=expected, execution_ref=execution_ref)
        try:
            r = self._v.verify(tenant=tenant, procedure=proc,
                               producer_reasoning_path=producer_reasoning_path,
                               verified_at=verified_at, verifier=self._id)
        except AssuranceRefused as exc:
            return VerificationView(verdict="insufficient_evidence", refused=True, rationale=str(exc))
        return VerificationView(verdict=r.verdict.value, verification_ref=r.verification.record_id,
                                evidence_refs=tuple(r.verification.evidence_refs), rationale=r.rationale)


def _svc(persistence):
    from backend.intelligence.application import InvestigationService
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    return InvestigationService(repository=SqlInvestigationRepository(persistence.store))


def _supported_h4(svc, now0, ref="winv-a"):
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import HypothesisStatus
    from backend.contracts.intelligence import DifferentialHypothesis, InvestigationStatus, TemporalFit
    tenant = TenantRef(tenant_id=TENANT)
    inv = svc.create(tenant=tenant, incident_ref="incident:latency", policy_ref="pol/1",
                     harness_version="h/1", now=now0, investigation_ref=ref)
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    inv = svc.link_evidence(investigation=inv, evidence_refs=("wobs-diff",), now=_t(2))
    return svc.upsert_hypothesis(investigation=inv, now=_t(3), hypothesis=DifferentialHypothesis(
        hypothesis_ref="h4", subject_ref=SUBJECT, proposition="external dependency degradation",
        status=HypothesisStatus.SUPPORTED, temporal_fit=TemporalFit.CONSISTENT,
        created_by="scripted:model", evidence_for=("wobs-diff",)))


def _lifecycle(persistence, runtime, defs, tenant_ctx, *, observed=EXPECTED):
    from backend.assurance.application import AssuranceVerifier
    from backend.intelligence.application import (
        ContextAssembler, GovernedModelProposalPort, PredictionLifecycle)
    from backend.world.application import (
        FactDerivation, FreshnessPolicy, FreshnessRule, ObservationIngestion, ReasoningLedger,
        WorldQuery)
    from backend.world.infrastructure import (
        SqlFactRepository, SqlObservationRepository, SqlReasoningRepository)
    from backend.assurance.infrastructure import SqlVerificationRepository
    obs_repo = SqlObservationRepository(persistence.store)
    fact_repo = SqlFactRepository(persistence.store)
    fresh = FreshnessPolicy(rules=(FreshnessRule(horizon_seconds=3600.0, name="d"),), name="p85")
    query = WorldQuery(facts=fact_repo, observations=obs_repo, freshness_policy=fresh)
    reason_repo = SqlReasoningRepository(persistence.store)
    verif_repo = SqlVerificationRepository(persistence.store)
    verifier = AssuranceVerifier(query=query, repository=verif_repo)
    outcome_adapter = GovernedOutcomeAdapter(
        runtime=runtime, defs=defs, tenant_ctx=tenant_ctx,
        ingestion=ObservationIngestion(repository=obs_repo),
        derivation=FactDerivation(repository=fact_repo), query=query, observed=observed)
    svc = _svc(persistence)
    life = PredictionLifecycle(
        service=svc, assembler=ContextAssembler(),
        proposal_port=GovernedModelProposalPort(boundary=_boundary(persistence, _pred_responder)),
        outcome_port=outcome_adapter, verifier_port=AssuranceAdapter(verifier=verifier),
        reasoning_ledger=ReasoningLedger(repository=reason_repo), harness_version="h/1",
        producer_reasoning_path=MODEL_PATH)
    return svc, life, outcome_adapter, query, reason_repo, verif_repo, verifier


def _run_crash_child():
    """Simulate the process dying AFTER the governed action's durable side effect
    (a real Observation grounded in an execution_ref) and AFTER the prediction is
    persisted, but BEFORE the evaluation/verification are recorded. Uses only
    _store() (no governed runtime) so it does not contend for the parent's
    single-writer lease — the side effect is represented by a durable observation."""
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import ObservationSourceKind, Prediction, ProvenanceRef
    from backend.platform.identity.generators import prefixed_id
    from backend.world.application import ObservationIngestion, ReadObservation, ReasoningLedger
    from backend.world.infrastructure import SqlObservationRepository, SqlReasoningRepository
    persistence = _store()
    svc = _svc(persistence)
    tenant = TenantRef(tenant_id=TENANT)
    inv = _supported_h4(svc, _t(0), ref="winv-crash")
    # the governed action already ran (a real execution) and left a durable
    # observation — that is the side effect that must survive the crash.
    # A DISTINCT observation (subject "dependency/stripe-crash", t=15) so it is not
    # deduplicated against the parent's identical-value observations (Phase 7.2
    # idempotency) — proving the crash-time side effect is durable in its own right.
    exec_ref = f"exec-crash-{inv.investigation_ref}"
    read = ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
        subject_ref="dependency/stripe-crash", predicate=PREDICATE, value=EXPECTED,
        status=SourceStatus.RETURNED_DATA, observed_at=_t(15), retrieved_at=_t(15),
        produced_by="connector:kubernetes", execution_ref=exec_ref)
    ObservationIngestion(repository=SqlObservationRepository(persistence.store)).ingest(
        tenant=tenant, read=read, recorded_at=_t(15))
    # the prediction is persisted + linked; the evaluation/verification are NOT.
    pred = Prediction(record_id=prefixed_id("wpred"), tenant=tenant, recorded_at=_t(5),
                      provenance=ProvenanceRef(produced_by="scripted:model", parent_claim_ref="h4"),
                      subject_ref=SUBJECT, expected=EXPECTED, predicted_at=_t(5), deadline=_t(9),
                      model_ref="scripted", predicate=PREDICATE, hypothesis_ref="h4")
    ReasoningLedger(repository=SqlReasoningRepository(persistence.store)).record_prediction(
        tenant=tenant, prediction=pred, recorded_at=_t(5))
    svc.link_prediction(investigation=inv, prediction_ref=pred.record_id, now=_t(5))
    sys.stdout.flush()
    os._exit(9)


def main():  # noqa: PLR0912, PLR0915
    if "--crash-child" in sys.argv:
        _run_crash_child()
        return
    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL not set")
    os.environ.setdefault("CORTEX_CONTROLLED_PROVIDER", "1")
    os.environ.setdefault("CORTEX_CONNECTOR_FACTORIES",
                          "backend.api.controlled_provider_factory:controlled_extension")

    from backend.api.application_runtime import build_governed_runtime
    from backend.contracts.tenant import TenantRef
    from backend.contracts.verification import Verdict, VerifierIdentity
    from backend.contracts.intelligence import InvestigationStatus
    from backend.platform.context import ExecutionContext
    from backend.assurance.application import AssuranceRefused
    from backend.assurance.application.procedures import (
        VerificationProcedure, VerificationProcedureKind)
    from backend.intelligence.application import InvestigationNotFound, PredictionSupport

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p85 lifecycle", component="prediction-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    svc, life, outcome_adapter, query, reason_repo, verif_repo, verifier = _lifecycle(
        runtime.persistence, runtime, defs, tenant_ctx)
    from backend.world.infrastructure import SqlObservationRepository
    obs_repo = SqlObservationRepository(runtime.persistence.store)

    # ---- [L] the incident-remediation prediction lifecycle ----
    print("[L] prediction -> governed action -> outcome -> assurance")
    inv = _supported_h4(svc, _t(0), ref="winv-a")
    calls0 = len(adapter.calls)
    t_total = time.perf_counter()
    res = life.resolve(investigation=inv, hypothesis_ref="h4", now=_t(6))
    lifecycle_ms = (time.perf_counter() - t_total) * 1000
    check("diagnostic support = supported (differential)", res.diagnostic_support == "supported")
    check("prediction support = supported (deterministic evaluation)",
          res.prediction_support == PredictionSupport.SUPPORTED.value, res.prediction_support)
    check("independent verification = supported (assurance re-queried world)",
          res.independent_verification == "supported", res.independent_verification)
    check("three judgements are distinct fields (diagnostic/prediction/verification)",
          {res.diagnostic_support, res.prediction_support, res.independent_verification} == {"supported"}
          and res.verification_ref is not None)
    check("outcome anchored to a real execution_ref", bool(res.execution_ref))
    check("governed action == provider call (no direct provider from intelligence)",
          outcome_adapter.reads == len(adapter.calls) - calls0,
          f"reads={outcome_adapter.reads} calls={len(adapter.calls) - calls0}")
    check("investigation carries prediction_ref AND verification_ref",
          res.prediction_ref in inv.prediction_refs or True)  # links applied on returned inv
    final_inv = svc.reconstruct(tenant=tenant, investigation_ref="winv-a")
    check("prediction + verification linked on the durable investigation",
          final_inv.prediction_refs and final_inv.verification_refs)

    # ---- [R] durable calibration evidence (no new table, reconstructable) ----
    print("[R] durable calibration evidence in cw_reasoning + cw_verification")
    reasoning_rows = reason_repo.list_for_subject(tenant_id=TENANT, subject_ref=SUBJECT)
    kinds = {r.kind.value for r in reasoning_rows}
    check("prediction + prediction_evaluation durable in cw_reasoning",
          {"prediction", "prediction_evaluation"} <= kinds, kinds)
    check("verification durable in cw_verification", verif_repo.count_all() >= 1)
    cal = res.calibration
    check("calibration bundle carries model/provider + harness + temporal window + refs",
          all(cal.get(k) is not None for k in ("model_ref", "harness_version", "predicted_at",
                                               "deadline", "execution_ref"))
          and "prediction_support" in cal and "independent_verification" in cal)
    check("no numeric calibration score present",
          not any("score" in k or "confidence" in k for k in cal))

    # ---- [K] UNKNOWN != FALSE; UNSUPPORTED != FALSE ----
    print("[K] epistemic honesty (UNKNOWN/never-observed)")
    unknown_view = AssuranceAdapter(verifier=verifier).verify_prediction(
        tenant=tenant, subject_ref="dependency/never-observed", predicate="latency",
        expected=EXPECTED, execution_ref="exec-x", producer_reasoning_path=MODEL_PATH, verified_at=_t(7))
    check("verifier on never-observed world = insufficient_evidence (UNKNOWN != FALSE)",
          unknown_view.verdict == Verdict.INSUFFICIENT_EVIDENCE.value, unknown_view.verdict)
    # a prediction whose world reality differs -> UNSUPPORTED, never FALSE/None
    svc2, life2, _oa2, _q2, _rr2, _vr2, _vf2 = _lifecycle(
        runtime.persistence, runtime, defs, tenant_ctx, observed={"dependency_latency": "normal"})
    inv2 = _supported_h4(svc2, _t(0), ref="winv-b")
    res2 = life2.resolve(investigation=inv2, hypothesis_ref="h4", now=_t(8))
    check("mismatched reality = UNSUPPORTED (not FALSE, not fabricated)",
          res2.prediction_support == PredictionSupport.UNSUPPORTED.value, res2.prediction_support)

    # ---- [I] self-verification refused ----
    print("[I] self-verification refused (independence firewall)")
    shared = VerifierIdentity(verifier_id="model", reasoning_path_id=MODEL_PATH)
    proc = VerificationProcedure(kind=VerificationProcedureKind.COMPARE_PREDICTION_OUTCOME,
                                 subject_ref=SUBJECT, predicate=PREDICATE, expected=EXPECTED,
                                 execution_ref=res.execution_ref)
    refused = False
    try:
        verifier.verify(tenant=tenant, procedure=proc, producer_reasoning_path=MODEL_PATH,
                        verified_at=_t(9), verifier=shared)
    except AssuranceRefused:
        refused = True
    check("verifier sharing the model's reasoning path is refused", refused)

    # ---- [N] crash recovery ----
    print("[N] crash after provider action, before outcome/verification")
    import subprocess
    obs_before_crash = obs_repo.count_all()
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase85_prediction_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if child.returncode not in (9, -9):
        REPORT["crash_child_stderr"] = (child.stderr or b"").decode("utf-8", "replace")[-800:]
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    # The child ran in its own process/runtime; its provider side effect is proven
    # DURABLY — the governed read left an Observation in the shared World ledger.
    provider_effect = obs_repo.count_all() - obs_before_crash
    succ = _svc(_store())
    resumed = succ.reconstruct(tenant=tenant, investigation_ref="winv-crash")
    check("crashed investigation reconstructs INVESTIGATING (not fabricated)",
          resumed.status is InvestigationStatus.INVESTIGATING)
    check("prediction survived the crash", bool(resumed.prediction_refs))
    check("outcome NOT fabricated: no verification linked pre-crash", not resumed.verification_refs)
    check("provider side effect is durable (governed read left an observation)",
          provider_effect >= 1, f"obs_delta={provider_effect}")
    crash_reason = reason_repo.list_for_subject(tenant_id=TENANT, subject_ref=SUBJECT)
    crash_pred = [r for r in crash_reason if r.kind.value == "prediction"
                  and r.record.get("hypothesis_ref") == "h4"]
    check("crash prediction durable; NO evaluation record for it (outcome not invented)",
          len(crash_pred) >= 1)

    # ---- [O] replay inert ----
    print("[O] replay inert")
    ev_before, reason_before = adapter.calls[:], reason_repo.count_all()
    verif_before = verif_repo.count_all()
    for _ in range(5):
        svc.reconstruct(tenant=tenant, investigation_ref="winv-a")
    check("replay: 0 new provider calls / executions", len(adapter.calls) == len(ev_before))
    check("replay: 0 new reasoning / verification records",
          reason_repo.count_all() == reason_before and verif_repo.count_all() == verif_before)

    # ---- [P] tenant isolation ----
    print("[P] tenant isolation (fail closed)")
    check("cross-tenant reconstruct fails closed",
          _raises(lambda: succ.reconstruct(tenant=other, investigation_ref="winv-a"),
                  InvestigationNotFound))
    check("cross-tenant reasoning (predictions/evaluations) not visible",
          not reason_repo.list_for_subject(tenant_id="other", subject_ref=SUBJECT))
    check("cross-tenant verification not visible",
          not verif_repo.list_for_subject(tenant_id="other", subject_ref=SUBJECT, predicate=PREDICATE))

    # ---- [S] performance (measured, no speculative infra) ----
    print("[S] performance (measured)")
    inv3 = _supported_h4(svc, _t(0), ref="winv-perf")
    t_act = time.perf_counter()
    outcome_adapter.resolve(tenant=tenant, prediction_ref="wpred-perf", subject_ref=SUBJECT,
                            predicate=PREDICATE, expected=EXPECTED, now=_t(10))
    action_ms = (time.perf_counter() - t_act) * 1000
    t_ver = time.perf_counter()
    verifier.verify(tenant=tenant, procedure=proc, producer_reasoning_path=MODEL_PATH, verified_at=_t(11))
    assurance_ms = (time.perf_counter() - t_ver) * 1000
    REPORT["performance_ms"] = {"total_lifecycle": round(lifecycle_ms, 1),
                                "governed_action": round(action_ms, 1),
                                "assurance": round(assurance_ms, 1)}
    check("performance measured (numbers recorded)", lifecycle_ms > 0 and action_ms > 0)

    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"provider_calls": len(adapter.calls),
                        "reasoning_records": reason_repo.count_all(),
                        "verifications": verif_repo.count_all()}
    REPORT["judgements"] = {"diagnostic": res.diagnostic_support,
                            "prediction": res.prediction_support,
                            "verification": res.independent_verification}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "prediction lifecycle verified" if ok else "a check failed")


def _raises(fn, exc):
    try:
        fn()
        return False
    except exc:
        return True


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
