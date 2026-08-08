"""WorkOrder domain: entities, value objects, events, and invariants.

Pure. No I/O, no persistence, no framework. Everything here is decidable from
its inputs, which is what makes the invariants testable without a database and
the digest reproducible without a running system.
"""

from backend.contexts.workorder.domain.assumption import Assumption, AssumptionResolution
from backend.contexts.workorder.domain.blast_radius import BlastRadius, PathPattern
from backend.contexts.workorder.domain.digest import (
    ARTIFACT_KIND,
    CANONICAL_FORM_VERSION,
    GOVERNED_FIELDS,
    compute_work_order_digest,
    digest_matches,
    digest_payload,
)
from backend.contexts.workorder.domain.errors import (
    BlastRadiusViolation,
    DigestMismatch,
    DigestNotComputed,
    DuplicateWorkOrder,
    ImmutableAfterApproval,
    InvalidIdentifier,
    InvalidTransition,
    TerminalState,
    UnresolvedReference,
    ValidationFailed,
    WorkOrderError,
    WorkOrderNotFound,
)
from backend.contexts.workorder.domain.factory import AssumptionSpec, draft_work_order
from backend.contexts.workorder.domain.identifiers import (
    AdrRef,
    AssumptionId,
    ConstraintRef,
    EvidenceRef,
    RejectionGroundId,
    WorkOrderId,
)
from backend.contexts.workorder.domain.rejection import (
    RejectionGround,
    RejectionType,
    Raiser,
    Resolver,
)
from backend.contexts.workorder.domain.states import (
    ALLOWED,
    FORBIDDEN,
    TERMINAL_STATES,
    WorkOrderState,
    is_allowed,
    transition_reason,
)
from backend.contexts.workorder.domain.validation import (
    Decidability,
    Finding,
    ReferenceResolver,
    Severity,
    StaticReferenceResolver,
    ValidationReport,
    validate,
)
from backend.contexts.workorder.domain.work_order import Priority, WorkOrder

__all__ = [
    "WorkOrder", "Priority", "WorkOrderState", "ALLOWED", "FORBIDDEN",
    "TERMINAL_STATES", "is_allowed", "transition_reason",
    "WorkOrderId", "AssumptionId", "RejectionGroundId", "AdrRef", "EvidenceRef",
    "ConstraintRef",
    "Assumption", "AssumptionResolution",
    "RejectionGround", "RejectionType", "Raiser", "Resolver",
    "BlastRadius", "PathPattern",
    "AssumptionSpec", "draft_work_order",
    "validate", "ValidationReport", "Finding", "Severity", "Decidability",
    "ReferenceResolver", "StaticReferenceResolver",
    "compute_work_order_digest", "digest_matches", "digest_payload",
    "ARTIFACT_KIND", "CANONICAL_FORM_VERSION", "GOVERNED_FIELDS",
    "WorkOrderError", "InvalidIdentifier", "InvalidTransition", "TerminalState",
    "ImmutableAfterApproval", "DigestMismatch", "DigestNotComputed",
    "BlastRadiusViolation", "ValidationFailed", "UnresolvedReference",
    "WorkOrderNotFound", "DuplicateWorkOrder",
]
