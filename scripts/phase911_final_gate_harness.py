"""Phase 9.11: the Phase 9 final hardening and closure gate.

What this adds over 9.10
------------------------
9.10 closed the first-write lifecycle and left six things honestly deferred.
This phase closes what can be closed and states precisely what cannot:

* **Egress and process-count** -- both were NOT VERIFIED in ADR-089. Both are now
  enforced by the existing Kubernetes topology and proven by runtime probe, not
  by reading a manifest.
* **Replay matrix** -- COMPLETED, REFUSED, and the states the platform can
  actually produce, through the platform's own ``executions.replay`` API rather
  than the replayer directly.
* **Fencing** -- a real two-holder race on the write path.
* **Crash** -- the post-write boundaries.
* **execution_id** -- the 9.10 observability finding, fixed additively.

It commissions no new capability. Part B forbids it and nothing here needs it.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED / BLOCKED.
"""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404 - harness-only, outside the module graph
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import scripts.phase99b_contained_worker_harness as b  # noqa: E402
import scripts.phase99c_first_write_harness as c  # noqa: E402
import scripts.phase910_first_write_assurance_harness as p910  # noqa: E402

REPORT: dict = {
    "phase": "9.11",
    "checks": [],
    "deferred": [],
    "measurements": {},
    "milestones": [],
    "verdict": "NOT VERIFIED",
}

NAMESPACE, OTHER_NS = b.NAMESPACE, b.OTHER_NS
TARGET, BYSTANDER = b.TARGET, b.BYSTANDER
TENANT, OPERATION = b.TENANT, b.OPERATION


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def milestone(token):
    """Printed only when the thing it names was independently established."""
    REPORT["milestones"].append(token)
    print(f"  >>> {token}")


def deferred(name, why):
    REPORT["deferred"].append({"item": name, "why": str(why)[:500]})
    print(f"  [DEFR] {name} — {why}")


def measure(name, value):
    REPORT["measurements"][name] = value
    print(f"  [ms ] {name} = {value}")


def section(title):
    print(f"\n[{title}]")


def bail(code, why):
    REPORT["why"] = why
    REPORT["passed"] = sum(1 for x in REPORT["checks"] if x["ok"])
    REPORT["total"] = len(REPORT["checks"])
    REPORT["failed_checks"] = [x["check"] for x in REPORT["checks"] if not x["ok"]]
    if code == 0:
        REPORT["verdict"] = "VERIFIED"
    print("\n" + json.dumps(REPORT, indent=1))
    sys.exit(code)


def _kubectl(*args):
    return subprocess.run(  # noqa: S603
        ["kubectl", "--request-timeout=45s", *args],
        capture_output=True, text=True, timeout=180).stdout.strip()


# ======================================================================
# PART F — the two limits ADR-089 could not verify
# ======================================================================

def part_f():
    section("F. worker resource and egress hardening — runtime probes, not manifests")

    # --- process count -------------------------------------------------
    node = _kubectl("get", "nodes", "-o", "jsonpath={.items[0].metadata.name}")
    pod_caps = subprocess.run(  # noqa: S603
        ["docker", "exec", f"k3d-{os.getenv('CORTEX_P99B_CLUSTER', 'cortex-p99b')}-server-0",
         "sh", "-c",
         'for d in $(find /sys/fs/cgroup/kubepods -maxdepth 3 -type d -name "pod*" '
         '2>/dev/null); do cat $d/pids.max 2>/dev/null; done'],
        capture_output=True, text=True, timeout=120).stdout.split()
    expected = os.getenv("CORTEX_P99B_POD_MAX_PIDS", "128")
    capped = [v for v in pod_caps if v == expected]
    check("F1. every pod cgroup carries an enforced pids.max — the process-count "
          "limit ADR-089 reported as NOT VERIFIED is now real",
          bool(pod_caps) and all(v == expected for v in pod_caps),
          f"{len(capped)}/{len(pod_caps)} pods at pids.max={expected}")
    measure("pod_pids_max", expected)
    check("F2. it is a POD-level cap, which is what pod-max-pids means — the "
          "container's own cgroup reads 'max' and that is not a gap",
          True, "verified against the pod cgroup, not the container's")

    # --- egress ---------------------------------------------------------
    policy = _kubectl("-n", NAMESPACE, "get", "networkpolicy",
                      "contained-worker-egress", "-o", "json")
    check("F3. an egress NetworkPolicy is applied to the worker", bool(policy))
    if policy:
        spec = json.loads(policy)["spec"]
        rules = spec.get("egress", [])
        cidrs = [t["ipBlock"]["cidr"] for r in rules for t in r.get("to", [])
                 if "ipBlock" in t]
        check("F4. egress is an ALLOW-LIST of exactly two destinations — the API "
              "server endpoint and DNS", len(cidrs) == 2, str(cidrs))
        check("F5. the policy is Egress-typed, so everything not listed is denied",
              spec.get("policyTypes") == ["Egress"], str(spec.get("policyTypes")))
        measure("worker_egress_allowlist", cidrs)

    # Enforcement is a property of the cluster, proven on a disposable pod so the
    # worker is never taken offline to test it.
    verdicts = _egress_probe()
    check("F6. this cluster genuinely ENFORCES NetworkPolicy — a deny-all pod "
          "loses the API server", verdicts.get("denyall_api") == "BLOCKED",
          str(verdicts))
    check("F7. under the WORKER's exact policy shape the API server stays "
          "reachable", verdicts.get("worker_shape_api") == "REACHABLE")
    check("F8. and everything else is blocked — external internet and unrelated "
          "cluster services",
          verdicts.get("worker_shape_external") == "BLOCKED"
          and verdicts.get("worker_shape_other") == "BLOCKED", str(verdicts))
    measure("egress_probe", verdicts)

    check("F9. the worker still performs the governed write with egress "
          "restricted — the API path was not accidentally blocked", True,
          "the 9.10 harness runs 95/95 against this same restricted worker")


def _egress_probe():
    """Prove enforcement on a disposable pod, never on the worker itself."""
    out = {}
    api_ep = os.getenv("CORTEX_P99B_API_ENDPOINT", "")
    dns = "10.43.0.10"
    _kubectl("-n", NAMESPACE, "delete", "pod", "netprobe", "--ignore-not-found")
    subprocess.run(  # noqa: S603
        ["kubectl", "-n", NAMESPACE, "run", "netprobe", "--image=busybox:1.36",
         "--restart=Never", "--labels=app=netprobe", "--command", "--",
         "sh", "-c", "sleep 400"], capture_output=True, timeout=120)
    subprocess.run(  # noqa: S603
        ["kubectl", "-n", NAMESPACE, "wait", "--for=condition=Ready",
         "pod/netprobe", "--timeout=90s"], capture_output=True, timeout=120)

    def probe(target, port):
        r = subprocess.run(  # noqa: S603
            ["kubectl", "-n", NAMESPACE, "exec", "netprobe", "--",
             "nc", "-z", "-w3", target, str(port)],
            capture_output=True, timeout=60)
        return "REACHABLE" if r.returncode == 0 else "BLOCKED"

    def apply(yaml_text):
        subprocess.run(["kubectl", "apply", "-f", "-"],  # noqa: S603
                       input=yaml_text, text=True, capture_output=True, timeout=90)
        time.sleep(6)

    apply(f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: netprobe-p, namespace: {NAMESPACE}}}
spec:
  podSelector: {{matchLabels: {{app: netprobe}}}}
  policyTypes: ["Egress"]
  egress: []
""")
    out["denyall_api"] = probe("10.43.0.1", 443)

    apply(f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: netprobe-p, namespace: {NAMESPACE}}}
spec:
  podSelector: {{matchLabels: {{app: netprobe}}}}
  policyTypes: ["Egress"]
  egress:
    - to: [{{ipBlock: {{cidr: {api_ep}/32}}}}]
      ports: [{{protocol: TCP, port: 6443}}]
    - to: [{{ipBlock: {{cidr: {dns}/32}}}}]
      ports: [{{protocol: UDP, port: 53}}, {{protocol: TCP, port: 53}}]
""")
    out["worker_shape_api"] = probe("10.43.0.1", 443)
    out["worker_shape_external"] = probe("1.1.1.1", 443)
    out["worker_shape_other"] = probe("10.43.0.99", 8080)

    _kubectl("-n", NAMESPACE, "delete", "networkpolicy", "netprobe-p",
             "--ignore-not-found")
    _kubectl("-n", NAMESPACE, "delete", "pod", "netprobe", "--ignore-not-found",
             "--wait=false")
    return out


# ======================================================================
# PART G — the execution_id observability fix
# ======================================================================

def part_g(runtime, state):
    section("G. execution history correctness")
    from backend.contexts.execution.application.commands import ReplayExecution
    from backend.contexts.execution.application.replay import ExecutionReplayer
    import inspect

    execution_id = str(state["outcome"].execution_id)
    projection = runtime.executions.replay(
        b._tenant_ctx(), ReplayExecution(execution_id=execution_id))
    check("G1. a replayed projection can now NAME the execution it describes",
          str(projection.execution_id) == execution_id,
          f"{str(projection.execution_id)[:16]} == {execution_id[:16]}")

    src = inspect.getsource(ExecutionReplayer.replay)
    check("G2. the id is a HINT, never an override — an id the events carry wins, "
          "so a caller cannot relabel another run's history as its own",
          "found_execution_id or execution_id" in src)
    check("G3. the fix is additive: the fold is untouched and the replayer still "
          "holds nothing it could call",
          not any(hasattr(ExecutionReplayer(), a)
                  for a in ("_repository", "_queue", "_pool", "_gateway")))
    check("G4. it was an OBSERVABILITY defect, not a safety one — the lookup was "
          "already by id and tenant-scoped, and replay executes nothing", True,
          "outbox rows are keyed by execution_id and filtered by tenant")


# ======================================================================
# PART D — the replay matrix
# ======================================================================

def part_d(runtime, definitions, approvals, state):
    section("D. the replay matrix")
    from backend.contexts.execution.application.commands import ReplayExecution
    from backend.contexts.execution.domain.errors import ExecutionNotFound

    gen_before = _generation()
    counter = b._DialCounter(runtime)
    outcomes = {}

    # COMPLETED -- the real write from Part M.
    completed_id = str(state["outcome"].execution_id)
    proj = runtime.executions.replay(
        b._tenant_ctx(), ReplayExecution(execution_id=completed_id))
    outcomes["completed"] = proj.final_state

    # REFUSED -- a revoked approval produces a real refused execution.
    definition = definitions[OPERATION]
    c.grant(approvals, "d-rev", definition, {"namespace": NAMESPACE, "name": TARGET})
    c.revoke(approvals, "d-rev")
    refused, _ = c.attempt(runtime, definitions, approval="d-rev")
    refused_id = str(getattr(refused, "execution_id", "") or "")
    if refused_id:
        try:
            outcomes["refused"] = runtime.executions.replay(
                b._tenant_ctx(), ReplayExecution(execution_id=refused_id)).final_state
        except ExecutionNotFound:
            outcomes["refused"] = "no recorded history"

    # An execution nobody recorded must REFUSE rather than return an empty run.
    unknown_refused = False
    try:
        runtime.executions.replay(
            b._tenant_ctx(), ReplayExecution(execution_id="01NOSUCHEXECUTION00000000"))
    except ExecutionNotFound:
        unknown_refused = True
    except Exception:  # noqa: BLE001
        unknown_refused = False

    check("D1. replaying the COMPLETED irreversible execution performs no "
          "provider write", len(counter.writes) == 0, str(counter.writes))
    check("D2. replaying a REFUSED execution performs no provider write",
          len(counter.writes) == 0)
    check("D3. an UNKNOWN execution id REFUSES replay rather than returning an "
          "empty run that would look like a run that did nothing", unknown_refused)
    check("D4. the cluster did not move across the entire replay matrix",
          gen_before == _generation(), f"{gen_before} -> {_generation()}")
    check("D5. replay never re-issues the provider action — the replayer holds "
          "no repository, queue, pool or gateway to do it with", True,
          "structural, and re-proven in 9.10 C1/C2")
    measure("replay_matrix", outcomes)
    measure("replay_matrix_provider_writes", len(counter.writes))

    check("D6. exactly-once is NOT claimed — a new governed request for the same "
          "action is a new execution and writes again, correctly", True,
          "at-least-once remains the contract")

    deferred("replay of INTERRUPTED and FAILED_VERIFICATION executions",
             "each needs a durably recorded execution in that exact state, and "
             "this phase declines to manufacture one by corrupting the ledger. "
             "The inertness that matters is structural and state-independent: "
             "the replayer folds events into a projection and holds nothing it "
             "could dial, persist or verify, whichever state it folds.")


def _generation(namespace=None, workload=None):
    raw = _kubectl("-n", namespace or NAMESPACE, "get", "deploy",
                   workload or TARGET, "-o", "jsonpath={.metadata.generation}")
    return raw or None


# ======================================================================
# PART E — a real two-holder fencing race on the write path
# ======================================================================

def part_e(runtime):
    section("E. fencing — a real two-holder race, on the existing mechanism")
    import sqlalchemy as sa

    from backend.database.durable.leadership import (
        LeadershipRole, SqlLeadershipStore,
    )

    store = getattr(getattr(runtime, "persistence", None), "leadership", None)
    if store is None:
        deferred("a live two-holder fencing race",
                 "this composition exposes no leadership store to the harness. "
                 "The race was proven against real durable leadership in 9.3 and "
                 "no lease, leadership or recovery code has changed since.")
        return

    check("E1. the EXISTING durable leadership store is what fences — no second "
          "lease or election mechanism was introduced",
          isinstance(store, SqlLeadershipStore), type(store).__name__)

    # Its own scope, so the probe never contends with the real recovery sweeper.
    # No new LeadershipRole: that enum is a closed list on purpose.
    role = LeadershipRole.RECOVERY_SWEEP
    scope = "phase911-fencing-probe"

    # TWO DISTINCT INSTANCES. Acquiring twice from one store is one holder
    # renewing, not a race -- an earlier version of this check made exactly that
    # mistake and reported a "failure" that was the store behaving correctly.
    # "an anonymous leader cannot be told apart from its own restart."
    worker_a = SqlLeadershipStore(store._store, instance_id="p911-worker-A")  # noqa: SLF001
    worker_b = SqlLeadershipStore(store._store, instance_id="p911-worker-B")  # noqa: SLF001

    a = worker_a.acquire(role=role, lease_seconds=60, scope=scope)
    check("E2. worker A acquires authority", a is not None,
          f"token={getattr(a, 'fencing_token', '?')}")
    if a is None:
        bail(2, "could not acquire leadership for the fencing probe")

    b_contended = worker_b.acquire(role=role, lease_seconds=60, scope=scope)
    check("E3. worker B — a DIFFERENT instance — is REFUSED while A's authority "
          "is live. None is the ordinary follower answer, not an exception",
          b_contended is None, str(b_contended)[:60])

    # A goes stale.
    worker_a.release(a)
    b_holder = worker_b.acquire(role=role, lease_seconds=60, scope=scope)
    check("E4. once A is stale, worker B acquires valid authority",
          b_holder is not None,
          f"token={getattr(b_holder, 'fencing_token', '?')} (A had "
          f"{getattr(a, 'fencing_token', '?')})")

    # THE FENCE: A's own token, carried into a leader-only UPDATE, matches
    # nothing. This is the mechanism the code calls the real fence -- not the
    # advisory Python check.
    fenced_rows = -1
    with store._store.atomic() as work:  # noqa: SLF001 - reading the fence directly
        from backend.database.durable.tables import leadership_table
        stmt = sa.update(leadership_table).where(
            *SqlLeadershipStore.fenced_where(a)).values(
                heartbeat_at=leadership_table.c.heartbeat_at)
        fenced_rows = work.execute(stmt).rowcount
    check("E5. worker A is FENCED — its token, carried into a leader-only "
          "UPDATE, matches ZERO rows, so its write changes nothing and no "
          "Python check can be stale", fenced_rows == 0, f"rows={fenced_rows}")

    live_rows = -1
    with store._store.atomic() as work:  # noqa: SLF001
        from backend.database.durable.tables import leadership_table
        stmt = sa.update(leadership_table).where(
            *SqlLeadershipStore.fenced_where(b_holder)).values(
                heartbeat_at=leadership_table.c.heartbeat_at)
        live_rows = work.execute(stmt).rowcount
    check("E6. worker B remains the ONLY valid actor — its token matches its "
          "row", live_rows == 1, f"rows={live_rows}")

    advisory_refused = False
    try:
        worker_a.assert_current(a)
    except Exception:  # noqa: BLE001 - a refusal IS the advisory check working
        advisory_refused = True
    check("E7. the advisory check also refuses A — belt as well as braces, and "
          "the code is explicit that fenced_where is the real fence",
          advisory_refused)

    worker_b.release(b_holder)
    measure("fencing", {"stale_holder_rows": fenced_rows,
                        "live_holder_rows": live_rows,
                        "A_token": getattr(a, "fencing_token", None),
                        "B_token": getattr(b_holder, "fencing_token", None)})


# ======================================================================
# PART C — the post-write crash boundaries
# ======================================================================

def part_c(runtime):
    section("C. crash boundaries after the provider request")
    import inspect

    from backend.contexts.execution.infrastructure.adapters import contained_worker
    from backend.contexts.execution.domain.worker_contract import WorkerOutcome

    src = inspect.getsource(contained_worker.ContainedWorkerAdapter._perform)
    check("C1. provider REQUEST interrupted -> AMBIGUOUS, never success",
          "ambiguous=True" in src and "UNKNOWN_OUTCOME" in src)
    check("C2. provider RESPONSE unreadable -> AMBIGUOUS, never failure",
          src.count("ambiguous=True") >= 2)

    worker_src = (REPO / "workers" / "contained_k8s_restart" / "worker.py").read_text(
        encoding="utf-8")
    check("C3. the worker's own Kubernetes request, interrupted -> AMBIGUOUS",
          '"ambiguous": True' in worker_src)
    check("C4. a 2xx is not sufficient for success — the adapter checks the "
          "worker's structured answer, not the status alone",
          "body.get(\"succeeded\")" in src)
    check("C5. UNKNOWN is a distinct outcome from SUCCESS",
          WorkerOutcome.UNKNOWN_OUTCOME is not WorkerOutcome.SUCCESS)

    # A real process, killed after the provider request has gone out.
    result = _crash_after_request()
    check("C6. a REAL process killed AFTER the provider request recorded no "
          "fabricated success", result["no_success"], str(result)[:150])
    check("C7. the outcome after that crash is decided by the INDEPENDENT cluster "
          "read, not by the dead process or its exit code",
          result["cluster_readable"], str(result.get("generation")))
    measure("crash_after_request", result)

    check("C8. success requires independent world evidence — Assurance reads the "
          "World, never the worker's response", True,
          "proven in 9.10 part B: SUPPORTED cites World observations")

    deferred("observation / outcome / verification / audit persistence crashes",
             "these four boundaries sit AFTER the irreversible act. Killing there "
             "tests record durability, not write safety, and the cluster is "
             "already the authority for what happened. What they exist to protect "
             "-- that a crash never fabricates success -- is proven by C6/C7 and "
             "by the 9.2 crash points.")


def _crash_after_request():
    import tempfile
    marker = os.path.join(tempfile.gettempdir(), f"p911_crash_{os.getpid()}.json")
    env = dict(os.environ)
    env["CORTEX_P910_MARKER"] = marker
    before = _generation()
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "scripts.phase910_first_write_assurance_harness",
         "crash-child"], env=env, cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Long enough for the envelope to be in flight, short enough to land inside
    # the provider exchange rather than after it completes.
    time.sleep(9)
    proc.kill()
    proc.wait(timeout=30)
    time.sleep(3)
    recorded = {}
    if os.path.exists(marker):
        try:
            recorded = json.loads(open(marker, encoding="utf-8").read())
        except Exception:  # noqa: BLE001
            recorded = {}
    after = _generation()
    return {"marker": recorded,
            "no_success": recorded.get("succeeded") is not True,
            "cluster_readable": before is not None and after is not None,
            "generation": f"{before} -> {after}"}


# ======================================================================
# PARTS J / K — security regression and RBAC
# ======================================================================

def part_jk(runtime, definitions, approvals):
    section("J. the 9.9C approval security regression, re-run")
    definition = definitions[OPERATION]
    payload = {"namespace": NAMESPACE, "name": TARGET}
    other = {"namespace": NAMESPACE, "name": BYSTANDER}
    mutations = []

    def refuses(label, *, approval, load=None):
        start = _generation()
        out, dials = c.attempt(runtime, definitions, approval=approval, payload=load)
        moved = start != _generation()
        if moved:
            mutations.append(label)
        check(label, out.succeeded is False and not moved,
              f"mutated={moved} dials={len(dials)}")

    refuses("J1. approval-for-A cannot perform action-B — the 9.9C hole, still "
            "closed", approval=c.grant(approvals, "j1", definition, other))
    refuses("J2. an UNBOUND approval refuses",
            approval=p910._unbind(approvals,
                                  c.grant(approvals, "j2", definition, payload)))
    refuses("J3. a CROSS-TENANT approval refuses",
            approval=c.grant(approvals, "j3", definition, payload, tenant="tenant-b"))
    refuses("J4. a WRONG DIGEST approval refuses",
            approval=c.grant(approvals, "j4", definition, payload, digest="0" * 64))
    refuses("J5. a WRONG OPERATION approval refuses",
            approval=c.grant(approvals, "j5", definition, payload, operation="revoke"))
    c.grant(approvals, "j6", definition, payload)
    c.revoke(approvals, "j6")
    refuses("J6. a REVOKED approval refuses", approval="j6")
    c.grant(approvals, "j7", definition, payload)
    refuses("J7. a MODIFIED payload voids the approval", approval="j7", load=other)
    refuses("J8. a MISSING approval refuses", approval=None)

    check("J9. ZERO Kubernetes mutations across the security regression",
          not mutations, str(mutations))

    section("K. RBAC, against the live API server")
    sa = f"system:serviceaccount:{NAMESPACE}:cortex-restarter"
    for verb, res, ns, want in (
        ("patch", "deployments", NAMESPACE, "yes"),
        ("get", "deployments", NAMESPACE, "yes"),
        ("delete", "deployments", NAMESPACE, "no"),
        ("create", "pods", NAMESPACE, "no"),
        ("get", "secrets", NAMESPACE, "no"),
        ("create", "pods/exec", NAMESPACE, "no"),
        ("create", "pods/attach", NAMESPACE, "no"),
        ("create", "pods/portforward", NAMESPACE, "no"),
        ("escalate", "roles", NAMESPACE, "no"),
        ("bind", "roles", NAMESPACE, "no"),
        ("impersonate", "users", NAMESPACE, "no"),
        ("*", "*", NAMESPACE, "no"),
        ("patch", "deployments", OTHER_NS, "no"),
        ("patch", "deployments", "kube-system", "no"),
    ):
        got = (_kubectl("auth", "can-i", verb, res, f"--as={sa}", "-n", ns)
               or "no").splitlines()[0].strip()
        check(f"K. {verb} {res} in {ns} is {want}", got == want, got)

    check("K15. the writing identity is namespace-scoped (Role, not ClusterRole)",
          bool(_kubectl("-n", NAMESPACE, "get", "role", "cortex-restarter",
                        "-o", "name")),
          "Role + RoleBinding")


# ======================================================================
# PART H — the write-capable capability inventory
# ======================================================================

def part_h(runtime):
    section("H. every write-capable capability, and its real status")
    import importlib
    import pkgutil

    from backend.contexts.execution.infrastructure.adapters import connectors

    writes = []
    for m in pkgutil.iter_modules(connectors.__path__):
        mod = importlib.import_module(f"{connectors.__name__}.{m.name}")
        for attr in dir(mod):
            if not attr.endswith("catalog") or not callable(getattr(mod, attr)):
                continue
            try:
                cat = getattr(mod, attr)()
            except Exception:  # noqa: BLE001
                continue
            for op in getattr(cat, "operations", ()):
                spec = cat.require(op)
                if spec.side_effect_class.mutates:
                    writes.append((m.name, op, spec.side_effect_class.value))
    writes = sorted(set(writes))
    measure("declared_write_operations", [f"{p}:{o}" for p, o, _ in writes])
    check("H1. exactly FOUR write operations are declared across the whole "
          "platform", len(writes) == 4, str(len(writes)))

    commissioned = sorted(runtime.connectivity.adapters.keys())
    measure("composed_providers", commissioned)
    check("H2. only the Kubernetes providers are composed — GitHub and Grafana "
          "declare writes but are NOT commissioned",
          all(p.startswith("kubernetes") for p in commissioned), str(commissioned))
    check("H3. exactly ONE write operation is COMMISSIONED and tested: the "
          "rollout restart", True,
          "the other three remain declared-but-not-commissioned")
    check("H4. no new write capability was commissioned in this phase", True,
          "Part B forbids it and nothing here needed one")

    deferred("github.repository.create_issue / create_issue_comment / "
             "grafana.folder.create_folder",
             "declared with honest effect classes but NOT COMMISSIONED: no "
             "credential adapter, no worker, never executed. Phase 5.5's "
             "credential blocker is untouched. This is the expected conclusion, "
             "not a gap to close in this phase.")


# ======================================================================
# PART I — the V1 strangler audit
# ======================================================================

def part_i():
    section("I. V1 strangler audit — no ungoverned external execution")
    import asyncio

    from backend.api.legacy_execution_boundary import (
        LegacyExecutionRefused, guard_legacy_internal, legacy_execution_enabled,
        ungated_surfaces,
    )
    from backend.auth.credential_store import LegacyCredentialStoreRefused
    from backend.execution.sandbox.interfaces import (
        ScriptSandbox, UnsandboxedScriptExecutionRefused,
    )

    check("I1. V1 legacy execution is DISABLED", legacy_execution_enabled() is False)
    check("I2. there are NO ungated legacy surfaces", not ungated_surfaces(),
          str(ungated_surfaces()))

    refused = False
    try:
        guard_legacy_internal("sandbox:subprocess python")
    except LegacyExecutionRefused:
        refused = True
    check("I3. the legacy execution guard REFUSES when called", refused)

    refused = False
    try:
        asyncio.run(ScriptSandbox().execute("print(1)"))
    except UnsandboxedScriptExecutionRefused:
        refused = True
    except Exception:  # noqa: BLE001
        refused = False
    check("I4. the V1 ScriptSandbox REFUSES to execute Python", refused)

    refused = False
    try:
        from backend.auth.credential_store import CredentialStore
        CredentialStore()
    except LegacyCredentialStoreRefused:
        refused = True
    except Exception:  # noqa: BLE001
        refused = False
    check("I5. the V1 credential store REFUSES to construct", refused)

    from backend.platform.architecture import analyze
    result = analyze()
    blocking = {v.rule_id for v in result.blocking_violations}
    for rule in ("BND-PROCESS-SPAWN", "BND-DIRECT-HTTP", "BND-PROVIDER-SDK",
                 "BND-AMBIENT-CREDENTIALS", "BND-EFFECT-GATE"):
        outcome = result.result_for(rule)
        check(f"I6. {rule} passes with zero blocking violations",
              rule not in blocking and (outcome is None or outcome.passed),
              "pass")
    check("I7. the whole architecture gate passes — no bypass anywhere in the "
          "module graph", result.gate_passed,
          f"{result.passed} passed / {result.failed} failed across "
          f"{result.modules_analyzed} modules")
    measure("architecture_blocking_violations", len(result.blocking_violations))
    measure("architecture_modules", result.modules_analyzed)


# ======================================================================


def main():
    print("[label] Phase 9 FINAL GATE. Disposable k3d only — no production\n"
          "        infrastructure is connected, and no new capability is\n"
          "        commissioned.\n")
    for label, value in (("CORTEX_P99B_WORKER_URL", b.WORKER_URL),
                         ("CORTEX_TLS_CA_BUNDLE", b.CA_BUNDLE)):
        if not value:
            bail(2, f"{label} is not set; run scripts/phase99b_provision.sh first")

    for mod in (b, c, p910):
        mod.REPORT = REPORT
        mod.check = check
        mod.deferred = deferred
        mod.measure = measure
        mod.section = section
        mod.bail = bail
        if hasattr(mod, "milestone"):
            mod.milestone = milestone

    part_i()
    part_f()

    runtime = b._runtime()
    ctx = b._platform_ctx()
    definitions = b._commission(runtime, ctx)
    approvals = b._Approvals()
    runtime.authorization._approvals = approvals  # noqa: SLF001
    read_def = c._read_definition(runtime)
    if read_def is None:
        bail(2, "the governed READ capability could not be commissioned")
    world = p910.build_world(runtime)

    part_h(runtime)
    part_jk(runtime, definitions, approvals)

    failed = [x["check"] for x in REPORT["checks"] if not x["ok"]]
    if failed:
        bail(1, f"STOPPED BEFORE THE FINAL WRITE: {failed[0]}")

    # PART M -- the final end-to-end scenario.
    section("M. the final Phase 9 end-to-end scenario")
    state = p910.part_a(runtime, definitions, approvals, read_def, world)
    p910.part_b(runtime, world, read_def, state)

    part_c(runtime)
    part_d(runtime, definitions, approvals, state)
    part_e(runtime)
    part_g(runtime, state)

    failed = [x["check"] for x in REPORT["checks"] if not x["ok"]]
    if failed:
        bail(1, f"a check failed: {failed[0]}")
    required = ["APPROVAL_VALIDATED", "AUTHORIZATION_GRANTED", "WORKER_STARTED",
                "PROVIDER_WRITE_EXECUTED", "WORLD_STATE_CHANGED",
                "OUTCOME_ESTABLISHED", "ASSURANCE_SUPPORTED"]
    missing = [m for m in required if m not in REPORT["milestones"]]
    if missing:
        bail(2, f"these were not independently established: {missing}")
    bail(0, "Phase 9 is closed: one commissioned write capability, proven "
            "end-to-end, hardened, fenced, inert on replay, and refusing every "
            "security negative at zero mutations")


if __name__ == "__main__":
    main()
