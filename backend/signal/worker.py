"""The supervised signal worker — Phase 11.2 (ADR-122).

    python -m backend.signal.worker

What it is
----------
The production runner the Kubernetes watch driver never had. One process,
one tenant, one namespace: it composes the governed runtime the API composes,
takes the ``WORLD_WATCH`` stream role through the SQL leadership store, and
drives ``KubernetesWatchDriver.cycle`` in a supervised loop:

    OBSERVE   a bounded governed WATCH window (LIST on first start / after 410)
    ENRICH    each mutation through the governed ``pod.get`` read (phase,
              restarts, waiting reason, last termination) -- same capability
              catalogue, same gateway, same credential path
    INGEST    one identity-deduplicated, tenant-scoped World observation per
              event, events before position, always
    DERIVE    a World fact from each NEW observation (``cw_fact``)
    PROJECT   incident candidates over the latest state of every subject
    HAND OFF  to the detection boundary port (Prompt 3 plugs a detector in;
              the default records the projection and opens nothing)

What it is not
--------------
Not an executor. It holds the READ credential only (``CORTEX_KUBERNETES_TOKEN``,
the ``cortex-reader`` ServiceAccount), never a restart token, and it composes
no dispatcher, scheduler or outbox pump. It cannot restart, delete, scale or
patch anything, and the capability catalogue it can reach is read-only by
declaration. It does not register capabilities: commissioning the catalogue is
an operator act (``scripts/phase93_kubernetes_watch_harness.py`` shows it);
a worker that finds them missing refuses to start.

Supervision
-----------
* ``follower``: another instance holds the role; sleep and retry (it will
  take over when the lease lapses).
* ``watch_failed`` / ``list_failed``: exponential backoff (1 s .. 60 s),
  counted as a retry. After ``max_stall_failures`` consecutive failures at the
  SAME position the position is abandoned by a governed relist -- explicit,
  counted loss (``cortex_signal_events_dropped_total{reason="stall"}``) and a
  checkpoint whose provenance names the stall.
* ``expiry_recovery_exhausted``: same relist path, reason ``expiry``.
* ``fenced``: leadership lost mid-cycle; events are already durable; the
  successor re-delivers the window (at-least-once).
* SIGTERM / SIGINT: finish the current cycle, release the role, exit 0.
* Any exception in a cycle: logged, counted, backed off, never fatal -- and
  never a fabricated success.

Every counter is exported on ``CORTEX_SIGNAL_METRICS_PORT`` through the
existing Prometheus registry.
"""

from __future__ import annotations

import json
import logging
import os
import signal as _signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Protocol

from backend.signal.contract import (
    PREDICATE_ALERT,
    PREDICATE_STATE,
    PREDICATE_WATCH_POSITION,
    SUBJECT_ALERTMANAGER_ALERT,
    SUBJECT_KUBERNETES_POD,
)
from backend.signal.correlation import project_candidates, workload_of

log = logging.getLogger("cortexprime.signal.worker")

__all__ = [
    "SignalWorkerConfig",
    "DetectionHandoff",
    "LoggingHandoff",
    "RecordingObserver",
    "StepReport",
    "SignalWorker",
    "build_worker_from_env",
    "build_worker_from_runtime",
    "EmbeddedSignalWorker",
    "start_embedded",
    "main",
]

LIST_OP = "kubernetes.pods.list"
WATCH_OP = "kubernetes.pods.watch"
GET_OP = "kubernetes.pod.get"

#: Scalars copied from a governed ``pod.get`` into the watch observation.
#: Declared, never "everything the provider said".
ENRICHMENT_FIELDS = ("phase", "restartCount", "waitingReason", "lastExitCode",
                     "lastTerminationReason", "resourceVersion")

_FAILURE_OUTCOMES = frozenset({"watch_failed", "list_failed"})
_PROGRESS_OUTCOMES = frozenset({"observed", "idle", "established", "recovered_from_expiry",
                                "relisted_after_stall"})


@dataclass(frozen=True)
class SignalWorkerConfig:
    tenant_id: str
    namespace: str
    cluster_ref: str
    window_seconds: int = 20
    lease_seconds: int = 60
    metrics_port: int = 9102
    follower_sleep_seconds: float = 5.0
    idle_sleep_seconds: float = 0.0
    backoff_min_seconds: float = 1.0
    backoff_max_seconds: float = 60.0
    max_stall_failures: int = 5
    max_cycles: int = 0  # 0 = until stopped
    status_file: Optional[str] = None
    produced_by: str = "signal:kubernetes-worker/1"

    @classmethod
    def from_env(cls) -> "SignalWorkerConfig":
        tenant = (os.getenv("CORTEX_SIGNAL_TENANT_ID") or "").strip()
        namespace = (os.getenv("CORTEX_SIGNAL_NAMESPACE") or "").strip()
        if not tenant or not namespace:
            raise SystemExit(
                "signal worker refuses to start: CORTEX_SIGNAL_TENANT_ID and "
                "CORTEX_SIGNAL_NAMESPACE must name the one tenant and namespace "
                "this worker observes; a worker with no tenant would write "
                "observations nobody owns")
        cluster = (os.getenv("CORTEX_SIGNAL_CLUSTER_REF") or "").strip()
        if not cluster:
            url = (os.getenv("CORTEX_KUBERNETES_URL") or "").strip()
            cluster = url.split("://", 1)[-1] or "unknown-cluster"

        def _int(name: str, default: int) -> int:
            raw = (os.getenv(name) or "").strip()
            return int(raw) if raw else default

        def _float(name: str, default: float) -> float:
            raw = (os.getenv(name) or "").strip()
            return float(raw) if raw else default

        return cls(
            tenant_id=tenant, namespace=namespace, cluster_ref=cluster,
            window_seconds=_int("CORTEX_SIGNAL_WINDOW_SECONDS", 20),
            lease_seconds=_int("CORTEX_SIGNAL_LEASE_SECONDS", 60),
            metrics_port=_int("CORTEX_SIGNAL_METRICS_PORT", 9102),
            follower_sleep_seconds=_float("CORTEX_SIGNAL_FOLLOWER_SLEEP_SECONDS", 5.0),
            idle_sleep_seconds=_float("CORTEX_SIGNAL_IDLE_SLEEP_SECONDS", 0.0),
            backoff_min_seconds=_float("CORTEX_SIGNAL_BACKOFF_MIN_SECONDS", 1.0),
            backoff_max_seconds=_float("CORTEX_SIGNAL_BACKOFF_MAX_SECONDS", 60.0),
            max_stall_failures=_int("CORTEX_SIGNAL_MAX_STALL_FAILURES", 5),
            max_cycles=_int("CORTEX_SIGNAL_MAX_CYCLES", 0),
            status_file=(os.getenv("CORTEX_SIGNAL_STATUS_FILE") or "").strip() or None,
        )


class DetectionHandoff(Protocol):
    """The detection boundary. Receives candidates; returns nothing; decides
    nothing here. Prompt 3 supplies the implementation that opens
    investigations through ``InvestigationService.create``."""

    def offer(self, candidates: tuple, *, tenant_id: str, now: datetime) -> None: ...


class LoggingHandoff:
    """The default: records the projection, opens nothing."""

    def __init__(self) -> None:
        self.offers: list = []
        self._last_ids: frozenset = frozenset()

    def offer(self, candidates: tuple, *, tenant_id: str, now: datetime) -> None:
        ids = frozenset(c.candidate_id for c in candidates)
        if ids != self._last_ids:
            log.info("detection handoff: tenant=%s candidates=%d %s", tenant_id, len(candidates),
                     [f"{c.kind}:{c.detail}"[:120] for c in candidates][:10])
            self._last_ids = ids
        self.offers.append({"at": now.isoformat(), "count": len(candidates),
                            "ids": sorted(ids)})
        del self.offers[:-50]


class RecordingObserver:
    """Wraps the governed observer to capture what a cycle recorded.

    The driver reports counts; fact derivation and the handoff need the
    observations themselves. A wrapper, not a driver change: the observer's
    contract and the driver's are both untouched.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._recorded: list = []

    def observe(self, **kwargs: Any) -> tuple:
        results = self._inner.observe(**kwargs)
        self._recorded.extend(results)
        return results

    def drain(self) -> list:
        out, self._recorded = self._recorded, []
        return out


@dataclass
class StepReport:
    outcome: str
    events_seen: int = 0
    recorded: int = 0
    deduped: int = 0
    facts: dict = field(default_factory=dict)
    candidates: int = 0
    backoff_seconds: float = 0.0
    relisted: bool = False
    leader: bool = False
    detail: Optional[str] = None
    cycle_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class SignalWorker:
    """The supervision loop. Every dependency is injected so the loop is
    testable without a cluster; ``build_worker_from_env`` composes the real ones."""

    def __init__(
        self,
        *,
        config: SignalWorkerConfig,
        driver: Any,
        tenant: Any,
        tenant_context: Any,
        observer: RecordingObserver,
        observations: Any,
        derivation: Any,
        handoff: Optional[DetectionHandoff] = None,
        metrics: Any = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], None] = time.sleep,
        roles: Optional[Callable[[], bool]] = None,
        release_roles: Optional[Callable[[], None]] = None,
    ) -> None:
        # ``roles`` answers "does THIS process hold what a governed read needs
        # right now" (the audit-writer role, in standalone mode). ``False`` is
        # the ordinary hot-standby answer: the worker reports ``follower`` and
        # waits; it never dispatches half-admitted. ``None`` (embedded mode)
        # means the hosting runtime holds the roles for its whole lifetime.
        self._roles = roles
        self._release_roles = release_roles
        self.config = config
        self._driver = driver
        self._tenant = tenant
        self._context = tenant_context
        self._observer = observer
        self._observations = observations
        self._derivation = derivation
        self._handoff = handoff or LoggingHandoff()
        self._metrics = metrics
        self._clock = clock
        self._sleep = sleep
        self._stop = threading.Event()
        self._consecutive_failures = 0
        self._failed_position: Optional[str] = None
        self._backoff = config.backoff_min_seconds
        self.cycles = 0
        self.last_report: Optional[StepReport] = None
        self.last_candidates: tuple = ()
        self.started_at = self._clock()

    # ------------------------------------------------------------------

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def _m(self, name: str):
        return getattr(self._metrics, name, None) if self._metrics is not None else None

    def _count(self, name: str, *labels: str, value: float = 1.0) -> None:
        counter = self._m(name)
        if counter is None:
            return
        try:
            (counter.labels(*labels) if labels else counter).inc(value)
        except Exception:  # noqa: BLE001 - metrics never on the decision path
            pass

    def _gauge(self, name: str, value: float, *labels: str) -> None:
        gauge = self._m(name)
        if gauge is None:
            return
        try:
            (gauge.labels(*labels) if labels else gauge).set(value)
        except Exception:  # noqa: BLE001
            pass

    def _observe(self, name: str, value: float, *labels: str) -> None:
        hist = self._m(name)
        if hist is None:
            return
        try:
            (hist.labels(*labels) if labels else hist).observe(value)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------

    def step(self) -> StepReport:
        """One supervised cycle. Never raises."""
        started = time.perf_counter()
        self.cycles += 1
        if self._roles is not None:
            try:
                admitted = bool(self._roles())
            except Exception as exc:  # noqa: BLE001 - unverifiable admission is no admission
                log.warning("role check raised; treating this cycle as follower: %s", exc)
                admitted = False
            if not admitted:
                self._observer.drain()
                self._count("signal_cycles", "kubernetes", "follower")
                self._gauge("signal_worker_leader", 0.0)
                step = StepReport(outcome="follower", leader=False,
                                  detail="the audit-writer role is held by another process; "
                                         "this instance waits as a hot standby",
                                  backoff_seconds=self.config.follower_sleep_seconds)
                return self._finish(step, started)
        try:
            report = self._driver.cycle(self._context)
        except Exception as exc:  # noqa: BLE001 - a crash is a failure, not a success
            log.exception("watch cycle raised")
            self._count("signal_provider_errors", "kubernetes", type(exc).__name__)
            return self._after_failure(StepReport(outcome="cycle_exception",
                                                  detail=f"{type(exc).__name__}: {exc}"[:200]),
                                       position=None)
        outcome = report.outcome
        self._count("signal_cycles", "kubernetes", outcome)
        step = StepReport(outcome=outcome, events_seen=report.events_seen,
                          recorded=report.observations_recorded,
                          deduped=report.observations_deduped, detail=report.detail,
                          leader=self._driver.leadership_handle is not None)
        self._gauge("signal_worker_leader", 1.0 if step.leader else 0.0)

        if outcome == "follower":
            self._observer.drain()
            step.backoff_seconds = self.config.follower_sleep_seconds
            return self._finish(step, started)

        if outcome in _FAILURE_OUTCOMES:
            self._observer.drain()
            self._count("signal_provider_errors", "kubernetes", outcome)
            # Decide the backoff BEFORE the status file is written, so what
            # an operator reads is what the loop will do (harness 7.1 found
            # the status reporting backoff 0 for a failed cycle).
            return self._finish(self._after_failure(step, position=report.started_from), started)

        if outcome == "expiry_recovery_exhausted":
            self._observer.drain()
            return self._relist(step, started, reason="expiry")

        if outcome == "fenced":
            # Events already durable; only the advance was refused. Try again
            # soon: either we regain the role or we become a follower honestly.
            self._ingest_recorded(step)
            step.backoff_seconds = self.config.backoff_min_seconds
            return self._finish(step, started)

        # Progress outcomes.
        self._consecutive_failures = 0
        self._failed_position = None
        self._backoff = self.config.backoff_min_seconds
        if report.recovered_from_expiry:
            self._count("signal_reconnects", "kubernetes", "expiry")
        self._count("signal_events_received", "kubernetes", "watch", value=report.events_seen)
        self._count("signal_events_persisted", "kubernetes", value=report.observations_recorded)
        self._count("signal_events_deduplicated", "kubernetes", value=report.observations_deduped)
        self._ingest_recorded(step)
        self._project(step)
        if outcome == "idle" and self.config.idle_sleep_seconds > 0:
            step.backoff_seconds = self.config.idle_sleep_seconds
        return self._finish(step, started)

    def _after_failure(self, step: StepReport, *, position: Optional[str]) -> StepReport:
        self._count("signal_retries", "kubernetes")
        if position is not None and position == self._failed_position:
            self._consecutive_failures += 1
        else:
            self._failed_position = position
            self._consecutive_failures = 1
        if (position is not None
                and self._consecutive_failures >= self.config.max_stall_failures):
            return self._relist(step, None, reason="stall")
        step.backoff_seconds = self._backoff
        self._backoff = min(self._backoff * 2, self.config.backoff_max_seconds)
        return step

    def _relist(self, step: StepReport, started: Optional[float], *, reason: str) -> StepReport:
        """Abandon the position. Explicit, counted loss."""
        detail = (f"{reason}: {self._consecutive_failures} consecutive failures at "
                  f"position {self._failed_position}" if reason == "stall"
                  else f"{reason}: {step.detail}")
        log.warning("signal worker relisting after %s", detail)
        try:
            report = self._driver.relist(self._context, reason=detail)
        except Exception as exc:  # noqa: BLE001
            log.exception("relist raised")
            step.detail = f"relist failed: {type(exc).__name__}"
            step.backoff_seconds = self.config.backoff_max_seconds
            return step
        self._count("signal_reconnects", "kubernetes", reason)
        self._count("signal_events_dropped", "kubernetes", reason)
        step.relisted = report.outcome == "relisted_after_stall"
        step.outcome = report.outcome
        step.detail = report.detail
        self._consecutive_failures = 0
        self._failed_position = None
        self._backoff = self.config.backoff_min_seconds
        if step.relisted:
            self._ingest_recorded(step)
        else:
            step.backoff_seconds = self._backoff
        return self._finish(step, started) if started is not None else step

    def _ingest_recorded(self, step: StepReport) -> None:
        """Derive facts from the observations THIS cycle newly recorded."""
        recorded = self._observer.drain()
        now = self._clock()
        outcomes: dict = {}
        for observation, newly in recorded:
            if not newly or observation.predicate == PREDICATE_WATCH_POSITION:
                continue
            lag = (now - observation.instant.observed_at).total_seconds()
            self._observe("signal_event_lag_seconds", max(0.0, lag), "kubernetes")
            if self._derivation is None:
                continue
            try:
                result = self._derivation.derive(
                    tenant=self._tenant, observation=observation, recorded_at=now)
                label = getattr(getattr(result, "outcome", None), "value", None) or str(
                    getattr(result, "outcome", "unknown"))
            except Exception as exc:  # noqa: BLE001 - a refused derivation is recorded, not hidden
                label = f"refused:{type(exc).__name__}"
                log.warning("fact derivation refused for %s: %s", observation.record_id, exc)
            outcomes[label] = outcomes.get(label, 0) + 1
            self._count("signal_facts_derived", label)
        step.facts = outcomes

    def _project(self, step: StepReport) -> None:
        if self._observations is None:
            return
        try:
            latest = list(self._observations.latest_by_subject_prefix(
                tenant_id=self._tenant.tenant_id, subject_prefix=SUBJECT_KUBERNETES_POD,
                predicate=PREDICATE_STATE))
            latest += list(self._observations.latest_by_subject_prefix(
                tenant_id=self._tenant.tenant_id, subject_prefix=SUBJECT_ALERTMANAGER_ALERT,
                predicate=PREDICATE_ALERT))
        except Exception as exc:  # noqa: BLE001 - a failed projection is not a failed cycle
            log.warning("candidate projection read failed: %s", exc)
            return
        candidates = project_candidates(latest, tenant_id=self._tenant.tenant_id)
        self.last_candidates = candidates
        step.candidates = len(candidates)
        kinds: dict = {}
        for candidate in candidates:
            kinds[candidate.kind] = kinds.get(candidate.kind, 0) + 1
        for kind in ("kubernetes.pod.backoff", "kubernetes.pod.restarting",
                     "alertmanager.alert.firing"):
            self._gauge("signal_candidates", float(kinds.get(kind, 0)), kind)
        try:
            self._handoff.offer(candidates, tenant_id=self._tenant.tenant_id, now=self._clock())
            self._count("signal_handoffs")
        except Exception as exc:  # noqa: BLE001 - the boundary refusing is not our failure
            log.warning("detection handoff refused the projection: %s", exc)

    def _finish(self, step: StepReport, started: float) -> StepReport:
        step.cycle_seconds = round(time.perf_counter() - started, 4)
        self._observe("signal_cycle_seconds", step.cycle_seconds, "kubernetes")
        self.last_report = step
        self._write_status()
        return step

    def _write_status(self) -> None:
        path = self.config.status_file
        if not path or self.last_report is None:
            return
        try:
            payload = {
                "pid": os.getpid(), "tenant_id": self.config.tenant_id,
                "namespace": self.config.namespace, "cycles": self.cycles,
                "started_at": self.started_at.isoformat(), "at": self._clock().isoformat(),
                "last": self.last_report.to_dict(),
                "candidates": [c.to_dict() for c in self.last_candidates],
            }
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=1, default=str)
            os.replace(tmp, path)
        except Exception as exc:  # noqa: BLE001
            log.debug("status file write failed: %s", exc)

    # ------------------------------------------------------------------

    def run(self) -> int:
        """Cycle until stopped or ``max_cycles``. Releases the role on exit."""
        log.info("signal worker starting: tenant=%s namespace=%s window=%ss lease=%ss",
                 self.config.tenant_id, self.config.namespace,
                 self.config.window_seconds, self.config.lease_seconds)
        try:
            while not self._stop.is_set():
                step = self.step()
                if self.config.max_cycles and self.cycles >= self.config.max_cycles:
                    break
                if step.backoff_seconds > 0 and not self._stop.is_set():
                    self._sleep(step.backoff_seconds)
        finally:
            try:
                released = self._driver.release_leadership()
                log.info("signal worker stopped after %d cycles (role released=%s)",
                         self.cycles, released)
            except Exception:  # noqa: BLE001
                log.exception("release on shutdown raised")
            if self._release_roles is not None:
                try:
                    self._release_roles()
                except Exception:  # noqa: BLE001
                    log.exception("role release on shutdown raised")
            self._gauge("signal_worker_leader", 0.0)
            self._write_status()
        return 0


# ----------------------------------------------------------------------
# Composition
# ----------------------------------------------------------------------

def _capability_definitions(runtime: Any, platform_ctx: Any) -> dict:
    from backend.contexts.connectivity.application.commands import GetCapability

    definitions: dict = {}
    missing: list = []
    for op in (LIST_OP, WATCH_OP, GET_OP):
        try:
            definitions[op] = runtime.capabilities.get(
                platform_ctx, GetCapability(capability_id=f"platform.{op}", version=1))
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{op} ({type(exc).__name__})")
    if missing:
        raise SystemExit(
            "signal worker refuses to start: the governed read capabilities are not "
            f"commissioned in this deployment: {', '.join(missing)}. Commission them "
            "through the capability registry (an operator act); the worker never "
            "registers capabilities for itself")
    return definitions


def _commission_connector_worker(runtime: Any, platform_ctx: Any,
                                 worker_id: str = "kubernetes-connector") -> None:
    """Admit the in-process connector worker to THIS process's worker directory.

    The runtime's worker directory is process-local (``InMemoryWorkerDirectory``),
    so every process that dispatches must admit the connector it will dispatch
    to; the API does the same for its own reads. This is operational state of
    the process, not governance: the capability registry -- what may be read,
    with what contract, at what trust -- is durable and is not touched here.
    Without this step the dispatcher refuses every read with
    ``invocation_request_unavailable`` and the node stays leased until the
    read budget lapses, which is how this was found.
    """
    from backend.contexts.execution.domain.worker_directory import (
        WorkerAvailability, WorkerTrust,
    )

    directory = runtime.connectivity.directory
    for step in (
        lambda: directory.validate(platform_ctx, worker_id=worker_id, tenant_id=""),
        lambda: directory.enable(platform_ctx, worker_id=worker_id, tenant_id=""),
        lambda: directory.set_trust(platform_ctx, worker_id=worker_id, tenant_id="",
                                    trust=WorkerTrust.VERIFIED, reason="signal worker boot"),
        lambda: directory.set_trust(platform_ctx, worker_id=worker_id, tenant_id="",
                                    trust=WorkerTrust.TRUSTED, reason="signal worker boot"),
        lambda: directory.set_availability(platform_ctx, worker_id=worker_id, tenant_id="",
                                           availability=WorkerAvailability.AVAILABLE),
    ):
        try:
            step()
        except Exception as exc:  # noqa: BLE001 - already in that state, or refused: say which
            log.debug("connector worker commissioning step: %s: %s", type(exc).__name__, exc)


def build_worker_from_env(*, config: Optional[SignalWorkerConfig] = None,
                          handoff: Optional[DetectionHandoff] = None) -> SignalWorker:
    """Compose the real worker as its OWN process from the deployment environment.

    Use this where the API runtime is NOT dispatching against the same durable
    store. The runtime scheduler and audit-writer roles are singletons across
    processes, and a runtime dispatches only the executions its own process
    started; a standalone worker beside a running API would hold neither role
    and its governed reads would wait out their budget (measured in Phase
    11.2). Beside the API, use :func:`start_embedded`.
    """
    from backend.api.application_runtime import build_governed_runtime

    cfg = config or SignalWorkerConfig.from_env()
    if not (os.getenv("CORTEX_CONNECTOR_FACTORIES") or "").strip():
        os.environ["CORTEX_CONNECTOR_FACTORIES"] = (
            "backend.api.kubernetes_provider_factory:kubernetes_real_extension")
    runtime = build_governed_runtime()
    if runtime is None:
        raise SystemExit("signal worker refuses to start: no governed runtime "
                         "(is CORTEX_DURABLE_URL set?)")
    return build_worker_from_runtime(runtime, config=cfg, handoff=handoff, standalone=True)


def build_worker_from_runtime(runtime: Any, *, config: SignalWorkerConfig,
                              handoff: Optional[DetectionHandoff] = None,
                              standalone: bool = False) -> SignalWorker:
    """Compose the worker over an EXISTING governed runtime (the API runtime, or
    a standalone one). No second runtime, no second leadership store, no second
    scheduler: the reads dispatch through the runtime that owns the roles."""
    from backend.api.governed_read_observer import (
        GovernedCapabilityReader, GovernedReadObserver,
    )
    from backend.api.kubernetes_watch_driver import KubernetesWatchDriver
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.contracts.tenant import TenantRef
    from backend.platform.context import ExecutionContext
    from backend.platform.context.identity import IdentityContext
    from backend.world.application import FactDerivation, ObservationIngestion
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    cfg = config
    if "kubernetes" not in runtime.connectivity.catalogs:
        raise SystemExit("signal worker refuses to start: the real Kubernetes provider is "
                         "absent (CORTEX_KUBERNETES_URL / TOKEN / CA bundle unset?)")

    bound_tenant = (os.getenv("CORTEX_KUBERNETES_TENANT") or "").strip()
    if bound_tenant and bound_tenant != cfg.tenant_id:
        raise SystemExit(
            "signal worker refuses to start: the real Kubernetes provider is bound to "
            f"tenant {bound_tenant!r} (CORTEX_KUBERNETES_TENANT) but this worker observes "
            f"for {cfg.tenant_id!r}; a read for one tenant with another tenant's credential "
            "is refused here rather than discovered as a stalled stream")

    platform_ctx = ExecutionContext.platform_internal(
        reason="signal worker: governed read capability lookup",
        component="cortexprime.signal_worker", source="lifecycle")
    definitions = _capability_definitions(runtime, platform_ctx)

    roles: Optional[Callable[[], bool]] = None
    release_roles: Optional[Callable[[], None]] = None
    if standalone:
        # A standalone process must hold the audit-writer role itself (the
        # runtime's start() would take it, but start() also starts the
        # scheduler thread and the outbox pump, which this process must not
        # run). Taken lazily, renewed by use, and released on exit; while
        # another process holds it this instance is a follower. Admitting the
        # connector worker is itself audited, so it waits for the role too.
        admitted = {"done": False}

        def _roles() -> bool:
            writer = runtime.audit_writer
            held = bool(writer.handle is not None and writer.is_writer())
            if not held:
                held = writer.acquire() is not None
            if held and not admitted["done"]:
                _commission_connector_worker(runtime, platform_ctx)
                admitted["done"] = True
            return held

        def _release() -> None:
            runtime.audit_writer.release()

        roles, release_roles = _roles, _release
    else:
        _commission_connector_worker(runtime, platform_ctx)

    principal = PrincipalRef(principal_id="signal-worker", kind=PrincipalKind.PLATFORM)
    tenant_ctx = ExecutionContext.for_tenant(
        tenant_id=cfg.tenant_id,
        identity=IdentityContext(principal=principal, capabilities=("capability:invoke",)),
        source="signal-worker")
    tenant = TenantRef(tenant_id=cfg.tenant_id)

    store = runtime.persistence.store
    observations = SqlObservationRepository(store)
    reader = GovernedCapabilityReader(runtime=runtime, capability_definitions=definitions,
                                      principal=principal)
    observer = RecordingObserver(GovernedReadObserver(
        ingestion=ObservationIngestion(repository=observations),
        source_ref="connector:kubernetes", produced_by=cfg.produced_by))

    def enrich(name: str) -> Mapping[str, Any]:
        outcome = reader.read(tenant_ctx, operation=GET_OP,
                              payload={"namespace": cfg.namespace, "name": name})
        if not outcome.succeeded:
            return {"enrichment": f"unavailable:{(outcome.failure_reason or 'read_failed')[:80]}",
                    "cluster": cfg.cluster_ref, "workload": workload_of(name)}
        out: dict = {"cluster": cfg.cluster_ref, "workload": workload_of(name),
                     "enrichment": "pod.get", "enrichmentExecution": outcome.execution_id}
        for key in ENRICHMENT_FIELDS:
            value = outcome.evidence.get(key)
            if value is not None and key != "resourceVersion":
                out[key] = value
        return out

    driver = KubernetesWatchDriver(
        reader=reader, observer=observer, observations=observations,
        leadership=runtime.persistence.leadership, tenant=tenant,
        namespace=cfg.namespace, list_operation=LIST_OP, watch_operation=WATCH_OP,
        window_seconds=cfg.window_seconds, lease_seconds=cfg.lease_seconds,
        enricher=enrich)
    derivation = FactDerivation(repository=SqlFactRepository(store))

    metrics = None
    try:
        from backend.observability.prometheus_metrics import metrics as _metrics
        metrics = _metrics
    except Exception:  # noqa: BLE001
        log.warning("metrics registry unavailable; the worker runs without counters")

    return SignalWorker(config=cfg, driver=driver, tenant=tenant, tenant_context=tenant_ctx,
                        observer=observer, observations=observations, derivation=derivation,
                        handoff=handoff, metrics=metrics, roles=roles, release_roles=release_roles)


class EmbeddedSignalWorker:
    """The signal loop as a supervised thread of an existing runtime process.

    Started by the main application lifespan when ``CORTEX_SIGNAL_TENANT_ID``
    and ``CORTEX_SIGNAL_NAMESPACE`` are configured; stopped on shutdown. It
    shares the API runtime (and therefore its scheduler and audit-writer
    roles), exports through the API ``/metrics``, and holds the same read-only
    credential the API Kubernetes provider holds. It still takes the
    ``WORLD_WATCH`` stream role through the leadership store, so two API
    replicas configured for the same tenant elect exactly one observer.
    """

    def __init__(self, worker: SignalWorker) -> None:
        self.worker = worker
        self._thread = threading.Thread(target=self._run, name="cortexprime-signal-worker",
                                        daemon=True)
        self.exit_code: Optional[int] = None

    def _run(self) -> None:
        try:
            self.exit_code = self.worker.run()
        except Exception:  # noqa: BLE001 - a crashed loop is logged, never silent
            log.exception("embedded signal worker loop crashed")
            self.exit_code = 1

    def start(self) -> "EmbeddedSignalWorker":
        self._thread.start()
        return self

    def stop(self, timeout: float = 30.0) -> None:
        self.worker.stop()
        self._thread.join(timeout=timeout)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()


def start_embedded(runtime: Any, *, handoff: Optional[DetectionHandoff] = None
                   ) -> Optional[EmbeddedSignalWorker]:
    """Start the signal loop inside the calling process if it is configured.

    Returns ``None`` (and does nothing) when ``CORTEX_SIGNAL_TENANT_ID`` or
    ``CORTEX_SIGNAL_NAMESPACE`` is unset: an unconfigured API observes nothing,
    which is the pre-11.2 behaviour. A misconfiguration (missing capabilities,
    wrong tenant binding) is logged and refuses -- the API keeps booting; the
    signal loop does not run half-configured.
    """
    if not ((os.getenv("CORTEX_SIGNAL_TENANT_ID") or "").strip()
            and (os.getenv("CORTEX_SIGNAL_NAMESPACE") or "").strip()):
        return None
    try:
        cfg = SignalWorkerConfig.from_env()
        cfg = SignalWorkerConfig(**{**cfg.__dict__, "metrics_port": 0})
        worker = build_worker_from_runtime(runtime, config=cfg, handoff=handoff)
    except SystemExit as exc:
        log.error("embedded signal worker refused to start: %s", exc)
        return None
    except Exception:  # noqa: BLE001
        log.exception("embedded signal worker could not be composed")
        return None
    embedded = EmbeddedSignalWorker(worker).start()
    log.info("embedded signal worker started: tenant=%s namespace=%s",
             cfg.tenant_id, cfg.namespace)
    return embedded


def main(argv: Optional[list] = None) -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    worker = build_worker_from_env()
    port = worker.config.metrics_port
    if port > 0:
        try:
            from prometheus_client import start_http_server
            start_http_server(port)
            log.info("signal worker metrics on :%d/metrics", port)
        except Exception as exc:  # noqa: BLE001
            log.warning("metrics endpoint not started on :%d: %s", port, exc)

    def _stop(signum, _frame):  # noqa: ANN001
        log.info("signal worker received signal %s; stopping after this cycle", signum)
        worker.stop()

    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        sig = getattr(_signal, name, None)
        if sig is not None:
            try:
                _signal.signal(sig, _stop)
            except (ValueError, OSError):
                pass
    return worker.run()


if __name__ == "__main__":
    sys.exit(main())
