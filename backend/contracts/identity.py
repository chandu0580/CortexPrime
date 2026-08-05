"""Identity vocabulary.

Owner: BC-9 Tenancy & Identity.

Identifies *who* is acting. CortexPrime has three kinds of actor and the
distinction is load-bearing for audit: a human approving an action, the
platform acting autonomously, and an external system delivering a webhook are
not interchangeable, and an audit record that cannot tell them apart is not
defensible (Constitution S8).

These contracts carry identity and granted capabilities only. They never carry
credentials. Credentials are brokered per execution and expire with it
(Constitution I5); a long-lived contract object is exactly the wrong place for
one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantScope

__all__ = ["PrincipalKind", "PrincipalRef", "SecurityContext"]


class PrincipalKind(str, Enum):
    """What kind of actor a principal is."""

    HUMAN = "human"
    """A person. The only kind that may satisfy an approval requirement."""

    PLATFORM = "platform"
    """CortexPrime acting on its own behalf (schedulers, watchers, dispatchers)."""

    EXTERNAL_SYSTEM = "external_system"
    """A third-party system, e.g. an inbound webhook sender."""


@dataclass(frozen=True)
class PrincipalRef(Contract):
    """A reference to an actor.

    ``display_name`` is optional because machine principals frequently have no
    meaningful human-facing name, and fabricating one would put unreliable data
    into the audit trail.
    """

    CONTRACT_NAME = "cortexprime.identity.principal"

    principal_id: str
    kind: PrincipalKind
    display_name: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ContractViolation("principal_id must be a non-blank string")
        if not isinstance(self.kind, PrincipalKind):
            raise ContractViolation("kind must be a PrincipalKind")

    @property
    def can_approve(self) -> bool:
        """Only humans may satisfy an approval requirement.

        This is vocabulary, not enforcement -- Governance enforces it. Exposing
        it here keeps the rule stated in exactly one place.
        """
        return self.kind is PrincipalKind.HUMAN


@dataclass(frozen=True)
class SecurityContext(Contract):
    """The identity and scope every cross-context message carries.

    Constitution BC-9: "every cross-context message carries a tenant-scoped
    security context. Non-negotiable."

    ``capabilities`` are coarse grants resolved at authentication time. They are
    an input to policy evaluation, never a substitute for it -- Governance still
    evaluates every action (I1).
    """

    CONTRACT_NAME = "cortexprime.identity.security_context"

    principal: PrincipalRef
    scope: TenantScope
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    on_behalf_of: Optional[PrincipalRef] = None

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, tuple):
            raise ContractViolation("capabilities must be a tuple (contracts are immutable)")
        for capability in self.capabilities:
            if not isinstance(capability, str) or not capability.strip():
                raise ContractViolation("capability entries must be non-blank strings")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ContractViolation("capabilities must not contain duplicates")
        if self.on_behalf_of is not None and self.on_behalf_of == self.principal:
            raise ContractViolation("on_behalf_of must differ from principal")

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    @property
    def effective_principal(self) -> PrincipalRef:
        """The principal whose authority is being exercised.

        For delegated action (platform acting for a human), audit must record
        both the actor and the authority. ``principal`` is the actor;
        ``effective_principal`` is the authority.
        """
        return self.on_behalf_of or self.principal
