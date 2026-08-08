"""Capability lifecycle and trust. Two axes, deliberately not one.

Existence is not trust
------------------------
The single most important idea in this module: a capability being *registered*
says only that somebody described it. It says nothing about whether the platform
should let it near production.

If those were one field, then "we know about this" and "we vouch for this" would
be the same statement, and every later resolution step would be entitled to
assume that anything it can find is safe to run. Keeping them apart means a
resolver has to ask the second question explicitly.

So:

``CapabilityStatus`` — where the definition is in its administrative life.
``TrustState``       — how much the platform vouches for it.

A capability can be ENABLED and QUARANTINED at once. That is not a contradiction:
it is an operator saying "this is meant to be available, and right now I do not
trust it". ``is_executable`` requires both axes to agree.

Why not a boolean
-------------------
``enabled: bool`` cannot express revocation. A revoked capability that is one
``enabled = True`` away from running again is not revoked; it is paused. Making
REVOKED a terminal state with no transitions out is what gives revocation
meaning.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

__all__ = [
    "CapabilityStatus",
    "TrustState",
    "STATUS_TRANSITIONS",
    "TRUST_TRANSITIONS",
    "is_legal_status_transition",
    "is_legal_trust_transition",
    "status_permitted_from",
    "trust_permitted_from",
    "status_refusal_reason",
]


class CapabilityStatus(str, Enum):
    """Where a capability definition is in its administrative life."""

    DRAFT = "draft"
    """Being described. Not yet asserted to be correct by anyone."""

    REGISTERED = "registered"
    """The definition is recorded and its contract is digest-bound. Nobody has
    checked it does what it claims."""

    VALIDATED = "validated"
    """The contract has been checked. Still not switched on."""

    ENABLED = "enabled"
    """Available for use, subject to trust."""

    DISABLED = "disabled"
    """Switched off, reversibly. The ordinary operational lever."""

    DEPRECATED = "deprecated"
    """Still works; should not be adopted by anything new. A successor version
    normally exists."""

    REVOKED = "revoked"
    """Withdrawn permanently. Terminal, with no transition out at all -- that
    absence *is* the security property. Bringing back a revoked capability means
    registering a new version, which forces a new digest and a new decision."""

    @property
    def is_terminal(self) -> bool:
        return self is CapabilityStatus.REVOKED

    @property
    def permits_execution(self) -> bool:
        """Whether this status alone would allow use. Trust still has a vote."""
        return self in {CapabilityStatus.ENABLED, CapabilityStatus.DEPRECATED}

    @property
    def is_discoverable(self) -> bool:
        """Whether it should appear to a caller listing what it may use.

        A revoked capability stays in the registry as a record and disappears
        from discovery: deleting it would erase the evidence that it once
        existed and was withdrawn.
        """
        return self not in {CapabilityStatus.REVOKED, CapabilityStatus.DRAFT}


STATUS_TRANSITIONS: dict = {
    CapabilityStatus.DRAFT: (CapabilityStatus.REGISTERED, CapabilityStatus.REVOKED),
    CapabilityStatus.REGISTERED: (
        CapabilityStatus.VALIDATED,
        CapabilityStatus.DISABLED,
        CapabilityStatus.REVOKED,
    ),
    # Validation does not switch anything on. Enabling is a separate, deliberate
    # act, so that "we checked it" and "we are using it" are two decisions with
    # two records.
    CapabilityStatus.VALIDATED: (
        CapabilityStatus.ENABLED,
        CapabilityStatus.DISABLED,
        CapabilityStatus.DEPRECATED,
        CapabilityStatus.REVOKED,
    ),
    CapabilityStatus.ENABLED: (
        CapabilityStatus.DISABLED,
        CapabilityStatus.DEPRECATED,
        CapabilityStatus.REVOKED,
    ),
    # A disabled capability returns to VALIDATED, never straight to ENABLED:
    # switching something back on goes through the same gate it went through the
    # first time.
    CapabilityStatus.DISABLED: (CapabilityStatus.VALIDATED, CapabilityStatus.REVOKED),
    CapabilityStatus.DEPRECATED: (CapabilityStatus.DISABLED, CapabilityStatus.REVOKED),
    CapabilityStatus.REVOKED: (),
}


class TrustState(str, Enum):
    """How much the platform vouches for what this capability claims."""

    UNVERIFIED = "unverified"
    """Registered, and nothing more. The default, because assuming otherwise is
    how an unchecked declaration becomes an executed one."""

    VERIFIED = "verified"
    """Its declaration has been checked against what it actually does."""

    TRUSTED = "trusted"
    """Verified, and cleared for consequential work."""

    QUARANTINED = "quarantined"
    """Something is wrong. Withheld from use without withdrawing the definition,
    so it can be investigated and released rather than re-registered."""

    UNTRUSTED = "untrusted"
    """Judged unfit. Terminal for this version."""

    @property
    def permits_execution(self) -> bool:
        """Whether trust allows use. Fails closed: only two states say yes."""
        return self in {TrustState.VERIFIED, TrustState.TRUSTED}

    @property
    def is_withheld(self) -> bool:
        return self in {TrustState.QUARANTINED, TrustState.UNTRUSTED}


TRUST_TRANSITIONS: dict = {
    TrustState.UNVERIFIED: (
        TrustState.VERIFIED,
        TrustState.QUARANTINED,
        TrustState.UNTRUSTED,
    ),
    TrustState.VERIFIED: (
        TrustState.TRUSTED,
        TrustState.QUARANTINED,
        TrustState.UNTRUSTED,
        TrustState.UNVERIFIED,
    ),
    TrustState.TRUSTED: (
        TrustState.VERIFIED,
        TrustState.QUARANTINED,
        TrustState.UNTRUSTED,
    ),
    # Quarantine is reversible -- that is its purpose. It returns to UNVERIFIED,
    # not to whatever it was before: coming out of quarantine means being checked
    # again, not resuming a trust that was already in doubt.
    TrustState.QUARANTINED: (TrustState.UNVERIFIED, TrustState.UNTRUSTED),
    TrustState.UNTRUSTED: (),
}


def is_legal_status_transition(source: CapabilityStatus, target: CapabilityStatus) -> bool:
    return target in STATUS_TRANSITIONS.get(source, ())


def is_legal_trust_transition(source: TrustState, target: TrustState) -> bool:
    return target in TRUST_TRANSITIONS.get(source, ())


def status_permitted_from(source: CapabilityStatus) -> tuple:
    return tuple(sorted(s.value for s in STATUS_TRANSITIONS.get(source, ())))


def trust_permitted_from(source: TrustState) -> tuple:
    return tuple(sorted(s.value for s in TRUST_TRANSITIONS.get(source, ())))


def status_refusal_reason(
    source: CapabilityStatus, target: CapabilityStatus
) -> Optional[str]:
    """Why a move is refused, in terms of what it would mean."""
    if source is CapabilityStatus.REVOKED:
        return (
            "a revoked capability cannot be brought back; revocation that can be "
            "undone with a status change is a pause wearing a stronger word. "
            "Register a new version, which forces a new digest and a new decision"
        )
    if source is CapabilityStatus.DISABLED and target is CapabilityStatus.ENABLED:
        return (
            "a disabled capability returns to validated before it is enabled; "
            "switching something back on goes through the gate it went through "
            "the first time"
        )
    if source is CapabilityStatus.REGISTERED and target is CapabilityStatus.ENABLED:
        return (
            "a registered capability has not been validated; enabling it now "
            "would put an unchecked declaration into use"
        )
    return None
