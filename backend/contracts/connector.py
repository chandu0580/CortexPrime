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
    "CodeTrust",
    "IsolationTier",
    "minimum_isolation",
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


class CodeTrust(str, Enum):
    """How much computation a worker can perform that nobody declared.

    **This is the axis isolation answers to** (ADR-088, ratified 2026-09-04). It
    is not how consequential the action is -- that is ``SideEffectClass``, and it
    is priced by governance under L10: *"Authority, approval depth, and
    verification strength scale with the class."* A sandbox does not make a wrong
    action right; it stops unknown code from doing unknown things.

    Before ADR-088 these two questions shared one enum, and the collapse was
    measurable: an ``IRREVERSIBLE_WRITE`` routed to ``SEALED`` regardless of what
    ran, so *posting a comment on a GitHub issue* required full virtualization,
    while ``terraform apply`` and arbitrary shell -- which declared no tier at
    all -- required nothing.

    A declaration here is a claim about **the code as shipped**, and it is only
    true while integrity is enforced. **Compromised fixed code is ARBITRARY
    code.** That is why ``code_trust`` is part of the capability digest: a
    capability that quietly changes class invalidates every approval bound to the
    old one, rather than inheriting authority granted to something else.
    """

    FIXED = "fixed"
    """One declared operation. Typed validated arguments, fixed destination. No
    shell, no dynamic dispatch, no branching on untrusted input. The worker
    cannot be made to do anything other than the one declared thing."""

    PARAMETERIZED = "parameterized"
    """A declared program whose caller-supplied data selects among *declared*
    behaviours. Still no new code, but the space of outcomes is larger than one."""

    THIRD_PARTY = "third_party"
    """A vendor binary invoked with declared arguments. Arbitrary behaviour
    *inside* the binary: its own syscalls, its own filesystem access, its own
    network. ``terraform``, ``kubectl``."""

    OPERATOR_SCRIPT = "operator_script"
    """Human-authored code of trusted origin. Arbitrary, but attributable and
    reviewable before it runs."""

    ARBITRARY = "arbitrary"
    """Untrusted origin, unbounded behaviour: model-generated code, a
    user-supplied script, an interactive shell. For this class the *declared*
    effect is meaningless -- the code is not bound by it. What bounds it is the
    credential and the network; what contains an escape is virtualization."""

    @property
    def rank(self) -> int:
        return _CODE_TRUST_RANK[self]


_CODE_TRUST_RANK = {
    CodeTrust.FIXED: 0,
    CodeTrust.PARAMETERIZED: 1,
    CodeTrust.THIRD_PARTY: 2,
    CodeTrust.OPERATOR_SCRIPT: 3,
    CodeTrust.ARBITRARY: 4,
}


class IsolationTier(str, Enum):
    """The execution boundary a worker runs behind.

    **Assigned by code trust, not by consequence** (ADR-088). Consequence is
    priced by governance under L10 -- authority, approval depth and verification
    strength -- not by a sandbox.

    The tiers are ordered: a worker at a higher tier satisfies a requirement for
    a lower one, never the reverse. Use :func:`minimum_isolation` to ask what a
    given (code trust, effect) pair requires; do not hand-compare tiers.
    """

    AMBIENT = "ambient"
    """In-process calls to declared APIs. Process-level, scoped credentials."""

    CONTAINED = "contained"
    """A **separate worker** with **per-execution credentials** and no ambient
    secrets. Note what this requires and what it therefore excludes: an
    in-process adapter is not CONTAINED however it is declared (ADR-059)."""

    SANDBOXED = "sandboxed"
    """A kernel-hardened boundary on a shared kernel: separate process or
    container, non-root, read-only root filesystem, dropped capabilities,
    seccomp, restricted egress, bounded CPU/memory/runtime, no ambient
    credentials. Stronger than CONTAINED against the *code*; it still shares the
    host kernel, so it is **not** SEALED and must never be described as such."""

    SEALED = "sealed"
    """Arbitrary commands or code. Full virtualization, no ambient credentials.

    Unchanged by ADR-088, deliberately and verbatim: ``SEALED`` explicitly
    excludes shared-kernel containers. Where untrusted or model-generated
    commands run, hardware-enforced isolation is required."""

    @property
    def rank(self) -> int:
        return _ISOLATION_RANK[self]

    def satisfies(self, required: "IsolationTier") -> bool:
        """Whether running at this tier meets a requirement for ``required``."""
        return self.rank >= required.rank

    @property
    def minimum_for(self) -> frozenset:
        """Effect classes this tier is sufficient for, **for FIXED code**.

        Retained so that pre-ADR-088 callers keep a meaningful answer, and
        deliberately narrowed to the ``FIXED`` row rather than left ambiguous:
        the question "what may this tier do" has no answer that does not name a
        code-trust class. New code should call :func:`minimum_isolation`.
        """
        return frozenset(
            effect
            for effect in SideEffectClass
            if self.satisfies(minimum_isolation(CodeTrust.FIXED, effect))
        )


_ISOLATION_RANK = {
    IsolationTier.AMBIENT: 0,
    IsolationTier.CONTAINED: 1,
    IsolationTier.SANDBOXED: 2,
    IsolationTier.SEALED: 3,
}


#: The minimum execution isolation for each (code trust, effect) pair -- ADR-088
#: section 4.3, ratified 2026-09-04.
#:
#: Read the **row** for isolation and the **column** for governance depth. The
#: column is not encoded here on purpose: approval depth, autonomy ceiling and
#: verification strength already live in the autonomy policy, which is where L10
#: puts them.
#:
#: The ARBITRARY row is flat at SEALED, including for READ. That is stricter than
#: anything the platform declared before ADR-088, and it is the point: for
#: arbitrary code the declared effect class is not a bound on what the code does.
_MINIMUM_ISOLATION = {
    CodeTrust.FIXED: {
        SideEffectClass.READ: IsolationTier.AMBIENT,
        SideEffectClass.REVERSIBLE_WRITE: IsolationTier.CONTAINED,
        SideEffectClass.IRREVERSIBLE_WRITE: IsolationTier.CONTAINED,
        SideEffectClass.DESTRUCTIVE: IsolationTier.CONTAINED,
    },
    CodeTrust.PARAMETERIZED: {
        SideEffectClass.READ: IsolationTier.AMBIENT,
        SideEffectClass.REVERSIBLE_WRITE: IsolationTier.CONTAINED,
        SideEffectClass.IRREVERSIBLE_WRITE: IsolationTier.CONTAINED,
        SideEffectClass.DESTRUCTIVE: IsolationTier.SANDBOXED,
    },
    CodeTrust.THIRD_PARTY: {
        SideEffectClass.READ: IsolationTier.CONTAINED,
        SideEffectClass.REVERSIBLE_WRITE: IsolationTier.SANDBOXED,
        SideEffectClass.IRREVERSIBLE_WRITE: IsolationTier.SANDBOXED,
        SideEffectClass.DESTRUCTIVE: IsolationTier.SEALED,
    },
    CodeTrust.OPERATOR_SCRIPT: {
        SideEffectClass.READ: IsolationTier.CONTAINED,
        SideEffectClass.REVERSIBLE_WRITE: IsolationTier.SANDBOXED,
        SideEffectClass.IRREVERSIBLE_WRITE: IsolationTier.SEALED,
        SideEffectClass.DESTRUCTIVE: IsolationTier.SEALED,
    },
    CodeTrust.ARBITRARY: {
        SideEffectClass.READ: IsolationTier.SEALED,
        SideEffectClass.REVERSIBLE_WRITE: IsolationTier.SEALED,
        SideEffectClass.IRREVERSIBLE_WRITE: IsolationTier.SEALED,
        SideEffectClass.DESTRUCTIVE: IsolationTier.SEALED,
    },
}


def minimum_isolation(
    code_trust: CodeTrust, side_effect: SideEffectClass
) -> IsolationTier:
    """The minimum execution boundary for this code, performing this effect.

    The one place the matrix is read. Both arguments are required and neither has
    a default: an unstated code trust is not "probably fine", and an unstated
    effect is not "probably a read". A caller that cannot say both is a caller
    that has not decided, and it should refuse rather than be answered.
    """
    if not isinstance(code_trust, CodeTrust):
        raise ContractViolation("code_trust must be a CodeTrust")
    if not isinstance(side_effect, SideEffectClass):
        raise ContractViolation("side_effect must be a SideEffectClass")
    return _MINIMUM_ISOLATION[code_trust][side_effect]


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
