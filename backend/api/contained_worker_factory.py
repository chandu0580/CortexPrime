"""Compose the CONTAINED Kubernetes worker, or nothing (ADR-089, Phase 9.9B).

Loaded through ``CORTEX_CONNECTOR_FACTORIES`` exactly like the Kubernetes,
Grafana and Prometheus factories. It contributes two things and only two:

* the ``ContainedWorkerAdapter`` and its worker registration, at
  ``IsolationTier.CONTAINED`` -- true because the thing it dispatches to is a
  separate process in a separate container;
* a credential provider for the contained provider id, holding the ServiceAccount
  token that may patch deployments in exactly one namespace.

Why the credential lives here and not in the worker
---------------------------------------------------
The worker holds no standing credential for the action. The token arrives per
execution, through the existing broker, as the transport authorization header --
the platform's single ``reveal()`` call site. So a worker that is idle holds
nothing worth stealing, and the credential's lifetime is the request's.

The connector module itself never reads the environment; only this factory does,
and only here. Same shape as ``kubernetes_provider_factory``: this is
CortexPrime's own credential to a piece of its own deployment infrastructure,
entering once, at composition, in the composition layer.

``DevelopmentCredentialProvider`` refuses PRODUCTION four ways over, so this
factory cannot quietly become the production credential path. Phase 5.5 remains
blocked and untouched.
"""

from __future__ import annotations

import os
from typing import Any, Optional

__all__ = ["contained_worker_extension"]

#: Deployment configuration. Every one is required: a partially configured
#: contained worker would be a worker nobody could address, bound to nothing.
_WORKER_URL = "CORTEX_P99B_WORKER_URL"
_RESTART_TOKEN = "CORTEX_P99B_RESTART_TOKEN"
_TENANT = "CORTEX_P99B_TENANT"
_CAPABILITY_ID = "CORTEX_P99B_CAPABILITY_ID"
_CAPABILITY_VERSION = "CORTEX_P99B_CAPABILITY_VERSION"
_IMPL_DIGEST = "CORTEX_P99B_IMPL_DIGEST"


def contained_worker_extension(environment: Any) -> Optional[dict]:
    """Contribute the contained worker, or ``None`` when it is not configured.

    A deployment that names this factory but provisions nothing gets a process
    without a contained worker rather than a contained worker that cannot
    authenticate or cannot be addressed.
    """
    url = (os.getenv(_WORKER_URL) or "").strip()
    token = (os.getenv(_RESTART_TOKEN) or "").strip()
    digest = (os.getenv(_IMPL_DIGEST) or "").strip()
    capability_id = (os.getenv(_CAPABILITY_ID) or "").strip()
    if not (url and token and digest and capability_id):
        return None

    tenant_id = (os.getenv(_TENANT) or "dev").strip()
    try:
        version = int((os.getenv(_CAPABILITY_VERSION) or "1").strip())
    except ValueError:
        return None

    from backend.api.capability_execution_composition import (
        CONTAINED_KUBERNETES_PROVIDER_ID,
        build_contained_worker_connector,
    )
    from backend.platform.credentials import DevelopmentCredentialProvider

    def connector_builder(
        *,
        transport_broker: Any,
        connection_policy: Any,
        environment: Any,
        preflight: Any = None,
        metrics: Any = None,
    ) -> tuple:
        return build_contained_worker_connector(
            transport_broker=transport_broker,
            connection_policy=connection_policy,
            environment=environment,
            worker_url=url,
            capability_id=capability_id,
            capability_version=version,
            implementation_digest=digest,
            preflight=preflight,
            metrics=metrics,
        )

    return {
        "connectors": [connector_builder],
        "credential_providers": [
            DevelopmentCredentialProvider(
                provider_id=CONTAINED_KUBERNETES_PROVIDER_ID,
                secrets={tenant_id: token},
                allow_non_production=True,
                environments=frozenset({environment}),
            )
        ],
    }
