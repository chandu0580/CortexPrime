"""Workflow nodes, conditions and edges: the control flow itself.

What Workflow adds that Planner did not have
----------------------------------------------
Planner produced a DAG of *data dependencies*: resize waits for audit because it
needs what audit found. That graph answers **what** and **in what order it must
happen**.

This graph answers **when, under what conditions, and what happens when it goes
wrong**: branches on outcomes, fan-outs with concurrency limits, retries with
backoff, compensations that walk the work back, timeouts, and the points a
suspended run can resume from.

Both are DAGs and they are not the same DAG. A plan dependency is a fact about
the work; a workflow edge is a decision about orchestration.

Nodes reference plan tasks; they never invent them
----------------------------------------------------
A ``TASK`` node names the plan task it runs. The aggregate refuses a workflow
that covers a plan task with no node -- it would report success having never
done part of what was approved -- and one whose node runs work the plan does not
contain. Orchestration may reorder, branch and parallelise what was authorised.
It may not add to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contexts.workflow.domain.errors import (
    BranchTooNarrow,
    BranchWithoutDefault,
    RetryWithoutIdempotency,
)
from backend.contexts.workflow.domain.identifiers import normalise_node_id

__all__ = [
    "NodeKind",
    "ConditionKind",
    "EdgeKind",
    "BackoffKind",
    "WorkflowCondition",
    "WorkflowEdge",
    "WorkflowRetryPolicy",
    "WorkflowTimeout",
    "WorkflowNode",
    "BranchArm",
]


class NodeKind(str, Enum):
    """What a node is for."""

    TASK = "task"
    """Runs one plan task. The only kind that does work."""

    BRANCH = "branch"
    """Chooses between outgoing paths on a condition."""

    PARALLEL = "parallel"
    """Fans out to a group of independent members."""

    JOIN = "join"
    """Waits for a fan-out to converge."""

    COMPENSATION = "compensation"
    """Walks back a task node that already ran."""

    @property
    def does_work(self) -> bool:
        """Whether this node runs something. Only tasks and compensations."""
        return self in (NodeKind.TASK, NodeKind.COMPENSATION)

    @property
    def is_control_flow(self) -> bool:
        return not self.does_work

    @property
    def needs_plan_task(self) -> bool:
        """Whether this node must name the plan task it runs.

        Only ``TASK``. A compensation names what it *undoes*, which is a node,
        not a plan task -- the plan declared the reversal, and the workflow
        orchestrates it.
        """
        return self is NodeKind.TASK


class ConditionKind(str, Enum):
    """What a condition reads.

    Deliberately small. Anything richer would need an expression language, and
    an expression language this context cannot evaluate is one whose errors are
    all discovered at run time.
    """

    ALWAYS = "always"
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    ON_OUTPUT = "on_output"

    @property
    def reads_a_node(self) -> bool:
        """Whether this condition depends on another node having run."""
        return self is not ConditionKind.ALWAYS

    @property
    def needs_expression(self) -> bool:
        return self is ConditionKind.ON_OUTPUT


class EdgeKind(str, Enum):
    """Which path an edge belongs to."""

    NORMAL = "normal"
    """The forward path."""

    ON_FAILURE = "on_failure"
    """Taken when the source fails. How a workflow handles a failure without
    treating it as the end."""

    COMPENSATING = "compensating"
    """Part of the walk-back path. Constitution S4 calls compensation a
    first-class path, not a failure state, and this is what makes it one."""

    @property
    def is_forward(self) -> bool:
        return self is EdgeKind.NORMAL


class BackoffKind(str, Enum):
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


@dataclass(frozen=True)
class WorkflowCondition(Contract):
    """A guard on an edge. Declared here, evaluated by execution.

    ``source_node`` is what makes this checkable: the aggregate refuses a
    condition whose source is not upstream, because the outcome would not exist
    when the condition is evaluated. That is the one thing this context can
    prove about a condition without evaluating it, and it is worth proving.
    """

    CONTRACT_NAME = "cortexprime.workflow.condition"

    kind: ConditionKind = ConditionKind.ALWAYS
    source_node: Optional[str] = None
    expression: Optional[str] = None
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ConditionKind):
            raise ContractViolation("kind must be a ConditionKind")

        if self.kind.reads_a_node:
            if not (self.source_node and self.source_node.strip()):
                raise ContractViolation(
                    f"a {self.kind.value!r} condition must name the node whose outcome "
                    "it reads; one that names nothing cannot be evaluated"
                )
            normalise_node_id(self.source_node)
        elif self.source_node is not None:
            raise ContractViolation("an 'always' condition reads no node")

        if self.kind.needs_expression and not (
            self.expression and self.expression.strip()
        ):
            raise ContractViolation(
                "an 'on_output' condition must carry the expression it evaluates; "
                "one that names an output but not a test decides nothing"
            )

    @property
    def is_unconditional(self) -> bool:
        return self.kind is ConditionKind.ALWAYS

    def __str__(self) -> str:
        if self.is_unconditional:
            return "always"
        if self.expression:
            return f"{self.kind.value}({self.source_node}): {self.expression}"
        return f"{self.kind.value}({self.source_node})"

    @classmethod
    def always(cls) -> "WorkflowCondition":
        return cls(kind=ConditionKind.ALWAYS)

    @classmethod
    def on_success(cls, source_node: str) -> "WorkflowCondition":
        return cls(kind=ConditionKind.ON_SUCCESS, source_node=source_node)

    @classmethod
    def on_failure(cls, source_node: str) -> "WorkflowCondition":
        return cls(kind=ConditionKind.ON_FAILURE, source_node=source_node)

    @classmethod
    def on_output(cls, source_node: str, expression: str) -> "WorkflowCondition":
        return cls(
            kind=ConditionKind.ON_OUTPUT, source_node=source_node, expression=expression
        )


@dataclass(frozen=True, order=True)
class WorkflowEdge:
    """One directed connection between nodes."""

    from_node: str
    to_node: str
    kind: EdgeKind = EdgeKind.NORMAL
    condition: WorkflowCondition = field(default_factory=WorkflowCondition.always)
    label: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_node", normalise_node_id(self.from_node))
        object.__setattr__(self, "to_node", normalise_node_id(self.to_node))
        if self.from_node == self.to_node:
            raise ContractViolation(
                f"edge {self.from_node!r} -> itself is a cycle of length one"
            )
        if not isinstance(self.kind, EdgeKind):
            raise ContractViolation("kind must be an EdgeKind")
        if not isinstance(self.condition, WorkflowCondition):
            raise ContractViolation("condition must be a WorkflowCondition")

    @property
    def edge_id(self) -> str:
        return f"{self.from_node}->{self.to_node}[{self.kind.value}]"

    @property
    def is_guarded(self) -> bool:
        return not self.condition.is_unconditional

    def __str__(self) -> str:
        return self.edge_id


@dataclass(frozen=True)
class WorkflowRetryPolicy(Contract):
    """How many times a node may be re-attempted, and how it waits.

    The rule this class exists for
    -------------------------------
    A node that mutates and is not idempotent may not be retried without an
    idempotency key. A retry after an *ambiguous* failure -- a timeout, a dropped
    connection -- cannot know whether the first attempt applied. Retrying anyway
    is how a thing happens twice, and the second time is the one nobody planned.

    Reads may be retried freely; ``SideEffectClass.READ`` is exempt.
    """

    CONTRACT_NAME = "cortexprime.workflow.retry_policy"

    max_attempts: int = 1
    backoff: BackoffKind = BackoffKind.NONE
    initial_delay_seconds: int = 0
    max_delay_seconds: Optional[int] = None
    idempotency_key: Optional[str] = None
    retry_on: tuple = ()

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or self.max_attempts < 1:
            raise ContractViolation(
                "max_attempts must be at least 1; the first attempt is an attempt"
            )
        if not isinstance(self.backoff, BackoffKind):
            raise ContractViolation("backoff must be a BackoffKind")
        if not isinstance(self.initial_delay_seconds, int) or self.initial_delay_seconds < 0:
            raise ContractViolation("initial_delay_seconds must be non-negative")

        if self.retries and self.backoff is BackoffKind.NONE and self.initial_delay_seconds == 0:
            raise ContractViolation(
                "a retry with no backoff and no delay re-attempts immediately; against "
                "a system that is failing because it is overloaded, that is the worst "
                "possible response"
            )
        if self.backoff is not BackoffKind.NONE and self.initial_delay_seconds < 1:
            raise ContractViolation(
                f"{self.backoff.value!r} backoff needs a delay to grow from"
            )
        if self.max_delay_seconds is not None:
            if self.max_delay_seconds < self.initial_delay_seconds:
                raise ContractViolation(
                    "max_delay_seconds cannot be below initial_delay_seconds"
                )
        if not isinstance(self.retry_on, tuple):
            raise ContractViolation("retry_on must be a tuple")

    @property
    def retries(self) -> bool:
        return self.max_attempts > 1

    @property
    def is_idempotent(self) -> bool:
        return bool(self.idempotency_key and self.idempotency_key.strip())

    def assert_safe_for(self, node_id: str, side_effect: SideEffectClass) -> None:
        """Refuse a retry that could apply a non-idempotent action twice."""
        if not self.retries:
            return
        if side_effect is SideEffectClass.READ:
            return
        if self.is_idempotent:
            return
        raise RetryWithoutIdempotency(node_id=node_id, side_effect=side_effect.value)

    def worst_case_seconds(self) -> int:
        """The longest this node could take waiting between attempts.

        Used by the timeout check. Deliberately worst-case: a timeout budget
        computed from the happy path is one that is only ever wrong when it
        matters.
        """
        if not self.retries:
            return 0
        total = 0
        delay = self.initial_delay_seconds
        for _ in range(self.max_attempts - 1):
            capped = min(delay, self.max_delay_seconds) if self.max_delay_seconds else delay
            total += capped
            if self.backoff is BackoffKind.EXPONENTIAL:
                delay *= 2
        return total

    @classmethod
    def none(cls) -> "WorkflowRetryPolicy":
        return cls(max_attempts=1)

    @classmethod
    def exponential(
        cls,
        max_attempts: int,
        *,
        initial_delay_seconds: int = 1,
        max_delay_seconds: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> "WorkflowRetryPolicy":
        return cls(
            max_attempts=max_attempts,
            backoff=BackoffKind.EXPONENTIAL,
            initial_delay_seconds=initial_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            idempotency_key=idempotency_key,
        )


@dataclass(frozen=True)
class WorkflowTimeout(Contract):
    """How long a node may take before it is abandoned.

    ``on_timeout`` says what a timeout *means*. Treating every timeout as a
    failure is wrong for a mutating node: a timed-out write may still have
    applied, so the safe response is to compensate rather than to retry or to
    carry on as though nothing happened.
    """

    CONTRACT_NAME = "cortexprime.workflow.timeout"

    seconds: int
    on_timeout: str = "fail"
    grace_seconds: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.seconds, int) or self.seconds < 1:
            raise ContractViolation(
                "a timeout must be at least one second; a zero timeout abandons work "
                "before it starts"
            )
        if self.on_timeout not in ("fail", "compensate", "cancel"):
            raise ContractViolation(
                "on_timeout must be one of: fail, compensate, cancel"
            )
        if not isinstance(self.grace_seconds, int) or self.grace_seconds < 0:
            raise ContractViolation("grace_seconds must be non-negative")

    @property
    def total_seconds(self) -> int:
        return self.seconds + self.grace_seconds

    @property
    def compensates(self) -> bool:
        return self.on_timeout == "compensate"


@dataclass(frozen=True)
class BranchArm:
    """One outgoing path from a branch, and the condition that selects it."""

    to_node: str
    condition: WorkflowCondition
    label: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "to_node", normalise_node_id(self.to_node))
        if not isinstance(self.condition, WorkflowCondition):
            raise ContractViolation("condition must be a WorkflowCondition")

    @property
    def is_default(self) -> bool:
        """The catch-all arm. Exactly one is required per branch."""
        return self.condition.is_unconditional


@dataclass(frozen=True)
class WorkflowNode(Contract):
    """One node in the control-flow graph."""

    CONTRACT_NAME = "cortexprime.workflow.node"

    node_id: str
    kind: NodeKind
    purpose: str
    plan_task_id: Optional[str] = None
    side_effect: SideEffectClass = SideEffectClass.READ
    retry: WorkflowRetryPolicy = field(default_factory=WorkflowRetryPolicy.none)
    timeout: Optional[WorkflowTimeout] = None
    compensates: Optional[str] = None
    arms: tuple = ()
    group_id: Optional[str] = None
    cancellable: bool = True
    execution_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", normalise_node_id(self.node_id))

        if not isinstance(self.kind, NodeKind):
            raise ContractViolation("kind must be a NodeKind")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ContractViolation(
                f"node {self.node_id!r} must state its purpose; one nobody can explain "
                "is one nobody can review"
            )
        if not isinstance(self.side_effect, SideEffectClass):
            raise ContractViolation("side_effect must be a SideEffectClass")
        if not isinstance(self.retry, WorkflowRetryPolicy):
            raise ContractViolation("retry must be a WorkflowRetryPolicy")
        if self.timeout is not None and not isinstance(self.timeout, WorkflowTimeout):
            raise ContractViolation("timeout must be a WorkflowTimeout")

        # A task node runs a plan task; nothing else does.
        if self.kind.needs_plan_task:
            if not (self.plan_task_id and self.plan_task_id.strip()):
                raise ContractViolation(
                    f"task node {self.node_id!r} must name the plan task it runs; "
                    "orchestration runs what was planned, never work of its own"
                )
        elif self.plan_task_id is not None:
            raise ContractViolation(
                f"a {self.kind.value!r} node runs no plan task"
            )

        # A compensation names what it undoes.
        if self.kind is NodeKind.COMPENSATION:
            if not (self.compensates and self.compensates.strip()):
                raise ContractViolation(
                    f"compensation {self.node_id!r} must name the node it walks back"
                )
            normalise_node_id(self.compensates)
            if self.compensates == self.node_id:
                raise ContractViolation(
                    f"compensation {self.node_id!r} cannot compensate itself"
                )
        elif self.compensates is not None:
            raise ContractViolation(
                f"a {self.kind.value!r} node compensates nothing"
            )

        # A branch declares its arms; nothing else does.
        if not isinstance(self.arms, tuple):
            raise ContractViolation("arms must be a tuple")
        if self.kind is NodeKind.BRANCH:
            for arm in self.arms:
                if not isinstance(arm, BranchArm):
                    raise ContractViolation("arms must contain BranchArm values")
            if len(self.arms) < 2:
                raise BranchTooNarrow(node_id=self.node_id, arms=len(self.arms))
            defaults = [a for a in self.arms if a.is_default]
            if not defaults:
                raise BranchWithoutDefault(self.node_id)
            if len(defaults) > 1:
                raise ContractViolation(
                    f"branch {self.node_id!r} declares {len(defaults)} default arms; "
                    "two catch-alls mean the second is unreachable"
                )
            targets = [a.to_node for a in self.arms]
            if len(set(targets)) != len(targets):
                raise ContractViolation(
                    f"branch {self.node_id!r} sends two arms to the same node; the "
                    "condition that chose between them decides nothing"
                )
        elif self.arms:
            raise ContractViolation(f"a {self.kind.value!r} node declares no arms")

        # Control-flow nodes do no work, so they classify no side effect.
        if self.kind.is_control_flow and self.side_effect is not SideEffectClass.READ:
            raise ContractViolation(
                f"a {self.kind.value!r} node performs no action, so it cannot be "
                f"classified {self.side_effect.value!r}"
            )

        # Constitution P2's retry corollary.
        self.retry.assert_safe_for(self.node_id, self.side_effect)

        if not isinstance(self.cancellable, bool):
            raise ContractViolation("cancellable must be a bool")

        # A mutating node that cannot be compensated must not be cancellable
        # mid-flight: cancelling it leaves a change nobody can walk back and
        # nobody recorded.
        if self.side_effect.mutates and not self.cancellable and self.timeout is None:
            # Legal, but worth nothing here -- policy reports it.
            pass

    # -- queries -------------------------------------------------------

    @property
    def mutates(self) -> bool:
        return self.side_effect.mutates

    @property
    def is_branch(self) -> bool:
        return self.kind is NodeKind.BRANCH

    @property
    def default_arm(self) -> Optional[BranchArm]:
        for arm in self.arms:
            if arm.is_default:
                return arm
        return None

    @property
    def worst_case_seconds(self) -> int:
        """The longest this node could take, including retry waits.

        Used by the whole-graph timeout check. A budget computed from the happy
        path is one that is only ever wrong when it matters.
        """
        base = self.timeout.total_seconds if self.timeout else 0
        attempts = self.retry.max_attempts
        return base * attempts + self.retry.worst_case_seconds()

    @classmethod
    def task(
        cls,
        node_id: str,
        purpose: str,
        plan_task_id: str,
        *,
        side_effect: SideEffectClass = SideEffectClass.READ,
        retry: Optional[WorkflowRetryPolicy] = None,
        timeout: Optional[WorkflowTimeout] = None,
        cancellable: bool = True,
        execution_key: Optional[str] = None,
    ) -> "WorkflowNode":
        return cls(
            node_id=node_id,
            kind=NodeKind.TASK,
            purpose=purpose,
            plan_task_id=plan_task_id,
            side_effect=side_effect,
            retry=retry or WorkflowRetryPolicy.none(),
            timeout=timeout,
            cancellable=cancellable,
            execution_key=execution_key,
        )

    @classmethod
    def branch(
        cls, node_id: str, purpose: str, arms: Sequence[BranchArm]
    ) -> "WorkflowNode":
        return cls(
            node_id=node_id, kind=NodeKind.BRANCH, purpose=purpose, arms=tuple(arms)
        )

    @classmethod
    def compensation(
        cls,
        node_id: str,
        purpose: str,
        compensates: str,
        *,
        side_effect: SideEffectClass = SideEffectClass.REVERSIBLE_WRITE,
        timeout: Optional[WorkflowTimeout] = None,
    ) -> "WorkflowNode":
        return cls(
            node_id=node_id,
            kind=NodeKind.COMPENSATION,
            purpose=purpose,
            compensates=compensates,
            side_effect=side_effect,
            timeout=timeout,
        )
