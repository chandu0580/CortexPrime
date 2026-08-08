"""Planned tasks: what would be done, declared without doing any of it.

Built on the published contracts
---------------------------------
``TaskRef`` (``contracts/mission.py``, BC-1) is the task vocabulary and this
context uses it rather than inventing a second one. It already enforces that a
task cannot depend on itself and that ``depends_on`` holds no duplicates.

``SideEffectClass`` (``contracts/execution.py``, BC-5) is how a task declares
what it would *do to the world* -- read, reversible write, irreversible write,
destructive. Declaring it is not invoking anything: that module says so itself,
and it is what lets a plan be risk-assessed and gated on rollback before anything
runs.

The rule this module carries
-----------------------------
Constitution P2, *reversibility precedes action*, at the task level: a task that
mutates must say how it would be undone, or say explicitly that it cannot be.
``ExecutionContract`` already enforces the same rule for a fully-specified
action; this applies it to a task that has not been specified that far yet,
because the planning stage is where the answer is cheapest to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionContract, SideEffectClass
from backend.contracts.mission import MissionRef, TaskRef, TaskState
from backend.contexts.planner.domain.identifiers import normalise_task_id

__all__ = ["Reversal", "PlanTask"]


@dataclass(frozen=True)
class Reversal:
    """How a task would be undone, and by what.

    ``compensating_task`` names another task in the same plan; ``inverse_action``
    names an action the executor would perform. Either answers the question. The
    third possibility -- that there is no way back -- is expressed by
    :attr:`PlanTask.irreversible_accepted_by`, which requires a name, because
    accepting an irreversible action is a decision somebody makes rather than a
    property something has.
    """

    compensating_task: Optional[str] = None
    inverse_action: Optional[str] = None
    note: str = ""

    def __post_init__(self) -> None:
        for label in ("compensating_task", "inverse_action"):
            value = getattr(self, label)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ContractViolation(f"{label} must be non-blank when given")
        if not (self.compensating_task or self.inverse_action):
            raise ContractViolation(
                "a reversal must name a compensating task or an inverse action; one "
                "that names neither is a promise nobody can act on"
            )

    @property
    def is_in_plan(self) -> bool:
        """Whether the way back is itself a task the plan contains."""
        return self.compensating_task is not None


@dataclass(frozen=True)
class PlanTask(Contract):
    """One unit of planned work. Nothing here performs it."""

    CONTRACT_NAME = "cortexprime.planner.task"

    task_id: str
    purpose: str
    goal_ids: frozenset = field(default_factory=frozenset)
    depends_on: tuple = ()
    side_effect: SideEffectClass = SideEffectClass.READ
    reversal: Optional[Reversal] = None
    irreversible_accepted_by: Optional[str] = None
    execution_key: Optional[str] = None
    execution_contract: Optional[ExecutionContract] = None
    estimate_note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", normalise_task_id(self.task_id))

        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ContractViolation(
                f"task {self.task_id!r} must state its purpose; a task nobody can "
                "explain is one nobody can review"
            )
        if not isinstance(self.side_effect, SideEffectClass):
            raise ContractViolation("side_effect must be a SideEffectClass")

        if not isinstance(self.depends_on, tuple):
            raise ContractViolation("depends_on must be a tuple")
        for dependency in self.depends_on:
            normalise_task_id(dependency)
        if self.task_id in self.depends_on:
            raise ContractViolation(f"task {self.task_id!r} depends on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ContractViolation(
                f"task {self.task_id!r} lists a dependency twice"
            )

        if not isinstance(self.goal_ids, (frozenset, set)):
            raise ContractViolation("goal_ids must be a set")
        object.__setattr__(self, "goal_ids", frozenset(self.goal_ids))

        if self.reversal is not None and not isinstance(self.reversal, Reversal):
            raise ContractViolation("reversal must be a Reversal")

        if self.execution_contract is not None and not isinstance(
            self.execution_contract, ExecutionContract
        ):
            raise ContractViolation("execution_contract must be an ExecutionContract")

        # Constitution P2, at the task level.
        if self.side_effect.mutates:
            has_reversal = self.reversal is not None or (
                self.execution_contract is not None
                and self.execution_contract.inverse is not None
            )
            accepted = bool(
                self.irreversible_accepted_by
                and self.irreversible_accepted_by.strip()
            )
            if not has_reversal and not accepted:
                raise ContractViolation(
                    f"task {self.task_id!r} is classified {self.side_effect.value!r} "
                    "and declares neither a reversal nor who accepted that it cannot "
                    "be reversed. Constitution P2 requires the answer before the "
                    "action, not after it"
                )
        elif self.reversal is not None:
            raise ContractViolation(
                f"task {self.task_id!r} only reads, so it has nothing to reverse"
            )

        # A declared contract must describe this task, not another one.
        if (
            self.execution_contract is not None
            and self.execution_key
            and self.execution_contract.execution_key != self.execution_key
        ):
            raise ContractViolation(
                f"task {self.task_id!r} names execution key {self.execution_key!r} but "
                f"carries a contract for {self.execution_contract.execution_key!r}"
            )

    # -- queries -------------------------------------------------------

    @property
    def mutates(self) -> bool:
        return self.side_effect.mutates

    @property
    def is_reversible(self) -> bool:
        """Whether a way back is declared. Irreversible-but-accepted is not one."""
        if self.reversal is not None:
            return True
        return (
            self.execution_contract is not None
            and self.execution_contract.inverse is not None
        )

    @property
    def is_accepted_irreversible(self) -> bool:
        return bool(self.mutates and not self.is_reversible)

    @property
    def requires_approval_by_default(self) -> bool:
        """Advisory only. Governance decides (I1); this never substitutes for it."""
        return self.side_effect in (
            SideEffectClass.IRREVERSIBLE_WRITE,
            SideEffectClass.DESTRUCTIVE,
        )

    def as_task_ref(self, mission_id: str) -> TaskRef:
        """Project onto the published vocabulary.

        What leaves this context when a plan is handed on. Every planned task is
        ``PENDING`` -- a plan describes work that has not happened, and a planner
        that could emit ``SUCCEEDED`` would be reporting execution it did not do.
        """
        return TaskRef(
            mission=MissionRef(mission_id=mission_id),
            task_id=self.task_id,
            purpose=self.purpose,
            state=TaskState.PENDING,
            depends_on=tuple(self.depends_on),
            execution_key=self.execution_key,
        )

    @classmethod
    def create(
        cls,
        task_id: str,
        purpose: str,
        *,
        goal_ids: Sequence[str] = (),
        depends_on: Sequence[str] = (),
        side_effect: SideEffectClass = SideEffectClass.READ,
        reversal: Optional[Reversal] = None,
        irreversible_accepted_by: Optional[str] = None,
        execution_key: Optional[str] = None,
        execution_contract: Optional[ExecutionContract] = None,
        estimate_note: str = "",
    ) -> "PlanTask":
        return cls(
            task_id=task_id,
            purpose=purpose,
            goal_ids=frozenset(goal_ids),
            depends_on=tuple(depends_on),
            side_effect=side_effect,
            reversal=reversal,
            irreversible_accepted_by=irreversible_accepted_by,
            execution_key=execution_key,
            execution_contract=execution_contract,
            estimate_note=estimate_note,
        )
