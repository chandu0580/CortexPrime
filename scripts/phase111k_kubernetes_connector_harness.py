"""Phase 11.1-K (ADR-125) -- the Kubernetes reference connector, proven as installed.

Nothing here runs CortexPrime in-process. The product is installed the way an
operator installs it -- ``helm upgrade --install`` of helm/cortexprime-governed
into a disposable k3d cluster, against a TLS PostgreSQL and a TLS Vault -- and
is then exercised only through what an operator or user has: the product API
(over a port-forward), the metrics endpoint, the cluster, Vault and the
database. Ground truth for "did anything happen" is always the external
system: the Deployment's generation and template, Vault's lease table, the
API server's own authorization answers.

Stages (``CORTEX_P111K_STAGES``, default all, in order):
  INSTALL    helm install (migrations as a pre-install Job), tenants, members
  CONNECT    health CONNECTED through the API, commissioning, capability contracts
  CREDS      credentials come from Vault per action; no static token anywhere
  RBAC       least privilege, asked of the API server itself
  TENANCY    tenant B sees no connection; cannot read A's namespace; A cannot reach B's
  INCIDENT   real bad rollout -> detection -> investigation -> plan -> human approval ->
             contained rollback with a Vault-minted token -> independent verification
  FAILURES   RoleBinding removed, Vault role removed, Vault down, worker down,
             misconfiguration refused at start -- each named by health, each recovered
  OBSERVE    metrics scrape (connector health, rate limiter), audit rows, secret scans

Usage:
    bash scripts/phase99b_provision.sh (once); bash scripts/phase111k_provision.sh
    python scripts/phase111k_kubernetes_connector_harness.py
Exit 0 = VERIFIED. Report: docs/phase111k_kubernetes_connector_report.json.
No credential value is printed, logged or written to the report.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import scripts.phase113_detection_investigation_harness as p113  # noqa: E402

KUBECONFIG = str(REPO / ".phase99b" / "kubeconfig")
HELM = os.environ.get("HELM", str(Path.home() / "bin" / "helm.exe"))
REL_NS = "cortexprime"
CONN_NS = "cortex-conn-a"
OTHER_NS = "cortex-conn-b"
RELEASE = "cortexprime"
CHART = str(REPO / "helm" / "cortexprime-governed")
TENANT_A = "tenant-p111k0000a"
TENANT_B = "tenant-p111k0000b"
API_PORT, METRICS_PORT, PG_PORT = 18111, 19111, 15441
API = f"http://127.0.0.1:{API_PORT}"
REPORT_PATH = REPO / "docs" / "phase111k_kubernetes_connector_report.json"
STAGES = [s.strip() for s in (os.environ.get("CORTEX_P111K_STAGES")
          or "INSTALL,CONNECT,CREDS,RBAC,TENANCY,INCIDENT,FAILURES,OBSERVE,EVALUATE").split(",") if s.strip()]
APP = "p111k-shop"
ROLLBACK_REF = "platform.kubernetes.deployment.rollback@1"
READ_PERMISSIONS = 7
SHIPPED = 10
IMAGE_TAG = os.environ.get("CORTEX_P111K_IMAGE_TAG", "1.0.0-b3")

REPORT: dict = {"phase": "11.1-K", "adr": "ADR-125", "checks": [], "measurements": {},
                "negative_matrix": [], "failure_injections": [], "stages": STAGES}
PASSED: list = []
FAILED: list = []
FORWARDS: list = []
STATE: dict = {}


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def check(name: str, ok: bool, detail: str = "") -> bool:
    (PASSED if ok else FAILED).append(name)
    REPORT["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(f"[{'OK ' if ok else 'FAIL'}] {name}" + (f"  -- {str(detail)[:360]}" if detail else ""), flush=True)
    return bool(ok)


def measure(name: str, value) -> None:
    REPORT["measurements"][name] = value
    print(f"[MEAS] {name} = {json.dumps(value, default=str)[:360]}", flush=True)


def negative(case: str, stopped_by: str, detail: str, writes: int) -> bool:
    REPORT["negative_matrix"].append({"case": case, "stopped_by": stopped_by,
                                      "detail": str(detail)[:300], "cluster_writes": writes})
    return check(f"{case} -> refused by {stopped_by} ({writes} cluster writes)", writes == 0, detail)


def finish(code: int, why: str = "") -> None:
    if why:
        REPORT["blocked"] = why
        print(f"\nBLOCKED: {why}", flush=True)
    for proc in FORWARDS:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
    REPORT["passed"], REPORT["failed"] = len(PASSED), len(FAILED)
    REPORT["total"] = len(PASSED) + len(FAILED)
    REPORT["failed_checks"] = list(FAILED)
    REPORT["verdict"] = "NOT VERIFIED" if why else ("FAILED" if FAILED else "VERIFIED")
    REPORT_PATH.write_text(json.dumps(REPORT, indent=1, default=str), encoding="utf-8")
    print(f"\n{REPORT['passed']}/{REPORT['total']} checks passed; verdict {REPORT['verdict']}", flush=True)
    if FAILED:
        print("FAILED: " + " | ".join(FAILED), flush=True)
    sys.exit(0 if REPORT["verdict"] == "VERIFIED" else (2 if why else 1))


# ---------------------------------------------------------------------------
# the operator's tools: kubectl, helm, vault (inside its pod), a port-forward
# ---------------------------------------------------------------------------

def kenv() -> dict:
    return dict(os.environ, KUBECONFIG=KUBECONFIG)


def kubectl(*args: str, timeout: int = 90, check_rc: bool = True, stdin: str | None = None) -> str:
    r = subprocess.run(["kubectl", "--request-timeout=60s", *args], capture_output=True, text=True,
                       timeout=timeout, env=kenv(), input=stdin)
    if check_rc and r.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args[:4])} failed: {r.stderr[-400:]}")
    return r.stdout


def kjson(*args: str) -> dict:
    out = kubectl(*args, "-o", "json", check_rc=False)
    try:
        return json.loads(out or "{}")
    except ValueError:
        return {}


def can_i(sa_ns: str, sa: str, verb: str, resource: str, namespace: str) -> bool:
    # "deployments/scale" is a SUBRESOURCE here; kubectl would read "TYPE/NAME"
    # (a Deployment named "scale") and answer a different question (run 9).
    extra = []
    if "/" in resource:
        resource, sub = resource.split("/", 1)
        extra = [f"--subresource={sub}"]
    r = subprocess.run(["kubectl", "--request-timeout=30s", "auth", "can-i", verb, resource, *extra,
                        "-n", namespace, f"--as=system:serviceaccount:{sa_ns}:{sa}"],
                       capture_output=True, text=True, timeout=60, env=kenv())
    return r.stdout.strip() == "yes"


def helm(*args: str, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run([HELM, *args], capture_output=True, text=True, timeout=timeout, env=kenv())


def vault(*args: str, check_rc: bool = False) -> str:
    pod = kubectl("-n", "vault", "get", "pod", "-l", "app=vault", "-o", "jsonpath={.items[0].metadata.name}")
    r = subprocess.run(["kubectl", "--request-timeout=30s", "-n", "vault", "exec", pod, "--", "env",
                        "VAULT_ADDR=http://127.0.0.1:8201", "VAULT_TOKEN=root", "vault", *args],
                       capture_output=True, text=True, timeout=90, env=kenv())
    if check_rc and r.returncode != 0:
        raise RuntimeError(f"vault {args[0]} failed: {r.stderr[-300:]}")
    return r.stdout


def secret_value(namespace: str, name: str, key: str) -> str:
    """A Secret's value, in memory only. Never printed."""
    raw = kubectl("-n", namespace, "get", "secret", name, "-o", f"jsonpath={{.data.{key}}}")
    return base64.b64decode(raw).decode()


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def forward(target: str, local: int, remote: int, namespace: str = REL_NS) -> None:
    for proc in list(FORWARDS):
        if getattr(proc, "_p111k_local", None) == local:
            proc.kill()
            FORWARDS.remove(proc)
    time.sleep(0.5)
    proc = subprocess.Popen(["kubectl", "-n", namespace, "port-forward", target, f"{local}:{remote}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=kenv())
    proc._p111k_local = local  # type: ignore[attr-defined]
    FORWARDS.append(proc)
    if not p113.wait_for(lambda: _port_open(local), timeout=40, interval=1):
        raise RuntimeError(f"port-forward {target} {local}:{remote} did not open")


def forward_runtime() -> None:
    forward("svc/cortexprime-governed", API_PORT, 8110)
    forward("svc/cortexprime-governed", METRICS_PORT, 9102)


# ---------------------------------------------------------------------------
# the product API, as its users see it (real HTTP)
# ---------------------------------------------------------------------------

class Client:
    def __init__(self, subject: str, tenant: str | None):
        self.subject, self.tenant = subject, tenant

    def headers(self) -> dict:
        if self.tenant is None:
            return {}
        from backend.auth.jwt_handler import create_access_token
        return {"Authorization": "Bearer " + create_access_token(
            self.subject, role="operator", tenant_id=self.tenant, user_role="member")}

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 60):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(API + path, data=data, method=method,
                                     headers={**self.headers(), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                code = resp.status
        except urllib.error.HTTPError as exc:
            raw, code = exc.read().decode(errors="replace"), exc.code
        except (urllib.error.URLError, OSError) as exc:
            return 0, {"error": type(exc).__name__}
        try:
            return code, json.loads(raw)
        except ValueError:
            return code, {"raw": raw[:300]}

    def get(self, path: str):
        return self.call("GET", path)

    def post(self, path: str, body: dict):
        return self.call("POST", path, body)


def api_get_resilient(client: Client, path: str):
    code, body = client.get(path)
    if code == 0:                       # port-forward died (pod restart): re-open once
        try:
            forward_runtime()
        except RuntimeError:
            return 0, {}
        code, body = client.get(path)
    return code, body


def connector(client: Client) -> dict:
    code, body = api_get_resilient(client, "/api/v1/connectors/kubernetes")
    return body if code == 200 else {"_code": code, **(body if isinstance(body, dict) else {})}


def health_state(client: Client) -> str:
    return (connector(client).get("health") or {}).get("state", "?")


def wait_health_after(client: Client, want: set, after: str, timeout: float = 400) -> dict:
    """A health snapshot taken AFTER ``after`` (ISO-8601), in one of ``want``.

    The probe reviews permissions one at a time, so a snapshot that straddles an
    RBAC change legitimately reports a partial answer; the test must read a
    check that began after the change had propagated (record run).
    """
    def fresh():
        body = connector(client)
        health = body.get("health") or {}
        if health.get("state") in want and str(health.get("checked_at") or "") > after:
            return body
        return None
    return p113.wait_for(fresh, timeout=timeout, interval=5) or connector(client)


def wait_health(client: Client, want: set, timeout: float = 240) -> dict:
    result = p113.wait_for(lambda: (lambda c: c if (c.get("health") or {}).get("state") in want else None)(
        connector(client)), timeout=timeout, interval=5)
    return result or connector(client)


def metrics_text() -> str:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{METRICS_PORT}/metrics", timeout=20) as resp:
            return resp.read().decode()
    except Exception:  # noqa: BLE001
        forward_runtime()
        with urllib.request.urlopen(f"http://127.0.0.1:{METRICS_PORT}/metrics", timeout=20) as resp:
            return resp.read().decode()


def runtime_pod() -> str:
    return kubectl("-n", REL_NS, "get", "pod", "-l", "app=cortexprime-governed",
                   "--field-selector=status.phase=Running", "-o", "jsonpath={.items[*].metadata.name}",
                   check_rc=False).split(" ")[0].strip()


def runtime_logs(since: str = "30m") -> str:
    pod = runtime_pod()
    return kubectl("-n", REL_NS, "logs", pod, f"--since={since}", check_rc=False, timeout=120) if pod else ""


def wait_runtime_ready(timeout: int = 420) -> bool:
    def ready():
        pods = kjson("-n", REL_NS, "get", "pod", "-l", "app=cortexprime-governed").get("items", [])
        live = [p for p in pods if not p["metadata"].get("deletionTimestamp")]
        return len(live) == 1 and all(cs.get("ready") for p in live
                                      for cs in (p.get("status") or {}).get("containerStatuses") or [])
    ok = bool(p113.wait_for(ready, timeout=timeout, interval=5))
    if ok:
        forward_runtime()
    return ok


def restart_runtime() -> bool:
    kubectl("-n", REL_NS, "rollout", "restart", "deploy/cortexprime-governed")
    time.sleep(5)
    return wait_runtime_ready()


# ---------------------------------------------------------------------------
# the database (operator's provisioning path)
# ---------------------------------------------------------------------------

def dsn() -> str:
    password = (REPO / ".phase111k" / "pg.password").read_text(encoding="utf-8").strip()
    return f"postgresql://cortex:{password}@127.0.0.1:{PG_PORT}/cortexprime?sslmode=require"


def ensure_pg() -> None:
    """kubectl port-forward drops under TLS connection churn; re-open it when it has."""
    if not _port_open(PG_PORT):
        forward("svc/cortexprime-postgres", PG_PORT, 5432)


def sql(query: str, **params):
    import sqlalchemy as sa
    ensure_pg()
    for attempt in (1, 2):
        eng = sa.create_engine(dsn().replace("postgresql://", "postgresql+psycopg2://"), future=True)
        try:
            with eng.connect() as c:
                return c.execute(sa.text(query), params).fetchall()
        except sa.exc.OperationalError:
            if attempt == 2:
                raise
            # A listening forward whose tunnel died: re-open it and try once more.
            forward("svc/cortexprime-postgres", PG_PORT, 5432)
        finally:
            eng.dispose()


def provision_people() -> None:
    import scripts.phase108_grant_provisioning as provisioning
    from backend.contexts.connectivity.infrastructure.sql_authority_grant import SqlAuthorityGrantRepository
    from backend.database.durable.config import build_development_store

    ensure_pg()
    store = build_development_store(dsn=dsn())
    grants = SqlAuthorityGrantRepository(store)
    provisioning.ensure_tenant(store, tenant_id=TENANT_A, slug="p111k-a", name="Phase 11.1-K tenant A")
    provisioning.ensure_tenant(store, tenant_id=TENANT_B, slug="p111k-b", name="Phase 11.1-K tenant B")
    for tenant, who, g in (
            (TENANT_A, "p111k-alice", []),
            (TENANT_A, "p111k-approver", [f"approve:remediation:capability={ROLLBACK_REF},environment=production",
                                          f"execute:remediation:capability={ROLLBACK_REF},environment=production"]),
            (TENANT_B, "p111k-mallory", []),
            (TENANT_B, "p111k-b-approver",
             [f"approve:remediation:capability={ROLLBACK_REF},environment=production"])):
        provisioning.ensure_membership(store, tenant_id=tenant, principal_id=who)
        provisioning.provision(grants, store, tenant_id=tenant, principal_id=who, grants=g)


# ---------------------------------------------------------------------------
# INSTALL
# ---------------------------------------------------------------------------

def helm_values(**overrides) -> list:
    values = {
        "connection.tenant": TENANT_A, "connection.namespace": CONN_NS, "connection.clusterRef": "k3d-cortex-p99b",
        "database.existingSecret": "cortexprime-db",
        "vault.address": "https://vault.vault.svc:8200", "vault.caSecret": "vault-ca",
        "model.provider": "openai-compatible", "model.name": STATE.get("model_name", ""),
        "model.existingSecret": "cortexprime-model", "model.allowPlaintextHttp": "true",
        "health.intervalSeconds": "30",
        "image.tag": IMAGE_TAG,
    }
    values.update(overrides)
    out = []
    for key, value in values.items():
        out += ["--set-string" if key.startswith("rateLimit.") or key in ("model.name", "image.tag") else "--set",
                f"{key}={value}"]
    return out


def helm_install(**overrides) -> subprocess.CompletedProcess:
    return helm("upgrade", "--install", RELEASE, CHART, "-n", REL_NS, "--wait", "--timeout", "12m",
                *helm_values(**overrides))


def stage_install() -> None:
    section("INSTALL: one helm install, against an existing PostgreSQL and Vault")
    for ns in (REL_NS, "vault", CONN_NS, OTHER_NS):
        if not kubectl("get", "ns", ns, check_rc=False).strip():
            finish(2, f"namespace {ns} missing: run scripts/phase111k_provision.sh")
    if not Path(HELM).exists():
        finish(2, f"helm not found at {HELM} (set HELM)")

    hosted = p113.hosted_provider_env()
    if not (hosted.get("LLM_API_KEY") and hosted.get("LLM_BASE_URL")):
        finish(2, "backend/.env has no LLM_API_KEY/LLM_BASE_URL for the operator's model")
    STATE["model_name"] = hosted.get("LLM_MODEL", "")
    manifest = json.dumps({"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
                           "metadata": {"name": "cortexprime-model", "namespace": REL_NS},
                           "stringData": {"LLM_API_KEY": hosted["LLM_API_KEY"],
                                          "LLM_BASE_URL": hosted["LLM_BASE_URL"]}})
    kubectl("apply", "-f", "-", stdin=manifest)      # through stdin: never on a command line or disk
    check("model credential delivered as a Kubernetes Secret through stdin (never printed, never on disk)", True)

    started = time.time()
    result = helm_install()
    measure("helm_install_seconds", round(time.time() - started, 1))
    if not check("helm upgrade --install --wait succeeded (migrations Job, workers, runtime, Redis)",
                 result.returncode == 0, (result.stderr or result.stdout)[-500:]):
        print(runtime_logs("15m")[-4000:])
        for job in kubectl("-n", REL_NS, "get", "pod", "-o", "name", check_rc=False).split():
            if "migrate" in job:
                print(kubectl("-n", REL_NS, "logs", job, "--tail=30", check_rc=False)[-3000:])
                break
        finish(2, "the chart did not install")
    status = json.loads(helm("status", RELEASE, "-n", REL_NS, "-o", "json").stdout or "{}")
    check("release deployed", (status.get("info") or {}).get("status") == "deployed",
          (status.get("info") or {}).get("status"))
    wait_runtime_ready()

    forward("svc/cortexprime-postgres", PG_PORT, 5432)
    heads = sql("SELECT version_num FROM alembic_version")
    check("schema migrated by the chart's pre-install Job (alembic_version present)", bool(heads),
          [h[0] for h in heads])
    try:
        provision_people()
    except Exception:  # noqa: BLE001 - one retry after re-opening a dropped forward
        time.sleep(3)
        provision_people()
    check("tenants A and B and their members provisioned durably", True)

    objects = kubectl("get", "deploy,svc,sa,role,rolebinding,networkpolicy,secret,configmap", "-n", CONN_NS,
                      "-l", "app.kubernetes.io/instance=" + RELEASE, "-o", "name", check_rc=False).split()
    measure("objects_in_connected_namespace", objects)
    check("workers, ServiceAccounts, Roles and egress policy created in the connected namespace",
          any("deployment" in o for o in objects) and any("role" in o for o in objects), len(objects))
    other = kubectl("get", "all,sa,role,rolebinding", "-n", OTHER_NS, "-l",
                    "app.kubernetes.io/instance=" + RELEASE, "-o", "name", check_rc=False).split()
    check("nothing installed in a namespace that is not connected", not other, other)


# ---------------------------------------------------------------------------
# CONNECT
# ---------------------------------------------------------------------------

def stage_connect() -> None:
    section("CONNECT: health, commissioning, capability contracts -- through the product API")
    os.environ["JWT_SECRET_KEY"] = secret_value(REL_NS, "cortexprime-auth", "JWT_SECRET_KEY")
    forward_runtime()
    alice = Client("p111k-alice", TENANT_A)
    code, _ = Client("anonymous", None).get("/api/v1/connectors")
    check("no credential -> the connector API refuses (401)", code == 401, code)
    for path in ("/healthz", "/readyz"):
        req = urllib.request.Request(API + path)
        with urllib.request.urlopen(req, timeout=20) as resp:
            check(f"{path} answers 200", resp.status == 200, resp.status)

    started = time.time()
    body = wait_health(alice, {"CONNECTED"}, timeout=300)
    measure("seconds_to_connected_after_ready", round(time.time() - started, 1))
    health = body.get("health") or {}
    if not check("health CONNECTED, read through the product API as the connection's tenant",
                 health.get("state") == "CONNECTED", json.dumps(health)[:500]):
        print(runtime_logs("10m")[-6000:])
    measure("health", health)
    report = body.get("commissioning") or {}
    measure("commissioning", report)
    usable = set(report.get("available") or ())
    check(f"all {SHIPPED} shipped capabilities commissioned at boot, zero conflicts or failures",
          len(usable) == SHIPPED and not report.get("conflicts") and not report.get("failed"),
          {k: report.get(k) for k in ("available", "conflicts", "failed", "skipped")})
    caps = {c["id"]: c for c in body.get("capabilities", [])}
    check("every capability publishes its contract (description, schema, permissions, risk, retry, "
          "timeout, verification)",
          len(caps) == SHIPPED and all(c.get("description") and c.get("input_schema") is not None
                                       and c.get("risk") and c.get("retry") and c.get("timeout_seconds")
                                       and c.get("verification") for c in caps.values()),
          sorted(caps))
    writes = {k: v for k, v in caps.items() if v.get("effect") == "write"}
    check("exactly two writes: rollback and rollout_restart, both NEVER-retry",
          sorted(writes) == ["platform.kubernetes.deployment.rollback",
                             "platform.kubernetes.workload.rollout_restart"]
          and all(v.get("retry") == "never" for v in writes.values()),
          {k: v.get("retry") for k, v in writes.items()})
    check("reads are SAFE-retry and carry their provider permission",
          all(v.get("retry") == "safe" for k, v in caps.items() if k not in writes)
          and all(v.get("required_permissions") for k, v in caps.items()
                  if k not in writes and k != "platform.kubernetes.access.review"))
    check("no arbitrary API / shell / raw-request capability exists",
          not any(t in k for k in caps for t in ("raw", "exec", "shell", "apply", "delete", "request")),
          sorted(caps))
    code, listing = alice.get("/api/v1/connectors")
    rows = {c["id"]: c for c in listing.get("connectors", [])}
    check("the connector list shows one line per connector with state and a one-line summary",
          code == 200 and rows.get("kubernetes", {}).get("state") == "CONNECTED"
          and rows["kubernetes"].get("summary"), rows.get("kubernetes"))

    rows = sql("SELECT capability_id, version, status, trust FROM cp_capability "
               "WHERE capability_id LIKE 'platform.kubernetes.%' ORDER BY capability_id") \
        if _has_table("cp_capability") else []
    if rows:
        measure("registry_rows", [list(r) for r in rows])
    before = len(rows)
    ok = restart_runtime()
    after_body = wait_health(alice, {"CONNECTED"}, timeout=300)
    report2 = after_body.get("commissioning") or {}
    check("restart: commissioning is idempotent (already current, no new registry rows, no conflicts)",
          ok and not report2.get("conflicts") and len(report2.get("already_current") or ()) >= SHIPPED - 2
          and (not rows or len(sql("SELECT capability_id FROM cp_capability WHERE capability_id LIKE "
                                   "'platform.kubernetes.%'")) == before),
          {k: len(report2.get(k) or ()) for k in ("commissioned", "already_current", "conflicts")})


def _has_table(name: str) -> bool:
    return bool(sql("SELECT 1 FROM information_schema.tables WHERE table_name = :n", n=name))


# ---------------------------------------------------------------------------
# CREDS
# ---------------------------------------------------------------------------

def vault_leases(role: str) -> list:
    out = vault("list", "-format=json", f"sys/leases/lookup/kubernetes/creds/{role}")
    try:
        return json.loads(out or "[]")
    except ValueError:
        return []


def stage_creds() -> None:
    section("CREDS: every Kubernetes credential is minted by Vault, per action, short-lived")
    dep = kjson("-n", REL_NS, "get", "deploy", "cortexprime-governed")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    names = {e["name"] for e in container.get("env", [])}
    cm = kjson("-n", REL_NS, "get", "configmap", "cortexprime-governed").get("data", {})
    static = {"VAULT_TOKEN", "CORTEX_KUBERNETES_TOKEN", "CORTEX_ROLLBACK_WORKER_TOKEN",
              "CORTEX_RESTART_WORKER_TOKEN", "KUBECONFIG"}
    check("runtime carries no Vault token and no Kubernetes token (env or config)",
          not (static & (names | set(cm))), sorted(static & (names | set(cm))))
    check("credentials mode is vault; Vault auth is the pod's own ServiceAccount identity",
          cm.get("CORTEX_KUBERNETES_CREDENTIALS") == "vault" and cm.get("CORTEX_VAULT_AUTH_ROLE"), cm.get(
              "CORTEX_VAULT_AUTH_ROLE"))
    reader = vault_leases("cortexprime-reader")
    measure("vault_reader_leases", len(reader))
    check("Vault's lease table shows reader tokens minted for this connection", len(reader) >= 1, len(reader))
    for sa in ("cortexprime-reader", "cortexprime-rollbacker", "cortexprime-restarter"):
        obj = kjson("-n", CONN_NS, "get", "sa", sa)
        check(f"{sa}: no long-lived token Secret, automount off",
              not obj.get("secrets") and obj.get("automountServiceAccountToken") is False,
              {"secrets": obj.get("secrets"), "automount": obj.get("automountServiceAccountToken")})
    token_secrets = [s["metadata"]["name"] for s in kjson("-n", CONN_NS, "get", "secret").get("items", [])
                     if s.get("type") == "kubernetes.io/service-account-token"]
    check("no service-account-token Secret exists in the connected namespace", not token_secrets, token_secrets)
    lease = vault("read", "-format=json", "kubernetes/roles/cortexprime-reader")
    try:
        ttl = json.loads(lease)["data"]["token_default_ttl"]
    except (ValueError, KeyError):
        ttl = None
    measure("vault_reader_token_ttl_seconds", ttl)
    check("reader tokens are short-lived (<= 10 minutes default)", ttl is not None and int(ttl) <= 600, ttl)


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

def stage_rbac() -> None:
    section("RBAC: least privilege, as the API server itself answers it")
    sa = ("cortexprime", "cortexprime-governed")
    check("the runtime's own identity holds NO Kubernetes permission in the connected namespace",
          not any(can_i(*sa, v, r, CONN_NS) for v, r in (("list", "pods"), ("get", "deployments"),
                                                          ("patch", "deployments"), ("get", "secrets"))))
    reader = (CONN_NS, "cortexprime-reader")
    allowed = {f"{v} {r}": can_i(*reader, v, r, CONN_NS) for v, r in (
        ("list", "pods"), ("get", "pods"), ("watch", "pods"), ("get", "pods/log"), ("list", "events"),
        ("get", "deployments.apps"), ("list", "replicasets.apps"))}
    allowed["get pods/log"] = can_i(*reader, "get", "pods/log", CONN_NS)
    check("reader: exactly the seven read permissions its capabilities declare", all(allowed.values()), allowed)
    denied = {f"{v} {r}": can_i(*reader, v, r, CONN_NS) for v, r in (
        ("patch", "deployments.apps"), ("delete", "pods"), ("get", "secrets"), ("create", "pods/exec"),
        ("list", "configmaps"), ("create", "pods"))}
    check("reader: no write, no secrets, no exec, no configmaps", not any(denied.values()), denied)
    check("reader: nothing at all in another namespace",
          not any(can_i(*reader, v, r, OTHER_NS) for v, r in (("list", "pods"), ("get", "deployments.apps"))))
    check("reader: no cluster-scoped reads", not can_i(*reader, "list", "nodes", CONN_NS)
          and not can_i(*reader, "list", "namespaces", CONN_NS))
    rb = (CONN_NS, "cortexprime-rollbacker")
    check("rollbacker: get+patch deployments, list replicasets",
          can_i(*rb, "patch", "deployments.apps", CONN_NS) and can_i(*rb, "list", "replicasets.apps", CONN_NS))
    check("rollbacker: no delete, no create, no scale, no secrets, no other namespace",
          not any((can_i(*rb, "delete", "deployments.apps", CONN_NS), can_i(*rb, "create", "deployments.apps",
                                                                             CONN_NS),
                   can_i(*rb, "patch", "deployments.apps/scale", CONN_NS), can_i(*rb, "get", "secrets", CONN_NS),
                   can_i(*rb, "patch", "deployments.apps", OTHER_NS))))
    rs = (CONN_NS, "cortexprime-restarter")
    check("restarter: patch deployments only, nothing in another namespace",
          can_i(*rs, "patch", "deployments.apps", CONN_NS) and not can_i(*rs, "list", "replicasets.apps", CONN_NS)
          and not can_i(*rs, "patch", "deployments.apps", OTHER_NS))
    vsa = ("vault", "vault")
    check("Vault may mint tokens ONLY for the three CortexPrime ServiceAccounts (not the namespace default)",
          not can_i(*vsa, "create", "serviceaccounts/token", OTHER_NS)
          and _vault_mint_scope_ok(), "resourceNames-scoped Role")
    crb = [b["metadata"]["name"] for b in kjson("get", "clusterrolebinding").get("items", [])
           if any((s.get("namespace") in (REL_NS, CONN_NS)) for s in b.get("subjects") or [])]
    check("no ClusterRoleBinding for any CortexPrime identity (no cluster-admin, nothing cluster-wide)",
          not crb, crb)


def _vault_mint_scope_ok() -> bool:
    role = kjson("-n", CONN_NS, "get", "role", "-l", "app.kubernetes.io/instance=" + RELEASE)
    for item in role.get("items", []):
        for rule in item.get("rules", []):
            if "serviceaccounts/token" in (rule.get("resources") or []):
                return sorted(rule.get("resourceNames") or []) == sorted(
                    ["cortexprime-reader", "cortexprime-rollbacker", "cortexprime-restarter"])
    return False


# ---------------------------------------------------------------------------
# TENANCY
# ---------------------------------------------------------------------------

def stage_tenancy() -> None:
    section("TENANCY: a namespace is not a tenant; a connection binds them")
    mallory = Client("p111k-mallory", TENANT_B)
    body = connector(mallory)
    health = body.get("health") or {}
    check("tenant B: the Kubernetes connector reports DISABLED (it has no connection)",
          health.get("state") == "DISABLED", health)
    text = json.dumps(body)
    check("tenant B learns nothing about A's connection (no namespace, cluster, tenant id)",
          CONN_NS not in text and TENANT_A not in text and "k3d-cortex-p99b" not in text,
          [t for t in (CONN_NS, TENANT_A, "k3d-cortex-p99b") if t in text])
    code, listing = mallory.get("/api/v1/connectors")
    check("tenant B's connector list shows DISABLED",
          code == 200 and all(c.get("state") == "DISABLED" for c in listing.get("connectors", [])), listing)
    code, plans = mallory.get("/api/v1/remediation/plans?limit=50")
    check("tenant B sees none of tenant A's plans", code == 200 and not plans.get("plans"), code)
    forged = Client("p111k-mallory", TENANT_A)
    code, _ = forged.get("/api/v1/connectors/kubernetes")
    check("a B member presenting A's tenant claim is refused (no membership of A)", code in (401, 403), code)

    # The gateway layer: the platform's own tenancy check, driven in-process against the
    # SAME contract (the running pod's input stage is the same code; the pod-level proof is
    # that B has no connection and no credential binding at all).
    from backend.api.connector_scope import ConnectionScope, ConnectionScopes, ConnectionScopeValidator

    class _Inner:
        def validate(self, binding, payload):
            return ()

    class _B:
        def __init__(self, tenant, provider):
            self.tenant_id, self.provider = tenant, provider

    validator = ConnectionScopeValidator(_Inner(), ConnectionScopes([ConnectionScope(
        tenant_id=TENANT_A, providers=frozenset({"kubernetes", "kubernetes-contained-rollback"}),
        targets=frozenset({CONN_NS}))]))
    for tenant, ns, want_refused, label in ((TENANT_A, OTHER_NS, True, "A -> B's namespace"),
                                            (TENANT_B, CONN_NS, True, "B -> A's namespace"),
                                            (TENANT_A, CONN_NS, False, "A -> its own namespace")):
        problems = validator.validate(_B(tenant, "kubernetes"), {"namespace": ns})
        refused, why = bool(problems), ("; ".join(problems) or "admitted")
        if want_refused:
            negative(f"cross-tenant target {label}", "gateway input stage (connection scope)", why, 0)
        else:
            check(f"{label} admitted by the connection scope", not refused, why)
    # The provider layer, independently: even A's own reader credential cannot reach B.
    check("provider layer: A's reader credential is refused in B's namespace by RBAC",
          not can_i(CONN_NS, "cortexprime-reader", "list", "pods", OTHER_NS))


# ---------------------------------------------------------------------------
# INCIDENT
# ---------------------------------------------------------------------------

APP_FLAG = "p111k-flagged"
FLAG_CONFIG = "p111k-flag-config"
FLAG_HEALTHY = ('[ -n "$FLAG" ] || { echo "FATAL: required configuration FLAG is not set"; exit 1; }; '
                'echo "shop v2 ready (flag set)"; while true; do sleep 5; done')


def app_manifest(command: str, name: str = APP, flag_configmap: str | None = None) -> str:
    env = ""
    if flag_configmap:
        env = ("\n          env:\n            - name: FLAG\n              valueFrom:\n"
               f"                configMapKeyRef: {{name: {flag_configmap}, key: flag, optional: true}}")
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: {CONN_NS}
  labels: {{app: {name}}}
spec:
  replicas: 1
  revisionHistoryLimit: 10
  strategy: {{type: Recreate}}
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata:
      labels: {{app: {name}}}
    spec:
      terminationGracePeriodSeconds: 1
      containers:
        - name: app
          image: busybox:1.36
          imagePullPolicy: IfNotPresent
          command: ["sh", "-c", {json.dumps(command)}]{env}
          resources:
            requests: {{cpu: 5m, memory: 8Mi}}
            limits: {{cpu: 100m, memory: 32Mi}}
"""


def truth(name: str = APP) -> dict:
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import pod_template_digest

    dep = kjson("-n", CONN_NS, "get", "deploy", name)
    meta, spec, status = dep.get("metadata") or {}, dep.get("spec") or {}, dep.get("status") or {}
    pods = kjson("-n", CONN_NS, "get", "pods", "-l", f"app={name}").get("items", [])
    live = [p for p in pods if not p["metadata"].get("deletionTimestamp")]
    crash = any(((cs.get("state") or {}).get("waiting") or {}).get("reason") in ("CrashLoopBackOff", "Error")
                or ((cs.get("restartCount") or 0) >= 1 and not cs.get("ready"))
                for p in live for cs in (p.get("status") or {}).get("containerStatuses") or [])
    return {"generation": meta.get("generation"),
            "revision": (meta.get("annotations") or {}).get("deployment.kubernetes.io/revision"),
            "template": pod_template_digest(spec["template"]) if spec.get("template") else None,
            "available": status.get("availableReplicas", 0) or 0, "crash_looping": crash,
            "rolled_back_by": (meta.get("annotations") or {}).get("cortexprime.io/rolled-back-by-action")}


def plans(client: Client, name: str = APP) -> list:
    code, body = api_get_resilient(client, "/api/v1/remediation/plans?limit=200")
    return [p for p in body.get("plans", []) if (p.get("target") or {}).get("name") == name] if code == 200 else []


def plan_detail(client: Client, plan_id: str) -> dict:
    code, body = api_get_resilient(client, f"/api/v1/remediation/plans/{plan_id}")
    return body if code == 200 else {}


def stages_of(detail: dict) -> list:
    return [e.get("stage") for e in (detail or {}).get("events", [])]


def stage_incident() -> None:
    section("INCIDENT: a real bad rollout, remediated end to end by the installed product")
    alice, approver = Client("p111k-alice", TENANT_A), Client("p111k-approver", TENANT_A)
    kubectl("-n", CONN_NS, "delete", "deploy", APP, "--ignore-not-found", "--wait=true")
    p113.kubectl_apply = None  # never used against the wrong cluster namespace by accident
    kubectl("apply", "-f", "-", stdin=app_manifest(p113.HEALTHY_COMMAND))
    if not p113.wait_for(lambda: truth()["available"] >= 1 and not truth()["crash_looping"], timeout=300,
                         interval=5):
        finish(2, f"{APP} never became healthy")
    healthy = truth()
    measure("healthy_revision", healthy)
    time.sleep(90)       # the fabric observes the healthy revision running (detection needs a baseline)
    leases_before = len(vault_leases("cortexprime-rollbacker"))
    earlier_plans = {p["plan_id"] for p in plans(alice)}      # a previous run's plans are not this incident's
    kubectl("apply", "-f", "-", stdin=app_manifest(p113.BAD_REVISION_COMMAND))
    broke_at = time.time()
    if not p113.wait_for(lambda: truth()["crash_looping"], timeout=240, interval=5):
        finish(2, "the bad revision did not crash-loop")
    bad = truth()
    measure("bad_revision", bad)
    check("the bad revision really crash-loops on the cluster", bad["crash_looping"] and
          bad["template"] != healthy["template"], bad)

    def pending_approval():
        code, body = api_get_resilient(approver, "/api/v1/approvals?status=pending&limit=50")
        items = [i for i in body.get("items", []) if i.get("workload") == APP] if code == 200 else []
        return items[0] if items else None
    item = p113.wait_for(pending_approval, timeout=1500, interval=10)
    measure("seconds_failure_to_approval_request", round(time.time() - broke_at, 1))
    if not check("detection -> investigation -> plan -> an approval request reached the human queue",
                 item is not None, item):
        print(runtime_logs("40m")[-8000:])
        finish(1, "no approval request was produced")
    STATE["approval_id"] = item["approval_id"]
    measure("approval_request", {k: item.get(k) for k in ("approval_id", "workload", "capability", "risk",
                                                           "action", "summary")})
    p = [x for x in plans(alice) if x["plan_id"] not in earlier_plans]
    check("the plan is visible to the tenant with its evidence-backed target", bool(p), [x.get("plan_id") for x in p])
    check("nothing was written before approval (template still the bad revision)",
          truth()["template"] == bad["template"] and truth()["generation"] == bad["generation"])

    # Separation of duties: the tenant member without approve authority cannot approve.
    code, _ = alice.post(f"/api/v1/approvals/{item['approval_id']}/decision",
                         {"decision": "approve", "confirm_workload": APP, "justification": "i want it"})
    negative("approval by a member without approve authority", "approval authority", f"HTTP {code}",
             0 if truth()["generation"] == bad["generation"] else 1)
    code, _ = Client("p111k-b-approver", TENANT_B).post(
        f"/api/v1/approvals/{item['approval_id']}/decision",
        {"decision": "approve", "confirm_workload": APP, "justification": "cross tenant"})
    negative("approval by another tenant's approver", "tenant boundary", f"HTTP {code}",
             0 if truth()["generation"] == bad["generation"] else 1)

    code, decision = approver.post(f"/api/v1/approvals/{item['approval_id']}/decision",
                                   {"decision": "approve", "confirm_workload": APP,
                                    "justification": "reviewed the plan preview: roll back to the healthy revision"})
    approved_at = time.time()
    check("the scoped approver approved through the product API", code in (200, 201, 202), f"HTTP {code}")

    def closed():
        for plan in plans(alice):
            if plan["plan_id"] in earlier_plans:
                continue
            detail = plan_detail(alice, plan["plan_id"])
            if "closed" in stages_of(detail):
                return detail
        return None
    detail = p113.wait_for(closed, timeout=900, interval=10)
    measure("seconds_approval_to_closed", round(time.time() - approved_at, 1))
    after = truth()
    measure("after_rollback", after)
    stages = stages_of(detail or {})
    measure("plan_stages", stages)
    check("the rollback executed through the contained worker (plan reached executing and closed)",
          "executing" in stages and "closed" in stages, stages)
    check("REAL WRITE: the cluster runs the healthy template again (generation advanced)",
          after["template"] == healthy["template"] and (after["generation"] or 0) > (bad["generation"] or 0),
          {"healthy": healthy["template"], "now": after["template"]})
    check("the write is attributable on the object (rolled-back-by-action annotation)",
          bool(after["rolled_back_by"]), after["rolled_back_by"])
    healed = p113.wait_for(lambda: (lambda t: t if t["available"] >= 1 and not t["crash_looping"] else None)(
        truth()), timeout=300, interval=5)
    check("the workload is healthy again on the cluster", bool(healed), healed)
    verification = next((e for e in (detail or {}).get("events", []) if e.get("stage") in
                         ("verified", "verification")), {})
    outcome = json.dumps(detail or {})
    check("independent verification established the outcome (not the executor's word)",
          any(s in stages for s in ("verified", "verification")) or "ESTABLISHED" in outcome.upper()
          or "established" in outcome, verification or stages)
    leases_after = len(vault_leases("cortexprime-rollbacker"))
    measure("vault_rollbacker_leases", {"before": leases_before, "after": leases_after})
    check("the write ran with a rollbacker token Vault minted for this action",
          leases_after > leases_before, {"before": leases_before, "after": leases_after})
    STATE["incident_detail"] = {"plan_id": (detail or {}).get("plan_id"), "stages": stages}
    code, again = approver.post(f"/api/v1/approvals/{item['approval_id']}/decision",
                                {"decision": "approve", "confirm_workload": APP, "justification": "replay"})
    time.sleep(20)
    negative("replaying the consumed approval", "approval consumption", f"HTTP {code}",
             0 if truth()["generation"] == after["generation"] else 1)
    incident_failed_verification(alice, approver)


def incident_failed_verification(alice: Client, approver: Client) -> None:
    """Verification must tell failure from success: the rollback target was
    healthy only while a configuration flag existed, and the flag is removed
    under it. The rollback runs, the incident persists, and the platform must
    say VERIFICATION FAILED and escalate -- never success, never a retry."""
    section("INCIDENT (failure): the rollback runs, the incident persists -> verification must fail")
    kubectl("-n", CONN_NS, "delete", "deploy", APP_FLAG, "--ignore-not-found", "--wait=true")
    kubectl("apply", "-f", "-", stdin=json.dumps({
        "apiVersion": "v1", "kind": "ConfigMap",
        "metadata": {"name": FLAG_CONFIG, "namespace": CONN_NS}, "data": {"flag": "on"}}))
    for command, flag in ((p113.HEALTHY_COMMAND, None), (FLAG_HEALTHY, FLAG_CONFIG)):
        kubectl("apply", "-f", "-", stdin=app_manifest(command, APP_FLAG, flag))
        time.sleep(5)
        if not p113.wait_for(lambda: truth(APP_FLAG)["available"] >= 1 and not truth(APP_FLAG)["crash_looping"],
                             timeout=300, interval=5):
            finish(2, f"{APP_FLAG} never became healthy")
    healthy = truth(APP_FLAG)
    time.sleep(90)                                   # observed healthy: it becomes the rollback target
    earlier = {p["plan_id"] for p in plans(alice, APP_FLAG)}
    kubectl("-n", CONN_NS, "delete", "configmap", FLAG_CONFIG)       # a dependency disappears under it
    kubectl("apply", "-f", "-", stdin=app_manifest(p113.BAD_REVISION_COMMAND, APP_FLAG, FLAG_CONFIG))
    if not p113.wait_for(lambda: truth(APP_FLAG)["crash_looping"], timeout=240, interval=5):
        finish(2, "the flagged workload's bad revision did not crash-loop")
    bad = truth(APP_FLAG)

    def pending():
        code, body = api_get_resilient(approver, "/api/v1/approvals?status=pending&limit=50")
        items = [i for i in body.get("items", []) if i.get("workload") == APP_FLAG] if code == 200 else []
        return items[0] if items else None
    item = p113.wait_for(pending, timeout=1500, interval=10)
    if not check("failure scenario: an approval request reached the queue", item is not None):
        return
    code, _ = approver.post(f"/api/v1/approvals/{item['approval_id']}/decision",
                            {"decision": "approve", "confirm_workload": APP_FLAG,
                             "justification": "reviewed: roll back to the last healthy revision"})
    check("failure scenario: approved by the scoped approver", code == 200, f"HTTP {code}")

    def closed():
        for plan in plans(alice, APP_FLAG):
            if plan["plan_id"] in earlier:
                continue
            detail = plan_detail(alice, plan["plan_id"])
            if "closed" in stages_of(detail):
                return detail
        return None
    detail = p113.wait_for(closed, timeout=900, interval=10) or {}
    stages = stages_of(detail)
    after = truth(APP_FLAG)
    measure("failure_scenario", {"stages": stages, "before": bad, "after": after, "healthy_was": healthy})
    check("failure scenario: the rollback executed exactly once to the approved (previously healthy) template",
          stages.count("executing") == 1 and after["template"] == healthy["template"]
          and after["generation"] == (bad["generation"] or 0) + 1, {"stages": stages})
    check("VERIFICATION DISTINGUISHES FAILURE: the incident persisted -> verification_failed, escalated, "
          "never reported as success",
          "verification_failed" in stages and "escalated" in stages and "verified" not in stages, stages)
    time.sleep(30)
    check("no retry after a failed verification (no second write)",
          truth(APP_FLAG)["generation"] == after["generation"], truth(APP_FLAG)["generation"])


# ---------------------------------------------------------------------------
# FAILURES
# ---------------------------------------------------------------------------

def injected(name: str, state: str, detail: str, recovered: bool) -> None:
    REPORT["failure_injections"].append({"injection": name, "health": state, "detail": detail[:300],
                                         "recovered": recovered})


def configure_vault() -> None:
    """The operator's one-time Vault step, re-run (idempotent). Bytes, not text:
    a text-mode pipe on Windows turns LF into CRLF and ``set -eu`` into
    ``set -eu\r`` (run 13)."""
    pod = kubectl("-n", "vault", "get", "pod", "-l", "app=vault", "-o", "jsonpath={.items[0].metadata.name}")
    script = (REPO / "scripts" / "connector" / "configure_vault_kubernetes.sh").read_bytes()
    r = subprocess.run(["kubectl", "-n", "vault", "exec", "-i", pod, "--", "env", "VAULT_ADDR=http://127.0.0.1:8201",
                        "VAULT_TOKEN=root", f"CONNECTION_NAMESPACE={CONN_NS}", f"RELEASE_NAMESPACE={REL_NS}",
                        "sh", "-s"], input=script, capture_output=True, timeout=120, env=kenv())
    check("operator re-ran the Vault configuration script (idempotent)", r.returncode == 0,
          r.stderr.decode(errors="replace")[-300:])


def stage_failures() -> None:
    section("FAILURES: each named by health, each recovered")
    alice = Client("p111k-alice", TENANT_A)

    # 1. The reader loses its permissions (RoleBinding deleted).
    rbs = [b for b in kjson("-n", CONN_NS, "get", "rolebinding").get("items", [])
           if any(s.get("name") == "cortexprime-reader" for s in b.get("subjects") or [])]
    if check("found the reader's RoleBinding", len(rbs) == 1, [b["metadata"]["name"] for b in rbs]):
        saved = rbs[0]
        for k in ("uid", "resourceVersion", "creationTimestamp", "managedFields"):
            saved["metadata"].pop(k, None)
        kubectl("-n", CONN_NS, "delete", "rolebinding", saved["metadata"]["name"])
        # The API server's authorizer caches: wait until the loss is effective
        # for every permission before reading a health answer about it.
        p113.wait_for(lambda: not any(can_i(CONN_NS, "cortexprime-reader", v, r, CONN_NS) for v, r in (
            ("list", "pods"), ("get", "deployments.apps"), ("list", "events"), ("list", "replicasets.apps"))),
            timeout=120, interval=3)
        propagated = datetime.now(timezone.utc).isoformat()
        body = wait_health_after(alice, {"MISCONFIGURED"}, propagated, timeout=400)
        h = body.get("health") or {}
        named = "kubernetes:pods:list" in json.dumps(h)
        check("RBAC removed -> MISCONFIGURED, naming the exact missing permissions",
              h.get("state") == "MISCONFIGURED" and named, json.dumps(h)[:400])
        kubectl("apply", "-f", "-", stdin=json.dumps(saved))
        rec = wait_health(alice, {"CONNECTED"}, timeout=330)
        ok = (rec.get("health") or {}).get("state") == "CONNECTED"
        check("RBAC restored -> CONNECTED without a restart", ok)
        injected("reader RoleBinding deleted", h.get("state", "?"), json.dumps(h.get("checks", ""))[:300], ok)

    # 2. The Vault role for the reader is removed.
    role = json.loads(vault("read", "-format=json", "kubernetes/roles/cortexprime-reader") or "{}").get("data", {})
    if check("read the Vault reader role", bool(role)):
        vault("delete", "kubernetes/roles/cortexprime-reader")
        body = wait_health(alice, {"AUTHENTICATION_REQUIRED", "MISCONFIGURED", "UNAVAILABLE"}, timeout=330)
        h = body.get("health") or {}
        check("Vault role removed -> not CONNECTED, with a credential-class reason",
              h.get("state") in ("AUTHENTICATION_REQUIRED", "MISCONFIGURED"), json.dumps(h)[:400])
        vault("write", "kubernetes/roles/cortexprime-reader",
              f"allowed_kubernetes_namespaces={CONN_NS}", "service_account_name=cortexprime-reader",
              "token_default_ttl=10m", "token_max_ttl=1h", check_rc=True)
        rec = wait_health(alice, {"CONNECTED"}, timeout=330)
        ok = (rec.get("health") or {}).get("state") == "CONNECTED"
        check("Vault role restored -> CONNECTED", ok)
        injected("Vault reader role deleted", h.get("state", "?"), json.dumps(h.get("checks", ""))[:300], ok)

    # 3. Vault is down.
    kubectl("-n", "vault", "scale", "deploy/vault", "--replicas=0")
    p113.wait_for(lambda: not kjson("-n", "vault", "get", "pod", "-l", "app=vault").get("items"), timeout=120)
    body = wait_health(alice, {"UNAVAILABLE", "AUTHENTICATION_REQUIRED"}, timeout=330)
    h = body.get("health") or {}
    check("Vault down -> UNAVAILABLE/AUTHENTICATION_REQUIRED (never CONNECTED on a stale answer)",
          h.get("state") in ("UNAVAILABLE", "AUTHENTICATION_REQUIRED"), json.dumps(h)[:400])
    kubectl("-n", "vault", "scale", "deploy/vault", "--replicas=1")
    kubectl("-n", "vault", "rollout", "status", "deploy/vault", "--timeout=240s", timeout=300)
    # Vault dev storage is in memory: a restarted dev Vault is an EMPTY Vault. The operator
    # re-runs the one configuration script -- which is itself the proof it is idempotent.
    configure_vault()
    rec = wait_health(alice, {"CONNECTED"}, timeout=300)
    ok = (rec.get("health") or {}).get("state") == "CONNECTED"
    check("Vault back -> CONNECTED (the runtime re-authenticated with its pod identity, no restart)", ok,
          (rec.get("health") or {}).get("state"))
    injected("Vault down", h.get("state", "?"), json.dumps(h.get("checks", ""))[:300], ok)

    # 4. The rollback worker is down.
    kubectl("-n", CONN_NS, "scale", "deploy/contained-rollback-worker", "--replicas=0")
    body = wait_health(alice, {"DEGRADED"}, timeout=330)
    h = body.get("health") or {}
    unavailable = h.get("unavailable_capabilities") or {}
    check("rollback worker down -> DEGRADED; reads stay available; rollback named unavailable",
          h.get("state") == "DEGRADED" and "platform.kubernetes.deployment.rollback" in unavailable
          and "platform.kubernetes.pods.list" in (h.get("available_capabilities") or []),
          json.dumps({"state": h.get("state"), "unavailable": unavailable,
                      "available": h.get("available_capabilities")})[:400])
    kubectl("-n", CONN_NS, "scale", "deploy/contained-rollback-worker", "--replicas=1")
    rec = wait_health(alice, {"CONNECTED"}, timeout=330)
    ok = (rec.get("health") or {}).get("state") == "CONNECTED"
    check("worker back -> CONNECTED", ok)
    injected("rollback worker down", h.get("state", "?"), json.dumps(unavailable)[:300], ok)

    # 5. Misconfiguration is refused at start with the exact variable named.
    r = helm_install(**{"vault.address": ""})
    check("helm refuses an install without a Vault address, naming the value",
          r.returncode != 0 and "vault.address" in (r.stderr or ""), (r.stderr or "")[-300:])
    r = helm("template", RELEASE, CHART, "-n", REL_NS, *helm_values(**{"connection.namespace": ""}))
    check("helm refuses a connection without a namespace, naming the value",
          r.returncode != 0 and "connection.namespace" in (r.stderr or ""), (r.stderr or "")[-300:])
    code, _ = alice.get("/api/v1/connectors/kubernetes")
    check("the running release is untouched by the refused upgrades", code == 200 and
          health_state(alice) == "CONNECTED")


# ---------------------------------------------------------------------------
# OBSERVE
# ---------------------------------------------------------------------------

def stage_observe() -> None:
    section("OBSERVE: metrics, audit, secrets")
    text = metrics_text()
    lines = [l for l in text.splitlines() if l.startswith("cortex_")]
    measure("metric_families", sorted({l.split("{")[0].split(" ")[0] for l in lines})[:60])
    check("connector health is exported (cortex_connector_health)", "cortex_connector_health" in text)
    leaked = [l for l in lines if any(t in l.lower() for t in ("token=", "secret=", "password=", "bearer"))]
    check("no metric carries a credential-like label", not leaked, leaked[:3])

    # Rate limiting, live: a tiny per-tenant budget via the chart, then a burst of health checks.
    # Coherent by the policy's own rule (a per-capability budget may not exceed
    # the tenant budget), which the runtime refuses at boot otherwise.
    r = helm_install(**{"rateLimit.TENANT_PER_MINUTE": "3", "rateLimit.TENANT_BURST": "3",
                        "rateLimit.CAPABILITY_PER_MINUTE": "2", "rateLimit.CAPABILITY_BURST": "2",
                        "rateLimit.PROVIDER_PER_MINUTE": "3", "rateLimit.PROVIDER_BURST": "3"})
    check("rate limits configured through Helm values (upgrade succeeded)", r.returncode == 0, r.stderr[-300:])
    wait_runtime_ready()
    alice = Client("p111k-alice", TENANT_A)
    body = wait_health(alice, {"RATE_LIMITED"}, timeout=240)
    h = body.get("health") or {}
    check("a real burst is refused by the gateway's limiter -> health RATE_LIMITED",
          h.get("state") == "RATE_LIMITED", json.dumps(h)[:300])
    check("the refusal is counted (cortex_gateway_rate_limited)", "cortex_gateway_rate_limited" in metrics_text())
    r = helm_install()
    wait_runtime_ready()
    check("limits restored -> CONNECTED", r.returncode == 0 and
          (wait_health(alice, {"CONNECTED"}, timeout=240).get("health") or {}).get("state") == "CONNECTED")

    # Audit: every governed invocation left a durable record.
    tables = [r[0] for r in sql("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%audit%' "
                                "OR table_name LIKE '%invocation%' ORDER BY table_name")]
    measure("audit_tables", tables)
    counts = {}
    for t in tables:
        try:
            counts[t] = sql(f'SELECT count(*) FROM "{t}"')[0][0]
        except Exception:  # noqa: BLE001
            counts[t] = None
    measure("audit_rows", counts)
    check("governed invocations are durably recorded", any((v or 0) > 0 for v in counts.values()), counts)

    # Secrets: nothing leaked into logs, report, DB or the image.
    logs = runtime_logs("3h")
    secrets = [secret_value(REL_NS, "cortexprime-model", "LLM_API_KEY"),
               secret_value(REL_NS, "cortexprime-auth", "JWT_SECRET_KEY"),
               secret_value(REL_NS, "cortexprime-redis", "password"),
               (REPO / ".phase111k" / "pg.password").read_text(encoding="utf-8").strip()]
    check("no credential value in the runtime's logs", not any(s and s in logs for s in secrets))
    check("no bearer token in the runtime's logs", "Bearer ey" not in logs and "eyJhbGciOi" not in logs)
    report_text = json.dumps(REPORT, default=str)
    check("no credential value in this report", not any(s and s in report_text for s in secrets))
    hits = 0
    for table in ("cw_observation", "cw_fact", "cp_remediation_event"):
        if _has_table(table):
            for s in secrets:
                hits += sql(f'SELECT count(*) FROM "{table}" WHERE CAST("{table}" AS text) LIKE :p',
                            p=f"%{s}%")[0][0]
    check("no credential value in the durable store (observations, facts, remediation events)", hits == 0, hits)
    envs = subprocess.run(["docker", "run", "--rm", "--entrypoint", "sh", f"cortexprime/governed-runtime:{IMAGE_TAG}",
                           "-c", "ls -a /app; ls /app/backend | head -50; test -e /app/backend/.env && echo HAS_ENV"],
                          capture_output=True, text=True, timeout=120).stdout
    check("the image carries no .env", "HAS_ENV" not in envs)


#: Which real-run checks answer each evaluation question (backend.api.connector_evaluation).
KUBERNETES_EVIDENCE = {
    "select": ("detection -> investigation -> plan", "the rollback executed through the contained worker",
               "exactly two writes"),
    "arguments": ("REAL WRITE: the cluster runs the healthy template again", "the write is attributable"),
    "governance": ("approval by a member without approve authority", "approval by another tenant's approver",
                   "cross-tenant target A -> B", "cross-tenant target B -> A",
                   "no arbitrary API / shell / raw-request capability exists", "no credential -> the connector API"),
    "authorized_execution": ("nothing was written before approval", "the scoped approver approved",
                             "replaying the consumed approval"),
    "verification": ("independent verification established the outcome", "the workload is healthy again",
                     "VERIFICATION DISTINGUISHES FAILURE", "no retry after a failed verification"),
    "recovery": ("RBAC restored -> CONNECTED", "Vault role restored -> CONNECTED", "Vault back -> CONNECTED",
                 "worker back -> CONNECTED"),
    "explain": ("health CONNECTED", "RBAC removed -> MISCONFIGURED, naming", "the plan is visible to the tenant",
                "rollback worker down -> DEGRADED"),
}


def stage_evaluate() -> None:
    section("EVALUATE: the reusable connector evaluation suite")
    from backend.api.capability_execution_composition import (
        CONTAINED_KUBERNETES_PROVIDER_ID, CONTAINED_ROLLBACK_PROVIDER_ID,
        contained_rollback_worker_catalog, contained_worker_catalog)
    from backend.api.connector_evaluation import evaluate_connector, evaluate_evidence
    from backend.api.kubernetes_connector import kubernetes_manifest
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        kubernetes_real_read_catalog)

    contract = evaluate_connector(kubernetes_manifest(), {
        "kubernetes": kubernetes_real_read_catalog(),
        CONTAINED_ROLLBACK_PROVIDER_ID: contained_rollback_worker_catalog(),
        CONTAINED_KUBERNETES_PROVIDER_ID: contained_worker_catalog()})
    measure("evaluation_contract", contract.to_dict())
    check("contract evaluation: the manifest and composed catalogs pass every rule", contract.passed,
          [f.rule for f in contract.findings])
    answers = evaluate_evidence(REPORT["checks"], KUBERNETES_EVIDENCE)
    REPORT["evaluation"] = answers
    for key, answer in answers.items():
        measure(f"evaluation_{key}", {"verdict": answer["verdict"], "missing": answer["missing_evidence"]})
    check("behavioural evaluation: every question answered PASS from this run's real evidence",
          all(a["verdict"] == "PASS" for a in answers.values()),
          {k: a["verdict"] for k, a in answers.items()})


def main() -> None:
    started = time.time()
    try:
        if "INSTALL" in STAGES:
            stage_install()
        else:
            os.environ.setdefault("JWT_SECRET_KEY", "")
            forward("svc/cortexprime-postgres", PG_PORT, 5432)
            wait_runtime_ready()
        os.environ["JWT_SECRET_KEY"] = secret_value(REL_NS, "cortexprime-auth", "JWT_SECRET_KEY")
        for name, fn in (("CONNECT", stage_connect), ("CREDS", stage_creds), ("RBAC", stage_rbac),
                         ("TENANCY", stage_tenancy), ("INCIDENT", stage_incident),
                         ("FAILURES", stage_failures), ("OBSERVE", stage_observe),
                         ("EVALUATE", stage_evaluate)):
            if name in STAGES:
                fn()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        measure("wall_clock_seconds", round(time.time() - started, 1))
        finish(2, f"harness crashed: {type(exc).__name__}: {str(exc)[:300]}")
    measure("wall_clock_seconds", round(time.time() - started, 1))
    finish(0)


if __name__ == "__main__":
    main()
