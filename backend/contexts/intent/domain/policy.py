"""Intent policy: whether a mandate is sound enough to act on.

The aggregate enforces *completeness* -- are the six elements present. This
decides *coherence*: do they hold together, and would a planner reading this be
able to act without guessing.

Kept out of the aggregate so the service can report every failure at once. A
validation refused one reason at a time takes five attempts to land, and the
fifth is made by someone who has stopped reading the refusals.

The rules, and the failure each prevents
-----------------------------------------
**I0 the intent is open.** An approved mandate is sealed.

**I1 the six elements are present.** Re-checked here so the report carries it
alongside everything else rather than raising first.

**I2 an acting objective has a hard constraint.** An objective that mutates a
live system with only soft boundaries hands a planner an effectively unbounded
mandate to change things.

**I3 production work names an approval.** Touching production without a recorded
approval constraint means the first human to see it will be whoever notices the
change.

**I4 a high-impact risk is accepted by somebody.** One acknowledged and not
accepted is one nobody has decided about. **Currently unreachable:**
``AcknowledgedRisk`` refuses to construct such a risk at all, so nothing that
exists today can produce one. The rule is kept as a second net for a record
assembled by some future path that bypasses construction -- and a test exercises
it by bypassing construction deliberately, so it cannot rot into dead code
nobody has run.

**I5 an averse appetite is contradicted by a tolerant scope.** Advisory: an
intent that says "prefer blocked over wrong" while scoping half the estate is
worth a second look before approval, not a refusal.

**I6 comparative criteria have baselines.** Advisory: "30% fewer errors" than
what, measured when? Settleable now, unanswerable after the before-state is gone.

**I7 a derived intent gets a closer look.** Advisory: nobody chose its words, so
an under-specified mandate is most likely to pass unnoticed here.

**I8 a critical intent stalled by approvals.** Advisory: the approval was the
right call and gathering it during an incident is not, which is worth knowing
before the incident.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contexts.intent.domain.constraints import ConstraintKind
from backend.contexts.intent.domain.priority import IntentPriority, RiskAppetite
from backend.contexts.intent.domain.status import (
    IntentStatus,
    is_legal_transition,
    permitted_from,
    refusal_reason,
)

__all__ = [
    "Severity",
    "PolicyFinding",
    "PolicyReport",
    "IntentPolicy",
    "default_policy",
    "BROAD_SCOPE_THRESHOLD",
]

#: Where a scope stops being a target and starts being an estate. A judgement,
#: stated here rather than buried in a conditional so it can be argued with.
BROAD_SCOPE_THRESHOLD = 10


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"

    @property
    def refuses(self) -> bool:
        return self is Severity.BLOCKING


@dataclass(frozen=True)
class PolicyFinding:
    rule: str
    severity: Severity
    detail: str
    subject: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class PolicyReport:
    findings: tuple = ()

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.refuses)

    @property
    def advisory(self) -> tuple:
        return tuple(f for f in self.findings if not f.severity.refuses)

    @property
    def may_proceed(self) -> bool:
        return not self.blocking


class IntentPolicy:
    """Decides whether an intent is sound enough to validate or approve."""

    def __init__(self, *, require_production_approval: bool = True) -> None:
        self._require_production_approval = require_production_approval

    @property
    def requires_production_approval(self) -> bool:
        return self._require_production_approval

    def evaluate(self, intent, to_status: IntentStatus) -> PolicyReport:
        """Every finding, not just the first."""
        findings: list = []

        # I0 -- the intent is open.
        if not intent.status.is_open:
            findings.append(
                PolicyFinding(
                    rule="I0-intent-open",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"the intent is {intent.status.value}; "
                        + (
                            refusal_reason(intent.status, to_status)
                            or "it may no longer be changed"
                        )
                    ),
                    subject=str(intent.intent_id),
                )
            )
            return PolicyReport(findings=tuple(findings))

        if not is_legal_transition(intent.status, to_status):
            findings.append(
                PolicyFinding(
                    rule="I0-legal-transition",
                    severity=Severity.BLOCKING,
                    detail=(
                        refusal_reason(intent.status, to_status)
                        or f"{intent.status.value} may only move to: "
                        f"{', '.join(permitted_from(intent.status))}"
                    ),
                    subject=to_status.value,
                )
            )

        # Everything below is about the mandate's substance, which only matters
        # when the intent is heading towards being acted on.
        if to_status not in (IntentStatus.VALIDATED, IntentStatus.APPROVED):
            return PolicyReport(findings=tuple(findings))

        # I1 -- the six elements.
        for element in intent.missing_elements:
            findings.append(
                PolicyFinding(
                    rule="I1-required-elements",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"no {element} is recorded; an intent without one is not a "
                        "mandate a planner can act on without guessing"
                    ),
                    subject=element,
                )
            )

        # I2 -- an acting objective has a hard boundary.
        if intent.changes_the_world and not intent.hard_constraints:
            findings.append(
                PolicyFinding(
                    rule="I2-acting-objective-bounded",
                    severity=Severity.BLOCKING,
                    detail=(
                        "this objective changes a live system and declares no hard "
                        "constraint; soft boundaries can be traded away, which makes "
                        "the mandate to change things effectively unbounded"
                    ),
                    subject=intent.objective.kind.value if intent.objective else None,
                )
            )

        # I3 -- production work names an approval.
        if self._require_production_approval and intent.touches_production:
            has_approval = any(
                c.kind is ConstraintKind.APPROVAL for c in intent.constraints
            )
            if not has_approval and intent.changes_the_world:
                findings.append(
                    PolicyFinding(
                        rule="I3-production-approval",
                        severity=Severity.BLOCKING,
                        detail=(
                            "this intent changes production and names no approval "
                            "constraint; without one the first human to see the change "
                            "is whoever notices it happened"
                        ),
                        subject="production",
                    )
                )

        # I4 -- a high-impact risk is somebody's to accept.
        for risk in intent.unaccepted_high_risks:
            findings.append(
                PolicyFinding(
                    rule="I4-risk-accepted",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"high-impact risk is acknowledged but not accepted: "
                        f"{risk.statement[:60]!r}"
                    ),
                    subject=str(risk.risk_id),
                )
            )

        # I5 -- appetite and breadth disagree.
        if (
            intent.risk_appetite is RiskAppetite.AVERSE
            and intent.scope is not None
            and intent.scope.breadth > BROAD_SCOPE_THRESHOLD
        ):
            findings.append(
                PolicyFinding(
                    rule="I5-appetite-matches-breadth",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"the appetite is 'averse' but the scope names "
                        f"{intent.scope.breadth} targets; a cautious mandate over a "
                        "broad estate usually means one of the two was not deliberate"
                    ),
                    subject=str(intent.scope.breadth),
                )
            )

        # I6 -- comparative criteria without a baseline.
        for criterion in intent.comparative_criteria_without_baseline:
            findings.append(
                PolicyFinding(
                    rule="I6-baseline-recorded",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"{criterion.statement[:60]!r} claims an improvement with no "
                        "baseline; it is settleable now and unanswerable once the "
                        "before-state is gone"
                    ),
                    subject=str(criterion.criterion_id),
                )
            )

        # I7 -- a derived intent had no author.
        if intent.metadata.origin.needs_stronger_review:
            findings.append(
                PolicyFinding(
                    rule="I7-derived-intent",
                    severity=Severity.ADVISORY,
                    detail=(
                        "this intent was derived rather than written; nobody chose its "
                        "words, which is when an under-specified mandate is most likely "
                        "to pass unnoticed"
                    ),
                    subject=intent.metadata.derived_from,
                )
            )

        # I8 -- a critical intent that will stall on approvals.
        if (
            intent.priority is IntentPriority.CRITICAL
            and any(c.kind is ConstraintKind.APPROVAL for c in intent.constraints)
        ):
            findings.append(
                PolicyFinding(
                    rule="I8-critical-awaiting-approval",
                    severity=Severity.ADVISORY,
                    detail=(
                        "a critical intent carries an approval constraint, so it will "
                        "stall waiting for a human. The constraint is right; gathering "
                        "the approval during the incident is what to avoid"
                    ),
                    subject=intent.priority.value,
                )
            )

        return PolicyReport(findings=tuple(findings))


def default_policy() -> IntentPolicy:
    """The policy the Constitution defines."""
    return IntentPolicy(require_production_approval=True)
