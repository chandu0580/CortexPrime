"""The governed Kubernetes READ capability — Phase 9.1 (ADR-081).

Kubernetes becomes a *governed capability of CortexPrime*, not a connector: a
declared, read-only ``OperationCatalog`` of `ProviderOperationSpec`s modelling the
Kubernetes HTTP API (the API server is plain HTTPS), so a Kubernetes read runs
through the ONE governed execution path — capability → authorization → lease →
gateway → transport → provider — exactly like GitHub/Grafana. There is NO second
gateway, executor, scheduler, credential system, or HTTP client here: this module
declares the *contract* only; provider I/O happens solely when the governed
execution transport invokes the composed adapter.

This module imports no `kubernetes` SDK, no `httpx`, no `backend.connectors`, no
credential carrier (structurally fenced by BND-PROVIDER-SDK / BND-DIRECT-HTTP), and
declares only READ operations (Part D) — a write would require a new, explicit
capability declaration with a `RiskClassification` + verification requirement.

resourceVersion (Part F): the governed ``evidence()`` extraction is deliberately
bounded to top-level scalars (ADR-042: raw payloads belong in an evidence store,
not the execution event). So the provider adapter NORMALIZES a Kubernetes response
— lifting ``metadata.resourceVersion`` to a top-level ``resourceVersion`` evidence
field — and every LIST/GET spec keeps ``resourceVersion`` in its
``response_evidence_fields``. A governed read's resourceVersion therefore survives
into the Observation, establishing the data contract a future LIST→WATCH continuity
(Phase 9.2/9.3) needs. resourceVersion is never fabricated: if the provider omits
it, it is simply absent (Part F). WATCH is deliberately NOT implemented here.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from backend.contracts.execution import (
    EffectSemantics, ExecutionEnvironment, SideEffectClass,
)
from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel
from backend.contracts.provider import ProviderRef
from backend.contracts.transport import TransportKind
from backend.contracts.intelligence.investigation import AutonomyLevel
from backend.contracts.intelligence.capability_profile import (
    CapabilityProfile, VerificationRequirement,
)
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog, ParameterKind, ParameterLocation, ParameterSpec, ProviderOperationSpec,
)
from backend.contexts.execution.infrastructure.adapters.channel import ProviderChannel
from backend.contexts.execution.infrastructure.adapters.connector import (
    HttpStatusTranslator,
)
from backend.platform.transport import ConnectionPolicy, TransportBroker, TransportEndpoint

__all__ = [
    "KUBERNETES_PROVIDER_ID",
    "KUBERNETES_PROVIDER",
    "KUBERNETES_READ_OPERATIONS",
    "KUBERNETES_REAL_READ_OPERATIONS",
    "KubernetesReadNormalizer",
    "KubernetesResponseTranslator",
    "kubernetes_read_catalog",
    "kubernetes_real_read_catalog",
    "kubernetes_read_profiles",
    "build_kubernetes_channel",
]

KUBERNETES_PROVIDER_ID = "kubernetes"
KUBERNETES_PROVIDER = ProviderRef(provider_id=KUBERNETES_PROVIDER_ID)
_POLICY_VERSION = "k8s-read-policy/1"

#: Phase 9.2 exposes exactly ONE real operation (Part E): the smallest read that
#: proves the whole governed chain against a live API server. The other five
#: remain declared contract, real-exposed only when a later phase decides to.
KUBERNETES_REAL_READ_OPERATIONS = ("kubernetes.pods.list",)

#: The smallest read-only set for the first incident-investigation vertical
#: (Phase 9.0 §8: CrashLoopBackOff / deployment-failure). Deriving cause from pods,
#: their events, their logs, and the owning deployment.
KUBERNETES_READ_OPERATIONS = (
    "kubernetes.pods.list",
    "kubernetes.pod.get",
    "kubernetes.pod.logs",
    "kubernetes.deployments.list",
    "kubernetes.deployment.get",
    "kubernetes.events.list",
)

# Shared parameter shapes — all references, never a URL or shell fragment.
_NS = ParameterSpec(name="namespace", kind=ParameterKind.RESOURCE_SEGMENT,
                    location=ParameterLocation.PATH, max_length=253)
_NAME = ParameterSpec(name="name", kind=ParameterKind.RESOURCE_SEGMENT,
                      location=ParameterLocation.PATH, max_length=253)
_LABEL = ParameterSpec(name="labelSelector", kind=ParameterKind.STRING,
                       location=ParameterLocation.QUERY, max_length=512, required=False)
_LIMIT = ParameterSpec(name="limit", kind=ParameterKind.INTEGER,
                       location=ParameterLocation.QUERY, required=False)

# resourceVersion (lifted to top-level by the adapter) is kept in the bounded
# scalar evidence of every read (Part F). Evidence fields are top-level scalars —
# the governed evidence extractor keeps only int/float/bool/str, by design.
_RV = "resourceVersion"
_TIMEOUT = 20.0

_K8S_HEADERS = {
    "accept": "application/json",
    "user-agent": "CortexPrime-ConnectorAdapter/1.0",
}


def _read(operation: str, path_template: str, *, parameters, evidence,
          required=(_RV,)) -> ProviderOperationSpec:
    return ProviderOperationSpec(
        operation=operation, method="GET", path_template=path_template,
        side_effect_class=SideEffectClass.READ, effect_semantics=EffectSemantics.READ_ONLY,
        parameters=parameters, success_statuses=(200,),
        response_required_fields=required, response_evidence_fields=evidence,
        static_headers=_K8S_HEADERS,
        provider_timeout_seconds=_TIMEOUT, max_response_bytes=4 * 1024 * 1024)


def kubernetes_read_catalog() -> OperationCatalog:
    """The declared, READ-only Kubernetes operation catalog (real capability
    contract). Provider I/O only happens when the governed transport invokes the
    composed adapter — this is the contract, not the client. Evidence fields are the
    normalized top-level scalars a real adapter lifts from the K8s response."""
    return OperationCatalog(
        KUBERNETES_PROVIDER_ID,
        (
            _read("kubernetes.pods.list", "/api/v1/namespaces/{namespace}/pods",
                  parameters=(_NS, _LABEL, _LIMIT),
                  evidence=(_RV, "kind", "apiVersion", "podCount", "crashLoopCount")),
            _read("kubernetes.pod.get", "/api/v1/namespaces/{namespace}/pods/{name}",
                  parameters=(_NS, _NAME),
                  evidence=(_RV, "kind", "name", "namespace", "phase", "restartCount",
                            "waitingReason")),
            _read("kubernetes.pod.logs", "/api/v1/namespaces/{namespace}/pods/{name}/log",
                  parameters=(_NS, _NAME), evidence=("name", "lineCount"),
                  required=()),   # log body is text; no envelope / no resourceVersion
            _read("kubernetes.deployments.list",
                  "/apis/apps/v1/namespaces/{namespace}/deployments",
                  parameters=(_NS, _LABEL, _LIMIT),
                  evidence=(_RV, "kind", "apiVersion", "deploymentCount")),
            _read("kubernetes.deployment.get",
                  "/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
                  parameters=(_NS, _NAME),
                  evidence=(_RV, "kind", "name", "namespace", "replicas", "readyReplicas",
                            "availableReplicas")),
            _read("kubernetes.events.list", "/api/v1/namespaces/{namespace}/events",
                  parameters=(_NS, _LIMIT),
                  evidence=(_RV, "kind", "apiVersion", "eventCount")),
        ),
    )


def kubernetes_real_read_catalog() -> OperationCatalog:
    """The Phase 9.2 REAL exposure: exactly one operation (Part E). A deployment
    that composes the real adapter exposes this subset; the full read catalog
    remains the declared contract for later phases to expose deliberately."""
    full = kubernetes_read_catalog()
    return OperationCatalog(
        KUBERNETES_PROVIDER_ID,
        tuple(full.require(op) for op in KUBERNETES_REAL_READ_OPERATIONS),
    )


class KubernetesResponseTranslator(HttpStatusTranslator):
    """Kubernetes answers failures with a ``Status`` object carrying a bounded
    ``message`` ("pods is forbidden: User ... cannot list resource ..."). The
    default status mapping already classifies 401/403/404/410 correctly; this
    translator only extracts that message so an operator sees the cluster's own
    sentence instead of a bare status code. It cannot reclassify a failure into
    a success: ``classify`` is inherited unchanged."""

    def describe(self, exchange: Any, body: Any) -> Tuple[Optional[str], Optional[str]]:
        code, reason = super().describe(exchange, body)
        if isinstance(body, Mapping) and body.get("kind") == "Status":
            message = body.get("message")
            if isinstance(message, str) and message.strip():
                return code, message.strip()[:200]
        return code, reason


class KubernetesReadNormalizer:
    """Lifts the declared evidence scalars out of the Kubernetes envelope
    (Part G). This is the code the 9.1 docstring promised and 9.2 makes real.

    - ``metadata.resourceVersion`` → top-level ``resourceVersion``, **exactly as
      returned**: an opaque string, never coerced to an integer, never hashed,
      never substituted, never fabricated. If the cluster omitted it, it stays
      absent — the operation's required-field check then refuses the answer as
      malformed (Part N: reject, never synthesize).
    - list envelopes gain their declared counts (``podCount``/``crashLoopCount``/
      ``deploymentCount``/``eventCount``) computed from ``items``.
    - single-resource reads lift the declared identity/status scalars.

    Pure and deterministic; understands the envelope of every operation in the
    declared catalog; raises on a non-mapping body (the adapter then refuses the
    answer as malformed — a refusal, not an invention).
    """

    def normalize(self, spec: ProviderOperationSpec, body: Any) -> Any:
        if not isinstance(body, Mapping):
            raise ValueError(
                f"{spec.operation}: expected a JSON object envelope, "
                f"got {type(body).__name__}"
            )
        out = dict(body)
        meta = body.get("metadata")
        if isinstance(meta, Mapping):
            version = meta.get("resourceVersion")
            if isinstance(version, str) and version:
                out[_RV] = version
        items = body.get("items")
        op = spec.operation
        if op == "kubernetes.pods.list" and isinstance(items, list):
            out["podCount"] = len(items)
            out["crashLoopCount"] = sum(1 for pod in items if self._is_crashloop(pod))
        elif op == "kubernetes.deployments.list" and isinstance(items, list):
            out["deploymentCount"] = len(items)
        elif op == "kubernetes.events.list" and isinstance(items, list):
            out["eventCount"] = len(items)
        elif op == "kubernetes.pod.get":
            self._lift_identity(out, meta)
            status = body.get("status")
            if isinstance(status, Mapping):
                phase = status.get("phase")
                if isinstance(phase, str):
                    out["phase"] = phase
                restarts, waiting = self._container_signal(status)
                if restarts is not None:
                    out["restartCount"] = restarts
                if waiting is not None:
                    out["waitingReason"] = waiting
        elif op == "kubernetes.deployment.get":
            self._lift_identity(out, meta)
            wanted = body.get("spec")
            if isinstance(wanted, Mapping) and isinstance(wanted.get("replicas"), int):
                out["replicas"] = wanted["replicas"]
            status = body.get("status")
            if isinstance(status, Mapping):
                for field in ("readyReplicas", "availableReplicas"):
                    if isinstance(status.get(field), int):
                        out[field] = status[field]
        return out

    @staticmethod
    def _lift_identity(out: dict, meta: Any) -> None:
        if isinstance(meta, Mapping):
            for field in ("name", "namespace"):
                value = meta.get(field)
                if isinstance(value, str) and value:
                    out[field] = value

    @staticmethod
    def _container_signal(status: Mapping) -> Tuple[Optional[int], Optional[str]]:
        """Total restart count and the first waiting reason, from the pod's
        container statuses. Absent statuses stay absent."""
        statuses = status.get("containerStatuses")
        if not isinstance(statuses, list) or not statuses:
            return None, None
        restarts, waiting = 0, None
        for entry in statuses:
            if not isinstance(entry, Mapping):
                return None, None
            count = entry.get("restartCount")
            restarts += count if isinstance(count, int) else 0
            state = entry.get("state")
            if waiting is None and isinstance(state, Mapping):
                block = state.get("waiting")
                if isinstance(block, Mapping) and isinstance(block.get("reason"), str):
                    waiting = block["reason"]
        return restarts, waiting

    @classmethod
    def _is_crashloop(cls, pod: Any) -> bool:
        if not isinstance(pod, Mapping):
            return False
        status = pod.get("status")
        if not isinstance(status, Mapping):
            return False
        _, waiting = cls._container_signal(status)
        return waiting == "CrashLoopBackOff"


def build_kubernetes_channel(
    *,
    broker: TransportBroker,
    policy: ConnectionPolicy,
    environment: ExecutionEnvironment,
    base_url: str,
) -> ProviderChannel:
    """The channel the Kubernetes API server is reached through. The endpoint is
    deployment configuration — there is deliberately NO default: no universal
    Kubernetes address exists, and a guessed one would be a fabricated
    destination. HTTPS only, refused here as well as by policy: a ServiceAccount
    bearer token on plaintext is exposed on every request (the GitHub channel's
    posture, not Grafana's stated dev exception)."""
    endpoint = TransportEndpoint.parse(
        base_url, transport=TransportKind.HTTPS, environment=environment
    )
    if endpoint.is_plaintext:
        raise ValueError(
            "the Kubernetes API endpoint must be HTTPS; a bearer token on "
            "plaintext is exposed on every request"
        )
    return ProviderChannel(
        provider=KUBERNETES_PROVIDER,
        broker=broker,
        base_endpoint=endpoint,
        policy=policy,
        transport=TransportKind.HTTPS,
    )


def _profile(operation: str, resource_scope: str) -> CapabilityProfile:
    """A READ profile: LOW blast radius, autonomy ceiling A1 (observe/investigate,
    never an action), no verification (nothing to verify), reversible by nature."""
    factors = RiskFactors(side_effect_class=SideEffectClass.READ, environment="development",
                          resource_count=1, reversible=True)
    return CapabilityProfile(
        capability_ref=f"platform.{operation}",
        provider=KUBERNETES_PROVIDER_ID, operation=operation,
        side_effect_class=SideEffectClass.READ, effect_semantics=EffectSemantics.READ_ONLY,
        risk=RiskClassification(level=RiskLevel.LOW, factors=factors,
                                rationale=f"{operation}: read-only cluster observation"),
        autonomy_ceiling=AutonomyLevel.A1_INVESTIGATE,
        verification_requirement=VerificationRequirement.NONE,
        resource_scope=resource_scope, reversible=True, timeout_seconds=_TIMEOUT,
        policy_version=_POLICY_VERSION)


def kubernetes_read_profiles() -> dict:
    """The capability-bridge profiles for each Kubernetes read operation (Part B/C)."""
    scope = {"kubernetes.pods.list": "namespace", "kubernetes.pod.get": "pod",
             "kubernetes.pod.logs": "pod", "kubernetes.deployments.list": "namespace",
             "kubernetes.deployment.get": "deployment", "kubernetes.events.list": "namespace"}
    return {op: _profile(op, scope[op]) for op in KUBERNETES_READ_OPERATIONS}
