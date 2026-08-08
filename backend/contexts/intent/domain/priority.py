"""Priority and risk appetite: how urgent, and how much risk is acceptable.

``IntentPriority`` mirrors the Mission context deliberately
------------------------------------------------------------
The values are exactly ``MissionPriority``'s, and this is **not** an import:
Constitution S2 forbids one bounded context importing another, and an approved
intent becomes a mission, so a priority that existed on one side and not the
other would silently downgrade in translation.

The duplication is made safe the way ADR-023 made the claim vocabulary safe:
``test_priority.py`` runs both enums over the same values and asserts they agree,
member for member, so a divergence names itself instead of shipping.

Risk appetite is not the same as risk
--------------------------------------
Appetite is what the *requester* will accept before work starts. A discovered
risk is what the work found. Only the first belongs in an intent -- the second
cannot exist yet -- and conflating them would let an intent pre-declare risks
nobody has looked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Final, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.intent.domain.identifiers import RiskId

__all__ = [
    "IntentPriority",
    "RiskAppetite",
    "ImpactLevel",
    "AcknowledgedRisk",
    "MIRRORED_PRIORITY_VALUES",
]


class IntentPriority(str, Enum):
    """How urgently the requester needs this.

    Values mirror ``MissionPriority`` exactly. See the module docstring.
    """

    ROUTINE = "routine"
    ELEVATED = "elevated"
    URGENT = "urgent"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _PRIORITY_RANK[self]

    @property
    def demands_immediate_attention(self) -> bool:
        return self in (IntentPriority.URGENT, IntentPriority.CRITICAL)

    @property
    def tolerates_deferred_approval(self) -> bool:
        """Whether waiting for a human approval is acceptable at this priority.

        ``CRITICAL`` does not -- which is a reason to have gathered the approvals
        *before* the incident, not a reason to skip them during one. Policy uses
        this to flag a critical intent whose approval constraints will stall it.
        """
        return self is not IntentPriority.CRITICAL


_PRIORITY_RANK: Final[dict] = {
    IntentPriority.ROUTINE: 0,
    IntentPriority.ELEVATED: 1,
    IntentPriority.URGENT: 2,
    IntentPriority.CRITICAL: 3,
}

#: The values the Mission context must agree with. Named so the drift test reads
#: as a statement about a contract rather than a list of strings.
MIRRORED_PRIORITY_VALUES: Final[tuple] = tuple(p.value for p in IntentPriority)


class RiskAppetite(str, Enum):
    """How much risk the requester will accept in pursuit of the objective.

    Three values, and the middle one is the honest default rather than a place to
    hide: ``MEASURED`` means "take risks you can explain", which is a real
    stance. ``AVERSE`` means prefer failing to proceeding on uncertainty --
    Constitution S6's *prefer blocked over wrong*, stated by the requester.
    """

    AVERSE = "averse"
    MEASURED = "measured"
    TOLERANT = "tolerant"

    @property
    def prefers_blocked_over_wrong(self) -> bool:
        return self is RiskAppetite.AVERSE

    @property
    def rank(self) -> int:
        return _APPETITE_RANK[self]


_APPETITE_RANK: Final[dict] = {
    RiskAppetite.AVERSE: 0,
    RiskAppetite.MEASURED: 1,
    RiskAppetite.TOLERANT: 2,
}


class ImpactLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def requires_acceptance(self) -> bool:
        """Whether somebody has to say out loud that they accept this.

        Only ``HIGH``. A risk the requester acknowledges as high-impact and does
        not explicitly accept is one nobody has actually decided about.
        """
        return self is ImpactLevel.HIGH


@dataclass(frozen=True)
class AcknowledgedRisk(Contract):
    """A risk the requester knows about before the work starts.

    Not a discovered risk -- nothing has been investigated yet. This is what the
    requester already believes could go wrong, recorded so that a planner is not
    the first party to think of it.
    """

    CONTRACT_NAME = "cortexprime.intent.acknowledged_risk"

    risk_id: RiskId
    statement: str
    impact: ImpactLevel = ImpactLevel.LOW
    accepted_by: Optional[str] = None
    declared_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.risk_id, RiskId):
            raise ContractViolation("risk_id must be a RiskId")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ContractViolation("a risk must state what could go wrong")
        if not isinstance(self.impact, ImpactLevel):
            raise ContractViolation("impact must be an ImpactLevel")

        if self.impact.requires_acceptance and not (
            self.accepted_by and self.accepted_by.strip()
        ):
            raise ContractViolation(
                f"a high-impact risk must name who accepted it: {self.statement[:60]!r}. "
                "One acknowledged and not accepted is one nobody has decided about"
            )
        if self.declared_at.tzinfo is None:
            raise ContractViolation("declared_at must be timezone-aware")

    @classmethod
    def create(
        cls,
        statement: str,
        impact: ImpactLevel = ImpactLevel.LOW,
        *,
        accepted_by: Optional[str] = None,
    ) -> "AcknowledgedRisk":
        return cls(
            risk_id=RiskId.new(),
            statement=statement,
            impact=impact,
            accepted_by=accepted_by,
        )
