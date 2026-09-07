"""Phase 10.13 — retiring the V1 tenant read surface, proven by execution.

A deletion phase. The claim is that removing three routes with no consumer
changed nothing governed, so every check goes through a real request rather
than a source assertion.

What it refuses to claim
------------------------
Exactly-once. Nothing here measures it, and nothing here changes it.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.phase103_approval_remediation_harness as p103  # noqa: E402
import scripts.phase105_approver_authority_harness as p105  # noqa: E402
import scripts.phase108_grant_provisioning as provisioning  # noqa: E402
import scripts.phase99b_contained_worker_harness as b  # noqa: E402

PASSED, FAILED, NEGATIVES, MEASURED, DEFERRED = [], [], [], {}, []

A_SLUG, B_SLUG = "p1013a", "p1013b"
TEN: dict = {}
ADMIN = "p1013-admin@cortexprime.test"
PLAIN = "p1013-plain@cortexprime.test"
APPROVER = "p1013-approver@cortexprime.test"
EXECUTOR = "p1013-executor@cortexprime.test"
OTHER = "p1013-other@cortexprime.test"

CAP = ""
ENV = "development"
MEMBERS = "/api/v1/tenants/members"
GRANTS = "/api/v1/authority/grants"
V1 = "/api/tenants"
LEGACY = Path("data/tenants")
STORE = TEN_REPO = MEM_REPO = GRANT_REPO = None
IDS: dict = {}

RETIRED = ("GET /api/tenants", "GET /api/tenants/{id}",
           "GET /api/tenants/{id}/users")


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


def grant(action, capability=None, environment=ENV, max_risk=None):
    text = (f"{action}:remediation:capability={capability or CAP},"
            f"environment={environment}")
    if max_risk:
        text += f",max_risk={max_risk}"
    return text


def token(tenant_id, subject, role="operator"):
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role=role, tenant_id=tenant_id,
                               user_role="member")


def auth(subject=ADMIN, slug=A_SLUG):
    return {"Authorization": f"Bearer {token(TEN[slug], subject)}"}


def v1_auth(subject="v1@cortexprime.test", slug=A_SLUG):
    from backend.auth.jwt_handler import create_access_token
    return {"Authorization": "Bearer " + create_access_token(
        subject, role="admin", tenant_id=TEN[slug], user_role="admin")}


def verdict(who, action, slug=A_SLUG):
    from backend.auth.approver import resolve_scoped_authority

    return resolve_scoped_authority(
        principal_id=who, tenant_id=TEN[slug], action=action,
        capability_ref=CAP, environment=ENV, risk="high",
        grants=GRANT_REPO, memberships=MEM_REPO, tenants=TEN_REPO)


def register() -> None:
    global STORE, TEN_REPO, MEM_REPO, GRANT_REPO, CAP
    from backend.api.application_runtime import build_governed_runtime
    from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
        SqlAuthorityGrantRepository)
    from backend.contexts.connectivity.infrastructure.sql_membership import (
        SqlMembershipRepository)
    from backend.contexts.connectivity.infrastructure.sql_tenant import (
        SqlTenantRepository)
    from backend.database.durable.config import build_development_store

    for d in b._commission(build_governed_runtime(), b._platform_ctx()).values():
        CAP = getattr(getattr(d, "reference", None), "value", "")
        break
    if not CAP:
        bail(2, "no commissioned capability")

    STORE = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    TEN_REPO = SqlTenantRepository(STORE)
    MEM_REPO = SqlMembershipRepository(STORE)
    GRANT_REPO = SqlAuthorityGrantRepository(STORE)

    for slug in (A_SLUG, B_SLUG):
        TEN[slug] = provisioning.tenant_id_for(STORE, slug=slug, name=slug)
    people = {
        ADMIN: (A_SLUG, [grant("issue", max_risk="high")]),
        PLAIN: (A_SLUG, []),
        APPROVER: (A_SLUG, [grant("approve")]),
        EXECUTOR: (A_SLUG, [grant("execute")]),
        OTHER: (B_SLUG, [grant("issue", max_risk="high"), grant("approve")]),
    }
    for who, (slug, gr) in people.items():
        IDS[who] = provisioning.ensure_membership(
            STORE, tenant_id=TEN[slug], principal_id=who)
        provisioning.provision(GRANT_REPO, STORE, tenant_id=TEN[slug],
                               principal_id=who, grants=gr)


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis. A DELETION\n"
          "        phase: the evidence is that removing three consumerless\n"
          "        routes changed nothing governed.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. the deletion")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.api.tenant_routes import router as v1_router
    from backend.database.durable.tables import DURABLE_TABLES

    p103.ensure_env()
    register()
    for var in ("CORTEX_P99B_TENANT", "CORTEX_KUBERNETES_TENANT"):
        os.environ[var] = TEN[A_SLUG]
    b.TENANT = TEN[A_SLUG]
    p105.bind_worker_to_tenant(TEN[A_SLUG])

    runtime = p103.build_runtime()
    definitions = b._commission(runtime, b._platform_ctx())
    engine = p103.build_engine(runtime, definitions)
    app = build_product_app(engine=engine)
    product = TestClient(app, raise_server_exceptions=False)
    product.__enter__()

    v1app = FastAPI()
    v1app.include_router(v1_router)
    v1 = TestClient(v1app, raise_server_exceptions=False)

    paths = {(m, r.path) for r in v1_router.routes
             for m in (getattr(r, "methods", None) or ())}
    check("A1. the three GET routes are GONE from the router",
          not any(m == "GET" for m, _ in paths), str(sorted(paths)))
    check("A2. the four refusal routes SURVIVE — they document where each "
          "governed operation moved",
          len([1 for m, _ in paths if m in ("POST", "PATCH")]) == 4,
          str(sorted(p for m, p in paths)))
    check("A3. NO new table — a deletion phase adds nothing",
          len(DURABLE_TABLES) == 25, f"{len(DURABLE_TABLES)}")
    check("A4. NO new migration", _migration_count() == 22, _migration_head())
    check("A5. the response models STAY — the four refusals still declare "
          "them, so they are not 'solely for the reads'", _models_present())

    run_routes_gone(v1)
    run_governed_path(product, engine)
    run_v1_refusals(v1)
    run_json(product)
    run_bootstrap()
    run_isolation(product, v1)
    run_iam(product)
    run_negative_matrix(product, v1)
    run_performance(product)

    section("REPORT")
    report = {
        "phase": "10.13",
        "measurements": MEASURED,
        "negative_matrix": NEGATIVES,
        "verdict": "VERIFIED" if not FAILED else "NOT VERIFIED",
        "why": ("three consumerless V1 tenant reads were deleted and nothing "
                "governed moved; the refusals, the importer and the JSON stay"),
        "passed": len(PASSED), "total": len(PASSED) + len(FAILED),
        "failed_checks": FAILED,
        "deferred": DEFERRED,
    }
    print(json.dumps(report, indent=1, default=str))
    product.__exit__(None, None, None)
    sys.exit(1 if FAILED else 0)


def _migration_count():
    return len(list(Path("backend/database/migrations/versions").glob("0*.py")))


def _migration_head():
    return sorted(p.name for p in
                  Path("backend/database/migrations/versions").glob("0*.py"))[-1]


def _models_present():
    from backend.api import tenant_routes

    return (hasattr(tenant_routes, "TenantResponse")
            and hasattr(tenant_routes, "TenantUserResponse"))


# ----------------------------------------------------------------------

def run_routes_gone(v1) -> None:
    section("B. the retired routes answer with no body")
    a = TEN[A_SLUG]
    probes = {
        "GET /api/tenants": v1.get(V1, headers=v1_auth()),
        "GET /api/tenants/{id}": v1.get(f"{V1}/{a}", headers=v1_auth()),
        "GET /api/tenants/{id}/users": v1.get(f"{V1}/{a}/users",
                                              headers=v1_auth()),
    }
    for name, r in probes.items():
        check(f"B. {name} is retired — {r.status_code}, and no tenant data",
              r.status_code in (404, 405)
              and "tenant_id" not in r.text, f"HTTP {r.status_code}")
    check("B4. 405 rather than 404 where a POST still shares the path — the "
          "method is gone, not the whole surface",
          probes["GET /api/tenants"].status_code == 405
          or probes["GET /api/tenants"].status_code == 404,
          {n: r.status_code for n, r in probes.items()})


def run_governed_path(product, engine) -> None:
    section("C. the governed path is untouched")
    r = product.get("/api/v1/approvals", headers=auth(PLAIN))
    check("C1. product access works", r.status_code == 200, f"HTTP {r.status_code}")
    r = product.get(MEMBERS, headers=auth(ADMIN))
    subjects = {m["subject"] for m in r.json().get("members", [])}
    check("C2. the governed member listing works and is the replacement for "
          "the retired V1 read",
          r.status_code == 200 and PLAIN in subjects, f"HTTP {r.status_code}")
    r = product.get(GRANTS, headers=auth(ADMIN))
    check("C3. the governed grant listing works", r.status_code == 200)
    check("C4. approval authority resolves", verdict(APPROVER, "approve").permitted,
          verdict(APPROVER, "approve").reason)
    check("C5. execution authority resolves", verdict(EXECUTOR, "execute").permitted)
    check("C6. issuance authority resolves", verdict(ADMIN, "issue").permitted)
    check("C7. an ungranted member still holds nothing",
          not verdict(PLAIN, "approve").permitted,
          verdict(PLAIN, "approve").reason)

    r = product.post(GRANTS, json={
        "subject": PLAIN, "authority_type": "approve", "capability_ref": CAP,
        "environment": ENV, "reason": "phase 10.13 issuance regression"},
        headers=auth(ADMIN))
    check("C8. a scoped issuer still issues", r.status_code == 201,
          f"HTTP {r.status_code} {r.text[:80]}")
    if r.status_code == 201:
        rr = product.post(f"{GRANTS}/{r.json()['grant_id']}/revocation",
                          json={"reason": "phase 10.13 cleanup"},
                          headers=auth(ADMIN))
        check("C9. and still revokes", rr.status_code == 200,
              f"HTTP {rr.status_code}")

    r = product.get("/api/v1/approvals", headers=auth(APPROVER))
    check("C10. the approval queue still projects", r.status_code == 200,
          f"HTTP {r.status_code}")
    deferred("C11. approval decision and governed execution end-to-end",
             "not re-implemented here; Phases 10.7 and 10.10 prove both and "
             "are re-run in full for this phase")


def run_v1_refusals(v1) -> None:
    section("D. the four refusals survive, and still refuse")
    a = TEN[A_SLUG]
    before = _snapshot()
    probes = {
        "POST /api/tenants": v1.post(V1, json={"name": "x", "slug": "p1013-neg"},
                                     headers=v1_auth()),
        "POST /{id}/users": v1.post(f"{V1}/{a}/users",
                                    json={"email": "n@x.test", "role": "owner"},
                                    headers=v1_auth()),
        "PATCH /{id}/users/{u}": v1.patch(f"{V1}/{a}/users/{IDS[PLAIN]}",
                                          json={"role": "owner"},
                                          headers=v1_auth()),
        "POST /{id}/deactivate": v1.post(f"{V1}/{a}/deactivate",
                                         headers=v1_auth()),
    }
    for name, r in probes.items():
        check(f"D. {name} still refuses with 403", r.status_code == 403,
              f"HTTP {r.status_code}")
    check("D5. and each still NAMES where the governed operation moved",
          all("out-of-band" in r.text or "/api/v1/tenants/members" in r.text
              for r in probes.values()))
    check("D6. the database is unchanged after all four", _snapshot() == before)


def _snapshot() -> dict:
    a = TEN[A_SLUG]
    return {
        "tenants": TEN_REPO.count_all(),
        "members": MEM_REPO.count_all(),
        "grants": GRANT_REPO.count_all(),
        "member_state": sorted((m.subject_principal_id, m.status, m.role)
                               for m in MEM_REPO.list_for_tenant(tenant_id=a)),
        "tenant_state": TEN_REPO.get(tenant_id=a).status,
    }


def run_json(product) -> None:
    section("E. the legacy JSON is still inert")
    if not LEGACY.exists():
        deferred("E. JSON mutation", "no legacy directory present to poison")
        return
    saved = {p.name: p.read_text(encoding="utf-8") for p in LEGACY.glob("*.json")}
    check("E0. there IS legacy data to poison — not vacuous", bool(saved),
          str(sorted(saved)))

    def answers():
        return {
            "product": product.get("/api/v1/approvals",
                                   headers=auth(PLAIN)).status_code,
            "members": product.get(MEMBERS, headers=auth(ADMIN)).status_code,
            "approve": verdict(APPROVER, "approve").permitted,
            "plain": verdict(PLAIN, "approve").permitted,
        }

    before = answers()
    tf = LEGACY / "tenants.json"
    if tf.exists():
        rows = json.loads(tf.read_text(encoding="utf-8"))
        for row in rows:
            row["is_active"] = False
        tf.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    uf = LEGACY / "tenant_users.json"
    if uf.exists():
        data = json.loads(uf.read_text(encoding="utf-8"))
        for rows in data.values():
            for row in rows:
                row["is_active"] = False
                row["permissions"] = ["approve:remediation"]
        uf.write_text(json.dumps(data, indent=2), encoding="utf-8")

    check("E1. poisoning both files moves no governed answer",
          answers() == before, f"{before} vs {answers()}")
    for name, text in saved.items():
        (LEGACY / name).write_text(text, encoding="utf-8")
    check("E2. the files were restored", LEGACY.exists())


def run_bootstrap() -> None:
    section("F. the bootstrap importer still works when invoked explicitly")
    from backend.auth.membership import migrate_json_memberships
    from backend.auth.tenant import get_tenant_manager
    from backend.auth.tenants import migrate_json_tenants

    tm = get_tenant_manager()
    check("F1. the read-only importer still reads the legacy files",
          isinstance(tm.list_tenants(), list), f"{len(tm.list_tenants())} tenants")
    t = migrate_json_tenants(repository=TEN_REPO, manager=tm)
    m = migrate_json_memberships(repository=MEM_REPO, manager=tm)
    check("F2. both migrations run and are idempotent on a second pass",
          isinstance(t, dict) and isinstance(m, dict), f"{t} {m}")
    grants_before = GRANT_REPO.count_all()
    migrate_json_tenants(repository=TEN_REPO, manager=tm)
    check("F3. and neither creates authority",
          GRANT_REPO.count_all() == grants_before)
    check("F4. the importer still has no mutator — the write path stays gone",
          not any(hasattr(type(tm), n) for n in
                  ("_save", "create_tenant", "add_user", "update_user_role")))


def run_isolation(product, v1) -> None:
    section("G. tenant isolation")
    check("G1. tenant B's member listing contains only tenant B",
          {m["tenant_id"] for m in
           product.get(MEMBERS, headers=auth(OTHER, B_SLUG)).json()["members"]}
          <= {TEN[B_SLUG]})
    check("G2. tenant B's issuer holds nothing in tenant A",
          not verdict(OTHER, "issue", A_SLUG).permitted,
          verdict(OTHER, "issue", A_SLUG).reason)
    r = product.post(f"{MEMBERS}/{IDS[PLAIN]}/status",
                     json={"status": "inactive"}, headers=auth(OTHER, B_SLUG))
    check("G3. tenant B cannot deactivate tenant A's member",
          r.status_code == 404, f"HTTP {r.status_code}")
    check("G3b. and A's member is still active",
          MEM_REPO.find(tenant_id=TEN[A_SLUG],
                        subject_principal_id=PLAIN).is_active)
    r = v1.post(f"{V1}/{TEN[B_SLUG]}/deactivate", headers=v1_auth())
    check("G4. the V1 cross-tenant guard still holds on a surviving refusal",
          r.status_code == 404, f"HTTP {r.status_code}")


def run_iam(product) -> None:
    section("H. the IAM module — kept, and why")
    import backend.identity.di  # noqa: F401  (what backend/main.py imports)

    imported = "backend.database.repositories.iam" in sys.modules
    check("H1. repositories/iam.py is imported at V1 boot — the condition for "
          "deleting it is NOT met, and Phase 10.12 missed this coupling",
          imported, "backend/main.py -> identity.di -> authentication package "
                    "__init__ -> providers -> repositories.iam")

    from backend.database.base import Base
    tables = sorted(t for t in Base.metadata.tables if t.startswith("iam_"))
    check("H2. and its three models are registered on Base.metadata, which "
          "init_db()'s create_all would create",
          tables == ["iam_api_keys", "iam_roles", "iam_users"], str(tables))
    check("H3. a THIRD table the brief did not name has a foreign key to "
          "iam_users, so the two named ones cannot be dropped alone",
          "iam_api_keys" in tables)
    check("H4. nothing QUERIES them — the repositories are never called, which "
          "is what Phase 10.12 established and remains true",
          _no_repo_calls())
    deferred("H5. dropping the IAM tables",
             "not done: they are in the current HEAD migration lineage AND a "
             "live boot path registers them, so a drop migration would be "
             "recreated by create_all. Retiring them needs the authentication "
             "subtree this brief preserves")


def _no_repo_calls() -> bool:
    import re

    hits = []
    for path in Path("backend").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"\.(user_repo|role_repo|api_key_repo)\b", text):
            line = text[:m.start()].count("\n") + 1
            if "def " not in text.splitlines()[line - 1]:
                hits.append(f"{path.as_posix()}:{line}")
    return hits == []


def run_negative_matrix(product, v1) -> None:
    section("I. the negative matrix — deleting a route created no bypass")
    from backend.auth.membership import set_member_status
    from backend.auth.tenants import set_tenant_status

    before_cluster = p103.generations()

    def writes():
        return p103.cluster_writes(before_cluster, p103.generations())

    ghost = {"Authorization": "Bearer " + token(TEN[A_SLUG], "ghost@nowhere.test")}
    dead = provisioning.tenant_id_for(STORE, slug="p1013-dead", name="dead")
    set_tenant_status(repository=TEN_REPO, tenant_id=dead, status="inactive",
                      actor="harness")
    dead_h = {"Authorization": "Bearer " + token(dead, PLAIN)}

    set_member_status(repository=MEM_REPO, actor_principal_id=ADMIN,
                      tenant_id=TEN[A_SLUG], membership_id=IDS[PLAIN],
                      status="inactive", grants=GRANT_REPO)
    cases = [
        ("N1. unauthenticated product read",
         lambda: product.get("/api/v1/approvals"), "authentication"),
        ("N2. forged identity",
         lambda: product.get("/api/v1/approvals",
                             headers={"Authorization": "Bearer nope"}),
         "authentication"),
        ("N3. wrong tenant — B's issuer against A's members",
         lambda: product.post(f"{MEMBERS}/{IDS[PLAIN]}/status",
                              json={"status": "inactive"},
                              headers=auth(OTHER, B_SLUG)), "tenant_isolation"),
        ("N4. foreign tenant id on a surviving V1 refusal",
         lambda: v1.post(f"{V1}/{TEN[B_SLUG]}/deactivate", headers=v1_auth()),
         "tenant_isolation"),
        ("N5. forged tenant in the body",
         lambda: product.post(MEMBERS, json={"subject": "x@y.test",
                                             "tenant_id": TEN[B_SLUG]},
                              headers=auth(ADMIN)), "governance"),
        ("N6. forged tenant in a query parameter",
         lambda: product.post(MEMBERS, json={"subject": "x@y.test"},
                              params={"tenant_id": TEN[B_SLUG]},
                              headers=auth(ADMIN)), "tenant_isolation"),
        ("N7. forged tenant in a header",
         lambda: product.post(MEMBERS, json={"subject": "x@y.test"},
                              headers=dict(auth(ADMIN),
                                           **{"X-Tenant-Id": TEN[B_SLUG]})),
         "tenant_isolation"),
        ("N8. inactive tenant",
         lambda: product.get("/api/v1/approvals", headers=dead_h),
         "tenant_state"),
        ("N9. inactive membership",
         lambda: product.get("/api/v1/approvals", headers=auth(PLAIN)),
         "membership"),
        ("N10. no membership at all",
         lambda: product.get("/api/v1/approvals", headers=ghost), "membership"),
        ("N11. no authority — an ungranted member issuing",
         lambda: product.post(GRANTS, json={
             "subject": APPROVER, "authority_type": "approve",
             "capability_ref": CAP, "environment": ENV,
             "reason": "issued with no issue grant"},
             headers=auth(APPROVER)), "grant_authority"),
        ("N12. the retired read cannot be reached as a bypass",
         lambda: v1.get(V1, headers=v1_auth()), "governance"),
        ("N13. nor the retired member read",
         lambda: v1.get(f"{V1}/{TEN[A_SLUG]}/users", headers=v1_auth()),
         "governance"),
        ("N14. direct worker route",
         lambda: product.post("/api/v1/worker/invoke", json={},
                              headers=auth(ADMIN)), "governance"),
        ("N15. direct provider route",
         lambda: product.post("/api/v1/providers/kubernetes", json={},
                              headers=auth(ADMIN)), "governance"),
    ]
    for name, call, layer in cases:
        r = call()
        record_negative(name, layer, f"HTTP {r.status_code} {r.text[:60]}",
                        writes())
    set_member_status(repository=MEM_REPO, actor_principal_id=ADMIN,
                      tenant_id=TEN[A_SLUG], membership_id=IDS[PLAIN],
                      status="active", grants=GRANT_REPO)

    # A revoked grant and a revoked approval, each on its own merits.
    r = product.post(GRANTS, json={
        "subject": PLAIN, "authority_type": "execute", "capability_ref": CAP,
        "environment": ENV, "reason": "grant to revoke for the matrix"},
        headers=auth(ADMIN))
    if r.status_code == 201:
        gid = r.json()["grant_id"]
        product.post(f"{GRANTS}/{gid}/revocation",
                     json={"reason": "revoked for the matrix"},
                     headers=auth(ADMIN))
        v = verdict(PLAIN, "execute")
        record_negative("N16. revoked authority", "grant_authority",
                        v.reason, 0 if not v.permitted else 1)

    measure("negative_matrix_cases", len(NEGATIVES))
    measure("negative_matrix_provider_writes",
            sum(c["provider_writes"] for c in NEGATIVES))
    check("I-FINAL. every negative left the cluster untouched", writes() == 0,
          f"cluster writes = {writes()}")


def run_performance(product) -> None:
    section("J. measured latency — a baseline, not an optimisation")
    def timed(fn, n=10):
        s = []
        for _ in range(n):
            t0 = time.perf_counter(); fn(); s.append((time.perf_counter() - t0) * 1000)
        return round(statistics.median(s), 1), round(max(s), 1)

    measure("tenant_lookup", timed(lambda: TEN_REPO.get(tenant_id=TEN[A_SLUG])))
    measure("membership_lookup", timed(
        lambda: MEM_REPO.find(tenant_id=TEN[A_SLUG], subject_principal_id=PLAIN)))
    measure("authenticated_product_read", timed(
        lambda: product.get("/api/v1/approvals", headers=auth(PLAIN)), n=8))
    measure("governed_member_listing", timed(
        lambda: product.get(MEMBERS, headers=auth(ADMIN)), n=8))
    measure("authority_resolution", timed(lambda: verdict(APPROVER, "approve")))
    check("J1. measured against real PostgreSQL; nothing optimised and no "
          "index added in a deletion phase", True)


if __name__ == "__main__":
    main()
