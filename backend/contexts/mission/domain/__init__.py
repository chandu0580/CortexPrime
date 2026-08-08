"""The Mission Runtime domain: pure, no I/O, no framework.

    status      the operational lifecycle this context owns
    metadata    what the mission is about, and what must hold before it runs
    execution   one run, and its Constitution S4 state
    checkpoint  the points a mission can be resumed from
    timeline    the append-only record replay reads
    mission     the aggregate, its two lifecycles, and the gate between them
    policy      whether a transition is advisable, reporting every reason
"""

from backend.contexts.mission.domain.checkpoint import (
    CHECKPOINT_KIND,
    MissionCheckpoint,
)
from backend.contexts.mission.domain.errors import (
    DigestMismatch,
    DigestNotComputed,
    DuplicateMission,
    ExecutionAlreadyOpen,
    IllegalExecutionTransition,
    IllegalStatusTransition,
    InvalidIdentifier,
    MissionArchived as MissionArchivedError,
    MissionError,
    MissionNotFound,
    MissionTerminal,
    NoOpenExecution,
    NoPlanRecorded,
    PreconditionsUnmet,
    TimelineOutOfOrder,
    TransitionRefused,
    UnknownCheckpoint,
    VerificationNotReached,
)
from backend.contexts.mission.domain.events import (
    AGGREGATE_TYPE,
    MISSION_EVENT_TYPES,
    MissionArchived,
    MissionCancelled,
    MissionCheckpointReached,
    MissionCompleted,
    MissionCreated,
    MissionFailed,
    MissionPaused,
    MissionResumed,
    MissionStarted,
)
from backend.contexts.mission.domain.execution import ExecutionOutcome, MissionExecution
from backend.contexts.mission.domain.factory import draft_mission, plan_ref, precondition
from backend.contexts.mission.domain.identifiers import (
    CheckpointId,
    ExecutionId,
    MissionId,
)
from backend.contexts.mission.domain.metadata import (
    MissionKind,
    MissionMetadata,
    MissionPriority,
    PlanRef,
    Precondition,
)
from backend.contexts.mission.domain.mission import (
    ARTIFACT_KIND,
    CANONICAL_FORM_VERSION,
    GOVERNED_FIELDS,
    Mission,
)
from backend.contexts.mission.domain.policy import (
    AUTHORISATION_PRECONDITION,
    MissionPolicy,
    PolicyFinding,
    PolicyReport,
    Severity,
    default_policy,
)
from backend.contexts.mission.domain.status import (
    OUTCOME_STATUSES,
    STATUS_TRANSITIONS,
    TERMINAL_STATUSES,
    MissionStatus,
    is_legal_status_transition,
    permitted_from,
    refusal_reason,
)
from backend.contexts.mission.domain.timeline import (
    MissionTimeline,
    MissionTimelineEntry,
    TimelineEntryKind,
)

__all__ = [
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
    "MissionPolicy",
    "PolicyReport",
    "PolicyFinding",
    "Severity",
    "default_policy",
    "AUTHORISATION_PRECONDITION",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "draft_mission",
    "precondition",
    "plan_ref",
    "AGGREGATE_TYPE",
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
