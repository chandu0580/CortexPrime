"""Execution strategy and rollback strategy: how the plan would be run, and undone.

**Declarations, not decisions taken.** This context states how the plan is meant
to be run; Execution decides what actually runs, when, and against what
contention. A planner that scheduled would be an executor with extra steps.

The two rules worth the module
-------------------------------
**Continuing past a failed mutation is opt-in and must be justified.** A plan
that changes things and carries on after a failure produces a half-applied
change -- the state nobody designed, nobody tested, and nobody can describe
afterwards. ``HALT`` and ``COMPENSATE`` are the defaults for a reason.

**A read-only plan declares no rollback.** Demanding an elaborate rollback
strategy for a plan that changes nothing trains people to write one that says
nothing, and a rollback strategy nobody means is worse than none: it reads as
though somebody thought about it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "ExecutionMode",
    "FailureResponse",
    "RollbackKind",
    "ExecutionStrategy",
    "RollbackStrategy",
]


class ExecutionMode(str, Enum):
    """How much of the plan may be in flight at once."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PHASED = "phased"

    @property
    def permits_concurrency(self) -> bool:
        return self is not ExecutionMode.SEQUENTIAL


class FailureResponse(str, Enum):
    """What happens to the rest of the plan when a task fails."""

    HALT = "halt"
    """Stop. Nothing further starts; what completed stays completed."""

    COMPENSATE = "compensate"
    """Stop and run the declared reversals, walking back what was done."""

    CONTINUE = "continue"
    """Carry on with whatever does not depend on the failure. Opt-in only."""

    @property
    def leaves_partial_state(self) -> bool:
        """Whether this response can leave the world half-changed.

        ``HALT`` can too -- work already done stays done -- but it stops adding
        to it. ``CONTINUE`` keeps going, which is the one that turns a failure
        into a state nobody designed.
        """
        return self is FailureResponse.CONTINUE


class RollbackKind(str, Enum):
    """How the plan would be walked back."""

    COMPENSATING_TASKS = "compensating_tasks"
    """Each mutating task declares its reversal. The strongest option."""

    SNAPSHOT_RESTORE = "snapshot_restore"
    """A snapshot is taken first and restored wholesale."""

    FORWARD_FIX_ONLY = "forward_fix_only"
    """There is no way back; recovery means going forward. Requires acceptance."""

    NONE_REQUIRED = "none_required"
    """The plan changes nothing, so there is nothing to undo."""

    @property
    def provides_a_way_back(self) -> bool:
        return self in (RollbackKind.COMPENSATING_TASKS, RollbackKind.SNAPSHOT_RESTORE)

    @property
    def requires_acceptance(self) -> bool:
        """Whether somebody has to put their name to it.

        ``FORWARD_FIX_ONLY`` is a legitimate answer and an expensive one. It is
        the only kind that says "if this goes wrong we cannot undo it", and that
        is a decision, not a property.
        """
        return self is RollbackKind.FORWARD_FIX_ONLY


@dataclass(frozen=True)
class ExecutionStrategy(Contract):
    """How the plan is meant to be run."""

    CONTRACT_NAME = "cortexprime.planner.execution_strategy"

    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    on_failure: FailureResponse = FailureResponse.HALT
    max_parallelism: int = 1
    checkpoint_after: tuple = ()
    continue_justification: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ExecutionMode):
            raise ContractViolation("mode must be an ExecutionMode")
        if not isinstance(self.on_failure, FailureResponse):
            raise ContractViolation("on_failure must be a FailureResponse")
        if not isinstance(self.max_parallelism, int) or self.max_parallelism < 1:
            raise ContractViolation("max_parallelism must be a positive integer")

        if self.mode.permits_concurrency and self.max_parallelism < 2:
            raise ContractViolation(
                f"mode {self.mode.value!r} permits concurrency but max_parallelism is "
                f"{self.max_parallelism}; a concurrent strategy that runs one task at "
                "a time is a sequential one wearing a different name"
            )
        if not self.mode.permits_concurrency and self.max_parallelism != 1:
            raise ContractViolation(
                "a sequential strategy runs one task at a time; max_parallelism must "
                "be 1"
            )

        if not isinstance(self.checkpoint_after, tuple):
            raise ContractViolation("checkpoint_after must be a tuple")
        for task_id in self.checkpoint_after:
            if not isinstance(task_id, str) or not task_id.strip():
                raise ContractViolation("checkpoint_after contains a blank task id")
        if len(set(self.checkpoint_after)) != len(self.checkpoint_after):
            raise ContractViolation("checkpoint_after names a task twice")

        # Continuing past a failure is opt-in and must be argued for.
        if self.on_failure.leaves_partial_state and not self.continue_justification.strip():
            raise ContractViolation(
                "a strategy that continues past a failure must justify it; carrying "
                "on after a failed task is how a plan produces a half-applied change "
                "nobody designed"
            )

    @property
    def is_concurrent(self) -> bool:
        return self.mode.permits_concurrency

    @property
    def stops_on_failure(self) -> bool:
        return not self.on_failure.leaves_partial_state

    @classmethod
    def sequential(cls, *, on_failure: FailureResponse = FailureResponse.HALT) -> "ExecutionStrategy":
        return cls(mode=ExecutionMode.SEQUENTIAL, on_failure=on_failure, max_parallelism=1)

    @classmethod
    def parallel(
        cls,
        max_parallelism: int,
        *,
        on_failure: FailureResponse = FailureResponse.HALT,
    ) -> "ExecutionStrategy":
        return cls(
            mode=ExecutionMode.PARALLEL,
            on_failure=on_failure,
            max_parallelism=max_parallelism,
        )


@dataclass(frozen=True)
class RollbackStrategy(Contract):
    """How the plan would be walked back if it goes wrong."""

    CONTRACT_NAME = "cortexprime.planner.rollback_strategy"

    kind: RollbackKind = RollbackKind.NONE_REQUIRED
    description: str = ""
    accepted_by: Optional[str] = None
    snapshot_of: tuple = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RollbackKind):
            raise ContractViolation("kind must be a RollbackKind")

        if not isinstance(self.snapshot_of, tuple):
            raise ContractViolation("snapshot_of must be a tuple")

        if self.kind is RollbackKind.SNAPSHOT_RESTORE and not self.snapshot_of:
            raise ContractViolation(
                "a snapshot-restore rollback must name what is snapshotted; one that "
                "names nothing cannot be shown to cover what the plan changes"
            )

        if self.kind.requires_acceptance and not (
            self.accepted_by and self.accepted_by.strip()
        ):
            raise ContractViolation(
                "a forward-fix-only rollback must name who accepted it; 'there is no "
                "way back' is a decision somebody makes, not a property a plan has"
            )

        if self.kind.requires_acceptance and not self.description.strip():
            raise ContractViolation(
                "a forward-fix-only rollback must describe how recovery would work; "
                "'go forward' with no forward is not a strategy"
            )

    @property
    def provides_a_way_back(self) -> bool:
        return self.kind.provides_a_way_back

    @classmethod
    def none_required(cls) -> "RollbackStrategy":
        return cls(kind=RollbackKind.NONE_REQUIRED)

    @classmethod
    def compensating(cls, description: str = "each mutating task declares its reversal") -> "RollbackStrategy":
        return cls(kind=RollbackKind.COMPENSATING_TASKS, description=description)
