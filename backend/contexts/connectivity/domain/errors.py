"""Refusals raised by the Capability Registry.

These differ in kind from the execution runtime's. Those refuse *actions* while
work is in flight. These refuse *declarations* — and the cost of getting one
wrong is not a failed run but a capability that says one thing and does another,
which is a security failure rather than an operational one.
"""

from __future__ import annotations

from typing import Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "CapabilityError",
    "InvalidCapabilityIdentity",
    "CapabilityNotFound",
    "CapabilityVersionNotFound",
    "ConflictingRegistration",
    "IllegalCapabilityTransition",
    "IllegalTrustTransition",
    "CapabilityRevokedError",
    "ImmutableCapabilityField",
    "CapabilityNotExecutable",
    "OwnerRequired",
    "TenancyViolation",
]


class CapabilityError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidCapabilityIdentity(CapabilityError):
    def __init__(self, value: object, reason: str) -> None:
        super().__init__(f"{value!r} is not a usable capability identity: {reason}")
        self.value = value
        self.reason = reason


class CapabilityNotFound(CapabilityError):
    def __init__(self, capability_id: str) -> None:
        super().__init__(f"no capability registered as {capability_id!r}")
        self.capability_id = capability_id


class CapabilityVersionNotFound(CapabilityError):
    def __init__(self, capability_id: str, version: int, known: Sequence[int] = ()) -> None:
        listed = ", ".join(str(v) for v in sorted(known)) or "none"
        super().__init__(
            f"{capability_id!r} has no version {version}; registered versions: {listed}"
        )
        self.capability_id = capability_id
        self.version = version
        self.known = tuple(known)


class ConflictingRegistration(CapabilityError):
    """The same version was registered with a different contract.

    The security invariant of the whole registry. Accepting this would let one
    process change what a capability *is* underneath an execution that was
    approved against the old contract -- an approval for one thing becoming
    permission for another, with no record that anything changed.
    """

    def __init__(self, *, capability_ref: str, registered_digest: str, offered_digest: str) -> None:
        super().__init__(
            f"{capability_ref} is already registered with contract digest "
            f"{registered_digest[:16]}..., and a different contract "
            f"({offered_digest[:16]}...) was offered for the same version. A "
            "registered version is immutable: publish a new version instead, so "
            "that anything approved against the old contract stays approved "
            "against the old contract"
        )
        self.capability_ref = capability_ref
        self.registered_digest = registered_digest
        self.offered_digest = offered_digest


class IllegalCapabilityTransition(CapabilityError):
    def __init__(
        self, *, capability_ref: str, source: str, target: str, permitted: Sequence[str], reason: str = ""
    ) -> None:
        allowed = ", ".join(sorted(permitted)) or "(nothing -- this state is terminal)"
        super().__init__(
            f"{capability_ref} cannot move {source} -> {target}; "
            + (reason or f"{source} may only move to: {allowed}")
        )
        self.capability_ref = capability_ref
        self.source = source
        self.target = target
        self.permitted = tuple(permitted)


class IllegalTrustTransition(CapabilityError):
    def __init__(
        self, *, capability_ref: str, source: str, target: str, permitted: Sequence[str]
    ) -> None:
        allowed = ", ".join(sorted(permitted)) or "(nothing -- this state is terminal)"
        super().__init__(
            f"trust in {capability_ref} cannot move {source} -> {target}; {source} "
            f"may only move to: {allowed}"
        )
        self.capability_ref = capability_ref
        self.source = source
        self.target = target
        self.permitted = tuple(permitted)


class CapabilityRevokedError(CapabilityError):
    """Named with the ``Error`` suffix to stay distinct from the *event*
    ``CapabilityRevoked``. Both are exported from this context, and a name
    serving as an exception in one module and a dataclass in another means
    ``except CapabilityRevoked`` silently catches nothing. Same convention as
    ``WorkflowApprovedError``.
    """

    def __init__(self, capability_ref: str, operation: str) -> None:
        super().__init__(
            f"{capability_ref} is revoked; {operation} would return a withdrawn "
            "capability to service without anybody deciding to. Register a new "
            "version instead"
        )
        self.capability_ref = capability_ref
        self.operation = operation


class ImmutableCapabilityField(CapabilityError):
    """Somebody tried to change what a registered version *is*."""

    def __init__(self, capability_ref: str, field_name: str) -> None:
        super().__init__(
            f"{field_name!r} is part of the registered identity of {capability_ref} "
            "and cannot be changed; anything approved against this version was "
            "approved against this value. Publish a new version"
        )
        self.capability_ref = capability_ref
        self.field_name = field_name


class CapabilityNotExecutable(CapabilityError):
    """Registered, findable, and still not something that may be run."""

    def __init__(self, *, capability_ref: str, status: str, trust: str) -> None:
        super().__init__(
            f"{capability_ref} may not be executed: status is {status!r} and trust "
            f"is {trust!r}. Both must permit it -- being registered is not being "
            "trusted"
        )
        self.capability_ref = capability_ref
        self.status = status
        self.trust = trust


class OwnerRequired(CapabilityError):
    def __init__(self, capability_ref: str) -> None:
        super().__init__(
            f"{capability_ref} names no owner. Every capability is somebody's "
            "responsibility, and an unowned one is an ability nobody answers for "
            "when it misbehaves"
        )
        self.capability_ref = capability_ref


class TenancyViolation(CapabilityError):
    def __init__(self, capability_ref: str, reason: str) -> None:
        super().__init__(f"{capability_ref}: {reason}")
        self.capability_ref = capability_ref
        self.reason = reason
