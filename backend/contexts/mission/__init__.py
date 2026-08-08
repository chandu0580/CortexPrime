"""The Mission Runtime bounded context (BC-1).

A mission is a long-running enterprise objective -- *monitor this cluster*,
*investigate this incident*, *reduce this bill*. This context owns the lifecycle
of every one of them and performs none of the work.

Two lifecycles, one gate
------------------------
``MissionStatus`` is **operational** and this context owns it: draft, planned,
ready, running, paused, completed, failed, cancelled, archived.

``contracts.mission.MissionState`` is **execution** and Constitution S4 owns it:
received, interpreted, gathering, reasoning, planned, awaiting_decision,
executing, verifying, compensating, concluded. Mission Runtime records it and
gates on it; Execution and Verification advance it.

``RUNNING -> COMPLETED`` is refused unless the execution reached ``CONCLUDED``,
and S4 forbids ``EXECUTING -> CONCLUDED`` directly. So a mission cannot be
reported complete over work nobody verified -- from either side. That gate is
why two machines are safer here than one. See ADR-025.

What this context cannot do
---------------------------
Plan, execute, gather, reason, or store what was learned. It holds *references*
to those things -- a plan id, an executor ref, a checkpoint payload ref -- and no
import path to the contexts that own them. A runtime that held the plan would be
a planner; one that held the findings would be a knowledge store.

    domain/          pure -- status, timeline, checkpoints, the aggregate
    application/     commands, queries, the service
    infrastructure/  repository, record mapping

This context imports ``contracts/`` and ``platform/`` and nothing else.
"""

from backend.contexts.mission.application import (
    AdvanceExecution,
    ArchiveMission,
    CancelMission,
    CommandResult,
    CompleteMission,
    CreateMission,
    DeclarePrecondition,
    FailMission,
    GetMission,
    GetTimeline,
    ListMissions,
    MissionService,
    PauseMission,
    RecordCheckpoint,
    RecordPlan,
    ResumeMission,
    SatisfyPrecondition,
    StartMission,
    TransitionMission,
)
from backend.contexts.mission.domain import (
    ARTIFACT_KIND,
    AUTHORISATION_PRECONDITION,
    CANONICAL_FORM_VERSION,
    CHECKPOINT_KIND,
    CheckpointId,
    DigestMismatch,
    DigestNotComputed,
    DuplicateMission,
    ExecutionAlreadyOpen,
    ExecutionId,
    ExecutionOutcome,
    GOVERNED_FIELDS,
    IllegalExecutionTransition,
    IllegalStatusTransition,
    InvalidIdentifier,
    MISSION_EVENT_TYPES,
    Mission,
    MissionArchived,
    MissionArchivedError,
    MissionCancelled,
    MissionCheckpoint,
    MissionCheckpointReached,
    MissionCompleted,
    MissionCreated,
    MissionError,
    MissionExecution,
    MissionFailed,
    MissionId,
    MissionKind,
    MissionMetadata,
    MissionNotFound,
    MissionPaused,
    MissionPolicy,
    MissionPriority,
    MissionResumed,
    MissionStarted,
    MissionStatus,
    MissionTerminal,
    MissionTimeline,
    MissionTimelineEntry,
    NoOpenExecution,
    NoPlanRecorded,
    OUTCOME_STATUSES,
    PlanRef,
    PolicyFinding,
    PolicyReport,
    Precondition,
    PreconditionsUnmet,
    STATUS_TRANSITIONS,
    Severity,
    TERMINAL_STATUSES,
    TimelineEntryKind,
    TimelineOutOfOrder,
    TransitionRefused,
    UnknownCheckpoint,
    VerificationNotReached,
    default_policy,
    draft_mission,
    is_legal_status_transition,
    permitted_from,
    plan_ref,
    precondition,
    refusal_reason,
)
from backend.contexts.mission.infrastructure import (
    InMemoryMissionRepository,
    MissionRepository,
)

__all__ = [
    # Aggregate and vocabulary
    "Mission",
    "MissionStatus",
    "STATUS_TRANSITIONS",
    "TERMINAL_STATUSES",
    "OUTCOME_STATUSES",
    "is_legal_status_transition",
    "permitted_from",
    "refusal_reason",
    "MissionId",
    "ExecutionId",
    "CheckpointId",
    "MissionMetadata",
    "MissionKind",
    "MissionPriority",
    "PlanRef",
    "Precondition",
    "MissionExecution",
    "ExecutionOutcome",
    "MissionCheckpoint",
    "CHECKPOINT_KIND",
    "MissionTimeline",
    "MissionTimelineEntry",
    "TimelineEntryKind",
    # Policy
    "MissionPolicy",
    "PolicyReport",
    "PolicyFinding",
    "Severity",
    "default_policy",
    "AUTHORISATION_PRECONDITION",
    # Digest
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    # Factories
    "draft_mission",
    "precondition",
    "plan_ref",
    # Application
    "MissionService",
    "CommandResult",
    "CreateMission",
    "RecordPlan",
    "DeclarePrecondition",
    "SatisfyPrecondition",
    "TransitionMission",
    "StartMission",
    "PauseMission",
    "ResumeMission",
    "AdvanceExecution",
    "RecordCheckpoint",
    "CompleteMission",
    "FailMission",
    "CancelMission",
    "ArchiveMission",
    "GetMission",
    "GetTimeline",
    "ListMissions",
    # Infrastructure
    "MissionRepository",
    "InMemoryMissionRepository",
    # Events
    "MissionCreated",
    "MissionStarted",
    "MissionPaused",
    "MissionResumed",
    "MissionCheckpointReached",
    "MissionCompleted",
    "MissionFailed",
    "MissionCancelled",
    "MissionArchived",
    "MISSION_EVENT_TYPES",
    # Errors
    "MissionError",
    "InvalidIdentifier",
    "IllegalStatusTransition",
    "IllegalExecutionTransition",
    "MissionTerminal",
    "MissionArchivedError",
    "VerificationNotReached",
    "PreconditionsUnmet",
    "NoPlanRecorded",
    "NoOpenExecution",
    "ExecutionAlreadyOpen",
    "UnknownCheckpoint",
    "TimelineOutOfOrder",
    "TransitionRefused",
    "DigestMismatch",
    "DigestNotComputed",
    "MissionNotFound",
    "DuplicateMission",
]
