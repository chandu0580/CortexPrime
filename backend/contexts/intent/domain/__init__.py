"""The Intent domain: pure, no I/O, no framework.

    status       the lifecycle from sentence to mandate
    objective    what should become true, and how anyone would know
    constraints  the boundaries it must be pursued within
    scope        what it is about, and what it is not
    priority     urgency, risk appetite, and acknowledged risks
    metadata     labels and provenance
    intent       the aggregate and its digest
    policy       whether the mandate is sound, reporting every reason
"""

from backend.contexts.intent.domain.constraints import (
    ConstraintEnforcement,
    ConstraintKind,
    IntentConstraint,
)
from backend.contexts.intent.domain.errors import (
    ContradictoryScope,
    DigestMismatch,
    DigestNotComputed,
    DuplicateConstraint,
    DuplicateIntent,
    EmptyScope,
    IllegalIntentTransition,
    IncompleteIntent,
    IntentApproved as IntentApprovedError,
    IntentError,
    IntentIsSuperseded,
    IntentNotFound,
    InvalidIdentifier,
    UnboundedConstraint,
    UnknownConstraint,
    UnknownCriterion,
    UnmeasurableCriterion,
    ValidationRefused,
)
from backend.contexts.intent.domain.events import (
    AGGREGATE_TYPE,
    INTENT_EVENT_TYPES,
    IntentApproved,
    IntentCreated,
    IntentExpanded,
    IntentRejected,
    IntentSuperseded,
    IntentValidated,
)
from backend.contexts.intent.domain.factory import (
    capture_intent,
    constraint,
    criterion,
    objective,
    risk,
    scope,
)
from backend.contexts.intent.domain.identifiers import (
    ConstraintId,
    CriterionId,
    IntentId,
    RiskId,
)
from backend.contexts.intent.domain.intent import (
    ARTIFACT_KIND,
    CANONICAL_FORM_VERSION,
    GOVERNED_FIELDS,
    REQUIRED_ELEMENTS,
    Intent,
)
from backend.contexts.intent.domain.metadata import IntentMetadata, IntentOrigin
from backend.contexts.intent.domain.objective import (
    IntentObjective,
    OutcomeKind,
    SuccessCriterion,
)
from backend.contexts.intent.domain.policy import (
    BROAD_SCOPE_THRESHOLD,
    IntentPolicy,
    PolicyFinding,
    PolicyReport,
    Severity,
    default_policy,
)
from backend.contexts.intent.domain.priority import (
    MIRRORED_PRIORITY_VALUES,
    AcknowledgedRisk,
    ImpactLevel,
    IntentPriority,
    RiskAppetite,
)
from backend.contexts.intent.domain.scope import Environment, IntentScope, ScopeTarget
from backend.contexts.intent.domain.status import (
    STATUS_TRANSITIONS,
    TERMINAL_STATUSES,
    IntentStatus,
    is_legal_transition,
    permitted_from,
    refusal_reason,
)

__all__ = [
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
    "IntentPolicy",
    "PolicyReport",
    "PolicyFinding",
    "Severity",
    "default_policy",
    "BROAD_SCOPE_THRESHOLD",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "REQUIRED_ELEMENTS",
    "capture_intent",
    "objective",
    "constraint",
    "criterion",
    "risk",
    "scope",
    "AGGREGATE_TYPE",
    "IntentCreated",
    "IntentValidated",
    "IntentExpanded",
    "IntentApproved",
    "IntentRejected",
    "IntentSuperseded",
    "INTENT_EVENT_TYPES",
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
