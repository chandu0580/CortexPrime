"""The Intent bounded context.

Intent turns a sentence somebody typed into a mandate an automated system can act
on without guessing. It is the canonical input to planning, and it produces
nothing else.

BC-1 is "Intent & Mission" (see ``backend/contracts/mission.py``). Intent is
Mission's sibling, not its parent: an approved intent is what a mission is
created *from*, and the two contexts do not import each other.

What this context refuses to be
--------------------------------
**Intent never plans.** It holds no tasks, no steps, no ordering, no tool
selection. The moment an intent could express a plan, the boundary between
wanting something and deciding how to get it would be gone -- and that boundary
is what lets a human approve the first without implicitly approving the second.

**Intent never executes.** Every field is a statement about what should become
true; none records anything having happened.

The six things an intent must contain
--------------------------------------
Objective, constraints, scope, priority, risk, success criteria. Each has a rule
about what makes it real, and each is refused at construction rather than flagged
later:

* **A success criterion nobody can check is a wish.** Every criterion names how
  it is measured. "The system should be faster" cannot be satisfied or refuted,
  so an executor cannot know when to stop.
* **A quantitative constraint carries its limit.** "Keep costs down" states a
  concern, not a boundary.
* **A scope that includes nothing authorises nothing** -- and one that both
  includes and excludes a target is a contradiction nobody downstream can
  resolve.

    domain/          pure -- objective, constraints, scope, priority, the aggregate
    application/     commands, queries, the service
    infrastructure/  repository, record mapping

This context imports ``contracts/`` and ``platform/`` and nothing else.
See ADR-026.
"""

from backend.contexts.intent.application import (
    AcknowledgeRisk,
    AddConstraint,
    AddSuccessCriterion,
    ApproveIntent,
    CaptureIntent,
    CommandResult,
    GetIntent,
    IntentService,
    ListIntents,
    RejectIntent,
    RemoveConstraint,
    RemoveSuccessCriterion,
    SetObjective,
    SetPriority,
    SetRiskAppetite,
    SetScope,
    SupersedeIntent,
    ValidateIntent,
)
from backend.contexts.intent.domain import (
    AGGREGATE_TYPE,
    ARTIFACT_KIND,
    AcknowledgedRisk,
    BROAD_SCOPE_THRESHOLD,
    CANONICAL_FORM_VERSION,
    ConstraintEnforcement,
    ConstraintId,
    ConstraintKind,
    ContradictoryScope,
    CriterionId,
    DigestMismatch,
    DigestNotComputed,
    DuplicateConstraint,
    DuplicateIntent,
    EmptyScope,
    Environment,
    GOVERNED_FIELDS,
    INTENT_EVENT_TYPES,
    IllegalIntentTransition,
    ImpactLevel,
    IncompleteIntent,
    Intent,
    IntentApproved,
    IntentApprovedError,
    IntentConstraint,
    IntentCreated,
    IntentError,
    IntentExpanded,
    IntentId,
    IntentIsSuperseded,
    IntentMetadata,
    IntentNotFound,
    IntentObjective,
    IntentOrigin,
    IntentPolicy,
    IntentPriority,
    IntentRejected,
    IntentScope,
    IntentStatus,
    IntentSuperseded,
    IntentValidated,
    InvalidIdentifier,
    MIRRORED_PRIORITY_VALUES,
    OutcomeKind,
    PolicyFinding,
    PolicyReport,
    REQUIRED_ELEMENTS,
    RiskAppetite,
    RiskId,
    STATUS_TRANSITIONS,
    ScopeTarget,
    Severity,
    SuccessCriterion,
    TERMINAL_STATUSES,
    UnboundedConstraint,
    UnknownConstraint,
    UnknownCriterion,
    UnmeasurableCriterion,
    ValidationRefused,
    capture_intent,
    constraint,
    criterion,
    default_policy,
    is_legal_transition,
    objective,
    permitted_from,
    refusal_reason,
    risk,
    scope,
)
from backend.contexts.intent.infrastructure import (
    InMemoryIntentRepository,
    IntentRepository,
)

__all__ = [
    # Aggregate and vocabulary
    "Intent",
    "IntentStatus",
    "STATUS_TRANSITIONS",
    "TERMINAL_STATUSES",
    "is_legal_transition",
    "permitted_from",
    "refusal_reason",
    "IntentId",
    "ConstraintId",
    "CriterionId",
    "RiskId",
    "IntentObjective",
    "OutcomeKind",
    "SuccessCriterion",
    "IntentConstraint",
    "ConstraintKind",
    "ConstraintEnforcement",
    "IntentScope",
    "ScopeTarget",
    "Environment",
    "IntentPriority",
    "RiskAppetite",
    "ImpactLevel",
    "AcknowledgedRisk",
    "MIRRORED_PRIORITY_VALUES",
    "IntentMetadata",
    "IntentOrigin",
    # Policy
    "IntentPolicy",
    "PolicyReport",
    "PolicyFinding",
    "Severity",
    "default_policy",
    "BROAD_SCOPE_THRESHOLD",
    # Digest
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "REQUIRED_ELEMENTS",
    # Factories
    "capture_intent",
    "objective",
    "constraint",
    "criterion",
    "risk",
    "scope",
    # Application
    "IntentService",
    "CommandResult",
    "CaptureIntent",
    "SetObjective",
    "SetScope",
    "SetPriority",
    "SetRiskAppetite",
    "AddConstraint",
    "RemoveConstraint",
    "AddSuccessCriterion",
    "RemoveSuccessCriterion",
    "AcknowledgeRisk",
    "ValidateIntent",
    "ApproveIntent",
    "RejectIntent",
    "SupersedeIntent",
    "GetIntent",
    "ListIntents",
    # Infrastructure
    "IntentRepository",
    "InMemoryIntentRepository",
    # Events
    "AGGREGATE_TYPE",
    "IntentCreated",
    "IntentValidated",
    "IntentExpanded",
    "IntentApproved",
    "IntentRejected",
    "IntentSuperseded",
    "INTENT_EVENT_TYPES",
    # Errors
    "IntentError",
    "InvalidIdentifier",
    "IllegalIntentTransition",
    "IntentApprovedError",
    "IntentIsSuperseded",
    "UnmeasurableCriterion",
    "UnboundedConstraint",
    "EmptyScope",
    "ContradictoryScope",
    "IncompleteIntent",
    "ValidationRefused",
    "UnknownConstraint",
    "UnknownCriterion",
    "DuplicateConstraint",
    "DigestMismatch",
    "DigestNotComputed",
    "IntentNotFound",
    "DuplicateIntent",
]
