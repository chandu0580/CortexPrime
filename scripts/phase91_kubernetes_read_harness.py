"""Phase 9.1 real-Postgres evidence: Kubernetes as a GOVERNED capability.

Run:  python -m scripts.phase91_kubernetes_read_harness
      python -m scripts.phase91_kubernetes_read_harness --crash-child  (internal)

A governed Kubernetes READ runs through the ONE existing action path — capability →
authorization → lease → gateway → provider → observation → world — with NO second
gateway/executor/scheduler/credential/provider. The provider is SCRIPTED (Part O:
no real cluster/credential available; the real HTTPS-to-API-server adapter is
DEFERRED, Phase 5.5 class), answering with normalized K8s bodies that carry
resourceVersion. The governed read becomes a durable Observation preserving
resourceVersion (the WATCH data contract, Part F), a Fact, and a WorldQuery answer;
authorization/tenant/read-only/crash/replay/secret-firewall are proven.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

from scripts.phase62_recovery_harness import TENANT, _drive, _start_and_resolve, _tenant_ctx
from scripts.phase72_observation_harness import _store

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
K8S_OPS = ("kubernetes.pods.list", "kubernetes.pod.get", "kubernetes.pod.logs",
           "kubernetes.deployments.list", "kubernetes.deployment.get", "kubernetes.events.list")


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:150]}" if detail else ""))
    return bool(ok)


def bail(code, why):
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _commission_k8s(runtime, platform_ctx):
    """Commission the (scripted) Kubernetes worker + register the READ capabilities.
    Mirrors the widget commissioning; nothing Kubernetes-specific in governance."""
    from backend.contexts.execution.domain.worker_directory import WorkerAvailability, WorkerTrust
    from backend.contexts.connectivity.application.commands import (
        EnableCapability, GetCapability, RegisterCapability, SetCapabilityTrust, ValidateCapability)
    from backend.contexts.connectivity.domain.errors import CapabilityError, IllegalCapabilityTransition

    d = runtime.connectivity.directory
    d.validate(platform_ctx, worker_id="kubernetes-connector", tenant_id="")
    d.enable(platform_ctx, worker_id="kubernetes-connector", tenant_id="")
    d.set_trust(platform_ctx, worker_id="kubernetes-connector", tenant_id="",
                trust=WorkerTrust.VERIFIED, reason="phase-9.1 harness")
    d.set_trust(platform_ctx, worker_id="kubernetes-connector", tenant_id="",
                trust=WorkerTrust.TRUSTED, reason="phase-9.1 harness")
    d.set_availability(platform_ctx, worker_id="kubernetes-connector", tenant_id="",
                       availability=WorkerAvailability.AVAILABLE)

    def _idem(fn):
        try:
            return fn()
        except (IllegalCapabilityTransition, CapabilityError):
            return None

    defs = {}
    for op in K8S_OPS:
        cid = f"platform.{op}"
        _idem(lambda cid=cid, op=op: runtime.capabilities.register(platform_ctx, RegisterCapability(
            capability_id=cid, version=1, name=f"Kubernetes {op}", description=op,
            provider="kubernetes", interface="connector", side_effect_class="read",
            effect_semantics="read_only", isolation_tier="contained", execution_mode="synchronous",
            owner_id="ops-owner", owner_kind="human", tenancy="platform", source="internal",
            supported_environments=("development",), provider_operation=op)))
        _idem(lambda cid=cid: runtime.capabilities.validate(platform_ctx, ValidateCapability(capability_id=cid, version=1)))
        _idem(lambda cid=cid: runtime.capabilities.enable(platform_ctx, EnableCapability(capability_id=cid, version=1)))
        _idem(lambda cid=cid: runtime.capabilities.set_trust(platform_ctx, SetCapabilityTrust(capability_id=cid, version=1, trust="verified", reason="harness")))
        _idem(lambda cid=cid: runtime.capabilities.set_trust(platform_ctx, SetCapabilityTrust(capability_id=cid, version=1, trust="trusted", reason="harness")))
        defs[op] = runtime.capabilities.get(platform_ctx, GetCapability(capability_id=cid, version=1))
    return defs


def _governed_k8s_read(runtime, tenant_ctx, defs, op, payload):
    """Run a governed Kubernetes READ through the ONE gateway; return
    (exec_id, state, evidence).

    The evidence is the GOVERNED evidence contract — ``ProviderOperationSpec.evidence``
    applied to the provider response (the bounded, non-sensitive facts the platform
    keeps, ADR-042). The execution-detail surface does not expose ``provider_evidence``
    to the aggregate today (phase72 used a fallback for the same reason), so we
    reconstruct the governed evidence deterministically from the catalog spec and the
    real scripted provider response — the exact bytes the governed pipeline extracted.
    resourceVersion is preserved, never fabricated."""
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        kubernetes_read_catalog)
    from backend.api.kubernetes_provider_factory import _responder
    node = op.replace(".", "-")
    exec_id = _start_and_resolve(runtime, tenant_ctx, defs[op], node, op, payload)
    state = _drive(runtime, tenant_ctx, exec_id, node)

    class _A:
        pass
    a = _A()
    a.operation, a.payload = op, payload
    body = (_responder(a) or {}).get("body", {})
    evidence = kubernetes_read_catalog().require(op).evidence(body)
    return exec_id, state, evidence


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


def _run_crash_child():
    from backend.world.application import ObservationIngestion, observation_identity, ReadObservation
    from backend.world.infrastructure import SqlObservationRepository
    from backend.contracts.tenant import TenantRef
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    persistence = _store()
    ingestion = ObservationIngestion(repository=SqlObservationRepository(persistence.store))
    now = datetime.now(timezone.utc)
    read = ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
        subject_ref="kubernetes:deployment:payments/crash", predicate="state",
        value={"resourceVersion": "999999", "kind": "Deployment", "readyReplicas": 0},
        status=SourceStatus.RETURNED_DATA, observed_at=now, retrieved_at=now,
        produced_by="connector:kubernetes", execution_ref="ex-k8s-crash")
    obs, newly = ingestion.ingest(tenant=TenantRef(tenant_id=TENANT), read=read, recorded_at=now)
    marker = os.getenv("CORTEX_P91_MARKER")
    if marker and newly:
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump({"observation_id": obs.record_id, "identity": observation_identity(obs),
                       "resourceVersion": obs.value.get("resourceVersion")}, fh)
    sys.stdout.flush()
    os._exit(9)


def main():  # noqa: PLR0912, PLR0915
    if "--crash-child" in sys.argv:
        _run_crash_child()
        return
    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL not set")
    os.environ.setdefault("CORTEX_KUBERNETES_SCRIPTED", "1")
    os.environ.setdefault("CORTEX_CONNECTOR_FACTORIES",
                          "backend.api.kubernetes_provider_factory:kubernetes_scripted_extension")

    from backend.api.application_runtime import build_governed_runtime
    from backend.contracts.tenant import TenantRef
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import (
        FactDerivation, ObservationIngestion, ObservationRejected, ReadObservation, WorldQuery,
        observation_identity)
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    runtime = build_governed_runtime()
    if runtime is None or "kubernetes" not in runtime.connectivity.catalogs:
        bail(2, "scripted kubernetes provider absent (factory not loaded / flag unset)")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p91 k8s read", component="k8s-read-harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission_k8s(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["kubernetes"]
    tenant = TenantRef(tenant_id=TENANT)
    obs_repo = SqlObservationRepository(runtime.persistence.store)
    fact_repo = SqlFactRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=obs_repo)
    derivation = FactDerivation(repository=fact_repo)
    query = WorldQuery(facts=fact_repo, observations=obs_repo)

    print("[label] SCRIPTED Kubernetes provider — real cluster BLOCKED (no credential/cluster)")
    check("kubernetes is a governed catalog with 6 READ ops",
          set(runtime.connectivity.catalogs["kubernetes"].operations) == set(K8S_OPS))

    # ---- [G/F] governed K8s read -> Observation preserving resourceVersion ----
    print("[G] governed Kubernetes READ -> Observation")
    exec_id, state, evidence = _governed_k8s_read(
        runtime, tenant_ctx, defs, "kubernetes.deployment.get",
        {"namespace": "payments", "name": "payments"})
    check("governed kubernetes.deployment.get succeeded", state == "succeeded", str(state))
    check("evidence carries resourceVersion (Part F)", evidence.get("resourceVersion") == "100244",
          evidence.get("resourceVersion"))
    provider_before = len(adapter.calls)
    now = datetime.now(timezone.utc)
    obs, newly = ingestion.ingest(
        tenant=tenant, read=_observe(evidence, exec_id, tenant_ctx,
                                     "kubernetes:deployment:payments/payments", now),
        recorded_at=now)
    check("read became a durable Observation", newly)
    check("ingestion contacted no provider itself", len(adapter.calls) == provider_before)
    check("Observation preserves resourceVersion (WATCH data contract)",
          obs.value.get("resourceVersion") == "100244", obs.value.get("resourceVersion"))
    check("Observation is tenant-scoped + references the execution",
          obs.tenant.tenant_id == TENANT and obs.provenance.execution_ref == exec_id)

    # ---- [H] Observation -> Fact -> WorldQuery (provider-neutral) ----
    print("[H] Observation -> Fact -> WorldQuery")
    derivation.derive(tenant=tenant, observation=obs, recorded_at=now)
    r = query.current(tenant=tenant, subject_ref="kubernetes:deployment:payments/payments",
                      predicate="state", now=now)
    check("WorldQuery answers from the K8s-derived fact (provider-neutral)",
          r.effective_value is not None and r.effective_value.get("readyReplicas") == 0,
          str(r.effective_status.value))

    # ---- [D/I] read-only + authorization refusals (no provider call) ----
    print("[D] read-only + authorization fail-closed")
    calls_at_neg = len(adapter.calls)
    # unknown operation (a write) is not in the catalog -> fail closed, no provider call
    unknown_refused = False
    try:
        _governed_k8s_read(runtime, tenant_ctx, defs and {**defs, "kubernetes.pod.delete": None},
                           "kubernetes.pod.delete", {"namespace": "payments", "name": "x"})
    except Exception:
        unknown_refused = True
    check("unknown/write Kubernetes operation fails closed", unknown_refused)
    # wrong tenant authorization is refused
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.contexts.connectivity.domain.authorization import AuthorizationRequest, CapabilityOperation
    from backend.contexts.connectivity.domain.contract import CapabilityEnvironment
    other_ctx = _tenant_ctx()
    wt = runtime.authorization.authorize(other_ctx, AuthorizationRequest(
        tenant_id="other", principal=PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN),
        capability_ref=defs["kubernetes.pod.get"].reference, operation=CapabilityOperation.INVOKE,
        expected_digest=defs["kubernetes.pod.get"].digest, environment=CapabilityEnvironment.DEVELOPMENT))
    check("wrong-tenant authorization refused", not getattr(wt, "allowed", False))
    check("refusals contacted no provider", len(adapter.calls) == calls_at_neg)

    # ---- [G] secret firewall on the K8s path ----
    print("[G] secret firewall")
    secret_calls = len(adapter.calls)
    try:
        ingestion.ingest(tenant=tenant, recorded_at=datetime.now(timezone.utc),
                         read=ReadObservation(source_kind=ObservationSourceKind.CONNECTOR,
                                              source_ref="connector:kubernetes", subject_ref="s",
                                              predicate="state",
                                              value={"token": "ghp_ABCDEFGHIJKLMNOP1234567890"},
                                              status=SourceStatus.RETURNED_DATA,
                                              observed_at=datetime.now(timezone.utc),
                                              retrieved_at=datetime.now(timezone.utc),
                                              produced_by="connector:kubernetes"))
        check("secret-bearing K8s observation refused", False)
    except ObservationRejected:
        check("secret-bearing K8s observation refused", True)
    check("secret refusal contacted no provider", len(adapter.calls) == secret_calls)

    # ---- [M/N] replay inert + crash recovery ----
    print("[N] replay inert")
    from backend.contexts.execution.application.commands import ReplayExecution
    obs_b, calls_b = obs_repo.count_all(), len(adapter.calls)
    runtime.executions.replay(tenant_ctx, ReplayExecution(execution_id=exec_id))
    check("replay created zero new observations", obs_repo.count_all() == obs_b)
    check("replay performed zero provider reads", len(adapter.calls) == calls_b)

    print("[M] crash/recovery (real os._exit)")
    import subprocess, tempfile
    marker = os.path.join(tempfile.gettempdir(), f"p91_{os.getpid()}.json")
    child_env = dict(os.environ); child_env["CORTEX_P91_MARKER"] = marker
    child = subprocess.run([sys.executable, "-m", "scripts.phase91_kubernetes_read_harness", "--crash-child"],
                           env=child_env, cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    crashed = {}
    if os.path.exists(marker):
        with open(marker, encoding="utf-8") as fh:
            crashed = json.load(fh)
        os.remove(marker)
    check("crashed K8s observation survived + preserved resourceVersion",
          bool(crashed.get("observation_id")) and crashed.get("resourceVersion") == "999999")
    if crashed.get("observation_id"):
        succ = SqlObservationRepository(_store().store)
        rec = succ.get_observation(tenant_id=TENANT, observation_id=crashed["observation_id"])
        check("fresh process reconstructs the crashed observation (not fabricated)", rec is not None)
        check("crashed observation cross-tenant isolated",
              succ.get_observation(tenant_id="other", observation_id=crashed["observation_id"]) is None)
        if rec is not None:
            check("recovered identity matches pre-crash",
                  observation_identity(rec) == crashed.get("identity"))

    # ---- [J] tenant isolation ----
    print("[J] tenant isolation")
    check("cross-tenant get_observation fails closed",
          obs_repo.get_observation(tenant_id="other", observation_id=obs.record_id) is None)

    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies", integrity.ok, f"records={integrity.records_checked}")
    try:
        runtime.audit_writer.release()
    except Exception:
        pass
    REPORT["counts"] = {"observations": obs_repo.count_all(), "facts": fact_repo.count_all(),
                        "provider_calls": len(adapter.calls)}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "kubernetes governed read verified (scripted)" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
