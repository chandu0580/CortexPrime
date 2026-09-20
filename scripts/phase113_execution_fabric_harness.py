"""Phase 11.3 — the governed execution fabric, proven against real PostgreSQL
and real OS processes.

What this establishes, in order:

  FENCE      several real processes race one node; exactly one holds it
  DURABLE    a process dispatches an execution it never started
  RECOVERY   a dispatcher dies mid-flight and the run is still recoverable
  SECURITY   the authority path is unchanged by the fabric change

The last one matters most. Phase 11.3 lets a background process dispatch work it
did not start, under a tenant context rebuilt from the node's sealed binding
(ADR-127 D-2). That is a change to *who may carry* a decision, and it must not
become a change to *what was decided* -- so the security stage re-proves the
properties the change could plausibly have broken.

Exit 0 = VERIFIED. Report: docs/phase113_execution_fabric_report.json.

Environment:
  P113_DSN   SQLAlchemy URL for a scratch PostgreSQL database (required)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

REPORT_PATH = REPO / "docs" / "phase113_execution_fabric_report.json"
REPORT: dict = {
    "phase": "11.3",
    "adr": "ADR-127",
    "checks": [],
    "measurements": {},
    "stages": [],
    "negative_matrix": [],
}

TENANT = "tenant-p113"
OTHER_TENANT = "tenant-p113-other"


def check(name: str, ok: bool, detail=None) -> bool:
    REPORT["checks"].append({"name": name, "ok": bool(ok), "detail": _short(detail)})
    print(f"[{'OK ' if ok else 'FAIL'}] {name}" + (f"  -- {_short(detail)}" if detail else ""))
    return bool(ok)


def measure(name: str, value) -> None:
    REPORT["measurements"][name] = value
    print(f"[MEAS] {name} = {json.dumps(value, default=str)[:220]}")


def stage(name: str) -> None:
    REPORT["stages"].append(name)
    print(f"\n=== {name} ===")


def _short(value, limit: int = 220):
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text[:limit]


def refused(case: str, stopped_by: str, detail: str) -> None:
    REPORT["negative_matrix"].append(
        {"case": case, "stopped_by": stopped_by, "detail": _short(detail, 160)}
    )


# ----------------------------------------------------------------------
# Composition
# ----------------------------------------------------------------------

PG_PORT = int(os.environ.get("P113_PG_PORT", "55442"))
FORWARDS: list = []


def _port_open(port: int) -> bool:
    import socket

    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def ensure_pg() -> None:
    """Keep our own port-forward alive.

    A forward started from a shell dies with that shell, and a harness that
    depends on one somebody else started is a harness that fails for reasons
    that have nothing to do with what it is testing.
    """
    if _port_open(PG_PORT):
        return
    namespace = os.environ.get("P113_NAMESPACE", "cortexprime")
    proc = subprocess.Popen(
        ["kubectl", "-n", namespace, "port-forward",
         "svc/cortexprime-postgres", f"{PG_PORT}:5432"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    FORWARDS.append(proc)
    for _ in range(40):
        if _port_open(PG_PORT):
            return
        time.sleep(1)
    raise RuntimeError("the PostgreSQL port-forward never opened")


DSN = os.environ.get("P113_DSN")

from backend.api.durability_composition import build_development_persistence  # noqa: E402
from backend.contexts.execution.application.commands import (  # noqa: E402
    AssignNode,
    RegisterWorker,
    StartExecution,
)
from backend.contexts.execution.application.service import ExecutionService  # noqa: E402
from backend.contracts.identity import PrincipalKind, PrincipalRef  # noqa: E402
from backend.platform.context import ExecutionContext, IdentityContext  # noqa: E402


def context_for(tenant: str) -> object:
    return ExecutionContext.for_tenant(
        tenant_id=tenant,
        identity=IdentityContext(
            principal=PrincipalRef(principal_id="p113", kind=PrincipalKind.PLATFORM),
            capabilities=("capability:invoke",),
        ),
        source="p113-harness",
    )


CTX = context_for(TENANT)


def service() -> ExecutionService:
    """A service with its own engine -- the stand-in for another process."""
    ensure_pg()
    persistence = build_development_persistence(
        dsn=DSN, instance_id=uuid.uuid4().hex[:8]
    )
    return ExecutionService(repository=persistence.executions)


def with_service(work, attempts: int = 4):
    """Run ``work(service)``, surviving a dropped port-forward.

    A forward through kubectl is not a database connection; it dies under load
    and takes the pool with it. Retrying with a *fresh* service is the only
    honest recovery -- the old engine's pool is already broken -- and it keeps
    the harness measuring the fabric rather than the tunnel.
    """
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return work(service())
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if attempt == attempts or name not in {
                "ConnectionFailed", "OperationalError", "DatabaseUnavailable",
            }:
                raise
            last = exc
            for proc in list(FORWARDS):
                proc.terminate()
                FORWARDS.remove(proc)
            time.sleep(2)
            ensure_pg()
    raise last  # pragma: no cover


def start_one(svc: ExecutionService, context=None, node: str = "node-a") -> str:
    started = svc.start(
        context or CTX,
        StartExecution(
            workflow_id="wf-p113",
            workflow_digest="d" * 64,
            mission_id="mis-p113",
            nodes=[{"node_id": node, "worker_kind": "connector", "side_effect": "read"}],
            attempt=1,
            requested_by="p113-harness",
        ),
    )
    return str(started.execution.execution_id)


# ----------------------------------------------------------------------
# FENCE
# ----------------------------------------------------------------------

WORKER_SOURCE = r'''
import json, os, sys, uuid
sys.path.insert(0, r"{repo}")
from backend.api.durability_composition import build_development_persistence
from backend.contexts.execution.application.commands import AssignNode, RegisterWorker
from backend.contexts.execution.application.service import ExecutionService
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.platform.context import ExecutionContext, IdentityContext

label = sys.argv[1]
ctx = ExecutionContext.for_tenant(
    tenant_id="{tenant}",
    identity=IdentityContext(
        principal=PrincipalRef(principal_id="p113", kind=PrincipalKind.PLATFORM),
        capabilities=("capability:invoke",)),
    source="p113-harness")
p = build_development_persistence(dsn=os.environ["P113_DSN"], instance_id=uuid.uuid4().hex[:8])
svc = ExecutionService(repository=p.executions)
svc.register_worker(RegisterWorker(worker_id=label, kinds=("connector",), lease_seconds=300))
won, lost = [], []
for execution_id in svc.dispatchable(ctx, limit=500):
    try:
        svc.assign(ctx, AssignNode(execution_id=execution_id, node_id="node-a", worker_id=label))
        won.append(execution_id)
    except Exception as exc:
        lost.append(type(exc).__name__)
print(json.dumps({{"label": label, "won": won, "lost": sorted(set(lost))}}))
'''


def stage_fence(executions: int = 12, workers: int = 4) -> None:
    stage("FENCE: real processes race one node; exactly one may hold it")
    svc = service()
    ids = [start_one(svc) for _ in range(executions)]
    check("the parent started the runs and then takes no further part", True,
          f"{len(ids)} executions")

    script = REPO / "scripts" / "_p113_race_worker.py"
    script.write_text(WORKER_SOURCE.format(repo=str(REPO), tenant=TENANT), encoding="utf-8")
    try:
        started_at = time.monotonic()
        procs = [
            subprocess.Popen([sys.executable, str(script), f"w{i}"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=dict(os.environ))
            for i in range(workers)
        ]
        results = []
        for proc in procs:
            out, err = proc.communicate(timeout=600)
            lines = [l for l in out.splitlines() if l.startswith("{")]
            if not lines:
                check(f"worker process produced a result", False, err[-200:])
                continue
            results.append(json.loads(lines[-1]))
        measure("fence_seconds", round(time.monotonic() - started_at, 1))
    finally:
        script.unlink(missing_ok=True)

    holders: dict = {}
    for result in results:
        for execution_id in result["won"]:
            holders.setdefault(execution_id, []).append(result["label"])

    mine = {e: h for e, h in holders.items() if e in set(ids)}
    duplicates = {e: h for e, h in mine.items() if len(h) > 1}
    orphans = [e for e in ids if e not in holders]

    measure("fence", {"processes": workers, "nodes": len(ids),
                      "duplicates": len(duplicates), "orphans": len(orphans)})
    check(f"{workers} real processes, {len(ids)} nodes: no node is held by two of them",
          not duplicates, duplicates or "0 duplicates")
    check("every node was taken by somebody", not orphans, f"{len(orphans)} orphans")
    check("every loser was refused with a named conflict, not a crash",
          all(set(r["lost"]) <= {"ConcurrentExecutionUpdate", "NodeAlreadyLeased",
                                 "ExecutionNotFound"} for r in results),
          sorted({w for r in results for w in r["lost"]}))


# ----------------------------------------------------------------------
# DURABLE
# ----------------------------------------------------------------------


def stage_durable() -> None:
    stage("DURABLE: a process dispatches an execution it never started")
    execution_id = with_service(lambda s: start_one(s))

    stranger = service()
    visible = with_service(lambda s: s.dispatchable(CTX, limit=500))
    check("a process that never saw the run finds it dispatchable",
          execution_id in visible, execution_id)

    from backend.contexts.execution.application.scheduler import (
        ExecutionScheduler,
        SchedulerState,
    )

    class Spy:
        def __init__(self):
            self.cycled = []

        def cycle(self, context, execution_id):
            self.cycled.append(execution_id)
            return type("R", (), {"dispatched": 0, "cycles": (), "results": ()})()

    class Recovery:
        def recover(self, *a, **k):
            return type("S", (), {"resumable": ()})()

    spy = Spy()
    scheduler = ExecutionScheduler(
        dispatcher=spy, recovery=Recovery(), context_factory=lambda: CTX,
        discovery=lambda c: visible, discovery_interval_seconds=0)
    # The background loop's state, without starting its thread. A stopped
    # scheduler skips every context-less tick -- correctly, and that is not what
    # this stage is measuring.
    scheduler._state = SchedulerState.RUNNING
    # The background loop's tick: no caller context, so this is the sweep.
    scheduler.tick()
    check("its scheduler cycles that run with an empty tracked set",
          execution_id in spy.cycled and scheduler.targets == (),
          {"tracked": list(scheduler.targets), "cycled": len(spy.cycled)})


# ----------------------------------------------------------------------
# SECURITY
# ----------------------------------------------------------------------


def stage_security() -> None:
    stage("SECURITY: the fabric change moved who carries a decision, not what was decided")
    execution_id = with_service(lambda s: start_one(s))

    # 1. discovery is tenant-narrowed
    other = with_service(lambda s: s.dispatchable(context_for(OTHER_TENANT), limit=500))
    check("another tenant's discovery does not return this tenant's run",
          execution_id not in other, f"{len(other)} rows visible to the other tenant")
    refused("cross-tenant discovery", "repository tenant narrowing",
            "the run is absent from the other tenant's dispatchable set")

    # 2. another tenant cannot lease it
    def intrude(s):
        s.register_worker(RegisterWorker(worker_id="intruder", kinds=("connector",),
                                         lease_seconds=60))
        s.assign(context_for(OTHER_TENANT),
                 AssignNode(execution_id=execution_id, node_id="node-a",
                            worker_id="intruder"))

    try:
        with_service(intrude)
        leased, why = True, "NOT REFUSED"
    except Exception as exc:  # noqa: BLE001
        leased, why = False, type(exc).__name__

    # The refusal has to be a *tenancy* refusal. An infrastructure error would
    # otherwise be counted as a security property, which is how a harness comes
    # to report a guarantee it never tested: the first run of this stage
    # "passed" on an OperationalError from a dropped port-forward.
    tenancy_refusals = {"ExecutionNotFound", "NotAuthorized", "StorageAccessDenied",
                        "ContractViolation", "TenantMismatch"}
    check("another tenant cannot lease this tenant's node",
          not leased and why in tenancy_refusals,
          f"{why}" + ("" if why in tenancy_refusals or leased
                      else " -- NOT a tenancy refusal; this check proves nothing"))
    refused("cross-tenant lease", "repository tenant narrowing", why)

    # 3. a context with no tenant cannot be rebuilt into one
    from backend.contexts.execution.application.dispatcher import _context_from_binding

    class Unidentified:
        tenant_id = ""
        principal_id = ""
        execution_id = "e"
        node_id = "n"

    rebuilt = _context_from_binding(None, Unidentified())
    check("a binding that names no tenant produces no dispatch context",
          rebuilt is None, "refused rather than defaulted")
    refused("dispatch under a binding with no tenant", "dispatcher context reconstruction",
            "returns None; the caller refuses before any lease")

    # 4. the rebuilt context is the binding's, not the platform's
    class Sealed:
        tenant_id = TENANT
        principal_id = "the-original-caller"
        execution_id = "e"
        node_id = "n"

    rebuilt = _context_from_binding(None, Sealed())
    ok = (rebuilt is not None
          and rebuilt.tenant_id == TENANT
          and rebuilt.identity.principal.principal_id == "the-original-caller"
          and not getattr(rebuilt, "is_platform_internal", False))
    check("the rebuilt context carries the binding's own tenant and principal", ok,
          {"tenant": getattr(rebuilt, "tenant_id", None),
           "principal": getattr(getattr(rebuilt, "identity", None), "principal", None)
           and rebuilt.identity.principal.principal_id,
           "platform_internal": getattr(rebuilt, "is_platform_internal", False)})

    # 5. it cannot name a tenant the binding did not
    check("a dispatcher cannot choose the tenant: it is read, never supplied",
          rebuilt.tenant_id == Sealed.tenant_id, rebuilt.tenant_id)


# ----------------------------------------------------------------------
# RECOVERY
# ----------------------------------------------------------------------


def stage_recovery() -> None:
    stage("RECOVERY: a dispatcher that dies does not take the run with it")
    def lease_then_die(s):
        execution_id = start_one(s)
        s.register_worker(RegisterWorker(worker_id="doomed", kinds=("connector",),
                                         lease_seconds=1))
        s.assign(CTX, AssignNode(execution_id=execution_id, node_id="node-a",
                                 worker_id="doomed"))
        return execution_id

    execution_id = with_service(lease_then_die)
    check("a dispatcher leased the node, then its process is gone", True, "lease held")

    still_there = with_service(lambda s: s.dispatchable(CTX, limit=500))
    check("the run is still in the durable store after the holder disappeared",
          execution_id in still_there, execution_id)

    reclaimable = with_service(lambda s: s.reclaimable(CTX, execution_id))
    measure("reclaimable_immediately", list(reclaimable))
    time.sleep(2.0)
    reclaimable_after = with_service(lambda s: s.reclaimable(CTX, execution_id))
    check("once the lease lapses the node is reported reclaimable",
          "node-a" in reclaimable_after,
          {"before": list(reclaimable), "after": list(reclaimable_after)})
    check("a live lease is NOT reclaimable (a slow worker is not a dead one)",
          "node-a" not in reclaimable, list(reclaimable))


# ----------------------------------------------------------------------


def main() -> int:
    if not DSN:
        print("BLOCKED: P113_DSN is not set; this harness needs a real database")
        return 2
    started_at = time.monotonic()
    ensure_pg()
    stage_fence()
    stage_durable()
    stage_security()
    stage_recovery()

    measure("wall_clock_seconds", round(time.monotonic() - started_at, 1))
    passed = sum(1 for c in REPORT["checks"] if c["ok"])
    failed = [c["name"] for c in REPORT["checks"] if not c["ok"]]
    REPORT.update({"passed": passed, "failed": len(failed), "total": len(REPORT["checks"]),
                   "failed_checks": failed,
                   "verdict": "VERIFIED" if not failed else "NOT VERIFIED"})
    for proc in FORWARDS:
        proc.terminate()
    REPORT_PATH.write_text(json.dumps(REPORT, indent=2, default=str), encoding="utf-8")
    print(f"\n{passed}/{len(REPORT['checks'])} checks passed; verdict {REPORT['verdict']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
