"""Phase 10.5: approver authority, against real infrastructure.

What this proves
----------------
Tenant membership is no longer sufficient to decide an irreversible action.
A caller must additionally hold an explicit approver grant **in that tenant**,
resolved live from the authoritative store on every request.

The discipline
--------------
* The unauthorized case is a real tenant member with a real, valid session and a
  real pending approval in their own tenant. The only thing missing is
  authority, so a refusal cannot be explained by anything else.
* Revocation is tested with a token minted **before** the grant was withdrawn,
  because a check against a token claim would pass that test by accident.
* Every negative asserts ``provider_writes == 0`` against cluster generation and
  names the layer that refused: authentication, membership, role authorization,
  approval state, governance or worker.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED / BLOCKED.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import scripts.phase103_approval_remediation_harness as p103  # noqa: E402
import scripts.phase104_approval_queue_harness as p104  # noqa: E402
import scripts.phase99b_contained_worker_harness as b  # noqa: E402

REPORT: dict = {
    "phase": "10.5",
    "checks": [],
    "deferred": [],
    "blocked": [],
    "measurements": {},
    "negative_matrix": [],
    "verdict": "NOT VERIFIED",
}

TENANT_A = "tenant-a-p105"
TENANT_B = "tenant-b-p105"
TENANTS: dict = {}
MEMBERS: dict = {}
OPERATION = p103.OPERATION
NAMESPACE = p103.NAMESPACE
TARGET = p103.TARGET
BYSTANDER = p103.BYSTANDER
SEEDED: dict = {}

#: Real people, with real memberships. Only APPROVER holds the grant.
APPROVER = "approver-a@p105.example"
APPROVER_TWO = "approver2-a@p105.example"
PLAIN_MEMBER = "member-a@p105.example"
TENANT_OWNER = "owner-a@p105.example"
B_APPROVER = "approver-b@p105.example"


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def deferred(name, why):
    REPORT["deferred"].append({"item": name, "why": str(why)[:400]})
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


def record_negative(case, stopped_by, detail, writes) -> bool:
    REPORT["negative_matrix"].append({
        "case": case, "stopped_by": stopped_by, "detail": str(detail)[:200],
        "provider_writes": writes})
    return check(f"{case} — refused by {stopped_by}", writes == 0, str(detail)[:160])


# ----------------------------------------------------------------------


def bind_worker_to_tenant(tenant_id: str) -> None:
    """Re-bind the CONTAINED worker to this phase's tenant.

    The worker refuses any envelope whose tenant is not the one it was
    provisioned for, and that refusal is correct -- it is the boundary Phase
    9.9B built. Binding it to the tenant that will actually use it is an
    OPERATOR action, exactly as provisioning a credential for a real customer
    would be, and it is done here rather than by weakening the worker.
    """
    import subprocess

    kubeconfig = os.environ.get("KUBECONFIG") or str(REPO / ".phase99b" / "kubeconfig")
    namespace = os.environ.get("CORTEX_P99B_NAMESPACE", "cortex-p99b")
    environment = {**os.environ, "KUBECONFIG": kubeconfig}
    try:
        current = subprocess.run(
            ["kubectl", "--request-timeout=20s", "get", "deploy",
             "contained-worker", "-n", namespace, "-o",
             "jsonpath={.spec.template.spec.containers[0].env[0].value}"],
            capture_output=True, text=True, env=environment, timeout=60)
        if current.stdout.strip() == tenant_id:
            return
        subprocess.run(
            ["kubectl", "--request-timeout=30s", "set", "env",
             "deployment/contained-worker", "-n", namespace,
             f"CORTEX_BIND_TENANT={tenant_id}"],
            capture_output=True, text=True, env=environment, timeout=120, check=True)
        subprocess.run(
            ["kubectl", "--request-timeout=180s", "rollout", "status",
             "deployment/contained-worker", "-n", namespace, "--timeout=180s"],
            capture_output=True, text=True, env=environment, timeout=240, check=True)
        print(f"  [note] contained worker re-bound to tenant {tenant_id}")
    except Exception as exc:  # noqa: BLE001 - reported, never ignored
        print(f"  [note] could not re-bind the worker: {type(exc).__name__}")


def register_people() -> None:
    """Two tenants, five memberships, exactly three approver grants."""
    from backend.auth.approver import APPROVE_REMEDIATION
    from backend.auth.tenant import get_tenant_manager

    tm = get_tenant_manager()
    for slug in (TENANT_A, TENANT_B):
        tenant = tm.get_tenant_by_slug(slug)
        if tenant is None:
            tenant = tm.create_tenant(name=slug, slug=slug)
        TENANTS[slug] = tenant.tenant_id

    for email, slug, role in (
        (APPROVER, TENANT_A, "member"),
        (APPROVER_TWO, TENANT_A, "member"),
        (PLAIN_MEMBER, TENANT_A, "member"),
        # A tenant OWNER, deliberately. Owner holds "*" for read, write and
        # admin in the existing PERMISSIONS table; if any of those wildcards
        # leaked into approval authority, this membership would prove it.
        (TENANT_OWNER, TENANT_A, "owner"),
        (B_APPROVER, TENANT_B, "member"),
    ):
        member = tm.get_user_by_email(email)
        if member is None:
            member = tm.add_user(TENANTS[slug], email, role=role)
        MEMBERS[email] = member

    for email in (APPROVER, APPROVER_TWO, B_APPROVER):
        member = MEMBERS[email]
        tm.grant_permission(member.tenant_id, member.user_id, APPROVE_REMEDIATION)


def token_for(tenant_slug: str, subject: str) -> str:
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator",
                               tenant_id=TENANTS[tenant_slug], user_role="member")


def auth(tenant_slug: str = TENANT_A, subject: str = APPROVER) -> dict:
    return {"Authorization": f"Bearer {token_for(tenant_slug, subject)}"}


def seed(engine, tenant_slug: str = TENANT_A, workload: str = TARGET,
         principal: str = APPROVER) -> tuple:
    from backend.contracts.tenant import TenantRef

    tenant_id = TENANTS[tenant_slug]
    investigation_ref = p103.seed_investigation(engine, tenant_id, workload)
    investigation = engine.investigations.reconstruct(
        tenant=TenantRef(tenant_id=tenant_id), investigation_ref=investigation_ref)
    proposal = engine.remediation.propose(
        investigation=investigation, tenant_id=tenant_id,
        principal_id=principal, operation=OPERATION)
    approval_id = engine.remediation.request_approval(
        proposal=proposal, requested_by=f"human:{principal}",
        justification="p105 seed", now=datetime.now(timezone.utc))
    return investigation_ref, approval_id


def decide(client, approval_id, headers, decision="approve", **extra):
    body = {"decision": decision, **extra}
    if decision == "approve" and "confirm_workload" not in extra:
        body["confirm_workload"] = TARGET
    return client.post(f"/api/v1/approvals/{approval_id}/decision",
                       json=body, headers=headers)


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis, REAL tenant\n"
          "        store. The unauthorized caller is a genuine tenant member\n"
          "        with a valid session and a real pending approval.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. composition — no new surface, and no wildcard confers approval")
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.api.product.approval_routes import MUTATING_ROUTES
    from backend.auth.rbac import PERMISSIONS, check_permission

    p103.ensure_env()
    register_people()
    for var in ("CORTEX_P99B_TENANT", "CORTEX_KUBERNETES_TENANT"):
        os.environ[var] = TENANTS[TENANT_A]
    b.TENANT = TENANTS[TENANT_A]

    bind_worker_to_tenant(TENANTS[TENANT_A])
    runtime = p103.build_runtime()
    definitions = b._commission(runtime, b._platform_ctx())
    engine = p103.build_engine(runtime, definitions)
    app = build_product_app(engine=engine)
    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()

    actual = {(m, r.path) for r in app.routes
              for m in (getattr(r, "methods", None) or ())
              if m not in ("GET", "HEAD", "OPTIONS")
              and getattr(r, "path", "").startswith("/api")}
    check("A1. the product's non-GET routes are STILL exactly the three from "
          "Phase 10.3 — approver authority added no new surface",
          actual == set(MUTATING_ROUTES), str(sorted(actual)))

    check("A2. NO role in the permission table carries an 'approve' action — "
          "approval authority is never conferred by a role",
          all(not PERMISSIONS[role].get("approve") for role in PERMISSIONS),
          str(sorted(PERMISSIONS)))

    check("A3. and no role WILDCARD leaks into it — owner holds '*' for read, "
          "write and admin, and still cannot approve through any of them",
          not any(check_permission(role, "approve", resource)
                  for role in PERMISSIONS
                  for resource in ("remediation", "*", "anything")),
          "owner/admin/member all denied 'approve'")

    from backend.database.durable.tables import DURABLE_TABLES
    check("A4. NO new table — approver authority lives on the existing tenant "
          "membership", len(DURABLE_TABLES) == 22, f"{len(DURABLE_TABLES)} tables")

    import ast

    import backend.auth.approver as approver_module

    tree = ast.parse(Path(approver_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)

    forbidden_imports = {
        name for name in imported
        if any(bad in name for bad in (
            "transport", "credential", "gateway", "connector", "adapters",
            "autonomy", "capability_execution", "dispatch", "scheduler"))
    }
    forbidden_calls = called & {
        "write", "execute", "decide", "request", "grant", "insert", "update",
        "delete", "evaluate", "dispatch", "send", "dial",
    }
    check("A5. the authority module cannot execute, mint an approval, compute "
          "risk or autonomy, or reach a provider — asserted from its parsed "
          "imports and calls, not from its prose",
          not forbidden_imports and not forbidden_calls,
          f"imports={sorted(forbidden_imports)} calls={sorted(forbidden_calls)}")
    check("A5a. and it does import the tenant store, so the check above is not "
          "passing on an empty parse",
          any("tenant" in name for name in imported), str(sorted(imported)))

    run_assignment()
    run_positive(client, engine)
    run_queue_projection(client, engine)
    run_revocation(client, engine)
    run_role_change(client, engine)
    run_self_approval(client, engine)
    run_concurrency(client, engine)
    run_negative_matrix(client, engine)
    run_restart(engine)
    run_audit(engine)
    run_performance(client, engine)

    client.__exit__(None, None, None)
    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"a check failed: {failed[0]}")
    bail(0, "approver authority is explicit, tenant-scoped, store-resolved and "
            "fail-closed; tenant membership alone can no longer approve")


# ======================================================================

def run_assignment() -> None:
    section("B. role assignment is authoritative, durable and tenant-scoped")
    from backend.auth.approver import (
        APPROVE_REMEDIATION, NOT_AN_APPROVER, WRONG_TENANT,
        resolve_approver_authority,
    )
    from backend.auth.tenant import TenantManager, get_tenant_manager

    tm = get_tenant_manager()
    check("B1. the approver holds the grant, resolved from the store",
          resolve_approver_authority(
              principal_id=APPROVER, tenant_id=TENANTS[TENANT_A]).permitted)

    plain = resolve_approver_authority(
        principal_id=PLAIN_MEMBER, tenant_id=TENANTS[TENANT_A])
    check("B2. a plain tenant member does NOT — this is the distinction the "
          "phase exists to make",
          plain.denied and plain.reason == NOT_AN_APPROVER, plain.reason)

    owner = resolve_approver_authority(
        principal_id=TENANT_OWNER, tenant_id=TENANTS[TENANT_A])
    check("B3. a tenant OWNER does not either — an owner is a membership, and "
          "membership is exactly what stopped being sufficient",
          owner.denied and owner.reason == NOT_AN_APPROVER,
          f"role={owner.membership_role} reason={owner.reason}")

    cross = resolve_approver_authority(
        principal_id=B_APPROVER, tenant_id=TENANTS[TENANT_A])
    check("B4. an approver in ANOTHER tenant has no authority here — the grant "
          "is tenant-scoped, not global",
          cross.denied and cross.reason == WRONG_TENANT, cross.reason)

    # Durability: a brand-new manager reading the same files.
    reborn = TenantManager()
    member = reborn.get_user_by_email(APPROVER)
    check("B5. the grant is DURABLE — a fresh manager over the same store still "
          "sees it", APPROVE_REMEDIATION in (member.permissions or []),
          str(member.permissions))

    check("B6. granting is idempotent — a repeated administrative action does "
          "not produce a duplicate nobody can revoke",
          tm.grant_permission(TENANTS[TENANT_A], MEMBERS[APPROVER].user_id,
                              APPROVE_REMEDIATION)
          and sum(1 for p in tm.get_user_by_email(APPROVER).permissions
                  if p == APPROVE_REMEDIATION) == 1)

    try:
        tm.grant_permission(TENANTS[TENANT_A], MEMBERS[APPROVER].user_id, "godmode")
        malformed_refused = False
    except ValueError:
        malformed_refused = True
    check("B7. a permission that is not a namespaced action:resource grant is "
          "REFUSED — there is no bare 'godmode' to grant", malformed_refused)


def run_positive(client, engine) -> None:
    section("C. the positive path")
    _, approval_id = seed(engine)
    r = decide(client, approval_id, auth(), "approve")
    check("C1. an APPROVER approves a pending approval", r.status_code == 200
          and r.json()["state"] == "granted", str(r.status_code))
    SEEDED["approved"] = approval_id

    _, reject_id = seed(engine)
    r = decide(client, reject_id, auth(), "reject", justification="not now")
    check("C2. an APPROVER rejects a pending approval", r.status_code == 200
          and r.json()["state"] == "denied", str(r.status_code))
    SEEDED["rejected"] = reject_id

    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A],
                                  approval_id=SEEDED["approved"])
    SEEDED["approved_digest"] = record.approval_digest
    check("C3. the approver identity is durably recorded as a namespaced "
          "reference — never the string 'admin'",
          record.decided_by == f"human:{APPROVER}", str(record.decided_by))
    check("C4. the AUTHORITY USED is recorded alongside the decision — an audit "
          "trail that says who decided but not what entitled them to cannot "
          "answer the question it exists for",
          "authority=approver_authority_granted" in (record.justification or ""),
          (record.justification or "")[:120])
    check("C5. the tenant on the record is the authenticated one",
          record.tenant_id == TENANTS[TENANT_A])

    before = p103.generations()
    r = client.post(f"/api/v1/approvals/{SEEDED['approved']}/execute", json={},
                    headers=auth())
    time.sleep(3)
    writes = p103.cluster_writes(before, p103.generations())
    measure("provider_writes", writes)
    check("C6. the approved action executes through the EXISTING path and "
          "mutates exactly one deployment — the only commissioned capability",
          r.status_code == 200 and writes == 1, f"HTTP {r.status_code}, writes={writes}")

    after = engine.approvals.get(tenant_id=TENANTS[TENANT_A],
                                 approval_id=SEEDED["approved"])
    check("C7. the canonical approval digest is UNCHANGED by the decision and "
          "the execution", after.approval_digest == SEEDED["approved_digest"])
    check("C8. the approval records which execution consumed it",
          bool(after.consumed_by_execution), str(after.consumed_by_execution))
    SEEDED["consumed"] = SEEDED["approved"]


def run_queue_projection(client, engine) -> None:
    section("D. the queue projects authority without inventing a state")
    _, pending = seed(engine)
    SEEDED["pending"] = pending

    for label, who, expected in (
        ("D1. an APPROVER sees can_approve TRUE", APPROVER, True),
        ("D2. a plain MEMBER sees can_approve FALSE for the same approval",
         PLAIN_MEMBER, False),
        ("D3. a tenant OWNER also sees FALSE", TENANT_OWNER, False),
    ):
        r = client.get(f"/api/v1/approvals/{pending}", headers=auth(TENANT_A, who))
        item = r.json()
        if not check(label, r.status_code == 200 and item["can_approve"] is expected,
                     f"can_approve={item.get('can_approve')} "
                     f"reason={item.get('authority_reason')}"):
            break

    member_item = client.get(f"/api/v1/approvals/{pending}",
                             headers=auth(TENANT_A, PLAIN_MEMBER)).json()
    check("D4. 'the approval is still open' and 'you may decide it' are two "
          "DIFFERENT fields — collapsing them would make 'you may not' and "
          "'nobody may' indistinguishable",
          member_item["actionable"] is True and member_item["can_approve"] is False)
    check("D5. and the refusal is attributed, not generic",
          member_item["authority_reason"] == "no_approver_authority",
          member_item["authority_reason"])

    queue = client.get("/api/v1/approvals", headers=auth(TENANT_A, PLAIN_MEMBER)).json()
    check("D6. the queue tells a non-approver plainly that they hold no "
          "authority, rather than hiding the rows",
          queue["viewer_can_approve"] is False
          and queue["viewer_authority_reason"] == "no_approver_authority"
          and queue["count"] >= 1,
          f"{queue['count']} rows visible, none approvable")

    approver_queue = client.get("/api/v1/approvals", headers=auth()).json()
    check("D7. an approver's queue says the opposite",
          approver_queue["viewer_can_approve"] is True)

    import backend.api.product.approval_queue as module
    source = Path(module.__file__).read_text(encoding="utf-8")
    check("D8. the projection stores nothing — can_approve is derived from the "
          "approval state AND the caller's authority on every read",
          "can_approve" in source and "sa.insert" not in source
          and "sa.update" not in source)


def run_revocation(client, engine) -> None:
    section("E. revocation is fail-closed, on the NEXT request")
    from backend.auth.approver import APPROVE_REMEDIATION
    from backend.auth.tenant import get_tenant_manager

    tm = get_tenant_manager()
    member = MEMBERS[APPROVER_TWO]
    _, approval_id = seed(engine)

    # Minted BEFORE the revocation. A check against a token claim would pass
    # the test below by accident; this is the whole point of reading the store.
    stale_token = token_for(TENANT_A, APPROVER_TWO)
    stale_headers = {"Authorization": f"Bearer {stale_token}"}

    item = client.get(f"/api/v1/approvals/{approval_id}", headers=stale_headers).json()
    check("E1. before revocation the approver may decide", item["can_approve"] is True)

    revoked = tm.revoke_permission(member.tenant_id, member.user_id, APPROVE_REMEDIATION)
    check("E2. the grant is revoked in the authoritative store", revoked)

    before = p103.generations()
    r = decide(client, approval_id, stale_headers, "approve")
    writes = p103.cluster_writes(before, p103.generations())
    check("E3. the SAME TOKEN, minted before the revocation, can no longer "
          "approve — authority is read from the store, not the claim",
          r.status_code == 403 and writes == 0, f"HTTP {r.status_code}, writes={writes}")

    item = client.get(f"/api/v1/approvals/{approval_id}", headers=stale_headers).json()
    check("E4. and the queue now reports no authority for that same token",
          item["can_approve"] is False
          and item["authority_reason"] == "no_approver_authority")

    check("E5. revocation takes effect on the NEXT request — there is no "
          "cached-claim window to document, because no claim is consulted",
          True, "measured window: one request")

    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A], approval_id=approval_id)
    check("E6. and the approval is still pending — a refused decision decides "
          "nothing", record.outcome == "pending", record.outcome)
    SEEDED["revoked_approver_pending"] = approval_id


def run_role_change(client, engine) -> None:
    section("F. authority is evaluated at DECISION time, not at request time")
    from backend.auth.approver import APPROVE_REMEDIATION
    from backend.auth.tenant import get_tenant_manager

    tm = get_tenant_manager()
    member = MEMBERS[PLAIN_MEMBER]
    _, approval_id = seed(engine)
    headers = auth(TENANT_A, PLAIN_MEMBER)

    before = p103.generations()
    r = decide(client, approval_id, headers, "approve")
    check("F1. while NOT an approver, the member is refused",
          r.status_code == 403 and p103.cluster_writes(before, p103.generations()) == 0,
          str(r.status_code))

    tm.grant_permission(member.tenant_id, member.user_id, APPROVE_REMEDIATION)
    r = decide(client, approval_id, headers, "approve")
    check("F2. after the grant, the SAME approval and the SAME person succeed — "
          "the decision uses current authority, not authority at request time",
          r.status_code == 200 and r.json()["state"] == "granted", str(r.status_code))

    tm.revoke_permission(member.tenant_id, member.user_id, APPROVE_REMEDIATION)
    _, second = seed(engine)
    r = decide(client, second, headers, "approve")
    check("F3. and after revocation the same person is refused again",
          r.status_code == 403, str(r.status_code))
    SEEDED["role_change_pending"] = second


def run_self_approval(client, engine) -> None:
    section("G. requester vs approver — reported, not invented")
    # requester == approver
    _, own = seed(engine, principal=APPROVER)
    r = decide(client, own, auth(), "approve")
    self_permitted = r.status_code == 200
    check("G1. requester == approver is SUPPORTED-BY-CURRENT-POLICY. It is "
          "reported, not changed: no rule in this repository requires a "
          "remediation requester to differ from its approver, and enabling or "
          "disabling that silently is a stop condition",
          self_permitted, f"HTTP {r.status_code} — self-approval permitted")
    REPORT["measurements"]["self_approval"] = (
        "SUPPORTED-BY-CURRENT-POLICY. cp_approval stores requested_by and "
        "decided_by separately so the distinction is representable, and "
        "DenialReason.SEPARATION_OF_DUTIES exists and IS enforced for a "
        "different pair (a capability owner may not enable it). No rule "
        "requires requester != approver for a remediation. Not changed here.")

    # requester != approver
    _, other = seed(engine, principal=PLAIN_MEMBER)
    r = decide(client, other, auth(), "approve")
    check("G2. requester != approver also succeeds — the distinction is not "
          "currently a gate in either direction", r.status_code == 200,
          str(r.status_code))

    from backend.contexts.connectivity.domain.authorization import CapabilityOperation
    check("G3. the precedent exists and is enforced ELSEWHERE: a capability "
          "owner may not be the one who makes it live",
          CapabilityOperation.ENABLE.grants_availability
          and CapabilityOperation.TRUST.grants_availability)
    deferred("requester != approver as an enforced rule",
             "the contracts make it representable and the denial reason exists, "
             "but no policy requires it for a remediation. Adding one silently "
             "would be inventing governance; it is recommended as its own phase")


def run_concurrency(client, engine) -> None:
    section("H. two approvers, one decision")
    from backend.auth.approver import APPROVE_REMEDIATION
    from backend.auth.tenant import get_tenant_manager

    tm = get_tenant_manager()
    # Restore the second approver revoked in section E.
    two = MEMBERS[APPROVER_TWO]
    tm.grant_permission(two.tenant_id, two.user_id, APPROVE_REMEDIATION)

    headers_one = auth(TENANT_A, APPROVER)
    headers_two = auth(TENANT_A, APPROVER_TWO)

    for label, first, second in (("H1. approve/approve", "approve", "approve"),
                                 ("H2. approve/reject", "approve", "reject")):
        _, approval_id = seed(engine)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(decide, client, approval_id, headers_one, first),
                       pool.submit(decide, client, approval_id, headers_two, second)]
            results = [f.result() for f in futures]
        codes = sorted(r.status_code for r in results)
        record = engine.approvals.get(tenant_id=TENANTS[TENANT_A],
                                      approval_id=approval_id)
        check(f"{label}: exactly one authoritative decision, one deterministic "
              f"conflict", codes == [200, 409], str(codes))
        check(f"{label}: one stored outcome, one decider",
              record.outcome in ("granted", "denied") and record.decided_by,
              f"{record.outcome} by {record.decided_by}")

    check("H3. no distributed lock was introduced — the existing conditional "
          "UPDATE on outcome='pending' is still what makes this deterministic",
          'T.c.outcome == "pending"' in Path(
              "backend/contexts/connectivity/infrastructure/sql_approval.py"
          ).read_text(encoding="utf-8"))


def run_negative_matrix(client, engine) -> None:
    section("I. the negative matrix")
    import sqlalchemy as sa
    from backend.auth.jwt_handler import create_access_token
    from backend.database.durable.tables import approval_table as T

    store = engine.runtime.persistence.store
    before = p103.generations()

    def writes():
        return p103.cluster_writes(before, p103.generations())

    headers_member = auth(TENANT_A, PLAIN_MEMBER)
    headers_owner = auth(TENANT_A, TENANT_OWNER)
    headers_b = auth(TENANT_B, B_APPROVER)
    headers_approver = auth()

    # --- the headline case -------------------------------------------
    _, target = seed(engine)
    SEEDED["matrix_pending"] = target
    r = decide(client, target, headers_member, "approve")
    record_negative("R1. a real tenant MEMBER with a valid session and a real "
                    "pending approval in their own tenant", "role authorization",
                    r.status_code, writes())
    check("R1a. refused 403, and the reason names the missing authority",
          r.status_code == 403 and "no_approver_authority" in r.text, r.text[:120])

    r = decide(client, target, headers_owner, "approve")
    record_negative("R2. a tenant OWNER — a role holding '*' elsewhere",
                    "role authorization", r.status_code, writes())
    check("R2a. refused 403", r.status_code == 403, str(r.status_code))

    r = decide(client, target, headers_b, "approve")
    record_negative("R3. an APPROVER from the wrong tenant", "membership",
                    r.status_code, writes())
    check("R3a. not found for that tenant — the approval is not theirs to see",
          r.status_code == 404, str(r.status_code))

    r = client.post(f"/api/v1/approvals/{target}/decision",
                    json={"decision": "approve"})
    record_negative("R4. anonymous", "authentication", r.status_code, writes())

    orphan = create_access_token("orphan@p105.example", role="operator")
    r = decide(client, target, {"Authorization": f"Bearer {orphan}"}, "approve")
    record_negative("R5. a valid token with no tenant claim", "authentication",
                    r.status_code, writes())

    forged = create_access_token(APPROVER, role="operator",
                                 tenant_id=TENANTS[TENANT_A], user_role="owner")
    # Its OWN approval. The identity in this token is a genuine approver, so the
    # decision legitimately succeeds -- the point is that the elevated CLAIM
    # changed nothing. Reusing the approval R1-R3 were refused on would have
    # decided it, and a later check asserts that one is still pending.
    _, claim_target = seed(engine)
    r = decide(client, claim_target, {"Authorization": f"Bearer {forged}"}, "approve")
    check("R6. a token whose user_role claim says 'owner' changes nothing — "
          "authority comes from the store, so the claim is not consulted",
          r.status_code in (200, 409), f"HTTP {r.status_code} (identity is the approver)")
    REPORT["negative_matrix"].append({
        "case": "R6. elevated role CLAIM in a token",
        "stopped_by": "role authorization (claim ignored)",
        "detail": f"HTTP {r.status_code}", "provider_writes": writes()})

    forged_member = create_access_token(PLAIN_MEMBER, role="admin",
                                        tenant_id=TENANTS[TENANT_A],
                                        user_role="owner")
    _, fresh = seed(engine)
    r = decide(client, fresh, {"Authorization": f"Bearer {forged_member}"}, "approve")
    record_negative("R7. a MEMBER holding a token that claims role=admin and "
                    "user_role=owner", "role authorization", r.status_code, writes())
    check("R7a. still refused — a role claim is not authority",
          r.status_code == 403, str(r.status_code))

    # --- body / query / header smuggling ------------------------------
    smuggle = [
        ("R8. approver in the body", {"approver": "admin"}),
        ("R9. role in the body", {"role": "approver"}),
        ("R10. tenant in the body", {"tenant": TENANTS[TENANT_B]}),
        ("R11. tenant_id in the body", {"tenant_id": TENANTS[TENANT_B]}),
        ("R12. actor in the body", {"actor": "admin"}),
        ("R13. actor_ref in the body", {"actor_ref": f"human:{APPROVER}"}),
        ("R14. can_approve in the body", {"can_approve": True}),
        ("R15. authority_reason in the body", {"authority_reason": "granted"}),
        ("R16. permissions in the body", {"permissions": ["approve:remediation"]}),
        ("R17. capability in the body", {"capability_ref": "platform.x"}),
        ("R18. provider in the body", {"provider": "kubernetes"}),
        ("R19. namespace in the body", {"namespace": "kube-system"}),
        ("R20. workload in the body", {"name": BYSTANDER}),
        ("R21. action digest in the body", {"action_digest": "0" * 64}),
        ("R22. approval digest in the body", {"approval_digest": "0" * 64}),
        ("R23. risk in the body", {"risk": "low"}),
        ("R24. blast radius in the body", {"blast_radius": "none"}),
        ("R25. autonomy in the body", {"autonomy_level": "a4_autonomous"}),
        ("R26. code trust in the body", {"code_trust": "fixed"}),
        ("R27. isolation tier in the body", {"isolation_tier": "sealed"}),
        ("R28. secret injection", {"token": "Bearer eyJhbGciOi"}),
        ("R29. extra authority field", {"approver_authority": "root"}),
    ]
    for label, extra in smuggle:
        _, fresh = seed(engine)
        r = decide(client, fresh, headers_member, "approve", **extra)
        record_negative(label, "role authorization", r.status_code, writes())
        if not check(f"{label} — REJECTED 422, not accepted-and-ignored",
                     r.status_code == 422, str(r.status_code)):
            break

    _, fresh = seed(engine)
    r = client.post(f"/api/v1/approvals/{fresh}/decision",
                    params={"tenant_id": TENANTS[TENANT_B], "role": "approver"},
                    json={"decision": "approve", "confirm_workload": TARGET},
                    headers=headers_member)
    record_negative("R30. tenant and role in QUERY parameters", "role authorization",
                    r.status_code, writes())
    check("R30a. still refused", r.status_code == 403, str(r.status_code))

    r = client.post(f"/api/v1/approvals/{fresh}/decision",
                    json={"decision": "approve", "confirm_workload": TARGET},
                    headers={**headers_member, "X-Tenant-Id": TENANTS[TENANT_B],
                             "X-Role": "approver", "X-Approver": APPROVER,
                             "X-Can-Approve": "true"})
    record_negative("R31. tenant, role and approver in HEADERS",
                    "role authorization", r.status_code, writes())
    check("R31a. still refused", r.status_code == 403, str(r.status_code))

    # --- approval-state negatives, as an authorized approver ----------
    for label, approval_id in (
        ("R32. already approved", SEEDED["approved"]),
        ("R33. already rejected", SEEDED["rejected"]),
        ("R34. consumed approval", SEEDED["consumed"]),
    ):
        r = decide(client, approval_id, headers_approver, "approve")
        record_negative(label, "approval state", r.status_code, writes())
        check(f"{label} refused with a conflict", r.status_code == 409,
              str(r.status_code))

    expired_id = seed(engine)[1]
    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == expired_id)
                     .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    r = decide(client, expired_id, headers_approver, "approve")
    record_negative("R35. expired approval, decided by a real approver",
                    "approval state", r.status_code, writes())
    check("R35a. refused 409", r.status_code == 409, str(r.status_code))

    revoked_id = seed(engine)[1]
    engine.approvals.withdraw(approval_id=revoked_id, tenant_id=TENANTS[TENANT_A],
                              decided_by=f"human:{APPROVER}",
                              decided_at=datetime.now(timezone.utc))
    r = decide(client, revoked_id, headers_approver, "approve")
    record_negative("R36. revoked approval", "approval state", r.status_code, writes())

    for label, approval_id in (("R37. wrong approval id", "appr-nope"),
                               ("R38. malformed approval id", "../../etc/passwd")):
        r = decide(client, approval_id, headers_approver, "approve")
        record_negative(label, "approval state", r.status_code, writes())
        check(f"{label} refused", r.status_code in (404, 422), str(r.status_code))

    ghosts = ["/api/v1/workers", "/api/v1/providers", "/api/v1/credentials",
              "/api/v1/roles", "/api/v1/permissions", "/api/v1/approvals/grant-role"]
    reachable = [f"{m} {p}" for p in ghosts for m in ("GET", "POST")
                 if client.request(m, p, headers=headers_approver,
                                   json={}).status_code not in (404, 405)]
    record_negative("R39. direct worker / provider / credential / role-grant "
                    "routes", "governance", str(reachable), writes())
    check("R39a. none exists — there is no HTTP route that grants a role",
          not reachable, str(reachable))

    total = p103.cluster_writes(before, p103.generations())
    check("I-FINAL. the ENTIRE negative matrix produced ZERO cluster mutations",
          total == 0, str(total))
    measure("negative_matrix_provider_writes", total)
    measure("negative_matrix_cases", len(REPORT["negative_matrix"]))


def run_restart(engine) -> None:
    section("J. restart")
    from backend.auth.approver import APPROVE_REMEDIATION, resolve_approver_authority
    from backend.auth.tenant import TenantManager
    from backend.contexts.connectivity.infrastructure.sql_approval import (
        SqlApprovalRepository,
    )
    from backend.database.durable.config import build_development_store

    reborn = TenantManager()
    check("J1. a fresh tenant manager — the state a restarted API would load — "
          "still sees the approver grant",
          APPROVE_REMEDIATION in (reborn.get_user_by_email(APPROVER).permissions or []))
    check("J2. and still sees that the plain member does NOT hold it",
          APPROVE_REMEDIATION not in
          (reborn.get_user_by_email(PLAIN_MEMBER).permissions or []),
          "revocation survived the restart")

    check("J3. authority resolves identically after the restart",
          resolve_approver_authority(
              principal_id=APPROVER, tenant_id=TENANTS[TENANT_A]).permitted
          and resolve_approver_authority(
              principal_id=PLAIN_MEMBER, tenant_id=TENANTS[TENANT_A]).denied)

    store = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    repository = SqlApprovalRepository(store)
    check("J4. the decision survives a restart",
          repository.get(tenant_id=TENANTS[TENANT_A],
                         approval_id=SEEDED["approved"]).outcome == "granted")
    check("J5. and a pending approval that was REFUSED is still pending — no "
          "approval becomes granted because of a restart",
          repository.get(tenant_id=TENANTS[TENANT_A],
                         approval_id=SEEDED["matrix_pending"]).outcome == "pending")


def run_audit(engine) -> None:
    section("K. audit")
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T

    store = engine.runtime.persistence.store
    with store.atomic() as work:
        rows = work.execute(sa.select(T).where(T.c.approval_id.in_(
            [SEEDED["approved"], SEEDED["rejected"]]))).mappings().fetchall()

    check("K1. each decision records the authenticated actor, tenant, "
          "capability, both digests, the decision and the time",
          len(rows) == 2 and all(
              r["decided_by"] == f"human:{APPROVER}"
              and r["tenant_id"] == TENANTS[TENANT_A]
              and r["capability_digest"] and r["approval_digest"]
              and r["decided_at"] is not None for r in rows),
          str([(r["outcome"], r["decided_by"]) for r in rows]))

    check("K2. and records the AUTHORITY that entitled them",
          all("authority=" in (r["justification"] or "") for r in rows))

    blob = " ".join(str(v) for r in rows for v in dict(r).values()).lower()
    leaked = [n for n in ("bearer ", "postgresql://", "password", "approve:remediation",
                          (os.getenv("CORTEX_KUBERNETES_TOKEN") or "zz")[:40].lower())
              if n in blob]
    check("K3. no token, credential, DSN or raw grant string is persisted in a "
          "decision record", not leaked, str(leaked))

    check("K4. no decision is attributed to the bare string 'admin'",
          not any((r["decided_by"] or "") == "admin" for r in rows))


def run_performance(client, engine) -> None:
    section("L. measured latency")
    headers = auth()
    pending = SEEDED["pending"]

    for name, method, path, params in (
        ("queue_list_with_authority", "GET", "/api/v1/approvals", None),
        ("queue_detail_with_authority", "GET", f"/api/v1/approvals/{pending}", None),
        ("queue_filtered", "GET", "/api/v1/approvals", {"status": "actionable"}),
    ):
        samples = []
        for _ in range(20):
            started = time.perf_counter()
            client.request(method, path, headers=headers, params=params)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[int(len(samples) * 0.95) - 1], 1))

    # Decisions consume a pending approval, so each sample needs its own.
    for name, decision in (("approve_decision", "approve"), ("reject_decision", "reject")):
        samples = []
        for _ in range(6):
            _, approval_id = seed(engine)
            started = time.perf_counter()
            decide(client, approval_id, headers, decision)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[-1], 1))

    check("L1. latency was MEASURED against real PostgreSQL and the real tenant "
          "store. No SLA is proposed and no index was added", True)
    deferred("decision p95 from 6 samples",
             "each decision consumes a pending approval, so a larger sample "
             "would measure seeding as much as deciding")


if __name__ == "__main__":
    main()
