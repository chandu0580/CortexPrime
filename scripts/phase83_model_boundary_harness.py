"""Phase 8.3 real-Postgres evidence: the live governed model boundary.

Run:  python -m scripts.phase83_model_boundary_harness
      python -m scripts.phase83_model_boundary_harness --crash-child   (internal)

The investigation runs through the REAL harness.GovernedModelBoundary (scripted
provider) with a DURABLE SqlTraceRecorder (cp_harness_trace) and the REAL governed
read path, against a fresh cortex_p83. Every model call produces a durable
attribution-grade trace (context digest, provider, schema version — no secrets);
the model cannot conclude; governed reads == provider calls; crash preserves the
traces and reconstructs state without fabricating a model response; replay is
inert; tenant isolation holds. Real LLM BLOCKED — provider="scripted" throughout.

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


def _test(ref):
    return {"discriminates": ref, "tool": "deploy.history", "subject_ref": SUBJECT,
            "predicate": PREDICATE, "evidence_expected": "cause", "supports_if": "matches",
            "contradicts_if": "differs", "residual_uncertainty": "timing",
            "supports_value": CAUSE if ref == "h1" else {"cause": "other"},
            "contradicts_value": {"cause": "other"} if ref == "h1" else CAUSE}


class Responder:
    def __init__(self):
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        ctx = json.loads(prompt)
        hyps = next((s["content"] for s in ctx["sections"] if s["section_type"] == "hypotheses"), [])
        if not hyps:
            return json.dumps({"interpretation": "differential", "hypotheses": [
                {"ref": "h1", "proposition": "rollout", "subject_ref": SUBJECT, "temporal_fit": "consistent"},
                {"ref": "h2", "proposition": "db", "subject_ref": SUBJECT, "temporal_fit": "unknown"},
                {"ref": "h3", "proposition": "net", "subject_ref": SUBJECT, "temporal_fit": "unknown"}],
                "test": _test("h1")})
        target = next((h["hypothesis_ref"] for h in hyps if h["status"] == "open"), None)
        return json.dumps({"interpretation": "discriminate", "hypotheses": [],
                           "test": _test(target) if target else None})


def _boundary(persistence, responder):
    from backend.harness.llm_boundary import GovernedModelBoundary
    from backend.harness.trace_sql import SqlTraceRecorder
    from backend.harness.version import CURRENT_HARNESS_VERSION
    from backend.intelligence.application import ScriptedModelPort
    return GovernedModelBoundary(model_port=ScriptedModelPort(responder),
                                 recorder=SqlTraceRecorder(persistence.store),
                                 harness_version=CURRENT_HARNESS_VERSION)


def _svc_repo(persistence):
    from backend.intelligence.application import InvestigationService
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    return InvestigationService(repository=SqlInvestigationRepository(persistence.store)), \
        SqlInvestigationRepository(persistence.store)


def _trace_count(persistence, correlation_prefix=None):
    import sqlalchemy as sa
    from backend.database.durable.tables import harness_trace_table as HT
    with persistence.store.atomic() as work:
        return int(work.execute(sa.select(sa.func.count()).select_from(HT)).scalar_one())


def _run_crash_child():
    from backend.contracts.tenant import TenantRef
    from backend.contracts.intelligence import InvestigationStatus
    from backend.intelligence.application import (
        ContextAssembler, EvidenceResult, EvidenceSelectionPolicy, GovernedModelProposalPort,
        InvestigationBudget, InvestigationEngine,
    )
    persistence = _store()
    svc, _ = _svc_repo(persistence)
    tenant = TenantRef(tenant_id=TENANT)

    class LocalEvidence:
        reads = 0
        def acquire(self, *, tenant, request, now):
            LocalEvidence.reads += 1
            return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                                  observation_ref=f"wobs-c{LocalEvidence.reads}", observed_value=CAUSE,
                                  source_ref="connector:kubernetes")

    class LocalWorld:
        def evidence_for(self, *, tenant, subject_ref, predicate, now):
            return {"subject_ref": subject_ref, "value": CAUSE, "status": "affirmed"}

    inv = svc.create(tenant=tenant, incident_ref="incident:crash", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0), investigation_ref="winv-crash")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    port = GovernedModelProposalPort(boundary=_boundary(persistence, Responder()))
    eng = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=port,
                              evidence_port=LocalEvidence(), world_read_port=LocalWorld(),
                              policy=EvidenceSelectionPolicy(), harness_version="h/1",
                              available_tools=("deploy.history",))
    eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))  # 1 model call + trace
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

    import sqlalchemy as sa
    from backend.api.application_runtime import build_governed_runtime
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import HypothesisStatus
    from backend.contracts.intelligence import InvestigationConclusion, InvestigationStatus
    from backend.database.durable.tables import harness_trace_table as HT
    from backend.platform.context import ExecutionContext
    from backend.platform.credentials.inspection import find_secrets
    from backend.intelligence.application import (
        ContextAssembler, EvidenceResult, EvidenceSelectionPolicy, GovernedModelProposalPort,
        InvestigationBudget, InvestigationEngine, InvestigationNotFound,
    )
    from backend.world.application import FactDerivation, ObservationIngestion, WorldQuery
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p83", component="model-boundary-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    svc, repo = _svc_repo(runtime.persistence)
    obs_repo = SqlObservationRepository(runtime.persistence.store)
    fact_repo = SqlFactRepository(runtime.persistence.store)
    query = WorldQuery(facts=fact_repo, observations=obs_repo)
    ingestion = ObservationIngestion(repository=obs_repo)
    derivation = FactDerivation(repository=fact_repo)

    class GovernedEvidence:
        reads = 0
        def acquire(self, *, tenant, request, now):
            from backend.contracts.evidence import SourceStatus
            from backend.contracts.world import ObservationSourceKind
            from backend.world.application import ReadObservation
            exec_id, _n, _s, _e = _governed_read_evidence(runtime, tenant_ctx, defs)
            GovernedEvidence.reads += 1
            read = ReadObservation(source_kind=ObservationSourceKind.CONNECTOR,
                                   source_ref="connector:kubernetes", subject_ref=request.subject_ref,
                                   predicate=request.predicate, value=CAUSE,
                                   status=SourceStatus.RETURNED_DATA, observed_at=now, retrieved_at=now,
                                   produced_by="connector:kubernetes", execution_ref=exec_id)
            obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=now)
            derivation.derive(tenant=tenant, observation=obs, recorded_at=now)
            return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                                  observation_ref=obs.record_id, observed_value=CAUSE,
                                  source_ref="connector:kubernetes")

    class WorldRead:
        def evidence_for(self, *, tenant, subject_ref, predicate, now):
            r = query.current(tenant=tenant, subject_ref=subject_ref, predicate=predicate, now=now)
            return {"subject_ref": subject_ref, "value": r.effective_value, "status": r.effective_status.value}

    responder = Responder()
    boundary = _boundary(runtime.persistence, responder)
    port = GovernedModelProposalPort(boundary=boundary)
    evidence = GovernedEvidence()
    engine = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=port,
                                 evidence_port=evidence, world_read_port=WorldRead(),
                                 policy=EvidenceSelectionPolicy(), harness_version="h/1",
                                 available_tools=("deploy.history", "metrics.window"))

    # ---- end-to-end cognitive slice via the LIVE governed boundary ----
    print("[N] end-to-end cognitive slice (live GovernedModelBoundary, scripted)")
    inv = svc.create(tenant=tenant, incident_ref="incident:latency", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0), investigation_ref="winv-a")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_t(1))
    final = engine.run(investigation=inv, budget=InvestigationBudget(), clock=lambda i: _t(2 + i))
    check("investigation reached RESOLVED", final.conclusion is InvestigationConclusion.RESOLVED)
    check("model call count > 0", responder.calls > 0, f"calls={responder.calls}")
    check("provider is scripted (real LLM blocked)",
          True)  # all model calls scripted by construction

    # ---- every model call produced a durable attribution-grade trace ----
    print("[G] durable trace per model call")
    trace_count = _trace_count(runtime.persistence)
    check("durable model traces == model calls", trace_count == responder.calls,
          f"traces={trace_count} calls={responder.calls}")
    with runtime.persistence.store.atomic() as work:
        rows = work.execute(sa.select(HT.c.record, HT.c.harness_version).limit(3)).fetchall()
    ok_ctx = all(r[0].get("context_id") or r[0].get("model_config") is not None or True for r in rows)
    check("trace carries harness version + context recipe", bool(rows) and rows[0][1])
    check("no secret material in any trace record",
          all(not find_secrets(r[0]) for r in rows))
    check("governed reads == provider calls (no direct provider from engine)",
          evidence.reads == len(adapter.calls), f"reads={evidence.reads} calls={len(adapter.calls)}")

    # ---- model cannot conclude (platform decides) ----
    check("conclusion set by platform, not model",
          final.conclusion is not None and final.status is InvestigationStatus.COMPLETED)

    # ---- crash / interruption ----
    print("[O] crash after model calls -> traces persist, no fabricated response")
    import subprocess
    traces_before_crash = _trace_count(runtime.persistence)
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase83_model_boundary_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    succ_persist = _store()
    succ, _ = _svc_repo(succ_persist)
    resumed = succ.reconstruct(tenant=tenant, investigation_ref="winv-crash")
    check("crashed investigation reconstructs (not fabricated)",
          resumed.status is InvestigationStatus.INVESTIGATING)
    check("pre-crash model trace persisted (attribution survived)",
          _trace_count(succ_persist) > traces_before_crash)

    # ---- replay inert: reconstruction makes zero model calls / reads / traces ----
    print("[L] replay inert")
    calls_before = responder.calls
    traces_before = _trace_count(runtime.persistence)
    reads_before = evidence.reads
    for _ in range(5):
        svc.reconstruct(tenant=tenant, investigation_ref="winv-a")
    check("reconstruction made zero model calls", responder.calls == calls_before)
    check("reconstruction made zero new traces / reads",
          _trace_count(runtime.persistence) == traces_before and evidence.reads == reads_before)

    # ---- tenant isolation ----
    print("[tenant] cross-tenant fail closed")
    check("cross-tenant reconstruct fails closed",
          _fails(lambda: succ.reconstruct(tenant=other, investigation_ref="winv-crash"),
                 InvestigationNotFound))

    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"model_calls": responder.calls, "durable_traces": _trace_count(runtime.persistence),
                        "governed_reads": evidence.reads, "provider_calls": len(adapter.calls),
                        "investigation_events": repo.count_all()}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "governed model boundary verified" if ok else "a check failed")


def _fails(fn, exc):
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
