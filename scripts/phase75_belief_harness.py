"""Phase 7.5 real-Postgres evidence: corroboration & belief formation.

Run:  python -m scripts.phase75_belief_harness
      python -m scripts.phase75_belief_harness --crash-child   (internal)

The full bridge, one governed provider call, none from belief formation:
  governed READ -> Observation -> Fact -> (authority + freshness + corroboration)
  -> Belief. Then the load-bearing matrix (independent vs correlated vs
  contradictory evidence, authority beats recency, equal-authority conflict,
  STALE/UNKNOWN != FALSE, temporal + knowledge-time beliefs), tenant fail-closed,
  replay inertness, and crash/recovery with deterministic belief reconstruction.

Belief is a DERIVED PROJECTION — no belief table. It reconstructs from the
durable facts/observations after a crash. Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
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
K8S, PROM, CACHE = "connector:kubernetes", "connector:prometheus", "connector:stale-cache"


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


def _read(subject, predicate, value, observed_at, *, source_ref=K8S, exec_ref="ex-scn", nonce=""):
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.world.application import ReadObservation
    return ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref=source_ref,
        subject_ref=subject, predicate=predicate, value=value,
        status=SourceStatus.RETURNED_DATA, observed_at=observed_at,
        retrieved_at=observed_at + timedelta(minutes=4), produced_by=source_ref,
        execution_ref=exec_ref, trace_ref="corr-scn" + nonce)


def _policies():
    from backend.contracts.world import SourceAuthority
    from backend.world.application import (
        AuthorityPolicy, AuthorityRule, FreshnessPolicy, FreshnessRule,
    )
    freshness = FreshnessPolicy(rules=(
        FreshnessRule(horizon_seconds=600, predicate="spec.replicas"),
        FreshnessRule(horizon_seconds=600, predicate="state"),
    ), name="p75-freshness")
    authority = AuthorityPolicy(rules=(
        AuthorityRule(tier=SourceAuthority.AUTHORITATIVE, source_ref=K8S),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref=PROM),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref=CACHE),
        AuthorityRule(tier=SourceAuthority.SINGLE_SOURCE, source_ref="connector:controlled"),
    ), name="p75-authority")
    return freshness, authority


def _stack(persistence, freshness, authority):
    from backend.world.application import (
        BeliefFormation, FactDerivation, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository
    obs_repo = SqlObservationRepository(persistence.store)
    fact_repo = SqlFactRepository(persistence.store)
    query = WorldQuery(facts=fact_repo, observations=obs_repo,
                       freshness_policy=freshness, authority_policy=authority)
    beliefs = BeliefFormation(query=query, observations=obs_repo, authority_policy=authority)
    return obs_repo, fact_repo, ObservationIngestion(repository=obs_repo), \
        FactDerivation(repository=fact_repo), query, beliefs


def _run_crash_child():
    from backend.contracts.tenant import TenantRef
    persistence = _store()
    freshness, authority = _policies()
    _, _, ingestion, derivation, _, _ = _stack(persistence, freshness, authority)
    tenant = TenantRef(tenant_id=TENANT)
    obs, _ = ingestion.ingest(tenant=tenant, recorded_at=_utc(12, 1),
                              read=_read("deployment/crash", "spec.replicas",
                                         {"replicas": 9}, _utc(12, 0), exec_ref="ex-crash"))
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
    from backend.contracts.world import EpistemicStatus
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import CorroborationLevel

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p75 harness", component="world-belief-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]
    freshness, authority = _policies()
    obs_repo, fact_repo, ingestion, derivation, query, beliefs = _stack(
        runtime.persistence, freshness, authority)
    tenant = TenantRef(tenant_id=TENANT)
    other = TenantRef(tenant_id="other")

    def idr(read, *, obs_recorded, knowledge_at):
        obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=obs_recorded)
        derivation.derive(tenant=tenant, observation=obs, recorded_at=knowledge_at)
        return obs

    def believe(subject, predicate, now, **kw):
        return beliefs.form_current(tenant=tenant, subject_ref=subject, predicate=predicate,
                                    now=now, **kw)

    # ---- Part Q: governed READ -> Observation -> Fact -> Belief ----
    print("[Q] governed READ -> Observation -> Fact -> Belief")
    exec_id, node, state, evidence = _governed_read_evidence(runtime, tenant_ctx, defs)
    check("governed widget.get READ succeeded", state == "succeeded", state)
    read = _read_from_governed_outcome(runtime, tenant_ctx, exec_id, node, evidence)
    obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=datetime.now(timezone.utc))
    derivation.derive(tenant=tenant, observation=obs, recorded_at=datetime.now(timezone.utc))
    provider_before = len(adapter.calls)
    b = believe("widget:w-1", "state", datetime.now(timezone.utc))
    check("belief formed from the governed observation", b.status is EpistemicStatus.AFFIRMED)
    check("belief formation contacted no provider", len(adapter.calls) == provider_before)
    check("belief confidence is UNCALIBRATED (no invented number)",
          b.confidence.value is None)
    check("belief grounds in the governed execution",
          b.belief is not None and b.belief.provenance.execution_ref == exec_id)

    # ---- S1: single authoritative source ----
    print("[S1] single authoritative source supports belief")
    idr(_read("deployment/a", "spec.replicas", {"replicas": 5}, _utc(10, 0), source_ref=K8S),
        obs_recorded=_utc(10, 1), knowledge_at=_utc(10, 1))
    b = believe("deployment/a", "spec.replicas", _utc(10, 2))
    check("belief AFFIRMED, single source", b.status is EpistemicStatus.AFFIRMED
          and b.corroboration.level is CorroborationLevel.SINGLE)

    # ---- S2/S4: independent corroboration (distinct sources agree) ----
    print("[S2/S4] independent sources agree -> INDEPENDENT")
    idr(_read("deployment/b", "spec.replicas", {"replicas": 4}, _utc(10, 0), source_ref=K8S),
        obs_recorded=_utc(10, 1), knowledge_at=_utc(10, 1))
    idr(_read("deployment/b", "spec.replicas", {"replicas": 4}, _utc(10, 0), source_ref=PROM),
        obs_recorded=_utc(10, 1), knowledge_at=_utc(10, 1))
    b = believe("deployment/b", "spec.replicas", _utc(10, 5))
    check("two independent sources -> INDEPENDENT",
          b.corroboration.level is CorroborationLevel.INDEPENDENT
          and set(b.corroboration.independent_sources) == {K8S, PROM})

    # ---- S3: same-provider duplicate is correlated, not independent ----
    print("[S3] same-provider duplicate is correlated, not independent")
    idr(_read("deployment/c", "spec.replicas", {"replicas": 6}, _utc(10, 0), source_ref=K8S, nonce="c1"),
        obs_recorded=_utc(10, 1), knowledge_at=_utc(10, 1))
    idr(_read("deployment/c", "spec.replicas", {"replicas": 6}, _utc(10, 1), source_ref=K8S, nonce="c2"),
        obs_recorded=_utc(10, 2), knowledge_at=_utc(10, 2))
    b = believe("deployment/c", "spec.replicas", _utc(10, 5))
    check("same-source duplicate -> SINGLE with correlated_count>=1",
          b.corroboration.level is CorroborationLevel.SINGLE and b.corroboration.correlated_count >= 1)

    # ---- S5: independent sources disagree (ungoverned would conflict); here
    #          governed by authority so a lower-tier disagreement is an alternative ----
    print("[S6] equal-authority disagreement stays CONFLICTED")
    idr(_read("deployment/d", "spec.replicas", {"replicas": 5}, _utc(10, 0), source_ref=K8S),
        obs_recorded=_utc(10, 1), knowledge_at=_utc(10, 1))
    idr(_read("deployment/d", "spec.replicas", {"replicas": 3}, _utc(10, 0),
              source_ref="connector:kubernetes-2"), obs_recorded=_utc(10, 2), knowledge_at=_utc(10, 2))
    # both AUTHORITATIVE via a kind-level rule
    from backend.contracts.world import SourceAuthority
    from backend.world.application import AuthorityPolicy, AuthorityRule, BeliefFormation, WorldQuery
    eq_auth = AuthorityPolicy(rules=(AuthorityRule(tier=SourceAuthority.AUTHORITATIVE,
                                                   source_kind="connector"),))
    eq_query = WorldQuery(facts=fact_repo, observations=obs_repo,
                          freshness_policy=freshness, authority_policy=eq_auth)
    eq_beliefs = BeliefFormation(query=eq_query, observations=obs_repo, authority_policy=eq_auth)
    bd = eq_beliefs.form_current(tenant=tenant, subject_ref="deployment/d",
                                 predicate="spec.replicas", now=_utc(10, 5))
    check("equal-authority disagreement -> CONFLICTED", bd.status is EpistemicStatus.CONFLICTED)
    check("both competing values preserved",
          len(bd.corroboration.supporting) + len(bd.corroboration.contradicting) == 2)

    # ---- S9/S10: authority beats recency; contradictory evidence retained ----
    print("[S9/S10] authority beats recency; contradiction retained")
    idr(_read("deployment/e", "spec.replicas", {"replicas": 5}, _utc(10, 0), source_ref=K8S),
        obs_recorded=_utc(10, 1), knowledge_at=_utc(10, 1))
    idr(_read("deployment/e", "spec.replicas", {"replicas": 3}, _utc(10, 5), source_ref=CACHE),
        obs_recorded=_utc(10, 6), knowledge_at=_utc(10, 6))
    be = believe("deployment/e", "spec.replicas", _utc(10, 10))
    check("belief holds the authoritative value, not the newer cache",
          be.value == {"replicas": 5} and be.status is EpistemicStatus.AFFIRMED)
    check("the contradicting cache evidence is retained",
          any(e.source_ref == CACHE for e in be.corroboration.contradicting))

    # ---- S7: stale != FALSE ----
    print("[S7] stale evidence -> STALE, not FALSE")
    bs = believe("deployment/a", "spec.replicas", _utc(10, 30))  # 30m after 10:00 obs
    check("stale belief is STALE not AFFIRMED/FALSE", bs.status is EpistemicStatus.STALE)
    check("stale belief keeps its value", bs.value == {"replicas": 5})

    # ---- S8: unknown != FALSE ----
    print("[S8] unknown -> UNKNOWN, not FALSE")
    bu = believe("deployment/nonexistent", "spec.replicas", _utc(10, 30))
    check("no evidence -> UNKNOWN, no belief object", bu.status is EpistemicStatus.UNKNOWN
          and bu.belief is None)

    # ---- S13/S14: temporal + knowledge-time beliefs ----
    print("[S13/S14] temporal + knowledge-time beliefs")
    idr(_read("deployment/f", "spec.replicas", {"replicas": 5}, _utc(10, 0)),
        obs_recorded=_utc(10, 4), knowledge_at=_utc(10, 4))
    idr(_read("deployment/f", "spec.replicas", {"replicas": 3}, _utc(9, 58)),
        obs_recorded=_utc(10, 10), knowledge_at=_utc(10, 10))
    check("world @ 09:59 -> 3", beliefs.form_as_of_valid(
        tenant=tenant, subject_ref="deployment/f", predicate="spec.replicas",
        at_valid=_utc(9, 59), now=_utc(10, 20)).value == {"replicas": 3})
    check("world @ 10:02 -> 5", beliefs.form_as_of_valid(
        tenant=tenant, subject_ref="deployment/f", predicate="spec.replicas",
        at_valid=_utc(10, 2), now=_utc(10, 20)).value == {"replicas": 5})
    check("known @ 10:00 -> UNKNOWN", beliefs.form_as_known(
        tenant=tenant, subject_ref="deployment/f", predicate="spec.replicas",
        known_at=_utc(10, 0)).status is EpistemicStatus.UNKNOWN)
    check("known @ 10:05 -> 5", beliefs.form_as_known(
        tenant=tenant, subject_ref="deployment/f", predicate="spec.replicas",
        known_at=_utc(10, 5)).value == {"replicas": 5})

    # ---- S12: tenant isolation ----
    print("[S12] tenant isolation (fail closed)")
    bt = beliefs.form_current(tenant=other, subject_ref="deployment/a",
                              predicate="spec.replicas", now=_utc(10, 2))
    check("cross-tenant belief is UNKNOWN", bt.status is EpistemicStatus.UNKNOWN)
    check("cross-tenant corroboration empty", bt.corroboration.supporting == ())

    # ---- S15/replay: inert; belief reconstruction read-only ----
    print("[R] replay inert; belief reconstruction read-only")
    from backend.contexts.execution.application.commands import ReplayExecution
    facts_before = fact_repo.count_all()
    provider_before_replay = len(adapter.calls)
    before = believe("deployment/e", "spec.replicas", _utc(10, 10)).to_dict()
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    check("replay created zero new facts", fact_repo.count_all() == facts_before)
    check("replay performed zero provider reads", len(adapter.calls) == provider_before_replay)
    after = believe("deployment/e", "spec.replicas", _utc(10, 10)).to_dict()
    check("belief identical across replay (read-only, deterministic)", before == after)

    # ---- S: crash / recovery -> deterministic reconstruction ----
    print("[S] crash/recovery; belief reconstructs deterministically")
    import subprocess
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase75_belief_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    _, _, _, _, _, succ_beliefs = _stack(_store(), freshness, authority)
    r1 = succ_beliefs.form_current(tenant=tenant, subject_ref="deployment/crash",
                                   predicate="spec.replicas", now=_utc(12, 5))
    r2 = succ_beliefs.form_current(tenant=tenant, subject_ref="deployment/crash",
                                   predicate="spec.replicas", now=_utc(12, 5))
    check("crashed belief reconstructs after restart", r1.value == {"replicas": 9})
    check("reconstruction is deterministic", r1.to_dict() == r2.to_dict())
    check("crashed belief cross-tenant fail-closed",
          succ_beliefs.form_current(tenant=other, subject_ref="deployment/crash",
                                    predicate="spec.replicas", now=_utc(12, 5)).status
          is EpistemicStatus.UNKNOWN)

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    REPORT["counts"] = {"facts": fact_repo.count_all(), "observations": obs_repo.count_all(),
                        "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "belief formation verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
