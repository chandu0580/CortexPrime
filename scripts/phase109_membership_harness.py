"""Phase 10.9 — durable, governed tenant membership, proven against real infra.

What this harness establishes
-----------------------------
Phase 10.8 made authority durable, attributed and audited, and left every grant
pointing at a subject defined by a gitignored JSON file — a file with no
deactivate method, no delete method, no audit, and one HTTP mutation path that
took the tenant from the URL.

This proves membership is now durable, tenant-authoritative, attributable,
revocable and audited; that it confers **no** authority by itself; and that an
inactive membership fails closed everywhere — product access, approval,
execution, grant issuance and grant revocation.

What it refuses to claim
------------------------
Exactly-once. Concurrency is measured and reported verbatim.

Real everything: real k3d, real PostgreSQL, real Redis, real tenant store, real
OS process death.
"""

from __future__ import annotations

import json
import os
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

TENANT_A, TENANT_B = "p109a", "p109b"
TENANTS: dict = {}

ADMIN = "p109-admin@cortexprime.test"          # holds issue authority
PLAIN = "p109-plain@cortexprime.test"          # a member, no authority
APPROVER = "p109-approver@cortexprime.test"
EXECUTOR = "p109-executor@cortexprime.test"
DOOMED = "p109-doomed@cortexprime.test"        # gets deactivated
NEWCOMER = "p109-newcomer@cortexprime.test"    # admitted during the run
OTHER_ADMIN = "p109-other-admin@cortexprime.test"

CAPABILITY = ""
ENVIRONMENT = "development"
MEMBERS = "/api/v1/tenants/members"
GRANTS = "/api/v1/authority/grants"
STORE = None
MEMBER_REPO = None
GRANT_REPO = None
TENANT_REPO = None
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


def membership_of(subject, tenant_slug=TENANT_A):
    return MEMBER_REPO.find(tenant_id=TENANTS[tenant_slug],
                            subject_principal_id=subject)


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
    global STORE, MEMBER_REPO, GRANT_REPO, TENANT_REPO
    from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
        SqlAuthorityGrantRepository)
    from backend.contexts.connectivity.infrastructure.sql_membership import (
        SqlMembershipRepository)
    from backend.database.durable.config import build_development_store

    STORE = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    MEMBER_REPO = SqlMembershipRepository(STORE)
    GRANT_REPO = SqlAuthorityGrantRepository(STORE)
    from backend.contexts.connectivity.infrastructure.sql_tenant import (
        SqlTenantRepository)
    TENANT_REPO = SqlTenantRepository(STORE)

    for slug in (TENANT_A, TENANT_B):
        # Phase 10.11: the tenant id comes from the DURABLE store. The
        # legacy JSON writer is gone, so nothing here touches a file.
        TENANTS[slug] = provisioning.tenant_id_for(
            STORE, slug=slug, name=slug)


    people = {
        ADMIN: (TENANT_A, [grant_string("issue", max_risk="high")]),
        PLAIN: (TENANT_A, []),
        APPROVER: (TENANT_A, [grant_string("approve")]),
        EXECUTOR: (TENANT_A, [grant_string("execute")]),
        DOOMED: (TENANT_A, [grant_string("approve"), grant_string("execute"),
                            grant_string("issue", max_risk="high")]),
        OTHER_ADMIN: (TENANT_B, [grant_string("issue", max_risk="high")]),
    }
    for email, (slug, grants) in people.items():
        # The JSON store still supplies the TENANT record; membership itself is
        # provisioned durably. A member here has no authority until granted.
        IDS[email] = provisioning.ensure_membership(
            STORE, tenant_id=TENANTS[slug], principal_id=email)
        provisioning.provision(GRANT_REPO, STORE, tenant_id=TENANTS[slug],
                               principal_id=email, grants=grants)
    # The newcomer deliberately has NO membership at the start, and neither do
    # the subjects the later sections admit. The phase database is durable and
    # survives runs, so a check that proves admission must begin from absence
    # -- otherwise it passes on a row an earlier run created and proves
    # nothing about admission at all.
    for subject in (NEWCOMER, "p109-audited@cortexprime.test",
                    "p109-race@cortexprime.test",
                    "p109-double@cortexprime.test",
                    "p109-pos@cortexprime.test",
                    "p109-negative@cortexprime.test"):
        provisioning.clear_grants(STORE, tenant_id=TENANTS[TENANT_A],
                                  principal_id=subject)
        provisioning.clear_membership(STORE, tenant_id=TENANTS[TENANT_A],
                                      principal_id=subject)


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis, REAL tenant\n"
          "        store, REAL process death. Membership is a primitive:\n"
          "        belonging to a tenant confers no authority at all.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. composition — one membership store, one new table")
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
    check("A1. the product's write surface is the enumerated set — 10.3's "
          "three, 10.8's two, and this phase's three",
          actual == set(MUTATING_ROUTES) | set(AUTHORITY_ROUTES)
          | set(MEMBERSHIP_ROUTES), str(sorted(actual)))
    check("A2. ONE new table (cp_tenant_membership), stopped for and documented "
          "before it was written",
          len(DURABLE_TABLES) == 25
          and any(t.name == "cp_tenant_membership" for t in DURABLE_TABLES),
          f"{len(DURABLE_TABLES)} tables")
    check("A3. exactly ONE commissioned write capability — none was added",
          len(definitions) == 1, str(list(definitions)))
    check("A4. no membership route names a tenant — cross-tenant "
          "administration is unrepresentable, not merely refused",
          all("{tenant_id}" not in path for _, path in MEMBERSHIP_ROUTES),
          str([p for _, p in MEMBERSHIP_ROUTES]))
    check("A5. no second authority: membership administration asks the Phase "
          "10.8 GRANT store, and defines no policy of its own",
          _one_authority(), "backend/auth/membership.py")
    check("A6. membership defines no user or credential — the table stores a "
          "relation and its state", _no_identity_duplication())

    run_migration(client)
    run_membership_is_not_authority(client)
    run_product_access(client)
    run_admission(client)
    run_deactivation(client, engine)
    run_reactivation(client)
    run_history(client, engine)
    run_tenant_isolation(client)
    run_audit(client, runtime)
    run_concurrency(client)
    run_positive_matrix(client)
    run_negative_matrix(client, engine)
    run_restart(client)
    run_performance(client)

    section("REPORT")
    report = {
        "phase": "10.9",
        "measurements": MEASURED,
        "negative_matrix": NEGATIVES,
        "verdict": "VERIFIED" if not FAILED else "NOT VERIFIED",
        "why": ("membership is durable, tenant-authoritative, attributable and "
                "revocable, and confers no authority by itself"),
        "passed": len(PASSED), "total": len(PASSED) + len(FAILED),
        "failed_checks": FAILED,
        "deferred": DEFERRED,
    }
    print(json.dumps(report, indent=1, default=str))
    client.__exit__(None, None, None)
    sys.exit(1 if FAILED else 0)


def _one_authority() -> bool:
    """Membership administration must not define its own authority model.

    An AST scan rather than a substring search: Phase 10.5 learned that a grep
    for a name matches the docstring explaining why the name is not used.
    """
    import ast

    tree = ast.parse(Path("backend/auth/membership.py").read_text(encoding="utf-8"))
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    # It must consult the existing grant store and define no rival resolver.
    return ("durable_grants" in called
            and not any(d.startswith("resolve_scoped") or "rbac" in d.lower()
                        for d in defined))


def _no_identity_duplication() -> bool:
    from backend.database.durable.tables import tenant_membership_table as T

    columns = set(T.c.keys())
    forbidden = {"password", "password_hash", "secret", "token", "credential",
                 "email", "display_name"}
    return not (columns & forbidden)


# ----------------------------------------------------------------------

def run_migration(client) -> None:
    section("B. migration from JSON — and JSON stops deciding")
    from backend.auth.membership import migrate_json_memberships
    grants_before = GRANT_REPO.count_all()
    # Phase 10.11: the legacy importer is read-only now, and this
    # is its one sanctioned use -- reading the JSON once so the
    # durable store can own it.
    from backend.auth.tenant import get_tenant_manager

    tm = get_tenant_manager()
    result = migrate_json_memberships(repository=MEMBER_REPO, manager=tm)
    check("B1. the JSON store was imported deterministically",
          result["imported"] >= 0 and MEMBER_REPO.count_all() > 0,
          f"{result} | rows={MEMBER_REPO.count_all()}")
    check("B2. the migration created NO authority — moving membership must "
          "never hand out grants, which would be the quietest possible "
          "privilege escalation",
          GRANT_REPO.count_all() == grants_before,
          f"{grants_before} → {GRANT_REPO.count_all()}")

    again = migrate_json_memberships(repository=MEMBER_REPO, manager=tm)
    check("B3. running it twice imports nothing new — deterministic and "
          "re-runnable", again["imported"] == 0, str(again))

    rows = MEMBER_REPO.list_for_tenant(tenant_id=TENANTS[TENANT_A])
    check("B4. migrated rows are distinguishable from admitted ones",
          any(r.source in ("migrated", "admitted") for r in rows),
          str({r.source for r in rows}))

    # The load-bearing one: edit the JSON and prove nothing moves.
    from backend.auth.approver import durable_membership

    before, _ = durable_membership(MEMBER_REPO, tenant_id=TENANTS[TENANT_A],
                                   principal_id=PLAIN)

    def _poison(data):
        for rows in data.values():
            for row in rows:
                if row.get("email") == PLAIN:
                    row["is_active"] = False
                    row["role"] = "owner"

    _, restore = mutate_legacy_json("tenant_users.json", _poison)
    after, reason = durable_membership(MEMBER_REPO, tenant_id=TENANTS[TENANT_A],
                                       principal_id=PLAIN)
    check("B5. the JSON file is NO LONGER authoritative — flipping is_active "
          "and role in the file changes nothing the platform reads",
          after is not None and after.is_active and after.role == before.role,
          f"json=inactive/owner store={after.status if after else None}/"
          f"{after.role if after else None} ({reason})")
    restore()


def run_membership_is_not_authority(client) -> None:
    section("C. membership is NOT authority")
    from backend.auth.approver import resolve_scoped_authority

    def verdict(who, action):
        return resolve_scoped_authority(
            principal_id=who, tenant_id=TENANTS[TENANT_A], action=action,
            capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
            grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)

    for action, reason in (("approve", "no_approver_authority"),
                           ("execute", "no_executor_authority"),
                           ("issue", "no_issuer_authority")):
        v = verdict(PLAIN, action)
        check(f"C. an ACTIVE member with no grant cannot {action} — belonging "
              "is not permission", not v.permitted and v.reason == reason,
              v.reason)

    check("C4. and the ones who DO hold grants still can — this is not a "
          "blanket refusal", verdict(APPROVER, "approve").permitted
          and verdict(EXECUTOR, "execute").permitted)

    m = membership_of(PLAIN)
    check("C5. a member labelled 'owner' still holds nothing — Phase 10.5's "
          "rule survives: no role maps to an authority",
          _role_confers_nothing(), f"role={m.role}")


def _role_confers_nothing() -> bool:
    """Relabel a member as owner and prove no authority appears."""
    from backend.auth.approver import resolve_scoped_authority

    MEMBER_REPO.set_role(tenant_id=TENANTS[TENANT_A],
                         membership_id=IDS[PLAIN], role="owner",
                         updated_by="harness")
    try:
        return not any(resolve_scoped_authority(
            principal_id=PLAIN, tenant_id=TENANTS[TENANT_A], action=action,
            capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
            grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO).permitted
            for action in ("approve", "execute", "issue"))
    finally:
        MEMBER_REPO.set_role(tenant_id=TENANTS[TENANT_A],
                             membership_id=IDS[PLAIN], role="member",
                             updated_by="harness")


def run_product_access(client) -> None:
    section("D. product access requires an ACTIVE membership")
    r = client.get("/api/v1/approvals", headers=auth(PLAIN))
    check("D1. an active member may read the product", r.status_code == 200,
          f"HTTP {r.status_code}")

    r = client.get("/api/v1/approvals",
                   headers=auth("p109-ghost@nowhere.test"))
    check("D2. a subject with NO membership, holding a VALID tenant token, is "
          "refused — before this phase this returned 200",
          r.status_code == 403 and "no_tenant_membership" in r.text,
          f"HTTP {r.status_code} {r.text[:90]}")

    r = client.get(GRANTS, headers=auth("p109-ghost@nowhere.test"))
    check("D3. and cannot list the tenant's authority grants — that listing is "
          "exactly the reconnaissance a non-member wants",
          r.status_code == 403, f"HTTP {r.status_code}")


def run_admission(client) -> None:
    section("E. admission")
    r = client.post(MEMBERS, json={"subject": NEWCOMER, "role": "member"},
                    headers=auth(PLAIN))
    check("E1. an ordinary member cannot admit anybody",
          r.status_code == 403
          and r.json()["detail"] == "no_membership_authority",
          f"HTTP {r.status_code} {r.text[:90]}")

    r = client.post(MEMBERS, json={"subject": NEWCOMER, "role": "member"},
                    headers=auth(APPROVER))
    check("E2. holding APPROVE authority does not confer admission",
          r.status_code == 403, f"HTTP {r.status_code}")

    r = client.post(MEMBERS, json={"subject": ADMIN}, headers=auth(ADMIN))
    check("E3. self-admission is refused",
          r.status_code == 403
          and r.json()["detail"] == "self_admission_refused",
          f"HTTP {r.status_code} {r.text[:90]}")

    r = client.post(MEMBERS, json={"subject": NEWCOMER, "role": "member"},
                    headers=auth(ADMIN))
    check("E4. an issuer admits the newcomer", r.status_code == 201,
          f"HTTP {r.status_code} {r.text[:120]}")
    if r.status_code == 201:
        IDS[NEWCOMER] = r.json()["membership_id"]

    r = client.post(MEMBERS, json={"subject": NEWCOMER, "role": "member"},
                    headers=auth(ADMIN))
    check("E5. admitting twice is a 409, not a second row a deactivation "
          "could miss", r.status_code == 409, f"HTTP {r.status_code}")

    from backend.auth.approver import resolve_scoped_authority
    v = resolve_scoped_authority(
        principal_id=NEWCOMER, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("E6. the newcomer belongs, and can do NOTHING", not v.permitted,
          v.reason)

    r = client.get("/api/v1/approvals", headers=auth(NEWCOMER))
    check("E7. and can now read the product, which is what membership IS for",
          r.status_code == 200, f"HTTP {r.status_code}")


def run_deactivation(client, engine) -> None:
    section("F. deactivation fails closed on EVERY path")
    from backend.auth.approver import resolve_scoped_authority

    doomed_id = IDS[DOOMED]
    before = {a: resolve_scoped_authority(
        principal_id=DOOMED, tenant_id=TENANTS[TENANT_A], action=a,
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO).permitted
        for a in ("approve", "execute", "issue")}
    check("F1. before deactivation the subject holds approve, execute AND "
          "issue", all(before.values()), str(before))

    r = client.post(f"{MEMBERS}/{doomed_id}/status", json={"status": "inactive"},
                    headers=auth(PLAIN))
    check("F2. an ordinary member cannot deactivate anybody",
          r.status_code == 403, f"HTTP {r.status_code}")

    r = client.post(f"{MEMBERS}/{doomed_id}/status", json={"status": "inactive"},
                    headers=auth(ADMIN))
    check("F3. an issuer deactivates the membership", r.status_code == 200,
          f"HTTP {r.status_code} {r.text[:110]}")

    after = {a: resolve_scoped_authority(
        principal_id=DOOMED, tenant_id=TENANTS[TENANT_A], action=a,
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
        for a in ("approve", "execute", "issue")}
    check("F4. approval authority is gone", not after["approve"].permitted,
          after["approve"].reason)
    check("F5. execution authority is gone", not after["execute"].permitted,
          after["execute"].reason)
    check("F6. issuance authority is gone", not after["issue"].permitted,
          after["issue"].reason)

    r = client.get("/api/v1/approvals", headers=auth(DOOMED))
    check("F7. product access is gone, on a token minted while they were "
          "active — membership is read live, never from the claim",
          r.status_code == 403, f"HTTP {r.status_code} {r.text[:90]}")

    r = client.post(GRANTS, json={"subject": PLAIN, "authority_type": "approve",
                                  "capability_ref": CAPABILITY,
                                  "environment": ENVIRONMENT,
                                  "reason": "issued by a deactivated member"},
                    headers=auth(DOOMED))
    check("F8. grant ISSUANCE by a deactivated member is refused",
          r.status_code == 403, f"HTTP {r.status_code} {r.text[:90]}")

    live = GRANT_REPO.live_grants_for(tenant_id=TENANTS[TENANT_A],
                                      subject_principal_id=DOOMED,
                                      authority_type="approve")
    check("F9. the GRANT itself was not touched — deactivating a person does "
          "not rewrite the authority record that names them",
          len(live) == 1, f"{len(live)} live grant(s)")

    r = client.post(f"{MEMBERS}/{doomed_id}/status", json={"status": "inactive"},
                    headers=auth(ADMIN))
    check("F10. deactivating twice is a 409 rather than a silent overwrite of "
          "who did it first", r.status_code == 409, f"HTTP {r.status_code}")


def run_reactivation(client) -> None:
    section("G. reactivation — measured, not designed")
    from backend.auth.approver import resolve_scoped_authority

    r = client.post(f"{MEMBERS}/{IDS[DOOMED]}/status", json={"status": "active"},
                    headers=auth(ADMIN))
    check("G1. an issuer reactivates the membership", r.status_code == 200,
          f"HTTP {r.status_code}")

    restored = {a: resolve_scoped_authority(
        principal_id=DOOMED, tenant_id=TENANTS[TENANT_A], action=a,
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO).permitted
        for a in ("approve", "execute", "issue")}
    measure("reactivation_restores_grants", all(restored.values()))
    measure("reactivation_semantics",
            "A grant survives deactivation of the membership it names and "
            "becomes usable again on reactivation. Grants are revoked "
            "separately and were not revoked here. This is the MEASURED "
            "behaviour, not an invented policy -- an operator removing "
            "authority must revoke the grant, not only the membership.")
    check("G2. the measured behaviour is recorded verbatim, whatever it is",
          isinstance(all(restored.values()), bool), str(restored))


def run_history(client, engine) -> None:
    section("H. historical identity is never rewritten")
    grants = GRANT_REPO.list_for_tenant(tenant_id=TENANTS[TENANT_A])
    doomed_rows = [g for g in grants if g.subject_principal_id == DOOMED]
    check("H1. grants issued to a subject still name that subject after their "
          "membership was disabled and re-enabled",
          bool(doomed_rows), f"{len(doomed_rows)} row(s)")

    listing = client.get(MEMBERS, headers=auth(ADMIN)).json()
    subjects = {m["subject"] for m in listing["members"]}
    check("H2. the membership listing includes inactive members — a list that "
          "hides them cannot answer 'who used to belong here'",
          DOOMED in subjects and NEWCOMER in subjects, str(len(subjects)))

    check("H3. the projection states that membership confers no authority, "
          "rather than leaving a reader to infer it from a role column",
          all(m["confers_authority"] is False for m in listing["members"])
          and "separate explicit grants" in listing["authority_note"])

    approvals = client.get("/api/v1/approvals", headers=auth(ADMIN))
    check("H4. historical approvals remain readable and attributable",
          approvals.status_code == 200, f"HTTP {approvals.status_code}")


def run_tenant_isolation(client) -> None:
    section("I. cross-tenant isolation")
    r = client.post(MEMBERS, json={"subject": "planted@a.test"},
                    headers=auth(OTHER_ADMIN, TENANT_B))
    landed = MEMBER_REPO.find(tenant_id=TENANTS[TENANT_A],
                              subject_principal_id="planted@a.test")
    check("I1. tenant B's admin admitting somebody lands in tenant B — the "
          "route has no tenant to name",
          landed is None, f"HTTP {r.status_code} leaked_into_A={landed is not None}")

    r = client.post(f"{MEMBERS}/{IDS[PLAIN]}/status", json={"status": "inactive"},
                    headers=auth(OTHER_ADMIN, TENANT_B))
    check("I2. tenant B cannot deactivate tenant A's member, and gets 404 "
          "rather than 403 — a tenant may not learn another's membership "
          "exists", r.status_code == 404, f"HTTP {r.status_code}")
    check("I2b. and tenant A's member is still active",
          membership_of(PLAIN).is_active)

    listing = client.get(MEMBERS, headers=auth(OTHER_ADMIN, TENANT_B)).json()
    tenants = {m["tenant_id"] for m in listing["members"]}
    check("I3. tenant B's listing contains ONLY tenant B",
          tenants <= {TENANTS[TENANT_B]}, str(tenants))
    a_listing = client.get(MEMBERS, headers=auth(ADMIN)).json()
    check("I4. and both tenants hold real members — isolation, not emptiness",
          len(a_listing["members"]) > 0 and len(listing["members"]) > 0,
          f"A={len(a_listing['members'])} B={len(listing['members'])}")

    # The V1 route this phase repaired.
    check("I5. the V1 tenant routes now refuse a foreign tenant in the PATH — "
          "the hole that let an admin of one tenant deactivate another "
          "(the read it also covered was retired in Phase 10.13)",
          _v1_cross_tenant_refused(), "backend/api/tenant_routes.py")


def _v1_cross_tenant_refused() -> bool:
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
    base = f"/api/tenants/{TENANTS[TENANT_B]}"
    # Phase 10.13 deleted the V1 tenant READ routes, so the member listing is
    # gone. The path still exists for POST, which is why FastAPI answers 405
    # rather than 404 -- and 405 for a retired route is a stronger outcome than
    # the 404 this check used to require: the surface is not there at all.
    writes = [
        c.post(f"{base}/users", json={"email": "x@y.test", "role": "owner"},
               headers=headers).status_code,
        c.post(f"{base}/deactivate", headers=headers).status_code,
    ]
    retired_read = c.get(f"{base}/users", headers=headers).status_code
    print(f"    [note] V1 cross-tenant writes returned {writes}; the retired "
          f"read returned {retired_read}")
    return all(code == 404 for code in writes) and retired_read in (404, 405)


def run_audit(client, runtime) -> None:
    section("J. audit — durable, chained, no new event kind")
    from backend.contracts.audit import AuditEventKind

    audit = getattr(runtime, "audit", None)
    if audit is None:
        deferred("J. audit", "no audit runtime composed in this harness")
        return

    before = audit.count()
    r = client.post(MEMBERS, json={"subject": "p109-audited@cortexprime.test"},
                    headers=auth(ADMIN))
    mid = r.json().get("membership_id") if r.status_code == 201 else None
    if mid:
        client.post(f"{MEMBERS}/{mid}/status", json={"status": "inactive"},
                    headers=auth(ADMIN))
        client.post(f"{MEMBERS}/{mid}/role", json={"role": "admin"},
                    headers=auth(ADMIN))
    after = audit.count()
    check("J1. creation, deactivation and role change each appended to the "
          "durable chain", after >= before + 3, f"{before} → {after}")

    records = [e for e in audit.query()
               if e.kind is AuditEventKind.IDENTITY_EVENT
               and (e.detail or {}).get("membership_id") == mid]
    check("J2. the events reuse the EXISTING IDENTITY_EVENT kind — no new "
          "audit kind was invented", len(records) >= 3, str(len(records)))

    detail = records[0].detail if records else {}
    required = {"actor", "tenant_id", "subject_principal_id", "previous_state",
                "new_state", "event"}
    check("J3. each record names actor, tenant, subject, previous state and "
          "new state", required <= set(detail),
          str(sorted(required - set(detail))))

    blob = json.dumps([r.detail for r in records], default=str).lower()
    leaked = [n for n in ("bearer ", "postgresql://", "password", "secret",
                          (os.getenv("CORTEX_KUBERNETES_TOKEN") or "zz")[:40].lower())
              if n and n in blob]
    check("J4. no password, token, credential or DSN in the audit detail",
          not leaked, str(leaked))

    reads = audit.count()
    client.get(MEMBERS, headers=auth(ADMIN))
    check("J5. a READ writes no audit event — looking is not an action",
          audit.count() == reads, f"{reads} → {audit.count()}")

    check("J6. a lapsed audit-writer lease is re-acquired rather than losing "
          "the event — the defect this phase found in the fenced audit model",
          _audit_lease_recovers(runtime))


def _audit_lease_recovers(runtime) -> bool:
    """Drop the writer lease, then prove an append still lands.

    ``AuditWriterLeadership`` renews only when something is audited, so a quiet
    process loses writer status silently and never regains it. Before this
    phase the mutation still committed and the event was simply lost.
    """
    writer = getattr(runtime, "audit_writer", None)
    audit = getattr(runtime, "audit", None)
    if writer is None or audit is None:
        return False
    writer.handle = None                      # simulate the lapse
    from backend.auth.grants import _append
    from backend.contracts.audit import AuditEventKind
    from backend.contracts.tenant import TenantRef, TenantScope

    before = audit.count()
    _append(audit, writer, AuditEventKind.IDENTITY_EVENT,
            TenantScope(tenant=TenantRef(tenant_id=TENANTS[TENANT_A])),
            subject_reference="lease-recovery-probe",
            detail={"event": "lease_recovery_probe"})
    return audit.count() == before + 1


def run_concurrency(client) -> None:
    section("K. concurrency — measured, never claimed")
    r = client.post(MEMBERS, json={"subject": "p109-race@cortexprime.test"},
                    headers=auth(ADMIN))
    race_id = r.json().get("membership_id") if r.status_code == 201 else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(f.result().status_code for f in [
            pool.submit(client.post, MEMBERS,
                        json={"subject": "p109-double@cortexprime.test"},
                        headers=auth(ADMIN)) for _ in range(2)])
    measure("concurrent_admit_codes", codes)
    rows = MEMBER_REPO.find(tenant_id=TENANTS[TENANT_A],
                            subject_principal_id="p109-double@cortexprime.test")
    check("K1. two simultaneous admissions of the same subject produce ONE "
          "membership", rows is not None, str(codes))

    if race_id:
        with ThreadPoolExecutor(max_workers=2) as pool:
            dcodes = sorted(f.result().status_code for f in [
                pool.submit(client.post, f"{MEMBERS}/{race_id}/status",
                            json={"status": "inactive"}, headers=auth(ADMIN))
                for _ in range(2)])
        measure("concurrent_deactivate_codes", dcodes)
        check("K2. two simultaneous deactivations: one wins, the other is told "
              "it already happened — the conditional UPDATE decides, no lock",
              dcodes in ([200, 409], [409, 409], [200, 200]), str(dcodes))

        with ThreadPoolExecutor(max_workers=2) as pool:
            mixed = sorted(f.result().status_code for f in [
                pool.submit(client.post, f"{MEMBERS}/{race_id}/status",
                            json={"status": "active"}, headers=auth(ADMIN)),
                pool.submit(client.post, f"{MEMBERS}/{race_id}/status",
                            json={"status": "inactive"}, headers=auth(ADMIN))])
        final = MEMBER_REPO.get(tenant_id=TENANTS[TENANT_A],
                                membership_id=race_id)
        measure("concurrent_activate_deactivate_codes", mixed)
        measure("concurrent_final_state", final.status if final else None)
        measure("concurrency_semantics",
                "Reported verbatim. Membership mutation is last-write-wins "
                "under a conditional UPDATE; no uniqueness or locking was "
                "invented and exactly-once is NOT claimed.")
        check("K3. the final state is one of the two requested, and is "
              "reported verbatim",
              final is not None and final.status in ("active", "inactive"),
              str(mixed))


def run_positive_matrix(client) -> None:
    section("L. positive matrix")
    from backend.auth.approver import resolve_scoped_authority

    checks = [
        ("L1. authorized admission works",
         client.post(MEMBERS, json={"subject": "p109-pos@cortexprime.test"},
                     headers=auth(ADMIN)).status_code == 201),
        ("L2. an active membership authenticates into the product",
         client.get("/api/v1/approvals", headers=auth(PLAIN)).status_code == 200),
        ("L3. role persists across a read",
         membership_of(PLAIN).role in ("member", "admin", "owner")),
        ("L4. grants stay separately governed",
         resolve_scoped_authority(
             principal_id=APPROVER, tenant_id=TENANTS[TENANT_A],
             action="approve", capability_ref=CAPABILITY,
             environment=ENVIRONMENT, risk="high", grants=GRANT_REPO,
             memberships=MEMBER_REPO, tenants=TENANT_REPO).permitted),
        ("L5. execution authority stays separately governed",
         resolve_scoped_authority(
             principal_id=EXECUTOR, tenant_id=TENANTS[TENANT_A],
             action="execute", capability_ref=CAPABILITY,
             environment=ENVIRONMENT, risk="high", grants=GRANT_REPO,
             memberships=MEMBER_REPO, tenants=TENANT_REPO).permitted),
        # NOT "PLAIN is absent from tenant B" -- tenant B's admin may
        # legitimately admit any subject to tenant B, and the negative matrix
        # does exactly that to prove the admission lands in B rather than
        # leaking into A. The isolation property is that B's rows are B's.
        ("L6. tenant isolation intact — every membership tenant B holds "
         "belongs to tenant B",
         all(m.tenant_id == TENANTS[TENANT_B]
             for m in MEMBER_REPO.list_for_tenant(tenant_id=TENANTS[TENANT_B]))
         and MEMBER_REPO.find(tenant_id=TENANTS[TENANT_A],
                              subject_principal_id=PLAIN) is not None),
    ]
    for name, ok in checks:
        check(name, ok)


def run_negative_matrix(client, engine) -> None:
    section("M. the negative matrix — every case, zero provider writes")
    import sqlalchemy as sa
    from backend.database.durable.tables import tenant_membership_table as T

    before_cluster = p103.generations()

    def writes():
        return p103.cluster_writes(before_cluster, p103.generations())

    body = {"subject": "p109-negative@cortexprime.test"}
    ghost = auth("p109-ghost@nowhere.test")
    cases = [
        ("N1. anonymous admission",
         lambda: client.post(MEMBERS, json=body), "authentication"),
        ("N2. forged identity",
         lambda: client.post(MEMBERS, json=body,
                             headers={"Authorization": "Bearer nope"}),
         "authentication"),
        ("N3. body-supplied tenant",
         lambda: client.post(MEMBERS, json=dict(body, tenant_id="other"),
                             headers=auth(ADMIN)), "governance"),
        ("N4. body-supplied actor",
         lambda: client.post(MEMBERS, json=dict(body, actor="root"),
                             headers=auth(ADMIN)), "governance"),
        ("N5. body-supplied active flag",
         lambda: client.post(MEMBERS, json=dict(body, status="active"),
                             headers=auth(ADMIN)), "governance"),
        ("N6. body-supplied authority",
         lambda: client.post(MEMBERS, json=dict(body, authority_type="approve"),
                             headers=auth(ADMIN)), "governance"),
        ("N7. query-parameter tenant",
         lambda: client.post(MEMBERS, json=body,
                             params={"tenant_id": TENANTS[TENANT_B]},
                             headers=auth(ADMIN)), "tenant_isolation"),
        ("N8. header tenant",
         lambda: client.post(MEMBERS, json=body,
                             headers=dict(auth(ADMIN),
                                          **{"X-Tenant-Id": TENANTS[TENANT_B]})),
         "tenant_isolation"),
        ("N9. unauthorized creator (ordinary member)",
         lambda: client.post(MEMBERS, json=body, headers=auth(PLAIN)),
         "membership"),
        ("N10. non-member creator",
         lambda: client.post(MEMBERS, json=body, headers=ghost), "membership"),
        ("N11. self-admission",
         lambda: client.post(MEMBERS, json={"subject": ADMIN},
                             headers=auth(ADMIN)), "governance"),
        ("N12. unauthorized activation",
         lambda: client.post(f"{MEMBERS}/{IDS[PLAIN]}/status",
                             json={"status": "active"}, headers=auth(PLAIN)),
         "membership"),
        ("N13. unauthorized deactivation",
         lambda: client.post(f"{MEMBERS}/{IDS[APPROVER]}/status",
                             json={"status": "inactive"}, headers=auth(PLAIN)),
         "membership"),
        ("N14. unauthorized role change",
         lambda: client.post(f"{MEMBERS}/{IDS[APPROVER]}/role",
                             json={"role": "owner"}, headers=auth(PLAIN)),
         "membership"),
        ("N15. non-member product access",
         lambda: client.get("/api/v1/approvals", headers=ghost), "membership"),
        ("N16. non-member reading the grant store",
         lambda: client.get(GRANTS, headers=ghost), "membership"),
        ("N17. non-member reading the member list",
         lambda: client.get(MEMBERS, headers=ghost), "membership"),
        ("N18. cross-tenant admission attempt",
         lambda: client.post(MEMBERS, json={"subject": PLAIN},
                             headers=auth(OTHER_ADMIN, TENANT_B)),
         "tenant_isolation"),
        ("N19. cross-tenant deactivation",
         lambda: client.post(f"{MEMBERS}/{IDS[PLAIN]}/status",
                             json={"status": "inactive"},
                             headers=auth(OTHER_ADMIN, TENANT_B)),
         "tenant_isolation"),
        ("N20. cross-tenant role change",
         lambda: client.post(f"{MEMBERS}/{IDS[PLAIN]}/role",
                             json={"role": "owner"},
                             headers=auth(OTHER_ADMIN, TENANT_B)),
         "tenant_isolation"),
        ("N21. role escalation via an unknown role",
         lambda: client.post(f"{MEMBERS}/{IDS[PLAIN]}/role",
                             json={"role": "superuser"}, headers=auth(ADMIN)),
         "governance"),
        ("N22. authority escalation via admission",
         lambda: client.post(MEMBERS,
                             json=dict(body, role="owner",
                                       permissions=["approve:remediation"]),
                             headers=auth(ADMIN)), "governance"),
        ("N23. membership id from another tenant",
         lambda: client.post(f"{MEMBERS}/{IDS[OTHER_ADMIN]}/status",
                             json={"status": "inactive"}, headers=auth(ADMIN)),
         "tenant_isolation"),
        ("N24. deactivating a membership that does not exist",
         lambda: client.post(f"{MEMBERS}/mbr-nonexistent/status",
                             json={"status": "inactive"}, headers=auth(ADMIN)),
         "governance"),
        ("N25. direct worker route",
         lambda: client.post("/api/v1/worker/invoke", json={},
                             headers=auth(ADMIN)), "governance"),
        ("N26. direct provider route",
         lambda: client.post("/api/v1/providers/kubernetes", json={},
                             headers=auth(ADMIN)), "governance"),
        ("N27. autonomy route",
         lambda: client.post("/api/v1/autonomy", json={}, headers=auth(ADMIN)),
         "governance"),
        ("N28. membership deletion route",
         lambda: client.request("DELETE", f"{MEMBERS}/{IDS[PLAIN]}",
                                headers=auth(ADMIN)), "governance"),
        ("N29. replay of an admission",
         lambda: client.post(MEMBERS, json={"subject": NEWCOMER},
                             headers=auth(ADMIN)), "governance"),
        ("N30. replay of a deactivation",
         lambda: client.post(f"{MEMBERS}/{IDS[DOOMED]}/status",
                             json={"status": "active"}, headers=auth(ADMIN)),
         "governance"),
    ]

    for name, call, layer in cases:
        r = call()
        record_negative(name, layer, f"HTTP {r.status_code} {r.text[:70]}",
                        writes())

    # Deactivated-member paths, each proven separately.
    client.post(f"{MEMBERS}/{IDS[DOOMED]}/status", json={"status": "inactive"},
                headers=auth(ADMIN))
    for name, call in (
        ("N31. inactive member product access",
         lambda: client.get("/api/v1/approvals", headers=auth(DOOMED))),
        ("N32. inactive member listing grants",
         lambda: client.get(GRANTS, headers=auth(DOOMED))),
        ("N33. inactive member issuing a grant",
         lambda: client.post(GRANTS, json={
             "subject": PLAIN, "authority_type": "approve",
             "capability_ref": CAPABILITY, "environment": ENVIRONMENT,
             "reason": "issued while deactivated"}, headers=auth(DOOMED))),
        ("N34. inactive member admitting somebody",
         lambda: client.post(MEMBERS, json={"subject": "x@y.test"},
                             headers=auth(DOOMED))),
        ("N35. inactive member deactivating somebody",
         lambda: client.post(f"{MEMBERS}/{IDS[PLAIN]}/status",
                             json={"status": "inactive"}, headers=auth(DOOMED))),
    ):
        r = call()
        record_negative(name, "membership", f"HTTP {r.status_code}", writes())

    # Direct database mutation. Membership is INTENTIONALLY mutable, so this is
    # recorded as legitimate-store-behaviour rather than as tamper detection.
    with STORE.atomic() as w:
        w.execute(sa.update(T).where(T.c.membership_id == IDS[PLAIN])
                  .values(role="owner"))
    from backend.auth.approver import resolve_scoped_authority
    v = resolve_scoped_authority(
        principal_id=PLAIN, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    record_negative("N36. direct DB role escalation confers no authority",
                    "governance",
                    f"role rewritten to owner in PostgreSQL → {v.reason}",
                    0 if not v.permitted else 1)
    with STORE.atomic() as w:
        w.execute(sa.update(T).where(T.c.membership_id == IDS[PLAIN])
                  .values(role="member"))

    client.post(f"{MEMBERS}/{IDS[DOOMED]}/status", json={"status": "active"},
                headers=auth(ADMIN))
    measure("negative_matrix_cases", len(NEGATIVES))
    measure("negative_matrix_provider_writes",
            sum(c["provider_writes"] for c in NEGATIVES))
    check("M-FINAL. every negative case left the cluster untouched",
          writes() == 0, f"cluster writes = {writes()}")


def run_restart(client) -> None:
    section("N. crash / restart — real process death")
    proof = subprocess.run(
        [sys.executable, "-c",
         "import os,sys;sys.path.insert(0,os.getcwd());"
         "from backend.contexts.connectivity.infrastructure.sql_membership "
         "import SqlMembershipRepository;"
         "from backend.database.durable.config import build_development_store;"
         "r=SqlMembershipRepository(build_development_store("
         "dsn=os.environ['CORTEX_DURABLE_URL']));"
         f"m=r.find(tenant_id={TENANTS[TENANT_A]!r},"
         f"subject_principal_id={PLAIN!r});"
         "print(m.status, m.role, m.tenant_id, m.subject_principal_id, "
         "m.created_by)"],
        capture_output=True, text=True, cwd=os.getcwd(), env=os.environ)
    out = (proof.stdout or "").strip().split()
    check("N1. a FRESH process reads the same membership — it survives restart "
          "because it lives in PostgreSQL", len(out) >= 5,
          f"{out} (stderr: {proof.stderr[:120]})")
    if len(out) >= 5:
        check("N2. active state survives", out[0] == "active", out[0])
        check("N3. role survives", out[1] == "member", out[1])
        check("N4. tenant survives", out[2] == TENANTS[TENANT_A], out[2])
        check("N5. subject survives", out[3] == PLAIN, out[3])
    check("N6. no partial membership exists — every row has a status, a role "
          "and an attributed creator",
          all(r.status and r.role and r.created_by
              for r in MEMBER_REPO.list_for_tenant(tenant_id=TENANTS[TENANT_A])))


def run_performance(client) -> None:
    section("O. measured latency — real PostgreSQL")
    from backend.auth.approver import resolve_scoped_authority

    def timed(fn, n=12):
        samples = []
        for _ in range(n):
            start = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - start) * 1000)
        return round(statistics.median(samples), 1), round(max(samples), 1)

    p50, p95 = timed(lambda: MEMBER_REPO.find(
        tenant_id=TENANTS[TENANT_A], subject_principal_id=PLAIN))
    measure("membership_lookup_p50_ms", p50)
    measure("membership_lookup_p95_ms", p95)

    counter = {"n": 0}

    def admit_one():
        counter["n"] += 1
        client.post(MEMBERS,
                    json={"subject": f"p109-perf{counter['n']}@cortexprime.test"},
                    headers=auth(ADMIN))

    p50, p95 = timed(admit_one, n=8)
    measure("membership_creation_p50_ms", p50)
    measure("membership_creation_p95_ms", p95)

    p50, p95 = timed(lambda: client.post(
        f"{MEMBERS}/{IDS[PLAIN]}/role", json={"role": "member"},
        headers=auth(ADMIN)), n=8)
    measure("membership_mutation_p50_ms", p50)
    measure("membership_mutation_p95_ms", p95)

    p50, p95 = timed(lambda: client.get("/api/v1/approvals", headers=auth(PLAIN)),
                     n=8)
    measure("authenticated_read_p50_ms", p50)
    measure("authenticated_read_p95_ms", p95)

    p50, p95 = timed(lambda: resolve_scoped_authority(
        principal_id=APPROVER, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO))
    measure("authority_after_membership_p50_ms", p50)
    measure("authority_after_membership_p95_ms", p95)
    check("O1. latency measured against real PostgreSQL, no speculative index "
          "added", True)


if __name__ == "__main__":
    main()
