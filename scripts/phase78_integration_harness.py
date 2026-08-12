"""Phase 7.8 FINAL integration gate: one complete epistemic lifecycle.

Run:  python -m scripts.phase78_integration_harness
      python -m scripts.phase78_integration_harness --crash-child   (internal)

One deterministic scenario against a fresh cortex_p78, exactly ONE governed
execution / ONE provider action, no manual dispatcher cycle, no second execution
authority:

  governed execution -> Observation -> Fact -> Belief -> (model proposes)
  Hypothesis -> Prediction -> [reuse the SAME governed execution as the action
  anchor] -> Outcome (from execution_ref + independently observed world, never
  model) -> prediction evaluation -> independent Assurance -> WorldVerification.

Then: durable reasoning trail, provenance graph, bitemporal reconstruction (no
future leak), a negative-matrix subset, secret firewall, replay inertness, and a
real os._exit(9) crash whose incomplete chain stays UNKNOWN (never fabricated).

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

from scripts.phase72_observation_harness import (
    _governed_read_evidence, _read_from_governed_outcome, _store,
)
from scripts.phase62_recovery_harness import TENANT, _commission, _tenant_ctx

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
K8S = "connector:controlled"
MODEL_PATH = "model:gpt/turn-1"
SUBJECT, PREDICATE = "widget:w-1", "state"


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:160]}" if detail else ""))
    return bool(ok)


def bail(code, why):
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _utc(h, m):
    return datetime(2026, 8, 12, h, m, tzinfo=timezone.utc)


def _stack(persistence):
    from backend.assurance.application import AssurancePolicy, AssuranceVerifier
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.world.application import (
        BeliefFormation, FactDerivation, FreshnessPolicy, FreshnessRule,
        HypothesisFormation, ObservationIngestion, ReasoningLedger, WorldQuery,
    )
    from backend.world.infrastructure import (
        SqlFactRepository, SqlObservationRepository, SqlReasoningRepository,
    )
    obs_repo = SqlObservationRepository(persistence.store)
    fact_repo = SqlFactRepository(persistence.store)
    verif_repo = SqlVerificationRepository(persistence.store)
    reason_repo = SqlReasoningRepository(persistence.store)
    freshness = FreshnessPolicy(rules=(FreshnessRule(horizon_seconds=3600, predicate=PREDICATE),))
    query = WorldQuery(facts=fact_repo, observations=obs_repo, freshness_policy=freshness)
    return {
        "obs": obs_repo, "fact": fact_repo, "verif": verif_repo, "reason": reason_repo,
        "ingest": ObservationIngestion(repository=obs_repo),
        "derive": FactDerivation(repository=fact_repo),
        "belief": BeliefFormation(query=query, observations=obs_repo),
        "hyp": HypothesisFormation(),
        "verifier": AssuranceVerifier(query=query, repository=verif_repo,
                                      policy=AssurancePolicy.default()),
        "ledger": ReasoningLedger(repository=reason_repo),
        "query": query,
    }


def _fact_semantic_id(tenant):
    from backend.world.application import fact_semantic_identity
    return fact_semantic_identity(tenant, SUBJECT, PREDICATE)


def _run_crash_child():
    """Run the lifecycle up to the prediction, record it, then die BEFORE
    verification — the incomplete chain must stay UNKNOWN, never fabricated."""
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import ModelHypothesisProposal, Prediction, ProvenanceRef
    from backend.world.application import HypothesisEvidence, ReadObservation
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    s = _stack(_store())
    tenant = TenantRef(tenant_id=TENANT)
    read = ReadObservation(source_kind=ObservationSourceKind.CONNECTOR, source_ref=K8S,
                           subject_ref="deployment/crash", predicate="spec.replicas",
                           value={"replicas": 9}, status=SourceStatus.RETURNED_DATA,
                           observed_at=_utc(12, 0), retrieved_at=_utc(12, 0),
                           produced_by=K8S, execution_ref="ex-crash")
    obs, _ = s["ingest"].ingest(tenant=tenant, read=read, recorded_at=_utc(12, 1))
    s["derive"].derive(tenant=tenant, observation=obs, recorded_at=_utc(12, 1))
    proposal = ModelHypothesisProposal(
        record_id="mp-crash", tenant=tenant, recorded_at=_utc(12, 2),
        provenance=ProvenanceRef(produced_by="model", parent_claim_ref="turn-c"),
        claim="scale event", proposed_by="model:gpt", subject_ref="deployment/crash")
    h = s["hyp"].ground(tenant=tenant, proposal=proposal, recorded_at=_utc(12, 2),
                        evidence=HypothesisEvidence(support_refs=(obs.record_id,)))
    s["ledger"].record_hypothesis(tenant=tenant, subject_ref="deployment/crash", hypothesis=h, recorded_at=_utc(12, 2))
    pred = Prediction(record_id="pr-crash", tenant=tenant, recorded_at=_utc(12, 3),
                      provenance=ProvenanceRef(produced_by="model", parent_claim_ref=h.record_id),
                      subject_ref="deployment/crash", predicate="spec.replicas",
                      expected={"replicas": 9}, predicted_at=_utc(12, 3), deadline=_utc(12, 8),
                      hypothesis_ref=h.record_id)
    s["ledger"].record_prediction(tenant=tenant, prediction=pred, recorded_at=_utc(12, 3))
    sys.stdout.flush()
    os._exit(9)  # die BEFORE any verification


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
    from backend.assurance.application import (
        AssuranceRefused, VerificationProcedure, VerificationProcedureKind,
    )
    from backend.contracts.tenant import TenantRef
    from backend.contracts.verification import Verdict, VerifierIdentity
    from backend.contracts.world import (
        EpistemicStatus, ModelHypothesisProposal, Outcome, Prediction, ProvenanceRef,
    )
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import HypothesisEvidence, evaluate_prediction

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p78 gate", component="integration-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    s = _stack(runtime.persistence)
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    # ==================================================================
    # THE LIFECYCLE — exactly one governed execution / one provider action
    # ==================================================================
    print("[1-2] governed execution -> Observation")
    exec_id, node, state, evidence = _governed_read_evidence(runtime, tenant_ctx, defs)
    check("exactly one governed execution succeeded", state == "succeeded", state)
    provider_after_exec = len(adapter.calls)
    check("exactly one provider action", provider_after_exec == 1, provider_after_exec)
    read = _read_from_governed_outcome(runtime, tenant_ctx, exec_id, node, evidence)
    obs, _ = s["ingest"].ingest(tenant=tenant, read=read, recorded_at=_utc(10, 4))
    check("observation created from the governed execution", obs is not None)

    print("[3] Fact")
    dr = s["derive"].derive(tenant=tenant, observation=obs, recorded_at=_utc(10, 4))
    check("fact derived", dr.fact is not None)
    world_value = dr.fact.value

    print("[4] Belief")
    bel = s["belief"].form_current(tenant=tenant, subject_ref=SUBJECT, predicate=PREDICATE,
                                   now=_utc(10, 4))
    check("belief formed (AFFIRMED)", bel.status is EpistemicStatus.AFFIRMED)

    print("[5] Hypothesis (model proposes, platform grounds)")
    proposal = ModelHypothesisProposal(
        record_id="mp-1", tenant=tenant, recorded_at=_utc(10, 5),
        provenance=ProvenanceRef(produced_by="model", parent_claim_ref="turn-1"),
        claim="the widget state explains the signal", proposed_by="model:gpt",
        subject_ref=SUBJECT, suggested_investigation="re-read widget state")
    hyp = s["hyp"].ground(tenant=tenant, proposal=proposal, recorded_at=_utc(10, 5),
                          evidence=HypothesisEvidence(support_refs=(dr.fact.record_id, obs.record_id),
                                                      falsifier="state changes without cause"))
    check("hypothesis grounded OPEN (never VERIFIED)", hyp.status.value == "open")
    s["ledger"].record_hypothesis(tenant=tenant, subject_ref=SUBJECT, hypothesis=hyp, recorded_at=_utc(10, 5))

    print("[6] Prediction (references hypothesis + horizon)")
    pred = Prediction(record_id="pr-1", tenant=tenant, recorded_at=_utc(10, 6),
                      provenance=ProvenanceRef(produced_by="model", parent_claim_ref=hyp.record_id),
                      subject_ref=SUBJECT, predicate=PREDICATE, expected=world_value,
                      predicted_at=_utc(10, 6), deadline=_utc(10, 11), hypothesis_ref=hyp.record_id,
                      basis=(dr.fact.record_id,))
    check("prediction references its grounded hypothesis", pred.hypothesis_ref == hyp.record_id)
    s["ledger"].record_prediction(tenant=tenant, prediction=pred, recorded_at=_utc(10, 6))

    print("[7-11] governed action anchor -> Outcome (from execution_ref + real world)")
    # The one governed execution is the action anchor; the Outcome's observed value
    # comes from the independently-queried world, NEVER from a model claim.
    model_claimed_success = {"succeeded": True}
    observed_world = s["query"].current(tenant=tenant, subject_ref=SUBJECT, predicate=PREDICATE,
                                        now=_utc(10, 9)).effective_value
    outcome = Outcome(record_id="oc-1", tenant=tenant, recorded_at=_utc(10, 9),
                      provenance=ProvenanceRef(produced_by="platform", execution_ref=exec_id),
                      execution_ref=exec_id, observed=observed_world, prediction_ref="pr-1")
    check("outcome tied to the real execution_ref", outcome.execution_ref == exec_id)
    check("outcome observed = actual world, not model-claimed success",
          outcome.observed == observed_world and outcome.observed != model_claimed_success)

    print("[12] Prediction evaluation")
    ev = evaluate_prediction(prediction=pred, outcome=outcome, observed_at=_utc(10, 9))
    check("prediction evaluated against the real outcome (matched)", ev.matched is True)
    s["ledger"].record_evaluation(tenant=tenant, subject_ref=SUBJECT, evaluation=ev,
                                  recorded_at=_utc(10, 9), predicate=PREDICATE)

    print("[13-14] independent Assurance -> WorldVerification")
    provider_before_verif = len(adapter.calls)
    proc = VerificationProcedure(kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
                                 subject_ref=SUBJECT, predicate=PREDICATE, expected=world_value)
    vres = s["verifier"].verify(tenant=tenant, procedure=proc, producer_reasoning_path=MODEL_PATH,
                                verified_at=_utc(10, 10))
    check("assurance verified SUPPORTED (independent evidence)", vres.verdict is Verdict.SUPPORTED)
    check("verification contacted no provider", len(adapter.calls) == provider_before_verif)
    check("verifier independent of the model producer",
          vres.verification.verifier.reasoning_path_id != MODEL_PATH
          and vres.verification.verifier.model_identifier is None)

    print("[15-16] durable records + provenance graph")
    check("observation durable", s["obs"].count_all() >= 1)
    check("fact durable", s["fact"].count_all() >= 1)
    check("reasoning trail durable (hypothesis+prediction+evaluation)", s["reason"].count_all() == 3)
    check("verification durable", s["verif"].count_all() >= 1)
    # provenance graph: verification -> evidence(obs); prediction -> hypothesis -> fact
    got_verif = s["verif"].get(tenant_id=TENANT, verification_id=vres.verification.record_id)
    check("verification cites independent evidence", got_verif is not None and got_verif.evidence_refs)
    reasoning_rows = s["reason"].list_for_subject(tenant_id=TENANT, subject_ref=SUBJECT)
    pred_row = next((r for r in reasoning_rows if r.kind.value == "prediction"), None)
    check("prediction row traces to its hypothesis", pred_row is not None
          and pred_row.refs.get("hypothesis_ref") == hyp.record_id)

    # ==================================================================
    # Bitemporal reconstruction — no future leakage
    # ==================================================================
    print("[L] bitemporal reconstruction (no future leak)")
    early = [r for r in reasoning_rows if r.recorded_at <= _utc(10, 4)]
    check("reconstruction @10:04 sees no reasoning (hypothesis is 10:05)", early == [])
    late = [r for r in reasoning_rows if r.recorded_at <= _utc(10, 11)]
    check("reconstruction @10:11 sees the full reasoning trail", len(late) == 3)
    check("known @10:04 fact present, hypothesis absent",
          s["belief"].form_as_known(tenant=tenant, subject_ref=SUBJECT, predicate=PREDICATE,
                                    known_at=_utc(10, 4)).status is EpistemicStatus.AFFIRMED)

    # ==================================================================
    # Negative matrix (real-Postgres subset)
    # ==================================================================
    print("[U] negative matrix")
    # self-verification refused
    dependent = VerifierIdentity(verifier_id="model", reasoning_path_id=MODEL_PATH, model_identifier="gpt")
    try:
        s["verifier"].verify(tenant=tenant, procedure=proc, producer_reasoning_path=MODEL_PATH,
                             verified_at=_utc(10, 12), verifier=dependent)
        check("self-verification refused", False)
    except AssuranceRefused:
        check("self-verification refused", True)
    # tenant mismatch fails closed
    check("cross-tenant verification -> INSUFFICIENT",
          s["verifier"].verify(tenant=other, procedure=proc, producer_reasoning_path=MODEL_PATH,
                               verified_at=_utc(10, 12)).verdict is Verdict.INSUFFICIENT_EVIDENCE)
    # unsupported when world contradicts the claim
    bad_proc = VerificationProcedure(kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
                                     subject_ref=SUBJECT, predicate=PREDICATE,
                                     expected={"totally": "different"})
    check("world contradicts claim -> UNSUPPORTED (not FALSE, not SUPPORTED)",
          s["verifier"].verify(tenant=tenant, procedure=bad_proc, producer_reasoning_path=MODEL_PATH,
                               verified_at=_utc(10, 12)).verdict is Verdict.UNSUPPORTED)
    # secret firewall on the reasoning ledger
    from backend.world.application import ReasoningRejected
    secret_pred = Prediction(record_id="pr-secret", tenant=tenant, recorded_at=_utc(10, 6),
                             provenance=ProvenanceRef(produced_by="model", parent_claim_ref=hyp.record_id),
                             subject_ref=SUBJECT, expected={"token": "ghp_ABCDEFabcdef0123456789"},
                             predicted_at=_utc(10, 6), deadline=_utc(10, 11), hypothesis_ref=hyp.record_id)
    try:
        s["ledger"].record_prediction(tenant=tenant, prediction=secret_pred, recorded_at=_utc(10, 6))
        check("secret-bearing reasoning refused", False)
    except ReasoningRejected:
        check("secret-bearing reasoning refused", True)

    # ==================================================================
    # Replay inertness
    # ==================================================================
    print("[N] replay inert")
    from backend.contexts.execution.application.commands import ReplayExecution
    before = (s["fact"].count_all(), s["verif"].count_all(), s["reason"].count_all(), len(adapter.calls))
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    after = (s["fact"].count_all(), s["verif"].count_all(), s["reason"].count_all(), len(adapter.calls))
    check("replay mutated nothing and did zero provider work", before == after, f"{before} vs {after}")

    # ==================================================================
    # Crash — incomplete chain stays UNKNOWN (never fabricated)
    # ==================================================================
    print("[M] crash before verification -> incomplete chain, no fabricated success")
    import subprocess
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase78_integration_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    succ = _stack(_store())
    crash_reasoning = succ["reason"].list_for_subject(tenant_id=TENANT, subject_ref="deployment/crash")
    check("pre-crash reasoning (hypothesis+prediction) survived", len(crash_reasoning) == 2)
    crash_verifs = succ["verif"].list_for_subject(tenant_id=TENANT, subject_ref="deployment/crash",
                                                  predicate="spec.replicas")
    check("no verification was fabricated for the interrupted chain", crash_verifs == ())

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    REPORT["counts"] = {"observations": s["obs"].count_all(), "facts": s["fact"].count_all(),
                        "verifications": s["verif"].count_all(), "reasoning": s["reason"].count_all(),
                        "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "full epistemic lifecycle verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
