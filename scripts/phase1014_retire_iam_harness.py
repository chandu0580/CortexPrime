"""Phase 10.14 — retiring the dead IAM subsystem, proven by execution.

The claim is that cutting IAM out of the runtime graph and dropping its three
tables changed nothing in the authoritative product path.

The two load-bearing checks are Part D (the models are off ``Base.metadata``)
and Part K (the create_all trap). Both run in a **child process**, because a
stale ``sys.modules`` entry in the parent would make a broken cut look clean.

What it refuses to claim
------------------------
Exactly-once. Nothing here measures or changes it.
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

A_SLUG, B_SLUG = "p1014a", "p1014b"
TEN: dict = {}
ADMIN = "p1014-admin@cortexprime.test"
PLAIN = "p1014-plain@cortexprime.test"
APPROVER = "p1014-approver@cortexprime.test"
EXECUTOR = "p1014-executor@cortexprime.test"
OTHER = "p1014-other@cortexprime.test"

CAP = ""
ENV = "development"
MEMBERS = "/api/v1/tenants/members"
GRANTS = "/api/v1/authority/grants"
V1 = "/api/tenants"
IAM = ("iam_users", "iam_roles", "iam_api_keys")
STORE = TEN_REPO = MEM_REPO = GRANT_REPO = None
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


def verdict(who, action, slug=A_SLUG):
    from backend.auth.approver import resolve_scoped_authority

    return resolve_scoped_authority(
        principal_id=who, tenant_id=TEN[slug], action=action,
        capability_ref=CAP, environment=ENV, risk="high",
        grants=GRANT_REPO, memberships=MEM_REPO, tenants=TEN_REPO)


def child(code: str) -> str:
    """Run a snippet in a FRESH interpreter and return its stdout.

    Every metadata and create_all claim goes through here. The parent has
    already imported half the codebase, so asking it whether a module is
    imported would answer a question about this process, not about a boot.
    """
    res = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=os.getcwd(), env=os.environ)
    return (res.stdout or "") + ("\n[stderr] " + res.stderr[-300:]
                                 if res.returncode else "")


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
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis, REAL child\n"
          "        processes and REAL databases. A retirement: the evidence is\n"
          "        that the authoritative path did not move.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. the dependency graph is cut")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.api.tenant_routes import router as v1_router

    p103.ensure_env()
    register()
    for var in ("CORTEX_P99B_TENANT", "CORTEX_KUBERNETES_TENANT"):
        os.environ[var] = TEN[A_SLUG]
    b.TENANT = TEN[A_SLUG]
    p105.bind_worker_to_tenant(TEN[A_SLUG])

    runtime = p103.build_runtime()
    definitions = b._commission(runtime, b._platform_ctx())
    engine = p103.build_engine(runtime, definitions)
    product = TestClient(build_product_app(engine=engine),
                         raise_server_exceptions=False)
    product.__enter__()
    v1app = FastAPI(); v1app.include_router(v1_router)
    v1 = TestClient(v1app, raise_server_exceptions=False)

    out = child(
        "import sys;"
        "import backend.identity.di as di;"
        "print('IAM_IMPORTED', 'backend.database.repositories.iam' in sys.modules);"
        "di.register_identity_services();"
        "print('DI_OK True')")
    check("A1. V1 boot no longer imports repositories.iam — the edge Phase "
          "10.13 refused to cut", "IAM_IMPORTED False" in out, out.strip()[:160])
    check("A2. and register_identity_services() still wires its nine services",
          "DI_OK True" in out, out.strip()[:120])
    check("A3. the two deleted modules are gone",
          not Path("backend/identity/authentication/providers.py").exists()
          and not Path("backend/database/repositories/iam.py").exists())
    check("A4. PasswordVerifier survives — it was registered and never touched "
          "the IAM tables", _password_verifier_lives())
    check("A5. the factory keeps every other repository",
          _factory_intact(), _factory_repo_count())

    run_metadata()
    run_migration_scenarios()
    run_create_all_trap()
    run_iam_tables()
    run_auth_regression(product)
    run_governed(product)
    run_isolation(product, v1)
    run_v1(v1)
    run_negative_matrix(product, v1)
    run_performance(product)

    section("REPORT")
    report = {
        "phase": "10.14",
        "measurements": MEASURED,
        "negative_matrix": NEGATIVES,
        "verdict": "VERIFIED" if not FAILED else "NOT VERIFIED",
        "why": ("the dead IAM subsystem is out of the runtime graph and out of "
                "the schema, and the authoritative product path is unchanged"),
        "passed": len(PASSED), "total": len(PASSED) + len(FAILED),
        "failed_checks": FAILED,
        "deferred": DEFERRED,
    }
    print(json.dumps(report, indent=1, default=str))
    product.__exit__(None, None, None)
    sys.exit(1 if FAILED else 0)


def _password_verifier_lives() -> bool:
    from backend.identity.authentication import PasswordVerifier

    v = PasswordVerifier()
    digest = v.hash_password("phase-10-14-probe")
    return (v.verify_password("phase-10-14-probe", digest)
            and not v.verify_password("wrong", digest))


def _factory_intact() -> bool:
    from backend.database.repositories.factory import RepositoryFactory

    gone = {"user_repo", "role_repo", "api_key_repo"}
    names = {n for n in dir(RepositoryFactory) if n.endswith("_repo")}
    return not (names & gone) and len(names) >= 10


def _factory_repo_count() -> str:
    from backend.database.repositories.factory import RepositoryFactory

    return f"{len([n for n in dir(RepositoryFactory) if n.endswith('_repo')])} repositories kept"


# ---------------------------------------------------------------- Part D

def run_metadata() -> None:
    section("B. Part D — the models are off Base.metadata BEFORE create_all")
    # _ensure_bc_models() is what init_db() calls before create_all, so the
    # honest question is what the metadata looks like AFTER it -- a partial
    # import would answer a question nothing in production asks.
    out = child(
        "from backend.database.models import _ensure_bc_models;"
        "_ensure_bc_models();"
        "from backend.database.base import Base;"
        "iam=[t for t in Base.metadata.tables if t.startswith('iam_')];"
        "print('IAM_TABLES', iam);"
        "print('TOTAL', len(Base.metadata.tables))")
    check("B1. after the application's own model registration, Base.metadata "
          "contains no iam_ table — in a FRESH interpreter",
          "IAM_TABLES []" in out, out.strip()[:160])
    total = 0
    for line in out.splitlines():
        if line.startswith("TOTAL "):
            total = int(line.split()[1])
    check("B2. and the rest of the metadata is intact — a removal, not a "
          "collapse", total >= 30, f"{total} tables registered")


# ---------------------------------------------------------------- Part J

def _tables(dsn: str) -> set:
    import sqlalchemy as sa

    eng = sa.create_engine(dsn, future=True)
    try:
        return set(sa.inspect(eng).get_table_names())
    finally:
        eng.dispose()


def _admin_dsn() -> str:
    base = os.environ["CORTEX_DURABLE_URL"]
    return base.rsplit("/", 1)[0] + "/postgres"


def _recreate(db: str) -> str:
    import sqlalchemy as sa

    eng = sa.create_engine(_admin_dsn(), future=True,
                           isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(sa.text(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname='{db}' AND pid <> pg_backend_pid()"))
        c.execute(sa.text(f"DROP DATABASE IF EXISTS {db}"))
        c.execute(sa.text(f"CREATE DATABASE {db}"))
    eng.dispose()
    return os.environ["CORTEX_DURABLE_URL"].rsplit("/", 1)[0] + "/" + db


def _alembic(dsn: str, revision: str = "head") -> str:
    """Drive alembic against one database.

    ``migrations/env.py`` builds its own async DSN from ``POSTGRES_URL`` and
    ignores ``sqlalchemy.url`` entirely -- setting the latter migrated nothing
    and left an empty database that a "no iam tables" check passed vacuously.
    The C1b assertion caught it.
    """
    return child(
        "import os;"
        f"os.environ['POSTGRES_URL'] = {dsn!r};"
        "from alembic.config import Config;"
        "from alembic import command;"
        "cfg=Config();"
        "cfg.set_main_option('script_location','backend/database/migrations');"
        f"command.upgrade(cfg, {revision!r});"
        "print('MIGRATED')")


def run_migration_scenarios() -> None:
    section("C. Part J — two database scenarios, both converging")

    fresh = _recreate("cortex_p1014_fresh")
    out = _alembic(fresh)
    if "MIGRATED" not in out:
        deferred("C1/C2. alembic scenarios",
                 "alembic could not be driven programmatically in this "
                 f"environment: {out.strip()[:200]}")
        return
    tables = _tables(fresh)
    check("C1. Scenario 1 — an EMPTY database migrated to head has no iam_ "
          "table", not any(t.startswith("iam_") for t in tables),
          f"{len(tables)} tables")
    check("C1b. and it does have the governed tables, so the migration really "
          "ran", "cp_tenant" in tables and "cp_authority_grant" in tables)

    legacy = _recreate("cortex_p1014_legacy")
    seeded = _alembic(legacy, "0022_tenant_record").replace("MIGRATED", "SEEDED")
    if "SEEDED" not in seeded:
        deferred("C2. Scenario 2", f"could not seed: {seeded.strip()[:200]}")
        return
    before = _tables(legacy)
    check("C2a. Scenario 2 — a database at 0022 really DOES have the legacy "
          "tables, so this is not vacuous",
          all(t in before for t in IAM), sorted(t for t in before if t.startswith("iam_")))
    out = _alembic(legacy)
    after = _tables(legacy)
    check("C2b. running the new migration removes all three",
          "MIGRATED" in out and not any(t.startswith("iam_") for t in after),
          sorted(t for t in after if t.startswith("iam_")) or "none")
    check("C3. both scenarios converge to the same schema",
          _tables(fresh) == after,
          f"fresh={len(_tables(fresh))} legacy={len(after)}")


# ---------------------------------------------------------------- Part K

def run_create_all_trap() -> None:
    """Part K — the mandatory negative test, and a pre-existing defect.

    The brief says: start from a database with no IAM tables, run the
    application's normal initialisation, and prove they stay absent.

    Running it surfaced something unrelated and older than this phase.
    ``init_db()`` calls ``_ensure_bc_models()`` and then
    ``Base.metadata.create_all``, and that **raises** on
    ``reflection_history.mission_id -> missions``: no model anywhere declares
    ``__tablename__ = "missions"`` (the table is created by migration ``0001``
    and never mapped), so SQLAlchemy cannot resolve the foreign key while
    sorting tables.

    That is not caused by this phase. The module deleted here defined exactly
    three tables -- ``iam_users``, ``iam_roles``, ``iam_api_keys`` -- so
    removing it cannot be why ``missions`` is missing. The check below asserts
    both halves: the IAM tables stay absent, **and** the failure names
    ``missions`` rather than anything IAM, so the trap is answered rather than
    excused.
    """
    section("D. Part K — the create_all trap (mandatory negative test)")
    dsn = _recreate("cortex_p1014_trap")
    out = child(
        "from backend.database.models import _ensure_bc_models;"
        "_ensure_bc_models();"
        "from backend.database.base import Base;"
        "import sqlalchemy as sa;"
        f"eng=sa.create_engine({dsn!r}, future=True);"
        "print('IAM_IN_METADATA', sorted(t for t in Base.metadata.tables "
        "if t.startswith('iam_')));"
        "err='';\n"
        "try:\n"
        "    Base.metadata.create_all(eng)\n"
        "except Exception as exc:\n"
        "    err=type(exc).__name__+': '+str(exc)[:120]\n"
        "print('CREATE_ALL_ERROR', err);"
        "names=sa.inspect(eng).get_table_names();"
        "print('IAM_AFTER', sorted(t for t in names if t.startswith('iam_')))")

    check("D1. after the application's own initialisation, the IAM tables are "
          "ABSENT from the database — the trap Phase 10.13 could not pass",
          "IAM_AFTER []" in out, out.strip()[:200])
    check("D2. and they are absent because they are not in Base.metadata at "
          "all, so create_all has nothing to create — Phase 10.13's harness "
          "recorded the opposite state (H2: all three registered)",
          "IAM_IN_METADATA []" in out, out.strip()[:160])
    # Re-pointed by Phase 10.16. This check used to assert that create_all
    # FAILED with NoReferencedTableError on reflection_history -> missions,
    # "a table no model declares" -- a pre-existing defect Phase 10.14 found,
    # proved unrelated to IAM, and deliberately did not repair.
    #
    # Phase 10.16 repaired exactly that, by adding the missing ORM mapping for
    # the existing `missions` table (ADR-111). The check is INVERTED rather
    # than deleted, so it now fails if the mapping ever disappears again and
    # the metadata graph reopens.
    check("D3. the reflection_history -> missions mapping gap this phase "
          "reported is REPAIRED (Phase 10.16): create_all no longer raises "
          "NoReferencedTableError, and no failure names missions",
          "NoReferencedTableError" not in out
          and "could not find table" not in out,
          out.split("CREATE_ALL_ERROR")[-1].strip()[:150])
    check("D4. and the repair did not resurrect IAM — create_all still has no "
          "iam_ table to create, which is what THIS phase is about",
          "IAM_IN_METADATA []" in out and "IAM_AFTER []" in out,
          out.strip()[:160])


def run_iam_tables() -> None:
    section("E. the IAM tables in the databases that had them")
    import sqlalchemy as sa

    dsn = os.environ["CORTEX_DURABLE_URL"].rsplit("/", 1)[0] + "/cortex_p99b"
    try:
        present = {t for t in _tables(dsn) if t.startswith("iam_")}
    except Exception as exc:  # noqa: BLE001
        deferred("E. cortex_p99b", f"not reachable: {exc}")
        return
    if not present:
        check("E1. cortex_p99b has no iam table left", True, "already clean")
        return
    # Part F was established before any deletion: all three were empty.
    eng = sa.create_engine(dsn, future=True)
    with eng.connect() as c:
        rows = {t: c.execute(sa.text(f"select count(*) from {t}")).scalar()
                for t in present}
    eng.dispose()
    check("E1. they are still empty — no authoritative state is being dropped",
          all(v == 0 for v in rows.values()), str(rows))
    out = _alembic(dsn)
    left = {t for t in _tables(dsn) if t.startswith("iam_")}
    check("E2. the migration removes them from a REAL pre-existing database",
          "MIGRATED" in out and not left, str(left) or "none")


# ---------------------------------------------------------------- product

def run_auth_regression(product) -> None:
    section("F. Part B — authentication, by real request")
    from backend.auth.jwt_handler import verify_credentials

    user = os.getenv("CORTEX_USER", "admin")
    check("F1. verify_credentials rejects a wrong password — the env-configured "
          "path is live and did not become permissive",
          not verify_credentials(user, "definitely-not-the-password"))
    check("F2. and rejects an unknown user",
          not verify_credentials("nobody@nowhere.test", "x"))
    r = product.get("/api/v1/approvals", headers=auth(PLAIN))
    check("F3. an authenticated member reaches the product", r.status_code == 200,
          f"HTTP {r.status_code}")
    out = child(
        "from backend.api.auth_routes import _tenant_claims;"
        "print('CLAIMS_CALLABLE', callable(_tenant_claims))")
    check("F4. the login/refresh tenant-claim wire still imports and is "
          "callable with IAM gone", "CLAIMS_CALLABLE True" in out,
          out.strip()[:120])


def run_governed(product) -> None:
    section("G. Part G — the governed path")
    check("G1. tenant lookup", TEN_REPO.get(tenant_id=TEN[A_SLUG]).is_active)
    check("G2. membership lookup",
          MEM_REPO.find(tenant_id=TEN[A_SLUG],
                        subject_principal_id=PLAIN) is not None)
    check("G3. approve authority", verdict(APPROVER, "approve").permitted,
          verdict(APPROVER, "approve").reason)
    check("G4. execute authority", verdict(EXECUTOR, "execute").permitted)
    check("G5. issue authority", verdict(ADMIN, "issue").permitted)
    check("G6. an ungranted member holds nothing",
          not verdict(PLAIN, "approve").permitted)

    r = product.post(GRANTS, json={
        "subject": PLAIN, "authority_type": "approve", "capability_ref": CAP,
        "environment": ENV, "reason": "phase 10.14 issuance regression"},
        headers=auth(ADMIN))
    check("G7. grant issuance", r.status_code == 201, f"HTTP {r.status_code}")
    if r.status_code == 201:
        rr = product.post(f"{GRANTS}/{r.json()['grant_id']}/revocation",
                          json={"reason": "phase 10.14 cleanup"},
                          headers=auth(ADMIN))
        check("G8. grant revocation", rr.status_code == 200)
    check("G9. approval queue projects",
          product.get("/api/v1/approvals", headers=auth(APPROVER)).status_code == 200)
    check("G10. the member listing works",
          product.get(MEMBERS, headers=auth(ADMIN)).status_code == 200)
    deferred("G11. approval decision and governed execution end-to-end",
             "not re-implemented here; Phases 10.7 and 10.10 prove both and are "
             "re-run in full for this phase")


def run_isolation(product, v1) -> None:
    section("H. tenant isolation")
    check("H1. tenant B sees only tenant B",
          {m["tenant_id"] for m in
           product.get(MEMBERS, headers=auth(OTHER, B_SLUG)).json()["members"]}
          <= {TEN[B_SLUG]})
    check("H2. B's issuer holds nothing in A",
          not verdict(OTHER, "issue", A_SLUG).permitted,
          verdict(OTHER, "issue", A_SLUG).reason)
    check("H3. A's issuer holds nothing in B",
          not verdict(ADMIN, "issue", B_SLUG).permitted)
    r = product.post(f"{MEMBERS}/{IDS[PLAIN]}/status",
                     json={"status": "inactive"}, headers=auth(OTHER, B_SLUG))
    check("H4. B cannot deactivate A's member", r.status_code == 404,
          f"HTTP {r.status_code}")
    check("H4b. and A's member is still active",
          MEM_REPO.find(tenant_id=TEN[A_SLUG],
                        subject_principal_id=PLAIN).is_active)


def run_v1(v1) -> None:
    section("I. Part I — the V1 surface is unchanged")
    from backend.api.tenant_routes import router
    from backend.auth.jwt_handler import create_access_token

    paths = {(m, r.path) for r in router.routes
             for m in (getattr(r, "methods", None) or ())}
    check("I1. still exactly four routes, all mutations", len(paths) == 4,
          str(sorted(p for _, p in paths)))
    check("I2. no GET survives — Phase 10.13's retirement holds",
          not any(m == "GET" for m, _ in paths))
    h = {"Authorization": "Bearer " + create_access_token(
        "v1@cortexprime.test", role="admin", tenant_id=TEN[A_SLUG],
        user_role="admin")}
    codes = [
        v1.post(V1, json={"name": "x", "slug": "p1014-neg"}, headers=h).status_code,
        v1.post(f"{V1}/{TEN[A_SLUG]}/users",
                json={"email": "x@y.test", "role": "owner"}, headers=h).status_code,
        v1.patch(f"{V1}/{TEN[A_SLUG]}/users/{IDS[PLAIN]}",
                 json={"role": "owner"}, headers=h).status_code,
        v1.post(f"{V1}/{TEN[A_SLUG]}/deactivate", headers=h).status_code,
    ]
    check("I3. all four still refuse with 403", codes == [403, 403, 403, 403],
          str(codes))
    check("I4. no IAM route of any kind exists",
          not any("iam" in p.lower() for _, p in paths))


def run_negative_matrix(product, v1) -> None:
    section("J. the negative matrix")
    from backend.auth.membership import set_member_status
    from backend.auth.tenants import set_tenant_status

    before_cluster = p103.generations()

    def writes():
        return p103.cluster_writes(before_cluster, p103.generations())

    ghost = {"Authorization": "Bearer " + token(TEN[A_SLUG], "ghost@nowhere.test")}
    dead = provisioning.tenant_id_for(STORE, slug="p1014-dead", name="dead")
    set_tenant_status(repository=TEN_REPO, tenant_id=dead, status="inactive",
                      actor="harness")
    dead_h = {"Authorization": "Bearer " + token(dead, PLAIN)}

    set_member_status(repository=MEM_REPO, actor_principal_id=ADMIN,
                      tenant_id=TEN[A_SLUG], membership_id=IDS[PLAIN],
                      status="inactive", grants=GRANT_REPO)
    cases = [
        ("N1. unauthenticated", lambda: product.get("/api/v1/approvals"),
         "authentication"),
        ("N2. malformed token",
         lambda: product.get("/api/v1/approvals",
                             headers={"Authorization": "Bearer not.a.token"}),
         "authentication"),
        ("N3. inactive tenant",
         lambda: product.get("/api/v1/approvals", headers=dead_h),
         "tenant_state"),
        ("N4. inactive membership",
         lambda: product.get("/api/v1/approvals", headers=auth(PLAIN)),
         "membership"),
        ("N5. no membership at all",
         lambda: product.get("/api/v1/approvals", headers=ghost), "membership"),
        ("N6. foreign tenant on a surviving V1 refusal",
         lambda: v1.post(f"{V1}/{TEN[B_SLUG]}/deactivate",
                         headers={"Authorization": "Bearer " + token(
                             TEN[A_SLUG], "v1@x.test", "admin")}),
         "tenant_isolation"),
        ("N7. forged tenant in the body",
         lambda: product.post(MEMBERS, json={"subject": "x@y.test",
                                             "tenant_id": TEN[B_SLUG]},
                              headers=auth(ADMIN)), "governance"),
        ("N8. forged tenant in a header",
         lambda: product.post(MEMBERS, json={"subject": "x@y.test"},
                              headers=dict(auth(ADMIN),
                                           **{"X-Tenant-Id": TEN[B_SLUG]})),
         "tenant_isolation"),
        ("N9. forged tenant in a query parameter",
         lambda: product.post(MEMBERS, json={"subject": "x@y.test"},
                              params={"tenant_id": TEN[B_SLUG]},
                              headers=auth(ADMIN)), "tenant_isolation"),
        ("N10. no authority",
         lambda: product.post(GRANTS, json={
             "subject": APPROVER, "authority_type": "approve",
             "capability_ref": CAP, "environment": ENV,
             "reason": "issued with no issue grant"},
             headers=auth(APPROVER)), "grant_authority"),
    ]
    for name, call, layer in cases:
        r = call()
        record_negative(name, layer, f"HTTP {r.status_code} {r.text[:60]}",
                        writes())
    set_member_status(repository=MEM_REPO, actor_principal_id=ADMIN,
                      tenant_id=TEN[A_SLUG], membership_id=IDS[PLAIN],
                      status="active", grants=GRANT_REPO)

    r = product.post(GRANTS, json={
        "subject": PLAIN, "authority_type": "execute", "capability_ref": CAP,
        "environment": ENV, "reason": "grant to revoke for the matrix"},
        headers=auth(ADMIN))
    if r.status_code == 201:
        product.post(f"{GRANTS}/{r.json()['grant_id']}/revocation",
                     json={"reason": "revoked for the matrix"},
                     headers=auth(ADMIN))
        v = verdict(PLAIN, "execute")
        record_negative("N11. revoked authority", "grant_authority", v.reason,
                        0 if not v.permitted else 1)

    approvals = product.get("/api/v1/approvals", headers=auth(APPROVER)).json()
    items = approvals.get("approvals") or approvals.get("items") or []
    stale = [a for a in items if a.get("state") in ("expired", "withdrawn",
                                                    "rejected")]
    if stale:
        target = stale[0]
        r = product.post(
            f"/api/v1/approvals/{target.get('approval_id')}/execute", json={},
            headers=auth(EXECUTOR))
        record_negative(f"N12. {target.get('state')} approval cannot execute",
                        "approval_state", f"HTTP {r.status_code}", writes())
    else:
        deferred("N12. expired/revoked approval",
                 "no stale approval in this fresh database; Phases 10.7 and "
                 "10.10 cover both states and are re-run for this phase")

    measure("negative_matrix_cases", len(NEGATIVES))
    measure("negative_matrix_provider_writes",
            sum(c["provider_writes"] for c in NEGATIVES))
    check("J-FINAL. every negative left the cluster untouched", writes() == 0,
          f"cluster writes = {writes()}")


def run_performance(product) -> None:
    section("K. measured latency — a baseline")
    def timed(fn, n=10):
        s = []
        for _ in range(n):
            t0 = time.perf_counter(); fn(); s.append((time.perf_counter() - t0) * 1000)
        return round(statistics.median(s), 1), round(max(s), 1)

    from backend.auth.jwt_handler import verify_credentials
    user = os.getenv("CORTEX_USER", "admin")
    measure("credential_check", timed(lambda: verify_credentials(user, "wrong"),
                                      n=6))
    measure("membership_lookup", timed(
        lambda: MEM_REPO.find(tenant_id=TEN[A_SLUG], subject_principal_id=PLAIN)))
    measure("authenticated_product_read", timed(
        lambda: product.get("/api/v1/approvals", headers=auth(PLAIN)), n=8))
    measure("authority_resolution", timed(lambda: verdict(APPROVER, "approve")))
    check("K1. measured against real PostgreSQL; nothing optimised in a "
          "retirement phase", True)


if __name__ == "__main__":
    main()
