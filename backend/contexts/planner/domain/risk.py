"""Risk assessment: declared, and floored by what the plan's own tasks do.

The rule that makes this an assessment rather than an adjective
----------------------------------------------------------------
A declared risk level below what the tasks imply is refused. The floor is
computed from the ``SideEffectClass`` of the tasks themselves:

* any ``DESTRUCTIVE`` task            → at least ``SEVERE``
* any ``IRREVERSIBLE_WRITE`` task     → at least ``ELEVATED``
* any mutation with no way back       → at least ``ELEVATED``
* everything else                     → ``LOW`` is permitted

So talking the risk down requires also understating what the tasks do, which is a
different and much more visible lie. Risk that can be argued down without
changing anything else is not an assessment; it is a mood.

The floor is a floor, never a ceiling. A plan of pure reads may be declared
``SEVERE`` -- reading the wrong production database at the wrong moment is a real
risk, and nothing here knows enough to argue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Final, Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contexts.planner.domain.errors import RiskUnderstated
from backend.contexts.planner.domain.identifiers import RiskId

__all__ = [
    "RiskLevel",
    "Likelihood",
    "PlanRisk",
    "RiskAssessment",
    "implied_floor",
]


class RiskLevel(str, Enum):
    """How much is at stake if the plan goes wrong."""

    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    SEVERE = "severe"

    @property
    def rank(self) -> int:
        return _LEVEL_RANK[self]

    def __lt__(self, other) -> bool:  # type: ignore[override]
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank < other.rank

    @property
    def demands_mitigation(self) -> bool:
        """Whether a risk at this level must say what is being done about it."""
        return self in (RiskLevel.ELEVATED, RiskLevel.SEVERE)


_LEVEL_RANK: Final[dict] = {
    RiskLevel.LOW: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.ELEVATED: 2,
    RiskLevel.SEVERE: 3,
}


class Likelihood(str, Enum):
    UNLIKELY = "unlikely"
    POSSIBLE = "possible"
    LIKELY = "likely"

    @property
    def rank(self) -> int:
        return {"unlikely": 0, "possible": 1, "likely": 2}[self.value]


def implied_floor(tasks: Sequence) -> tuple:
    """The lowest risk level the plan's own tasks permit, and why.

    Returns ``(level, driver)``. The driver is what a refusal quotes, because
    "at least elevated" without the reason is a number somebody will argue with.
    """
    destructive = [t for t in tasks if t.side_effect is SideEffectClass.DESTRUCTIVE]
    if destructive:
        return (
            RiskLevel.SEVERE,
            f"{len(destructive)} destructive task(s), e.g. {destructive[0].task_id!r}",
        )

    irreversible = [
        t for t in tasks if t.side_effect is SideEffectClass.IRREVERSIBLE_WRITE
    ]
    if irreversible:
        return (
            RiskLevel.ELEVATED,
            f"{len(irreversible)} irreversible write(s), e.g. {irreversible[0].task_id!r}",
        )

    unbacked = [t for t in tasks if t.mutates and not t.is_reversible]
    if unbacked:
        return (
            RiskLevel.ELEVATED,
            f"{len(unbacked)} mutation(s) with no declared way back, e.g. "
            f"{unbacked[0].task_id!r}",
        )

    if any(t.mutates for t in tasks):
        return (RiskLevel.MODERATE, "reversible changes to live state")

    return (RiskLevel.LOW, "no task changes anything")


@dataclass(frozen=True)
class PlanRisk(Contract):
    """One thing the planner believes could go wrong."""

    CONTRACT_NAME = "cortexprime.planner.risk"

    risk_id: RiskId
    statement: str
    level: RiskLevel = RiskLevel.LOW
    likelihood: Likelihood = Likelihood.POSSIBLE
    mitigation: Optional[str] = None
    affected_tasks: tuple = ()
    declared_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.risk_id, RiskId):
            raise ContractViolation("risk_id must be a RiskId")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ContractViolation("a risk must state what could go wrong")
        if not isinstance(self.level, RiskLevel):
            raise ContractViolation("level must be a RiskLevel")
        if not isinstance(self.likelihood, Likelihood):
            raise ContractViolation("likelihood must be a Likelihood")
        if not isinstance(self.affected_tasks, tuple):
            raise ContractViolation("affected_tasks must be a tuple")

        if self.level.demands_mitigation and not (
            self.mitigation and self.mitigation.strip()
        ):
            raise ContractViolation(
                f"a {self.level.value!r} risk must say what is being done about it: "
                f"{self.statement[:60]!r}. One recorded without a mitigation is a "
                "worry, not a plan"
            )
        if self.declared_at.tzinfo is None:
            raise ContractViolation("declared_at must be timezone-aware")

    @property
    def is_mitigated(self) -> bool:
        return bool(self.mitigation and self.mitigation.strip())

    @classmethod
    def create(
        cls,
        statement: str,
        level: RiskLevel = RiskLevel.LOW,
        *,
        likelihood: Likelihood = Likelihood.POSSIBLE,
        mitigation: Optional[str] = None,
        affected_tasks: Sequence[str] = (),
    ) -> "PlanRisk":
        return cls(
            risk_id=RiskId.new(),
            statement=statement,
            level=level,
            likelihood=likelihood,
            mitigation=mitigation,
            affected_tasks=tuple(affected_tasks),
        )


@dataclass(frozen=True)
class RiskAssessment(Contract):
    """What the planner says the plan is worth worrying about."""

    CONTRACT_NAME = "cortexprime.planner.risk_assessment"

    overall: RiskLevel = RiskLevel.LOW
    risks: tuple = ()
    assessed_by: str = "planner"
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.overall, RiskLevel):
            raise ContractViolation("overall must be a RiskLevel")
        if not isinstance(self.risks, tuple):
            raise ContractViolation("risks must be a tuple")
        for risk in self.risks:
            if not isinstance(risk, PlanRisk):
                raise ContractViolation(f"risks contains {risk!r}, which is not a PlanRisk")
        if not isinstance(self.assessed_by, str) or not self.assessed_by.strip():
            raise ContractViolation("an assessment must name who made it")

        # The overall level cannot sit below the worst individual risk either.
        # Otherwise a plan lists a severe risk and calls itself low overall.
        worst = max((r.level for r in self.risks), default=RiskLevel.LOW)
        if self.overall.rank < worst.rank:
            raise ContractViolation(
                f"the assessment is {self.overall.value!r} overall but lists a "
                f"{worst.value!r} risk; the overall level cannot be below the worst "
                "thing in it"
            )

    # -- queries -------------------------------------------------------

    @property
    def unmitigated(self) -> tuple:
        return tuple(r for r in self.risks if r.level.demands_mitigation and not r.is_mitigated)

    @property
    def severe_risks(self) -> tuple:
        return tuple(r for r in self.risks if r.level is RiskLevel.SEVERE)

    def assert_covers(self, tasks: Sequence) -> None:
        """Refuse an assessment that sits below what the tasks imply."""
        floor, driver = implied_floor(tasks)
        if self.overall.rank < floor.rank:
            raise RiskUnderstated(
                declared=self.overall.value, implied=floor.value, driver=driver
            )

    @classmethod
    def create(
        cls,
        overall: RiskLevel = RiskLevel.LOW,
        *,
        risks: Sequence = (),
        assessed_by: str = "planner",
        note: str = "",
    ) -> "RiskAssessment":
        return cls(
            overall=overall, risks=tuple(risks), assessed_by=assessed_by, note=note
        )
