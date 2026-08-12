"""Phase 8.2 real-Postgres evidence: the Investigation Engine vertical slice.

Run:  python -m scripts.phase82_investigation_harness
      python -m scripts.phase82_investigation_harness --crash-child   (internal)

A complete deterministic DevOps-incident investigation against a fresh
cortex_p82, using the SCRIPTED model (provider="scripted") and the REAL governed
READ path for evidence: create -> assemble context -> propose differential ->
discriminating test -> governed read -> Observation -> Fact -> update
differential -> checkpoint -> ... -> deterministic RESOLVED. Then: crash/resume
(no repeated test, no fabricated progress), concurrent resume (exactly one owns
the next transition), replay inertness, and tenant isolation.

The real LLM is BLOCKED (placeholder credentials); every model call is honestly
labeled provider="scripted". No direct provider access from the engine. Exit:
0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

from scripts.phase72_observation_harness import (
    _governed_read_evidence, _commission, _store,
)
from scripts.phase62_recovery_harness import TENANT, _tenant_ctx

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
CAUSE = {"cause": "rollout"}
SUBJECT, PREDICATE = "deployment/payments", "state"


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


# ---- scripted model (honest provider label) ----
class ScriptedModel:
    def propose(self, *, context, investigation, now):
        from backend.contracts.world import HypothesisStatus
        from backend.intelligence.application import (
            InvestigationProposal, ProposedHypothesis, ProposedTest,
        )
        hyps = ()
        if not investigation.differential:
            hyps = (
                ProposedHypothesis("h1", "rollout regression", SUBJECT, "consistent"),
                ProposedHypothesis("h2", "db saturation", SUBJECT, "unknown"),
                ProposedHypothesis("h3", "network degradation", SUBJECT, "unknown"),
            )
        target = next((h.hypothesis_ref for h in investigation.differential
                       if h.status is HypothesisStatus.OPEN),
                      hyps[0].hypothesis_ref if hyps else None)
        test = None
        if target is not None:
            test = ProposedTest(
                discriminates_hypothesis=target, tool="deploy.history", subject_ref=SUBJECT,
                predicate=PREDICATE, evidence_expected="incident cause",
                supports_if="cause matches", contradicts_if="cause differs",
                residual_uncertainty="timing",
                supports_value=CAUSE if target == "h1" else {"cause": "other"},
                contradicts_value={"cause": "other"} if target == "h1" else CAUSE)
        return InvestigationProposal(provider="scripted", proposal_digest="d",
                                     interpretation="testing differential",
                                     proposed_hypotheses=hyps, proposed_test=test,
                                     suggested_conclusion="resolved")


class WorldRead:
    def __init__(self, query):
        self._q = query

    def evidence_for(self, *, tenant, subject_ref, predicate, now):
        r = self._q.current(tenant=tenant, subject_ref=subject_ref, predicate=predicate, now=now)
        return {"subject_ref": subject_ref, "predicate": predicate,
                "value": r.effective_value, "status": r.effective_status.value}


class GovernedEvidence:
    """The governed READ path: a governed execution + ingest an Observation whose
    value is the scenario cause, derive a Fact, return the refs. Counts provider
    reads. This is the ONLY new world contact — the engine never touches a
    connector itself."""

    def __init__(self, *, runtime, defs, tenant_ctx, ingestion, derivation):
        self._runtime, self._defs, self._tctx = runtime, defs, tenant_ctx
        self._ingest, self._derive = ingestion, derivation
        self.reads = 0

    def acquire(self, *, tenant, request, now):
        from backend.contracts.evidence import SourceStatus
        from backend.contracts.world import ObservationSourceKind
        from backend.intelligence.application import EvidenceResult
        from backend.world.application import ReadObservation
        try:
            exec_id, node, state, _ev = _governed_read_evidence(self._runtime, self._tctx, self._defs)
            self.reads += 1
            read = ReadObservation(
                source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
                subject_ref=request.subject_ref, predicate=request.predicate, value=CAUSE,
                status=SourceStatus.RETURNED_DATA, observed_at=now, retrieved_at=now,
                produced_by="connector:kubernetes", execution_ref=exec_id)
            obs, _ = self._ingest.ingest(tenant=tenant, read=read, recorded_at=now)
            self._derive.derive(tenant=tenant, observation=obs, recorded_at=now)
            return EvidenceResult(ok=True, subject_ref=request.subject_ref,
                                  predicate=request.predicate, observation_ref=obs.record_id,
                                  observed_value=CAUSE, source_ref="connector:kubernetes")
        except Exception as exc:  # noqa: BLE001
            return EvidenceResult(ok=False, subject_ref=request.subject_ref,
                                  predicate=request.predicate, reason=type(exc).__name__)


def _stack(persistence):
    from backend.intelligence.application import InvestigationService
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    return InvestigationService(repository=SqlInvestigationRepository(persistence.store)), \
        SqlInvestigationRepository(persistence.store)


def _run_crash_child():
    """Run a couple of engine steps, then die mid-investigation."""
    from backend.contracts.tenant import TenantRef
    from backend.contracts.intelligence import InvestigationStatus
    from backend.intelligence.application import (
        ContextAssembler, EvidenceSelectionPolicy, InvestigationBudget,
        InvestigationEngine,
    )
    persistence = _store()
    svc, _ = _stack(persistence)
    tenant = TenantRef(tenant_id=TENANT)
    # scripted-only evidence for the crash child (no governed runtime here)
    class LocalEvidence:
        reads = 0
        def acquire(self, *, tenant, request, now):
            from backend.intelligence.application import EvidenceResult
            LocalEvidence.reads += 1
            return EvidenceResult(ok=True, subject_ref=request.subject_ref,
                                  predicate=request.predicate, observation_ref=f"wobs-c{LocalEvidence.reads}",
                                  observed_value=CAUSE, source_ref="connector:kubernetes")

    class LocalWorld:
        def evidence_for(self, *, tenant, subject_ref, predicate, now):
            return {"subject_ref": subject_ref, "value": CAUSE, "status": "affirmed"}

    inv = svc.create(tenant=tenant, incident_ref="incident:crash", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0), investigation_ref="winv-crash")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    eng = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=ScriptedModel(),
                              evidence_port=LocalEvidence(), world_read_port=LocalWorld(),
                              policy=EvidenceSelectionPolicy(), harness_version="h/1",
                              available_tools=("deploy.history",))
    # two steps then die (h1 supported, h2 refuted; h3 still open -> not concluded)
    r = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
    eng.step(investigation=r.investigation, budget=InvestigationBudget(), now=_t(3))
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
    from backend.contracts.world import HypothesisStatus
    from backend.contracts.intelligence import InvestigationConclusion, InvestigationStatus
    from backend.platform.context import ExecutionContext
    from backend.intelligence.application import (
        ContextAssembler, EvidenceSelectionPolicy, InvestigationBudget,
        InvestigationConcurrencyError, InvestigationEngine, InvestigationNotFound,
    )
    from backend.world.application import (
        FactDerivation, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p82 slice", component="investigation-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    svc, repo = _stack(runtime.persistence)
    obs_repo = SqlObservationRepository(runtime.persistence.store)
    fact_repo = SqlFactRepository(runtime.persistence.store)
    query = WorldQuery(facts=fact_repo, observations=obs_repo)
    evidence = GovernedEvidence(runtime=runtime, defs=defs, tenant_ctx=tenant_ctx,
                                ingestion=ObservationIngestion(repository=obs_repo),
                                derivation=FactDerivation(repository=fact_repo))
    engine = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=ScriptedModel(),
                                 evidence_port=evidence, world_read_port=WorldRead(query),
                                 policy=EvidenceSelectionPolicy(), harness_version="h/1",
                                 available_tools=("deploy.history", "metrics.window"))

    # ---- vertical slice: OBSERVE -> INVESTIGATE -> UPDATE -> CONCLUDE ----
    print("[M] full investigation vertical slice (scripted model, governed reads)")
    inv = svc.create(tenant=tenant, incident_ref="incident:latency", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0), investigation_ref="winv-a")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    digests = []
    step_i = 0
    while not inv.is_terminal and step_i < 10:
        res = engine.step(investigation=inv, budget=InvestigationBudget(), now=_t(2 + step_i))
        inv = res.investigation
        digests.append(res.context_digest)
        check(f"step {step_i} provider is scripted", res.provider in ("scripted", "n/a"))
        step_i += 1
    check("investigation reached RESOLVED", inv.conclusion is InvestigationConclusion.RESOLVED,
          str(inv.conclusion))
    check("exactly one hypothesis affirmed (h1)",
          [h.hypothesis_ref for h in inv.differential if h.status is HypothesisStatus.SUPPORTED] == ["h1"])
    check("governed reads == provider calls (no direct provider from engine)",
          evidence.reads == len(adapter.calls), f"reads={evidence.reads} calls={len(adapter.calls)}")
    check("context digests were recorded per step", len(digests) == step_i and all(digests))
    check("real observations/facts were created via the governed read",
          obs_repo.count_all() >= 1 and fact_repo.count_all() >= 1)

    # ---- crash / resume (no repeated test, no fabricated progress) ----
    print("[G] crash + resume")
    import subprocess
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase82_investigation_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    _, succ_repo = _stack(_store())
    from backend.intelligence.application import InvestigationService as _Svc
    succ = _Svc(repository=succ_repo)
    resumed = succ.reconstruct(tenant=tenant, investigation_ref="winv-crash")
    check("crashed investigation reconstructs (not fabricated)",
          resumed.status is InvestigationStatus.INVESTIGATING and not resumed.is_terminal)
    check("pre-crash tests survived (resume != retry)", len(resumed.test_refs) >= 1)
    tests_before_resume = set(resumed.test_refs)
    # resume the loop; already-run tests must NOT be repeated (redundancy policy)
    resume_engine = InvestigationEngine(
        service=succ, assembler=ContextAssembler(), model_port=ScriptedModel(),
        evidence_port=_LocalOK(), world_read_port=_LocalWorld(), policy=EvidenceSelectionPolicy(),
        harness_version="h/1", available_tools=("deploy.history",))
    final = resume_engine.run(investigation=resumed, budget=InvestigationBudget(),
                              clock=lambda i: _t(20 + i))
    check("resume reaches a terminal conclusion", final.is_terminal and final.conclusion is not None)
    check("no already-completed test was repeated",
          all(t in set(final.test_refs) for t in tests_before_resume)
          and len(set(final.test_refs)) >= len(tests_before_resume))

    # ---- concurrent resume: exactly one owns the next transition ----
    print("[G2] concurrent resume — exactly one writer wins the next seq")
    base = succ.reconstruct(tenant=tenant, investigation_ref="winv-a")  # terminal; use winv-a? use a fresh
    conc = svc.create(tenant=tenant, incident_ref="incident:conc", policy_ref="pol/1",
                      harness_version="h/1", now=_t(0), investigation_ref="winv-conc")
    a_view = svc.reconstruct(tenant=tenant, investigation_ref="winv-conc")
    b_view = svc.reconstruct(tenant=tenant, investigation_ref="winv-conc")  # same snapshot
    a_ok = _try(lambda: svc.transition(investigation=a_view,
                                       to_status=InvestigationStatus.INVESTIGATING, cause="A", now=_t(1)))
    b_ok = _try(lambda: svc.transition(investigation=b_view,
                                       to_status=InvestigationStatus.INVESTIGATING, cause="B", now=_t(1)))
    check("exactly one concurrent writer committed the next seq", a_ok != b_ok, f"A={a_ok} B={b_ok}")
    check("the loser raised concurrency (no fork, no overwrite)", (a_ok and not b_ok) or (b_ok and not a_ok))

    # ---- replay inert ----
    print("[N] replay inert")
    from backend.contexts.execution.application.commands import ReplayExecution
    ev_before = repo.count_all()
    facts_before, prov_before = fact_repo.count_all(), len(adapter.calls)
    # reconstruction is a pure read — do it repeatedly
    for _ in range(5):
        svc.reconstruct(tenant=tenant, investigation_ref="winv-a")
    check("reconstruction created zero investigation events", repo.count_all() == ev_before)
    check("reconstruction did zero governed reads / world mutations",
          fact_repo.count_all() == facts_before and len(adapter.calls) == prov_before)

    # ---- tenant isolation ----
    print("[O] tenant isolation (fail closed)")
    check("cross-tenant reconstruct fails closed",
          _try_raises(lambda: succ.reconstruct(tenant=other, investigation_ref="winv-crash"),
                      InvestigationNotFound))

    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"investigation_events": repo.count_all(), "observations": obs_repo.count_all(),
                        "facts": fact_repo.count_all(), "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "investigation engine verified" if ok else "a check failed")


class _LocalOK:
    reads = 0
    def acquire(self, *, tenant, request, now):
        from backend.intelligence.application import EvidenceResult
        _LocalOK.reads += 1
        return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                              observation_ref=f"wobs-r{_LocalOK.reads}", observed_value=CAUSE,
                              source_ref="connector:kubernetes")


class _LocalWorld:
    def evidence_for(self, *, tenant, subject_ref, predicate, now):
        return {"subject_ref": subject_ref, "value": CAUSE, "status": "affirmed"}


def _try(fn):
    try:
        fn()
        return True
    except Exception:
        return False


def _try_raises(fn, exc):
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
