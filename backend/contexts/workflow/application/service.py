"""The Workflow application service.

Where the aggregate's invariants meet workflow policy and the repository's facts.
Events are returned, never published -- this context owns no bus, the same
arrangement as every other context in this codebase.

Every gate reports every failure at once
------------------------------------------
Validation, compilation and approval all run the policy first and refuse with
the whole list. For a graph this matters more than elsewhere: a workflow can have
an unreachable node *and* an uncompensated mutation *and* an unmeetable deadline,
and finding them one round-trip at a time is how orchestration becomes the slow
part.

What this service deliberately cannot do
-----------------------------------------
It cannot run a node, invoke a tool, schedule anything, or touch a plan. Every
method either records a decision about the graph, checks whether the graph holds
together, or answers a question about it. If a method ever needs to *make
something happen*, it belongs in Execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contracts.execution import SideEffectClass
from backend.contexts.workflow.application.commands import (
    AddBranch,
    AddCompensation,
    AddEdge,
    AddNode,
    AddParallelGroup,
    AddResumePoint,
    ApproveWorkflow,
    CompileGraph,
    CompileWorkflow,
    GetGraph,
    GetWorkflow,
    ListWorkflows,
    RemoveNode,
    ReviseWorkflow,
    SetWorkflowTimeout,
    ValidateWorkflow,
)
from backend.contexts.workflow.domain.errors import WorkflowNotFound, WorkflowRefused
from backend.contexts.workflow.domain.events import (
    AGGREGATE_TYPE,
    BranchCreated,
    NodeAdded,
    ParallelGroupCreated,
    WorkflowApproved,
    WorkflowCompiled,
    WorkflowCreated,
    WorkflowValidated,
    WorkflowVersioned,
)
from backend.contexts.workflow.domain.factory import (
    arm,
    branch_node,
    compensation,
    compensation_node,
    compile_from_plan,
    edge,
    parallel_group,
    resume_point,
    retry,
    task_node,
    timeout,
)
from backend.contexts.workflow.domain.identifiers import WorkflowId
from backend.contexts.workflow.domain.nodes import (
    BackoffKind,
    ConditionKind,
    EdgeKind,
    NodeKind,
    WorkflowCondition,
    WorkflowRetryPolicy,
)
from backend.contexts.workflow.domain.parallel import JoinPolicy
from backend.contexts.workflow.domain.policy import WorkflowPolicy, default_policy
from backend.contexts.workflow.domain.status import WorkflowStatus
from backend.contexts.workflow.domain.workflow import Workflow
from backend.platform.events import EventMetadata

__all__ = ["WorkflowService", "CommandResult"]


def _condition(kind: str, source: Optional[str], expression: Optional[str]):
    return WorkflowCondition(
        kind=ConditionKind(kind), source_node=source, expression=expression
    )


@dataclass(frozen=True)
class CommandResult:
    workflow: Workflow
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class WorkflowService:
    def __init__(self, repository: Any, policy: Optional[WorkflowPolicy] = None) -> None:
        self._repository = repository
        self._policy = policy or default_policy()

    @property
    def policy(self) -> WorkflowPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, workflow: Workflow) -> EventMetadata:
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(workflow.workflow_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
        )

    def _load(self, context: Any, workflow_id: str) -> Workflow:
        found = self._repository.find(context, WorkflowId(workflow_id))
        if found is None:
            raise WorkflowNotFound(workflow_id)
        return found

    def _saved(self, context: Any, workflow: Workflow, events: tuple = ()) -> CommandResult:
        self._repository.replace(context, workflow)
        return CommandResult(workflow=workflow, events=events)

    def _gated(self, workflow: Workflow, to_status: WorkflowStatus) -> None:
        report = self._policy.evaluate(workflow, to_status)
        if not report.may_proceed:
            raise WorkflowRefused(
                workflow_id=str(workflow.workflow_id),
                target=to_status.value,
                failures=report.blocking,
            )

    # ------------------------------------------------------------------
    # Compiling from a plan
    # ------------------------------------------------------------------

    def compile_workflow(self, context: Any, command: CompileWorkflow) -> CommandResult:
        """Open a workflow bound to the plan it orchestrates."""
        workflow = compile_from_plan(
            plan_id=command.plan_id,
            plan_digest=command.plan_digest,
            mission_id=command.mission_id,
            title=command.title,
            plan_task_ids=tuple(command.plan_task_ids),
            compiled_by=command.compiled_by,
        )
        self._repository.save(context, workflow)
        return CommandResult(
            workflow=workflow,
            events=(
                WorkflowCreated(
                    metadata=self._metadata(context, workflow),
                    workflow_id=str(workflow.workflow_id),
                    plan_id=workflow.plan_id,
                    plan_digest=workflow.plan_digest,
                    mission_id=workflow.mission_id,
                    title=workflow.title,
                    version=workflow.version,
                    plan_tasks=len(workflow.plan_task_ids),
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Building the graph
    # ------------------------------------------------------------------

    def add_node(self, context: Any, command: AddNode) -> CommandResult:
        workflow = self._load(context, command.workflow_id)

        retry_policy = WorkflowRetryPolicy.none()
        if command.max_attempts > 1:
            retry_policy = retry(
                command.max_attempts,
                backoff=BackoffKind(command.backoff),
                initial_delay_seconds=max(command.initial_delay_seconds, 1),
                idempotency_key=command.idempotency_key,
            )
        node_timeout = (
            timeout(command.timeout_seconds, on_timeout=command.on_timeout)
            if command.timeout_seconds
            else None
        )

        kind = NodeKind(command.kind)
        if kind is NodeKind.COMPENSATION:
            node = compensation_node(
                command.node_id,
                command.purpose,
                command.compensates,
                side_effect=SideEffectClass(command.side_effect),
                node_timeout=node_timeout,
            )
        else:
            node = task_node(
                command.node_id,
                command.purpose,
                command.plan_task_id,
                side_effect=SideEffectClass(command.side_effect),
                retry_policy=retry_policy,
                node_timeout=node_timeout,
                cancellable=command.cancellable,
                execution_key=command.execution_key,
            )

        updated = workflow.add_node(node)
        self._repository.replace(context, updated)
        return CommandResult(
            workflow=updated,
            events=(
                NodeAdded(
                    metadata=self._metadata(context, updated),
                    workflow_id=str(updated.workflow_id),
                    node_id=node.node_id,
                    kind=node.kind.value,
                    purpose=node.purpose,
                    plan_task_id=node.plan_task_id or "",
                    side_effect=node.side_effect.value,
                    retries=node.retry.max_attempts,
                    has_timeout=node.timeout is not None,
                ),
            ),
        )

    def remove_node(self, context: Any, command: RemoveNode) -> CommandResult:
        workflow = self._load(context, command.workflow_id)
        return self._saved(context, workflow.remove_node(command.node_id))

    def add_edge(self, context: Any, command: AddEdge) -> CommandResult:
        workflow = self._load(context, command.workflow_id)
        updated = workflow.add_edge(
            edge(
                command.from_node,
                command.to_node,
                kind=EdgeKind(command.kind),
                condition=_condition(
                    command.condition_kind,
                    command.condition_source,
                    command.condition_expression,
                ),
                label=command.label,
            )
        )
        return self._saved(context, updated)

    def add_branch(self, context: Any, command: AddBranch) -> CommandResult:
        """Add a decision point. The default arm is required."""
        workflow = self._load(context, command.workflow_id)
        arms = tuple(
            arm(
                entry["to_node"],
                _condition(
                    entry.get("condition_kind", "always"),
                    entry.get("source"),
                    entry.get("expression"),
                ),
                entry.get("label", ""),
            )
            for entry in command.arms
        )
        node = branch_node(command.node_id, command.purpose, arms)
        updated = workflow.add_node(node)
        self._repository.replace(context, updated)

        return CommandResult(
            workflow=updated,
            events=(
                BranchCreated(
                    metadata=self._metadata(context, updated),
                    workflow_id=str(updated.workflow_id),
                    node_id=node.node_id,
                    arms=len(node.arms),
                    has_default=node.default_arm is not None,
                    conditions=tuple(str(a.condition) for a in node.arms),
                ),
            ),
        )

    def add_parallel_group(
        self, context: Any, command: AddParallelGroup
    ) -> CommandResult:
        """Declare a fan-out. Independence is checked against the graph."""
        workflow = self._load(context, command.workflow_id)
        group = parallel_group(
            command.label,
            tuple(command.members),
            join=JoinPolicy(command.join),
            quorum=command.quorum,
            max_concurrency=command.max_concurrency,
        )
        updated = workflow.add_parallel_group(group)
        self._repository.replace(context, updated)

        return CommandResult(
            workflow=updated,
            events=(
                ParallelGroupCreated(
                    metadata=self._metadata(context, updated),
                    workflow_id=str(updated.workflow_id),
                    group_id=str(group.group_id),
                    label=group.label,
                    members=group.size,
                    join=group.join.value,
                    max_concurrency=group.effective_concurrency,
                ),
            ),
        )

    def add_compensation(self, context: Any, command: AddCompensation) -> CommandResult:
        workflow = self._load(context, command.workflow_id)
        updated = workflow.add_compensation(
            compensation(
                command.compensates, command.performed_by, trigger=command.trigger
            )
        )
        return self._saved(context, updated)

    def add_resume_point(self, context: Any, command: AddResumePoint) -> CommandResult:
        workflow = self._load(context, command.workflow_id)
        updated = workflow.add_resume_point(
            resume_point(command.node_id, command.label)
        )
        return self._saved(context, updated)

    def set_timeout(self, context: Any, command: SetWorkflowTimeout) -> CommandResult:
        workflow = self._load(context, command.workflow_id)
        updated = workflow.set_timeout(
            timeout(
                command.seconds,
                on_timeout=command.on_timeout,
                grace_seconds=command.grace_seconds,
            )
        )
        return self._saved(context, updated)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def validate(self, context: Any, command: ValidateWorkflow) -> CommandResult:
        workflow = self._load(context, command.workflow_id)
        self._gated(workflow, WorkflowStatus.VALIDATED)
        validated = workflow.validate()
        self._repository.replace(context, validated)

        graph = validated.graph
        advisories = self._policy.evaluate(validated, WorkflowStatus.COMPILED).advisory
        return CommandResult(
            workflow=validated,
            events=(
                WorkflowValidated(
                    metadata=self._metadata(context, validated),
                    workflow_id=str(validated.workflow_id),
                    version=validated.version,
                    nodes=len(validated.nodes),
                    edges=len(validated.edges),
                    depth=graph.depth,
                    widest_layer=graph.widest_layer,
                    uncovered_plan_tasks=len(validated.uncovered_plan_tasks),
                    advisories=len(advisories),
                ),
            ),
        )

    def compile_graph(self, context: Any, command: CompileGraph) -> CommandResult:
        """Freeze the derived form and bind the digest."""
        workflow = self._load(context, command.workflow_id)
        self._gated(workflow, WorkflowStatus.COMPILED)
        compiled = workflow.compile()
        self._repository.replace(context, compiled)

        needed, _ = compiled.critical_path()
        return CommandResult(
            workflow=compiled,
            events=(
                WorkflowCompiled(
                    metadata=self._metadata(context, compiled),
                    workflow_id=str(compiled.workflow_id),
                    version=compiled.version,
                    digest=compiled.digest or "",
                    execution_order_length=len(compiled.execution_order),
                    compensation_order_length=len(compiled.compensation_order),
                    critical_path_seconds=needed,
                    workflow_timeout_seconds=(
                        compiled.workflow_timeout.total_seconds
                        if compiled.workflow_timeout
                        else 0
                    ),
                ),
            ),
        )

    def approve(self, context: Any, command: ApproveWorkflow) -> CommandResult:
        workflow = self._load(context, command.workflow_id)
        self._gated(workflow, WorkflowStatus.APPROVED)
        approved = workflow.approve(command.approved_by)
        self._repository.replace(context, approved)

        return CommandResult(
            workflow=approved,
            events=(
                WorkflowApproved(
                    metadata=self._metadata(context, approved),
                    workflow_id=str(approved.workflow_id),
                    version=approved.version,
                    approved_by=approved.approved_by or "",
                    digest=approved.digest or "",
                    mutating_nodes=len(approved.mutating_nodes),
                    uncompensated_mutations=len(approved.uncompensated_mutations),
                ),
            ),
        )

    def revise(self, context: Any, command: ReviseWorkflow) -> CommandResult:
        """Open the next version and supersede this one. Both stay on record."""
        workflow = self._load(context, command.workflow_id)
        successor = workflow.revise()
        self._repository.save(context, successor)

        superseded = workflow.supersede(successor.workflow_id)
        self._repository.replace(context, superseded)

        return CommandResult(
            workflow=successor,
            events=(
                WorkflowVersioned(
                    metadata=self._metadata(context, successor),
                    workflow_id=str(workflow.workflow_id),
                    successor_id=str(successor.workflow_id),
                    from_version=workflow.version,
                    to_version=successor.version,
                    reason=command.reason,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetWorkflow) -> Workflow:
        return self._load(context, query.workflow_id)

    def graph(self, context: Any, query: GetGraph):
        return self._load(context, query.workflow_id).graph

    def evaluate(self, context: Any, workflow_id: str, to_status: str):
        """Run the policy without transitioning."""
        return self._policy.evaluate(
            self._load(context, workflow_id), WorkflowStatus(to_status)
        )

    def list(self, context: Any, query: ListWorkflows) -> tuple:
        found = self._repository.all(context)
        if query.plan_id:
            found = tuple(w for w in found if w.plan_id == query.plan_id)
        if query.mission_id:
            found = tuple(w for w in found if w.mission_id == query.mission_id)
        if query.status:
            wanted = WorkflowStatus(query.status)
            found = tuple(w for w in found if w.status is wanted)
        if query.executable_only:
            found = tuple(w for w in found if w.is_executable)
        return tuple(found)

    def executable_for(self, context: Any, mission_id: str) -> Optional[Workflow]:
        """The approved workflow for a mission, if there is one.

        What Execution asks for, and the only thing it reads from this context.
        ``is_executable`` is APPROVED and nothing else, so this query is where
        approval becomes a precondition of running rather than a note on a record.

        Execution never calls this directly -- the two contexts do not import each
        other. ``backend.api.mission_control_composition`` is the one module that
        joins them.
        """
        candidates = [
            w
            for w in self._repository.all(context)
            if w.mission_id == mission_id and w.is_executable
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda w: (w.version, str(w.workflow_id)))
