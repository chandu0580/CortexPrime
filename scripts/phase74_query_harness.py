"""Phase 7.4 real-Postgres evidence: World Query, freshness, authority.

Run:  python -m scripts.phase74_query_harness
      python -m scripts.phase74_query_harness --crash-child   (internal)

The complete read path (Part Q), one governed provider call, none from the query:
  governed widget.get READ -> Observation -> Fact -> WorldQuery -> structured
  result. Then the load-bearing bitemporal example queried, authority
  (recency != authority), same-instant CONFLICT, freshness under an injected
  clock (STALE != FALSE), evidence, tenant fail-closed, replay inertness,
  crash/recovery, and query counts.

Exit codes: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

from scripts.phase72_observation_harness import (
    _governed_read_evidence, _read_from_governed_outcome, _store,
)
from scripts.phase62_recovery_harness import TENANT, _commission, _tenant_ctx

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
K8S = "connector:kubernetes"
CACHE = "connector:stale-cache"


def check(name: str, ok: bool, detail: str = "") -> bool:
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": detail[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail[:160]}" if detail else ""))
    return bool(ok)


def bail(code: int, why: str) -> None:
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _utc(h, m):
    return datetime(2026, 8, 12, h, m, tzinfo=timezone.utc)


def _read(subject, predicate, value, observed_at, *, source_ref=K8S, exec_ref="ex-scn"):
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.world.application import ReadObservation
    return ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref=source_ref,
        subject_ref=subject, predicate=predicate, value=value,
        status=SourceStatus.RETURNED_DATA, observed_at=observed_at,
        retrieved_at=observed_at + timedelta(minutes=4), produced_by=source_ref,
        execution_ref=exec_ref, trace_ref="corr-scn")


def _policies():
    from backend.contracts.world import SourceAuthority
    from backend.world.application import (
        AuthorityPolicy, AuthorityRule, FreshnessPolicy, FreshnessRule,
    )
    freshness = FreshnessPolicy(rules=(
        FreshnessRule(horizon_seconds=600, predicate="spec.replicas", name="replicas-10m"),
        FreshnessRule(horizon_seconds=600, predicate="state", name="widget-10m"),
    ), name="p74-freshness")
    authority = AuthorityPolicy(rules=(
        AuthorityRule(tier=SourceAuthority.AUTHORITATIVE, source_ref=K8S),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref=CACHE),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref="connector:controlled"),
    ), name="p74-authority")
    return freshness, authority


def _run_crash_child() -> None:
    from backend.contracts.tenant import TenantRef
    from backend.world.application import FactDerivation, ObservationIngestion
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository
    persistence = _store()
    tenant = TenantRef(tenant_id=TENANT)
    ingestion = ObservationIngestion(repository=SqlObservationRepository(persistence.store))
    derivation = FactDerivation(repository=SqlFactRepository(persistence.store))
    obs, _ = ingestion.ingest(tenant=tenant, recorded_at=_utc(12, 1),
                              read=_read("deployment/crash", "spec.replicas",
                                         {"replicas": 9}, _utc(12, 0), exec_ref="ex-crash"))
    derivation.derive(tenant=tenant, observation=obs, recorded_at=_utc(12, 1))
    sys.stdout.flush()
    os._exit(9)


def main() -> None:  # noqa: PLR0915
    if "--crash-child" in sys.argv:
        _run_crash_child()
        return
    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL not set")
    os.environ.setdefault("CORTEX_CONTROLLED_PROVIDER", "1")
    os.environ.setdefault(
        "CORTEX_CONNECTOR_FACTORIES",
        "backend.api.controlled_provider_factory:controlled_extension")

    from backend.api.application_runtime import build_governed_runtime
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import EpistemicStatus
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import (
        AuthorityStatus, FactDerivation, FreshnessState, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p74 harness", component="world-query-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]

    obs_repo = SqlObservationRepository(runtime.persistence.store)
    fact_repo = SqlFactRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=obs_repo)
    derivation = FactDerivation(repository=fact_repo)
    freshness, authority = _policies()
    wq = WorldQuery(facts=fact_repo, observations=obs_repo,
                    freshness_policy=freshness, authority_policy=authority)
    tenant = TenantRef(tenant_id=TENANT)
    other = TenantRef(tenant_id="other")

    def ingest_derive(read, *, obs_recorded, knowledge_at):
        obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=obs_recorded)
        derivation.derive(tenant=tenant, observation=obs, recorded_at=knowledge_at)
        return obs

    # ------------------------------------------------------------------
    # Part Q — governed READ -> Observation -> Fact -> World Query
    # ------------------------------------------------------------------
    print("[Q] governed READ -> Observation -> Fact -> World Query")
    exec_id, node, state, evidence = _governed_read_evidence(runtime, tenant_ctx, defs)
    check("governed widget.get READ succeeded", state == "succeeded", str(state))
    read = _read_from_governed_outcome(runtime, tenant_ctx, exec_id, node, evidence)
    obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=datetime.now(timezone.utc))
    derivation.derive(tenant=tenant, observation=obs, recorded_at=datetime.now(timezone.utc))
    provider_before = len(adapter.calls)
    q = wq.current(tenant=tenant, subject_ref="widget:w-1", predicate="state",
                   now=datetime.now(timezone.utc))
    check("world query returned a fact for the governed observation",
          q.effective_status is EpistemicStatus.AFFIRMED)
    check("world query contacted no provider", len(adapter.calls) == provider_before)
    check("query result is explainable (to_dict has all axes)",
          all(k in q.to_dict() for k in
              ("what", "status", "why", "fresh", "conflicted", "evidence", "tenant")))
    check("evidence references the governed execution",
          any(e.execution_ref == exec_id for e in q.evidence))

    # ------------------------------------------------------------------
    # Part J — load-bearing bitemporal example, queried
    # ------------------------------------------------------------------
    print("[J] point-in-time correctness through the query")
    ingest_derive(_read("deployment/payments", "spec.replicas", {"replicas": 5}, _utc(10, 0)),
                  obs_recorded=_utc(10, 4), knowledge_at=_utc(10, 4))
    ingest_derive(_read("deployment/payments", "spec.replicas", {"replicas": 3}, _utc(9, 58)),
                  obs_recorded=_utc(10, 10), knowledge_at=_utc(10, 10))
    S, P = "deployment/payments", "spec.replicas"
    check("world @ 09:59 -> 3", wq.as_of_valid(tenant=tenant, subject_ref=S, predicate=P,
          at_valid=_utc(9, 59), now=_utc(10, 20)).temporal.value == {"replicas": 3})
    check("world @ 10:02 -> 5", wq.as_of_valid(tenant=tenant, subject_ref=S, predicate=P,
          at_valid=_utc(10, 2), now=_utc(10, 20)).temporal.value == {"replicas": 5})
    check("known @ 10:00 -> UNKNOWN", wq.as_known(tenant=tenant, subject_ref=S, predicate=P,
          known_at=_utc(10, 0)).temporal.status is EpistemicStatus.UNKNOWN)
    check("known @ 10:05 -> 5", wq.as_known(tenant=tenant, subject_ref=S, predicate=P,
          known_at=_utc(10, 5)).temporal.value == {"replicas": 5})
    check("current -> 5", wq.current(tenant=tenant, subject_ref=S, predicate=P,
          now=_utc(10, 20)).temporal.value == {"replicas": 5})
    check("history -> both versions", [e.value for e in wq.history(
          tenant=tenant, subject_ref=S, predicate=P)] == [{"replicas": 5}, {"replicas": 3}])

    # ------------------------------------------------------------------
    # Part F — recency != authority
    # ------------------------------------------------------------------
    print("[F] recency != authority")
    ingest_derive(_read("deployment/api", "spec.replicas", {"replicas": 5}, _utc(10, 0),
                        source_ref=K8S), obs_recorded=_utc(10, 1), knowledge_at=_utc(10, 1))
    ingest_derive(_read("deployment/api", "spec.replicas", {"replicas": 3}, _utc(10, 5),
                        source_ref=CACHE), obs_recorded=_utc(10, 6), knowledge_at=_utc(10, 6))
    aq = wq.current(tenant=tenant, subject_ref="deployment/api", predicate="spec.replicas",
                    now=_utc(10, 10))
    check("temporal projection would pick the newer cache value",
          aq.temporal.value == {"replicas": 3})
    check("authority resolves to the authoritative K8s value (recency overridden)",
          aq.authority.status is AuthorityStatus.RESOLVED
          and aq.authority.value == {"replicas": 5} and aq.effective_value == {"replicas": 5})
    check("the cache value is preserved as a lower-tier alternative",
          any(a.value == {"replicas": 3} and a.source_ref == CACHE
              for a in aq.authority.alternatives))

    # ------------------------------------------------------------------
    # Part K — same valid instant, different value -> CONFLICTED, both kept
    # ------------------------------------------------------------------
    print("[K] conflict preserved (never latest/confidence wins)")
    ingest_derive(_read("deployment/web", "spec.replicas", {"replicas": 5}, _utc(11, 0),
                        source_ref="connector:a"), obs_recorded=_utc(11, 1), knowledge_at=_utc(11, 1))
    ingest_derive(_read("deployment/web", "spec.replicas", {"replicas": 3}, _utc(11, 0),
                        source_ref="connector:b"), obs_recorded=_utc(11, 5), knowledge_at=_utc(11, 5))
    cq = wq.current(tenant=tenant, subject_ref="deployment/web", predicate="spec.replicas",
                    now=_utc(11, 30))
    check("same-instant disagreement is CONFLICTED",
          cq.effective_status is EpistemicStatus.CONFLICTED)
    check("both competing values are preserved",
          {a.value["replicas"] for a in cq.authority.alternatives} == {5, 3})

    # ------------------------------------------------------------------
    # Part L — freshness under an injected clock (STALE != FALSE)
    # ------------------------------------------------------------------
    print("[L] freshness (deterministic clock, STALE != FALSE)")
    fq_fresh = wq.current(tenant=tenant, subject_ref="deployment/api",
                          predicate="spec.replicas", now=_utc(10, 3))  # 3m after K8s obs
    fq_stale = wq.current(tenant=tenant, subject_ref="deployment/api",
                          predicate="spec.replicas", now=_utc(10, 30))  # 30m after
    check("fresh within the explicit horizon", fq_fresh.freshness.state is FreshnessState.FRESH)
    check("stale beyond the explicit horizon", fq_stale.freshness.state is FreshnessState.STALE)
    check("STALE is not FALSE — the value is unchanged",
          fq_stale.effective_value == {"replicas": 5})
    # a predicate with no rule stays UNKNOWN, never STALE
    fq_unknown = wq.current(tenant=tenant, subject_ref="widget:w-1", predicate="state",
                            now=_utc(23, 0))
    # 'state' has a rule -> so use a rule-less predicate for the UNKNOWN check
    no_rule = WorldQuery(facts=fact_repo, observations=obs_repo,
                         freshness_policy=None, authority_policy=authority)
    check("no freshness policy -> UNKNOWN (never STALE by default)",
          no_rule.current(tenant=tenant, subject_ref="deployment/api",
                          predicate="spec.replicas", now=_utc(20, 0)).freshness.state
          is FreshnessState.UNKNOWN)

    # ------------------------------------------------------------------
    # Part M — tenant isolation / cross-tenant fail closed
    # ------------------------------------------------------------------
    print("[M] tenant isolation (fail closed)")
    tq = wq.current(tenant=other, subject_ref="deployment/payments", predicate="spec.replicas",
                    now=_utc(10, 20))
    check("cross-tenant current is UNKNOWN", tq.temporal.status is EpistemicStatus.UNKNOWN)
    check("cross-tenant evidence is empty", tq.evidence == ())
    check("cross-tenant history is empty", wq.history(
          tenant=other, subject_ref="deployment/payments", predicate="spec.replicas") == ())

    # ------------------------------------------------------------------
    # Part R — replay inertness + query read-only
    # ------------------------------------------------------------------
    print("[R] replay inert; query read-only")
    from backend.contexts.execution.application.commands import ReplayExecution
    facts_before = fact_repo.count_all()
    provider_before_replay = len(adapter.calls)
    before_q = wq.current(tenant=tenant, subject_ref=S, predicate=P, now=_utc(10, 20)).effective_value
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    check("replay created zero new facts", fact_repo.count_all() == facts_before)
    check("replay performed zero provider reads", len(adapter.calls) == provider_before_replay)
    after_q = wq.current(tenant=tenant, subject_ref=S, predicate=P, now=_utc(10, 20)).effective_value
    check("query is read-only (identical result across replay)", before_q == after_q)

    # ------------------------------------------------------------------
    # Part S — crash / recovery; query after restart
    # ------------------------------------------------------------------
    print("[S] crash/recovery, query after restart")
    import subprocess
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase74_query_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    successor = WorldQuery(
        facts=SqlFactRepository(_store().store),
        observations=SqlObservationRepository(_store().store),
        freshness_policy=freshness, authority_policy=authority)
    cq2 = successor.current(tenant=tenant, subject_ref="deployment/crash",
                            predicate="spec.replicas", now=_utc(12, 5))
    check("crashed fact queryable after restart", cq2.effective_value == {"replicas": 9})
    check("evidence intact after restart", len(cq2.evidence) == 1)
    check("freshness reproducible after restart (fresh at +5m)",
          cq2.freshness.state is FreshnessState.FRESH)
    check("crashed fact cross-tenant fail-closed",
          successor.current(tenant=other, subject_ref="deployment/crash",
                            predicate="spec.replicas", now=_utc(12, 5)).temporal.status
          is EpistemicStatus.UNKNOWN)

    # ------------------------------------------------------------------
    # Part T — query performance discipline (measure, don't optimize)
    # ------------------------------------------------------------------
    print("[T] query performance (measured)")
    t0 = time.perf_counter()
    for _ in range(20):
        wq.current(tenant=tenant, subject_ref=S, predicate=P, now=_utc(10, 20))
    latency_ms = (time.perf_counter() - t0) / 20 * 1000
    check("current query latency recorded", latency_ms >= 0, f"{latency_ms:.1f}ms avg over 20")
    REPORT["performance"] = {"current_query_avg_ms": round(latency_ms, 2)}

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    REPORT["counts"] = {"facts": fact_repo.count_all(), "observations": obs_repo.count_all(),
                        "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "world query verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
