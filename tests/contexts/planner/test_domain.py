"""The Plan aggregate: composition, the whole-plan checks, versioning, digest.

Four rules need the whole plan, and this file is where they are pinned:

* the graph is acyclic and complete;
* every task serves a goal;
* every criterion is covered by a goal;
* the declared risk is not below what the tasks imply.

Plus Constitution P2 at the plan level: a plan that mutates cannot claim it needs
no rollback.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contexts.planner import (
    ARTIFACT_KIND,
    CyclicDependency,
    DigestMismatch,
    DigestNotComputed,
    DuplicateTask,
    ExecutionStrategy,
    GOVERNED_FIELDS,
    GoalWithoutTasks,
    IllegalPlanTransition,
    IncompletePlan,
    OrphanTask,
    Plan,
    PlanApprovedError,
    PlanId,
    PlanIsSuperseded,
    PlanStatus,
    REQUIRED_ELEMENTS,
    RiskLevel,
    RiskUnderstated,
    RollbackKind,
    RollbackStrategy,
    UncoveredCriterion,
    UnknownTask,
    assessment,
    criterion,
    draft_plan,
    goal,
    reversal,
    risk,
    task,
)

CRITERION = "CR-1"


def _drafted(**overrides) -> Plan:
    fields = dict(
        mission_id="M-1",
        intent_id="I-1",
        intent_digest="9f2c1a7b",
        title="Cut AWS spend 20%",
    )
    fields.update(overrides)
    return draft_plan(**fields)


def _with_goal(**overrides):
    """A plan carrying one criterion and one goal that serves it."""
    plan = _drafted(**overrides).declare_criteria([criterion(CRITERION, "spend drops 20%")])
    made = goal("Rightsize over-provisioned instances", [criterion(CRITERION)])
    return plan.add_goal(made), str(made.goal_id)


def _complete(**overrides) -> Plan:
    """A plan with all seven elements, coherent and ready to validate."""
    plan, goal_id = _with_goal(**overrides)
    plan = plan.add_task(task("audit", "list instance utilisation", goals=(goal_id,)))
    plan = plan.add_task(
        task(
            "resize",
            "resize the over-provisioned ones",
            goals=(goal_id,),
            depends_on=("audit",),
            side_effect=SideEffectClass.REVERSIBLE_WRITE,
            reverses_with=reversal(inverse_action="restore-previous-size"),
        )
    )
    plan = plan.set_rollback_strategy(RollbackStrategy.compensating())
    return plan.assess_risk(
        assessment(
            RiskLevel.MODERATE,
            risks=[risk("resizing may throttle batch jobs", RiskLevel.MODERATE)],
        )
    )


# ----------------------------------------------------------------------
# Creation and binding
# ----------------------------------------------------------------------


def test_a_plan_names_the_mandate_it_was_built_from() -> None:
    """A plan is a statement about *that* intent, at *that* digest."""
    plan = _drafted()
    assert plan.mission_id == "M-1"
    assert plan.intent_id == "I-1"
    assert plan.intent_digest == "9f2c1a7b"
    assert plan.version == 1
    assert plan.status is PlanStatus.DRAFT


@pytest.mark.parametrize(
    "blank", ["mission_id", "intent_id", "intent_digest", "title"]
)
def test_a_plan_missing_a_binding_is_refused(blank: str) -> None:
    with pytest.raises(ContractViolation):
        _drafted(**{blank: "  "})


def test_a_fresh_plan_is_missing_the_elements_it_needs() -> None:
    missing = set(_drafted().missing_elements)
    assert missing == {"goals", "tasks", "success criteria", "risk"}
    assert missing <= set(REQUIRED_ELEMENTS)


# ----------------------------------------------------------------------
# The graph, through the aggregate
# ----------------------------------------------------------------------


def test_adding_a_dependency_that_would_cycle_is_refused() -> None:
    """The refusal arrives at the edge that makes the cycle."""
    plan = _complete()
    with pytest.raises(CyclicDependency):
        plan.add_dependency("audit", "resize")


def test_a_duplicate_task_id_is_refused() -> None:
    plan, goal_id = _with_goal()
    plan = plan.add_task(task("audit", "first", goals=(goal_id,)))
    with pytest.raises(DuplicateTask):
        plan.add_task(task("audit", "second", goals=(goal_id,)))


def test_a_dependency_on_an_unknown_task_is_refused() -> None:
    plan = _complete()
    with pytest.raises(UnknownTask):
        plan.add_dependency("resize", "ghost")


def test_adding_the_same_dependency_twice_is_a_no_op() -> None:
    plan = _complete()
    assert plan.add_dependency("resize", "audit") is plan


def test_the_graph_is_rebuilt_on_every_construction() -> None:
    """So a stored plan edited into a cycle refuses to load."""
    plan = _complete()
    broken = [
        dataclasses.replace(t, depends_on=("resize",)) if t.task_id == "audit" else t
        for t in plan.tasks
    ]
    with pytest.raises(CyclicDependency):
        dataclasses.replace(plan, tasks=tuple(broken))


def test_the_graph_reports_layers_through_the_plan() -> None:
    plan = _complete()
    assert plan.graph.layers() == (("audit",), ("resize",))
    assert plan.graph.depth == 2


# ----------------------------------------------------------------------
# The four whole-plan checks
# ----------------------------------------------------------------------


def test_a_task_serving_no_goal_is_refused_at_validation() -> None:
    """Work that traces to nothing asked for still spends the blast radius."""
    plan, goal_id = _with_goal()
    plan = plan.add_task(task("audit", "list", goals=(goal_id,)))
    orphaned = dataclasses.replace(
        plan, tasks=plan.tasks + (dataclasses.replace(plan.tasks[0], task_id="stray", goal_ids=frozenset()),)
    )
    plan = orphaned.set_rollback_strategy(RollbackStrategy.none_required()).assess_risk(
        assessment(RiskLevel.LOW)
    )
    with pytest.raises(OrphanTask) as caught:
        plan.validate()
    assert "stray" in caught.value.orphans


def test_a_criterion_no_goal_covers_is_refused() -> None:
    """The plan could complete every task and still not achieve it."""
    plan = _complete().declare_criteria([criterion("CR-UNCOVERED")])
    with pytest.raises(UncoveredCriterion) as caught:
        plan.validate()
    assert caught.value.uncovered == ("CR-UNCOVERED",)


def test_a_goal_with_no_tasks_is_refused() -> None:
    plan = _complete()
    idle = goal("Something nothing works towards", [criterion(CRITERION)])
    with pytest.raises(GoalWithoutTasks):
        plan.add_goal(idle).validate()


def test_a_mutating_plan_cannot_claim_it_needs_no_rollback() -> None:
    """Constitution P2 at the plan level."""
    from backend.contexts.planner import RollbackNotDeclared

    plan = _complete().set_rollback_strategy(RollbackStrategy.none_required())
    with pytest.raises(RollbackNotDeclared) as caught:
        plan.validate()
    assert "resize" in caught.value.mutating


def test_a_read_only_plan_needs_no_rollback() -> None:
    plan, goal_id = _with_goal()
    plan = plan.add_task(task("audit", "read only", goals=(goal_id,)))
    plan = plan.assess_risk(assessment(RiskLevel.LOW))
    assert plan.validate().status is PlanStatus.VALIDATED


def test_a_risk_below_the_floor_is_refused_when_assessed() -> None:
    plan = _complete()
    with pytest.raises(RiskUnderstated):
        plan.assess_risk(assessment(RiskLevel.LOW))


def test_the_implied_floor_is_reported() -> None:
    level, driver = _complete().implied_risk_floor
    assert level is RiskLevel.MODERATE
    assert driver


# ----------------------------------------------------------------------
# Validation and approval
# ----------------------------------------------------------------------


def test_an_incomplete_plan_is_refused_and_names_what_is_missing() -> None:
    with pytest.raises(IncompletePlan) as caught:
        _drafted().validate()
    assert set(caught.value.missing) == {"goals", "tasks", "success criteria", "risk"}


def test_a_complete_coherent_plan_validates() -> None:
    validated = _complete().validate()
    assert validated.status is PlanStatus.VALIDATED
    assert validated.validated_at is not None


def test_an_incoherent_plan_cannot_be_assembled_as_validated() -> None:
    """The refusal holds for a record built directly, which is the path replay takes."""
    plan = _complete()
    with pytest.raises(ContractViolation):
        dataclasses.replace(plan, status=PlanStatus.VALIDATED, success_criteria=frozenset())


def test_a_validated_plan_is_not_yet_executable() -> None:
    """Sound is not the same as authorised."""
    validated = _complete().validate()
    assert not validated.is_executable
    assert validated.approve("sre-lead").is_executable


def test_approving_a_draft_is_refused_with_the_argument() -> None:
    from backend.contexts.planner import refusal_reason

    with pytest.raises(IllegalPlanTransition):
        _complete().approve("sre-lead")
    assert "validated before it is approved" in refusal_reason(
        PlanStatus.DRAFT, PlanStatus.APPROVED
    )


def test_an_approval_must_name_who_gave_it() -> None:
    with pytest.raises(ContractViolation):
        _complete().validate().approve("  ")


# ----------------------------------------------------------------------
# Editing invalidates validation
# ----------------------------------------------------------------------


def test_adding_a_task_to_a_validated_plan_returns_it_to_draft() -> None:
    validated = _complete().validate()
    _, goal_id = _with_goal()
    edited = validated.add_task(
        task("extra", "another read", goals=(str(validated.goals[0].goal_id),))
    )
    assert edited.status is PlanStatus.DRAFT
    assert edited.validated_at is None


def test_removing_a_task_from_a_validated_plan_returns_it_to_draft() -> None:
    """The demotion happens in the same construction, so no invalid intermediate."""
    validated = _complete().validate()
    edited = validated.remove_task("resize")
    assert edited.status is PlanStatus.DRAFT
    assert edited.task("resize") is None


def test_removing_an_unknown_task_is_refused() -> None:
    with pytest.raises(UnknownTask):
        _complete().remove_task("ghost")


# ----------------------------------------------------------------------
# Immutability after approval
# ----------------------------------------------------------------------


_MUTATIONS = {
    "add_goal": lambda p: p.add_goal(goal("late", [criterion(CRITERION)])),
    "add_task": lambda p: p.add_task(task("late", "late work", goals=(str(p.goals[0].goal_id),))),
    "remove_task": lambda p: p.remove_task("audit"),
    "add_dependency": lambda p: p.add_dependency("audit", "resize"),
    "declare_criteria": lambda p: p.declare_criteria([criterion("CR-2")]),
    "set_execution_strategy": lambda p: p.set_execution_strategy(ExecutionStrategy()),
    "set_rollback_strategy": lambda p: p.set_rollback_strategy(RollbackStrategy.none_required()),
    "assess_risk": lambda p: p.assess_risk(assessment(RiskLevel.SEVERE)),
    "validate": lambda p: p.validate(),
    "approve": lambda p: p.approve("someone-else"),
    "reject": lambda p: p.reject("changed my mind"),
}


@pytest.mark.parametrize("name", sorted(_MUTATIONS))
def test_every_mutation_refuses_on_an_approved_plan(name: str) -> None:
    approved = _complete().validate().approve("sre-lead")
    with pytest.raises(PlanApprovedError):
        _MUTATIONS[name](approved)


def test_every_mutation_is_covered_by_the_immutability_test() -> None:
    """Fails if a mutation is added to the aggregate without an entry above."""
    exposed = {
        name
        for name in dir(Plan)
        if not name.startswith("_")
        and callable(getattr(Plan, name))
        and name
        not in {
            "compute_digest",
            "digest_payload",
            "verify_digest",
            "task",
            "goal",
            "tasks_for_goal",
            "permitted_transitions",
            "as_task_refs",
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


def test_revising_opens_the_next_version_carrying_the_content() -> None:
    approved = _complete().validate().approve("sre-lead")
    successor = approved.revise()

    assert successor.version == 2
    assert successor.supersedes == approved.plan_id
    assert successor.status is PlanStatus.DRAFT
    assert len(successor.tasks) == len(approved.tasks)
    assert successor.intent_digest == approved.intent_digest


def test_superseding_is_permitted_on_an_approved_plan() -> None:
    approved = _complete().validate().approve("sre-lead")
    successor = approved.revise()
    superseded = approved.supersede(successor.plan_id)

    assert superseded.status is PlanStatus.SUPERSEDED
    superseded.verify_digest()


def test_a_superseded_plan_refuses_edits_with_its_own_error() -> None:
    superseded = _complete().supersede(PlanId.new())
    with pytest.raises(PlanIsSuperseded):
        superseded.add_task(task("x", "late", goals=("g",)))


def test_a_plan_cannot_supersede_itself() -> None:
    plan = _complete()
    with pytest.raises(ContractViolation):
        plan.supersede(plan.plan_id)


def test_a_version_above_one_must_name_what_it_supersedes() -> None:
    """A version chain with a gap cannot be walked back."""
    plan = _complete()
    with pytest.raises(ContractViolation):
        dataclasses.replace(plan, version=2, supersedes=None)


# ----------------------------------------------------------------------
# Digest
# ----------------------------------------------------------------------


def test_approving_binds_a_digest_that_verifies() -> None:
    approved = _complete().validate().approve("sre-lead")
    assert approved.digest
    approved.verify_digest()


def test_verifying_an_unapproved_plan_says_so_rather_than_passing() -> None:
    with pytest.raises(DigestNotComputed):
        _complete().verify_digest()


def test_tampering_with_a_task_is_caught() -> None:
    approved = _complete().validate().approve("sre-lead")
    tampered = dataclasses.replace(
        approved,
        tasks=tuple(
            dataclasses.replace(t, purpose="something else") if t.task_id == "audit" else t
            for t in approved.tasks
        ),
    )
    with pytest.raises(DigestMismatch):
        tampered.verify_digest()


def test_the_digest_covers_the_governed_fields_and_nothing_else() -> None:
    payload = _complete().validate().approve("sre-lead").digest_payload()
    covered = set(payload) - {"__artifact__", "__canonical_form__"}
    assert covered == set(GOVERNED_FIELDS)


def test_status_and_approval_metadata_are_not_governed() -> None:
    for excluded in ("status", "digest", "approved_at", "approved_by", "validated_at"):
        assert excluded not in GOVERNED_FIELDS


def test_the_artifact_kind_is_named_in_the_payload() -> None:
    assert _complete().digest_payload()["__artifact__"] == ARTIFACT_KIND


def test_the_intent_digest_is_governed() -> None:
    """A plan built against a revised mandate must not verify against the old one."""
    assert "intent_digest" in GOVERNED_FIELDS
    approved = _complete().validate().approve("sre-lead")
    with pytest.raises(DigestMismatch):
        dataclasses.replace(approved, intent_digest="different").verify_digest()


# ----------------------------------------------------------------------
# Planner never executes
# ----------------------------------------------------------------------


def test_the_aggregate_holds_no_execution_state() -> None:
    """Every field describes work that has not happened."""
    execution_shaped = {
        "results",
        "outcomes",
        "started_at",
        "completed_at",
        "task_states",
        "attempts",
        "failures",
    }
    fields = {f.name for f in dataclasses.fields(Plan)}
    assert fields & execution_shaped == set()


def test_every_projected_task_is_pending() -> None:
    """A planner that could emit SUCCEEDED would be reporting execution."""
    from backend.contracts.mission import TaskState

    approved = _complete().validate().approve("sre-lead")
    assert all(ref.state is TaskState.PENDING for ref in approved.as_task_refs())
