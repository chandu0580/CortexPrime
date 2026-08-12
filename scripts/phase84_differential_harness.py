"""Phase 8.4 real-Postgres evidence: differential diagnosis & evidence intelligence.

Run:  python -m scripts.phase84_differential_harness
      python -m scripts.phase84_differential_harness --crash-child   (internal)

A realistic 4-hypothesis DevOps incident against a fresh cortex_p84, using the
scripted model (provider="scripted") and the REAL governed read path + REAL
WorldQuery (freshness + authority):

  "Production API latency increased sharply at 10:03."
    H1 deployment regression   H2 database saturation
    H3 network degradation     H4 external dependency degradation

The model proposes the differential + candidate discriminating tests; the PLATFORM
selects the most discriminating admissible test each step; governed reads produce
real Observations/Facts; the differential updates from the OBSERVED value:
  H2, H3 -> REFUTED (eliminated)      H4 -> SUPPORTED
  H1 -> OPEN (deploy at 09:58 is temporally consistent but inconclusive)
Terminal: RESOLVED with H4 the leading explanation, residual uncertainty naming H1
(not eliminated) and "not Assurance-verified" — a supported hypothesis is NOT a
verified one, and an open alternative is NOT false.

Then: evidence reuse (a second hypothesis on an already-read subject spends no new
governed read), freshness/authority consumption (STALE/CONFLICTED never reused),
real process crash + reconstruction (no repeated tests, no fabricated progress),
replay inertness, and tenant isolation.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone

from scripts.phase72_observation_harness import _governed_read_evidence, _commission, _store
from scripts.phase62_recovery_harness import TENANT, _tenant_ctx

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}

# The scenario: each hypothesis on a DISTINCT subject/predicate, with a structured
# expectation the platform compares against the observed world value.
SCENARIO = {
    "h1": {"prop": "deployment regression", "subject": "deployment/payments",
           "predicate": "rollout_window", "tool": "deploy.history", "fit": "consistent",
           "supports": {"window_s": 60}, "contradicts": {"window_s": 86400},
           "observed": {"window_s": 300}},          # 09:58 deploy, 5 min before -> inconclusive
    "h2": {"prop": "database saturation", "subject": "database/payments",
           "predicate": "saturation", "tool": "metrics.window", "fit": "unknown",
           "supports": {"saturated": True}, "contradicts": {"saturated": False},
           "observed": {"saturated": False}},        # db normal -> refuted
    "h3": {"prop": "network degradation", "subject": "network/payments",
           "predicate": "health", "tool": "metrics.window", "fit": "unknown",
           "supports": {"degraded": True}, "contradicts": {"degraded": False},
           "observed": {"degraded": False}},         # network normal -> refuted
    "h4": {"prop": "external dependency degradation", "subject": "dependency/stripe",
           "predicate": "latency", "tool": "metrics.window", "fit": "consistent",
           "supports": {"elevated": True}, "contradicts": {"elevated": False},
           "observed": {"elevated": True}},          # dependency elevated at 10:02 -> supported
}
SUBJECT_VALUE = {v["subject"]: v["observed"] for v in SCENARIO.values()}
TOOLS = ("deploy.history", "metrics.window")


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


def _mk_test(ref):
    from backend.intelligence.application import ProposedTest
    s = SCENARIO[ref]
    return ProposedTest(
        discriminates_hypothesis=ref, tool=s["tool"], subject_ref=s["subject"],
        predicate=s["predicate"], evidence_expected=f"whether {s['prop']} explains the latency",
        supports_if="observation matches the hypothesis", contradicts_if="observation is inconsistent",
        residual_uncertainty="temporal precision", supports_value=s["supports"],
        contradicts_value=s["contradicts"])


def _test_ran(ref, test_refs):
    from backend.intelligence.application.proposal import test_identity
    s = SCENARIO[ref]
    tid = test_identity(discriminates=ref, tool=s["tool"], subject_ref=s["subject"],
                        predicate=s["predicate"])
    return any(tid in r for r in test_refs)


class ScenarioModel:
    """Proposes the 4-hypothesis differential once, then — each step — a candidate
    discriminating test for every OPEN hypothesis whose test has not yet run. The
    PLATFORM selects among the candidates; the model never dictates the order."""

    def propose(self, *, context, investigation, now):
        from backend.contracts.world import HypothesisStatus
        from backend.intelligence.application import InvestigationProposal, ProposedHypothesis
        hyps = ()
        if not investigation.differential:
            hyps = tuple(ProposedHypothesis(ref, SCENARIO[ref]["prop"], SCENARIO[ref]["subject"],
                                            SCENARIO[ref]["fit"]) for ref in SCENARIO)
            candidates = tuple(_mk_test(ref) for ref in SCENARIO)
        else:
            candidates = tuple(
                _mk_test(h.hypothesis_ref) for h in investigation.differential
                if h.status is HypothesisStatus.OPEN
                and not _test_ran(h.hypothesis_ref, investigation.test_refs))
        return InvestigationProposal(
            provider="scripted", proposal_digest="d", interpretation="differential diagnosis",
            proposed_hypotheses=hyps, proposed_tests=candidates, suggested_conclusion="resolved")


class WorldRead:
    """The read-only World port, backed by the REAL WorldQuery (freshness +
    authority). Returns the structured verdicts the investigator CONSUMES — it does
    not reclassify freshness/authority itself."""

    def __init__(self, query):
        self._q = query

    def evidence_for(self, *, tenant, subject_ref, predicate, now):
        r = self._q.current(tenant=tenant, subject_ref=subject_ref, predicate=predicate, now=now)
        d = r.to_dict()
        return {
            "subject_ref": subject_ref, "predicate": predicate, "value": r.effective_value,
            "status": r.effective_status.value, "freshness": d["fresh"]["state"],
            "authority_tier": d["why"]["tier"], "authority_status": d["why"]["authority_status"],
            "conflicted": d["conflicted"], "source_ref": d["why"]["source_ref"],
            "evidence": [{"observation_id": e["observation_id"], "source_ref": e["source_ref"],
                          "authority_tier": e["authority_tier"]} for e in d["evidence"]],
        }


class GovernedEvidence:
    """The governed READ path: a governed execution + ingest an Observation whose
    value is the scenario value for the requested subject, derive a Fact, return
    refs. Counts provider reads — the engine never touches a connector itself."""

    def __init__(self, *, runtime, defs, tenant_ctx, ingestion, derivation, value_map=None):
        self._runtime, self._defs, self._tctx = runtime, defs, tenant_ctx
        self._ingest, self._derive = ingestion, derivation
        self._values = value_map if value_map is not None else SUBJECT_VALUE
        self.reads = 0

    def acquire(self, *, tenant, request, now):
        from backend.contracts.evidence import SourceStatus
        from backend.contracts.world import ObservationSourceKind
        from backend.intelligence.application import EvidenceResult
        from backend.world.application import ReadObservation
        try:
            exec_id, _n, _s, _e = _governed_read_evidence(self._runtime, self._tctx, self._defs)
            self.reads += 1
            value = self._values.get(request.subject_ref, {"unknown": True})
            read = ReadObservation(
                source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
                subject_ref=request.subject_ref, predicate=request.predicate, value=value,
                status=SourceStatus.RETURNED_DATA, observed_at=now, retrieved_at=now,
                produced_by="connector:kubernetes", execution_ref=exec_id)
            obs, _ = self._ingest.ingest(tenant=tenant, read=read, recorded_at=now)
            self._derive.derive(tenant=tenant, observation=obs, recorded_at=now)
            return EvidenceResult(ok=True, subject_ref=request.subject_ref,
                                  predicate=request.predicate, observation_ref=obs.record_id,
                                  observed_value=value, source_ref="connector:kubernetes")
        except Exception as exc:  # noqa: BLE001
            return EvidenceResult(ok=False, subject_ref=request.subject_ref,
                                  predicate=request.predicate, reason=type(exc).__name__)


def _stack(persistence):
    from backend.intelligence.application import InvestigationService
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    return InvestigationService(repository=SqlInvestigationRepository(persistence.store)), \
        SqlInvestigationRepository(persistence.store)


def _world(persistence):
    from backend.world.application import FreshnessPolicy, FreshnessRule, WorldQuery
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository
    obs_repo = SqlObservationRepository(persistence.store)
    fact_repo = SqlFactRepository(persistence.store)
    fresh = FreshnessPolicy(rules=(FreshnessRule(horizon_seconds=3600.0, name="default"),),
                            name="p84")
    query = WorldQuery(facts=fact_repo, observations=obs_repo, freshness_policy=fresh)
    return obs_repo, fact_repo, query


def _run_crash_child():
    from backend.contracts.tenant import TenantRef
    from backend.contracts.intelligence import InvestigationStatus
    from backend.intelligence.application import (
        ContextAssembler, EvidenceSelectionPolicy, InvestigationBudget, InvestigationEngine,
    )
    persistence = _store()
    svc, _ = _stack(persistence)
    tenant = TenantRef(tenant_id=TENANT)

    class LocalEvidence:
        reads = 0
        def acquire(self, *, tenant, request, now):
            from backend.intelligence.application import EvidenceResult
            LocalEvidence.reads += 1
            return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                                  observation_ref=f"wobs-c{LocalEvidence.reads}",
                                  observed_value=SUBJECT_VALUE.get(request.subject_ref, {}),
                                  source_ref="connector:kubernetes")

    class LocalWorld:
        def evidence_for(self, *, tenant, subject_ref, predicate, now):
            return {"subject_ref": subject_ref, "predicate": predicate, "value": None,
                    "status": "unknown", "freshness": "unknown", "evidence": []}

    inv = svc.create(tenant=tenant, incident_ref="incident:crash", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0), investigation_ref="winv-crash")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    eng = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=ScenarioModel(),
                              evidence_port=LocalEvidence(), world_read_port=LocalWorld(),
                              policy=EvidenceSelectionPolicy(), harness_version="h/1",
                              available_tools=TOOLS)
    eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
    r = eng.step(investigation=svc.reconstruct(tenant=tenant, investigation_ref="winv-crash"),
                 budget=InvestigationBudget(), now=_t(3))
    del r
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
    from backend.contracts.world import HypothesisStatus
    from backend.contracts.intelligence import InvestigationConclusion, InvestigationStatus
    from backend.platform.context import ExecutionContext
    from backend.intelligence.application import (
        ContextAssembler, EvidenceSelectionPolicy, InvestigationBudget, InvestigationEngine,
        InvestigationNotFound, ProposedHypothesis, InvestigationProposal, analyze_gaps,
    )
    from backend.world.application import FactDerivation, ObservationIngestion

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p84 differential", component="differential-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    svc, repo = _stack(runtime.persistence)
    obs_repo, fact_repo, query = _world(runtime.persistence)
    evidence = GovernedEvidence(runtime=runtime, defs=defs, tenant_ctx=tenant_ctx,
                                ingestion=ObservationIngestion(repository=obs_repo),
                                derivation=FactDerivation(repository=fact_repo))
    engine = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=ScenarioModel(),
                                 evidence_port=evidence, world_read_port=WorldRead(query),
                                 policy=EvidenceSelectionPolicy(), harness_version="h/1",
                                 available_tools=TOOLS)

    # ---- [P] the 4-hypothesis differential ----
    print("[P] 4-hypothesis DevOps differential diagnosis (scripted model, governed reads)")
    inv = svc.create(tenant=tenant, incident_ref="incident:latency", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0), investigation_ref="winv-a")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    last_gaps = ()
    i = 0
    while not inv.is_terminal and i < 12:
        res = engine.step(investigation=inv, budget=InvestigationBudget(max_steps=10, max_reads=12),
                          now=_t(2 + i))
        inv = res.investigation
        if res.gaps:
            last_gaps = res.gaps
        i += 1
    by_ref = {h.hypothesis_ref: h.status for h in inv.differential}
    check("H2 eliminated (database normal)", by_ref.get("h2") is HypothesisStatus.REFUTED, by_ref)
    check("H3 eliminated (network normal)", by_ref.get("h3") is HypothesisStatus.REFUTED, by_ref)
    check("H4 supported (dependency elevated)", by_ref.get("h4") is HypothesisStatus.SUPPORTED, by_ref)
    check("H1 remains OPEN (temporally consistent but inconclusive) — not FALSE",
          by_ref.get("h1") is HypothesisStatus.OPEN, by_ref)
    check("conclusion RESOLVED with H4 leading", inv.conclusion is InvestigationConclusion.RESOLVED,
          str(inv.conclusion))
    # honesty: supported != verified; open alternative named, never claimed false
    check("no verification claimed (verification_refs empty)", not inv.verification_refs)
    check("governed reads == provider calls (no direct provider from engine)",
          evidence.reads == len(adapter.calls), f"reads={evidence.reads} calls={len(adapter.calls)}")
    check("real observations/facts created via governed reads",
          obs_repo.count_all() >= 4 and fact_repo.count_all() >= 4)

    # ---- [C] evidence gaps are explicit ----
    print("[C] evidence-gap analysis is explicit")
    # gaps computed for the final live differential (H1 supported? no — H4 supported, H1 open)
    final_gaps = {g["hypothesis_ref"]: g for g in (last_gaps or tuple(
        g.to_dict() for g in analyze_gaps(inv)))}
    check("a gap explains why a hypothesis is unresolved",
          any("unresolved" in g["unresolved_reason"] for g in final_gaps.values()),
          list(final_gaps))

    # ---- [F] evidence reuse: second hypothesis on an already-read subject ----
    print("[F] evidence reuse (no redundant governed read)")
    reuse_values = {"cache/redis": {"evicting": True}}
    reuse_ev = GovernedEvidence(runtime=runtime, defs=defs, tenant_ctx=tenant_ctx,
                                ingestion=ObservationIngestion(repository=obs_repo),
                                derivation=FactDerivation(repository=fact_repo),
                                value_map=reuse_values)

    class ReuseModel:
        def propose(self, *, context, investigation, now):
            if not investigation.differential:
                hyps = (ProposedHypothesis("ra", "cache eviction storm", "cache/redis", "consistent"),
                        ProposedHypothesis("rb", "cache thrash", "cache/redis", "consistent"))
                return InvestigationProposal(
                    provider="scripted", proposal_digest="d", proposed_hypotheses=hyps,
                    proposed_tests=(_reuse_test("ra"), _reuse_test("rb")))
            cands = tuple(
                _reuse_test(h.hypothesis_ref) for h in investigation.differential
                if h.status is HypothesisStatus.OPEN and not _reuse_ran(h.hypothesis_ref, investigation.test_refs))
            return InvestigationProposal(provider="scripted", proposal_digest="d",
                                         proposed_hypotheses=(), proposed_tests=cands)

    reuse_engine = InvestigationEngine(
        service=svc, assembler=ContextAssembler(), model_port=ReuseModel(), evidence_port=reuse_ev,
        world_read_port=WorldRead(query), policy=EvidenceSelectionPolicy(), harness_version="h/1",
        available_tools=("cache.inspect",))
    rinv = svc.create(tenant=tenant, incident_ref="incident:cache", policy_ref="pol/1",
                      harness_version="h/1", now=_t(0), investigation_ref="winv-reuse")
    rinv = svc.transition(investigation=rinv, to_status=InvestigationStatus.INVESTIGATING,
                          cause="triage", now=_t(1))
    calls_before = len(adapter.calls)
    j = 0
    while not rinv.is_terminal and j < 6:
        rr = reuse_engine.step(investigation=rinv, budget=InvestigationBudget(), now=_t(30 + j))
        rinv = rr.investigation
        j += 1
    reuse_by = {h.hypothesis_ref: h.status for h in rinv.differential}
    check("two hypotheses share a subject; both resolved",
          reuse_by.get("ra") is HypothesisStatus.SUPPORTED and reuse_by.get("rb") is HypothesisStatus.SUPPORTED,
          reuse_by)
    check("second hypothesis reused evidence — exactly ONE new governed read for two tests",
          len(adapter.calls) - calls_before == 1, f"delta={len(adapter.calls) - calls_before}")

    # ---- [G] freshness != truth; conflict preserved (STALE/CONFLICTED never reused) ----
    print("[G] freshness/authority consumed from WorldQuery (STALE/CONFLICTED not reused)")
    from backend.intelligence.application import EvidenceSelectionPolicy as _Pol
    probe_inv = svc.reconstruct(tenant=tenant, investigation_ref="winv-reuse")
    validated = _Pol().validate(
        investigation=_FakeDiff([("ra", HypothesisStatus.OPEN, "cache/redis")]),
        proposed=_reuse_test("ra"), available_tools=("cache.inspect",))
    stale_engine = InvestigationEngine(
        service=svc, assembler=ContextAssembler(), model_port=ReuseModel(), evidence_port=reuse_ev,
        world_read_port=_StaleWorld("stale"), policy=_Pol(), harness_version="h/1",
        available_tools=("cache.inspect",))
    check("STALE world evidence is NOT reused (freshness != truth)",
          stale_engine._reuse_existing_evidence(probe_inv, validated, _t(40)) is None)
    conflict_engine = InvestigationEngine(
        service=svc, assembler=ContextAssembler(), model_port=ReuseModel(), evidence_port=reuse_ev,
        world_read_port=_StaleWorld("conflicted", status="conflicted"), policy=_Pol(),
        harness_version="h/1", available_tools=("cache.inspect",))
    check("CONFLICTED world evidence is NOT reused (conflict preserved)",
          conflict_engine._reuse_existing_evidence(probe_inv, validated, _t(40)) is None)
    wd = WorldRead(query).evidence_for(tenant=tenant, subject_ref="dependency/stripe",
                                       predicate="latency", now=_t(20))
    check("investigator consumes WorldQuery authority tier (not reimplemented)",
          "authority_tier" in wd and wd["status"] == "affirmed", wd.get("authority_tier"))

    # ---- [O] adversarial: a favoured hypothesis does not become truth ----
    print("[O] adversarial — model claim never becomes platform truth")
    check("no model verdict promoted H1 to supported (world governs)",
          by_ref.get("h1") is not HypothesisStatus.SUPPORTED)

    # ---- [Q] crash + reconstruction; replay inert ----
    print("[Q] crash + reconstruction, replay inert")
    import subprocess
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase84_differential_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    succ_svc, succ_repo = _stack(_store())
    resumed = succ_svc.reconstruct(tenant=tenant, investigation_ref="winv-crash")
    check("crashed investigation reconstructs INVESTIGATING (not fabricated)",
          resumed.status is InvestigationStatus.INVESTIGATING and not resumed.is_terminal)
    check("pre-crash tests survived (resume != retry)", len(resumed.test_refs) >= 1)
    tests_before = set(resumed.test_refs)
    ev_before, facts_before, prov_before = repo.count_all(), fact_repo.count_all(), len(adapter.calls)
    for _ in range(5):
        svc.reconstruct(tenant=tenant, investigation_ref="winv-a")
    check("replay inert: 0 new investigation events", repo.count_all() == ev_before)
    check("replay inert: 0 governed reads / world mutations",
          fact_repo.count_all() == facts_before and len(adapter.calls) == prov_before)
    check("reconstruction did not repeat completed tests",
          set(succ_svc.reconstruct(tenant=tenant, investigation_ref="winv-crash").test_refs) == tests_before)

    # ---- [R] tenant isolation ----
    print("[R] tenant isolation (fail closed)")
    check("cross-tenant reconstruct fails closed",
          _raises(lambda: succ_svc.reconstruct(tenant=other, investigation_ref="winv-crash"),
                  InvestigationNotFound))
    other_world = WorldRead(query).evidence_for(tenant=other, subject_ref="dependency/stripe",
                                                predicate="latency", now=_t(20))
    check("cross-tenant world evidence is empty (no leak of tenant A facts)",
          not other_world["evidence"] and other_world["status"] != "affirmed", other_world["status"])

    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"investigation_events": repo.count_all(), "observations": obs_repo.count_all(),
                        "facts": fact_repo.count_all(), "provider_calls": len(adapter.calls),
                        "governed_reads": evidence.reads + reuse_ev.reads}
    REPORT["conclusion"] = {"status": inv.status.value, "conclusion": inv.conclusion.value,
                            "differential": by_ref and {k: v.value for k, v in by_ref.items()}}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "differential diagnosis verified" if ok else "a check failed")


# -- reuse-scenario helpers -------------------------------------------------

def _reuse_test(ref):
    from backend.intelligence.application import ProposedTest
    return ProposedTest(discriminates_hypothesis=ref, tool="cache.inspect", subject_ref="cache/redis",
                        predicate="state", evidence_expected="eviction state",
                        supports_if="evicting", contradicts_if="calm", residual_uncertainty="x",
                        supports_value={"evicting": True}, contradicts_value={"evicting": False})


def _reuse_ran(ref, test_refs):
    from backend.intelligence.application.proposal import test_identity
    tid = test_identity(discriminates=ref, tool="cache.inspect", subject_ref="cache/redis",
                        predicate="state")
    return any(tid in r for r in test_refs)


class _FakeDiff:
    def __init__(self, hyps):
        from backend.contracts.intelligence import DifferentialHypothesis, TemporalFit
        self.differential = tuple(
            DifferentialHypothesis(hypothesis_ref=r, subject_ref=s, proposition=f"p {r}",
                                   status=st, temporal_fit=TemporalFit.UNKNOWN, created_by="scripted:model")
            for (r, st, s) in hyps)
        self.test_refs = ()


class _StaleWorld:
    def __init__(self, freshness, status="affirmed"):
        self._f, self._s = freshness, status
    def evidence_for(self, *, tenant, subject_ref, predicate, now):
        return {"subject_ref": subject_ref, "predicate": predicate, "value": {"evicting": True},
                "status": self._s, "freshness": self._f,
                "evidence": [{"observation_id": "wobs-x", "source_ref": "connector:kubernetes"}]}


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
