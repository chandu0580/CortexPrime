"""The Workflow bounded context.

Planner said *what* and *in what order it must happen*. This says **when, under
what conditions, and what happens when it goes wrong** -- branches, fan-outs,
retries, compensations, timeouts, cancellation and resume.

Both are DAGs and they are not the same DAG. A plan dependency is a fact about
the work; a workflow edge is a decision about orchestration.

What this context refuses to be
--------------------------------
**Workflow never executes.** No run state, no node outcomes, no attempts. Every
field describes a graph that has not been run.

**Workflow never invokes tools.** It declares an ``execution_key`` and a
``SideEffectClass``; the module those come from says of itself that they are
declarations, not invocations.

**Workflow never modifies plans.** It holds ``plan_id`` and ``plan_digest`` as
opaque strings plus the plan's task ids, and has no import path to the Planner.

Seven checks need the whole graph
-----------------------------------
The graph is acyclic; every node is reachable; every plan task is covered and no
node invents work; every condition reads an upstream node; parallel members are
genuinely independent; compensations target real mutating nodes; and the
workflow's own timeout is not shorter than its longest forward path.

    domain/          pure -- nodes, edges, groups, the graph, the aggregate
    application/     commands, queries, the service
    infrastructure/  repository, record mapping

This context imports ``contracts/`` and ``platform/`` and nothing else.
See ADR-028.
"""

from backend.contexts.workflow.application import (
    AddBranch,
    AddCompensation,
    AddEdge,
    AddNode,
    AddParallelGroup,
    AddResumePoint,
    ApproveWorkflow as ApproveWorkflowCommand,
    CommandResult,
    CompileGraph,
    CompileWorkflow,
    GetGraph,
    GetWorkflow,
    ListWorkflows,
    RemoveNode,
    ReviseWorkflow,
    SetWorkflowTimeout,
    ValidateWorkflow,
    WorkflowService,
)
from backend.contexts.workflow.domain import *  # noqa: F401,F403
from backend.contexts.workflow.domain import __all__ as _domain_all
from backend.contexts.workflow.infrastructure import (
    InMemoryWorkflowRepository,
    WorkflowRepository,
)

__all__ = list(_domain_all) + [
    "WorkflowService",
    "CommandResult",
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
    "ApproveWorkflowCommand",
    "ReviseWorkflow",
    "GetWorkflow",
    "GetGraph",
    "ListWorkflows",
    "WorkflowRepository",
    "InMemoryWorkflowRepository",
]
