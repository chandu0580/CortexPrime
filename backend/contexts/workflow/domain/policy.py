"""Workflow policy: whether a graph is sound enough to compile and run.

The aggregate enforces what is *structurally* true. This decides what is
*advisable* -- a graph every invariant permits can still be one nobody should
run.

Kept out of the aggregate so the service can report every failure at once. For a
graph this matters more than elsewhere: a workflow can have an unreachable node
*and* an uncompensated mutation *and* an unmeetable deadline, and finding them
one round-trip at a time is how orchestration becomes the slow part.

The rules, and the failure each prevents
-----------------------------------------
**W0 the workflow is open, and the move is legal.**

**W1 the required elements are present.**

**W2 the graph is sound.** Re-checked here so the report carries every graph
problem at once rather than raising on the first.

**W3 a mutating node has a way back.** Constitution P2 at the orchestration
level: a change nothing walks back is one whose failure mode is "leave it and
call somebody".

**W4 a node that mutates and cannot be cancelled declares a timeout.** Otherwise
a run that must be stopped has no mechanism to stop it, and the only remaining
option is killing the executor mid-write.

**W5 an un-waited-for parallel member does not mutate.** Advisory-turned-blocking
for mutations: with ``ANY`` or ``QUORUM``, members that were not waited for may
still be applying changes after the workflow moved on, so the record of what
happened is wrong.

**W6 there is somewhere to resume from.** Advisory: a long workflow with no
resume point restarts from the beginning after any suspension, over a world that
has already changed.

**W7 a single point of failure is visible.** Advisory: one node whose failure
strands most of the graph is worth knowing about before committing.

**W8 unused concurrency.** Advisory: the graph permits a fan-out no parallel
group uses.

**W9 the deadline is meetable.** The workflow's own timeout must not be shorter
than its longest forward path. The aggregate refuses this too; the policy reports
it so an unmeetable deadline arrives alongside the other problems rather than
raising first and hiding them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contexts.workflow.domain.errors import (
    CyclicWorkflow,
    DanglingEdge,
    UnreachableNode,
)
from backend.contexts.workflow.domain.graph import WorkflowGraph
from backend.contexts.workflow.domain.status import (
    WorkflowStatus,
    is_legal_transition,
    permitted_from,
    refusal_reason,
)

__all__ = [
    "Severity",
    "PolicyFinding",
    "PolicyReport",
    "WorkflowPolicy",
    "default_policy",
    "SPOF_RATIO",
    "LONG_WORKFLOW_NODES",
]

#: A node whose failure would strand more than this share of the graph is called
#: out. A judgement, named so it can be argued with.
SPOF_RATIO = 0.5

#: Above this many nodes, a workflow with no resume point is worth a comment.
LONG_WORKFLOW_NODES = 8


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"

    @property
    def refuses(self) -> bool:
        return self is Severity.BLOCKING


@dataclass(frozen=True)
class PolicyFinding:
    rule: str
    severity: Severity
    detail: str
    subject: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class PolicyReport:
    findings: tuple = ()

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.refuses)

    @property
    def advisory(self) -> tuple:
        return tuple(f for f in self.findings if not f.severity.refuses)

    @property
    def may_proceed(self) -> bool:
        return not self.blocking


class WorkflowPolicy:
    """Decides whether a workflow is sound enough to validate, compile or approve."""

    def __init__(self, *, require_compensation: bool = True) -> None:
        self._require_compensation = require_compensation

    @property
    def requires_compensation(self) -> bool:
        return self._require_compensation

    def evaluate(self, workflow, to_status: WorkflowStatus) -> PolicyReport:
        """Every finding, not just the first."""
        findings: list = []

        if not workflow.status.is_open:
            findings.append(
                PolicyFinding(
                    rule="W0-workflow-open",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"the workflow is {workflow.status.value}; "
                        + (
                            refusal_reason(workflow.status, to_status)
                            or "it may no longer be changed"
                        )
                    ),
                    subject=str(workflow.workflow_id),
                )
            )
            return PolicyReport(findings=tuple(findings))

        if not is_legal_transition(workflow.status, to_status):
            findings.append(
                PolicyFinding(
                    rule="W0-legal-transition",
                    severity=Severity.BLOCKING,
                    detail=(
                        refusal_reason(workflow.status, to_status)
                        or f"{workflow.status.value} may only move to: "
                        f"{', '.join(permitted_from(workflow.status))}"
                    ),
                    subject=to_status.value,
                )
            )

        if to_status is WorkflowStatus.SUPERSEDED:
            return PolicyReport(findings=tuple(findings))

        # W1 -- required elements.
        for element in workflow.missing_elements:
            findings.append(
                PolicyFinding(
                    rule="W1-required-elements",
                    severity=Severity.BLOCKING,
                    detail=f"no {element} recorded; the workflow cannot be run",
                    subject=element,
                )
            )

        # W2 -- the graph, reported rather than raised.
        graph = None
        try:
            graph = WorkflowGraph.of(workflow.nodes, workflow.edges)
            graph.assert_fully_reachable()
        except CyclicWorkflow as exc:
            findings.append(
                PolicyFinding(
                    rule="W2-acyclic",
                    severity=Severity.BLOCKING,
                    detail=str(exc),
                    subject=" -> ".join(exc.cycle),
                )
            )
        except DanglingEdge as exc:
            findings.append(
                PolicyFinding(
                    rule="W2-edges-resolve",
                    severity=Severity.BLOCKING,
                    detail=str(exc),
                    subject=exc.edge,
                )
            )
        except UnreachableNode as exc:
            findings.append(
                PolicyFinding(
                    rule="W2-fully-reachable",
                    severity=Severity.BLOCKING,
                    detail=str(exc),
                    subject=", ".join(exc.unreachable[:3]),
                )
            )

        for uncovered in workflow.uncovered_plan_tasks:
            findings.append(
                PolicyFinding(
                    rule="W2-plan-task-covered",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"plan task {uncovered!r} is run by no node; the workflow would "
                        "report success having never done it"
                    ),
                    subject=uncovered,
                )
            )

        for invented in workflow.invented_tasks:
            findings.append(
                PolicyFinding(
                    rule="W2-no-invented-work",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"a node runs {invented!r}, which the plan does not contain; "
                        "orchestration may reorder what was approved, never add to it"
                    ),
                    subject=invented,
                )
            )

        # W3 -- a mutating node has a way back.
        if self._require_compensation:
            for node_id in workflow.uncompensated_mutations:
                findings.append(
                    PolicyFinding(
                        rule="W3-mutation-compensated",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"node {node_id!r} changes state and nothing walks it back; "
                            "its failure mode is 'leave it half-applied and call "
                            "somebody' (Constitution P2)"
                        ),
                        subject=node_id,
                    )
                )

        # W4 -- an uncancellable mutation declares a timeout.
        for node in workflow.nodes:
            if node.mutates and not node.cancellable and node.timeout is None:
                findings.append(
                    PolicyFinding(
                        rule="W4-stoppable",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"node {node.node_id!r} mutates, cannot be cancelled, and "
                            "declares no timeout; a run that must be stopped has no "
                            "mechanism to stop it"
                        ),
                        subject=node.node_id,
                    )
                )

        # W5 -- un-waited-for parallel members must not mutate.
        by_id = {n.node_id: n for n in workflow.nodes}
        for group in workflow.parallel_groups:
            if group.join.waits_for_everything:
                continue
            for member in group.members:
                node = by_id.get(member)
                if node is not None and node.mutates:
                    findings.append(
                        PolicyFinding(
                            rule="W5-abandoned-mutation",
                            severity=Severity.BLOCKING,
                            detail=(
                                f"group {group.label!r} uses a {group.join.value!r} join "
                                f"and contains the mutating node {member!r}; a member "
                                "that is not waited for may still be applying changes "
                                "after the workflow has moved on"
                            ),
                            subject=member,
                        )
                    )

        # W9 -- the deadline is meetable.
        #
        # The aggregate refuses this too, and both are needed: the aggregate's
        # check is what stops an unmeetable deadline being assembled from
        # storage, and this one is what lets it be *reported alongside* the
        # unreachable node and the uncompensated mutation instead of raising
        # first and hiding them.
        if workflow.workflow_timeout is not None and workflow.nodes:
            needed, path = workflow.critical_path()
            budget = workflow.workflow_timeout.total_seconds
            if needed > budget:
                route = " -> ".join(path[:6]) + (" ..." if len(path) > 6 else "")
                findings.append(
                    PolicyFinding(
                        rule="W9-deadline-meetable",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"the workflow times out after {budget}s but its longest "
                            f"path needs {needed}s ({route}); it can never complete "
                            "within its own deadline, so the kill will always look "
                            "like a slow dependency"
                        ),
                        subject=str(needed),
                    )
                )

        # W6 -- somewhere to resume from.
        if len(workflow.nodes) > LONG_WORKFLOW_NODES and not workflow.resume_points:
            findings.append(
                PolicyFinding(
                    rule="W6-resumable",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"{len(workflow.nodes)} nodes and no resume point; a suspension "
                        "would restart from the beginning, over a world that has "
                        "already changed"
                    ),
                    subject=str(len(workflow.nodes)),
                )
            )

        # W7 -- a single point of failure.
        if graph is not None and len(graph) > 2:
            for node_id in graph.nodes:
                stranded = len(graph.descendants_of(node_id))
                if stranded > len(graph) * SPOF_RATIO:
                    findings.append(
                        PolicyFinding(
                            rule="W7-single-point-of-failure",
                            severity=Severity.ADVISORY,
                            detail=(
                                f"a failure at {node_id!r} would strand {stranded} of "
                                f"{len(graph)} nodes"
                            ),
                            subject=node_id,
                        )
                    )

        # W8 -- unused concurrency.
        if graph is not None and graph.widest_layer > 1 and not workflow.parallel_groups:
            findings.append(
                PolicyFinding(
                    rule="W8-unused-concurrency",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"the graph permits {graph.widest_layer} nodes at once but no "
                        "parallel group declares it; sometimes deliberate, worth "
                        "stating either way"
                    ),
                    subject=str(graph.widest_layer),
                )
            )

        return PolicyReport(findings=tuple(findings))


def default_policy() -> WorkflowPolicy:
    """The policy the Constitution defines."""
    return WorkflowPolicy(require_compensation=True)
