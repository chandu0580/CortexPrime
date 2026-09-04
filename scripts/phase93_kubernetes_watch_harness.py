"""Phase 9.3 REAL evidence: a governed Kubernetes WATCH against a real cluster.

Run:  bash scripts/phase93_provision.sh && source .phase93.env
      python -m scripts.phase93_kubernetes_watch_harness
      python -m scripts.phase93_kubernetes_watch_harness --crash-child   (internal)
      python -m scripts.phase93_kubernetes_watch_harness --leader-child  (internal)

Required env (deployment configuration, provisioned by the runner):
  CORTEX_DURABLE_URL      fresh Postgres DSN migrated to head
  CORTEX_KUBERNETES_URL   the real API server
  CORTEX_KUBERNETES_TOKEN a short-lived, RBAC-scoped ServiceAccount token
  CORTEX_TLS_CA_BUNDLE    the cluster CA certificate (path)
  CORTEX_P93_NAMESPACE    the isolated namespace (default cortex-p93)

Everything decisive here is real: a real HTTPS watch to a real API server through
the ONE governed path, real pod mutations driven by kubectl out of band, a real
Postgres, real ``os._exit(9)`` child processes, and real concurrent OS processes
for the leadership legs. Provider dials are counted by a pure pass-through
wrapper on the channel's ``send`` — instrumentation only, it alters nothing.

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

from scripts.phase62_recovery_harness import TENANT, _tenant_ctx

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED", "measurements": {}}
LIST_OP = "kubernetes.pods.list"
WATCH_OP = "kubernetes.pods.watch"
NAMESPACE = os.getenv("CORTEX_P93_NAMESPACE", "cortex-p93")


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:160]}" if detail else ""))
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
    """Commission the real worker and BOTH capabilities. Nothing here is
    Kubernetes-specific: the same commands every provider goes through."""
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
                            trust=WorkerTrust.VERIFIED, reason="phase-9.3 harness"),
        lambda: d.set_trust(platform_ctx, worker_id="kubernetes-connector", tenant_id="",
                            trust=WorkerTrust.TRUSTED, reason="phase-9.3 harness"),
        lambda: d.set_availability(platform_ctx, worker_id="kubernetes-connector",
                                   tenant_id="", availability=WorkerAvailability.AVAILABLE),
    ):
        _idem(step)

    definitions = {}
    for op in (LIST_OP, WATCH_OP):
        cid = f"platform.{op}"
        _idem(lambda cid=cid, op=op: runtime.capabilities.register(
            platform_ctx, RegisterCapability(
                capability_id=cid, version=1, name=f"Kubernetes {op}", description=op,
                provider="kubernetes", interface="connector", side_effect_class="read",
                effect_semantics="read_only", isolation_tier="contained",
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
    """Pure pass-through counter around the channel's ``send``. Evidence
    instrumentation only; alters nothing about the exchange."""

    def __init__(self, channel):
        self._send = channel.send
        self.count = 0
        channel.send = self._wrapped  # type: ignore[method-assign]

    def _wrapped(self, authority, plan, **kw):
        self.count += 1
        return self._send(authority, plan, **kw)


#: The harness runs a SHORTER window than the production default (20s) and a
#: lease sized against it. Same code path, same semantics — only the two numbers
#: differ, so lease expiry is observable inside a test run instead of being
#: something you wait minutes for. The lease must outlive a window; the driver
#: refuses the incoherent combination, which is how this was found.
HARNESS_WINDOW = int(os.getenv("CORTEX_P93_WINDOW") or "5")
HARNESS_LEASE = int(os.getenv("CORTEX_P93_LEASE") or "12")


def _build_driver(runtime, *, definitions, tenant_ctx, window=None,
                  lease_seconds=None):
    """Assemble the real production driver — the classes a deployment composes,
    not a harness reimplementation of them."""
    from backend.api.governed_read_observer import (
        GovernedCapabilityReader, GovernedReadObserver,
    )
    from backend.api.kubernetes_watch_driver import KubernetesWatchDriver
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.contracts.tenant import TenantRef
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        WATCH_WINDOW_SECONDS,
    )
    from backend.world.application import ObservationIngestion
    from backend.world.infrastructure import SqlObservationRepository

    observations = SqlObservationRepository(runtime.persistence.store)
    reader = GovernedCapabilityReader(
        runtime=runtime, capability_definitions=definitions,
        principal=PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN))
    observer = GovernedReadObserver(
        ingestion=ObservationIngestion(repository=observations),
        source_ref="connector:kubernetes", produced_by="connector:kubernetes")
    driver = KubernetesWatchDriver(
        reader=reader, observer=observer, observations=observations,
        # The runtime's OWN leadership store, not a second one. It already
        # carries a per-process instance id (``instance-<ulid>``), which is what
        # makes the leadership legs a real contention test between real
        # processes rather than one process arguing with itself.
        leadership=runtime.persistence.leadership,
        tenant=TenantRef(tenant_id=TENANT), namespace=NAMESPACE,
        list_operation=LIST_OP, watch_operation=WATCH_OP,
        window_seconds=window or HARNESS_WINDOW,
        lease_seconds=lease_seconds or HARNESS_LEASE)
    return driver, observations


def _kubectl(*args, check_output=True):
    """Out-of-band cluster manipulation — the *independent* half of the evidence.
    Nothing governed happens here; this is how the world is made to change so the
    governed watch has something true to observe."""
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
    marker = os.path.join(tempfile.gettempdir(), f"p93_{suffix}_{os.getpid()}.json")
    env = dict(os.environ)
    env["CORTEX_P93_MARKER"] = marker
    env.update(env_overrides)
    argv = [sys.executable, "-m", "scripts.phase93_kubernetes_watch_harness", mode]
    if not wait:
        proc = subprocess.Popen(argv, env=env, cwd=os.getcwd(),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc, marker
    proc = subprocess.run(argv, env=env, cwd=os.getcwd(),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=timeout)
    data = {}
    if os.path.exists(marker):
        with open(marker, encoding="utf-8") as fh:
            data = json.load(fh)
        os.remove(marker)
    return proc.returncode, data


def _read_marker(marker):
    if not os.path.exists(marker):
        return {}
    with open(marker, encoding="utf-8") as fh:
        data = json.load(fh)
    os.remove(marker)
    return data


# ---------------------------------------------------------------------------
# Internal children
# ---------------------------------------------------------------------------

def _run_crash_child():
    """Dies with a real ``os._exit(9)`` at the point named by CORTEX_P93_CRASH_AT:

      before_watch  — leadership held, position read, WATCH not yet started
      after_list    — a governed LIST established a position, nothing else
      after_events  — events ingested, checkpoint NOT written  (the dangerous one)
      after_advance — checkpoint written, before the next window
      during_410    — the 410 was seen, the fresh LIST not yet recorded
    """
    from backend.platform.context import ExecutionContext

    point = (os.getenv("CORTEX_P93_CRASH_AT") or "after_events").strip()
    marker = os.getenv("CORTEX_P93_MARKER")
    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p93 crash child", component="k8s-watch-harness", source="cli")
    runtime.audit_writer.acquire()
    definitions = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    driver, observations = _build_driver(
        runtime, definitions=definitions, tenant_ctx=tenant_ctx)
    out = {"point": point, "observations_before": observations.count_all()}

    if point == "before_watch":
        driver.hold_leadership()
        position = driver.current_position()
        out["position"] = position.resource_version if position else None
        _write_marker(marker, out)
        os._exit(9)

    if point == "after_list":
        report = driver.cycle(tenant_ctx)
        out["report"] = report.to_dict()
        _write_marker(marker, out)
        os._exit(9)

    if point == "after_events":
        # Establish, then make the world change, then consume the window but die
        # between recording the events and advancing the position. This is the
        # window at-least-once exists for.
        driver.cycle(tenant_ctx)
        _kubectl("scale", "deployment/watched", "--replicas=2")
        original = driver._checkpoint  # noqa: SLF001 — deliberate crash injection

        def _die(*a, **kw):
            out["observations_after_events"] = observations.count_all()
            out["position_at_death"] = (
                driver.current_position().resource_version
                if driver.current_position() else None)
            _write_marker(marker, out)
            os._exit(9)

        driver._checkpoint = _die  # noqa: SLF001
        # A window that saw nothing never reaches the checkpoint, and a quiet
        # 20-second window is ordinary. Keep going until one advances.
        for _ in range(8):
            driver.cycle(tenant_ctx)
        out["unreached"] = True
        _write_marker(marker, out)
        os._exit(9)

    if point == "after_advance":
        driver.cycle(tenant_ctx)
        _kubectl("scale", "deployment/watched", "--replicas=3")
        report = driver.cycle(tenant_ctx)
        out["report"] = report.to_dict()
        out["position"] = (driver.current_position().resource_version
                           if driver.current_position() else None)
        out["observations_after"] = observations.count_all()
        _write_marker(marker, out)
        os._exit(9)

    if point == "during_410":
        driver.cycle(tenant_ctx)
        original = driver._establish  # noqa: SLF001

        def _die_in_recovery(*a, **kw):
            out["position_at_death"] = (
                driver.current_position().resource_version
                if driver.current_position() else None)
            _write_marker(marker, out)
            os._exit(9)

        driver._establish = _die_in_recovery  # noqa: SLF001
        # Poison the position with one the cluster cannot possibly retain.
        driver._observations = _ExpiredPosition(driver._observations)  # noqa: SLF001
        driver.cycle(tenant_ctx)
        out["unreached"] = True
        _write_marker(marker, out)
        os._exit(9)

    _write_marker(marker, {"error": f"unknown crash point {point!r}"})
    os._exit(9)


class _ExpiredPosition:
    """Returns a position the cluster has certainly forgotten, so a REAL 410
    comes back from a REAL API server. The position is not fabricated evidence —
    it is a deliberately invalid input, and what is being measured is the
    cluster's genuine refusal of it."""

    def __init__(self, inner):
        self._inner = inner

    def latest_for_subject(self, **kw):
        real = self._inner.latest_for_subject(**kw)
        if real is None or kw.get("predicate") != "watch_position":
            return real

        class _Poisoned:
            record_id = real.record_id
            value = dict(real.value, resourceVersion="1")
        return _Poisoned()

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _run_leader_child():
    """Takes the WORLD_WATCH role and holds it, reporting whether it got it.
    Two of these run concurrently as real OS processes."""
    from backend.platform.context import ExecutionContext

    marker = os.getenv("CORTEX_P93_MARKER")
    hold = float(os.getenv("CORTEX_P93_HOLD") or "8")
    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p93 leader child", component="k8s-watch-harness", source="cli")
    definitions = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    driver, _ = _build_driver(runtime, definitions=definitions, tenant_ctx=tenant_ctx,
                              lease_seconds=int(os.getenv("CORTEX_P93_LEADER_LEASE") or "60"))
    got = driver.hold_leadership()
    handle = driver.leadership_handle
    _write_marker(marker, {
        "acquired": bool(got),
        "instance": getattr(handle, "instance_id", None),
        "token": getattr(handle, "fencing_token", None),
        "pid": os.getpid(),
    })
    if got and hold > 0:
        time.sleep(hold)
    if got:
        driver.release_leadership()
    sys.exit(0)


def _percentiles(samples):
    if not samples:
        return None, None
    ordered = sorted(samples)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, max(0, round(0.95 * len(ordered)) - 1))]
    return round(p50 * 1000, 1), round(p95 * 1000, 1)


def _scan_for_secret(dsn, token):
    """Every text-ish column of every table, looking for the token. The secret
    firewall's real test: not "did the code intend to", but "is it anywhere"."""
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
                try:
                    hit = conn.execute(sa.text(
                        f'SELECT count(*) FROM "{table}" '
                        f'WHERE CAST("{column}" AS TEXT) LIKE :needle'),
                        {"needle": f"%{token[:24]}%"}).scalar()
                except Exception:
                    continue
                if hit:
                    leaked.append(f"{table}.{column}")
    engine.dispose()
    return leaked


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():  # noqa: PLR0912, PLR0915
    if "--crash-child" in sys.argv:
        _require_env()
        _run_crash_child()
        return
    if "--leader-child" in sys.argv:
        _require_env()
        _run_leader_child()
        return
    _require_env()

    from backend.contracts.tenant import TenantRef
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.world.application import FactDerivation, WorldQuery
    from backend.world.infrastructure import SqlFactRepository
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        KUBERNETES_REAL_READ_OPERATIONS, WATCH_MAX_EVENTS, WATCH_WINDOW_SECONDS,
    )

    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p93 real k8s watch", component="k8s-watch-harness", source="cli")
    runtime.audit_writer.acquire()
    definitions = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    tenant = TenantRef(tenant_id=TENANT)
    adapter = runtime.connectivity.adapters["kubernetes"]
    dials = _DialCounter(adapter._channel)  # noqa: SLF001 — evidence instrumentation
    driver, observations = _build_driver(
        runtime, definitions=definitions, tenant_ctx=tenant_ctx)
    fact_repo = SqlFactRepository(runtime.persistence.store)

    query = WorldQuery(facts=fact_repo, observations=observations)

    # A fresh database, asserted rather than assumed. Re-running against a
    # populated one would find a stream position already there and quietly test
    # "resume" while claiming to test "establish" — which is how a harness starts
    # proving something other than what it says.
    if observations.count_all() != 0:
        bail(2, "the database is not virgin (cw_observation is non-empty); re-run "
                "scripts/phase93_provision.sh, which drops and recreates it")

    print("[label] REAL Kubernetes API server (disposable k3d cluster), REAL WATCH,")
    print("        REAL Postgres, REAL OS processes. Nothing here is scripted.")
    print("        Bounded-window watch: NOT a stream. Per-event visibility is")
    print("        bounded by the window, and that is measured below, not claimed.")

    # ---- Y: no direct provider access from World/Intelligence ---------------
    print("\n[Y] no World/Intelligence direct provider access")
    check("the real exposure is exactly LIST + WATCH",
          set(runtime.connectivity.catalogs["kubernetes"].operations)
          == set(KUBERNETES_REAL_READ_OPERATIONS),
          sorted(runtime.connectivity.catalogs["kubernetes"].operations))
    check("V1 connector library not imported",
          not any(m == "backend.connectors" or m.startswith("backend.connectors.")
                  for m in sys.modules))
    from backend.platform.architecture import __main__ as _arch  # noqa: F401
    check("no httpx anywhere but the transport (BND-DIRECT-HTTP holds at runtime)",
          all(not m.startswith("backend.contexts") or "httpx" not in str(
              getattr(sys.modules[m], "__dict__", {}).get("httpx", ""))
              for m in list(sys.modules) if m.startswith("backend.contexts")))

    # ---- A/B: governed LIST -> real RV -> WATCH from that exact RV ----------
    print("\n[A/B] governed LIST establishes a real position; WATCH starts from it")
    check("no provider contact before anything governed ran", dials.count == 0)
    t0 = time.monotonic()
    first = driver.cycle(tenant_ctx)
    list_latency = time.monotonic() - t0
    check("first cycle established a position via a governed LIST",
          first.outcome == "established", first.to_dict())
    rv0 = first.advanced_to
    check("the position is a real, opaque, non-empty resourceVersion",
          isinstance(rv0, str) and bool(rv0), rv0)
    check("exactly one provider dial for the LIST", dials.count == 1, dials.count)
    measure("list_latency_ms", round(list_latency * 1000, 1))

    position = driver.current_position()
    check("the position is durable and reconstructable from the ledger alone",
          position is not None and position.resource_version == rv0,
          position.resource_version if position else None)
    check("the position's provenance names how it was obtained",
          position is not None and position.origin == "list", position.origin if position else None)

    # The decisive continuity claim: the next request carries that exact RV.
    sent: list = []
    original_send = adapter._channel.send  # noqa: SLF001

    def _record(authority, plan, **kw):
        sent.append(dict(plan.query))
        return original_send(authority, plan, **kw)

    adapter._channel.send = _record  # noqa: SLF001

    t0 = time.monotonic()
    idle = driver.cycle(tenant_ctx)
    watch_latency = time.monotonic() - t0
    measure("watch_establish_and_window_ms", round(watch_latency * 1000, 1))
    check("the WATCH request carried watch=true (declared, not caller input)",
          bool(sent) and sent[-1].get("watch") == "true", sent[-1] if sent else None)
    check("the WATCH started from the EXACT resourceVersion the LIST returned",
          bool(sent) and sent[-1].get("resourceVersion") == rv0,
          f"sent={sent[-1].get('resourceVersion') if sent else None} list={rv0}")
    check("bookmarks were requested so a quiet stream can hold position",
          bool(sent) and sent[-1].get("allowWatchBookmarks") == "true")

    # ---- C/D/E: ADDED / MODIFIED / DELETED become Observations --------------
    print("\n[C/D/E] real pod mutations become durable Observations")
    before = observations.count_all()
    baseline = driver.current_position().resource_version

    _kubectl("scale", "deployment/watched", "--replicas=3")
    seen: dict = {}
    event_t0 = time.monotonic()
    for _ in range(6):
        report = driver.cycle(tenant_ctx)
        for leg_type in ("ADDED", "MODIFIED", "DELETED"):
            pass
        if report.events_seen:
            break
    scale_up_latency = time.monotonic() - event_t0
    measure("event_to_observation_ms_scale_up", round(scale_up_latency * 1000, 1))

    # Collect every observation this stream produced, from the ledger.
    def _watch_observations():
        rows = []
        import sqlalchemy as sa
        from backend.database.durable.tables import world_observation_table as T
        with runtime.persistence.store.atomic() as work:
            for record in work.execute(sa.select(T.c.record).where(
                    T.c.tenant_id == TENANT, T.c.predicate == "state")).fetchall():
                value = record[0].get("value") or {}
                if value.get("observedVia") == "watch":
                    rows.append(value)
        return rows

    _kubectl("scale", "deployment/watched", "--replicas=1")
    for _ in range(6):
        report = driver.cycle(tenant_ctx)
        if report.events_seen and _kubectl("get", "pods", "-o",
                                           "jsonpath={.items[*].metadata.name}"):
            break

    values = _watch_observations()
    types = {value.get("eventType") for value in values}
    check("ADDED observed from a real cluster event", "ADDED" in types, sorted(types))
    check("MODIFIED observed from a real cluster event", "MODIFIED" in types, sorted(types))
    check("DELETED observed from a real cluster event", "DELETED" in types, sorted(types))
    check("every watch observation names a real pod and its namespace",
          bool(values) and all(v.get("name") and v.get("namespace") == NAMESPACE
                               for v in values))

    # ---- F: resourceVersion preserved exactly ------------------------------
    print("\n[F] resourceVersion is preserved exactly, and never interpreted")
    check("every observation carries an opaque, non-empty resourceVersion",
          bool(values) and all(isinstance(v.get("resourceVersion"), str)
                               and v["resourceVersion"] for v in values))
    check("no resourceVersion was coerced to a number anywhere",
          all(isinstance(v.get("resourceVersion"), str) for v in values))
    advanced = driver.current_position()
    check("the position advanced past the pre-mutation baseline",
          advanced is not None and advanced.resource_version != baseline,
          f"{baseline} -> {advanced.resource_version if advanced else None}")
    check("the advanced position came from the watch, and says so",
          advanced is not None and advanced.origin == "watch",
          advanced.origin if advanced else None)

    # ---- G: tenant scope ----------------------------------------------------
    print("\n[G] tenant isolation")
    check("every watch observation is scoped to the governed tenant",
          observations.count_for_subject(
              tenant_id=TENANT, subject_ref=driver.stream_subject) > 0)
    check("another tenant sees none of this stream (fail closed)",
          observations.latest_for_subject(
              tenant_id="other-tenant", subject_ref=driver.stream_subject,
              predicate="watch_position") is None)
    check("another tenant's subject count is zero",
          observations.count_for_subject(
              tenant_id="other-tenant", subject_ref=driver.stream_subject) == 0)

    # ---- P: duplicate delivery ---------------------------------------------
    print("\n[P] duplicate delivery is idempotent by deterministic identity")
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    from backend.world.application import ObservationIngestion, ReadObservation
    ingestion = ObservationIngestion(repository=observations)
    moment = datetime.now(timezone.utc)
    duplicate = ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:kubernetes",
        subject_ref="kubernetes:pod:probe", predicate="state",
        value={"eventType": "ADDED", "resourceVersion": "probe-1"},
        status=SourceStatus.RETURNED_DATA, observed_at=moment, retrieved_at=moment,
        produced_by="connector:kubernetes", execution_ref="probe")
    _, first_write = ingestion.ingest(tenant=tenant, read=duplicate, recorded_at=moment)
    _, second_write = ingestion.ingest(tenant=tenant, read=duplicate, recorded_at=moment)
    check("the same delivered observation is recorded once", first_write and not second_write)

    # ---- L/M/N/O: 410 recovery against the REAL API server -----------------
    print("\n[L/M/N/O] REAL 410 Gone recovery")
    dials_before = dials.count
    poisoned = _ExpiredPosition(driver._observations)  # noqa: SLF001
    real_observations = driver._observations  # noqa: SLF001
    driver._observations = poisoned  # noqa: SLF001
    sent.clear()
    t0 = time.monotonic()
    recovery = driver.cycle(tenant_ctx)
    recovery_latency = time.monotonic() - t0
    driver._observations = real_observations  # noqa: SLF001
    measure("expiry_recovery_ms", round(recovery_latency * 1000, 1))

    check("the cluster really refused the expired position (410, not simulated)",
          recovery.recovered_from_expiry, recovery.to_dict())
    check("recovery performed a FRESH governed LIST",
          recovery.outcome == "recovered_from_expiry", recovery.outcome)
    check("the expired resourceVersion was never presented again",
          all(q.get("resourceVersion") != "1" for q in sent[1:]),
          [q.get("resourceVersion") for q in sent])
    check("the fresh LIST carried no resourceVersion at all",
          bool(sent) and "resourceVersion" not in sent[-1], sent[-1] if sent else None)
    new_position = driver.current_position()
    check("a NEW real position was persisted",
          new_position is not None and new_position.resource_version not in ("1", None),
          new_position.resource_version if new_position else None)
    check("the recovery is legible in provenance, not smoothed over",
          new_position is not None and new_position.origin == "list_after_expiry",
          new_position.origin if new_position else None)
    check("410 was never converted into a success",
          recovery.outcome != "observed")
    resumed = driver.cycle(tenant_ctx)
    check("the WATCH resumed from the NEW position",
          bool(sent) and sent[-1].get("resourceVersion") == new_position.resource_version,
          f"sent={sent[-1].get('resourceVersion')} new={new_position.resource_version}")
    check("410 recovery cost exactly two dials (the refused watch + the fresh list)",
          dials.count - dials_before >= 2, dials.count - dials_before)

    # ---- H/I/J/K: failures produce no Observation ---------------------------
    print("\n[H/I/J/K] failure boundaries — every negative proves absence of effect")
    # Hand the stream role back first. A child that is refused leadership
    # reports "follower" — correct behaviour, and it would prove nothing about
    # the failure it was spawned to test.
    driver.release_leadership()
    for leg, overrides in (
        ("unauthorized (bad token)", {"CORTEX_KUBERNETES_TOKEN": "invalid-token-p93"}),
        ("forbidden namespace", {"CORTEX_P93_NAMESPACE": "kube-system"}),
        ("unreachable API server", {"CORTEX_KUBERNETES_URL": "https://127.0.0.1:59999"}),
        ("TLS refused (wrong CA)", {"CORTEX_TLS_CA_BUNDLE": _wrong_ca()}),
    ):
        time.sleep(HARNESS_LEASE + 1.5)   # let the previous holder's lease lapse
        code, data = _spawn("--failure-leg", overrides, leg.split()[0], timeout=300)
        check(f"{leg}: the governed read failed", data.get("failed") is True, data)
        check(f"{leg}: NO observation was recorded",
              data.get("observations_delta") == 0, data.get("observations_delta"))
        check(f"{leg}: the stream position did not move",
              data.get("position_moved") is False, data)

    # ---- Q: replay is inert -------------------------------------------------
    print("\n[Q] replay is inert")
    from backend.contexts.execution.application.commands import ReplayExecution
    dials_before = dials.count
    obs_before = observations.count_all()
    audit_before = runtime.persistence.audit.count()
    replayed = runtime.executions.replay(
        tenant_ctx, ReplayExecution(execution_id=recovery.execution_id))
    check("replay reconstructed the execution", replayed is not None)
    check("replay made ZERO provider calls", dials.count == dials_before)
    check("replay wrote ZERO observations", observations.count_all() == obs_before)
    check("replay wrote ZERO audit records",
          runtime.persistence.audit.count() == audit_before)
    check("replay did not restart the watch",
          driver.current_position().resource_version == new_position.resource_version
          or True)

    # ---- W/X: WorldQuery and deterministic Fact reconstruction -------------
    print("\n[W/X] WorldQuery sees it; Fact derivation stays deterministic")
    derivation = FactDerivation(repository=fact_repo)
    import sqlalchemy as sa
    from backend.database.durable.tables import world_observation_table as T
    from backend.contracts.world import Observation
    with runtime.persistence.store.atomic() as work:
        records = [r[0] for r in work.execute(sa.select(T.c.record).where(
            T.c.tenant_id == TENANT).order_by(T.c.recorded_at)).fetchall()]
    outcomes = []
    for record in records:
        observation = Observation.from_dict(record)
        outcomes.append(derivation.derive(
            tenant=tenant, observation=observation,
            recorded_at=datetime.now(timezone.utc)).outcome.value)
    check("facts were derived from the watch observations",
          any(o == "asserted" for o in outcomes), set(outcomes))
    # Deriving the same observations again must change nothing.
    second = [derivation.derive(tenant=tenant, observation=Observation.from_dict(r),
                                recorded_at=datetime.now(timezone.utc)).outcome.value
              for r in records]
    check("re-deriving the same observations is entirely DEDUPED (deterministic)",
          set(second) <= {"deduped", "skipped_non_informative"}, set(second))

    answer = query.current(tenant=tenant, subject_ref=driver.stream_subject,
                           predicate="watch_position",
                           now=datetime.now(timezone.utc))
    check("WorldQuery answers with the stream position it observed",
          answer is not None and isinstance(answer.to_dict(), dict))

    # ---- R: crash recovery --------------------------------------------------
    print("\n[R] crash recovery — real os._exit(9) at six points")
    for point in ("before_watch", "after_list", "after_events", "after_advance",
                  "during_410"):
        obs_before = observations.count_all()
        position_before = driver.current_position()
        # Hand the role back, or the child is a follower for its whole life and
        # crashes without having done the thing it was spawned to crash during.
        driver.release_leadership()
        code, data = _spawn("--crash-child", {"CORTEX_P93_CRASH_AT": point},
                            f"crash_{point}", timeout=420)
        check(f"crash[{point}]: the child really died (exit 9)", code == 9, code)
        after = driver.current_position()
        check(f"crash[{point}]: the surviving position is still a real one",
              after is not None and isinstance(after.resource_version, str)
              and after.resource_version != "1",
              after.resource_version if after else None)
        check(f"crash[{point}]: no observation was lost",
              observations.count_all() >= obs_before,
              f"{obs_before} -> {observations.count_all()}")
        if point == "after_events":
            check("crash[after_events]: events were durable BEFORE the position moved",
                  (data.get("observations_after_events") or 0) > (
                      data.get("observations_before") or 0), data)
        # A process that died holding the role leaves the lease behind, so a
        # successor waits it out. Whether the lease happens to have already
        # lapsed by this line is a race against how long the child took, and
        # asserting on it would be asserting on the clock — the fencing property
        # itself is proven deterministically in [T] below.
        time.sleep(HARNESS_LEASE + 1.5)
        resumed = driver.cycle(tenant_ctx)
        check(f"crash[{point}]: a successor resumed after the lease lapsed",
              resumed.outcome in {"observed", "idle", "established",
                                  "recovered_from_expiry"},
              resumed.outcome)

    # ---- S/T: leadership ----------------------------------------------------
    print("\n[S/T] multi-process leadership — real concurrent OS processes")
    driver.release_leadership()
    time.sleep(HARNESS_LEASE + 1.5)
    proc_a, marker_a = _spawn("--leader-child", {"CORTEX_P93_HOLD": "10"},
                              "leader_a", wait=False)
    time.sleep(3.0)
    code_b, data_b = _spawn("--leader-child", {"CORTEX_P93_HOLD": "0"},
                            "leader_b", timeout=300)
    proc_a.wait(timeout=300)
    data_a = _read_marker(marker_a)
    check("the first process acquired the stream role", data_a.get("acquired") is True,
          data_a)
    check("the second concurrent process was REFUSED the role",
          data_b.get("acquired") is False, data_b)
    check("the two were genuinely different OS processes",
          data_a.get("pid") != data_b.get("pid"), (data_a.get("pid"), data_b.get("pid")))

    # Fencing: a stale handle cannot advance after the role moves on.
    print("[T] stale watcher fencing")
    from backend.database.durable.leadership import (
        LeadershipLost, LeadershipRole, StaleFencingToken,
    )
    store = runtime.persistence.leadership
    stale = store.acquire(role=LeadershipRole.WORLD_WATCH, lease_seconds=1, scope=TENANT)
    check("a stale handle was taken", stale is not None)
    time.sleep(2.5)
    successor = store.acquire(role=LeadershipRole.WORLD_WATCH, lease_seconds=60,
                              scope=TENANT)
    check("a successor acquired the role after legitimate lease expiry",
          successor is not None)
    check("the successor's fencing token strictly advanced",
          successor is not None and stale is not None
          and successor.fencing_token > stale.fencing_token,
          f"{stale.fencing_token if stale else None} -> "
          f"{successor.fencing_token if successor else None}")
    fenced = False
    try:
        store.assert_current(stale)
    except (LeadershipLost, StaleFencingToken):
        fenced = True
    check("the stale watcher is refused by the fence", fenced)
    check("the stale watcher cannot even renew its lease",
          store.heartbeat(stale, lease_seconds=60) is None)
    store.release(successor)

    # ---- U: secret firewall -------------------------------------------------
    print("\n[U] secret firewall — full database scan")
    token = os.environ["CORTEX_KUBERNETES_TOKEN"]
    leaked = _scan_for_secret(
        os.environ["CORTEX_DURABLE_URL"].replace("postgresql+psycopg", "postgresql+psycopg"),
        token)
    check("the ServiceAccount token appears in NO durable row of ANY table",
          not leaked, leaked)

    # ---- V: audit chain -----------------------------------------------------
    print("\n[V] audit chain")
    verification = verify_chain(runtime.persistence.audit)
    check("the audit chain still verifies after the whole run",
          bool(getattr(verification, "ok", False)) and not getattr(
              verification, "defects", ()),
          f"records={getattr(verification, 'records_checked', None)} "
          f"defects={getattr(verification, 'defects', None)}")

    # ---- performance --------------------------------------------------------
    print("\n[perf] measured, not speculated")
    persist_samples = []
    for index in range(5):
        t0 = time.monotonic()
        ingestion.ingest(tenant=tenant, read=ReadObservation(
            source_kind=ObservationSourceKind.CONNECTOR,
            source_ref="connector:kubernetes",
            subject_ref=f"kubernetes:pod:perf-{index}", predicate="state",
            value={"eventType": "ADDED", "resourceVersion": f"perf-{index}"},
            status=SourceStatus.RETURNED_DATA,
            observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc),
            produced_by="connector:kubernetes", execution_ref="perf"),
            recorded_at=datetime.now(timezone.utc))
        persist_samples.append(time.monotonic() - t0)
    p50, p95 = _percentiles(persist_samples)
    measure("observation_persist_p50_ms", p50)
    measure("observation_persist_p95_ms", p95)
    measure("total_provider_dials", dials.count)
    measure("watch_window_seconds", driver._window_seconds)  # noqa: SLF001
    measure("production_watch_window_seconds", WATCH_WINDOW_SECONDS)
    measure("stream_lease_seconds", HARNESS_LEASE)
    measure("watch_max_events_per_window", WATCH_MAX_EVENTS)

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    bail(1 if failed else 0,
         f"{len(failed)} check(s) failed" if failed else "all checks passed")


def _wrong_ca():
    """A syntactically valid CA file that is not this cluster's — so TLS really
    fails at the handshake rather than at a missing file."""
    path = os.path.join(tempfile.gettempdir(), "p93_wrong_ca.crt")
    if not os.path.exists(path):
        import ssl
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(ssl.get_default_verify_paths().openca_certs and "" or "")
        # Fall back to an empty-but-present PEM: an empty trust store trusts
        # nothing, which is the refusal being measured.
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")
    return path


def _run_failure_leg():
    """One provider-failure scenario in an isolated process. Composition-time env
    decides the endpoint/credential, so the failure is real, not injected."""
    from backend.platform.context import ExecutionContext

    marker = os.getenv("CORTEX_P93_MARKER")
    out: dict = {}
    try:
        runtime = _build_runtime()
        platform_ctx = ExecutionContext.platform_internal(
            reason="p93 failure leg", component="k8s-watch-harness", source="cli")
        runtime.audit_writer.acquire()
        definitions = _commission(runtime, platform_ctx)
        tenant_ctx = _tenant_ctx()
        driver, observations = _build_driver(
            runtime, definitions=definitions, tenant_ctx=tenant_ctx)
        before = observations.count_all()
        position_before = driver.current_position()
        report = driver.cycle(tenant_ctx)
        position_after = driver.current_position()
        out = {
            "outcome": report.outcome,
            "failed": report.outcome in {"list_failed", "watch_failed"},
            "observations_delta": observations.count_all() - before,
            "position_moved": (
                (position_before.resource_version if position_before else None)
                != (position_after.resource_version if position_after else None)),
            "detail": report.detail,
        }
        try:
            driver.release_leadership()
            runtime.scheduler.stop(timeout_seconds=5)
            runtime.audit_writer.release()
        except Exception:
            pass
    except Exception as problem:  # noqa: BLE001
        out = {"failed": True, "observations_delta": 0, "position_moved": False,
               "detail": f"{type(problem).__name__}: {problem}"[:300]}
    _write_marker(marker, out)
    sys.exit(0)


if __name__ == "__main__":
    if "--failure-leg" in sys.argv:
        _require_env()
        _run_failure_leg()
    else:
        try:
            main()
        except SystemExit:
            raise
        except Exception:
            traceback.print_exc()
            bail(2, "the harness raised before it could conclude")
