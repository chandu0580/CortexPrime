"""Failures raised by the Workflow context.

Every one is a refusal to compile a workflow that cannot be executed, or that
could be executed into a state nobody designed.

The graph failures carry their evidence -- the cycle path, the unreachable nodes,
the tasks that were dropped. A refusal that says "the graph is wrong" leaves
whoever reads it to find the wrong part in two hundred nodes.

None of these are execution failures. This context runs nothing.
"""

from __future__ import annotations

from typing import Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "WorkflowError",
    "InvalidIdentifier",
    "IllegalWorkflowTransition",
    "WorkflowApproved",
    "WorkflowIsSuperseded",
    "CyclicWorkflow",
    "UnreachableNode",
    "DanglingEdge",
    "DuplicateNode",
    "UnknownNode",
    "TaskNotCovered",
    "TaskInvented",
    "ConditionNotUpstream",
    "BranchWithoutDefault",
    "BranchTooNarrow",
    "ParallelMembersDependent",
    "ParallelGroupTooSmall",
    "RetryWithoutIdempotency",
    "CompensationTargetInvalid",
    "TimeoutUnsatisfiable",
    "ResumePointInsideGroup",
    "IncompleteWorkflow",
    "WorkflowRefused",
    "DigestMismatch",
    "DigestNotComputed",
    "WorkflowNotFound",
    "DuplicateWorkflow",
]


class WorkflowError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(WorkflowError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class IllegalWorkflowTransition(WorkflowError):
    def __init__(
        self, *, workflow_id: str, source: str, target: str, permitted: Sequence[str]
    ) -> None:
        allowed = ", ".join(sorted(permitted)) or "(nothing -- this state is terminal)"
        super().__init__(
            f"workflow {workflow_id} cannot move {source} -> {target}; {source} may "
            f"only move to: {allowed}"
        )
        self.workflow_id = workflow_id
        self.source = source
        self.target = target
        self.permitted = tuple(permitted)


class WorkflowApproved(WorkflowError):
    """The workflow is approved and may not change.

    An approved workflow is what execution runs. One that changed afterwards
    would mean work ran against something nobody approved. Revise it into a new
    version; the link is kept.
    """

    def __init__(self, *, workflow_id: str, operation: str) -> None:
        super().__init__(
            f"workflow {workflow_id} is approved; {operation} would change a graph "
            "execution has already been authorised to run. Revise it into a new version"
        )
        self.workflow_id = workflow_id
        self.operation = operation


class WorkflowIsSuperseded(WorkflowError):
    def __init__(self, *, workflow_id: str, successor: str) -> None:
        super().__init__(
            f"workflow {workflow_id} is superseded by {successor}; a later version "
            "replaced it"
        )
        self.workflow_id = workflow_id
        self.successor = successor


class CyclicWorkflow(WorkflowError):
    """The control-flow graph contains a cycle.

    A loop in an orchestration graph is not iteration -- there is no loop
    construct here, deliberately -- it is a path that can never complete. An
    executor entering it either spins or waits forever.
    """

    def __init__(self, cycle: Sequence[str]) -> None:
        path = " -> ".join(list(cycle) + [cycle[0]]) if cycle else "?"
        super().__init__(
            f"the workflow graph contains a cycle: {path}. There is no loop construct "
            "here; a cycle is a path that can never complete"
        )
        self.cycle = tuple(cycle)


class UnreachableNode(WorkflowError):
    """A node disconnected from the rest of the workflow.

    Worse than an error at runtime: nothing triggers it and nothing waits for it,
    so the workflow completes *successfully* having silently skipped it, and the
    work it represented simply never happened.

    Detected by weak connectivity rather than reachability from entry points,
    because an unwired node has no predecessors and would therefore look like a
    legitimate entry point -- passing exactly the check meant to catch it.
    """

    def __init__(self, unreachable: Sequence[str]) -> None:
        listed = ", ".join(sorted(unreachable)[:5])
        more = f" (+{len(unreachable) - 5} more)" if len(unreachable) > 5 else ""
        super().__init__(
            f"{len(unreachable)} node(s) are disconnected from the rest of the "
            f"workflow: {listed}{more}. Nothing triggers them and nothing waits for "
            "them, so the workflow would report success having never run them"
        )
        self.unreachable = tuple(unreachable)


class DanglingEdge(WorkflowError):
    def __init__(self, *, edge: str, missing: Sequence[str]) -> None:
        listed = ", ".join(sorted(missing))
        super().__init__(
            f"edge {edge} references {listed}, which the workflow does not contain"
        )
        self.edge = edge
        self.missing = tuple(missing)


class DuplicateNode(WorkflowError):
    def __init__(self, node_id: str) -> None:
        super().__init__(
            f"node {node_id!r} is already in the workflow; two nodes with one id make "
            "every edge naming it ambiguous"
        )
        self.node_id = node_id


class UnknownNode(WorkflowError):
    def __init__(self, *, workflow_id: str, node_id: str) -> None:
        super().__init__(f"workflow {workflow_id} has no node {node_id!r}")
        self.workflow_id = workflow_id
        self.node_id = node_id


class TaskNotCovered(WorkflowError):
    """A plan task no node runs.

    The workflow would report success having never done part of what the plan
    said. This is the orchestration equivalent of an approval that skipped a
    file.
    """

    def __init__(self, uncovered: Sequence[str]) -> None:
        listed = ", ".join(sorted(uncovered)[:5])
        more = f" (+{len(uncovered) - 5} more)" if len(uncovered) > 5 else ""
        super().__init__(
            f"{len(uncovered)} plan task(s) are covered by no node: {listed}{more}. "
            "The workflow would report success having never done them"
        )
        self.uncovered = tuple(uncovered)


class TaskInvented(WorkflowError):
    """A node running work the plan does not contain.

    Orchestration may reorder, branch and parallelise what the plan authorised.
    It may not add to it -- work nobody planned is work nobody approved.
    """

    def __init__(self, invented: Sequence[str]) -> None:
        listed = ", ".join(sorted(invented)[:5])
        more = f" (+{len(invented) - 5} more)" if len(invented) > 5 else ""
        super().__init__(
            f"{len(invented)} node(s) run work the plan does not contain: {listed}"
            f"{more}. Orchestration may reorder what was approved, never add to it"
        )
        self.invented = tuple(invented)


class ConditionNotUpstream(WorkflowError):
    """A condition branching on a node that has not run yet.

    Reading the outcome of something downstream is not a decision, it is a
    guess -- and at runtime it is a null the executor has to invent a meaning for.
    """

    def __init__(self, *, node_id: str, source: str) -> None:
        super().__init__(
            f"node {node_id!r} branches on the outcome of {source!r}, which is not "
            "upstream of it; the outcome will not exist when the condition is "
            "evaluated"
        )
        self.node_id = node_id
        self.source = source


class BranchWithoutDefault(WorkflowError):
    """A branch with no default stalls on the case nobody thought of.

    Arbitrary conditions cannot be proved exhaustive, so an explicit default is
    required rather than inferred. Without one, an input that matches no arm
    leaves the workflow with nowhere to go and no error to report.
    """

    def __init__(self, node_id: str) -> None:
        super().__init__(
            f"branch {node_id!r} declares no default arm; conditions cannot be proved "
            "exhaustive, so an input matching none of them would leave the workflow "
            "with nowhere to go and nothing to report"
        )
        self.node_id = node_id


class BranchTooNarrow(WorkflowError):
    def __init__(self, *, node_id: str, arms: int) -> None:
        super().__init__(
            f"branch {node_id!r} has {arms} arm(s); a branch that always goes the same "
            "way is an edge with extra steps"
        )
        self.node_id = node_id
        self.arms = arms


class ParallelMembersDependent(WorkflowError):
    """Two members of a parallel group where one waits for the other.

    Running them concurrently is not faster; it is a deadlock or a race,
    depending on how the executor handles the dependency it was told to ignore.
    """

    def __init__(self, *, group: str, dependent: str, depends_on: str) -> None:
        super().__init__(
            f"parallel group {group!r} contains {dependent!r} and {depends_on!r}, but "
            f"{dependent!r} waits for {depends_on!r}; running them concurrently is a "
            "deadlock or a race, not a speed-up"
        )
        self.group = group
        self.dependent = dependent
        self.depends_on = depends_on


class ParallelGroupTooSmall(WorkflowError):
    def __init__(self, *, group: str, members: int) -> None:
        super().__init__(
            f"parallel group {group!r} has {members} member(s); a group of one is "
            "sequential execution with more machinery"
        )
        self.group = group
        self.members = members


class RetryWithoutIdempotency(WorkflowError):
    """Retrying a non-idempotent action is how a thing happens twice.

    A read may be retried freely. A write that is not idempotent and is retried
    after an ambiguous failure -- a timeout, a dropped connection -- may apply
    twice, and the second application is the one nobody planned.
    """

    def __init__(self, *, node_id: str, side_effect: str) -> None:
        super().__init__(
            f"node {node_id!r} is {side_effect!r} and is retried without an "
            "idempotency key; a retry after an ambiguous failure may apply the action "
            "twice, and nothing downstream would know"
        )
        self.node_id = node_id
        self.side_effect = side_effect


class CompensationTargetInvalid(WorkflowError):
    def __init__(self, *, node_id: str, reason: str) -> None:
        super().__init__(f"compensation {node_id!r} is invalid: {reason}")
        self.node_id = node_id
        self.reason = reason


class TimeoutUnsatisfiable(WorkflowError):
    """The workflow's own timeout is shorter than its longest path.

    A workflow that cannot complete within its deadline under any circumstances
    is one whose deadline is a lie: it will always be killed, and the kill will
    always look like a slow dependency.
    """

    def __init__(self, *, workflow_timeout: int, critical_path: int, path: Sequence[str]) -> None:
        route = " -> ".join(path[:6]) + (" ..." if len(path) > 6 else "")
        super().__init__(
            f"the workflow times out after {workflow_timeout}s but its longest path "
            f"needs {critical_path}s ({route}); it can never complete within its own "
            "deadline"
        )
        self.workflow_timeout = workflow_timeout
        self.critical_path = critical_path
        self.path = tuple(path)


class ResumePointInsideGroup(WorkflowError):
    """Resuming into half a fan-out is undefined.

    The other members either already ran, never ran, or ran partially, and
    nothing in the record says which.
    """

    def __init__(self, *, node_id: str, group: str) -> None:
        super().__init__(
            f"resume point {node_id!r} is inside parallel group {group!r}; resuming "
            "into half a fan-out leaves the other members in a state nothing records"
        )
        self.node_id = node_id
        self.group = group


class IncompleteWorkflow(WorkflowError):
    def __init__(self, *, workflow_id: str, missing: Sequence[str]) -> None:
        listed = ", ".join(sorted(missing))
        super().__init__(f"workflow {workflow_id} is missing: {listed}")
        self.workflow_id = workflow_id
        self.missing = tuple(missing)


class WorkflowRefused(WorkflowError):
    """Policy refused, with every reason at once."""

    def __init__(self, *, workflow_id: str, target: str, failures: Sequence) -> None:
        summary = "; ".join(f"{f.rule}: {f.detail}" for f in list(failures)[:3])
        more = f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        super().__init__(
            f"workflow {workflow_id} cannot be {target} -- {summary}{more}"
        )
        self.workflow_id = workflow_id
        self.target = target
        self.failures = tuple(failures)


class DigestMismatch(WorkflowError):
    def __init__(self, *, workflow_id: str, recorded: str, recomputed: str) -> None:
        super().__init__(
            f"workflow {workflow_id}: compiled with digest {recorded} but content now "
            f"hashes to {recomputed}; the graph on record is not the one compiled"
        )
        self.workflow_id = workflow_id
        self.recorded = recorded
        self.recomputed = recomputed


class DigestNotComputed(WorkflowError):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(
            f"workflow {workflow_id} has no digest; digests are computed at compilation"
        )
        self.workflow_id = workflow_id


class WorkflowNotFound(WorkflowError):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(f"no workflow with id {workflow_id}")
        self.workflow_id = workflow_id


class DuplicateWorkflow(WorkflowError):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(f"workflow {workflow_id} already exists")
        self.workflow_id = workflow_id
