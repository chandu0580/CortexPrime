"""Infrastructure: the repository, the queue, and the record mapping."""

from backend.contexts.execution.infrastructure.outbox import (
    ExecutionOutbox,
    InMemoryExecutionOutbox,
    OutboxEntry,
    OutboxStatus,
)
from backend.contexts.execution.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.contexts.execution.infrastructure.queue import (
    ExecutionQueue,
    InMemoryExecutionQueue,
    QueueItem,
)
from backend.contexts.execution.infrastructure.repository import (
    EXECUTION_BINDING,
    ExecutionRepository,
    InMemoryExecutionRepository,
)

__all__ = [
    "ExecutionOutbox",
    "InMemoryExecutionOutbox",
    "OutboxEntry",
    "OutboxStatus",

    "ExecutionRepository",
    "InMemoryExecutionRepository",
    "EXECUTION_BINDING",
    "ExecutionQueue",
    "InMemoryExecutionQueue",
    "QueueItem",
    "RECORD_SCHEMA_VERSION",
    "to_record",
    "from_record",
]
