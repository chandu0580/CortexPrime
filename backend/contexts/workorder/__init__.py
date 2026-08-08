"""The WorkOrder bounded context.

Owns the unit of engineering work defined by the Engineering Constitution and
the Engineering Artifact Specification: the WorkOrder aggregate, its lifecycle,
its blast radius, its assumptions and rejection grounds, and the canonical
digest that makes approval bind to content rather than to a name.

Layered, and the direction is enforced by ``DEP-LAYERS``::

    domain/          pure -- no I/O, no framework, no persistence
    application/     commands, queries, and the service that runs them
    infrastructure/  repository, record mapping, reference resolution

This context imports ``contracts/`` and ``platform/`` and nothing else. It emits
events; it does not publish them -- it owns no bus, and reaching for one would
couple it to infrastructure it has no business knowing about.
"""

from backend.contexts.workorder.application import (
    ApproveWorkOrder, CheckBlastRadiusConflicts, CommandResult, DraftWorkOrder,
    ExpandBlastRadius, GetWorkOrder, ListWorkOrders, RejectWorkOrder, Reprioritise,
    ResolveAssumption, SupersedeWorkOrder, TransitionWorkOrder, WorkOrderService,
)
from backend.contexts.workorder.domain import (
    Assumption, AssumptionResolution, AssumptionSpec, BlastRadius, PathPattern,
    Priority, RejectionGround, RejectionType, StaticReferenceResolver, WorkOrder,
    WorkOrderId, WorkOrderState, draft_work_order, validate,
)
from backend.contexts.workorder.infrastructure import (
    FilesystemReferenceResolver, InMemoryWorkOrderRepository, WorkOrderRepository,
)

__all__ = [
    "WorkOrder", "WorkOrderId", "WorkOrderState", "Priority", "BlastRadius",
    "PathPattern", "Assumption", "AssumptionResolution", "AssumptionSpec",
    "RejectionGround", "RejectionType", "draft_work_order", "validate",
    "StaticReferenceResolver", "FilesystemReferenceResolver",
    "WorkOrderService", "CommandResult",
    "DraftWorkOrder", "ApproveWorkOrder", "TransitionWorkOrder", "RejectWorkOrder",
    "ResolveAssumption", "ExpandBlastRadius", "Reprioritise", "SupersedeWorkOrder",
    "GetWorkOrder", "ListWorkOrders", "CheckBlastRadiusConflicts",
    "WorkOrderRepository", "InMemoryWorkOrderRepository",
]
