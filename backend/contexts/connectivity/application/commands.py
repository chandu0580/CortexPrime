"""Commands and queries for the Capability Registry.

Frozen values carrying primitives, so a command can be serialised, queued and
audited without dragging the domain across the wire.

Every command that changes availability or trust carries a reason. A registry
whose history says "disabled" without saying why cannot be reviewed, and the
review is the entire point of keeping the history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "RegisterCapability",
    "ValidateCapability",
    "EnableCapability",
    "DisableCapability",
    "DeprecateCapability",
    "RevokeCapability",
    "SetCapabilityTrust",
    "GetCapability",
    "ListCapabilities",
    "ListVersions",
    "InspectContract",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class RegisterCapability:
    """Declare one version of one ability."""

    capability_id: str
    version: int
    name: str
    description: str
    provider: str

    interface: str
    side_effect_class: str
    effect_semantics: str
    isolation_tier: str

    owner_id: str
    owner_kind: str
    tenancy: str
    source: str

    supported_environments: tuple = ()
    execution_mode: str = "synchronous"
    tenant_id: Optional[str] = None
    shared_with: tuple = ()
    category: Optional[str] = None
    owner_display_name: Optional[str] = None

    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    required_permissions: tuple = ()

    idempotency_supported: bool = False
    retryable: bool = False
    cancellable: bool = False
    compensation_capability: Optional[str] = None
    timeout_seconds: Optional[int] = None
    supersedes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        _require(bool(self.capability_id), "capability_id is required")
        _require(
            isinstance(self.version, int) and self.version >= 1,
            "version must be an integer of at least 1; 'latest' is not a version "
            "because a run bound to a moving target can have the capability change "
            "underneath it after approval",
        )
        for label in ("name", "description", "provider", "owner_id"):
            _require(bool(getattr(self, label)), f"{label} is required")
        _require(
            bool(self.supported_environments),
            "supported_environments is required; a capability that names none is "
            "either unusable or usable everywhere, and the second is not something "
            "to arrive at by omission",
        )
        _require(
            bool(self.owner_id.strip()) and self.owner_id.strip().lower() != "system",
            "owner_id is required and may not be 'system'; every capability is "
            "somebody's responsibility, and a fake owner is nobody's",
        )


@dataclass(frozen=True)
class _Targeted:
    capability_id: str
    version: int

    def __post_init__(self) -> None:
        _require(bool(self.capability_id), "capability_id is required")
        _require(
            isinstance(self.version, int) and self.version >= 1,
            "version is required; an operation on an unpinned capability could "
            "affect a version nobody meant to touch",
        )


@dataclass(frozen=True)
class ValidateCapability(_Targeted):
    note: str = "contract checked"


@dataclass(frozen=True)
class EnableCapability(_Targeted):
    note: str = "made available"


@dataclass(frozen=True)
class DisableCapability(_Targeted):
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(bool(self.reason.strip()), "disabling a capability must say why")


@dataclass(frozen=True)
class DeprecateCapability(_Targeted):
    reason: str = ""
    successor_version: Optional[int] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(bool(self.reason.strip()), "deprecating a capability must say why")


@dataclass(frozen=True)
class RevokeCapability(_Targeted):
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(
            bool(self.reason.strip()),
            "revoking a capability must say why; revocation is permanent and the "
            "reason is the only thing that explains it afterwards",
        )


@dataclass(frozen=True)
class SetCapabilityTrust(_Targeted):
    """Move trust. Deliberately separate from every status command."""

    trust: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(bool(self.trust), "trust is required")
        _require(
            bool(self.reason.strip()),
            "changing trust must say why; trust is the judgement that lets a "
            "capability near production, and an unexplained one cannot be reviewed",
        )


@dataclass(frozen=True)
class GetCapability(_Targeted):
    pass


@dataclass(frozen=True)
class InspectContract(_Targeted):
    pass


@dataclass(frozen=True)
class ListVersions:
    capability_id: str

    def __post_init__(self) -> None:
        _require(bool(self.capability_id), "capability_id is required")


@dataclass(frozen=True)
class ListCapabilities:
    provider: Optional[str] = None
    interface: Optional[str] = None
    status: Optional[str] = None
    trust: Optional[str] = None
    environment: Optional[str] = None
    executable_only: bool = False
    include_undiscoverable: bool = False
