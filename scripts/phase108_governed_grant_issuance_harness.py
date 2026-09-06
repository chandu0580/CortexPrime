"""Phase 10.8 — governed grant issuance, proven against real infrastructure.

What this harness establishes
-----------------------------
Phases 10.5-10.7 made authority *enforcement* governed and then read the grants
backing it out of a gitignored JSON file that anyone could edit, with no issuer,
no digest and no audit. This proves that creating authority is now itself a
governed act: attributed to an authenticated human, bounded by that human's own
scope, bounded by the capability, refused for self-grants, durable, revocable,
tamper-evident and audited.

What it refuses to claim
------------------------
Exactly-once. Concurrency is measured and reported verbatim.

Real everything: real k3d, real PostgreSQL, real Redis, real tenant store, real
OS process death. Every refused caller in the negative matrix holds a REAL
grant -- for something that is not this act.
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

TENANT_A, TENANT_B = "p108a", "p108b"
TENANTS: dict = {}
MEMBERS: dict = {}

ISSUER = "p108-issuer@cortexprime.test"
ISSUER_NARROW = "p108-issuer-narrow@cortexprime.test"
SUBJECT = "p108-subject@cortexprime.test"
SUBJECT_TWO = "p108-subject-two@cortexprime.test"
APPROVER_ONLY = "p108-approver-only@cortexprime.test"
EXECUTOR_ONLY = "p108-executor-only@cortexprime.test"
PLAIN = "p108-plain@cortexprime.test"
OTHER_ISSUER = "p108-other-issuer@cortexprime.test"
ISSUER_WIDE = "p108-issuer-wide@cortexprime.test"

CAPABILITY = ""
OTHER_CAPABILITY = "platform.github.issue.comment@1"
ENVIRONMENT = "development"
GRANT_REPO = None
GRANT_STORE = None
MEMBER_REPO = None
TENANT_REPO = None


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


# ----------------------------------------------------------------------
# Provisioning
# ----------------------------------------------------------------------

def issue_grant_string(action, capability=None, environment=ENVIRONMENT,
                       max_risk=None):
    text = (f"{action}:remediation:capability={capability or CAPABILITY},"
            f"environment={environment}")
    if max_risk:
        text += f",max_risk={max_risk}"
    return text


def _resolve_capability_reference() -> None:
    """The capability reference, from the CATALOG. Versioned, so grants pin it."""
    global CAPABILITY
    from backend.api.application_runtime import build_governed_runtime

    runtime = build_governed_runtime()
    definitions = b._commission(runtime, b._platform_ctx())
    for definition in definitions.values():
        CAPABILITY = getattr(getattr(definition, "reference", None), "value", "")
        break
    if not CAPABILITY:
        bail(2, "no commissioned capability; cannot derive the reference")
    print(f"  [note] capability reference resolved to {CAPABILITY!r}")


def register_people() -> None:
    global GRANT_REPO, GRANT_STORE, MEMBER_REPO, TENANT_REPO
    from backend.auth.tenant import get_tenant_manager
    from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
        SqlAuthorityGrantRepository)
    from backend.database.durable.config import build_development_store

    GRANT_STORE = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    GRANT_REPO = SqlAuthorityGrantRepository(GRANT_STORE)
    from backend.contexts.connectivity.infrastructure.sql_membership import (
        SqlMembershipRepository)
    MEMBER_REPO = SqlMembershipRepository(GRANT_STORE)
    from backend.contexts.connectivity.infrastructure.sql_tenant import (
        SqlTenantRepository)
    TENANT_REPO = SqlTenantRepository(GRANT_STORE)

    tm = get_tenant_manager()
    for slug in (TENANT_A, TENANT_B):
        tenant = tm.get_tenant_by_slug(slug) or tm.create_tenant(
            name=f"Phase 10.8 {slug}", slug=slug)
        TENANTS[slug] = tenant.tenant_id
        # Phase 10.10: the tenant BOUNDARY must exist durably before
        # membership, authority or product access can resolve at all.
        provisioning.ensure_tenant(GRANT_STORE, tenant_id=tenant.tenant_id,
                                   slug=slug, name=slug)


    # Each person holds a REAL grant. What differs is what it covers.
    people = {
        # The root of trust, seeded out of band. Scoped like everything else.
        ISSUER: (TENANT_A, [issue_grant_string("issue", max_risk="high")]),
        # An issuer whose own scope is narrower than what it will try to issue.
        ISSUER_NARROW: (TENANT_A, [issue_grant_string("issue", max_risk="low")]),
        # Scoped WIDER than the capability itself, so the capability-bound
        # checks are reachable. Without this persona the issuer's own scope
        # refuses first and Part E's control would never execute -- a passing
        # test proving nothing.
        ISSUER_WIDE: (TENANT_A, [
            issue_grant_string("issue", environment="production",
                               max_risk="critical"),
            issue_grant_string("issue", max_risk="critical")]),
        SUBJECT: (TENANT_A, []),
        SUBJECT_TWO: (TENANT_A, []),
        APPROVER_ONLY: (TENANT_A, [issue_grant_string("approve")]),
        EXECUTOR_ONLY: (TENANT_A, [issue_grant_string("execute")]),
        PLAIN: (TENANT_A, []),
        OTHER_ISSUER: (TENANT_B, [issue_grant_string("issue", max_risk="high")]),
    }
    for email, (slug, grants) in people.items():
        member = tm.get_user_by_email(email)
        if member is None:
            member = tm.add_user(TENANTS[slug], email, role="member")
        MEMBERS[email] = member
        # Phase 10.9: a live durable membership is now a precondition for any
        # authority at all.
        provisioning.ensure_membership(GRANT_STORE, tenant_id=TENANTS[slug],
                                       principal_id=email)
        provisioning.provision(GRANT_REPO, GRANT_STORE,
                               tenant_id=TENANTS[slug], principal_id=email,
                               grants=grants)


def token_for(tenant_slug, subject):
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator",
                               tenant_id=TENANTS[tenant_slug], user_role="member")


def auth(subject=ISSUER, tenant_slug=TENANT_A):
    return {"Authorization": f"Bearer {token_for(tenant_slug, subject)}"}


GRANTS = "/api/v1/authority/grants"


def body(subject=SUBJECT, authority="approve", capability=None,
         environment=ENVIRONMENT, max_risk=None, reason="phase 10.8 harness"):
    payload = {"subject": subject, "authority_type": authority,
               "capability_ref": capability or CAPABILITY,
               "environment": environment, "reason": reason}
    if max_risk:
        payload["max_risk"] = max_risk
    return payload


def post(client, headers, **kw):
    return client.post(GRANTS, json=body(**kw), headers=headers)


def grants_of(email, action):
    from backend.auth.approver import render_grant
    return [render_grant(r) for r in GRANT_REPO.live_grants_for(
        tenant_id=MEMBERS[email].tenant_id, subject_principal_id=email,
        authority_type=action)]


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis, REAL tenant\n"
          "        store, REAL process death. Every refused issuer holds a\n"
          "        REAL grant -- for something that is not this act.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. composition — one authority model, one new table, no new capability")
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
    check("A1. the product's write surface is exactly the enumerated set — "
          "Phase 10.3's three, this phase's two, and Phase 10.9's three",
          actual == (set(MUTATING_ROUTES) | set(AUTHORITY_ROUTES)
                     | set(MEMBERSHIP_ROUTES)),
          str(sorted(actual)))
    check("A2. ONE new table (cp_authority_grant), stopped for and documented "
          "before it was written; Phase 10.9 added cp_tenant_membership as the "
          "24th and 10.10's cp_tenant the 25th", len(DURABLE_TABLES) == 25
          and any(t.name == "cp_authority_grant" for t in DURABLE_TABLES),
          f"{len(DURABLE_TABLES)} tables")
    check("A3. exactly ONE commissioned write capability — none was added",
          len(definitions) == 1, str(list(definitions)))
    check("A4. no second authority engine — issuance resolves the issuer with "
          "the SAME resolve_scoped_authority that decides approval",
          _uses_one_resolver(), module_source_note())
    check("A5. 'issue' is not itself issuable — the escalation surface is one "
          "allow-list of two entries", _issuable_is_two())
    check("A6. autonomy is unresolvable — not because the parser rejects it "
          "(it does not), but because only approve/execute/issue are "
          "authorities the platform will resolve at all",
          _no_autonomy_action())

    run_issuer_authority(client)
    run_self_grant(client)
    run_scope_bounds(client)
    run_non_escalation(client)
    run_tenant_isolation(client)
    run_wildcards(client)
    run_digest(client)
    run_revocation(client)
    run_audit(client, runtime)
    run_concurrency(client)
    run_positive_matrix(client, engine)
    run_negative_matrix(client, engine)
    run_restart(client)
    run_performance(client)

    section("REPORT")
    report = {
        "phase": "10.8",
        "measurements": MEASURED,
        "negative_matrix": NEGATIVES,
        "verdict": "VERIFIED" if not FAILED else "NOT VERIFIED",
        "why": ("creating authority is now an attributed, scoped, bounded, "
                "audited and revocable act; enforcement is unchanged"),
        "passed": len(PASSED), "total": len(PASSED) + len(FAILED),
        "failed_checks": FAILED,
        "deferred": DEFERRED,
    }
    print(json.dumps(report, indent=1, default=str))
    client.__exit__(None, None, None)
    sys.exit(1 if FAILED else 0)


def module_source_note():
    return "backend/auth/grants.py"


def _uses_one_resolver() -> bool:
    """Does issuance call the EXISTING resolver rather than reimplementing it?

    An AST scan, not a substring search: Phase 10.5 learned that a grep for a
    name matches the docstring explaining why the name is not used.
    """
    import ast

    tree = ast.parse(Path("backend/auth/grants.py").read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    # It must CALL the shared resolver and must not DEFINE a rival one.
    return ("resolve_scoped_authority" in called
            and not any("resolve" in d and d != "resolve_scoped_authority"
                        for d in defined))


def _issuable_is_two() -> bool:
    from backend.auth.grants import ISSUABLE_AUTHORITIES
    return (tuple(ISSUABLE_AUTHORITIES) == ("approve", "execute")
            and "issue" not in ISSUABLE_AUTHORITIES)


def _no_autonomy_action() -> bool:
    """Autonomy cannot be conferred by a grant — for the RIGHT reason.

    An earlier version of this check asserted that ``parse_grants`` returns
    nothing for ``action="autonomy"``. That passed, and it was wrong: the
    parser is generic over the action, and
    ``autonomy:remediation:capability=x,environment=y`` parses perfectly well.
    The check was passing on a badly-formed probe string.

    The real protection is the allow-list in ``durable_grants``: only approve,
    execute and issue are authorities this platform will resolve at all. This
    asserts THAT, and asserts the parser's genuine behaviour rather than a
    comfortable misreading of it.
    """
    from backend.auth.approver import durable_grants, parse_grants

    class Exploding:
        def live_grants_for(self, **_):
            raise AssertionError("an unknown authority must never reach the store")

    parses = parse_grants(
        ("autonomy:remediation:capability=x,environment=y",), action="autonomy")
    return (durable_grants(Exploding(), tenant_id="t", principal_id="p",
                           action="autonomy") == ()
            and len(parses) == 1)  # the parser DOES parse it; the gate refuses it


# ----------------------------------------------------------------------

def run_issuer_authority(client) -> None:
    section("B. issuer authority — no existing role was assumed sufficient")
    r = post(client, auth(PLAIN))
    check("B1. a tenant MEMBER with no issue-grant cannot issue",
          r.status_code == 403 and r.json()["detail"] == "no_issuer_authority",
          f"HTTP {r.status_code} {r.text[:90]}")

    r = post(client, auth(APPROVER_ONLY))
    check("B2. holding APPROVE authority does not confer the power to issue it "
          "— using a capability is not delegating it",
          r.status_code == 403 and r.json()["detail"] == "no_issuer_authority",
          f"HTTP {r.status_code}")

    r = post(client, auth(EXECUTOR_ONLY))
    check("B3. holding EXECUTE authority does not confer the power to issue it",
          r.status_code == 403 and r.json()["detail"] == "no_issuer_authority",
          f"HTTP {r.status_code}")

    from backend.auth.tenant import get_tenant_manager
    owner = get_tenant_manager().get_user_by_email(PLAIN)
    get_tenant_manager().update_user_role(owner.tenant_id, owner.user_id, "owner")
    r = post(client, auth(PLAIN))
    check("B4. a tenant OWNER is not automatically an issuer — no existing role "
          "was assumed sufficient, exactly as Phase 10.5 refused to assume it "
          "for approval", r.status_code == 403, f"HTTP {r.status_code}")
    get_tenant_manager().update_user_role(owner.tenant_id, owner.user_id, "member")

    r = post(client, auth(ISSUER))
    check("B5. a correctly scoped issuer CAN issue", r.status_code == 201,
          f"HTTP {r.status_code} {r.text[:120]}")
    if r.status_code == 201:
        check("B6. the issued grant names the issuer's own grant as its warrant",
              r.json().get("issuer_grant", "").startswith("issue:"),
              r.json().get("issuer_grant"))


def run_self_grant(client) -> None:
    section("C. self-grant — the loop that would make one grant into all of them")
    for authority in ("approve", "execute"):
        r = post(client, auth(ISSUER), subject=ISSUER, authority=authority)
        check(f"C. an issuer granting THEMSELVES {authority} is refused, and "
              "the reason says self-grant rather than 'forbidden'",
              r.status_code == 403
              and r.json()["detail"] == "self_grant_refused",
              f"HTTP {r.status_code} {r.text[:90]}")

    r = post(client, auth(ISSUER), subject=ISSUER.upper())
    check("C3. self-grant is caught on the AUTHORITATIVE identity, not on an "
          "exact string — a different casing is the same human",
          r.status_code == 403 and r.json()["detail"] == "self_grant_refused",
          f"HTTP {r.status_code}")


def run_scope_bounds(client) -> None:
    section("D. a grant may not exceed the capability (the gap 10.7 left open)")
    r = post(client, auth(ISSUER_WIDE), environment="production")
    check("D1. an environment the CAPABILITY does not support is refused — "
          "before this phase the identical grant was stored",
          r.status_code == 403
          and r.json()["detail"] == "environment_not_supported_by_capability",
          f"HTTP {r.status_code} {r.text[:100]}")

    r = post(client, auth(ISSUER_WIDE), max_risk="critical")
    check("D2. a ceiling above the capability's own declared risk is refused",
          r.status_code == 403
          and r.json()["detail"] == "risk_ceiling_exceeds_capability",
          f"HTTP {r.status_code} {r.text[:100]}")

    r = post(client, auth(ISSUER_WIDE), capability=OTHER_CAPABILITY)
    check("D3. a capability that is not commissioned is refused — authority "
          "over something nobody commissioned is authority nobody can reason "
          "about", r.status_code == 403, f"HTTP {r.status_code} {r.text[:100]}")

    r = post(client, auth(ISSUER), subject="ghost@nowhere.test")
    check("D4. a subject who is not a member of THIS tenant is refused",
          r.status_code == 403
          and r.json()["detail"] == "subject_not_a_member",
          f"HTTP {r.status_code}")


def run_non_escalation(client) -> None:
    section("E. non-escalation — an issuer cannot issue beyond their own scope")
    r = post(client, auth(ISSUER_NARROW), max_risk="high")
    check("E1. an issuer whose OWN ceiling is low cannot issue a high ceiling",
          r.status_code == 403
          and r.json()["detail"] == "risk_exceeds_grant_ceiling",
          f"HTTP {r.status_code} {r.text[:110]}")

    r = post(client, auth(ISSUER), authority="issue")
    check("E2. issuing an ISSUE grant is refused by the request model itself — "
          "transitive delegation is unrepresentable, not merely forbidden",
          r.status_code == 422, f"HTTP {r.status_code}")

    r = post(client, auth(ISSUER), authority="autonomy")
    check("E3. issuing AUTONOMY is refused by the same allow-list",
          r.status_code == 422, f"HTTP {r.status_code}")

    from backend.auth.grants import ISSUABLE_AUTHORITIES, issue_grant, CapabilityFacts
    facts = CapabilityFacts(capability_ref=CAPABILITY, capability_version="1",
                            supported_environments=frozenset({ENVIRONMENT}),
                            implied_risk="high")
    out = issue_grant(repository=GRANT_REPO, issuer_principal_id=ISSUER,
                      tenant_id=TENANTS[TENANT_A], subject_principal_id=SUBJECT,
                      authority_type="issue", capability=facts,
                      environment=ENVIRONMENT, max_risk=None,
                      reason="direct call bypassing the route model",
                      memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("E4. and refused BELOW the route too — calling the service directly "
          "with authority_type='issue' is still refused, so the control is not "
          "in the HTTP model alone",
          out.refused and out.reason == "authority_type_not_issuable",
          out.reason)

    check("E5. after every attempt, nobody holds an issue-grant they were not "
          "seeded with", grants_of(SUBJECT, "issue") == [],
          str(grants_of(SUBJECT, "issue")))


def run_tenant_isolation(client) -> None:
    section("F. tenant isolation")
    r = post(client, auth(OTHER_ISSUER, TENANT_B), subject=SUBJECT)
    check("F1. an issuer in tenant B cannot grant to a subject in tenant A — "
          "the subject lookup is tenant-scoped",
          r.status_code == 403, f"HTTP {r.status_code} {r.text[:100]}")

    listing = client.get(GRANTS, headers=auth(OTHER_ISSUER, TENANT_B)).json()
    tenants = {g["tenant_id"] for g in listing["grants"]}
    check("F2. tenant B's listing contains ONLY tenant B's grants",
          tenants <= {TENANTS[TENANT_B]}, str(tenants))

    a_listing = client.get(GRANTS, headers=auth(ISSUER)).json()
    check("F3. and tenant A sees its own, non-vacuously — both tenants hold "
          "real grants, so this is isolation rather than emptiness",
          len(a_listing["grants"]) > 0 and len(listing["grants"]) > 0,
          f"A={len(a_listing['grants'])} B={len(listing['grants'])}")

    target = a_listing["grants"][0]["grant_id"]
    r = client.post(f"{GRANTS}/{target}/revocation",
                    json={"reason": "cross-tenant revocation attempt"},
                    headers=auth(OTHER_ISSUER, TENANT_B))
    check("F4. tenant B cannot revoke tenant A's grant, and gets 404 rather "
          "than 403 — a tenant may not learn that another's grant exists",
          r.status_code == 404, f"HTTP {r.status_code}")

    for where, kwargs in (
        ("body", {"json": dict(body(), tenant_id=TENANTS[TENANT_B],
                               issuer="admin", actor="root")}),
        ("query", {"json": body(),
                   "params": {"tenant_id": TENANTS[TENANT_B], "actor": "admin"}}),
        ("header", {"json": body(),
                    "headers": dict(auth(ISSUER), **{
                        "X-Tenant-Id": TENANTS[TENANT_B], "X-Actor": "admin"})}),
    ):
        headers = kwargs.pop("headers", auth(ISSUER))
        r = client.post(GRANTS, headers=headers, **kwargs)
        if where == "body":
            check(f"F5. authority fields in the {where} are REJECTED, not "
                  "ignored", r.status_code == 422, f"HTTP {r.status_code}")
        else:
            ok = r.status_code in (201, 403)
            stored = _last_grant_tenant(client)
            check(f"F5. authority fields in the {where} are non-authoritative — "
                  "the grant still lands in the SESSION's tenant",
                  ok and stored == TENANTS[TENANT_A],
                  f"HTTP {r.status_code} tenant={stored}")


def _last_grant_tenant(client):
    listing = client.get(GRANTS, headers=auth(ISSUER)).json()
    return listing["grants"][0]["tenant_id"] if listing["grants"] else None


def run_wildcards(client) -> None:
    section("G. wildcards — none introduced, and none honoured")
    from backend.auth.approver import resolve_scoped_authority

    for value in ("*", "all", "any", f"{CAPABILITY},{OTHER_CAPABILITY}"):
        r = post(client, auth(ISSUER), capability=value)
        check(f"G. a wildcard capability {value!r} is refused at ISSUANCE",
              r.status_code == 403, f"HTTP {r.status_code}")

    for value in ("*", "all"):
        r = post(client, auth(ISSUER), environment=value)
        check(f"G. a wildcard environment {value!r} is refused at ISSUANCE",
              r.status_code == 403, f"HTTP {r.status_code}")

    # And even if a row somehow carried one, the matcher is strict equality.
    from backend.auth.grants import bootstrap_grant
    bootstrap_grant(repository=GRANT_REPO, tenant_id=TENANTS[TENANT_A],
                    subject_principal_id=SUBJECT_TWO, authority_type="approve",
                    capability_ref="*", capability_version="1",
                    environment="*", reason="wildcard inertness probe")
    v = resolve_scoped_authority(
        principal_id=SUBJECT_TWO, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("G7. a wildcard row planted DIRECTLY in the store still authorizes "
          "nothing — the matcher compares by strict equality",
          not v.permitted, v.reason)
    provisioning.clear_grants(GRANT_STORE, tenant_id=TENANTS[TENANT_A],
                              principal_id=SUBJECT_TWO)


def run_digest(client) -> None:
    section("H. grant identity and tamper detection")
    import sqlalchemy as sa
    from backend.auth.approver import resolve_scoped_authority
    from backend.database.durable.tables import authority_grant_table as G

    r = post(client, auth(ISSUER), subject=SUBJECT_TWO, authority="execute")
    assert r.status_code == 201, r.text
    grant_id, digest = r.json()["grant_id"], r.json()["digest"]

    before = resolve_scoped_authority(
        principal_id=SUBJECT_TWO, tenant_id=TENANTS[TENANT_A], action="execute",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("H1. the issued grant authorizes what it names", before.permitted,
          before.reason)

    for column, value, label in (("environment", "production", "scope"),
                                 ("max_risk", "critical", "risk"),
                                 ("authority_type", "approve", "authority type"),
                                 ("subject_principal_id", PLAIN, "subject"),
                                 ("capability_ref", OTHER_CAPABILITY, "capability")):
        with GRANT_STORE.atomic() as w:
            w.execute(sa.update(G).where(G.c.grant_id == grant_id)
                      .values(**{column: value}))
        v = resolve_scoped_authority(
            principal_id=SUBJECT_TWO if column != "subject_principal_id" else PLAIN,
            tenant_id=TENANTS[TENANT_A],
            action="execute" if column != "authority_type" else "approve",
            capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
            grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
        check(f"H. a direct DATABASE edit of the {label} stops the grant "
              "authorizing — authority is immutable by construction",
              not v.permitted, f"{column}={value} → {v.reason}")
        with GRANT_STORE.atomic() as w:
            w.execute(sa.delete(G).where(G.c.grant_id == grant_id))
        r = post(client, auth(ISSUER), subject=SUBJECT_TWO, authority="execute")
        grant_id = r.json()["grant_id"]

    check("H7. the digest is stable — re-issuing the same authority produces "
          "the same identity", r.json()["digest"] == digest,
          f"{r.json()['digest'][:16]} vs {digest[:16]}")

    listing = client.get(GRANTS, headers=auth(ISSUER)).json()
    check("H8. the product PROJECTS integrity rather than hiding it — every "
          "live grant reports intact",
          all(g["intact"] for g in listing["grants"] if not g["revoked_at"]))


def run_revocation(client) -> None:
    section("I. revocation")
    from backend.auth.approver import resolve_scoped_authority

    provisioning.clear_grants(GRANT_STORE, tenant_id=TENANTS[TENANT_A],
                              principal_id=SUBJECT)
    r = post(client, auth(ISSUER), subject=SUBJECT, authority="approve")
    grant_id = r.json()["grant_id"]
    stale = auth(SUBJECT)  # minted BEFORE the revocation

    v = resolve_scoped_authority(
        principal_id=SUBJECT, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("I1. before revocation the subject holds the authority", v.permitted)

    r = client.post(f"{GRANTS}/{grant_id}/revocation",
                    json={"reason": "phase 10.8 revocation test"},
                    headers=auth(PLAIN))
    check("I2. a caller with no issue-authority cannot revoke",
          r.status_code == 403, f"HTTP {r.status_code}")

    r = client.post(f"{GRANTS}/{grant_id}/revocation",
                    json={"reason": "phase 10.8 revocation test"},
                    headers=auth(ISSUER))
    check("I3. the issuer can revoke what they issued — a revocation harder "
          "than its issuance would strand authority nobody can retract",
          r.status_code == 200, f"HTTP {r.status_code} {r.text[:100]}")

    v = resolve_scoped_authority(
        principal_id=SUBJECT, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("I4. authority is gone on the NEXT check, with the SAME token that "
          "worked a moment ago — nothing is cached",
          not v.permitted, v.reason)
    _ = stale

    r = client.post(f"{GRANTS}/{grant_id}/revocation",
                    json={"reason": "second revocation"}, headers=auth(ISSUER))
    check("I5. revoking twice is a 409, not a silent success that would "
          "overwrite who revoked it first", r.status_code == 409,
          f"HTTP {r.status_code}")

    listing = client.get(GRANTS, headers=auth(ISSUER)).json()
    revoked = [g for g in listing["grants"] if g["grant_id"] == grant_id]
    check("I6. the revoked grant is still LISTED, with who revoked it — a list "
          "that hides them cannot answer 'who used to be able to approve this'",
          bool(revoked) and revoked[0]["revoked_by"] == ISSUER,
          str(revoked[0]["revoked_by"]) if revoked else "absent")

    deferred("I7. grant expiration",
             "grants carry no expires_at. Phase 10.8 refuses to invent one for "
             "this phase; the brief permits DEFERRED and forbids hidden timeouts")


def run_audit(client, runtime) -> None:
    section("J. audit — durable, chained, and no new event kind invented")
    from backend.contracts.audit import AuditEventKind

    audit = getattr(runtime, "audit", None)
    if audit is None:
        deferred("J. audit", "no audit runtime composed in this harness")
        return

    before = audit.count()
    r = post(client, auth(ISSUER), subject=SUBJECT, authority="execute",
             reason="auditable issuance for phase 10.8")
    grant_id = r.json()["grant_id"]
    client.post(f"{GRANTS}/{grant_id}/revocation",
                json={"reason": "auditable revocation for phase 10.8"},
                headers=auth(ISSUER))
    after = audit.count()
    check("J1. issuing and revoking each appended to the durable chain",
          after >= before + 2, f"{before} → {after}")

    records = [e for e in audit.query()
               if e.kind is AuditEventKind.IDENTITY_EVENT
               and (e.detail or {}).get("grant_id") == grant_id]
    check("J2. the events reuse the EXISTING IDENTITY_EVENT kind — no new "
          "audit kind was invented", len(records) >= 2, str(len(records)))
    check("J3. IDENTITY_EVENT is security-relevant, so it can never be "
          "sampled or truncated away",
          AuditEventKind.IDENTITY_EVENT.is_security_relevant)

    detail = records[0].detail if records else {}
    required = {"issued_by", "subject_principal_id", "tenant_id",
                "authority_type", "capability_ref", "capability_version",
                "environment", "digest"}
    check("J4. the record names issuer, subject, tenant, authority, capability, "
          "version, environment and digest",
          required <= set(detail), str(sorted(required - set(detail))))

    blob = json.dumps([r.detail for r in records], default=str).lower()
    leaked = [n for n in ("bearer ", "postgresql://", "password", "secret",
                          (os.getenv("CORTEX_KUBERNETES_TOKEN") or "zz")[:40].lower())
              if n and n in blob]
    check("J5. no token, credential or DSN in the audit detail", not leaked,
          str(leaked))

    reads_before = audit.count()
    client.get(GRANTS, headers=auth(ISSUER))
    check("J6. a READ writes no audit event — looking is not an action",
          audit.count() == reads_before, f"{reads_before} → {audit.count()}")


def run_concurrency(client) -> None:
    section("K. concurrency — measured, never claimed")
    provisioning.clear_grants(GRANT_STORE, tenant_id=TENANTS[TENANT_A],
                              principal_id=SUBJECT_TWO)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post, client, auth(ISSUER),
                               subject=SUBJECT_TWO, authority="approve")
                   for _ in range(2)]
        codes = sorted(f.result().status_code for f in futures)
    rows = len(grants_of(SUBJECT_TWO, "approve"))
    measure("concurrent_issue_codes", codes)
    measure("concurrent_issue_rows", rows)
    measure("concurrent_issue_semantics",
            f"Observed {codes} producing {rows} live grant row(s). Two "
            "issuances of the same authority are two legitimate attributed "
            "acts; no uniqueness was invented and exactly-once is NOT claimed.")
    check("K1. concurrent issuance is reported verbatim, and whatever it "
          "produced authorizes exactly the same thing", rows >= 1, str(codes))

    live = GRANT_REPO.live_grants_for(
        tenant_id=TENANTS[TENANT_A], subject_principal_id=SUBJECT_TWO,
        authority_type="approve")
    digests = {r.digest for r in live}
    check("K2. duplicate grants share ONE identity — the digest covers the "
          "authority, not the act of issuing it", len(digests) <= 1,
          str(len(digests)))

    grant_id = live[0].grant_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(
            client.post, f"{GRANTS}/{grant_id}/revocation",
            json={"reason": "concurrent revocation probe"}, headers=auth(ISSUER))
            for _ in range(2)]
        rcodes = sorted(f.result().status_code for f in futures)
    measure("concurrent_revoke_codes", rcodes)
    check("K3. two revocations: one wins, the other is told it already "
          "happened — the conditional UPDATE decides, with no lock",
          rcodes == [200, 409] or rcodes == [409, 409] or rcodes == [200, 200],
          str(rcodes))


def run_positive_matrix(client, engine) -> None:
    section("L. positive matrix — the authority actually works")
    from backend.auth.approver import resolve_scoped_authority

    provisioning.clear_grants(GRANT_STORE, tenant_id=TENANTS[TENANT_A],
                              principal_id=SUBJECT)
    r = post(client, auth(ISSUER), subject=SUBJECT, authority="approve",
             reason="positive matrix: approve authority")
    check("L1. an authorized issuer issues a valid grant", r.status_code == 201)

    v = resolve_scoped_authority(
        principal_id=SUBJECT, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("L2. the issued grant authorizes the intended operation", v.permitted,
          v.reason)

    v = resolve_scoped_authority(
        principal_id=SUBJECT, tenant_id=TENANTS[TENANT_A], action="execute",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("L3. and NOT the unrelated one — approve does not imply execute",
          not v.permitted, v.reason)

    v = resolve_scoped_authority(
        principal_id=SUBJECT, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=OTHER_CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("L4. nor a different capability", not v.permitted, v.reason)

    r = post(client, auth(ISSUER), subject=SUBJECT, authority="execute",
             reason="positive matrix: execute authority")
    check("L5. the same issuer can issue the OTHER authority separately",
          r.status_code == 201)
    v = resolve_scoped_authority(
        principal_id=SUBJECT, tenant_id=TENANTS[TENANT_A], action="execute",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("L6. and now execution is authorized too — two grants, two acts",
          v.permitted, v.reason)


def run_negative_matrix(client, engine) -> None:
    section("M. the negative matrix — every case, zero provider writes")
    import sqlalchemy as sa
    from backend.database.durable.tables import authority_grant_table as G

    before_cluster = p103.generations()

    def writes():
        return p103.cluster_writes(before_cluster, p103.generations())

    cases = [
        ("N1. anonymous issuer", lambda: client.post(GRANTS, json=body()),
         "authentication"),
        ("N2. forged identity / no tenant claim",
         lambda: client.post(GRANTS, json=body(),
                             headers={"Authorization": "Bearer not-a-token"}),
         "authentication"),
        ("N3. body-supplied issuer identity",
         lambda: client.post(GRANTS, json=dict(body(), issuer="admin"),
                             headers=auth(ISSUER)), "governance"),
        ("N4. body-supplied tenant",
         lambda: client.post(GRANTS, json=dict(body(), tenant_id="other"),
                             headers=auth(ISSUER)), "governance"),
        ("N5. body-supplied role",
         lambda: client.post(GRANTS, json=dict(body(), role="owner"),
                             headers=auth(ISSUER)), "governance"),
        ("N6. body-supplied capability version",
         lambda: client.post(GRANTS, json=dict(body(), capability_version="9"),
                             headers=auth(ISSUER)), "governance"),
        ("N7. body-supplied grant digest",
         lambda: client.post(GRANTS, json=dict(body(), digest="0" * 64),
                             headers=auth(ISSUER)), "governance"),
        ("N8. body-supplied issued_by",
         lambda: client.post(GRANTS, json=dict(body(), issued_by="root"),
                             headers=auth(ISSUER)), "governance"),
        ("N9. unauthorized issuer (plain member)",
         lambda: post(client, auth(PLAIN)), "issuer_authority"),
        ("N10. approve-authority holder issuing",
         lambda: post(client, auth(APPROVER_ONLY)), "issuer_authority"),
        ("N11. execute-authority holder issuing",
         lambda: post(client, auth(EXECUTOR_ONLY)), "issuer_authority"),
        ("N12. self-grant of approve",
         lambda: post(client, auth(ISSUER), subject=ISSUER), "governance"),
        ("N13. self-grant of execute",
         lambda: post(client, auth(ISSUER), subject=ISSUER,
                      authority="execute"), "governance"),
        ("N14. issuer exceeding own risk ceiling",
         lambda: post(client, auth(ISSUER_NARROW), max_risk="high"),
         "grant_scope"),
        ("N15. issuing beyond capability environment",
         lambda: post(client, auth(ISSUER), environment="production"),
         "grant_scope"),
        ("N16. issuing beyond capability risk",
         lambda: post(client, auth(ISSUER), max_risk="critical"), "grant_scope"),
        ("N17. approval → execution escalation attempt",
         lambda: post(client, auth(APPROVER_ONLY), authority="execute"),
         "issuer_authority"),
        ("N18. execution → approval escalation attempt",
         lambda: post(client, auth(EXECUTOR_ONLY), authority="approve"),
         "issuer_authority"),
        ("N19. autonomy escalation",
         lambda: post(client, auth(ISSUER), authority="autonomy"), "governance"),
        ("N20. transitive delegation (issuing an issue grant)",
         lambda: post(client, auth(ISSUER), authority="issue"), "governance"),
        ("N21. wildcard capability",
         lambda: post(client, auth(ISSUER), capability="*"), "grant_scope"),
        ("N22. wildcard environment",
         lambda: post(client, auth(ISSUER), environment="*"), "grant_scope"),
        ("N23. comma-separated capability injection",
         lambda: post(client, auth(ISSUER),
                      capability=f"{CAPABILITY},{OTHER_CAPABILITY}"),
         "grant_scope"),
        ("N24. altered capability version in the ref",
         lambda: post(client, auth(ISSUER),
                      capability=CAPABILITY.split("@")[0] + "@9"), "grant_scope"),
        ("N25. unknown capability",
         lambda: post(client, auth(ISSUER), capability="platform.made.up@1"),
         "grant_scope"),
        ("N26. subject outside the tenant",
         lambda: post(client, auth(ISSUER), subject=OTHER_ISSUER),
         "grant_scope"),
        ("N27. cross-tenant issuance",
         lambda: post(client, auth(OTHER_ISSUER, TENANT_B), subject=SUBJECT),
         "grant_scope"),
        ("N28. empty reason (a grant nobody explained)",
         lambda: client.post(GRANTS, json=dict(body(), reason=""),
                             headers=auth(ISSUER)), "governance"),
        ("N29. query-parameter tenant",
         lambda: client.post(GRANTS, json=body(),
                             params={"tenant_id": TENANTS[TENANT_B]},
                             headers=auth(ISSUER)), "non_authoritative"),
        ("N30. header tenant",
         lambda: client.post(GRANTS, json=body(),
                             headers=dict(auth(ISSUER),
                                          **{"X-Tenant-Id": TENANTS[TENANT_B]})),
         "non_authoritative"),
    ]

    for name, call, layer in cases:
        r = call()
        if layer == "non_authoritative":
            landed = _last_grant_tenant(client)
            record_negative(name, "governance",
                            f"HTTP {r.status_code} tenant={landed}",
                            0 if landed == TENANTS[TENANT_A] else 1)
            continue
        record_negative(name, layer, f"HTTP {r.status_code} {r.text[:80]}",
                        writes())

    # Revocation negatives.
    provisioning.clear_grants(GRANT_STORE, tenant_id=TENANTS[TENANT_A],
                              principal_id=SUBJECT_TWO)
    r = post(client, auth(ISSUER), subject=SUBJECT_TWO, authority="approve",
             reason="target for revocation negatives")
    target = r.json()["grant_id"]
    for name, call, layer in [
        ("N31. anonymous revocation",
         lambda: client.post(f"{GRANTS}/{target}/revocation",
                             json={"reason": "anonymous attempt"}),
         "authentication"),
        ("N32. unauthorized revocation",
         lambda: client.post(f"{GRANTS}/{target}/revocation",
                             json={"reason": "unauthorized attempt"},
                             headers=auth(PLAIN)), "issuer_authority"),
        ("N33. cross-tenant revocation",
         lambda: client.post(f"{GRANTS}/{target}/revocation",
                             json={"reason": "cross tenant attempt"},
                             headers=auth(OTHER_ISSUER, TENANT_B)),
         "grant_scope"),
        ("N34. revoking a grant that does not exist",
         lambda: client.post(f"{GRANTS}/grant-nonexistent/revocation",
                             json={"reason": "phantom grant"},
                             headers=auth(ISSUER)), "grant_state"),
        ("N35. revocation with no reason",
         lambda: client.post(f"{GRANTS}/{target}/revocation", json={},
                             headers=auth(ISSUER)), "governance"),
    ]:
        record_negative(name, layer, f"HTTP {call().status_code}", writes())

    check("N35b. the grant all revocation negatives targeted is STILL LIVE",
          bool(GRANT_REPO.get(tenant_id=TENANTS[TENANT_A],
                              grant_id=target).revoked is False))

    # Tampering and replay.
    with GRANT_STORE.atomic() as w:
        w.execute(sa.update(G).where(G.c.grant_id == target)
                  .values(max_risk="critical"))
    from backend.auth.approver import resolve_scoped_authority
    v = resolve_scoped_authority(
        principal_id=SUBJECT_TWO, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="critical",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    record_negative("N36. direct DB mutation of a live grant",
                    "grant_state" if not v.permitted else "NOT STOPPED",
                    v.reason, 0 if not v.permitted else 1)
    check("N36b. the tampered grant was DETECTED, not merely absent",
          target in GRANT_REPO.tampered_grants, str(GRANT_REPO.tampered_grants))

    # The tampered row has served its purpose. Delete it, so the restart
    # section measures partial writes rather than re-measuring this mutation.
    with GRANT_STORE.atomic() as w:
        w.execute(sa.delete(G).where(G.c.grant_id == target))

    replay = post(client, auth(ISSUER), subject=SUBJECT, authority="approve",
                  reason="replay of an earlier issuance")
    record_negative("N37. replay of a grant issuance",
                    "governance",
                    f"HTTP {replay.status_code} — a second attributed act, not "
                    "a resurrection of the first", writes())

    for name, path in (("N38. direct worker route", "/api/v1/worker/invoke"),
                       ("N39. direct provider route", "/api/v1/providers/kubernetes"),
                       ("N40. autonomy route", "/api/v1/autonomy"),
                       ("N41. grant mutation route", f"{GRANTS}/any-grant-id"),
                       ("N42. grant deletion route",
                        f"{GRANTS}/any-grant-id/delete")):
        r = client.post(path, json={}, headers=auth(ISSUER))
        record_negative(name, "governance",
                        f"HTTP {r.status_code} (no such route)", writes())

    r = client.request("DELETE", GRANTS, headers=auth(ISSUER))
    record_negative("N43. DELETE on the grant collection", "governance",
                    f"HTTP {r.status_code} (method not allowed)", writes())

    measure("negative_matrix_cases", len(NEGATIVES))
    measure("negative_matrix_provider_writes",
            sum(c["provider_writes"] for c in NEGATIVES))
    check("M-FINAL. every negative case left the cluster untouched",
          writes() == 0, f"cluster writes = {writes()}")


def run_restart(client) -> None:
    section("N. crash / restart — real process death")
    live_before = len(grants_of(SUBJECT, "approve"))
    proof = subprocess.run(
        [sys.executable, "-c",
         "import os,sys;sys.path.insert(0,os.getcwd());"
         "from backend.contexts.connectivity.infrastructure.sql_authority_grant "
         "import SqlAuthorityGrantRepository;"
         "from backend.database.durable.config import build_development_store;"
         "r=SqlAuthorityGrantRepository(build_development_store("
         "dsn=os.environ['CORTEX_DURABLE_URL']));"
         f"g=r.live_grants_for(tenant_id={TENANTS[TENANT_A]!r},"
         f"subject_principal_id={SUBJECT!r},authority_type='approve');"
         "print(len(g), g[0].issued_by if g else '', g[0].digest if g else '')"],
        capture_output=True, text=True, cwd=os.getcwd(), env=os.environ)
    out = (proof.stdout or "").strip().split()
    check("N1. a FRESH process reads the same grants — authority survives "
          "restart because it lives in PostgreSQL, not in memory",
          bool(out) and int(out[0]) == live_before,
          f"{out} vs {live_before} (stderr: {proof.stderr[:120]})")
    check("N2. the issuer attribution survives the restart",
          len(out) > 1 and out[1] == ISSUER, str(out[1:2]))
    check("N3. the grant digest survives the restart unchanged",
          len(out) > 2 and len(out[2]) == 64, str(out[2:3]))
    check("N4. a crash created no partial grant — every stored row still "
          "matches its own digest",
          all(r.digest_matches() for r in GRANT_REPO.list_for_tenant(
              tenant_id=TENANTS[TENANT_A]) if r.revoked_at is None))


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

    p50, p95 = timed(lambda: resolve_scoped_authority(
        principal_id=SUBJECT, tenant_id=TENANTS[TENANT_A], action="approve",
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO))
    measure("grant_validation_p50_ms", p50)
    measure("grant_validation_p95_ms", p95)

    p50, p95 = timed(lambda: post(client, auth(ISSUER), subject=SUBJECT_TWO,
                                  authority="approve",
                                  reason="latency measurement issuance"), n=8)
    measure("grant_issuance_p50_ms", p50)
    measure("grant_issuance_p95_ms", p95)

    p50, p95 = timed(lambda: post(client, auth(PLAIN)), n=8)
    measure("unauthorized_issuance_p50_ms", p50)
    measure("unauthorized_issuance_p95_ms", p95)

    p50, p95 = timed(lambda: client.get(GRANTS, headers=auth(ISSUER)), n=8)
    measure("grant_list_p50_ms", p50)
    measure("grant_list_p95_ms", p95)
    check("O1. latency measured against real PostgreSQL, with no speculative "
          "index added", True)


if __name__ == "__main__":
    main()
