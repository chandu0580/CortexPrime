"""Composition root for the Mission Control Plane: Workflow -> Execution.

**This is the only module that imports both the Workflow and Execution bounded
contexts**, which is why it lives at the API layer rather than inside either of
them. Same reasoning as ``engineering_composition``: putting the join inside
Workflow would make Workflow depend on Execution, and putting it inside
Execution would reverse the coupling and be no better. Layer 3 may import
layer 2, so the composition root is the one place the join is both legal and
correct.

Keeping it in one small named module means the coupling is greppable. Anyone
asking "how does an approved workflow become a run?" reads this file and nothing
else.

What this closes
-----------------
Before this module, ``StartExecution`` was only ever built by the execution route
from a caller-supplied ``workflow_id`` and ``workflow_digest``. Any string was
accepted. A run could be started from a workflow that was never approved, never
compiled, or did not exist at all -- and the digest that is supposed to bind the
run to the exact graph it executes was whatever the caller typed.

The launcher below is the only sanctioned way to turn a workflow into a run:
the workflow is loaded, its approval is checked, its digest is verified against
its own canonical payload, and the digest handed to Execution is the workflow's
own -- never the caller's.

What this deliberately does not do
------------------------------------
It does not decide *which worker* runs a node. Workflow describes how work should
execute; it does not name a runtime capability, and pushing ``worker_kind`` back
into ``WorkflowNode`` would move an execution concern into the planning plane.
Capability routing is Phase 3.

So the worker kind arrives through :class:`WorkerKindResolver` -- a port, with no
implementation here beyond an explicit caller-supplied mapping that refuses to
guess. When the capability registry exists it implements this interface and
nothing else in this file changes.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contexts.execution import (
    ExecutionService,
    StartExecution,
)
from backend.contexts.workflow import (
    GetWorkflow,
    WorkflowService,
)

__all__ = [
    "WorkerKindResolver",
    "ExplicitWorkerKinds",
    "WorkflowNotExecutable",
    "UnresolvedWorkerKind",
    "WorkflowExecutionLauncher",
]

# Edges that mean "this must succeed before that may start". A failure edge is a
# route taken when something went wrong, not a dependency to wait on, and
# treating one as a dependency would leave a node waiting for a failure that a
# healthy run will never produce.
_SEQUENCE_EDGE = "normal"

# Compensation nodes are deliberately not projected into the run. Execution
# requires every node it was given to finish before a run may complete, and a
# compensation node is reachable only when something failed -- so projecting one
# would leave every *successful* run permanently outstanding, unable to complete
# and unable to fail. Execution walks back a change by calling ``compensate`` on
# the mutated node itself. Dispatching the compensating *action* is Phase 3.
_COMPENSATION_KIND = "compensation"


class WorkflowNotExecutable(ContractViolation):
    """The workflow may not be run: absent, unapproved, or not itself."""


class UnresolvedWorkerKind(ContractViolation):
    """Nothing said which kind of worker runs a node, and guessing is worse."""

    def __init__(self, node_id: str) -> None:
        super().__init__(
            f"no worker kind was resolved for node {node_id!r}; Workflow describes "
            "how work should execute but does not name a runtime capability, and "
            "defaulting one here would hand real work to whatever happened to be "
            "first in an enum"
        )
        self.node_id = node_id


@runtime_checkable
class WorkerKindResolver(Protocol):
    """Decides which kind of worker runs a node.

    The seam where Phase 3's capability routing plugs in. Deliberately narrow:
    it answers one question and holds no state that Execution can reach.
    """

    def kind_for(self, workflow_id: str, node: Any) -> Optional[str]: ...


class ExplicitWorkerKinds:
    """A resolver that only knows what it was told.

    Not a registry and not a router -- both are Phase 3. This exists so a caller
    that already knows how its nodes should run can say so, and so that a caller
    that does not gets a refusal rather than a default.
    """

    def __init__(self, kinds: Mapping[str, str]) -> None:
        self._kinds = dict(kinds)

    def kind_for(self, workflow_id: str, node: Any) -> Optional[str]:
        return self._kinds.get(getattr(node, "node_id", None))


class WorkflowExecutionLauncher:
    """Turns an approved workflow into a started run. The only sanctioned path."""

    def __init__(
        self,
        *,
        workflows: WorkflowService,
        executions: ExecutionService,
    ) -> None:
        self._workflows = workflows
        self._executions = executions

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def executable_workflow(self, context: Any, mission_id: str):
        """The approved workflow for a mission, or a refusal saying why not."""
        found = self._workflows.executable_for(context, mission_id)
        if found is None:
            raise WorkflowNotExecutable(
                f"mission {mission_id!r} has no approved workflow; a run started from "
                "an unapproved graph would execute work nobody signed off"
            )
        return found

    def _approved(self, context: Any, workflow_id: str):
        workflow = self._workflows.get(context, GetWorkflow(workflow_id=workflow_id))
        if not workflow.is_executable:
            raise WorkflowNotExecutable(
                f"workflow {workflow_id!r} is {workflow.status.value}, not approved; "
                "execution consumes an approved workflow and does not approve one"
            )
        return workflow

    # ------------------------------------------------------------------
    # Projection
    # ------------------------------------------------------------------

    @staticmethod
    def project(workflow, resolver: WorkerKindResolver) -> tuple:
        """The node set Execution runs, derived from the compiled graph.

        Derived rather than accepted: the caller does not get to say what the run
        contains. That is the whole point of binding the run to a digest.
        """
        runnable = [n for n in workflow.nodes if n.kind.value != _COMPENSATION_KIND]
        if not runnable:
            raise WorkflowNotExecutable(
                f"workflow {str(workflow.workflow_id)!r} has no runnable nodes; a run "
                "over none of them would complete instantly having done nothing"
            )

        known = {node.node_id for node in runnable}
        dependencies: dict = {node.node_id: [] for node in runnable}
        for edge in workflow.edges:
            if edge.kind.value != _SEQUENCE_EDGE:
                continue
            if edge.from_node in known and edge.to_node in known:
                dependencies[edge.to_node].append(edge.from_node)

        projected: list = []
        for node in runnable:
            kind = resolver.kind_for(str(workflow.workflow_id), node)
            if not kind:
                raise UnresolvedWorkerKind(node.node_id)
            retry = node.retry
            projected.append(
                {
                    "node_id": node.node_id,
                    "worker_kind": kind,
                    "depends_on": sorted(dependencies[node.node_id]),
                    "side_effect": node.side_effect.value,
                    "max_attempts": getattr(retry, "max_attempts", 1) if retry else 1,
                    "timeout_seconds": node.timeout.seconds if node.timeout else None,
                    "idempotency_key": (
                        getattr(retry, "idempotency_key", None) if retry else None
                    ),
                    "compensates": node.compensates,
                    "cancellable": node.cancellable,
                    "execution_key": node.execution_key,
                }
            )
        return tuple(projected)

    # ------------------------------------------------------------------
    # Launch
    # ------------------------------------------------------------------

    def launch(
        self,
        context: Any,
        *,
        mission_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        resolver: WorkerKindResolver,
        attempt: int = 1,
        requested_by: str = "mission-runtime",
    ):
        """Start a run from an approved workflow.

        Give a ``workflow_id`` to run a named workflow, or a ``mission_id`` to run
        whichever approved workflow that mission currently has.
        """
        if bool(mission_id) == bool(workflow_id):
            raise ContractViolation(
                "name exactly one of mission_id or workflow_id; naming both leaves it "
                "ambiguous which graph the run is of, and naming neither leaves nothing "
                "to run"
            )

        workflow = (
            self._approved(context, workflow_id)
            if workflow_id
            else self.executable_workflow(context, mission_id)
        )

        # The workflow is the one that was approved, not one edited since. The
        # digest is recomputed against the canonical payload and compared with
        # the recorded one; a mismatch means the stored artifact changed after
        # approval, and running it would execute work nobody signed off.
        workflow.verify_digest()

        return self._executions.start(
            context,
            StartExecution(
                workflow_id=str(workflow.workflow_id),
                # The workflow's own digest -- never a caller-supplied string.
                workflow_digest=workflow.digest,
                mission_id=workflow.mission_id,
                nodes=self.project(workflow, resolver),
                attempt=attempt,
                requested_by=requested_by,
            ),
        )
