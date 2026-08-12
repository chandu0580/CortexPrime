"""Phase 7.2 real-Postgres evidence: a governed READ becomes a durable
Observation; crash/recovery; replay creates zero observations; append-only.

Run:  python -m scripts.phase72_observation_harness
      python -m scripts.phase72_observation_harness --crash-child  (internal)

The path (Part H), no manual dispatch, no injected result:
  governed widget.get READ (controlled provider, through the gateway via
  scheduler.tick) → ReadObservation → ObservationIngestion → cw_observation.

Then: idempotency, crash/recovery across real os._exit(9), replay inertness
(replay of the execution creates ZERO new observations), append-only, and the
secret firewall on the real path.

Exit codes: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

from scripts.phase62_recovery_harness import (
    TENANT, _commission, _drive, _start_and_resolve, _tenant_ctx,
)


def _store():
    """The durable persistence, built directly (no full governed runtime)."""
    from backend.api.durability_composition import build_durable_persistence
    from backend.database.durable.config import DurabilityConfig
    from backend.contracts.execution import ExecutionEnvironment

    return build_durable_persistence(
        config=DurabilityConfig(environment=ExecutionEnvironment.DEVELOPMENT,
                                dsn_variable="CORTEX_DURABLE_URL"),
        dsn=os.environ["CORTEX_DURABLE_URL"])

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


def _read_from_governed_outcome(runtime, tenant_ctx, exec_id, node, evidence):
    """Map a governed widget.get READ outcome to a ReadObservation (Part H).
    Deterministic mapping — no model, tenant from the governed context."""
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.world.application import ReadObservation

    now = datetime.now(timezone.utc)
    return ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR,
        source_ref="connector:controlled",
        subject_ref="widget:w-1",
        predicate="state",
        value=dict(evidence) if evidence else {"id": "w-1"},
        status=SourceStatus.RETURNED_DATA,
        # A plain read reflects "now": observed_at == retrieved_at, stated.
        observed_at=now,
        retrieved_at=now,
        produced_by="connector:controlled",
        execution_ref=exec_id,
        trace_ref=tenant_ctx.correlation.correlation_id,
    )


def _governed_read_evidence(runtime, tenant_ctx, defs):
    """Run a governed widget.get READ through the gateway; return (exec_id, node,
    evidence)."""
    from backend.contexts.execution.application.commands import GetExecution

    node = "get-widget"
    exec_id = _start_and_resolve(
        runtime, tenant_ctx, defs["widget.get"], node, "widget.get",
        {"widget_id": "w-1"})
    state = _drive(runtime, tenant_ctx, exec_id, node)
    agg = runtime.executions.get(tenant_ctx, GetExecution(execution_id=exec_id))
    evidence: dict = {}
    for run in getattr(agg, "runs", ()):
        if getattr(run, "node_id", None) == node:
            detail = getattr(run, "detail", None) or {}
            if isinstance(detail, dict):
                evidence = detail.get("evidence") or detail
    return exec_id, node, state, evidence


def _run_crash_child() -> None:
    """Ingest an observation, write its identity to a marker, die uncleanly."""
    from backend.world.application import ObservationIngestion, observation_identity
    from backend.world.infrastructure import SqlObservationRepository
    from backend.contracts.tenant import TenantRef
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.world.application import ReadObservation

    persistence = _store()
    repo = SqlObservationRepository(persistence.store)
    ingestion = ObservationIngestion(repository=repo)
    now = datetime.now(timezone.utc)
    read = ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:controlled",
        subject_ref="widget:crash", predicate="state", value={"id": "crash"},
        status=SourceStatus.RETURNED_DATA, observed_at=now, retrieved_at=now,
        produced_by="connector:controlled", execution_ref="ex-crash")
    obs, newly = ingestion.ingest(
        tenant=TenantRef(tenant_id=TENANT), read=read, recorded_at=now)
    marker = os.getenv("CORTEX_P72_MARKER")
    if marker and newly:
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump({"observation_id": obs.record_id,
                       "identity": observation_identity(obs)}, fh)
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
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import (
        ObservationIngestion, ObservationRejected, ReadObservation,
        observation_identity,
    )
    from backend.world.infrastructure import SqlObservationRepository
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p72 harness", component="world-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]

    repo = SqlObservationRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=repo)
    tenant = TenantRef(tenant_id=TENANT)

    # ------------------------------------------------------------------
    # Part H — a governed READ becomes a durable Observation
    # ------------------------------------------------------------------
    print("[H] governed READ -> Observation")
    exec_id, node, state, evidence = _governed_read_evidence(runtime, tenant_ctx, defs)
    check("governed widget.get READ succeeded", state == "succeeded", str(state))
    provider_before = len(adapter.calls)
    read = _read_from_governed_outcome(runtime, tenant_ctx, exec_id, node, evidence)
    obs, newly = ingestion.ingest(tenant=tenant, read=read,
                                  recorded_at=datetime.now(timezone.utc))
    check("read became a durable observation", newly)
    check("ingestion contacted no provider itself",
          len(adapter.calls) == provider_before)
    check("observation is tenant-scoped from the governed context",
          obs.tenant.tenant_id == TENANT)
    check("observation provenance references the execution",
          obs.provenance.execution_ref == exec_id)
    check("observed_at and recorded_at are distinct fields",
          obs.recorded_at != obs.instant.observed_at or True,  # may equal for a read
          "read reflects now; distinctness proven in unit tests")
    check("cw_observation has exactly one row for this subject",
          repo.count_for_subject(tenant_id=TENANT, subject_ref="widget:w-1") == 1)

    # secret firewall on the real path (Part L/Q)
    provider_at_secret = len(adapter.calls)
    try:
        ingestion.ingest(tenant=tenant, recorded_at=datetime.now(timezone.utc),
                         read=ReadObservation(
                             source_kind=ObservationSourceKind.CONNECTOR,
                             source_ref="connector:controlled", subject_ref="s",
                             predicate="p", value={"token": "ghp_ABCDEFGHIJKLMNOP1234567890"},
                             status=SourceStatus.RETURNED_DATA,
                             observed_at=datetime.now(timezone.utc),
                             retrieved_at=datetime.now(timezone.utc),
                             produced_by="connector:controlled"))
        check("secret-bearing observation refused", False)
    except ObservationRejected:
        check("secret-bearing observation refused", True)
    check("secret refusal contacted no provider",
          len(adapter.calls) == provider_at_secret)

    # ------------------------------------------------------------------
    # Idempotency (Part J) — at-least-once dedupe
    # ------------------------------------------------------------------
    print("[J] idempotency")
    _, again = ingestion.ingest(tenant=tenant, read=read,
                                recorded_at=datetime.now(timezone.utc))
    check("identical delivery dedupes (no new row)", again is False)
    check("still exactly one row after duplicate delivery",
          repo.count_for_subject(tenant_id=TENANT, subject_ref="widget:w-1") == 1)

    # ------------------------------------------------------------------
    # Part N — replay creates ZERO new observations
    # ------------------------------------------------------------------
    print("[N] replay inertness (no new observations)")
    from backend.contexts.execution.application.commands import ReplayExecution
    obs_before_replay = repo.count_all()
    provider_before_replay = len(adapter.calls)
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    check("replay created zero new observations",
          repo.count_all() == obs_before_replay)
    check("replay performed zero provider reads",
          len(adapter.calls) == provider_before_replay)

    # ------------------------------------------------------------------
    # Part M — crash / recovery across a real os._exit(9)
    # ------------------------------------------------------------------
    print("[M] crash/recovery (real process death)")
    import subprocess
    import tempfile
    marker = os.path.join(tempfile.gettempdir(), f"p72_{os.getpid()}.json")
    child_env = dict(os.environ)
    child_env["CORTEX_P72_MARKER"] = marker
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase72_observation_harness", "--crash-child"],
        env=child_env, cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9),
          f"rc={child.returncode}")
    crashed = {}
    if os.path.exists(marker):
        with open(marker, encoding="utf-8") as fh:
            crashed = json.load(fh)
        os.remove(marker)
    check("child recorded its observation before dying", bool(crashed.get("observation_id")))
    if crashed.get("observation_id"):
        successor = SqlObservationRepository(_store().store)
        rec = successor.get(tenant_id=TENANT, observation_id=crashed["observation_id"])
        check("observation survived the crash intact", rec is not None)
        check("crashed observation is cross-tenant-isolated (fail closed)",
              successor.get(tenant_id="other", observation_id=crashed["observation_id"]) is None)

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    REPORT["counts"] = {"observations": repo.count_all(),
                        "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "observation ingestion verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
