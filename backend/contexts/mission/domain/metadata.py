"""What a mission is about, and what must be true before it runs.

Mission Runtime performs no work, so almost everything here is a *reference* to
something another context owns. That is deliberate: a runtime that held the plan
would be a planner, and one that held the findings would be a knowledge store.
What it holds is enough to govern the lifecycle and nothing more.

Preconditions are declared, then satisfied
-------------------------------------------
A precondition is named when the mission is drafted and satisfied later, by
whoever can satisfy it. Mission Runtime never satisfies one itself -- it records
that someone did, and refuses ``READY`` while any remain outstanding.

Declaring them up front rather than checking them at launch is the point: a
precondition discovered at launch has already cost the delay it was meant to
prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "MissionKind",
    "MissionPriority",
    "MissionMetadata",
    "Precondition",
    "PlanRef",
]


class MissionKind(str, Enum):
    """What class of objective this is.

    Coarse on purpose. The kind steers policy defaults and reporting; it is not
    a taxonomy of everything an enterprise might ask for, and a runtime that
    tried to be one would need a new value for every customer.
    """

    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    OPTIMIZE = "optimize"
    REMEDIATE = "remediate"
    VALIDATE = "validate"
    AUDIT = "audit"

    @property
    def is_continuous(self) -> bool:
        """Whether this kind of mission is expected to run indefinitely.

        A monitor has no natural completion -- it is archived when someone stops
        caring, not when it finishes. Policy uses this to avoid warning about a
        long-running mission that is long-running by design.
        """
        return self is MissionKind.MONITOR

    @property
    def changes_the_world(self) -> bool:
        """Whether executing this kind of mission mutates a live system.

        ``REMEDIATE`` and ``OPTIMIZE`` act; the rest observe. Policy requires an
        explicit authorisation before a mission that acts may become ``READY``,
        because the cost of a wrong observation is a wrong answer and the cost of
        a wrong action is an outage.
        """
        return self in (MissionKind.REMEDIATE, MissionKind.OPTIMIZE)


class MissionPriority(str, Enum):
    ROUTINE = "routine"
    ELEVATED = "elevated"
    URGENT = "urgent"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _PRIORITY_RANK[self]

    @property
    def demands_immediate_attention(self) -> bool:
        return self in (MissionPriority.URGENT, MissionPriority.CRITICAL)


_PRIORITY_RANK = {
    MissionPriority.ROUTINE: 0,
    MissionPriority.ELEVATED: 1,
    MissionPriority.URGENT: 2,
    MissionPriority.CRITICAL: 3,
}


@dataclass(frozen=True)
class PlanRef:
    """Where the plan lives. Mission Runtime does not plan.

    Holding a reference rather than a plan is what keeps this context from
    becoming a planner. The runtime needs to know that planning happened and
    where to find it; it has no business knowing what the plan says.
    """

    plan_id: str
    produced_by: str = "planner"
    revision: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise ContractViolation(
                "a plan reference must name the plan; 'planned' with nothing to "
                "point at is an assertion about nothing"
            )
        if not isinstance(self.produced_by, str) or not self.produced_by.strip():
            raise ContractViolation("a plan reference must say who produced it")

    def __str__(self) -> str:
        return self.plan_id


@dataclass(frozen=True, order=True)
class Precondition:
    """Something that must hold before the mission may run."""

    key: str
    description: str = ""
    satisfied: bool = False
    satisfied_by: Optional[str] = None
    satisfied_at: Optional[datetime] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ContractViolation("a precondition must have a key")
        if self.key != self.key.strip():
            raise ContractViolation("a precondition key must not have surrounding whitespace")
        if self.satisfied:
            if not (self.satisfied_by and self.satisfied_by.strip()):
                raise ContractViolation(
                    f"precondition {self.key!r} is satisfied but names nobody; an "
                    "unattributed clearance has nobody accountable for it"
                )
            if self.satisfied_at is None:
                raise ContractViolation(
                    f"precondition {self.key!r} is satisfied but records no time"
                )
        elif self.satisfied_by is not None:
            raise ContractViolation(
                f"precondition {self.key!r} is unsatisfied but names a satisfier"
            )
        if self.satisfied_at is not None and self.satisfied_at.tzinfo is None:
            raise ContractViolation("satisfied_at must be timezone-aware")

    def satisfy(self, by: str, note: Optional[str] = None) -> "Precondition":
        if self.satisfied:
            raise ContractViolation(
                f"precondition {self.key!r} is already satisfied by {self.satisfied_by!r}"
            )
        if not by or not by.strip():
            raise ContractViolation("satisfying a precondition must say who did so")
        return replace(
            self,
            satisfied=True,
            satisfied_by=by.strip(),
            satisfied_at=datetime.now(timezone.utc),
            note=note.strip() if note and note.strip() else None,
        )


@dataclass(frozen=True)
class MissionMetadata(Contract):
    """What the mission is for, and how it should be treated."""

    CONTRACT_NAME = "cortexprime.mission.metadata"

    title: str
    kind: MissionKind
    priority: MissionPriority = MissionPriority.ROUTINE
    target: Optional[str] = None
    tags: frozenset = field(default_factory=frozenset)
    labels: tuple = ()

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ContractViolation("a mission must have a title")
        if not isinstance(self.kind, MissionKind):
            raise ContractViolation("kind must be a MissionKind")
        if not isinstance(self.priority, MissionPriority):
            raise ContractViolation("priority must be a MissionPriority")
        if self.target is not None and not self.target.strip():
            raise ContractViolation("target must be non-blank when given")
        if not isinstance(self.tags, (frozenset, set)):
            raise ContractViolation("tags must be a set")
        for tag in self.tags:
            if not isinstance(tag, str) or not tag.strip():
                raise ContractViolation("tags contains a blank entry")
        object.__setattr__(self, "tags", frozenset(t.strip() for t in self.tags))
        if not isinstance(self.labels, tuple):
            raise ContractViolation("labels must be a tuple")

    @classmethod
    def create(
        cls,
        title: str,
        kind: MissionKind,
        *,
        priority: MissionPriority = MissionPriority.ROUTINE,
        target: Optional[str] = None,
        tags: Sequence[str] = (),
    ) -> "MissionMetadata":
        return cls(
            title=title,
            kind=kind,
            priority=priority,
            target=target,
            tags=frozenset(tags),
        )
