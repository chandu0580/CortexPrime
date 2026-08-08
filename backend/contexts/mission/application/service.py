"""The Mission Runtime application service.

Where the aggregate's invariants meet mission policy and the repository's facts.
Events are returned, never published -- this context owns no bus, the same
arrangement as every other context in this codebase.

Transitions are gated, not asserted
------------------------------------
Every move runs the policy first and refuses with **every** failure rather than
the first. A transition refused one reason at a time takes five attempts to land,
and the fifth is made by someone who has stopped reading the refusals.

What this service deliberately cannot do
-----------------------------------------
It cannot plan, execute, gather, or reason. Every method here either moves the
lifecycle, records something another context reported, or answers a question
about the record. If a method ever needs to *decide what the mission should do
next*, it belongs in a context that does not exist yet -- not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contracts.mission import MissionState
from backend.contexts.mission.application.commands import (
    AdvanceExecution,
    ArchiveMission,
    CancelMission,
    CompleteMission,
    CreateMission,
    DeclarePrecondition,
    FailMission,
    GetMission,
    GetTimeline,
    ListMissions,
    PauseMission,
    RecordCheckpoint,
    RecordPlan,
    ResumeMission,
    SatisfyPrecondition,
    StartMission,
    TransitionMission,
)
from backend.contexts.mission.domain.errors import MissionNotFound, TransitionRefused
from backend.contexts.mission.domain.events import (
    AGGREGATE_TYPE,
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
from backend.contexts.mission.domain.execution import ExecutionOutcome
from backend.contexts.mission.domain.factory import draft_mission, plan_ref, precondition
from backend.contexts.mission.domain.identifiers import CheckpointId, MissionId
from backend.contexts.mission.domain.metadata import MissionKind, MissionPriority
from backend.contexts.mission.domain.mission import Mission
from backend.contexts.mission.domain.policy import MissionPolicy, default_policy
from backend.contexts.mission.domain.status import MissionStatus
from backend.platform.events import EventMetadata

__all__ = ["MissionService", "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    mission: Mission
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class MissionService:
    def __init__(self, repository: Any, policy: Optional[MissionPolicy] = None) -> None:
        self._repository = repository
        self._policy = policy or default_policy()

    @property
    def policy(self) -> MissionPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, mission: Mission) -> EventMetadata:
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(mission.mission_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
        )

    def _load(self, context: Any, mission_id: str) -> Mission:
        found = self._repository.find(context, MissionId(mission_id))
        if found is None:
            raise MissionNotFound(mission_id)
        return found

    def _gated(self, mission: Mission, to_status: MissionStatus) -> None:
        """Run policy and refuse with every failure at once."""
        report = self._policy.evaluate(mission, to_status)
        if not report.may_transition:
            raise TransitionRefused(
                mission_id=str(mission.mission_id),
                target=to_status.value,
                failures=report.blocking,
            )

    # ------------------------------------------------------------------
    # Creation and scoping
    # ------------------------------------------------------------------

    def create(self, context: Any, command: CreateMission) -> CommandResult:
        """Draft a mission, preserving the requester's own words."""
        mission = draft_mission(
            stated_goal=command.stated_goal,
            requested_by=context.security_context,
            title=command.title,
            kind=MissionKind(command.kind),
            priority=MissionPriority(command.priority),
            target=command.target,
            tags=tuple(command.tags),
            preconditions=tuple(precondition(key) for key in command.preconditions),
        )
        self._repository.save(context, mission)
        return CommandResult(
            mission=mission,
            events=(
                MissionCreated(
                    metadata=self._metadata(context, mission),
                    mission_id=str(mission.mission_id),
                    title=mission.metadata.title,
                    kind=mission.metadata.kind.value,
                    priority=mission.metadata.priority.value,
                    stated_goal=mission.stated_goal,
                    requested_by=str(mission.intent.requested_by.principal.principal_id),
                ),
            ),
        )

    def record_plan(self, context: Any, command: RecordPlan) -> CommandResult:
        mission = self._load(context, command.mission_id).record_plan(
            plan_ref(
                command.plan_id,
                produced_by=command.produced_by,
                revision=command.revision,
            ),
            reason=command.reason,
            actor=command.actor,
        )
        self._repository.replace(context, mission)
        return CommandResult(mission=mission, events=())

    def declare_precondition(
        self, context: Any, command: DeclarePrecondition
    ) -> CommandResult:
        mission = self._load(context, command.mission_id).declare_precondition(
            precondition(command.key, command.description)
        )
        self._repository.replace(context, mission)
        return CommandResult(mission=mission, events=())

    def satisfy_precondition(
        self, context: Any, command: SatisfyPrecondition
    ) -> CommandResult:
        mission = self._load(context, command.mission_id).satisfy_precondition(
            command.key, by=command.satisfied_by, note=command.note
        )
        self._repository.replace(context, mission)
        return CommandResult(mission=mission, events=())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def transition(self, context: Any, command: TransitionMission) -> CommandResult:
        """A move with no side effect beyond the status: ``planned``, ``ready``."""
        mission = self._load(context, command.mission_id)
        target = MissionStatus(command.to_status)
        self._gated(mission, target)
        moved = mission.transition(target, reason=command.reason, actor=command.actor)
        self._repository.replace(context, moved)
        return CommandResult(mission=moved, events=())

    def start(self, context: Any, command: StartMission) -> CommandResult:
        """Open an execution and begin running.

        The execution is opened *before* the transition, because a mission that
        is running with nothing in flight describes nothing that is happening --
        and the policy refuses exactly that (P6).
        """
        mission = self._load(context, command.mission_id)
        opened = mission.open_execution(
            reason=command.reason, actor=command.actor, executor_ref=command.executor_ref
        )
        self._gated(opened, MissionStatus.RUNNING)
        running = opened.transition(
            MissionStatus.RUNNING, reason=command.reason, actor=command.actor
        )
        self._repository.replace(context, running)

        execution = running.current_execution
        return CommandResult(
            mission=running,
            events=(
                MissionStarted(
                    metadata=self._metadata(context, running),
                    mission_id=str(running.mission_id),
                    execution_id=str(execution.execution_id),
                    attempt=execution.attempt,
                    reason=command.reason,
                    actor=command.actor,
                ),
            ),
        )

    def pause(self, context: Any, command: PauseMission) -> CommandResult:
        """Suspend the run.

        The open execution is closed as ``SUSPENDED`` rather than left open: a
        paused mission has ended that stretch of running, and leaving it open
        would make ``current_execution`` describe a run nothing is working on.
        Resuming opens a new attempt that records which checkpoint it resumed
        from, which is what makes attempts countable.
        """
        mission = self._load(context, command.mission_id)
        self._gated(mission, MissionStatus.PAUSED)

        paused = mission
        if paused.current_execution is not None:
            paused = paused.close_execution(
                ExecutionOutcome.SUSPENDED, reason=command.reason, actor=command.actor
            )
        paused = paused.transition(
            MissionStatus.PAUSED, reason=command.reason, actor=command.actor
        )
        self._repository.replace(context, paused)

        latest = paused.latest_checkpoint
        return CommandResult(
            mission=paused,
            events=(
                MissionPaused(
                    metadata=self._metadata(context, paused),
                    mission_id=str(paused.mission_id),
                    reason=command.reason,
                    actor=command.actor,
                    resumable_from=str(latest.checkpoint_id) if latest else "",
                ),
            ),
        )

    def resume(self, context: Any, command: ResumeMission) -> CommandResult:
        """Open a new attempt from a checkpoint and run again."""
        mission = self._load(context, command.mission_id)

        checkpoint_id = None
        if command.from_checkpoint:
            checkpoint_id = CheckpointId(command.from_checkpoint)
        elif mission.latest_checkpoint is not None:
            checkpoint_id = mission.latest_checkpoint.checkpoint_id

        opened = mission.open_execution(
            reason=command.reason,
            actor=command.actor,
            resumed_from=checkpoint_id,
            executor_ref=command.executor_ref,
        )
        self._gated(opened, MissionStatus.RUNNING)
        running = opened.transition(
            MissionStatus.RUNNING, reason=command.reason, actor=command.actor
        )
        self._repository.replace(context, running)

        execution = running.current_execution
        return CommandResult(
            mission=running,
            events=(
                MissionResumed(
                    metadata=self._metadata(context, running),
                    mission_id=str(running.mission_id),
                    execution_id=str(execution.execution_id),
                    attempt=execution.attempt,
                    reason=command.reason,
                    actor=command.actor,
                    resumed_from_checkpoint=str(checkpoint_id) if checkpoint_id else "",
                ),
            ),
        )

    def complete(self, context: Any, command: CompleteMission) -> CommandResult:
        """Finish the mission on verified work.

        The open execution is closed as ``SUCCEEDED`` first, which the execution
        value object refuses unless its S4 state is ``CONCLUDED``. So there are
        two independent checks between here and an unverified completion: this
        one, and the aggregate's gate.
        """
        mission = self._load(context, command.mission_id)
        self._gated(mission, MissionStatus.COMPLETED)

        finished = mission
        if finished.current_execution is not None:
            finished = finished.close_execution(
                ExecutionOutcome.SUCCEEDED, reason=command.reason, actor=command.actor
            )
        finished = finished.transition(
            MissionStatus.COMPLETED, reason=command.reason, actor=command.actor
        )
        self._repository.replace(context, finished)

        return CommandResult(
            mission=finished,
            events=(
                MissionCompleted(
                    metadata=self._metadata(context, finished),
                    mission_id=str(finished.mission_id),
                    execution_state=finished.execution_state.value,
                    executions=len(finished.executions),
                    checkpoints=len(finished.checkpoints),
                    reason=command.reason,
                    actor=command.actor,
                ),
            ),
        )

    def fail(self, context: Any, command: FailMission) -> CommandResult:
        mission = self._load(context, command.mission_id)
        self._gated(mission, MissionStatus.FAILED)

        failed = mission
        if failed.current_execution is not None:
            failed = failed.close_execution(
                ExecutionOutcome.FAILED, reason=command.reason, actor=command.actor
            )
        failed = failed.transition(
            MissionStatus.FAILED, reason=command.reason, actor=command.actor
        )
        self._repository.replace(context, failed)

        return CommandResult(
            mission=failed,
            events=(
                MissionFailed(
                    metadata=self._metadata(context, failed),
                    mission_id=str(failed.mission_id),
                    reason=command.reason,
                    actor=command.actor,
                    execution_state=failed.execution_state.value,
                    attempts=len(failed.executions),
                ),
            ),
        )

    def cancel(self, context: Any, command: CancelMission) -> CommandResult:
        mission = self._load(context, command.mission_id)
        self._gated(mission, MissionStatus.CANCELLED)
        cancelled_from = mission.status.value

        cancelled = mission
        if cancelled.current_execution is not None:
            cancelled = cancelled.close_execution(
                ExecutionOutcome.ABANDONED, reason=command.reason, actor=command.actor
            )
        cancelled = cancelled.transition(
            MissionStatus.CANCELLED, reason=command.reason, actor=command.actor
        )
        self._repository.replace(context, cancelled)

        return CommandResult(
            mission=cancelled,
            events=(
                MissionCancelled(
                    metadata=self._metadata(context, cancelled),
                    mission_id=str(cancelled.mission_id),
                    reason=command.reason,
                    actor=command.actor,
                    cancelled_from=cancelled_from,
                ),
            ),
        )

    def archive(self, context: Any, command: ArchiveMission) -> CommandResult:
        mission = self._load(context, command.mission_id)
        self._gated(mission, MissionStatus.ARCHIVED)
        archived = mission.archive(reason=command.reason, actor=command.actor)
        self._repository.replace(context, archived)

        return CommandResult(
            mission=archived,
            events=(
                MissionArchived(
                    metadata=self._metadata(context, archived),
                    mission_id=str(archived.mission_id),
                    digest=archived.digest or "",
                    final_status=MissionStatus.ARCHIVED.value,
                    timeline_entries=len(archived.timeline),
                    reason=command.reason,
                    actor=command.actor,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Recording what other contexts report
    # ------------------------------------------------------------------

    def advance_execution(self, context: Any, command: AdvanceExecution) -> CommandResult:
        """Record an S4 movement another context made. Never decides one."""
        mission = self._load(context, command.mission_id).advance_execution(
            MissionState(command.to_state),
            reason=command.reason,
            actor=command.actor,
        )
        self._repository.replace(context, mission)
        return CommandResult(mission=mission, events=())

    def record_checkpoint(self, context: Any, command: RecordCheckpoint) -> CommandResult:
        mission = self._load(context, command.mission_id).record_checkpoint(
            command.label,
            actor=command.actor,
            payload_ref=command.payload_ref,
            payload_digest=command.payload_digest,
        )
        self._repository.replace(context, mission)

        checkpoint = mission.latest_checkpoint
        return CommandResult(
            mission=mission,
            events=(
                MissionCheckpointReached(
                    metadata=self._metadata(context, mission),
                    mission_id=str(mission.mission_id),
                    checkpoint_id=str(checkpoint.checkpoint_id),
                    sequence=checkpoint.sequence,
                    label=checkpoint.label,
                    execution_state=checkpoint.execution_state.value,
                    digest=checkpoint.digest or "",
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetMission) -> Mission:
        return self._load(context, query.mission_id)

    def timeline(self, context: Any, query: GetTimeline):
        return self._load(context, query.mission_id).timeline

    def evaluate(self, context: Any, mission_id: str, to_status: str):
        """Run the policy without transitioning.

        What an operator checks before moving a mission. Discovering four
        failures one refusal at a time is how a transition takes four attempts.
        """
        return self._policy.evaluate(
            self._load(context, mission_id), MissionStatus(to_status)
        )

    def list(self, context: Any, query: ListMissions) -> tuple:
        found = self._repository.all(context)
        if query.status:
            wanted = MissionStatus(query.status)
            found = tuple(m for m in found if m.status is wanted)
        if query.kind:
            wanted_kind = MissionKind(query.kind)
            found = tuple(m for m in found if m.metadata.kind is wanted_kind)
        if query.priority:
            wanted_priority = MissionPriority(query.priority)
            found = tuple(m for m in found if m.metadata.priority is wanted_priority)
        if query.live_only:
            found = tuple(m for m in found if m.status.is_live)
        return tuple(found)
