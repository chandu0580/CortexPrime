"""Failures raised by the Planner context.

Every one is a refusal to hand out a plan that cannot be executed safely or
cannot be shown to serve what was asked for.

The graph failures carry their evidence. A refusal that says "there is a cycle"
leaves whoever reads it to find the cycle; one that names ``a -> b -> c -> a``
has already done the work. That difference is the entire value of the check when
a plan has ninety tasks.

None of these are execution failures. This context runs nothing.
"""

from __future__ import annotations

from typing import Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "PlanError",
    "InvalidIdentifier",
    "IllegalPlanTransition",
    "PlanApproved",
    "PlanIsSuperseded",
    "CyclicDependency",
    "DanglingDependency",
    "DuplicateTask",
    "UnknownTask",
    "UnknownGoal",
    "OrphanTask",
    "UncoveredCriterion",
    "GoalWithoutTasks",
    "RollbackNotDeclared",
    "RiskUnderstated",
    "IncompletePlan",
    "PlanRefused",
    "DigestMismatch",
    "DigestNotComputed",
    "PlanNotFound",
    "DuplicatePlan",
]


class PlanError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(PlanError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class IllegalPlanTransition(PlanError):
    def __init__(
        self, *, plan_id: str, source: str, target: str, permitted: Sequence[str]
    ) -> None:
        allowed = ", ".join(sorted(permitted)) or "(nothing -- this state is terminal)"
        super().__init__(
            f"plan {plan_id} cannot move {source} -> {target}; {source} may only "
            f"move to: {allowed}"
        )
        self.plan_id = plan_id
        self.source = source
        self.target = target
        self.permitted = tuple(permitted)


class PlanApproved(PlanError):
    """The plan is approved and may not change.

    An approved plan is what execution acts on. One that changed afterwards
    would mean work was done against something nobody approved -- and the
    approval would be evidence for a plan that no longer exists. Revise it into
    a new version instead; the link is kept.
    """

    def __init__(self, *, plan_id: str, operation: str) -> None:
        super().__init__(
            f"plan {plan_id} is approved; {operation} would change a plan execution "
            "has already been authorised to act on. Revise it into a new version"
        )
        self.plan_id = plan_id
        self.operation = operation


class PlanIsSuperseded(PlanError):
    def __init__(self, *, plan_id: str, successor: str) -> None:
        super().__init__(
            f"plan {plan_id} is superseded by {successor}; a later version replaced it"
        )
        self.plan_id = plan_id
        self.successor = successor


class CyclicDependency(PlanError):
    """The task graph contains a cycle.

    ``TaskRef`` enforces that a task cannot depend on itself; the whole-graph
    check is explicitly delegated to whoever holds the graph, which is this
    context. A cycle means no task in it can ever become ready, so the plan
    would stall forever rather than fail -- which is the worse outcome, because
    stalling looks like slowness.
    """

    def __init__(self, cycle: Sequence[str]) -> None:
        path = " -> ".join(list(cycle) + [cycle[0]]) if cycle else "?"
        super().__init__(
            f"the task graph contains a cycle: {path}. No task in a cycle can ever "
            "become ready, so the plan would stall rather than fail"
        )
        self.cycle = tuple(cycle)


class DanglingDependency(PlanError):
    """A task depends on something the plan does not contain."""

    def __init__(self, *, task_id: str, missing: Sequence[str]) -> None:
        listed = ", ".join(sorted(missing))
        super().__init__(
            f"task {task_id!r} depends on {listed}, which the plan does not contain; "
            "the dependency can never be satisfied and the task can never start"
        )
        self.task_id = task_id
        self.missing = tuple(missing)


class DuplicateTask(PlanError):
    def __init__(self, task_id: str) -> None:
        super().__init__(
            f"task {task_id!r} is already in the plan; two tasks with one id make "
            "every dependency naming it ambiguous"
        )
        self.task_id = task_id


class UnknownTask(PlanError):
    def __init__(self, *, plan_id: str, task_id: str) -> None:
        super().__init__(f"plan {plan_id} has no task {task_id!r}")
        self.plan_id = plan_id
        self.task_id = task_id


class UnknownGoal(PlanError):
    def __init__(self, *, plan_id: str, goal_id: str) -> None:
        super().__init__(f"plan {plan_id} has no goal {goal_id!r}")
        self.plan_id = plan_id
        self.goal_id = goal_id


class OrphanTask(PlanError):
    """A task that serves no goal is work nobody asked for."""

    def __init__(self, orphans: Sequence[str]) -> None:
        listed = ", ".join(sorted(orphans)[:5])
        more = f" (+{len(orphans) - 5} more)" if len(orphans) > 5 else ""
        super().__init__(
            f"{len(orphans)} task(s) serve no goal: {listed}{more}. Work that traces "
            "to no goal is work nobody asked for, and it will still consume the "
            "blast radius and the time"
        )
        self.orphans = tuple(orphans)


class UncoveredCriterion(PlanError):
    """A success criterion no goal claims to satisfy.

    The plan can complete every task and still not achieve what was asked for.
    That is the failure a plan is supposed to make impossible.
    """

    def __init__(self, uncovered: Sequence[str]) -> None:
        listed = ", ".join(sorted(uncovered)[:5])
        more = f" (+{len(uncovered) - 5} more)" if len(uncovered) > 5 else ""
        super().__init__(
            f"{len(uncovered)} success criterion/criteria are covered by no goal: "
            f"{listed}{more}. The plan could complete every task and still not "
            "achieve what was asked for"
        )
        self.uncovered = tuple(uncovered)


class GoalWithoutTasks(PlanError):
    def __init__(self, goals: Sequence[str]) -> None:
        listed = ", ".join(sorted(goals))
        super().__init__(
            f"goal(s) {listed} have no tasks; a goal nothing works towards will not "
            "be achieved by the plan claiming it"
        )
        self.goals = tuple(goals)


class RollbackNotDeclared(PlanError):
    """Constitution P2: reversibility precedes action.

    A plan that mutates and declares no way back is one whose failure mode is
    "leave it half-applied and call somebody". The published
    ``ExecutionContract`` enforces the same rule per action; this is the plan-level
    half.
    """

    def __init__(self, *, mutating: Sequence[str], strategy: str) -> None:
        listed = ", ".join(sorted(mutating)[:5])
        more = f" (+{len(mutating) - 5} more)" if len(mutating) > 5 else ""
        super().__init__(
            f"{len(mutating)} task(s) change state ({listed}{more}) but the rollback "
            f"strategy is {strategy!r}; Constitution P2 requires reversibility to be "
            "decided before action, not discovered after it"
        )
        self.mutating = tuple(mutating)
        self.strategy = strategy


class RiskUnderstated(PlanError):
    """The declared risk is below what the plan's own tasks imply.

    Risk that can be talked down is not an assessment. The floor is computed from
    the side-effect classes the plan itself declares, so understating it requires
    also understating what the tasks do -- which is a different and much more
    visible lie.
    """

    def __init__(self, *, declared: str, implied: str, driver: str) -> None:
        super().__init__(
            f"the plan declares {declared!r} risk but contains {driver}, which implies "
            f"at least {implied!r}. A risk level below what the tasks do is not an "
            "assessment"
        )
        self.declared = declared
        self.implied = implied
        self.driver = driver


class IncompletePlan(PlanError):
    def __init__(self, *, plan_id: str, missing: Sequence[str]) -> None:
        listed = ", ".join(sorted(missing))
        super().__init__(f"plan {plan_id} is missing: {listed}")
        self.plan_id = plan_id
        self.missing = tuple(missing)


class PlanRefused(PlanError):
    """Policy refused, with every reason at once."""

    def __init__(self, *, plan_id: str, target: str, failures: Sequence) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in list(failures)[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(f"plan {plan_id} cannot be {target} -- {summary}{more}")
        self.plan_id = plan_id
        self.target = target
        self.failures = tuple(failures)


class DigestMismatch(PlanError):
    def __init__(self, *, plan_id: str, recorded: str, recomputed: str) -> None:
        super().__init__(
            f"plan {plan_id}: approved with digest {recorded} but content now hashes "
            f"to {recomputed}; the plan on record is not the one approved"
        )
        self.plan_id = plan_id
        self.recorded = recorded
        self.recomputed = recomputed


class DigestNotComputed(PlanError):
    def __init__(self, plan_id: str) -> None:
        super().__init__(f"plan {plan_id} has no digest; digests are computed at approval")
        self.plan_id = plan_id


class PlanNotFound(PlanError):
    def __init__(self, plan_id: str) -> None:
        super().__init__(f"no plan with id {plan_id}")
        self.plan_id = plan_id


class DuplicatePlan(PlanError):
    def __init__(self, plan_id: str) -> None:
        super().__init__(f"plan {plan_id} already exists")
        self.plan_id = plan_id
