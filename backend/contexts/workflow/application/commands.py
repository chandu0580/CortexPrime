"""Commands and queries for the Workflow context.

Frozen values naming one intent each, carrying primitives rather than domain
objects so a command can be serialised, queued, and replayed without dragging the
domain across the wire.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "CompileWorkflow",
    "AddNode",
    "RemoveNode",
    "AddEdge",
    "AddBranch",
    "AddParallelGroup",
    "AddCompensation",
    "AddResumePoint",
    "SetWorkflowTimeout",
    "ValidateWorkflow",
    "CompileGraph",
    "ApproveWorkflow",
    "ReviseWorkflow",
    "GetWorkflow",
    "GetGraph",
    "ListWorkflows",
]

#: Side effects that change the world. Mirrors ``SideEffectClass.mutates`` so the
#: command can refuse before loading; the domain enforces it regardless.
_MUTATING = frozenset({"reversible_write", "irreversible_write", "destructive"})


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class CompileWorkflow:
    plan_id: str
    plan_digest: str
    mission_id: str
    title: str
    plan_task_ids: tuple = ()
    compiled_by: str = "workflow-runtime"

    def __post_init__(self) -> None:
        _require(bool(self.plan_id), "plan_id is required")
        _require(
            bool(self.plan_digest and self.plan_digest.strip()),
            "plan_digest is required; without it the workflow cannot be shown to "
            "orchestrate the plan that was actually approved",
        )
        _require(bool(self.mission_id), "mission_id is required")
        _require(bool(self.title and self.title.strip()), "title is required")
        _require(
            bool(self.plan_task_ids),
            "plan_task_ids is required; without it nothing can check that the "
            "workflow runs all of the plan and none of its own invention",
        )


@dataclass(frozen=True)
class AddNode:
    workflow_id: str
    node_id: str
    purpose: str
    kind: str = "task"
    plan_task_id: Optional[str] = None
    side_effect: str = "read"
    max_attempts: int = 1
    backoff: str = "none"
    initial_delay_seconds: int = 0
    idempotency_key: Optional[str] = None
    timeout_seconds: Optional[int] = None
    on_timeout: str = "fail"
    compensates: Optional[str] = None
    cancellable: bool = True
    execution_key: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(bool(self.node_id and self.node_id.strip()), "node_id is required")
        _require(
            bool(self.purpose and self.purpose.strip()),
            "a node must state its purpose; one nobody can explain is one nobody can "
            "review",
        )
        _require(
            self.kind != "task" or bool(self.plan_task_id),
            "a task node must name the plan task it runs; orchestration runs what was "
            "planned, never work of its own",
        )
        _require(
            self.kind != "compensation" or bool(self.compensates),
            "a compensation must name the node it walks back",
        )
        _require(
            self.max_attempts < 2
            or self.side_effect not in _MUTATING
            or bool(self.idempotency_key and self.idempotency_key.strip()),
            f"a {self.side_effect!r} node retried without an idempotency key may apply "
            "the action twice after an ambiguous failure",
        )


@dataclass(frozen=True)
class RemoveNode:
    workflow_id: str
    node_id: str

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(bool(self.node_id), "node_id is required")


@dataclass(frozen=True)
class AddEdge:
    workflow_id: str
    from_node: str
    to_node: str
    kind: str = "normal"
    condition_kind: str = "always"
    condition_source: Optional[str] = None
    condition_expression: Optional[str] = None
    label: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(bool(self.from_node), "from_node is required")
        _require(bool(self.to_node), "to_node is required")
        _require(
            self.from_node != self.to_node,
            "an edge from a node to itself is a cycle of length one",
        )
        _require(
            self.condition_kind == "always" or bool(self.condition_source),
            "a condition that reads an outcome must name the node it reads",
        )


@dataclass(frozen=True)
class AddBranch:
    """``arms`` is a tuple of mappings: to_node, condition_kind, source, expression."""

    workflow_id: str
    node_id: str
    purpose: str
    arms: tuple = ()

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(bool(self.node_id), "node_id is required")
        _require(bool(self.purpose and self.purpose.strip()), "purpose is required")
        _require(
            len(self.arms) >= 2,
            "a branch has at least two arms; one that always goes the same way is an "
            "edge with extra steps",
        )
        _require(
            any(a.get("condition_kind", "always") == "always" for a in self.arms),
            "a branch must declare a default arm; conditions cannot be proved "
            "exhaustive, so an input matching none of them would stall the run",
        )


@dataclass(frozen=True)
class AddParallelGroup:
    workflow_id: str
    label: str
    members: tuple = ()
    join: str = "all"
    quorum: Optional[int] = None
    max_concurrency: Optional[int] = None

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(bool(self.label and self.label.strip()), "label is required")
        _require(
            len(self.members) >= 2,
            "a parallel group has at least two members; a group of one is sequential "
            "execution with more machinery",
        )
        _require(
            self.join != "quorum" or bool(self.quorum),
            "a quorum join must say how many members it needs",
        )


@dataclass(frozen=True)
class AddCompensation:
    workflow_id: str
    compensates: str
    performed_by: str
    trigger: str = "on_failure"

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(bool(self.compensates), "compensates is required")
        _require(bool(self.performed_by), "performed_by is required")
        _require(
            self.compensates != self.performed_by, "a node cannot compensate itself"
        )


@dataclass(frozen=True)
class AddResumePoint:
    workflow_id: str
    node_id: str
    label: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(bool(self.node_id), "node_id is required")


@dataclass(frozen=True)
class SetWorkflowTimeout:
    workflow_id: str
    seconds: int
    on_timeout: str = "fail"
    grace_seconds: int = 0

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(
            self.seconds >= 1,
            "a timeout must be at least one second; a zero timeout abandons work "
            "before it starts",
        )


@dataclass(frozen=True)
class ValidateWorkflow:
    workflow_id: str

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")


@dataclass(frozen=True)
class CompileGraph:
    workflow_id: str

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")


@dataclass(frozen=True)
class ApproveWorkflow:
    workflow_id: str
    approved_by: str

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(
            bool(self.approved_by and self.approved_by.strip()),
            "an approval must name who gave it; an unattributed authorisation has "
            "nobody accountable for it",
        )


@dataclass(frozen=True)
class ReviseWorkflow:
    workflow_id: str
    reason: str = "a revised version replaces this one"

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")


@dataclass(frozen=True)
class GetWorkflow:
    workflow_id: str


@dataclass(frozen=True)
class GetGraph:
    workflow_id: str


@dataclass(frozen=True)
class ListWorkflows:
    plan_id: Optional[str] = None
    mission_id: Optional[str] = None
    status: Optional[str] = None
    executable_only: bool = False
