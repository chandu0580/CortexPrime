"""A SCRIPTED Kubernetes provider for Phase 9.1 evidence.

Loaded through ``CORTEX_CONNECTOR_FACTORIES`` exactly like the controlled/Grafana
factories. It composes the REAL governed Kubernetes READ catalog
(`kubernetes_read_catalog`) with a `TestProviderAdapter` (ADR-042 §testing): the
adapter runs every gate of the real fabric — authority, TOCTOU re-read,
credential-for-this-digest, input validation, effect comparison — and answers with
deterministic, K8s-shaped, NORMALIZED bodies (resourceVersion lifted to the top
level) instead of a network call.

Honest label (Part O): this is a SCRIPTED provider. It proves the governed
capability path — capability → authorization → lease → gateway → provider →
observation — and the resourceVersion data contract, WITHOUT contacting a real
cluster. The real HTTPS-to-API-server adapter is DEFERRED (no cluster/credential
available; Phase 5.5 class). This factory refuses PRODUCTION (via the adapter) and
is enabled only by ``CORTEX_KUBERNETES_SCRIPTED``. It performs NO Kubernetes
mutation and cannot: the catalog declares only READ operations.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
    KUBERNETES_PROVIDER_ID, kubernetes_read_catalog,
)

__all__ = ["kubernetes_scripted_extension", "KUBERNETES_PROVIDER_ID"]

_ENABLE = "CORTEX_KUBERNETES_SCRIPTED"
_TENANT = "CORTEX_CONTROLLED_TENANT"


def _responder(authority: Any):
    """Deterministic, normalized K8s-shaped answers keyed by operation. Every
    envelope carries a top-level ``resourceVersion`` (Part F). The pod scenario is a
    CrashLoopBackOff; the deployment has 0 ready replicas — the first vertical's
    signal. Never fabricates a resourceVersion for the logs op (no envelope)."""
    op = authority.operation
    if op == "kubernetes.pods.list":
        return {"body": {"resourceVersion": "100241", "kind": "PodList", "apiVersion": "v1",
                         "podCount": 3, "crashLoopCount": 1,
                         "items": [{"name": "payments-abc", "phase": "Running",
                                    "restartCount": 7, "waitingReason": "CrashLoopBackOff"}]}}
    if op == "kubernetes.pod.get":
        return {"body": {"resourceVersion": "100242", "kind": "Pod", "name": "payments-abc",
                         "namespace": "payments", "phase": "Running", "restartCount": 7,
                         "waitingReason": "CrashLoopBackOff"}}
    if op == "kubernetes.pod.logs":
        return {"body": {"name": "payments-abc", "lineCount": 12,
                         "log": "Error: connection refused\n" * 3}}
    if op == "kubernetes.deployments.list":
        return {"body": {"resourceVersion": "100243", "kind": "DeploymentList",
                         "apiVersion": "apps/v1", "deploymentCount": 1}}
    if op == "kubernetes.deployment.get":
        return {"body": {"resourceVersion": "100244", "kind": "Deployment", "name": "payments",
                         "namespace": "payments", "replicas": 3, "readyReplicas": 0,
                         "availableReplicas": 0}}
    if op == "kubernetes.events.list":
        return {"body": {"resourceVersion": "100245", "kind": "EventList", "apiVersion": "v1",
                         "eventCount": 4}}
    return {}


def _build_kubernetes_connector(
    *, transport_broker=None, connection_policy=None, environment,
    preflight=None, metrics=None,
):
    from backend.contracts.connector import IsolationTier
    from backend.contracts.provider import ProviderRef
    from backend.contexts.execution import WorkerEntry, WorkerInterface, WorkerScope
    from backend.contexts.execution.domain.worker import WorkerKind
    from backend.contexts.execution.domain.worker_directory import WorkerImplementation
    from backend.contexts.execution.infrastructure.adapters.testing import TestProviderAdapter

    catalog = kubernetes_read_catalog()
    provider = ProviderRef(provider_id=KUBERNETES_PROVIDER_ID)
    implementation = WorkerImplementation(
        worker_id="kubernetes-connector", worker_kind=WorkerKind.CONNECTOR,
        interface=WorkerInterface.CONNECTOR,
        implementation="backend.contexts.execution.infrastructure.adapters.testing.TestProviderAdapter",
        implementation_version="0.0.0-scripted", isolation=IsolationTier.CONTAINED,
        scope=WorkerScope.PLATFORM, supported_environments=frozenset({environment}),
        supported_effects=frozenset(
            {catalog.require(op).effect_semantics for op in catalog.operations}),
        supported_providers=frozenset({KUBERNETES_PROVIDER_ID}),
        supported_operations=frozenset(catalog.operations),
        supports_provider_idempotency=False)
    adapter = TestProviderAdapter(
        implementation=implementation, provider=provider, catalog=catalog,
        allow_non_production=True, responder=_responder,
        environments=frozenset({environment}), preflight=preflight, metrics=metrics)
    return WorkerEntry(implementation=implementation), adapter, catalog


def kubernetes_scripted_extension(environment: Any) -> Optional[dict]:
    """Contribute the SCRIPTED Kubernetes provider + a development credential, or
    None when ``CORTEX_KUBERNETES_SCRIPTED`` is not set."""
    if (os.getenv(_ENABLE) or "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    from backend.platform.credentials import DevelopmentCredentialProvider
    tenant_id = (os.getenv(_TENANT) or "dev").strip()
    return {
        "connectors": [_build_kubernetes_connector],
        "credential_providers": [
            DevelopmentCredentialProvider(
                provider_id=KUBERNETES_PROVIDER_ID,
                secrets={tenant_id: "kubernetes-scripted-token"},
                allow_non_production=True, environments=frozenset({environment}))
        ],
    }
