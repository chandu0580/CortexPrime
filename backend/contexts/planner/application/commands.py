"""Commands and queries for the Planner context.

Frozen values naming one intent each, carrying primitives rather than domain
objects so a command can be serialised, queued, and replayed without dragging the
domain across the wire.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "DraftPlan",
    "AddGoal",
    "AddTask",
    "RemoveTask",
    "AddDependency",
    "DeclareCriteria",
    "SetExecutionStrategy",
    "SetRollbackStrategy",
    "AssessRisk",
    "ValidatePlan",
    "ApprovePlan",
    "RejectPlan",
    "RevisePlan",
    "GetPlan",
    "GetGraph",
    "ListPlans",
]

#: Side effects that change the world. Mirrors ``SideEffectClass.mutates`` so the
#: command can refuse before loading; the domain enforces it regardless.
_MUTATING = frozenset({"reversible_write", "irreversible_write", "destructive"})


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class DraftPlan:
    mission_id: str
    intent_id: str
    intent_digest: str
    title: str
    planned_by: str = "planner"

    def __post_init__(self) -> None:
        _require(bool(self.mission_id), "mission_id is required")
        _require(bool(self.intent_id), "intent_id is required")
        _require(
            bool(self.intent_digest and self.intent_digest.strip()),
            "intent_digest is required; without it the plan cannot be shown to serve "
            "the mandate that was actually approved",
        )
        _require(bool(self.title and self.title.strip()), "title is required")


@dataclass(frozen=True)
class AddGoal:
    plan_id: str
    statement: str
    satisfies: tuple = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(
            bool(self.statement and self.statement.strip()),
            "a goal must state the outcome it produces",
        )
        _require(
            bool(self.satisfies),
            "a goal must trace to at least one success criterion; one that satisfies "
            "nothing asked for is work the plan invented",
        )


@dataclass(frozen=True)
class AddTask:
    plan_id: str
    task_id: str
    purpose: str
    goals: tuple = ()
    depends_on: tuple = ()
    side_effect: str = "read"
    compensating_task: Optional[str] = None
    inverse_action: Optional[str] = None
    irreversible_accepted_by: Optional[str] = None
    execution_key: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(bool(self.task_id and self.task_id.strip()), "task_id is required")
        _require(
            bool(self.purpose and self.purpose.strip()),
            "a task must state its purpose; one nobody can explain is one nobody can "
            "review",
        )
        _require(
            bool(self.goals),
            "a task must serve at least one goal; work that traces to nothing asked "
            "for still spends the blast radius and the time",
        )
        _require(
            self.side_effect not in _MUTATING
            or bool(self.compensating_task or self.inverse_action)
            or bool(self.irreversible_accepted_by),
            f"a {self.side_effect!r} task must declare a reversal or name who accepted "
            "that it cannot be reversed; Constitution P2 requires the answer before "
            "the action",
        )


@dataclass(frozen=True)
class RemoveTask:
    plan_id: str
    task_id: str

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(bool(self.task_id), "task_id is required")


@dataclass(frozen=True)
class AddDependency:
    plan_id: str
    task_id: str
    depends_on: str

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(bool(self.task_id), "task_id is required")
        _require(bool(self.depends_on), "depends_on is required")
        _require(
            self.task_id != self.depends_on, "a task cannot depend on itself"
        )


@dataclass(frozen=True)
class DeclareCriteria:
    plan_id: str
    criteria: tuple = ()

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(
            bool(self.criteria),
            "a plan must carry the criteria it is answerable for",
        )


@dataclass(frozen=True)
class SetExecutionStrategy:
    plan_id: str
    mode: str = "sequential"
    on_failure: str = "halt"
    max_parallelism: int = 1
    checkpoint_after: tuple = ()
    continue_justification: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(self.max_parallelism >= 1, "max_parallelism must be positive")
        _require(
            self.on_failure != "continue"
            or bool(self.continue_justification and self.continue_justification.strip()),
            "a strategy that continues past a failure must justify it; carrying on "
            "after a failed task is how a plan produces a half-applied change",
        )


@dataclass(frozen=True)
class SetRollbackStrategy:
    plan_id: str
    kind: str = "none_required"
    description: str = ""
    accepted_by: Optional[str] = None
    snapshot_of: tuple = ()

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(
            self.kind != "forward_fix_only"
            or bool(self.accepted_by and self.accepted_by.strip()),
            "a forward-fix-only rollback must name who accepted it; 'there is no way "
            "back' is a decision somebody makes, not a property a plan has",
        )
        _require(
            self.kind != "snapshot_restore" or bool(self.snapshot_of),
            "a snapshot-restore rollback must name what is snapshotted",
        )


@dataclass(frozen=True)
class AssessRisk:
    plan_id: str
    overall: str = "low"
    risks: tuple = ()
    assessed_by: str = "planner"
    note: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(bool(self.overall), "overall is required")
        _require(
            bool(self.assessed_by and self.assessed_by.strip()),
            "an assessment must name who made it",
        )


@dataclass(frozen=True)
class ValidatePlan:
    plan_id: str

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")


@dataclass(frozen=True)
class ApprovePlan:
    plan_id: str
    approved_by: str

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(
            bool(self.approved_by and self.approved_by.strip()),
            "an approval must name who gave it; an unattributed authorisation has "
            "nobody accountable for it",
        )


@dataclass(frozen=True)
class RejectPlan:
    plan_id: str
    reason: str
    rejected_by: str = "reviewer"

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(
            bool(self.reason and self.reason.strip()),
            "rejecting a plan must say why; the next version is built from the reason",
        )


@dataclass(frozen=True)
class RevisePlan:
    plan_id: str
    reason: str = "a revised version replaces this one"

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")


@dataclass(frozen=True)
class GetPlan:
    plan_id: str


@dataclass(frozen=True)
class GetGraph:
    plan_id: str


@dataclass(frozen=True)
class ListPlans:
    mission_id: Optional[str] = None
    intent_id: Optional[str] = None
    status: Optional[str] = None
    executable_only: bool = False
