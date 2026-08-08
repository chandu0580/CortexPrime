"""Construction helpers.

The aggregate's constructor takes strongly-typed values and enforces every
invariant, which is correct and verbose. These are the ergonomic paths in: an
intent always keeps the requester's own words, a criterion always gets its
measure, and a constraint always gets its limit where one is required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from backend.contracts.identity import SecurityContext
from backend.contracts.mission import MissionIntent
from backend.contexts.intent.domain.constraints import (
    ConstraintEnforcement,
    ConstraintKind,
    IntentConstraint,
)
from backend.contexts.intent.domain.identifiers import IntentId
from backend.contexts.intent.domain.intent import Intent
from backend.contexts.intent.domain.metadata import IntentMetadata, IntentOrigin
from backend.contexts.intent.domain.objective import (
    IntentObjective,
    OutcomeKind,
    SuccessCriterion,
)
from backend.contexts.intent.domain.priority import AcknowledgedRisk, ImpactLevel
from backend.contexts.intent.domain.scope import Environment, IntentScope

__all__ = [
    "capture_intent",
    "objective",
    "constraint",
    "criterion",
    "risk",
    "scope",
]


def capture_intent(
    *,
    stated_goal: str,
    requested_by: SecurityContext,
    title: str,
    origin: IntentOrigin = IntentOrigin.HUMAN,
    tags: Sequence[str] = (),
    requested_for: Optional[str] = None,
    derived_from: Optional[str] = None,
    requested_at: Optional[datetime] = None,
) -> Intent:
    """A drafted intent holding the requester's words and nothing structured yet.

    Structure arrives through expansion. Capturing the sentence first and
    structuring it second is deliberate: an intent that could only be created
    fully-formed would force whoever captured it to invent the constraints and
    criteria on the requester's behalf, and invented constraints are worse than
    absent ones because they look decided.
    """
    return Intent(
        intent_id=IntentId.new(),
        raw=MissionIntent(
            stated_goal=stated_goal,
            requested_by=requested_by,
            requested_at=requested_at or datetime.now(timezone.utc),
        ),
        metadata=IntentMetadata.create(
            title,
            origin=origin,
            tags=tags,
            requested_for=requested_for,
            derived_from=derived_from,
        ),
    )


def objective(
    outcome: str,
    kind: OutcomeKind = OutcomeKind.UNDERSTAND,
    *,
    rationale: str = "",
    subject: Optional[str] = None,
) -> IntentObjective:
    return IntentObjective.create(outcome, kind, rationale=rationale, subject=subject)


def constraint(
    kind: ConstraintKind,
    statement: str,
    *,
    limit: Optional[str] = None,
    enforcement: ConstraintEnforcement = ConstraintEnforcement.HARD,
    rationale: str = "",
) -> IntentConstraint:
    return IntentConstraint.create(
        kind, statement, limit=limit, enforcement=enforcement, rationale=rationale
    )


def criterion(
    statement: str,
    measure: str,
    *,
    threshold: Optional[str] = None,
    baseline: Optional[str] = None,
) -> SuccessCriterion:
    """A success criterion. ``measure`` is mandatory and has no default.

    Defaulting it would be the single most damaging convenience in this context:
    every criterion would silently acquire a plausible-looking measure that
    nobody chose.
    """
    return SuccessCriterion.create(
        statement, measure, threshold=threshold, baseline=baseline
    )


def risk(
    statement: str,
    impact: ImpactLevel = ImpactLevel.LOW,
    *,
    accepted_by: Optional[str] = None,
) -> AcknowledgedRisk:
    return AcknowledgedRisk.create(statement, impact, accepted_by=accepted_by)


def scope(
    included: Sequence[str],
    *,
    excluded: Sequence[str] = (),
    environments: Iterable[Environment] = (Environment.DEVELOPMENT,),
    target_type: str = "system",
    note: Optional[str] = None,
) -> IntentScope:
    return IntentScope.of(
        included,
        excluded=excluded,
        environments=environments,
        target_type=target_type,
        note=note,
    )
