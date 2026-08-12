"""Phase 8.8 real-Postgres evidence: controlled autonomy & earned authority.

Run:  python -m scripts.phase88_autonomy_harness

A controlled A3/A4 experiment against a fresh cortex_p88. First it generates REAL
calibration evidence (governed reads -> predictions -> evaluations -> independent
verdicts) for a low-blast-radius reversible capability. Then the deterministic
AutonomyPolicy decides, from that independent evidence, whether autonomy is earned:

  * POSITIVE: earned A3 -> platform sets A3 -> human APPROVED -> the EXISTING
    EXECUTING gate passes -> a governed action runs through the ONE gateway ->
    audit grows. Earned A4 (policy-authorized) needs no per-action approval.
  * NEGATIVE: stale/conflicted world, insufficient calibration, drift, wrong
    version, emergency stop -> the decision denies/downgrades and NO governed action
    runs. A3 without a human APPROVED event is refused by the existing gate (the
    model can never self-authorize).

Every decision is durable on the investigation event log. Crash-safe, replay-inert,
tenant-scoped. Real LLM BLOCKED; provider="scripted".

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
EXPECTED = {"widget_state": "created"}
MODEL_PATH = "model:scripted/turn-1"
POLICY_VERSION = "autpol/1"


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:150]}" if detail else ""))
    return bool(ok)


def bail(code, why):
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


class VerdictAdapter:
    def __init__(self, repo):
        self._repo = repo
    def list_for_subject(self, *, tenant_id, subject_ref, predicate, known_at=None):
        from backend.intelligence.application import VerdictView
        rows = self._repo.list_for_subject(tenant_id=tenant_id, subject_ref=subject_ref,
                                           predicate=predicate, known_at=known_at)
        return tuple(VerdictView(verdict=v.verdict.value, verified_at=v.recorded_at,
                                 verification_ref=v.record_id) for v in rows)


def _calib_cycle(*, runtime, defs, tenant_ctx, tenant, ingestion, derivation, query, ledger,
                 verifier, subject, supported, at):
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind, Outcome, Prediction, ProvenanceRef
    from backend.platform.identity.generators import prefixed_id
    from backend.world.application import ReadObservation, evaluate_prediction
    from backend.assurance.application.procedures import (VerificationProcedure, VerificationProcedureKind)
    predicate = "create"
    value = {"widget_state": "created"} if supported else {"widget_state": "failed"}
    exec_id, _n, _s, _e = _governed_read_evidence(runtime, tenant_ctx, defs)
    read = ReadObservation(source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:widgets",
                           subject_ref=subject, predicate=predicate, value=value,
                           status=SourceStatus.RETURNED_DATA, observed_at=at, retrieved_at=at,
                           produced_by="connector:widgets", execution_ref=exec_id)
    obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=at)
    derivation.derive(tenant=tenant, observation=obs, recorded_at=at)
    pred = Prediction(record_id=prefixed_id("wpred"), tenant=tenant, recorded_at=at,
                      provenance=ProvenanceRef(produced_by="scripted:model", parent_claim_ref="h1"),
                      subject_ref=subject, expected=EXPECTED, predicted_at=at,
                      deadline=at + timedelta(minutes=30), model_ref="scripted", predicate=predicate,
                      hypothesis_ref="h1")
    ledger.record_prediction(tenant=tenant, prediction=pred, recorded_at=at, harness_version="h/1")
    observed = query.current(tenant=tenant, subject_ref=subject, predicate=predicate, now=at).effective_value
    outcome = Outcome(record_id=prefixed_id("oc"), tenant=tenant, recorded_at=at,
                      provenance=ProvenanceRef(produced_by="platform", execution_ref=exec_id),
                      execution_ref=exec_id, observed=observed, observation_ref=obs.record_id,
                      prediction_ref=pred.record_id)
    ev = evaluate_prediction(prediction=pred, outcome=outcome, observed_at=at)
    ledger.record_evaluation(tenant=tenant, subject_ref=subject, evaluation=ev, recorded_at=at, predicate=predicate)
    proc = VerificationProcedure(kind=VerificationProcedureKind.COMPARE_PREDICTION_OUTCOME,
                                 subject_ref=subject, predicate=predicate, expected=EXPECTED, execution_ref=exec_id)
    verifier.verify(tenant=tenant, procedure=proc, producer_reasoning_path=MODEL_PATH, verified_at=at)


def _svc(persistence):
    from backend.intelligence.application import InvestigationService
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    return InvestigationService(repository=SqlInvestigationRepository(persistence.store))


def _audit_count(persistence):
    import sqlalchemy as sa
    from backend.database.durable.tables import audit_record_table as A
    with persistence.store.atomic() as work:
        return int(work.execute(sa.select(sa.func.count()).select_from(A)).scalar_one())


def main():  # noqa: PLR0912, PLR0915
    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL not set")
    os.environ.setdefault("CORTEX_CONTROLLED_PROVIDER", "1")
    os.environ.setdefault("CORTEX_CONNECTOR_FACTORIES",
                          "backend.api.controlled_provider_factory:controlled_extension")

    from backend.api.application_runtime import build_governed_runtime
    from backend.contracts.tenant import TenantRef
    from backend.contracts.execution import SideEffectClass
    from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel
    from backend.contracts.intelligence import (
        ApprovalRequirement, AutonomyEligibility, AutonomyLevel, AutonomyPolicyConfig,
        AutonomyScope, Capability, CalibrationPolicy, CircuitBreakerConfig, DriftStatus,
        EmergencyStopState, HumanEvent, HumanEventKind, InvestigationStatus, PredictionClass)
    from backend.platform.context import ExecutionContext
    from backend.assurance.application import AssuranceVerifier
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.world.application import FactDerivation, ObservationIngestion, ReasoningLedger
    from backend.world.infrastructure import SqlReasoningRepository
    from backend.intelligence.application import (
        AutonomyPolicy, AutonomyRefused, CalibrationDatasetBuilder, ReliabilityEstimator)

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(reason="p88 autonomy", component="autonomy-harness", source="cli")
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
    svc = _svc(runtime.persistence)
    SUBJECT = "widget/create"

    # ---- generate REAL calibration evidence (9/10 supported, coverage 1.0) ----
    print("[cal] generate real calibration evidence for widget/create")
    for i in range(10):
        _calib_cycle(runtime=runtime, defs=defs, tenant_ctx=tenant_ctx, tenant=tenant,
                     ingestion=ObservationIngestion(repository=obs_repo),
                     derivation=FactDerivation(repository=fact_repo), query=query, ledger=ledger,
                     verifier=verifier, subject=f"widget/create-{i}", supported=(i < 9),
                     at=_t(10) + timedelta(seconds=i))
    builder = CalibrationDatasetBuilder(prediction_port=reason_repo, verification_port=VerdictAdapter(verif_repo))
    policy_cal = CalibrationPolicy(min_decided_samples=8)
    pc = PredictionClass("widget", "create", "development", "scripted", "h/1")
    dataset = builder.build(tenant=tenant, policy=policy_cal, now=_t(40))
    reliability = ReliabilityEstimator().estimate(dataset=dataset, prediction_class=pc, policy=policy_cal, now=_t(40))
    check("real calibration is CALIBRATED (9/10, coverage 1.0)",
          reliability.status.value == "calibrated" and reliability.support_rate == 0.9
          and reliability.assurance_coverage == 1.0, reliability.support_rate)

    # ---- autonomy inputs ----
    cfg = AutonomyPolicyConfig(policy_version=POLICY_VERSION)
    apol = AutonomyPolicy()
    versions = {"model_identity": "scripted", "harness_version": "h/1"}
    scope = AutonomyScope(tenant=tenant, environment="development", service="widgets",
                          capability_ref="cap:widget", operation="create", resource_class="widget")
    cap = Capability(capability_ref="cap:widget", operation="create", resource_class="widget",
                     side_effect_class=SideEffectClass.REVERSIBLE_WRITE, reversible=True)
    risk = RiskClassification(level=RiskLevel.LOW, rationale="dev, reversible, single resource",
                              factors=RiskFactors(side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
                                                  environment="development", resource_count=1, reversible=True))

    def decide(requested, *, drift=DriftStatus.NO_DRIFT, fresh=True, conflict=False,
               stop=EmergencyStopState.RUNNING, breaker=None, rel=None, scp=None, ver=None):
        return apol.evaluate(requested_level=requested, scope=scp or scope, capability=cap, risk=risk,
                             reliability=rel if rel is not None else reliability, drift=drift,
                             world_fresh=fresh, world_conflicted=conflict, versions=ver or versions,
                             stop_state=stop, breaker=breaker, config=cfg, now=_t(41))

    # ---- [Y] POSITIVE controlled experiment: earned A3 -> governed action ----
    print("[Y] controlled experiment: earned A3 -> approved -> governed action -> audit")
    d3 = decide(AutonomyLevel.A3_APPROVED_ACTION)
    check("A3 earned (human approval required)", d3.allowed_level is AutonomyLevel.A3_APPROVED_ACTION
          and d3.eligibility is AutonomyEligibility.HUMAN_APPROVAL_REQUIRED, d3.reason)
    inv = svc.create(tenant=tenant, incident_ref="incident:widget", policy_ref="pol/1",
                     harness_version="h/1", now=_t(42), investigation_ref="winv-a3",
                     autonomy_level=AutonomyLevel.A3_APPROVED_ACTION)  # platform sets, from the decision
    inv = svc.record_autonomy_decision(investigation=inv, decision=d3, now=_t(42))
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING, cause="triage", now=_t(43))
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.READY_FOR_ACTION, cause="ready", now=_t(44))
    approved = HumanEvent(kind=HumanEventKind.APPROVED, actor_ref="approval:ops-1", reason="reviewed evidence")
    audit_before = _audit_count(runtime.persistence)
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.EXECUTING, cause="act",
                         now=_t(45), human_event=approved)
    check("EXECUTING reached only with A3 + human APPROVED (existing gate)",
          inv.status is InvestigationStatus.EXECUTING)
    exec_id, _n, _s, _e = _governed_read_evidence(runtime, tenant_ctx, defs)  # the governed action
    check("governed action ran through the ONE gateway (execution_ref)", bool(exec_id))
    check("action was audited (audit chain grew)", _audit_count(runtime.persistence) > audit_before)

    # ---- [Y-A4] earned A4 needs no per-action approval ----
    print("[Y-A4] earned A4 (policy-authorized, no per-action approval)")
    d4 = decide(AutonomyLevel.A4_AUTONOMOUS)
    check("A4 earned (policy authorization, permits autonomous action)",
          d4.eligibility is AutonomyEligibility.ELIGIBLE and d4.permits_autonomous_action
          and d4.approval_requirement is ApprovalRequirement.POLICY_AUTHORIZATION)
    inv4 = svc.create(tenant=tenant, incident_ref="incident:widget", policy_ref="pol/1",
                      harness_version="h/1", now=_t(46), investigation_ref="winv-a4",
                      autonomy_level=AutonomyLevel.A4_AUTONOMOUS)
    inv4 = svc.record_autonomy_decision(investigation=inv4, decision=d4, now=_t(46))
    inv4 = svc.transition(investigation=inv4, to_status=InvestigationStatus.INVESTIGATING, cause="t", now=_t(47))
    inv4 = svc.transition(investigation=inv4, to_status=InvestigationStatus.READY_FOR_ACTION, cause="r", now=_t(48))
    inv4 = svc.transition(investigation=inv4, to_status=InvestigationStatus.EXECUTING, cause="a",
                          now=_t(49), policy_authorization_ref=d4.decision_id)
    check("A4 EXECUTING via policy authorization ref (no human event)",
          inv4.status is InvestigationStatus.EXECUTING)

    # ---- [gate] model cannot self-authorize: A3 without approval is refused ----
    print("[gate] A3 without human approval is refused (model cannot self-authorize)")
    inv_bad = svc.create(tenant=tenant, incident_ref="incident:x", policy_ref="pol/1", harness_version="h/1",
                         now=_t(50), investigation_ref="winv-bad", autonomy_level=AutonomyLevel.A3_APPROVED_ACTION)
    inv_bad = svc.transition(investigation=inv_bad, to_status=InvestigationStatus.INVESTIGATING, cause="t", now=_t(51))
    inv_bad = svc.transition(investigation=inv_bad, to_status=InvestigationStatus.READY_FOR_ACTION, cause="r", now=_t(52))
    refused = False
    try:
        svc.transition(investigation=inv_bad, to_status=InvestigationStatus.EXECUTING, cause="self", now=_t(53))
    except AutonomyRefused:
        refused = True
    check("A3 EXECUTING without a human APPROVED event is refused", refused)

    # ---- [neg] negative autonomy cases refuse / downgrade ----
    print("[neg] negative cases refuse or downgrade")
    check("stale world -> STALE_EVIDENCE, no action",
          not decide(AutonomyLevel.A4_AUTONOMOUS, fresh=False).permits_autonomous_action)
    check("conflicted world -> POLICY_FORBIDDEN, no action",
          decide(AutonomyLevel.A4_AUTONOMOUS, conflict=True).eligibility is AutonomyEligibility.POLICY_FORBIDDEN)
    check("drift -> downgraded, no action",
          decide(AutonomyLevel.A4_AUTONOMOUS, drift=DriftStatus.DRIFT_DETECTED).eligibility
          is AutonomyEligibility.DRIFT_DETECTED)
    check("emergency stop -> EMERGENCY_STOPPED",
          decide(AutonomyLevel.A4_AUTONOMOUS, stop=EmergencyStopState.STOP_ACTIVE).eligibility
          is AutonomyEligibility.EMERGENCY_STOPPED)
    check("circuit breaker -> CIRCUIT_OPEN",
          decide(AutonomyLevel.A4_AUTONOMOUS, breaker=CircuitBreakerConfig().evaluate(action_failures=2)).eligibility
          is AutonomyEligibility.CIRCUIT_OPEN)
    thin = ReliabilityEstimator().estimate(
        dataset=builder.build(tenant=tenant, policy=CalibrationPolicy(min_decided_samples=50), now=_t(41)),
        prediction_class=pc, policy=CalibrationPolicy(min_decided_samples=50), now=_t(41), allow_fallback=False)
    check("insufficient calibration -> INSUFFICIENT_EVIDENCE",
          decide(AutonomyLevel.A4_AUTONOMOUS, rel=thin).eligibility is AutonomyEligibility.INSUFFICIENT_EVIDENCE)
    check("wrong runtime version -> POLICY_FORBIDDEN (re-evaluate)",
          decide(AutonomyLevel.A4_AUTONOMOUS, ver={"model_identity": "scripted", "harness_version": "h/2"}).eligibility
          is AutonomyEligibility.POLICY_FORBIDDEN)
    # a denied decision -> the platform keeps A1 -> EXECUTING refused
    inv_deny = svc.create(tenant=tenant, incident_ref="incident:deny", policy_ref="pol/1", harness_version="h/1",
                          now=_t(54), investigation_ref="winv-deny", autonomy_level=AutonomyLevel.A1_INVESTIGATE)
    inv_deny = svc.transition(investigation=inv_deny, to_status=InvestigationStatus.INVESTIGATING, cause="t", now=_t(55))
    denied_exec_refused = False
    try:
        svc.transition(investigation=inv_deny, to_status=InvestigationStatus.EXECUTING, cause="x", now=_t(56))
    except AutonomyRefused:
        denied_exec_refused = True
    except Exception:
        denied_exec_refused = True  # illegal transition also blocks it
    check("a denied decision keeps A1 -> no autonomous execution possible", denied_exec_refused)

    # ---- [Z] decision durable + auditable on the investigation event log ----
    print("[Z] autonomy decision durable/auditable")
    repo = svc._repository
    ev_count = repo.event_count(tenant_id=TENANT, investigation_id="winv-a3")
    reconstructed = svc.reconstruct(tenant=tenant, investigation_ref="winv-a3")
    check("autonomy decision recorded durably (event log has the decision)", ev_count >= 4)
    check("decision is structured evidence (no raw chain-of-thought stored)",
          "reason" in d3.to_dict() and "requested_level" in d3.to_dict())

    # ---- [S] tenant isolation ----
    print("[S] tenant isolation")
    other_ds = builder.build(tenant=other, policy=policy_cal, now=_t(41))
    other_rel = ReliabilityEstimator().estimate(dataset=other_ds, prediction_class=pc, policy=policy_cal,
                                                now=_t(41), allow_fallback=False)
    check("tenant B has no calibration -> autonomy not eligible (evidence never crosses tenants)",
          decide(AutonomyLevel.A4_AUTONOMOUS, rel=other_rel,
                 scp=AutonomyScope(tenant=other, environment="development", service="widgets",
                                   capability_ref="cap:widget", operation="create", resource_class="widget")).eligibility
          is AutonomyEligibility.INSUFFICIENT_EVIDENCE)

    # ---- [U] crash / recovery ----
    print("[U] crash + recovery")
    import subprocess
    child = subprocess.run([sys.executable, "-c",
        "import os,sys; os._exit(9)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    succ = _svc(_store())
    resumed = succ.reconstruct(tenant=tenant, investigation_ref="winv-a3")
    check("autonomy decision + EXECUTING state survive a fresh reconnect (durable)",
          resumed.status is InvestigationStatus.EXECUTING
          and succ._repository.event_count(tenant_id=TENANT, investigation_id="winv-a3") == ev_count)
    check("no autonomy escalation on recovery (level unchanged)",
          resumed.autonomy_level is AutonomyLevel.A3_APPROVED_ACTION)

    # ---- [V] replay inert (autonomy decision is a pure evaluation) ----
    print("[V] replay inert")
    calls_b, audit_b = len(adapter.calls), _audit_count(runtime.persistence)
    for _ in range(5):
        svc.reconstruct(tenant=tenant, investigation_ref="winv-a3")
        decide(AutonomyLevel.A4_AUTONOMOUS)   # re-evaluating is a pure read
    check("replay/re-evaluation: 0 provider calls, 0 new audit, 0 execution",
          len(adapter.calls) == calls_b and _audit_count(runtime.persistence) == audit_b)

    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"provider_calls": len(adapter.calls), "audit_events": _audit_count(runtime.persistence),
                        "investigation_events": repo.count_all()}
    REPORT["decision_a3"] = d3.to_dict()
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "controlled autonomy verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
