"""The production connectivity path, assembled in one place and traceable.

What this module is
---------------------
The composition root for external side effects. It is the **only** place that
wires a credential adapter to the credential broker, a transport adapter to the
transport broker, a provider adapter to the worker directory, and all three to
the invocation gateway. Nothing in a bounded context constructs any of them, and
there is no global mutable singleton holding a security authority.

What it is **not**
--------------------
It is not a gateway. ``SecureCapabilityInvocationGateway`` (ADR-038) remains the
authoritative gate, and ``ProductionConnectivity`` is a *handle on an assembled
graph*, not a second authorization path. Its ``invoke`` is three lines and every
one of them delegates — see the method, which exists so callers have something to
hold rather than to add a decision.

There is deliberately no ``ConnectivityGateway``, no ``ProviderGateway`` and no
``ConnectorGateway`` type. A second thing named "gateway" is how a second place
to authorize appears.

The whole path, in order
--------------------------
    Mission → Intent → Planner → Workflow → Approved Workflow
      → Execution → CapabilityBinding → AuthorizationDecision
      → WorkerSelection → InvocationRequest
      → [ identity · tenant · binding · authorization · delegation · approval
          · worker · input · action digest · obligations · freshness · lease
          · rate · credential ]                       ← SecureCapabilityInvocationGateway
      → CredentialProvider  → CredentialBroker → VaultCredentialAdapter
      → WorkerRuntime (TOCTOU re-read) → AdapterSeam (TOCTOU re-read)
      → ProviderChannel → TransportBroker → HttpxTransportAdapter
      → provider
      → ProviderOutcome → WorkerExecutionResult → Execution → Audit → Replay

Everything left of ``SecureCapabilityInvocationGateway`` was built in Phase 3.
Everything right of it was built in Phases 4.1–4.3. This module is the wiring,
and the wiring is the deliverable: the chain is only authoritative if there is
exactly one of it.

Fail closed, at construction
------------------------------
``ProductionConnectivityConfig.for_environment`` refuses to produce a production
configuration that is missing a security dependency. A deployment that has not
configured Vault does not get a platform that quietly issues no credentials — it
gets a platform that will not start, because "credential acquisition silently
refuses" and "credentials are not configured" look identical at runtime and only
one of them is a bug somebody will notice.

Development is not production wearing a smaller hat
-----------------------------------------------------
``build_development_connectivity`` is a separately-named function, not a flag.
It refuses ``PRODUCTION`` and it wires the scripted transport and the scripted
credential provider — both of which refuse production themselves, three times
over. A flag is something a configuration file sets by accident; a differently
named function is something a person has to type.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

from backend.contracts.credential import CredentialRef, CredentialType
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.transport import TransportKind

__all__ = [
    "ProductionConnectivityConfig",
    "ProductionConnectivity",
    "ConnectivityMisconfigured",
    "build_production_connectivity",
    "build_development_connectivity",
    "PRODUCTION_SECURITY_REQUIREMENTS",
    "CONNECTIVITY_METRICS",
]

log = logging.getLogger(__name__)

#: Environment variables that must be present for a production build. Named
#: here so the failure is "VAULT_ADDR is not set" rather than "credential
#: acquisition refused", which is the same words a working platform uses when a
#: tenant simply has no credential stored.
PRODUCTION_SECURITY_REQUIREMENTS = ("VAULT_ADDR", "VAULT_TOKEN")

#: The connectivity-level metric names, on top of the fabric's own
#: (``CREDENTIAL_METRICS``, ``TRANSPORT_METRICS``, ``ADAPTER_METRICS``). No new
#: telemetry framework: these are counted through the same metrics port
#: everything else uses.
CONNECTIVITY_METRICS = (
    "connectivity.attempt",
    "connectivity.success",
    "connectivity.failure",
    "connectivity.refused",
    "connectivity.unknown_outcome",
)

#: The one environment variable this module reads for a secret, and the reason
#: it is allowed to.
#:
#: ADR-040 §5 forbids reading *provider* credentials from the process
#: environment: they are per-tenant, and one process variable cannot be. This is
#: different in kind — it is CortexPrime's own credential to its secret store,
#: the bootstrap root of trust, and it has to enter the process from somewhere
#: that is not the secret store it unlocks. It is read once, at construction,
#: wrapped immediately in ``CredentialMaterial`` (which cannot be logged,
#: serialised or compared), and never read again.
_VAULT_TOKEN_ENV = "VAULT_TOKEN"
_VAULT_ADDR_ENV = "VAULT_ADDR"


class ConnectivityMisconfigured(RuntimeError):
    """A production security dependency is missing. Nothing was assembled."""


@dataclass(frozen=True)
class ProductionConnectivityConfig:
    """Every configuration value the production path needs, stated explicitly.

    Split three ways on purpose, because the three have different review
    requirements and mixing them is how a security value ends up changed by
    somebody tuning a timeout:

    ``security-critical``  environment, vault address, TLS trust, address policy
    ``provider``           provider base URLs
    ``operational``        timeouts, budgets, user agent

    **No secret is a field here.** The Vault token is read from the environment
    into ``CredentialMaterial`` at build time and never lands on this object, so
    a configuration that somebody logs, serialises or puts in a bug report
    carries nothing to leak.
    """

    # -- security-critical ----------------------------------------------
    environment: ExecutionEnvironment
    vault_address: str
    vault_mount: str = "secret"
    vault_path_prefix: str = "cortexprime/providers"
    ca_bundle_path: Optional[str] = None

    allow_private_destinations: bool = False
    """Off for production and refused there by ``build_connection_policy``. An
    in-cluster production provider needs an explicit reviewed policy naming the
    address classes it reaches, not a boolean."""

    allow_plaintext: bool = False
    trust_environment_proxy: bool = False
    """Off. httpx honours ``HTTP_PROXY``/``HTTPS_PROXY``/``ALL_PROXY`` by
    default, so a deployment variable would silently become the real destination
    of every outbound request — an SSRF bypass no endpoint check catches."""

    proxy_url: Optional[str] = None
    follow_redirects: bool = False
    max_redirect_hops: int = 0

    # -- provider ---------------------------------------------------------
    github_base_url: str = "https://api.github.com"
    mcp_servers: Mapping[str, str] = field(default_factory=dict)
    """``server_id -> base URL``. Deployment configuration, never request input.
    Empty means no MCP server is reachable, which is the correct default."""

    # -- operational --------------------------------------------------------
    user_agent: str = "CortexPrime/1.0"
    max_concurrent_connections: int = 8

    def __post_init__(self) -> None:
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ConnectivityMisconfigured("environment must be an ExecutionEnvironment")
        if not isinstance(self.vault_address, str) or not self.vault_address.strip():
            raise ConnectivityMisconfigured(
                "a credential source address is required; a platform with no "
                "secret store should refuse to start rather than run with every "
                "credential acquisition failing for a reason nobody can see"
            )
        if self.environment is ExecutionEnvironment.PRODUCTION:
            if self.allow_plaintext:
                raise ConnectivityMisconfigured(
                    "plaintext is not permitted in production; it exposes both "
                    "the credential and the payload"
                )
            if self.allow_private_destinations:
                raise ConnectivityMisconfigured(
                    "private destinations cannot be enabled for production "
                    "through this configuration; an in-cluster production "
                    "provider needs an explicit reviewed policy"
                )
            if self.trust_environment_proxy:
                raise ConnectivityMisconfigured(
                    "environment proxy inheritance is not permitted in "
                    "production; a variable set anywhere in the deployment would "
                    "become the real destination of every request"
                )
            if not self.vault_address.lower().startswith("https://"):
                raise ConnectivityMisconfigured(
                    "a production secret store must be reached over https; "
                    "plaintext exposes the token and every secret it returns"
                )
            if not self.github_base_url.lower().startswith("https://"):
                raise ConnectivityMisconfigured(
                    "a production provider endpoint must be https"
                )

    # ------------------------------------------------------------------

    @classmethod
    def for_environment(
        cls, environment: ExecutionEnvironment, **overrides: Any
    ) -> "ProductionConnectivityConfig":
        """Build from the process environment, refusing an incomplete production.

        Deliberately loud. A production deployment missing ``VAULT_ADDR`` gets an
        exception naming the variable; the alternative is a platform that starts
        cleanly and refuses every credential with ``credential_no_provider``,
        which reads exactly like "this tenant has no credential configured".
        """
        if environment is ExecutionEnvironment.PRODUCTION:
            missing = [
                name
                for name in PRODUCTION_SECURITY_REQUIREMENTS
                if not os.environ.get(name, "").strip()
            ]
            if missing:
                raise ConnectivityMisconfigured(
                    "production connectivity requires "
                    f"{', '.join(missing)}; refusing to assemble a connectivity "
                    "path whose security dependencies are absent"
                )
        address = overrides.pop(
            "vault_address", os.environ.get(_VAULT_ADDR_ENV, "").strip()
        )
        if not address and environment is not ExecutionEnvironment.PRODUCTION:
            # Non-production may point at a local Vault. Stated rather than
            # defaulted silently, and it is still refused for production above.
            address = "http://localhost:8200"
        return cls(environment=environment, vault_address=address, **overrides)

    def to_dict(self) -> dict:
        """Safe to log. There is no secret on this object to omit."""
        return {
            "environment": self.environment.value,
            "vault_address": self.vault_address,
            "vault_mount": self.vault_mount,
            "ca_bundle_configured": self.ca_bundle_path is not None,
            "allow_private_destinations": self.allow_private_destinations,
            "allow_plaintext": self.allow_plaintext,
            "trust_environment_proxy": self.trust_environment_proxy,
            "proxy_configured": self.proxy_url is not None,
            "follow_redirects": self.follow_redirects,
            "github_base_url": self.github_base_url,
            "mcp_servers": sorted(self.mcp_servers),
            "max_concurrent_connections": self.max_concurrent_connections,
        }


class ProductionConnectivity:
    """A handle on the assembled graph. **Not a gateway, and not a decision.**

    Holds the components so a caller has one object to keep, and delegates every
    security question to the thing that owns it. ``invoke`` exists because
    callers need somewhere to call; it adds no check, no branch and no fallback,
    and it could be deleted without changing what is enforced.
    """

    __slots__ = (
        "config",
        "gateway",
        "worker_runtime",
        "directory",
        "credential_broker",
        "transport_broker",
        "input_validator",
        "adapters",
        "catalogs",
        "_metrics",
    )

    def __init__(
        self,
        *,
        config: ProductionConnectivityConfig,
        gateway: Any,
        worker_runtime: Any,
        directory: Any,
        credential_broker: Any,
        transport_broker: Any,
        input_validator: Any,
        adapters: Mapping[str, Any],
        catalogs: Mapping[str, Any],
        metrics: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.gateway = gateway
        self.worker_runtime = worker_runtime
        self.directory = directory
        self.credential_broker = credential_broker
        self.transport_broker = transport_broker
        self.input_validator = input_validator
        self.adapters = dict(adapters)
        self.catalogs = dict(catalogs)
        self._metrics = metrics

    # ------------------------------------------------------------------

    def invoke(self, context: Any, request: Any, binding: Any) -> Any:
        """Delegate to the invocation gateway. **Nothing else happens here.**

        Deliberately three statements. Every check that governs an external side
        effect lives inside ``SecureCapabilityInvocationGateway``; anything added
        here would be a second place the answer could differ, and a second place
        somebody would eventually relax.
        """
        self._count("connectivity.attempt", request)
        try:
            outcome = self.gateway.invoke(context, request, binding)
        except Exception:
            # A refusal is a refusal. It is counted and re-raised untouched --
            # translating it here would put a decision in a facade.
            self._count("connectivity.refused", request)
            raise
        self._count(
            "connectivity.success"
            if outcome.succeeded
            else (
                "connectivity.unknown_outcome"
                if not outcome.outcome_is_known
                else "connectivity.failure"
            ),
            request,
        )
        return outcome

    # ------------------------------------------------------------------

    def trace(self) -> dict:
        """What is actually wired, for an operator and for an architecture test.

        Answers "can this deployment reach a provider, and through what" without
        making a call. Every value is a name or a boolean; there is no field here
        that could hold a secret, and no method that contacts anybody.
        """
        return {
            "config": self.config.to_dict(),
            "entry_point": type(self.gateway).__name__,
            "credential_providers": list(self.credential_broker.providers),
            "transport_kinds": list(self.transport_broker.kinds),
            "adapters": {
                name: adapter.describe()
                for name, adapter in self.adapters.items()
                if hasattr(adapter, "describe")
            },
            "validated_providers": list(self.input_validator.providers),
            "catalogs": {
                name: catalog.to_dict() for name, catalog in self.catalogs.items()
            },
            "registered_workers": sorted(self.adapters),
        }

    def readiness(self) -> dict:
        """Four separate answers, never collapsed into one.

        A deployment can be architecturally sound and operationally unready, and
        saying "ready" would be true of the first and false of the second. The
        one that is deliberately never ``True`` in Phase 4 is durability.
        """
        has_credentials = bool(self.credential_broker.providers)
        has_transport = bool(self.transport_broker.kinds)
        return {
            "architecturally_ready": True,
            "operationally_ready": has_credentials and has_transport,
            "provider_ready": bool(self.adapters) and has_credentials and has_transport,
            "durability_ready": False,
            "durability_note": (
                "Execution state, the outbox, leases and the worker directory "
                "are in-process. Phase 4 does not solve durable distributed "
                "state and claims no crash safety, no exactly-once, no "
                "cross-process leases and no zero-loss outbox"
            ),
            "missing": [
                name
                for name, present in (
                    ("credential_adapter", has_credentials),
                    ("transport_adapter", has_transport),
                    ("provider_adapter", bool(self.adapters)),
                )
                if not present
            ],
        }

    def _count(self, name: str, request: Any) -> None:
        if self._metrics is None or name not in CONNECTIVITY_METRICS:
            return
        try:
            self._metrics.increment(
                name,
                labels={
                    "tenant": getattr(request, "tenant_id", "unknown"),
                    "environment": self.config.environment.value,
                },
            )
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("connectivity metric failed", exc_info=False)


# ----------------------------------------------------------------------
# Assembly
# ----------------------------------------------------------------------


def build_production_connectivity(
    *,
    config: ProductionConnectivityConfig,
    resolution_service: Any,
    authorization_service: Any,
    execution_service: Any,
    worker_kind_resolver: Any,
    context_factory: Optional[Any] = None,
    delegation: Optional[Any] = None,
    rate_limiter: Optional[Any] = None,
    audit: Optional[Any] = None,
    observer: Optional[Any] = None,
    metrics: Optional[Any] = None,
    clock: Optional[Any] = None,
    enable_github: bool = True,
    connectors: Any = (),
) -> ProductionConnectivity:
    """Assemble the one production path. Every seam wired, or refused.

    Order matters and mirrors the authority chain: transport is built before
    credentials because the credential adapter dials Vault *through* the
    transport broker, and adapters last because they need both.

    ``audit`` is **required** (Phase 5.13, ADR-056). The governed path must
    not assemble without its evidence sink: an unaudited production gateway
    performs actions it cannot later demonstrate, and a default of ``None``
    is exactly how that happens silently. Pass ``DurablePersistence.audit`` —
    the fenced PostgreSQL chain — which is the one production authority.
    There is deliberately no JSONL and no in-memory fallback here.

    ``connectors`` registers additional providers through the same seams the
    GitHub connector uses — directory registration, adapter preflight, and
    the shared input validator — as ``(entry, adapter, catalog)`` triples.
    One path, more providers; never a second path.
    """
    from backend.api.capability_execution_composition import (
        build_adapter_preflight,
        build_github_connector,
        build_invocation_gateway,
        build_operation_input_validator,
        build_worker_directory,
        build_worker_runtime,
    )
    from backend.api.credential_composition import (
        BrokerCredentialProvider,
        build_credential_broker,
    )
    from backend.api.transport_composition import (
        build_connection_policy,
        build_transport_broker,
    )
    from backend.platform.credentials.vault import VaultCredentialAdapter
    from backend.platform.transport import (
        HttpxTransportAdapter,
        ResourceBudget,
        TransportEndpoint,
    )

    if not isinstance(config, ProductionConnectivityConfig):
        raise ConnectivityMisconfigured("a configuration is required")
    if audit is None:
        raise ConnectivityMisconfigured(
            "the production path requires an audit runtime; assembling the "
            "governed gateway without its evidence sink would produce actions "
            "that cannot be demonstrated afterwards. Pass the durable audit "
            "runtime (DurablePersistence.audit) — there is no JSONL or "
            "in-memory fallback on this path, deliberately"
        )

    # 1. Policy, from deployment configuration and nowhere else.
    policy = build_connection_policy(
        config.environment,
        allow_private_destinations=config.allow_private_destinations,
        allow_plaintext=config.allow_plaintext,
        proxy_url=config.proxy_url,
        trust_environment_proxy=config.trust_environment_proxy,
        follow_redirects=config.follow_redirects,
        max_redirect_hops=config.max_redirect_hops,
        ca_bundle_path=config.ca_bundle_path,
        budget=ResourceBudget(
            max_concurrent_connections=config.max_concurrent_connections
        ),
    )

    # 2. Transport. One adapter, registered for the kinds it can actually carry.
    transport_broker = build_transport_broker(
        audit=audit, metrics=metrics, clock=clock
    )
    transport_broker.register(
        HttpxTransportAdapter(
            environments=frozenset({config.environment}),
            user_agent=config.user_agent,
        )
    )

    # 3. Credentials. The Vault token is the one secret that enters from the
    #    environment, and it is CortexPrime's own credential to its secret
    #    store rather than any tenant's credential to a provider.
    credential_broker = build_credential_broker(
        resolution_service=resolution_service,
        context_factory=context_factory,
        audit=audit,
        metrics=metrics,
        clock=clock,
    )
    vault_token = _bootstrap_vault_token(config)
    if vault_token is not None:
        vault_endpoint = TransportEndpoint.parse(
            config.vault_address,
            transport=TransportKind.HTTPS,
            environment=config.environment,
        )
        for provider_id in _credentialled_providers(config, enable_github=enable_github):
            credential_broker.register(
                VaultCredentialAdapter(
                    provider_id=provider_id,
                    environments=frozenset({config.environment}),
                    broker=transport_broker,
                    endpoint=vault_endpoint,
                    policy=policy,
                    vault_token=vault_token,
                    mount=config.vault_mount,
                    path_prefix=config.vault_path_prefix,
                    credential_type=CredentialType.API_KEY,
                    clock=clock,
                )
            )

    # 4. The worker directory and the adapter preflight over it.
    directory = build_worker_directory()
    preflight = build_adapter_preflight(directory, context_factory=context_factory)

    # 5. Provider adapters. Registered, and deliberately not enabled -- see
    #    ``build_github_connector``: four separate deliberate acts stand between
    #    a registration and real work.
    adapters: dict = {}
    catalogs: dict = {}
    if enable_github:
        entry, adapter, catalog = build_github_connector(
            transport_broker=transport_broker,
            connection_policy=policy,
            environment=config.environment,
            base_url=config.github_base_url,
            preflight=preflight,
            metrics=metrics,
        )
        adapters["github"] = adapter
        catalogs["github"] = catalog
        _register(directory, entry, adapter, context_factory)

    # 5b. Additional providers, through the very same seams. A deployment
    #     with a second provider registers it here; nothing about the path
    #     downstream of registration knows or cares which providers exist.
    for entry, adapter, catalog in connectors:
        provider_id = getattr(catalog, "provider_id", None) or getattr(
            entry, "worker_id", "connector"
        )
        adapters[str(provider_id)] = adapter
        catalogs[str(provider_id)] = catalog
        _register(directory, entry, adapter, context_factory)

    # 6. Input validation, from the same catalogs the adapters build from.
    input_validator = build_operation_input_validator(*catalogs.values())

    # 7. The runtime and the one gate.
    worker_runtime = build_worker_runtime(
        resolution_service=resolution_service,
        worker_kind_resolver=worker_kind_resolver,
        directory=directory,
        input_validator=input_validator,
        observer=observer,
    )
    gateway = build_invocation_gateway(
        worker_runtime=worker_runtime,
        authorization_service=authorization_service,
        execution_service=execution_service,
        input_validator=input_validator,
        credentials=BrokerCredentialProvider(credential_broker),
        rate_limiter=rate_limiter,
        delegation=delegation,
        audit=audit,
        observer=observer,
        clock=clock,
    )

    return ProductionConnectivity(
        config=config,
        gateway=gateway,
        worker_runtime=worker_runtime,
        directory=directory,
        credential_broker=credential_broker,
        transport_broker=transport_broker,
        input_validator=input_validator,
        adapters=adapters,
        catalogs=catalogs,
        metrics=metrics,
    )


def build_development_connectivity(
    *,
    environment: ExecutionEnvironment = ExecutionEnvironment.DEVELOPMENT,
    **kwargs: Any,
) -> ProductionConnectivity:
    """The same graph with the scripted transport and credential provider.

    A separately-named function rather than a flag, for the same reason
    ``build_development_broker`` is one: a flag is something configuration sets
    by accident and a differently-named function is something a person types.
    Refuses production here, and both scripted components refuse it again.
    """
    if environment is ExecutionEnvironment.PRODUCTION:
        raise ConnectivityMisconfigured(
            "build_development_connectivity cannot serve production; a scripted "
            "transport there would make every provider look reachable and every "
            "action look performed, silently"
        )
    config = kwargs.pop(
        "config",
        ProductionConnectivityConfig(
            environment=environment,
            vault_address="http://localhost:8200",
            allow_private_destinations=True,
            allow_plaintext=True,
        ),
    )
    return build_production_connectivity(config=config, **kwargs)


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _bootstrap_vault_token(
    config: ProductionConnectivityConfig,
) -> Optional[Any]:
    """Read the platform's own Vault token, once, into unserialisable material.

    ADR-040 forbids reading *provider* credentials from the environment, and
    that prohibition is unchanged: a provider credential is per tenant and one
    process variable cannot be. This is the bootstrap credential to the secret
    store itself, which by definition cannot come from the secret store, and the
    environment is the conventional place for it.

    Read once at build time and wrapped immediately, so the plain string exists
    for the length of this function and lives afterwards only inside
    ``CredentialMaterial`` — which raises on ``to_dict``, on pickling, on
    ``deepcopy`` and on ``==``, and renders redacted in every f-string.

    Returns ``None`` when unset outside production, which leaves the broker with
    no adapter and every acquisition refusing ``credential_no_provider``. In
    production the absence was already refused in ``for_environment``.
    """
    from datetime import datetime, timedelta, timezone

    from backend.platform.credentials.material import CredentialMaterial

    raw = os.environ.get(_VAULT_TOKEN_ENV, "").strip()
    if not raw:
        if config.environment is ExecutionEnvironment.PRODUCTION:
            raise ConnectivityMisconfigured(
                f"{_VAULT_TOKEN_ENV} is not set; production connectivity will "
                "not assemble a credential path it cannot authenticate"
            )
        log.warning(
            "no %s is set; no credential adapter is registered and every "
            "acquisition will refuse credential_no_provider",
            _VAULT_TOKEN_ENV,
        )
        return None
    now = datetime.now(timezone.utc)
    return CredentialMaterial(
        secret=raw,
        ref=CredentialRef(
            tenant_id="cortexprime-platform",
            credential_id="vault-bootstrap",
        ),
        credential_type=CredentialType.BEARER,
        # The platform's own token is long-lived by nature. A nominal expiry is
        # given so the type's invariants hold; it is not a claim that the token
        # rotates, and the credentials this adapter *issues* are bounded by the
        # authority window regardless of what this one does.
        expires_at=now + timedelta(days=365),
        acquired_at=now,
        headers=("Authorization",),
    )


def _credentialled_providers(
    config: ProductionConnectivityConfig, *, enable_github: bool
) -> Tuple[str, ...]:
    """Which providers get a credential adapter. Explicit, never discovered."""
    providers: list = []
    if enable_github:
        providers.append("github")
    providers.extend(sorted(config.mcp_servers))
    return tuple(providers)


def _register(
    directory: Any, entry: Any, adapter: Any, context_factory: Optional[Any]
) -> None:
    """Record the registration. **Registered is not enabled.**

    The entry goes in at REGISTERED/UNVERIFIED/UNAVAILABLE and stays there.
    Validating it, enabling it, trusting it and marking it available are four
    separate deliberate acts with four separate records (ADR-036), and none of
    them happens as a side effect of assembling a graph.
    """
    if context_factory is None:
        log.warning(
            "no context factory: worker %s was built but not registered, so "
            "every invocation of it will refuse at selection",
            entry.worker_id,
        )
        return
    try:
        directory.register(context_factory(), entry.implementation, adapter)
    except Exception:  # noqa: BLE001 - a failed registration is a refusal later
        log.error("registering worker %s failed", entry.worker_id, exc_info=False)
