"""The Execution Runtime bounded context (BC-5).

Workflow produced a validated, compiled execution graph. This runs it -- and runs
nothing itself, because every worker is a ``Protocol`` implemented somewhere this
context deliberately cannot see.

The first context here whose record is about the present
---------------------------------------------------------
Intent, Plan and Workflow describe work that has not happened. This one describes
work that is happening, while it is happening. That difference is where its rules
come from: they are not about documents being well-formed, they are about a
record staying true to a world that is changing underneath it.

The rule this context exists for
----------------------------------
**Only the worker holding the lease may record a result.** Two workers on one
node is the failure with no honest recovery -- the action happened twice, the
record shows once, and nothing in the system can say which result describes the
world. Every write goes through the lease check.

Unknown is a first-class outcome
----------------------------------
A lease that lapses without a result does not mean failure. It means nothing is
known: the work may have completed, may be half-applied, may never have started.
``UNKNOWN`` records that honestly, and it is what makes the retry rule
enforceable -- re-running an ambiguous mutation requires an idempotency key,
because a second application is exactly what the ambiguity is about. That is
Constitution P2 at the only moment it costs anything.

Workers are contracts, never implementations
----------------------------------------------
``ExecutionWorker`` is a Protocol. No browser, no shell, no Docker, no
Kubernetes. The runtime is written, tested and reasoned about against workers
that do not exist -- the same arrangement ADR-020 chose for the Engineering
Runtime, and for the same reason.

    domain/          pure -- state, leases, attempts, checkpoints, the aggregate
    application/     commands, queries, the worker pool, the service
    infrastructure/  repository, queue, record mapping

This context imports ``contracts/`` and ``platform/`` and nothing else.
See ADR-029.
"""

from backend.contexts.execution.application import (
    AssignNode,
    BindingValidator,
    CredentialProvider,
    InputValidator,
    WorkerAdmission,
    WorkerDirectory,
    WorkerInvocationRefused,
    WorkerKindPort,
    WorkerRuntime,
    classify_exception,
    AuthorityFacts,
    CapabilityAuthority,
    InvocationAdmission,
    InvocationOutcome,
    InvocationRecorder,
    LeaseAuthority,
    LeaseFacts,
    RateLimiter,
    SecureCapabilityInvocationGateway,
    BindingSource,
    CycleReport,
    DispatchResult,
    ExecutionDispatcher,
    ExecutionMetrics,
    ExecutionScheduler,
    InvocationRequestFactory,
    NullMetrics,
    RecordingMetrics,
    RecoveryCoordinator,
    RecoveryPlan,
    SafeMetrics,
    SchedulerState,
    StartupReport,
    TickReport,
    CompositeObserver,
    ExecutionObserver,
    ExecutionReplayer,
    Heartbeat,
    NullObserver,
    PlanRecovery,
    RecordingObserver,
    ReplayExecution,
    ReplayedExecution,
    ReplayFrame,
    SafeObserver,
    CancelExecution,
    CommandResult,
    CompensateNode,
    CompleteExecution,
    CreateCheckpoint,
    ExecutionService,
    FailExecution,
    GetExecution,
    GetReadyNodes,
    ListExecutions,
    PauseExecution,
    ReclaimNode,
    RecordFailure,
    RecordSuccess,
    RegisterWorker,
    ResumeExecution,
    RetryNode,
    SkipNode,
    StartExecution,
    TimeOutExecution,
    WorkerPool,
)
from backend.contexts.execution.domain import *  # noqa: F401,F403
from backend.contexts.execution.domain import __all__ as _domain_all
from backend.contexts.execution.infrastructure import (
    ADAPTER_UNAVAILABLE_REASON,
    AUTHORITY_REQUIRED_REASON,
    EXECUTION_BINDING,
    AdapterPreflight,
    AdapterSeam,
    AgentAdapter,
    AgentInvocation,
    AgentInvoker,
    ConnectorAdapter,
    ExecutionOutbox,
    HttpStatusTranslator,
    InMemoryExecutionOutbox,
    InMemoryWorkerDirectory,
    McpServerRef,
    McpToolAdapter,
    McpToolTarget,
    OperationInputValidator,
    OutboxEntry,
    OutboxStatus,
    ProviderChannel,
    ProviderExchange,
    ProviderOutcome,
    ProviderResponseTranslator,
    TestProviderAdapter,
    ExecutionQueue,
    ExecutionRepository,
    InMemoryExecutionQueue,
    InMemoryExecutionRepository,
    ConcurrentExecutionUpdate,
    QueueItem,
    UnregisteredWorker,
    WorkerAlreadyRegistered,
)

__all__ = list(_domain_all) + [
    "WorkerRuntime",
    "WorkerInvocationRefused",
    "BindingValidator",
    "WorkerKindPort",
    "WorkerDirectory",
    "WorkerAdmission",
    "InputValidator",
    "CredentialProvider",
    "classify_exception",

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

    "SecureCapabilityInvocationGateway",
    "InvocationAdmission",
    "InvocationOutcome",
    "AuthorityFacts",
    "LeaseFacts",
    "CapabilityAuthority",
    "LeaseAuthority",
    "InvocationRecorder",
    "RateLimiter",

    "ExecutionDispatcher",
    "CycleReport",
    "DispatchResult",
    "BindingSource",
    "InvocationRequestFactory",
    "RecoveryCoordinator",
    "RecoveryPlan",
    "StartupReport",
    "ExecutionScheduler",
    "SchedulerState",
    "TickReport",
    "ExecutionMetrics",
    "NullMetrics",
    "SafeMetrics",
    "RecordingMetrics",

    "ExecutionObserver",
    "NullObserver",
    "SafeObserver",
    "CompositeObserver",
    "RecordingObserver",
    "ExecutionReplayer",
    "ReplayedExecution",
    "ReplayFrame",
    "Heartbeat",
    "PlanRecovery",
    "ReplayExecution",
    "ExecutionOutbox",
    "InMemoryExecutionOutbox",
    "OutboxEntry",
    "OutboxStatus",

    "ExecutionService",
    "WorkerPool",
    "CommandResult",
    "StartExecution",
    "RegisterWorker",
    "AssignNode",
    "RecordSuccess",
    "RecordFailure",
    "ReclaimNode",
    "RetryNode",
    "SkipNode",
    "CompensateNode",
    "CreateCheckpoint",
    "PauseExecution",
    "ResumeExecution",
    "CompleteExecution",
    "FailExecution",
    "CancelExecution",
    "TimeOutExecution",
    "GetExecution",
    "GetReadyNodes",
    "ListExecutions",
    "ExecutionRepository",
    "InMemoryExecutionRepository",
    "ConcurrentExecutionUpdate",
    "EXECUTION_BINDING",
    "ExecutionQueue",
    "InMemoryExecutionQueue",
    "QueueItem",
]
