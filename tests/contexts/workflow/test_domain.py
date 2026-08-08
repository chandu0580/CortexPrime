"""The Workflow aggregate: composition, the seven whole-graph checks, compilation.

The rule this file exists to pin hardest is **plan coverage**: a workflow that
runs some of the plan reports success having never done the rest, and a workflow
that runs work the plan does not contain has added something nobody approved.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contexts.workflow import (
    ARTIFACT_KIND,
    CompensationTargetInvalid,
    ConditionNotUpstream,
    CyclicWorkflow,
    DigestMismatch,
    DigestNotComputed,
    DuplicateNode,
    EdgeKind,
    GOVERNED_FIELDS,
    IllegalWorkflowTransition,
    IncompleteWorkflow,
    JoinPolicy,
    ParallelMembersDependent,
    REQUIRED_ELEMENTS,
    ResumePointInsideGroup,
    TaskInvented,
    TaskNotCovered,
    TimeoutUnsatisfiable,
    UnknownNode,
    UnreachableNode,
    Workflow,
    WorkflowApprovedError,
    WorkflowCondition,
    WorkflowId,
    WorkflowIsSuperseded,
    WorkflowStatus,
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


def _empty(**overrides) -> Workflow:
    fields = dict(
        plan_id="P-1",
        plan_digest="9f2c1a7b",
        mission_id="M-1",
        title="Rightsize instances",
        plan_task_ids=("audit", "resize"),
    )
    fields.update(overrides)
    return compile_from_plan(**fields)


def _wired(**overrides) -> Workflow:
    """A sound workflow: audit -> resize, with a compensation on failure."""
    workflow = _empty(**overrides)
    workflow = workflow.add_node(
        task_node("audit", "list utilisation", "audit", node_timeout=timeout(60))
    )
    workflow = workflow.add_node(
        task_node(
            "resize",
            "resize the over-provisioned ones",
            "resize",
            side_effect=SideEffectClass.REVERSIBLE_WRITE,
            retry_policy=retry(2, idempotency_key="resize-key"),
            node_timeout=timeout(120),
        )
    )
    workflow = workflow.add_node(
        compensation_node("restore", "restore sizes", "resize", node_timeout=timeout(60))
    )
    workflow = workflow.add_edge(edge("audit", "resize"))
    workflow = workflow.add_edge(edge("resize", "restore", kind=EdgeKind.ON_FAILURE))
    workflow = workflow.add_compensation(compensation("resize", "restore"))
    return workflow.set_timeout(timeout(900))


# ----------------------------------------------------------------------
# Creation and binding
# ----------------------------------------------------------------------


def test_a_workflow_names_the_plan_it_orchestrates() -> None:
    workflow = _empty()
    assert workflow.plan_id == "P-1"
    assert workflow.plan_digest == "9f2c1a7b"
    assert workflow.version == 1
    assert workflow.status is WorkflowStatus.DRAFT


@pytest.mark.parametrize("blank", ["plan_id", "plan_digest", "mission_id", "title"])
def test_a_workflow_missing_a_binding_is_refused(blank: str) -> None:
    with pytest.raises(ContractViolation):
        _empty(**{blank: "  "})


def test_a_fresh_workflow_is_missing_what_it_needs() -> None:
    missing = set(_empty().missing_elements)
    assert missing == {"nodes", "workflow timeout"}
    assert missing <= set(REQUIRED_ELEMENTS)


# ----------------------------------------------------------------------
# Plan coverage -- the rule that matters most
# ----------------------------------------------------------------------


def test_a_plan_task_no_node_runs_is_refused() -> None:
    """The workflow would report success having never done it."""
    workflow = _empty().add_node(
        task_node("audit", "list", "audit", node_timeout=timeout(10))
    ).set_timeout(timeout(60))
    with pytest.raises(TaskNotCovered) as caught:
        workflow.validate()
    assert caught.value.uncovered == ("resize",)


def test_a_node_running_work_the_plan_lacks_is_refused() -> None:
    """Orchestration may reorder what was approved, never add to it."""
    workflow = _wired().add_node(
        task_node("extra", "something nobody planned", "not-in-plan")
    )
    workflow = workflow.add_edge(edge("resize", "extra"))
    with pytest.raises(TaskInvented) as caught:
        workflow.validate()
    assert caught.value.invented == ("not-in-plan",)


def test_coverage_is_reported_without_raising() -> None:
    workflow = _empty().add_node(task_node("audit", "list", "audit"))
    assert workflow.uncovered_plan_tasks == ("resize",)
    assert workflow.invented_tasks == ()


# ----------------------------------------------------------------------
# The graph, through the aggregate
# ----------------------------------------------------------------------


def test_an_edge_that_would_cycle_is_refused() -> None:
    workflow = _wired()
    with pytest.raises(CyclicWorkflow):
        workflow.add_edge(edge("resize", "audit"))


def test_a_duplicate_node_id_is_refused() -> None:
    workflow = _wired()
    with pytest.raises(DuplicateNode):
        workflow.add_node(task_node("audit", "again", "audit"))


def test_an_edge_to_an_unknown_node_is_refused() -> None:
    workflow = _wired()
    with pytest.raises(UnknownNode):
        workflow.add_edge(edge("audit", "ghost"))


def test_a_disconnected_node_is_refused_at_validation() -> None:
    workflow = _wired().add_node(
        task_node("stray", "unwired", "audit")
    )
    with pytest.raises(UnreachableNode):
        workflow.validate()


def test_adding_the_same_edge_twice_is_a_no_op() -> None:
    workflow = _wired()
    assert workflow.add_edge(edge("audit", "resize")) is workflow


def test_the_graph_is_rebuilt_on_every_construction() -> None:
    """So a stored workflow edited into a cycle refuses to load."""
    workflow = _wired()
    with pytest.raises(CyclicWorkflow):
        dataclasses.replace(workflow, edges=workflow.edges + (edge("resize", "audit"),))


# ----------------------------------------------------------------------
# Conditions read upstream
# ----------------------------------------------------------------------


def test_a_condition_reading_a_downstream_node_is_refused() -> None:
    """The outcome will not exist when the condition is evaluated."""
    workflow = _wired().add_edge(
        edge(
            "audit",
            "restore",
            condition=WorkflowCondition.on_success("resize"),
        )
    )
    with pytest.raises(ConditionNotUpstream) as caught:
        workflow.validate()
    assert caught.value.source == "resize"


def test_a_condition_reading_an_upstream_node_is_accepted() -> None:
    workflow = _wired().add_edge(
        edge(
            "resize",
            "restore",
            kind=EdgeKind.COMPENSATING,
            condition=WorkflowCondition.on_failure("audit"),
        )
    )
    assert workflow.validate().status is WorkflowStatus.VALIDATED


# ----------------------------------------------------------------------
# Parallel independence
# ----------------------------------------------------------------------


def test_a_parallel_group_of_dependent_nodes_is_refused() -> None:
    """Running them concurrently is a deadlock or a race, not a speed-up."""
    workflow = _wired().add_parallel_group(parallel_group("g", ["audit", "resize"]))
    with pytest.raises(ParallelMembersDependent) as caught:
        workflow.validate()
    assert caught.value.dependent == "resize"
    assert caught.value.depends_on == "audit"


def test_a_parallel_group_of_independent_nodes_is_accepted() -> None:
    workflow = _empty(plan_task_ids=("a", "b", "c"))
    workflow = workflow.add_node(task_node("start", "kick off", "a", node_timeout=timeout(5)))
    workflow = workflow.add_node(task_node("left", "one branch", "b", node_timeout=timeout(5)))
    workflow = workflow.add_node(task_node("right", "other branch", "c", node_timeout=timeout(5)))
    workflow = workflow.add_edge(edge("start", "left"))
    workflow = workflow.add_edge(edge("start", "right"))
    workflow = workflow.add_parallel_group(parallel_group("fan", ["left", "right"]))
    workflow = workflow.set_timeout(timeout(60))
    assert workflow.validate().status is WorkflowStatus.VALIDATED


def test_a_parallel_group_naming_an_unknown_node_is_refused() -> None:
    workflow = _wired().add_parallel_group(parallel_group("g", ["audit", "ghost"]))
    with pytest.raises(UnknownNode):
        workflow.validate()


# ----------------------------------------------------------------------
# Compensation
# ----------------------------------------------------------------------


def test_a_compensation_for_a_read_only_node_is_refused() -> None:
    """There is nothing to walk back."""
    workflow = _wired().add_compensation(compensation("audit", "restore"))
    with pytest.raises(CompensationTargetInvalid):
        workflow.validate()


def test_a_compensation_naming_an_unknown_node_is_refused() -> None:
    workflow = _wired().add_compensation(compensation("ghost", "restore"))
    with pytest.raises(CompensationTargetInvalid):
        workflow.validate()


def test_the_compensation_order_is_the_reverse_of_execution() -> None:
    """Undoing the earliest change first, while later ones still depend on it,
    is the one order that is certainly wrong."""
    compiled = _wired().validate().compile()
    assert compiled.execution_order == ("audit", "resize", "restore")
    assert compiled.compensation_order == ("restore",)


def test_a_compensation_node_needs_no_compensation_of_its_own() -> None:
    """It *is* the walk-back; demanding one would be infinite regress."""
    workflow = _wired()
    assert "restore" not in workflow.uncompensated_mutations
    assert workflow.uncompensated_mutations == ()


# ----------------------------------------------------------------------
# Timeouts
# ----------------------------------------------------------------------


def test_a_deadline_shorter_than_the_longest_path_is_refused() -> None:
    """It can never complete, and the kill always looks like a slow dependency."""
    workflow = _wired().set_timeout(timeout(30))
    with pytest.raises(TimeoutUnsatisfiable) as caught:
        workflow.validate()
    assert caught.value.workflow_timeout == 30
    assert caught.value.critical_path > 30


def test_the_deadline_budget_includes_retries() -> None:
    workflow = _wired()
    needed, path = workflow.critical_path()
    # audit 60 + resize (120 * 2 attempts + 1s backoff)
    assert needed == 60 + 241
    assert path == ("audit", "resize")


def test_a_generous_deadline_is_accepted() -> None:
    assert _wired().set_timeout(timeout(900)).validate().status is WorkflowStatus.VALIDATED


# ----------------------------------------------------------------------
# Resume points
# ----------------------------------------------------------------------


def test_a_resume_point_inside_a_parallel_group_is_refused() -> None:
    """Resuming into half a fan-out leaves the rest in a state nothing records."""
    workflow = _empty(plan_task_ids=("a", "b", "c"))
    workflow = workflow.add_node(task_node("start", "kick off", "a", node_timeout=timeout(5)))
    workflow = workflow.add_node(task_node("left", "one", "b", node_timeout=timeout(5)))
    workflow = workflow.add_node(task_node("right", "other", "c", node_timeout=timeout(5)))
    workflow = workflow.add_edge(edge("start", "left")).add_edge(edge("start", "right"))
    workflow = workflow.add_parallel_group(parallel_group("fan", ["left", "right"]))
    workflow = workflow.add_resume_point(resume_point("left"))
    workflow = workflow.set_timeout(timeout(60))

    with pytest.raises(ResumePointInsideGroup) as caught:
        workflow.validate()
    assert caught.value.node_id == "left"


def test_a_resume_point_outside_a_group_is_accepted() -> None:
    workflow = _wired().add_resume_point(resume_point("audit", "after the audit"))
    assert workflow.validate().status is WorkflowStatus.VALIDATED


def test_a_resume_point_on_an_unknown_node_is_refused() -> None:
    workflow = _wired().add_resume_point(resume_point("ghost"))
    with pytest.raises(UnknownNode):
        workflow.validate()


# ----------------------------------------------------------------------
# Lifecycle: validate, compile, approve
# ----------------------------------------------------------------------


def test_an_incomplete_workflow_is_refused() -> None:
    with pytest.raises(IncompleteWorkflow) as caught:
        _empty().validate()
    assert set(caught.value.missing) == {"nodes", "workflow timeout"}


def test_compiling_freezes_the_execution_order_and_binds_the_digest() -> None:
    compiled = _wired().validate().compile()
    assert compiled.status is WorkflowStatus.COMPILED
    assert compiled.digest
    assert set(compiled.execution_order) == {n.node_id for n in compiled.nodes}
    compiled.verify_digest()


def test_compiling_before_validating_is_refused_with_the_argument() -> None:
    from backend.contexts.workflow import refusal_reason

    with pytest.raises(IllegalWorkflowTransition):
        _wired().compile()
    assert "validated before it is compiled" in refusal_reason(
        WorkflowStatus.DRAFT, WorkflowStatus.COMPILED
    )


def test_approving_before_compiling_is_refused() -> None:
    from backend.contexts.workflow import refusal_reason

    with pytest.raises(IllegalWorkflowTransition):
        _wired().validate().approve("sre-lead")
    assert "frozen at compilation" in refusal_reason(
        WorkflowStatus.VALIDATED, WorkflowStatus.APPROVED
    )


def test_only_an_approved_workflow_is_executable() -> None:
    compiled = _wired().validate().compile()
    assert not compiled.is_executable
    assert compiled.approve("sre-lead").is_executable


def test_a_compiled_workflow_without_an_order_cannot_exist() -> None:
    compiled = _wired().validate().compile()
    with pytest.raises(ContractViolation):
        dataclasses.replace(compiled, execution_order=())


def test_an_approval_must_name_who_gave_it() -> None:
    with pytest.raises(ContractViolation):
        _wired().validate().compile().approve("   ")


# ----------------------------------------------------------------------
# Editing invalidates compilation
# ----------------------------------------------------------------------


def test_editing_a_compiled_workflow_returns_it_to_draft() -> None:
    """A frozen order is a statement about a particular graph."""
    compiled = _wired().validate().compile()
    edited = compiled.add_resume_point(resume_point("audit"))

    assert edited.status is WorkflowStatus.DRAFT
    assert edited.digest is None
    assert edited.execution_order == ()


def test_removing_a_node_from_a_compiled_workflow_drops_its_edges() -> None:
    compiled = _wired().validate().compile()
    edited = compiled.remove_node("restore")

    assert edited.status is WorkflowStatus.DRAFT
    assert edited.node("restore") is None
    assert all("restore" not in (e.from_node, e.to_node) for e in edited.edges)


# ----------------------------------------------------------------------
# Immutability after approval
# ----------------------------------------------------------------------


_MUTATIONS = {
    "add_node": lambda w: w.add_node(task_node("late", "late work", "audit")),
    "remove_node": lambda w: w.remove_node("audit"),
    "add_edge": lambda w: w.add_edge(edge("audit", "restore")),
    "add_parallel_group": lambda w: w.add_parallel_group(
        parallel_group("g", ["audit", "resize"])
    ),
    "add_compensation": lambda w: w.add_compensation(compensation("resize", "audit")),
    "add_resume_point": lambda w: w.add_resume_point(resume_point("audit")),
    "set_timeout": lambda w: w.set_timeout(timeout(1200)),
    "validate": lambda w: w.validate(),
    "compile": lambda w: w.compile(),
    "approve": lambda w: w.approve("someone-else"),
}


@pytest.mark.parametrize("name", sorted(_MUTATIONS))
def test_every_mutation_refuses_on_an_approved_workflow(name: str) -> None:
    approved = _wired().validate().compile().approve("sre-lead")
    with pytest.raises(WorkflowApprovedError):
        _MUTATIONS[name](approved)


def test_every_mutation_is_covered_by_the_immutability_test() -> None:
    exposed = {
        name
        for name in dir(Workflow)
        if not name.startswith("_")
        and callable(getattr(Workflow, name))
        and name
        not in {
            "compute_digest",
            "digest_payload",
            "verify_digest",
            "node",
            "group",
            "graph",
            "critical_path",
            "derived_execution_order",
            "derived_compensation_order",
            "permitted_transitions",
            "supersede",
            "revise",
            "to_dict",
            "from_dict",
            "contract_name",
            "contract_version",
        }
    }
    assert exposed == set(_MUTATIONS), exposed.symmetric_difference(set(_MUTATIONS))


# ----------------------------------------------------------------------
# Versioning
# ----------------------------------------------------------------------


def test_revising_carries_the_graph_into_a_new_version() -> None:
    approved = _wired().validate().compile().approve("sre-lead")
    successor = approved.revise()

    assert successor.version == 2
    assert successor.supersedes == approved.workflow_id
    assert successor.status is WorkflowStatus.DRAFT
    assert len(successor.nodes) == len(approved.nodes)
    assert successor.plan_digest == approved.plan_digest


def test_superseding_is_permitted_on_an_approved_workflow() -> None:
    approved = _wired().validate().compile().approve("sre-lead")
    successor = approved.revise()
    superseded = approved.supersede(successor.workflow_id)

    assert superseded.status is WorkflowStatus.SUPERSEDED
    superseded.verify_digest()


def test_a_superseded_workflow_refuses_edits_with_its_own_error() -> None:
    superseded = _wired().supersede(WorkflowId.new())
    with pytest.raises(WorkflowIsSuperseded):
        superseded.add_resume_point(resume_point("audit"))


def test_a_workflow_cannot_supersede_itself() -> None:
    workflow = _wired()
    with pytest.raises(ContractViolation):
        workflow.supersede(workflow.workflow_id)


def test_a_version_above_one_must_name_what_it_supersedes() -> None:
    workflow = _wired()
    with pytest.raises(ContractViolation):
        dataclasses.replace(workflow, version=2, supersedes=None)


# ----------------------------------------------------------------------
# Digest
# ----------------------------------------------------------------------


def test_verifying_an_uncompiled_workflow_says_so() -> None:
    with pytest.raises(DigestNotComputed):
        _wired().verify_digest()


def test_tampering_with_a_node_is_caught() -> None:
    compiled = _wired().validate().compile()
    tampered = dataclasses.replace(
        compiled,
        nodes=tuple(
            dataclasses.replace(n, purpose="something else") if n.node_id == "audit" else n
            for n in compiled.nodes
        ),
    )
    with pytest.raises(DigestMismatch):
        tampered.verify_digest()


def test_the_digest_covers_the_governed_fields_and_nothing_else() -> None:
    payload = _wired().validate().compile().digest_payload()
    covered = set(payload) - {"__artifact__", "__canonical_form__"}
    assert covered == set(GOVERNED_FIELDS)


def test_derived_orders_are_not_governed() -> None:
    """They are recomputable from what is, so hashing them would be redundant."""
    for excluded in ("execution_order", "compensation_order", "status", "digest"):
        assert excluded not in GOVERNED_FIELDS


def test_the_plan_digest_is_governed() -> None:
    """A workflow compiled against a revised plan must not verify against the old."""
    assert "plan_digest" in GOVERNED_FIELDS
    compiled = _wired().validate().compile()
    with pytest.raises(DigestMismatch):
        dataclasses.replace(compiled, plan_digest="different").verify_digest()


def test_the_artifact_kind_is_named_in_the_payload() -> None:
    assert _wired().digest_payload()["__artifact__"] == ARTIFACT_KIND


# ----------------------------------------------------------------------
# Workflow never executes
# ----------------------------------------------------------------------


def test_the_aggregate_holds_no_run_state() -> None:
    run_shaped = {
        "results",
        "outcomes",
        "node_states",
        "attempts",
        "started_at",
        "completed_at",
        "failures",
        "current_node",
    }
    fields = {f.name for f in dataclasses.fields(Workflow)}
    assert fields & run_shaped == set()
