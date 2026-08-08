"""Capability registry events.

Namespaced ``connectivity.capability.*``. ``CONTRACT_NAME`` is globally unique
and a clash raises at import time.

One event per real state transition and no more. There is deliberately no
``CapabilityUpdated``: nothing updates a capability. A definition is registered
once and thereafter only its status and trust move, and each of those moves has
its own named fact.

Every event carries the contract digest. An event that said "capability enabled"
without saying *which contract* was enabled would be unusable during an incident,
because the interesting question is always which version was live at the time.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "CapabilityRegistered",
    "CapabilityValidated",
    "CapabilityEnabled",
    "CapabilityDisabled",
    "CapabilityDeprecated",
    "CapabilityRevoked",
    "CapabilityTrustChanged",
    "DiscoveryStarted",
    "DiscoveryCompleted",
    "DiscoveryFailed",
    "DiscoveryConflictDetected",
    "CapabilityResolved",
    "CapabilityBound",
    "CapabilityResolutionRefused",
    "CAPABILITY_EVENT_TYPES",
    "DISCOVERY_EVENT_TYPES",
    "RESOLUTION_EVENT_TYPES",
]

AGGREGATE_TYPE = "capability"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class _CapabilityEvent(DomainEvent):
    """Shared shape: which capability, which version, which contract."""

    capability_id: str = ""
    version: int = 0
    digest: str = ""
    tenancy: str = ""
    owner: str = ""

    def __post_init__(self) -> None:
        _require_text("capability_id", self.capability_id)
        _require_text("owner", self.owner)
        _require_text(
            "digest",
            self.digest,
        )
        if self.version < 1:
            raise ContractViolation("version starts at 1")

    @property
    def reference(self) -> str:
        return f"{self.capability_id}@{self.version}"


@dataclass(frozen=True)
class CapabilityRegistered(_CapabilityEvent):
    """A capability version was recorded. Not validated, not trusted, not usable."""

    EVENT_TYPE = "connectivity.capability.registered"

    provider: str = ""
    interface: str = ""
    side_effect_class: str = ""
    effect_semantics: str = ""
    source: str = ""
    idempotent_registration: bool = False
    """True when this repeated an identical earlier registration. Recorded rather
    than suppressed: knowing something re-registered is operationally useful, and
    a silently dropped event looks like a registration that never happened."""


@dataclass(frozen=True)
class CapabilityValidated(_CapabilityEvent):
    """The contract was checked. Still switched off."""

    EVENT_TYPE = "connectivity.capability.validated"

    note: str = ""


@dataclass(frozen=True)
class CapabilityEnabled(_CapabilityEvent):
    """Made available, subject to trust."""

    EVENT_TYPE = "connectivity.capability.enabled"

    trust: str = ""
    executable: bool = False
    """Whether it can actually run now. Enabling something untrusted is legal and
    leaves this false -- which is the fact worth recording."""


@dataclass(frozen=True)
class CapabilityDisabled(_CapabilityEvent):
    """Switched off, reversibly."""

    EVENT_TYPE = "connectivity.capability.disabled"

    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class CapabilityDeprecated(_CapabilityEvent):
    """Still works; nothing new should adopt it."""

    EVENT_TYPE = "connectivity.capability.deprecated"

    reason: str = ""
    successor_version: int = 0


@dataclass(frozen=True)
class CapabilityRevoked(_CapabilityEvent):
    """Withdrawn permanently. Terminal."""

    EVENT_TYPE = "connectivity.capability.revoked"

    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class CapabilityTrustChanged(_CapabilityEvent):
    """How much the platform vouches for this capability changed.

    Separate from the status events because trust and availability are separate
    axes. Collapsing them would make "we stopped trusting this" and "we turned
    this off" the same record, and during an incident they are very different.
    """

    EVENT_TYPE = "connectivity.capability.trust_changed"

    previous_trust: str = ""
    trust: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("trust", self.trust)
        _require_text("reason", self.reason)


CAPABILITY_EVENT_TYPES = (
    CapabilityRegistered,
    CapabilityValidated,
    CapabilityEnabled,
    CapabilityDisabled,
    CapabilityDeprecated,
    CapabilityRevoked,
    CapabilityTrustChanged,
)


# ----------------------------------------------------------------------
# Discovery (Phase 3.2.2)
#
# Four facts, not a trace. There is deliberately no event per normalised tool
# or per validation step: those answer "what function ran", and an event stream
# that answers that is a log wearing an envelope.
#
# Note what is absent: there is no ``CapabilityDiscovered`` event that implies
# anything became available. Discovery produces candidates; the only thing that
# puts a capability into the registry is ``CapabilityRegistered``, which is the
# same event a manual registration emits. Discovery gets no shortcut and no
# vocabulary of its own for entering the registry.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _DiscoveryEvent(DomainEvent):
    source_id: str = ""
    source_type: str = ""

    def __post_init__(self) -> None:
        _require_text("source_id", self.source_id)
        _require_text("source_type", self.source_type)


@dataclass(frozen=True)
class DiscoveryStarted(_DiscoveryEvent):
    """A source is about to be asked what it offers."""

    EVENT_TYPE = "connectivity.discovery.started"


@dataclass(frozen=True)
class DiscoveryCompleted(_DiscoveryEvent):
    """A source answered.

    ``health`` travels with the counts on purpose: ``candidates=0`` means
    something entirely different depending on whether the source was healthy or
    unreachable, and a consumer that saw only the count would conclude the
    provider had nothing.
    """

    EVENT_TYPE = "connectivity.discovery.completed"

    health: str = ""
    candidates: int = 0
    registered: int = 0
    conflicts: int = 0
    not_seen: int = 0


@dataclass(frozen=True)
class DiscoveryFailed(_DiscoveryEvent):
    """A source could not be asked, or answered with something unusable."""

    EVENT_TYPE = "connectivity.discovery.failed"

    health: str = ""
    reason: str = ""


@dataclass(frozen=True)
class DiscoveryConflictDetected(_DiscoveryEvent):
    """A source offered a different contract for a version already registered.

    The security-relevant discovery event. Something is trying to redefine a
    capability version that may already have been approved and executed against,
    and this is the record that it tried.
    """

    EVENT_TYPE = "connectivity.discovery.conflict"

    capability_reference: str = ""
    observation_digest: str = ""
    detail: str = ""


DISCOVERY_EVENT_TYPES = (
    DiscoveryStarted,
    DiscoveryCompleted,
    DiscoveryFailed,
    DiscoveryConflictDetected,
)


# ----------------------------------------------------------------------
# Resolution and binding (Phase 3.2.4)
#
# Three facts. Note what is absent: there is no ``CapabilityRebound`` and no
# ``BindingUpdated``. A binding is immutable, so the only thing that can happen
# to a choice after it is made is that a *new* choice is made -- which emits a
# new ``CapabilityBound`` with a new binding id.
#
# Every event carries the digest of what was selected, so a replay can tell
# which contract was actually chosen rather than only which name was asked for.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _ResolutionEvent(DomainEvent):
    capability_id: str = ""
    operation: str = ""
    policy_version: str = ""

    def __post_init__(self) -> None:
        _require_text("capability_id", self.capability_id)
        _require_text("operation", self.operation)


@dataclass(frozen=True)
class CapabilityResolved(_ResolutionEvent):
    """One implementation was selected from the eligible set."""

    EVENT_TYPE = "connectivity.capability.resolved"

    version: int = 0
    digest: str = ""
    provider: str = ""
    candidate_count: int = 0
    rejected_count: int = 0


@dataclass(frozen=True)
class CapabilityBound(_ResolutionEvent):
    """The choice was frozen into an immutable, expiring binding.

    The security-relevant one: this is the fact that says *this exact contract
    from this exact provider* was bound to a run, under a named authorization.
    """

    EVENT_TYPE = "connectivity.capability.bound"

    version: int = 0
    digest: str = ""
    provider: str = ""
    binding_id: str = ""
    binding_digest: str = ""
    authorization_digest: str = ""
    expires_at: str = ""


@dataclass(frozen=True)
class CapabilityResolutionRefused(_ResolutionEvent):
    """No binding was produced, and why.

    Recorded as its own fact rather than an absence. A refusal to resolve --
    especially an ambiguous one -- is something an operator needs to find.
    """

    EVENT_TYPE = "connectivity.capability.resolution_refused"

    failure: str = ""
    detail: str = ""
    candidate_count: int = 0


RESOLUTION_EVENT_TYPES = (
    CapabilityResolved,
    CapabilityBound,
    CapabilityResolutionRefused,
)
