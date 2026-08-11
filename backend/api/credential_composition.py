"""Composition root: the credential fabric meets Execution's seam.

What crosses here
-------------------
Execution declares ``CredentialProvider`` and never implements it. The platform
fabric implements issuance and knows nothing about executions. This module is the
only place the two meet, and what crosses is a ``CredentialRequest`` in and an
``IssuedCredential`` out — no vendor type, no provider client, no execution
aggregate.

The revalidator is the interesting part
-----------------------------------------
``GatewayAuthorityRevalidator`` re-reads the authority chain immediately before a
credential is minted. That closes a window the gateway alone cannot: the gateway
admits an invocation, and between admission and the credential being issued a
capability can be revoked or a binding invalidated. Minting after that produces a
live credential for something no longer permitted — and unlike a refused
invocation, a minted credential exists at the provider whether or not we use it.

No vendor adapter is wired
----------------------------
Vault, AWS Secrets Manager, Azure Key Vault and OAuth brokers are all
implementations of ``CredentialAdapter``, and **none is built in Phase 4.1**.
``build_credential_broker`` assembles an empty broker: every acquisition refuses
with ``credential_no_provider``, which is correct for a platform with no
credential source. There is no default and no fallback to invent one.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from backend.contracts.execution import ExecutionEnvironment
from backend.platform.credentials import (
    CredentialAdapter,
    CredentialBroker,
    CredentialRefused,
    CredentialRequest,
    DevelopmentCredentialProvider,
)

__all__ = [
    "BrokerCredentialProvider",
    "GatewayAuthorityRevalidator",
    "build_credential_broker",
    "build_development_broker",
]

log = logging.getLogger(__name__)


class BrokerCredentialProvider:
    """Execution's ``CredentialProvider``, answered by the platform broker.

    The whole adapter. Execution asks for a credential for an action; the broker
    decides. Nothing is translated, because both sides already speak
    ``CredentialRequest`` — which is the point of putting that type in the
    platform rather than in either context.
    """

    def __init__(self, broker: CredentialBroker) -> None:
        if not isinstance(broker, CredentialBroker):
            raise ValueError("a credential provider must be backed by the broker")
        self._broker = broker

    def scoped_credential(self, context: Any, request: Any) -> Any:
        """Acquire for one invocation. Refusals travel with their reason code."""
        if not isinstance(request, CredentialRequest):
            raise CredentialRefused(
                __import__(
                    "backend.platform.credentials", fromlist=["CredentialRefusal"]
                ).CredentialRefusal.REQUEST_INCOMPLETE,
                "a credential requires a fully-formed request",
            )
        # Tenancy is checked against the caller's context as well as the
        # request's own fields. The request could be built by anything; the
        # context was authenticated.
        tenant = getattr(context, "tenant_id", None)
        if not tenant or tenant != request.tenant_id:
            from backend.platform.credentials import CredentialRefusal

            raise CredentialRefused(
                CredentialRefusal.TENANT_MISMATCH,
                "the credential request names a tenant the context did not "
                "authenticate",
                correlation_id=request.correlation_id,
            )
        return self._broker.acquire(request)


class GatewayAuthorityRevalidator:
    """Re-reads capability and binding authority just before a credential is minted.

    Implements the broker's ``AuthorityRevalidator`` over the same Connectivity
    service the gateway consults (ADR-035 ``validate_binding``), so this is a
    re-read rather than a second opinion. Returning a non-empty tuple refuses.

    Fails closed in every direction: no service wired, the lookup raising, or the
    binding missing all produce refusal reasons rather than an empty tuple.
    """

    def __init__(self, resolution_service: Any, *, context_factory: Any = None) -> None:
        self._resolution = resolution_service
        self._context_factory = context_factory

    def still_valid(self, request: CredentialRequest) -> tuple:
        if self._resolution is None or self._context_factory is None:
            return ("authority_unverifiable",)
        try:
            context = self._context_factory()
            stored = self._resolution._bindings.find(  # noqa: SLF001
                context, request.binding_id
            )
            if stored is None:
                return ("binding_not_found",)
            if stored.digest != request.binding_digest:
                return ("binding_digest_mismatch",)
            return tuple(
                str(reason)
                for reason in self._resolution.validate_binding(
                    context,
                    stored,
                    tenant_id=request.tenant_id,
                    principal_id=request.principal_id,
                    execution_id=request.execution_id,
                    node_id=request.node_id,
                )
            )
        except Exception:  # noqa: BLE001 - unverifiable is unusable
            log.warning("credential authority revalidation failed", exc_info=False)
            return ("authority_unverifiable",)


def build_credential_broker(
    *,
    adapters: Optional[Mapping[str, CredentialAdapter]] = None,
    resolution_service: Any = None,
    context_factory: Any = None,
    audit: Optional[Any] = None,
    metrics: Optional[Any] = None,
    clock: Optional[Any] = None,
) -> CredentialBroker:
    """Assemble the broker. Empty by default, and that is the correct default.

    With no adapters every acquisition refuses ``credential_no_provider``. A
    platform with no credential source should refuse rather than find one, and
    there is deliberately no environment-variable path, no ambient store, and no
    default adapter to fall back to.
    """
    return CredentialBroker(
        adapters=adapters,
        revalidator=(
            GatewayAuthorityRevalidator(
                resolution_service, context_factory=context_factory
            )
            if resolution_service is not None
            else None
        ),
        audit=audit,
        metrics=metrics,
        clock=clock,
    )


def build_development_broker(
    *,
    provider_id: str,
    secrets_by_tenant: Mapping[str, str],
    environment: ExecutionEnvironment = ExecutionEnvironment.DEVELOPMENT,
    **kwargs: Any,
) -> CredentialBroker:
    """A broker with a development adapter attached. **Never for production.**

    A separate function rather than a flag on ``build_credential_broker``,
    because a flag is something a configuration file can set by accident and a
    differently-named function is something a person has to type. It refuses
    ``PRODUCTION`` here, and the adapter refuses it again at construction and a
    third time at acquisition.
    """
    if environment is ExecutionEnvironment.PRODUCTION:
        raise ValueError(
            "build_development_broker cannot serve production; use "
            "build_credential_broker with a real adapter"
        )
    broker = build_credential_broker(**kwargs)
    broker.register(
        DevelopmentCredentialProvider(
            provider_id=provider_id,
            secrets=secrets_by_tenant,
            allow_non_production=True,
            environments=frozenset({environment}),
        )
    )
    return broker
