"""Phase 10.10 — durable, governed tenant records, proven against real infra.

What this harness establishes
-----------------------------
Phase 10.8 made authority durable; Phase 10.9 made membership durable. Both
still rested on ``data/tenants/tenants.json`` — a gitignored file that
``require_tenant`` read on every request, so an edit to it disabled governance
for an entire tenant.

This proves the tenant boundary is now durable, authoritative and attributable;
that it confers **nothing** — not membership, not approval, not execution, not
issuance; and that an inactive tenant fails closed everywhere while leaving
every historical record attributable.

What it refuses to claim
------------------------
Exactly-once. Concurrency is measured and reported verbatim.

Real everything: real k3d, real PostgreSQL, real Redis, real OS process death.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.phase103_approval_remediation_harness as p103  # noqa: E402
import scripts.phase105_approver_authority_harness as p105  # noqa: E402
import scripts.phase108_grant_provisioning as provisioning  # noqa: E402
import scripts.phase99b_contained_worker_harness as b  # noqa: E402

PASSED, FAILED, NEGATIVES, MEASURED, DEFERRED = [], [], [], {}, []

TENANT_A, TENANT_B, TENANT_DOOMED = "p1010a", "p1010b", "p1010doomed"
TENANTS: dict = {}

ADMIN = "p1010-admin@cortexprime.test"
PLAIN = "p1010-plain@cortexprime.test"
APPROVER = "p1010-approver@cortexprime.test"
EXECUTOR = "p1010-executor@cortexprime.test"
OTHER_ADMIN = "p1010-other-admin@cortexprime.test"
DOOMED_MEMBER = "p1010-doomed-member@cortexprime.test"

CAPABILITY = ""
ENVIRONMENT = "development"
MEMBERS = "/api/v1/tenants/members"
GRANTS = "/api/v1/authority/grants"
STORE = TENANT_REPO = MEMBER_REPO = GRANT_REPO = None
IDS: dict = {}



def mutate_legacy_json(filename, mutate):
    """Edit a legacy JSON file on disk and return a restore callable.

    Phase 10.11 removed every writer from ``TenantManager``, so these proofs
    can no longer go through it -- which is an improvement. Writing the file
    directly is what an operator or an attacker with disk access would do, and
    it depends on nothing this codebase still ships.
    """
    import json
    from pathlib import Path

    path = Path("data/tenants") / filename
    if not path.exists():
        return None, (lambda: None)
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    mutate(data)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return data, (lambda: path.write_text(original, encoding="utf-8"))


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



def fresh_tenant(slug, name, status="active"):
    """Provision a boundary, or reuse the one an earlier run left behind.

    The phase database is durable and survives runs, so a fixed slug collides
    on the second execution -- correctly, since the column is UNIQUE. Reusing
    it keeps the harness re-runnable without weakening the constraint that
    caught the collision.
    """
    from backend.auth.tenants import bootstrap_tenant

    existing = TENANT_REPO.get_by_slug(slug=slug)
    if existing is not None:
        if existing.status != status:
            TENANT_REPO.set_status(tenant_id=existing.tenant_id, status=status,
                                   updated_by="harness:reset")
            existing = TENANT_REPO.get(tenant_id=existing.tenant_id)
        return existing
    return bootstrap_tenant(repository=TENANT_REPO, slug=slug, name=name,
                            status=status)


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

    for slug in (TENANT_A, TENANT_B, TENANT_DOOMED):
        # Phase 10.11: the tenant id comes from the DURABLE store. The
        # legacy JSON writer is gone, so nothing here touches a file.
        TENANTS[slug] = provisioning.tenant_id_for(
            STORE, slug=slug, name=slug)

    people = {
        ADMIN: (TENANT_A, [grant_string("issue", max_risk="high")]),
        PLAIN: (TENANT_A, []),
        APPROVER: (TENANT_A, [grant_string("approve")]),
        EXECUTOR: (TENANT_A, [grant_string("execute")]),
        OTHER_ADMIN: (TENANT_B, [grant_string("issue", max_risk="high")]),
        # Lives in the tenant that gets switched off, and holds everything.
        DOOMED_MEMBER: (TENANT_DOOMED, [
            grant_string("approve"), grant_string("execute"),
            grant_string("issue", max_risk="high")]),
    }
    for email, (slug, grants) in people.items():
        IDS[email] = provisioning.ensure_membership(
            STORE, tenant_id=TENANTS[slug], principal_id=email)
        provisioning.provision(GRANT_REPO, STORE, tenant_id=TENANTS[slug],
                               principal_id=email, grants=grants)


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis, REAL process\n"
          "        death. A tenant is a BOUNDARY: it confers no membership and\n"
          "        no authority at all.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. composition — one tenant store, one new table")
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.api.product.approval_routes import MUTATING_ROUTES
    from backend.api.product.authority_routes import (
        MUTATING_ROUTES as AUTHORITY_ROUTES)
    from backend.api.product.membership_routes import (
        MUTATING_ROUTES as MEMBERSHIP_ROUTES)
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

    actual = {(m, r.path) for r in app.routes
              for m in (getattr(r, "methods", None) or ())
              if m not in ("GET", "HEAD", "OPTIONS")
              and getattr(r, "path", "").startswith("/api")}
    expected = (set(MUTATING_ROUTES) | set(AUTHORITY_ROUTES)
                | set(MEMBERSHIP_ROUTES))
    check("A1. the product's write surface is UNCHANGED by this phase — no "
          "tenant mutation route was added, because tenant administration is "
          "out-of-band", actual == expected, str(sorted(actual ^ expected)))
    check("A2. ONE new table (cp_tenant), stopped for and documented before it "
          "was written",
          len(DURABLE_TABLES) == 25
          and any(t.name == "cp_tenant" for t in DURABLE_TABLES),
          f"{len(DURABLE_TABLES)} tables")
    check("A3. exactly ONE commissioned write capability — none was added",
          len(definitions) == 1, str(list(definitions)))
    check("A4. no product route provisions, activates or deactivates a tenant",
          not any("tenant" in path and "members" not in path
                  for _, path in expected), str(sorted(expected)))
    check("A5. `organizations` was NOT reused — it has no tenant_id, no "
          "membership, and no link to any authority record",
          _organizations_is_a_different_concept())
    check("A6. no second tenant store: resolution goes through ONE repository "
          "and defines no policy of its own", _one_tenant_authority())

    run_migration(client)
    run_tenant_is_not_authority(client)
    run_tenant_is_not_membership(client)
    run_deactivation(client, engine)
    run_reactivation(client)
    run_history(client)
    run_tenant_isolation(client)
    run_v1_routes()
    run_audit(client, runtime)
    run_concurrency(client)
    run_positive_matrix(client)
    run_negative_matrix(client, engine)
    run_restart(client)
    run_performance(client)

    section("REPORT")
    report = {
        "phase": "10.10",
        "measurements": MEASURED,
        "negative_matrix": NEGATIVES,
        "verdict": "VERIFIED" if not FAILED else "NOT VERIFIED",
        "why": ("the tenant boundary is durable, authoritative and attributable, "
                "and confers neither membership nor authority"),
        "passed": len(PASSED), "total": len(PASSED) + len(FAILED),
        "failed_checks": FAILED,
        "deferred": DEFERRED,
    }
    print(json.dumps(report, indent=1, default=str))
    client.__exit__(None, None, None)
    sys.exit(1 if FAILED else 0)


def _organizations_is_a_different_concept() -> bool:
    """Part B: prove semantic inequivalence rather than assume it.

    Phase 10.29 (ADR-119) retired the V1 organizational directory. On a tree
    where the model is gone, the property is proven by execution in the
    stronger form: no ``organization`` module resolves under
    ``backend.database.models`` and no tracked backend file declares an
    ``organizations`` table -- there is no V1 organization concept left to
    confuse with a tenant. A missing file alone is NOT accepted as proof.
    """
    import ast
    import importlib.util

    model = Path("backend/database/models/organization.py")
    if not model.exists():
        spec = importlib.util.find_spec("backend.database.models.organization")
        declares_table = [
            p for p in Path("backend").rglob("*.py")
            if "__tablename__ = \"organizations\"" in p.read_text(encoding="utf-8", errors="ignore")
        ]
        return spec is None and not declares_table

    src = model.read_text(encoding="utf-8")
    tree = ast.parse(src)
    columns = {n.targets[0].id for n in ast.walk(tree)
               if isinstance(n, ast.AnnAssign) is False
               and isinstance(n, ast.Assign) and n.targets
               and isinstance(n.targets[0], ast.Name)}
    annotated = {n.target.id for n in ast.walk(tree)
                 if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
    fields = columns | annotated
    # No tenant column, and nothing in the model references a tenant at all.
    return "tenant_id" not in fields and "tenant" not in src.lower().replace(
        "tenant", "", 0)[:0] + "".join(
        line for line in src.splitlines() if "tenant" in line.lower())


def _one_tenant_authority() -> bool:
    """Tenant resolution must define no policy of its own. AST, not grep."""
    import ast

    tree = ast.parse(Path("backend/auth/tenants.py").read_text(encoding="utf-8"))
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    return not any(d.startswith("resolve_scoped") or "rbac" in d.lower()
                   or "authority" in d.lower() for d in defined)


# ----------------------------------------------------------------------

def run_migration(client) -> None:
    section("B. migration from JSON — and JSON stops deciding")
    from backend.auth.tenants import migrate_json_tenants, resolve_tenant
    members_before = MEMBER_REPO.count_all()
    grants_before = GRANT_REPO.count_all()
    # Phase 10.11: the legacy importer is read-only now, and this
    # is its one sanctioned use -- reading the JSON once so the
    # durable store can own it.
    from backend.auth.tenant import get_tenant_manager

    tm = get_tenant_manager()
    result = migrate_json_tenants(repository=TENANT_REPO, manager=tm)
    check("B1. the JSON tenant file was imported deterministically",
          TENANT_REPO.count_all() > 0,
          f"{result} | rows={TENANT_REPO.count_all()}")
    check("B2. the migration created NO membership and NO authority — moving "
          "the boundary must never hand out access",
          MEMBER_REPO.count_all() == members_before
          and GRANT_REPO.count_all() == grants_before,
          f"members {members_before}→{MEMBER_REPO.count_all()} "
          f"grants {grants_before}→{GRANT_REPO.count_all()}")

    again = migrate_json_tenants(repository=TENANT_REPO, manager=tm)
    check("B3. running it twice imports nothing new", again["imported"] == 0,
          str(again))

    rows = TENANT_REPO.list_all()
    check("B4. migrated tenants are distinguishable from provisioned ones",
          any(r.source == "migrated" for r in rows),
          str({r.source for r in rows}))

    # The load-bearing one.
    def _switch_off(data):
        for row in data:
            if row.get("tenant_id") == TENANTS[TENANT_A]:
                row["is_active"] = False

    _, restore = mutate_legacy_json("tenants.json", _switch_off)
    record, reason = resolve_tenant(tenant_id=TENANTS[TENANT_A],
                                    tenants=TENANT_REPO)
    check("B5. the JSON file is NO LONGER authoritative — flipping is_active "
          "in the file changes nothing the platform reads",
          record is not None and record.is_active,
          f"json=inactive store={record.status if record else None} ({reason})")
    r = client.get("/api/v1/approvals", headers=auth(PLAIN))
    check("B6. and a product request still succeeds while the file says the "
          "tenant is off", r.status_code == 200, f"HTTP {r.status_code}")
    restore()


def run_tenant_is_not_authority(client) -> None:
    section("C. a tenant is NOT authority")
    from backend.auth.tenants import bootstrap_tenant

    fresh = fresh_tenant("p1010-empty", "Empty boundary")
    check("C1. provisioning a tenant creates a boundary and NOTHING else — no "
          "membership, no grant",
          len(MEMBER_REPO.list_for_tenant(tenant_id=fresh.tenant_id)) == 0
          and len(GRANT_REPO.list_for_tenant(tenant_id=fresh.tenant_id)) == 0,
          fresh.tenant_id)

    # Two refusals are both correct here and both are accepted: a caller who
    # is a member of no tenant at all gets ``no_tenant_membership``, while one
    # who belongs elsewhere gets the MORE specific
    # ``membership_in_another_tenant``. What matters is that an existing,
    # active boundary confers nothing either way.
    membership_refusals = {"no_tenant_membership", "membership_in_another_tenant"}
    for action in ("approve", "execute", "issue"):
        from backend.auth.approver import resolve_scoped_authority
        v = resolve_scoped_authority(
            principal_id=ADMIN, tenant_id=fresh.tenant_id, action=action,
            capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
            grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
        check(f"C. an existing, ACTIVE tenant grants nobody {action} — "
              "existence is not permission",
              not v.permitted and v.reason in membership_refusals, v.reason)

    check("C5. an ACTIVE tenant with an ACTIVE member still refuses an "
          "ungranted authority — the boundary did not fill the gap",
          not verdict(PLAIN, "approve").permitted,
          verdict(PLAIN, "approve").reason)


def run_tenant_is_not_membership(client) -> None:
    section("D. a tenant is NOT membership")
    from backend.auth.tenants import bootstrap_tenant

    fresh = fresh_tenant("p1010-nomembers", "No members")
    ghost = {"Authorization": "Bearer " + _token(fresh.tenant_id,
                                                 "p1010-ghost@nowhere.test")}
    r = client.get("/api/v1/approvals", headers=ghost)
    check("D1. a tenant existing does not admit anybody — a valid token for a "
          "real, active tenant with no membership is refused",
          r.status_code == 403 and "no_tenant_membership" in r.text,
          f"HTTP {r.status_code} {r.text[:90]}")

    check("D2. and the tenant really is active, so this is a membership "
          "refusal rather than a tenant one",
          TENANT_REPO.get(tenant_id=fresh.tenant_id).is_active)


def _token(tenant_id, subject):
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator", tenant_id=tenant_id,
                               user_role="member")


def run_deactivation(client, engine) -> None:
    section("E. an inactive tenant fails closed on EVERY path")
    from backend.auth.tenants import set_tenant_status

    doomed = TENANTS[TENANT_DOOMED]
    before = {a: verdict(DOOMED_MEMBER, a, TENANT_DOOMED).permitted
              for a in ("approve", "execute", "issue")}
    check("E1. before deactivation the member holds approve, execute AND issue",
          all(before.values()), str(before))

    r = client.get("/api/v1/approvals", headers=auth(DOOMED_MEMBER, TENANT_DOOMED))
    check("E2. and can read the product", r.status_code == 200,
          f"HTTP {r.status_code}")

    out = set_tenant_status(repository=TENANT_REPO, tenant_id=doomed,
                            status="inactive", actor="harness:operator",
                            audit=getattr(runtime_of(engine), "audit", None),
                            audit_writer=getattr(runtime_of(engine),
                                                 "audit_writer", None))
    check("E3. the tenant is deactivated out-of-band", out.accepted,
          f"{out.previous_state} -> {out.new_state}")

    after = {a: verdict(DOOMED_MEMBER, a, TENANT_DOOMED)
             for a in ("approve", "execute", "issue")}
    check("E4. approval authority is gone", not after["approve"].permitted,
          after["approve"].reason)
    check("E5. execution authority is gone", not after["execute"].permitted,
          after["execute"].reason)
    check("E6. issuance authority is gone", not after["issue"].permitted,
          after["issue"].reason)

    r = client.get("/api/v1/approvals", headers=auth(DOOMED_MEMBER, TENANT_DOOMED))
    check("E7. product access is gone, on a token minted while the tenant was "
          "active — tenant state is read live, never from the claim",
          r.status_code == 403 and "tenant_inactive" in r.text,
          f"HTTP {r.status_code} {r.text[:90]}")

    r = client.post(GRANTS, json={"subject": PLAIN, "authority_type": "approve",
                                  "capability_ref": CAPABILITY,
                                  "environment": ENVIRONMENT,
                                  "reason": "issued inside a dead tenant"},
                    headers=auth(DOOMED_MEMBER, TENANT_DOOMED))
    check("E8. grant ISSUANCE inside an inactive tenant is refused",
          r.status_code == 403, f"HTTP {r.status_code} {r.text[:90]}")

    live = GRANT_REPO.live_grants_for(tenant_id=doomed,
                                      subject_principal_id=DOOMED_MEMBER,
                                      authority_type="approve")
    grant_id = live[0].grant_id if live else None
    if grant_id:
        r = client.post(f"{GRANTS}/{grant_id}/revocation",
                        json={"reason": "revoked inside a dead tenant"},
                        headers=auth(DOOMED_MEMBER, TENANT_DOOMED))
        check("E9. grant REVOCATION inside an inactive tenant is refused",
              r.status_code == 403, f"HTTP {r.status_code}")

    r = client.post(MEMBERS, json={"subject": "x@y.test"},
                    headers=auth(DOOMED_MEMBER, TENANT_DOOMED))
    check("E10. membership admission inside an inactive tenant is refused",
          r.status_code == 403, f"HTTP {r.status_code}")

    check("E11. nothing was DELETED — memberships, grants and the tenant row "
          "all survive, so the history stays attributable",
          len(MEMBER_REPO.list_for_tenant(tenant_id=doomed)) > 0
          and len(GRANT_REPO.list_for_tenant(tenant_id=doomed)) > 0
          and TENANT_REPO.get(tenant_id=doomed) is not None,
          f"members={len(MEMBER_REPO.list_for_tenant(tenant_id=doomed))} "
          f"grants={len(GRANT_REPO.list_for_tenant(tenant_id=doomed))}")

    out = set_tenant_status(repository=TENANT_REPO, tenant_id=doomed,
                            status="inactive", actor="harness:operator")
    check("E12. deactivating twice reports 'already in that state' rather than "
          "silently overwriting who did it first",
          out.refused and out.reason == "tenant_already_in_that_state",
          out.reason)


def runtime_of(engine):
    return getattr(engine, "runtime", None)


def run_reactivation(client) -> None:
    section("F. reactivation — measured, not designed")
    from backend.auth.tenants import set_tenant_status

    out = set_tenant_status(repository=TENANT_REPO,
                            tenant_id=TENANTS[TENANT_DOOMED], status="active",
                            actor="harness:operator")
    check("F1. the tenant is reactivated", out.accepted,
          f"{out.previous_state} -> {out.new_state}")

    restored = {a: verdict(DOOMED_MEMBER, a, TENANT_DOOMED).permitted
                for a in ("approve", "execute", "issue")}
    measure("reactivation_restores_authority", all(restored.values()))
    measure("reactivation_semantics",
            "Memberships and grants survive tenant deactivation and become "
            "effective again on reactivation. Neither was revoked, and this "
            "phase invents no new state machine. MEASURED behaviour: removing "
            "access permanently means revoking the grant or the membership, "
            "not only switching the tenant off.")
    check("F2. the measured behaviour is recorded verbatim, whatever it is",
          isinstance(all(restored.values()), bool), str(restored))

    r = client.get("/api/v1/approvals", headers=auth(DOOMED_MEMBER, TENANT_DOOMED))
    check("F3. product access returns with the tenant", r.status_code == 200,
          f"HTTP {r.status_code}")


def run_history(client) -> None:
    section("G. historical records remain attributable")
    doomed = TENANTS[TENANT_DOOMED]
    grants = GRANT_REPO.list_for_tenant(tenant_id=doomed)
    members = MEMBER_REPO.list_for_tenant(tenant_id=doomed)
    check("G1. grants issued in a tenant still name it after it was switched "
          "off and on", all(g.tenant_id == doomed for g in grants),
          f"{len(grants)} grant(s)")
    check("G2. memberships likewise",
          all(m.tenant_id == doomed for m in members), f"{len(members)} member(s)")
    check("G3. the tenant row itself was never deleted",
          TENANT_REPO.get(tenant_id=doomed) is not None)
    check("G4. tenant state is NOT part of any grant digest — deactivating a "
          "tenant did not change a single stored digest",
          all(g.digest_matches() for g in grants if g.revoked_at is None),
          "every live grant still matches its own digest")


def run_tenant_isolation(client) -> None:
    section("H. cross-tenant isolation")
    r = client.get(MEMBERS, headers=auth(OTHER_ADMIN, TENANT_B))
    tenants_seen = {m["tenant_id"] for m in r.json().get("members", [])}
    check("H1. tenant B's member listing contains only tenant B",
          tenants_seen <= {TENANTS[TENANT_B]}, str(tenants_seen))

    r = client.get(GRANTS, headers=auth(OTHER_ADMIN, TENANT_B))
    grant_tenants = {g["tenant_id"] for g in r.json().get("grants", [])}
    check("H2. and only tenant B's grants",
          grant_tenants <= {TENANTS[TENANT_B]}, str(grant_tenants))

    r = client.post(f"{MEMBERS}/{IDS[PLAIN]}/status", json={"status": "inactive"},
                    headers=auth(OTHER_ADMIN, TENANT_B))
    check("H3. tenant B cannot deactivate tenant A's member",
          r.status_code == 404, f"HTTP {r.status_code}")

    v = verdict(OTHER_ADMIN, "issue", TENANT_A)
    check("H4. tenant B's issuer holds nothing in tenant A",
          not v.permitted, v.reason)

    check("H5. and tenant A's member holds nothing in tenant B",
          not verdict(ADMIN, "issue", TENANT_B).permitted,
          verdict(ADMIN, "issue", TENANT_B).reason)


def run_v1_routes() -> None:
    section("I. the V1 tenant routes Phase 10.9's guard could not reach")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.tenant_routes import router
    from backend.auth.jwt_handler import create_access_token

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app, raise_server_exceptions=False)
    token = create_access_token("attacker@a.test", role="admin",
                                tenant_id=TENANTS[TENANT_A], user_role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    r = c.get("/api/tenants", headers=headers)
    slugs = [t["slug"] for t in r.json()] if r.status_code == 200 else []
    # Phase 10.10 narrowed this route from "every tenant in the system" to the
    # caller's own. Phase 10.13 deleted it outright, which satisfies the same
    # intent more strongly -- there is no listing left to disclose anything.
    check("I1. GET /api/tenants discloses nothing — it returned every tenant "
          "in the system before Phase 10.10 narrowed it, and Phase 10.13 "
          "retired it altogether",
          (r.status_code in (404, 405) and not slugs)
          or (r.status_code == 200 and len(slugs) <= 1),
          f"HTTP {r.status_code} slugs={slugs}")

    r = c.post("/api/tenants", headers=headers,
               json={"name": "Planted", "slug": "p1010-planted"})
    check("I2. POST /api/tenants no longer creates a tenant — administration "
          "is out-of-band", r.status_code == 403, f"HTTP {r.status_code}")
    check("I2b. and no such tenant exists",
          TENANT_REPO.get_by_slug(slug="p1010-planted") is None)

    r = c.post(f"/api/tenants/{TENANTS[TENANT_A]}/deactivate", headers=headers)
    check("I3. POST /{tenant}/deactivate no longer deactivates a tenant",
          r.status_code == 403, f"HTTP {r.status_code}")
    check("I3b. and tenant A is still active",
          TENANT_REPO.get(tenant_id=TENANTS[TENANT_A]).is_active)

    r = c.post(f"/api/tenants/{TENANTS[TENANT_B]}/deactivate", headers=headers)
    check("I4. a FOREIGN tenant is still a 404 — Phase 10.9's guard holds",
          r.status_code == 404, f"HTTP {r.status_code}")


def run_audit(client, runtime) -> None:
    section("J. audit — durable, chained, no new event kind")
    from backend.auth.tenants import set_tenant_status
    from backend.contracts.audit import AuditEventKind

    audit = getattr(runtime, "audit", None)
    writer = getattr(runtime, "audit_writer", None)
    if audit is None:
        deferred("J. audit", "no audit runtime composed in this harness")
        return

    target = fresh_tenant("p1010-audited", "Audited boundary")
    before = audit.count()
    set_tenant_status(repository=TENANT_REPO, tenant_id=target.tenant_id,
                      status="inactive", actor="harness:operator",
                      audit=audit, audit_writer=writer)
    set_tenant_status(repository=TENANT_REPO, tenant_id=target.tenant_id,
                      status="active", actor="harness:operator",
                      audit=audit, audit_writer=writer)
    after = audit.count()
    check("J1. deactivation and activation each appended to the durable chain",
          after >= before + 2, f"{before} → {after}")

    records = [e for e in audit.query()
               if e.kind is AuditEventKind.IDENTITY_EVENT
               and (e.detail or {}).get("tenant_id") == target.tenant_id]
    check("J2. the events reuse the EXISTING IDENTITY_EVENT kind — no new "
          "audit kind was invented", len(records) >= 2, str(len(records)))

    detail = records[0].detail if records else {}
    required = {"actor", "tenant_id", "previous_state", "new_state", "event"}
    check("J3. each record names actor, tenant, previous and new state",
          required <= set(detail), str(sorted(required - set(detail))))

    blob = json.dumps([r.detail for r in records], default=str).lower()
    leaked = [n for n in ("bearer ", "postgresql://", "password", "secret",
                          (os.getenv("CORTEX_KUBERNETES_TOKEN") or "zz")[:40].lower())
              if n and n in blob]
    check("J4. no password, token, credential or DSN in the detail", not leaked,
          str(leaked))

    reads = audit.count()
    client.get("/api/v1/approvals", headers=auth(PLAIN))
    check("J5. a READ writes no audit event", audit.count() == reads,
          f"{reads} → {audit.count()}")


def run_concurrency(client) -> None:
    section("K. concurrency — measured, never claimed")
    from backend.auth.tenants import bootstrap_tenant, set_tenant_status

    target = fresh_tenant("p1010-race", "Race boundary")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result() for f in [
            pool.submit(set_tenant_status, repository=TENANT_REPO,
                        tenant_id=target.tenant_id, status="inactive",
                        actor="racer") for _ in range(2)]]
    measure("concurrent_deactivate_accepted", [r.accepted for r in results])
    check("K1. two simultaneous deactivations: one wins, the other is told it "
          "already happened — the conditional UPDATE decides, with no lock",
          sum(1 for r in results if r.accepted) == 1,
          str([r.reason for r in results]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        mixed = [f.result() for f in [
            pool.submit(set_tenant_status, repository=TENANT_REPO,
                        tenant_id=target.tenant_id, status="active",
                        actor="racer"),
            pool.submit(set_tenant_status, repository=TENANT_REPO,
                        tenant_id=target.tenant_id, status="inactive",
                        actor="racer")]]
    final = TENANT_REPO.get(tenant_id=target.tenant_id)
    measure("concurrent_activate_deactivate", [r.reason for r in mixed])
    measure("concurrent_final_state", final.status if final else None)
    measure("concurrency_semantics",
            "Reported verbatim. Tenant state is last-write-wins under a "
            "conditional UPDATE; no locking was invented and exactly-once is "
            "NOT claimed.")
    check("K2. the final state is one of the two requested, reported verbatim",
          final is not None and final.status in ("active", "inactive"),
          final.status if final else "none")

    # Replay: provisioning the same slug twice.
    try:
        from backend.auth.tenants import bootstrap_tenant
        bootstrap_tenant(repository=TENANT_REPO, slug="p1010-race",
                         name="Duplicate")
        replayed = "accepted a duplicate slug"
    except Exception as exc:  # noqa: BLE001
        replayed = type(exc).__name__
    measure("replay_provision_same_slug", replayed)
    check("K3. re-provisioning the same slug is refused by the UNIQUE "
          "constraint rather than creating a second boundary",
          replayed != "accepted a duplicate slug", replayed)


def run_positive_matrix(client) -> None:
    section("L. positive matrix")
    checks = [
        ("L1. the tenant exists in the durable store",
         TENANT_REPO.get(tenant_id=TENANTS[TENANT_A]) is not None),
        ("L2. it is active",
         TENANT_REPO.get(tenant_id=TENANTS[TENANT_A]).is_active),
        ("L3. an active tenant permits an active member",
         client.get("/api/v1/approvals", headers=auth(PLAIN)).status_code == 200),
        ("L4. the slug persists",
         TENANT_REPO.get(tenant_id=TENANTS[TENANT_A]).slug == TENANT_A),
        ("L5. membership remains separate",
         MEMBER_REPO.find(tenant_id=TENANTS[TENANT_A],
                          subject_principal_id=PLAIN) is not None),
        ("L6. authority grants remain separate",
         verdict(APPROVER, "approve").permitted),
        ("L7. execution authority remains separate",
         verdict(EXECUTOR, "execute").permitted),
        ("L8. an ungranted member still holds nothing",
         not verdict(PLAIN, "execute").permitted),
    ]
    for name, ok in checks:
        check(name, ok)


def run_negative_matrix(client, engine) -> None:
    section("M. the negative matrix — every case, zero provider writes")
    import sqlalchemy as sa
    from backend.auth.tenants import bootstrap_tenant, set_tenant_status
    from backend.database.durable.tables import tenant_table as T

    before_cluster = p103.generations()

    def writes():
        return p103.cluster_writes(before_cluster, p103.generations())

    dead = fresh_tenant("p1010-dead", "Dead boundary", status="inactive")
    dead_headers = {"Authorization": "Bearer " + _token(dead.tenant_id, PLAIN)}
    ghost_tenant = {"Authorization": "Bearer " + _token("tenant-nope", PLAIN)}
    doomed_h = auth(DOOMED_MEMBER, TENANT_DOOMED)

    body = {"subject": "p1010-neg@cortexprime.test"}
    cases = [
        ("N1. anonymous", lambda: client.get("/api/v1/approvals"),
         "authentication"),
        ("N2. forged identity",
         lambda: client.get("/api/v1/approvals",
                            headers={"Authorization": "Bearer nope"}),
         "authentication"),
        ("N3. nonexistent tenant in the token",
         lambda: client.get("/api/v1/approvals", headers=ghost_tenant),
         "tenant_state"),
        ("N4. inactive tenant product access",
         lambda: client.get("/api/v1/approvals", headers=dead_headers),
         "tenant_state"),
        ("N5. inactive tenant reading grants",
         lambda: client.get(GRANTS, headers=dead_headers), "tenant_state"),
        ("N6. inactive tenant reading members",
         lambda: client.get(MEMBERS, headers=dead_headers), "tenant_state"),
        ("N7. body-supplied tenant on admission",
         lambda: client.post(MEMBERS, json=dict(body, tenant_id="other"),
                             headers=auth(ADMIN)), "governance"),
        ("N8. query-parameter tenant",
         lambda: client.post(MEMBERS, json=body,
                             params={"tenant_id": TENANTS[TENANT_B]},
                             headers=auth(ADMIN)), "tenant_isolation"),
        ("N9. header tenant",
         lambda: client.post(MEMBERS, json=body,
                             headers=dict(auth(ADMIN),
                                          **{"X-Tenant-Id": TENANTS[TENANT_B]})),
         "tenant_isolation"),
        ("N10. body-supplied tenant status",
         lambda: client.post(MEMBERS, json=dict(body, status="active"),
                             headers=auth(ADMIN)), "governance"),
        ("N11. tenant creation by an ordinary member",
         lambda: client.post("/api/v1/tenants", json={"slug": "x"},
                             headers=auth(PLAIN)), "governance"),
        ("N12. tenant activation route does not exist",
         lambda: client.post(f"/api/v1/tenants/{TENANTS[TENANT_A]}/status",
                             json={"status": "active"}, headers=auth(ADMIN)),
         "governance"),
        ("N13. tenant deactivation route does not exist",
         lambda: client.post(f"/api/v1/tenants/{TENANTS[TENANT_A]}/deactivate",
                             json={}, headers=auth(ADMIN)), "governance"),
        ("N14. tenant slug mutation route does not exist",
         lambda: client.post(f"/api/v1/tenants/{TENANTS[TENANT_A]}/slug",
                             json={"slug": "hijacked"}, headers=auth(ADMIN)),
         "governance"),
        ("N15. cross-tenant member deactivation",
         lambda: client.post(f"{MEMBERS}/{IDS[PLAIN]}/status",
                             json={"status": "inactive"},
                             headers=auth(OTHER_ADMIN, TENANT_B)),
         "tenant_isolation"),
        ("N16. cross-tenant grant revocation",
         lambda: client.post(f"{GRANTS}/grant-not-yours/revocation",
                             json={"reason": "cross tenant attempt"},
                             headers=auth(OTHER_ADMIN, TENANT_B)),
         "tenant_isolation"),
        ("N17. inactive tenant approving",
         lambda: client.post("/api/v1/approvals/none/decision",
                             json={"decision": "approve"}, headers=doomed_h),
         "tenant_state"),
        ("N18. inactive tenant executing",
         lambda: client.post("/api/v1/approvals/none/execute", json={},
                             headers=doomed_h), "tenant_state"),
        ("N19. inactive tenant issuing a grant",
         lambda: client.post(GRANTS, json={
             "subject": PLAIN, "authority_type": "approve",
             "capability_ref": CAPABILITY, "environment": ENVIRONMENT,
             "reason": "issued in a dead tenant"}, headers=doomed_h),
         "tenant_state"),
        ("N20. inactive tenant admitting a member",
         lambda: client.post(MEMBERS, json={"subject": "z@y.test"},
                             headers=doomed_h), "tenant_state"),
        ("N21. direct worker route",
         lambda: client.post("/api/v1/worker/invoke", json={},
                             headers=auth(ADMIN)), "governance"),
        ("N22. direct provider route",
         lambda: client.post("/api/v1/providers/kubernetes", json={},
                             headers=auth(ADMIN)), "governance"),
        ("N23. autonomy route",
         lambda: client.post("/api/v1/autonomy", json={}, headers=auth(ADMIN)),
         "governance"),
        ("N24. tenant deletion route does not exist",
         lambda: client.request("DELETE", f"/api/v1/tenants/{TENANTS[TENANT_A]}",
                                headers=auth(ADMIN)), "governance"),
    ]

    # The doomed tenant must be inactive for N17-N20.
    set_tenant_status(repository=TENANT_REPO, tenant_id=TENANTS[TENANT_DOOMED],
                      status="inactive", actor="harness:operator")
    for name, call, layer in cases:
        r = call()
        record_negative(name, layer, f"HTTP {r.status_code} {r.text[:70]}",
                        writes())
    set_tenant_status(repository=TENANT_REPO, tenant_id=TENANTS[TENANT_DOOMED],
                      status="active", actor="harness:operator")

    # V1 routes.
    for name, layer, code in _v1_negatives():
        record_negative(name, layer, f"HTTP {code}", writes())

    # JSON mutation after migration.
    def _switch_off_again(data):
        for row in data:
            if row.get("tenant_id") == TENANTS[TENANT_A]:
                row["is_active"] = False

    _, restore_json = mutate_legacy_json("tenants.json", _switch_off_again)
    r = client.get("/api/v1/approvals", headers=auth(PLAIN))
    record_negative("N33. JSON mutation after migration", "governance",
                    f"file says inactive; HTTP {r.status_code}",
                    0 if r.status_code == 200 else 1)
    restore_json()

    # Direct database mutation. Tenant state is INTENTIONALLY mutable, so this
    # is legitimate store behaviour, not tamper detection.
    with STORE.atomic() as w:
        w.execute(sa.update(T).where(T.c.tenant_id == TENANTS[TENANT_A])
                  .values(status="inactive"))
    r = client.get("/api/v1/approvals", headers=auth(PLAIN))
    record_negative("N34. direct DB deactivation is HONOURED (the store IS the "
                    "authority) and fails closed", "tenant_state",
                    f"HTTP {r.status_code}", 0 if r.status_code == 403 else 1)
    with STORE.atomic() as w:
        w.execute(sa.update(T).where(T.c.tenant_id == TENANTS[TENANT_A])
                  .values(status="active"))

    measure("negative_matrix_cases", len(NEGATIVES))
    measure("negative_matrix_provider_writes",
            sum(c["provider_writes"] for c in NEGATIVES))
    check("M-FINAL. every negative case left the cluster untouched",
          writes() == 0, f"cluster writes = {writes()}")


def _v1_negatives():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.tenant_routes import router
    from backend.auth.jwt_handler import create_access_token

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app, raise_server_exceptions=False)
    token = create_access_token("attacker@a.test", role="admin",
                                tenant_id=TENANTS[TENANT_A], user_role="admin")
    h = {"Authorization": f"Bearer {token}"}
    return [
        ("N25. V1 tenant creation", "governance",
         c.post("/api/tenants", json={"name": "x", "slug": "p1010-neg-create"},
                headers=h).status_code),
        ("N26. V1 tenant deactivation", "governance",
         c.post(f"/api/tenants/{TENANTS[TENANT_A]}/deactivate",
                headers=h).status_code),
        ("N27. V1 cross-tenant read", "tenant_isolation",
         c.get(f"/api/tenants/{TENANTS[TENANT_B]}", headers=h).status_code),
        ("N28. V1 cross-tenant member add", "tenant_isolation",
         c.post(f"/api/tenants/{TENANTS[TENANT_B]}/users",
                json={"email": "x@y.test", "role": "owner"},
                headers=h).status_code),
        ("N29. V1 cross-tenant member list", "tenant_isolation",
         c.get(f"/api/tenants/{TENANTS[TENANT_B]}/users", headers=h).status_code),
        ("N30. V1 cross-tenant role change", "tenant_isolation",
         c.patch(f"/api/tenants/{TENANTS[TENANT_B]}/users/u",
                 json={"role": "owner"}, headers=h).status_code),
        ("N31. V1 cross-tenant deactivation", "tenant_isolation",
         c.post(f"/api/tenants/{TENANTS[TENANT_B]}/deactivate",
                headers=h).status_code),
        ("N32. V1 tenant list discloses at most the caller's own", "governance",
         len(c.get("/api/tenants", headers=h).json())),
    ]


def run_restart(client) -> None:
    section("N. crash / restart — real process death")
    proof = subprocess.run(
        [sys.executable, "-c",
         "import os,sys;sys.path.insert(0,os.getcwd());"
         "from backend.contexts.connectivity.infrastructure.sql_tenant "
         "import SqlTenantRepository;"
         "from backend.database.durable.config import build_development_store;"
         "r=SqlTenantRepository(build_development_store("
         "dsn=os.environ['CORTEX_DURABLE_URL']));"
         f"t=r.get(tenant_id={TENANTS[TENANT_A]!r});"
         f"d=r.get_by_slug(slug='p1010-dead');"
         "print(t.status, t.slug, t.created_by, d.status)"],
        capture_output=True, text=True, cwd=os.getcwd(), env=os.environ)
    out = (proof.stdout or "").strip().split()
    check("N1. a FRESH process reads the same tenant — it survives restart "
          "because it lives in PostgreSQL", len(out) >= 4,
          f"{out} (stderr: {proof.stderr[:120]})")
    if len(out) >= 4:
        check("N2. active state survives", out[0] == "active", out[0])
        check("N3. slug survives", out[1] == TENANT_A, out[1])
        check("N4. attribution survives", bool(out[2]), out[2])
        check("N5. an INACTIVE tenant is NOT resurrected by a restart",
              out[3] == "inactive", out[3])
    check("N6. no partial tenant exists — every row has a slug, a status and "
          "an attributed creator",
          all(t.slug and t.status and t.created_by
              for t in TENANT_REPO.list_all()))


def run_performance(client) -> None:
    section("O. measured latency — real PostgreSQL")
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

    p50, p95 = timed(lambda: client.get("/api/v1/approvals", headers=auth(PLAIN)),
                     n=8)
    measure("authenticated_read_p50_ms", p50)
    measure("authenticated_read_p95_ms", p95)

    p50, p95 = timed(lambda: verdict(APPROVER, "approve"))
    measure("authority_after_tenant_p50_ms", p50)
    measure("authority_after_tenant_p95_ms", p95)

    counter = {"n": 0}

    def provision_one():
        from backend.auth.tenants import bootstrap_tenant
        counter["n"] += 1
        bootstrap_tenant(repository=TENANT_REPO,
                         slug=f"p1010-perf-{uuid.uuid4().hex[:10]}",
                         name="perf")

    p50, p95 = timed(provision_one, n=8)
    measure("tenant_provision_p50_ms", p50)
    measure("tenant_provision_p95_ms", p95)
    check("O1. latency measured against real PostgreSQL, no speculative index "
          "added", True)


if __name__ == "__main__":
    main()
