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

from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel
from backend.contracts.intelligence.investigation import AutonomyLevel
from backend.contracts.intelligence.capability_profile import (
    CapabilityProfile, VerificationRequirement,
)
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog, ParameterKind, ParameterLocation, ParameterSpec, ProviderOperationSpec,
)

__all__ = [
    "KUBERNETES_PROVIDER_ID",
    "KUBERNETES_READ_OPERATIONS",
    "kubernetes_read_catalog",
    "kubernetes_read_profiles",
]

KUBERNETES_PROVIDER_ID = "kubernetes"
_POLICY_VERSION = "k8s-read-policy/1"

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


def _read(operation: str, path_template: str, *, parameters, evidence,
          required=(_RV,)) -> ProviderOperationSpec:
    return ProviderOperationSpec(
        operation=operation, method="GET", path_template=path_template,
        side_effect_class=SideEffectClass.READ, effect_semantics=EffectSemantics.READ_ONLY,
        parameters=parameters, success_statuses=(200,),
        response_required_fields=required, response_evidence_fields=evidence,
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
