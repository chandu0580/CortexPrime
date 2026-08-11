"""A controlled (scripted) provider for Phase 6.2 real-process evidence.

Loaded through ``CORTEX_CONNECTOR_FACTORIES`` exactly like the Grafana factory,
but the adapter is ``TestProviderAdapter`` (ADR-042 §testing): it runs every
gate of the real fabric — authority, TOCTOU re-read, credential-for-this-digest,
input validation, effect comparison, ambiguity — and answers from a script
instead of a network. That makes crash/recovery and replay evidence
**deterministic and countable** without contacting any external system, which
is what Part O asks for (controlled providers acceptable; real external contact
BLOCKED).

It refuses PRODUCTION four ways over (construction, registration, and twice at
invocation), so this factory cannot become a production execution path.

The controlled catalog is two operations mirroring the Grafana shape: one
``REVERSIBLE_WRITE`` and one ``READ``, so a governed write can be crashed
mid-flight and a governed read can prove replay performs nothing.
"""

from __future__ import annotations

import os
from typing import Any, Optional

__all__ = ["controlled_extension", "CONTROLLED_PROVIDER_ID"]

CONTROLLED_PROVIDER_ID = "controlled"
_ENABLE = "CORTEX_CONTROLLED_PROVIDER"
_TENANT = "CORTEX_CONTROLLED_TENANT"


def _controlled_catalog():
    from backend.contracts.execution import EffectSemantics, SideEffectClass
    from backend.contexts.execution.domain.provider_operation import (
        OperationCatalog,
        ParameterKind,
        ParameterLocation,
        ParameterSpec,
        ProviderOperationSpec,
    )

    return OperationCatalog(
        CONTROLLED_PROVIDER_ID,
        (
            ProviderOperationSpec(
                operation="widget.create",
                method="POST",
                path_template="/widgets",
                side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
                effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
                parameters=(
                    ParameterSpec(
                        name="name", kind=ParameterKind.STRING,
                        location=ParameterLocation.BODY, max_length=80,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("id",),
                response_evidence_fields=("id", "name"),
                provider_timeout_seconds=15.0,
                max_response_bytes=64 * 1024,
            ),
            ProviderOperationSpec(
                operation="widget.get",
                method="GET",
                path_template="/widgets/{widget_id}",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    ParameterSpec(
                        name="widget_id", kind=ParameterKind.RESOURCE_SEGMENT,
                        location=ParameterLocation.PATH, max_length=40,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("id",),
                response_evidence_fields=("id", "name"),
                provider_timeout_seconds=15.0,
                max_response_bytes=64 * 1024,
            ),
        ),
    )


def _responder(authority: Any):
    """Deterministic scripted answers, keyed by operation."""
    if authority.operation == "widget.create":
        payload = authority.payload or {}
        return {"body": {"id": "w-1", "name": payload.get("name", "widget")}}
    if authority.operation == "widget.get":
        return {"body": {"id": "w-1", "name": "widget"}}
    return {}


def _build_controlled_connector(
    *, transport_broker=None, connection_policy=None, environment,
    preflight=None, metrics=None,
):
    from backend.contracts.connector import IsolationTier
    from backend.contracts.provider import ProviderRef
    from backend.contexts.execution import WorkerEntry, WorkerInterface, WorkerScope
    from backend.contexts.execution.domain.worker import WorkerKind
    from backend.contexts.execution.domain.worker_directory import WorkerImplementation
    from backend.contexts.execution.infrastructure.adapters.testing import (
        TestProviderAdapter,
    )

    catalog = _controlled_catalog()
    provider = ProviderRef(provider_id=CONTROLLED_PROVIDER_ID)
    implementation = WorkerImplementation(
        worker_id="controlled-connector",
        worker_kind=WorkerKind.CONNECTOR,
        interface=WorkerInterface.CONNECTOR,
        implementation="backend.contexts.execution.infrastructure.adapters.testing.TestProviderAdapter",
        implementation_version="0.0.0-test",
        isolation=IsolationTier.CONTAINED,
        scope=WorkerScope.PLATFORM,
        supported_environments=frozenset({environment}),
        supported_effects=frozenset(
            {catalog.require(op).effect_semantics for op in catalog.operations}
        ),
        supported_providers=frozenset({CONTROLLED_PROVIDER_ID}),
        supported_operations=frozenset(catalog.operations),
        supports_provider_idempotency=False,
    )
    adapter = TestProviderAdapter(
        implementation=implementation,
        provider=provider,
        catalog=catalog,
        allow_non_production=True,
        responder=_responder,
        environments=frozenset({environment}),
        preflight=preflight,
        metrics=metrics,
    )
    return WorkerEntry(implementation=implementation), adapter, catalog


def controlled_extension(environment: Any) -> Optional[dict]:
    """Contribute the controlled provider + a development credential, or None
    when ``CORTEX_CONTROLLED_PROVIDER`` is not set."""
    if (os.getenv(_ENABLE) or "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None

    from backend.platform.credentials import DevelopmentCredentialProvider

    tenant_id = (os.getenv(_TENANT) or "dev").strip()
    return {
        "connectors": [_build_controlled_connector],
        "credential_providers": [
            DevelopmentCredentialProvider(
                provider_id=CONTROLLED_PROVIDER_ID,
                secrets={tenant_id: "controlled-scripted-secret"},
                allow_non_production=True,
                environments=frozenset({environment}),
            )
        ],
    }
