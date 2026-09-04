"""The Prometheus deployment factory — Phase 9.4 (ADR-084).

Loaded through ``CORTEX_CONNECTOR_FACTORIES``, the same seam every other provider
arrives through. That seam takes a comma-separated list, which is what lets a
deployment compose Kubernetes *and* Prometheus into one process — and composing
both is the entire point of this phase: two governed providers, two instruments,
one World Plane deciding whether they independently support a proposition.

The credential, stated
------------------------
``CORTEX_PROMETHEUS_TOKEN`` is a bearer token for the reverse proxy in front of
Prometheus — the same trust shape as ``CORTEX_GRAFANA_TOKEN`` and
``CORTEX_KUBERNETES_TOKEN``: CortexPrime's own credential to a piece of its
deployment infrastructure, entering once, at composition, in the composition
layer. The connector itself never reads the environment; only this module does,
and only here.

Prometheus has no native bearer authentication, so a real deployment puts it
behind a proxy that does. That is not a workaround for the governed path — the
credential broker refuses per provider ("no credential adapter is registered for
this provider; there is no default credential and no fallback"), so a provider
reached with no credential is a provider that cannot be read at all. The proxy is
what makes the credential do real work and makes a 401 a real refusal.

The observed namespace is deployment configuration
----------------------------------------------------
``CORTEX_PROMETHEUS_NAMESPACE`` is compiled into the catalog's declared PromQL at
composition. It is not an invocation parameter and there is no code path that
makes it one: a catalog built for one namespace cannot read another.
"""

from __future__ import annotations

import os
from typing import Any, Optional

__all__ = ["prometheus_extension", "PROMETHEUS_PROVIDER_ID"]

from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
    PROMETHEUS_PROVIDER_ID,
)

_URL = "CORTEX_PROMETHEUS_URL"
_TOKEN = "CORTEX_PROMETHEUS_TOKEN"
_TENANT = "CORTEX_PROMETHEUS_TENANT"
_NAMESPACE = "CORTEX_PROMETHEUS_NAMESPACE"
_FALLBACK_NAMESPACE = "CORTEX_P94_NAMESPACE"


def prometheus_extension(environment: Any) -> Optional[dict]:
    """Contribute the governed Prometheus read connector and its credential.

    Returns ``None`` when either the address or the token is unconfigured — a
    deployment that names this factory but provisions neither gets a process
    without Prometheus rather than a Prometheus that cannot authenticate.
    """
    url = (os.getenv(_URL) or "").strip()
    token = (os.getenv(_TOKEN) or "").strip()
    if not url or not token:
        return None

    from backend.api.capability_execution_composition import build_prometheus_connector
    from backend.platform.credentials import DevelopmentCredentialProvider

    tenant_id = (os.getenv(_TENANT) or "dev").strip()
    namespace = (os.getenv(_NAMESPACE) or os.getenv(_FALLBACK_NAMESPACE) or "").strip()
    if not namespace:
        raise RuntimeError(
            "a Prometheus catalog is scoped to one observed namespace and none "
            "is configured; set CORTEX_PROMETHEUS_NAMESPACE. An unscoped catalog "
            "would read whatever the whole cluster reports, which is a different "
            "capability than the one anybody approved"
        )

    def connector_builder(
        *,
        transport_broker: Any,
        connection_policy: Any,
        environment: Any,
        preflight: Any = None,
        metrics: Any = None,
    ) -> tuple:
        return build_prometheus_connector(
            transport_broker=transport_broker,
            connection_policy=connection_policy,
            environment=environment,
            base_url=url,
            namespace=namespace,
            preflight=preflight,
            metrics=metrics,
        )

    return {
        "connectors": [connector_builder],
        "credential_providers": [
            DevelopmentCredentialProvider(
                provider_id=PROMETHEUS_PROVIDER_ID,
                secrets={tenant_id: token},
                allow_non_production=True,
                environments=frozenset({environment}),
            )
        ],
    }
