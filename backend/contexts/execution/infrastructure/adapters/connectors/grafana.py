"""Grafana: the second declared provider, and the Phase 6.1 vertical-slice target.

Why Grafana for the first governed write
------------------------------------------
Phase 5.5's GitHub credential remains blocked, and the Phase 6.1 slice needs a
provider that can take a **real, observable, reversible** write on this
machine without touching that boundary. Grafana is in the repository's own
docker-compose (``cortex-grafana``), speaks a conventional REST API over HTTP,
authenticates with one bearer token (a service-account token the operator
provisions), and offers an operation pair that is honest under Constitution
P2: ``POST /api/folders`` has a complete declared inverse
(``DELETE /api/folders/{uid}``), so ``REVERSIBLE_WRITE`` is a statement of
fact, not optimism — unlike every write in the GitHub catalog.

Everything Grafana-specific lives here and nowhere else — the same rule as the
GitHub reference connector. The adapter is the generic ``ConnectorAdapter``;
this file contributes a catalog, a thin translator, and a channel builder.

Plaintext, stated
-------------------
The dev deployment reaches Grafana at ``http://localhost``. Plaintext is a
per-policy exception the deployment states (``allow_plaintext``,
non-production only — the policy refuses it in production four ways over), and
this channel builder additionally refuses plaintext unless the policy
explicitly carries the exception. The exposure is a local service-account
token on a loopback interface, stated rather than hidden.

The catalog is two operations
-------------------------------
Create a folder; read it back. The smallest vocabulary that proves the whole
governed chain: a write the gateway must authorize, and an independent read
the observation leg re-checks the world with. No list operation — "show me
everything this token reaches" is the shape that turns a shared instance into
a cross-tenant read (the GitHub tenancy rule, applied here by ``uid`` being a
required, validated, digested path parameter).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from backend.contracts.execution import (
    EffectSemantics,
    ExecutionEnvironment,
    SideEffectClass,
)
from backend.contracts.provider import ProviderFailure, ProviderRef
from backend.contracts.transport import TransportKind
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog,
    ParameterKind,
    ParameterLocation,
    ParameterSpec,
    ProviderOperationSpec,
)
from backend.contexts.execution.infrastructure.adapters.channel import ProviderChannel
from backend.contexts.execution.infrastructure.adapters.connector import (
    HttpStatusTranslator,
)
from backend.platform.transport import ConnectionPolicy, TransportBroker, TransportEndpoint

__all__ = [
    "GRAFANA_PROVIDER_ID",
    "GRAFANA_PROVIDER",
    "GRAFANA_API_BASE",
    "GRAFANA_SCOPES",
    "GrafanaResponseTranslator",
    "grafana_catalog",
    "build_grafana_channel",
]

GRAFANA_PROVIDER_ID = "grafana"
GRAFANA_PROVIDER = ProviderRef(provider_id=GRAFANA_PROVIDER_ID)

#: The compose default: host port 3001 → container 3000. Deployment
#: configuration, never request input. A literal address, deliberately: the
#: transport broker refuses loopback *aliases* ("localhost") unconditionally —
#: a resolver that answers oddly must not matter — while a literal loopback
#: address is judged against the policy's address classes, which permit
#: LOOPBACK outside production.
GRAFANA_API_BASE = "http://127.0.0.1:3001"

GRAFANA_SCOPES: Mapping[str, Tuple[str, ...]] = {
    "folder.create_folder": ("folders:create",),
    "folder.get_folder": ("folders:read",),
}

_GRAFANA_HEADERS = {
    "accept": "application/json",
    "user-agent": "CortexPrime-ConnectorAdapter/1.0",
}

#: Grafana folder UIDs: 40 chars max, conservative charset enforced by the
#: parameter kind. Required on both operations so the write and the read-back
#: name the same resource, and the resource is part of the action digest.
_FOLDER_UID = ParameterSpec(
    name="uid",
    kind=ParameterKind.RESOURCE_SEGMENT,
    location=ParameterLocation.PATH,
    max_length=40,
)


class GrafanaResponseTranslator(HttpStatusTranslator):
    """Grafana departs from convention in one place worth naming: conflicts on
    folder creation (same uid or same title) return 409/412 with a ``message``
    field. The default status mapping already classifies both correctly; this
    translator only extracts the bounded message so an operator sees "a folder
    with that name already exists" instead of a bare status code."""

    def describe(self, exchange: Any, body: Any) -> Tuple[Optional[str], Optional[str]]:
        code, reason = super().describe(exchange, body)
        if isinstance(body, Mapping):
            message = body.get("message")
            if isinstance(message, str) and message.strip():
                return code, message.strip()[:200]
        return code, reason


def grafana_catalog() -> OperationCatalog:
    """Two operations, and no others."""
    return OperationCatalog(
        GRAFANA_PROVIDER_ID,
        (
            ProviderOperationSpec(
                operation="folder.create_folder",
                method="POST",
                path_template="/api/folders",
                # REVERSIBLE_WRITE as a fact: ``DELETE /api/folders/{uid}``
                # removes exactly what this created, restoring the prior
                # state completely. That inverse is deliberately NOT in this
                # catalog — nobody has decided to allow the platform to
                # delete folders; reversibility describes the action, not a
                # capability grant.
                side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
                # Non-idempotent, honestly: the same title posted twice is a
                # 409/412, and posting without a uid mints a fresh folder.
                # Grafana reads no idempotency key, so Execution's retry
                # rules must know a blind retry is not safe.
                effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
                parameters=(
                    ParameterSpec(
                        name="title",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.BODY,
                        max_length=189,
                    ),
                    ParameterSpec(
                        name="uid",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.BODY,
                        required=False,
                        max_length=40,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("uid", "title"),
                response_evidence_fields=("id", "uid", "title", "url"),
                static_headers=_GRAFANA_HEADERS,
                provider_timeout_seconds=15.0,
                max_response_bytes=1 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="folder.get_folder",
                method="GET",
                path_template="/api/folders/{uid}",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(_FOLDER_UID,),
                success_statuses=(200,),
                response_required_fields=("uid", "title"),
                response_evidence_fields=("id", "uid", "title", "url"),
                static_headers=_GRAFANA_HEADERS,
                provider_timeout_seconds=15.0,
                max_response_bytes=1 * 1024 * 1024,
            ),
        ),
    )


def build_grafana_channel(
    *,
    broker: TransportBroker,
    policy: ConnectionPolicy,
    environment: ExecutionEnvironment,
    base_url: str = GRAFANA_API_BASE,
) -> ProviderChannel:
    """The channel Grafana is reached through. Destination from configuration.

    Plaintext is permitted **only** when the policy explicitly carries the
    exception (which the policy itself refuses in production). Refused here as
    well as by policy so a deployment that never stated the exception cannot
    reach a plaintext Grafana by accident — the same double-refusal shape as
    the GitHub channel, with the opposite default rationale documented.
    """
    endpoint = TransportEndpoint.parse(
        base_url, transport=TransportKind.HTTPS, environment=environment
    )
    if endpoint.is_plaintext and not getattr(policy.tls, "allow_plaintext", False):
        raise ValueError(
            "the Grafana endpoint is plaintext and this policy does not state "
            "the plaintext exception; a bearer token on plaintext is exposed "
            "on every request"
        )
    return ProviderChannel(
        provider=GRAFANA_PROVIDER,
        broker=broker,
        base_endpoint=endpoint,
        policy=policy,
        transport=TransportKind.HTTPS,
    )
