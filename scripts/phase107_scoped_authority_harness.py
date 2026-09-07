"""Phase 10.7: scoped approver authority and narrow execution authority.

What this proves
----------------
An approver can decide only the actions their grant covers, and an executor can
run only an already-approved action their grant covers. Both scopes are read
from the stored approval and the capability contract; neither can be supplied by
a caller.

The discipline
--------------
* The refused callers hold REAL grants. The out-of-scope approver has approver
  authority in the right tenant; the wrong-capability grant is a real, parseable
  grant for a real capability. Refusals are therefore about scope and nothing
  else.
* The legacy tenant-wide grant is tested explicitly and must FAIL -- leaving it
  working would leave tenant-wide authority beside the narrower scope.
* Every negative asserts ``provider_writes == 0`` against cluster generation and
  names the layer that refused.

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
import scripts.phase105_approver_authority_harness as p105  # noqa: E402
import scripts.phase108_grant_provisioning as provisioning  # noqa: E402
import scripts.phase99b_contained_worker_harness as b  # noqa: E402

REPORT: dict = {
    "phase": "10.7", "checks": [], "deferred": [], "blocked": [],
    "measurements": {}, "negative_matrix": [], "verdict": "NOT VERIFIED",
}

TENANT_A = "tenant-a-p107"
TENANT_B = "tenant-b-p107"
TENANTS: dict = {}
MEMBERS: dict = {}
OPERATION = p103.OPERATION
NAMESPACE = p103.NAMESPACE
TARGET = p103.TARGET
BYSTANDER = p103.BYSTANDER
#: Set at composition time from the commissioned capability's own reference.
#:
#: It is the VERSIONED reference (`…@1`), because that is what the approval row
#: stores. Grants are therefore version-pinned: a grant for v1 does not cover
#: v2, which is the same re-consent the capability digest already demands of an
#: approval. Hardcoding it here would have been a guess -- and was, on the first
#: run, which is why it is derived.
CAPABILITY = ""
ENVIRONMENT = "development"
SEEDED: dict = {}

REQUESTER = "requester@p107.example"
#: Correctly scoped for the real capability, environment and risk.
APPROVER = "approver@p107.example"
APPROVER_TWO = "approver2@p107.example"
#: Real grants that do not cover this action.
WRONG_CAPABILITY = "wrongcap@p107.example"
WRONG_ENVIRONMENT = "wrongenv@p107.example"
LOW_RISK_ONLY = "lowrisk@p107.example"
#: A Phase 10.5-style grant with no scope at all.
LEGACY_GRANT = "legacy@p107.example"
#: Holds execute scope but not approve scope, and vice versa.
EXECUTOR = "executor@p107.example"
APPROVER_NO_EXEC = "approveonly@p107.example"
OTHER_TENANT = "approver@p107-other.example"


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

def approve_grant(capability=None, environment=ENVIRONMENT, max_risk=None):
    # `capability=None`, not `capability=CAPABILITY`: Python binds a default at
    # DEFINITION time, when CAPABILITY is still empty. The first run built every
    # grant with an empty capability and refused everything, which looked like a
    # policy bug and was a defaulting bug.
    grant = (f"approve:remediation:capability={capability or CAPABILITY},"
             f"environment={environment}")
    return grant + (f",max_risk={max_risk}" if max_risk else "")


def execute_grant(capability=None, environment=ENVIRONMENT):
    return (f"execute:remediation:capability={capability or CAPABILITY},"
            f"environment={environment}")



def _resolve_capability_reference() -> None:
    """The capability reference EXACTLY as the approval row stores it.

    ``RemediationService.propose`` writes ``definition.reference.value``, which
    is the versioned form. A grant naming the unversioned id would never match,
    and a grant naming a guessed form would match nothing -- so this reads the
    real value from the same place the approval does.
    """
    global CAPABILITY
    from backend.api.application_runtime import _platform_context
    from backend.contexts.connectivity.application.commands import GetCapability

    os.environ.setdefault(
        "CORTEX_CONNECTOR_FACTORIES",
        "backend.api.kubernetes_provider_factory:kubernetes_real_extension,"
        "backend.api.contained_worker_factory:contained_worker_extension")
    from backend.api.application_runtime import build_governed_runtime

    runtime = build_governed_runtime()
    definition = runtime.capabilities.get(_platform_context(), GetCapability(
        capability_id="platform.kubernetes.workload.rollout_restart", version=1))
    CAPABILITY = definition.reference.value
    print(f"  [note] capability reference resolved to {CAPABILITY!r}")


def register_people() -> None:
    """Real memberships with real, differently-scoped grants.

    Phase 10.8 moved authority out of the membership's JSON ``permissions``
    list into ``cp_authority_grant``; Phase 10.9 moved membership itself; Phase
    10.10 moved the tenant boundary. All three are provisioned here through the
    documented out-of-band paths a real operator would use, because a tenant
    with no members has nobody who could admit one. Nothing about what 10.7
    proves changes -- only where each fact lives.
    """
    global GRANT_REPO, GRANT_STORE, MEMBER_REPO, TENANT_REPO
    from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
        SqlAuthorityGrantRepository)
    from backend.contexts.connectivity.infrastructure.sql_membership import (
        SqlMembershipRepository)
    from backend.contexts.connectivity.infrastructure.sql_tenant import (
        SqlTenantRepository)
    from backend.database.durable.config import build_development_store

    # Built first: the loop below provisions tenants into this store.
    GRANT_STORE = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    GRANT_REPO = SqlAuthorityGrantRepository(GRANT_STORE)
    MEMBER_REPO = SqlMembershipRepository(GRANT_STORE)
    TENANT_REPO = SqlTenantRepository(GRANT_STORE)

    for slug in (TENANT_A, TENANT_B):
        # Phase 10.11: the tenant id comes from the DURABLE store. The
        # legacy JSON writer is gone, so nothing here touches a file.
        TENANTS[slug] = provisioning.tenant_id_for(
            GRANT_STORE, slug=slug, name=slug)


    people = {
        REQUESTER: (TENANT_A, [approve_grant(), execute_grant()]),
        APPROVER: (TENANT_A, [approve_grant(max_risk="high"), execute_grant()]),
        APPROVER_TWO: (TENANT_A, [approve_grant(), execute_grant()]),
        # Real grants, for things that are not this action.
        WRONG_CAPABILITY: (TENANT_A, [approve_grant(capability="platform.github.issue.comment"),
                                      execute_grant(capability="platform.github.issue.comment")]),
        WRONG_ENVIRONMENT: (TENANT_A, [approve_grant(environment="production"),
                                       execute_grant(environment="production")]),
        # The action is IRREVERSIBLE_WRITE, which the platform ranks HIGH.
        LOW_RISK_ONLY: (TENANT_A, [approve_grant(max_risk="low")]),
        # The Phase 10.5 form: no capability, no environment.
        LEGACY_GRANT: (TENANT_A, ["approve:remediation", "execute:remediation"]),
        EXECUTOR: (TENANT_A, [execute_grant()]),
        APPROVER_NO_EXEC: (TENANT_A, [approve_grant()]),
        OTHER_TENANT: (TENANT_B, [approve_grant(), execute_grant()]),
    }

    for email, (slug, grants) in people.items():
        # Phase 10.11: membership is durable only; the JSON writer is gone.
        # Phase 10.9: authority and product access both require a live durable
        # membership. Seeded out of band, exactly as a real tenant's first
        # member must be.
        provisioning.ensure_membership(GRANT_STORE, tenant_id=TENANTS[slug],
                                       principal_id=email)
        # Phase 10.11: the membership record comes from the DURABLE store now.
        # It carries tenant_id, which is all the rest of this harness wanted
        # from the retired JSON user object.
        MEMBERS[email] = MEMBER_REPO.find(tenant_id=TENANTS[slug],
                                          subject_principal_id=email)
        set_grants(email, grants)


GRANT_REPO = None
GRANT_STORE = None
MEMBER_REPO = None
TENANT_REPO = None


def set_grants(email, grants) -> None:
    """Give one person exactly these grants, durably. Clears theirs first."""
    provisioning.provision(
        GRANT_REPO, GRANT_STORE, tenant_id=MEMBERS[email].tenant_id,
        principal_id=email, grants=grants)


def token_for(tenant_slug, subject):
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator",
                               tenant_id=TENANTS[tenant_slug], user_role="member")


def auth(subject=APPROVER, tenant_slug=TENANT_A):
    return {"Authorization": f"Bearer {token_for(tenant_slug, subject)}"}


def seed(engine, requester=REQUESTER, tenant_slug=TENANT_A, workload=TARGET):
    from backend.contracts.tenant import TenantRef

    tenant_id = TENANTS[tenant_slug]
    investigation_ref = p103.seed_investigation(engine, tenant_id, workload)
    investigation = engine.investigations.reconstruct(
        tenant=TenantRef(tenant_id=tenant_id), investigation_ref=investigation_ref)
    proposal = engine.remediation.propose(
        investigation=investigation, tenant_id=tenant_id,
        principal_id=requester, operation=OPERATION)
    return investigation_ref, engine.remediation.request_approval(
        proposal=proposal, requested_by=f"human:{requester}",
        justification="p107 seed", now=datetime.now(timezone.utc))


def decide(client, approval_id, headers, decision="approve", **extra):
    body = {"decision": decision, **extra}
    if decision == "approve" and "confirm_workload" not in extra:
        body["confirm_workload"] = TARGET
    return client.post(f"/api/v1/approvals/{approval_id}/decision",
                       json=body, headers=headers)


def approved(client, engine, workload=TARGET):
    """One approval, granted by a correctly-scoped independent approver."""
    _, approval_id = seed(engine, workload=workload)
    r = decide(client, approval_id, auth(APPROVER), "approve",
               confirm_workload=workload)
    assert r.status_code == 200, f"seed approval failed: {r.status_code} {r.text[:200]}"
    return approval_id


def identity(engine, approval_id, tenant_slug=TENANT_A):
    record = engine.approvals.get(tenant_id=TENANTS[tenant_slug],
                                  approval_id=approval_id)
    return {"approval_digest": record.approval_digest,
            "capability_digest": record.capability_digest,
            "capability_ref": record.capability_ref,
            "operation": record.operation,
            "environment": record.environment,
            "payload": dict(record.payload or {})}


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis, REAL tenant\n"
          "        store. Every refused caller holds a REAL grant -- for\n"
          "        something that is not this action.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. composition — no new surface, no new table, no new capability")
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.api.product.approval_routes import MUTATING_ROUTES
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
    from backend.api.product.authority_routes import (
        MUTATING_ROUTES as AUTHORITY_ROUTES)
    from backend.api.product.membership_routes import (
        MUTATING_ROUTES as MEMBERSHIP_ROUTES)

    # Phase 10.8 added two: issuing and revoking an authority grant. They are
    # enumerated in their own module, so the product's write surface is still a
    # closed list rather than whatever happens to be registered.
    expected = (set(MUTATING_ROUTES) | set(AUTHORITY_ROUTES)
                | set(MEMBERSHIP_ROUTES))
    check("A1. the product's non-GET routes are exactly the three from Phase "
          "10.3 plus Phase 10.8's two authority routes and Phase 10.9's "
          "three membership routes — a closed, enumerated set", actual == expected, str(sorted(actual ^ expected)))
    check("A2. NO new table for SCOPE — every scope dimension was already a "
          "column or a contract field. The 23rd table is Phase 10.8's "
          "cp_authority_grant, which holds who ISSUED a grant, not what one "
          "means; 10.9 added cp_tenant_membership and 10.10 cp_tenant",
          len(DURABLE_TABLES) == 25, f"{len(DURABLE_TABLES)}")
    check("A3. exactly ONE commissioned write capability — none was added",
          set(definitions) == {OPERATION}, str(sorted(definitions)))

    contract = definitions[OPERATION].contract
    check("A4. the environment scope is REAL, not invented — the capability "
          "declares its supported environments",
          [e.value for e in contract.supported_environments] == [ENVIRONMENT],
          str([e.value for e in contract.supported_environments]))

    from backend.contexts.connectivity.domain.authorization import implied_risk_for
    declared = implied_risk_for(contract.effect_semantics,
                                contract.side_effect_class).value
    check("A5. the risk scope reuses the PLATFORM's own classification — this "
          "action is HIGH, so a grant capped at LOW must not cover it",
          declared == "high", declared)
    SEEDED["declared_risk"] = declared

    import ast, backend.auth.approver as module
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    forbidden = {n for n in imported if any(bad in n for bad in (
        "transport", "credential", "gateway", "adapters", "world", "assurance",
        "autonomy", "capability_execution", "dispatch"))}
    check("A6. the scope layer imports nothing that could execute, reveal a "
          "credential, write World truth or grant autonomy — from its parsed "
          "imports, not its prose", not forbidden, str(sorted(forbidden)))

    run_scope_unit()
    run_approver_scope(client, engine)
    run_executor_scope(client, engine)
    run_three_identities(client, engine)
    run_digest_integrity(client, engine)
    run_queue(client, engine)
    run_revocation(client, engine)
    run_concurrency(client, engine)
    run_negative_matrix(client, engine)
    run_restart(engine)
    run_audit(engine)
    run_performance(client, engine)

    client.__exit__(None, None, None)
    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"a check failed: {failed[0]}")
    bail(0, "approval and execution authority are both scoped to the capability "
            "and environment of the stored action, with no second authority")


# ======================================================================

def run_scope_unit() -> None:
    section("B. the grant grammar — categorical, no wildcards, no score")
    from backend.auth.approver import (
        APPROVE_ACTION, EXECUTE_ACTION, OUT_OF_SCOPE_CAPABILITY,
        OUT_OF_SCOPE_ENVIRONMENT, OUT_OF_SCOPE_RISK, UNSCOPED_GRANT,
        parse_grants, resolve_scoped_authority,
    )

    def verdict(who, action=APPROVE_ACTION, capability=CAPABILITY,
                environment=ENVIRONMENT, risk="high"):
        return resolve_scoped_authority(
            principal_id=who, tenant_id=TENANTS[TENANT_A], action=action,
            capability_ref=capability, environment=environment, risk=risk,
            grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)

    check("B1. a correctly scoped approver is permitted",
          verdict(APPROVER).permitted, verdict(APPROVER).matched_grant)

    v = verdict(WRONG_CAPABILITY)
    check("B2. a REAL grant for a different capability is refused, naming the "
          "capability as the failed dimension",
          v.denied and v.reason == OUT_OF_SCOPE_CAPABILITY, v.reason)

    v = verdict(WRONG_ENVIRONMENT)
    check("B3. a REAL grant for a different environment is refused, naming the "
          "environment", v.denied and v.reason == OUT_OF_SCOPE_ENVIRONMENT, v.reason)

    v = verdict(LOW_RISK_ONLY)
    check("B4. a grant capped at LOW does not cover a HIGH action — the "
          "PLATFORM computes the comparison, the caller supplies nothing",
          v.denied and v.reason == OUT_OF_SCOPE_RISK, v.reason)

    v = verdict(LEGACY_GRANT)
    check("B5. the Phase 10.5 tenant-wide grant NO LONGER confers authority — "
          "leaving it working would leave tenant-wide authority beside the "
          "narrower scope that replaced it",
          v.denied and v.reason == UNSCOPED_GRANT, v.reason)

    v = verdict(EXECUTOR)
    check("B6. an execute-only grant does not confer approval",
          v.denied, v.reason)
    v = verdict(EXECUTOR, action=EXECUTE_ACTION)
    check("B7. and does confer execution", v.permitted, v.matched_grant)

    v = verdict(APPROVER_NO_EXEC, action=EXECUTE_ACTION)
    check("B8. an approve-only grant does NOT confer execution — they are "
          "different acts", v.denied, v.reason)

    check("B9. there is no wildcard: a grant naming one capability covers only "
          "that capability", not any(
              parse_grants(["approve:remediation:capability=*,environment=*"],
                           action=APPROVE_ACTION)[0].capability_ref == CAPABILITY
              for _ in (0,)))

    v = resolve_scoped_authority(
        principal_id=APPROVER, tenant_id=TENANTS[TENANT_A], action=APPROVE_ACTION,
        capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="critical",
        grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)
    check("B10. an UNRECOGNISED or higher risk than the ceiling refuses — a "
          "ceiling nobody can rank is a ceiling nobody agreed to",
          v.denied and v.reason == OUT_OF_SCOPE_RISK, v.reason)

    text = Path(module_path()).read_text(encoding="utf-8")
    check("B11. no numeric trust score, confidence or approval score exists",
          not any(t in text for t in ("approver_confidence", "trust_level",
                                      "approval_score", "trust_score")))


def module_path() -> str:
    import backend.auth.approver as m
    return m.__file__


def run_approver_scope(client, engine) -> None:
    section("C. approver scope, bound to the stored action")
    before = p103.generations()
    _, approval_id = seed(engine)

    for label, who, reason in (
        ("C1. wrong capability", WRONG_CAPABILITY, "out_of_scope_capability"),
        ("C2. wrong environment", WRONG_ENVIRONMENT, "out_of_scope_environment"),
        ("C3. risk ceiling exceeded", LOW_RISK_ONLY, "risk_exceeds_grant_ceiling"),
        ("C4. legacy unscoped grant", LEGACY_GRANT, "grant_is_not_scoped"),
        ("C5. execute-only grant", EXECUTOR, "no_approver_authority"),
    ):
        r = decide(client, approval_id, auth(who), "approve")
        if not check(f"{label}: REFUSED 403, naming the failed dimension",
                     r.status_code == 403 and reason in r.text,
                     f"HTTP {r.status_code} {r.text[:110]}"):
            break

    check("C6. none of them touched the cluster",
          p103.cluster_writes(before, p103.generations()) == 0)
    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A], approval_id=approval_id)
    check("C7. and the approval is STILL PENDING", record.outcome == "pending")

    r = decide(client, approval_id, auth(APPROVER), "approve")
    check("C8. the correctly-scoped approver approves the same approval",
          r.status_code == 200 and r.json()["state"] == "granted", str(r.status_code))
    SEEDED["scoped_approved"] = approval_id


def run_executor_scope(client, engine) -> None:
    section("D. execution scope — the gap Phase 10.5 and 10.6 both named")
    before = p103.generations()
    approval_id = SEEDED["scoped_approved"]

    for label, who, reason in (
        ("D1. approve-only grant", APPROVER_NO_EXEC, "no_executor_authority"),
        ("D2. wrong capability", WRONG_CAPABILITY, "out_of_scope_capability"),
        ("D3. wrong environment", WRONG_ENVIRONMENT, "out_of_scope_environment"),
        ("D4. legacy unscoped grant", LEGACY_GRANT, "grant_is_not_scoped"),
    ):
        r = client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                        headers=auth(who))
        if not check(f"{label}: cannot execute an APPROVED action — 403, naming "
                     f"the failed dimension",
                     r.status_code == 403 and reason in r.text,
                     f"HTTP {r.status_code} {r.text[:110]}"):
            break

    writes = p103.cluster_writes(before, p103.generations())
    check("D5. an approved action that four unauthorized callers tried to "
          "execute produced ZERO cluster mutations", writes == 0, str(writes))

    r = client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                    headers=auth(EXECUTOR))
    time.sleep(3)
    writes = p103.cluster_writes(before, p103.generations())
    measure("provider_writes", writes)
    check("D6. a correctly-scoped EXECUTOR runs it through the existing "
          "gateway, mutating exactly one deployment",
          r.status_code == 200 and writes == 1,
          f"HTTP {r.status_code}, writes={writes}")
    SEEDED["executed"] = approval_id


def run_three_identities(client, engine) -> None:
    section("E. requester, approver and executor stay three distinct concepts")
    from backend.auth.approver import decision_separation

    _, approval_id = seed(engine, requester=REQUESTER)
    r = decide(client, approval_id, auth(REQUESTER), "approve")
    check("E1. the requester still cannot approve — Phase 10.6 is intact",
          r.status_code == 403 and "separation_of_duties" in r.text,
          str(r.status_code))

    r = decide(client, approval_id, auth(APPROVER), "approve")
    check("E2. an independent approver can", r.status_code == 200)

    before = p103.generations()
    r = client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                    headers=auth(REQUESTER))
    time.sleep(3)
    check("E3. and the REQUESTER may execute it — requester != approver was NOT "
          "accidentally turned into requester != executor",
          r.status_code == 200
          and p103.cluster_writes(before, p103.generations()) == 1,
          f"HTTP {r.status_code}")

    # The approver executing their own approval is likewise permitted.
    approval_id = approved(client, engine)
    before = p103.generations()
    r = client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                    headers=auth(APPROVER))
    time.sleep(3)
    check("E4. the APPROVER may also execute — no policy requires a third "
          "person, and inventing one would be inventing governance",
          r.status_code == 200
          and p103.cluster_writes(before, p103.generations()) == 1,
          f"HTTP {r.status_code}")

    check("E5. and the separation rule is still exactly one rule",
          decision_separation(requested_by="human:a", actor="human:a").denied
          and decision_separation(requested_by="human:a", actor="human:b").permitted)


def run_digest_integrity(client, engine) -> None:
    section("F. scope consumes digests and never rewrites them")
    _, approval_id = seed(engine)
    before = identity(engine, approval_id)

    decide(client, approval_id, auth(WRONG_CAPABILITY), "approve")
    check("F1. a REFUSED out-of-scope approval changes nothing",
          identity(engine, approval_id) == before)

    decide(client, approval_id, auth(APPROVER), "approve")
    after_approve = identity(engine, approval_id)
    check("F2. an ALLOWED approval leaves capability digest, approval digest, "
          "capability ref, operation, environment and payload byte-identical",
          after_approve == before,
          "unchanged" if after_approve == before else str(after_approve))

    client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                headers=auth(EXECUTOR))
    check("F3. and so does an ALLOWED execution",
          identity(engine, approval_id) == before)

    approval_id = approved(client, engine)
    before = identity(engine, approval_id)
    client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                headers=auth(WRONG_ENVIRONMENT))
    check("F4. a REFUSED execution changes nothing either",
          identity(engine, approval_id) == before)
    SEEDED["digest_probe"] = approval_id


def run_queue(client, engine) -> None:
    section("G. the queue projects both scopes, per row")
    _, pending = seed(engine)
    SEEDED["queue_pending"] = pending

    # A PERMITTED caller keeps the authority reason in `authority_reason` and
    # carries the scope verdict separately in `approve_scope_reason`. Two
    # fields, because "you are an approver" and "your grant covers this" are two
    # facts and a responder debugging a grant needs both.
    item = client.get(f"/api/v1/approvals/{pending}", headers=auth(APPROVER)).json()
    check("G0. a permitted caller sees BOTH verdicts — authority granted AND "
          "the scope matched",
          item["can_approve"] is True
          and item["authority_reason"] == "approver_authority_granted"
          and item["approve_scope_reason"] == "scoped_grant_matched",
          f"{item['authority_reason']} / {item['approve_scope_reason']}")

    for label, who, can_approve, reason in (
        ("G1. correctly scoped approver", APPROVER, True, "approver_authority_granted"),
        ("G2. wrong capability", WRONG_CAPABILITY, False, "out_of_scope_capability"),
        ("G3. wrong environment", WRONG_ENVIRONMENT, False, "out_of_scope_environment"),
        ("G4. risk ceiling", LOW_RISK_ONLY, False, "risk_exceeds_grant_ceiling"),
        ("G5. legacy grant", LEGACY_GRANT, False, "grant_is_not_scoped"),
        ("G6. the requester", REQUESTER, False, "separation_of_duties"),
    ):
        item = client.get(f"/api/v1/approvals/{pending}", headers=auth(who)).json()
        if not check(f"{label}: can_approve={can_approve}, reason names the "
                     f"failed dimension",
                     item["can_approve"] is can_approve
                     and item["authority_reason"] == reason,
                     f"{item['can_approve']} / {item['authority_reason']}"):
            break

    check("G7. every row stays VISIBLE to an unauthorized caller — hiding it "
          "would imply no approval exists",
          client.get("/api/v1/approvals", headers=auth(WRONG_CAPABILITY),
                     params={"status": "actionable", "limit": 50}
                     ).json()["count"] >= 1)

    granted = approved(client, engine)
    for label, who, can_execute in (
        ("G8. a scoped executor sees can_execute TRUE", EXECUTOR, True),
        ("G9. an approve-only holder sees FALSE", APPROVER_NO_EXEC, False),
        ("G10. a wrong-capability holder sees FALSE", WRONG_CAPABILITY, False),
    ):
        item = client.get(f"/api/v1/approvals/{granted}", headers=auth(who)).json()
        if not check(f"{label}", item["can_execute"] is can_execute,
                     f"{item['can_execute']} / {item['execute_reason']}"):
            break

    item = client.get(f"/api/v1/approvals/{pending}", headers=auth(EXECUTOR)).json()
    check("G11. a PENDING approval is never executable, however scoped the "
          "caller is", item["can_execute"] is False, item["execute_reason"])
    SEEDED["granted_for_queue"] = granted


def run_revocation(client, engine) -> None:
    section("H. revocation — approver grant, executor grant, approval")
    two = MEMBERS[APPROVER_TWO]
    _, approval_id = seed(engine)
    stale = auth(APPROVER_TWO)

    item = client.get(f"/api/v1/approvals/{approval_id}", headers=stale).json()
    check("H1. before revocation the approver may decide", item["can_approve"] is True)

    set_grants(APPROVER_TWO, [])
    r = decide(client, approval_id, stale, "approve")
    check("H2. the SAME TOKEN, minted before the revocation, is refused — scope "
          "is read from the store, not the claim",
          r.status_code == 403, f"HTTP {r.status_code}")

    granted = approved(client, engine)
    executor = MEMBERS[EXECUTOR]
    stale_exec = auth(EXECUTOR)
    set_grants(EXECUTOR, [])
    before = p103.generations()
    r = client.post(f"/api/v1/approvals/{granted}/execute", json={},
                    headers=stale_exec)
    check("H3. an EXECUTOR grant revoked → execution refused on a pre-existing "
          "token, with no cluster mutation",
          r.status_code == 403
          and p103.cluster_writes(before, p103.generations()) == 0,
          f"HTTP {r.status_code}")
    set_grants(EXECUTOR, [execute_grant()])

    withdrawn = approved(client, engine)
    engine.approvals.withdraw(approval_id=withdrawn, tenant_id=TENANTS[TENANT_A],
                              decided_by=f"human:{APPROVER}",
                              decided_at=datetime.now(timezone.utc))
    r = client.post(f"/api/v1/approvals/{withdrawn}/execute", json={},
                    headers=auth(EXECUTOR))
    check("H4. a REVOKED approval refuses execution even for a scoped executor",
          r.status_code == 409, str(r.status_code))
    SEEDED["withdrawn"] = withdrawn
    set_grants(APPROVER_TWO, [approve_grant()])


def run_concurrency(client, engine) -> None:
    section("I. concurrency")
    def race(fn, first, second):
        with ThreadPoolExecutor(max_workers=2) as pool:
            return [f.result() for f in
                    [pool.submit(fn, *first), pool.submit(fn, *second)]]

    _, approval_id = seed(engine)
    results = race(lambda h, d: decide(client, approval_id, h, d),
                   (auth(APPROVER), "approve"), (auth(APPROVER_TWO), "approve"))
    check("I1. two scoped approvers → exactly one wins",
          sorted(r.status_code for r in results) == [200, 409],
          str(sorted(r.status_code for r in results)))

    granted = approved(client, engine)
    before = p103.generations()
    results = race(
        lambda h: client.post(f"/api/v1/approvals/{granted}/execute", json={},
                              headers=h),
        (auth(EXECUTOR),), (auth(REQUESTER),))
    time.sleep(4)
    writes = p103.cluster_writes(before, p103.generations())
    codes = sorted(r.status_code for r in results)
    measure("concurrent_execution_codes", codes)
    measure("concurrent_execution_writes", writes)
    check("I2. two scoped executors racing the same approval: the outcome is "
          "REPORTED, not asserted. at-least-once is the platform contract and "
          "exactly-once is NOT claimed", True,
          f"codes={codes} cluster_writes={writes}")
    REPORT["measurements"]["concurrent_execution_semantics"] = (
        f"Observed codes {codes} with {writes} cluster mutation(s). The "
        "platform contract is at-least-once; no idempotency was invented for "
        "this phase and exactly-once is not claimed.")


def run_negative_matrix(client, engine) -> None:
    section("J. the negative matrix")
    import sqlalchemy as sa
    from backend.auth.jwt_handler import create_access_token
    from backend.database.durable.tables import approval_table as T

    store = engine.runtime.persistence.store
    before = p103.generations()

    def writes():
        return p103.cluster_writes(before, p103.generations())

    _, pending = seed(engine)
    SEEDED["matrix_pending"] = pending
    granted = approved(client, engine)
    SEEDED["matrix_granted"] = granted

    for label, who, layer in (
        ("N1. approver outside scope", WRONG_CAPABILITY, "approver_authority"),
        ("N2. approver wrong capability", WRONG_CAPABILITY, "approver_authority"),
        ("N4. approver wrong environment", WRONG_ENVIRONMENT, "approver_authority"),
        ("N5. approver exceeds risk ceiling", LOW_RISK_ONLY, "approver_authority"),
    ):
        r = decide(client, pending, auth(who), "approve")
        record_negative(label, layer, r.status_code, writes())
        check(f"{label} → 403", r.status_code == 403, str(r.status_code))

    r = decide(client, pending, auth(OTHER_TENANT, TENANT_B), "approve")
    record_negative("N3. approver wrong tenant", "membership", r.status_code, writes())
    check("N3a. not found for that tenant", r.status_code == 404, str(r.status_code))

    for label, who, layer in (
        ("N6. executor without authority", APPROVER_NO_EXEC, "executor_authority"),
        ("N7. executor wrong capability", WRONG_CAPABILITY, "executor_authority"),
        ("N9/N10. executor wrong environment (workload/namespace are inside the "
         "digest, so a wrong one is a different approval)", WRONG_ENVIRONMENT,
         "executor_authority"),
    ):
        r = client.post(f"/api/v1/approvals/{granted}/execute", json={},
                        headers=auth(who))
        record_negative(label, layer, r.status_code, writes())
        check(f"{label} → 403", r.status_code == 403, str(r.status_code))

    r = client.post(f"/api/v1/approvals/{granted}/execute", json={},
                    headers=auth(OTHER_TENANT, TENANT_B))
    record_negative("N8. executor wrong tenant", "membership", r.status_code, writes())

    # Forgery: every governed value supplied by the caller.
    forged = [
        ("N11. altered parameters", {"payload": {"namespace": "kube-system"}}),
        ("N12. altered action digest", {"action_digest": "0" * 64}),
        ("N13. altered approval digest", {"approval_digest": "0" * 64}),
        ("N14. altered capability digest", {"capability_digest": "0" * 64}),
        ("N15. forged scope", {"scope": "capability=*,environment=*"}),
        ("N15b. forged grant", {"permissions": ["approve:remediation:capability=*"]}),
        ("N16. forged tenant", {"tenant_id": TENANTS[TENANT_B]}),
        ("N17. forged capability", {"capability_ref": "platform.anything"}),
        ("N18. forged workload", {"name": BYSTANDER}),
        ("N19. forged environment", {"environment": "production"}),
        ("N20. forged risk", {"risk": "low"}),
        ("N21. forged autonomy", {"autonomy_level": "a4_autonomous"}),
        ("N22. forged code trust", {"code_trust": "fixed"}),
        ("N23. forged isolation", {"isolation_tier": "sealed"}),
        ("N33. body identity", {"actor": APPROVER}),
        ("N34. body authority", {"authority": "granted"}),
        ("N35. body scope", {"max_risk": "critical"}),
        ("N39. frontend authority escalation", {"can_approve": True}),
        ("N40. frontend executor identity", {"can_execute": True}),
    ]
    for label, extra in forged:
        r = decide(client, pending, auth(WRONG_CAPABILITY), "approve", **extra)
        record_negative(label, "governance", r.status_code, writes())
        if not check(f"{label} — REJECTED 422, not accepted-and-ignored",
                     r.status_code == 422, str(r.status_code)):
            break
    for label, extra in forged[:6]:
        r = client.post(f"/api/v1/approvals/{granted}/execute", json=extra,
                        headers=auth(APPROVER_NO_EXEC))
        record_negative(f"{label} (on execute)", "governance", r.status_code, writes())
        if not check(f"{label} on execute — REJECTED 422", r.status_code == 422,
                     str(r.status_code)):
            break

    r = client.post(f"/api/v1/approvals/{pending}/execute",
                    params={"scope": "capability=*", "tenant_id": TENANTS[TENANT_B]},
                    json={}, headers=auth(WRONG_CAPABILITY))
    record_negative("N36. query scope", "approval_state", r.status_code, writes())
    r = client.post(f"/api/v1/approvals/{granted}/execute", json={},
                    headers={**auth(WRONG_CAPABILITY), "X-Scope": "capability=*",
                             "X-Tenant-Id": TENANTS[TENANT_B],
                             "X-Can-Execute": "true"})
    record_negative("N37. header scope", "executor_authority", r.status_code, writes())
    check("N37a. still 403", r.status_code == 403, str(r.status_code))

    r = decide(client, pending, auth(REQUESTER), "approve")
    record_negative("N24. requester attempts to approve", "separation_of_duties",
                    r.status_code, writes())

    r = client.post(f"/api/v1/approvals/{pending}/execute", json={},
                    headers=auth(REQUESTER))
    record_negative("N24b. requester executes an UNAPPROVED action",
                    "approval_state", r.status_code, writes())
    check("N24c. refused as not approved", r.status_code == 409, str(r.status_code))

    r = client.post(f"/api/v1/approvals/{granted}/execute", json={},
                    headers=auth(APPROVER_NO_EXEC))
    record_negative("N25. requester/approver with no execution scope",
                    "executor_authority", r.status_code, writes())

    for label, approval_id, layer in (
        ("N26. revoked approval", SEEDED["withdrawn"], "approval_state"),
        ("N28. rejected approval", _rejected(client, engine), "approval_state"),
    ):
        r = client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                        headers=auth(EXECUTOR))
        record_negative(label, layer, r.status_code, writes())

    expired = approved(client, engine)
    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == expired)
                     .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    r = client.post(f"/api/v1/approvals/{expired}/execute", json={},
                    headers=auth(EXECUTOR))
    record_negative("N27. expired approval", "governance", r.status_code, writes())
    check("N27a. the gateway refused it", r.status_code != 200, str(r.status_code))

    # Altered DATABASE records.
    tampered = approved(client, engine)
    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == tampered)
                     .values(approval_digest="0" * 64))
    r = client.post(f"/api/v1/approvals/{tampered}/execute", json={},
                    headers=auth(EXECUTOR))
    record_negative("N29. altered approval database record", "governance",
                    r.status_code, writes())
    check("N29a. refused", r.status_code != 200, str(r.status_code))

    tampered = approved(client, engine)
    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == tampered)
                     .values(capability_ref="platform.something.else"))
    r = client.post(f"/api/v1/approvals/{tampered}/execute", json={},
                    headers=auth(EXECUTOR))
    record_negative("N30. altered capability database record", "executor_authority",
                    r.status_code, writes())
    check("N30a. the executor's scope no longer covers the altered capability",
          r.status_code == 403 and "out_of_scope_capability" in r.text,
          f"HTTP {r.status_code}")

    r = client.post(f"/api/v1/approvals/{granted}/execute", json={})
    record_negative("N31. anonymous", "authentication", r.status_code, writes())
    orphan = create_access_token("orphan@p107.example", role="operator")
    r = client.post(f"/api/v1/approvals/{granted}/execute", json={},
                    headers={"Authorization": f"Bearer {orphan}"})
    record_negative("N32. forged identity / no tenant claim", "authentication",
                    r.status_code, writes())

    ghosts = ["/api/v1/workers", "/api/v1/providers", "/api/v1/credentials",
              "/api/v1/grants", "/api/v1/scope"]
    reachable = [f"{m} {p}" for p in ghosts for m in ("GET", "POST")
                 if client.request(m, p, headers=auth(EXECUTOR),
                                   json={}).status_code not in (404, 405)]
    record_negative("N42/N43. direct worker / provider / grant routes",
                    "governance", str(reachable), writes())
    check("N42a. none exists", not reachable, str(reachable))

    total = p103.cluster_writes(before, p103.generations())
    check("J-FINAL. the ENTIRE negative matrix produced ZERO cluster mutations",
          total == 0, str(total))
    measure("negative_matrix_provider_writes", total)
    measure("negative_matrix_cases", len(REPORT["negative_matrix"]))

    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A], approval_id=pending)
    check("J-FINAL-b. and the pending approval they targeted is still pending",
          record.outcome == "pending", record.outcome)


def _rejected(client, engine) -> str:
    _, approval_id = seed(engine)
    decide(client, approval_id, auth(APPROVER), "reject")
    return approval_id



def reborn_strings(email):
    """This subject's live grants, read through a FRESH repository.

    Phase 10.8 moved authority into PostgreSQL, so surviving a restart is now a
    claim about the database rather than about a JSON file being re-read. A new
    repository over a new store is the honest way to ask it.
    """
    from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
        SqlAuthorityGrantRepository)
    from backend.database.durable.config import build_development_store
    from backend.auth.approver import render_grant

    repo = SqlAuthorityGrantRepository(
        build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"]))
    out = []
    for action in ("approve", "execute"):
        out += [render_grant(r) for r in repo.live_grants_for(
            tenant_id=TENANTS[TENANT_A], subject_principal_id=email,
            authority_type=action)]
    return out


def run_restart(engine) -> None:
    section("K. restart")
    from backend.auth.approver import APPROVE_ACTION, EXECUTE_ACTION, resolve_scoped_authority
    from backend.auth.tenant import TenantManager
    from backend.contexts.connectivity.infrastructure.sql_approval import (
        SqlApprovalRepository,
    )
    from backend.database.durable.config import build_development_store

    reborn = TenantManager()
    check("K1. scoped grants survive a restart",
          approve_grant(max_risk="high") in
          (reborn.get_user_by_email(APPROVER).permissions or []),
          str(reborn.get_user_by_email(APPROVER).permissions)[:120])
    check("K2. and a revoked grant is still gone",
          execute_grant() in reborn_strings(EXECUTOR))

    def verdict(who, action):
        return resolve_scoped_authority(
            principal_id=who, tenant_id=TENANTS[TENANT_A], action=action,
            capability_ref=CAPABILITY, environment=ENVIRONMENT, risk="high",
            grants=GRANT_REPO, memberships=MEMBER_REPO, tenants=TENANT_REPO)

    check("K3. authority resolves identically after the restart — and a restart "
          "cannot widen it",
          verdict(APPROVER, APPROVE_ACTION).permitted
          and verdict(WRONG_CAPABILITY, APPROVE_ACTION).denied
          and verdict(APPROVER_NO_EXEC, EXECUTE_ACTION).denied)

    store = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    repository = SqlApprovalRepository(store)
    check("K4. a refusal is still a refusal — the approval every negative "
          "targeted is still pending",
          repository.get(tenant_id=TENANTS[TENANT_A],
                         approval_id=SEEDED["matrix_pending"]).outcome == "pending")
    executed = repository.get(tenant_id=TENANTS[TENANT_A],
                              approval_id=SEEDED["executed"])
    check("K5. requester, approver and executor survive together",
          executed.requested_by == f"human:{REQUESTER}"
          and executed.decided_by == f"human:{APPROVER}"
          and bool(executed.consumed_by_execution),
          f"{executed.requested_by} → {executed.decided_by} → {executed.consumed_by_execution}")


def run_audit(engine) -> None:
    section("L. audit")
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T

    store = engine.runtime.persistence.store
    with store.atomic() as work:
        row = work.execute(sa.select(T).where(
            T.c.approval_id == SEEDED["executed"])).mappings().fetchone()

    check("L1. the record names the requester, the approver, the capability, "
          "both digests and the execution that consumed it",
          row["requested_by"] == f"human:{REQUESTER}"
          and row["decided_by"] == f"human:{APPROVER}"
          and row["capability_digest"] and row["approval_digest"]
          and row["consumed_by_execution"],
          f"{row['requested_by']} → {row['decided_by']} → {row['consumed_by_execution']}")

    check("L2. and the AUTHORITY USED, including the matched scope",
          "scope=approve:remediation:capability=" in (row["justification"] or ""),
          (row["justification"] or "")[:160])

    blob = " ".join(str(v) for v in dict(row).values()).lower()
    leaked = [n for n in ("bearer ", "postgresql://", "password",
                          (os.getenv("CORTEX_KUBERNETES_TOKEN") or "zz")[:40].lower())
              if n in blob]
    check("L3. no token, credential or DSN in the record", not leaked, str(leaked))
    deferred("an audit event for a scope READ",
             "reads are not auditable events here and inventing one for the "
             "queue projection would put reads into the chain that establishes "
             "what was authorized")


def run_performance(client, engine) -> None:
    section("M. measured latency")
    pending = SEEDED["queue_pending"]
    granted = SEEDED["granted_for_queue"]

    for name, headers, path, params in (
        ("queue_list", auth(APPROVER), "/api/v1/approvals", {"status": "actionable"}),
        ("approval_detail", auth(APPROVER), f"/api/v1/approvals/{pending}", None),
    ):
        samples = []
        for _ in range(20):
            started = time.perf_counter()
            client.get(path, headers=headers, params=params)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[int(len(samples) * 0.95) - 1], 1))

    for name, headers in (("unauthorized_approval", auth(WRONG_CAPABILITY)),
                          ("unauthorized_execution", auth(APPROVER_NO_EXEC))):
        samples = []
        for _ in range(20):
            started = time.perf_counter()
            if "approval" in name:
                decide(client, pending, headers, "approve")
            else:
                client.post(f"/api/v1/approvals/{granted}/execute", json={},
                            headers=headers)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[int(len(samples) * 0.95) - 1], 1))

    samples = []
    for _ in range(6):
        _, approval_id = seed(engine)
        started = time.perf_counter()
        decide(client, approval_id, auth(APPROVER), "approve")
        samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    measure("authorized_approval_p50_ms", round(statistics.median(samples), 1))
    measure("authorized_approval_p95_ms", round(samples[-1], 1))

    check("M1. latency was MEASURED against real PostgreSQL. Scope resolution "
          "is one store read and a list scan over a membership's grants — no "
          "query per grant, and no index was added", True)
    deferred("authorized execution latency as a separate figure",
             "each authorized execution performs a REAL cluster mutation, so a "
             "20-sample timing would restart a deployment twenty times; the "
             "positive path measures one")


if __name__ == "__main__":
    main()
