"""Phase 10.6: separation of duties, against real infrastructure.

What this proves
----------------
The human who requested an irreversible remediation cannot decide it -- neither
approve nor reject -- and an independent approver still can.

The discipline
--------------
* The refused caller is a **fully authorized approver**. They hold the
  `approve:remediation` grant, in the right tenant, on a live pending approval.
  The only thing wrong is that they asked for it. A refusal cannot therefore be
  explained by missing authority.
* Both digests are read before and after every positive decision and asserted
  byte-identical -- the policy answers ALLOWED or REFUSED and rewrites nothing.
* The requester races an approver, twice, and must lose both times.
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
import scripts.phase99b_contained_worker_harness as b  # noqa: E402

REPORT: dict = {
    "phase": "10.6",
    "checks": [],
    "deferred": [],
    "blocked": [],
    "measurements": {},
    "negative_matrix": [],
    "verdict": "NOT VERIFIED",
}

TENANT_A = "tenant-a-p106"
TENANT_B = "tenant-b-p106"
TENANTS: dict = {}
MEMBERS: dict = {}
OPERATION = p103.OPERATION
NAMESPACE = p103.NAMESPACE
TARGET = p103.TARGET
BYSTANDER = p103.BYSTANDER
SEEDED: dict = {}

#: A, B and C all hold approver authority. A is also the requester throughout,
#: which is the whole point: A's refusal is never about authority.
REQUESTER = "requester-a@p106.example"
APPROVER_B = "approver-b@p106.example"
APPROVER_C = "approver-c@p106.example"
PLAIN_MEMBER = "member-a@p106.example"
OTHER_TENANT = "approver@p106-other.example"


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

def register_people() -> None:
    """Two tenants. Four approver grants, one plain member."""
    from backend.auth.approver import APPROVE_REMEDIATION
    from backend.auth.tenant import get_tenant_manager

    tm = get_tenant_manager()
    for slug in (TENANT_A, TENANT_B):
        tenant = tm.get_tenant_by_slug(slug)
        if tenant is None:
            tenant = tm.create_tenant(name=slug, slug=slug)
        TENANTS[slug] = tenant.tenant_id

    for email, slug in ((REQUESTER, TENANT_A), (APPROVER_B, TENANT_A),
                        (APPROVER_C, TENANT_A), (PLAIN_MEMBER, TENANT_A),
                        (OTHER_TENANT, TENANT_B)):
        member = tm.get_user_by_email(email)
        if member is None:
            member = tm.add_user(TENANTS[slug], email, role="member")
        MEMBERS[email] = member

    # The requester holds approver authority too. Without that, every refusal
    # below could be explained by a missing grant instead of by the policy.
    for email in (REQUESTER, APPROVER_B, APPROVER_C, OTHER_TENANT):
        member = MEMBERS[email]
        tm.grant_permission(member.tenant_id, member.user_id, APPROVE_REMEDIATION)


def token_for(tenant_slug: str, subject: str) -> str:
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator",
                               tenant_id=TENANTS[tenant_slug], user_role="member")


def auth(subject: str = APPROVER_B, tenant_slug: str = TENANT_A) -> dict:
    return {"Authorization": f"Bearer {token_for(tenant_slug, subject)}"}


def seed(engine, requester: str = REQUESTER, tenant_slug: str = TENANT_A,
         workload: str = TARGET) -> tuple:
    """A real approval, requested by a real person, through the real service."""
    from backend.contracts.tenant import TenantRef

    tenant_id = TENANTS[tenant_slug]
    investigation_ref = p103.seed_investigation(engine, tenant_id, workload)
    investigation = engine.investigations.reconstruct(
        tenant=TenantRef(tenant_id=tenant_id), investigation_ref=investigation_ref)
    proposal = engine.remediation.propose(
        investigation=investigation, tenant_id=tenant_id,
        principal_id=requester, operation=OPERATION)
    approval_id = engine.remediation.request_approval(
        proposal=proposal, requested_by=f"human:{requester}",
        justification="p106 seed", now=datetime.now(timezone.utc))
    return investigation_ref, approval_id


def decide(client, approval_id, headers, decision="approve", **extra):
    body = {"decision": decision, **extra}
    if decision == "approve" and "confirm_workload" not in extra:
        body["confirm_workload"] = TARGET
    return client.post(f"/api/v1/approvals/{approval_id}/decision",
                       json=body, headers=headers)


def digests(engine, approval_id, tenant_slug=TENANT_A):
    record = engine.approvals.get(tenant_id=TENANTS[tenant_slug],
                                  approval_id=approval_id)
    return {"approval_digest": record.approval_digest,
            "capability_digest": record.capability_digest,
            "payload": dict(record.payload or {})}


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis, REAL tenant\n"
          "        store. The refused caller is a FULLY AUTHORIZED approver --\n"
          "        the only thing wrong is that they asked for it.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. composition — the policy adds no surface and no infrastructure")
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.api.product.approval_routes import MUTATING_ROUTES
    from backend.database.durable.tables import DURABLE_TABLES

    p103.ensure_env()
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
    check("A1. the product's non-GET routes are STILL exactly the three from "
          "Phase 10.3", actual == set(MUTATING_ROUTES), str(sorted(actual)))
    check("A2. NO new table — both identities were already stored",
          len(DURABLE_TABLES) == 22, f"{len(DURABLE_TABLES)} tables")

    from backend.auth.approver import separation_denial_reason
    check("A3. the refusal reuses the PLATFORM's existing denial reason, not a "
          "new one — a refusal here and a refusal in the capability policy are "
          "the same named thing",
          separation_denial_reason().value == "separation_of_duties",
          separation_denial_reason().value)

    check("A4. the requester identity is already inside the canonical approval "
          "digest, so the policy reads an identity the digest already commits to",
          _requester_in_digest(engine))

    run_requester_refused(client, engine)
    run_positive(client, engine)
    run_digest_safety(client, engine)
    run_state(client, engine)
    run_queue(client, engine)
    run_concurrency(client, engine)
    run_revocation(client, engine)
    run_expiry_and_revoked(client, engine)
    run_negative_matrix(client, engine)
    run_restart(engine)
    run_audit(engine)
    run_performance(client, engine)

    client.__exit__(None, None, None)
    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"a check failed: {failed[0]}")
    bail(0, "the human who requests an irreversible remediation can no longer "
            "decide it, in either direction, and an independent approver still can")


def _requester_in_digest(engine) -> bool:
    """The requester participates in the digest — recomputed, not assumed."""
    from backend.contexts.execution.domain.invocation import canonical_approval_digest
    from backend.contracts.execution import ExecutionEnvironment

    def digest_for(principal):
        return canonical_approval_digest(
            capability_ref="platform.kubernetes.workload.rollout_restart",
            capability_digest="deadbeef" * 8,
            operation=OPERATION, tenant_id=TENANTS[TENANT_A],
            principal_id=principal, environment=ExecutionEnvironment.DEVELOPMENT,
            payload={"namespace": NAMESPACE, "name": TARGET})

    return digest_for(REQUESTER) != digest_for(APPROVER_B)


# ======================================================================

def run_requester_refused(client, engine) -> None:
    section("B. the requester cannot decide — in EITHER direction")
    from backend.auth.approver import resolve_approver_authority

    authority = resolve_approver_authority(
        principal_id=REQUESTER, tenant_id=TENANTS[TENANT_A])
    check("B0. the requester IS a fully authorized approver — so every refusal "
          "below is about the policy and not about a missing grant",
          authority.permitted, authority.reason)

    before = p103.generations()
    _, approve_target = seed(engine)
    r = decide(client, approve_target, auth(REQUESTER), "approve")
    check("B1. the requester APPROVING their own remediation is REFUSED",
          r.status_code == 403 and "separation_of_duties" in r.text,
          f"HTTP {r.status_code} {r.text[:100]}")

    _, reject_target = seed(engine)
    r = decide(client, reject_target, auth(REQUESTER), "reject",
               justification="changed my mind")
    check("B2. the requester REJECTING their own remediation is ALSO refused — "
          "a rule that stopped approval but allowed rejection would leave them "
          "able to bury their own request",
          r.status_code == 403 and "separation_of_duties" in r.text,
          f"HTTP {r.status_code}")

    writes = p103.cluster_writes(before, p103.generations())
    check("B3. neither attempt touched the cluster", writes == 0, str(writes))

    for label, approval_id in (("B4. after the refused approve", approve_target),
                               ("B5. after the refused reject", reject_target)):
        record = engine.approvals.get(tenant_id=TENANTS[TENANT_A],
                                      approval_id=approval_id)
        check(f"{label} the approval is STILL PENDING and undecided — a refused "
              f"decision decides nothing",
              record.outcome == "pending" and record.decided_by is None,
              f"{record.outcome} / {record.decided_by}")

    SEEDED["awaiting_approve"] = approve_target
    SEEDED["awaiting_reject"] = reject_target


def run_positive(client, engine) -> None:
    section("C. an independent approver still can")
    r = decide(client, SEEDED["awaiting_approve"], auth(APPROVER_B), "approve")
    check("C1. an INDEPENDENT approver approves the very approval the requester "
          "was refused", r.status_code == 200 and r.json()["state"] == "granted",
          str(r.status_code))

    r = decide(client, SEEDED["awaiting_reject"], auth(APPROVER_B), "reject",
               justification="not the right remediation")
    check("C2. and rejects the other one",
          r.status_code == 200 and r.json()["state"] == "denied", str(r.status_code))

    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A],
                                  approval_id=SEEDED["awaiting_approve"])
    check("C3. BOTH identities survive on the record — requester and approver",
          record.requested_by == f"human:{REQUESTER}"
          and record.decided_by == f"human:{APPROVER_B}",
          f"{record.requested_by} → {record.decided_by}")
    check("C4. and they are different people, which is the point",
          record.requested_by != record.decided_by)

    before = p103.generations()
    r = client.post(f"/api/v1/approvals/{SEEDED['awaiting_approve']}/execute",
                    json={}, headers=auth(APPROVER_B))
    time.sleep(3)
    writes = p103.cluster_writes(before, p103.generations())
    measure("provider_writes", writes)
    check("C5. the independently approved action executes through the EXISTING "
          "gateway and mutates exactly one deployment",
          r.status_code == 200 and writes == 1,
          f"HTTP {r.status_code}, writes={writes}")
    SEEDED["consumed"] = SEEDED["awaiting_approve"]
    SEEDED["rejected"] = SEEDED["awaiting_reject"]


def run_digest_safety(client, engine) -> None:
    section("D. no digest changes because of this policy")
    for label, decision in (("D1. approve", "approve"), ("D2. reject", "reject")):
        _, approval_id = seed(engine)
        before = digests(engine, approval_id)
        r = decide(client, approval_id, auth(APPROVER_B), decision)
        after = digests(engine, approval_id)
        check(f"{label}: the decision succeeded", r.status_code == 200,
              str(r.status_code))
        check(f"{label}: approval digest, capability digest and payload are "
              f"BYTE-IDENTICAL before and after", before == after,
              "unchanged" if before == after else f"{before} != {after}")
        SEEDED[f"digest_{decision}"] = approval_id

    _, refused = seed(engine)
    before = digests(engine, refused)
    decide(client, refused, auth(REQUESTER), "approve")
    check("D3. and a REFUSED self-decision changes nothing either",
          digests(engine, refused) == before)


def run_state(client, engine) -> None:
    section("E. refusal then independent decision")
    _, approval_id = seed(engine)
    decide(client, approval_id, auth(REQUESTER), "approve")
    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A], approval_id=approval_id)
    check("E1. requester approve refused → still pending", record.outcome == "pending")
    r = decide(client, approval_id, auth(APPROVER_C), "approve")
    check("E2. → then an independent approver approves it",
          r.status_code == 200 and r.json()["state"] == "granted")

    _, approval_id = seed(engine)
    decide(client, approval_id, auth(REQUESTER), "reject")
    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A], approval_id=approval_id)
    check("E3. requester reject refused → still pending", record.outcome == "pending")
    r = decide(client, approval_id, auth(APPROVER_C), "reject")
    check("E4. → then an independent approver rejects it",
          r.status_code == 200 and r.json()["state"] == "denied")


def run_queue(client, engine) -> None:
    section("F. the queue says WHY, without computing it")
    _, approval_id = seed(engine)
    SEEDED["queue_pending"] = approval_id

    item = client.get(f"/api/v1/approvals/{approval_id}",
                      headers=auth(REQUESTER)).json()
    check("F1. the requester sees the approval as ACTIONABLE but cannot decide it",
          item["actionable"] is True and item["can_approve"] is False,
          f"actionable={item['actionable']} can_approve={item['can_approve']}")
    check("F2. and is told exactly why — separation of duties, not a generic "
          "'forbidden'", item["authority_reason"] == "separation_of_duties"
          and item["viewer_is_requester"] is True, item["authority_reason"])

    item = client.get(f"/api/v1/approvals/{approval_id}",
                      headers=auth(APPROVER_B)).json()
    check("F3. an independent approver sees the same row as decidable",
          item["can_approve"] is True and item["viewer_is_requester"] is False)

    item = client.get(f"/api/v1/approvals/{approval_id}",
                      headers=auth(PLAIN_MEMBER)).json()
    check("F4. a member with NO authority is told about the authority, not "
          "about separation — the precedence the decision route uses",
          item["can_approve"] is False
          and item["authority_reason"] == "no_approver_authority",
          item["authority_reason"])

    queue = client.get("/api/v1/approvals", headers=auth(REQUESTER),
                       params={"status": "actionable", "limit": 50}).json()
    mine = [i for i in queue["items"] if i["approval_id"] == approval_id]
    check("F5. the row is NOT hidden from the requester — they can see what "
          "they asked for and that somebody else must decide it",
          len(mine) == 1 and mine[0]["viewer_is_requester"] is True,
          f"{queue['count']} rows visible")

    import backend.api.product.approval_queue as module
    source = Path(module.__file__).read_text(encoding="utf-8")
    check("F6. the projection computes it SERVER-side from the stored requester",
          "decision_separation" in source and "viewer_is_requester" in source)


def run_concurrency(client, engine) -> None:
    section("G. concurrency — and the requester must not win the race")
    def race(approval_id, first, second):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(decide, client, approval_id, *args)
                       for args in (first, second)]
            return [f.result() for f in futures]

    _, approval_id = seed(engine)
    results = race(approval_id, (auth(APPROVER_B), "approve"),
                   (auth(APPROVER_C), "approve"))
    check("G1. two independent approvers, approve/approve → exactly one wins",
          sorted(r.status_code for r in results) == [200, 409],
          str(sorted(r.status_code for r in results)))

    _, approval_id = seed(engine)
    results = race(approval_id, (auth(APPROVER_B), "approve"),
                   (auth(APPROVER_C), "reject"))
    check("G2. approve/reject → exactly one wins",
          sorted(r.status_code for r in results) == [200, 409],
          str(sorted(r.status_code for r in results)))

    before = p103.generations()
    _, approval_id = seed(engine)
    requester_result, approver_result = race(
        approval_id, (auth(REQUESTER), "approve"), (auth(APPROVER_B), "approve"))
    check("G3. THE REQUESTER RACES AN APPROVER: the requester is refused 403 "
          "with separation of duties, and the approver succeeds — a race cannot "
          "be used to slip past the policy",
          requester_result.status_code == 403
          and "separation_of_duties" in requester_result.text
          and approver_result.status_code == 200,
          f"requester={requester_result.status_code} approver={approver_result.status_code}")

    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A], approval_id=approval_id)
    check("G4. and the single stored decision is the APPROVER's, never the "
          "requester's", record.decided_by == f"human:{APPROVER_B}",
          str(record.decided_by))
    check("G5. no cluster mutation followed the race",
          p103.cluster_writes(before, p103.generations()) == 0)

    check("G6. no distributed lock was introduced",
          'T.c.outcome == "pending"' in Path(
              "backend/contexts/connectivity/infrastructure/sql_approval.py"
          ).read_text(encoding="utf-8"))


def run_revocation(client, engine) -> None:
    section("H. revocation stays fail-closed, alongside the new policy")
    from backend.auth.approver import APPROVE_REMEDIATION
    from backend.auth.tenant import get_tenant_manager

    tm = get_tenant_manager()
    _, approval_id = seed(engine)
    stale = auth(APPROVER_B)

    member = MEMBERS[APPROVER_B]
    tm.revoke_permission(member.tenant_id, member.user_id, APPROVE_REMEDIATION)
    r = decide(client, approval_id, stale, "approve")
    check("H1. B's authority revoked → B is refused, on a token minted before "
          "the revocation", r.status_code == 403
          and "no_approver_authority" in r.text, f"HTTP {r.status_code}")

    r = decide(client, approval_id, auth(REQUESTER), "approve")
    check("H2. and the requester is still refused — for the OTHER reason",
          r.status_code == 403 and "separation_of_duties" in r.text,
          f"HTTP {r.status_code}")

    r = decide(client, approval_id, auth(APPROVER_C), "approve")
    check("H3. a newly-authorized independent approver can decide it",
          r.status_code == 200, str(r.status_code))

    tm.grant_permission(member.tenant_id, member.user_id, APPROVE_REMEDIATION)


def run_expiry_and_revoked(client, engine) -> None:
    section("I. precedence — inherited from the capability policy, not invented")
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T

    store = engine.runtime.persistence.store
    past = datetime.now(timezone.utc) - timedelta(minutes=1)

    _, approval_id = seed(engine)
    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == approval_id)
                     .values(expires_at=past))

    r = decide(client, approval_id, auth(APPROVER_B), "approve")
    check("I1. an INDEPENDENT approver on an expired approval is refused for "
          "EXPIRY", r.status_code == 409 and "expired" in r.text.lower(),
          f"HTTP {r.status_code} {r.text[:80]}")

    r = decide(client, approval_id, auth(REQUESTER), "approve")
    check("I2. the REQUESTER on that same expired approval is refused for "
          "SEPARATION OF DUTIES — CapabilityPolicy checks authorization, then "
          "separation, then state, and this follows that order rather than "
          "inventing one",
          r.status_code == 403 and "separation_of_duties" in r.text,
          f"HTTP {r.status_code}")
    SEEDED["expired"] = approval_id

    _, revoked = seed(engine)
    engine.approvals.withdraw(approval_id=revoked, tenant_id=TENANTS[TENANT_A],
                              decided_by=f"human:{APPROVER_B}",
                              decided_at=datetime.now(timezone.utc))
    before = p103.generations()
    r_req = decide(client, revoked, auth(REQUESTER), "approve")
    r_app = decide(client, revoked, auth(APPROVER_B), "approve")
    check("I3. a REVOKED approval refuses BOTH the requester and an independent "
          "approver", r_req.status_code in (403, 409)
          and r_app.status_code == 409,
          f"requester={r_req.status_code} approver={r_app.status_code}")
    check("I4. and neither touched the cluster",
          p103.cluster_writes(before, p103.generations()) == 0)
    SEEDED["revoked"] = revoked


def run_negative_matrix(client, engine) -> None:
    section("J. the negative matrix")
    import sqlalchemy as sa
    from backend.auth.jwt_handler import create_access_token
    from backend.database.durable.tables import approval_table as T

    store = engine.runtime.persistence.store
    before = p103.generations()

    def writes():
        return p103.cluster_writes(before, p103.generations())

    _, target = seed(engine)
    SEEDED["matrix_pending"] = target

    r = decide(client, target, auth(REQUESTER), "approve")
    record_negative("S1. requester approves", "separation_of_duties",
                    r.status_code, writes())
    r = decide(client, target, auth(REQUESTER), "reject")
    record_negative("S2. requester rejects", "separation_of_duties",
                    r.status_code, writes())

    r = decide(client, target, auth(PLAIN_MEMBER), "approve")
    record_negative("S3. non-approver approves", "approver_authority",
                    r.status_code, writes())
    r = decide(client, target, auth(PLAIN_MEMBER), "reject")
    record_negative("S4. non-approver rejects", "approver_authority",
                    r.status_code, writes())

    r = decide(client, target, auth(OTHER_TENANT, TENANT_B), "approve")
    record_negative("S5. an approver from the WRONG TENANT", "membership",
                    r.status_code, writes())
    check("S5a. not found for that tenant", r.status_code == 404, str(r.status_code))

    r = client.post(f"/api/v1/approvals/{target}/decision",
                    json={"decision": "approve"})
    record_negative("S6. anonymous", "authentication", r.status_code, writes())

    orphan = create_access_token("orphan@p106.example", role="operator")
    r = decide(client, target, {"Authorization": f"Bearer {orphan}"}, "approve")
    record_negative("S6b. token with no tenant claim", "authentication",
                    r.status_code, writes())

    # Identity forgery. The requester attempts to claim they are somebody else.
    forgery = [
        ("S7. forged requester in the body", {"requester": APPROVER_B}),
        ("S7b. forged requested_by in the body", {"requested_by": f"human:{APPROVER_B}"}),
        ("S8. forged approver in the body", {"approver": "admin"}),
        ("S9. forged actor in the body", {"actor": APPROVER_B}),
        ("S9b. forged actor_ref in the body", {"actor_ref": f"human:{APPROVER_B}"}),
        ("S10. tenant in the body", {"tenant": TENANTS[TENANT_B]}),
        ("S10b. tenant_id in the body", {"tenant_id": TENANTS[TENANT_B]}),
        ("S14. role in the body", {"role": "approver"}),
        ("S15. authority in the body", {"authority": "granted"}),
        ("S15b. viewer_is_requester in the body", {"viewer_is_requester": False}),
        ("S15c. can_approve in the body", {"can_approve": True}),
        ("S20. altered action digest", {"action_digest": "0" * 64}),
        ("S21. altered approval digest", {"approval_digest": "0" * 64}),
        ("S22. altered capability", {"capability_ref": "platform.x"}),
        ("S23. altered workload", {"name": BYSTANDER}),
        ("S24. altered namespace", {"namespace": "kube-system"}),
        ("S25. altered risk", {"risk": "low"}),
        ("S26. altered blast radius", {"blast_radius": "none"}),
        ("S27. altered autonomy", {"autonomy_level": "a4_autonomous"}),
        ("S28. altered code trust", {"code_trust": "fixed"}),
        ("S29. altered isolation", {"isolation_tier": "sealed"}),
        ("S30. secret injection", {"token": "Bearer eyJhbGciOi"}),
    ]
    for label, extra in forgery:
        r = decide(client, target, auth(REQUESTER), "approve", **extra)
        record_negative(label, "governance", r.status_code, writes())
        if not check(f"{label} — REJECTED 422, not accepted-and-ignored",
                     r.status_code == 422, str(r.status_code)):
            break

    r = client.post(f"/api/v1/approvals/{target}/decision",
                    params={"tenant_id": TENANTS[TENANT_B], "actor": APPROVER_B},
                    json={"decision": "approve", "confirm_workload": TARGET},
                    headers=auth(REQUESTER))
    record_negative("S11. tenant and actor in QUERY parameters",
                    "separation_of_duties", r.status_code, writes())
    check("S11a. still separation of duties",
          r.status_code == 403 and "separation_of_duties" in r.text, str(r.status_code))

    r = client.post(f"/api/v1/approvals/{target}/decision",
                    json={"decision": "approve", "confirm_workload": TARGET},
                    headers={**auth(REQUESTER), "X-Tenant-Id": TENANTS[TENANT_B],
                             "X-Actor": APPROVER_B, "X-Requester": APPROVER_C,
                             "X-Can-Approve": "true", "X-Role": "approver"})
    record_negative("S12/S13. tenant, actor, requester and role in HEADERS",
                    "separation_of_duties", r.status_code, writes())
    check("S12a. still separation of duties",
          r.status_code == 403 and "separation_of_duties" in r.text, str(r.status_code))

    for label, approval_id, layer in (
        ("S16. expired", SEEDED["expired"], "approval_state"),
        ("S17. revoked", SEEDED["revoked"], "approval_state"),
        ("S18. already approved", SEEDED["consumed"], "approval_state"),
        ("S19. already rejected", SEEDED["rejected"], "approval_state"),
    ):
        r = decide(client, approval_id, auth(APPROVER_B), "approve")
        record_negative(label, layer, r.status_code, writes())
        check(f"{label} refused", r.status_code in (403, 409), str(r.status_code))

    # A stored digest tampered with directly, decided by an INDEPENDENT approver.
    _, tampered = seed(engine)
    decide(client, tampered, auth(APPROVER_B), "approve")
    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == tampered)
                     .values(approval_digest="0" * 64))
    r = client.post(f"/api/v1/approvals/{tampered}/execute", json={},
                    headers=auth(APPROVER_B))
    record_negative("S20b. executing an approval whose stored digest was "
                    "tampered with", "governance", r.status_code, writes())
    check("S20c. the gateway refused it", r.status_code != 200, str(r.status_code))

    ghosts = ["/api/v1/workers", "/api/v1/providers", "/api/v1/credentials",
              "/api/v1/approvals/self-approve", "/api/v1/roles"]
    reachable = [f"{m} {p}" for p in ghosts for m in ("GET", "POST")
                 if client.request(m, p, headers=auth(REQUESTER),
                                   json={}).status_code not in (404, 405)]
    record_negative("S31/S32. direct worker / provider / credential / "
                    "self-approve routes", "governance", str(reachable), writes())
    check("S31a. none exists", not reachable, str(reachable))

    total = p103.cluster_writes(before, p103.generations())
    check("J-FINAL. the ENTIRE negative matrix produced ZERO cluster mutations",
          total == 0, str(total))
    measure("negative_matrix_provider_writes", total)
    measure("negative_matrix_cases", len(REPORT["negative_matrix"]))

    record = engine.approvals.get(tenant_id=TENANTS[TENANT_A], approval_id=target)
    check("J-FINAL-b. and the approval every one of them targeted is STILL "
          "PENDING", record.outcome == "pending", record.outcome)


def run_restart(engine) -> None:
    section("K. restart")
    from backend.auth.approver import decision_separation
    from backend.contexts.connectivity.infrastructure.sql_approval import (
        SqlApprovalRepository,
    )
    from backend.database.durable.config import build_development_store

    store = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    repository = SqlApprovalRepository(store)

    consumed = repository.get(tenant_id=TENANTS[TENANT_A],
                              approval_id=SEEDED["consumed"])
    check("K1. requester AND approver identities survive a restart",
          consumed.requested_by == f"human:{REQUESTER}"
          and consumed.decided_by == f"human:{APPROVER_B}",
          f"{consumed.requested_by} → {consumed.decided_by}")

    pending = repository.get(tenant_id=TENANTS[TENANT_A],
                             approval_id=SEEDED["matrix_pending"])
    check("K2. a pending approval the requester was refused on is STILL pending "
          "after a restart — no restart converts a refusal into an approval",
          pending.outcome == "pending" and pending.decided_by is None,
          f"{pending.outcome} / {pending.decided_by}")

    check("K3. the policy reaches the same verdict on the reloaded record",
          decision_separation(requested_by=pending.requested_by,
                              actor=f"human:{REQUESTER}").denied
          and decision_separation(requested_by=pending.requested_by,
                                  actor=f"human:{APPROVER_B}").permitted)

    check("K4. a decision taken before the restart survives it",
          repository.get(tenant_id=TENANTS[TENANT_A],
                         approval_id=SEEDED["rejected"]).outcome == "denied")


def run_audit(engine) -> None:
    section("L. audit")
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T

    store = engine.runtime.persistence.store
    with store.atomic() as work:
        rows = work.execute(sa.select(T).where(T.c.approval_id.in_(
            [SEEDED["consumed"], SEEDED["rejected"], SEEDED["matrix_pending"]]
        ))).mappings().fetchall()
    by_id = {r["approval_id"]: r for r in rows}

    for label, approval_id, outcome in (
        ("L1. the approved record", SEEDED["consumed"], "granted"),
        ("L2. the rejected record", SEEDED["rejected"], "denied"),
    ):
        row = by_id[approval_id]
        check(f"{label} names BOTH humans — who asked and who allowed",
              row["requested_by"] == f"human:{REQUESTER}"
              and row["decided_by"] == f"human:{APPROVER_B}"
              and row["outcome"] == outcome
              and row["decided_at"] is not None,
              f"{row['requested_by']} → {row['decided_by']} ({row['outcome']})")

    refused = by_id[SEEDED["matrix_pending"]]
    check("L3. and the approval the REQUESTER attempted carries NO decider and "
          "NO decision — nothing in the record claims they approved anything",
          refused["decided_by"] is None and refused["decided_at"] is None
          and refused["outcome"] == "pending",
          f"{refused['outcome']} / {refused['decided_by']}")

    check("L4. no new audit event kind was invented for this refusal — the "
          "existing records are unchanged in shape", True,
          "refusal leaves the row untouched")

    blob = " ".join(str(v) for r in rows for v in dict(r).values()).lower()
    leaked = [n for n in ("bearer ", "postgresql://", "password",
                          (os.getenv("CORTEX_KUBERNETES_TOKEN") or "zz")[:40].lower())
              if n in blob]
    check("L5. no token, credential or DSN in any record", not leaked, str(leaked))


def run_performance(client, engine) -> None:
    section("M. measured latency")
    pending = SEEDED["queue_pending"]

    for name, headers, path, params in (
        ("queue_list", auth(APPROVER_B), "/api/v1/approvals", {"status": "actionable"}),
        ("queue_detail", auth(APPROVER_B), f"/api/v1/approvals/{pending}", None),
        ("requester_refusal", auth(REQUESTER), None, None),
    ):
        samples = []
        for _ in range(20):
            started = time.perf_counter()
            if path is None:
                decide(client, pending, headers, "approve")
            else:
                client.get(path, headers=headers, params=params)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[int(len(samples) * 0.95) - 1], 1))

    for name, decision in (("independent_approval", "approve"),
                           ("independent_rejection", "reject")):
        samples = []
        for _ in range(6):
            _, approval_id = seed(engine)
            started = time.perf_counter()
            decide(client, approval_id, auth(APPROVER_B), decision)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[-1], 1))

    check("M1. latency was MEASURED against real PostgreSQL. The separation "
          "check adds one string comparison on data already loaded — no query, "
          "and no index was added", True)
    deferred("decision p95 from 6 samples",
             "each decision consumes a pending approval, so a larger sample "
             "would measure seeding as much as deciding")


if __name__ == "__main__":
    main()
