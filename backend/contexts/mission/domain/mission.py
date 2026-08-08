"""The Mission aggregate.

A mission is a long-running enterprise objective. This aggregate owns its
lifecycle and nothing else -- it does not plan, execute, reason, or store what
was learned. Those belong to contexts this one deliberately cannot import.

What the aggregate actually enforces
-------------------------------------
**Two lifecycles, one gate.** The operational status (``MissionStatus``) and the
execution state (Constitution S4's ``MissionState``) advance independently, and
``RUNNING -> COMPLETED`` is refused unless the execution reached ``CONCLUDED``.
Since S4 forbids ``EXECUTING -> CONCLUDED`` directly, verification cannot be
skipped from either side. That single gate is the reason two machines are safer
here than one.

**Every movement records why.** Constitution S4 again. The timeline is
append-only and gapless, and the status is *derived* from it on replay and
asserted to match the stored one -- so a mission whose history disagrees with its
state is a test failure rather than a mystery.

**Archived means sealed.** The digest covers the whole timeline. A mission that
changed after archival would make its digest a statement about a record that no
longer exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Final, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.mission import MissionIntent, MissionState
from backend.contexts.mission.domain.checkpoint import MissionCheckpoint
from backend.contexts.mission.domain.errors import (
    DigestMismatch,
    DigestNotComputed,
    ExecutionAlreadyOpen,
    IllegalStatusTransition,
    MissionArchived,
    NoOpenExecution,
    NoPlanRecorded,
    PreconditionsUnmet,
    UnknownCheckpoint,
    VerificationNotReached,
)
from backend.contexts.mission.domain.execution import ExecutionOutcome, MissionExecution
from backend.contexts.mission.domain.identifiers import CheckpointId, MissionId
from backend.contexts.mission.domain.metadata import (
    MissionMetadata,
    PlanRef,
    Precondition,
)
from backend.contexts.mission.domain.status import (
    MissionStatus,
    is_legal_status_transition,
    permitted_from,
)
from backend.contexts.mission.domain.timeline import (
    MissionTimeline,
    MissionTimelineEntry,
    TimelineEntryKind,
)
from backend.platform.hashing import compute_digest, digests_match

__all__ = ["Mission", "ARTIFACT_KIND", "CANONICAL_FORM_VERSION", "GOVERNED_FIELDS"]

ARTIFACT_KIND: Final[str] = "cortexprime.mission.mission"
CANONICAL_FORM_VERSION: Final[int] = 1

#: What the archival digest covers. Excludes the digest itself and the wall-clock
#: fields that are not part of what the mission *did*.
GOVERNED_FIELDS: Final[tuple] = (
    "mission_id",
    "metadata",
    "stated_goal",
    "status",
    "execution_state",
    "plan_ref",
    "preconditions",
    "timeline",
    "checkpoints",
    "executions",
    "outcome_note",
)


@dataclass(frozen=True)
class Mission(Contract):
    """One long-running enterprise objective, and its governed lifecycle."""

    CONTRACT_NAME = "cortexprime.mission.mission_aggregate"

    mission_id: MissionId
    intent: MissionIntent
    metadata: MissionMetadata

    status: MissionStatus = MissionStatus.DRAFT
    execution_state: MissionState = MissionState.RECEIVED
    plan_ref: Optional[PlanRef] = None
    preconditions: tuple = ()
    timeline: MissionTimeline = field(default_factory=MissionTimeline)
    checkpoints: tuple = ()
    executions: tuple = ()

    outcome_note: Optional[str] = None
    digest: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    archived_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, MissionId):
            raise ContractViolation("mission_id must be a MissionId")
        if not isinstance(self.intent, MissionIntent):
            raise ContractViolation(
                "intent must be a MissionIntent; the requester's own words are what "
                "makes it auditable whether the mission solved the stated problem"
            )
        if not isinstance(self.metadata, MissionMetadata):
            raise ContractViolation("metadata must be a MissionMetadata")
        if not isinstance(self.status, MissionStatus):
            raise ContractViolation("status must be a MissionStatus")
        if not isinstance(self.execution_state, MissionState):
            raise ContractViolation("execution_state must be a MissionState")
        if not isinstance(self.timeline, MissionTimeline):
            raise ContractViolation("timeline must be a MissionTimeline")

        if self.plan_ref is not None and not isinstance(self.plan_ref, PlanRef):
            raise ContractViolation("plan_ref must be a PlanRef")

        for label, items, expected in (
            ("preconditions", self.preconditions, Precondition),
            ("checkpoints", self.checkpoints, MissionCheckpoint),
            ("executions", self.executions, MissionExecution),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        keys = [p.key for p in self.preconditions]
        if len(set(keys)) != len(keys):
            raise ContractViolation("preconditions contains duplicate keys")

        attempts = [e.attempt for e in self.executions]
        if len(set(attempts)) != len(attempts):
            raise ContractViolation("executions contains duplicate attempt numbers")

        open_runs = [e for e in self.executions if e.is_open]
        if len(open_runs) > 1:
            raise ContractViolation(
                "a mission has at most one open execution; two concurrent runs "
                "produce two answers for one objective"
            )

        sequences = [c.sequence for c in self.checkpoints]
        if sequences != sorted(sequences) or len(set(sequences)) != len(sequences):
            raise ContractViolation(
                "checkpoints must be sequenced without gaps or repeats; resuming "
                "depends on knowing which is latest"
            )

        # A mission past DRAFT has a plan to point at.
        if self.status not in (MissionStatus.DRAFT, MissionStatus.CANCELLED):
            if self.plan_ref is None:
                raise ContractViolation(
                    f"a {self.status.value} mission must reference its plan; Mission "
                    "Runtime does not plan, so it records where the plan lives"
                )

        # An outcome says what happened.
        if self.status in (MissionStatus.FAILED, MissionStatus.CANCELLED):
            if not (self.outcome_note and self.outcome_note.strip()):
                raise ContractViolation(
                    f"a {self.status.value} mission must record why; an unexplained "
                    "outcome tells whoever reads it nothing"
                )

        # Completion means the execution was verified. Held here as well as at
        # the transition, because a mission assembled from storage bypasses it.
        if self.status is MissionStatus.COMPLETED:
            if self.execution_state is not MissionState.CONCLUDED:
                raise VerificationNotReached(
                    mission_id=str(self.mission_id),
                    execution_state=self.execution_state.value,
                )

        if self.status is MissionStatus.ARCHIVED:
            if not self.digest:
                raise ContractViolation(
                    "an archived mission must carry the digest computed at archival"
                )
            if self.archived_at is None:
                raise ContractViolation("an archived mission must record when")

        for label, value in (
            ("created_at", self.created_at),
            ("archived_at", self.archived_at),
        ):
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def stated_goal(self) -> str:
        return self.intent.stated_goal

    @property
    def is_open(self) -> bool:
        return self.status.is_open

    @property
    def outstanding_preconditions(self) -> tuple:
        return tuple(sorted(p.key for p in self.preconditions if not p.satisfied))

    @property
    def current_execution(self) -> Optional[MissionExecution]:
        for execution in self.executions:
            if execution.is_open:
                return execution
        return None

    @property
    def latest_checkpoint(self) -> Optional[MissionCheckpoint]:
        return self.checkpoints[-1] if self.checkpoints else None

    @property
    def next_attempt(self) -> int:
        return len(self.executions) + 1

    @property
    def is_verified(self) -> bool:
        """Whether S4 says this mission's work was checked."""
        return self.execution_state is MissionState.CONCLUDED

    def checkpoint(self, checkpoint_id: CheckpointId) -> Optional[MissionCheckpoint]:
        for candidate in self.checkpoints:
            if candidate.checkpoint_id == checkpoint_id:
                return candidate
        return None

    def permitted_transitions(self) -> tuple:
        return permitted_from(self.status)

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        """Exactly what the archival digest covers."""
        return {
            "__artifact__": ARTIFACT_KIND,
            "__canonical_form__": CANONICAL_FORM_VERSION,
            "mission_id": str(self.mission_id),
            "stated_goal": self.intent.stated_goal,
            "metadata": {
                "title": self.metadata.title,
                "kind": self.metadata.kind.value,
                "priority": self.metadata.priority.value,
                "target": self.metadata.target,
                "tags": sorted(self.metadata.tags),
            },
            "status": self.status.value,
            "execution_state": self.execution_state.value,
            "plan_ref": str(self.plan_ref) if self.plan_ref else None,
            "preconditions": sorted(
                (
                    {"key": p.key, "satisfied": p.satisfied, "satisfied_by": p.satisfied_by}
                    for p in self.preconditions
                ),
                key=lambda item: item["key"],
            ),
            "timeline": [
                {
                    "sequence": e.sequence,
                    "kind": e.kind.value,
                    "reason": e.reason,
                    "actor": e.actor,
                    "from_status": e.from_status.value if e.from_status else None,
                    "to_status": e.to_status.value if e.to_status else None,
                    "from_execution_state": (
                        e.from_execution_state.value if e.from_execution_state else None
                    ),
                    "to_execution_state": (
                        e.to_execution_state.value if e.to_execution_state else None
                    ),
                    "checkpoint_id": e.checkpoint_id,
                }
                for e in self.timeline
            ],
            "checkpoints": [
                {
                    "checkpoint_id": str(c.checkpoint_id),
                    "sequence": c.sequence,
                    "label": c.label,
                    "execution_state": c.execution_state.value,
                    "digest": c.digest,
                }
                for c in self.checkpoints
            ],
            "executions": [
                {
                    "execution_id": str(e.execution_id),
                    "attempt": e.attempt,
                    "state": e.state.value,
                    "outcome": e.outcome.value,
                }
                for e in self.executions
            ],
            "outcome_note": self.outcome_note,
        }

    def compute_digest(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def verify_digest(self) -> None:
        """Raise unless the mission still hashes to the digest bound at archival."""
        if not self.digest:
            raise DigestNotComputed(str(self.mission_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                mission_id=str(self.mission_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _require_open(self, operation: str) -> None:
        if self.status is MissionStatus.ARCHIVED:
            raise MissionArchived(mission_id=str(self.mission_id), operation=operation)

    def _entry(
        self,
        kind: TimelineEntryKind,
        reason: str,
        actor: str,
        **fields: Any,
    ) -> MissionTimelineEntry:
        return MissionTimelineEntry(
            sequence=self.timeline.next_sequence,
            kind=kind,
            reason=reason,
            actor=actor,
            **fields,
        )

    # ------------------------------------------------------------------
    # Scoping
    # ------------------------------------------------------------------

    def record_plan(self, plan: PlanRef, *, reason: str, actor: str) -> "Mission":
        """Record where the plan lives. Mission Runtime does not produce it."""
        self._require_open("recording a plan")
        if not isinstance(plan, PlanRef):
            raise ContractViolation("plan must be a PlanRef")
        noted = replace(self, plan_ref=plan)
        return replace(
            noted,
            timeline=self.timeline.append(
                noted._entry(
                    TimelineEntryKind.NOTE,
                    reason,
                    actor,
                    detail=f"plan:{plan.plan_id}",
                )
            ),
        )

    def declare_precondition(self, precondition: Precondition) -> "Mission":
        self._require_open("declaring a precondition")
        if not isinstance(precondition, Precondition):
            raise ContractViolation("precondition must be a Precondition")
        if any(p.key == precondition.key for p in self.preconditions):
            raise ContractViolation(
                f"precondition {precondition.key!r} is already declared"
            )
        return replace(self, preconditions=self.preconditions + (precondition,))

    def satisfy_precondition(self, key: str, *, by: str, note: Optional[str] = None) -> "Mission":
        """Record that someone cleared a precondition. Never satisfies one itself."""
        self._require_open("satisfying a precondition")
        found = next((p for p in self.preconditions if p.key == key), None)
        if found is None:
            raise ContractViolation(f"mission has no precondition {key!r}")
        satisfied = found.satisfy(by, note)
        return replace(
            self,
            preconditions=tuple(
                satisfied if p.key == key else p for p in self.preconditions
            ),
        )

    # ------------------------------------------------------------------
    # The operational lifecycle
    # ------------------------------------------------------------------

    def transition(
        self, to_status: MissionStatus, *, reason: str, actor: str
    ) -> "Mission":
        """Move the operational lifecycle, recording why.

        Every gate that guards a specific transition lives here rather than in
        the caller, because the caller is the party the gates exist to constrain.
        """
        self._require_open(f"moving to {to_status.value}")
        if not isinstance(to_status, MissionStatus):
            raise ContractViolation("to_status must be a MissionStatus")

        if not is_legal_status_transition(self.status, to_status):
            raise IllegalStatusTransition(
                mission_id=str(self.mission_id),
                source=self.status.value,
                target=to_status.value,
                permitted=permitted_from(self.status),
            )

        if to_status is MissionStatus.PLANNED and self.plan_ref is None:
            raise NoPlanRecorded(str(self.mission_id))

        if to_status is MissionStatus.READY and self.outstanding_preconditions:
            raise PreconditionsUnmet(
                mission_id=str(self.mission_id),
                outstanding=self.outstanding_preconditions,
            )

        # The gate. Completion requires the execution to have been verified, and
        # Constitution S4 only lets an execution reach CONCLUDED through
        # VERIFYING -- so this cannot be satisfied by skipping verification.
        if to_status is MissionStatus.COMPLETED and not self.is_verified:
            raise VerificationNotReached(
                mission_id=str(self.mission_id),
                execution_state=self.execution_state.value,
            )

        # An outcome has to say why, and the reason for the move *is* why. Taking
        # it from the transition rather than demanding it separately means the
        # aggregate can produce every state it declares legal -- an aggregate
        # whose own transition cannot satisfy its own invariant would force every
        # caller into the same workaround, and one of them would get it wrong.
        outcome_note = self.outcome_note
        if to_status in (MissionStatus.FAILED, MissionStatus.CANCELLED) and not outcome_note:
            outcome_note = reason.strip()

        moved = replace(self, status=to_status, outcome_note=outcome_note)
        return replace(
            moved,
            timeline=self.timeline.append(
                moved._entry(
                    TimelineEntryKind.STATUS,
                    reason,
                    actor,
                    from_status=self.status,
                    to_status=to_status,
                )
            ),
        )

    # ------------------------------------------------------------------
    # Executions
    # ------------------------------------------------------------------

    def open_execution(
        self,
        *,
        reason: str,
        actor: str,
        resumed_from: Optional[CheckpointId] = None,
        executor_ref: Optional[str] = None,
    ) -> "Mission":
        """Open a run. Refuses a second concurrent one."""
        self._require_open("opening an execution")
        current = self.current_execution
        if current is not None:
            raise ExecutionAlreadyOpen(
                mission_id=str(self.mission_id), execution_id=str(current.execution_id)
            )
        checkpoint = None
        if resumed_from is not None:
            checkpoint = self.checkpoint(resumed_from)
            if checkpoint is None:
                raise UnknownCheckpoint(
                    mission_id=str(self.mission_id), checkpoint_id=str(resumed_from)
                )

        # A resumed run starts where its checkpoint was taken; a fresh one starts
        # at RECEIVED because nothing has happened yet. Carrying the previous
        # run's state into a new one would claim progress this run has not made.
        start_state = (
            checkpoint.execution_state if checkpoint is not None else MissionState.RECEIVED
        )

        execution = MissionExecution.open(
            mission_id=str(self.mission_id),
            attempt=self.next_attempt,
            state=start_state,
            resumed_from_checkpoint=str(resumed_from) if resumed_from else None,
            executor_ref=executor_ref,
        )
        opened = replace(
            self,
            executions=self.executions + (execution,),
            execution_state=start_state,
            timeline=self.timeline.append(
                self._entry(
                    TimelineEntryKind.NOTE,
                    reason,
                    actor,
                    detail=f"execution:{execution.execution_id}:attempt:{execution.attempt}",
                )
            ),
        )

        if start_state is self.execution_state:
            return opened

        # The execution state moved, so the timeline has to say so or replay will
        # disagree with the aggregate. This is *not* an S4 transition -- S4
        # governs movement within one run, and this is a new run beginning at a
        # recorded position -- so it is recorded without being checked against
        # the S4 table, which would refuse a perfectly legitimate resumption.
        origin = (
            f"resumed from checkpoint {checkpoint.checkpoint_id}"
            if checkpoint is not None
            else "new execution starting from the beginning"
        )
        return replace(
            opened,
            timeline=opened.timeline.append(
                opened._entry(
                    TimelineEntryKind.EXECUTION,
                    f"{reason} ({origin})",
                    actor,
                    from_execution_state=self.execution_state,
                    to_execution_state=start_state,
                )
            ),
        )

    def advance_execution(
        self, to_state: MissionState, *, reason: str, actor: str
    ) -> "Mission":
        """Move the S4 execution state of the open run.

        The runtime does not decide these -- Execution and Verification do. What
        it does is record the movement, refuse an illegal one through the
        published contract, and keep the mission's copy in step.
        """
        self._require_open("advancing the execution")
        current = self.current_execution
        if current is None:
            raise NoOpenExecution(
                mission_id=str(self.mission_id), operation="advancing the execution"
            )

        advanced = current.advance(to_state, reason)
        updated = replace(
            self,
            execution_state=to_state,
            executions=tuple(
                advanced if e.execution_id == current.execution_id else e
                for e in self.executions
            ),
        )
        return replace(
            updated,
            timeline=self.timeline.append(
                updated._entry(
                    TimelineEntryKind.EXECUTION,
                    reason,
                    actor,
                    from_execution_state=current.state,
                    to_execution_state=to_state,
                )
            ),
        )

    def close_execution(
        self, outcome: ExecutionOutcome, *, reason: str, actor: str
    ) -> "Mission":
        self._require_open("closing the execution")
        current = self.current_execution
        if current is None:
            raise NoOpenExecution(
                mission_id=str(self.mission_id), operation="closing the execution"
            )
        closed = current.close(outcome, reason)
        updated = replace(
            self,
            executions=tuple(
                closed if e.execution_id == current.execution_id else e
                for e in self.executions
            ),
        )
        return replace(
            updated,
            timeline=self.timeline.append(
                updated._entry(
                    TimelineEntryKind.NOTE,
                    reason,
                    actor,
                    detail=f"execution:{closed.execution_id}:{outcome.value}",
                )
            ),
        )

    # ------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------

    def record_checkpoint(
        self,
        label: str,
        *,
        actor: str,
        payload_ref: Optional[str] = None,
        payload_digest: Optional[str] = None,
    ) -> "Mission":
        """Record a recoverable position.

        Only while running: a checkpoint records progress, so there has to be
        progress to record. A checkpoint taken while paused would describe a
        position the mission already occupies.
        """
        self._require_open("recording a checkpoint")
        if not self.status.accepts_checkpoints:
            raise ContractViolation(
                f"a checkpoint cannot be recorded while {self.status.value}; a "
                "checkpoint records progress, and progress needs a running mission"
            )
        current = self.current_execution
        if current is None:
            raise NoOpenExecution(
                mission_id=str(self.mission_id), operation="recording a checkpoint"
            )

        checkpoint = MissionCheckpoint.create(
            sequence=len(self.checkpoints) + 1,
            label=label,
            execution_state=self.execution_state,
            execution_id=str(current.execution_id),
            payload_ref=payload_ref,
            payload_digest=payload_digest,
            recorded_by=actor,
        )
        recorded = replace(self, checkpoints=self.checkpoints + (checkpoint,))
        return replace(
            recorded,
            timeline=self.timeline.append(
                recorded._entry(
                    TimelineEntryKind.CHECKPOINT,
                    f"checkpoint reached: {label}",
                    actor,
                    checkpoint_id=str(checkpoint.checkpoint_id),
                )
            ),
        )

    # ------------------------------------------------------------------
    # Archival
    # ------------------------------------------------------------------

    def archive(self, *, reason: str, actor: str) -> "Mission":
        """Seal the mission and bind its digest.

        Only from an outcome. Archiving a live mission would seal a record that
        is still being written.
        """
        self._require_open("archiving")
        if not self.status.is_outcome:
            raise IllegalStatusTransition(
                mission_id=str(self.mission_id),
                source=self.status.value,
                target=MissionStatus.ARCHIVED.value,
                permitted=permitted_from(self.status),
            )

        # Append the archival entry while the mission is still in its outcome
        # status, which is a valid state to hold.
        with_entry = replace(
            self,
            timeline=self.timeline.append(
                self._entry(
                    TimelineEntryKind.STATUS,
                    reason,
                    actor,
                    from_status=self.status,
                    to_status=MissionStatus.ARCHIVED,
                )
            ),
        )

        # The digest covers the *archived* content, but an archived mission
        # cannot be constructed without one. So the payload is assembled
        # directly rather than by building an intermediate that would violate one
        # invariant to satisfy the other. It is byte-identical to what the sealed
        # mission reports -- ``status`` is the only field that differs, and it is
        # substituted here -- which is what makes ``verify_digest`` on the result
        # pass. A test asserts exactly that.
        payload = with_entry.digest_payload()
        payload["status"] = MissionStatus.ARCHIVED.value
        digest = compute_digest(payload).value

        return replace(
            with_entry,
            status=MissionStatus.ARCHIVED,
            archived_at=datetime.now(timezone.utc),
            digest=digest,
        )

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replayed_status(self) -> MissionStatus:
        """The status the timeline says this mission is in."""
        return self.timeline.replay_status()

    def replayed_execution_state(self) -> MissionState:
        return self.timeline.replay_execution_state()

    def timeline_agrees(self) -> bool:
        """Whether the stored state matches what replaying the timeline produces.

        The check that makes the timeline authoritative rather than decorative.
        """
        return (
            self.replayed_status() is self.status
            and self.replayed_execution_state() is self.execution_state
        )
