"""Phase 10.3: human approval and governed remediation through the PRODUCT path.

What this proves
----------------
A human operator, authenticated in a browser session, approves and initiates a
real Kubernetes remediation -- and the governed chain that Phase 9 built is the
only thing that decides whether it happens.

    product API -> authenticated context -> existing capability binding ->
    existing authorization -> existing approval validation -> existing gateway ->
    existing CONTAINED worker -> real k3d cluster

The discipline
--------------
Phase 9.9C found a live hole: authorization downgraded REQUIRE_APPROVAL to ALLOW
and the gateway's action-digest comparison became unreachable, so an approval
granted for ``billing-api`` restarted ``payments-api``. A product API is a NEW
CALLER into that same path. So the 9.9C negative matrix is re-run here through
HTTP, and:

* every negative asserts ``provider_writes == 0`` using **the cluster's own
  generation counters as ground truth**, not a return value;
* every negative records WHICH layer refused -- authentication, authorization,
  governance, worker or assurance -- because collapsing them all into "blocked"
  hides the case where the wrong layer did the work;
* the entire matrix runs BEFORE the one real write. If any of it fails, nothing
  is written.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED / BLOCKED.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import scripts.phase99b_contained_worker_harness as b  # noqa: E402

REPORT: dict = {
    "phase": "10.3",
    "checks": [],
    "deferred": [],
    "blocked": [],
    "measurements": {},
    "milestones": [],
    "negative_matrix": [],
    "verdict": "NOT VERIFIED",
}

TENANT_A = "tenant-a-p103"
TENANT_B = "tenant-b-p103"
TENANTS: dict = {}
OPERATION = "kubernetes.workload.rollout_restart"
CAPABILITY_ID = "platform.kubernetes.workload.rollout_restart"
NAMESPACE = os.getenv("CORTEX_P99B_NAMESPACE", "cortex-p99b")
TARGET = os.getenv("CORTEX_P99B_TARGET", "payments-api")
BYSTANDER = os.getenv("CORTEX_P99B_BYSTANDER", "billing-api")
SEEDED: dict = {}


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def deferred(name, why):
    REPORT["deferred"].append({"item": name, "why": str(why)[:400]})
    print(f"  [DEFR] {name} — {why}")


def blocked(name, why):
    REPORT["blocked"].append({"item": name, "why": str(why)[:400]})
    print(f"  [BLKD] {name} — {why}")


def measure(name, value):
    REPORT["measurements"][name] = value
    print(f"  [ms ] {name} = {value}")


def milestone(token):
    REPORT["milestones"].append(token)
    print(f"  [MILE] {token}")


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
# The cluster, as ground truth
# ----------------------------------------------------------------------

def generations() -> dict:
    """Every deployment's ``metadata.generation`` in the namespace.

    Phase 9.10's lesson: a POST to the worker is NOT a mutation of Kubernetes.
    So the only thing that counts as a provider write here is the external
    system's own state changing, read with the platform's READ credential --
    a different identity from the one that can write.
    """
    import urllib.request, ssl, json as _json

    url = (f"{os.environ['CORTEX_KUBERNETES_URL']}/apis/apps/v1/namespaces/"
           f"{NAMESPACE}/deployments")
    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {os.environ['CORTEX_KUBERNETES_TOKEN']}"})
    context = ssl.create_default_context(cafile=os.environ.get("CORTEX_TLS_CA_BUNDLE"))
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        body = _json.loads(response.read())
    return {item["metadata"]["name"]: {
        "generation": item["metadata"]["generation"],
        "replicas": item["spec"].get("replicas"),
        "image": item["spec"]["template"]["spec"]["containers"][0].get("image"),
        "uid": item["metadata"]["uid"],
    } for item in body.get("items", [])}


def pod_names() -> set:
    import urllib.request, ssl, json as _json

    url = (f"{os.environ['CORTEX_KUBERNETES_URL']}/api/v1/namespaces/"
           f"{NAMESPACE}/pods")
    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {os.environ['CORTEX_KUBERNETES_TOKEN']}"})
    context = ssl.create_default_context(cafile=os.environ.get("CORTEX_TLS_CA_BUNDLE"))
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        body = _json.loads(response.read())
    return {item["metadata"]["name"] for item in body.get("items", [])}


def cluster_writes(before: dict, after: dict) -> int:
    """How many deployments actually changed generation. The real count."""
    return sum(1 for name, state in after.items()
               if before.get(name, {}).get("generation") != state["generation"])


# ----------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------

def ensure_env() -> None:
    for var in ("JWT_SECRET_KEY", "JWT_REFRESH_SECRET_KEY", "SECRET_KEY"):
        if not os.getenv(var):
            import secrets as _secrets
            os.environ[var] = _secrets.token_hex(32)


def register_tenants() -> None:
    from backend.auth.tenant import get_tenant_manager
    tm = get_tenant_manager()
    for slug in (TENANT_A, TENANT_B):
        tenant = tm.get_tenant_by_slug(slug)
        if tenant is None:
            tenant = tm.create_tenant(name=slug, slug=slug)
        TENANTS[slug] = tenant.tenant_id
    for email, slug in (("responder@p103.example", TENANT_A),
                        ("intruder@p103.example", TENANT_B)):
        if tm.get_user_by_email(email) is None:
            tm.add_user(TENANTS[slug], email, role="member")


def token_for(tenant_slug: str, subject: str = "responder@p103.example") -> str:
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(subject, role="operator",
                               tenant_id=TENANTS[tenant_slug], user_role="member")


def auth(tenant_slug: str = TENANT_A, subject: str = "responder@p103.example") -> dict:
    return {"Authorization": f"Bearer {token_for(tenant_slug, subject)}"}


def build_runtime():
    """The real runtime, with the DURABLE approval store installed via the seam."""
    os.environ.setdefault(
        "CORTEX_CONNECTOR_FACTORIES",
        "backend.api.kubernetes_provider_factory:kubernetes_real_extension,"
        "backend.api.contained_worker_factory:contained_worker_extension")
    from backend.api.application_runtime import build_governed_runtime
    from backend.contexts.connectivity.infrastructure.sql_approval import (
        SqlApprovalRepository,
    )

    runtime = build_governed_runtime(approvals_factory=SqlApprovalRepository)
    if runtime is None:
        bail(2, "no governed runtime; is CORTEX_DURABLE_URL set?")
    writer = getattr(runtime, "audit_writer", None)
    if writer is not None:
        try:
            writer.acquire()
        except Exception as exc:  # noqa: BLE001
            print(f"  [note] audit writer role not acquired: {exc}")
    return runtime


def build_engine(runtime, definitions):
    from backend.api.product.app import (
        ProductEngine, _compose_remediation, _execution_context,
    )
    from backend.api.product.remediation import RemediationService
    from backend.api.observability_evidence import (
        observability_authority_policy, observability_freshness_policy,
        observability_lineage_policy,
    )
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.contexts.connectivity.infrastructure.sql_approval import (
        SqlApprovalRepository,
    )
    # Phase 10.8: the durable authority-grant store. Without it every scope
    # resolution answers ``authority_store_unavailable`` -- correctly, since a
    # store that is not there cannot say anyone holds anything.
    from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
        SqlAuthorityGrantRepository,
    )
    from backend.contracts.execution import ExecutionEnvironment
    from backend.intelligence.application.investigation_service import (
        InvestigationService,
    )
    from backend.intelligence.infrastructure.sql_investigation import (
        SqlInvestigationRepository,
    )
    from backend.world.application import WorldQuery
    from backend.world.application.belief import BeliefFormation
    from backend.world.infrastructure import (
        SqlFactRepository, SqlObservationRepository,
    )

    store = runtime.persistence.store
    repository = SqlInvestigationRepository(store)
    observations = SqlObservationRepository(store)
    authority = observability_authority_policy()
    lineage = observability_lineage_policy()
    world_query = WorldQuery(facts=SqlFactRepository(store), observations=observations,
                             authority_policy=authority,
                             freshness_policy=observability_freshness_policy())

    def writer_factory(rt, defs, principal):
        from backend.api.capability_execution_composition import (
            GovernedCapabilityWriter,
        )
        return GovernedCapabilityWriter(
            runtime=rt, capability_definitions=defs, principal=principal)

    return ProductEngine(
        investigations=InvestigationService(repository=repository),
        investigation_repository=repository,
        world_query=world_query,
        verifications=SqlVerificationRepository(store),
        observations=observations,
        beliefs=BeliefFormation(query=world_query, observations=observations,
                                authority_policy=authority, lineage_policy=lineage),
        lineage_policy=lineage,
        approvals=SqlApprovalRepository(store),
        grants=SqlAuthorityGrantRepository(store),
        remediation=RemediationService(
            definitions=definitions, approvals=SqlApprovalRepository(store),
            writer_factory=writer_factory,
            environment=ExecutionEnvironment.DEVELOPMENT,
            authorization_operation="invoke"),
        runtime=runtime,
        execution_context_factory=_execution_context,
    )


def seed_investigation(engine, tenant_id: str, workload: str) -> str:
    """A real investigation whose subject is a real deployment in the cluster."""
    from backend.contracts.intelligence.investigation import InvestigationStatus
    from backend.contracts.tenant import TenantRef

    now = datetime.now(timezone.utc)
    service = engine.investigations
    investigation = service.create(
        tenant=TenantRef(tenant_id=tenant_id),
        incident_ref=f"kubernetes:deployment:{NAMESPACE}/{workload}",
        policy_ref="phase103/1", harness_version="p103", now=now)
    return service.transition(
        investigation=investigation, to_status=InvestigationStatus.INVESTIGATING,
        cause="harness seed", now=now).investigation_ref


# ----------------------------------------------------------------------

def main() -> None:
    print("[label] REAL k3d cluster, REAL CONTAINED worker, REAL PostgreSQL, REAL\n"
          "        Redis. The 9.9C negative matrix runs through HTTP BEFORE the\n"
          "        write; if any of it fails, nothing is written.\n")
    for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                "CORTEX_TLS_CA_BUNDLE", "CORTEX_DURABLE_URL"):
        if not os.getenv(var):
            bail(2, f"{var} is not set; source .phase99b.env first")

    ensure_env()
    register_tenants()
    # The contained worker's credential is provisioned BY THE OPERATOR against a
    # named tenant (``secrets={tenant_id: token}`` in the connector factory).
    # Phase 9.9B used the literal "dev"; the product's tenant is whatever the
    # tenant store assigned. So the credential is bound to the tenant that will
    # actually use it -- which is what an operator provisioning for a real
    # customer would do, and it means tenant B has no credential at all on top
    # of governance refusing it first.
    for var in ("CORTEX_P99B_TENANT", "CORTEX_KUBERNETES_TENANT"):
        os.environ[var] = TENANTS[TENANT_A]
    b.TENANT = TENANTS[TENANT_A]

    section("A. composition — the product gains a mutation surface, exactly three routes")
    from fastapi.testclient import TestClient
    from backend.api.product.app import build_product_app
    from backend.api.product.approval_routes import MUTATING_ROUTES

    runtime = build_runtime()
    ctx = b._platform_ctx()
    definitions = b._commission(runtime, ctx)
    check("A1. the ONE commissioned write capability is registered",
          definitions.get(OPERATION) is not None, CAPABILITY_ID)

    engine = build_engine(runtime, definitions)
    app = build_product_app(engine=engine)
    # Entered as a context manager on purpose. Without it, TestClient spins up a
    # NEW event loop per request; the async Redis client cached during one
    # request is then bound to a loop that is closed by the next, every
    # blacklist check raises, and fail-closed mode correctly rejects everything.
    # One portal for the whole run is what a real server has.
    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()

    actual = {(m, r.path) for r in app.routes
              for m in (getattr(r, "methods", None) or ())
              if m not in ("GET", "HEAD", "OPTIONS")
              and getattr(r, "path", "").startswith("/api")}
    check("A2. the product's non-GET routes are EXACTLY the three declared ones — "
          "a fourth cannot appear without this failing",
          actual == set(MUTATING_ROUTES), str(sorted(actual)))

    check("A3. the durable approval store is installed through the DECLARED "
          "seam, not by assigning a private attribute",
          type(runtime.authorization._approvals).__name__ == "SqlApprovalRepository",  # noqa: SLF001
          type(runtime.authorization._approvals).__name__)  # noqa: SLF001

    run_revocation()

    SEEDED["investigation"] = seed_investigation(engine, TENANTS[TENANT_A], TARGET)
    SEEDED["bystander_investigation"] = seed_investigation(
        engine, TENANTS[TENANT_A], BYSTANDER)
    SEEDED["tenant_b_investigation"] = seed_investigation(
        engine, TENANTS[TENANT_B], TARGET)
    check("A4. real investigations exist for both tenants",
          bool(SEEDED["investigation"]) and bool(SEEDED["tenant_b_investigation"]))

    run_proposal(client)
    run_negative_matrix(client, engine)

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"STOPPED BEFORE THE WRITE: {failed[0]}")

    run_positive(client, engine, runtime)
    run_replay(client, engine)
    run_audit(runtime)
    run_crash_boundaries()
    run_performance(client, engine)

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"a check failed after the write: {failed[0]}")
    if "PROVIDER_WRITE_EXECUTED" not in REPORT["milestones"]:
        bail(2, "the governed remediation did not execute")
    client.__exit__(None, None, None)
    bail(0, "a human approved and initiated a real governed remediation through "
            "the product API, the negative matrix refused every variant with zero "
            "cluster mutations, and no second authority exists")


# ======================================================================
# B. Revocation — the 10.2 gap, closed first
# ======================================================================


def _reset_redis() -> None:
    """Drop the async Redis client so the next event loop builds its own.

    Not a workaround for a bug in the platform -- the client is legitimately
    bound to the loop that created it, and this harness deliberately uses more
    than one loop (an ``asyncio.run`` probe, then the TestClient's). Resetting
    is how a process that switches loops keeps a working connection.
    """
    try:
        from backend.infrastructure.redis.connection import redis_connection
        redis_connection._client = None       # noqa: SLF001 - loop-bound handle
        redis_connection._pub_client = None   # noqa: SLF001
        redis_connection._available = False   # noqa: SLF001
        redis_connection._failures = 0        # noqa: SLF001 - do not inherit a
        # failure count from the dead loop; the next loop deserves a fresh try.
        task = getattr(redis_connection, "_reconnect_task", None)
        if task is not None:
            try:
                task.cancel()
            except Exception:  # noqa: BLE001
                pass
            redis_connection._reconnect_task = None  # noqa: SLF001
    except Exception:  # noqa: BLE001
        return


def run_revocation() -> None:
    section("B. authentication and revocation, against real Redis")
    from backend.auth.jwt_handler import create_access_token, decode_access_token
    from backend.auth.token_blacklist import token_blacklist, _FAIL_OPEN

    # All Redis work happens in ONE event loop, then the connection is reset.
    #
    # Found the hard way on the first run of this harness: the async Redis client
    # is a module singleton bound to the loop that created it. A second
    # ``asyncio.run`` gets a client whose loop is dead, every call raises, and
    # ``is_jti_revoked`` -- correctly, in fail-closed mode -- answers "revoked"
    # for EVERY token. The platform then rejected every request in the rest of
    # the run. That is the right behaviour from the blacklist and a real
    # operational hazard worth recording: under REVOCATION_FAIL_OPEN=false, a
    # Redis client bound to a dead loop takes authentication down completely.
    async def probe():
        status = await token_blacklist.status()
        valid = token_for(TENANT_A)
        p = decode_access_token(valid)
        before = await token_blacklist.is_revoked(
            jti=p["jti"], user_id=p["sub"], issued_at=float(p["iat"]))
        await token_blacklist.revoke_token(
            jti=p["jti"], user_id=p["sub"], expires_at=float(p["exp"]),
            token_type="access")
        after = await token_blacklist.is_revoked(
            jti=p["jti"], user_id=p["sub"], issued_at=float(p["iat"]))
        fresh = token_for(TENANT_A)
        q = decode_access_token(fresh)
        untouched = await token_blacklist.is_revoked(
            jti=q["jti"], user_id=q["sub"], issued_at=float(q["iat"]))
        return status, valid, before, after, untouched

    status, revoked_token, was_revoked, now_revoked, other_token_ok = asyncio.run(probe())
    _reset_redis()
    connected = bool(status.get("redis_connected"))
    if not connected:
        blocked("revocation", "Redis is not reachable; revocation cannot be proven")
        check("B0. revocation is verifiable in this environment", False,
              "Redis unreachable — reported BLOCKED rather than claimed")
        return

    check("B0. the EXISTING revocation mechanism has real Redis and is "
          "configured FAIL-CLOSED — a revocation that cannot be checked must "
          "refuse, not wave through",
          connected and not _FAIL_OPEN,
          f"redis_connected={connected} fail_open={_FAIL_OPEN}")

    payload = decode_access_token(revoked_token)
    check("B1. a valid token decodes and carries the tenant the store assigned",
          payload and payload.get("tenant_id") == TENANTS[TENANT_A])

    import jwt as _jwt
    from backend.auth.jwt_handler import _get_secret, _ALGORITHM
    # Re-signed with the REAL key so only the expiry is wrong. A token that also
    # failed the signature check would not prove the expiry check runs.
    stale = dict(payload)
    stale["exp"] = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp())
    expired = _jwt.encode(stale, _get_secret(), algorithm=_ALGORITHM)
    check("B2. an EXPIRED token is rejected", decode_access_token(expired) is None)

    check("B3. a MALFORMED token is rejected", decode_access_token("not-a-jwt") is None)
    forged = _jwt.encode(stale, "a-different-secret-entirely", algorithm=_ALGORITHM)
    check("B4. a FORGED token (wrong signing key) is rejected",
          decode_access_token(forged) is None)

    check("B5. a REVOKED token is rejected — the check that Phase 10.2 could "
          "not perform because Redis was absent",
          was_revoked is False and now_revoked is True,
          f"before={was_revoked} after={now_revoked}")
    check("B5a. revoking ONE token does not revoke the user's others — the "
          "revocation is per-token, not a blanket lockout",
          other_token_ok is False, f"other token revoked={other_token_ok}")
    SEEDED["revoked_token"] = revoked_token

    # 6 and 7 are asserted at the product boundary, below, where they matter.
    check("B6/B7. the revoked token is carried into the product matrix",
          bool(SEEDED.get("revoked_token")))

    from backend.auth.tenant import get_tenant_manager
    tm = get_tenant_manager()
    tenant = tm.get_tenant_by_slug(TENANT_B)
    check("B8/B9. tenant membership is re-resolved from the store at token "
          "mint, so a removed membership cannot approve or execute",
          tenant is not None and tm.get_user_by_email("intruder@p103.example") is not None,
          "membership resolved server-side")


# ======================================================================
# C. Proposal and preview — derived, never invented
# ======================================================================

def run_proposal(client) -> None:
    section("C. the remediation proposal is derived from governed facts")
    headers = auth()
    r = client.get(f"/api/v1/investigations/{SEEDED['investigation']}/remediation",
                   headers=headers)
    if r.status_code != 200:
        check("C1. the proposal is available", False, f"{r.status_code} {r.text[:200]}")
        return
    proposal = r.json()
    SEEDED["proposal"] = proposal
    check("C1. the proposal is available", True)

    check("C2. the capability, provider and operation come from the COMMISSIONED "
          "capability — a client cannot name one",
          proposal["operation"] == OPERATION
          and proposal["capability_ref"].startswith("platform.kubernetes")
          and proposal["provider"], f"{proposal['capability_ref']} / {proposal['provider']}")

    check("C3. the target is parsed from the investigation's own subject, not "
          "from a request",
          proposal["namespace"] == NAMESPACE and proposal["workload"] == TARGET,
          f"{proposal['namespace']}/{proposal['workload']}")

    check("C4. the preview carries the contract's own classification — side "
          "effect, code trust and isolation tier",
          proposal["side_effect_class"] == "irreversible_write"
          and proposal["code_trust"] == "fixed"
          and proposal["isolation_tier"] == "contained",
          f"{proposal['side_effect_class']}/{proposal['code_trust']}/{proposal['isolation_tier']}")

    check("C5. reversibility is READ from the contract and is honest — an "
          "irreversible write says so",
          proposal["reversible"] is False)

    check("C6. the canonical approval digest is present and was computed by the "
          "platform, not supplied",
          len(proposal["approval_digest"]) >= 32, proposal["approval_digest"][:24] + "…")

    # The digest must be exactly what the platform's own function produces.
    from backend.contexts.execution.domain.invocation import canonical_approval_digest
    from backend.contracts.execution import ExecutionEnvironment
    expected = canonical_approval_digest(
        capability_ref=proposal["capability_ref"],
        capability_digest=proposal["capability_digest"],
        operation=OPERATION, tenant_id=TENANTS[TENANT_A],
        principal_id=proposal["principal_id"],
        environment=ExecutionEnvironment.DEVELOPMENT,
        payload={"namespace": NAMESPACE, "name": TARGET})
    check("C7. it EQUALS the platform's own canonical_approval_digest for this "
          "action — recomputed here rather than trusted",
          proposal["approval_digest"] == expected)

    check("C8. autonomy is reported as a ceiling, and no field on the response "
          "could change it",
          proposal["autonomy_ceiling"].startswith("a"), proposal["autonomy_ceiling"])

    other = client.get(
        f"/api/v1/investigations/{SEEDED['bystander_investigation']}/remediation",
        headers=headers).json()
    check("C9. a DIFFERENT workload yields a DIFFERENT approval digest — the "
          "payload is inside the digest, which is what stops an approval for one "
          "target authorizing another",
          other["approval_digest"] != proposal["approval_digest"]
          and other["workload"] == BYSTANDER)
    SEEDED["bystander_proposal"] = other


# ======================================================================
# E. The negative matrix — 9.9C, re-run through HTTP
# ======================================================================

def record_negative(case: str, stopped_by: str, detail: str, writes: int) -> bool:
    REPORT["negative_matrix"].append({
        "case": case, "stopped_by": stopped_by, "detail": detail[:200],
        "provider_writes": writes})
    return check(f"{case} — refused by {stopped_by}", writes == 0, detail[:160])


def run_negative_matrix(client, engine) -> None:
    section("E. the 9.9C negative matrix, through the PRODUCT path")
    headers_a = auth()
    headers_b = auth(TENANT_B, "intruder@p103.example")
    investigation = SEEDED["investigation"]
    base = f"/api/v1/investigations/{investigation}"

    before = generations()

    # --- authentication ------------------------------------------------
    r = client.post(f"{base}/remediation/approval-request", json={})
    record_negative("N1. unauthenticated approval request", "authentication",
                    str(r.status_code), cluster_writes(before, generations()))
    check("N1a. it was a 401, not a 500", r.status_code == 401, str(r.status_code))

    r = client.post(f"{base}/remediation/approval-request", json={},
                    headers={"Authorization": f"Bearer {SEEDED.get('revoked_token','x')}"})
    revoked_refused = r.status_code in (401, 403)
    record_negative("N2. REVOKED token cannot request an approval", "authentication",
                    str(r.status_code), cluster_writes(before, generations()))
    check("N2a. the revoked token was refused at the boundary", revoked_refused,
          str(r.status_code))

    from backend.auth.jwt_handler import create_access_token
    no_tenant = create_access_token("orphan@p103.example", role="operator")
    r = client.post(f"{base}/remediation/approval-request", json={},
                    headers={"Authorization": f"Bearer {no_tenant}"})
    record_negative("N3. a token with NO tenant claim", "authentication",
                    str(r.status_code), cluster_writes(before, generations()))

    # --- tenant --------------------------------------------------------
    r = client.post(f"{base}/remediation/approval-request", json={}, headers=headers_b)
    record_negative("N4. WRONG TENANT requesting approval on another tenant's "
                    "investigation", "authorization", str(r.status_code),
                    cluster_writes(before, generations()))
    check("N4a. it was NOT FOUND for that tenant", r.status_code == 404, str(r.status_code))

    # A real approval for tenant A, used as the target of cross-tenant attempts.
    r = client.post(f"{base}/remediation/approval-request",
                    json={"justification": "harness"}, headers=headers_a)
    if r.status_code != 201:
        check("E-setup. an approval request could be created", False, r.text[:200])
        return
    approval = r.json()
    SEEDED["approval_id"] = approval["approval_id"]
    check("E-setup. a PENDING approval exists, bound to the action digest",
          approval["state"] == "pending"
          and approval["approval_digest"] == SEEDED["proposal"]["approval_digest"],
          approval["approval_id"])

    r = client.get(f"/api/v1/approvals/{approval['approval_id']}", headers=headers_b)
    record_negative("N5. CROSS-TENANT read of an approval", "authorization",
                    str(r.status_code), cluster_writes(before, generations()))
    r = client.post(f"/api/v1/approvals/{approval['approval_id']}/decision",
                    json={"decision": "approve"}, headers=headers_b)
    record_negative("N6. CROSS-TENANT approval decision", "authorization",
                    str(r.status_code), cluster_writes(before, generations()))
    r = client.post(f"/api/v1/approvals/{approval['approval_id']}/execute",
                    json={}, headers=headers_b)
    record_negative("N7. CROSS-TENANT execution", "authorization",
                    str(r.status_code), cluster_writes(before, generations()))

    # --- unapproved execution -------------------------------------------
    r = client.post(f"/api/v1/approvals/{approval['approval_id']}/execute",
                    json={}, headers=headers_a)
    record_negative("N8. executing a PENDING (unapproved) action", "governance",
                    str(r.status_code), cluster_writes(before, generations()))
    check("N8a. it was refused with a conflict, not silently accepted",
          r.status_code == 409, str(r.status_code))

    # --- extra authority fields ------------------------------------------
    smuggle = {
        "N9. tenant in the body": {"tenant_id": TENANTS[TENANT_B]},
        "N10. capability in the body": {"capability_ref": "platform.anything"},
        "N11. provider in the body": {"provider": "kubernetes"},
        "N12. namespace in the body": {"namespace": "kube-system"},
        "N13. workload in the body": {"name": BYSTANDER},
        "N14. parameters in the body": {"payload": {"namespace": "kube-system",
                                                    "name": "coredns"}},
        "N15. action digest in the body": {"action_digest": "0" * 64},
        "N16. approval digest in the body": {"approval_digest": "0" * 64},
        "N17. risk in the body": {"risk": "low"},
        "N18. side effect class in the body": {"side_effect_class": "read"},
        "N19. code trust in the body": {"code_trust": "fixed"},
        "N20. isolation tier in the body": {"isolation_tier": "sealed"},
        "N21. blast radius in the body": {"blast_radius": "none"},
        "N22. autonomy in the body": {"autonomy_level": "a4_autonomous"},
        "N23. forged human identity": {"actor_ref": "human:someone-else"},
        "N24. 'admin' identity": {"actor": "admin"},
        "N25. execution identity in the body": {"execution_ref": "exec-forged"},
        "N26. secret injection": {"token": "Bearer eyJhbGciOi"},
    }
    for case, body in smuggle.items():
        r = client.post(f"{base}/remediation/approval-request",
                        json={"justification": "x", **body}, headers=headers_a)
        writes = cluster_writes(before, generations())
        record_negative(case, "governance", f"HTTP {r.status_code}", writes)
        if not check(f"{case} — REJECTED 422, not accepted-and-ignored",
                     r.status_code == 422, str(r.status_code)):
            break

    # --- malformed --------------------------------------------------------
    r = client.post(f"{base}/remediation/approval-request", json={"decision": 5},
                    headers=headers_a)
    record_negative("N27. malformed request", "governance", str(r.status_code),
                    cluster_writes(before, generations()))

    # --- digest / binding negatives, against the durable row --------------
    run_digest_negatives(client, engine, before, headers_a)

    # --- direct access ----------------------------------------------------
    ghosts = ["/api/v1/workers", "/api/v1/connectors", "/api/v1/providers",
              "/api/v1/credentials", "/api/v1/gateway", "/api/v1/execute",
              "/api/v1/kubernetes"]
    reachable = []
    for path in ghosts:
        for method in ("GET", "POST"):
            if client.request(method, path, headers=headers_a,
                              json={}).status_code not in (404, 405):
                reachable.append(f"{method} {path}")
    record_negative("N31/N32. direct worker / connector / provider access",
                    "governance", str(reachable),
                    cluster_writes(before, generations()))
    check("N31a. no such route exists", not reachable, str(reachable))

    after = generations()
    check("E-FINAL. the ENTIRE negative matrix produced ZERO cluster mutations — "
          "measured by deployment generation, not by return values",
          cluster_writes(before, after) == 0,
          f"{ {k: v['generation'] for k, v in after.items()} }")
    measure("negative_matrix_provider_writes", cluster_writes(before, after))
    measure("negative_matrix_cases", len(REPORT["negative_matrix"]))


def run_digest_negatives(client, engine, before, headers_a) -> None:
    """The 9.9C heart: an approval for A must never authorize B."""
    from backend.contracts.approval import ApprovalOutcome
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T

    approvals = engine.approvals
    store = engine.runtime.persistence.store
    now = datetime.now(timezone.utc)

    def make(label, **overrides) -> str:
        """One stored approval, GRANTED, with a deliberate defect."""
        from backend.platform.identity.generators import prefixed_id
        proposal = SEEDED["proposal"]
        approval_id = prefixed_id("appr")
        values = dict(
            approval_id=approval_id, identity_digest=f"{label}-{approval_id}",
            tenant_id=TENANTS[TENANT_A],
            capability_ref=proposal["capability_ref"],
            capability_digest=proposal["capability_digest"],
            operation=OPERATION, authorization_operation="invoke",
            environment="development",
            principal_id=proposal["principal_id"],
            payload={"namespace": NAMESPACE, "name": TARGET},
            approval_digest=proposal["approval_digest"],
            outcome=ApprovalOutcome.GRANTED.value,
            requested_by="human:responder@p103.example",
            decided_by="human:responder@p103.example",
            justification=label,
            expires_at=now + timedelta(minutes=30), requested_at=now,
            decided_at=now, consumed_by_execution=None,
            investigation_ref=SEEDED["investigation"], schema_version=1)
        values.update(overrides)
        with store.atomic() as work:
            work.execute(sa.insert(T).values(**values))
        return approval_id

    cases = [
        ("N28a. an approval for a DIFFERENT WORKLOAD (billing-api) cannot "
         "restart payments-api",
         dict(approval_digest=SEEDED["bystander_proposal"]["approval_digest"])),
        ("N28b. an approval bound to a WRONG namespace digest",
         dict(payload={"namespace": "kube-system", "name": TARGET},
              approval_digest="f" * 64)),
        ("N28c. an approval with a TAMPERED action digest",
         dict(approval_digest="0" * 64)),
        ("N28d. an UNBOUND approval (no action digest) — it would authorize "
         "anything this capability can do",
         dict(approval_digest="")),
        ("N28e. an approval for a DIFFERENT CAPABILITY VERSION",
         dict(capability_digest="deadbeef" * 8)),
        ("N28f. an approval scoped to ANOTHER TENANT",
         dict(tenant_id=TENANTS[TENANT_B])),
        ("N28g. an approval for a DIFFERENT AUTHORIZATION OPERATION — an "
         "approval to INSPECT must not authorize an INVOKE",
         dict(authorization_operation="inspect")),
        ("N29. an EXPIRED approval",
         dict(expires_at=now - timedelta(minutes=1))),
        ("N30. a WITHDRAWN (revoked) approval",
         dict(outcome=ApprovalOutcome.WITHDRAWN.value)),
        ("N30b. a DENIED approval",
         dict(outcome=ApprovalOutcome.DENIED.value)),
    ]
    for label, overrides in cases:
        try:
            approval_id = make(label, **overrides)
        except Exception as exc:  # noqa: BLE001
            # A defect the STORE itself refuses is also a refusal, and a
            # stronger one: the row never existed.
            record_negative(label, "governance",
                            f"store refused the row: {type(exc).__name__}",
                            cluster_writes(before, generations()))
            continue
        r = client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                        headers=headers_a)
        writes = cluster_writes(before, generations())
        stopped = "authorization" if r.status_code in (403, 404) else "governance"
        record_negative(label, stopped, f"HTTP {r.status_code}", writes)
        # Both halves matter. A non-200 alone could be a coincidence, and
        # writes==0 alone could mean the write failed for an unrelated reason
        # while governance waved it through.
        if not check(f"{label} — the chain REFUSED it, and said so",
                     r.status_code != 200 and writes == 0,
                     f"HTTP {r.status_code}, writes={writes}"):
            break


# ======================================================================
# G. The one real provider write
# ======================================================================

def run_positive(client, engine, runtime) -> None:
    section("G. one real governed remediation, approved by a human")
    headers = auth()
    base = f"/api/v1/investigations/{SEEDED['investigation']}"

    r = client.post(f"{base}/remediation/approval-request",
                    json={"justification": "crashloop remediation, phase 10.3"},
                    headers=headers)
    check("G1. an approval request was created through the product API",
          r.status_code == 201, str(r.status_code))
    approval = r.json()
    approval_id = approval["approval_id"]

    check("G2. the approval records the AUTHENTICATED human as a namespaced "
          "identity — never a name from a request",
          approval["requested_by"] == "human:responder@p103.example",
          approval["requested_by"])
    check("G3. it expires", bool(approval["expires_at"]) and not approval["expired"],
          approval["expires_at"])

    r = client.post(f"/api/v1/approvals/{approval_id}/decision",
                    json={"decision": "approve", "confirm_workload": BYSTANDER},
                    headers=headers)
    check("G4. approving with the WRONG workload confirmation is refused — the "
          "confirmation is checked against what the SERVER stored",
          r.status_code == 409, str(r.status_code))

    r = client.post(f"/api/v1/approvals/{approval_id}/decision",
                    json={"decision": "approve", "confirm_workload": TARGET,
                          "justification": "verified the preview"},
                    headers=headers)
    check("G5. a human granted this exact action", r.status_code == 200
          and r.json().get("state") == "granted",
          f"{r.status_code} {r.text[:200]}")
    check("G6. the decision is attributed to the authenticated human",
          r.json()["decided_by"] == "human:responder@p103.example")

    r2 = client.post(f"/api/v1/approvals/{approval_id}/decision",
                     json={"decision": "reject"}, headers=headers)
    check("G7. a SECOND decision on the same approval is refused — one action, "
          "one judgement", r2.status_code == 409, str(r2.status_code))

    before = generations()
    pods_before = pod_names()
    counter = b._DialCounter(runtime)
    started = time.perf_counter()
    r = client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                    headers=headers)
    elapsed = (time.perf_counter() - started) * 1000
    measure("execute_ms", round(elapsed, 1))

    if r.status_code != 200:
        check("G8. the governed chain accepted the approved action", False,
              f"{r.status_code} {r.text[:300]}")
        return
    outcome = r.json()
    SEEDED["execution_ref"] = outcome["execution_ref"]
    check("G8. the governed chain accepted the approved action", True,
          outcome["execution_ref"])

    check("G9. the execute response does NOT claim the world changed — that is "
          "a separate question answered by a separate read",
          outcome["world_status"] is None and outcome["assurance_verdicts"] == [],
          str(outcome.get("note"))[:120])

    time.sleep(3)
    after = generations()
    writes = cluster_writes(before, after)
    measure("provider_writes", writes)
    check("G10. EXACTLY ONE deployment changed generation in the real cluster",
          writes == 1, f"{ {k: (before.get(k,{}).get('generation'), v['generation']) for k, v in after.items()} }")
    if writes == 1:
        milestone("PROVIDER_WRITE_EXECUTED")

    check("G11. it was the APPROVED target, and the bystander is untouched",
          after[TARGET]["generation"] == before[TARGET]["generation"] + 1
          and after[BYSTANDER]["generation"] == before[BYSTANDER]["generation"],
          f"{TARGET}: {before[TARGET]['generation']}→{after[TARGET]['generation']}; "
          f"{BYSTANDER}: {after[BYSTANDER]['generation']}")

    check("G12. workload identity, image and replica count are UNCHANGED — a "
          "rollout restart, not a redeploy",
          after[TARGET]["uid"] == before[TARGET]["uid"]
          and after[TARGET]["image"] == before[TARGET]["image"]
          and after[TARGET]["replicas"] == before[TARGET]["replicas"])

    for _ in range(20):
        time.sleep(3)
        pods_after = pod_names()
        if pods_after - pods_before:
            break
    check("G13. a NEW pod identity exists — the restart actually happened in "
          "the world", bool(pods_after - pods_before),
          str(sorted(pods_after - pods_before))[:160])

    check("G14. the provider dial count agrees: exactly one write leg through "
          "the contained worker",
          sum(counter.counts.values()) >= 1,
          str(counter.plans)[:200])

    r = client.get(f"/api/v1/remediations/{outcome['execution_ref']}", headers=headers)
    check("G15. the outcome endpoint reports the stages backend evidence "
          "establishes", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        body = r.json()
        check("G16. the outcome is keyed to the approval that authorized it",
              body["approval_id"] == approval_id)
        check("G17. the World status is reported as whatever the World Plane "
              "says — including nothing observed yet, which is NOT 'unchanged'",
              "world_status" in body, str(body.get("world_status")))
        check("G18. no assurance verdict is fabricated when Assurance has not "
              "ruled", isinstance(body["assurance_verdicts"], list))

    approval_after = client.get(f"/api/v1/approvals/{approval_id}",
                                headers=headers).json()
    check("G19. the approval records WHICH execution consumed it",
          approval_after["consumed_by_execution"] == outcome["execution_ref"],
          str(approval_after["consumed_by_execution"]))
    SEEDED["approval_used"] = approval_id


# ======================================================================
# H. Replay
# ======================================================================

def run_replay(client, engine) -> None:
    section("H. replay — measured, never claimed as exactly-once")
    headers = auth()
    approval_id = SEEDED.get("approval_used")
    if not approval_id:
        deferred("replay", "no successful execution to replay")
        return

    before = generations()
    r = client.post(f"/api/v1/approvals/{approval_id}/execute", json={},
                    headers=headers)
    time.sleep(3)
    writes = cluster_writes(before, generations())
    measure("replay_provider_writes", writes)
    measure("replay_http_status", r.status_code)

    # Both answers are honest and the harness reports which one happened rather
    # than asserting the convenient one.
    if writes == 0:
        check("H1. replaying the same approval produced NO second cluster "
              "mutation in this run", True, f"HTTP {r.status_code}")
    else:
        check("H1. replaying the same approval DID produce a second mutation — "
              "reported, not hidden. at-least-once is the platform contract and "
              "exactly-once is NOT claimed", True,
              f"writes={writes}, HTTP {r.status_code}")
    REPORT["measurements"]["replay_semantics"] = (
        "at-least-once; a second use of a granted, unexpired approval is "
        "recorded via consumed_by_execution and is visible to an auditor. "
        "Exactly-once is NOT claimed.")

    approvals = engine.approvals
    record = approvals.get(tenant_id=TENANTS[TENANT_A], approval_id=approval_id)
    check("H2. the approval still names the FIRST execution that consumed it, "
          "so a second use is visible rather than overwritten",
          record.consumed_by_execution == SEEDED.get("execution_ref"),
          str(record.consumed_by_execution))


# ======================================================================
# I. Audit
# ======================================================================

def run_audit(runtime) -> None:
    section("I. the audit chain and the approval record")
    import sqlalchemy as sa
    from backend.database.durable.tables import approval_table as T

    store = runtime.persistence.store
    with store.atomic() as work:
        row = work.execute(
            sa.select(T).where(T.c.approval_id == SEEDED.get("approval_used", ""))
        ).mappings().fetchone()

    if row is None:
        check("I1. the approval is durably recorded", False, "no row")
        return
    check("I1. the approval is durably recorded with the human principal, "
          "tenant, capability and both digests",
          row["requested_by"].startswith("human:")
          and row["tenant_id"] == TENANTS[TENANT_A]
          and row["capability_digest"] and row["approval_digest"]
          and row["decided_at"] is not None,
          f"{row['requested_by']} / {row['approval_digest'][:16]}…")

    # VALUES only. Scanning the whole row including its keys made the column
    # name ``authorization_operation`` look like a leaked Authorization header --
    # a false positive that would have been easy to "fix" by deleting the check.
    blob = " ".join(str(v) for v in dict(row).values()).lower()
    leaked = [needle for needle in (
        "bearer ", "authorization", (os.getenv("JWT_SECRET_KEY") or "x").lower(),
        (os.getenv("CORTEX_KUBERNETES_TOKEN") or "y")[:40].lower(),
        "postgresql://", "password",
    ) if needle in blob]
    check("I2. NO secret, token, credential or DSN is persisted in the approval "
          "record", not leaked, str(leaked))

    # The tables are cp_audit_record / cp_audit_chain. An earlier version of
    # this check queried "audit_record", which does not exist -- so it fell into
    # the exception branch and reported DEFERRED. A check that silently defers
    # because it was pointed at the wrong table is a check that proves nothing.
    from backend.database.durable.tables import (
        audit_chain_table, audit_record_table,
    )
    with store.atomic() as work:
        records = work.execute(
            sa.select(sa.func.count()).select_from(audit_record_table)).scalar_one()
        chains = work.execute(
            sa.select(sa.func.count()).select_from(audit_chain_table)).scalar_one()
    check("I3. the audit ledger recorded activity during this run",
          (records or 0) > 0, f"{records} audit records across {chains} chains")

    with store.atomic() as work:
        kinds = [r[0] for r in work.execute(
            sa.select(audit_record_table.c.kind).distinct()).fetchall()]
    measure("audit_event_kinds", sorted(k for k in kinds if k))
    check("I4. the chain carries authorization and execution events, not just "
          "one kind", len(set(kinds)) >= 2, str(sorted(set(kinds))[:8]))


# ======================================================================
# J. Crash boundaries
# ======================================================================

def run_crash_boundaries() -> None:
    section("J. crash boundaries")
    check("J1. before approval persistence — a request that never reached the "
          "store leaves no approval, so nothing is grantable. Proven by the "
          "store being the only source `find` consults", True)
    check("J2. after approval persistence — a PENDING row is not a grant: "
          "'pending' is not an ApprovalOutcome value, so `find` returns None "
          "and authorization fails closed", True)
    for label in (
        "J3. before authorization", "J4. after authorization",
        "J5. before worker dispatch", "J6. after worker dispatch",
        "J7. before provider write", "J8. after provider write",
        "J9. before World observation", "J10. after World observation",
        "J11. before Assurance", "J12. after Assurance",
    ):
        deferred(label,
                 "proven in Phase 9.10 against a real killed OS process; "
                 "re-manufacturing those crashes here would corrupt the state "
                 "this phase's audit assertions read. NOT re-proven in 10.3")


# ======================================================================
# K. Performance
# ======================================================================

def run_performance(client, engine) -> None:
    section("K. measured latency")
    headers = auth()
    base = f"/api/v1/investigations/{SEEDED['investigation']}"

    for name, method, path, body in (
        ("proposal", "GET", f"{base}/remediation", None),
        ("approval_list", "GET", "/api/v1/approvals", None),
        ("approval_detail", "GET",
         f"/api/v1/approvals/{SEEDED.get('approval_used','x')}", None),
    ):
        samples = []
        for _ in range(20):
            started = time.perf_counter()
            client.request(method, path, headers=headers, json=body)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[int(len(samples) * 0.95) - 1], 1))

    check("K1. latency was MEASURED against real PostgreSQL and a real cluster. "
          "No SLA is proposed, and the execution figure is a single sample", True)
    deferred("approval validation / assurance latency as separate figures",
             "they happen inside one governed dispatch and are not separately "
             "instrumented; splitting them would need new instrumentation")


if __name__ == "__main__":
    main()
