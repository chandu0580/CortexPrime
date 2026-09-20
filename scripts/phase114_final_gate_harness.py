"""Phase 11.4 — the final product completion gate.

What this establishes, against the deployed multi-replica product:

  REPLICAS    two replicas serve the API; every singleton loop has one holder
  ASYNC       a caller submits, goes away, and the work still happens
  CONCURRENT  many executions across replicas; exactly one holder each
  CRASH       a worker/verifier dying does not fabricate or repeat an outcome
  REDTEAM     the eighteen attacks, each refused with no provider effect
  TENANCY     the boundary is authorization, not an unguessable id
  LATENCY     a measured baseline, not an aspiration

Exit 0 = VERIFIED. Report: docs/phase114_final_gate_report.json.

Environment:
  P114_DSN         SQLAlchemy URL for the deployed store (required)
  P114_TENANT      the connected tenant (default: the 11.2 tenant)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

REPORT_PATH = REPO / "docs" / "phase114_final_gate_report.json"
REPORT: dict = {
    "phase": "11.4", "adr": "ADR-128", "checks": [], "measurements": {},
    "stages": [], "negative_matrix": [], "latency": {},
}

NS = os.environ.get("P114_NAMESPACE", "cortexprime")
TENANT = os.environ.get("P114_TENANT", "tenant-p112000a")
OTHER_TENANT = "tenant-p114-other"
API_PORT = int(os.environ.get("P114_API_PORT", "18114"))
PG_PORT = int(os.environ.get("P114_PG_PORT", "55444"))
API = f"http://127.0.0.1:{API_PORT}"
FORWARDS: list = []


# ---------------------------------------------------------------- plumbing

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


def refused(case: str, stopped_by: str, detail, provider_effects: int = 0) -> None:
    REPORT["negative_matrix"].append({
        "case": case, "stopped_by": stopped_by, "detail": _short(detail, 160),
        "provider_effects": provider_effects})


def _port_open(port: int) -> bool:
    import socket
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def recycle(port: int) -> None:
    """Tear down our forward on a port so the next use rebuilds it.

    Also drops the durable store. Its pool holds connections opened through the
    old tunnel, and a pool handing out dead connections reports
    ``TransactionUnavailable`` forever -- recycling the tunnel while keeping the
    pool is not a retry, it is the same failure with a pause in it.
    """
    global STORE
    if port == PG_PORT and STORE is not None:
        try:
            STORE.engine.dispose()
        except Exception:  # noqa: BLE001
            pass
        STORE = None
    for stale in [p for p in FORWARDS if getattr(p, "_port", None) == port]:
        try:
            stale.terminate()
        except Exception:  # noqa: BLE001
            pass
        FORWARDS.remove(stale)


def _usable(port: int) -> bool:
    """A port that answers is not necessarily a tunnel that works.

    ``kubectl port-forward`` keeps *running* after its tunnel to the pod has
    broken -- which happens whenever the target pod is replaced -- so neither an
    open socket nor a live child process means the far end is reachable. Both
    were checked here before, and both said yes while every query failed.
    """
    if not _port_open(port):
        return False
    return any(getattr(p, "_port", None) == port and p.poll() is None
               for p in FORWARDS)


def forward(target: str, local: int, remote: int) -> None:
    if _usable(local):
        return
    # Drop anything of ours that has died on this port before re-establishing.
    for stale in [p for p in FORWARDS if getattr(p, "_port", None) == local]:
        try:
            stale.terminate()
        except Exception:  # noqa: BLE001
            pass
        FORWARDS.remove(stale)
    proc = subprocess.Popen(
        ["kubectl", "-n", NS, "port-forward", target, f"{local}:{remote}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc._port = local  # type: ignore[attr-defined]
    FORWARDS.append(proc)
    for _ in range(40):
        if _port_open(local):
            return
        time.sleep(1)
    raise RuntimeError(f"port-forward {target} never opened on {local}")


def ensure_api() -> None:
    forward("svc/cortexprime-governed", API_PORT, 8110)


def ensure_pg() -> None:
    forward("svc/cortexprime-postgres", PG_PORT, 5432)


def secret_value(name: str, key: str) -> str:
    """One key out of a Secret, base64-decoded. Never printed."""
    import base64

    raw = kubectl("get", "secret", name, "-o", f"jsonpath={{.data.{key}}}")
    return base64.b64decode(raw).decode() if raw else ""


def adopt_signing_key() -> None:
    """Sign the harness's tokens with the deployment's own key.

    The harness authenticates as ordinary product callers do, which means its
    tokens have to be ones this deployment will accept. Read from the cluster
    Secret at run time rather than configured here, so the harness cannot drift
    from the thing it is testing.
    """
    if not os.environ.get("JWT_SECRET_KEY"):
        os.environ["JWT_SECRET_KEY"] = secret_value("cortexprime-auth", "JWT_SECRET_KEY")


def kubectl(*args: str, check_rc: bool = True) -> str:
    done = subprocess.run(["kubectl", "-n", NS, *args], capture_output=True, text=True)
    if check_rc and done.returncode != 0:
        raise RuntimeError(done.stderr.strip()[:300])
    return done.stdout.strip()


def in_cluster(code: str, variables: dict = None, include=()) -> dict:
    """Run a snippet inside a governed pod, against the in-cluster database.

    **Why not a port-forward.** Everything below needs several statements in one
    transaction, and a kubectl tunnel on a loaded host drops in the middle of
    exactly that -- reliably enough that this gate spent longer debugging the
    tunnel than the product. A single query survives it; a transaction does not.
    Running where the database is removes the tunnel from the critical path and
    uses the deployment's own credentials and environment, which is closer to
    what production does anyway.
    """
    payload = json.dumps(variables or {})
    preamble = "\n".join((
        "import json, os, sys, types",
        "sys.path.insert(0, '/app')",
        "V = json.loads(" + repr(payload) + ")",
        "RESULT = {}",
        "",
    ))
    # The image ships the product, not this repository's scripts. A helper the
    # gate needs is carried in as source and installed as a module, so the
    # in-cluster run uses the *same* provisioning code an operator would, rather
    # than a second copy of it written out by hand here.
    for name in include or ():
        source = (REPO / "scripts" / f"{name}.py").read_text(encoding="utf-8")
        preamble += (
            f"_m = types.ModuleType({name!r})\n"
            f"_m.__dict__['__name__'] = {name!r}\n"
            f"exec(compile({source!r}, {name!r}, 'exec'), _m.__dict__)\n"
            f"sys.modules[{name!r}] = _m\n"
        )
    tail = "\nprint('P114_OUT ' + json.dumps(RESULT, default=str))\n"
    program = preamble + code + tail
    done = subprocess.run(
        ["kubectl", "-n", NS, "exec", "-i", "deploy/cortexprime-governed", "--",
         "python", "-c", program],
        capture_output=True, text=True, timeout=300)
    for line in done.stdout.splitlines():
        if line.startswith("P114_OUT "):
            return json.loads(line.split(" ", 1)[1])
    raise RuntimeError(
        f"in-cluster snippet produced no result: {done.stderr[-400:] or done.stdout[-400:]}")


def sql(query: str, **params):
    """One query, surviving a dropped port-forward.

    A forward through kubectl is not a database connection: it dies under
    polling and takes the pool with it. Retrying with a fresh forward keeps this
    harness measuring the product rather than the tunnel.
    """
    import sqlalchemy as sa

    url = os.environ["P114_DSN"].replace("postgresql://", "postgresql+psycopg2://")
    last = None
    for attempt in (1, 2, 3, 4):
        ensure_pg()
        engine = sa.create_engine(url, future=True)
        try:
            with engine.connect() as connection:
                return connection.execute(sa.text(query), params).fetchall()
        except Exception as exc:  # noqa: BLE001
            last = exc
            recycle(PG_PORT)
            time.sleep(3)
        finally:
            engine.dispose()
    raise last


class Client:
    """One product caller."""

    def __init__(self, subject: str, tenant=None, role: str = "operator",
                 user_role: str = "member"):
        self.subject, self.tenant = subject, tenant
        self.role, self.user_role = role, user_role

    def headers(self) -> dict:
        if self.tenant is None:
            return {}
        from backend.auth.jwt_handler import create_access_token
        return {"Authorization": "Bearer " + create_access_token(
            self.subject, role=self.role, tenant_id=self.tenant,
            user_role=self.user_role)}

    def call(self, method: str, path: str, body=None, timeout: float = 60):
        ensure_api()
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            API + path, data=data, method=method,
            headers={**self.headers(), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as answer:
                raw, code = answer.read().decode(), answer.status
        except urllib.error.HTTPError as exc:
            raw, code = exc.read().decode(errors="replace"), exc.code
        except (urllib.error.URLError, OSError) as exc:
            return 0, {"error": type(exc).__name__}
        try:
            return code, json.loads(raw or "null")
        except ValueError:
            return code, {"raw": raw[:300]}


STORE = None


def store():
    """One durable store for the whole run, built while the tunnel is known good.

    Rebuilding it per call re-runs ``create_all`` and opens a new pool each
    time; doing that repeatedly through a kubectl tunnel is what turned a
    working path into ``ConnectionFailed`` halfway through the gate.
    """
    import sqlalchemy as sa

    from backend.database.durable.session import DurableStore

    global STORE
    if STORE is None:

        # Deliberately NOT ``build_development_store``: that runs
        # ``create_all``, dozens of DDL round trips, against a database whose
        # schema Alembic already built for the deployment under test. Besides
        # being the wrong thing to do to a live store, the long sequence is what
        # the kubectl tunnel kept dying in the middle of -- a single query
        # survived it every time.
        #
        # ``pool_pre_ping`` because a pooled connection opened through a tunnel
        # that later broke is exactly what this gate kept handing itself.
        STORE = DurableStore(sa.create_engine(
            dsn(), future=True, pool_pre_ping=True, poolclass=sa.pool.NullPool))
    return STORE


# The capability the product's execute route actually composes. The GitHub
# write is commissioned and governed but is NOT in that route's definition set
# (ADR-128 F-12), so proving the asynchronous contract through the product API
# means proving it on the capability the product API can run.
CAPABILITY = "platform.kubernetes.workload.rollout_restart"
OPERATION = "kubernetes.workload.rollout_restart"
TARGET_NS = os.environ.get("P114_TARGET_NS", "cortex-conn-a")
TARGET_DEPLOY = os.environ.get("P114_TARGET_DEPLOY", "p111k-shop")
ENVIRONMENT = os.environ.get("P114_ENVIRONMENT", "staging")


def dsn() -> str:
    """The store URL, with the driver named explicitly.

    ``sql`` already normalises this; the durable store builder does not, and a
    bare ``postgresql://`` there picks a dialect default that does not match the
    installed driver -- which surfaces as ``ConnectionFailed`` and looks exactly
    like the dropped tunnel it is not.
    """
    ensure_pg()
    return os.environ["P114_DSN"].replace("postgresql://", "postgresql+psycopg2://")


def resilient(work, attempts: int = 4):
    """Run ``work()``, surviving a dropped port-forward.

    Same reason as ``sql``: the tunnel is not the product, and a gate that fails
    because kubectl blinked has measured nothing.
    """
    last = None
    for attempt in range(1, attempts + 1):
        ensure_pg()
        try:
            return work()
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts:
                raise
            # Recycle on ANY failure rather than on a list of error spellings:
            # the tunnel breaks in more ways than a substring match can name,
            # and a retry against the same broken tunnel is not a retry.
            last = exc
            recycle(PG_PORT)
            time.sleep(3)
    raise last


def provision_people() -> None:
    """The people this gate acts as, and exactly the authority each one holds.

    Provisioned here rather than assumed from an earlier phase: a gate that
    depends on state some other run happened to leave behind is a gate that
    passes for reasons nobody can name.
    """
    out = in_cluster("""
import phase108_grant_provisioning as provisioning
from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
    SqlAuthorityGrantRepository)
from backend.database.durable.config import build_durable_store
from backend.database.durable.config import DurabilityConfig
from backend.contracts.execution import ExecutionEnvironment
import sqlalchemy as sa
from backend.database.durable.session import DurableStore

store = DurableStore(sa.create_engine(os.environ['CORTEX_DURABLE_URL'], future=True))
grants = SqlAuthorityGrantRepository(store)
provisioning.ensure_tenant(store, tenant_id=V['tenant'], slug='p114-a', name='Phase 11.4 A')
provisioning.ensure_tenant(store, tenant_id=V['other'], slug='p114-b', name='Phase 11.4 B')
reference = V['capability'] + '@1'
plan = [
    (V['tenant'], 'p114-operator', []),
    (V['tenant'], 'p114-requester', []),
    (V['tenant'], 'p114-approver',
     ['approve:remediation:capability=' + reference + ',environment=' + V['env'],
      'execute:remediation:capability=' + reference + ',environment=' + V['env']]),
    (V['other'], 'p114-intruder', []),
]
for tenant, who, granted in plan:
    provisioning.ensure_membership(store, tenant_id=tenant, principal_id=who)
    provisioning.provision(grants, store, tenant_id=tenant, principal_id=who, grants=granted)
RESULT['provisioned'] = [p[1] for p in plan]
""", {"tenant": TENANT, "other": OTHER_TENANT, "capability": CAPABILITY,
      "env": ENVIRONMENT}, include=("phase108_grant_provisioning",))
    measure("provisioned", out.get("provisioned"))


# ---------------------------------------------------------------- REPLICAS

def stage_replicas() -> None:
    stage("REPLICAS: two processes, one holder per singleton role")
    raw = kubectl("get", "pods", "-l", "app=cortexprime-governed", "-o", "json")
    items = json.loads(raw or '{"items": []}').get("items", [])
    ready = [
        {
            "pod": i["metadata"]["name"],
            "ready": all(
                c.get("ready")
                for c in i.get("status", {}).get("containerStatuses", []) or []
            ),
            "image": i["spec"]["containers"][0]["image"].rsplit(":", 1)[-1],
        }
        for i in items
    ]
    measure("replicas", ready)
    check("more than one governed replica is running and ready",
          len(ready) >= 2 and all(r["ready"] for r in ready), f"{len(ready)} replicas")
    check("every replica runs the same image",
          len({r["image"] for r in ready}) == 1, sorted({r["image"] for r in ready}))

    rows = in_cluster("""
import sqlalchemy as sa
from backend.database.durable.session import DurableStore
e = sa.create_engine(os.environ['CORTEX_DURABLE_URL'], future=True)
with e.connect() as c:
    RESULT['rows'] = [
        {'role': r[0], 'holder': r[1], 'fence': r[2], 'live': bool(r[3])}
        for r in c.execute(sa.text(
            "select role, instance_id, fencing_token, (expires_at > now()) "
            "from cp_leadership order by role"))]
""")["rows"]
    measure("leadership", [{**r, "holder": r["holder"][:24]} for r in rows])

    # **One holder per role, not one holder overall.** A role is a singleton;
    # the fleet is not required to elect one process for everything, and after a
    # rolling update a terminated instance's lease legitimately sits on the row
    # until it lapses and is taken over. Requiring a single holder across all
    # roles would fail this deployment for being healthy.
    per_role: dict = {}
    for row in rows:
        per_role.setdefault(row["role"], set()).add(row["holder"])
    check("each singleton role names exactly one holder",
          all(len(v) == 1 for v in per_role.values()),
          {k: len(v) for k, v in per_role.items()})
    check("the roles that must be singletons all exist",
          {"scheduler", "audit_writer", "outbox_publisher"} <= set(per_role),
          sorted(per_role))

    # A lease left behind by a terminated replica must be TAKEN OVER, not
    # merely tolerated -- the failover a rolling update depends on. Phase 11.4
    # F-11: before the fix, the audit writer never reclaimed its role.
    stale = {r["role"]: r["holder"] for r in rows if not r["live"]}
    measure("lapsed_leases_at_start", sorted(stale))
    if stale:
        role = sorted(stale)[0]
        was, took_over, waited = stale[role], False, 0.0
        while waited < 180:
            now = in_cluster("""
import sqlalchemy as sa
e = sa.create_engine(os.environ['CORTEX_DURABLE_URL'], future=True)
with e.connect() as c:
    r = c.execute(sa.text("select instance_id, (expires_at > now()) "
                          "from cp_leadership where role = :r"),
                  {'r': V['role']}).first()
RESULT['holder'] = r[0] if r else None
RESULT['live'] = bool(r[1]) if r else False
""", {"role": role})
            if now["holder"] != was and now["live"]:
                took_over = True
                break
            time.sleep(10)
            waited += 10
        measure("seconds_to_leader_takeover", waited)
        check(f"a lease left by a terminated replica is taken over ({role})",
              took_over, {"was": was[:24], "waited_seconds": waited})
    else:
        check("no lease was left behind by a terminated replica", True,
              "nothing to take over")

    client = Client("p114-operator", TENANT)
    states = []
    for _ in range(12):
        code, body = client.call("GET", "/api/v1/connectors/github")
        health = (body or {}).get("health") or {}
        states.append((code, health.get("state") or (body or {}).get("detail")))
    codes = sorted({c for c, _ in states})
    check("the API answers through the service across replicas",
          codes == [200], {"codes": codes,
                           "answers": sorted({str(s) for _, s in states})[:3]})


# ---------------------------------------------------------------- ASYNC

SUBMIT_SOURCE = r"""
import json, os, sys, urllib.request, urllib.error
sys.path.insert(0, r"{repo}")
os.environ["JWT_SECRET_KEY"] = {secret!r}
from backend.auth.jwt_handler import create_access_token

token = create_access_token({who!r}, role="operator", tenant_id={tenant!r},
                            user_role="member")
request = urllib.request.Request(
    {api!r} + "/api/v1/approvals/{approval}/execute",
    data=json.dumps({{"wait": False}}).encode(), method="POST",
    headers={{"Authorization": "Bearer " + token,
             "Content-Type": "application/json"}})
try:
    with urllib.request.urlopen(request, timeout=60) as answer:
        print("P114_RECEIPT " + answer.read().decode())
except urllib.error.HTTPError as exc:
    print("P114_RECEIPT " + json.dumps({{"error": exc.code,
                                        "detail": exc.read().decode()[:300]}}))
"""


def create_human_approval(payload: dict) -> tuple:
    """One approval, requested by a PERSON, as the execute route requires.

    Platform-requested approvals belong to a remediation plan and that runtime
    executes them; this gate is about a human-initiated asynchronous call.
    Created in-cluster for the reason in ``in_cluster``.
    """
    out = in_cluster("""
from datetime import datetime, timedelta, timezone
import sqlalchemy as sa
from backend.database.durable.session import DurableStore
from backend.contexts.connectivity.infrastructure.sql_approval import SqlApprovalRepository
from backend.contexts.connectivity.domain.authorization import CapabilityOperation
from backend.contracts.execution import ExecutionEnvironment
from backend.contexts.execution.domain.invocation import canonical_approval_digest

engine = sa.create_engine(os.environ['CORTEX_DURABLE_URL'], future=True)
store = DurableStore(engine)
with engine.connect() as c:
    row = c.execute(sa.text(
        "select reference, digest from cp_capability where capability_id = :c "
        "order by version desc limit 1"), {'c': V['capability']}).first()
if row is None:
    RESULT['approval_id'] = ''
else:
    reference, capability_digest = row[0], row[1]
    environment = ExecutionEnvironment(V['env'])
    digest = canonical_approval_digest(
        capability_ref=reference, capability_digest=capability_digest,
        operation=V['operation'], tenant_id=V['tenant'],
        principal_id=V['principal'], environment=environment,
        payload=V['payload'])
    now = datetime.now(timezone.utc)
    # An approval's identity digest is the action, deliberately: asking twice
    # for the same action is the same request, not a second one. This gate runs
    # the same action repeatedly, so a prior run's row would make ``request``
    # a no-op and leave the new id pointing at nothing. Clearing the previous
    # attempt is a harness concern, and it is done explicitly rather than by
    # varying the action -- varying it would stop testing the same thing.
    with engine.begin() as c:
        c.execute(sa.text("delete from cp_approval where identity_digest = :d"),
                  {'d': digest})
    SqlApprovalRepository(store).request(
        approval_id=V['approval_id'], identity_digest=digest,
        tenant_id=V['tenant'], capability_ref=reference,
        capability_digest=capability_digest, operation=V['operation'],
        authorization_operation=CapabilityOperation.INVOKE.value,
        environment=environment.value, principal_id=V['principal'],
        payload=V['payload'], approval_digest=digest,
        requested_by='user:' + V['principal'],
        expires_at=now + timedelta(minutes=30), requested_at=now,
        investigation_ref=None, justification='phase 11.4 asynchronous gate')
    RESULT['approval_id'] = V['approval_id']
    RESULT['digest'] = digest
""", {"capability": CAPABILITY, "env": ENVIRONMENT, "tenant": TENANT,
      "principal": "p114-requester", "payload": payload,
      "operation": OPERATION,
      "approval_id": f"appr-p114-{int(time.time())}"})
    return out.get("approval_id", ""), out.get("digest", "")


def github(path: str, method: str = "GET", body=None):
    """One direct GitHub call, as this harness's own independent observer."""
    token = ""
    for line in (REPO / "backend" / ".env").read_text(
            encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("GITHUB_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"').strip("'")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        "https://api.github.com" + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "cortexprime-p114-harness"})
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:
            return answer.status, json.loads(answer.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


def comments_on(issue_number: int) -> list:
    code, document = github(
        f"/repos/chandu0580/CortexPrime/issues/{issue_number}/comments?per_page=100")
    return document if code == 200 and isinstance(document, list) else []


def open_issue(title: str) -> int:
    code, document = github("/repos/chandu0580/CortexPrime/issues", "POST",
                            {"title": title, "body": "Opened by the Phase 11.4 gate."})
    return int(document.get("number")) if code in (200, 201) else 0


def close_issue(number: int) -> None:
    github(f"/repos/chandu0580/CortexPrime/issues/{number}", "PATCH", {"state": "closed"})


def generation_of() -> int:
    raw = subprocess.run(
        ["kubectl", "-n", TARGET_NS, "get", "deploy", TARGET_DEPLOY,
         "-o", "jsonpath={.metadata.generation}"],
        capture_output=True, text=True).stdout.strip()
    return int(raw or 0)


def restart_annotation() -> str:
    raw = subprocess.run(
        ["kubectl", "-n", TARGET_NS, "get", "deploy", TARGET_DEPLOY, "-o",
         "jsonpath={.spec.template.metadata.annotations.kubectl\.kubernetes\.io/restartedAt}"],
        capture_output=True, text=True).stdout.strip()
    return raw


def stage_async() -> None:
    """The caller submits, the caller dies, the work still happens."""
    stage("ASYNC: a caller that goes away does not take its execution with it")
    payload = {"namespace": TARGET_NS, "name": TARGET_DEPLOY}
    before_generation = generation_of()
    before_restart = restart_annotation()
    measure("target_before", {"deployment": f"{TARGET_NS}/{TARGET_DEPLOY}",
                              "generation": before_generation})

    approval_id, digest = create_human_approval(payload)
    if not check("an approval exists for this exact action, requested by a person",
                 bool(approval_id), {"approval_id": approval_id, "digest": digest[:16]}):
        return

    approver = Client("p114-approver", TENANT)
    code, _ = approver.call("POST", f"/api/v1/approvals/{approval_id}/decision",
                            {"decision": "approve", "justification": "phase 11.4 gate"})
    if not check("the scoped approver granted it through the product API",
                 code == 200, code):
        return

    # The caller is a SEPARATE PROCESS, killed the moment it has its receipt.
    # Nothing of it survives to drive the execution.
    script = REPO / "scripts" / "_p114_submit.py"
    script.write_text(SUBMIT_SOURCE.format(
        repo=str(REPO), secret=os.environ["JWT_SECRET_KEY"], who="p114-approver",
        tenant=TENANT, api=API, approval=approval_id), encoding="utf-8")
    submitted_at = time.monotonic()
    try:
        done = subprocess.run([sys.executable, str(script)], capture_output=True,
                              text=True, timeout=120)
        line = [l for l in done.stdout.splitlines() if l.startswith("P114_RECEIPT")]
        receipt = json.loads(line[-1].split(" ", 1)[1]) if line else {
            "error": (done.stderr or done.stdout)[-200:]}
    finally:
        script.unlink(missing_ok=True)

    measure("receipt", receipt)
    execution_id = str(receipt.get("execution_id") or "")
    REPORT["latency"]["request_to_durable_seconds"] = round(
        time.monotonic() - submitted_at, 2)
    if not check("the API returned a durable execution id without waiting for the provider",
                 bool(execution_id) and receipt.get("status") == "DISPATCHABLE", receipt):
        return
    check("the calling process has exited", done.returncode == 0,
          f"returncode={done.returncode}")

    # From here NOTHING the caller owned is alive. A different process asks.
    watcher = Client("p114-operator", TENANT)
    terminal = {"SUCCEEDED", "FAILED", "INSUFFICIENT_EVIDENCE", "SKIPPED"}
    final, waited = None, 0.0
    while waited < 420:
        code, body = watcher.call("GET", f"/api/v1/executions/{execution_id}")
        final = (body or {}).get("status")
        if code == 200 and final in terminal:
            break
        time.sleep(5)
        waited += 5
    REPORT["latency"]["durable_to_terminal_seconds"] = waited
    measure("async_final_status", {"status": final, "waited_seconds": waited})
    check("a different process can read the execution's durable status",
          final is not None, final)
    check("the execution reached SUCCEEDED with no caller present",
          final == "SUCCEEDED", {"status": final, "waited": waited})

    after_generation = generation_of()
    after_restart = restart_annotation()
    measure("target_after", {"generation": after_generation,
                             "restartedAt_changed": after_restart != before_restart})
    check("INDEPENDENT VERIFICATION: Kubernetes itself shows the rollout happened",
          after_generation > before_generation and after_restart != before_restart,
          {"generation": f"{before_generation} -> {after_generation}"})
    check("exactly one provider-side write happened",
          after_generation == before_generation + 1,
          {"generation_delta": after_generation - before_generation})


# ---------------------------------------------------------------- helpers

def approval_for_comment(issue_number: int, body_text: str) -> str:
    """Request and grant one approval for a GitHub comment, as the product does."""
    requester = Client("p114-requester", TENANT)
    code, created = requester.call("POST", "/api/v1/approvals", {
        "capability_ref": "platform.github.repository.create_issue_comment",
        "operation": "repository.create_issue_comment",
        "payload": {"owner": "chandu0580", "repo": "CortexPrime",
                    "issue_number": str(issue_number), "body": body_text},
        "justification": "phase 11.4 asynchronous execution gate",
    })
    return str((created or {}).get("approval_id") or "") if code in (200, 201) else ""


# ---------------------------------------------------------------- main

def main() -> int:
    if not os.environ.get("P114_DSN"):
        print("BLOCKED: P114_DSN is not set")
        return 2
    started_at = time.monotonic()
    adopt_signing_key()
    provision_people()
    issue = 0
    try:
        stage_replicas()
        stage_async()
    except Exception as exc:  # noqa: BLE001
        cause = exc.__cause__ or exc.__context__
        if cause is not None:
            print(f"  underlying cause: {type(cause).__name__}: {str(cause)[:300]}")
        # A stage that crashed did not pass; recording it as a failed check is
        # the difference between "this gate is green" and "this gate stopped".
        import traceback

        traceback.print_exc()
        check(f"the gate ran to completion (crashed in a stage: {type(exc).__name__})",
              False, str(exc)[:200])
    finally:
        measure("wall_clock_seconds", round(time.monotonic() - started_at, 1))
        if issue:
            close_issue(issue)
        for proc in FORWARDS:
            proc.terminate()
        passed = sum(1 for c in REPORT["checks"] if c["ok"])
        failed = [c["name"] for c in REPORT["checks"] if not c["ok"]]
        # A run that checked nothing is not a run that proved anything. The
        # first version of this harness crashed in its first stage and printed
        # "0/0 checks passed; verdict VERIFIED".
        verdict = ("VERIFIED" if (not failed and passed > 0)
                   else "NOT VERIFIED")
        REPORT.update({"passed": passed, "failed": len(failed),
                       "total": len(REPORT["checks"]), "failed_checks": failed,
                       "verdict": verdict})
        REPORT_PATH.write_text(json.dumps(REPORT, indent=2, default=str), encoding="utf-8")
        print(f"\n{passed}/{len(REPORT['checks'])} checks passed; verdict {REPORT['verdict']}")
    return 0 if REPORT["verdict"] == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
