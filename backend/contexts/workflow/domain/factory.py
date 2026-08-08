"""Construction helpers for the Workflow context."""

from __future__ import annotations

from typing import Optional, Sequence

from backend.contracts.execution import SideEffectClass
from backend.contexts.workflow.domain.identifiers import WorkflowId
from backend.contexts.workflow.domain.nodes import (
    BackoffKind,
    BranchArm,
    EdgeKind,
    WorkflowCondition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRetryPolicy,
    WorkflowTimeout,
)
from backend.contexts.workflow.domain.parallel import (
    JoinPolicy,
    ResumePoint,
    WorkflowCompensation,
    WorkflowParallelGroup,
)
from backend.contexts.workflow.domain.workflow import Workflow

__all__ = [
    "compile_from_plan",
    "task_node",
    "branch_node",
    "compensation_node",
    "edge",
    "arm",
    "retry",
    "timeout",
    "parallel_group",
    "compensation",
    "resume_point",
]


def compile_from_plan(
    *,
    plan_id: str,
    plan_digest: str,
    mission_id: str,
    title: str,
    plan_task_ids: Sequence[str],
    compiled_by: str = "workflow-runtime",
) -> Workflow:
    """An empty workflow bound to the plan it orchestrates.

    ``plan_task_ids`` is what makes coverage checkable without importing the
    Planner: the workflow declares what it was compiled from, and the aggregate
    checks its nodes against that declaration.
    """
    return Workflow(
        workflow_id=WorkflowId.new(),
        plan_id=plan_id,
        plan_digest=plan_digest,
        mission_id=mission_id,
        title=title,
        plan_task_ids=frozenset(plan_task_ids),
        compiled_by=compiled_by,
    )


def task_node(
    node_id: str,
    purpose: str,
    plan_task_id: str,
    *,
    side_effect: SideEffectClass = SideEffectClass.READ,
    retry_policy: Optional[WorkflowRetryPolicy] = None,
    node_timeout: Optional[WorkflowTimeout] = None,
    cancellable: bool = True,
    execution_key: Optional[str] = None,
) -> WorkflowNode:
    return WorkflowNode.task(
        node_id,
        purpose,
        plan_task_id,
        side_effect=side_effect,
        retry=retry_policy,
        timeout=node_timeout,
        cancellable=cancellable,
        execution_key=execution_key,
    )


def branch_node(node_id: str, purpose: str, arms: Sequence[BranchArm]) -> WorkflowNode:
    return WorkflowNode.branch(node_id, purpose, arms)


def compensation_node(
    node_id: str,
    purpose: str,
    compensates: str,
    *,
    side_effect: SideEffectClass = SideEffectClass.REVERSIBLE_WRITE,
    node_timeout: Optional[WorkflowTimeout] = None,
) -> WorkflowNode:
    return WorkflowNode.compensation(
        node_id, purpose, compensates, side_effect=side_effect, timeout=node_timeout
    )


def edge(
    from_node: str,
    to_node: str,
    *,
    kind: EdgeKind = EdgeKind.NORMAL,
    condition: Optional[WorkflowCondition] = None,
    label: str = "",
) -> WorkflowEdge:
    return WorkflowEdge(
        from_node=from_node,
        to_node=to_node,
        kind=kind,
        condition=condition or WorkflowCondition.always(),
        label=label,
    )


def arm(to_node: str, condition: WorkflowCondition, label: str = "") -> BranchArm:
    return BranchArm(to_node=to_node, condition=condition, label=label)


def retry(
    max_attempts: int,
    *,
    backoff: BackoffKind = BackoffKind.EXPONENTIAL,
    initial_delay_seconds: int = 1,
    max_delay_seconds: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> WorkflowRetryPolicy:
    return WorkflowRetryPolicy(
        max_attempts=max_attempts,
        backoff=backoff,
        initial_delay_seconds=initial_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        idempotency_key=idempotency_key,
    )


def timeout(
    seconds: int, *, on_timeout: str = "fail", grace_seconds: int = 0
) -> WorkflowTimeout:
    return WorkflowTimeout(
        seconds=seconds, on_timeout=on_timeout, grace_seconds=grace_seconds
    )


def parallel_group(
    label: str,
    members: Sequence[str],
    *,
    join: JoinPolicy = JoinPolicy.ALL,
    quorum: Optional[int] = None,
    max_concurrency: Optional[int] = None,
) -> WorkflowParallelGroup:
    return WorkflowParallelGroup.create(
        label, members, join=join, quorum=quorum, max_concurrency=max_concurrency
    )


def compensation(
    compensates: str, performed_by: str, *, trigger: str = "on_failure", order: int = 0
) -> WorkflowCompensation:
    return WorkflowCompensation(
        compensates=compensates, performed_by=performed_by, trigger=trigger, order=order
    )


def resume_point(node_id: str, label: str = "") -> ResumePoint:
    return ResumePoint(node_id=node_id, label=label)
