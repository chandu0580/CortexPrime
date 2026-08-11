"""Infrastructure: the repository, the queue, the record mapping, the worker
directory, and the adapter seams that perform no work.

``adapters/`` is deliberately here rather than in ``application/``: an adapter is
where a provider attaches, which makes it infrastructure by definition. Nothing
under it imports Connectivity, so the boundary holds.
"""

from backend.contexts.execution.infrastructure.worker_directory import (
    InMemoryWorkerDirectory,
    UnregisteredWorker,
    WorkerAlreadyRegistered,
)
from backend.contexts.execution.infrastructure.adapters import (
    ADAPTER_UNAVAILABLE_REASON,
    AUTHORITY_REQUIRED_REASON,
    AdapterPreflight,
    AdapterSeam,
    AgentAdapter,
    AgentInvocation,
    AgentInvoker,
    ConnectorAdapter,
    HttpStatusTranslator,
    McpServerRef,
    McpToolAdapter,
    McpToolTarget,
    ProviderChannel,
    ProviderExchange,
    ProviderOutcome,
    ProviderResponseTranslator,
    TestProviderAdapter,
)
from backend.contexts.execution.infrastructure.input_validation import (
    OperationInputValidator,
)
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
    ConcurrentExecutionUpdate,
    ExecutionRepository,
    InMemoryExecutionRepository,
)

__all__ = [
    "InMemoryWorkerDirectory",
    "WorkerAlreadyRegistered",
    "UnregisteredWorker",
    "AdapterSeam",
    "AdapterPreflight",
    "ProviderOutcome",
    "ADAPTER_UNAVAILABLE_REASON",
    "AUTHORITY_REQUIRED_REASON",
    "ProviderChannel",
    "ProviderExchange",
    "McpToolAdapter",
    "McpToolTarget",
    "McpServerRef",
    "ConnectorAdapter",
    "ProviderResponseTranslator",
    "HttpStatusTranslator",
    "AgentAdapter",
    "AgentInvoker",
    "AgentInvocation",
    "TestProviderAdapter",
    "OperationInputValidator",

    "ExecutionOutbox",
    "InMemoryExecutionOutbox",
    "OutboxEntry",
    "OutboxStatus",

    "ExecutionRepository",
    "InMemoryExecutionRepository",
    "ConcurrentExecutionUpdate",
    "EXECUTION_BINDING",
    "ExecutionQueue",
    "InMemoryExecutionQueue",
    "QueueItem",
    "RECORD_SCHEMA_VERSION",
    "to_record",
    "from_record",
]
