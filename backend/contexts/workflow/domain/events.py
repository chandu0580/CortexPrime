"""Workflow lifecycle events.

Namespaced ``workflow.runtime.*``. ``CONTRACT_NAME`` is globally unique and a
clash raises at import time.

These describe a graph *being assembled and decided on*, never a run. There is no
``NodeStarted``, no ``NodeSucceeded``: this context compiles workflows and has
nothing to say about what an executor did with one.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "WorkflowCreated",
    "WorkflowValidated",
    "WorkflowCompiled",
    "WorkflowApproved",
    "WorkflowVersioned",
    "NodeAdded",
    "BranchCreated",
    "ParallelGroupCreated",
    "WORKFLOW_EVENT_TYPES",
]

AGGREGATE_TYPE = "workflow"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class WorkflowCreated(DomainEvent):
    """A workflow was opened against an approved plan."""

    EVENT_TYPE = "workflow.runtime.created"

    workflow_id: str = ""
    plan_id: str = ""
    plan_digest: str = ""
    mission_id: str = ""
    title: str = ""
    version: int = 1
    plan_tasks: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("workflow_id", self.workflow_id)
        _require_text("plan_id", self.plan_id)
        _require_text("plan_digest", self.plan_digest)
        _require_text("mission_id", self.mission_id)
        if self.version < 1:
            raise ContractViolation("version starts at 1")


@dataclass(frozen=True)
class NodeAdded(DomainEvent):
    """A node joined the graph. Nothing has run."""

    EVENT_TYPE = "workflow.runtime.node_added"

    workflow_id: str = ""
    node_id: str = ""
    kind: str = ""
    purpose: str = ""
    plan_task_id: str = ""
    side_effect: str = "read"
    retries: int = 1
    has_timeout: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("workflow_id", self.workflow_id)
        _require_text("node_id", self.node_id)
        _require_text("kind", self.kind)
        if not isinstance(self.has_timeout, bool):
            raise ContractViolation("has_timeout must be a bool")
        # A task node runs planned work; a control-flow node runs none.
        if self.kind == "task" and not self.plan_task_id.strip():
            raise ContractViolation(
                "a task node names the plan task it runs; orchestration runs what was "
                "planned, never work of its own"
            )


@dataclass(frozen=True)
class BranchCreated(DomainEvent):
    """A decision point was added.

    Refuses construction without a default arm, mirroring the node: a branch that
    could stall on the case nobody thought of should not be describable in the
    log either.
    """

    EVENT_TYPE = "workflow.runtime.branch_created"

    workflow_id: str = ""
    node_id: str = ""
    arms: int = 0
    has_default: bool = False
    conditions: tuple = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("workflow_id", self.workflow_id)
        _require_text("node_id", self.node_id)
        if not isinstance(self.has_default, bool):
            raise ContractViolation("has_default must be a bool")
        if self.arms < 2:
            raise ContractViolation(
                "a branch has at least two arms; one that always goes the same way is "
                "an edge with extra steps"
            )
        if not self.has_default:
            raise ContractViolation(
                "a branch declares a default arm; conditions cannot be proved "
                "exhaustive, so an input matching none of them would stall the run"
            )


@dataclass(frozen=True)
class ParallelGroupCreated(DomainEvent):
    """A fan-out was declared, and its members were checked for independence."""

    EVENT_TYPE = "workflow.runtime.parallel_group_created"

    workflow_id: str = ""
    group_id: str = ""
    label: str = ""
    members: int = 0
    join: str = "all"
    max_concurrency: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("workflow_id", self.workflow_id)
        _require_text("group_id", self.group_id)
        _require_text("join", self.join)
        if self.members < 2:
            raise ContractViolation(
                "a parallel group has at least two members; a group of one is "
                "sequential execution with more machinery"
            )


@dataclass(frozen=True)
class WorkflowValidated(DomainEvent):
    """The graph is well-formed."""

    EVENT_TYPE = "workflow.runtime.validated"

    workflow_id: str = ""
    version: int = 1
    nodes: int = 0
    edges: int = 0
    depth: int = 0
    widest_layer: int = 0
    uncovered_plan_tasks: int = 0
    advisories: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("workflow_id", self.workflow_id)
        if self.nodes < 1:
            raise ContractViolation("a validated workflow contains at least one node")
        if self.uncovered_plan_tasks:
            raise ContractViolation(
                f"a workflow cannot be validated with {self.uncovered_plan_tasks} plan "
                "task(s) covered by no node"
            )


@dataclass(frozen=True)
class WorkflowCompiled(DomainEvent):
    """The derived form is frozen and the digest is bound.

    ``execution_order_length`` is what an executor checks against: a compiled
    order that does not cover every node is one an executor would silently
    complete early.
    """

    EVENT_TYPE = "workflow.runtime.compiled"

    workflow_id: str = ""
    version: int = 1
    digest: str = ""
    execution_order_length: int = 0
    compensation_order_length: int = 0
    critical_path_seconds: int = 0
    workflow_timeout_seconds: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("workflow_id", self.workflow_id)
        _require_text("digest", self.digest)
        if self.execution_order_length < 1:
            raise ContractViolation(
                "a compiled workflow carries an execution order; recomputing it at run "
                "time lets two executors disagree about a graph both consider valid"
            )
        if (
            self.workflow_timeout_seconds
            and self.critical_path_seconds > self.workflow_timeout_seconds
        ):
            raise ContractViolation(
                f"the longest path needs {self.critical_path_seconds}s but the workflow "
                f"times out after {self.workflow_timeout_seconds}s; it can never "
                "complete within its own deadline"
            )


@dataclass(frozen=True)
class WorkflowApproved(DomainEvent):
    """The workflow was accepted. Execution may run it."""

    EVENT_TYPE = "workflow.runtime.approved"

    workflow_id: str = ""
    version: int = 1
    approved_by: str = ""
    digest: str = ""
    mutating_nodes: int = 0
    uncompensated_mutations: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("workflow_id", self.workflow_id)
        _require_text("digest", self.digest)
        _require_text("approved_by", self.approved_by)
        if self.uncompensated_mutations:
            raise ContractViolation(
                f"a workflow cannot be approved with {self.uncompensated_mutations} "
                "mutation(s) nothing walks back; reversibility is decided before "
                "action (Constitution P2)"
            )


@dataclass(frozen=True)
class WorkflowVersioned(DomainEvent):
    EVENT_TYPE = "workflow.runtime.versioned"

    workflow_id: str = ""
    successor_id: str = ""
    from_version: int = 1
    to_version: int = 2
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("workflow_id", self.workflow_id)
        _require_text("successor_id", self.successor_id)
        if self.workflow_id == self.successor_id:
            raise ContractViolation("a workflow cannot be its own successor")
        if self.to_version <= self.from_version:
            raise ContractViolation(
                f"version {self.to_version} does not follow {self.from_version}"
            )


WORKFLOW_EVENT_TYPES = (
    WorkflowCreated,
    WorkflowValidated,
    WorkflowCompiled,
    WorkflowApproved,
    WorkflowVersioned,
    NodeAdded,
    BranchCreated,
    ParallelGroupCreated,
)
