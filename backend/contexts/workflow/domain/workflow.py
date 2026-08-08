"""The Workflow aggregate: how an approved plan is orchestrated.

Planner said *what* and *in what order it must happen*. This says *when, under
what conditions, and what happens when it goes wrong*.

What only the whole workflow can check
----------------------------------------
The value objects enforce what is locally visible -- a branch has a default, a
parallel group has two members, a retry on a mutating node carries an idempotency
key. Seven checks need everything at once, and this is the only place everything
is visible:

1. **The graph is acyclic.** There is no loop construct; a cycle never completes.
2. **Every node is reachable.** An unreachable node never runs and the workflow
   reports success having skipped it.
3. **Every plan task is covered, and no node invents work.** Orchestration may
   reorder what was approved; it may not add to it or drop it.
4. **Every condition reads an upstream node.** Branching on an outcome that does
   not exist yet is a guess the executor has to invent a meaning for.
5. **Parallel members are genuinely independent.** Declaring independence does
   not create it.
6. **Compensations target real, mutating nodes.**
7. **The workflow's timeout is not shorter than its longest forward path.** A
   deadline nothing can meet is one that always fires and always looks like a
   slow dependency.

Compiled means the derived form is frozen
-------------------------------------------
Validation says the graph is well-formed. Compilation freezes what is *derived*
from it -- execution order, compensation order, the critical path -- and binds
the digest. Execution reads those rather than recomputing them, which is what
stops two executors disagreeing about a graph both consider valid.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Final, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contexts.workflow.domain.errors import (
    CompensationTargetInvalid,
    ConditionNotUpstream,
    DigestMismatch,
    DigestNotComputed,
    DuplicateNode,
    IllegalWorkflowTransition,
    IncompleteWorkflow,
    ParallelMembersDependent,
    ResumePointInsideGroup,
    TaskInvented,
    TaskNotCovered,
    TimeoutUnsatisfiable,
    UnknownNode,
    WorkflowApproved,
    WorkflowIsSuperseded,
)
from backend.contexts.workflow.domain.graph import WorkflowGraph
from backend.contexts.workflow.domain.identifiers import WorkflowId
from backend.contexts.workflow.domain.nodes import (
    NodeKind,
    WorkflowEdge,
    WorkflowNode,
    WorkflowTimeout,
)
from backend.contexts.workflow.domain.parallel import (
    ResumePoint,
    WorkflowCompensation,
    WorkflowParallelGroup,
)
from backend.contexts.workflow.domain.status import (
    WorkflowStatus,
    is_legal_transition,
    permitted_from,
)
from backend.platform.hashing import compute_digest, digests_match

__all__ = [
    "Workflow",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "REQUIRED_ELEMENTS",
]

ARTIFACT_KIND: Final[str] = "cortexprime.workflow.workflow"
CANONICAL_FORM_VERSION: Final[int] = 1

GOVERNED_FIELDS: Final[tuple] = (
    "workflow_id",
    "version",
    "plan_id",
    "plan_digest",
    "mission_id",
    "title",
    "plan_task_ids",
    "nodes",
    "edges",
    "parallel_groups",
    "compensations",
    "resume_points",
    "workflow_timeout",
    "supersedes",
)

REQUIRED_ELEMENTS: Final[tuple] = ("nodes", "edges", "workflow timeout")


@dataclass(frozen=True)
class Workflow(Contract):
    """One version of how an approved plan is orchestrated."""

    CONTRACT_NAME = "cortexprime.workflow.workflow_aggregate"

    workflow_id: WorkflowId
    plan_id: str
    plan_digest: str
    mission_id: str
    title: str

    plan_task_ids: frozenset = field(default_factory=frozenset)
    version: int = 1
    nodes: tuple = ()
    edges: tuple = ()
    parallel_groups: tuple = ()
    compensations: tuple = ()
    resume_points: tuple = ()
    workflow_timeout: Optional[WorkflowTimeout] = None

    status: WorkflowStatus = WorkflowStatus.DRAFT
    validated_at: Optional[datetime] = None
    compiled_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    digest: Optional[str] = None
    execution_order: tuple = ()
    compensation_order: tuple = ()
    supersedes: Optional[WorkflowId] = None
    superseded_by: Optional[WorkflowId] = None
    compiled_by: str = "workflow-runtime"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_id, WorkflowId):
            raise ContractViolation("workflow_id must be a WorkflowId")

        for label, value in (
            ("plan_id", self.plan_id),
            ("plan_digest", self.plan_digest),
            ("mission_id", self.mission_id),
            ("title", self.title),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a workflow that cannot say which "
                    "plan it orchestrates is not a workflow for anything"
                )

        if not isinstance(self.version, int) or self.version < 1:
            raise ContractViolation("version must be a positive integer starting at 1")

        for label, items, expected in (
            ("nodes", self.nodes, WorkflowNode),
            ("edges", self.edges, WorkflowEdge),
            ("parallel_groups", self.parallel_groups, WorkflowParallelGroup),
            ("compensations", self.compensations, WorkflowCompensation),
            ("resume_points", self.resume_points, ResumePoint),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        node_ids = [n.node_id for n in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            duplicate = next(n for n in node_ids if node_ids.count(n) > 1)
            raise DuplicateNode(duplicate)

        if not isinstance(self.plan_task_ids, (frozenset, set)):
            raise ContractViolation("plan_task_ids must be a set")
        object.__setattr__(self, "plan_task_ids", frozenset(self.plan_task_ids))

        if self.workflow_timeout is not None and not isinstance(
            self.workflow_timeout, WorkflowTimeout
        ):
            raise ContractViolation("workflow_timeout must be a WorkflowTimeout")

        # The graph is rebuilt rather than stored, so it is checked on every
        # construction -- including one assembled from storage.
        if self.nodes:
            WorkflowGraph.of(self.nodes, self.edges)

        if not isinstance(self.status, WorkflowStatus):
            raise ContractViolation("status must be a WorkflowStatus")

        # Validation, compilation and approval are statements about a sound graph.
        if self.status is not WorkflowStatus.DRAFT and self.status is not WorkflowStatus.SUPERSEDED:
            missing = self._missing_elements()
            if missing:
                raise IncompleteWorkflow(
                    workflow_id=str(self.workflow_id), missing=missing
                )
            self._assert_sound()

        if self.status is WorkflowStatus.VALIDATED and self.validated_at is None:
            raise ContractViolation("a validated workflow must record when")

        if self.status.has_frozen_order:
            if not self.digest:
                raise ContractViolation(
                    "a compiled workflow must carry the digest bound at compilation; "
                    "without it the graph execution runs cannot be shown to be the one "
                    "that was compiled"
                )
            if self.compiled_at is None:
                raise ContractViolation("a compiled workflow must record when")
            if not self.execution_order:
                raise ContractViolation(
                    "a compiled workflow must carry its frozen execution order; "
                    "recomputing it at run time lets two executors disagree about a "
                    "graph both consider valid"
                )
            if set(self.execution_order) != set(node_ids):
                raise ContractViolation(
                    "the frozen execution order does not cover every node"
                )

        if self.status is WorkflowStatus.APPROVED:
            if self.approved_at is None:
                raise ContractViolation("an approved workflow must record when")
            if not (self.approved_by and self.approved_by.strip()):
                raise ContractViolation(
                    "an approved workflow must name who approved it; an unattributed "
                    "authorisation has nobody accountable for it"
                )

        if self.status is WorkflowStatus.SUPERSEDED and self.superseded_by is None:
            raise ContractViolation("a superseded workflow must name its successor")

        for label in ("supersedes", "superseded_by"):
            value = getattr(self, label)
            if value is not None and not isinstance(value, WorkflowId):
                raise ContractViolation(f"{label} must be a WorkflowId")

        if self.version > 1 and self.supersedes is None:
            raise ContractViolation(
                f"version {self.version} must name the version it supersedes"
            )

        for label in ("created_at", "validated_at", "compiled_at", "approved_at"):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # ------------------------------------------------------------------
    # The seven whole-graph checks
    # ------------------------------------------------------------------

    def _missing_elements(self) -> tuple:
        missing: list = []
        if not self.nodes:
            missing.append("nodes")
        if len(self.nodes) > 1 and not self.edges:
            missing.append("edges")
        if self.workflow_timeout is None:
            missing.append("workflow timeout")
        return tuple(missing)

    def _assert_sound(self) -> None:
        graph = self.graph
        known = {n.node_id for n in self.nodes}

        # 2 -- every node reachable.
        graph.assert_fully_reachable()

        # 3 -- the plan's work, all of it and only it.
        covered = {n.plan_task_id for n in self.nodes if n.plan_task_id}
        uncovered = sorted(self.plan_task_ids - covered)
        if uncovered:
            raise TaskNotCovered(uncovered)
        invented = sorted(covered - self.plan_task_ids)
        if invented:
            raise TaskInvented(invented)

        # 4 -- conditions read upstream nodes.
        for node in self.nodes:
            ancestors = graph.ancestors_of(node.node_id)
            for arm in node.arms:
                source = arm.condition.source_node
                if source is not None and source not in ancestors and source != node.node_id:
                    raise ConditionNotUpstream(node_id=node.node_id, source=source)
        for edge in self.edges:
            source = edge.condition.source_node
            if source is None:
                continue
            ancestors = graph.ancestors_of(edge.from_node)
            if source not in ancestors and source != edge.from_node:
                raise ConditionNotUpstream(node_id=edge.from_node, source=source)

        # 5 -- parallel members are independent, and exist.
        for group in self.parallel_groups:
            for member in group.members:
                if member not in known:
                    raise UnknownNode(
                        workflow_id=str(self.workflow_id), node_id=member
                    )
            ordered = sorted(group.members)
            for index, left in enumerate(ordered):
                for right in ordered[index + 1 :]:
                    if not graph.are_independent(left, right):
                        dependent, depends_on = (
                            (left, right)
                            if right in graph.ancestors_of(left)
                            else (right, left)
                        )
                        raise ParallelMembersDependent(
                            group=str(group.group_id),
                            dependent=dependent,
                            depends_on=depends_on,
                        )

        # 6 -- compensations target real, mutating nodes.
        by_id = {n.node_id: n for n in self.nodes}
        for compensation in self.compensations:
            for label, node_id in (
                ("compensates", compensation.compensates),
                ("performed_by", compensation.performed_by),
            ):
                if node_id not in known:
                    raise CompensationTargetInvalid(
                        node_id=compensation.performed_by,
                        reason=f"{label} names {node_id!r}, which the workflow does not contain",
                    )
            target = by_id[compensation.compensates]
            if not target.mutates:
                raise CompensationTargetInvalid(
                    node_id=compensation.performed_by,
                    reason=(
                        f"{target.node_id!r} only reads, so there is nothing to walk back"
                    ),
                )

        # 7 -- the deadline is meetable.
        if self.workflow_timeout is not None:
            weights = {n.node_id: n.worst_case_seconds for n in self.nodes}
            needed, path = graph.critical_path(weights)
            if needed > self.workflow_timeout.total_seconds:
                raise TimeoutUnsatisfiable(
                    workflow_timeout=self.workflow_timeout.total_seconds,
                    critical_path=needed,
                    path=path,
                )

        # Resume points sit outside fan-outs.
        for point in self.resume_points:
            if point.node_id not in known:
                raise UnknownNode(
                    workflow_id=str(self.workflow_id), node_id=point.node_id
                )
            for group in self.parallel_groups:
                if point.node_id in group:
                    raise ResumePointInsideGroup(
                        node_id=point.node_id, group=str(group.group_id)
                    )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def graph(self) -> WorkflowGraph:
        return WorkflowGraph.of(self.nodes, self.edges)

    @property
    def missing_elements(self) -> tuple:
        return self._missing_elements()

    @property
    def is_open(self) -> bool:
        return self.status.is_open

    @property
    def is_executable(self) -> bool:
        return self.status.is_executable

    @property
    def task_nodes(self) -> tuple:
        return tuple(n for n in self.nodes if n.kind is NodeKind.TASK)

    @property
    def mutating_nodes(self) -> tuple:
        return tuple(n for n in self.nodes if n.mutates)

    @property
    def uncompensated_mutations(self) -> tuple:
        """Mutating nodes nothing walks back. Policy reports these.

        Compensation nodes are excluded, and the exclusion is the point rather
        than an oversight: a compensation *is* the walk-back. Demanding a
        compensation for it would be infinite regress, and the honest answer to
        "what if the walk-back fails" is an operator, not another node.
        """
        compensated = {c.compensates for c in self.compensations}
        return tuple(
            n.node_id
            for n in self.nodes
            if n.mutates
            and n.kind is not NodeKind.COMPENSATION
            and n.node_id not in compensated
        )

    @property
    def uncovered_plan_tasks(self) -> tuple:
        covered = {n.plan_task_id for n in self.nodes if n.plan_task_id}
        return tuple(sorted(self.plan_task_ids - covered))

    @property
    def invented_tasks(self) -> tuple:
        covered = {n.plan_task_id for n in self.nodes if n.plan_task_id}
        return tuple(sorted(covered - self.plan_task_ids))

    def node(self, node_id: str) -> Optional[WorkflowNode]:
        for candidate in self.nodes:
            if candidate.node_id == node_id:
                return candidate
        return None

    def group(self, group_id: str) -> Optional[WorkflowParallelGroup]:
        for candidate in self.parallel_groups:
            if str(candidate.group_id) == group_id:
                return candidate
        return None

    def derived_execution_order(self) -> tuple:
        return self.graph.topological_order() if self.nodes else ()

    def derived_compensation_order(self) -> tuple:
        """Compensations in reverse execution order.

        Walking back in the order things were done would undo the earliest change
        first, while the later ones still depend on it. Reverse is the only order
        that is correct, so it is derived rather than declared -- a declared one
        can be wrong.
        """
        if not self.compensations:
            return ()
        order = {node: index for index, node in enumerate(self.derived_execution_order())}
        return tuple(
            c.performed_by
            for c in sorted(
                self.compensations,
                key=lambda c: -order.get(c.compensates, 0),
            )
        )

    def critical_path(self) -> tuple:
        weights = {n.node_id: n.worst_case_seconds for n in self.nodes}
        return self.graph.critical_path(weights)

    def permitted_transitions(self) -> tuple:
        return permitted_from(self.status)

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        return {
            "__artifact__": ARTIFACT_KIND,
            "__canonical_form__": CANONICAL_FORM_VERSION,
            "workflow_id": str(self.workflow_id),
            "version": self.version,
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "mission_id": self.mission_id,
            "title": self.title,
            "plan_task_ids": sorted(self.plan_task_ids),
            "nodes": sorted(
                (
                    {
                        "node_id": n.node_id,
                        "kind": n.kind.value,
                        "purpose": n.purpose,
                        "plan_task_id": n.plan_task_id,
                        "side_effect": n.side_effect.value,
                        "compensates": n.compensates,
                        "retry": {
                            "max_attempts": n.retry.max_attempts,
                            "backoff": n.retry.backoff.value,
                            "initial_delay_seconds": n.retry.initial_delay_seconds,
                            "idempotency_key": n.retry.idempotency_key,
                        },
                        "timeout": (
                            {
                                "seconds": n.timeout.seconds,
                                "on_timeout": n.timeout.on_timeout,
                                "grace_seconds": n.timeout.grace_seconds,
                            }
                            if n.timeout
                            else None
                        ),
                        "arms": sorted(
                            (
                                {"to_node": a.to_node, "condition": str(a.condition)}
                                for a in n.arms
                            ),
                            key=lambda item: item["to_node"],
                        ),
                        "cancellable": n.cancellable,
                        "execution_key": n.execution_key,
                    }
                    for n in self.nodes
                ),
                key=lambda item: item["node_id"],
            ),
            "edges": sorted(
                (
                    {
                        "from": e.from_node,
                        "to": e.to_node,
                        "kind": e.kind.value,
                        "condition": str(e.condition),
                    }
                    for e in self.edges
                ),
                key=lambda item: (item["from"], item["to"], item["kind"]),
            ),
            "parallel_groups": sorted(
                (
                    {
                        "group_id": str(g.group_id),
                        "label": g.label,
                        "members": sorted(g.members),
                        "join": g.join.value,
                        "quorum": g.quorum,
                        "max_concurrency": g.max_concurrency,
                    }
                    for g in self.parallel_groups
                ),
                key=lambda item: item["group_id"],
            ),
            "compensations": sorted(
                (
                    {
                        "compensates": c.compensates,
                        "performed_by": c.performed_by,
                        "trigger": c.trigger,
                    }
                    for c in self.compensations
                ),
                key=lambda item: item["performed_by"],
            ),
            "resume_points": sorted(p.node_id for p in self.resume_points),
            "workflow_timeout": (
                {
                    "seconds": self.workflow_timeout.seconds,
                    "on_timeout": self.workflow_timeout.on_timeout,
                    "grace_seconds": self.workflow_timeout.grace_seconds,
                }
                if self.workflow_timeout
                else None
            ),
            "supersedes": str(self.supersedes) if self.supersedes else None,
        }

    def compute_digest(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def verify_digest(self) -> None:
        if not self.digest:
            raise DigestNotComputed(str(self.workflow_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                workflow_id=str(self.workflow_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _require_open(self, operation: str) -> None:
        if self.status is WorkflowStatus.SUPERSEDED:
            raise WorkflowIsSuperseded(
                workflow_id=str(self.workflow_id), successor=str(self.superseded_by)
            )
        if not self.status.is_open:
            raise WorkflowApproved(workflow_id=str(self.workflow_id), operation=operation)

    def _edited(self, **changes: Any) -> "Workflow":
        """Apply a change, returning a validated or compiled workflow to draft.

        The demotion happens in the same construction as the change, never a
        second one -- removing a node from a compiled workflow would otherwise
        build an intermediate that is compiled and incoherent, which its own
        invariant refuses, correctly.
        """
        if self.status in (WorkflowStatus.VALIDATED, WorkflowStatus.COMPILED):
            return replace(
                self,
                status=WorkflowStatus.DRAFT,
                validated_at=None,
                compiled_at=None,
                digest=None,
                execution_order=(),
                compensation_order=(),
                **changes,
            )
        return replace(self, **changes)

    # ------------------------------------------------------------------
    # Building the graph
    # ------------------------------------------------------------------

    def add_node(self, node: WorkflowNode) -> "Workflow":
        self._require_open("adding a node")
        if not isinstance(node, WorkflowNode):
            raise ContractViolation("node must be a WorkflowNode")
        if self.node(node.node_id) is not None:
            raise DuplicateNode(node.node_id)
        return self._edited(nodes=self.nodes + (node,))

    def remove_node(self, node_id: str) -> "Workflow":
        self._require_open("removing a node")
        if self.node(node_id) is None:
            raise UnknownNode(workflow_id=str(self.workflow_id), node_id=node_id)
        return self._edited(
            nodes=tuple(n for n in self.nodes if n.node_id != node_id),
            edges=tuple(
                e for e in self.edges if node_id not in (e.from_node, e.to_node)
            ),
        )

    def add_edge(self, edge: WorkflowEdge) -> "Workflow":
        """Connect two nodes. The graph is re-checked, so a cycle is refused here."""
        self._require_open("adding an edge")
        if not isinstance(edge, WorkflowEdge):
            raise ContractViolation("edge must be a WorkflowEdge")
        for node_id in (edge.from_node, edge.to_node):
            if self.node(node_id) is None:
                raise UnknownNode(workflow_id=str(self.workflow_id), node_id=node_id)
        if any(
            e.from_node == edge.from_node
            and e.to_node == edge.to_node
            and e.kind is edge.kind
            for e in self.edges
        ):
            return self
        return self._edited(edges=self.edges + (edge,))

    def add_parallel_group(self, group: WorkflowParallelGroup) -> "Workflow":
        """Declare a fan-out. Independence is checked against the graph."""
        self._require_open("adding a parallel group")
        if not isinstance(group, WorkflowParallelGroup):
            raise ContractViolation("group must be a WorkflowParallelGroup")
        return self._edited(parallel_groups=self.parallel_groups + (group,))

    def add_compensation(self, compensation: WorkflowCompensation) -> "Workflow":
        self._require_open("adding a compensation")
        if not isinstance(compensation, WorkflowCompensation):
            raise ContractViolation("compensation must be a WorkflowCompensation")
        return self._edited(compensations=self.compensations + (compensation,))

    def add_resume_point(self, point: ResumePoint) -> "Workflow":
        self._require_open("adding a resume point")
        if not isinstance(point, ResumePoint):
            raise ContractViolation("point must be a ResumePoint")
        if any(p.node_id == point.node_id for p in self.resume_points):
            return self
        return self._edited(resume_points=self.resume_points + (point,))

    def set_timeout(self, timeout: WorkflowTimeout) -> "Workflow":
        self._require_open("setting the workflow timeout")
        if not isinstance(timeout, WorkflowTimeout):
            raise ContractViolation("timeout must be a WorkflowTimeout")
        return self._edited(workflow_timeout=timeout)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _transition(self, to_status: WorkflowStatus, **changes: Any) -> "Workflow":
        if not is_legal_transition(self.status, to_status):
            raise IllegalWorkflowTransition(
                workflow_id=str(self.workflow_id),
                source=self.status.value,
                target=to_status.value,
                permitted=permitted_from(self.status),
            )
        return replace(self, status=to_status, **changes)

    def validate(self) -> "Workflow":
        """Assert the graph is well-formed."""
        self._require_open("validating")
        missing = self._missing_elements()
        if missing:
            raise IncompleteWorkflow(workflow_id=str(self.workflow_id), missing=missing)
        self._assert_sound()
        return self._transition(
            WorkflowStatus.VALIDATED, validated_at=datetime.now(timezone.utc)
        )

    def compile(self) -> "Workflow":
        """Freeze the derived form and bind the digest.

        Execution reads the frozen order rather than recomputing it, so two
        executors cannot disagree about a graph both consider valid.
        """
        self._require_open("compiling")
        if not is_legal_transition(self.status, WorkflowStatus.COMPILED):
            raise IllegalWorkflowTransition(
                workflow_id=str(self.workflow_id),
                source=self.status.value,
                target=WorkflowStatus.COMPILED.value,
                permitted=permitted_from(self.status),
            )
        self._assert_sound()

        execution_order = self.derived_execution_order()
        compensation_order = self.derived_compensation_order()

        # The digest covers the compiled content. No governed field changes at
        # compilation -- the derived orders are not governed, because they are
        # recomputable from what is -- so the payload is already what the sealed
        # workflow reports. A test asserts ``verify_digest`` passes.
        digest = compute_digest(self.digest_payload()).value

        return self._transition(
            WorkflowStatus.COMPILED,
            compiled_at=datetime.now(timezone.utc),
            digest=digest,
            execution_order=execution_order,
            compensation_order=compensation_order,
        )

    def approve(self, approved_by: str) -> "Workflow":
        self._require_open("approving")
        if not approved_by or not approved_by.strip():
            raise ContractViolation("an approval must name who gave it")
        if not is_legal_transition(self.status, WorkflowStatus.APPROVED):
            raise IllegalWorkflowTransition(
                workflow_id=str(self.workflow_id),
                source=self.status.value,
                target=WorkflowStatus.APPROVED.value,
                permitted=permitted_from(self.status),
            )
        return self._transition(
            WorkflowStatus.APPROVED,
            approved_at=datetime.now(timezone.utc),
            approved_by=approved_by.strip(),
        )

    def supersede(self, successor: WorkflowId) -> "Workflow":
        if not isinstance(successor, WorkflowId):
            raise ContractViolation("successor must be a WorkflowId")
        if successor == self.workflow_id:
            raise ContractViolation("a workflow cannot supersede itself")
        if self.superseded_by is not None:
            raise ContractViolation(
                f"workflow {self.workflow_id} is already superseded by "
                f"{self.superseded_by}"
            )
        return self._transition(WorkflowStatus.SUPERSEDED, superseded_by=successor)

    def revise(self) -> "Workflow":
        """Open the next version, carrying the graph forward."""
        return Workflow(
            workflow_id=WorkflowId.new(),
            plan_id=self.plan_id,
            plan_digest=self.plan_digest,
            mission_id=self.mission_id,
            title=self.title,
            plan_task_ids=self.plan_task_ids,
            version=self.version + 1,
            nodes=self.nodes,
            edges=self.edges,
            parallel_groups=self.parallel_groups,
            compensations=self.compensations,
            resume_points=self.resume_points,
            workflow_timeout=self.workflow_timeout,
            supersedes=self.workflow_id,
            compiled_by=self.compiled_by,
        )
