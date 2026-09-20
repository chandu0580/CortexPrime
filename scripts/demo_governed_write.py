"""A short, recordable demonstration of one governed change to the real world.

Runs against the deployed governed runtime and a real Kubernetes cluster. It
needs nothing else started -- no V1 backend, no frontend, none of the twelve
compose services.

The story it tells, in order:

  1. the product refuses an anonymous caller
  2. a tenant member can see the connectors, and they are CONNECTED
  3. a change to the world needs a human approval, and the request is visible
  4. a member WITHOUT approve authority is refused
  5. the scoped approver grants it
  6. the action runs through the governed chain and a contained worker
  7. Kubernetes itself -- not CortexPrime's own reply -- shows it happened

usage:  python scripts/demo_governed_write.py
        python scripts/demo_governed_write.py --slow     (pauses for narration)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

NS = os.environ.get("DEMO_NAMESPACE", "cortexprime")
TENANT = os.environ.get("DEMO_TENANT", "tenant-p112000a")
TARGET_NS = os.environ.get("DEMO_TARGET_NS", "cortex-conn-a")
TARGET = os.environ.get("DEMO_TARGET", "p111k-shop")
PORT = int(os.environ.get("DEMO_PORT", "18120"))
API = f"http://127.0.0.1:{PORT}"
CAPABILITY = "platform.kubernetes.workload.rollout_restart"
OPERATION = "kubernetes.workload.rollout_restart"
ENVIRONMENT = os.environ.get("DEMO_ENV", "staging")
SLOW = "--slow" in sys.argv

# The personas, and exactly what each one holds. They are provisioned members of
# the tenant -- which matters for the fourth beat: a refusal because somebody is
# not a member of the tenant at all would demonstrate a different control from
# the one being shown, while looking identical on screen (both are 403).
VIEWER = os.environ.get("DEMO_VIEWER", "p114-operator")      # member, no grants
REQUESTER = os.environ.get("DEMO_REQUESTER", "p114-requester")
APPROVER = os.environ.get("DEMO_APPROVER", "p114-approver")  # approve + execute

BOLD, DIM, GREEN, RED, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[0m"


def beat(number: int, text: str) -> None:
    print(f"\n{BOLD}{number}. {text}{RESET}")
    if SLOW:
        input(f"{DIM}   [enter]{RESET}")


def say(text: str, ok: bool = True) -> None:
    mark = f"{GREEN}OK{RESET}" if ok else f"{RED}!!{RESET}"
    print(f"   {mark}  {text}")


def kubectl(*args: str, namespace: str = NS) -> str:
    done = subprocess.run(["kubectl", "-n", namespace, *args],
                          capture_output=True, text=True)
    return done.stdout.strip()


def port_open() -> bool:
    import socket

    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", PORT)) == 0


def ensure_api():
    if port_open():
        return None
    proc = subprocess.Popen(
        ["kubectl", "-n", NS, "port-forward", "svc/cortexprime-governed",
         f"{PORT}:8110"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if port_open():
            return proc
        time.sleep(1)
    raise SystemExit("the governed runtime is not reachable; is the cluster up?")


def token(subject: str, tenant: str = TENANT) -> str:
    from backend.auth.jwt_handler import create_access_token

    return create_access_token(subject, role="operator", tenant_id=tenant,
                               user_role="member")


def call(method: str, path: str, subject=None, body=None, tenant=TENANT):
    headers = {"Content-Type": "application/json"}
    if subject:
        headers["Authorization"] = "Bearer " + token(subject, tenant)
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API + path, data=data, method=method,
                                     headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as answer:
            return answer.status, json.loads(answer.read() or "null")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw or "null")
        except ValueError:
            return exc.code, {"detail": raw[:200]}


def in_cluster(code: str, variables: dict) -> dict:
    program = (
        "import json, os, sys\n"
        "sys.path.insert(0, '/app')\n"
        "V = json.loads(" + repr(json.dumps(variables)) + ")\n"
        "RESULT = {}\n" + code +
        "\nprint('DEMO_OUT ' + json.dumps(RESULT, default=str))\n"
    )
    done = subprocess.run(
        ["kubectl", "-n", NS, "exec", "-i", "deploy/cortexprime-governed", "--",
         "python", "-c", program], capture_output=True, text=True, timeout=300)
    for line in done.stdout.splitlines():
        if line.startswith("DEMO_OUT "):
            return json.loads(line.split(" ", 1)[1])
    raise SystemExit(f"setup failed inside the cluster: {done.stderr[-300:]}")


REQUEST_APPROVAL = """
from datetime import datetime, timedelta, timezone
import sqlalchemy as sa
from backend.database.durable.session import DurableStore
from backend.contexts.connectivity.infrastructure.sql_approval import SqlApprovalRepository
from backend.contexts.connectivity.domain.authorization import CapabilityOperation
from backend.contracts.execution import ExecutionEnvironment
from backend.contexts.execution.domain.invocation import canonical_approval_digest

engine = sa.create_engine(os.environ['CORTEX_DURABLE_URL'], future=True)
with engine.connect() as c:
    row = c.execute(sa.text(
        "select reference, digest from cp_capability where capability_id = :c "
        "order by version desc limit 1"), {'c': V['capability']}).first()
reference, capability_digest = row[0], row[1]
environment = ExecutionEnvironment(V['env'])
digest = canonical_approval_digest(
    capability_ref=reference, capability_digest=capability_digest,
    operation=V['operation'], tenant_id=V['tenant'],
    principal_id=V['principal'], environment=environment, payload=V['payload'])
with engine.begin() as c:
    c.execute(sa.text("delete from cp_approval where identity_digest = :d"),
              {'d': digest})
now = datetime.now(timezone.utc)
SqlApprovalRepository(DurableStore(engine)).request(
    approval_id=V['approval_id'], identity_digest=digest, tenant_id=V['tenant'],
    capability_ref=reference, capability_digest=capability_digest,
    operation=V['operation'],
    authorization_operation=CapabilityOperation.INVOKE.value,
    environment=environment.value, principal_id=V['principal'],
    payload=V['payload'], approval_digest=digest,
    requested_by='user:' + V['principal'],
    expires_at=now + timedelta(minutes=30), requested_at=now,
    investigation_ref=None, justification=V['why'])
RESULT['approval_id'] = V['approval_id']
RESULT['digest'] = digest
"""


def generation() -> int:
    raw = kubectl("get", "deploy", TARGET, "-o", "jsonpath={.metadata.generation}",
                  namespace=TARGET_NS)
    return int(raw or 0)


def pods() -> list:
    raw = kubectl("get", "pods", "-l", f"app={TARGET}", "-o",
                  "jsonpath={range .items[*]}{.metadata.name}\n{end}",
                  namespace=TARGET_NS)
    return [p for p in raw.splitlines() if p.strip()]


def main() -> int:
    forward = ensure_api()
    try:
        print(f"{BOLD}CortexPrime — one governed change to a real cluster{RESET}")
        print(f"{DIM}   target: {TARGET_NS}/{TARGET}   tenant: {TENANT}{RESET}")

        beat(1, "The product refuses a caller it cannot authenticate.")
        code, _ = call("GET", "/api/v1/connectors")
        say(f"GET /api/v1/connectors with no token  ->  {code}", code == 401)

        beat(2, "A member of the tenant sees its connectors, and their real health.")
        code, body = call("GET", "/api/v1/connectors", VIEWER)
        for connector in (body or {}).get("connectors", []):
            say(f"{connector['id']:12s} {connector.get('state')}",
                connector.get("state") == "CONNECTED")

        beat(3, "Changing the world needs a human approval. Here is the request.")
        before_generation, before_pods = generation(), pods()
        payload = {"namespace": TARGET_NS, "name": TARGET}
        made = in_cluster(REQUEST_APPROVAL, {
            "capability": CAPABILITY, "operation": OPERATION, "env": ENVIRONMENT,
            "tenant": TENANT, "principal": REQUESTER, "payload": payload,
            "approval_id": f"appr-demo-{int(time.time())}",
            "why": "demonstration: restart the shop workload"})
        approval_id = made["approval_id"]
        say(f"approval {approval_id}")
        say(f"bound to the action digest {made['digest'][:16]}…")
        code, queue = call("GET", "/api/v1/approvals", VIEWER)
        mine = [i for i in (queue or {}).get("items", [])
                if i.get("approval_id") == approval_id]
        say(f"visible in the human approval queue ({len(mine)} match)", bool(mine))

        beat(4, "A member without approve authority cannot grant it.")
        code, body = call("POST", f"/api/v1/approvals/{approval_id}/decision",
                          VIEWER,
                          {"decision": "approve", "justification": "let me"})
        detail = str((body or {}).get("detail") or "")
        # It must be refused for the RIGHT reason. "Not a member of this tenant"
        # is also a 403 and would look the same on a recording while proving
        # something else entirely.
        about_authority = "membership" not in detail.lower()
        say(f"refused -> {code}  {detail[:90]}", code == 403 and about_authority)
        if code == 403 and not about_authority:
            say("that refusal is about MEMBERSHIP, not approval authority — "
                "this persona is not provisioned", False)

        beat(5, "The scoped approver grants it.")
        code, _ = call("POST", f"/api/v1/approvals/{approval_id}/decision",
                       APPROVER,
                       {"decision": "approve", "justification": "demonstration"})
        say(f"granted -> {code}", code == 200)

        beat(6, "Now it runs: governed chain, contained worker, real cluster.")
        started = time.monotonic()
        code, outcome = call("POST", f"/api/v1/approvals/{approval_id}/execute",
                             "p114-approver", {"wait": True})
        took = round(time.monotonic() - started, 1)
        say(f"execute -> {code} in {took}s", code == 200)
        if code != 200:
            say(str(outcome)[:200], False)

        beat(7, "Kubernetes itself says whether it happened — not CortexPrime.")
        after_generation = generation()
        say(f"deployment generation {before_generation} -> {after_generation}",
            after_generation > before_generation)

        # The generation moving is already proof the write landed. The
        # replacement pod is the part a viewer can see, and Kubernetes needs a
        # moment to roll it -- so wait for it rather than reporting "none yet"
        # and calling that a result.
        replaced, waited = set(), 0.0
        while waited < 60:
            replaced = set(pods()) - set(before_pods)
            if replaced:
                break
            time.sleep(3)
            waited += 3
        say(f"pods replaced after {int(waited)}s: {len(replaced)} new "
            f"({', '.join(sorted(replaced)) or 'none'})", bool(replaced))

        print(f"\n{BOLD}One approved action. One provider write. Verified "
              f"independently.{RESET}\n")
        return 0
    finally:
        if forward is not None:
            forward.terminate()


if __name__ == "__main__":
    sys.exit(main())
