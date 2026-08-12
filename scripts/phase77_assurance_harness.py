"""Phase 7.7 real-Postgres evidence: independent assurance verification.

Run:  python -m scripts.phase77_assurance_harness
      python -m scripts.phase77_assurance_harness --crash-child   (internal)

Proves against a fresh cortex_p77: a governed READ -> Observation -> Fact ->
independent verification that mints a durable WorldVerification (cw_verification);
SUPPORTED only when independent world evidence matches the claim; UNKNOWN / STALE
/ CONFLICTED / missing evidence -> INSUFFICIENT (never success); self-verification
refused; unknown-lineage cannot prove independence; tenant fail-closed;
idempotency; verification persisted + reconstructable; replay inert; crash
os._exit(9) + deterministic reconstruction. Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
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
K8S = "connector:kubernetes"
MODEL_PATH = "model:gpt/turn-1"
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


def _read(subject, value, observed_at, source_ref=K8S, *, predicate="spec.replicas"):
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
        LineageRule(origin_id="controlled", relation=LineageRelation.DIRECT,
                    source_ref="connector:controlled"),
    ))


def _stack(persistence, *, policy=None):
    from backend.assurance.application import AssurancePolicy, AssuranceVerifier
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.world.application import (
        FactDerivation, FreshnessPolicy, FreshnessRule, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository
    obs_repo = SqlObservationRepository(persistence.store)
    fact_repo = SqlFactRepository(persistence.store)
    verif_repo = SqlVerificationRepository(persistence.store)
    freshness = FreshnessPolicy(rules=(
        FreshnessRule(horizon_seconds=600, predicate="spec.replicas"),
        FreshnessRule(horizon_seconds=600, predicate="state")))
    query = WorldQuery(facts=fact_repo, observations=obs_repo, freshness_policy=freshness)
    verifier = AssuranceVerifier(query=query, repository=verif_repo,
                                 policy=policy or AssurancePolicy.default(), lineage_policy=_lineage())
    return obs_repo, fact_repo, verif_repo, ObservationIngestion(repository=obs_repo), \
        FactDerivation(repository=fact_repo), query, verifier


def _procedure(subject, expected, at_valid=None, predicate="spec.replicas"):
    from backend.assurance.application import VerificationProcedure, VerificationProcedureKind
    return VerificationProcedure(kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
                                 subject_ref=subject, predicate=predicate,
                                 expected=expected, at_valid=at_valid)


def _run_crash_child():
    from backend.contracts.tenant import TenantRef
    persistence = _store()
    _, _, _, ingestion, derivation, _, verifier = _stack(persistence)
    tenant = TenantRef(tenant_id=TENANT)
    obs, _ = ingestion.ingest(tenant=tenant, recorded_at=_utc(12, 1),
                              read=_read("deployment/crash", {"replicas": 9}, _utc(12, 0)))
    derivation.derive(tenant=tenant, observation=obs, recorded_at=_utc(12, 1))
    res = verifier.verify(tenant=tenant, procedure=_procedure("deployment/crash", {"replicas": 9}),
                          producer_reasoning_path=MODEL_PATH, verified_at=_utc(12, 2))
    marker = os.getenv("CORTEX_P77_MARKER")
    if marker and res.newly_recorded:
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump({"verification_id": res.verification.record_id,
                       "verdict": res.verdict.value}, fh)
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
    from backend.assurance.application import AssurancePolicy, AssuranceRefused, AssuranceVerifier
    from backend.contracts.tenant import TenantRef
    from backend.contracts.verification import Verdict, VerifierIdentity
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p77 harness", component="assurance-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    obs_repo, fact_repo, verif_repo, ingestion, derivation, query, verifier = _stack(runtime.persistence)
    tenant, other = TenantRef(tenant_id=TENANT), TenantRef(tenant_id="other")

    def idr(read, *, at):
        obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=at)
        derivation.derive(tenant=tenant, observation=obs, recorded_at=at)
        return obs

    def verify(subject, expected, *, now=_utc(10, 5), at_valid=None, who=tenant, v=verifier):
        return v.verify(tenant=who, procedure=_procedure(subject, expected, at_valid),
                        producer_reasoning_path=MODEL_PATH, verified_at=now)

    # ---- Q: governed READ -> Observation -> Fact -> Verification ----
    print("[Q] governed READ -> Observation -> Fact -> independent Verification")
    exec_id, node, state, evidence = _governed_read_evidence(runtime, tenant_ctx, defs)
    check("governed READ succeeded", state == "succeeded", state)
    read = _read_from_governed_outcome(runtime, tenant_ctx, exec_id, node, evidence)
    obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=datetime.now(timezone.utc))
    derivation.derive(tenant=tenant, observation=obs, recorded_at=datetime.now(timezone.utc))
    provider_before = len(adapter.calls)
    world_val = query.current(tenant=tenant, subject_ref="widget:w-1", predicate="state",
                              now=datetime.now(timezone.utc)).effective_value
    res = verifier.verify(tenant=tenant, procedure=_procedure("widget:w-1", world_val, predicate="state"),
                          producer_reasoning_path=MODEL_PATH, verified_at=datetime.now(timezone.utc))
    check("verification SUPPORTED against independent evidence", res.verdict is Verdict.SUPPORTED)
    check("verification contacted no provider", len(adapter.calls) == provider_before)
    check("verifier is deterministic (no model)", res.verification.verifier.model_identifier is None)
    check("verification persisted to cw_verification", verif_repo.count_all() >= 1)

    # ---- SUPPORTED vs UNSUPPORTED (claim compared to world, never model) ----
    print("[claim] SUPPORTED matches, UNSUPPORTED contradicts")
    idr(_read("deployment/a", {"replicas": 5}, _utc(10, 0)), at=_utc(10, 1))
    check("world matches claim -> SUPPORTED", verify("deployment/a", {"replicas": 5}).verdict is Verdict.SUPPORTED)
    check("world contradicts claim -> UNSUPPORTED (not FALSE)",
          verify("deployment/a", {"replicas": 3}).verdict is Verdict.UNSUPPORTED)

    # ---- failure semantics: missing / unknown / stale / conflicted -> INSUFFICIENT ----
    print("[fail] missing/unknown/stale/conflicted != SUPPORTED")
    check("missing evidence -> INSUFFICIENT",
          verify("deployment/none", {"replicas": 5}).verdict is Verdict.INSUFFICIENT_EVIDENCE)
    check("UNKNOWN world (valid time before obs) -> INSUFFICIENT",
          verify("deployment/a", {"replicas": 5}, at_valid=_utc(9, 0)).verdict
          is Verdict.INSUFFICIENT_EVIDENCE)
    check("STALE evidence -> INSUFFICIENT",
          verify("deployment/a", {"replicas": 5}, now=_utc(10, 40)).verdict
          is Verdict.INSUFFICIENT_EVIDENCE)
    # conflict
    from backend.contracts.world import SourceAuthority
    from backend.world.application import AuthorityPolicy, AuthorityRule, WorldQuery
    conf_query = WorldQuery(facts=fact_repo, observations=obs_repo,
                            authority_policy=AuthorityPolicy(rules=(AuthorityRule(
                                tier=SourceAuthority.AUTHORITATIVE, source_kind="connector"),)))
    conf_verifier = AssuranceVerifier(query=conf_query, repository=verif_repo)
    idr(_read("deployment/conf", {"replicas": 5}, _utc(10, 0), "connector:a"), at=_utc(10, 1))
    idr(_read("deployment/conf", {"replicas": 3}, _utc(10, 0), "connector:b"), at=_utc(10, 2))
    check("CONFLICTED evidence -> INSUFFICIENT",
          verify("deployment/conf", {"replicas": 5}, now=_utc(10, 10), v=conf_verifier).verdict
          is Verdict.INSUFFICIENT_EVIDENCE)

    # ---- self-verification refused ----
    print("[independence] self-verification refused")
    dependent = VerifierIdentity(verifier_id="model", reasoning_path_id=MODEL_PATH, model_identifier="gpt")
    try:
        verifier.verify(tenant=tenant, procedure=_procedure("deployment/a", {"replicas": 5}),
                        producer_reasoning_path=MODEL_PATH, verified_at=_utc(10, 5), verifier=dependent)
        check("self-verification refused", False)
    except AssuranceRefused:
        check("self-verification refused", True)

    # ---- unknown lineage cannot prove independence ----
    print("[lineage] unknown lineage -> cannot prove independence")
    strict = AssuranceVerifier(query=query, repository=verif_repo,
                               policy=AssurancePolicy(require_known_lineage=True), lineage_policy=_lineage())
    idr(_read("deployment/unk", {"replicas": 7}, _utc(10, 0), "connector:mystery"), at=_utc(10, 1))
    check("unknown-lineage source -> INSUFFICIENT under require_known_lineage",
          strict.verify(tenant=tenant, procedure=_procedure("deployment/unk", {"replicas": 7}),
                        producer_reasoning_path=MODEL_PATH, verified_at=_utc(10, 5)).verdict
          is Verdict.INSUFFICIENT_EVIDENCE)

    # ---- tenant fail closed ----
    print("[tenant] cross-tenant fail closed")
    check("cross-tenant verification -> INSUFFICIENT",
          verify("deployment/a", {"replicas": 5}, who=other).verdict is Verdict.INSUFFICIENT_EVIDENCE)

    # ---- idempotency + reconstructable ----
    print("[idempotency] re-verify dedupes; verification reconstructable")
    # a fresh verified_at (10:07, unique and still covering the 10:00 obs) so this
    # verification is genuinely new (persisted)
    r1 = verify("deployment/a", {"replicas": 5}, now=_utc(10, 7))
    check("new verification is recorded", r1.newly_recorded is True)
    check("new verification is SUPPORTED", r1.verdict is Verdict.SUPPORTED)
    got = verif_repo.get(tenant_id=TENANT, verification_id=r1.verification.record_id)
    check("verification reconstructable from cw_verification", got is not None)
    check("reconstructed verdict intact", got is not None and got.verdict is Verdict.SUPPORTED)
    # deterministic identity uses verified_at; re-run with the SAME verified_at dedupes:
    same = verifier.verify(tenant=tenant, procedure=_procedure("deployment/a", {"replicas": 5}),
                           producer_reasoning_path=MODEL_PATH, verified_at=_utc(10, 7))
    check("identical verification (same verified_at) dedupes", same.newly_recorded is False)
    check("reconstructed cross-tenant fail-closed",
          verif_repo.get(tenant_id="other", verification_id=r1.verification.record_id) is None)

    # ---- replay inert ----
    print("[replay] inert")
    from backend.contexts.execution.application.commands import ReplayExecution
    facts_before, verif_before, prov_before = fact_repo.count_all(), verif_repo.count_all(), len(adapter.calls)
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    check("replay zero new facts", fact_repo.count_all() == facts_before)
    check("replay zero new verifications", verif_repo.count_all() == verif_before)
    check("replay zero provider reads", len(adapter.calls) == prov_before)

    # ---- crash / recovery ----
    print("[crash] real os._exit(9) + reconstruction")
    import subprocess
    import tempfile
    marker = os.path.join(tempfile.gettempdir(), f"p77_{os.getpid()}.json")
    child_env = dict(os.environ)
    child_env["CORTEX_P77_MARKER"] = marker
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase77_assurance_harness", "--crash-child"],
        env=child_env, cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    crashed = {}
    if os.path.exists(marker):
        with open(marker, encoding="utf-8") as fh:
            crashed = json.load(fh)
        os.remove(marker)
    check("child minted a verification before dying", bool(crashed.get("verification_id")))
    if crashed.get("verification_id"):
        succ_repo = __import__("backend.assurance.infrastructure", fromlist=["SqlVerificationRepository"]) \
            .SqlVerificationRepository(_store().store)
        rec = succ_repo.get(tenant_id=TENANT, verification_id=crashed["verification_id"])
        check("verification survived the crash intact", rec is not None)
        check("crashed verification cross-tenant fail-closed",
              succ_repo.get(tenant_id="other", verification_id=crashed["verification_id"]) is None)

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    REPORT["counts"] = {"facts": fact_repo.count_all(), "observations": obs_repo.count_all(),
                        "verifications": verif_repo.count_all(), "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "independent assurance verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
