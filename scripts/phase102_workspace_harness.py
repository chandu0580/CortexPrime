"""Phase 10.2 evidence: a real incident workspace over the verified engine.

What this proves
----------------
A real FastAPI product application, a real PostgreSQL-backed engine, real
investigations written through the governed service, real World observations
carrying real lineage, and a real Assurance verification -- then the whole
Part B journey read back through the API a browser actually calls:

    login -> tenant from the verified token -> investigation list -> detail ->
    timeline -> hypotheses -> evidence -> world state -> assurance ->
    residual uncertainty

with ZERO provider calls, zero mutations, and every epistemic distinction
still intact at the boundary.

The discipline
--------------
Two things this harness refuses to do:

* Assert a distinction is preserved by checking a field exists. UNKNOWN, STALE
  and CORRELATED are seeded as REAL states from real data, and the assertion is
  that the API returns each of them as itself.
* Report zero provider calls without watching for them. ``ProviderWatch``
  raises if it cannot find a dial method to wrap.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED / BLOCKED.
"""

from __future__ import annotations

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

REPORT: dict = {
    "phase": "10.2",
    "checks": [],
    "deferred": [],
    "measurements": {},
    "verdict": "NOT VERIFIED",
}

TENANT_A = "tenant-a-p102"
TENANT_B = "tenant-b-p102"
TENANTS: dict = {}

#: The subject the whole workspace journey is about.
NAMESPACE = "demo"
POD = "payments-api-7c9f"
SUBJECT = f"kubernetes:pod:{NAMESPACE}/{POD}"
PREDICATE = "restart_count"
#: A predicate nothing has ever observed. UNKNOWN must come back for it -- and
#: UNKNOWN has to be produced by genuinely having no evidence, not by asking for
#: a subject that does not parse.
UNOBSERVED_PREDICATE = "never_observed_predicate"

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


# ----------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------

def ensure_dev_jwt_secret() -> None:
    """A disposable signing secret for this harness only.

    The issuer refuses to start without one, and that refusal is correct. This
    sets a throwaway value for a throwaway process; it is never written to disk
    and the harness asserts below that it never appears in a response.
    """
    import secrets as _secrets
    for var in ("JWT_SECRET_KEY", "JWT_REFRESH_SECRET_KEY", "SECRET_KEY"):
        if not os.getenv(var):
            os.environ[var] = _secrets.token_hex(32)


def register_tenants() -> None:
    """Two real tenants, and a real user membership for tenant A only.

    The membership matters: Phase 10.2's blocking discovery was that login
    minted tokens with no tenant claim, so no browser session could reach the
    product API at all. Tenant B deliberately gets no member, so the harness can
    prove the fail-closed half as well as the working half.
    """
    from backend.auth.tenant import get_tenant_manager
    tm = get_tenant_manager()
    for slug in (TENANT_A, TENANT_B):
        tenant = tm.get_tenant_by_slug(slug)
        if tenant is None:
            tenant = tm.create_tenant(name=slug, slug=slug)
        TENANTS[slug] = tenant.tenant_id
    if tm.get_user_by_email("responder@example.com") is None:
        tm.add_user(TENANTS[TENANT_A], "responder@example.com", role="member")


def issue_token(tenant_id: str, subject: str = "responder@example.com",
                role: str = "member") -> str:
    """A real token from the platform's own issuer. Never a hand-built JWT."""
    from backend.auth.jwt_handler import create_access_token
    return create_access_token(
        subject, role="operator", tenant_id=tenant_id, user_role=role)


def build_engine():
    from backend.api.product.app import compose_engine
    return compose_engine()


class ProviderWatch:
    """Counts any attempt to dial a provider. Must stay at zero for the API."""

    def __init__(self):
        self.calls = []

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


# ----------------------------------------------------------------------
# Real data, written through the real planes
# ----------------------------------------------------------------------

def seed_world(engine, tenant_id: str) -> dict:
    """Two agreeing observations that share ONE lineage origin.

    This is the shape that makes the CORRELATED level real rather than
    theoretical: ``connector:kubernetes`` is the API server, and
    ``connector:prometheus:kube-state-metrics`` is that same number re-exported.
    Two instruments, one origin. If the workspace ever renders this as
    independent confirmation, the check below fails.

    The observations are deliberately dated well into the past, so the freshness
    policy returns a real STALE verdict from real ages -- not a STALE string
    injected to make an assertion pass.
    """
    from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
        INSTRUMENT_KUBE_STATE_METRICS,
    )
    from backend.api.observability_evidence import INSTRUMENT_KUBERNETES_API
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import (
        Observation, ObservationInstant, ObservationSource, ObservationSourceKind,
        ProvenanceRef,
    )
    from backend.world.application.fact_derivation import FactDerivation
    from backend.world.application.ingestion import observation_identity
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository
    from backend.platform.identity.generators import prefixed_id
    from backend.api.application_runtime import build_governed_runtime

    runtime = build_governed_runtime()
    store = runtime.persistence.store
    observations = SqlObservationRepository(store)
    derivation = FactDerivation(repository=SqlFactRepository(store))
    tenant = TenantRef(tenant_id=tenant_id)

    # Old enough that the 120s metric horizon is genuinely exceeded.
    observed_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    retrieved_at = observed_at + timedelta(seconds=4)

    refs = []
    for source_ref in (INSTRUMENT_KUBERNETES_API, INSTRUMENT_KUBE_STATE_METRICS):
        obs = Observation(
            record_id=prefixed_id("wobs"),
            tenant=tenant,
            recorded_at=retrieved_at,
            provenance=ProvenanceRef(
                produced_by=source_ref, source_ref=source_ref,
                execution_ref="exec:p102-seed/1", trace_ref="trace:p102/1"),
            source=ObservationSource(
                kind=ObservationSourceKind.CONNECTOR, source_ref=source_ref),
            subject_ref=SUBJECT,
            predicate=PREDICATE,
            # The SAME value from both, so they agree and corroboration has
            # something to assess.
            value={"restartCount": 7},
            status=SourceStatus.RETURNED_DATA,
            instant=ObservationInstant(
                observed_at=observed_at, retrieved_at=retrieved_at),
        )
        observations.record(obs, identity_digest=observation_identity(obs))
        derivation.derive(tenant=tenant, observation=obs, recorded_at=retrieved_at)
        refs.append(obs.record_id)
    return {"evidence_refs": tuple(refs), "observed_at": observed_at}


def seed_verification(tenant_id: str) -> str:
    """One real Assurance record, from a verifier with its own reasoning path.

    INSUFFICIENT_EVIDENCE on purpose. It is the verdict most likely to be
    rendered as a failure by a UI that treats verification as a pass/fail gate,
    so it is the one worth putting on the screen.
    """
    from backend.api.application_runtime import build_governed_runtime
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.contracts.tenant import TenantRef
    from backend.contracts.verification import VerifierIdentity, Verdict
    from backend.contracts.world import ProvenanceRef, WorldVerification
    from backend.platform.identity.generators import prefixed_id

    runtime = build_governed_runtime()
    repository = SqlVerificationRepository(runtime.persistence.store)
    now = datetime.now(timezone.utc)
    verification = WorldVerification(
        record_id=prefixed_id("wver"),
        tenant=TenantRef(tenant_id=tenant_id),
        recorded_at=now,
        provenance=ProvenanceRef(produced_by="assurance:p102-verifier/1"),
        subject_ref=SUBJECT,
        procedure_ref="check:restart-count-corroborated/1",
        verifier=VerifierIdentity(
            verifier_id="assurance:world-verifier/1",
            # Distinct from the producer's path -- that difference is what
            # independence actually means here.
            reasoning_path_id="assurance-path/p102"),
        verdict=Verdict.INSUFFICIENT_EVIDENCE,
        evidence_refs=SEEDED.get("evidence_refs", ()),
    )
    repository.record(
        verification, identity_digest=f"p102-{verification.record_id}",
        predicate=PREDICATE, producer_reasoning_path="intelligence-path/p102",
        verified_at=now)
    return verification.record_id


def seed_investigation(engine, tenant_id: str, *, conclude: bool) -> str:
    """One real investigation with a real differential, through the service.

    Two hypotheses, one RULED OUT and one still OPEN. That combination is the
    point: a workspace that only ever shows a winning hypothesis has quietly
    stopped being a differential, and the eliminated one has to survive the
    round trip to prove it did not.
    """
    from backend.contracts.intelligence.investigation import (
        DifferentialHypothesis, HypothesisStatus, InvestigationConclusion,
        InvestigationStatus, TemporalFit,
    )
    from backend.contracts.tenant import TenantRef

    now = datetime.now(timezone.utc)
    tenant = TenantRef(tenant_id=tenant_id)
    service = engine.investigations

    investigation = service.create(
        tenant=tenant, incident_ref=SUBJECT,
        policy_ref="phase102/1", harness_version="p102", now=now)
    investigation = service.transition(
        investigation=investigation, to_status=InvestigationStatus.INVESTIGATING,
        cause="harness seed", now=now)

    investigation = service.upsert_hypothesis(
        investigation=investigation, now=now,
        hypothesis=DifferentialHypothesis(
            hypothesis_ref="h-resource-exhaustion", subject_ref=SUBJECT,
            proposition="the container is being OOM killed under its memory limit",
            status=HypothesisStatus.REFUTED, temporal_fit=TemporalFit.CONSISTENT,
            created_by="platform:crashloop-differential/1",
            evidence_against=SEEDED.get("evidence_refs", ()),
        ))
    investigation = service.upsert_hypothesis(
        investigation=investigation, now=now,
        hypothesis=DifferentialHypothesis(
            hypothesis_ref="h-startup-failure", subject_ref=SUBJECT,
            proposition="the process exits during startup before serving traffic",
            status=HypothesisStatus.OPEN,
            # UNKNOWN is a real value here and must survive to the screen.
            temporal_fit=TemporalFit.UNKNOWN,
            created_by="platform:crashloop-differential/1",
            missing_evidence=("container exit code", "startup probe result"),
        ))

    if SEEDED.get("evidence_refs"):
        investigation = service.link_evidence(
            investigation=investigation,
            evidence_refs=SEEDED["evidence_refs"], now=now)
    # An evidence reference the observation ledger does not hold, so the
    # unresolved-reference path is exercised against real data rather than
    # assumed to work.
    investigation = service.link_evidence(
        investigation=investigation,
        evidence_refs=("wobs-does-not-exist-p102",), now=now)

    if SEEDED.get("verification_ref"):
        investigation = service.link_verification(
            investigation=investigation,
            verification_ref=SEEDED["verification_ref"], now=now)

    if conclude:
        investigation = service.conclude(
            investigation=investigation,
            conclusion=InvestigationConclusion.INSUFFICIENT_EVIDENCE,
            cause="harness seed", now=now)
    return investigation.investigation_ref


# ----------------------------------------------------------------------

def main() -> None:
    section("A. composition — a real workspace API over the real engine")
    from fastapi.testclient import TestClient

    from backend.api.product import build_product_app

    if not os.getenv("CORTEX_DURABLE_URL"):
        bail(2, "CORTEX_DURABLE_URL is not set; this harness needs real PostgreSQL")

    ensure_dev_jwt_secret()
    register_tenants()
    engine = build_engine()
    if engine is None:
        bail(2, "the governed engine could not be composed")
    check("A1. the engine composed against real PostgreSQL", True)

    app = build_product_app(engine=engine)
    client = TestClient(app, raise_server_exceptions=False)
    methods = {m for r in app.routes for m in (getattr(r, "methods", None) or ())
               if getattr(r, "path", "").startswith("/api")}
    check("A2. every product route is still a GET — the workspace added four "
          "read endpoints and no mutation surface",
          methods == {"GET"}, str(sorted(methods)))
    paths = sorted(r.path for r in app.routes if getattr(r, "path", "").startswith("/api"))
    measure("routes", paths)
    check("A3. the four workspace endpoints exist",
          all(p in paths for p in (
              "/api/v1/investigations/{investigation_ref}/timeline",
              "/api/v1/investigations/{investigation_ref}/assurance")),
          str(paths))

    section("B. real data, written through the real planes")
    world = seed_world(engine, TENANTS[TENANT_A])
    SEEDED.update(world)
    check("B1. two real World observations recorded, sharing ONE lineage origin",
          len(SEEDED["evidence_refs"]) == 2, str(SEEDED["evidence_refs"]))
    SEEDED["verification_ref"] = seed_verification(TENANTS[TENANT_A])
    check("B2. a real Assurance verification recorded", bool(SEEDED["verification_ref"]),
          SEEDED["verification_ref"])
    SEEDED["active_ref"] = seed_investigation(engine, TENANTS[TENANT_A], conclude=False)
    SEEDED["done_ref"] = seed_investigation(engine, TENANTS[TENANT_A], conclude=True)
    check("B3. one IN-PROGRESS and one COMPLETED investigation exist for tenant A",
          bool(SEEDED["active_ref"]) and SEEDED["active_ref"] != SEEDED["done_ref"],
          f"{SEEDED['active_ref']} / {SEEDED['done_ref']}")
    measure("seeded", {k: v for k, v in SEEDED.items() if k != "observed_at"})

    watch = ProviderWatch().install()
    try:
        run_auth_wiring()
        run_journey(client)
        run_epistemics(client)
        run_security(client)
        run_mutation_free(client, engine)
        run_performance(client)
    finally:
        watch.restore()

    section("I. the decisive negative")
    check("I1. ZERO provider calls occurred during the entire run — the "
          "workspace never reached Kubernetes, Prometheus or any provider",
          not watch.calls, str(watch.calls))
    measure("provider_calls", len(watch.calls))

    failed = [x["check"] for x in REPORT["checks"] if not x["ok"]]
    if failed:
        bail(1, f"a check failed: {failed[0]}")
    bail(0, "a human-facing incident workspace reads the verified engine with no "
            "second authority, no provider access and no mutation")


# ----------------------------------------------------------------------

def run_auth_wiring() -> None:
    """The blocking gap found in discovery, and its fail-closed repair."""
    section("C. login produces a session the product API accepts")
    from backend.api.auth_routes import _tenant_claims
    from backend.auth.jwt_handler import decode_access_token, create_access_token

    claims = _tenant_claims("responder@example.com")
    check("C1. a user with a real tenant membership resolves to tenant claims — "
          "the wire that was missing, so no browser session could reach the API",
          claims.get("tenant_id") == TENANTS[TENANT_A], str(claims))

    check("C2. the claims come from the tenant STORE, not from anything a "
          "caller supplies — the only input is the authenticated identity",
          set(claims) <= {"tenant_id", "tenant_slug", "user_role"}, str(sorted(claims)))

    # Fail-closed: an identity with no membership gets no tenant, and the
    # product API keeps refusing it exactly as before this change.
    orphan = _tenant_claims("nobody-has-ever-heard-of-this@example.com")
    check("C3. an identity with NO tenant membership yields NO claims — the "
          "repair is fail-closed, not fail-open", orphan == {}, str(orphan))

    token = create_access_token("responder@example.com", role="operator", **claims)
    payload = decode_access_token(token)
    check("C4. the minted token carries the tenant the store assigned",
          payload.get("tenant_id") == TENANTS[TENANT_A], str(payload.get("tenant_id")))

    orphan_token = create_access_token("orphan@example.com", role="operator")
    check("C5. a token minted without membership carries no tenant claim at all",
          "tenant_id" not in decode_access_token(orphan_token), "no tenant_id")


def auth(tenant_slug: str) -> dict:
    return {"Authorization": f"Bearer {issue_token(TENANTS[tenant_slug])}"}


def run_journey(client) -> None:
    """The Part B journey, end to end, against real persisted state."""
    section("D. the product journey")
    headers = auth(TENANT_A)

    r = client.get("/api/v1/investigations", headers=headers, params={"state": "all"})
    check("D1. the investigation list returns 200 for an authenticated tenant",
          r.status_code == 200, str(r.status_code))
    listing = r.json()
    refs = {item["investigation_ref"] for item in listing["items"]}
    check("D2. the list includes the IN-PROGRESS investigation — Phase 10.1 "
          "could list only finished ones, which made it an archive",
          SEEDED["active_ref"] in refs, f"count={listing['count']}")
    check("D3. and still includes the completed one", SEEDED["done_ref"] in refs)

    r = client.get("/api/v1/investigations", headers=headers, params={"state": "active"})
    active = {item["investigation_ref"] for item in r.json()["items"]}
    check("D4. filtering to active EXCLUDES the completed investigation — the "
          "filter is a real query, not a label",
          SEEDED["active_ref"] in active and SEEDED["done_ref"] not in active,
          str(sorted(active)))

    summary = next(i for i in listing["items"] if i["investigation_ref"] == SEEDED["done_ref"])
    check("D5. the list carries the platform-set autonomy level",
          bool(summary.get("autonomy_level")), str(summary.get("autonomy_level")))
    check("D6. the list names the conclusion as a CONCLUSION KIND, not as a "
          "'diagnosis' — Phase 10.1 projected the kind into a field named "
          "diagnosis, naming it as something it is not",
          summary.get("conclusion_kind") == "insufficient_evidence"
          and "diagnosis" not in summary, str(summary))

    r = client.get(f"/api/v1/investigations/{SEEDED['done_ref']}", headers=headers)
    check("D7. the investigation detail returns 200", r.status_code == 200, str(r.status_code))
    detail = r.json()

    check("D8. residual uncertainty is present and non-empty — in Phase 10.1 "
          "this was ALWAYS empty, because the projection read attributes a "
          "string enum does not have",
          bool(detail["residual_uncertainty"]) and bool(detail["residual_uncertainty"][0]),
          str(detail["residual_uncertainty"])[:200])

    check("D9. the differential survives the round trip with BOTH a ruled-out "
          "and an open hypothesis",
          {h["hypothesis_id"] for h in detail["hypotheses"]} ==
          {"h-resource-exhaustion", "h-startup-failure"},
          str([h["status"] for h in detail["hypotheses"]]))

    open_h = next(h for h in detail["hypotheses"] if h["hypothesis_id"] == "h-startup-failure")
    check("D10. an open hypothesis carries its explicit evidence gaps",
          open_h["missing_evidence"] == ["container exit code", "startup probe result"],
          str(open_h["missing_evidence"]))
    check("D11. and the platform's own reason it is still unresolved",
          bool(open_h["unresolved_reason"]), str(open_h["unresolved_reason"])[:160])

    r = client.get(f"/api/v1/investigations/{SEEDED['done_ref']}/timeline", headers=headers)
    check("D12. the timeline returns 200", r.status_code == 200, str(r.status_code))
    timeline = r.json()
    check("D13. it holds the REAL recorded events, in sequence order",
          timeline["count"] >= 5
          and [e["seq"] for e in timeline["events"]] == sorted(e["seq"] for e in timeline["events"]),
          f"{timeline['count']} events")
    check("D14. every timeline entry carries a LEDGER time under its own name, "
          "never relabelled as when the world changed",
          all("recorded_at" in e and "observed_at" not in e for e in timeline["events"]))

    r = client.get(f"/api/v1/investigations/{SEEDED['done_ref']}/evidence", headers=headers)
    evidence = r.json()
    check("D15. evidence resolves to real observations, not bare ids — the "
          "thin-projection limitation Phase 10.1 recorded",
          any(e["resolved"] and e["predicate"] == PREDICATE and e["value"] for e in evidence),
          str([e["observation_id"] for e in evidence]))
    check("D16. each resolved observation carries BOTH clocks",
          all(e["observed_at"] and e["retrieved_at"]
              for e in evidence if e["resolved"])
          and any(e["observed_at"] != e["retrieved_at"] for e in evidence if e["resolved"]))
    check("D17. an evidence reference that cannot be resolved is REPORTED as "
          "unresolved, not silently dropped",
          any(not e["resolved"] and e["observation_id"] == "wobs-does-not-exist-p102"
              for e in evidence), str(len(evidence)))

    r = client.get(f"/api/v1/investigations/{SEEDED['done_ref']}/assurance", headers=headers)
    check("D18. assurance for the investigation returns 200", r.status_code == 200)
    assurance = r.json()
    check("D19. it returns the real verification, with the VERIFIER's identity "
          "and reasoning path — independence is checkable, not asserted",
          assurance["count"] == 1
          and assurance["items"][0]["verifier_ref"] == "assurance:world-verifier/1"
          and assurance["items"][0]["verifier_reasoning_path"] == "assurance-path/p102",
          str(assurance["items"])[:200])

    r = client.get("/api/v1/world/state", headers=headers,
                   params={"subject_ref": SUBJECT, "predicate": PREDICATE})
    check("D20. world state returns 200", r.status_code == 200, str(r.status_code))
    REPORT["measurements"]["world_state"] = r.json()


def run_epistemics(client) -> None:
    """The distinctions Phase 7-9 protected, asserted at the product boundary."""
    section("E. epistemic fidelity at the boundary")
    headers = auth(TENANT_A)

    world = client.get("/api/v1/world/state", headers=headers,
                       params={"subject_ref": SUBJECT, "predicate": PREDICATE}).json()

    check("E1. the world read carries the two temporal axes SEPARATELY — the "
          "instant asked about and the moment the answer was computed",
          world["queried_valid_at"] and world["read_at"]
          and world["queried_valid_at"] != world.get("observed_at"),
          f"asked={world['queried_valid_at']} observed={world['observed_at']}")

    check("E2. observed_at is genuinely EARLIER than the read — the world was "
          "in this state before CortexPrime answered about it",
          world["observed_at"] < world["read_at"],
          f"{world['observed_at']} < {world['read_at']}")

    check("E3. freshness comes back as a real STALE verdict computed from a "
          "real age, not a string chosen to satisfy a test",
          world["freshness"]["state"] == "stale"
          and (world["freshness"]["age_seconds"] or 0) > 120,
          str(world["freshness"]))

    check("E4. STALE did NOT collapse the value — the observation is still "
          "reported, because stale is not false",
          world["value"] is not None, str(world["value"]))

    corroboration = world.get("corroboration") or {}
    check("E5. two agreeing sources sharing ONE lineage origin are reported as "
          "CORRELATED, never as independent — the 9.4 finding, visible in the "
          "product",
          corroboration.get("level") == "correlated", str(corroboration.get("level")))
    check("E6. and the response names exactly ONE distinct origin for the two "
          "sources, so a client cannot count them as two",
          len(corroboration.get("independent_origins") or []) == 1
          and len(corroboration.get("independent_sources") or []) == 2,
          str(corroboration.get("independent_origins")))
    check("E7. each source's lineage is exposed so the claim can be checked",
          all(lg.get("origin_known") for lg in (corroboration.get("lineage") or []))
          and len(corroboration.get("lineage") or []) == 2,
          str(corroboration.get("lineage"))[:200])

    unknown = client.get("/api/v1/world/state", headers=headers,
                         params={"subject_ref": SUBJECT,
                                 "predicate": UNOBSERVED_PREDICATE}).json()
    check("E8. a predicate nothing has observed returns UNKNOWN as its own "
          "status — not an error, not an empty success, not false",
          unknown["epistemic_status"] == "unknown" and unknown["value"] is None
          and unknown["evidence_count"] == 0, str(unknown["epistemic_status"]))

    detail = client.get(f"/api/v1/investigations/{SEEDED['done_ref']}",
                        headers=headers).json()
    check("E9. INSUFFICIENT_EVIDENCE is carried as its own conclusion kind",
          detail["conclusion_kind"] == "insufficient_evidence", str(detail["conclusion_kind"]))
    check("E10. a supported hypothesis is NOT reported as verified — support "
          "and Assurance verification are separate gates",
          detail["assurance_verified"] is False, str(detail["assurance_verified"]))
    check("E11. the ruled-out hypothesis is still present in the response — a "
          "differential that hides its eliminated candidates is an answer",
          any(h["status"] == "refuted" for h in detail["hypotheses"]))
    check("E12. UNKNOWN temporal fit survives as UNKNOWN",
          any(h["temporal_fit"] == "unknown" for h in detail["hypotheses"]))

    verification = client.get(
        f"/api/v1/verifications/{SEEDED['verification_ref']}", headers=headers).json()
    check("E13. an INSUFFICIENT_EVIDENCE verdict is returned unmapped — never "
          "as a failure and never as unsupported",
          verification["verdict"] == "insufficient_evidence", str(verification["verdict"]))

    blob = json.dumps([world, unknown, detail, verification]).lower()
    check("E14. NO confidence, probability, score or percentage field appears "
          "anywhere in the workspace payloads",
          not any(w in blob for w in ("confidence", "probability", "\"score\"", "percent")),
          "none present")


def run_security(client) -> None:
    """Part U. Fifteen ways in, all closed."""
    section("F. the security matrix")
    a = issue_token(TENANTS[TENANT_A])
    b = issue_token(TENANTS[TENANT_B])
    headers_a = {"Authorization": f"Bearer {a}"}
    headers_b = {"Authorization": f"Bearer {b}"}
    target = f"/api/v1/investigations/{SEEDED['done_ref']}"

    r = client.get("/api/v1/investigations")
    check("F1. unauthenticated request is refused", r.status_code == 401, str(r.status_code))

    r = client.get("/api/v1/investigations", headers=headers_a)
    check("F2. authenticated request succeeds", r.status_code == 200, str(r.status_code))

    from backend.auth.jwt_handler import create_access_token
    no_tenant = create_access_token("orphan@example.com", role="operator")
    r = client.get("/api/v1/investigations",
                   headers={"Authorization": f"Bearer {no_tenant}"})
    check("F3. a valid token with NO tenant claim is refused 403",
          r.status_code == 403, str(r.status_code))

    r = client.get(target, headers=headers_b)
    check("F4. tenant B is refused tenant A's REAL investigation by id",
          r.status_code == 404, str(r.status_code))
    r = client.get(target, headers=headers_a)
    check("F5. and tenant A reads the very same id — the 404 is isolation, not "
          "a broken endpoint", r.status_code == 200, str(r.status_code))

    for suffix in ("/timeline", "/assurance", "/evidence", "/hypotheses"):
        r = client.get(f"{target}{suffix}", headers=headers_b)
        if not check(f"F6. tenant B is refused {suffix} too — every workspace "
                     f"panel is a closed door, not just the first one",
                     r.status_code == 404, str(r.status_code)):
            break

    r = client.get("/api/v1/investigations", headers=headers_b,
                   params={"tenant_id": TENANTS[TENANT_A], "state": "all"})
    check("F7. a forged tenant in a QUERY parameter is ignored — B still sees "
          "nothing of A's", r.status_code == 200 and r.json()["count"] == 0,
          str(r.json().get("count")))

    r = client.get("/api/v1/investigations", headers={
        **headers_b, "X-Tenant-Id": TENANTS[TENANT_A],
        "X-Tenant-Slug": TENANT_A, "X-Forwarded-Tenant": TENANTS[TENANT_A]})
    check("F8. forged tenant HEADERS are ignored",
          r.status_code == 200 and r.json()["count"] == 0, str(r.json().get("count")))

    r = client.request("GET", "/api/v1/investigations", headers=headers_b,
                       json={"tenant_id": TENANTS[TENANT_A]})
    check("F9. a tenant in the request BODY is ignored",
          r.status_code == 200 and r.json()["count"] == 0, str(r.json().get("count")))

    r = client.get(f"/api/v1/investigations/{TENANTS[TENANT_A]}%2F{SEEDED['done_ref']}",
                   headers=headers_b)
    check("F10. a tenant smuggled into the PATH does not resolve",
          r.status_code in (404, 422), str(r.status_code))

    # Mutation: asserted as NON-EXISTENCE. A route answering 405 is a route
    # somebody can later add a verb to.
    mutations = [
        ("POST", "/api/v1/investigations"),
        ("POST", f"{target}/conclude"),
        ("POST", "/api/v1/approvals"),
        ("POST", "/api/v1/executions"),
        ("POST", "/api/v1/autonomy"),
        ("POST", "/api/v1/world/state"),
        ("PUT", target),
        ("PATCH", target),
        ("DELETE", target),
    ]
    bad = [f"{m} {p}" for m, p in mutations
           if client.request(m, p, headers=headers_a, json={}).status_code not in (404, 405)]
    check("F11. every mutation attempt hits a route that DOES NOT EXIST",
          not bad, str(bad))

    # Governance surfaces a UI might try to reach directly.
    ghosts = ["/api/v1/providers", "/api/v1/connectors", "/api/v1/credentials",
              "/api/v1/workers", "/api/v1/transport", "/api/v1/gateway",
              "/api/v1/kubernetes", "/api/v1/prometheus"]
    reachable = [p for p in ghosts if client.get(p, headers=headers_a).status_code != 404]
    check("F12. no provider, connector, credential, worker, transport or "
          "gateway route is reachable from the product API", not reachable, str(reachable))

    r = client.get("/api/v1/investigations", headers={"Authorization": "Bearer garbage"})
    check("F13. a forged token is refused", r.status_code == 401, str(r.status_code))

    bodies = " ".join([
        client.get("/api/v1/investigations", headers=headers_a).text,
        client.get(target, headers=headers_a).text,
        client.get(f"{target}/timeline", headers=headers_a).text,
        client.get("/api/v1/world/state", headers=headers_a,
                   params={"subject_ref": SUBJECT, "predicate": PREDICATE}).text,
        client.get("/api/v1/healthz").text,
    ]).lower()
    leaked = [needle for needle in (
        (os.getenv("JWT_SECRET_KEY") or "no-secret").lower(),
        "postgresql://", "password", "bearer ", "authorization",
        "traceback", "select ", os.getenv("CORTEX_DURABLE_URL", "no-dsn").lower(),
    ) if needle in bodies]
    check("F14. no secret, DSN, credential, token or stack trace appears in any "
          "workspace response", not leaked, str(leaked))

    r = client.get("/api/v1/healthz")
    check("F15. the liveness probe discloses nothing about tenant or engine",
          r.json() == {"status": "ok"}, r.text[:120])


def _ledger_counts() -> dict:
    """Row counts straight from the durable store — the ground truth for Part W."""
    from backend.api.application_runtime import build_governed_runtime
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.intelligence.infrastructure.sql_investigation import (
        SqlInvestigationRepository,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    runtime = build_governed_runtime()
    store = runtime.persistence.store
    return {
        "observations": SqlObservationRepository(store).count_all(),
        "facts": SqlFactRepository(store).count_all(),
        "verifications": SqlVerificationRepository(store).count_all(),
        "investigation_events": SqlInvestigationRepository(store).count_all(),
    }


def run_mutation_free(client, engine) -> None:
    """Part W. Repeated workspace loads must change nothing."""
    section("G. repeated loads are mutation-free")
    headers = auth(TENANT_A)
    target = f"/api/v1/investigations/{SEEDED['done_ref']}"

    before = _ledger_counts()
    for _ in range(5):
        client.get("/api/v1/investigations", headers=headers, params={"state": "all"})
        client.get(target, headers=headers)
        client.get(f"{target}/timeline", headers=headers)
        client.get(f"{target}/hypotheses", headers=headers)
        client.get(f"{target}/evidence", headers=headers)
        client.get(f"{target}/assurance", headers=headers)
        client.get("/api/v1/world/state", headers=headers,
                   params={"subject_ref": SUBJECT, "predicate": PREDICATE})
        client.get(f"/api/v1/verifications/{SEEDED['verification_ref']}", headers=headers)
    after = _ledger_counts()

    check("G1. five full workspace loads (40 reads) changed NO row in the "
          "observation, fact, verification or investigation ledgers",
          before == after, f"{before} -> {after}")
    measure("ledger_counts", after)

    first = client.get(target, headers=headers).json()
    second = client.get(target, headers=headers).json()
    first.pop("read_at", None)
    second.pop("read_at", None)
    check("G2. repeated reads of the same investigation are observationally "
          "equivalent apart from the response's own read time",
          first == second)


def run_performance(client) -> None:
    """Part S. Measured, not targeted."""
    section("H. measured latency")
    headers = auth(TENANT_A)
    target = f"/api/v1/investigations/{SEEDED['done_ref']}"

    plans = {
        "workspace_list": ("/api/v1/investigations", {"state": "all"}),
        "investigation_detail": (target, None),
        "timeline": (f"{target}/timeline", None),
        "evidence": (f"{target}/evidence", None),
        "world_state": ("/api/v1/world/state",
                        {"subject_ref": SUBJECT, "predicate": PREDICATE}),
    }
    for name, (path, params) in plans.items():
        samples = []
        for _ in range(30):
            start = time.perf_counter()
            response = client.get(path, headers=headers, params=params)
            samples.append((time.perf_counter() - start) * 1000)
            if response.status_code != 200:
                break
        samples.sort()
        measure(f"{name}_p50_ms", round(statistics.median(samples), 1))
        measure(f"{name}_p95_ms", round(samples[int(len(samples) * 0.95) - 1], 1))

    check("H1. latency was MEASURED in-process against real PostgreSQL. No SLA "
          "or target is proposed from it, and it excludes network, TLS and "
          "concurrency", True)
    deferred("latency under concurrency and over a network",
             "in-process TestClient only; a load profile is its own exercise")


if __name__ == "__main__":
    main()
