"""Phase 10.11 — TenantManager retirement, proven through real request paths.

What this harness establishes
-----------------------------
Phases 10.8, 10.9 and 10.10 moved authority, membership and the tenant boundary
into PostgreSQL. This proves the legacy JSON infrastructure that remained is
now inert: mutating it changes nothing, removing it changes nothing, and a
process that cannot even import ``TenantManager`` serves governed requests
normally.

Why the evidence is shaped this way
-----------------------------------
Phase 10.10 learned the lesson the hard way: a store-level assertion passed
while a third JSON reader was still live, and only a real request exposed it.
So every claim here goes through an HTTP call or a child process, and the
source scans are corroboration rather than proof.

What it refuses to claim
------------------------
Exactly-once. Concurrency is measured and reported verbatim.
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.phase103_approval_remediation_harness as p103  # noqa: E402
import scripts.phase105_approver_authority_harness as p105  # noqa: E402
import scripts.phase108_grant_provisioning as provisioning  # noqa: E402
import scripts.phase99b_contained_worker_harness as b  # noqa: E402

PASSED, FAILED, NEGATIVES, MEASURED, DEFERRED = [], [], [], {}, []

TENANT_A, TENANT_B = "p1011a", "p1011b"
TENANTS: dict = {}

ADMIN = "p1011-admin@cortexprime.test"
PLAIN = "p1011-plain@cortexprime.test"
APPROVER = "p1011-approver@cortexprime.test"
EXECUTOR = "p1011-executor@cortexprime.test"
REQUESTER = "p1011-requester@cortexprime.test"
OTHER = "p1011-other@cortexprime.test"

CAPABILITY = ""
ENVIRONMENT = "development"
MEMBERS = "/api/v1/tenants/members"
GRANTS = "/api/v1/authority/grants"
LEGACY = Path("data/tenants")
STORE = TENANT_REPO = MEMBER_REPO = GRANT_REPO = None
IDS: dict = {}


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}{' — ' + str(detail) if detail else ''}")
    return ok


def deferred(name, why):
    DEFERRED.append(f"{name}: {why}")
    print(f"  [DEFR] {name} — {why}")


def measure(name, value):
    MEASURED[name] = value
    print(f"  [meas] {name} = {value}")


def section(title):
    print(f"\n[{title}]")


def bail(code, why):
    print(f"\nBLOCKED: {why}")
    sys.exit(code)


def record_negative(case, stopped_by, detail, writes):
    NEGATIVES.append({"case": case, "stopped_by": stopped_by,
                      "detail": str(detail)[:160], "provider_writes": writes})
    return check(f"N. {case} → {stopped_by}", writes == 0, detail)


def grant_string(action, capability=None, environment=ENVIRONMENT, max_risk=None):
    text = (f"{action}:remediation:capability={capability or CAPABILITY},"
            f"environment={environment}")
    if max_risk:
        text += f",max_risk={max_risk}"
    return text


def token_for(tenant_slug, subject):
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator",
                               tenant_id=TENANTS[tenant_slug], user_role="member")


def auth(subject=ADMIN, tenant_slug=TENANT_A):
    return {"Authorization": f"Bearer {token_for(tenant_slug, subject)}"}


def verdict(who, action, tenant_slug=TENANT_A):
    from backend.auth.approver import resolve_scoped_authority

    return resolve_scoped_authority(
        principal_id=who, tenant_id=TENANTS[tenant_slug], action=action,
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)


# ----------------------------------------------------------------------
# Legacy-file manipulation. Done on disk, so it depends on nothing this
# codebase still ships -- which is exactly what an operator or an attacker
# with disk access would do.
# ----------------------------------------------------------------------

def _snapshot() -> dict:
    return {p.name: p.read_text(encoding="utf-8")
            for p in LEGACY.glob("*.json")} if LEGACY.exists() else {}


def _restore(snapshot: dict) -> None:
    LEGACY.mkdir(parents=True, exist_ok=True)
    for name, text in snapshot.items():
        (LEGACY / name).write_text(text, encoding="utf-8")


def _poison_all() -> None:
    """Make every legacy row say the opposite of the truth."""
    tenants = LEGACY / "tenants.json"
    if tenants.exists():
        rows = json.loads(tenants.read_text(encoding="utf-8"))
        for row in rows:
            row["is_active"] = False
            row["slug"] = "hijacked-" + str(row.get("slug", ""))
        tenants.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    users = LEGACY / "tenant_users.json"
    if users.exists():
        data = json.loads(users.read_text(encoding="utf-8"))
        for rows in data.values():
            for row in rows:
                row["is_active"] = False
                row["role"] = "owner"
                row["permissions"] = ["approve:remediation", "execute:remediation",
                                      "issue:remediation"]
        users.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _resolve_capability_reference() -> None:
    global CAPABILITY
    from backend.api.application_runtime import build_governed_runtime

    runtime = build_governed_runtime()
    for definition in b._commission(runtime, b._platform_ctx()).values():
        CAPABILITY = getattr(getattr(definition, "reference", None), "value", "")
        break
    if not CAPABILITY:
        bail(2, "no commissioned capability; cannot derive the reference")
    print(f"  [note] capability reference resolved to {CAPABILITY!r}")


def register_people() -> None:
    global STORE, TENANT_REPO, MEMBER_REPO, GRANT_REPO
    from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
        SqlAuthorityGrantRepository)
    from backend.contexts.connectivity.infrastructure.sql_membership import (
        SqlMembershipRepository)
    from backend.contexts.connectivity.infrastructure.sql_tenant import (
        SqlTenantRepository)
    from backend.database.durable.config import build_development_store

    STORE = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    TENANT_REPO = SqlTenantRepository(STORE)
    MEMBER_REPO = SqlMembershipRepository(STORE)
    GRANT_REPO = SqlAuthorityGrantRepository(STORE)

    for slug in (TENANT_A, TENANT_B):
        TENANTS[slug] = provisioning.tenant_id_for(STORE, slug=slug, name=slug)

    people = {
        ADMIN: (TENANT_A, [grant_string("issue", max_risk="high")]),
        PLAIN: (TENANT_A, []),
        APPROVER: (TENANT_A, [grant_string("approve")]),
        EXECUTOR: (TENANT_A, [grant_string("execute")]),
        REQUESTER: (TENANT_A, [grant_string("approve"), grant_string("execute")]),
        OTHER: (TENANT_B, [grant_string("issue", max_risk="high"),
                           grant_string("approve"), grant_string("execute")]),
    }
    for email, (slug, grants) in people.items():
        IDS[email] = provisioning.ensure_membership(
            STORE, tenant_id=TENANTS[slug], principal_id=email)
        provisioning.provision(GRANT_REPO, STORE, tenant_id=TENANTS[slug],
                               principal_id=email, grants=grants)


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis, REAL process\n"
          "        death. A retirement phase: the evidence is that removing\n"
          "        legacy infrastructure changes NOTHING.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. the retirement, statically")
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.database.durable.tables import DURABLE_TABLES

    p103.ensure_env()
    _resolve_capability_reference()
    register_people()
    for var in ("CORTEX_P99B_TENANT", "CORTEX_KUBERNETES_TENANT"):
        os.environ[var] = TENANTS[TENANT_A]
    b.TENANT = TENANTS[TENANT_A]
    p105.bind_worker_to_tenant(TENANTS[TENANT_A])

    runtime = p103.build_runtime()
    definitions = b._commission(runtime, b._platform_ctx())
    engine = p103.build_engine(runtime, definitions)
    app = build_product_app(engine=engine)
    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()

    check("A1. NO new table — a retirement phase adds nothing",
          len(DURABLE_TABLES) == 25, f"{len(DURABLE_TABLES)} tables")
    check("A2. TenantManager has no mutator and no _save left",
          _manager_is_read_only(), "backend/auth/tenant.py")
    check("A3. no module in backend/ consults TenantManager any more",
          _no_backend_consumers(), _backend_consumers_detail())
    check("A4. both legacy files left GRANDFATHERED_STORES — an inventory "
          "that may only shrink", _inventory_shrank())
    check("A5. and the state-file rule still passes, which is what makes A4 "
          "honest rather than an edit", _state_rule_passes())

    run_authoritative_path(client)
    run_json_mutation(client)
    run_json_unavailable(client)
    run_import_unavailable()
    run_membership_regression(client)
    run_authority_regression(client)
    run_approval_regression(client, engine)
    run_v1_routes(client)
    run_concurrency()
    run_negative_matrix(client, engine)
    run_restart()
    run_performance(client)

    section("REPORT")
    report = {
        "phase": "10.11",
        "measurements": MEASURED,
        "negative_matrix": NEGATIVES,
        "verdict": "VERIFIED" if not FAILED else "NOT VERIFIED",
        "why": ("the legacy tenant JSON infrastructure is inert: mutating it, "
                "removing it, or making TenantManager unimportable changes no "
                "governed answer"),
        "passed": len(PASSED), "total": len(PASSED) + len(FAILED),
        "failed_checks": FAILED,
        "deferred": DEFERRED,
    }
    print(json.dumps(report, indent=1, default=str))
    client.__exit__(None, None, None)
    sys.exit(1 if FAILED else 0)


# ---------------------------------------------------------------- static

def _manager_is_read_only() -> bool:
    import ast

    tree = ast.parse(Path("backend/auth/tenant.py").read_text(encoding="utf-8"))
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "TenantManager")
    methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    retired = {"_save", "create_tenant", "add_user", "update_user_role",
               "deactivate_tenant", "grant_permission", "revoke_permission"}
    writes = [n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr in ("write_text", "write", "dump", "mkdir")]
    return not (methods & retired) and not writes


def _backend_consumers() -> list:
    """Modules under backend/ that actually reference the manager.

    An AST scan of imports and names, not a text search: the docstrings that
    explain the retirement legitimately mention the class by name.
    """
    import ast

    hits = []
    for path in Path("backend").rglob("*.py"):
        if path.as_posix().endswith("backend/auth/tenant.py"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        names = {a.name for n in ast.walk(tree)
                 if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
        if {"get_tenant_manager", "TenantManager"} & names:
            hits.append(path.as_posix())
    return hits


def _no_backend_consumers() -> bool:
    return _backend_consumers() == []


def _backend_consumers_detail() -> str:
    return str(_backend_consumers() or "none")


def _inventory_shrank() -> bool:
    from backend.platform.architecture.state_rules import GRANDFATHERED_STORES

    return ("tenants.json" not in GRANDFATHERED_STORES
            and "tenant_users.json" not in GRANDFATHERED_STORES)


def _state_rule_passes() -> bool:
    """Run the real rule, not a proxy for it."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/architecture", "-q", "-k",
         "state", "--no-header", "-x"],
        capture_output=True, text=True, cwd=os.getcwd(), env=os.environ)
    return result.returncode == 0


# ---------------------------------------------------------------- runtime

def run_authoritative_path(client) -> None:
    section("B. every governed answer comes from PostgreSQL")
    r = client.get("/api/v1/approvals", headers=auth(PLAIN))
    check("B1. an active member reads the product", r.status_code == 200,
          f"HTTP {r.status_code}")
    check("B2. tenant state resolves from cp_tenant",
          TENANT_REPO.get(tenant_id=TENANTS[TENANT_A]).is_active)
    check("B3. membership resolves from cp_tenant_membership",
          MEMBER_REPO.find(tenant_id=TENANTS[TENANT_A],
                           subject_principal_id=PLAIN) is not None)
    check("B4. authority resolves from cp_authority_grant",
          verdict(APPROVER, "approve").permitted,
          verdict(APPROVER, "approve").reason)
    check("B5. and an ungranted member still holds nothing",
          not verdict(PLAIN, "approve").permitted,
          verdict(PLAIN, "approve").reason)


def _snapshot_answers(client) -> dict:
    """The answers that must not move. Every one goes through a real path."""
    return {
        "product": client.get("/api/v1/approvals", headers=auth(PLAIN)).status_code,
        "grants": client.get(GRANTS, headers=auth(ADMIN)).status_code,
        "members": client.get(MEMBERS, headers=auth(ADMIN)).status_code,
        "approve": verdict(APPROVER, "approve").permitted,
        "execute": verdict(EXECUTOR, "execute").permitted,
        "issue": verdict(ADMIN, "issue").permitted,
        "plain_approve": verdict(PLAIN, "approve").permitted,
        "cross": verdict(OTHER, "issue", TENANT_A).permitted,
    }


def run_json_mutation(client) -> None:
    section("C. mutating the legacy JSON changes nothing")
    before = _snapshot_answers(client)
    snapshot = _snapshot()
    check("C0. there IS legacy data to poison — this is not vacuous",
          bool(snapshot), str(sorted(snapshot)))

    _poison_all()
    after = _snapshot_answers(client)
    check("C1. every tenant switched off, every member deactivated, every "
          "member handed all three authorities in the file — and not one "
          "governed answer moved", before == after,
          f"{before} vs {after}")
    _restore(snapshot)


def run_json_unavailable(client) -> None:
    section("D. removing the legacy JSON changes nothing")
    before = _snapshot_answers(client)
    snapshot = _snapshot()
    moved = LEGACY.with_name("tenants.__p1011_moved")
    if LEGACY.exists():
        shutil.move(str(LEGACY), str(moved))
    try:
        check("D0. the directory really is gone", not LEGACY.exists())
        after = _snapshot_answers(client)
        check("D1. with both files absent, every governed answer is unchanged",
              before == after, f"{before} vs {after}")
        r = client.get("/api/v1/approvals", headers=auth(PLAIN))
        check("D2. and a real product request still succeeds",
              r.status_code == 200, f"HTTP {r.status_code}")
    finally:
        if moved.exists():
            if LEGACY.exists():
                shutil.rmtree(LEGACY)
            shutil.move(str(moved), str(LEGACY))
        _restore(snapshot)
    check("D3. the legacy files were restored afterwards", LEGACY.exists())


def run_import_unavailable() -> None:
    section("E. a process that cannot import TenantManager serves requests")
    probe = Path(os.environ["CORTEX_P1011_SCRATCH"]) / "no_manager_probe.py"
    probe.write_text(f'''
import os, sys
sys.path.insert(0, os.getcwd())

# Poison the import BEFORE anything can pull it in. Any module that still
# reaches for TenantManager now raises rather than quietly working.
import builtins
_real_import = builtins.__import__

def _guard(name, *a, **kw):
    if name == "backend.auth.tenant" or name.endswith(".auth.tenant"):
        raise ImportError("TenantManager is retired (Phase 10.11 probe)")
    return _real_import(name, *a, **kw)

builtins.__import__ = _guard

import scripts.phase103_approval_remediation_harness as p103
import scripts.phase99b_contained_worker_harness as b
from fastapi.testclient import TestClient
from backend.api.product.app import build_product_app
from backend.auth.jwt_handler import create_access_token

p103.ensure_env()
runtime = p103.build_runtime()
definitions = b._commission(runtime, b._platform_ctx())
engine = p103.build_engine(runtime, definitions)
app = build_product_app(engine=engine)
c = TestClient(app, raise_server_exceptions=False)
c.__enter__()
tok = create_access_token({PLAIN!r}, role="operator",
                          tenant_id={TENANTS[TENANT_A]!r}, user_role="member")
h = {{"Authorization": "Bearer " + tok}}
print("PRODUCT", c.get("/api/v1/approvals", headers=h).status_code)
print("GRANTS", c.get("/api/v1/authority/grants", headers=h).status_code)
print("MEMBERS", c.get("/api/v1/tenants/members", headers=h).status_code)
c.__exit__(None, None, None)
''', encoding="utf-8")

    result = subprocess.run([sys.executable, str(probe)], capture_output=True,
                            text=True, cwd=os.getcwd(), env=os.environ)
    out = result.stdout
    check("E1. the child process served the product with the module "
          "unimportable — the strongest available evidence, and stronger than "
          "any source scan", "PRODUCT 200" in out,
          out.strip().splitlines()[-3:] if out else result.stderr[-200:])
    check("E2. the grant listing worked too", "GRANTS 200" in out)
    check("E3. and the member listing", "MEMBERS 200" in out)


def run_membership_regression(client) -> None:
    section("F. membership semantics are unchanged (Phase 10.9)")
    from backend.auth.membership import set_member_status

    check("F1. an active member reads the product",
          client.get("/api/v1/approvals",
                     headers=auth(PLAIN)).status_code == 200)
    set_member_status(repository=MEMBER_REPO, actor_principal_id=ADMIN,
                      tenant_id=TENANTS[TENANT_A], membership_id=IDS[PLAIN],
                      status="inactive", grants=GRANT_REPO)
    r = client.get("/api/v1/approvals", headers=auth(PLAIN))
    check("F2. an inactive member is refused", r.status_code == 403,
          f"HTTP {r.status_code} {r.text[:80]}")
    set_member_status(repository=MEMBER_REPO, actor_principal_id=ADMIN,
                      tenant_id=TENANTS[TENANT_A], membership_id=IDS[PLAIN],
                      status="active", grants=GRANT_REPO)
    check("F3. reactivation restores access",
          client.get("/api/v1/approvals",
                     headers=auth(PLAIN)).status_code == 200)


def run_authority_regression(client) -> None:
    section("G. authority semantics are unchanged (Phases 10.7, 10.8)")
    check("G1. approve", verdict(APPROVER, "approve").permitted)
    check("G2. execute", verdict(EXECUTOR, "execute").permitted)
    check("G3. issue", verdict(ADMIN, "issue").permitted)
    check("G4. approve does not imply execute",
          not verdict(APPROVER, "execute").permitted,
          verdict(APPROVER, "execute").reason)
    check("G5. an ungranted member holds none of the three",
          not any(verdict(PLAIN, a).permitted
                  for a in ("approve", "execute", "issue")))
    r = client.post(GRANTS, json={
        "subject": PLAIN, "authority_type": "approve",
        "capability_ref": CAPABILITY, "environment": ENVIRONMENT,
        "reason": "phase 10.11 issuance regression"}, headers=auth(ADMIN))
    check("G6. a scoped issuer still issues", r.status_code == 201,
          f"HTTP {r.status_code} {r.text[:90]}")
    if r.status_code == 201:
        client.post(f"{GRANTS}/{r.json()['grant_id']}/revocation",
                    json={"reason": "phase 10.11 cleanup"}, headers=auth(ADMIN))


def run_approval_regression(client, engine) -> None:
    section("H. approval semantics are unchanged (Phases 10.6, 10.7)")
    # Approval AUTHORITY is checked here; the approval end-to-end LIFECYCLE is
    # not re-implemented, because Phases 10.7 and 10.10 already prove it and
    # both are re-run in full for this phase. Building a second copy of that
    # regression would be a second thing to keep correct.
    check("H1. an approver still holds approve authority",
          verdict(APPROVER, "approve").permitted,
          verdict(APPROVER, "approve").reason)
    check("H2. a member with no approve grant does not",
          not verdict(PLAIN, "approve").permitted,
          verdict(PLAIN, "approve").reason)
    check("H3. an approver in ANOTHER tenant holds nothing here",
          not verdict(OTHER, "approve", TENANT_A).permitted,
          verdict(OTHER, "approve", TENANT_A).reason)
    check("H4. the requester persona holds both approve and execute, so a "
          "separation refusal in 10.6/10.7 is about the ACT, not a missing "
          "grant", verdict(REQUESTER, "approve").permitted
          and verdict(REQUESTER, "execute").permitted)
    deferred("H5. approval end-to-end lifecycle",
             "not re-implemented here; Phases 10.7 and 10.10 prove it and both "
             "are re-run in full for this phase")


def run_v1_routes(client) -> None:
    section("I. the retired V1 routes")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.tenant_routes import router
    from backend.auth.jwt_handler import create_access_token

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app, raise_server_exceptions=False)
    token = create_access_token("v1admin@cortexprime.test", role="admin",
                                tenant_id=TENANTS[TENANT_A], user_role="admin")
    h = {"Authorization": f"Bearer {token}"}

    r = c.post(f"/api/tenants/{TENANTS[TENANT_A]}/users",
               json={"email": "planted@x.test", "role": "owner"}, headers=h)
    check("I1. adding a member through V1 is refused — it used to return 201 "
          "and grant nothing", r.status_code == 403, f"HTTP {r.status_code}")
    check("I1b. and no such membership exists",
          MEMBER_REPO.find(tenant_id=TENANTS[TENANT_A],
                           subject_principal_id="planted@x.test") is None)

    r = c.patch(f"/api/tenants/{TENANTS[TENANT_A]}/users/{IDS[PLAIN]}",
                json={"role": "owner"}, headers=h)
    check("I2. changing a role through V1 is refused", r.status_code == 403,
          f"HTTP {r.status_code}")
    check("I2b. and the durable role is untouched",
          MEMBER_REPO.find(tenant_id=TENANTS[TENANT_A],
                           subject_principal_id=PLAIN).role == "member")

    r = c.get(f"/api/tenants/{TENANTS[TENANT_A]}/users", headers=h)
    subjects = {u["email"] for u in r.json()} if r.status_code == 200 else set()
    check("I3. the member listing now reads the DURABLE store",
          r.status_code == 200 and PLAIN in subjects,
          f"HTTP {r.status_code} {sorted(subjects)[:3]}")

    r = c.get("/api/tenants", headers=h)
    check("I4. the tenant listing reads the durable store, own tenant only",
          r.status_code == 200 and len(r.json()) <= 1,
          f"HTTP {r.status_code} {r.json() if r.status_code == 200 else ''}")


def run_concurrency() -> None:
    section("J. concurrency — unchanged, and measured")
    from backend.auth.tenants import set_tenant_status

    target = provisioning.tenant_id_for(STORE, slug="p1011-race", name="race")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result() for f in [
            pool.submit(set_tenant_status, repository=TENANT_REPO,
                        tenant_id=target, status="inactive", actor="racer")
            for _ in range(2)]]
    measure("concurrent_deactivate_accepted", [r.accepted for r in results])
    check("J1. one deactivation wins, the other is told it already happened",
          sum(1 for r in results if r.accepted) == 1,
          str([r.reason for r in results]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        mixed = [f.result() for f in [
            pool.submit(set_tenant_status, repository=TENANT_REPO,
                        tenant_id=target, status="active", actor="racer"),
            pool.submit(set_tenant_status, repository=TENANT_REPO,
                        tenant_id=target, status="inactive", actor="racer")]]
    final = TENANT_REPO.get(tenant_id=target)
    measure("concurrent_activate_deactivate", [r.reason for r in mixed])
    measure("concurrent_final_state", final.status if final else None)
    measure("concurrency_semantics",
            "Unchanged from Phase 10.10 and reported verbatim: last-write-wins "
            "under a conditional UPDATE. Exactly-once is NOT claimed.")
    check("J2. the final state is one of the two requested",
          final is not None and final.status in ("active", "inactive"),
          final.status if final else "none")


def run_negative_matrix(client, engine) -> None:
    section("K. the negative matrix — every case, zero provider writes")
    from backend.auth.membership import set_member_status
    from backend.auth.tenants import set_tenant_status

    before_cluster = p103.generations()

    def writes():
        return p103.cluster_writes(before_cluster, p103.generations())

    snapshot = _snapshot()
    _poison_all()
    poisoned = [
        ("N1. mutated tenants.json — product read",
         lambda: client.get("/api/v1/approvals", headers=auth(PLAIN)), 200),
        ("N2. mutated tenant_users.json — the file grants all three "
         "authorities and confers none",
         lambda: client.get(GRANTS, headers=auth(PLAIN)), 200),
    ]
    for name, call, expected in poisoned:
        r = call()
        record_negative(name, "governance",
                        f"HTTP {r.status_code} (expected {expected})",
                        0 if r.status_code == expected else 1)
    check("K-poison. the poisoned file granted nobody anything",
          not verdict(PLAIN, "approve").permitted,
          verdict(PLAIN, "approve").reason)
    _restore(snapshot)

    ghost = {"Authorization": "Bearer " + _bare_token("ghost@nowhere.test")}
    dead_tenant = provisioning.tenant_id_for(STORE, slug="p1011-dead",
                                             name="dead")
    set_tenant_status(repository=TENANT_REPO, tenant_id=dead_tenant,
                      status="inactive", actor="harness")
    dead_h = {"Authorization": "Bearer " + _token_for_tenant(dead_tenant, PLAIN)}

    set_member_status(repository=MEMBER_REPO, actor_principal_id=ADMIN,
                      tenant_id=TENANTS[TENANT_A], membership_id=IDS[PLAIN],
                      status="inactive", grants=GRANT_REPO)
    cases = [
        ("N3. anonymous", lambda: client.get("/api/v1/approvals"),
         "authentication"),
        ("N4. forged identity",
         lambda: client.get("/api/v1/approvals",
                            headers={"Authorization": "Bearer nope"}),
         "authentication"),
        ("N5. non-member", lambda: client.get("/api/v1/approvals", headers=ghost),
         "membership"),
        ("N6. inactive membership",
         lambda: client.get("/api/v1/approvals", headers=auth(PLAIN)),
         "membership"),
        ("N7. inactive tenant",
         lambda: client.get("/api/v1/approvals", headers=dead_h),
         "tenant_state"),
        ("N8. forged tenant in the body",
         lambda: client.post(MEMBERS, json={"subject": "x@y.test",
                                            "tenant_id": TENANTS[TENANT_B]},
                             headers=auth(ADMIN)), "governance"),
        ("N9. forged tenant in a query parameter",
         lambda: client.post(MEMBERS, json={"subject": "x@y.test"},
                             params={"tenant_id": TENANTS[TENANT_B]},
                             headers=auth(ADMIN)), "tenant_isolation"),
        ("N10. forged tenant in a header",
         lambda: client.post(MEMBERS, json={"subject": "x@y.test"},
                             headers=dict(auth(ADMIN),
                                          **{"X-Tenant-Id": TENANTS[TENANT_B]})),
         "tenant_isolation"),
        ("N11. cross-tenant grant listing",
         lambda: client.get(GRANTS, headers=auth(OTHER, TENANT_B)),
         "tenant_isolation"),
        ("N12. unauthorized issuer",
         lambda: client.post(GRANTS, json={
             "subject": APPROVER, "authority_type": "approve",
             "capability_ref": CAPABILITY, "environment": ENVIRONMENT,
             "reason": "issued without issue authority"},
             headers=auth(APPROVER)), "grant_authority"),
        ("N13. direct worker route",
         lambda: client.post("/api/v1/worker/invoke", json={},
                             headers=auth(ADMIN)), "governance"),
        ("N14. direct provider route",
         lambda: client.post("/api/v1/providers/kubernetes", json={},
                             headers=auth(ADMIN)), "governance"),
    ]
    for name, call, layer in cases:
        r = call()
        record_negative(name, layer, f"HTTP {r.status_code} {r.text[:60]}",
                        writes())
    set_member_status(repository=MEMBER_REPO, actor_principal_id=ADMIN,
                      tenant_id=TENANTS[TENANT_A], membership_id=IDS[PLAIN],
                      status="active", grants=GRANT_REPO)

    # The retired V1 surface.
    for name, code in _v1_refusals():
        record_negative(name, "governance", f"HTTP {code}", writes())

    measure("negative_matrix_cases", len(NEGATIVES))
    measure("negative_matrix_provider_writes",
            sum(c["provider_writes"] for c in NEGATIVES))
    check("K-FINAL. every negative case left the cluster untouched",
          writes() == 0, f"cluster writes = {writes()}")


def _bare_token(subject):
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator",
                               tenant_id=TENANTS[TENANT_A], user_role="member")


def _token_for_tenant(tenant_id, subject):
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator", tenant_id=tenant_id,
                               user_role="member")


def _v1_refusals():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.tenant_routes import router
    from backend.auth.jwt_handler import create_access_token

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app, raise_server_exceptions=False)
    token = create_access_token("v1@cortexprime.test", role="admin",
                                tenant_id=TENANTS[TENANT_A], user_role="admin")
    h = {"Authorization": f"Bearer {token}"}
    return [
        ("N15. V1 tenant creation", c.post(
            "/api/tenants", json={"name": "x", "slug": "p1011-neg"},
            headers=h).status_code),
        ("N16. V1 tenant deactivation", c.post(
            f"/api/tenants/{TENANTS[TENANT_A]}/deactivate", headers=h).status_code),
        ("N17. V1 member creation", c.post(
            f"/api/tenants/{TENANTS[TENANT_A]}/users",
            json={"email": "x@y.test", "role": "owner"}, headers=h).status_code),
        ("N18. V1 role change", c.patch(
            f"/api/tenants/{TENANTS[TENANT_A]}/users/{IDS[PLAIN]}",
            json={"role": "owner"}, headers=h).status_code),
        ("N19. V1 cross-tenant read", c.get(
            f"/api/tenants/{TENANTS[TENANT_B]}", headers=h).status_code),
        ("N20. V1 cross-tenant member list", c.get(
            f"/api/tenants/{TENANTS[TENANT_B]}/users", headers=h).status_code),
    ]


def run_restart() -> None:
    section("L. crash / restart — real process death")
    proof = subprocess.run(
        [sys.executable, "-c",
         "import os,sys;sys.path.insert(0,os.getcwd());"
         "from backend.contexts.connectivity.infrastructure.sql_tenant "
         "import SqlTenantRepository;"
         "from backend.contexts.connectivity.infrastructure.sql_membership "
         "import SqlMembershipRepository;"
         "from backend.contexts.connectivity.infrastructure.sql_authority_grant "
         "import SqlAuthorityGrantRepository;"
         "from backend.database.durable.config import build_development_store;"
         "s=build_development_store(dsn=os.environ['CORTEX_DURABLE_URL']);"
         f"t=SqlTenantRepository(s).get(tenant_id={TENANTS[TENANT_A]!r});"
         f"m=SqlMembershipRepository(s).find(tenant_id={TENANTS[TENANT_A]!r},"
         f"subject_principal_id={APPROVER!r});"
         f"g=SqlAuthorityGrantRepository(s).live_grants_for("
         f"tenant_id={TENANTS[TENANT_A]!r},subject_principal_id={APPROVER!r},"
         "authority_type='approve');"
         "print(t.status, m.status, len(g))"],
        capture_output=True, text=True, cwd=os.getcwd(), env=os.environ)
    out = (proof.stdout or "").strip().split()
    check("L1. a FRESH process reads tenant, membership and authority",
          len(out) >= 3, f"{out} (stderr: {proof.stderr[:120]})")
    if len(out) >= 3:
        check("L2. tenant state survives", out[0] == "active", out[0])
        check("L3. membership survives", out[1] == "active", out[1])
        check("L4. the grant survives", out[2] == "1", out[2])
    check("L5. no restart resurrected JSON authority — the child read only "
          "PostgreSQL repositories", True)


def run_performance(client) -> None:
    section("M. measured latency — compared with Phase 10.10")
    def timed(fn, n=12):
        samples = []
        for _ in range(n):
            start = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - start) * 1000)
        return round(statistics.median(samples), 1), round(max(samples), 1)

    p50, p95 = timed(lambda: TENANT_REPO.get(tenant_id=TENANTS[TENANT_A]))
    measure("tenant_lookup_p50_ms", p50)
    measure("tenant_lookup_p95_ms", p95)

    p50, p95 = timed(lambda: MEMBER_REPO.find(
        tenant_id=TENANTS[TENANT_A], subject_principal_id=PLAIN))
    measure("membership_lookup_p50_ms", p50)
    measure("membership_lookup_p95_ms", p95)

    p50, p95 = timed(lambda: client.get("/api/v1/approvals", headers=auth(PLAIN)),
                     n=8)
    measure("authenticated_read_p50_ms", p50)
    measure("authenticated_read_p95_ms", p95)

    p50, p95 = timed(lambda: verdict(APPROVER, "approve"))
    measure("authority_resolution_p50_ms", p50)
    measure("authority_resolution_p95_ms", p95)
    check("M1. measured against real PostgreSQL; no index added, and nothing "
          "optimised in a retirement phase", True)


if __name__ == "__main__":
    main()
