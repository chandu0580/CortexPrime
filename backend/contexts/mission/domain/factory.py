"""Construction helpers.

The aggregate's constructor takes strongly-typed values and enforces every
invariant, which is correct and verbose. These are the ergonomic paths in: a
mission always gets the requester's own words, and a precondition always gets a
key someone can satisfy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from backend.contracts.identity import SecurityContext
from backend.contracts.mission import MissionIntent
from backend.contexts.mission.domain.identifiers import MissionId
from backend.contexts.mission.domain.metadata import (
    MissionKind,
    MissionMetadata,
    MissionPriority,
    PlanRef,
    Precondition,
)
from backend.contexts.mission.domain.mission import Mission

__all__ = ["draft_mission", "precondition", "plan_ref"]


def draft_mission(
    *,
    stated_goal: str,
    requested_by: SecurityContext,
    title: str,
    kind: MissionKind,
    priority: MissionPriority = MissionPriority.ROUTINE,
    target: Optional[str] = None,
    tags: Sequence[str] = (),
    preconditions: Iterable[Precondition] = (),
    requested_at: Optional[datetime] = None,
) -> Mission:
    """A drafted mission carrying the requester's own words verbatim.

    ``stated_goal`` is preserved rather than normalised. Storing only an
    interpretation would make it impossible to audit whether CortexPrime solved
    the problem it was actually asked to solve -- which is the published
    ``MissionIntent`` contract's stated reason for existing, and it holds here.
    """
    return Mission(
        mission_id=MissionId.new(),
        intent=MissionIntent(
            stated_goal=stated_goal,
            requested_by=requested_by,
            requested_at=requested_at or datetime.now(timezone.utc),
        ),
        metadata=MissionMetadata.create(
            title,
            kind,
            priority=priority,
            target=target,
            tags=tags,
        ),
        preconditions=tuple(preconditions),
    )


def precondition(
    key: str, description: str = "", *, satisfied: bool = False, by: Optional[str] = None
) -> Precondition:
    """A precondition, unsatisfied by default.

    Defaulting to unsatisfied is the safe direction: a precondition that defaults
    to met is one nobody notices they never checked.
    """
    if satisfied:
        return Precondition(
            key=key,
            description=description,
            satisfied=True,
            satisfied_by=by or "operator",
            satisfied_at=datetime.now(timezone.utc),
        )
    return Precondition(key=key, description=description)


def plan_ref(plan_id: str, *, produced_by: str = "planner", revision: Optional[str] = None) -> PlanRef:
    return PlanRef(plan_id=plan_id, produced_by=produced_by, revision=revision)
