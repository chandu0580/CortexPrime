"""The Planner bounded context.

Intent said *what* the enterprise wants. Planner says *how* it would be achieved,
and produces nothing else.

What this context refuses to be
--------------------------------
**Planner never executes.** No results, no task outcomes, no execution state.
Every field describes work that has not happened. ``PlanTask.as_task_ref``
projects onto the published vocabulary with every task ``PENDING``, because a
planner that could emit ``SUCCEEDED`` would be reporting execution it did not do.

**Planner never invokes tools.** It *declares* what would be done -- an
``execution_key``, a ``SideEffectClass``, optionally a full ``ExecutionContract``
-- and the module those come from says plainly that they are declarations, not
invocations.

**Planner never modifies missions.** It holds ``mission_id`` and ``intent_id`` as
opaque strings, plus the intent's approval digest, and has no import path to
either context.

The checks only the whole plan can make
----------------------------------------
``TaskRef`` in ``contracts/mission.py`` enforces what it can locally and says the
rest belongs to whoever holds the graph:

    Cycles are forbidden by Constitution S4; detecting them requires the whole
    graph, so that check belongs to BC-1.

That check lives here, along with three more that need the whole plan:

* every task serves a goal -- work tracing to nothing asked for still spends the
  blast radius and the time;
* every success criterion is covered by a goal -- otherwise the plan can complete
  every task and still not achieve what was asked for;
* the declared risk is not below what the tasks imply -- risk that can be argued
  down without changing anything else is a mood, not an assessment.

And Constitution P2, *reversibility precedes action*, at both levels: a task that
mutates declares its reversal or names who accepted that it cannot be reversed,
and a plan that mutates cannot claim it needs no rollback.

    domain/          pure -- goals, tasks, the graph, strategy, risk, the plan
    application/     commands, queries, the service
    infrastructure/  repository, record mapping

This context imports ``contracts/`` and ``platform/`` and nothing else.
See ADR-027.
"""

from backend.contexts.planner.application import (
    AddDependency,
    AddGoal,
    AddTask,
    ApprovePlan,
    AssessRisk,
    CommandResult,
    DeclareCriteria,
    DraftPlan,
    GetGraph,
    GetPlan,
    ListPlans,
    PlannerService,
    RejectPlan,
    RemoveTask,
    RevisePlan,
    SetExecutionStrategy,
    SetRollbackStrategy,
    ValidatePlan,
)
from backend.contexts.planner.domain import (
    AGGREGATE_TYPE,
    ARTIFACT_KIND,
    BLAST_OUTLIER_RATIO,
    CANONICAL_FORM_VERSION,
    CyclicDependency,
    DanglingDependency,
    DependencyAdded,
    DependencyGraph,
    DigestMismatch,
    DigestNotComputed,
    DuplicatePlan,
    DuplicateTask,
    ExecutionMode,
    ExecutionStrategy,
    FailureResponse,
    GOVERNED_FIELDS,
    GoalId,
    GoalWithoutTasks,
    IllegalPlanTransition,
    IncompletePlan,
    InvalidIdentifier,
    Likelihood,
    OrphanTask,
    PLAN_EVENT_TYPES,
    Plan,
    PlanApproved,
    PlanApprovedError,
    PlanCreated,
    PlanError,
    PlanGoal,
    PlanId,
    PlanIsSuperseded,
    PlanNotFound,
    PlanPolicy,
    PlanRefused,
    PlanRejected,
    PlanRisk,
    PlanStatus,
    PlanTask,
    PlanValidated,
    PlanVersioned,
    PolicyFinding,
    PolicyReport,
    REQUIRED_ELEMENTS,
    Reversal,
    RiskAssessment,
    RiskId,
    RiskLevel,
    RiskUnderstated,
    RiskUpdated,
    RollbackKind,
    RollbackNotDeclared,
    RollbackStrategy,
    STATUS_TRANSITIONS,
    Severity,
    SuccessCriterionRef,
    TERMINAL_STATUSES,
    TaskAdded,
    UncoveredCriterion,
    UnknownGoal,
    UnknownTask,
    assessment,
    criterion,
    default_policy,
    draft_plan,
    goal,
    implied_floor,
    is_legal_transition,
    normalise_task_id,
    permitted_from,
    refusal_reason,
    reversal,
    risk,
    task,
)
from backend.contexts.planner.infrastructure import (
    InMemoryPlanRepository,
    PlanRepository,
)

__all__ = [
    # Aggregate and vocabulary
    "Plan",
    "PlanStatus",
    "STATUS_TRANSITIONS",
    "TERMINAL_STATUSES",
    "is_legal_transition",
    "permitted_from",
    "refusal_reason",
    "PlanId",
    "GoalId",
    "RiskId",
    "normalise_task_id",
    "PlanGoal",
    "SuccessCriterionRef",
    "PlanTask",
    "Reversal",
    "DependencyGraph",
    "ExecutionStrategy",
    "ExecutionMode",
    "FailureResponse",
    "RollbackStrategy",
    "RollbackKind",
    "RiskAssessment",
    "PlanRisk",
    "RiskLevel",
    "Likelihood",
    "implied_floor",
    # Policy
    "PlanPolicy",
    "PolicyReport",
    "PolicyFinding",
    "Severity",
    "default_policy",
    "BLAST_OUTLIER_RATIO",
    # Digest
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "REQUIRED_ELEMENTS",
    # Factories
    "draft_plan",
    "goal",
    "task",
    "reversal",
    "risk",
    "assessment",
    "criterion",
    # Application
    "PlannerService",
    "CommandResult",
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
    # Infrastructure
    "PlanRepository",
    "InMemoryPlanRepository",
    # Events
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
    # Errors
    "PlanError",
    "InvalidIdentifier",
    "IllegalPlanTransition",
    "PlanApprovedError",
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
