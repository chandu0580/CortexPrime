"""The Planner domain: pure, no I/O, no framework.

    status      the lifecycle from draft to approved
    goals       outcomes, and the criteria they trace back to
    tasks       planned work, and how it would be undone
    graph       the dependency DAG and the checks only the whole graph can make
    strategy    how the plan would be run, and walked back
    risk        the assessment, floored by what the tasks imply
    plan        the aggregate and its digest
    policy      whether the plan is advisable, reporting every reason
"""

from backend.contexts.planner.domain.errors import (
    CyclicDependency,
    DanglingDependency,
    DigestMismatch,
    DigestNotComputed,
    DuplicatePlan,
    DuplicateTask,
    GoalWithoutTasks,
    IllegalPlanTransition,
    IncompletePlan,
    InvalidIdentifier,
    OrphanTask,
    PlanApproved as PlanApprovedError,
    PlanError,
    PlanIsSuperseded,
    PlanNotFound,
    PlanRefused,
    RiskUnderstated,
    RollbackNotDeclared,
    UncoveredCriterion,
    UnknownGoal,
    UnknownTask,
)
from backend.contexts.planner.domain.events import (
    AGGREGATE_TYPE,
    PLAN_EVENT_TYPES,
    DependencyAdded,
    PlanApproved,
    PlanCreated,
    PlanRejected,
    PlanValidated,
    PlanVersioned,
    RiskUpdated,
    TaskAdded,
)
from backend.contexts.planner.domain.factory import (
    assessment,
    criterion,
    draft_plan,
    goal,
    reversal,
    risk,
    task,
)
from backend.contexts.planner.domain.goals import PlanGoal, SuccessCriterionRef
from backend.contexts.planner.domain.graph import DependencyGraph
from backend.contexts.planner.domain.identifiers import (
    GoalId,
    PlanId,
    RiskId,
    normalise_task_id,
)
from backend.contexts.planner.domain.plan import (
    ARTIFACT_KIND,
    CANONICAL_FORM_VERSION,
    GOVERNED_FIELDS,
    REQUIRED_ELEMENTS,
    Plan,
)
from backend.contexts.planner.domain.policy import (
    BLAST_OUTLIER_RATIO,
    PlanPolicy,
    PolicyFinding,
    PolicyReport,
    Severity,
    default_policy,
)
from backend.contexts.planner.domain.risk import (
    Likelihood,
    PlanRisk,
    RiskAssessment,
    RiskLevel,
    implied_floor,
)
from backend.contexts.planner.domain.status import (
    STATUS_TRANSITIONS,
    TERMINAL_STATUSES,
    PlanStatus,
    is_legal_transition,
    permitted_from,
    refusal_reason,
)
from backend.contexts.planner.domain.strategy import (
    ExecutionMode,
    ExecutionStrategy,
    FailureResponse,
    RollbackKind,
    RollbackStrategy,
)
from backend.contexts.planner.domain.tasks import PlanTask, Reversal

__all__ = [
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
    "PlanPolicy",
    "PolicyReport",
    "PolicyFinding",
    "Severity",
    "default_policy",
    "BLAST_OUTLIER_RATIO",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "REQUIRED_ELEMENTS",
    "draft_plan",
    "goal",
    "task",
    "reversal",
    "risk",
    "assessment",
    "criterion",
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
