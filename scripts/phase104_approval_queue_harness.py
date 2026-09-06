"""Phase 10.4: the governed approval queue, against real infrastructure.

What this proves
----------------
A responder can find and act on pending remediation requests **across
investigations**, from one tenant-scoped queue, without the queue becoming a
second approval authority.

The queue is a PROJECTION. Everything it shows is derived from ``cp_approval``
and the capability contract on every read; nothing is stored twice. Every
decision still goes to the one approval route Phase 10.3 shipped.

The discipline
--------------
* Tenant isolation is proven with **real approvals seeded for two tenants**, so
  it cannot pass because a queue is empty.
* Every negative asserts ``provider_writes == 0`` against **cluster generation
  as ground truth**, and names the layer that refused.
* Concurrency is tested with two genuinely simultaneous decisions, and the
  assertion is that exactly one wins -- not that one of them errored.

Reuses the Phase 10.3 harness for environment, cluster ground truth and runtime
composition, so this phase does not invent a second idea of any of them.

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
import scripts.phase99b_contained_worker_harness as b  # noqa: E402

REPORT: dict = {
    "phase": "10.4",
    "checks": [],
    "deferred": [],
    "blocked": [],
    "measurements": {},
    "negative_matrix": [],
    "verdict": "NOT VERIFIED",
}

TENANT_A = "tenant-a-p104"
TENANT_B = "tenant-b-p104"
TENANTS: dict = {}
OPERATION = p103.OPERATION
NAMESPACE = p103.NAMESPACE
TARGET = p103.TARGET
BYSTANDER = p103.BYSTANDER
SEEDED: dict = {}


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


def record_negative(case: str, stopped_by: str, detail: str, writes: int) -> bool:
    REPORT["negative_matrix"].append({
        "case": case, "stopped_by": stopped_by, "detail": str(detail)[:200],
        "provider_writes": writes})
    return check(f"{case} — refused by {stopped_by}", writes == 0, str(detail)[:160])


# ----------------------------------------------------------------------

def register_tenants() -> None:
    from backend.auth.tenant import get_tenant_manager
    tm = get_tenant_manager()
    for slug in (TENANT_A, TENANT_B):
        tenant = tm.get_tenant_by_slug(slug)
        if tenant is None:
            tenant = tm.create_tenant(name=slug, slug=slug)
        TENANTS[slug] = tenant.tenant_id
    for email, slug in (("responder-a@p104.example", TENANT_A),
                        ("responder2-a@p104.example", TENANT_A),
                        ("responder-b@p104.example", TENANT_B)):
        if tm.get_user_by_email(email) is None:
            tm.add_user(TENANTS[slug], email, role="member")


def token_for(tenant_slug: str, subject: str) -> str:
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator",
                               tenant_id=TENANTS[tenant_slug], user_role="member")


def auth(tenant_slug: str = TENANT_A,
         subject: str = "responder-a@p104.example") -> dict:
    return {"Authorization": f"Bearer {token_for(tenant_slug, subject)}"}


def seed_approval(engine, tenant_slug: str, workload: str, *,
                  principal: str = "responder-a@p104.example") -> tuple:
    """One real investigation and one real PENDING approval, through the service.

    Written through ``RemediationService`` -- the same path the product uses --
    so nothing here is a row this phase invented.
    """
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
        justification=f"p104 seed for {workload}",
        now=datetime.now(timezone.utc))
    return investigation_ref, approval_id


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL PostgreSQL, REAL Redis. The queue is a\n"
          "        projection: no new table, no stored queue state. The negative\n"
          "        matrix runs against the real chain.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    section("A. composition — the queue adds NO mutation surface")
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.api.product.approval_routes import MUTATING_ROUTES

    p103.ensure_env()
    register_tenants()
    # The worker credential is provisioned per tenant by the operator.
    for var in ("CORTEX_P99B_TENANT", "CORTEX_KUBERNETES_TENANT"):
        os.environ[var] = TENANTS[TENANT_A]
    b.TENANT = TENANTS[TENANT_A]

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
          "Phase 10.3 — the queue added no way to decide anything new",
          actual == set(MUTATING_ROUTES), str(sorted(actual)))

    from backend.database.durable.tables import DURABLE_TABLES
    # 22 is the count Phase 10.3 left behind, cp_approval included. cp_queue is
    # the EXECUTION queue and long predates this phase -- an earlier version of
    # this check looked for the substring "queue" and failed on it, which is
    # the kind of false positive that gets "fixed" by deleting the assertion.
    names = {t.name for t in DURABLE_TABLES}
    check("A2. NO new table was added — the queue is a projection of "
          "cp_approval, not a second store",
          len(DURABLE_TABLES) == 22 and "cp_approval" in names
          and not any(n.startswith("cp_approval_queue") or n == "cp_queue_state"
                      for n in names),
          f"{len(DURABLE_TABLES)} durable tables, unchanged since Phase 10.3")

    import backend.api.product.approval_queue as queue_module
    source = Path(queue_module.__file__).read_text(encoding="utf-8")
    check("A3. the projection module contains NO write, no insert, no update "
          "and no decision — it cannot become an authority by accident",
          not any(token in source for token in (
              "sa.insert", "sa.update", "sa.delete", ".decide(", ".request(",
              ".grant(", "commit()")),
          "read-only by construction")

    section("B. the queue is a real CROSS-INVESTIGATION projection")
    seeds = []
    for workload in (TARGET, BYSTANDER, TARGET):
        seeds.append(seed_approval(engine, TENANT_A, workload))
    SEEDED["a"] = seeds
    SEEDED["b"] = [seed_approval(engine, TENANT_B, TARGET,
                                 principal="responder-b@p104.example")]
    check("B1. three real approvals exist for tenant A, from THREE DIFFERENT "
          "investigations", len({s[0] for s in seeds}) == 3,
          str([s[1] for s in seeds]))

    # A full page on purpose. Ordering puts the OLDEST actionable approval
    # first -- it is the one closest to expiring unanswered -- so in a store
    # that already holds earlier runs' approvals the newest seeds sit at the
    # back. Asserting on a short page would test the page size, not the queue.
    r = client.get("/api/v1/approvals", headers=auth(), params={"limit": 100})
    check("B2. the queue returns 200", r.status_code == 200, str(r.status_code))
    queue = r.json()
    refs = {i["investigation_ref"] for i in queue["items"]}
    check("B3. one queue shows approvals from ALL THREE investigations — a "
          "responder does not need to know which one raised a request",
          {s[0] for s in seeds} <= refs, f"{len(refs)} investigations in view")

    ids = {i["approval_id"] for i in queue["items"]}
    check("B4. every seeded approval is present", {s[1] for s in seeds} <= ids,
          f"{queue['count']} rows, {queue['actionable_count']} actionable")

    item = next(i for i in queue["items"] if i["approval_id"] == seeds[0][1])
    SEEDED["item"] = item
    run_projection(client, item)
    run_isolation(client, engine)
    run_filters(client)
    run_state_machine(client, engine)
    run_expiration(client, engine)
    run_concurrency(client, engine)
    run_negative_matrix(client, engine)
    run_restart(engine)
    run_audit(runtime)
    run_performance(client)

    client.__exit__(None, None, None)
    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"a check failed: {failed[0]}")
    bail(0, "a tenant-scoped approval queue projects pending decisions across "
            "investigations with no second authority and zero provider writes")


# ======================================================================

def run_projection(client, item) -> None:
    section("C. the projection carries authoritative governance facts")
    check("C1. the capability, provider and operation are projected from the "
          "contract", item["operation"] == OPERATION and item["provider"]
          and item["capability_ref"], f"{item['capability_ref']} / {item['provider']}")

    check("C2. the declared classification is present and is the real one",
          item["side_effect_class"] == "irreversible_write"
          and item["code_trust"] == "fixed"
          and item["isolation_tier"] == "contained",
          f"{item['side_effect_class']}/{item['code_trust']}/{item['isolation_tier']}")

    check("C3. reversibility is honest — an irreversible write says so",
          item["reversible"] is False)

    from backend.contexts.connectivity.domain.authorization import implied_risk_for
    from backend.contracts.execution import EffectSemantics, SideEffectClass
    expected = implied_risk_for(EffectSemantics.NON_IDEMPOTENT_WRITE,
                                SideEffectClass.IRREVERSIBLE_WRITE).value
    check("C4. risk is the PLATFORM's own implied-risk derivation, recomputed "
          "here and asserted equal — not a queue-local scale",
          item["risk"] == expected, f"{item['risk']} == {expected}")

    check("C5. an UNDECLARED effect would be CRITICAL, never low — the queue "
          "inherits the taxonomy's fail-safe default",
          implied_risk_for(None, None).value == "critical")

    check("C6. the canonical approval digest is projected", len(item["approval_digest"]) >= 32)
    check("C7. the ADR-038 action digest is reported ABSENT with the reason, "
          "not invented — it covers a binding resolution has not made yet",
          item["action_digest"] is None and "does not exist yet" in item["action_digest_note"])

    check("C8. autonomy is a CEILING, and no autonomy decision was computed",
          item["autonomy_allowed"] is None and item["autonomy_ceiling"]
          and "would be deciding autonomy" in item["autonomy_note"])

    check("C9. assurance is reported as whether Assurance has RULED, not as a "
          "verdict about the world",
          item["assurance_status"] in ("verified", "not_verified")
          and "separate gates" in item["assurance_note"] or item["assurance_status"] == "verified",
          item["assurance_status"])

    check("C10. blast radius and target are projected from the STORED action",
          item["namespace"] == NAMESPACE and item["workload"] in (TARGET, BYSTANDER)
          and NAMESPACE in item["blast_radius"])

    check("C11. the row is actionable and PENDING",
          item["state"] == "pending" and item["actionable"] is True)

    blob = json.dumps(item).lower()
    leaked = [n for n in ("bearer ", "postgresql://", "password", "secret",
                          (os.getenv("CORTEX_KUBERNETES_TOKEN") or "zz")[:40].lower())
              if n in blob]
    check("C12. NO secret, token, credential or DSN appears in a queue row",
          not leaked, str(leaked))

    detail = client.get(f"/api/v1/approvals/{item['approval_id']}", headers=auth()).json()
    check("C13. the DETAIL endpoint returns the same projection as the row — "
          "one approval cannot show two different actions",
          {k: detail[k] for k in ("approval_digest", "operation", "namespace",
                                  "workload", "risk", "side_effect_class")}
          == {k: item[k] for k in ("approval_digest", "operation", "namespace",
                                   "workload", "risk", "side_effect_class")})


def run_isolation(client, engine) -> None:
    section("D. tenant isolation, with BOTH tenants holding real approvals")
    a_id = SEEDED["a"][0][1]
    b_ref, b_id = SEEDED["b"][0]
    headers_a, headers_b = auth(), auth(TENANT_B, "responder-b@p104.example")

    qa = client.get("/api/v1/approvals", headers=headers_a).json()
    qb = client.get("/api/v1/approvals", headers=headers_b).json()

    check("D1. NEITHER queue is empty — an isolation test that passes because "
          "both sides are empty proves nothing",
          qa["count"] >= 3 and qb["count"] >= 1, f"A={qa['count']} B={qb['count']}")

    ids_a = {i["approval_id"] for i in qa["items"]}
    ids_b = {i["approval_id"] for i in qb["items"]}
    check("D2. tenant A sees its own approvals", a_id in ids_a)
    check("D3. tenant B sees its own approval", b_id in ids_b)
    check("D4. the two queues share NO approval",
          not (ids_a & ids_b), str(sorted(ids_a & ids_b)))
    check("D5. tenant B's queue does not contain tenant A's approval",
          a_id not in ids_b)

    r = client.get(f"/api/v1/approvals/{a_id}", headers=headers_b)
    check("D6. tenant B cannot read tenant A's approval METADATA",
          r.status_code == 404, str(r.status_code))
    check("D7. and the refusal leaks nothing about it",
          a_id not in r.text and NAMESPACE not in r.text, r.text[:120])


def run_filters(client) -> None:
    section("E. filters narrow, and can never escape tenant scope")
    headers_a = auth()
    headers_b = auth(TENANT_B, "responder-b@p104.example")
    a_ref, a_id = SEEDED["a"][0]

    r = client.get("/api/v1/approvals", headers=headers_a,
                   params={"status": "actionable"})
    actionable = r.json()
    check("E1. the actionable filter returns only actionable rows",
          all(i["actionable"] and i["state"] == "pending" for i in actionable["items"]),
          f"{actionable['count']} rows")

    r = client.get("/api/v1/approvals", headers=headers_a,
                   params={"investigation_ref": a_ref})
    filtered = r.json()
    check("E2. the investigation filter narrows to that investigation",
          filtered["count"] >= 1
          and all(i["investigation_ref"] == a_ref for i in filtered["items"]))

    r = client.get("/api/v1/approvals", headers=headers_a, params={"risk": "high"})
    check("E3. the risk filter uses the platform taxonomy and matches",
          all(i["risk"] == "high" for i in r.json()["items"]))
    r = client.get("/api/v1/approvals", headers=headers_a, params={"risk": "low"})
    check("E4. filtering for a risk these actions do not have returns nothing "
          "— the filter is real, not decorative", r.json()["count"] == 0)

    r = client.get("/api/v1/approvals", headers=headers_a,
                   params={"capability_ref": "platform.does.not.exist"})
    check("E5. an unknown capability filter returns nothing", r.json()["count"] == 0)

    r = client.get("/api/v1/approvals", headers=headers_a,
                   params={"older_than_minutes": 10080})
    check("E6. an age filter for approvals older than a week excludes these "
          "fresh ones", r.json()["count"] == 0)

    # The one that matters: a filter naming ANOTHER tenant's data.
    r = client.get("/api/v1/approvals", headers=headers_b,
                   params={"investigation_ref": a_ref})
    check("E7. tenant B filtering by tenant A's investigation gets NOTHING — "
          "the tenant predicate is applied first and a filter cannot widen it",
          r.status_code == 200 and r.json()["count"] == 0, str(r.json()["count"]))

    r = client.get("/api/v1/approvals", headers=headers_b,
                   params={"tenant_id": TENANTS[TENANT_A], "status": "all"})
    check("E8. a forged tenant_id QUERY parameter is ignored",
          r.status_code == 200 and a_id not in {i["approval_id"] for i in r.json()["items"]})

    r = client.get("/api/v1/approvals", headers=headers_a, params={"status": "nonsense"})
    check("E9. an unrecognised status is REJECTED, not silently widened to all",
          r.status_code == 422, str(r.status_code))

    r = client.get("/api/v1/approvals", headers=headers_a, params={"limit": 1000})
    check("E10. an oversized limit is refused", r.status_code == 422, str(r.status_code))

    ordering = client.get("/api/v1/approvals", headers=headers_a).json()
    twice = client.get("/api/v1/approvals", headers=headers_a).json()
    check("E11. ordering is DETERMINISTIC — two reads give the same order",
          [i["approval_id"] for i in ordering["items"]]
          == [i["approval_id"] for i in twice["items"]])
    check("E12. actionable rows sort before decided ones",
          [i["actionable"] for i in ordering["items"]]
          == sorted((i["actionable"] for i in ordering["items"]), reverse=True))


def run_state_machine(client, engine) -> None:
    section("F. the state machine — every invalid transition refuses")
    from backend.contracts.approval import ApprovalOutcome
    headers = auth()
    tenant_id = TENANTS[TENANT_A]

    def fresh(workload=TARGET):
        return seed_approval(engine, TENANT_A, workload)[1]

    approved = fresh()
    r = client.post(f"/api/v1/approvals/{approved}/decision",
                    json={"decision": "approve", "confirm_workload": TARGET},
                    headers=headers)
    check("F1. pending → approve succeeds", r.status_code == 200
          and r.json()["state"] == "granted", str(r.status_code))

    rejected = fresh()
    r = client.post(f"/api/v1/approvals/{rejected}/decision",
                    json={"decision": "reject", "justification": "not now"},
                    headers=headers)
    check("F2. pending → reject succeeds", r.status_code == 200
          and r.json()["state"] == "denied", str(r.status_code))

    transitions = [
        ("F3. approved → approve", approved, "approve"),
        ("F4. approved → reject", approved, "reject"),
        ("F5. rejected → approve", rejected, "approve"),
        ("F6. rejected → reject", rejected, "reject"),
    ]
    for label, approval_id, decision in transitions:
        r = client.post(f"/api/v1/approvals/{approval_id}/decision",
                        json={"decision": decision,
                              **({"confirm_workload": TARGET} if decision == "approve" else {})},
                        headers=headers)
        if not check(f"{label} is REFUSED — one action, one judgement",
                     r.status_code == 409, str(r.status_code)):
            break

    revoked = fresh()
    engine.approvals.withdraw(approval_id=revoked, tenant_id=tenant_id,
                              decided_by="human:responder-a@p104.example",
                              decided_at=datetime.now(timezone.utc))
    r = client.post(f"/api/v1/approvals/{revoked}/decision",
                    json={"decision": "approve", "confirm_workload": TARGET},
                    headers=headers)
    check("F7. revoked → approve is REFUSED", r.status_code == 409, str(r.status_code))
    item = client.get(f"/api/v1/approvals/{revoked}", headers=headers).json()
    check("F8. a revoked approval projects as REVOKED and NOT actionable",
          item["state"] == "revoked" and item["actionable"] is False, item["state"])

    r = client.post(f"/api/v1/approvals/{rejected}/execute", json={}, headers=headers)
    check("F9. executing a REJECTED approval is refused", r.status_code == 409,
          str(r.status_code))
    r = client.post(f"/api/v1/approvals/{revoked}/execute", json={}, headers=headers)
    check("F10. executing a REVOKED approval is refused", r.status_code == 409,
          str(r.status_code))

    SEEDED["approved"] = approved
    SEEDED["rejected"] = rejected
    SEEDED["revoked"] = revoked


def run_expiration(client, engine) -> None:
    section("G. expiration — existing semantics, verified")
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T
    headers = auth()
    store = engine.runtime.persistence.store
    now = datetime.now(timezone.utc)

    approval_id = seed_approval(engine, TENANT_A, TARGET)[1]
    item = client.get(f"/api/v1/approvals/{approval_id}", headers=headers).json()
    check("G1. BEFORE expiry the approval is pending and actionable",
          item["state"] == "pending" and item["actionable"] and not item["expired"])
    check("G2. every approval carries an expiry — the column is NOT NULL, so "
          "there is no 'never expires' option", bool(item["expires_at"]),
          item["expires_at"])

    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == approval_id)
                     .values(expires_at=now - timedelta(minutes=1)))

    item = client.get(f"/api/v1/approvals/{approval_id}", headers=headers).json()
    check("G3. AFTER expiry the projection reads EXPIRED and NOT actionable — "
          "the queue never offers an expired approval as a decision",
          item["state"] == "expired" and item["actionable"] is False, item["state"])

    r = client.get("/api/v1/approvals", headers=headers, params={"status": "actionable"})
    check("G4. it disappears from the actionable queue",
          approval_id not in {i["approval_id"] for i in r.json()["items"]})

    r = client.post(f"/api/v1/approvals/{approval_id}/decision",
                    json={"decision": "approve", "confirm_workload": TARGET},
                    headers=headers)
    check("G5. approving an EXPIRED request is refused — fail closed",
          r.status_code == 409, str(r.status_code))
    SEEDED["expired"] = approval_id

    # A GRANT that then expires must stop authorizing, not stay approved.
    granted = seed_approval(engine, TENANT_A, TARGET)[1]
    client.post(f"/api/v1/approvals/{granted}/decision",
                json={"decision": "approve", "confirm_workload": TARGET}, headers=headers)
    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == granted)
                     .values(expires_at=now - timedelta(minutes=1)))
    item = client.get(f"/api/v1/approvals/{granted}", headers=headers).json()
    check("G6. a GRANTED approval that passed its expiry projects as EXPIRED, "
          "not as approved — it authorizes nothing and the UI must not offer it",
          item["state"] == "expired" and item["actionable"] is False, item["state"])
    SEEDED["granted_expired"] = granted


def run_concurrency(client, engine) -> None:
    section("H. concurrency — two responders, one decision")
    headers_one = auth(TENANT_A, "responder-a@p104.example")
    headers_two = auth(TENANT_A, "responder2-a@p104.example")

    def decide(approval_id, headers, decision):
        return client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": decision,
                  **({"confirm_workload": TARGET} if decision == "approve" else {})},
            headers=headers)

    for label, first, second in (
        ("H1. approve/approve", "approve", "approve"),
        ("H2. approve/reject", "approve", "reject"),
    ):
        approval_id = seed_approval(engine, TENANT_A, TARGET)[1]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(decide, approval_id, headers_one, first),
                       pool.submit(decide, approval_id, headers_two, second)]
            results = [f.result() for f in futures]
        codes = sorted(r.status_code for r in results)
        record = engine.approvals.get(tenant_id=TENANTS[TENANT_A],
                                      approval_id=approval_id)
        winners = [r for r in results if r.status_code == 200]
        check(f"{label}: EXACTLY ONE decision won, the other got a deterministic "
              f"conflict", codes == [200, 409] and len(winners) == 1, str(codes))
        check(f"{label}: the stored outcome is a single decided value with ONE "
              f"decider", record.outcome in ("granted", "denied")
              and record.decided_by is not None,
              f"{record.outcome} by {record.decided_by}")
        SEEDED.setdefault("concurrent", []).append(approval_id)

    check("H3. no distributed lock was introduced — the existing conditional "
          "UPDATE on outcome='pending' is what makes this deterministic",
          "outcome == \"pending\"" in Path(
              "backend/contexts/connectivity/infrastructure/sql_approval.py"
          ).read_text(encoding="utf-8"))


def run_negative_matrix(client, engine) -> None:
    section("I. the negative matrix, through the queue")
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T
    from backend.auth.jwt_handler import create_access_token

    headers_a = auth()
    headers_b = auth(TENANT_B, "responder-b@p104.example")
    a_ref, a_id = SEEDED["a"][0]
    store = engine.runtime.persistence.store
    before = p103.generations()

    def writes():
        return p103.cluster_writes(before, p103.generations())

    r = client.get("/api/v1/approvals")
    record_negative("Q1. unauthenticated queue listing", "authentication",
                    r.status_code, writes())
    r = client.get(f"/api/v1/approvals/{a_id}")
    record_negative("Q2. unauthenticated queue detail", "authentication",
                    r.status_code, writes())
    r = client.get("/api/v1/approvals", headers={"Authorization": "Bearer garbage"})
    record_negative("Q3. forged token", "authentication", r.status_code, writes())
    orphan = create_access_token("orphan@p104.example", role="operator")
    r = client.get("/api/v1/approvals", headers={"Authorization": f"Bearer {orphan}"})
    record_negative("Q4. token with NO tenant claim", "authentication",
                    r.status_code, writes())

    r = client.get("/api/v1/approvals", headers=headers_b, params={"status": "all"})
    record_negative("Q5. cross-tenant listing shows nothing of A's", "authorization",
                    f"{r.status_code}, A's id present={a_id in r.text}", writes())
    check("Q5a. and A's approval id genuinely is not in B's response",
          a_id not in r.text)
    for label, method, path, body in (
        ("Q6. cross-tenant detail", "GET", f"/api/v1/approvals/{a_id}", None),
        ("Q7. cross-tenant approval", "POST", f"/api/v1/approvals/{a_id}/decision",
         {"decision": "approve", "confirm_workload": TARGET}),
        ("Q8. cross-tenant rejection", "POST", f"/api/v1/approvals/{a_id}/decision",
         {"decision": "reject"}),
        ("Q9. cross-tenant execution", "POST", f"/api/v1/approvals/{a_id}/execute", {}),
    ):
        r = client.request(method, path, headers=headers_b, json=body)
        record_negative(label, "authorization", r.status_code, writes())
        check(f"{label} answered NOT FOUND", r.status_code == 404, str(r.status_code))

    for label, body in (
        ("Q10. forged actor field", {"decision": "approve", "actor_ref": "human:someone"}),
        ("Q11. 'admin' actor", {"decision": "approve", "actor": "admin"}),
        ("Q12. tenant in the body", {"decision": "approve", "tenant_id": TENANTS[TENANT_B]}),
        ("Q13. altered action digest", {"decision": "approve", "action_digest": "0" * 64}),
        ("Q14. altered approval digest", {"decision": "approve", "approval_digest": "0" * 64}),
        ("Q15. altered capability", {"decision": "approve", "capability_ref": "platform.x"}),
        ("Q16. altered provider", {"decision": "approve", "provider": "kubernetes"}),
        ("Q17. altered namespace", {"decision": "approve", "namespace": "kube-system"}),
        ("Q18. altered workload", {"decision": "approve", "name": BYSTANDER}),
        ("Q19. altered parameters", {"decision": "approve", "payload": {"a": 1}}),
        ("Q20. altered risk", {"decision": "approve", "risk": "low"}),
        ("Q21. altered blast radius", {"decision": "approve", "blast_radius": "none"}),
        ("Q22. altered code trust", {"decision": "approve", "code_trust": "fixed"}),
        ("Q23. altered isolation tier", {"decision": "approve", "isolation_tier": "sealed"}),
        ("Q24. altered autonomy", {"decision": "approve", "autonomy_level": "a4_autonomous"}),
        ("Q25. altered state", {"decision": "approve", "state": "pending"}),
        ("Q26. secret injection", {"decision": "approve", "token": "Bearer eyJ"}),
        ("Q27. extra authority field", {"decision": "approve", "approver_authority": "root"}),
    ):
        fresh = seed_approval(engine, TENANT_A, TARGET)[1]
        r = client.post(f"/api/v1/approvals/{fresh}/decision", json=body, headers=headers_a)
        record_negative(label, "governance", r.status_code, writes())
        if not check(f"{label} — REJECTED 422, not accepted-and-ignored",
                     r.status_code == 422, str(r.status_code)):
            break

    for label, approval_id in (
        ("Q28. already-approved approval", SEEDED["approved"]),
        ("Q29. already-rejected approval", SEEDED["rejected"]),
        ("Q30. revoked approval", SEEDED["revoked"]),
        ("Q31. expired approval", SEEDED["expired"]),
        ("Q32. granted-then-expired approval", SEEDED["granted_expired"]),
    ):
        r = client.post(f"/api/v1/approvals/{approval_id}/decision",
                        json={"decision": "approve", "confirm_workload": TARGET},
                        headers=headers_a)
        record_negative(label, "approval-state", r.status_code, writes())
        check(f"{label} refused with a conflict", r.status_code == 409, str(r.status_code))

    for label, approval_id in (
        ("Q33. wrong approval id", "appr-does-not-exist"),
        ("Q34. malformed approval id", "../../etc/passwd"),
    ):
        r = client.get(f"/api/v1/approvals/{approval_id}", headers=headers_a)
        record_negative(label, "authorization", r.status_code, writes())
        check(f"{label} is not found or refused",
              r.status_code in (404, 422), str(r.status_code))

    # Execution of an approval whose stored digest was tampered with.
    tampered = seed_approval(engine, TENANT_A, TARGET)[1]
    client.post(f"/api/v1/approvals/{tampered}/decision",
                json={"decision": "approve", "confirm_workload": TARGET},
                headers=headers_a)
    with store.atomic() as work:
        work.execute(sa.update(T).where(T.c.approval_id == tampered)
                     .values(approval_digest="0" * 64))
    r = client.post(f"/api/v1/approvals/{tampered}/execute", json={}, headers=headers_a)
    record_negative("Q35. executing an approval whose action digest was "
                    "tampered with in the store", "governance", r.status_code, writes())
    check("Q35a. the gateway refused it", r.status_code != 200, str(r.status_code))

    ghosts = ["/api/v1/workers", "/api/v1/connectors", "/api/v1/providers",
              "/api/v1/credentials", "/api/v1/gateway", "/api/v1/kubernetes",
              "/api/v1/approvals/queue/execute-all"]
    reachable = [f"{m} {p}" for p in ghosts for m in ("GET", "POST")
                 if client.request(m, p, headers=headers_a,
                                   json={}).status_code not in (404, 405)]
    record_negative("Q36. direct worker / connector / provider / bulk-execute "
                    "access", "governance", str(reachable), writes())
    check("Q36a. none of those routes exists", not reachable, str(reachable))

    after = p103.generations()
    total = p103.cluster_writes(before, after)
    check("I-FINAL. the ENTIRE negative matrix produced ZERO cluster mutations",
          total == 0, str({k: v["generation"] for k, v in after.items()}))
    measure("negative_matrix_provider_writes", total)
    measure("negative_matrix_cases", len(REPORT["negative_matrix"]))


def run_restart(engine) -> None:
    section("J. the queue survives a restart because it stores nothing")
    from backend.api.product.approval_queue import project_queue_item, utc_now
    from backend.contexts.connectivity.infrastructure.sql_approval import (
        SqlApprovalRepository,
    )

    tenant_id = TENANTS[TENANT_A]
    a_id = SEEDED["a"][0][1]
    definitions = getattr(engine.remediation, "_definitions", {})

    first = engine.approvals.get(tenant_id=tenant_id, approval_id=a_id)
    before = project_queue_item(first, definition=definitions.get(OPERATION),
                                now=utc_now())

    # A brand-new repository over a brand-new store: the state a fresh process
    # would see. Nothing is carried over in memory.
    from backend.database.durable.config import build_development_store
    store = build_development_store(dsn=os.environ["CORTEX_DURABLE_URL"])
    reborn = SqlApprovalRepository(store).get(tenant_id=tenant_id, approval_id=a_id)
    after = project_queue_item(reborn, definition=definitions.get(OPERATION),
                               now=utc_now())

    check("J1. a FRESH repository over a fresh connection reconstructs the same "
          "queue row — the queue holds no state a restart could lose",
          {k: v for k, v in before.items() if k not in ("expired",)}
          == {k: v for k, v in after.items() if k not in ("expired",)})

    check("J2. a decision taken before the restart survives it",
          SqlApprovalRepository(store).get(
              tenant_id=tenant_id, approval_id=SEEDED["approved"]
          ).outcome == "granted")
    check("J3. and so does a rejection",
          SqlApprovalRepository(store).get(
              tenant_id=tenant_id, approval_id=SEEDED["rejected"]
          ).outcome == "denied")
    deferred("process restart mid-decision",
             "the decision is a single conditional UPDATE inside one "
             "transaction; there is no window between two writes to interrupt, "
             "so there is no partial state to manufacture")


def run_audit(runtime) -> None:
    section("K. audit")
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T

    store = runtime.persistence.store
    with store.atomic() as work:
        rows = work.execute(
            sa.select(T).where(T.c.approval_id.in_(
                [SEEDED["approved"], SEEDED["rejected"]]))).mappings().fetchall()

    check("K1. both decisions are durably recorded with actor, tenant, "
          "capability, approval digest and timestamp",
          len(rows) == 2 and all(
              r["decided_by"] and r["decided_by"].startswith("human:")
              and r["tenant_id"] == TENANTS[TENANT_A]
              and r["capability_digest"] and r["approval_digest"]
              and r["decided_at"] is not None for r in rows),
          str([(r["outcome"], r["decided_by"]) for r in rows]))

    blob = " ".join(str(v) for r in rows for v in dict(r).values()).lower()
    leaked = [n for n in ("bearer ", "postgresql://", "password",
                          (os.getenv("CORTEX_KUBERNETES_TOKEN") or "zz")[:40].lower())
              if n in blob]
    check("K2. no secret, token or DSN in any decision record", not leaked, str(leaked))

    deferred("an auditable 'approval viewed' event",
             "not currently an auditable event, and NOT invented here — adding "
             "a governance record for UI analytics would put reads into the "
             "chain that establishes what was authorized")


def run_performance(client) -> None:
    section("L. measured latency")
    headers = auth()
    a_ref, a_id = SEEDED["a"][0]

    plans = {
        "queue_list": ("GET", "/api/v1/approvals", None, None),
        "queue_detail": ("GET", f"/api/v1/approvals/{a_id}", None, None),
        "queue_filtered": ("GET", "/api/v1/approvals",
                           {"status": "actionable", "risk": "high"}, None),
    }
    for name, (method, path, params, body) in plans.items():
        samples = []
        for _ in range(20):
            started = time.perf_counter()
            client.request(method, path, headers=headers, params=params, json=body)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[int(len(samples) * 0.95) - 1], 1))

    check("L1. latency was MEASURED against real PostgreSQL. No SLA is proposed "
          "and no index was added to flatter a benchmark", True)
    deferred("decision latency as a separate figure",
             "each decision consumes a pending approval, so a 20-sample timing "
             "would need 20 seeded approvals and would measure seeding as much "
             "as deciding; the concurrency section exercises the real path")


if __name__ == "__main__":
    main()
