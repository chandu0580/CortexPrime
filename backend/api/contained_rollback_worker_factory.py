"""Compose the CONTAINED rollback worker, or nothing (ADR-124, Phase 11.4).

Loaded through ``CORTEX_CONNECTOR_FACTORIES`` exactly like the restart worker's
factory. It contributes two things and only two:

* the ``ContainedRollbackWorkerAdapter`` and its worker registration, at
  ``IsolationTier.CONTAINED`` -- true because the rollback worker is a separate
  process in a separate container;
* a credential provider for the rollback provider id, holding the token of the
  ServiceAccount that may list ReplicaSets and patch Deployments in exactly one
  namespace.

The credential never reaches the model, the plan, the approval, the envelope or
a log. It enters here, once, at composition, is handed to the existing broker,
and leaves the process only as the transport authorization header of the one
connection to the worker (the platform's single ``reveal()`` call site).

``DevelopmentCredentialProvider`` refuses PRODUCTION, so this factory cannot
quietly become the production credential path; a production deployment needs a
credential adapter behind the same broker (named in ADR-124 as a limitation).
"""

from __future__ import annotations

import os
from typing import Any, Optional

__all__ = ["contained_rollback_worker_extension"]

_WORKER_URL = "CORTEX_ROLLBACK_WORKER_URL"
_TOKEN = "CORTEX_ROLLBACK_WORKER_TOKEN"
_TENANT = "CORTEX_ROLLBACK_WORKER_TENANT"
_CAPABILITY_ID = "CORTEX_ROLLBACK_CAPABILITY_ID"
_CAPABILITY_VERSION = "CORTEX_ROLLBACK_CAPABILITY_VERSION"
_IMPL_DIGEST = "CORTEX_ROLLBACK_IMPL_DIGEST"


def contained_rollback_worker_extension(environment: Any) -> Optional[dict]:
    """Contribute the rollback worker, or ``None`` when it is not configured."""
    url = (os.getenv(_WORKER_URL) or "").strip()
    token = (os.getenv(_TOKEN) or "").strip()
    digest = (os.getenv(_IMPL_DIGEST) or "").strip()
    capability_id = (os.getenv(_CAPABILITY_ID) or "").strip()
    tenant_id = (os.getenv(_TENANT) or "").strip()
    if not (url and token and digest and capability_id and tenant_id):
        # Partially configured is not configured: a worker nobody can address, or
        # one bound to no tenant, is refused rather than composed.
        return None
    try:
        version = int((os.getenv(_CAPABILITY_VERSION) or "1").strip())
    except ValueError:
        return None

    from backend.api.capability_execution_composition import (
        CONTAINED_ROLLBACK_PROVIDER_ID,
        build_contained_rollback_worker_connector,
    )
    from backend.platform.credentials import DevelopmentCredentialProvider

    def connector_builder(*, transport_broker: Any, connection_policy: Any, environment: Any,
                          preflight: Any = None, metrics: Any = None) -> tuple:
        return build_contained_rollback_worker_connector(
            transport_broker=transport_broker, connection_policy=connection_policy,
            environment=environment, worker_url=url, capability_id=capability_id,
            capability_version=version, implementation_digest=digest,
            preflight=preflight, metrics=metrics,
        )

    return {
        "connectors": [connector_builder],
        "credential_providers": [
            DevelopmentCredentialProvider(
                provider_id=CONTAINED_ROLLBACK_PROVIDER_ID,
                # Keyed by the ONE tenant the worker is bound to. Another
                # tenant's execution gets no credential here at all.
                secrets={tenant_id: token},
                allow_non_production=True,
                environments=frozenset({environment}),
            )
        ],
    }
