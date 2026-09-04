"""Composition root: Connectivity's binding meets Execution's runtime.

**This is the only module that imports both contexts.** Execution does not import
Connectivity and Connectivity does not import Execution — verified in both
directions by architecture tests. Everything they exchange crosses here, as
primitives.

Three adapters, three ports
-----------------------------
``BindingProjector``   — ``CapabilityBinding`` → ``BoundCapability``. A one-way
                         projection into primitives: Execution receives what was
                         authorized and gains no way to mint one.
``BindingValidatorAdapter`` — implements Execution's ``BindingValidator`` over
                         Connectivity's ``validate_binding`` (ADR-035), so the
                         authoritative lifecycle/trust/digest re-check happens
                         where that state actually lives.
``WorkerKindAdapter``  — implements Execution's ``WorkerKindPort`` over the
                         existing ``WorkerKindResolver`` (ADR-030), which is
                         unchanged and remains the single execution attachment
                         seam.

Phase 3.3.2 — the adapter fabric attaches here, and only here
---------------------------------------------------------------
``build_worker_directory`` assembles the governed directory and the three adapter
seams. It is the only place where a worker implementation, a capability binding
and an execution runtime are in the same room, which is what keeps the two
contexts from learning about each other.

Environment and interface cross here too. ``CapabilityBinding`` carries neither —
they belong to the resolution request and to the capability definition — so
``project_binding`` takes them explicitly from a caller that still has the
Connectivity picture. Where a caller cannot supply the environment, every worker
selection refuses, because an unstated environment is not a wildcard.

Phase 4.3 — providers attach here, and only here
--------------------------------------------------
``build_github_connector`` is the first real provider wiring: a worker
registration, an operation catalog, a channel over the Phase 4.2 transport
broker, and a translator. It is a *function a deployment calls*, not something
that happens at import — a provider that attached itself on import would be a
provider nobody decided to enable.

``build_adapter_preflight`` implements the adapter's final TOCTOU re-read over
the worker directory, so an adapter about to open a socket asks the
authoritative record one more time (ADR-042 §37).

``build_operation_input_validator`` fills the Phase 3.3.3 ``InputValidator`` seam
from the same catalogs the adapters build requests from — one declaration, used
for both, so "what is checked" and "what may be sent" cannot diverge.

Deliberately absent
---------------------
No worker registers itself. The directory starts empty, so every invocation
refuses. That is the correct behaviour for a platform with no workers: it
refuses rather than inventing a default.

No transport adapter. ``build_github_connector`` takes a ``TransportBroker``;
with no HTTP adapter registered on it, every dial refuses
``transport_unavailable`` and the connector reports a definite failure having
sent nothing. Phase 4.4 is where a production transport is attached.

No credential adapter. The gateway acquires through ``CredentialProvider``;
with no vendor adapter registered, acquisition refuses ``credential_no_provider``
and the invocation never reaches an adapter.

No bridge to the V1 registries. ``backend.tools.tool_registry``,
``backend.connectors.registry``, ``backend.agents.registry``,
``backend.mcp.registry`` and ``backend.runtime.agent_registry`` are all mutable
module-level singletons and all **strangler targets**. Nothing in this module
imports any of them, and the new fabric depends on none of their state. When one
must be bridged, it goes behind an invoker port *here*, explicitly marked
migration infrastructure — never imported into a context.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.policy import PolicyEffect
from backend.contexts.connectivity import CapabilityBinding
from backend.contexts.execution import (
    AgentAdapter,
    AuthorityFacts,
    BoundCapability,
    ConnectorAdapter,
    InMemoryWorkerDirectory,
    InvocationRequest,
    LeaseFacts,
    ExecutionDispatcher,
    McpToolAdapter,
    RecoveryCoordinator,
    SecureCapabilityInvocationGateway,
    WorkerImplementation,
    WorkerKind,
    WorkerRuntime,
)

__all__ = [
    "project_binding",
    "BindingValidatorAdapter",
    "WorkerKindAdapter",
    "AuthorizationAuthorityAdapter",
    "DelegationGrant",
    "ExecutionLeaseAdapter",
    "ExecutionResultRecorder",
    "build_worker_directory",
    "build_adapter",
    "build_adapter_preflight",
    "build_operation_input_validator",
    "build_github_connector",
    "DirectoryAdapterPreflight",
    "build_worker_runtime",
    "build_invocation_gateway",
    "build_execution_lifecycle",
    "StoredBindingSource",
    "SelectingRequestFactory",
    "ADAPTER_SEAMS",
    "GovernedCapabilityReader",
    "GovernedCapabilityWriter",
    "build_prometheus_connector",
]

log = logging.getLogger(__name__)

#: Which seam drives which kind. The whole mapping, and it is exhaustive: a kind
#: with no seam has no adapter, and a binding that resolves to it refuses. Adding
#: a provider does not add an entry here — providers attach behind an invoker.
ADAPTER_SEAMS: Mapping[WorkerKind, type] = {
    WorkerKind.MCP: McpToolAdapter,
    WorkerKind.CONNECTOR: ConnectorAdapter,
    WorkerKind.AGENT: AgentAdapter,
}


def project_binding(
    binding: CapabilityBinding,
    *,
    environment: Optional[ExecutionEnvironment] = None,
    interface: Optional[str] = None,
) -> BoundCapability:
    """Project a Connectivity binding into the primitives Execution may hold.

    One-way on purpose. There is no inverse: Execution cannot reconstruct a
    ``CapabilityBinding``, so it can never produce authority — only carry it.

    ``environment`` and ``interface`` are supplied rather than read off the
    binding, which carries neither. They are **not defaulted**: a projection that
    guessed ``PRODUCTION`` would authorize the worst case, and one that guessed
    ``DEVELOPMENT`` would let a development-only worker perform production work.
    Omitting the environment makes every selection refuse, which is the only safe
    third option.
    """
    if binding.digest is None:
        raise ValueError(
            f"binding {binding.binding_id} is unsealed; an unsealed binding "
            "cannot be shown to be the one that was made"
        )
    if binding.effect_semantics is None or binding.side_effect_class is None:
        raise ValueError(
            f"binding {binding.binding_id} does not declare its effect; Execution "
            "decides retry safety from that declaration and will not infer one"
        )
    if environment is not None and not isinstance(environment, ExecutionEnvironment):
        raise ValueError("environment must be an ExecutionEnvironment")
    return BoundCapability(
        environment=environment,
        interface=interface,
        binding_id=binding.binding_id,
        binding_digest=binding.digest,
        capability_ref=binding.reference.value,
        capability_digest=binding.capability_digest,
        provider=binding.provider,
        # The **provider** operation when the capability declares one, and the
        # governance verb only as a fallback. Execution's two consumers of this
        # field -- worker selection and input validation -- both look it up in a
        # provider catalog, so handing them 'invoke' means no worker with a
        # declared catalog can ever be selected. Falling back keeps the previous
        # behaviour for capabilities that declare nothing, and that fallback is
        # still a refusal rather than a wildcard.
        operation=binding.provider_operation or binding.operation.value,
        governance_operation=binding.operation.value,
        authorization_digest=binding.authorization_digest,
        tenant_id=binding.tenant_id,
        principal_id=binding.principal.principal_id,
        expires_at=binding.expires_at,
        side_effect_class=binding.side_effect_class,
        effect_semantics=binding.effect_semantics,
        execution_id=binding.execution_id,
        node_id=binding.node_id,
        workflow_id=binding.workflow_id,
        mission_id=binding.mission_id,
        resolution_policy_version=binding.resolution_policy_version,
        authorization_policy_version=binding.authorization_policy_version,
    )


class BindingValidatorAdapter:
    """Execution's ``BindingValidator``, answered by Connectivity.

    Looks the binding up by id and asks ``validate_binding`` — the same
    authoritative re-check ADR-035 defined. Execution never sees the aggregate;
    it receives the invalidation reasons.

    A binding that cannot be found is invalid, not absent-and-therefore-fine.
    """

    def __init__(self, resolution_service: Any) -> None:
        self._resolution = resolution_service

    def invalidations(self, context: Any, binding: BoundCapability) -> tuple:
        stored = self._resolution._bindings.find(  # noqa: SLF001
            context, binding.binding_id
        )
        if stored is None:
            return ("binding_not_found",)
        if stored.digest != binding.binding_digest:
            # The projection disagrees with the record it claims to describe.
            return ("binding_digest_mismatch",)
        return tuple(
            self._resolution.validate_binding(
                context,
                stored,
                tenant_id=binding.tenant_id,
                principal_id=binding.principal_id,
                execution_id=binding.execution_id,
                node_id=binding.node_id,
            )
        )


class WorkerKindAdapter:
    """Execution's ``WorkerKindPort``, answered by the existing resolver.

    ``WorkerKindResolver`` (ADR-030) is unchanged. It was written to answer
    "which kind of worker runs this node?" from a workflow node; here it is
    asked the same question about a bound capability, and the mapping key is the
    capability reference.

    A resolver that cannot answer returns ``None``, and Execution refuses.
    Nothing here supplies a default.
    """

    def __init__(self, resolver: Any) -> None:
        self._resolver = resolver

    def kind_for(self, binding: BoundCapability) -> Optional[str]:
        # The resolver's node-shaped interface, satisfied by the capability.
        probe = _CapabilityAsNode(binding)
        try:
            return self._resolver.kind_for(binding.capability_ref, probe)
        except Exception:  # noqa: BLE001 - unresolvable is a refusal, not a guess
            log.warning("worker kind resolution failed", exc_info=True)
            return None


class _CapabilityAsNode:
    """Adapts a bound capability to the shape ``WorkerKindResolver`` reads.

    The resolver takes something with a ``node_id``. Rather than change its
    semantics — which ADR-030 and every later phase have preserved — the
    capability reference is presented as the node identity, so an existing
    resolver keyed by capability works unmodified.
    """

    __slots__ = ("node_id", "binding")

    def __init__(self, binding: BoundCapability) -> None:
        self.node_id = binding.capability_ref
        self.binding = binding


def build_worker_directory() -> InMemoryWorkerDirectory:
    """The governed directory. Empty, and it stays empty until somebody registers.

    **Supersedes ``StaticWorkerDirectory`` (ADR-036).** That was one lookup from
    kind to adapter — deliberately minimal, and insufficient once workers are
    real: it could not express a worker being disabled rather than absent, could
    not confine a tenant's registration to that tenant, and offered nothing to
    re-read between selecting a worker and calling it. It is removed rather than
    kept alongside, because two lookup paths is how one of them stops being
    checked. It had no callers.
    """
    return InMemoryWorkerDirectory()


def build_adapter(
    implementation: WorkerImplementation,
    *,
    provider: Any,
    catalog: Optional[Any] = None,
    channel: Optional[Any] = None,
    invoker: Optional[Any] = None,
    translator: Optional[Any] = None,
    normalizer: Optional[Any] = None,
    decoder: Optional[Any] = None,
    body_builder: Optional[Any] = None,
    preflight: Optional[Any] = None,
    metrics: Optional[Any] = None,
) -> Any:
    """Construct the seam for an implementation's kind, wired to one provider.

    ``provider`` is required and not derived: an adapter that inferred which
    provider it served — from the registration, from the first binding it saw —
    would be an adapter that could serve a different one tomorrow. It is stated,
    checked against the registration, and checked again against every binding.

    A ``channel`` is the transport for MCP and connector adapters; an ``invoker``
    is the runtime for agent adapters. With neither attached the adapter reports
    a definite failure having sent nothing, which is honest: a call that could
    not be made did not happen, and calling it ambiguous would block a retry on
    a node that never left this process.
    """
    from backend.contracts.provider import ProviderRef

    if not isinstance(provider, ProviderRef):
        raise ValueError("an adapter must be built for an explicit ProviderRef")
    kind = implementation.worker_kind
    seam = ADAPTER_SEAMS.get(kind)
    if seam is None:
        raise ValueError(
            f"no adapter seam drives {kind.value} work; a kind with no seam has "
            "no adapter, and inventing one here would run real work through "
            "something nobody wrote for it"
        )
    common = {
        "implementation": implementation,
        "provider": provider,
        "preflight": preflight,
        "metrics": metrics,
    }
    if kind is WorkerKind.AGENT:
        return seam(invoker=invoker, **common)
    if kind is WorkerKind.MCP:
        return seam(catalog=catalog, channel=channel, **common)
    return seam(
        catalog=catalog, channel=channel, translator=translator,
        normalizer=normalizer, decoder=decoder, body_builder=body_builder,
        **common,
    )


class DirectoryAdapterPreflight:
    """The adapter's last authoritative re-read. Implements ``AdapterPreflight``.

    ADR-042 §37. The worker runtime already re-read the directory entry when it
    admitted the invocation; this runs *inside* the adapter, immediately before
    a socket exists, because the gap between those two moments is exactly the
    window an operator uses to disable a compromised adapter.

    Fails closed in every direction: no directory, no context, a lookup that
    raises, a missing entry or an entry whose digest moved all produce refusal
    reasons rather than an empty tuple.
    """

    def __init__(
        self,
        directory: Any,
        *,
        context_factory: Optional[Any] = None,
    ) -> None:
        self._directory = directory
        self._context_factory = context_factory

    def refusals(self, authority: Any, *, now: Any) -> tuple:
        if self._directory is None or self._context_factory is None:
            return ("adapter_state_unverifiable",)
        try:
            context = self._context_factory()
            entry = self._directory.entry(
                context,
                worker_id=authority.worker_id,
                tenant_id=authority.tenant_id,
            )
        except Exception:  # noqa: BLE001 - unverifiable is unusable
            log.warning("adapter preflight lookup failed", exc_info=False)
            return ("adapter_state_unverifiable",)

        if entry is None:
            return ("adapter_not_registered",)
        problems: list = []
        if not entry.lifecycle.permits_execution:
            # A disabled adapter must never execute, and a revoked one is
            # terminal. Both arrive here as the same refusal shape and keep
            # their own reason so an operator can tell which.
            problems.append(f"adapter_lifecycle_{entry.lifecycle.value}")
        if not entry.trust.permits_execution:
            # Adapter trust, separate from capability trust. A trusted
            # capability reached through an unverified adapter is not a trusted
            # execution.
            problems.append(f"adapter_trust_{entry.trust.value}")
        if not entry.availability.accepts_work:
            problems.append(f"adapter_availability_{entry.availability.value}")
        if entry.worker_digest != authority.worker_digest:
            # Same id, different build. The audit trail would name the
            # implementation that was selected while different code ran.
            problems.append("adapter_digest_changed")
        return tuple(problems)


def build_adapter_preflight(
    directory: Any, *, context_factory: Optional[Any] = None
) -> DirectoryAdapterPreflight:
    return DirectoryAdapterPreflight(directory, context_factory=context_factory)


def build_operation_input_validator(*catalogs: Any) -> Any:
    """Fill the Phase 3.3.3 ``InputValidator`` seam from the adapter catalogs.

    One declaration, used by the validator and by the adapter that builds the
    request. A separate schema copy would diverge on the first change, after
    which one of the two is wrong and nobody knows which.

    With no catalogs, every payload-carrying invocation refuses — the same
    fail-closed behaviour the seam has had since it was empty.
    """
    from backend.contexts.execution import OperationInputValidator

    return OperationInputValidator(catalogs)


def build_github_connector(
    *,
    transport_broker: Any,
    connection_policy: Any,
    environment: ExecutionEnvironment,
    worker_id: str = "github-connector",
    base_url: Optional[str] = None,
    preflight: Optional[Any] = None,
    metrics: Optional[Any] = None,
    isolation: Optional[Any] = None,
) -> tuple:
    """The first production connector. Returns ``(entry, adapter, catalog)``.

    Returns the ``WorkerEntry`` at ``REGISTERED``/``UNVERIFIED``/``UNAVAILABLE``
    rather than enabling it. Three separate deliberate acts stand between
    recording an implementation and it being handed real work, and none of them
    happens as a side effect of construction (ADR-036). A deployment that wants
    this connector live has to validate it, enable it, trust it and mark it
    available — four decisions with four records.

    Nothing here contacts GitHub. Construction is side-effect-free (§52): no
    resource is created, no capability is registered, no provider state is
    touched, and no health probe is fired.
    """
    from backend.contracts.connector import IsolationTier
    from backend.contexts.execution import (
        WorkerEntry,
        WorkerInterface,
        WorkerScope,
    )
    from backend.contexts.execution.infrastructure.adapters.connectors.github import (
        GITHUB_PROVIDER,
        GITHUB_PROVIDER_ID,
        GITHUB_API_BASE,
        GitHubResponseTranslator,
        build_github_channel,
        github_catalog,
    )

    catalog = github_catalog()
    channel = build_github_channel(
        broker=transport_broker,
        policy=connection_policy,
        environment=environment,
        base_url=base_url or GITHUB_API_BASE,
    )
    implementation = WorkerImplementation(
        worker_id=worker_id,
        worker_kind=WorkerKind.CONNECTOR,
        interface=WorkerInterface.CONNECTOR,
        implementation=(
            "backend.contexts.execution.infrastructure.adapters.connector."
            "ConnectorAdapter+connectors.github"
        ),
        implementation_version="1.0.0",
        # What this implementation *actually* provides, and the default is the
        # weakest tier on purpose.
        #
        # ``AMBIENT`` is ADR-005's "read-only calls to declared APIs, with
        # process-level scoped credentials", which is exactly what an in-process
        # HTTPS adapter is. The consequence is deliberate and worth stating: the
        # two mutating operations in the GitHub catalog are
        # ``IRREVERSIBLE_WRITE``, ``IsolationTier.AMBIENT`` is sufficient only
        # for ``READ``, and so **worker selection refuses them with
        # ``isolation_insufficient``** until a deployment runs this adapter
        # somewhere that genuinely provides more and says so here.
        #
        # That refusal is the fabric working. Declaring ``SEALED`` to make the
        # write selectable would be claiming hardware isolation this process
        # does not have, and the gate would then be waved through for every
        # later capability that needs it.
        isolation=isolation or IsolationTier.AMBIENT,
        scope=WorkerScope.PLATFORM,
        supported_environments=frozenset({environment}),
        supported_effects=frozenset(
            {spec.effect_semantics for spec in _catalog_specs(catalog)}
        ),
        supported_providers=frozenset({GITHUB_PROVIDER_ID}),
        supported_operations=frozenset(catalog.operations),
        # GitHub has no idempotency mechanism. Declared honestly so Execution's
        # retry rules know which kind of provider they are dealing with.
        supports_provider_idempotency=False,
    )
    adapter = build_adapter(
        implementation,
        provider=GITHUB_PROVIDER,
        catalog=catalog,
        channel=channel,
        translator=GitHubResponseTranslator(),
        preflight=preflight,
        metrics=metrics,
    )
    return WorkerEntry(implementation=implementation), adapter, catalog


def build_grafana_connector(
    *,
    transport_broker: Any,
    connection_policy: Any,
    environment: ExecutionEnvironment,
    worker_id: str = "grafana-connector",
    base_url: Optional[str] = None,
    preflight: Optional[Any] = None,
    metrics: Optional[Any] = None,
    isolation: Optional[Any] = None,
) -> tuple:
    """The second declared provider (Phase 6.1). Returns ``(entry, adapter, catalog)``.

    Same contract as :func:`build_github_connector`: the entry is returned at
    ``REGISTERED``/``UNVERIFIED``/``UNAVAILABLE``, construction contacts
    nothing, and four separate deliberate acts stand between this and real
    work.

    Isolation is ``CONTAINED``, and the claim is examined rather than assumed
    (the GitHub comment below this one is the precedent for saying this out
    loud): the catalog's one write is ``REVERSIBLE_WRITE`` with a complete
    declared inverse; every operation is declared, validated, and digested;
    and the credential is minted per execution by the broker with a bounded
    lifetime. What this in-process adapter does NOT provide is a separate
    worker process — recorded here and in ADR-059 as the accepted deviation
    for the development deployment, to be revisited when workers gain process
    separation. Declaring ``AMBIENT`` instead would refuse the write and with
    it the phase's one governed side effect; declaring ``SEALED`` would claim
    hardware isolation that does not exist. ``CONTAINED`` is the honest middle
    with one stated gap.
    """
    from backend.contracts.connector import IsolationTier
    from backend.contexts.execution import (
        WorkerEntry,
        WorkerInterface,
        WorkerScope,
    )
    from backend.contexts.execution.infrastructure.adapters.connectors.grafana import (
        GRAFANA_API_BASE,
        GRAFANA_PROVIDER,
        GRAFANA_PROVIDER_ID,
        GrafanaResponseTranslator,
        build_grafana_channel,
        grafana_catalog,
    )

    catalog = grafana_catalog()
    channel = build_grafana_channel(
        broker=transport_broker,
        policy=connection_policy,
        environment=environment,
        base_url=base_url or GRAFANA_API_BASE,
    )
    implementation = WorkerImplementation(
        worker_id=worker_id,
        worker_kind=WorkerKind.CONNECTOR,
        interface=WorkerInterface.CONNECTOR,
        implementation=(
            "backend.contexts.execution.infrastructure.adapters.connector."
            "ConnectorAdapter+connectors.grafana"
        ),
        implementation_version="1.0.0",
        isolation=isolation or IsolationTier.CONTAINED,
        scope=WorkerScope.PLATFORM,
        supported_environments=frozenset({environment}),
        supported_effects=frozenset(
            {spec.effect_semantics for spec in _catalog_specs(catalog)}
        ),
        supported_providers=frozenset({GRAFANA_PROVIDER_ID}),
        supported_operations=frozenset(catalog.operations),
        # Grafana reads no idempotency key on these endpoints. Declared
        # honestly, exactly as for GitHub.
        supports_provider_idempotency=False,
    )
    adapter = build_adapter(
        implementation,
        provider=GRAFANA_PROVIDER,
        catalog=catalog,
        channel=channel,
        translator=GrafanaResponseTranslator(),
        preflight=preflight,
        metrics=metrics,
    )
    return WorkerEntry(implementation=implementation), adapter, catalog


def build_kubernetes_connector(
    *,
    transport_broker: Any,
    connection_policy: Any,
    environment: ExecutionEnvironment,
    base_url: str,
    worker_id: str = "kubernetes-connector",
    preflight: Optional[Any] = None,
    metrics: Optional[Any] = None,
    isolation: Optional[Any] = None,
) -> tuple:
    """The REAL governed Kubernetes read connector (Phase 9.2, ADR-082).
    Returns ``(entry, adapter, catalog)`` — the same contract as the GitHub and
    Grafana builders: the entry is returned at REGISTERED/UNVERIFIED/UNAVAILABLE,
    construction contacts nothing, and the same deliberate acts stand between
    this and real work.

    The catalog is the real exposure, which has only ever grown deliberately:
    the list (9.2), the watch that continues it (9.3), and the two reads a
    CrashLoopBackOff differential turns on (9.5). The declared write
    (``kubernetes.workload.rollout_restart``) is **deliberately not in it**: an
    ``IRREVERSIBLE_WRITE`` may not be performed by a CONTAINED in-process worker,
    so composing it here would offer an operation this worker must refuse
    (ADR-086). The adapter is the generic
    ``ConnectorAdapter``: catalog + translator + normalizer + channel, no
    Kubernetes SDK, no second HTTP client, no connector-owned credential. The
    ``base_url`` is deployment configuration with deliberately no default: no
    universal Kubernetes address exists. Isolation is ``CONTAINED`` with the
    same stated in-process gap as GitHub/Grafana (ADR-059).
    """
    from backend.contracts.connector import IsolationTier
    from backend.contexts.execution import (
        WorkerEntry,
        WorkerInterface,
        WorkerScope,
    )
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        KUBERNETES_PROVIDER,
        KUBERNETES_PROVIDER_ID,
        KubernetesReadNormalizer,
        KubernetesResponseTranslator,
        KubernetesRestartBodyBuilder,
        KubernetesWatchDecoder,
        build_kubernetes_channel,
        kubernetes_real_read_catalog,
    )

    catalog = kubernetes_real_read_catalog()
    channel = build_kubernetes_channel(
        broker=transport_broker,
        policy=connection_policy,
        environment=environment,
        base_url=base_url,
    )
    implementation = WorkerImplementation(
        worker_id=worker_id,
        worker_kind=WorkerKind.CONNECTOR,
        interface=WorkerInterface.CONNECTOR,
        implementation=(
            "backend.contexts.execution.infrastructure.adapters.connector."
            "ConnectorAdapter+connectors.kubernetes"
        ),
        implementation_version="1.0.0",
        isolation=isolation or IsolationTier.CONTAINED,
        scope=WorkerScope.PLATFORM,
        supported_environments=frozenset({environment}),
        supported_effects=frozenset(
            {spec.effect_semantics for spec in _catalog_specs(catalog)}
        ),
        supported_providers=frozenset({KUBERNETES_PROVIDER_ID}),
        supported_operations=frozenset(catalog.operations),
        # The API server reads no idempotency key; reads need none. Declared
        # honestly, exactly as for GitHub/Grafana.
        supports_provider_idempotency=False,
    )
    adapter = build_adapter(
        implementation,
        provider=KUBERNETES_PROVIDER,
        catalog=catalog,
        channel=channel,
        translator=KubernetesResponseTranslator(),
        normalizer=KubernetesReadNormalizer(),
        # Phase 9.3: the watch window is newline-delimited JSON. The decoder
        # dispatches on the operation's own declaration (static_query watch=true)
        # and hands every other operation straight to the JSON path.
        decoder=KubernetesWatchDecoder(),
        # Phase 9.6: every Kubernetes mutation is a nested document, which the
        # flat body a spec declares cannot express. The builder constructs the ONE
        # document this platform may send, from the already-validated payload.
        body_builder=KubernetesRestartBodyBuilder(),
        preflight=preflight,
        metrics=metrics,
    )
    return WorkerEntry(implementation=implementation), adapter, catalog


def build_prometheus_connector(
    *,
    transport_broker: Any,
    connection_policy: Any,
    environment: ExecutionEnvironment,
    base_url: str,
    namespace: str,
    worker_id: str = "prometheus-connector",
    preflight: Optional[Any] = None,
    metrics: Optional[Any] = None,
    isolation: Optional[Any] = None,
) -> tuple:
    """The governed Prometheus READ connector (Phase 9.4, ADR-084).

    Returns ``(entry, adapter, catalog)`` — the same contract as the GitHub,
    Grafana and Kubernetes builders: the entry is returned at
    REGISTERED/UNVERIFIED/UNAVAILABLE, construction contacts nothing, and the
    same deliberate acts stand between this and real work.

    The adapter is the generic ``ConnectorAdapter``: catalog + translator +
    normalizer + channel. No Prometheus client, no second HTTP client, no
    connector-owned credential. ``base_url`` and ``namespace`` are both
    deployment configuration with deliberately no default — there is no universal
    Prometheus and no universal namespace to observe.
    """
    from backend.contracts.connector import IsolationTier
    from backend.contexts.execution import (
        WorkerEntry,
        WorkerInterface,
        WorkerScope,
    )
    from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
        PROMETHEUS_PROVIDER,
        PROMETHEUS_PROVIDER_ID,
        PrometheusResponseTranslator,
        PrometheusVectorNormalizer,
        build_prometheus_channel,
        prometheus_read_catalog,
    )

    catalog = prometheus_read_catalog(namespace=namespace)
    channel = build_prometheus_channel(
        broker=transport_broker,
        policy=connection_policy,
        environment=environment,
        base_url=base_url,
    )
    implementation = WorkerImplementation(
        worker_id=worker_id,
        worker_kind=WorkerKind.CONNECTOR,
        interface=WorkerInterface.CONNECTOR,
        implementation=(
            "backend.contexts.execution.infrastructure.adapters.connector."
            "ConnectorAdapter+connectors.prometheus"
        ),
        implementation_version="1.0.0",
        isolation=isolation or IsolationTier.CONTAINED,
        scope=WorkerScope.PLATFORM,
        supported_environments=frozenset({environment}),
        supported_effects=frozenset(
            {spec.effect_semantics for spec in _catalog_specs(catalog)}
        ),
        supported_providers=frozenset({PROMETHEUS_PROVIDER_ID}),
        supported_operations=frozenset(catalog.operations),
        # Prometheus reads no idempotency key, and a read needs none. Declared
        # honestly, exactly as for every other provider.
        supports_provider_idempotency=False,
    )
    adapter = build_adapter(
        implementation,
        provider=PROMETHEUS_PROVIDER,
        catalog=catalog,
        channel=channel,
        translator=PrometheusResponseTranslator(),
        normalizer=PrometheusVectorNormalizer(),
        preflight=preflight,
        metrics=metrics,
    )
    return WorkerEntry(implementation=implementation), adapter, catalog


def _catalog_specs(catalog: Any) -> tuple:
    return tuple(catalog.require(name) for name in catalog.operations)


def build_worker_runtime(
    *,
    resolution_service: Any,
    worker_kind_resolver: Any,
    directory: Optional[InMemoryWorkerDirectory] = None,
    input_validator: Optional[Any] = None,
    observer: Optional[Any] = None,
) -> WorkerRuntime:
    """Assemble the runtime. Refuses everything until workers exist.

    With an empty directory every invocation refuses at selection. With a
    registered-but-not-enabled worker it refuses at compatibility. With no input
    validator it refuses any request carrying a payload. None of those is a gap
    waiting to be filled with a default.
    """
    return WorkerRuntime(
        binding_validator=BindingValidatorAdapter(resolution_service),
        worker_kinds=WorkerKindAdapter(worker_kind_resolver),
        directory=directory if directory is not None else build_worker_directory(),
        input_validator=input_validator,
        observer=observer,
    )


# ----------------------------------------------------------------------
# Phase 3.3.3 — the gateway's ports, answered by the real services
# ----------------------------------------------------------------------


class AuthorizationAuthorityAdapter:
    """Execution's ``CapabilityAuthority``, answered by Connectivity.

    Re-asks ``CapabilityAuthorizationService.authorize`` at invocation time. Not
    a cache read and not a second policy engine: the same service, the same
    policy, asked again at the moment it matters. A binding being valid says the
    *target* is still the one chosen; it does not say the principal may still
    invoke it, and between binding and invocation a grant can be withdrawn.

    Everything crosses as primitives. Execution never sees an
    ``AuthorizationDecision``; it receives what the decision said.
    """

    def __init__(
        self,
        authorization_service: Any,
        *,
        delegation: Optional[Any] = None,
    ) -> None:
        self._authorization = authorization_service
        self._delegation = delegation
        """The ``DelegationAuthority`` port, and **normally absent**.

        Phase 4.4 finding, recorded rather than engineered around:
        ``AuthorizationRequest`` has no delegation concept. Connectivity answers
        "may this principal invoke this capability" and has never been asked
        "may this principal act for another". So there is nothing in an
        ``AuthorizationDecision`` to project into ``delegated_principal_id``.

        Inventing one here would be building a second authorization engine at
        the composition root, which is the thing this phase must not do. So the
        seam is explicit and its absence is a refusal: with no delegation
        authority wired, ``delegation_permitted`` stays ``False`` and every
        on-behalf-of invocation is refused by ``_check_delegation``.

        That is the correct fail-closed answer to a capability the platform does
        not yet have, and it is a *stricter* position than before this phase —
        delegation previously travelled unchecked.
        """

    def facts_for(
        self, context: Any, request: InvocationRequest, binding: BoundCapability
    ) -> Optional[AuthorityFacts]:
        from backend.contexts.connectivity import (
            AuthorizationRequest,
            CapabilityOperation,
            CapabilityRef,
        )

        # Parsing the rendered reference happens *here*, at the translation
        # layer, and nowhere else. ADR-036 established that Execution never
        # parses it — it carries the token and hands it back — so reconstituting
        # the structured form is the composition root's job by construction.
        decision = self._authorization.authorize(
            context,
            AuthorizationRequest(
                tenant_id=request.tenant_id,
                principal=request.principal,
                capability_ref=CapabilityRef.parse(binding.capability_ref),
                # The governance verb, taken from the binding. ``request.operation``
                # is the provider operation and is not a member of this enum.
                operation=CapabilityOperation(
                    getattr(binding, "governance_operation", None) or request.operation
                ),
                # The contract the binding was made against. Without it the
                # policy denies with ``digest_missing`` -- so the gateway's
                # re-authorization refused *every* invocation, which is only
                # visible once a real binding reaches a real gateway.
                expected_digest=binding.capability_digest,
                environment=binding.environment,
                execution_id=str(request.execution_id),
                node_id=request.node_id,
            ),
        )
        if decision is None:
            return None
        permitted, delegated_to = self._delegation_facts(context, request, decision)
        return AuthorityFacts(
            effect=decision.effect,
            policy_version=decision.policy_version,
            decision_digest=decision.digest or "",
            capability_digest=decision.capability_digest or "",
            tenant_id=decision.request.tenant_id,
            principal_id=decision.request.principal.principal_id,
            # The governance verb the decision was actually about, read
            # back off the decision rather than off the request -- a fact
            # is what authorization concluded, never what a caller asked.
            governance_operation=decision.request.operation.value,
            # The concrete action, copied from the binding. Copied, not
            # invented: the projection may carry authoritative values and
            # may not manufacture them.
            provider_operation=binding.operation,
            expires_at=decision.expires_at,
            binding_key=decision.binding_key,
            risk=decision.risk,
            side_effect_class=binding.side_effect_class,
            effect_semantics=binding.effect_semantics,
            environment=binding.environment,
            delegation_permitted=permitted,
            delegated_principal_id=delegated_to,
            approval_required=decision.effect is PolicyEffect.REQUIRE_APPROVAL,
            approval_artifact_id=decision.approval_artifact_id,
            obligations=tuple(decision.obligations),
            reasons=decision.reason_codes,
        )

    def _delegation_facts(
        self, context: Any, request: InvocationRequest, decision: Any
    ) -> tuple:
        """``(permitted, delegated_principal_id)``. Fails closed in every branch.

        No port wired, a port that raises, a port that answers with something
        uninterpretable, or a port that names a principal the request did not —
        all of them produce ``(False, None)`` or a mismatch the gateway refuses.
        There is no path here that returns permission by accident.
        """
        if self._delegation is None:
            return False, None
        try:
            answer = self._delegation.delegation_for(context, request)
        except Exception:  # noqa: BLE001 - unverifiable delegation is no delegation
            log.warning("delegation authority failed", exc_info=False)
            return False, None
        if answer is None:
            return False, None
        permitted = bool(getattr(answer, "permitted", False))
        delegated_to = getattr(answer, "delegated_principal_id", None)
        if not permitted or not isinstance(delegated_to, str) or not delegated_to.strip():
            # "Permitted, but for nobody in particular" is an unbound delegation
            # and would authorize acting for anybody.
            return False, None
        return True, delegated_to.strip()


class ExecutionLeaseAdapter:
    """Execution's ``LeaseAuthority``, answered by the execution service.

    Reads only. The gateway may not grant, renew or reclaim a lease — reclaiming
    one would take a node away from a worker that may still be writing to a
    production system, and that decision belongs to recovery with the facts in
    front of it.
    """

    def __init__(self, execution_service: Any) -> None:
        self._executions = execution_service

    def lease_for(
        self, context: Any, execution_id: str, node_id: str
    ) -> Optional[LeaseFacts]:
        from backend.contexts.execution import GetExecution

        execution = self._executions.get(context, GetExecution(execution_id=execution_id))
        for run in getattr(execution, "runs", ()):
            if run.node_id != node_id:
                continue
            lease = getattr(run, "lease", None)
            if lease is None:
                return LeaseFacts(held=False, node_id=node_id)
            attempt = getattr(run, "current_attempt", None)
            return LeaseFacts(
                held=not lease.is_released,
                node_id=node_id,
                worker_id=lease.worker_id,
                attempt_id=str(attempt.attempt_id) if attempt else None,
                expires_at=lease.expires_at,
                node_state=getattr(run, "state", None)
                and getattr(run.state, "value", None),
            )
        return None


class ExecutionResultRecorder:
    """Execution's ``InvocationRecorder``. The aggregate is written here, not there.

    The gateway holds no repository and mutates no run. It decides admission and
    reports what happened; recording is the execution service's, under the lease
    check that has always governed it.
    """

    def __init__(self, execution_service: Any) -> None:
        self._executions = execution_service

    def record(self, context: Any, request: InvocationRequest, result: Any) -> Any:
        from backend.contexts.execution import RecordFailure, RecordSuccess
        from backend.contexts.execution.domain.failure import FailureClass
        from backend.contexts.execution.application.worker_runtime import WorkerRuntime

        published = WorkerRuntime.to_execution_result(
            _as_worker_request(request), result
        )
        # ``worker_id`` here is the **lease holder**, not the implementation.
        #
        # ``NodeRun.concluded`` calls ``assert_held_by(worker_id)`` -- the
        # authoritative, fenced lease check ADR-036 §16 points at, the one that
        # can actually refuse a write. It asks "does the participant recording
        # this result hold the lease", and the holder is the dispatcher. Passing
        # the selected worker here would fail that check for every result.
        holder = request.lease_holder_id or request.worker_id
        if result.succeeded:
            return self._executions.record_success(
                context,
                RecordSuccess(
                    execution_id=str(request.execution_id),
                    node_id=request.node_id,
                    worker_id=holder,
                    execution_key=published.execution_key,
                    detail=dict(published.detail or {}),
                ),
            )
        failure = result.failure
        return self._executions.record_failure(
            context,
            RecordFailure(
                execution_id=str(request.execution_id),
                node_id=request.node_id,
                worker_id=holder,
                reason=(failure.reason if failure else "unknown outcome"),
                execution_key=published.execution_key,
                # Restored from the worker's classification, never re-derived
                # here: this layer cannot tell a timeout from a refusal, and
                # guessing would put a wrong class into the retry rules.
                failure_class=(
                    failure.failure_class.value
                    if failure is not None and hasattr(failure, "failure_class")
                    else FailureClass.UNKNOWN_OUTCOME.value
                ),
                failure_source=(
                    getattr(failure, "source", None) or "worker"
                ),
            ),
        )


def _as_worker_request(request: InvocationRequest) -> Any:
    """A minimal shim so the published projection can read the execution key.

    ``to_execution_result`` needs only ``execution_key`` and ``node_id``. Building
    a whole ``WorkerExecutionRequest`` here would require the binding again, and
    passing the binding to a *recorder* is how a recorder ends up in a position
    to make an authorization-shaped decision.
    """

    class _Shim:
        execution_key = request.execution_key
        node_id = request.node_id

    return _Shim()


class DelegationGrant:
    """What a delegation authority answers with. Two fields, both required.

    A tiny type rather than a tuple so that "permitted" and "for whom" cannot be
    supplied independently by accident — the pair is the answer, and half of it
    is not a weaker answer, it is none.
    """

    __slots__ = ("permitted", "delegated_principal_id")

    def __init__(self, *, permitted: bool, delegated_principal_id: Optional[str]) -> None:
        self.permitted = bool(permitted)
        self.delegated_principal_id = delegated_principal_id

    def __repr__(self) -> str:
        return (
            f"<DelegationGrant permitted={self.permitted} "
            f"for={self.delegated_principal_id!r}>"
        )


def build_invocation_gateway(
    *,
    worker_runtime: WorkerRuntime,
    authorization_service: Any,
    execution_service: Any,
    input_validator: Optional[Any] = None,
    credentials: Optional[Any] = None,
    rate_limiter: Optional[Any] = None,
    delegation: Optional[Any] = None,
    audit: Optional[Any] = None,
    observer: Optional[Any] = None,
    clock: Optional[Any] = None,
) -> SecureCapabilityInvocationGateway:
    """Assemble the one authoritative invocation path.

    Every authority port is wired to the service that actually owns that
    authority. The two seams that stay empty — credentials and the rate limiter —
    stay empty deliberately: no credential system and no limiter is built in this
    phase, and the gateway's behaviour with each absent is stated rather than
    assumed (a missing credential provider is not consulted; a missing limiter is
    not a rule; an *unavailable* one refuses).
    """
    return SecureCapabilityInvocationGateway(
        worker_runtime=worker_runtime,
        authority=AuthorizationAuthorityAdapter(
            authorization_service, delegation=delegation
        ),
        leases=ExecutionLeaseAdapter(execution_service),
        recorder=ExecutionResultRecorder(execution_service),
        input_validator=input_validator,
        credentials=credentials,
        rate_limiter=rate_limiter,
        outbox=getattr(execution_service, "outbox", None),
        audit=audit,
        observer=observer,
        clock=clock,
    )


# ----------------------------------------------------------------------
# Phase 3.3.4 — the production lifecycle
# ----------------------------------------------------------------------


class StoredBindingSource:
    """The dispatcher's ``BindingSource``, answered by Connectivity.

    Finds the binding Connectivity already made **for this execution and node**
    and projects it. It never resolves and never binds: binding at dispatch time
    would let the dispatcher choose a provider, which is exactly the authority
    the dispatcher exists not to have.

    A missing binding returns ``None`` and the node is refused. There is no
    branch that makes one.
    """

    def __init__(
        self,
        resolution_service: Any,
        *,
        environment: Optional[ExecutionEnvironment] = None,
        interface: Optional[str] = None,
    ) -> None:
        self._resolution = resolution_service
        self._environment = environment
        self._interface = interface

    def binding_for(
        self, context: Any, execution_id: str, node_id: str
    ) -> Optional[BoundCapability]:
        found = self._resolution._bindings.for_execution(  # noqa: SLF001
            context, execution_id
        )
        for binding in found or ():
            if (binding.node_id or None) != node_id:
                continue
            try:
                return project_binding(
                    binding,
                    environment=self._environment,
                    interface=self._interface,
                )
            except ValueError:
                # Unsealed or effect-less. Refused rather than projected with a
                # gap that the gateway would then have to guess about.
                log.warning(
                    "binding %s for node %s could not be projected",
                    binding.binding_id,
                    node_id,
                )
                return None
        return None


class SelectingRequestFactory:
    """Builds the ADR-038 request, selecting the worker through the 3.3.2 fabric.

    **This is the authoritative worker-selection boundary**, and therefore the
    emission point for ``WorkerSelected`` (ADR-037 left it with none). A selection
    made anywhere else would not be the one the gateway re-checks, so an event
    emitted anywhere else would name a worker that never ran.
    """

    def __init__(
        self,
        worker_runtime: WorkerRuntime,
        *,
        outbox: Optional[Any] = None,
    ) -> None:
        self._workers = worker_runtime
        self._outbox = outbox

    def build(
        self,
        context: Any,
        candidate: Any,
        binding: BoundCapability,
        *,
        attempt_id: str,
        deadline_at: Optional[Any],
        lease_holder: Optional[str] = None,
    ) -> Optional[InvocationRequest]:
        from backend.contexts.execution import (
            AttemptId,
            ExecutionId,
            WorkerSelected,
            WorkerInvocationRefused,
        )
        from backend.platform.events import EventMetadata

        try:
            selection = self._workers.select(context, binding)
        except WorkerInvocationRefused:
            # No eligible worker. The node is refused, never bound to a
            # substitute -- there is no fallback anywhere in this fabric.
            return None

        request = InvocationRequest(
            execution_id=ExecutionId(candidate.execution_id),
            attempt_id=AttemptId(attempt_id),
            attempt_number=candidate.attempt_number,
            node_id=candidate.node_id,
            tenant_id=candidate.tenant_id,
            principal=context.identity.principal,
            capability_ref=binding.capability_ref,
            capability_digest=binding.capability_digest,
            operation=binding.operation,
            governance_operation=binding.governance_operation,
            environment=selection.environment,
            binding_id=binding.binding_id,
            binding_digest=binding.binding_digest,
            worker_selection_id=selection.selection_id,
            worker_id=selection.worker_id,
            worker_digest=selection.worker_digest,
            # The node's declared input. Unvalidated at this point and
            # deliberately so: the gateway validates it against the provider
            # catalog and only then digests the *validated* form, so the action
            # digest can never cover input nobody checked.
            payload=candidate.input,
            # Copied from the dispatcher, which wrote the same identity
            # into the aggregate when it took the lease.
            lease_holder_id=lease_holder,
            correlation_id=context.correlation.correlation_id,
            trace_id=context.trace.trace_id,
            deadline_at=deadline_at,
        )

        if self._outbox is not None:
            event = WorkerSelected(
                metadata=EventMetadata.create(
                    aggregate_id=selection.worker_id,
                    aggregate_type="execution_worker",
                    scope=context.scope,
                    correlation_id=request.correlation_id,
                ),
                worker_id=selection.worker_id,
                worker_kind=selection.worker_kind.value,
                worker_version=selection.worker_version,
                worker_digest=selection.worker_digest,
                scope="platform",
                selection_id=selection.selection_id,
                selection_digest=selection.digest or "",
                policy_version=selection.policy_version,
                binding_id=selection.binding_id,
                binding_digest=selection.binding_digest,
                capability_ref=selection.capability_ref,
                capability_digest=selection.capability_digest,
                provider=selection.provider,
                operation=selection.operation,
                environment=selection.environment.value,
                interface=selection.interface.value,
                execution_id=selection.execution_id or candidate.execution_id,
                node_id=selection.node_id or candidate.node_id,
                reasons=tuple(selection.reasons),
            )
            try:
                self._outbox.record(context, candidate.execution_id, [event])
            except Exception:  # noqa: BLE001 - publication is not a decision
                log.error("recording WorkerSelected failed", exc_info=True)

        return request


def build_execution_lifecycle(
    *,
    execution_service: Any,
    gateway: SecureCapabilityInvocationGateway,
    resolution_service: Any,
    worker_runtime: WorkerRuntime,
    environment: Optional[ExecutionEnvironment] = None,
    interface: Optional[str] = None,
    queue: Optional[Any] = None,
    metrics: Optional[Any] = None,
    observer: Optional[Any] = None,
    clock: Optional[Any] = None,
) -> tuple:
    """Assemble the dispatcher and the recovery coordinator.

    Returns ``(dispatcher, recovery)``. The scheduler is left to the caller to
    construct and own, because *when* cycles run is a deployment decision and
    binding it here would make the lifecycle depend on this process having a
    thread.
    """
    outbox = getattr(execution_service, "outbox", None)
    dispatcher = ExecutionDispatcher(
        executions=execution_service,
        gateway=gateway,
        bindings=StoredBindingSource(
            resolution_service, environment=environment, interface=interface
        ),
        requests=SelectingRequestFactory(worker_runtime, outbox=outbox),
        queue=queue,
        outbox=outbox,
        observer=observer,
        metrics=metrics,
        clock=clock,
    )
    recovery = RecoveryCoordinator(
        executions=execution_service,
        outbox=outbox,
        observer=observer,
        metrics=metrics,
        clock=clock,
    )
    return dispatcher, recovery


class GovernedCapabilityReader:
    """Runs one declared READ operation through the whole governed path.

    Lives here rather than beside ``GovernedReadObserver`` because running a
    governed capability means touching BOTH contexts — Connectivity authorizes
    and resolves, Execution starts and dispatches — and this is one of the five
    named modules permitted to import two contexts. The observer, which needs
    neither, stays out of the composition root.

    Every gate runs, in the order it exists in: authorize → start → resolve and
    seal the binding → the scheduler dispatches → the adapter re-reads the
    directory → the channel dials once → the answer is classified, normalized and
    shape-checked. This class adds none of that and skips none of it; it is the
    caller that a long-running observer needs and that until now only a harness
    had.

    It is deliberately **not** a second executor. It starts an execution and
    ticks the existing scheduler. It cannot dispatch, cannot lease, cannot record
    an outcome, and cannot conclude anything the scheduler did not conclude.
    """

    def __init__(
        self,
        *,
        runtime: Any,
        capability_definitions: Mapping[str, Any],
        principal: Any,
        environment: Any = None,
        max_ticks: int = 450,
        tick_seconds: float = 0.1,
    ) -> None:
        if not capability_definitions:
            raise ContractViolation(
                "a governed reader needs the capability definitions it may run; "
                "with none it could only refuse, and a reader that refuses "
                "everything hides a wiring mistake behind a plausible answer"
            )
        self._runtime = runtime
        self._definitions = dict(capability_definitions)
        self._principal = principal
        self._environment = environment
        self._max_ticks = max_ticks
        self._tick_seconds = tick_seconds

    def read(
        self,
        context: Any,
        *,
        operation: str,
        payload: Mapping[str, Any],
        node_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> GovernedReadOutcome:
        """Perform one governed READ. Refuses anything that mutates.

        The assertion is not ceremony. This object is handed to the investigator
        and to the evidence-acquisition port, and the one thing neither may ever
        do is change the world through a door labelled "read"."""
        definition = self._definitions.get(operation)
        if definition is not None and definition.contract.side_effect_class.mutates:
            raise ContractViolation(
                f"{operation!r} is a {definition.contract.side_effect_class.value} "
                "and cannot be performed through the read path; a mutation goes "
                "through GovernedCapabilityWriter, which requires an approval")
        return self._perform(context, operation=operation, payload=payload,
                             node_id=node_id, workflow_id=workflow_id)

    def _perform(
        self,
        context: Any,
        *,
        operation: str,
        payload: Mapping[str, Any],
        node_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        approval_artifact_id: Optional[str] = None,
    ) -> GovernedReadOutcome:
        """The one governed chain. Both doors above lead here and nowhere else."""
        from backend.contexts.connectivity.domain.authorization import (
            AuthorizationRequest, CapabilityOperation,
        )
        from backend.contexts.connectivity.domain.contract import CapabilityEnvironment
        from backend.contexts.connectivity.domain.identifiers import (
            CapabilityId, CapabilityVersion,
        )
        from backend.contexts.connectivity.domain.resolution import (
            ResolutionRequest, VersionSelection,
        )
        from backend.contexts.execution.application.commands import (
            RegisterWorker, StartExecution,
        )
        from backend.api.governed_read_observer import GovernedReadOutcome

        definition = self._definitions.get(operation)
        if definition is None:
            raise ContractViolation(
                f"{operation!r} is not a capability this reader was given; an "
                "operation nobody declared is not one this may run"
            )
        node = node_id or operation.replace(".", "-")
        environment = self._environment or CapabilityEnvironment.DEVELOPMENT
        started_at = time.monotonic()

        decision = self._runtime.authorization.authorize(context, AuthorizationRequest(
            tenant_id=context.tenant_id, principal=self._principal,
            capability_ref=definition.reference,
            operation=CapabilityOperation.INVOKE,
            expected_digest=definition.digest, environment=environment,
            # Carried, never invented. A capability whose policy says
            # REQUIRE_APPROVAL is allowed only when the approval presented here
            # is valid for this tenant, this operation and this digest.
            approval_artifact_id=approval_artifact_id,
        ))
        if not getattr(decision, "allowed", False):
            return GovernedReadOutcome(
                operation=operation, execution_id="", node_state=None,
                succeeded=False, evidence={},
                failure_reason=f"authorization refused: "
                               f"{getattr(decision, 'reason', None)}",
                duration_seconds=time.monotonic() - started_at,
            )

        started = self._runtime.executions.start(context, StartExecution(
            workflow_id=workflow_id or f"observe-{operation}",
            workflow_digest=f"observe-{operation}-digest",
            mission_id="world-observation",
            nodes=(
                {"node_id": node, "worker_kind": "connector",
                 "side_effect": definition.contract.side_effect_class.value,
                 "max_attempts": 1, "input": dict(payload)},
            ),
            requested_by="world-observer",
        ))
        execution_id = str(started.execution.execution_id)
        self._runtime.executions.register_worker(RegisterWorker(
            worker_id=f"dispatcher:{execution_id}", kinds=("connector",),
            lease_seconds=300))

        outcome = self._runtime.resolution.resolve(context, ResolutionRequest(
            tenant_id=context.tenant_id, principal=self._principal,
            capability_id=CapabilityId.parse(str(definition.capability_id)),
            operation=CapabilityOperation.INVOKE, authorization=decision,
            version=CapabilityVersion(1), version_selection=VersionSelection.EXACT,
            environment=environment, execution_id=execution_id, node_id=node,
        ))
        if not outcome.resolved:
            return GovernedReadOutcome(
                operation=operation, execution_id=execution_id, node_state=None,
                succeeded=False, evidence={},
                failure_reason=f"resolution refused: {outcome.result}",
                duration_seconds=time.monotonic() - started_at,
            )

        state = self._drive(context, execution_id, node)
        evidence, status, reason = self._aggregate(context, execution_id, node)
        return GovernedReadOutcome(
            operation=operation, execution_id=execution_id, node_state=state,
            succeeded=state == "succeeded", evidence=evidence, status=status,
            failure_reason=reason, duration_seconds=time.monotonic() - started_at,
        )

    # ------------------------------------------------------------------

    def _drive(self, context: Any, execution_id: str, node_id: str) -> Optional[str]:
        """Tick the existing scheduler until the node is terminal.

        Not a second scheduler: this calls ``tick`` on the one that already
        exists, which is the same thing the runtime's own background loop does.
        A process that is not the scheduler leader ticks and does nothing, which
        is the correct behaviour and is why the budget outlives one lease."""
        self._runtime.scheduler.track(execution_id)
        terminal = {"succeeded", "failed", "unknown", "skipped"}
        for _ in range(self._max_ticks):
            self._runtime.scheduler.tick(context)
            stream = self._runtime.executions.stream_state(context, execution_id)
            states = {n["node_id"]: n["state"] for n in stream.get("nodes", ())}
            if states.get(node_id) in terminal:
                return states.get(node_id)
            time.sleep(self._tick_seconds)
        return None

    def _aggregate(
        self, context: Any, execution_id: str, node_id: str
    ) -> tuple[dict, Optional[int], Optional[str]]:
        """Read what actually traversed the pipeline, from the aggregate.

        The aggregate, not a reconstruction: what is recorded is what happened,
        and rebuilding it from the request would describe what we intended.
        """
        from backend.contexts.execution.application.commands import GetExecution

        execution = self._runtime.executions.get(
            context, GetExecution(execution_id=execution_id))
        run = execution.run_for(node_id)
        if run is None or not run.attempts:
            return {}, None, "the node recorded no attempt"
        attempt = run.attempts[-1]
        detail = dict(attempt.result.detail) if attempt.result is not None else {}
        evidence = detail.get("provider_evidence")
        status = detail.get("provider_status")
        return (
            dict(evidence) if isinstance(evidence, dict) else {},
            status if isinstance(status, int) else None,
            getattr(attempt, "failure_reason", None),
        )


class GovernedCapabilityWriter(GovernedCapabilityReader):
    """The typed door for a governed MUTATION — Phase 9.6 (ADR-086).

    It is a subclass and not a second implementation on purpose: there is exactly
    one governed chain, and a write that took a different route to the provider
    would be a second execution authority however carefully it was written. What
    this adds is a door that knows what it is for.

    Two things it asserts that the read door does not:

    * the operation must actually mutate — a read performed through the write
      path would carry an approval that describes an action nobody took;
    * an approval artifact id is carried through to authorization, where the
      existing approval facts decide whether it covers this tenant, this
      operation and this exact input digest. This class does not decide that and
      holds no approval state.
    """

    def write(
        self,
        context: Any,
        *,
        operation: str,
        payload: Mapping[str, Any],
        approval_artifact_id: Optional[str] = None,
        node_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> Any:
        definition = self._definitions.get(operation)
        if definition is None:
            raise ContractViolation(
                f"{operation!r} is not a capability this writer was given")
        if not definition.contract.side_effect_class.mutates:
            raise ContractViolation(
                f"{operation!r} is a read; performing it through the write path "
                "would attach an approval to an action that changes nothing")
        return self._perform(
            context, operation=operation, payload=payload, node_id=node_id,
            workflow_id=workflow_id or f"remediate-{operation}",
            approval_artifact_id=approval_artifact_id)
