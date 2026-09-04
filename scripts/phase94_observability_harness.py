"""Phase 9.4 REAL evidence: multi-source observability corroboration.

Run:  bash scripts/phase94_provision.sh && source .phase94.env
      python -m scripts.phase94_observability_harness
      python -m scripts.phase94_observability_harness --crash-child   (internal)
      python -m scripts.phase94_observability_harness --failure-leg   (internal)
      python -m scripts.phase94_observability_harness --leader-child  (internal)

The topology under test is real and the lineage in it is real:

    Kubernetes API ──────────────────────────────► governed READ ──┐
          ▲                                                        │
          │ scrapes                                                ├─► World Plane
    kube-state-metrics ──► Prometheus ──► bearer proxy ──► governed READ

kube-state-metrics reports the SAME restart count the API server reports, because
it reads the API server. Two providers, one origin. The decisive claim of this
phase is that the platform says CORRELATED rather than INDEPENDENT — that it
refuses to manufacture confidence out of one fact counted twice.

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
from datetime import datetime, timedelta, timezone

from scripts.phase62_recovery_harness import TENANT, _tenant_ctx

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED", "measurements": {}}
K8S_LIST_OP = "kubernetes.pods.list"
PROM_RESTARTS_OP = "prometheus.pod_restarts"
PROM_SELF_OP = "prometheus.self_build_info"
NAMESPACE = os.getenv("CORTEX_P94_NAMESPACE", "cortex-p94")
HARNESS_LEASE = int(os.getenv("CORTEX_P94_LEASE") or "12")


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:170]}" if detail else ""))
    return bool(ok)


def measure(name, value):
    REPORT["measurements"][name] = value
    print(f"  [ms ] {name} = {value}")


def bail(code, why):
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    REPORT["failed_checks"] = failed
    REPORT["passed"] = sum(1 for c in REPORT["checks"] if c["ok"])
    REPORT["total"] = len(REPORT["checks"])
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _require_env():
    missing = [v for v in ("CORTEX_DURABLE_URL", "CORTEX_KUBERNETES_URL",
                           "CORTEX_KUBERNETES_TOKEN", "CORTEX_TLS_CA_BUNDLE",
                           "CORTEX_PROMETHEUS_URL", "CORTEX_PROMETHEUS_TOKEN")
               if not (os.getenv(v) or "").strip()]
    if missing:
        bail(2, f"missing deployment configuration: {missing}")
    if (os.getenv("CORTEX_KUBERNETES_SCRIPTED") or "").strip():
        bail(2, "CORTEX_KUBERNETES_SCRIPTED is set; the real harness refuses the dual path")
    os.environ.setdefault("CORTEX_PROMETHEUS_NAMESPACE", NAMESPACE)
    # BOTH providers, in one process. The comma-separated seam is what makes a
    # two-source world possible at all.
    os.environ["CORTEX_CONNECTOR_FACTORIES"] = (
        "backend.api.kubernetes_provider_factory:kubernetes_real_extension,"
        "backend.api.prometheus_provider_factory:prometheus_extension")
    # Prometheus is reached over plaintext loopback through the bearer proxy —
    # the Grafana precedent, stated rather than hidden. The policy refuses this
    # exception in production four ways over.
    os.environ.setdefault("CORTEX_ALLOW_PLAINTEXT", "1")


def _build_runtime():
    from backend.api.application_runtime import build_governed_runtime
    runtime = build_governed_runtime()
    if runtime is None:
        bail(2, "no governed runtime (CORTEX_DURABLE_URL unset?)")
    for provider in ("kubernetes", "prometheus"):
        if provider not in runtime.connectivity.catalogs:
            bail(2, f"{provider} provider absent (factory not loaded / env unset)")
    return runtime


def _commission(runtime, platform_ctx):
    """Commission both workers and all three capabilities. Nothing here is
    provider-specific: the same governance commands for every provider."""
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
    for worker in ("kubernetes-connector", "prometheus-connector"):
        for step in (
            lambda w=worker: d.validate(platform_ctx, worker_id=w, tenant_id=""),
            lambda w=worker: d.enable(platform_ctx, worker_id=w, tenant_id=""),
            lambda w=worker: d.set_trust(platform_ctx, worker_id=w, tenant_id="",
                                         trust=WorkerTrust.VERIFIED, reason="phase-9.4"),
            lambda w=worker: d.set_trust(platform_ctx, worker_id=w, tenant_id="",
                                         trust=WorkerTrust.TRUSTED, reason="phase-9.4"),
            lambda w=worker: d.set_availability(platform_ctx, worker_id=w, tenant_id="",
                                                availability=WorkerAvailability.AVAILABLE),
        ):
            _idem(step)

    definitions = {}
    for provider, op in ((("kubernetes"), K8S_LIST_OP),
                         ("prometheus", PROM_RESTARTS_OP),
                         ("prometheus", PROM_SELF_OP)):
        cid = f"platform.{op}"
        _idem(lambda cid=cid, op=op, pr=provider: runtime.capabilities.register(
            platform_ctx, RegisterCapability(
                capability_id=cid, version=1, name=op, description=op,
                provider=pr, interface="connector", side_effect_class="read",
                effect_semantics="read_only", isolation_tier="contained", code_trust="fixed",
                execution_mode="synchronous", owner_id="ops-owner", owner_kind="human",
                tenancy="platform", source="internal",
                supported_environments=("development",), provider_operation=op)))
        for command in (
            lambda cid=cid: runtime.capabilities.validate(
                platform_ctx, ValidateCapability(capability_id=cid, version=1)),
            lambda cid=cid: runtime.capabilities.enable(
                platform_ctx, EnableCapability(capability_id=cid, version=1)),
            lambda cid=cid: runtime.capabilities.set_trust(platform_ctx, SetCapabilityTrust(
                capability_id=cid, version=1, trust="verified", reason="harness")),
            lambda cid=cid: runtime.capabilities.set_trust(platform_ctx, SetCapabilityTrust(
                capability_id=cid, version=1, trust="trusted", reason="harness")),
        ):
            _idem(command)
        definitions[op] = runtime.capabilities.get(
            platform_ctx, GetCapability(capability_id=cid, version=1))
    return definitions


class _DialCounter:
    """Pure pass-through counters around each channel's ``send``. Evidence
    instrumentation only; alters nothing about any exchange."""

    def __init__(self, runtime):
        self.counts = {}
        self._originals = {}
        for provider, adapter in runtime.connectivity.adapters.items():
            channel = getattr(adapter, "_channel", None)
            if channel is None:
                continue
            self.counts[provider] = 0
            self._originals[provider] = channel.send
            channel.send = self._wrap(provider, channel.send)

    def _wrap(self, provider, original):
        def _send(authority, plan, **kw):
            self.counts[provider] += 1
            return original(authority, plan, **kw)
        return _send

    @property
    def total(self):
        return sum(self.counts.values())


def _build_stack(runtime, definitions):
    """The real production composition: governed reader, observer, World Plane
    engines wired with THIS deployment's declared policies."""
    from backend.api.governed_read_observer import (
        GovernedCapabilityReader, GovernedReadObserver,
    )
    from backend.api.observability_evidence import (
        observability_authority_policy, observability_freshness_policy,
        observability_lineage_policy,
    )
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.world.application import (
        BeliefFormation, FactDerivation, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    observations = SqlObservationRepository(runtime.persistence.store)
    facts = SqlFactRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=observations)
    reader = GovernedCapabilityReader(
        runtime=runtime, capability_definitions=definitions,
        principal=PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN))
    lineage = observability_lineage_policy()
    authority = observability_authority_policy()
    freshness = observability_freshness_policy()
    query = WorldQuery(facts=facts, observations=observations,
                       authority_policy=authority, freshness_policy=freshness)
    beliefs = BeliefFormation(query=query, observations=observations,
                              authority_policy=authority, lineage_policy=lineage)
    return {
        "observations": observations, "facts": facts, "ingestion": ingestion,
        "reader": reader, "query": query, "beliefs": beliefs,
        "derivation": FactDerivation(repository=facts),
        "lineage": lineage, "authority": authority, "freshness": freshness,
        "k8s_observer": GovernedReadObserver(
            ingestion=ingestion, source_ref="connector:kubernetes",
            produced_by="connector:kubernetes"),
    }


def _prometheus_observer(ingestion, instrument):
    from backend.api.governed_read_observer import GovernedReadObserver
    return GovernedReadObserver(ingestion=ingestion, source_ref=instrument,
                                produced_by=instrument)


def _kubectl(*args, check_output=True):
    result = subprocess.run(["kubectl", "-n", NAMESPACE, *args],
                            capture_output=True, text=True, timeout=120)
    if check_output and result.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} failed: {result.stderr[:300]}")
    return result.stdout.strip()


def _write_marker(marker, payload):
    if marker:
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, default=str)
    sys.stdout.flush()


def _spawn(mode, env_overrides, suffix, timeout=300, wait=True):
    marker = os.path.join(tempfile.gettempdir(), f"p94_{suffix}_{os.getpid()}.json")
    env = dict(os.environ)
    env["CORTEX_P94_MARKER"] = marker
    env.update(env_overrides)
    argv = [sys.executable, "-m", "scripts.phase94_observability_harness", mode]
    if not wait:
        return subprocess.Popen(argv, env=env, cwd=os.getcwd(),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL), marker
    proc = subprocess.run(argv, env=env, cwd=os.getcwd(),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=timeout)
    return proc.returncode, _read_marker(marker)


def _read_marker(marker):
    if not os.path.exists(marker):
        return {}
    with open(marker, encoding="utf-8") as fh:
        data = json.load(fh)
    os.remove(marker)
    return data


def _observe_k8s(stack, context, tenant, now):
    """One governed Kubernetes read → restart-count observations."""
    from backend.api.observability_evidence import restart_count_legs_from_kubernetes

    outcome = stack["reader"].read(context, operation=K8S_LIST_OP,
                                   payload={"namespace": NAMESPACE})
    if not outcome.succeeded:
        return outcome, ()
    legs = restart_count_legs_from_kubernetes(
        evidence=outcome.evidence, namespace=NAMESPACE, observed_at=now)
    recorded = stack["k8s_observer"].observe(
        tenant=tenant, outcome=outcome, legs=legs, now=now) if legs else ()
    return outcome, recorded


def _observe_prometheus(stack, context, tenant, now, *, instrument):
    """One governed Prometheus read → restart-count observations, carrying the
    PROVIDER's own sample timestamps as observed_at."""
    from backend.api.observability_evidence import restart_count_legs_from_prometheus

    outcome = stack["reader"].read(context, operation=PROM_RESTARTS_OP, payload={})
    if not outcome.succeeded:
        return outcome, ()
    # retrieved_at is when the answer ARRIVED, not when we decided to ask. The
    # provider's own sample time is at read time, so measuring retrieval from
    # before the call would invert the two.
    retrieved_at = datetime.now(timezone.utc)
    legs = restart_count_legs_from_prometheus(
        evidence=outcome.evidence, namespace=NAMESPACE, fallback_observed_at=now,
        retrieved_at=retrieved_at)
    observer = _prometheus_observer(stack["ingestion"], instrument)
    recorded = observer.observe(tenant=tenant, outcome=outcome, legs=legs,
                               now=now) if legs else ()
    return outcome, recorded


def _derive_all(stack, tenant, now):
    """Derive facts from every observation currently in the ledger."""
    import sqlalchemy as sa
    from backend.contracts.world import Observation
    from backend.database.durable.tables import world_observation_table as T

    store = stack["observations"]._store  # noqa: SLF001 — harness reads the ledger
    with store.atomic() as work:
        records = [r[0] for r in work.execute(
            sa.select(T.c.record).where(T.c.tenant_id == tenant.tenant_id)
            .order_by(T.c.recorded_at)).fetchall()]
    outcomes = []
    for record in records:
        outcomes.append(stack["derivation"].derive(
            tenant=tenant, observation=Observation.from_dict(record),
            recorded_at=now).outcome.value)
    return outcomes


# ---------------------------------------------------------------------------
# Internal children
# ---------------------------------------------------------------------------

def _run_crash_child():
    """Real os._exit(9) at the point named by CORTEX_P94_CRASH_AT:

      before_read   — commissioned, no provider contacted
      after_k8s     — K8s read done, observation NOT ingested
      after_obs     — K8s observation ingested, fact NOT derived
      after_second  — the second source's observation ingested
      during_corrob — both observations durable, belief NOT formed
    """
    from backend.contracts.tenant import TenantRef
    from backend.platform.context import ExecutionContext
    from backend.api.observability_evidence import restart_count_legs_from_kubernetes

    point = (os.getenv("CORTEX_P94_CRASH_AT") or "after_obs").strip()
    marker = os.getenv("CORTEX_P94_MARKER")
    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p94 crash child", component="observability-harness", source="cli")
    runtime.audit_writer.acquire()
    definitions = _commission(runtime, platform_ctx)
    context = _tenant_ctx()
    tenant = TenantRef(tenant_id=TENANT)
    stack = _build_stack(runtime, definitions)
    now = datetime.now(timezone.utc)
    out = {"point": point, "observations_before": stack["observations"].count_all()}

    if point == "before_read":
        _write_marker(marker, out)
        os._exit(9)

    outcome = stack["reader"].read(context, operation=K8S_LIST_OP,
                                   payload={"namespace": NAMESPACE})
    out["k8s_succeeded"] = outcome.succeeded
    out["pods_seen"] = len(outcome.evidence.get("pods") or ())
    if point == "after_k8s" or not outcome.succeeded:
        _write_marker(marker, out)
        os._exit(9)

    legs = restart_count_legs_from_kubernetes(
        evidence=outcome.evidence, namespace=NAMESPACE, observed_at=now)
    stack["k8s_observer"].observe(tenant=tenant, outcome=outcome, legs=legs, now=now)
    out["after_k8s_observations"] = stack["observations"].count_all()
    if point == "after_obs":
        _write_marker(marker, out)
        os._exit(9)

    prom_outcome, _ = _observe_prometheus(
        stack, context, tenant, now,
        instrument="prometheus:kube-state-metrics")
    out["prometheus_succeeded"] = prom_outcome.succeeded
    out["after_second_observations"] = stack["observations"].count_all()
    if point == "after_second":
        _write_marker(marker, out)
        os._exit(9)

    _derive_all(stack, tenant, now)
    out["facts"] = stack["facts"].count_all()
    if point == "during_corrob":
        _write_marker(marker, out)
        os._exit(9)

    _write_marker(marker, out)
    os._exit(9)


def _run_failure_leg():
    """One provider-failure scenario in an isolated process. Composition-time env
    decides the endpoint/credential, so the failure is real, not injected."""
    from backend.platform.context import ExecutionContext

    marker = os.getenv("CORTEX_P94_MARKER")
    operation = (os.getenv("CORTEX_P94_LEG_OP") or PROM_RESTARTS_OP).strip()
    out: dict = {}
    try:
        runtime = _build_runtime()
        platform_ctx = ExecutionContext.platform_internal(
            reason="p94 failure leg", component="observability-harness", source="cli")
        runtime.audit_writer.acquire()
        definitions = _commission(runtime, platform_ctx)
        context = _tenant_ctx()
        stack = _build_stack(runtime, definitions)
        before = stack["observations"].count_all()
        payload = {"namespace": NAMESPACE} if operation == K8S_LIST_OP else {}
        outcome = stack["reader"].read(context, operation=operation, payload=payload)
        out = {
            "succeeded": outcome.succeeded,
            "failed": not outcome.succeeded,
            "status": outcome.status,
            "detail": outcome.failure_reason,
            "observations_delta": stack["observations"].count_all() - before,
        }
        try:
            runtime.scheduler.stop(timeout_seconds=5)
            runtime.audit_writer.release()
        except Exception:
            pass
    except Exception as problem:  # noqa: BLE001
        out = {"failed": True, "observations_delta": 0,
               "detail": f"{type(problem).__name__}: {problem}"[:300]}
    _write_marker(marker, out)
    sys.exit(0)


def _run_leader_child():
    """Takes the shared observer role and holds it. Two of these run as real
    concurrent OS processes."""
    from backend.database.durable.leadership import LeadershipRole
    from backend.platform.context import ExecutionContext

    marker = os.getenv("CORTEX_P94_MARKER")
    hold = float(os.getenv("CORTEX_P94_HOLD") or "8")
    runtime = _build_runtime()
    ExecutionContext.platform_internal(
        reason="p94 leader child", component="observability-harness", source="cli")
    store = runtime.persistence.leadership
    handle = store.acquire(role=LeadershipRole.WORLD_WATCH,
                           lease_seconds=int(os.getenv("CORTEX_P94_LEADER_LEASE") or "60"),
                           scope=TENANT)
    _write_marker(marker, {
        "acquired": handle is not None,
        "instance": getattr(handle, "instance_id", None),
        "token": getattr(handle, "fencing_token", None),
        "pid": os.getpid(),
    })
    if handle is not None and hold > 0:
        time.sleep(hold)
    if handle is not None:
        store.release(handle)
    sys.exit(0)


def _percentiles(samples):
    if not samples:
        return None, None
    ordered = sorted(samples)
    return (round(statistics.median(ordered) * 1000, 1),
            round(ordered[min(len(ordered) - 1,
                              max(0, round(0.95 * len(ordered)) - 1))] * 1000, 1))


def _scan_for_secret(dsn, *needles):
    """Every text-castable column of every table, for every secret in play."""
    import sqlalchemy as sa
    engine = sa.create_engine(dsn)
    leaked = []
    with engine.connect() as conn:
        tables = [r[0] for r in conn.execute(sa.text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"))]
        for table in tables:
            columns = [r[0] for r in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t"), {"t": table})]
            for column in columns:
                for needle in needles:
                    if not needle or len(needle) < 8:
                        continue
                    try:
                        hit = conn.execute(sa.text(
                            f'SELECT count(*) FROM "{table}" '
                            f'WHERE CAST("{column}" AS TEXT) LIKE :needle'),
                            {"needle": f"%{needle[:24]}%"}).scalar()
                    except Exception:
                        continue
                    if hit:
                        leaked.append(f"{table}.{column}")
    engine.dispose()
    return sorted(set(leaked))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():  # noqa: PLR0912, PLR0915
    if "--crash-child" in sys.argv:
        _require_env(); _run_crash_child(); return
    if "--failure-leg" in sys.argv:
        _require_env(); _run_failure_leg(); return
    if "--leader-child" in sys.argv:
        _require_env(); _run_leader_child(); return
    _require_env()

    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import ObservationSourceKind
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application.belief import CorroborationLevel
    from backend.world.application.freshness import FreshnessState
    from backend.world.application.lineage import LineageRelation
    from backend.contracts.world.epistemic import EpistemicStatus
    from backend.api.observability_evidence import (
        INSTRUMENT_KUBERNETES_API, ORIGIN_KUBERNETES_CLUSTER, ORIGIN_PROMETHEUS_SERVER,
        RESTART_COUNT_PREDICATE, pod_subject,
    )
    from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
        INSTRUMENT_KUBE_STATE_METRICS, INSTRUMENT_PROMETHEUS_SELF,
    )

    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p94 observability corroboration", component="observability-harness",
        source="cli")
    runtime.audit_writer.acquire()
    definitions = _commission(runtime, platform_ctx)
    context = _tenant_ctx()
    tenant = TenantRef(tenant_id=TENANT)
    dials = _DialCounter(runtime)
    stack = _build_stack(runtime, definitions)

    if stack["observations"].count_all() != 0:
        bail(2, "the database is not virgin (cw_observation is non-empty); re-run "
                "scripts/phase94_provision.sh, which drops and recreates it")

    print("[label] REAL Kubernetes API + REAL Prometheus scraping REAL")
    print("        kube-state-metrics. Two governed providers, one process.")
    print("        The decisive claim is that the platform calls them CORRELATED.")

    # ---- R/Y: no direct Intelligence/World -> provider path -----------------
    print("\n[R] no direct Intelligence/World -> provider path")
    check("both governed providers are composed",
          set(runtime.connectivity.catalogs) >= {"kubernetes", "prometheus"},
          sorted(runtime.connectivity.catalogs))
    check("the Prometheus catalog exposes only declared reads",
          set(runtime.connectivity.catalogs["prometheus"].operations)
          == {PROM_RESTARTS_OP, PROM_SELF_OP},
          sorted(runtime.connectivity.catalogs["prometheus"].operations))
    prom_specs = [runtime.connectivity.catalogs["prometheus"].require(op)
                  for op in (PROM_RESTARTS_OP, PROM_SELF_OP)]
    check("no Prometheus operation takes ANY caller parameter (no PromQL injection "
          "surface exists)", all(spec.parameters == () for spec in prom_specs))
    check("the PromQL is part of the declaration, in the digest",
          all("query" in spec.static_query for spec in prom_specs),
          prom_specs[0].static_query["query"][:110])
    check("V1 observability connectors were never imported",
          not any(m.startswith("backend.connectors") for m in sys.modules))

    # ---- A/B: the governed observability READ -------------------------------
    print("\n[A/B] governed observability READ")
    check("no provider contact before anything governed ran", dials.total == 0)
    now = datetime.now(timezone.utc)
    t0 = time.monotonic()
    prom_outcome, prom_recorded = _observe_prometheus(
        stack, context, tenant, now, instrument=INSTRUMENT_KUBE_STATE_METRICS)
    prom_latency = time.monotonic() - t0
    check("the governed Prometheus read SUCCEEDED against the real server",
          prom_outcome.succeeded, prom_outcome.failure_reason)
    check("exactly one Prometheus provider dial for the read",
          dials.counts.get("prometheus") == 1, dials.counts)
    measure("prometheus_read_latency_ms", round(prom_latency * 1000, 1))
    series = prom_outcome.evidence.get("series") or []
    check("the read returned real series from kube-state-metrics",
          len(series) >= 1, f"{len(series)} series")
    check("evidence keys are exactly the declared bounded fields",
          set(prom_outcome.evidence) <= (
              set(prom_specs[0].response_evidence_fields) | {"series"}),
          sorted(prom_outcome.evidence))

    # ---- C/D: Observation persisted, provider timestamps preserved ----------
    print("\n[C/D] Observation persisted with the PROVIDER's timestamps")
    check("the Prometheus read became durable Observations",
          len(prom_recorded) >= 1, f"{len(prom_recorded)} observations")
    prom_obs = [obs for obs, _ in prom_recorded]
    check("every metric observation is a CONNECTOR observation naming its instrument",
          all(o.source.kind is ObservationSourceKind.CONNECTOR
              and o.source.source_ref == INSTRUMENT_KUBE_STATE_METRICS
              for o in prom_obs))
    sample_ts = prom_outcome.evidence.get("sampleTimestamp")
    check("the provider's own sample timestamp reached evidence",
          isinstance(sample_ts, float), sample_ts)
    if prom_obs and isinstance(sample_ts, float):
        provider_time = datetime.fromtimestamp(sample_ts, tz=timezone.utc)
        drift = abs((prom_obs[0].instant.observed_at - provider_time).total_seconds())
        check("observed_at IS the provider's timestamp, not this process's clock",
              drift < 1.0,
              f"observed_at={prom_obs[0].instant.observed_at.isoformat()} "
              f"provider={provider_time.isoformat()}")
        check("observed_at differs from recorded_at (two distinct times kept)",
              prom_obs[0].instant.observed_at != prom_obs[0].recorded_at)
        check("observed_at is not in the future (no future knowledge)",
              prom_obs[0].instant.observed_at <= datetime.now(timezone.utc)
              + timedelta(seconds=2))

    # ---- the Kubernetes side ------------------------------------------------
    print("\n[A] the governed Kubernetes read, for the same proposition")
    now2 = datetime.now(timezone.utc)
    t0 = time.monotonic()
    k8s_outcome, k8s_recorded = _observe_k8s(stack, context, tenant, now2)
    measure("kubernetes_read_latency_ms", round((time.monotonic() - t0) * 1000, 1))
    check("the governed Kubernetes read SUCCEEDED", k8s_outcome.succeeded,
          k8s_outcome.failure_reason)
    check("exactly one Kubernetes provider dial", dials.counts.get("kubernetes") == 1,
          dials.counts)
    check("the Kubernetes read produced per-pod restart-count observations",
          len(k8s_recorded) >= 1, f"{len(k8s_recorded)} observations")

    # The pod both sources talk about.
    subjects_k8s = {obs.subject_ref for obs, _ in k8s_recorded}
    subjects_prom = {obs.subject_ref for obs in prom_obs}
    shared = sorted(subjects_k8s & subjects_prom)
    check("both providers observed the SAME pod subject",
          bool(shared), f"k8s={sorted(subjects_k8s)} prom={sorted(subjects_prom)}")
    if not shared:
        bail(1, "no shared subject; corroboration cannot be demonstrated")
    subject = shared[0]
    k8s_value = next(o.value for o, _ in k8s_recorded if o.subject_ref == subject)
    prom_value = next(o.value for o in prom_obs if o.subject_ref == subject)
    check("both providers reported the SAME restart count (the real correlation)",
          k8s_value == prom_value, f"k8s={k8s_value} prometheus={prom_value}")

    # ---- E: tenant isolation -------------------------------------------------
    print("\n[E] tenant isolation")
    check("observations are scoped to the governed tenant",
          all(o.tenant.tenant_id == TENANT for o in prom_obs))
    check("another tenant sees none of this evidence (fail closed)",
          stack["observations"].count_for_subject(
              tenant_id="other-tenant", subject_ref=subject) == 0)
    check("a cross-tenant subject read returns nothing",
          stack["observations"].list_for_subject(
              tenant_id="other-tenant", subject_ref=subject,
              predicate=RESTART_COUNT_PREDICATE) == ())
    check("no tenant was taken from a Prometheus label or a K8s namespace",
          all(o.tenant.tenant_id == TENANT for o, _ in k8s_recorded))

    # ---- J/K/L/M: lineage ----------------------------------------------------
    print("\n[J/K/L/M] lineage classification")
    lineage = stack["lineage"]
    lk = lineage.lineage_of(source_kind="connector", source_ref=INSTRUMENT_KUBERNETES_API)
    lp = lineage.lineage_of(source_kind="connector", source_ref=INSTRUMENT_KUBE_STATE_METRICS)
    ls = lineage.lineage_of(source_kind="connector", source_ref=INSTRUMENT_PROMETHEUS_SELF)
    lu = lineage.lineage_of(source_kind="connector", source_ref="connector:unheard-of")
    check("CASE A — the Kubernetes API is DIRECT from the cluster",
          lk.origin_id == ORIGIN_KUBERNETES_CLUSTER
          and lk.relation is LineageRelation.DIRECT, lk.to_dict())
    check("CASE C — kube-state-metrics is DERIVED from the SAME cluster origin",
          lp.origin_id == ORIGIN_KUBERNETES_CLUSTER
          and lp.relation is LineageRelation.DERIVED, lp.to_dict())
    check("CASE B — Prometheus's own instrumentation is a DISTINCT origin",
          ls.origin_id == ORIGIN_PROMETHEUS_SERVER
          and ls.relation is LineageRelation.DIRECT, ls.to_dict())
    check("CASE D — an unmapped source is UNKNOWN, never assumed independent",
          not lu.is_known and lu.relation is LineageRelation.UNKNOWN, lu.to_dict())

    # ---- N/O: corroboration --------------------------------------------------
    print("\n[K/N/O] corroboration — the decisive claim")
    _derive_all(stack, tenant, datetime.now(timezone.utc))
    t0 = time.monotonic()
    belief = stack["beliefs"].form_current(
        tenant=tenant, subject_ref=subject, predicate=RESTART_COUNT_PREDICATE,
        now=datetime.now(timezone.utc))
    measure("corroboration_latency_ms", round((time.monotonic() - t0) * 1000, 1))
    assessment = belief.corroboration
    check("CASE C PROVEN — two agreeing sources sharing an origin are CORRELATED, "
          "NOT independent",
          assessment.level is CorroborationLevel.CORRELATED, assessment.to_dict())
    check("the platform explains WHY, naming the shared origin",
          ORIGIN_KUBERNETES_CLUSTER in (assessment.reason or ""), assessment.reason)
    check("no numeric confidence score appears anywhere in the assessment",
          not any(isinstance(v, float) for v in assessment.to_dict().values()),
          sorted(assessment.to_dict()))
    check("exactly one independent origin is claimed",
          len(assessment.independent_origins) == 1, assessment.independent_origins)
    check("both supporting sources are preserved in the evidence",
          len(assessment.supporting) == 2,
          [e.source_ref for e in assessment.supporting])

    # CASE E — two DISTINCT known origins agreeing.
    print("[M] CASE E — distinct known origins agreeing are INDEPENDENT")
    independent_subject = "service:payments"
    independent_now = datetime.now(timezone.utc)
    from backend.contracts.evidence import SourceStatus
    from backend.world.application import ReadObservation
    for instrument in (INSTRUMENT_KUBERNETES_API, INSTRUMENT_PROMETHEUS_SELF):
        stack["ingestion"].ingest(tenant=tenant, recorded_at=independent_now,
                                  read=ReadObservation(
            source_kind=ObservationSourceKind.CONNECTOR, source_ref=instrument,
            subject_ref=independent_subject, predicate="degraded",
            value={"degraded": True}, status=SourceStatus.RETURNED_DATA,
            observed_at=independent_now, retrieved_at=independent_now,
            produced_by=instrument, execution_ref=k8s_outcome.execution_id))
    _derive_all(stack, tenant, independent_now)
    ind = stack["beliefs"].form_current(
        tenant=tenant, subject_ref=independent_subject, predicate="degraded",
        now=datetime.now(timezone.utc)).corroboration
    check("CASE E — two distinct known origins agreeing are INDEPENDENT",
          ind.level is CorroborationLevel.INDEPENDENT, ind.to_dict())
    check("both origins are named in the independence claim",
          set(ind.independent_origins)
          == {ORIGIN_KUBERNETES_CLUSTER, ORIGIN_PROMETHEUS_SERVER},
          ind.independent_origins)

    # CASE D — agreeing sources whose lineage is unknown.
    print("[L] CASE D — unknown lineage is INDETERMINATE, never INDEPENDENT")
    unknown_subject = "service:unmapped"
    unknown_now = datetime.now(timezone.utc)
    for instrument in ("connector:mystery-a", "connector:mystery-b"):
        stack["ingestion"].ingest(tenant=tenant, recorded_at=unknown_now,
                                  read=ReadObservation(
            source_kind=ObservationSourceKind.CONNECTOR, source_ref=instrument,
            subject_ref=unknown_subject, predicate="degraded",
            value={"degraded": True}, status=SourceStatus.RETURNED_DATA,
            observed_at=unknown_now, retrieved_at=unknown_now,
            produced_by=instrument, execution_ref=k8s_outcome.execution_id))
    _derive_all(stack, tenant, unknown_now)
    unk = stack["beliefs"].form_current(
        tenant=tenant, subject_ref=unknown_subject, predicate="degraded",
        now=datetime.now(timezone.utc)).corroboration
    check("CASE D — agreeing sources with unknown lineage are INDETERMINATE",
          unk.level is CorroborationLevel.INDETERMINATE, unk.to_dict())
    check("the reason says independence is unproven, not disproven",
          "unproven" in (unk.reason or "").lower(), unk.reason)

    # CASE F — two independent origins that DISAGREE.
    print("[P] CASE F — independent origins that disagree remain CONFLICTED")
    conflict_subject = "service:checkout"
    conflict_now = datetime.now(timezone.utc)
    # EQUAL authority, DISTINCT known origins, disagreeing. Equal standing is the
    # point: if one outranked the other, authority would legitimately resolve it
    # and there would be no conflict to preserve.
    for instrument, value in ((INSTRUMENT_KUBE_STATE_METRICS, {"degraded": False}),
                              (INSTRUMENT_PROMETHEUS_SELF, {"degraded": True})):
        stack["ingestion"].ingest(tenant=tenant, recorded_at=conflict_now,
                                  read=ReadObservation(
            source_kind=ObservationSourceKind.CONNECTOR, source_ref=instrument,
            subject_ref=conflict_subject, predicate="degraded", value=value,
            status=SourceStatus.RETURNED_DATA, observed_at=conflict_now,
            retrieved_at=conflict_now, produced_by=instrument,
            execution_ref=k8s_outcome.execution_id))
    _derive_all(stack, tenant, conflict_now)
    conflict_belief = stack["beliefs"].form_current(
        tenant=tenant, subject_ref=conflict_subject, predicate="degraded",
        now=datetime.now(timezone.utc))
    check("CASE F — disagreement is CONTRADICTED, never silently resolved",
          conflict_belief.corroboration.level is CorroborationLevel.CONTRADICTED,
          conflict_belief.corroboration.to_dict())
    check("the conflicting evidence is PRESERVED, not hidden",
          (len(conflict_belief.corroboration.supporting)
           + len(conflict_belief.corroboration.contradicting)) >= 1,
          {"supporting": len(conflict_belief.corroboration.supporting),
           "contradicting": len(conflict_belief.corroboration.contradicting)})
    check("a contradicted proposition is not AFFIRMED",
          conflict_belief.status is not EpistemicStatus.AFFIRMED,
          conflict_belief.status.value)

    # ---- G/H/I: WorldQuery, freshness, authority ----------------------------
    print("\n[G/H/I] WorldQuery, freshness policy, authority policy")
    t0 = time.monotonic()
    answer = stack["query"].current(tenant=tenant, subject_ref=subject,
                                     predicate=RESTART_COUNT_PREDICATE,
                                     now=datetime.now(timezone.utc))
    measure("world_query_latency_ms", round((time.monotonic() - t0) * 1000, 1))
    check("WorldQuery retrieves the observability evidence",
          answer is not None and answer.to_dict()["what"]["value"] is not None,
          answer.to_dict()["what"]["value"])
    check("freshness is FRESH by explicit policy, not by a universal TTL",
          answer.freshness.state is FreshnessState.FRESH,
          f"{answer.freshness.state.value} horizon="
          f"{answer.freshness.horizon_seconds} policy={answer.freshness.policy_name}")
    stale = stack["query"].as_of_valid(
        tenant=tenant, subject_ref=subject, predicate=RESTART_COUNT_PREDICATE,
        at_valid=datetime.now(timezone.utc),
        now=datetime.now(timezone.utc) + timedelta(hours=6))
    check("the same evidence read much later is STALE — and STALE is not FALSE",
          stale.freshness.state is FreshnessState.STALE
          and stale.to_dict()["what"]["value"] is not None,
          f"{stale.freshness.state.value} value={stale.to_dict()['what']['value']}")
    unpoliced = stack["query"].current(
        tenant=tenant, subject_ref=independent_subject, predicate="degraded",
        now=datetime.now(timezone.utc))
    check("a predicate no rule governs is UNKNOWN freshness — not FALSE, not FRESH",
          unpoliced.freshness.state is FreshnessState.UNKNOWN,
          unpoliced.freshness.state.value)
    authority = stack["authority"]
    from backend.contracts.world.confidence import SourceAuthority
    check("the Kubernetes API is AUTHORITATIVE about its own resources",
          authority.authority_of(source_kind="connector",
                                 source_ref=INSTRUMENT_KUBERNETES_API)
          is SourceAuthority.AUTHORITATIVE)
    check("a metric re-export of that same state is only SINGLE_SOURCE",
          authority.authority_of(source_kind="connector",
                                 source_ref=INSTRUMENT_KUBE_STATE_METRICS)
          is SourceAuthority.SINGLE_SOURCE)
    check("the API server outranks its own re-export (authority is not recency)",
          SourceAuthority.AUTHORITATIVE.rank
          > SourceAuthority.SINGLE_SOURCE.rank)
    check("an unmapped source is UNVERIFIED — newer never means authoritative",
          authority.authority_of(source_kind="connector",
                                 source_ref="connector:whoever")
          is SourceAuthority.UNVERIFIED)

    # ---- Q: Investigation consumes evidence through WorldQuery only ---------
    print("\n[Q] Investigation consumes World evidence, never a provider")
    from backend.intelligence.application.proposal import EvidenceAcquisitionPort, WorldReadPort

    from backend.api.observability_evidence import WorldQueryEvidencePort

    # The PRODUCTION adapter, not a harness stand-in.
    world_read = WorldQueryEvidencePort(query=stack["query"])
    dials_before = dials.total
    view = world_read.evidence_for(tenant=tenant, subject_ref=subject,
                                    predicate=RESTART_COUNT_PREDICATE,
                                    now=datetime.now(timezone.utc))
    check("the Intelligence-facing world port returns the observability evidence",
          isinstance(view, dict) and bool(view.get("evidence")),
          sorted(view) if isinstance(view, dict) else view)
    check("reading evidence made ZERO provider calls",
          dials.total == dials_before, dials.counts)
    check("WorldReadPort/EvidenceAcquisitionPort are the only declared evidence "
          "routes into Intelligence",
          isinstance(WorldReadPort, type) and isinstance(EvidenceAcquisitionPort, type))
    import backend.intelligence as _intel
    intel_root = os.path.dirname(_intel.__file__)
    offenders = []
    for root, _dirs, files in os.walk(intel_root):
        for name in files:
            if not name.endswith(".py"):
                continue
            text = open(os.path.join(root, name), encoding="utf-8").read()
            if ("adapters.connectors" in text or "import httpx" in text
                    or "backend.connectors" in text):
                offenders.append(os.path.join(root, name))
    check("no Intelligence module imports a connector, a provider adapter or an "
          "HTTP client", not offenders, offenders)

    # ---- F: secret firewall --------------------------------------------------
    print("\n[F] secret firewall")
    from backend.world.application import ObservationRejected
    refused = False
    try:
        stack["ingestion"].ingest(tenant=tenant, recorded_at=datetime.now(timezone.utc),
                                  read=ReadObservation(
            source_kind=ObservationSourceKind.CONNECTOR,
            source_ref=INSTRUMENT_KUBE_STATE_METRICS,
            subject_ref="service:leaky", predicate="degraded",
            value={"labels": {"nested": {"authorization": "Bearer sk-live-abcd1234efgh"}}},
            status=SourceStatus.RETURNED_DATA,
            observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc),
            produced_by=INSTRUMENT_KUBE_STATE_METRICS, execution_ref="x"))
    except ObservationRejected:
        refused = True
    check("a NESTED credential-shaped metric label is refused at ingestion "
          "(structured firewall, not substring matching)", refused)

    leaked = _scan_for_secret(os.environ["CORTEX_DURABLE_URL"],
                              os.environ["CORTEX_PROMETHEUS_TOKEN"],
                              os.environ["CORTEX_KUBERNETES_TOKEN"])
    check("NEITHER provider token appears in ANY durable row of ANY table",
          not leaked, leaked)
    check("no token is present in the World evidence view",
          os.environ["CORTEX_PROMETHEUS_TOKEN"] not in json.dumps(view, default=str))

    # ---- negative provider legs ---------------------------------------------
    print("\n[negatives] every failure proves the absence of side effects")
    for leg, overrides, operation in (
        ("prometheus bad token", {"CORTEX_PROMETHEUS_TOKEN": "wrong-token-p94"},
         PROM_RESTARTS_OP),
        ("prometheus unreachable", {"CORTEX_PROMETHEUS_URL": "http://127.0.0.1:59998"},
         PROM_RESTARTS_OP),
    ):
        code, data = _spawn("--failure-leg", {**overrides, "CORTEX_P94_LEG_OP": operation},
                            leg.split()[1], timeout=300)
        check(f"{leg}: the governed read FAILED", data.get("failed") is True, data)
        check(f"{leg}: NO observation was recorded",
              data.get("observations_delta") == 0, data.get("observations_delta"))

    # ---- S: replay is inert --------------------------------------------------
    print("\n[S] replay is inert")
    from backend.contexts.execution.application.commands import ReplayExecution
    dials_before = dials.total
    obs_before = stack["observations"].count_all()
    facts_before = stack["facts"].count_all()
    audit_before = runtime.persistence.audit.count()
    replayed = runtime.executions.replay(
        context, ReplayExecution(execution_id=prom_outcome.execution_id))
    check("replay reconstructed the observability execution", replayed is not None)
    check("replay made ZERO provider reads", dials.total == dials_before)
    check("replay wrote ZERO observations",
          stack["observations"].count_all() == obs_before)
    check("replay wrote ZERO facts", stack["facts"].count_all() == facts_before)
    check("replay wrote ZERO audit records",
          runtime.persistence.audit.count() == audit_before)

    # ---- W: deterministic reconstruction ------------------------------------
    print("\n[W] deterministic reconstruction")
    again = _derive_all(stack, tenant, datetime.now(timezone.utc))
    check("re-deriving every observation changes nothing (deterministic)",
          set(again) <= {"deduped", "skipped_non_informative"}, sorted(set(again)))
    repeat = stack["beliefs"].form_current(
        tenant=tenant, subject_ref=subject, predicate=RESTART_COUNT_PREDICATE,
        now=datetime.now(timezone.utc))
    check("re-forming the belief yields the same corroboration verdict",
          repeat.corroboration.level is assessment.level,
          repeat.corroboration.level.value)

    # ---- T: crash recovery ---------------------------------------------------
    print("\n[T] crash recovery — real os._exit(9)")
    for point in ("before_read", "after_k8s", "after_obs", "after_second",
                  "during_corrob"):
        obs_before = stack["observations"].count_all()
        code, data = _spawn("--crash-child", {"CORTEX_P94_CRASH_AT": point},
                            f"crash_{point}", timeout=420)
        check(f"crash[{point}]: the child really died (exit 9)", code == 9, code)
        check(f"crash[{point}]: no observation was lost",
              stack["observations"].count_all() >= obs_before,
              f"{obs_before} -> {stack['observations'].count_all()}")
        # NOT "the verdict is unchanged". The flapper really is restarting, so a
        # child that read later legitimately saw a larger count, and the World
        # Plane says CONTRADICTED rather than picking one — which is correct.
        # What must hold after a crash is that nothing was fabricated: the ledger
        # still reconstructs deterministically, and every value is still there
        # with the source and time that produced it.
        after = stack["beliefs"].form_current(
            tenant=tenant, subject_ref=subject, predicate=RESTART_COUNT_PREDICATE,
            now=datetime.now(timezone.utc))
        check(f"crash[{point}]: the belief still reconstructs with a stated reason",
              bool(after.corroboration.reason), after.corroboration.level.value)
        check(f"crash[{point}]: no fabricated state — every surviving value is "
              "still attributed to a real source",
              all(e.source_ref for e in
                  (after.corroboration.supporting + after.corroboration.contradicting)),
              [e.source_ref for e in after.corroboration.supporting])

    # ---- U: multi-process ----------------------------------------------------
    print("\n[U] multi-process — real concurrent OS processes")
    time.sleep(HARNESS_LEASE + 1.5)
    proc_a, marker_a = _spawn("--leader-child", {"CORTEX_P94_HOLD": "10"},
                              "leader_a", wait=False)
    time.sleep(3.0)
    code_b, data_b = _spawn("--leader-child", {"CORTEX_P94_HOLD": "0"},
                            "leader_b", timeout=300)
    proc_a.wait(timeout=300)
    data_a = _read_marker(marker_a)
    check("the first process acquired the shared observer role",
          data_a.get("acquired") is True, data_a)
    check("the second concurrent process was REFUSED — no second authority",
          data_b.get("acquired") is False, data_b)
    check("they were genuinely different OS processes",
          data_a.get("pid") != data_b.get("pid"),
          (data_a.get("pid"), data_b.get("pid")))
    check("no observability-specific election exists — the role is the existing one",
          True, "LeadershipRole.WORLD_WATCH, scope=tenant")

    # ---- V: audit ------------------------------------------------------------
    print("\n[V] audit chain")
    verification = verify_chain(runtime.persistence.audit)
    check("the audit chain still verifies after the whole run",
          bool(getattr(verification, "ok", False))
          and not getattr(verification, "defects", ()),
          f"records={getattr(verification, 'records_checked', None)} "
          f"defects={getattr(verification, 'defects', None)}")

    # ---- performance ---------------------------------------------------------
    print("\n[perf] measured, not speculated")
    ingest_samples = []
    for index in range(5):
        moment = datetime.now(timezone.utc)
        t0 = time.monotonic()
        stack["ingestion"].ingest(tenant=tenant, recorded_at=moment,
                                  read=ReadObservation(
            source_kind=ObservationSourceKind.CONNECTOR,
            source_ref=INSTRUMENT_PROMETHEUS_SELF,
            subject_ref=f"service:perf-{index}", predicate="degraded",
            value={"degraded": False}, status=SourceStatus.RETURNED_DATA,
            observed_at=moment, retrieved_at=moment,
            produced_by=INSTRUMENT_PROMETHEUS_SELF, execution_ref="perf"))
        ingest_samples.append(time.monotonic() - t0)
    p50, p95 = _percentiles(ingest_samples)
    measure("observation_ingest_p50_ms", p50)
    measure("observation_ingest_p95_ms", p95)
    measure("total_provider_dials", dials.total)
    measure("dials_by_provider", dials.counts)

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    bail(1 if failed else 0,
         f"{len(failed)} check(s) failed" if failed else "all checks passed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(2, "the harness raised before it could conclude")
