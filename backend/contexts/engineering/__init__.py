"""The Engineering Runtime.

Executes the Engineering Constitution's WorkOrder lifecycle. It orchestrates and
gates; it never implements, reviews, or verifies -- those are contexts reached
through ports this package defines.

    ports.py            the collaborators, as Protocols
    state_executor.py   legality, then policy
    policy.py           the checks a transition must pass
    lifecycle.py        which collaborator a phase needs
    event_log.py        append-only log plus dispatcher (outbox)
    runtime.py          the service that ties them together
    commands.py         commands and queries as values
    queries.py          the read side

This package imports **no bounded context**. Adapters are wired at the
composition root, the only layer permitted to see both sides.

See ADR-020.
"""

from backend.contexts.engineering.commands import (
    AdvanceWorkOrder,
    GetEventHistory,
    GetLifecycleCapability,
    GetRuntimeState,
    RejectWorkOrderCommand,
    ReplayWorkOrder,
    SupersedeWorkOrderCommand,
)
from backend.contexts.engineering.errors import (
    CollaboratorUnavailable,
    ConcurrentModification,
    EngineeringRuntimeError,
    IllegalTransition,
    PhaseUnknown,
    PolicyRefused,
    PreconditionFailed,
    TransitionRolledBack,
    WorkOrderUnknown,
)
from backend.contexts.engineering.event_log import (
    DeliveryFailure,
    EngineeringEventDispatcher,
    EngineeringEventLog,
    LoggedEvent,
)
from backend.contexts.engineering.events import (
    RUNTIME_EVENT_TYPES,
    WORK_ORDER_EVENT_ALIASES,
    ImplementationCompleted,
    ImplementationStarted,
    ReviewCompleted,
    ReviewRequested,
    VerificationCompleted,
    VerificationRequested,
)
from backend.contexts.engineering.lifecycle import (
    PHASE_REQUIREMENTS,
    Collaborators,
    WorkOrderLifecycleManager,
)
from backend.contexts.engineering.policy import (
    ARCHITECTURE_GATE_TRANSITION,
    EngineeringPolicy,
    PolicyCheck,
    PolicyFinding,
    PolicyResult,
    Severity,
    default_policy,
)
from backend.contexts.engineering.ports import (
    GOVERNED_PHASES,
    PHASE_TRANSITIONS,
    TERMINAL_PHASES,
    ContextBundleRef,
    ContextPort,
    ReviewOutcome,
    ReviewPort,
    VerificationOutcome,
    VerificationPort,
    WorkOrderPhase,
    WorkOrderPort,
    WorkOrderSnapshot,
)
from backend.contexts.engineering.queries import EngineeringRuntimeQueries, RuntimeState
from backend.contexts.engineering.runtime import EngineeringRuntime, TransitionResult
from backend.contexts.engineering.state_executor import (
    StateMachineExecutor,
    TransitionDecision,
    TransitionValidator,
    coerce_phase,
)

__all__ = [
    "EngineeringRuntime",
    "TransitionResult",
    "EngineeringRuntimeQueries",
    "RuntimeState",
    "Collaborators",
    "WorkOrderLifecycleManager",
    "PHASE_REQUIREMENTS",
    "StateMachineExecutor",
    "TransitionValidator",
    "TransitionDecision",
    "coerce_phase",
    "EngineeringPolicy",
    "PolicyCheck",
    "PolicyFinding",
    "PolicyResult",
    "Severity",
    "default_policy",
    "ARCHITECTURE_GATE_TRANSITION",
    "EngineeringEventLog",
    "EngineeringEventDispatcher",
    "LoggedEvent",
    "DeliveryFailure",
    "WorkOrderPhase",
    "WorkOrderSnapshot",
    "PHASE_TRANSITIONS",
    "TERMINAL_PHASES",
    "GOVERNED_PHASES",
    "WorkOrderPort",
    "ReviewPort",
    "VerificationPort",
    "ContextPort",
    "ReviewOutcome",
    "VerificationOutcome",
    "ContextBundleRef",
    "ImplementationStarted",
    "ImplementationCompleted",
    "ReviewRequested",
    "ReviewCompleted",
    "VerificationRequested",
    "VerificationCompleted",
    "RUNTIME_EVENT_TYPES",
    "WORK_ORDER_EVENT_ALIASES",
    "AdvanceWorkOrder",
    "RejectWorkOrderCommand",
    "SupersedeWorkOrderCommand",
    "GetRuntimeState",
    "GetEventHistory",
    "GetLifecycleCapability",
    "ReplayWorkOrder",
    "EngineeringRuntimeError",
    "IllegalTransition",
    "PhaseUnknown",
    "PolicyRefused",
    "PreconditionFailed",
    "CollaboratorUnavailable",
    "ConcurrentModification",
    "WorkOrderUnknown",
    "TransitionRolledBack",
]
