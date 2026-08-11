"""The Grafana deployment factory — Phase 6.1's second declared provider.

Loaded through ``CORTEX_CONNECTOR_FACTORIES`` (the seam ADR-058 built for
exactly this), so a deployment that wants Grafana names this module in
configuration and one that does not never composes it. The connector itself is
returned as a *builder* so it is constructed with the production composition's
own transport broker and connection policy — never a second broker.

Bootstrap secret, stated
--------------------------
``CORTEX_GRAFANA_TOKEN`` is a Grafana service-account token the operator
provisions and exports — the same trust shape as ``VAULT_TOKEN`` (ADR-040):
CortexPrime's own credential to a piece of its deployment infrastructure,
entering once, at composition, in the composition layer. It is handed to a
``DevelopmentCredentialProvider``, which refuses production four ways over,
so this factory cannot quietly become the production credential path.
"""

from __future__ import annotations

import os
from typing import Any, Optional

__all__ = ["grafana_extension"]

TOKEN_VARIABLE = "CORTEX_GRAFANA_TOKEN"
TENANT_VARIABLE = "CORTEX_GRAFANA_TENANT"
BASE_URL_VARIABLE = "CORTEX_GRAFANA_URL"


def grafana_extension(environment: Any) -> Optional[dict]:
    """Contribute the Grafana connector and its development credential.

    Returns ``None`` (contributing nothing) when no token is configured —
    a deployment that names this factory but provisions no token gets a
    process without Grafana rather than a Grafana that cannot authenticate.
    """
    token = (os.getenv(TOKEN_VARIABLE) or "").strip()
    if not token:
        return None

    from backend.api.capability_execution_composition import build_grafana_connector
    from backend.platform.credentials import DevelopmentCredentialProvider

    tenant_id = (os.getenv(TENANT_VARIABLE) or "dev").strip()
    base_url = (os.getenv(BASE_URL_VARIABLE) or "").strip() or None

    def connector_builder(
        *,
        transport_broker: Any,
        connection_policy: Any,
        environment: Any,
        preflight: Any = None,
        metrics: Any = None,
    ) -> tuple:
        return build_grafana_connector(
            transport_broker=transport_broker,
            connection_policy=connection_policy,
            environment=environment,
            base_url=base_url,
            preflight=preflight,
            metrics=metrics,
        )

    return {
        "connectors": [connector_builder],
        "credential_providers": [
            DevelopmentCredentialProvider(
                provider_id="grafana",
                secrets={tenant_id: token},
                allow_non_production=True,
                environments=frozenset({environment}),
            )
        ],
    }
