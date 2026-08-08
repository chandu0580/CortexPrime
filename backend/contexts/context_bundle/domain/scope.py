"""The four things every bundle must carry.

Engineering Constitution: a ContextBundle must contain a repository scope, ADR
references, dependency contracts, and a blast radius. Each is a value object
here, and each refuses to be empty in the way that would make it decorative.

On the blast radius, and a duplication deliberately not made
------------------------------------------------------------
:class:`BlastRadiusSpec` records the declared patterns and **does not match
paths**. The WorkOrder context already owns a ``BlastRadius`` with a glob engine,
forbidden-wins subtraction, and conservative conflict detection. Reimplementing
that here would be a second copy of security-relevant matching logic, and the two
would drift.

So resolution happens at the composition root, which may legally hold both, and
this value object records what was declared for the manifest and the audit trail.
The bundle knows *what scope was authorised*; it does not decide *which paths that
means*. Stated plainly because it is a real seam: a caller that resolves the
radius wrongly produces a bundle this context will accept.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = ["RepositoryScope", "AdrBundle", "DependencyContract", "BlastRadiusSpec"]


def _clean_patterns(label: str, values: Iterable[str]) -> tuple:
    cleaned: list = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ContractViolation(f"{label} contains a blank pattern")
        normalised = value.strip().replace("\\", "/")
        if normalised.startswith("/"):
            raise ContractViolation(f"{label} pattern {value!r} must be repository-relative")
        if ".." in normalised.split("/"):
            raise ContractViolation(f"{label} pattern {value!r} must not traverse upward")
        cleaned.append(normalised)
    return tuple(sorted(set(cleaned)))


@dataclass(frozen=True)
class RepositoryScope(Contract):
    """What L4 may be asked about.

    Search is the mechanism that makes a false premise discoverable: a
    repository-wide search returning nothing is exactly how an unverifiable
    assumption falls. A bundle with no search scope removes that, so an empty
    scope is refused rather than defaulted.
    """

    CONTRACT_NAME = "cortexprime.engineering.repository_scope"

    searchable: tuple
    excluded: tuple = ()
    rationale: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "searchable", _clean_patterns("searchable", self.searchable))
        object.__setattr__(self, "excluded", _clean_patterns("excluded", self.excluded))

        if not self.searchable:
            raise ContractViolation(
                "a bundle must be searchable somewhere; search is how a false premise "
                "is discovered, and a bundle with none removes that"
            )
        overlap = set(self.searchable) & set(self.excluded)
        if overlap:
            raise ContractViolation(
                f"patterns are both searchable and excluded: {sorted(overlap)}"
            )

    @property
    def is_repository_wide(self) -> bool:
        return any(p in {"**", "*", "."} for p in self.searchable)


@dataclass(frozen=True)
class AdrBundle(Contract):
    """The decisions governing this work, and what they replaced.

    ``superseded`` carries the chain deliberately. An agent given only the current
    ADR knows what was decided; given the chain, it knows what was tried and
    rejected -- which is the part that stops a superseded approach being proposed
    again as though it were new.
    """

    CONTRACT_NAME = "cortexprime.engineering.adr_bundle"

    references: tuple
    superseded: tuple = ()
    index_digest: Optional[str] = None

    def __post_init__(self) -> None:
        for label, values in (("references", self.references), ("superseded", self.superseded)):
            cleaned: list = []
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    raise ContractViolation(f"{label} contains a blank ADR reference")
                cleaned.append(value.strip().upper())
            object.__setattr__(self, label, tuple(sorted(set(cleaned))))

        overlap = set(self.references) & set(self.superseded)
        if overlap:
            raise ContractViolation(
                f"an ADR cannot be both governing and superseded: {sorted(overlap)}; "
                "a WorkOrder governed by a dead decision is ungoverned"
            )

    @property
    def is_empty(self) -> bool:
        """An empty bundle is legitimate and is a positive assertion.

        It says no architectural decision governs this work. The Architect is
        held to that claim by review, not by this type.
        """
        return not self.references

    def governs(self, reference: str) -> bool:
        return reference.strip().upper() in self.references


@dataclass(frozen=True)
class DependencyContract(Contract):
    """An interface the owned code depends on, supplied without its implementation.

    ``interface_paths`` are what the agent receives. ``implementation_paths`` are
    recorded but deliberately *not* included -- naming them makes the omission
    visible, so a reviewer can see the boundary was drawn rather than forgotten.
    """

    CONTRACT_NAME = "cortexprime.engineering.dependency_contract"

    name: str
    interface_paths: tuple
    implementation_paths: tuple = ()
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ContractViolation("a dependency contract must be named")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(
            self, "interface_paths", _clean_patterns("interface_paths", self.interface_paths)
        )
        object.__setattr__(
            self,
            "implementation_paths",
            _clean_patterns("implementation_paths", self.implementation_paths),
        )

        if not self.interface_paths:
            raise ContractViolation(
                f"dependency {self.name!r} supplies no interface; a dependency with "
                "nothing to depend on is not a dependency"
            )
        overlap = set(self.interface_paths) & set(self.implementation_paths)
        if overlap:
            raise ContractViolation(
                f"dependency {self.name!r}: {sorted(overlap)} is listed as both interface "
                "and implementation; supplying an implementation as an interface is how "
                "a boundary erodes"
            )


@dataclass(frozen=True)
class BlastRadiusSpec(Contract):
    """The blast radius as declared, recorded for audit.

    Deliberately not a matcher. See the module docstring.
    """

    CONTRACT_NAME = "cortexprime.engineering.context_blast_radius"

    allowed: tuple
    forbidden: tuple = ()
    read_only: tuple = ()

    def __post_init__(self) -> None:
        for label in ("allowed", "forbidden", "read_only"):
            object.__setattr__(self, label, _clean_patterns(label, getattr(self, label)))

        if not self.allowed:
            raise ContractViolation(
                "a blast radius that allows nothing authorises nothing; that is the "
                "absence of a scope, not a narrow one"
            )
        overlap = set(self.allowed) & set(self.read_only)
        if overlap:
            raise ContractViolation(
                f"patterns are both writable and read-only: {sorted(overlap)}"
            )

    @property
    def top_level_packages(self) -> tuple:
        return tuple(sorted({p.split("/", 1)[0] for p in self.allowed}))
