"""Identity and authorization context.

Answers *who is acting*, and *whose authority they are exercising* — which are
not always the same principal. When the platform acts on a human's approval,
audit must record both: the actor performed it, the human authorized it.

Reuses ``PrincipalRef`` from contracts rather than redefining it. The contract
is the vocabulary; this is the runtime context that carries it alongside the
capabilities resolved at authentication time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.contracts import ContractViolation, PrincipalKind, PrincipalRef

__all__ = ["IdentityContext"]


@dataclass(frozen=True)
class IdentityContext:
    """Who is acting, and with what granted capabilities.

    ``capabilities`` are coarse grants resolved once at authentication. They are
    an *input* to policy evaluation, never a substitute for it — Constitution I1
    requires a recorded policy decision regardless of what a principal holds.
    """

    principal: PrincipalRef
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    on_behalf_of: Optional[PrincipalRef] = None
    """Set when one principal acts under another's authority."""

    authenticated_at: Optional[str] = None
    """ISO-8601 instant of authentication, when a transport supplied one."""

    def __post_init__(self) -> None:
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if not isinstance(self.capabilities, tuple):
            raise ContractViolation("capabilities must be a tuple (contexts are immutable)")
        for capability in self.capabilities:
            if not isinstance(capability, str) or not capability.strip():
                raise ContractViolation("capability entries must be non-blank strings")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ContractViolation("capabilities must not contain duplicates")
        if self.on_behalf_of is not None and self.on_behalf_of == self.principal:
            raise ContractViolation("on_behalf_of must differ from principal")

    @classmethod
    def human(
        cls, principal_id: str, *, capabilities: tuple[str, ...] = (), display_name: str | None = None
    ) -> "IdentityContext":
        return cls(
            principal=PrincipalRef(
                principal_id=principal_id,
                kind=PrincipalKind.HUMAN,
                display_name=display_name,
            ),
            capabilities=capabilities,
        )

    @classmethod
    def platform(cls, component: str) -> "IdentityContext":
        """Identity for the platform acting on its own behalf.

        Note such a principal cannot approve anything — ``can_approve`` is False
        for PLATFORM — which is the Constitution's rule that the system never
        authorizes itself, expressed in the type rather than in a check.
        """
        return cls(
            principal=PrincipalRef(principal_id=component, kind=PrincipalKind.PLATFORM)
        )

    @property
    def principal_id(self) -> str:
        return self.principal.principal_id

    @property
    def can_approve(self) -> bool:
        return self.principal.can_approve

    @property
    def effective_principal(self) -> PrincipalRef:
        """The principal whose *authority* is being exercised.

        For delegated action the actor and the authority differ, and an audit
        record naming only one of them cannot answer "who allowed this?".
        """
        return self.on_behalf_of or self.principal

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def delegating_to(self, actor: PrincipalRef) -> "IdentityContext":
        """Return a context where ``actor`` acts under this principal's authority."""
        return IdentityContext(
            principal=actor,
            capabilities=self.capabilities,
            on_behalf_of=self.principal,
            authenticated_at=self.authenticated_at,
        )
