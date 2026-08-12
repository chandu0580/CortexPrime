"""Phase 7.3 real-Postgres evidence: deterministic Observation -> Fact derivation,
bitemporal queries, conflict, crash/recovery, rollback, replay inertness.

Run:  python -m scripts.phase73_fact_harness
      python -m scripts.phase73_fact_harness --crash-child   (internal)

The pipeline (at least once fully governed):
  governed widget.get READ (controlled provider, through the gateway) ->
  ReadObservation -> ObservationIngestion -> cw_observation ->
  FactDerivation.derive -> cw_fact.

Then: the load-bearing bitemporal example (valid vs knowledge time), a
same-valid-instant CONFLICT, idempotency, crash/recovery across a real
os._exit(9), failed-append rollback, replay inertness (zero new facts, zero
provider reads), and cross-tenant fail-closed reads.

Exit codes: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from scripts.phase72_observation_harness import (
    _governed_read_evidence, _read_from_governed_outcome, _store,
)
from scripts.phase62_recovery_harness import (
    TENANT, _commission, _tenant_ctx,
)

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}


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


def _read(subject, predicate, value, observed_at, *, exec_ref="ex-scn", obs_suffix=""):
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.world.application import ReadObservation
    return ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
        subject_ref=subject, predicate=predicate, value=value,
        status=SourceStatus.RETURNED_DATA, observed_at=observed_at,
        retrieved_at=observed_at + timedelta(minutes=4),
        produced_by="connector:kubernetes", execution_ref=exec_ref,
        trace_ref="corr-scn" + obs_suffix)


def _ingest_and_derive(ingestion, derivation, tenant, read, *, obs_recorded, knowledge_at):
    obs, _ = ingestion.ingest(tenant=tenant, read=read, recorded_at=obs_recorded)
    return derivation.derive(tenant=tenant, observation=obs, recorded_at=knowledge_at), obs


def _run_crash_child() -> None:
    """Ingest one observation, derive a fact, write its identity to a marker, die."""
    from backend.contracts.tenant import TenantRef
    from backend.world.application import (
        FactDerivation, ObservationIngestion, fact_semantic_identity,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    persistence = _store()
    tenant = TenantRef(tenant_id=TENANT)
    ingestion = ObservationIngestion(repository=SqlObservationRepository(persistence.store))
    derivation = FactDerivation(repository=SqlFactRepository(persistence.store))
    read = _read("deployment/crash", "spec.replicas", {"replicas": 7}, _utc(12, 0),
                 exec_ref="ex-crash", obs_suffix="-crash")
    result, _ = _ingest_and_derive(ingestion, derivation, tenant, read,
                                   obs_recorded=_utc(12, 1), knowledge_at=_utc(12, 1))
    marker = os.getenv("CORTEX_P73_MARKER")
    if marker and result.fact is not None:
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump({"fact_id": result.fact.record_id,
                       "semantic_identity": fact_semantic_identity(
                           tenant, "deployment/crash", "spec.replicas")}, fh)
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
    from backend.contracts.world import EpistemicStatus, Fact
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import (
        DerivationOutcome, FactDerivation, ObservationIngestion, as_known,
        as_of_valid, current_state, fact_semantic_identity, history,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p73 harness", component="world-fact-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]

    obs_repo = SqlObservationRepository(runtime.persistence.store)
    fact_repo = SqlFactRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=obs_repo)
    derivation = FactDerivation(repository=fact_repo)
    tenant = TenantRef(tenant_id=TENANT)

    # ------------------------------------------------------------------
    # Part A — a governed READ becomes an Observation becomes a Fact
    # ------------------------------------------------------------------
    print("[A] governed READ -> Observation -> Fact")
    exec_id, node, state, evidence = _governed_read_evidence(runtime, tenant_ctx, defs)
    check("governed widget.get READ succeeded", state == "succeeded", str(state))
    read = _read_from_governed_outcome(runtime, tenant_ctx, exec_id, node, evidence)
    obs, _ = ingestion.ingest(tenant=tenant, read=read,
                              recorded_at=datetime.now(timezone.utc))
    provider_before = len(adapter.calls)
    result = derivation.derive(tenant=tenant, observation=obs,
                               recorded_at=datetime.now(timezone.utc))
    check("a fact was derived from the governed observation",
          result.outcome is DerivationOutcome.ASSERTED and result.fact is not None)
    check("derivation contacted no provider itself",
          len(adapter.calls) == provider_before)
    check("fact is grounded in its observation (provenance chain)",
          result.fact.provenance.observation_ref == obs.record_id)
    check("fact carries the execution reference from the observation",
          result.fact.provenance.execution_ref == obs.provenance.execution_ref)
    check("fact is tenant-scoped from the governed context",
          result.fact.tenant.tenant_id == TENANT)
    check("a Fact carries no confidence field (no invented calibration)",
          not hasattr(result.fact, "confidence"))

    # ------------------------------------------------------------------
    # Part B — the load-bearing bitemporal example (valid vs knowledge time)
    # ------------------------------------------------------------------
    print("[B] bitemporal: valid time vs knowledge time")
    # replicas=5 valid_from 10:00, recorded (knowledge) 10:04
    _ingest_and_derive(ingestion, derivation, tenant,
                       _read("deployment/payments", "spec.replicas", {"replicas": 5},
                             _utc(10, 0), obs_suffix="-p5"),
                       obs_recorded=_utc(10, 4), knowledge_at=_utc(10, 4))
    # replicas=3 valid_from 09:58 (earlier world time), recorded 10:10 — correction
    _ingest_and_derive(ingestion, derivation, tenant,
                       _read("deployment/payments", "spec.replicas", {"replicas": 3},
                             _utc(9, 58), obs_suffix="-p3"),
                       obs_recorded=_utc(10, 10), knowledge_at=_utc(10, 10))
    sid = fact_semantic_identity(tenant, "deployment/payments", "spec.replicas")
    versions = fact_repo.versions_for(tenant_id=TENANT, semantic_identity=sid)
    check("both fact versions retained (history not overwritten)", len(versions) == 2,
          f"versions={len(versions)}")
    check("what was true at 09:59 -> replicas 3",
          as_of_valid(versions, _utc(9, 59)).value == {"replicas": 3})
    check("what was true at 10:02 -> replicas 5",
          as_of_valid(versions, _utc(10, 2)).value == {"replicas": 5})
    check("what CortexPrime knew at 10:00 -> UNKNOWN (not FALSE)",
          as_known(versions, _utc(10, 0)).status is EpistemicStatus.UNKNOWN)
    check("what CortexPrime knew at 10:05 -> replicas 5",
          as_known(versions, _utc(10, 5)).value == {"replicas": 5})
    check("what the World Plane currently represents -> replicas 5",
          current_state(versions, _utc(10, 20)).value == {"replicas": 5})
    hist = history(versions)
    check("history is ordered by knowledge time", [e.value for e in hist] ==
          [{"replicas": 5}, {"replicas": 3}])

    # ------------------------------------------------------------------
    # Part C — conflict: same valid instant, different value, no authority
    # ------------------------------------------------------------------
    print("[C] conflict stays CONFLICTED (never latest-wins)")
    _ingest_and_derive(ingestion, derivation, tenant,
                       _read("deployment/api", "spec.replicas", {"replicas": 5},
                             _utc(11, 0), obs_suffix="-a5"),
                       obs_recorded=_utc(11, 1), knowledge_at=_utc(11, 1))
    conflict_result, _ = _ingest_and_derive(
        ingestion, derivation, tenant,
        _read("deployment/api", "spec.replicas", {"replicas": 3}, _utc(11, 0),
              obs_suffix="-a3"),
        obs_recorded=_utc(11, 5), knowledge_at=_utc(11, 5))
    check("a same-instant different value is CONFLICTED",
          conflict_result.outcome is DerivationOutcome.CONFLICTED)
    api_sid = fact_semantic_identity(tenant, "deployment/api", "spec.replicas")
    api_versions = fact_repo.versions_for(tenant_id=TENANT, semantic_identity=api_sid)
    conflict_view = current_state(api_versions, _utc(11, 30))
    check("the conflicted instant reports CONFLICTED with both values",
          conflict_view.status is EpistemicStatus.CONFLICTED
          and {c.value["replicas"] for c in conflict_view.conflicts} == {5, 3})
    check("both conflicting evidence paths are preserved", len(api_versions) == 2)

    # ------------------------------------------------------------------
    # Part D — idempotency (semantic level)
    # ------------------------------------------------------------------
    print("[D] idempotency: re-derive is a deterministic no-op")
    before = fact_repo.count_all()
    again = derivation.derive(tenant=tenant, observation=obs,
                              recorded_at=datetime.now(timezone.utc))
    check("re-deriving the same observation dedupes",
          again.outcome is DerivationOutcome.DEDUPED)
    check("no new fact row from the duplicate derivation",
          fact_repo.count_all() == before)

    # ------------------------------------------------------------------
    # Part E — replay inertness: zero new facts, zero provider reads
    # ------------------------------------------------------------------
    print("[E] replay creates zero facts and zero provider reads")
    from backend.contexts.execution.application.commands import ReplayExecution
    facts_before = fact_repo.count_all()
    provider_before_replay = len(adapter.calls)
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    check("replay created zero new facts", fact_repo.count_all() == facts_before)
    check("replay performed zero provider reads",
          len(adapter.calls) == provider_before_replay)

    # ------------------------------------------------------------------
    # Part F — crash / recovery across a real os._exit(9)
    # ------------------------------------------------------------------
    print("[F] crash/recovery (real process death)")
    import subprocess
    import tempfile
    marker = os.path.join(tempfile.gettempdir(), f"p73_{os.getpid()}.json")
    child_env = dict(os.environ)
    child_env["CORTEX_P73_MARKER"] = marker
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase73_fact_harness", "--crash-child"],
        env=child_env, cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9),
          f"rc={child.returncode}")
    crashed = {}
    if os.path.exists(marker):
        with open(marker, encoding="utf-8") as fh:
            crashed = json.load(fh)
        os.remove(marker)
    check("child derived its fact before dying", bool(crashed.get("fact_id")))
    if crashed.get("fact_id"):
        successor = SqlFactRepository(_store().store)
        rec = successor.get(tenant_id=TENANT, fact_id=crashed["fact_id"])
        check("fact survived the crash intact", rec is not None and isinstance(rec, Fact))
        check("recovered fact provenance intact after crash",
              rec is not None and rec.provenance.execution_ref == "ex-crash")
        check("crashed fact is cross-tenant-isolated (fail closed)",
              successor.get(tenant_id="other", fact_id=crashed["fact_id"]) is None)
        check("cross-tenant versions_for is empty (fail closed)",
              successor.versions_for(
                  tenant_id="other",
                  semantic_identity=crashed["semantic_identity"]) == ())

    # ------------------------------------------------------------------
    # Part G — failed append leaves no partial fact
    # ------------------------------------------------------------------
    print("[G] failed append rolls back (no partial fact)")
    from backend.database.durable.tables import world_fact_table as FT
    before_rollback = fact_repo.count_all()
    try:
        with runtime.persistence.store.atomic() as work:
            work.execute(sa.insert(FT).values(
                fact_id="wfact-rollback", version_digest="fact-rollback-probe",
                semantic_identity="sid", tenant_id=TENANT, subject_ref="s",
                predicate="p", value_digest="v", valid_from=_utc(13, 0),
                valid_to=None, status="affirmed", authority="advisory",
                recorded_at=work.now, record={"_contract": "probe"}, produced_by="c",
                observation_ref="o", parent_claim_ref=None, schema_version=1))
            raise RuntimeError("deliberate mid-transaction failure")
    except RuntimeError:
        pass
    check("failed transaction left the fact count unchanged",
          fact_repo.count_all() == before_rollback)
    check("the rolled-back fact is not readable",
          fact_repo.get(tenant_id=TENANT, fact_id="wfact-rollback") is None)

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    REPORT["counts"] = {"facts": fact_repo.count_all(),
                        "observations": obs_repo.count_all(),
                        "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "fact derivation verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
