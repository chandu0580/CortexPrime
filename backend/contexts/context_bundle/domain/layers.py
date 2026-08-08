"""Context layers and the references placed in them.

Five tiers, from Engineering Constitution §6. The tiering is not organisational
tidiness -- each layer has a different access mode, and the mode is what the
layer *means*::

    L0 MINIMAL       read        Constitutions, ADR index, the WorkOrder
    L1 OWNED         read/write  the blast radius, in full
    L2 DEPENDENCIES  read        interfaces of what L1 depends on -- never bodies
    L3 ADR_BUNDLE    read        full text of every referenced decision
    L4 SEARCH        search      the repository, askable but not retrievable

Why L2 carries interfaces and not implementations
-------------------------------------------------
An agent working on Execution needs to know what an approval *is*, not how the
dispatcher stores one. Supplying the implementation invites reasoning about it,
and reasoning about another context's internals is how a boundary erodes one
convenient shortcut at a time.

Why L4 is search-only
---------------------
Search answers *"does this exist, and where?"*. Retrieval answers *"what does it
say?"*. The first is what makes a false premise discoverable -- a repository-wide
search returning nothing is exactly how an unverifiable assumption falls. The
second is an expansion, and treating it as a search would be implicit expansion
wearing a query's clothes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.context_bundle.domain.errors import LayerViolation

__all__ = ["AccessMode", "ContextLayer", "ContextReference", "LAYER_ACCESS"]


class AccessMode(str, Enum):
    READ = "read"
    READ_WRITE = "read_write"
    SEARCH = "search"

    @property
    def permits_write(self) -> bool:
        return self is AccessMode.READ_WRITE

    @property
    def permits_read(self) -> bool:
        """Search does not. A hit is a location, not content."""
        return self in {AccessMode.READ, AccessMode.READ_WRITE}


class ContextLayer(str, Enum):
    MINIMAL = "minimal"
    OWNED = "owned"
    DEPENDENCIES = "dependencies"
    ADR_BUNDLE = "adr_bundle"
    SEARCH = "search"

    @property
    def access(self) -> AccessMode:
        return LAYER_ACCESS[self]

    @property
    def order(self) -> int:
        """L0 through L4, for stable ordering in the manifest."""
        return {
            ContextLayer.MINIMAL: 0,
            ContextLayer.OWNED: 1,
            ContextLayer.DEPENDENCIES: 2,
            ContextLayer.ADR_BUNDLE: 3,
            ContextLayer.SEARCH: 4,
        }[self]

    @property
    def carries_content(self) -> bool:
        """Whether references in this layer have retrievable content.

        Search does not: it holds patterns, and a pattern has no digest because
        what it matches changes with the tree.
        """
        return self is not ContextLayer.SEARCH


#: The access each layer grants. Fixed, not configurable -- a layer whose access
#: could be raised per bundle would let a caller turn a read-only dependency into
#: a writable one and call it configuration.
LAYER_ACCESS = {
    ContextLayer.MINIMAL: AccessMode.READ,
    ContextLayer.OWNED: AccessMode.READ_WRITE,
    ContextLayer.DEPENDENCIES: AccessMode.READ,
    ContextLayer.ADR_BUNDLE: AccessMode.READ,
    ContextLayer.SEARCH: AccessMode.SEARCH,
}


@dataclass(frozen=True, order=True)
class ContextReference(Contract):
    """One thing in a bundle: where it is, which layer it sits in, and its digest.

    ``content_digest`` is what makes the manifest verifiable. Without it the
    bundle records that a path was included; with it, the bundle records *what
    was there*, and a later reader can tell whether the file has changed since.
    """

    CONTRACT_NAME = "cortexprime.engineering.context_reference"

    path: str
    layer: ContextLayer
    content_digest: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise ContractViolation("a context reference must name a path")
        if self.path != self.path.strip():
            raise ContractViolation("path must not have surrounding whitespace")
        if not isinstance(self.layer, ContextLayer):
            raise ContractViolation("layer must be a ContextLayer")

        normalised = self.path.replace("\\", "/")
        if normalised.startswith("/"):
            raise ContractViolation(
                f"{self.path!r} must be repository-relative, not absolute"
            )
        if ".." in normalised.split("/"):
            raise ContractViolation(f"{self.path!r} must not traverse upward with '..'")
        object.__setattr__(self, "path", normalised)

        # A retrievable reference without a digest is a claim about the past that
        # nobody can check. A search pattern has nothing to digest, because what
        # it matches depends on the tree.
        if self.layer.carries_content and not self.content_digest:
            raise LayerViolation(
                path=self.path,
                layer=self.layer.value,
                access=self.layer.access.value,
                reason=(
                    "a retrievable reference must record the digest of what was "
                    "included, or the manifest cannot be verified later"
                ),
            )
        if not self.layer.carries_content and self.content_digest:
            raise LayerViolation(
                path=self.path,
                layer=self.layer.value,
                access=self.layer.access.value,
                reason=(
                    "a search pattern has no content to digest; what it matches "
                    "changes with the tree"
                ),
            )

    @property
    def access(self) -> AccessMode:
        return self.layer.access

    @property
    def writable(self) -> bool:
        return self.access.permits_write

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.layer.value}:{self.path}"
