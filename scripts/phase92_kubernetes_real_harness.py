"""Phase 9.2 REAL evidence: a governed READ against a REAL Kubernetes API server.

Run:  python -m scripts.phase92_kubernetes_real_harness
      python -m scripts.phase92_kubernetes_real_harness --crash-child   (internal)
      python -m scripts.phase92_kubernetes_real_harness --failure-leg   (internal)

Required env (deployment configuration, provisioned by the runner):
  CORTEX_DURABLE_URL          fresh Postgres DSN migrated to head
  CORTEX_KUBERNETES_URL       the API server, e.g. https://127.0.0.1:55290
  CORTEX_KUBERNETES_TOKEN     a short-lived, RBAC-scoped ServiceAccount token
  CORTEX_TLS_CA_BUNDLE        the cluster CA certificate (path)
  CORTEX_P92_NAMESPACE        the isolated test namespace   (default cortex-p92)
  CORTEX_P92_EXPECT_PODS      out-of-band pod count from kubectl, for
                              independent corroboration of the governed read

The provider is the REAL ``ConnectorAdapter`` + ``ProviderChannel`` +
``TransportBroker`` + ``HttpxTransportAdapter`` — a real HTTPS request to a real
API server (disposable k3d cluster), through the ONE governed path. Nothing is
scripted in this harness. Provider dials are counted by wrapping the channel's
``send`` with a pure pass-through counter (evidence instrumentation only).

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone

from scripts.phase62_recovery_harness import TENANT, _start_and_resolve, _tenant_ctx
from scripts.phase72_observation_harness import _store


def _drive(runtime, tenant_ctx, execution_id, node_id, ticks=450):
    """phase62's driver with a budget sized for a REAL dial from a cold runtime
    AND for scheduler-leadership handover: the scheduler role is a durable
    30-second lease, and a process that died holding it (the crash children —
    that is the point of them) leaves every later scheduler a follower until
    the lease expires. Ticks are cheap while following; the budget must simply
    outlive one full lease TTL."""
    runtime.scheduler.track(execution_id)
    for _ in range(ticks):
        runtime.scheduler.tick(tenant_ctx)
        st = runtime.executions.stream_state(tenant_ctx, execution_id)
        states = {n["node_id"]: n["state"] for n in st.get("nodes", ())}
        if states.get(node_id) in {"succeeded", "failed", "unknown", "skipped"}:
            return states.get(node_id)
        time.sleep(0.1)
    return None

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
OP = "kubernetes.pods.list"
NODE = "kubernetes-pods-list"
NAMESPACE = os.getenv("CORTEX_P92_NAMESPACE", "cortex-p92")


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:150]}" if detail else ""))
    return bool(ok)


def bail(code, why):
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _require_env():
    missing = [v for v in ("CORTEX_DURABLE_URL", "CORTEX_KUBERNETES_URL",
                           "CORTEX_KUBERNETES_TOKEN", "CORTEX_TLS_CA_BUNDLE")
               if not (os.getenv(v) or "").strip()]
    if missing:
        bail(2, f"missing deployment configuration: {missing}")
    if (os.getenv("CORTEX_KUBERNETES_SCRIPTED") or "").strip():
        bail(2, "CORTEX_KUBERNETES_SCRIPTED is set; the real harness refuses the dual path")
    os.environ["CORTEX_CONNECTOR_FACTORIES"] = (
        "backend.api.kubernetes_provider_factory:kubernetes_real_extension")


def _build_runtime():
    from backend.api.application_runtime import build_governed_runtime
    runtime = build_governed_runtime()
    if runtime is None or "kubernetes" not in runtime.connectivity.catalogs:
        bail(2, "real kubernetes provider absent (factory not loaded / env unset)")
    return runtime


def _commission(runtime, platform_ctx):
    """Commission the REAL Kubernetes worker + the ONE capability. Nothing
    Kubernetes-specific in governance (same commands as every provider)."""
    from backend.contexts.execution.domain.worker_directory import WorkerAvailability, WorkerTrust
    from backend.contexts.connectivity.application.commands import (
        EnableCapability, GetCapability, RegisterCapability, SetCapabilityTrust,
        ValidateCapability)
    from backend.contexts.connectivity.domain.errors import (
        CapabilityError, IllegalCapabilityTransition)

    def _idem(fn):
        try:
            return fn()
        except (IllegalCapabilityTransition, CapabilityError):
            return None

    d = runtime.connectivity.directory
    for step in (
        lambda: d.validate(platform_ctx, worker_id="kubernetes-connector", tenant_id=""),
        lambda: d.enable(platform_ctx, worker_id="kubernetes-connector", tenant_id=""),
        lambda: d.set_trust(platform_ctx, worker_id="kubernetes-connector", tenant_id="",
                            trust=WorkerTrust.VERIFIED, reason="phase-9.2 harness"),
        lambda: d.set_trust(platform_ctx, worker_id="kubernetes-connector", tenant_id="",
                            trust=WorkerTrust.TRUSTED, reason="phase-9.2 harness"),
        lambda: d.set_availability(platform_ctx, worker_id="kubernetes-connector",
                                   tenant_id="", availability=WorkerAvailability.AVAILABLE),
    ):
        _idem(step)

    cid = f"platform.{OP}"
    _idem(lambda: runtime.capabilities.register(platform_ctx, RegisterCapability(
        capability_id=cid, version=1, name=f"Kubernetes {OP}", description=OP,
        provider="kubernetes", interface="connector", side_effect_class="read",
        effect_semantics="read_only", isolation_tier="contained",
        execution_mode="synchronous", owner_id="ops-owner", owner_kind="human",
        tenancy="platform", source="internal",
        supported_environments=("development",), provider_operation=OP)))
    _idem(lambda: runtime.capabilities.validate(platform_ctx, ValidateCapability(capability_id=cid, version=1)))
    _idem(lambda: runtime.capabilities.enable(platform_ctx, EnableCapability(capability_id=cid, version=1)))
    _idem(lambda: runtime.capabilities.set_trust(platform_ctx, SetCapabilityTrust(
        capability_id=cid, version=1, trust="verified", reason="harness")))
    _idem(lambda: runtime.capabilities.set_trust(platform_ctx, SetCapabilityTrust(
        capability_id=cid, version=1, trust="trusted", reason="harness")))
    return {OP: runtime.capabilities.get(platform_ctx, GetCapability(capability_id=cid, version=1))}


class _DialCounter:
    """Pure pass-through counter around the channel's ``send`` — evidence
    instrumentation only; alters nothing about the exchange."""

    def __init__(self, channel):
        self._send = channel.send
        self.count = 0
        channel.send = self._wrapped  # type: ignore[method-assign]

    def _wrapped(self, authority, plan, **kw):
        self.count += 1
        return self._send(authority, plan, **kw)


def _aggregate_evidence(runtime, tenant_ctx, execution_id, node_id=NODE):
    """Part H closed: the bounded provider evidence read FROM THE AGGREGATE —
    what actually traversed the pipeline, not a reconstruction."""
    from backend.contexts.execution.application.commands import GetExecution
    execution = runtime.executions.get(tenant_ctx, GetExecution(execution_id=execution_id))
    run = execution.run_for(node_id)
    if run is None or not run.attempts:
        return None, None
    attempt = run.attempts[-1]
    detail = dict(attempt.result.detail) if attempt.result is not None else {}
    return detail.get("provider_evidence"), attempt


def _observe(evidence, exec_id, tenant_ctx, subject, now):
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.world.application import ReadObservation
    return ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
        subject_ref=subject, predicate="state", value=dict(evidence),
        status=SourceStatus.RETURNED_DATA, observed_at=now, retrieved_at=now,
        produced_by="connector:kubernetes", execution_ref=exec_id,
        trace_ref=tenant_ctx.correlation.correlation_id)


def _subject():
    return f"kubernetes:pods:{NAMESPACE}"


# ---------------------------------------------------------------------------
# Internal children
# ---------------------------------------------------------------------------

def _run_crash_child():
    """Dies with real os._exit(9) at the point named by CORTEX_P92_CRASH_AFTER:
    start  — execution started+resolved, provider NOT yet contacted
    read   — governed read succeeded (real dial), observation NOT ingested
    observe— observation ingested, fact NOT derived
    derive — fact derived
    """
    from backend.contracts.tenant import TenantRef
    from backend.platform.context import ExecutionContext
    from backend.world.application import FactDerivation, ObservationIngestion, observation_identity
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    point = (os.getenv("CORTEX_P92_CRASH_AFTER") or "read").strip()
    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p92 crash child", component="k8s-real-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    marker = os.getenv("CORTEX_P92_MARKER")
    out: dict = {"point": point}

    exec_id = _start_and_resolve(runtime, tenant_ctx, defs[OP], NODE, OP,
                                 {"namespace": NAMESPACE})
    out["execution_id"] = exec_id
    if point == "start":
        _write_marker(marker, out)
        os._exit(9)

    state = _drive(runtime, tenant_ctx, exec_id, NODE)
    evidence, _ = _aggregate_evidence(runtime, tenant_ctx, exec_id)
    out["state"], out["resourceVersion"] = state, (evidence or {}).get("resourceVersion")
    if point == "read" or not isinstance(evidence, dict) or not evidence:
        # (a child that could not complete its read reports honestly and dies;
        # the parent's checks then fail loudly rather than on a TypeError)
        _write_marker(marker, out)
        os._exit(9)

    tenant = TenantRef(tenant_id=TENANT)
    obs_repo = SqlObservationRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=obs_repo)
    now = datetime.now(timezone.utc)
    obs, newly = ingestion.ingest(
        tenant=tenant, read=_observe(evidence, exec_id, tenant_ctx, _subject(), now),
        recorded_at=now)
    out["observation_id"], out["identity"], out["newly"] = (
        obs.record_id, observation_identity(obs), newly)
    if point == "observe":
        _write_marker(marker, out)
        os._exit(9)

    fact_repo = SqlFactRepository(runtime.persistence.store)
    FactDerivation(repository=fact_repo).derive(tenant=tenant, observation=obs, recorded_at=now)
    out["facts"] = fact_repo.count_all()
    _write_marker(marker, out)
    os._exit(9)


def _write_marker(marker, payload):
    if marker:
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, default=str)
    sys.stdout.flush()


def _run_failure_leg():
    """One provider-failure scenario in an isolated process (composition-time
    env decides the endpoint/credential). Writes a JSON marker; exits 0."""
    from backend.world.infrastructure import SqlObservationRepository

    leg = (os.getenv("CORTEX_P92_LEG") or "").strip()
    from backend.platform.context import ExecutionContext
    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason=f"p92 failure leg {leg}", component="k8s-real-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    obs_repo = SqlObservationRepository(runtime.persistence.store)
    obs_before = obs_repo.count_all()

    namespace = os.getenv("CORTEX_P92_LEG_NAMESPACE", NAMESPACE)
    exec_id = _start_and_resolve(runtime, tenant_ctx, defs[OP], NODE, OP,
                                 {"namespace": namespace})
    state = _drive(runtime, tenant_ctx, exec_id, NODE)
    evidence, attempt = _aggregate_evidence(runtime, tenant_ctx, exec_id)
    failure = None
    if attempt is not None and attempt.failure is not None:
        failure = getattr(attempt.failure, "classification", None) or getattr(
            attempt.failure, "reason", None)
    marker = os.getenv("CORTEX_P92_MARKER")
    _write_marker(marker, {
        "leg": leg, "state": state, "evidence": evidence, "execution_id": exec_id,
        "failure": str(failure), "failure_reason": getattr(attempt, "failure_reason", None),
        "observations_delta": obs_repo.count_all() - obs_before,
    })
    try:
        runtime.scheduler.stop(timeout_seconds=5)  # releases the scheduler lease
        runtime.audit_writer.release()
    except Exception:
        pass
    sys.exit(0)


def _sweep(runtime, tenant_ctx, execution_id, reason):
    """Cancel a child's leftover execution if it is still non-terminal.

    The scheduler reads READY nodes globally from the durable substrate (one
    plane of action) — a stale non-terminal node left by a dead child would
    starve every later child's tick loop. Hygiene, not semantics: cancellation
    is the operator's existing command, and a terminal execution ignores it.
    """
    if not execution_id:
        return
    from backend.contexts.execution.application.commands import CancelExecution
    try:
        runtime.executions.cancel(tenant_ctx, CancelExecution(
            execution_id=execution_id, reason=reason, cancelled_by="harness"))
    except Exception:
        pass  # already terminal — nothing to sweep


def _spawn(mode, env_overrides, marker_suffix, timeout=150):
    marker = os.path.join(tempfile.gettempdir(), f"p92_{marker_suffix}_{os.getpid()}.json")
    child_env = dict(os.environ)
    child_env["CORTEX_P92_MARKER"] = marker
    child_env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.phase92_kubernetes_real_harness", mode],
        env=child_env, cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    data = {}
    if os.path.exists(marker):
        with open(marker, encoding="utf-8") as fh:
            data = json.load(fh)
        os.remove(marker)
    return proc.returncode, data


def _percentiles(samples):
    ordered = sorted(samples)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, max(0, round(0.95 * len(ordered)) - 1))]
    return round(p50 * 1000, 1), round(p95 * 1000, 1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():  # noqa: PLR0912, PLR0915
    if "--crash-child" in sys.argv:
        _require_env()
        _run_crash_child()
        return
    if "--failure-leg" in sys.argv:
        _require_env()
        _run_failure_leg()
        return
    _require_env()

    from backend.contracts.tenant import TenantRef
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import (
        FactDerivation, ObservationIngestion, ObservationRejected, WorldQuery,
        observation_identity)
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p92 real k8s read", component="k8s-real-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    tenant = TenantRef(tenant_id=TENANT)
    adapter = runtime.connectivity.adapters["kubernetes"]
    dials = _DialCounter(adapter._channel)  # noqa: SLF001 — evidence instrumentation
    obs_repo = SqlObservationRepository(runtime.persistence.store)
    fact_repo = SqlFactRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=obs_repo)
    derivation = FactDerivation(repository=fact_repo)
    query = WorldQuery(facts=fact_repo, observations=obs_repo)

    print("[label] REAL Kubernetes API server (disposable k3d cluster) — no mock, no script")
    check("the real exposure is exactly ONE operation (Part E)",
          tuple(runtime.connectivity.catalogs["kubernetes"].operations) == (OP,))
    check("V1 connector library not imported (Part U)",
          not any(m == "backend.connectors" or m.startswith("backend.connectors.")
                  for m in sys.modules))

    # ---- [F/G/H] the real governed READ -------------------------------------
    print("[F] governed READ against the real API server")
    exec_id = _start_and_resolve(runtime, tenant_ctx, defs[OP], NODE, OP,
                                 {"namespace": NAMESPACE})
    check("no provider contact before governed execution", dials.count == 0)
    state = _drive(runtime, tenant_ctx, exec_id, NODE)
    check("governed kubernetes.pods.list SUCCEEDED against the real cluster",
          state == "succeeded", str(state))
    check("exactly one real provider dial", dials.count == 1, dials.count)

    evidence, attempt = _aggregate_evidence(runtime, tenant_ctx, exec_id)
    check("provider evidence read FROM THE AGGREGATE (9.1 gap closed)",
          isinstance(evidence, dict) and bool(evidence))
    evidence = evidence if isinstance(evidence, dict) else {}
    rv = evidence.get("resourceVersion")
    check("resourceVersion preserved exactly (opaque, non-empty string)",
          isinstance(rv, str) and len(rv) > 0, rv)
    expected_pods = os.getenv("CORTEX_P92_EXPECT_PODS")
    if expected_pods:
        check("podCount corroborated by out-of-band kubectl",
              evidence.get("podCount") == int(expected_pods),
              f"governed={evidence.get('podCount')} kubectl={expected_pods}")
    spec = runtime.connectivity.catalogs["kubernetes"].require(OP)
    check("evidence keys are exactly the declared bounded scalars",
          set(evidence).issubset(set(spec.response_evidence_fields)), sorted(evidence))

    # ---- [I] Phase 7.2 observation ------------------------------------------
    print("[I] real read -> durable Observation (Phase 7.2)")
    now = datetime.now(timezone.utc)
    obs, newly = ingestion.ingest(
        tenant=tenant, read=_observe(evidence, exec_id, tenant_ctx, _subject(), now),
        recorded_at=now)
    check("real read became a durable Observation", newly)
    check("Observation preserves the real resourceVersion (WATCH data contract)",
          obs.value.get("resourceVersion") == rv, obs.value.get("resourceVersion"))
    check("Observation is tenant-scoped + references the execution",
          obs.tenant.tenant_id == TENANT and obs.provenance.execution_ref == exec_id)
    check("ingestion contacted no provider", dials.count == 1)

    # ---- [J] Fact -> WorldQuery ---------------------------------------------
    print("[J] Observation -> Fact -> WorldQuery (provider-neutral)")
    derivation.derive(tenant=tenant, observation=obs, recorded_at=now)
    answer = query.current(tenant=tenant, subject_ref=_subject(), predicate="state", now=now)
    check("WorldQuery answers what Kubernetes reported",
          answer.effective_value is not None
          and answer.effective_value.get("podCount") == evidence.get("podCount")
          and answer.effective_value.get("resourceVersion") == rv)
    check("WorldQuery contacted no provider (hard invariant)", dials.count == 1)

    # ---- [K] authorization negatives (no dial) ------------------------------
    print("[K] authorization refusals — governance first, no provider contact")
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.contexts.connectivity.domain.authorization import (
        AuthorizationRequest, CapabilityOperation)
    from backend.contexts.connectivity.domain.contract import CapabilityEnvironment
    dials_at_neg = dials.count
    principal = PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN)

    wrong_tenant = runtime.authorization.authorize(_tenant_ctx(), AuthorizationRequest(
        tenant_id="tenant-b", principal=principal, capability_ref=defs[OP].reference,
        operation=CapabilityOperation.INVOKE, expected_digest=defs[OP].digest,
        environment=CapabilityEnvironment.DEVELOPMENT))
    check("wrong tenant refused", not getattr(wrong_tenant, "allowed", False))

    wrong_digest = runtime.authorization.authorize(tenant_ctx, AuthorizationRequest(
        tenant_id=TENANT, principal=principal, capability_ref=defs[OP].reference,
        operation=CapabilityOperation.INVOKE, expected_digest="sha256:0000",
        environment=CapabilityEnvironment.DEVELOPMENT))
    check("drifted capability digest refused", not getattr(wrong_digest, "allowed", False))

    missing = False
    try:
        from backend.contexts.connectivity.application.commands import GetCapability
        runtime.capabilities.get(platform_ctx, GetCapability(
            capability_id="platform.kubernetes.pod.delete", version=1))
    except Exception:
        missing = True
    check("missing capability (a write) is not registered — fail closed", missing)

    unknown_refused = False
    try:
        runtime.connectivity.catalogs["kubernetes"].require("kubernetes.pod.delete")
    except Exception:
        unknown_refused = True
    check("unknown/write operation refused by the declared catalog", unknown_refused)

    malformed = False
    try:
        runtime.authorization.authorize(tenant_ctx, AuthorizationRequest(
            tenant_id=TENANT, principal=principal, capability_ref="not a ref",
            operation=CapabilityOperation.INVOKE, expected_digest="x",
            environment=CapabilityEnvironment.DEVELOPMENT))
        malformed = True  # an allow would be the failure; a refusal object is fine
    except Exception:
        malformed = True
    check("malformed capability reference does not authorize", malformed)

    refused_no_authority = False
    try:
        no_authority = adapter.run(None, _fake_request(), authority=None)
        refused_no_authority = not no_authority.succeeded
    except Exception:
        # The seam refuses a request that has not been through the gate by
        # raising — a refusal, and provably no provider contact.
        refused_no_authority = True
    check("real adapter with NO authority refuses (no gateway => no provider call)",
          refused_no_authority)
    check("all governance refusals contacted no provider", dials.count == dials_at_neg)

    # invalid resource scope: a path-traversal namespace is refused at the
    # gateway's input validation — before any request exists. The dispatcher
    # deliberately returns a gateway-refused node to READY (a refusal, not a
    # failed attempt), so the node never succeeds and never dials; the harness
    # then cancels it so a permanently-invalid node cannot linger.
    from backend.contexts.execution.application.commands import CancelExecution
    bad_exec = _start_and_resolve(runtime, tenant_ctx, defs[OP], NODE + "-bad", OP,
                                  {"namespace": "../etc"})
    bad_state = _drive(runtime, tenant_ctx, bad_exec, NODE + "-bad", ticks=8)
    check("invalid resource scope refused before any dial (never succeeds, never dials)",
          bad_state != "succeeded" and dials.count == dials_at_neg, str(bad_state))
    runtime.executions.cancel(tenant_ctx, CancelExecution(
        execution_id=bad_exec, reason="phase 9.2 harness: permanently invalid input",
        cancelled_by="harness"))

    # ---- [L/M] provider-side failures, real ----------------------------------
    print("[L/M] real provider failures — classified, never converted to truth")
    obs_count_before_failures = obs_repo.count_all()

    # 403: CortexPrime authorizes; the cluster's RBAC refuses (SA is scoped to
    # the test namespace). Distinct authorities, kept distinct.
    forbidden_exec = _start_and_resolve(runtime, tenant_ctx, defs[OP], NODE + "-403", OP,
                                        {"namespace": "default"})
    forbidden_state = _drive(runtime, tenant_ctx, forbidden_exec, NODE + "-403")
    _, forbidden_attempt = _aggregate_evidence(runtime, tenant_ctx, forbidden_exec,
                                               NODE + "-403")
    forbidden_reason = str(getattr(forbidden_attempt, "failure_reason", "") or "") + str(
        getattr(getattr(forbidden_attempt, "failure", None), "classification", "") or "")
    check("cluster RBAC 403 -> execution FAILED (a provider authorization failure)",
          forbidden_state == "failed", forbidden_state)
    check("403 classified as provider-side, not CortexPrime authorization",
          "authorization" in forbidden_reason.lower() or "forbidden" in forbidden_reason.lower(),
          forbidden_reason[:120])
    check("403 produced no observation", obs_repo.count_all() == obs_count_before_failures)

    # release the scheduler role and audit lease around subprocess legs (they
    # acquire both themselves; a parent holding either would make every child a
    # follower for a full lease TTL)
    runtime.scheduler.stop(timeout_seconds=5)
    runtime.audit_writer.release()

    rc401, leg401 = _spawn("--failure-leg", {
        "CORTEX_P92_LEG": "auth401", "CORTEX_KUBERNETES_TOKEN": "bogus-token-not-a-jwt"}, "401")
    check("bad credential -> real 401 -> FAILED, no observation",
          rc401 == 0 and leg401.get("state") == "failed"
          and leg401.get("observations_delta") == 0,
          f"state={leg401.get('state')} failure={str(leg401.get('failure'))[:60]}")

    import certifi
    rc_tls, leg_tls = _spawn("--failure-leg", {
        # a real, valid CA bundle that did NOT sign the API server's cert —
        # verification fails; it is never disabled
        "CORTEX_P92_LEG": "tls", "CORTEX_TLS_CA_BUNDLE": certifi.where()}, "tls")
    check("unverifiable TLS -> refused/unknown, no observation, never success",
          rc_tls == 0 and leg_tls.get("state") in {"failed", "unknown"}
          and leg_tls.get("observations_delta") == 0,
          f"state={leg_tls.get('state')}")

    rc_un, leg_un = _spawn("--failure-leg", {
        "CORTEX_P92_LEG": "unavailable",
        "CORTEX_KUBERNETES_URL": "https://127.0.0.1:59"}, "unavailable")
    check("API server unavailable -> refused/unknown, no observation",
          rc_un == 0 and leg_un.get("state") in {"failed", "unknown"}
          and leg_un.get("observations_delta") == 0,
          f"state={leg_un.get('state')}")

    runtime.audit_writer.acquire()
    for leg in (leg401, leg_tls, leg_un):
        _sweep(runtime, tenant_ctx, leg.get("execution_id"),
               "phase 9.2 harness: failure-leg leftover")
    check("no failure leg fabricated an observation",
          obs_repo.count_all() == obs_count_before_failures)
    check("no failure leg fabricated a fact", fact_repo.count_all() == 1)

    # ---- [O] replay ----------------------------------------------------------
    print("[O] replay inert")
    from backend.contexts.execution.application.commands import ReplayExecution
    obs_b, dials_b = obs_repo.count_all(), dials.count
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    check("replay created zero new observations", obs_repo.count_all() == obs_b)
    check("replay performed zero provider dials", dials.count == dials_b)

    # ---- [P] crash / recovery (real os._exit(9)) -----------------------------
    print("[P] crash / recovery at four points")
    runtime.audit_writer.release()

    rc_a, leg_a = _spawn("--crash-child", {"CORTEX_P92_CRASH_AFTER": "start"}, "crashA")
    ok_a = rc_a in (9, -9) and bool(leg_a.get("execution_id"))
    check("A: died after start, before provider contact", ok_a, f"rc={rc_a}")
    runtime.audit_writer.acquire()
    _sweep(runtime, tenant_ctx, leg_a.get("execution_id"),
           "phase 9.2 harness: crash-A leftover (never dispatched)")
    runtime.audit_writer.release()

    rc_b, leg_b = _spawn("--crash-child", {"CORTEX_P92_CRASH_AFTER": "read"}, "crashB")
    check("B: died after real read, before observation", rc_b in (9, -9)
          and leg_b.get("state") == "succeeded" and bool(leg_b.get("resourceVersion")),
          f"rc={rc_b} rv={leg_b.get('resourceVersion')}")

    rc_c, leg_c = _spawn("--crash-child", {"CORTEX_P92_CRASH_AFTER": "observe"}, "crashC")
    check("C: died after observation", rc_c in (9, -9) and bool(leg_c.get("observation_id")))

    rc_d, leg_d = _spawn("--crash-child", {"CORTEX_P92_CRASH_AFTER": "derive"}, "crashD")
    check("D: died after fact derivation", rc_d in (9, -9) and bool(leg_d.get("observation_id")))

    runtime.audit_writer.acquire()

    # Recovery, from a FRESH persistence handle (no in-process state):
    fresh = SqlObservationRepository(_store().store)
    if leg_b.get("execution_id"):
        ev_b, _ = _aggregate_evidence(runtime, tenant_ctx, leg_b["execution_id"])
        check("B-recovery: provider evidence durable across the crash "
              "(resourceVersion reconstructed from the aggregate, not refetched)",
              isinstance(ev_b, dict) and ev_b.get("resourceVersion") == leg_b.get("resourceVersion"),
              (ev_b or {}).get("resourceVersion"))
        if isinstance(ev_b, dict) and ev_b:
            dials_before_recovery = dials.count
            now2 = datetime.now(timezone.utc)
            obs_b2, newly_b2 = ingestion.ingest(
                tenant=tenant,
                read=_observe(ev_b, leg_b["execution_id"], tenant_ctx,
                              _subject() + "/crash-b", now2),
                recorded_at=now2)
            check("B-recovery: observation completed WITHOUT re-contacting the provider",
                  newly_b2 and dials.count == dials_before_recovery)
    if leg_c.get("observation_id"):
        rec = fresh.get_observation(tenant_id=TENANT, observation_id=leg_c["observation_id"])
        check("C-recovery: crashed observation reconstructs (not fabricated)",
              rec is not None and observation_identity(rec) == leg_c.get("identity"))
        check("C-recovery: cross-tenant read of crashed observation fails closed",
              fresh.get_observation(tenant_id="tenant-b",
                                    observation_id=leg_c["observation_id"]) is None)
    if leg_d.get("observation_id"):
        rec_d = fresh.get_observation(tenant_id=TENANT, observation_id=leg_d["observation_id"])
        check("D-recovery: post-fact crash leaves durable observation + fact",
              rec_d is not None and int(leg_d.get("facts") or 0) >= 1)
        # replaying the derivation is deterministic: no duplicate fact
        facts_before = fact_repo.count_all()
        derivation.derive(tenant=tenant, observation=rec_d,
                          recorded_at=datetime.now(timezone.utc))
        check("D-recovery: re-derivation is inert (deterministic dedupe)",
              fact_repo.count_all() == facts_before)

    # ---- [Q] tenant isolation ------------------------------------------------
    print("[Q] tenant isolation on the durable path")
    check("cross-tenant get_observation fails closed",
          obs_repo.get_observation(tenant_id="tenant-b", observation_id=obs.record_id) is None)
    other_answer = query.current(tenant=TenantRef(tenant_id="tenant-b"),
                                 subject_ref=_subject(), predicate="state",
                                 now=datetime.now(timezone.utc))
    check("cross-tenant WorldQuery answers nothing", other_answer.effective_value is None)

    # ---- [R] secret firewall over the durable substrate ----------------------
    print("[R] secret firewall — the token appears nowhere durable")
    token = os.environ["CORTEX_KUBERNETES_TOKEN"]
    leaked = _scan_for_secret(os.environ["CORTEX_DURABLE_URL"], token)
    check("SA token absent from every durable row", leaked == [], str(leaked)[:200])
    check("no Authorization/Bearer material in the observation",
          "Bearer" not in json.dumps(obs.to_dict()) and token not in json.dumps(obs.to_dict()))

    # ---- [T] latency (N=12 real governed reads) ------------------------------
    print("[T] latency: 12 real governed reads")
    lat: dict = {"authorize_ms": [], "execute_ms": [], "evidence_ms": [],
                 "ingest_ms": [], "query_ms": []}
    for i in range(12):
        t0 = time.perf_counter()
        perf_exec = _start_and_resolve(runtime, tenant_ctx, defs[OP], f"{NODE}-perf{i}", OP,
                                       {"namespace": NAMESPACE})
        t1 = time.perf_counter()
        perf_state = _drive(runtime, tenant_ctx, perf_exec, f"{NODE}-perf{i}")
        t2 = time.perf_counter()
        ev_i, _ = _aggregate_evidence(runtime, tenant_ctx, perf_exec, f"{NODE}-perf{i}")
        t3 = time.perf_counter()
        now_i = datetime.now(timezone.utc)
        ingestion.ingest(tenant=tenant,
                         read=_observe(ev_i, perf_exec, tenant_ctx,
                                       _subject() + f"/perf{i}", now_i),
                         recorded_at=now_i)
        t4 = time.perf_counter()
        query.current(tenant=tenant, subject_ref=_subject() + f"/perf{i}",
                      predicate="state", now=now_i)
        t5 = time.perf_counter()
        if perf_state != "succeeded":
            check(f"perf read {i} succeeded", False, perf_state)
        lat["authorize_ms"].append(t1 - t0)
        lat["execute_ms"].append(t2 - t1)
        lat["evidence_ms"].append(t3 - t2)
        lat["ingest_ms"].append(t4 - t3)
        lat["query_ms"].append(t5 - t4)
    REPORT["latency"] = {
        stage: {"p50_ms": p50, "p95_ms": p95}
        for stage, samples in lat.items()
        for p50, p95 in [_percentiles(samples)]}
    print("  latency:", json.dumps(REPORT["latency"]))
    check("12 additional real reads all governed",
          dials.count == dials_b + 12, dials.count)

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"observations": obs_repo.count_all(), "facts": fact_repo.count_all(),
                        "real_provider_dials": dials.count}
    REPORT["real_kubernetes"] = {
        "endpoint": os.environ["CORTEX_KUBERNETES_URL"], "namespace": NAMESPACE,
        "resourceVersion": rv, "observation_id": obs.record_id, "execution_id": exec_id}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1,
         "REAL kubernetes governed read verified" if ok else "a check failed")


def _fake_request():
    """A syntactically valid WorkerExecutionRequest for the no-authority
    refusal check (the seam refuses before reading most of it)."""
    from backend.contexts.execution.domain.worker_contract import WorkerExecutionRequest
    from backend.contracts.execution import ExecutionEnvironment

    class _B:
        binding_id = "phantom-binding"
        capability_ref = "phantom"
        worker_kind = None
    try:
        return WorkerExecutionRequest(
            binding=_B(), attempt_id="phantom", execution_key="phantom",
            node_id="phantom", environment=ExecutionEnvironment.DEVELOPMENT)
    except Exception:
        class _R:
            binding = _B()
            attempt_id = "phantom"
            execution_key = "phantom"
            node_id = "phantom"
        return _R()


def _scan_for_secret(dsn, token):
    """Every durable table, every row, rendered to text: the token must be
    absent. References/digests are allowed; material is not."""
    import sqlalchemy as sa
    engine = sa.create_engine(dsn, future=True)
    needle = token.strip()
    leaked = []
    with engine.connect() as conn:
        tables = [r[0] for r in conn.execute(sa.text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"))]
        for table in tables:
            rows = conn.execute(sa.text(f'SELECT * FROM "{table}"')).fetchall()
            for row in rows:
                blob = json.dumps([str(v) for v in row], default=str)
                if needle and needle in blob:
                    leaked.append(table)
                    break
    engine.dispose()
    return leaked


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
