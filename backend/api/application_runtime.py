"""The governed application runtime: the 5.x composition, in the real app.

Phase 5.14, ADR-057. Before this module existed, the production architecture —
``DurablePersistence`` (which owns the fenced audit authority, ADR-056),
``build_production_connectivity`` (which refuses to assemble unaudited), the
``ExecutionScheduler``, the ``OutboxPublisher``, durable recovery — was proven
end to end by phase evidence but composed by nothing the application actually
runs. ``backend/main.py`` had no reference to any of it.

This module is that missing composition, and nothing else. It builds no new
mechanism: every part is the existing production builder, assembled in the
order their own contracts dictate, with the one lifecycle glue the parts do
not carry themselves (a pump thread for the outbox publisher, which is a batch
API by design).

Enablement is explicit, and failure is fail-closed
---------------------------------------------------
The governed runtime exists iff ``CORTEX_DURABLE_URL`` is set.

* **Unset** — the runtime is *absent*: no persistence, no gateway, no audit
  runtime, and the V1 application behaves exactly as before. Absence is not a
  fallback; there is nothing degraded pretending to be the governed path.
* **Set** — every failure from here is **fatal to startup**. A missing schema,
  an unreachable database, an invalid configuration: the process refuses to
  boot rather than run a version of itself that cannot durably record what it
  does. There is no create_all, no schema repair, no JSONL or in-memory
  fallback, and no branch that catches these and carries on.

The startup and shutdown orders are the components' own
--------------------------------------------------------
Startup: configuration → ``build_durable_persistence`` (verifies reachability,
transactions, and the Alembic-built schema, refusing otherwise) → services →
``build_production_connectivity`` (audit required) → lifecycle (dispatcher,
recovery) → scheduler → publisher pump → legacy facade rebind. The scheduler's
own ``start()`` runs recovery before dispatching (ADR-050); nothing here
re-implements that.

Shutdown: ``scheduler.stop()`` first — its contract drains the active cycle,
leaves live leases to recovery, and releases its leadership **last** — then
the publisher pump stops and releases ``OUTBOX_PUBLISHER``, then the audit
writer role is released, then the engine is disposed. Leadership is never
released while the work it coordinates might still be mid-cycle.
"""

from __future__ import annotations

import importlib
import logging
import os
import threading
from typing import Any, Callable, Optional, Sequence

__all__ = [
    "GovernedApplicationRuntime",
    "build_governed_runtime",
    "EventBusSink",
]

log = logging.getLogger(__name__)

#: The one switch. Absent: the governed runtime does not exist. Present: it
#: must assemble completely or the application must not start.
DSN_VARIABLE = "CORTEX_DURABLE_URL"


class EventBusSink:
    """Outbox delivery onto the application's existing EventBus.

    The V1 application already has one event backbone; outbox entries join it
    rather than a second one being invented. ``deliver`` runs on the publisher
    pump thread, so the coroutine is handed to the application's running loop;
    if no loop is available the outcome is **UNKNOWN** — truthful, because the
    delivery genuinely was not acknowledged — and the entry stays claimed for
    retry rather than being marked delivered on hope.
    """

    def __init__(self, bus: Any, *, loop: Optional[Any] = None,
                 timeout_seconds: float = 5.0) -> None:
        self._bus = bus
        self._loop = loop
        self._timeout = timeout_seconds

    def bind_loop(self, loop: Any) -> None:
        self._loop = loop

    def deliver(self, context: Any, entry: Any):
        from backend.contexts.execution.application.outbox_publisher import (
            DeliveryOutcome,
        )
        from backend.events.event_models import CognitionEvent

        try:
            import asyncio
            import json as _json

            # ``OutboxEntry.event`` is the serialized domain event document —
            # the thing the durable store can offer after a restart.
            document = entry.event if isinstance(entry.event, dict) else {
                "event": str(entry.event)}
            event = CognitionEvent(
                agent="governed_runtime",
                event_type=f"governed.{entry.event_type}",
                status="completed",
                message=_json.dumps(document, default=str, sort_keys=True),
                execution_id=str(entry.execution_id or entry.event_id),
                payload=document,
            )
            coroutine = self._bus.publish(event)
            if self._loop is not None and self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
                future.result(timeout=self._timeout)
            else:
                asyncio.run(coroutine)
            return DeliveryOutcome.DELIVERED
        except Exception as exc:  # noqa: BLE001 - unacknowledged is unknown, not failed
            # The cause is named: an operator staring at a stuck outbox needs
            # the reason, not just the outcome.
            log.warning(
                "outbox delivery to the event bus unacknowledged (%s: %s)",
                type(exc).__name__, str(exc)[:200], exc_info=False)
            return DeliveryOutcome.UNKNOWN


class GovernedApplicationRuntime:
    """The assembled governed composition and its lifecycle."""

    def __init__(
        self,
        *,
        persistence: Any,
        connectivity: Any,
        capabilities: Any,
        authorization: Any,
        resolution: Any,
        executions: Any,
        dispatcher: Any,
        recovery: Any,
        scheduler: Any,
        publisher: Any,
        publisher_leadership: Any,
        context_factory: Callable[[], Any],
        publish_interval_seconds: float = 1.0,
    ) -> None:
        self.persistence = persistence
        self.connectivity = connectivity
        self.capabilities = capabilities
        self.authorization = authorization
        self.resolution = resolution
        self.executions = executions
        self.dispatcher = dispatcher
        self.recovery = recovery
        self.scheduler = scheduler
        self.publisher = publisher
        self.audit = persistence.audit
        self.audit_writer = persistence.audit_writer
        # Phase 11.1-K: set by build_governed_runtime after commissioning.
        self.environment: Any = None
        self.manifests: tuple = ()
        self.connection_scopes: tuple = ()
        self.connector_reports: dict = {}
        self.health_probe_factories: dict = {}
        self.connector_health: Any = None
        self._publisher_leadership = publisher_leadership
        self._publisher_handle = None
        self._context_factory = context_factory
        self._publish_interval = publish_interval_seconds
        self._pump_stop = threading.Event()
        self._pump_thread: Optional[threading.Thread] = None
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> dict:
        """Start coordinating. Ordered by the components' own contracts."""
        if self._started:
            return {"started": False, "reason": "already started"}
        self._started = True

        # The legacy approval facade records into THE chain from now on —
        # the strangler seam of ADR-057. Bound before anything can record.
        from backend.services.enterprise_integrity_audit import integrity_audit

        integrity_audit.rebind(self.audit)

        # One process in the fleet becomes the audit writer; the others'
        # appends refuse and are contained (ADR-054/056). Not fatal: losing
        # this race is the ordinary follower outcome, not a failure.
        audit_handle = self.audit_writer.acquire()

        report = self.scheduler.start(self._context_factory())

        self._pump_stop.clear()
        self._pump_thread = threading.Thread(
            target=self._pump, name="governed-outbox-pump", daemon=True)
        self._pump_thread.start()

        summary = {
            "started": True,
            "audit_writer": audit_handle is not None,
            "scheduler": report.to_dict() if hasattr(report, "to_dict")
            else str(report),
        }
        log.info("governed runtime started: %s", summary)
        return summary

    def stop(self, *, timeout_seconds: float = 30.0) -> None:
        """Stop in the safe order; idempotent.

        Scheduler first (drains its cycle, releases its own role last), then
        the publisher pump (joined, then its role released), then the audit
        writer role, then the engine. Nothing releases a role while the work
        it coordinates may still be running.
        """
        if not self._started:
            return
        self._started = False

        try:
            self.scheduler.stop(timeout_seconds=timeout_seconds)
        except Exception:  # noqa: BLE001 - shutdown continues; recovery decides
            log.warning("scheduler stop failed; leases lapse on their own",
                        exc_info=False)

        self._pump_stop.set()
        thread = self._pump_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout_seconds)
        self._pump_thread = None
        if self._publisher_handle is not None:
            try:
                self._publisher_leadership.release(self._publisher_handle)
            except Exception:  # noqa: BLE001
                log.warning("outbox leadership release failed; lease will lapse",
                            exc_info=False)
            self._publisher_handle = None

        try:
            self.audit_writer.release()
        except Exception:  # noqa: BLE001
            log.warning("audit writer release failed; lease will lapse",
                        exc_info=False)

        try:
            self.persistence.store.engine.dispose()
        except Exception:  # noqa: BLE001
            log.debug("engine dispose failed", exc_info=False)
        log.info("governed runtime stopped")

    # ------------------------------------------------------------------

    def _pump(self) -> None:
        """Publish claimed outbox batches while holding OUTBOX_PUBLISHER.

        The claim is already exclusive per entry; the role bounds how many
        publishers compete (ADR-054). A process that does not hold the role
        idles rather than publishing — and keeps trying to acquire, because a
        publisher fleet must survive the current holder dying.
        """
        while not self._pump_stop.wait(self._publish_interval):
            try:
                # Phase 11.4 (F-11). The audit writer renews its lease through
                # ``is_writer`` on every append, so a quiet spell longer than the
                # lease lets it lapse -- and then any process may take the role.
                # When that happens the incumbent's next heartbeat returns None
                # and it drops its handle, and until now nothing ever called
                # ``acquire`` again outside startup: the runtime stopped writing
                # audit, permanently and without an error, because refused
                # appends are contained rather than raised (ADR-054/056).
                #
                # Reclaiming here costs one conditional UPDATE per pump cycle and
                # gives audit the same survivability the publisher already has.
                # Proven live: a second process seized the role (fence 51 -> 52)
                # while the deployment was idle.
                if getattr(self.audit_writer, "handle", None) is None:
                    if self.audit_writer.acquire() is not None:
                        log.info("audit-writer role (re)acquired by this instance")
                else:
                    # **Renew while we hold it.** The first version of this fix
                    # only re-acquired, which made two replicas thrash: the
                    # holder's lease lapsed in a quiet moment, the other
                    # reclaimed it, the first lost its next append and
                    # reclaimed it back, and the chain tail went stale under
                    # both. ``is_writer`` heartbeats, so calling it on the pump
                    # keeps the lease alive between appends instead of leaving
                    # it to expire whenever nothing is being audited.
                    self.audit_writer.is_writer()

                if self._publisher_handle is None:
                    self._publisher_handle = self._publisher_leadership.acquire()
                else:
                    renewed = self._publisher_leadership.heartbeat(
                        self._publisher_handle)
                    if renewed is None:
                        self._publisher_handle = None
                        continue
                    self._publisher_handle = renewed
                if self._publisher_handle is None:
                    continue
                self.publisher.publish_batch(self._context_factory())
            except Exception:  # noqa: BLE001 - the pump survives a bad batch
                log.warning("outbox publish cycle failed", exc_info=False)

    def describe(self) -> dict:
        return {
            "durable": True,
            "dialect": self.persistence.store.dialect,
            "instance_id": self.persistence.instance_id,
            "audit_store": type(self.audit.store).__name__,
            "audit_writer_held": self.audit_writer.handle is not None,
            "scheduler_state": getattr(
                getattr(self.scheduler, "_state", None), "value", "unknown"),
            "entry_point": self.connectivity.trace()["entry_point"],
        }


# ----------------------------------------------------------------------
# Assembly
# ----------------------------------------------------------------------


_RUNTIME_METRICS: dict = {}


def runtime_metrics() -> Any:
    """The process-wide fabric metrics recorder (Phase 11.1-K).

    One ``SafeMetrics``-wrapped Prometheus recorder per process, shared by the
    gateway's rate limiter, the credential and transport brokers and every
    connector adapter, so their counters appear on the one ``/metrics``
    endpoint the process serves. Without ``prometheus_client`` it is a
    ``NullMetrics`` -- measurement is never a reason a runtime cannot start.
    """
    recorder = _RUNTIME_METRICS.get("recorder")
    if recorder is None:
        from backend.platform.observability.metrics import NullMetrics, SafeMetrics

        try:
            from backend.observability.prometheus_recorder import PrometheusMetricsRecorder

            inner: Any = PrometheusMetricsRecorder()
        except ImportError:  # pragma: no cover - prometheus_client is a dependency
            inner = NullMetrics()
        recorder = _RUNTIME_METRICS.setdefault("recorder", SafeMetrics(inner))
    return recorder


def _load_extensions(environment: Any) -> dict:
    """Deployment-provided providers, from ``CORTEX_CONNECTOR_FACTORIES``.

    Comma-separated ``module:callable`` entries; each callable receives the
    execution environment and returns a mapping that may carry ``connectors``
    (``(entry, adapter, catalog)`` triples for the production builder's
    seam), ``credential_providers`` (registered on the production credential
    broker), and optionally ``context_factory`` / ``event_sink``.

    This is the same seam a second real provider arrives through — loading is
    explicit configuration, and a factory that fails is **fatal**, because a
    deployment that names a provider it cannot load should not come up
    half-composed.
    """
    spec = (os.getenv("CORTEX_CONNECTOR_FACTORIES") or "").strip()
    merged: dict = {"connectors": [], "credential_providers": [],
                    "context_factory": None, "event_sink": None,
                    # Phase 11.1-K: a connector extension may also declare its
                    # manifest (commissioned at boot) and the connection scopes
                    # its tenants are confined to (enforced at the gateway).
                    "manifests": [], "connection_scopes": [],
                    "credential_provider_builders": [], "health_probes": {}}
    if not spec:
        return merged
    for item in spec.split(","):
        module_name, _, attribute = item.strip().partition(":")
        factory = getattr(importlib.import_module(module_name), attribute)
        produced = factory(environment) or {}
        merged["connectors"].extend(produced.get("connectors", ()))
        merged["credential_providers"].extend(
            produced.get("credential_providers", ()))
        merged["context_factory"] = (
            produced.get("context_factory") or merged["context_factory"])
        merged["event_sink"] = produced.get("event_sink") or merged["event_sink"]
        merged["manifests"].extend(produced.get("manifests", ()))
        merged["connection_scopes"].extend(produced.get("connection_scopes", ()))
        merged["credential_provider_builders"].extend(
            produced.get("credential_provider_builders", ()))
        merged["health_probes"].update(produced.get("health_probes", {}))
    return merged


def build_governed_runtime(
    *,
    event_bus: Optional[Any] = None,
    loop: Optional[Any] = None,
    instance_id: Optional[str] = None,
    approvals_factory: Optional[Any] = None,
) -> Optional[GovernedApplicationRuntime]:
    """Assemble the governed runtime, or return ``None`` when disabled.

    ``None`` means **absent** — ``CORTEX_DURABLE_URL`` is not set and the V1
    application runs exactly as before. Once the variable is set, every
    failure in here propagates: the caller (the application lifespan) must
    not catch it and continue, because a process that starts anyway would be
    the unaudited, non-durable version of itself wearing the same name.
    """
    dsn = (os.getenv(DSN_VARIABLE) or "").strip()
    if not dsn:
        log.info(
            "governed durable runtime is absent (%s not set); the V1 "
            "composition is unchanged and no governed gateway exists in this "
            "process", DSN_VARIABLE)
        return None

    from backend.api.capability_authorization_composition import build_authorization
    from backend.api.capability_execution_composition import (
        build_execution_lifecycle,
    )
    from backend.api.capability_resolution_composition import build_resolution
    from backend.api.delegation_composition import build_delegation_authority
    from backend.api.durability_composition import (
        SchedulerLeadership,
        build_durable_persistence,
    )
    from backend.api.production_connectivity import (
        ProductionConnectivityConfig,
        build_production_connectivity,
    )
    from backend.contexts.connectivity.application.service import CapabilityService
    from backend.contexts.execution.application.outbox_publisher import (
        OutboxPublisher,
    )
    from backend.contexts.execution.application.scheduler import ExecutionScheduler
    from backend.contexts.execution.application.service import ExecutionService
    from backend.contracts.execution import ExecutionEnvironment
    from backend.database.durable.config import DurabilityConfig
    from backend.database.durable.leadership import LeadershipRole

    environment = ExecutionEnvironment(
        (os.getenv("CORTEX_DURABLE_ENV") or "development").lower())

    # 1. The durable root. Verifies reachability, transactions, and the
    #    Alembic schema; refuses otherwise. Owns THE audit (ADR-056).
    persistence = build_durable_persistence(
        config=DurabilityConfig(environment=environment,
                                dsn_variable=DSN_VARIABLE),
        dsn=dsn,
        instance_id=instance_id,
    )

    # 2. Services, from their real builders.
    capabilities = CapabilityService(persistence.capabilities)
    # ``approvals_factory`` is called with the durable store and returns an
    # ``ApprovalLookup``. Passing it HERE rather than assigning
    # ``authorization._approvals`` afterwards matters: ``build_authorization``
    # already declares the parameter, and reaching into a private attribute to
    # install a security-relevant dependency is how a deployment ends up with an
    # approval system nobody can find by reading the composition.
    #
    # ``None`` remains the default and still means every approval lookup fails
    # closed, so no existing caller changes behaviour.
    approvals = None
    if approvals_factory is not None:
        approvals = approvals_factory(persistence.store)
    authorization = build_authorization(capabilities, approvals=approvals)
    resolution = build_resolution(capabilities, bindings=persistence.bindings)
    executions = ExecutionService(persistence.executions,
                                  outbox=persistence.outbox)

    # 3. Deployment extensions (additional providers, credentials).
    extensions = _load_extensions(environment)
    context_factory = extensions["context_factory"] or _platform_context

    # 4. The one governed path. GitHub stays off unless explicitly enabled;
    #    enabling it is a deployment decision, never a default.
    enable_github = (os.getenv("CORTEX_ENABLE_GITHUB") or "0").strip() == "1"
    # Phase 11.1-K (audit S-3): the gateway's rate stage existed and nothing
    # was ever passed to it. One limiter, at the one choke point, always on;
    # CORTEX_RATE_LIMIT_* resizes the budgets and can never remove them.
    from backend.contexts.execution.infrastructure.rate_limiting import build_rate_limiter

    rate_limiter = build_rate_limiter(metrics=runtime_metrics())
    connectivity = build_production_connectivity(
        config=ProductionConnectivityConfig(
            environment=environment,
            vault_address=os.getenv("CORTEX_VAULT_ADDR",
                                    "http://localhost:8200"),
            allow_private_destinations=environment
            is not ExecutionEnvironment.PRODUCTION,
            allow_plaintext=environment is not ExecutionEnvironment.PRODUCTION,
            # Transport policy, not a credential: a CA bundle *path* for
            # deployments whose provider endpoints present a private-CA
            # certificate (a local k3d/kind API server). Verification is never
            # disabled — this only states which authority to verify against
            # (TlsPolicy.ca_bundle_path → httpx verify=<path>; there is no
            # verify=False anywhere in the transport).
            ca_bundle_path=(os.getenv("CORTEX_TLS_CA_BUNDLE") or "").strip()
            or None,
        ),
        resolution_service=resolution,
        authorization_service=authorization,
        execution_service=executions,
        worker_kind_resolver=_ConnectorKindResolver(),
        context_factory=context_factory,
        delegation=build_delegation_authority(persistence.delegations),
        rate_limiter=rate_limiter,
        audit=persistence.audit,
        # Phase 11.1-K: the fabric's credential, transport and adapter metrics
        # were threaded through every builder and never supplied.
        metrics=runtime_metrics(),
        enable_github=enable_github,
        connectors=extensions["connectors"],
        connection_scopes=extensions["connection_scopes"],
    )
    for provider in extensions["credential_providers"]:
        connectivity.credential_broker.register(provider)
    # Phase 11.1-K: adapters that dial through the transport broker (Vault) can
    # only be built once it exists.
    for build_provider in extensions["credential_provider_builders"]:
        connectivity.credential_broker.register(build_provider(connectivity))

    # 5. Lifecycle: dispatcher + recovery, scheduler, publisher.
    dispatcher, recovery = build_execution_lifecycle(
        execution_service=executions,
        gateway=connectivity.gateway,
        resolution_service=resolution,
        worker_runtime=connectivity.worker_runtime,
        environment=environment,
        queue=persistence.queue,
    )
    scheduler = ExecutionScheduler(
        dispatcher=dispatcher,
        recovery=recovery,
        context_factory=context_factory,
        interval_seconds=float(os.getenv("CORTEX_SCHEDULER_INTERVAL", "0.5")),
        leadership=SchedulerLeadership(persistence.leadership),
        readiness=persistence.readiness_port,
        # Phase 11.3 (ADR-127): dispatch targets come from the durable store, not
        # only from what this process happened to start. Without this the
        # scheduler dispatches an execution nobody else can see and no other
        # process can rescue -- F-3.
        discovery=lambda ctx: executions.dispatchable(ctx),
    )
    sink = extensions["event_sink"]
    if sink is None:
        if event_bus is None:
            from backend.events.event_bus import event_bus as bus

            event_bus = bus
        sink = EventBusSink(event_bus, loop=loop)
    publisher = OutboxPublisher(
        outbox=persistence.outbox,
        sink=sink,
        publisher_id=persistence.instance_id,
        claim_seconds=int(os.getenv("CORTEX_OUTBOX_CLAIM_SECONDS", "60")),
        batch_size=int(os.getenv("CORTEX_OUTBOX_BATCH", "50")),
    )
    publisher_leadership = SchedulerLeadership(
        persistence.leadership, role=LeadershipRole.OUTBOX_PUBLISHER)

    runtime = GovernedApplicationRuntime(
        persistence=persistence,
        connectivity=connectivity,
        capabilities=capabilities,
        authorization=authorization,
        resolution=resolution,
        executions=executions,
        dispatcher=dispatcher,
        recovery=recovery,
        scheduler=scheduler,
        publisher=publisher,
        publisher_leadership=publisher_leadership,
        context_factory=context_factory,
        publish_interval_seconds=float(
            os.getenv("CORTEX_OUTBOX_INTERVAL", "1.0")),
    )

    # 6. Phase 11.1-K: boot-time connector commissioning. Every connector this
    #    process composed and declared a manifest for gets its capabilities
    #    registered (full contract), enabled and trusted, and its workers
    #    admitted -- idempotently, refusing silent contract drift. Before this
    #    a governed process had no capabilities until a script registered them.
    from backend.api.connector_commissioning import commission_connector

    runtime.environment = environment
    runtime.manifests = tuple(extensions["manifests"])
    runtime.health_probe_factories = dict(extensions["health_probes"])
    runtime.connection_scopes = tuple(extensions["connection_scopes"])
    runtime.connector_reports = {}
    for manifest in runtime.manifests:
        try:
            runtime.connector_reports[manifest.connector_id] = commission_connector(
                runtime, manifest, environment=environment.value)
        except Exception as exc:  # noqa: BLE001 - reported through health, not fatal
            log.error("connector %s could not be commissioned: %s",
                      manifest.connector_id, type(exc).__name__, exc_info=True)
    return runtime


class _ConnectorKindResolver:
    """Every governed capability in this composition rides a connector."""

    def kind_for(self, capability_ref: Any, node: Any = None) -> str:
        return "connector"

    def resolve(self, capability_ref: Any, node: Any = None) -> str:
        return "connector"


def _platform_context() -> Any:
    """The background-coordination context, from the platform's own contract."""
    from backend.platform.context import ExecutionContext

    return ExecutionContext.platform_internal(
        reason="governed runtime background coordination (scheduler/outbox)",
        component="cortexprime.governed_runtime",
        source="lifecycle",
    )
