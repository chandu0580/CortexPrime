"""Connector vocabulary.

Owner: BC-8 Connectivity.

Describes *what a tool can do*, so that Governance can reason about a tool it
has never seen. Constitution S6 requires that allowlisting be "semantic, not
textual" -- classification by declared capability rather than by
pattern-matching command strings, because published research has bypassed
string filters using secondary execution primitives inside permitted tools.

``ToolDescriptor.side_effect_class`` is that declaration. A tool states its
consequence class once, at registration, and policy reasons about the
declaration rather than about a command line.

This module describes tools. It does not invoke them, hold credentials for
them, or define their parameter schemas -- all BC-8 responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass

__all__ = [
    "ConnectorHealth",
    "IsolationTier",
    "ConnectorRef",
    "ToolDescriptor",
    "ConnectorCapabilities",
]


class ConnectorHealth(str, Enum):
    """Whether a connector can currently be relied upon."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    """Reachable but impaired. Evidence from it carries reduced confidence."""

    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"

    @property
    def can_execute(self) -> bool:
        return self is ConnectorHealth.HEALTHY


class IsolationTier(str, Enum):
    """The isolation a tool's invocation requires (Constitution S6).

    Assigned by consequence, not convenience. ``SEALED`` explicitly excludes
    shared-kernel containers: where untrusted or model-generated commands run,
    hardware-enforced isolation is required.
    """

    AMBIENT = "ambient"
    """Read-only calls to declared APIs. Process-level, scoped credentials."""

    CONTAINED = "contained"
    """Reversible writes via known APIs. Separate worker, per-execution credentials."""

    SEALED = "sealed"
    """Arbitrary commands or code. Full virtualization, no ambient credentials."""

    @property
    def minimum_for(self) -> frozenset[SideEffectClass]:
        """Side-effect classes this tier is sufficient for."""
        return _TIER_SUFFICIENCY[self]


_TIER_SUFFICIENCY = {
    IsolationTier.AMBIENT: frozenset({SideEffectClass.READ}),
    IsolationTier.CONTAINED: frozenset({SideEffectClass.READ, SideEffectClass.REVERSIBLE_WRITE}),
    IsolationTier.SEALED: frozenset(SideEffectClass),
}


@dataclass(frozen=True)
class ConnectorRef(Contract):
    """A reference to one configured integration."""

    CONTRACT_NAME = "cortexprime.connector.ref"

    connector_id: str
    system: str

    def __post_init__(self) -> None:
        for label, value in (("connector_id", self.connector_id), ("system", self.system)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")


@dataclass(frozen=True)
class ToolDescriptor(Contract):
    """A declaration of one operation a connector exposes.

    The isolation tier must be sufficient for the declared side-effect class.
    Declaring a destructive tool as ``AMBIENT`` is rejected at construction --
    an under-isolated destructive tool is exactly the configuration that turns a
    prompt-injection into an incident.

    ``inverse_tool`` names the tool that undoes this one, supporting
    Constitution P2 at registration time rather than at execution time.
    """

    CONTRACT_NAME = "cortexprime.connector.tool"

    connector: ConnectorRef
    tool_name: str
    description: str
    side_effect_class: SideEffectClass
    isolation_tier: IsolationTier
    required_capability: Optional[str] = None
    inverse_tool: Optional[str] = None

    def __post_init__(self) -> None:
        for label, value in (("tool_name", self.tool_name), ("description", self.description)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise ContractViolation("side_effect_class must be a SideEffectClass")
        if not isinstance(self.isolation_tier, IsolationTier):
            raise ContractViolation("isolation_tier must be an IsolationTier")

        if self.side_effect_class not in self.isolation_tier.minimum_for:
            raise ContractViolation(
                f"isolation tier {self.isolation_tier.value} is insufficient for a "
                f"{self.side_effect_class.value} tool"
            )
        if self.side_effect_class is SideEffectClass.READ and self.inverse_tool is not None:
            raise ContractViolation("a read tool must not declare an inverse")
        if self.inverse_tool is not None and self.inverse_tool == self.tool_name:
            raise ContractViolation("a tool cannot be its own inverse")

    @property
    def is_reversible(self) -> bool:
        return self.inverse_tool is not None


@dataclass(frozen=True)
class ConnectorCapabilities(Contract):
    """The full set of tools one connector exposes, plus its current health.

    Health travels with capability because a tool that cannot be reached is not
    a capability. Consumers checking ``executable_tools`` get both facts in one
    place rather than checking availability separately and racing.
    """

    CONTRACT_NAME = "cortexprime.connector.capabilities"

    connector: ConnectorRef
    health: ConnectorHealth
    tools: tuple[ToolDescriptor, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.health, ConnectorHealth):
            raise ContractViolation("health must be a ConnectorHealth")
        if not isinstance(self.tools, tuple):
            raise ContractViolation("tools must be a tuple (contracts are immutable)")

        names = [tool.tool_name for tool in self.tools]
        if len(set(names)) != len(names):
            raise ContractViolation("tools must not contain duplicate tool_name values")
        for tool in self.tools:
            if tool.connector != self.connector:
                raise ContractViolation(
                    f"tool {tool.tool_name!r} belongs to a different connector"
                )

    @property
    def executable_tools(self) -> tuple[ToolDescriptor, ...]:
        """Tools that may currently be invoked. Empty unless the connector is healthy."""
        if not self.health.can_execute:
            return ()
        return self.tools

    def tool(self, tool_name: str) -> Optional[ToolDescriptor]:
        for descriptor in self.tools:
            if descriptor.tool_name == tool_name:
                return descriptor
        return None
