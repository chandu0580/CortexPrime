"""Capability identity and version.

Why identity is structured text rather than a ULID
----------------------------------------------------
Every other identifier in this codebase is a ULID, because every other
identifier names *an occurrence*: this mission, this run, this attempt. Those
are created by the platform and nobody outside it needs to recognise them.

A capability is not an occurrence. It is a **declaration of an ability**, and it
has to be recognisable by the people who write workflows and by the people
reading an audit log two years later. ``github.pull_request.create`` says what it
is; ``01KZ7Q...`` says nothing and would have to be looked up every time.

The identity must also survive things a ULID would not. If the GitHub connector
is rewritten from scratch in a different language, it is still
``github.pull_request.create``. Identity tracks the *ability*, not the code that
happens to provide it -- which is exactly why it must not be a class name, a
module path, a URL, or a database key.

Structure
-----------
    <namespace>.<provider>.<capability>[.<operation>]

    platform . github  . pull_request . create
    platform . shell   . execute
    tenant   . acme    . deploy       . rollback

``namespace`` separates platform-supplied abilities from tenant-supplied ones,
so a tenant cannot register something that shadows a platform capability.

Version is deliberately **not** part of identity. ``github.pull_request.create``
is one ability; ``@1`` and ``@2`` are two contracts for it. Folding the version
into the identity would make every upgrade look like a different capability and
make "which versions of this exist?" unanswerable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "CapabilityNamespace",
    "CapabilityId",
    "CapabilityVersion",
    "CapabilityRef",
]

#: One segment: lowercase, digits, underscores. No dots (they separate segments),
#: no hyphens (they read as minus in expressions), no case (so ``GitHub`` and
#: ``github`` cannot become two capabilities that look identical in a log).
_SEGMENT = re.compile(r"^[a-z][a-z0-9_]*$")

_MAX_SEGMENT = 64


class CapabilityNamespace(str, Enum):
    """Who is entitled to declare this ability."""

    PLATFORM = "platform"
    """Supplied by CortexPrime itself."""

    TENANT = "tenant"
    """Supplied by a customer. Never shadows a platform capability, because the
    namespace is part of the identity."""


def _segment(label: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")
    cleaned = value.strip().lower()
    if len(cleaned) > _MAX_SEGMENT:
        raise ContractViolation(f"{label} may not exceed {_MAX_SEGMENT} characters")
    if not _SEGMENT.match(cleaned):
        raise ContractViolation(
            f"{label} must be lowercase letters, digits and underscores, starting "
            f"with a letter; got {value!r}. Identity appears in audit records and "
            "in workflow definitions, so it is constrained rather than free text"
        )
    return cleaned


@dataclass(frozen=True, order=True)
class CapabilityId:
    """A stable name for one executable ability."""

    namespace: CapabilityNamespace
    provider: str
    capability: str
    operation: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, CapabilityNamespace):
            raise ContractViolation("namespace must be a CapabilityNamespace")
        object.__setattr__(self, "provider", _segment("provider", self.provider))
        object.__setattr__(self, "capability", _segment("capability", self.capability))
        if self.operation is not None:
            object.__setattr__(self, "operation", _segment("operation", self.operation))

    @property
    def value(self) -> str:
        parts = [self.namespace.value, self.provider, self.capability]
        if self.operation:
            parts.append(self.operation)
        return ".".join(parts)

    @property
    def is_tenant_supplied(self) -> bool:
        return self.namespace is CapabilityNamespace.TENANT

    def __str__(self) -> str:
        return self.value

    @classmethod
    def parse(cls, text: str) -> "CapabilityId":
        """Parse ``namespace.provider.capability[.operation]``."""
        if not isinstance(text, str) or not text.strip():
            raise ContractViolation("a capability id must be non-blank text")
        parts = text.strip().lower().split(".")
        if len(parts) not in (3, 4):
            raise ContractViolation(
                f"{text!r} is not a capability id; expected "
                "namespace.provider.capability[.operation]"
            )
        try:
            namespace = CapabilityNamespace(parts[0])
        except ValueError as exc:
            permitted = ", ".join(n.value for n in CapabilityNamespace)
            raise ContractViolation(
                f"{parts[0]!r} is not a capability namespace; permitted: {permitted}"
            ) from exc
        return cls(
            namespace=namespace,
            provider=parts[1],
            capability=parts[2],
            operation=parts[3] if len(parts) == 4 else None,
        )


@dataclass(frozen=True, order=True)
class CapabilityVersion:
    """A contract version for one capability. Integers, not semver.

    Semver invites the judgement call this registry must not allow: "is this a
    minor change?" A capability's contract either is what an approved workflow
    bound to, or it is not. One integer, incremented whenever the security-
    relevant contract changes, keeps that question answerable.

    ``latest`` is deliberately absent. A run must be bindable to an exact
    version, and a moving target would let a capability change underneath an
    approved execution -- the failure this whole model exists to prevent.
    """

    number: int

    def __post_init__(self) -> None:
        if not isinstance(self.number, int) or isinstance(self.number, bool):
            raise ContractViolation("a capability version must be an integer")
        if self.number < 1:
            raise ContractViolation("capability versions start at 1")

    @property
    def next(self) -> "CapabilityVersion":
        return CapabilityVersion(self.number + 1)

    def __str__(self) -> str:
        return str(self.number)

    @classmethod
    def parse(cls, text) -> "CapabilityVersion":
        if isinstance(text, int) and not isinstance(text, bool):
            return cls(text)
        if isinstance(text, str) and text.strip().isdigit():
            return cls(int(text.strip()))
        raise ContractViolation(
            f"{text!r} is not a capability version. Note that 'latest' is not a "
            "version: a run bound to a moving target can have the capability "
            "change underneath it after approval"
        )


@dataclass(frozen=True, order=True)
class CapabilityRef:
    """A pinned reference: exactly one contract of one ability.

    What an execution binds to, and what an approval is about. Rendered
    ``github.pull_request.create@2`` so the pin is visible wherever it is logged.
    """

    capability_id: CapabilityId
    version: CapabilityVersion

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, CapabilityId):
            raise ContractViolation("capability_id must be a CapabilityId")
        if not isinstance(self.version, CapabilityVersion):
            raise ContractViolation(
                "version must be a CapabilityVersion; an unpinned reference lets "
                "the capability change after the workflow was approved"
            )

    @property
    def value(self) -> str:
        return f"{self.capability_id.value}@{self.version.number}"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def parse(cls, text: str) -> "CapabilityRef":
        if not isinstance(text, str) or "@" not in text:
            raise ContractViolation(
                f"{text!r} is not a pinned capability reference; expected "
                "namespace.provider.capability[.operation]@version"
            )
        identity, _, version = text.rpartition("@")
        return cls(
            capability_id=CapabilityId.parse(identity),
            version=CapabilityVersion.parse(version),
        )
