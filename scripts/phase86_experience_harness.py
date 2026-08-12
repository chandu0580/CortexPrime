"""Phase 8.6 real-Postgres evidence: incident episodes & investigation experience.

Run:  python -m scripts.phase86_experience_harness
      python -m scripts.phase86_experience_harness --crash-child   (internal)

A prior investigation E123 (payments-api latency → external dependency degradation
SUPPORTED) becomes durable EXPERIENCE. A new incident E456 with the same symptoms
retrieves E123 and injects it as HISTORICAL context — but the current world says
dependency latency is NORMAL, so H4 is NOT auto-accepted; E456 independently finds
deployment regression. Experience is relevant, never current truth.

Proves against a fresh cortex_p86: experience is reconstructed from the durable
ledgers (no new table), retrieval is deterministic/explainable/tenant-scoped/
temporally-safe, history cannot become current truth, historical test IDEAS are
re-governed (never historical authorization), the calibration substrate is captured
in cw_reasoning, and crash/replay/tenant/temporal all hold. Real LLM BLOCKED;
provider="scripted".

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
from scripts.phase84_differential_harness import GovernedEvidence, WorldRead, _world

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
INCIDENT = "incident:production:payments-api:latency-spike"
TOOLS = ("deploy.history", "metrics.window")

# E456's world: deployment regression is real THIS time; dependency is NORMAL —
# directly contradicting E123's historical conclusion.
E456 = {
    "h1": {"prop": "deployment regression", "subject": "deployment/payments",
           "predicate": "rollout_window", "tool": "deploy.history",
           "supports": {"regression": True}, "contradicts": {"regression": False},
           "observed": {"regression": True}},
    "h2": {"prop": "database saturation", "subject": "database/payments",
           "predicate": "saturation", "tool": "metrics.window",
           "supports": {"saturated": True}, "contradicts": {"saturated": False},
           "observed": {"saturated": False}},
    "h3": {"prop": "network degradation", "subject": "network/payments",
           "predicate": "health", "tool": "metrics.window",
           "supports": {"degraded": True}, "contradicts": {"degraded": False},
           "observed": {"degraded": False}},
    "h4": {"prop": "external dependency degradation", "subject": "dependency/stripe",
           "predicate": "latency", "tool": "metrics.window",
           "supports": {"elevated": True}, "contradicts": {"elevated": False},
           "observed": {"elevated": False}},   # NORMAL now — history said elevated
}
E456_VALUES = {v["subject"]: v["observed"] for v in E456.values()}


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
    s = E456[ref]
    return ProposedTest(
        discriminates_hypothesis=ref, tool=s["tool"], subject_ref=s["subject"],
        predicate=s["predicate"], evidence_expected=f"whether {s['prop']} explains latency",
        supports_if="matches", contradicts_if="differs", residual_uncertainty="timing",
        supports_value=s["supports"], contradicts_value=s["contradicts"])


def _test_ran(ref, test_refs):
    from backend.intelligence.application.proposal import test_identity
    s = E456[ref]
    tid = test_identity(discriminates=ref, tool=s["tool"], subject_ref=s["subject"],
                        predicate=s["predicate"])
    return any(tid in r for r in test_refs)


class E456Model:
    """Proposes the differential once, then a candidate test per open untested
    hypothesis. It may REUSE the historical test IDEA (dependency latency) — the
    platform re-governs it; historical authorization is never reused."""
    def propose(self, *, context, investigation, now):
        from backend.contracts.world import HypothesisStatus
        from backend.intelligence.application import InvestigationProposal, ProposedHypothesis
        if not investigation.differential:
            hyps = tuple(ProposedHypothesis(r, E456[r]["prop"], E456[r]["subject"], "unknown")
                         for r in E456)
            cands = tuple(_mk_test(r) for r in E456)
        else:
            hyps = ()
            cands = tuple(_mk_test(h.hypothesis_ref) for h in investigation.differential
                          if h.status is HypothesisStatus.OPEN
                          and not _test_ran(h.hypothesis_ref, investigation.test_refs))
        return InvestigationProposal(provider="scripted", proposal_digest="d",
                                     proposed_hypotheses=hyps, proposed_tests=cands)


def _svc(persistence):
    from backend.intelligence.application import InvestigationService
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    return InvestigationService(repository=SqlInvestigationRepository(persistence.store))


def _repo(persistence):
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    return SqlInvestigationRepository(persistence.store)


def _build_e123(svc):
    """A prior TERMINAL investigation: dependency degradation SUPPORTED, RESOLVED."""
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import HypothesisStatus
    from backend.contracts.intelligence import (
        DifferentialHypothesis, InvestigationConclusion, InvestigationStatus, TemporalFit)
    tenant = TenantRef(tenant_id=TENANT)
    inv = svc.create(tenant=tenant, incident_ref=INCIDENT, policy_ref="pol/1",
                     harness_version="h/1", now=_t(0), investigation_ref="winv-e123")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    for ref, subj, prop, st in (
        ("h4", "dependency/stripe", "external dependency degradation", HypothesisStatus.SUPPORTED),
        ("h2", "database/payments", "database saturation", HypothesisStatus.REFUTED),
        ("h1", "deployment/payments", "deployment regression", HypothesisStatus.OPEN)):
        inv = svc.upsert_hypothesis(investigation=inv, now=_t(2), hypothesis=DifferentialHypothesis(
            hypothesis_ref=ref, subject_ref=subj, proposition=prop, status=st,
            temporal_fit=TemporalFit.CONSISTENT, created_by="scripted:model",
            evidence_for=("wobs-e123",) if st is HypothesisStatus.SUPPORTED else ()))
    inv = svc.link_evidence(investigation=inv, evidence_refs=("wobs-e123",), now=_t(3))
    inv = svc.conclude(investigation=inv, conclusion=InvestigationConclusion.RESOLVED,
                       cause="dependency degradation supported (open: h1)", now=_t(4))
    return inv


def _run_crash_child():
    from backend.contracts.tenant import TenantRef
    from backend.contracts.intelligence import InvestigationStatus
    from backend.intelligence.application import (
        ContextAssembler, EvidenceSelectionPolicy, InvestigationBudget, InvestigationEngine,
        StructuredExperienceRetrieval)
    persistence = _store()
    svc = _svc(persistence)
    tenant = TenantRef(tenant_id=TENANT)

    class LocalEvidence:
        reads = 0
        def acquire(self, *, tenant, request, now):
            from backend.intelligence.application import EvidenceResult
            LocalEvidence.reads += 1
            return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                                  observation_ref=f"wobs-c{LocalEvidence.reads}",
                                  observed_value=E456_VALUES.get(request.subject_ref, {}),
                                  source_ref="connector:kubernetes")

    class LocalWorld:
        def evidence_for(self, *, tenant, subject_ref, predicate, now):
            return {"subject_ref": subject_ref, "predicate": predicate, "value": None,
                    "status": "unknown", "freshness": "unknown", "evidence": []}

    inv = svc.create(tenant=tenant, incident_ref=INCIDENT, policy_ref="pol/1",
                     harness_version="h/1", now=_t(0), investigation_ref="winv-crash")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    eng = InvestigationEngine(
        service=svc, assembler=ContextAssembler(), model_port=E456Model(),
        evidence_port=LocalEvidence(), world_read_port=LocalWorld(),
        policy=EvidenceSelectionPolicy(), harness_version="h/1", available_tools=TOOLS,
        experience_port=StructuredExperienceRetrieval(source=_repo(persistence)))
    eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(5))
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
    from backend.contracts.intelligence import InvestigationStatus
    from backend.platform.context import ExecutionContext
    from backend.intelligence.application import (
        ContextAssembler, EpisodeProjection, EvidenceSelectionPolicy, InvestigationBudget,
        InvestigationEngine, InvestigationNotFound, StructuredExperienceRetrieval, derive_facets)
    from backend.world.application import FactDerivation, ObservationIngestion, ReasoningLedger
    from backend.world.infrastructure import SqlReasoningRepository

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p86 experience", component="experience-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    svc = _svc(runtime.persistence)
    repo = _repo(runtime.persistence)
    obs_repo, fact_repo, query = _world(runtime.persistence)
    reason_repo = SqlReasoningRepository(runtime.persistence.store)

    # ---- prior episode E123 ----
    print("[E] build prior episode E123 (dependency degradation supported)")
    _build_e123(svc)
    e123 = svc.reconstruct(tenant=tenant, investigation_ref="winv-e123")
    episode = EpisodeProjection().project(investigation=e123)
    check("E123 is a terminal, reusable episode", episode is not None and episode.episode_ref == "winv-e123")
    check("E123 quality reflects support without independent verification",
          episode.assurance_status.value == "unassured", episode.assurance_status.value)

    # ---- [P] experience-assisted new investigation E456 ----
    print("[P] experience-assisted investigation E456 (same symptoms)")
    retrieval = StructuredExperienceRetrieval(source=repo)
    e456_facets = derive_facets(e123)  # same incident facets
    matches = retrieval.find_relevant_episodes(tenant=tenant, facets=e456_facets, now=_t(20),
                                               exclude_ref="winv-e456")
    check("retrieval found E123 for the new incident", any(m.episode_ref == "winv-e123" for m in matches))
    m = next(m for m in matches if m.episode_ref == "winv-e123")
    check("match is explainable (service+symptom reasons, no similarity score)",
          any("service=payments-api" in r for r in m.match_reasons)
          and not any("similarity" in str(r).lower() for r in m.match_reasons), m.match_reasons)

    # the context the model sees carries HISTORICAL experience, explicitly labelled
    inv = svc.create(tenant=tenant, incident_ref=INCIDENT, policy_ref="pol/1",
                     harness_version="h/1", now=_t(10), investigation_ref="winv-e456")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(11))
    ctx = ContextAssembler().assemble(
        investigation=inv, world_evidence=(), available_tools=TOOLS, harness_version="h/1",
        now=_t(12), historical_experience=tuple(mm.to_context_dict() for mm in matches))
    exp_section = next(s for s in ctx.sections if s.section_type == "historical_investigation_experience")
    check("context labels experience as HISTORICAL (never world_facts)",
          exp_section.content and exp_section.content[0]["kind"] == "HISTORICAL_INVESTIGATION_EXPERIENCE"
          and "not current world truth" in exp_section.content[0]["caveat"])
    check("no world_facts / authoritative section carries the episode",
          not any(s.section_type in ("world_evidence",) and s.content
                  and isinstance(s.content, list) and any("episode_ref" in str(x) for x in s.content)
                  for s in ctx.sections))

    # run E456 through the engine WITH the experience port; current world governs
    evidence = GovernedEvidence(runtime=runtime, defs=defs, tenant_ctx=tenant_ctx,
                                ingestion=ObservationIngestion(repository=obs_repo),
                                derivation=FactDerivation(repository=fact_repo), value_map=E456_VALUES)
    engine = InvestigationEngine(
        service=svc, assembler=ContextAssembler(), model_port=E456Model(), evidence_port=evidence,
        world_read_port=WorldRead(query), policy=EvidenceSelectionPolicy(), harness_version="h/1",
        available_tools=TOOLS, experience_port=retrieval)
    calls0 = len(adapter.calls)
    t_total = time.perf_counter()
    i = 0
    while not inv.is_terminal and i < 12:
        res = engine.step(investigation=inv, budget=InvestigationBudget(max_steps=10, max_reads=12),
                          now=_t(12 + i))
        inv = res.investigation
        i += 1
    total_ms = (time.perf_counter() - t_total) * 1000
    by = {h.hypothesis_ref: h.status for h in inv.differential}
    check("H4 (dependency) NOT auto-accepted from history — current world REFUTES it",
          by.get("h4") is HypothesisStatus.REFUTED, by)
    check("E456 reaches a DIFFERENT current cause than E123 (deployment, not dependency)",
          by.get("h1") is HypothesisStatus.SUPPORTED, by)
    check("E456 required a FRESH governed read (historical authorization never reused)",
          len(adapter.calls) - calls0 >= 1, f"provider_calls={len(adapter.calls) - calls0}")
    check("experience relevant but not truth: E123.h4=supported, E456.h4=refuted",
          "supported" == next(h.status for h in episode.hypotheses if h.hypothesis_ref == "h4")
          and by.get("h4") is HypothesisStatus.REFUTED)

    # ---- [T] calibration substrate: EXPERIENCE_USE durable ----
    print("[T] capture calibration substrate (EXPERIENCE_USE)")
    ledger = ReasoningLedger(repository=reason_repo)
    ledger.record_experience_use(
        tenant=tenant, subject_ref=INCIDENT, investigation_ref="winv-e456", episode_ref="winv-e123",
        document={"episode_ref": "winv-e123", "match_reasons": list(m.match_reasons),
                  "assurance_status": m.assurance_status, "quality": m.quality,
                  "current_outcome_hint": "refuted_h4"}, recorded_at=_t(30))
    exp_rows = [r for r in reason_repo.list_for_subject(tenant_id=TENANT, subject_ref=INCIDENT)
                if r.kind.value == "experience_use"]
    check("EXPERIENCE_USE record durable in cw_reasoning (no new table)", len(exp_rows) == 1)
    check("EXPERIENCE_USE carries references only (no numeric confidence/score)",
          exp_rows and not any("confidence" in k or "score" in k for k in exp_rows[0].record))

    # ---- [K] temporal safety ----
    print("[K] temporal safety (as-known reconstruction)")
    # E123 completed at 10:04; an as-known cut at 10:02 must not show its conclusion
    early = svc.reconstruct_as_known(tenant=tenant, investigation_ref="winv-e123", known_at=_t(2))
    check("as-known-10:02 view of E123 has no terminal conclusion (no future leak)",
          early.conclusion is None and early.status is InvestigationStatus.INVESTIGATING,
          f"{early.status.value}/{early.conclusion}")
    check("retrieval excludes an episode completed after the as-known cutoff",
          retrieval.find_relevant_episodes(tenant=tenant, facets=e456_facets, now=_t(20),
                                           exclude_ref="winv-e456", as_known_at=_t(3)) == ())

    # ---- [R] crash: historical experience immutable, E456 resumes ----
    print("[R] crash + recovery")
    import subprocess
    e123_before = svc.reconstruct(tenant=tenant, investigation_ref="winv-e123").to_dict()
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase86_experience_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    succ = _svc(_store())
    e123_after = succ.reconstruct(tenant=tenant, investigation_ref="winv-e123").to_dict()
    check("historical episode E123 is immutable across the crash", e123_before == e123_after)
    resumed = succ.reconstruct(tenant=tenant, investigation_ref="winv-crash")
    check("crashed investigation reconstructs (not fabricated)", resumed.status is not None)

    # ---- [S] replay inert ----
    print("[S] replay inert")
    calls_b, reason_b = len(adapter.calls), reason_repo.count_all()
    fact_b = fact_repo.count_all()
    for _ in range(5):
        svc.reconstruct(tenant=tenant, investigation_ref="winv-e123")
        retrieval.find_relevant_episodes(tenant=tenant, facets=e456_facets, now=_t(40),
                                         exclude_ref="winv-e456")
    check("replay/retrieval: 0 provider calls, 0 world mutations, 0 new reasoning",
          len(adapter.calls) == calls_b and fact_repo.count_all() == fact_b
          and reason_repo.count_all() == reason_b)

    # ---- [J] tenant isolation ----
    print("[J] tenant isolation (fail closed)")
    check("cross-tenant retrieval returns no episodes",
          retrieval.find_relevant_episodes(tenant=other, facets=e456_facets, now=_t(40)) == ())
    check("cross-tenant reconstruct fails closed",
          _raises(lambda: succ.reconstruct(tenant=other, investigation_ref="winv-e123"),
                  InvestigationNotFound))

    # ---- [V] performance ----
    print("[V] performance (measured)")
    t_r = time.perf_counter()
    retrieval.find_relevant_episodes(tenant=tenant, facets=e456_facets, now=_t(40),
                                     exclude_ref="winv-e456")
    retrieval_ms = (time.perf_counter() - t_r) * 1000
    t_a = time.perf_counter()
    ContextAssembler().assemble(investigation=inv, world_evidence=(), available_tools=TOOLS,
                                harness_version="h/1", now=_t(40),
                                historical_experience=tuple(mm.to_context_dict() for mm in matches))
    assembly_ms = (time.perf_counter() - t_a) * 1000
    REPORT["performance_ms"] = {"episode_retrieval": round(retrieval_ms, 2),
                                "context_assembly": round(assembly_ms, 2),
                                "total_e456_investigation": round(total_ms, 1)}
    check("performance measured", retrieval_ms >= 0 and assembly_ms >= 0)

    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"investigation_events": repo.count_all(), "reasoning_records": reason_repo.count_all(),
                        "provider_calls": len(adapter.calls)}
    REPORT["e456_differential"] = {k: v.value for k, v in by.items()}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "experience memory verified" if ok else "a check failed")


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
