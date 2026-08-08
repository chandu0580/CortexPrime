"""Plan lifecycle events.

Namespaced ``planner.runtime.*``. ``CONTRACT_NAME`` is globally unique and a
clash raises at import time.

These describe a plan *being built and decided on*, never work. There is no
``TaskStarted``, no ``TaskSucceeded``: this context produces plans and has
nothing to say about what execution did with one.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "PlanCreated",
    "PlanValidated",
    "PlanApproved",
    "PlanRejected",
    "PlanVersioned",
    "TaskAdded",
    "DependencyAdded",
    "RiskUpdated",
    "PLAN_EVENT_TYPES",
]

AGGREGATE_TYPE = "plan"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class PlanCreated(DomainEvent):
    """A plan was opened against a mission and an approved intent."""

    EVENT_TYPE = "planner.runtime.created"

    plan_id: str = ""
    mission_id: str = ""
    intent_id: str = ""
    intent_digest: str = ""
    title: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("plan_id", self.plan_id)
        _require_text("mission_id", self.mission_id)
        _require_text("intent_id", self.intent_id)
        _require_text(
            "intent_digest",
            self.intent_digest,
        )
        if self.version < 1:
            raise ContractViolation("version starts at 1")


@dataclass(frozen=True)
class TaskAdded(DomainEvent):
    """A unit of planned work was added. Nothing has run."""

    EVENT_TYPE = "planner.runtime.task_added"

    plan_id: str = ""
    task_id: str = ""
    purpose: str = ""
    side_effect: str = ""
    goal_count: int = 0
    reversible: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("plan_id", self.plan_id)
        _require_text("task_id", self.task_id)
        _require_text("side_effect", self.side_effect)
        if not isinstance(self.reversible, bool):
            raise ContractViolation("reversible must be a bool")
        if self.goal_count < 1:
            raise ContractViolation(
                "a task serves at least one goal; work that traces to nothing asked "
                "for still spends the blast radius and the time"
            )


@dataclass(frozen=True)
class DependencyAdded(DomainEvent):
    """One task was made to wait for another.

    Carries the resulting depth, because that is what the edge actually cost: a
    dependency that adds a layer adds a sequential step to every run of the plan.
    """

    EVENT_TYPE = "planner.runtime.dependency_added"

    plan_id: str = ""
    task_id: str = ""
    depends_on: str = ""
    graph_depth: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("plan_id", self.plan_id)
        _require_text("task_id", self.task_id)
        _require_text("depends_on", self.depends_on)
        if self.task_id == self.depends_on:
            raise ContractViolation("a task cannot depend on itself")


@dataclass(frozen=True)
class RiskUpdated(DomainEvent):
    """The risk assessment changed.

    Refuses construction below the implied floor, mirroring the aggregate: an
    event that could describe an understated assessment would make the log a
    worse record than the plan.
    """

    EVENT_TYPE = "planner.runtime.risk_updated"

    plan_id: str = ""
    overall: str = ""
    implied_floor: str = ""
    risk_count: int = 0
    unmitigated: int = 0
    assessed_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("plan_id", self.plan_id)
        _require_text("overall", self.overall)
        _require_text("implied_floor", self.implied_floor)

        order = {"low": 0, "moderate": 1, "elevated": 2, "severe": 3}
        if order.get(self.overall, 0) < order.get(self.implied_floor, 0):
            raise ContractViolation(
                f"an assessment of {self.overall!r} is below the {self.implied_floor!r} "
                "its own tasks imply"
            )


@dataclass(frozen=True)
class PlanValidated(DomainEvent):
    """The plan is complete and its graph is sound."""

    EVENT_TYPE = "planner.runtime.validated"

    plan_id: str = ""
    version: int = 1
    goals: int = 0
    tasks: int = 0
    graph_depth: int = 0
    widest_layer: int = 0
    missing_elements: int = 0
    advisories: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("plan_id", self.plan_id)
        if self.missing_elements:
            raise ContractViolation(
                f"a plan cannot be validated with {self.missing_elements} required "
                "element(s) missing"
            )
        if self.tasks < 1:
            raise ContractViolation("a validated plan contains at least one task")
        if self.goals < 1:
            raise ContractViolation("a validated plan contains at least one goal")


@dataclass(frozen=True)
class PlanApproved(DomainEvent):
    """The plan was accepted. Execution may act on it."""

    EVENT_TYPE = "planner.runtime.approved"

    plan_id: str = ""
    version: int = 1
    approved_by: str = ""
    digest: str = ""
    overall_risk: str = ""
    mutating_tasks: int = 0
    rollback_kind: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("plan_id", self.plan_id)
        _require_text("digest", self.digest)
        _require_text("approved_by", self.approved_by)
        _require_text("rollback_kind", self.rollback_kind)

        # Constitution P2, on the event as well as the aggregate.
        if self.mutating_tasks and self.rollback_kind == "none_required":
            raise ContractViolation(
                "a plan that changes state cannot be approved with no rollback "
                "strategy; reversibility is decided before action (P2)"
            )


@dataclass(frozen=True)
class PlanRejected(DomainEvent):
    EVENT_TYPE = "planner.runtime.rejected"

    plan_id: str = ""
    reason: str = ""
    rejected_by: str = ""
    rejected_from: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("plan_id", self.plan_id)
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class PlanVersioned(DomainEvent):
    """A later version was opened from this plan.

    Both stay on record, which is what makes "what changed between v2 and v3"
    answerable at all.
    """

    EVENT_TYPE = "planner.runtime.versioned"

    plan_id: str = ""
    successor_id: str = ""
    from_version: int = 1
    to_version: int = 2
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("plan_id", self.plan_id)
        _require_text("successor_id", self.successor_id)
        if self.plan_id == self.successor_id:
            raise ContractViolation("a plan cannot be its own successor")
        if self.to_version <= self.from_version:
            raise ContractViolation(
                f"version {self.to_version} does not follow {self.from_version}"
            )


PLAN_EVENT_TYPES = (
    PlanCreated,
    PlanValidated,
    PlanApproved,
    PlanRejected,
    PlanVersioned,
    TaskAdded,
    DependencyAdded,
    RiskUpdated,
)
