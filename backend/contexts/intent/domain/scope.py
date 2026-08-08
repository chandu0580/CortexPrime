"""Scope: what the intent is about, and what it is explicitly not about.

Two rules, both refused at construction
----------------------------------------
**A scope that includes nothing authorises nothing.** An intent with an empty
scope gives a planner no ground to stand on, and the natural reading of "no
scope" is "everything" -- which is the most expensive possible default.

**A target both included and excluded is a contradiction.** Nobody downstream
can resolve it; a planner would have to guess which the requester meant, and
guessing about scope is how blast radius grows.

Exclusions are worth more than they look
-----------------------------------------
``exclude`` exists because the interesting half of scope is usually the part
somebody thought about and ruled out. "Everything in the payments namespace
except the settlement job" carries a decision. Recording only the inclusion
loses it, and the next round re-litigates it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.intent.domain.errors import ContradictoryScope, EmptyScope

__all__ = ["Environment", "ScopeTarget", "IntentScope"]


class Environment(str, Enum):
    """Where the intent applies.

    Recorded separately from the targets because it changes what is at stake.
    The same objective against ``PRODUCTION`` and against ``DEVELOPMENT`` are
    different requests, and policy holds them to different standards.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_live(self) -> bool:
        """Whether real users are affected by what happens here."""
        return self is Environment.PRODUCTION


@dataclass(frozen=True, order=True)
class ScopeTarget:
    """One system, service, or resource the intent concerns.

    A plain identifier and its type. This context does not resolve targets --
    it has no connector, no inventory, and no business having either. What it
    records is what the requester named.
    """

    identifier: str
    target_type: str = "system"

    def __post_init__(self) -> None:
        for label, value in (
            ("identifier", self.identifier),
            ("target_type", self.target_type),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"a scope target must have a {label}")
            if value != value.strip():
                raise ContractViolation(
                    f"scope target {label} must not have surrounding whitespace"
                )

    def __str__(self) -> str:
        return self.identifier


@dataclass(frozen=True)
class IntentScope(Contract):
    """What is in, what is out, and where."""

    CONTRACT_NAME = "cortexprime.intent.scope"

    included: frozenset = field(default_factory=frozenset)
    excluded: frozenset = field(default_factory=frozenset)
    environments: frozenset = field(default_factory=frozenset)
    note: Optional[str] = None

    def __post_init__(self) -> None:
        for label in ("included", "excluded"):
            value = getattr(self, label)
            if not isinstance(value, (frozenset, set)):
                raise ContractViolation(f"{label} must be a set")
            for item in value:
                if not isinstance(item, ScopeTarget):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a ScopeTarget"
                    )
            object.__setattr__(self, label, frozenset(value))

        if not isinstance(self.environments, (frozenset, set)):
            raise ContractViolation("environments must be a set")
        for environment in self.environments:
            if not isinstance(environment, Environment):
                raise ContractViolation("environments must contain Environment members")
        object.__setattr__(self, "environments", frozenset(self.environments))

        if not self.included:
            raise EmptyScope()

        overlapping = {t.identifier for t in self.included} & {
            t.identifier for t in self.excluded
        }
        if overlapping:
            raise ContradictoryScope(sorted(overlapping))

        if not self.environments:
            raise ContractViolation(
                "a scope must name at least one environment; the same objective "
                "against production and against development are different requests"
            )

        if self.note is not None and not self.note.strip():
            raise ContractViolation("note must be non-blank when given")

    # -- queries -------------------------------------------------------

    @property
    def touches_production(self) -> bool:
        return any(e.is_live for e in self.environments)

    @property
    def included_identifiers(self) -> tuple:
        return tuple(sorted(t.identifier for t in self.included))

    @property
    def excluded_identifiers(self) -> tuple:
        return tuple(sorted(t.identifier for t in self.excluded))

    @property
    def breadth(self) -> int:
        """How many targets this authorises. Policy reads it; nothing else does."""
        return len(self.included)

    def covers(self, identifier: str) -> bool:
        """Whether a target is inside this scope.

        Exclusion wins. A target that is both would have been refused at
        construction, so this only has to answer the ordinary case -- but stating
        the precedence means a later change cannot quietly invert it.
        """
        if identifier in self.excluded_identifiers:
            return False
        return identifier in self.included_identifiers

    def widened_by(self, other: "IntentScope") -> tuple:
        """Targets ``other`` includes that this one does not.

        Expansion has to be visible. An intent whose scope grew between drafting
        and approval approved something the earlier reader never saw.
        """
        return tuple(
            sorted(set(other.included_identifiers) - set(self.included_identifiers))
        )

    @classmethod
    def of(
        cls,
        included: Sequence[str],
        *,
        excluded: Sequence[str] = (),
        environments: Iterable[Environment] = (Environment.DEVELOPMENT,),
        target_type: str = "system",
        note: Optional[str] = None,
    ) -> "IntentScope":
        return cls(
            included=frozenset(ScopeTarget(i, target_type) for i in included),
            excluded=frozenset(ScopeTarget(e, target_type) for e in excluded),
            environments=frozenset(environments),
            note=note,
        )
