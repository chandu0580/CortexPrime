"""MissionExecution: one run of a mission, as the runtime sees it.

**This is not the execution.** The Execution context runs things; this records
that a run was opened, what state Constitution S4 says it is in, and how it
ended. The distinction is the one the whole context rests on: Mission Runtime
orchestrates work and performs none.

Why a mission has many executions
----------------------------------
A continuous mission -- "Monitor Production Kubernetes Cluster" -- is a single
objective that runs, pauses, resumes and runs again for months. Each stretch of
actual running is an execution with its own S4 lifecycle: it gathers, reasons,
acts, and is verified. Modelling one execution per mission would force either a
new mission per cycle (losing the objective's history) or a single S4 pass
stretched across months (making "verified" meaningless).

Only one execution is open at a time. Two concurrent runs of one objective
produce two answers, and nothing in the model says which one the mission means.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.mission import MissionRef, MissionState, MissionTransition
from backend.contexts.mission.domain.errors import IllegalExecutionTransition
from backend.contexts.mission.domain.identifiers import ExecutionId

__all__ = ["ExecutionOutcome", "MissionExecution"]


class ExecutionOutcome(str, Enum):
    """How a run ended. ``OPEN`` while it has not."""

    OPEN = "open"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"
    SUSPENDED = "suspended"

    @property
    def is_open(self) -> bool:
        return self is ExecutionOutcome.OPEN

    @property
    def is_resumable(self) -> bool:
        """Only a suspended run resumes. A failed one starts a new attempt.

        Resuming a failed run would replay whatever failed; the honest move is a
        new attempt that can be counted, compared, and given up on.
        """
        return self is ExecutionOutcome.SUSPENDED


@dataclass(frozen=True)
class MissionExecution(Contract):
    """One attempt at achieving the mission's objective."""

    CONTRACT_NAME = "cortexprime.mission.execution"

    execution_id: ExecutionId
    mission_id: str
    attempt: int
    state: MissionState = MissionState.RECEIVED
    outcome: ExecutionOutcome = ExecutionOutcome.OPEN
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    resumed_from_checkpoint: Optional[str] = None
    executor_ref: Optional[str] = None
    closing_note: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, ExecutionId):
            raise ContractViolation("execution_id must be an ExecutionId")
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise ContractViolation("an execution must name its mission")
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ContractViolation("attempt must be a positive integer starting at 1")
        if not isinstance(self.state, MissionState):
            raise ContractViolation("state must be a MissionState")
        if not isinstance(self.outcome, ExecutionOutcome):
            raise ContractViolation("outcome must be an ExecutionOutcome")

        if self.outcome.is_open:
            if self.ended_at is not None:
                raise ContractViolation("an open execution has not ended")
        else:
            if self.ended_at is None:
                raise ContractViolation(
                    f"an execution that {self.outcome.value} must record when it ended"
                )

        # A succeeded run is one whose execution reached CONCLUDED -- which S4
        # only permits through VERIFYING. Recording success at any other state
        # would let the mission complete over unverified work.
        if self.outcome is ExecutionOutcome.SUCCEEDED and self.state is not MissionState.CONCLUDED:
            raise ContractViolation(
                f"an execution cannot have succeeded at {self.state.value!r}; success "
                "means the execution reached 'concluded', which Constitution S4 only "
                "permits through verification"
            )

        for label, value in (("started_at", self.started_at), ("ended_at", self.ended_at)):
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # -- queries -------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.outcome.is_open

    @property
    def is_verified(self) -> bool:
        """Whether S4 says this run's work was checked."""
        return self.state is MissionState.CONCLUDED

    # -- transitions ---------------------------------------------------

    def advance(self, to_state: MissionState, reason: str) -> "MissionExecution":
        """Move the S4 execution state.

        Legality is delegated to the published ``MissionTransition`` contract
        rather than re-implemented. Constitution S4's table is not this context's
        to redefine, and a second copy of it would drift with nothing catching
        the drift -- so the contract is *used*, and its refusal is re-raised with
        the mission named.
        """
        if not isinstance(to_state, MissionState):
            raise ContractViolation("to_state must be a MissionState")
        if not self.is_open:
            raise ContractViolation(
                f"execution {self.execution_id} is {self.outcome.value} and cannot advance"
            )
        try:
            MissionTransition(
                mission=MissionRef(mission_id=self.mission_id),
                from_state=self.state,
                to_state=to_state,
                reason=reason,
                occurred_at=datetime.now(timezone.utc),
                sequence=0,
            )
        except ContractViolation as exc:
            if "illegal mission transition" in str(exc):
                raise IllegalExecutionTransition(
                    mission_id=self.mission_id,
                    source=self.state.value,
                    target=to_state.value,
                ) from exc
            raise
        return replace(self, state=to_state)

    def close(self, outcome: ExecutionOutcome, note: Optional[str] = None) -> "MissionExecution":
        if not isinstance(outcome, ExecutionOutcome) or outcome.is_open:
            raise ContractViolation("closing an execution needs a non-open outcome")
        if not self.is_open:
            raise ContractViolation(
                f"execution {self.execution_id} is already {self.outcome.value}"
            )
        return replace(
            self,
            outcome=outcome,
            ended_at=datetime.now(timezone.utc),
            closing_note=note.strip() if note and note.strip() else None,
        )

    @classmethod
    def open(
        cls,
        *,
        mission_id: str,
        attempt: int,
        state: MissionState = MissionState.RECEIVED,
        resumed_from_checkpoint: Optional[str] = None,
        executor_ref: Optional[str] = None,
    ) -> "MissionExecution":
        """Open a run, optionally at the state a checkpoint captured.

        ``state`` is not defaulted away lightly. A run resumed from a checkpoint
        starts where the checkpoint was taken -- resuming into a different phase
        than the one that was checkpointed is how a mission silently redoes work
        it already did, or skips work it never did. A fresh run starts at
        ``RECEIVED`` because nothing has happened yet.
        """
        return cls(
            execution_id=ExecutionId.new(),
            mission_id=mission_id,
            attempt=attempt,
            state=state,
            resumed_from_checkpoint=resumed_from_checkpoint,
            executor_ref=executor_ref,
        )
