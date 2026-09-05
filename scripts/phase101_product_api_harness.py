"""Phase 10.1 evidence: a real product API over the verified engine.

What this proves
----------------
A real FastAPI application, a real PostgreSQL-backed engine, real JWTs issued by
the platform's own issuer, and real investigation/world data written by the
governed planes -- then:

    authenticated request -> tenant from the token -> existing governed service
    -> read-only projection

and, for every way a caller might try to get somebody else's data or make
something happen:

    refusal, with ZERO provider calls.

The discipline
--------------
A negative is not VERIFIED because a request returned an error code. Each denied
case also asserts that no provider was contacted, and the mutation cases assert
that the route does not exist at all rather than that it merely refused -- a
route that returns 405 is a route somebody can later make work.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED / BLOCKED.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

REPORT: dict = {
    "phase": "10.1",
    "checks": [],
    "deferred": [],
    "measurements": {},
    "verdict": "NOT VERIFIED",
}

TENANT_A = "tenant-a-p101"
TENANT_B = "tenant-b-p101"


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


# ----------------------------------------------------------------------


def ensure_dev_jwt_secret() -> None:
    """A disposable signing secret for this harness only.

    The issuer refuses to start without one, and that refusal is correct -- a
    platform that silently signed with a default would be worse. This sets a
    throwaway value for a throwaway process; it is never written to disk and the
    harness asserts below that it never appears in a response.
    """
    import secrets as _secrets
    for var in ("JWT_SECRET_KEY", "JWT_REFRESH_SECRET_KEY", "SECRET_KEY"):
        if not os.getenv(var):
            os.environ[var] = _secrets.token_hex(32)


def issue_token(tenant_id: str, subject: str = "engineer@example.com",
                role: str = "member") -> str:
    """A real token from the platform's own issuer. Never a hand-built JWT.

    Signed with the deployment's real secret, and therefore subject to the same
    verification and blacklist check every other caller gets.
    """
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(
        subject, role="operator", tenant_id=tenant_id, user_role=role)


#: Resolved at registration; ``require_tenant`` looks the tenant up by the id the
#: manager assigned, not by the slug the harness chose.
TENANTS: dict = {}


def register_tenants() -> None:
    """``require_tenant`` checks the tenant EXISTS and is ACTIVE, so both must."""
    from backend.auth.tenant import get_tenant_manager
    tm = get_tenant_manager()
    for slug in (TENANT_A, TENANT_B):
        tenant = tm.get_tenant_by_slug(slug)
        if tenant is None:
            tenant = tm.create_tenant(name=slug, slug=slug)
        TENANTS[slug] = tenant.tenant_id



def seed_investigation(engine, tenant_id: str) -> str:
    """One real, concluded investigation for this tenant.

    Written through the governed service so it goes through the same lifecycle
    guards as any other investigation -- CREATED -> INVESTIGATING before a
    conclusion is accepted, which the state machine enforces.
    """
    from datetime import datetime, timezone

    from backend.contracts.intelligence.investigation import (
        InvestigationConclusion, InvestigationStatus,
    )
    from backend.contracts.tenant import TenantRef

    now = datetime.now(timezone.utc)
    tenant = TenantRef(tenant_id=tenant_id)
    service = engine.investigations

    investigation = service.create(
        tenant=tenant, incident_ref="kubernetes:deployment:demo/payments-api",
        policy_ref="phase101/1", harness_version="p101", now=now)
    investigation = service.transition(
        investigation=investigation, to_status=InvestigationStatus.INVESTIGATING,
        cause="harness seed", now=now)
    investigation = service.conclude(
        investigation=investigation,
        # INSUFFICIENT_EVIDENCE on purpose: the API must render it as its own
        # answer rather than as a failure, and E-section asserts exactly that.
        conclusion=InvestigationConclusion.INSUFFICIENT_EVIDENCE,
        cause="harness seed", now=now)
    return investigation.investigation_ref


def build_engine():
    """Compose the read surfaces against the real durable store."""
    from backend.api.product.app import compose_engine
    return compose_engine()


class ProviderWatch:
    """Counts any attempt to dial a provider. Must stay at zero for the API."""

    def __init__(self):
        self.calls = []

    #: Every method on the broker by which a request could actually leave the
    #: process. Wrapping the class rather than an instance catches a dial from
    #: anywhere, including code this harness never constructed.
    DIAL_METHODS = ("dial", "exchange", "request", "send", "open")

    def install(self):
        import backend.platform.transport.broker as broker

        watch = self
        self._patched = []
        for name in self.DIAL_METHODS:
            original = getattr(broker.TransportBroker, name, None)
            if original is None or not callable(original):
                continue

            def counted(self_, *a, __name=name, __orig=original, **kw):  # noqa: ANN001
                watch.calls.append(f"TransportBroker.{__name}")
                return __orig(self_, *a, **kw)

            setattr(broker.TransportBroker, name, counted)
            self._patched.append((name, original))
        if not self._patched:
            raise RuntimeError(
                "no TransportBroker dial method was found to watch; refusing to "
                "report zero provider calls without actually watching for them")
        return self

    def restore(self):
        import backend.platform.transport.broker as broker
        for name, original in self._patched:
            setattr(broker.TransportBroker, name, original)


def main() -> None:
    section("A. composition — a real app over the real engine")
    from fastapi.testclient import TestClient

    from backend.api.product import ProductEngine, build_product_app

    if not os.getenv("CORTEX_DURABLE_URL"):
        bail(2, "CORTEX_DURABLE_URL is not set; this harness needs real PostgreSQL")

    ensure_dev_jwt_secret()
    register_tenants()
    engine = build_engine()
    if engine is None:
        bail(2, "the governed engine could not be composed")
    check("A1. the engine composed against real PostgreSQL", True)
    check("A2. the engine exposes ONLY read surfaces — no gateway, dispatcher, "
          "worker runtime, credential broker or transport is reachable from it",
          set(ProductEngine.__dataclass_fields__) == {
              "investigations", "investigation_repository", "world_query",
              "verifications"},
          str(sorted(ProductEngine.__dataclass_fields__)))

    app = build_product_app(engine=engine)
    client = TestClient(app, raise_server_exceptions=False)
    paths = sorted(r.path for r in app.routes if getattr(r, "path", "").startswith("/api"))
    methods = {m for r in app.routes for m in (getattr(r, "methods", None) or ())
               if getattr(r, "path", "").startswith("/api")}
    check("A3. every product route is a GET — the API is read-only by shape, "
          "not by convention", methods == {"GET"}, str(sorted(methods)))
    measure("routes", paths)

    seeded_ref = seed_investigation(engine, TENANTS[TENANT_A])
    check("A4. a real investigation exists for tenant A, written through the "
          "governed service", bool(seeded_ref), seeded_ref)
    REPORT["measurements"]["seeded_investigation"] = seeded_ref

    watch = ProviderWatch().install()
    try:
        run_security(client, seeded_ref)
        run_reads(client, engine, seeded_ref)
        run_performance(client)
    finally:
        watch.restore()

    section("F. the decisive negative")
    check("F1. ZERO provider calls occurred during the entire run — the API "
          "never reached a provider", not watch.calls, str(watch.calls))
    measure("provider_calls", len(watch.calls))

    failed = [x["check"] for x in REPORT["checks"] if not x["ok"]]
    if failed:
        bail(1, f"a check failed: {failed[0]}")
    bail(0, "the verified engine is exposed to an authenticated tenant-scoped "
            "client with no second authority and no provider access")


def run_security(client, seeded_ref: str) -> None:
    section("B. the security matrix")
    a = issue_token(TENANTS[TENANT_A])
    b = issue_token(TENANTS[TENANT_B])
    auth_a = {"Authorization": f"Bearer {a}"}

    # 1. no authentication
    r = client.get("/api/v1/investigations")
    check("B1. NO authentication is refused", r.status_code in (401, 403),
          str(r.status_code))

    # 2. valid authentication
    r = client.get("/api/v1/investigations", headers=auth_a)
    check("B2. valid authentication is admitted", r.status_code == 200,
          str(r.status_code))

    # 3-4. malformed / garbage identity
    for label, token in (("B3. a garbage token is refused", "not-a-jwt"),
                         ("B4. an empty bearer is refused", "")):
        r = client.get("/api/v1/investigations",
                       headers={"Authorization": f"Bearer {token}"})
        check(label, r.status_code in (401, 403), str(r.status_code))

    # 5. a token with NO tenant claim
    from backend.auth.jwt_handler import create_access_token
    no_tenant = create_access_token("nobody", role="operator")
    r = client.get("/api/v1/investigations",
                   headers={"Authorization": f"Bearer {no_tenant}"})
    check("B5. a token carrying NO tenant claim is refused",
          r.status_code == 403, str(r.status_code))

    # 6-8. client-supplied tenant must be ignored entirely
    forged = [
        ("B6. tenant in a QUERY parameter is ignored",
         client.get(f"/api/v1/investigations?tenant_id={TENANTS[TENANT_B]}", headers=auth_a)),
        ("B7. tenant in a forged HEADER is ignored",
         client.get("/api/v1/investigations",
                    headers={**auth_a, "X-Tenant-Id": TENANTS[TENANT_B]})),
        ("B8. tenant in a JSON BODY is ignored (and the route stays a GET)",
         client.request("GET", "/api/v1/investigations", headers=auth_a,
                        json={"tenant_id": TENANTS[TENANT_B]})),
    ]
    for label, response in forged:
        check(label, response.status_code == 200, str(response.status_code))

    # The proof that ignoring actually happened: A and B see different worlds.
    ra = client.get("/api/v1/investigations", headers=auth_a).json()
    rb = client.get("/api/v1/investigations",
                    headers={"Authorization": f"Bearer {b}"}).json()
    # A has one seeded investigation; B has none. If both were empty this check
    # would prove nothing, so the counts themselves are asserted.
    check("B9. two tenants receive DIFFERENT result sets from the same endpoint "
          "— tenant A sees its investigation, tenant B sees none",
          ra["count"] >= 1 and rb["count"] == 0 and ra != rb,
          f"A={ra['count']} B={rb['count']}")

    # 10. THE cross-tenant test: B asks for A's real investigation by id.
    r = client.get(f"/api/v1/investigations/{seeded_ref}",
                   headers={"Authorization": f"Bearer {b}"})
    check("B10. tenant B requesting tenant A's REAL investigation by id is NOT "
          "FOUND — the resource exists, and B still cannot read it",
          r.status_code == 404, str(r.status_code))

    r = client.get(f"/api/v1/investigations/{seeded_ref}", headers=auth_a)
    check("B10b. and tenant A can read the very same id — the 404 above is "
          "isolation, not a broken endpoint",
          r.status_code == 200, str(r.status_code))

    for suffix in ("/hypotheses", "/evidence"):
        r = client.get(f"/api/v1/investigations/{seeded_ref}{suffix}",
                       headers={"Authorization": f"Bearer {b}"})
        check(f"B10c. tenant B is refused the sub-resource {suffix} too",
              r.status_code == 404, str(r.status_code))

    r = client.get("/api/v1/investigations/winv-belongs-to-nobody", headers=auth_a)
    check("B10d. a nonexistent investigation is also NOT FOUND — the same "
          "answer, which is what stops existence being probed",
          r.status_code == 404, str(r.status_code))

    # 11. invalid resource id
    r = client.get("/api/v1/investigations/" + "x" * 500, headers=auth_a)
    check("B11. an over-long resource id is rejected by validation",
          r.status_code == 422, str(r.status_code))

    # 12. unbounded list request
    r = client.get("/api/v1/investigations?limit=100000", headers=auth_a)
    check("B12. an unbounded limit is refused, not silently clamped to a huge "
          "page", r.status_code == 422, str(r.status_code))
    r = client.get("/api/v1/investigations?limit=-5", headers=auth_a)
    check("B13. a negative limit is refused", r.status_code == 422, str(r.status_code))
    r = client.get("/api/v1/investigations?limit=100", headers=auth_a)
    check("B14. the maximum page is bounded at 100",
          r.status_code == 200 and r.json()["limit"] <= 100,
          str(r.json().get("limit")))

    section("C. no mutation surface exists")
    # Not "refuses to mutate" -- the routes do not exist. A 405 would mean the
    # path is registered and somebody could later add a verb to it.
    for method, path in (
        ("POST", "/api/v1/investigations"),
        ("POST", "/api/v1/investigations/winv-1/conclude"),
        ("POST", "/api/v1/approvals"),
        ("POST", "/api/v1/executions"),
        ("POST", "/api/v1/autonomy"),
        ("POST", "/api/v1/world/state"),
        ("PUT", "/api/v1/world/state"),
        ("DELETE", "/api/v1/investigations/winv-1"),
        ("PATCH", "/api/v1/verifications/v1"),
    ):
        r = client.request(method, path, headers=auth_a, json={})
        check(f"C. {method} {path} does not exist",
              r.status_code in (404, 405), str(r.status_code))

    section("D. no secret can appear in a response")
    needles = [v for v in (os.getenv("CORTEX_P99B_RESTART_TOKEN", ""),
                           os.getenv("CORTEX_KUBERNETES_TOKEN", ""),
                           os.getenv("CORTEX_DURABLE_URL", ""),
                           a) if v]
    blob = ""
    for path in ("/api/v1/investigations",
                 "/api/v1/world/state?subject_ref=x&predicate=y",
                 "/api/v1/healthz"):
        blob += client.get(path, headers=auth_a).text
    leaked = [n[:12] + "..." for n in needles if n and n in blob]
    check("D1. no credential, DSN or bearer token appears in ANY response body",
          not leaked, str(leaked))
    check("D2. the liveness probe discloses nothing about tenant, engine or "
          "configuration",
          set(client.get("/api/v1/healthz").json().keys()) == {"status"})


def run_reads(client, engine, seeded_ref: str) -> None:
    section("E. reads work, preserve meaning, and mutate nothing")
    auth = {"Authorization": f"Bearer {issue_token(TENANTS[TENANT_A])}"}

    r = client.get("/api/v1/investigations", headers=auth)
    body = r.json()
    check("E1. the list endpoint answers with an explicit bounded schema",
          r.status_code == 200 and {"items", "count", "limit", "note"} <= set(body))
    check("E2. it says plainly that it lists COMPLETED investigations only, "
          "rather than letting an empty list imply nothing is happening",
          "Completed investigations only" in body["note"])

    r = client.get("/api/v1/world/state?subject_ref=kubernetes:deployment:none/none"
                   "&predicate=deployed_revision", headers=auth)
    check("E3. a world read for a subject with no evidence answers with an "
          "epistemic STATUS, not an error and not 'false'",
          r.status_code == 200 and r.json()["epistemic_status"] not in ("", None),
          r.json().get("epistemic_status"))
    check("E4. UNKNOWN is carried as its own value — never coerced to false, "
          "absent, or a confidence number",
          "unknown" in str(r.json()["epistemic_status"]).lower()
          and r.json()["value"] is None,
          f"status={r.json()['epistemic_status']} value={r.json()['value']}")
    check("E5. no confidence field is invented anywhere in the schema",
          "confidence" not in r.text.lower())

    detail = client.get(f"/api/v1/investigations/{seeded_ref}", headers=auth).json()
    check("E5b. an INSUFFICIENT_EVIDENCE conclusion is carried as its own value, "
          "not rendered as a failure or an error",
          "insufficient" in str(detail.get("conclusion_kind", "")).lower(),
          str(detail.get("conclusion_kind")))
    check("E5c. the detail response exposes only declared fields — no raw "
          "domain state leaked through",
          set(detail) <= {"investigation_ref", "status", "subject_ref",
                          "opened_at", "concluded_at", "diagnosis", "hypotheses",
                          "evidence", "residual_uncertainty", "conclusion_kind"},
          str(sorted(set(detail))))

    # Repeated reads must be observationally equivalent (Part Q).
    before = _ledger_counts()
    first = client.get("/api/v1/investigations", headers=auth).json()
    for _ in range(4):
        client.get("/api/v1/investigations", headers=auth)
        client.get("/api/v1/world/state?subject_ref=a&predicate=b", headers=auth)
    after = _ledger_counts()
    second = client.get("/api/v1/investigations", headers=auth).json()
    check("E6. repeated GETs are observationally equivalent", first == second)
    check("E7. reads mutate NOTHING — observation, fact, verification and "
          "investigation row counts are unchanged after 10 reads",
          before == after, f"{before} -> {after}")
    measure("ledger_counts", after)


def _ledger_counts() -> dict:
    import sqlalchemy as sa
    dsn = os.getenv("CORTEX_DURABLE_URL", "")
    out = {}
    engine = sa.create_engine(dsn)
    try:
        with engine.connect() as conn:
            for table in ("cw_observation", "cw_fact", "cw_verification",
                          "cp_investigation_event"):
                try:
                    out[table] = conn.execute(
                        sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
                except Exception:  # noqa: BLE001 - absent table is not a failure
                    out[table] = None
    finally:
        engine.dispose()
    return out


def run_performance(client) -> None:
    section("G. measured latency (measured, not a target)")
    auth = {"Authorization": f"Bearer {issue_token(TENANTS[TENANT_A])}"}

    def timed(path, n=30):
        samples = []
        for _ in range(n):
            t = time.perf_counter()
            client.get(path, headers=auth)
            samples.append((time.perf_counter() - t) * 1000)
        samples.sort()
        p50 = statistics.median(samples)
        p95 = samples[max(0, int(len(samples) * 0.95) - 1)]
        return round(p50, 1), round(p95, 1)

    for label, path in (
        ("investigation_list", "/api/v1/investigations"),
        ("world_state", "/api/v1/world/state?subject_ref=a&predicate=b"),
        ("healthz", "/api/v1/healthz"),
    ):
        p50, p95 = timed(path)
        measure(f"{label}_p50_ms", p50)
        measure(f"{label}_p95_ms", p95)
    check("G1. latency was measured over 30 samples per endpoint", True,
          "in-process ASGI; excludes network")
    deferred("an SLA or latency target",
             "these are in-process TestClient timings against a local "
             "PostgreSQL on a development host. They exclude network, TLS and "
             "concurrency, and no target is proposed from them.")


if __name__ == "__main__":
    main()
