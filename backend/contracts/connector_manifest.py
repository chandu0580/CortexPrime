"""The connector manifest: what a governed connector declares about itself.

Why this exists (Phase 11.1-K)
--------------------------------
Until now a connector's capabilities existed in three places that nobody tied
together: an ``OperationCatalog`` (request shape), a ``CapabilityProfile`` (risk,
autonomy ceiling, verification) and -- in every test harness, separately -- a
hand-written ``RegisterCapability`` loop that committed a thin contract to the
durable registry (no schema, no permissions, no timeout). Nothing registered a
connector's capabilities at startup, so a production process had none until a
script ran (connector reality audit, section 11).

A manifest is the one declaration a connector ships. The generic registrar
(``backend.api.connector_commissioning``) turns it into full durable
capability contracts at boot -- idempotently, and refusing silent drift -- and
the connector health contract reads the same manifest to decide which
permissions a connection must hold.

What a manifest is not
------------------------
Not a second capability model: every field maps onto an existing one
(``RegisterCapability``, ``CapabilityProfile``, ``ProviderOperationSpec``).
Not authority: registering a capability grants nobody the right to invoke it;
authorization, approval and the gateway still decide every invocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "RetryClass",
    "CapabilityManifest",
    "ConnectorManifest",
]


class RetryClass(str, Enum):
    """What the platform may do when an attempt fails transiently.

    Derived from the operation's effect semantics, never chosen by a caller:
    a read may be repeated; a write whose outcome is unknown is reconciled by
    reading the world, never by trying again (ADR-031, ADR-124 D-10).
    """

    SAFE = "safe"
    NEVER = "never"


@dataclass(frozen=True)
class CapabilityManifest:
    """One capability a connector offers."""

    capability_id: str
    version: int
    operation: str
    provider: str
    description: str
    category: str
    profile: Any
    required_permissions: tuple = ()
    target_parameter: Optional[str] = "namespace"
    """The payload field naming the target the connection scope constrains
    (``namespace`` for Kubernetes). ``None`` for a capability with no target."""

    def __post_init__(self) -> None:
        if not self.capability_id.startswith("platform."):
            raise ContractViolation("a shipped connector capability id starts with 'platform.'")
        if self.version < 1:
            raise ContractViolation("capability versions start at 1")
        if not self.description.strip():
            raise ContractViolation(
                "a capability without a description is one no agent can choose correctly")
        for permission in self.required_permissions:
            if not isinstance(permission, str) or permission.count(":") < 2:
                raise ContractViolation(
                    "a required permission is '<provider>:<resource>:<verb>'")
        if getattr(self.profile, "operation", self.operation) != self.operation:
            raise ContractViolation("the profile describes a different operation")

    @property
    def mutates(self) -> bool:
        return bool(getattr(self.profile.side_effect_class, "mutates", False))

    @property
    def retry(self) -> RetryClass:
        return RetryClass.NEVER if self.mutates else RetryClass.SAFE


@dataclass(frozen=True)
class ConnectorManifest:
    """Everything a connector declares: identity, capabilities, providers."""

    connector_id: str
    display_name: str
    version: str
    description: str
    capabilities: tuple = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ids = [c.capability_id for c in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ContractViolation(f"{self.connector_id}: duplicate capability ids")
        if not self.capabilities:
            raise ContractViolation(f"{self.connector_id}: a connector with no capabilities")

    @property
    def providers(self) -> tuple:
        return tuple(sorted({c.provider for c in self.capabilities}))

    def required_permissions(self, provider: Optional[str] = None) -> tuple:
        """Every permission the connection must hold, optionally for one provider."""
        return tuple(sorted({p for c in self.capabilities
                             if provider is None or c.provider == provider
                             for p in c.required_permissions}))

    def capability(self, capability_id: str) -> CapabilityManifest:
        for capability in self.capabilities:
            if capability.capability_id == capability_id:
                return capability
        raise KeyError(capability_id)
