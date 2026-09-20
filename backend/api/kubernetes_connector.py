"""The Kubernetes reference connector: manifest, connection and permissions.

Phase 11.1-K. Kubernetes is the first connector taken to the connector
completion standard, and this module is the part of it a future connector
copies: one manifest declaring every capability the connector offers, one
explicit connection binding a CortexPrime tenant to a cluster target, and the
exact provider permissions each capability needs.

Capabilities (and why only these)
-----------------------------------
READ (provider ``kubernetes``, in-process, read-only ServiceAccount):
pods.list, pod.get, pod.logs, deployment.get, events.list, replicasets.list,
pods.watch -- the evidence an incident investigation actually uses -- and
access.review, the connector's own permission check used by health.

WRITE (each on its own contained worker with its own ServiceAccount):
deployment.rollback (compensable, ADR-124) and workload.rollout_restart
(human-approved, ADR-086/089). No other write exists and none is invented to
make the connector look complete. ``deployments.list`` is declared in the
catalog but used by nothing, so it is not shipped as a capability.

Tenancy (the relationship, stated)
------------------------------------
A Kubernetes namespace is NOT a CortexPrime tenant. A **connection** binds one
tenant to one cluster and one namespace:

    CortexPrime tenant  --connection-->  cluster  +  namespace

and every capability invocation must name a target inside the invoking
tenant's connection (enforced at the gateway input stage by
``backend.api.connector_scope``) AND runs with a credential minted for that
tenant from a ServiceAccount whose RBAC is confined to that namespace (enforced
by the provider). Either layer alone refuses a cross-tenant target.

One connection per deployment in this phase: the signal, investigation and
remediation loops are single-tenant (ADR-122..124). Several connections per
deployment is a stated limitation, not an implied capability.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from backend.contracts.connector_manifest import CapabilityManifest, ConnectorManifest
from backend.contracts.errors import ContractViolation

log = logging.getLogger(__name__)

__all__ = [
    "kubernetes_connector_extension",
    "KUBERNETES_CONNECTOR_ID",
    "KubernetesConnection",
    "kubernetes_manifest",
    "permission_review",
    "IN_CLUSTER_API_URL",
]

KUBERNETES_CONNECTOR_ID = "kubernetes"
IN_CLUSTER_API_URL = "https://kubernetes.default.svc"

_PODS_LIST = "kubernetes:pods:list"
_PODS_GET = "kubernetes:pods:get"
_PODS_WATCH = "kubernetes:pods:watch"
_PODS_LOG = "kubernetes:pods/log:get"
_EVENTS_LIST = "kubernetes:events:list"
_DEPLOY_GET = "kubernetes:apps/deployments:get"
_DEPLOY_PATCH = "kubernetes:apps/deployments:patch"
_RS_LIST = "kubernetes:apps/replicasets:list"

#: How each permission string is asked of the API server (SelfSubjectAccessReview).
_REVIEWS: Mapping[str, dict] = {
    _PODS_LIST: {"verb": "list", "resource": "pods"},
    _PODS_GET: {"verb": "get", "resource": "pods"},
    _PODS_WATCH: {"verb": "watch", "resource": "pods"},
    _PODS_LOG: {"verb": "get", "resource": "pods", "subresource": "log"},
    _EVENTS_LIST: {"verb": "list", "resource": "events"},
    _DEPLOY_GET: {"verb": "get", "resource": "deployments", "group": "apps"},
    _DEPLOY_PATCH: {"verb": "patch", "resource": "deployments", "group": "apps"},
    _RS_LIST: {"verb": "list", "resource": "replicasets", "group": "apps"},
}


def permission_review(permission: str, namespace: str) -> dict:
    """The access-review payload that asks whether ``permission`` is held."""
    try:
        attributes = dict(_REVIEWS[permission])
    except KeyError as exc:
        raise ContractViolation(f"no access review is defined for {permission!r}") from exc
    return {"namespace": namespace, **attributes}


_DESCRIPTIONS = {
    "kubernetes.pods.list": (
        "List the pods of the connected namespace with their phase, readiness, restart count "
        "and waiting reason (for example CrashLoopBackOff). Use to find which workloads are unhealthy."),
    "kubernetes.pod.get": (
        "Read one pod's status, including how its container last terminated (exit code and "
        "reason such as OOMKilled). Use to tell an application crash from a resource kill."),
    "kubernetes.pod.logs": (
        "Read the shape of one pod's recent container log: line counts, error-line counts and "
        "normalized recurring patterns, never raw text. Use to see what a failing container reported."),
    "kubernetes.deployment.get": (
        "Read one Deployment: revision, image, replica availability, rollout progress, template "
        "digest and conditions. Use to decide whether a recent rollout changed what is running."),
    "kubernetes.events.list": (
        "List the control plane's recent events for the connected namespace (BackOff, Unhealthy, "
        "Failed, scaling) with timestamps. Use to see what Kubernetes itself recorded about a failure."),
    "kubernetes.replicasets.list": (
        "List a namespace's ReplicaSets: every revision a Deployment rolled, with its image, "
        "template digest and creation time. Use to answer what changed, and when."),
    "kubernetes.pods.watch": (
        "Observe pod changes in the connected namespace for a bounded window. Used by the "
        "signal fabric to detect failures as they happen."),
    "kubernetes.access.review": (
        "Ask the cluster whether this connection's own credential holds one permission. Used "
        "by connector health to report exactly which permission is missing."),
    "kubernetes.deployment.rollback": (
        "Roll one Deployment back to a revision it previously ran, after the platform verified "
        "that revision exists and was observed healthy. Governed: requires approval (or earned, "
        "policy-delegated autonomy for this compensable action) and is independently verified."),
    "kubernetes.workload.rollout_restart": (
        "Restart one Deployment's pods without changing its configuration. Governed: always "
        "requires a human approval and is independently verified."),
}

_PERMISSIONS = {
    "kubernetes.pods.list": (_PODS_LIST,),
    "kubernetes.pod.get": (_PODS_GET,),
    "kubernetes.pod.logs": (_PODS_LOG,),
    "kubernetes.deployment.get": (_DEPLOY_GET,),
    "kubernetes.events.list": (_EVENTS_LIST,),
    "kubernetes.replicasets.list": (_RS_LIST,),
    "kubernetes.pods.watch": (_PODS_WATCH,),
    "kubernetes.access.review": (),
    "kubernetes.deployment.rollback": (_DEPLOY_GET, _DEPLOY_PATCH, _RS_LIST),
    "kubernetes.workload.rollout_restart": (_DEPLOY_GET, _DEPLOY_PATCH),
}

_CATEGORY = {
    "kubernetes.pods.watch": "signal",
    "kubernetes.access.review": "health",
    "kubernetes.deployment.rollback": "remediation",
    "kubernetes.workload.rollout_restart": "remediation",
}

#: Which provider (worker boundary) serves each capability.
_PROVIDER = {
    "kubernetes.deployment.rollback": "kubernetes-contained-rollback",
    "kubernetes.workload.rollout_restart": "kubernetes-contained",
}

SHIPPED_READS = (
    "kubernetes.pods.list", "kubernetes.pod.get", "kubernetes.pod.logs",
    "kubernetes.deployment.get", "kubernetes.events.list", "kubernetes.replicasets.list",
    "kubernetes.pods.watch", "kubernetes.access.review",
)
SHIPPED_WRITES = ("kubernetes.deployment.rollback", "kubernetes.workload.rollout_restart")


def kubernetes_manifest() -> ConnectorManifest:
    """The one declaration of the Kubernetes connector."""
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        kubernetes_read_profiles,
        kubernetes_write_profiles,
    )

    profiles = {**kubernetes_read_profiles(), **kubernetes_write_profiles()}
    capabilities = tuple(
        CapabilityManifest(
            capability_id=f"platform.{operation}", version=1, operation=operation,
            provider=_PROVIDER.get(operation, "kubernetes"),
            description=_DESCRIPTIONS[operation],
            category=_CATEGORY.get(operation, "observation"),
            profile=profiles[operation],
            required_permissions=_PERMISSIONS[operation],
        )
        for operation in SHIPPED_READS + SHIPPED_WRITES
    )
    return ConnectorManifest(
        connector_id=KUBERNETES_CONNECTOR_ID, display_name="Kubernetes", version="1.0.0",
        description=("Observe one Kubernetes namespace and take governed, independently "
                     "verified remediation actions on its Deployments."),
        capabilities=capabilities)


@dataclass(frozen=True)
class KubernetesConnection:
    """One tenant bound to one cluster namespace. Deployment configuration only."""

    tenant_id: str
    namespace: str
    api_url: str = IN_CLUSTER_API_URL
    cluster_ref: str = "in-cluster"

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ContractViolation("a Kubernetes connection names the tenant it belongs to")
        if not self.namespace.strip():
            raise ContractViolation("a Kubernetes connection names the namespace it may reach")
        if not self.api_url.lower().startswith("https://"):
            raise ContractViolation(
                "the Kubernetes API is reached over https only; a bearer token on plaintext is "
                "exposed on every request")

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> Optional["KubernetesConnection"]:
        """``CORTEX_KUBERNETES_TENANT`` + ``CORTEX_KUBERNETES_NAMESPACE`` (or the signal
        namespace), optional ``CORTEX_KUBERNETES_URL`` (default: the in-cluster API)."""
        env = os.environ if environ is None else environ
        tenant = (env.get("CORTEX_KUBERNETES_TENANT") or "").strip()
        namespace = (env.get("CORTEX_KUBERNETES_NAMESPACE")
                     or env.get("CORTEX_SIGNAL_NAMESPACE") or "").strip()
        if not tenant or not namespace:
            return None
        return cls(tenant_id=tenant, namespace=namespace,
                   api_url=(env.get("CORTEX_KUBERNETES_URL") or IN_CLUSTER_API_URL).strip(),
                   cluster_ref=(env.get("CORTEX_SIGNAL_CLUSTER_REF") or "in-cluster").strip())


# ---------------------------------------------------------------------------
# Composition: one connection in, the whole connector out
# ---------------------------------------------------------------------------

SA_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _pinned(policy: Any, url: str, ca_bundle: str = "") -> Any:
    """``policy`` narrowed to ``url``'s own resolved private addresses.

    The explicit, reviewed in-cluster policy (``ConnectionPolicy.
    allowed_private_addresses``): exactly the addresses this connector's
    configured endpoint resolves to at composition, nothing wider. A public
    endpoint is left as it is. An unresolvable one is left unpinned, so the
    dial is refused and health reports UNAVAILABLE rather than composition
    guessing an address.
    """
    import ipaddress
    import socket
    from dataclasses import replace
    from urllib.parse import urlsplit

    host = urlsplit(url).hostname or ""
    private = set()
    try:
        for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP):
            address = info[4][0]
            parsed = ipaddress.ip_address(address)
            if parsed.is_private and not parsed.is_loopback and not parsed.is_link_local:
                private.add(address)
    except OSError:
        log.warning("kubernetes connector: %s did not resolve at composition", host)
    if private:
        policy = replace(policy, allowed_private_addresses=frozenset(
            set(policy.allowed_private_addresses) | private))
    if ca_bundle:
        policy = replace(policy, tls=replace(policy.tls, ca_bundle_path=ca_bundle))
    return policy


def _ca(specific: str) -> str:
    value = _env(specific) or _env("CORTEX_TLS_CA_BUNDLE")
    if not value and specific == "CORTEX_KUBERNETES_CA_BUNDLE" and os.path.exists(SA_CA_PATH):
        value = SA_CA_PATH
    return value


def kubernetes_connector_extension(environment: Any) -> Optional[dict]:
    """``CORTEX_CONNECTOR_FACTORIES`` entry for the Kubernetes reference connector.

    Composes, from ONE connection (``CORTEX_KUBERNETES_TENANT`` +
    ``CORTEX_KUBERNETES_NAMESPACE``): the read connector, the contained
    rollback and restart workers that are configured, their credentials, the
    manifest (commissioned at boot) and the connection scope (enforced at the
    gateway). Returns ``None`` when no connection is configured.

    Credentials (``CORTEX_KUBERNETES_CREDENTIALS``):
      * ``vault`` (the default, and the only mode production accepts): Vault's
        Kubernetes secrets engine mints a short-lived token per acquisition for
        the role of each provider; CortexPrime authenticates to Vault with
        ``VAULT_TOKEN`` if one is set, otherwise with Vault's Kubernetes auth
        method and the pod's projected ServiceAccount token.
      * ``static``: the non-production development path, tokens from the
        environment into ``DevelopmentCredentialProvider`` (refuses production).
    """
    from backend.contracts.execution import ExecutionEnvironment

    connection = KubernetesConnection.from_env()
    if connection is None:
        return None
    production = environment is ExecutionEnvironment.PRODUCTION
    mode = _env("CORTEX_KUBERNETES_CREDENTIALS", "vault").lower()
    if mode not in ("vault", "static"):
        raise ContractViolation("CORTEX_KUBERNETES_CREDENTIALS is 'vault' or 'static'")
    if production and mode != "vault":
        raise ContractViolation(
            "a production Kubernetes connection takes its credentials from Vault; "
            "static tokens are a development path")

    from backend.api.capability_execution_composition import (
        CONTAINED_KUBERNETES_PROVIDER_ID,
        CONTAINED_ROLLBACK_PROVIDER_ID,
        build_contained_rollback_worker_connector,
        build_contained_worker_connector,
        build_kubernetes_connector,
    )
    from backend.api.connector_scope import ConnectionScope

    api_url, api_ca = connection.api_url, _ca("CORTEX_KUBERNETES_CA_BUNDLE")
    worker_ca = _ca("CORTEX_WORKER_CA_BUNDLE")

    def read_builder(*, transport_broker: Any, connection_policy: Any, environment: Any,
                     preflight: Any = None, metrics: Any = None) -> tuple:
        return build_kubernetes_connector(
            transport_broker=transport_broker,
            connection_policy=_pinned(connection_policy, api_url, api_ca),
            environment=environment, base_url=api_url, preflight=preflight, metrics=metrics)

    connectors = [read_builder]
    providers = {"kubernetes": ("CORTEX_KUBERNETES_TOKEN", "CORTEX_VAULT_ROLE_READER",
                                "cortexprime-reader")}
    workers = (
        (CONTAINED_ROLLBACK_PROVIDER_ID, "CORTEX_ROLLBACK", build_contained_rollback_worker_connector,
         "platform.kubernetes.deployment.rollback", "CORTEX_VAULT_ROLE_ROLLBACK",
         "cortexprime-rollbacker"),
        (CONTAINED_KUBERNETES_PROVIDER_ID, "CORTEX_RESTART", build_contained_worker_connector,
         "platform.kubernetes.workload.rollout_restart", "CORTEX_VAULT_ROLE_RESTART",
         "cortexprime-restarter"),
    )
    for provider_id, prefix, builder, capability_id, role_env, role_default in workers:
        url, digest = _env(f"{prefix}_WORKER_URL"), _env(f"{prefix}_IMPL_DIGEST")
        if not (url and digest):
            continue  # not deployed: its capability is SKIPPED by commissioning

        def worker_builder(*, transport_broker: Any, connection_policy: Any, environment: Any,
                           preflight: Any = None, metrics: Any = None, _url=url, _digest=digest,
                           _builder=builder, _capability=capability_id) -> tuple:
            return _builder(
                transport_broker=transport_broker,
                connection_policy=_pinned(connection_policy, _url, worker_ca),
                environment=environment, worker_url=_url, capability_id=_capability,
                capability_version=1, implementation_digest=_digest,
                preflight=preflight, metrics=metrics)

        connectors.append(worker_builder)
        providers[provider_id] = (f"{prefix}_WORKER_TOKEN", role_env, role_default)

    produced: dict = {
        "connectors": connectors,
        "manifests": [kubernetes_manifest()],
        "connection_scopes": [ConnectionScope(
            tenant_id=connection.tenant_id, providers=frozenset(providers),
            targets=frozenset({connection.namespace}))],
        "credential_providers": [],
        "credential_provider_builders": [],
        # Connector health, built against the composed runtime.
        "health_probes": {KUBERNETES_CONNECTOR_ID: lambda runtime: kubernetes_health_probe(
            runtime, connection, environment)},
    }
    if mode == "static":
        from backend.platform.credentials import DevelopmentCredentialProvider

        for provider_id, (token_env, _role_env, _role) in providers.items():
            token = _env(token_env)
            if token:
                produced["credential_providers"].append(DevelopmentCredentialProvider(
                    provider_id=provider_id, secrets={connection.tenant_id: token},
                    allow_non_production=True, environments=frozenset({environment})))
        return produced

    for provider_id, (_token_env, role_env, role_default) in providers.items():
        produced["credential_provider_builders"].append(
            _vault_builder(provider_id, connection, _env(role_env, role_default), environment))
    return produced


def _vault_builder(provider_id: str, connection: KubernetesConnection, role: str,
                   environment: Any) -> Any:
    """A credential adapter built once the transport broker exists."""

    def build(connectivity: Any) -> Any:
        from datetime import datetime, timedelta, timezone

        from backend.api.transport_composition import build_connection_policy
        from backend.contracts.credential import CredentialRef, CredentialType
        from backend.platform.credentials.material import CredentialMaterial
        from backend.platform.credentials.vault_kubernetes import (
            VaultKubernetesAuth,
            VaultKubernetesCredentialAdapter,
        )
        from backend.platform.transport.endpoint import TransportEndpoint, TransportKind

        address = _env("CORTEX_VAULT_ADDR")
        if not address:
            raise ContractViolation(
                "CORTEX_VAULT_ADDR is required for Vault-issued Kubernetes credentials")
        endpoint = TransportEndpoint.parse(address, transport=TransportKind.HTTPS,
                                           environment=environment)
        policy = _pinned(build_connection_policy(environment), address,
                         _ca("CORTEX_VAULT_CA_BUNDLE"))
        static = _env("VAULT_TOKEN")
        if static:
            now = datetime.now(timezone.utc)
            token: Any = CredentialMaterial(
                secret=static, ref=CredentialRef(tenant_id="cortexprime-platform",
                                                 credential_id="vault-bootstrap"),
                credential_type=CredentialType.BEARER, expires_at=now + timedelta(days=365),
                acquired_at=now, headers=("Authorization",))
        else:
            token = _shared_auth(lambda: VaultKubernetesAuth(
                broker=connectivity.transport_broker, endpoint=endpoint, policy=policy,
                role=_env("CORTEX_VAULT_AUTH_ROLE", "cortexprime"),
                mount=_env("CORTEX_VAULT_AUTH_MOUNT", "kubernetes")))
        return VaultKubernetesCredentialAdapter(
            provider_id=provider_id, environments=frozenset({environment}),
            broker=connectivity.transport_broker, endpoint=endpoint, policy=policy,
            vault_token=token,
            kubernetes_mount=_env("CORTEX_VAULT_KUBERNETES_MOUNT", "kubernetes"),
            bindings={connection.tenant_id: (connection.namespace, role)})

    return build


def kubernetes_health_probe(runtime: Any, connection: KubernetesConnection,
                            environment: Any) -> Any:
    """The Kubernetes connector's health probe (returns a zero-argument callable).

    Evidence, in order; the first failure that makes later checks meaningless
    stops them:
      1. commissioning -- every shipped capability registered as declared
         (a contract conflict is MISCONFIGURED);
      2. authentication + reachability + permissions -- one governed
         ``kubernetes.access.review`` per permission the read capabilities need,
         in the connection tenant's own context, with its own credential: the
         real path, rate limit and audit included;
      3. each deployed contained worker answers ``/healthz`` over verified TLS,
         through the transport broker (no side channel).
    A write worker's own RBAC is not reviewable from here without handling its
    credential in-process, which the architecture forbids; it is verified by
    the worker at execution and by the permission checks of provisioning.
    """
    from backend.api.connector_health import ConnectorHealth, ConnectorHealthState, HealthCheck
    from backend.contracts.connector_errors import (
        ConnectorErrorClass,
        classify_failure_text,
        classify_status,
    )

    S = ConnectorHealthState
    state_for = {
        ConnectorErrorClass.AUTHENTICATION_FAILED: S.AUTHENTICATION_REQUIRED,
        ConnectorErrorClass.RATE_LIMITED: S.RATE_LIMITED,
        ConnectorErrorClass.NETWORK_FAILURE: S.UNAVAILABLE,
        ConnectorErrorClass.TIMEOUT: S.UNAVAILABLE,
        ConnectorErrorClass.PROVIDER_UNAVAILABLE: S.UNAVAILABLE,
    }

    def probe() -> ConnectorHealth:
        import time as _time

        from backend.api.capability_execution_composition import GovernedCapabilityReader
        from backend.api.connector_commissioning import commissioned_capability
        from backend.contracts.identity import PrincipalKind, PrincipalRef
        from backend.platform.context import ExecutionContext
        from backend.platform.context.identity import IdentityContext

        started = _time.monotonic()
        manifest = kubernetes_manifest()
        checks: list = []
        unavailable: dict = {}
        report = getattr(runtime, "connector_reports", {}).get(KUBERNETES_CONNECTOR_ID)
        if report is None:
            checks.append(HealthCheck("commissioning", False, S.MISCONFIGURED,
                                      "the connector was not commissioned in this process"))
            return ConnectorHealth.from_checks(KUBERNETES_CONNECTOR_ID, connection.tenant_id,
                                               checks, duration_seconds=_time.monotonic() - started)
        broken = {**report.conflicts, **report.failed}
        checks.append(HealthCheck(
            "commissioning", not broken, S.MISCONFIGURED,
            "; ".join(f"{k}: {v}" for k, v in broken.items()) or
            f"{len(report.available)} capabilities commissioned"))
        for cid, reason in report.skipped.items():
            unavailable[cid] = reason
        review = commissioned_capability(runtime, "platform.kubernetes.access.review")
        missing: set = set()
        if review is None:
            checks.append(HealthCheck("permissions", False, S.MISCONFIGURED,
                                      "the permission-check capability is not commissioned"))
        else:
            reader = GovernedCapabilityReader(
                runtime=runtime,
                capability_definitions={"kubernetes.access.review": review},
                principal=PrincipalRef(principal_id="connector-health", kind=PrincipalKind.PLATFORM))
            tenant_ctx = ExecutionContext.for_tenant(
                tenant_id=connection.tenant_id,
                identity=IdentityContext(
                    principal=PrincipalRef(principal_id="connector-health",
                                           kind=PrincipalKind.PLATFORM),
                    capabilities=("capability:invoke",)),
                source="connector-health")
            reached = True
            for permission in manifest.required_permissions("kubernetes"):
                outcome = reader.read(tenant_ctx, operation="kubernetes.access.review",
                                      payload=permission_review(permission, connection.namespace))
                if not getattr(outcome, "succeeded", False):
                    reason = str(getattr(outcome, "failure_reason", "") or "")
                    error = (classify_status(getattr(outcome, "status", None))
                             or classify_failure_text(reason))
                    # The refusal's own words say WHICH layer refused (gateway
                    # stage, credential broker, transport, provider) -- without
                    # them "authorization_denied" cannot be acted on (11.1-K).
                    checks.append(HealthCheck(
                        "api", False, state_for.get(error, S.MISCONFIGURED),
                        f"a permission check through the governed path failed ({error.value})"
                        + (f": {reason[:240]}" if reason else ""),
                        error_class=error.value))
                    reached = False
                    break
                if not dict(getattr(outcome, "evidence", {}) or {}).get("allowed"):
                    missing.add(permission)
            if reached:
                checks.append(HealthCheck("api", True, S.UNAVAILABLE,
                                          f"authenticated to {connection.cluster_ref}"))
                checks.append(HealthCheck(
                    "permissions", not missing,
                    S.MISCONFIGURED if missing == set(manifest.required_permissions("kubernetes"))
                    else S.DEGRADED,
                    ("missing: " + ", ".join(sorted(missing))) if missing
                    else f"all {len(manifest.required_permissions('kubernetes'))} read permissions held in "
                         f"namespace {connection.namespace}"))
        for capability in manifest.capabilities:
            lacking = set(capability.required_permissions) & missing
            if capability.provider == "kubernetes" and lacking:
                unavailable[capability.capability_id] = "missing " + ", ".join(sorted(lacking))
        for provider_id, prefix in (("kubernetes-contained-rollback", "CORTEX_ROLLBACK"),
                                    ("kubernetes-contained", "CORTEX_RESTART")):
            url = _env(f"{prefix}_WORKER_URL")
            if not url:
                continue
            ok, detail = _worker_reachable(runtime, connection, url, environment)
            checks.append(HealthCheck(f"worker:{provider_id}", ok, S.DEGRADED, detail))
            if not ok:
                for capability in manifest.capabilities:
                    if capability.provider == provider_id:
                        unavailable[capability.capability_id] = f"worker unreachable: {detail}"
        available = tuple(c for c in report.available if c not in unavailable)
        return ConnectorHealth.from_checks(KUBERNETES_CONNECTOR_ID, connection.tenant_id, checks,
                                           available=available, unavailable=unavailable,
                                           duration_seconds=_time.monotonic() - started)

    return probe


def _worker_reachable(runtime: Any, connection: KubernetesConnection, url: str,
                      environment: Any) -> tuple:
    """GET ``/healthz`` through the transport broker: pinned address, verified TLS."""
    from backend.api.transport_composition import build_connection_policy
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.platform.transport.endpoint import TransportEndpoint, TransportKind
    from backend.platform.transport.request import DeliveryState, TransportRequest

    try:
        endpoint = TransportEndpoint.parse(url.rstrip("/") + "/healthz",
                                           transport=TransportKind.HTTPS, environment=environment)
        policy = _pinned(build_connection_policy(environment), url, _ca("CORTEX_WORKER_CA_BUNDLE"))
        outcome = runtime.connectivity.transport_broker.dial(TransportRequest(
            endpoint=endpoint, policy=policy, tenant_id=connection.tenant_id,
            principal=PrincipalRef(principal_id="connector-health", kind=PrincipalKind.PLATFORM),
            method="GET", authority_seconds_remaining=10.0))
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}"
    if outcome.delivery is not DeliveryState.DELIVERED:
        return False, "not delivered"
    return outcome.status_code == 200, f"HTTP {outcome.status_code} over verified TLS"


_AUTH: dict = {}


def _shared_auth(factory: Any) -> Any:
    """One Vault login per process, shared by every provider's adapter."""
    auth = _AUTH.get("auth")
    if auth is None:
        auth = _AUTH.setdefault("auth", factory())
    return auth
