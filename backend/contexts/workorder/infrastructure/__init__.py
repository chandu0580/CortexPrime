"""WorkOrder persistence and reference resolution."""

from backend.contexts.workorder.infrastructure.adr_resolver import FilesystemReferenceResolver
from backend.contexts.workorder.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.contexts.workorder.infrastructure.repository import (
    WORK_ORDER_BINDING,
    InMemoryWorkOrderRepository,
    WorkOrderRepository,
)

__all__ = [
    "WorkOrderRepository",
    "InMemoryWorkOrderRepository",
    "WORK_ORDER_BINDING",
    "to_record",
    "from_record",
    "RECORD_SCHEMA_VERSION",
    "FilesystemReferenceResolver",
]
