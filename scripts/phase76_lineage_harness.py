"""Phase 7.6 real-Postgres evidence: source lineage, governed belief policy,
hypothesis grounding, prediction evaluation.

Run:  python -m scripts.phase76_lineage_harness
      python -m scripts.phase76_lineage_harness --crash-child   (internal)

Proves against a fresh cortex_p76: the governed READ -> Observation -> Fact ->
Belief path with lineage-aware corroboration (same lineage = correlated;
unknown lineage = indeterminate; distinct known origins = independent),
authority still separate and beating recency, the governed support policy
(no numbers), model-proposes/platform-grounds hypotheses, prediction vs real
outcome, temporal + tenant correctness, replay inertness, and deterministic
belief reconstruction after a real crash. Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
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
K8S, PROM, DATADOG = "connector:kubernetes", "connector:prometheus", "connector:datadog"
CP = "k8s-control-plane"


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


def _read(subject, value, observed_at, source_ref, *, predicate="spec.replicas"):
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.world.application import ReadObservation
    return ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref=source_ref,
        subject_ref=subject, predicate=predicate, value=value,
        status=SourceStatus.RETURNED_DATA, observed_at=observed_at,
        retrieved_at=observed_at + timedelta(minutes=4), produced_by=source_ref,
        execution_ref="ex-scn", trace_ref="corr")


def _lineage():
    from backend.world.application import LineagePolicy, LineageRelation, LineageRule
    return LineagePolicy(rules=(
        LineageRule(origin_id=CP, relation=LineageRelation.DIRECT, source_ref=K8S),
        LineageRule(origin_id=CP, relation=LineageRelation.DERIVED, source_ref=PROM),
        LineageRule(origin_id="datadog-agent", relation=LineageRelation.DIRECT, source_ref=DATADOG),
        LineageRule(origin_id="controlled", relation=LineageRelation.DIRECT,
                    source_ref="connector:controlled"),
    ), name="p76-lineage")


def _authority():
    from backend.contracts.world import SourceAuthority
    from backend.world.application import AuthorityPolicy, AuthorityRule
    return AuthorityPolicy(rules=(
        AuthorityRule(tier=SourceAuthority.AUTHORITATIVE, source_ref=K8S),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref=PROM),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref="connector:controlled"),
    ), name="p76-authority")


def _support():
    from backend.world.application import (
        BeliefSupportPolicy, BeliefSupportRule, SupportRequirement,
    )
    return BeliefSupportPolicy(rules=(BeliefSupportRule(
        requirement=SupportRequirement.INDEPENDENT_REQUIRED),), name="p76-support")


def _stack(persistence):
    from backend.world.application import (
        BeliefFormation, FactDerivation, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository
    obs_repo = SqlObservationRepository(persistence.store)
    fact_repo = SqlFactRepository(persistence.store)
    query = WorldQuery(facts=fact_repo, observations=obs_repo, authority_policy=_authority())
    beliefs = BeliefFormation(query=query, observations=obs_repo, authority_policy=_authority(),
                              lineage_policy=_lineage(), support_policy=_support())
    return obs_repo, fact_repo, ObservationIngestion(repository=obs_repo), \
        FactDerivation(repository=fact_repo), query, beliefs


def _run_crash_child():
    from backend.contracts.tenant import TenantRef
    _, _, ingestion, derivation, _, _ = _stack(_store())
    tenant = TenantRef(tenant_id=TENANT)
    obs, _ = ingestion.ingest(tenant=tenant, recorded_at=_utc(12, 1),
                              read=_read("deployment/crash", {"replicas": 9}, _utc(12, 0), K8S))
    derivation.derive(tenant=tenant, observation=obs, recorded_at=_utc(12, 1))
    sys.stdout.flush()
    os._exit(9)


def main():  # noqa: PLR0915
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
    from backend.contracts.world import (
        EpistemicStatus, HypothesisStatus, ModelHypothesisProposal, Outcome,
        Prediction, ProvenanceRef,
    )
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import (
        BeliefAcceptance, CorroborationLevel, HypothesisEvidence, HypothesisFormation,
        evaluate_prediction,
    )

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p76 harness", component="world-lineage-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    obs_repo, fact_repo, ingestion, derivation, query, beliefs = _stack(runtime.persistence)
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    def idr(read, *, at):
        obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=at)
        derivation.derive(tenant=tenant, observation=obs, recorded_at=at)
        return obs

    def believe(subject, now, predicate="spec.replicas", who=tenant):
        return beliefs.form_current(tenant=who, subject_ref=subject, predicate=predicate, now=now)

    # ---- Q: governed READ -> Observation -> Fact -> Belief ----
    print("[Q] governed READ -> Observation -> Fact -> Belief")
    exec_id, node, state, evidence = _governed_read_evidence(runtime, tenant_ctx, defs)
    check("governed READ succeeded", state == "succeeded", state)
    read = _read_from_governed_outcome(runtime, tenant_ctx, exec_id, node, evidence)
    obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=datetime.now(timezone.utc))
    derivation.derive(tenant=tenant, observation=obs, recorded_at=datetime.now(timezone.utc))
    provider_before = len(adapter.calls)
    b = believe("widget:w-1", datetime.now(timezone.utc), predicate="state")
    check("belief formed", b.status is EpistemicStatus.AFFIRMED)
    check("belief formation contacted no provider", len(adapter.calls) == provider_before)

    # ---- T1/T2: same lineage origin -> CORRELATED ----
    print("[T1/T2] same lineage origin -> CORRELATED (not independent)")
    idr(_read("deployment/corr", {"replicas": 5}, _utc(10, 0), K8S), at=_utc(10, 1))
    idr(_read("deployment/corr", {"replicas": 5}, _utc(10, 0), PROM), at=_utc(10, 1))  # derived
    bc = believe("deployment/corr", _utc(10, 5))
    check("K8s + Prometheus (derived) -> CORRELATED",
          bc.corroboration.level is CorroborationLevel.CORRELATED)
    check("one shared lineage origin", bc.corroboration.independent_origins == (CP,))

    # ---- T3: unknown lineage -> INDETERMINATE ----
    print("[T3] unknown lineage -> INDETERMINATE")
    idr(_read("deployment/unk", {"replicas": 4}, _utc(10, 0), "connector:mystery-a"), at=_utc(10, 1))
    idr(_read("deployment/unk", {"replicas": 4}, _utc(10, 0), "connector:mystery-b"), at=_utc(10, 1))
    check("two unknown-lineage sources -> INDETERMINATE",
          believe("deployment/unk", _utc(10, 5)).corroboration.level
          is CorroborationLevel.INDETERMINATE)

    # ---- T4: distinct known origins -> INDEPENDENT ----
    print("[T4] distinct known origins -> INDEPENDENT")
    idr(_read("deployment/ind", {"replicas": 6}, _utc(10, 0), K8S), at=_utc(10, 1))
    idr(_read("deployment/ind", {"replicas": 6}, _utc(10, 0), DATADOG), at=_utc(10, 1))
    bi = believe("deployment/ind", _utc(10, 5))
    check("K8s + Datadog (distinct origins) -> INDEPENDENT",
          bi.corroboration.level is CorroborationLevel.INDEPENDENT)
    check("acceptance ACCEPTED (independent requirement met)",
          bi.acceptance.acceptance is BeliefAcceptance.ACCEPTED)

    # ---- support policy: single authoritative -> PROVISIONAL under INDEPENDENT_REQUIRED ----
    print("[policy] independent-required -> single source is PROVISIONAL")
    idr(_read("deployment/one", {"replicas": 2}, _utc(10, 0), K8S), at=_utc(10, 1))
    bp = believe("deployment/one", _utc(10, 5))
    check("single authoritative source -> PROVISIONAL",
          bp.acceptance.acceptance is BeliefAcceptance.PROVISIONAL)

    # ---- authority beats recency, lineage separate ----
    print("[auth] authority separate from lineage and recency")
    idr(_read("deployment/auth", {"replicas": 5}, _utc(10, 0), K8S), at=_utc(10, 1))
    idr(_read("deployment/auth", {"replicas": 3}, _utc(10, 5), PROM), at=_utc(10, 6))  # newer, derived
    ba = believe("deployment/auth", _utc(10, 10))
    check("authority = K8s value despite newer Prometheus", ba.value == {"replicas": 5})
    check("Prometheus preserved as contradicting evidence",
          any(e.source_ref == PROM for e in ba.corroboration.contradicting))

    # ---- hypothesis: model proposes, platform grounds in real facts ----
    print("[hyp] model proposes -> platform grounds in real evidence")
    sid_facts = fact_repo.versions_for(
        tenant_id=TENANT,
        semantic_identity=__import__("backend.world.application", fromlist=["fact_semantic_identity"])
        .fact_semantic_identity(tenant, "deployment/ind", "spec.replicas"))
    proposal = ModelHypothesisProposal(
        record_id="mp-1", tenant=tenant, recorded_at=_utc(10, 6),
        provenance=ProvenanceRef(produced_by="model:gpt", parent_claim_ref="turn-1"),
        claim="replica scale-up explains the load", proposed_by="model:gpt",
        subject_ref="deployment/ind", suggested_investigation="inspect HPA events")
    h = HypothesisFormation().ground(
        tenant=tenant, proposal=proposal, recorded_at=_utc(10, 7),
        evidence=HypothesisEvidence(support_refs=tuple(v.fact_id for v in sid_facts),
                                    falsifier="load persists after scale-down"))
    check("grounded hypothesis is OPEN (never VERIFIED)", h.status is HypothesisStatus.OPEN)
    check("hypothesis grounds in real fact refs", len(h.support_refs) >= 1)
    check("hypothesis traces to the model proposal", h.provenance.parent_claim_ref == "mp-1")

    # ---- prediction vs real outcome (execution_ref) ----
    print("[pred] prediction evaluated against a real outcome")
    pred = Prediction(record_id="pr-1", tenant=tenant, recorded_at=_utc(10, 7),
                      provenance=ProvenanceRef(produced_by="model:gpt", parent_claim_ref=h.record_id),
                      subject_ref="deployment/ind", expected={"healthy": True},
                      predicted_at=_utc(10, 7), deadline=_utc(10, 12), hypothesis_ref=h.record_id)
    outcome = Outcome(record_id="oc-1", tenant=tenant, recorded_at=_utc(10, 11),
                      provenance=ProvenanceRef(produced_by="platform", execution_ref=exec_id),
                      execution_ref=exec_id, observed={"healthy": True}, prediction_ref="pr-1")
    ev = evaluate_prediction(prediction=pred, outcome=outcome, observed_at=_utc(10, 11))
    check("prediction matched the real outcome", ev.matched is True)
    check("outcome within the prediction horizon", ev.within_horizon is True)
    check("evaluation ties to the real execution_ref", ev.execution_ref == exec_id)

    # ---- temporal + knowledge-time ----
    print("[temporal] world-time and knowledge-time beliefs")
    idr(_read("deployment/tmp", {"replicas": 5}, _utc(10, 0), K8S), at=_utc(10, 4))
    idr(_read("deployment/tmp", {"replicas": 3}, _utc(9, 58), K8S), at=_utc(10, 10))
    check("world @ 09:59 -> 3", beliefs.form_as_of_valid(
        tenant=tenant, subject_ref="deployment/tmp", predicate="spec.replicas",
        at_valid=_utc(9, 59), now=_utc(10, 20)).value == {"replicas": 3})
    check("known @ 10:00 -> UNKNOWN (no future leak)", beliefs.form_as_known(
        tenant=tenant, subject_ref="deployment/tmp", predicate="spec.replicas",
        known_at=_utc(10, 0)).status is EpistemicStatus.UNKNOWN)

    # ---- tenant fail-closed ----
    print("[tenant] cross-tenant fail closed")
    check("cross-tenant belief UNKNOWN",
          believe("deployment/ind", _utc(10, 5), who=other).status is EpistemicStatus.UNKNOWN)

    # ---- replay inert ----
    print("[replay] inert; belief identical across replay")
    from backend.contexts.execution.application.commands import ReplayExecution
    facts_before, prov_before = fact_repo.count_all(), len(adapter.calls)
    before = believe("deployment/ind", _utc(10, 5)).to_dict()
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    check("replay zero new facts", fact_repo.count_all() == facts_before)
    check("replay zero provider reads", len(adapter.calls) == prov_before)
    check("belief identical across replay", before == believe("deployment/ind", _utc(10, 5)).to_dict())

    # ---- crash / deterministic reconstruction ----
    print("[crash] deterministic belief reconstruction after os._exit(9)")
    import subprocess
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase76_lineage_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    _, _, _, _, _, succ = _stack(_store())
    r1 = succ.form_current(tenant=tenant, subject_ref="deployment/crash",
                           predicate="spec.replicas", now=_utc(12, 5))
    r2 = succ.form_current(tenant=tenant, subject_ref="deployment/crash",
                           predicate="spec.replicas", now=_utc(12, 5))
    check("crashed belief reconstructs", r1.value == {"replicas": 9})
    check("reconstruction deterministic", r1.to_dict() == r2.to_dict())

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    REPORT["counts"] = {"facts": fact_repo.count_all(), "observations": obs_repo.count_all(),
                        "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "lineage/belief-policy/hypothesis verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
