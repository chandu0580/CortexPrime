"""The dependency graph, and the value objects a plan is assembled from.

The graph tests carry the most weight in this PR. ``TaskRef`` in
``contracts/mission.py`` says the whole-graph cycle check belongs to whoever
holds the graph; this is that check, and these are the tests that make the
delegation real rather than a comment.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contracts.mission import TaskState
from backend.contexts.planner import (
    CyclicDependency,
    DanglingDependency,
    DependencyGraph,
    ExecutionMode,
    ExecutionStrategy,
    FailureResponse,
    Likelihood,
    RiskAssessment,
    RiskLevel,
    RiskUnderstated,
    RollbackKind,
    RollbackStrategy,
    SuccessCriterionRef,
    criterion,
    goal,
    implied_floor,
    normalise_task_id,
    reversal,
    risk,
    task,
)


# ----------------------------------------------------------------------
# The graph -- the check the published contract delegated here
# ----------------------------------------------------------------------


def test_a_simple_graph_reports_its_layers() -> None:
    graph = DependencyGraph(edges={"a": (), "b": ("a",), "c": ("a",), "d": ("b", "c")})
    assert graph.layers() == (("a",), ("b", "c"), ("d",))
    assert graph.roots == ("a",)
    assert graph.leaves == ("d",)
    assert graph.depth == 3
    assert graph.widest_layer == 2


def test_a_cycle_is_refused_and_names_the_path() -> None:
    """A refusal that says only 'there is a cycle' leaves the reader to find it."""
    with pytest.raises(CyclicDependency) as caught:
        DependencyGraph(edges={"a": ("c",), "b": ("a",), "c": ("b",)})
    assert set(caught.value.cycle) == {"a", "b", "c"}
    assert "->" in str(caught.value)


def test_a_two_task_cycle_is_refused() -> None:
    with pytest.raises(CyclicDependency):
        DependencyGraph(edges={"a": ("b",), "b": ("a",)})


def test_a_self_dependency_is_refused() -> None:
    with pytest.raises(ContractViolation):
        DependencyGraph(edges={"a": ("a",)})


def test_a_dangling_dependency_is_refused_and_names_what_is_missing() -> None:
    with pytest.raises(DanglingDependency) as caught:
        DependencyGraph(edges={"a": (), "b": ("ghost", "a")})
    assert caught.value.missing == ("ghost",)
    assert caught.value.task_id == "b"


def test_a_duplicate_dependency_is_refused() -> None:
    with pytest.raises(ContractViolation):
        DependencyGraph(edges={"a": (), "b": ("a", "a")})


def test_a_deep_chain_does_not_hit_a_recursion_limit() -> None:
    """A plan is allowed to be deep; a recursion limit is a silly reason to refuse."""
    edges = {f"t{i}": ((f"t{i-1}",) if i else ()) for i in range(3000)}
    assert DependencyGraph(edges=edges).depth == 3000


def test_a_deep_cycle_is_still_found() -> None:
    edges = {f"t{i}": ((f"t{i-1}",) if i else ("t999",)) for i in range(1000)}
    with pytest.raises(CyclicDependency):
        DependencyGraph(edges=edges)


def test_an_empty_graph_is_permitted() -> None:
    graph = DependencyGraph(edges={})
    assert graph.is_empty
    assert graph.layers() == ()
    assert graph.depth == 0
    assert graph.widest_layer == 0


def test_a_fully_parallel_graph_has_depth_one() -> None:
    graph = DependencyGraph(edges={"a": (), "b": (), "c": ()})
    assert graph.depth == 1
    assert graph.widest_layer == 3


def test_a_fully_sequential_graph_has_depth_equal_to_its_size() -> None:
    graph = DependencyGraph(edges={"a": (), "b": ("a",), "c": ("b",)})
    assert graph.depth == len(graph) == 3
    assert graph.widest_layer == 1


def test_blast_radius_counts_what_a_failure_would_strand() -> None:
    graph = DependencyGraph(edges={"a": (), "b": ("a",), "c": ("b",), "d": ()})
    assert graph.blast_of("a") == 2
    assert sorted(graph.reachable_from("a")) == ["b", "c"]
    assert graph.blast_of("d") == 0


def test_dependents_and_dependencies_are_both_answerable() -> None:
    graph = DependencyGraph(edges={"a": (), "b": ("a",), "c": ("a",)})
    assert graph.dependents_of("a") == ("b", "c")
    assert graph.dependencies_of("b") == ("a",)


def test_a_graph_built_from_tasks_matches_their_dependencies() -> None:
    tasks = [
        task("a", "first", goals=("g",)),
        task("b", "second", goals=("g",), depends_on=("a",)),
    ]
    graph = DependencyGraph.of(tasks)
    assert graph.task_ids == ("a", "b")
    assert graph.dependencies_of("b") == ("a",)


# ----------------------------------------------------------------------
# Task ids stay readable
# ----------------------------------------------------------------------


def test_a_task_id_with_surrounding_whitespace_is_refused() -> None:
    """Two ids differing only by spacing look identical in a dependency list."""
    with pytest.raises(ContractViolation):
        normalise_task_id(" deploy ")


def test_a_blank_task_id_is_refused() -> None:
    with pytest.raises(ContractViolation):
        normalise_task_id("   ")


def test_a_task_id_with_a_newline_is_refused() -> None:
    with pytest.raises(ContractViolation):
        normalise_task_id("deploy\napi")


def test_an_ordinary_readable_id_is_accepted() -> None:
    assert normalise_task_id("snapshot-db") == "snapshot-db"


# ----------------------------------------------------------------------
# Tasks -- Constitution P2 at the task level
# ----------------------------------------------------------------------


def test_a_read_task_needs_no_reversal() -> None:
    read = task("audit", "list utilisation", goals=("g",))
    assert not read.mutates
    assert read.side_effect is SideEffectClass.READ


def test_a_mutating_task_without_a_way_back_is_refused() -> None:
    """Constitution P2: reversibility precedes action."""
    with pytest.raises(ContractViolation) as caught:
        task("resize", "resize instances", goals=("g",), side_effect=SideEffectClass.REVERSIBLE_WRITE)
    assert "P2" in str(caught.value)


def test_a_mutating_task_with_a_reversal_is_accepted() -> None:
    reversible = task(
        "resize",
        "resize instances",
        goals=("g",),
        side_effect=SideEffectClass.REVERSIBLE_WRITE,
        reverses_with=reversal(inverse_action="restore-size"),
    )
    assert reversible.is_reversible
    assert not reversible.is_accepted_irreversible


def test_an_irreversible_task_may_be_accepted_by_name() -> None:
    """'There is no way back' is a decision somebody makes, not a property."""
    accepted = task(
        "purge",
        "delete the old bucket",
        goals=("g",),
        side_effect=SideEffectClass.DESTRUCTIVE,
        irreversible_accepted_by="head-of-platform",
    )
    assert accepted.is_accepted_irreversible
    assert accepted.requires_approval_by_default


def test_a_read_task_that_declares_a_reversal_is_refused() -> None:
    with pytest.raises(ContractViolation):
        task("audit", "read only", goals=("g",), reverses_with=reversal(inverse_action="x"))


def test_a_reversal_must_name_something() -> None:
    with pytest.raises(ContractViolation):
        reversal()


def test_a_task_must_state_its_purpose() -> None:
    with pytest.raises(ContractViolation):
        task("t", "   ", goals=("g",))


def test_a_task_projects_onto_the_published_vocabulary_as_pending() -> None:
    """A planner that could emit SUCCEEDED would be reporting execution it did not do."""
    ref = task("a", "do a thing", goals=("g",), depends_on=()).as_task_ref("M-1")
    assert ref.state is TaskState.PENDING
    assert ref.task_id == "a"
    assert ref.mission.mission_id == "M-1"


# ----------------------------------------------------------------------
# Goals and criteria
# ----------------------------------------------------------------------


def test_a_goal_must_trace_to_a_criterion() -> None:
    with pytest.raises(ContractViolation):
        goal("do something useful", [])


def test_a_goal_records_the_criteria_it_serves() -> None:
    made = goal("rightsize", [criterion("CR-1", "spend drops 20%")])
    assert made.criterion_ids == ("CR-1",)


def test_a_criterion_reference_must_name_the_criterion() -> None:
    with pytest.raises(ContractViolation):
        SuccessCriterionRef(criterion_id="   ")


def test_a_criterion_reference_renders_its_statement_when_it_has_one() -> None:
    assert str(criterion("CR-1", "spend drops")) == "spend drops"
    assert str(criterion("CR-2")) == "CR-2"


# ----------------------------------------------------------------------
# Strategy
# ----------------------------------------------------------------------


def test_a_parallel_strategy_that_runs_one_task_at_a_time_is_refused() -> None:
    with pytest.raises(ContractViolation):
        ExecutionStrategy(mode=ExecutionMode.PARALLEL, max_parallelism=1)


def test_a_sequential_strategy_with_parallelism_is_refused() -> None:
    with pytest.raises(ContractViolation):
        ExecutionStrategy(mode=ExecutionMode.SEQUENTIAL, max_parallelism=4)


def test_continuing_past_a_failure_must_be_justified() -> None:
    """Carrying on after a failed task is how a plan half-applies a change."""
    with pytest.raises(ContractViolation):
        ExecutionStrategy(on_failure=FailureResponse.CONTINUE)

    justified = ExecutionStrategy(
        on_failure=FailureResponse.CONTINUE,
        continue_justification="every task is independent and read-only",
    )
    assert not justified.stops_on_failure


def test_halt_and_compensate_stop_the_work() -> None:
    assert ExecutionStrategy(on_failure=FailureResponse.HALT).stops_on_failure
    assert ExecutionStrategy(on_failure=FailureResponse.COMPENSATE).stops_on_failure


def test_a_checkpoint_named_twice_is_refused() -> None:
    with pytest.raises(ContractViolation):
        ExecutionStrategy(checkpoint_after=("a", "a"))


def test_a_forward_fix_rollback_must_name_who_accepted_it() -> None:
    with pytest.raises(ContractViolation):
        RollbackStrategy(kind=RollbackKind.FORWARD_FIX_ONLY, description="roll forward")


def test_a_forward_fix_rollback_must_describe_recovery() -> None:
    with pytest.raises(ContractViolation):
        RollbackStrategy(kind=RollbackKind.FORWARD_FIX_ONLY, accepted_by="cto")


def test_a_snapshot_rollback_must_name_what_is_snapshotted() -> None:
    with pytest.raises(ContractViolation):
        RollbackStrategy(kind=RollbackKind.SNAPSHOT_RESTORE)


def test_which_rollbacks_provide_a_way_back() -> None:
    assert RollbackKind.COMPENSATING_TASKS.provides_a_way_back
    assert RollbackKind.SNAPSHOT_RESTORE.provides_a_way_back
    assert not RollbackKind.FORWARD_FIX_ONLY.provides_a_way_back
    assert not RollbackKind.NONE_REQUIRED.provides_a_way_back


# ----------------------------------------------------------------------
# Risk -- the floor the tasks imply
# ----------------------------------------------------------------------


def test_a_read_only_plan_implies_low_risk() -> None:
    tasks = [task("a", "read", goals=("g",))]
    level, _ = implied_floor(tasks)
    assert level is RiskLevel.LOW


def test_a_reversible_mutation_implies_moderate() -> None:
    tasks = [
        task(
            "a",
            "write",
            goals=("g",),
            side_effect=SideEffectClass.REVERSIBLE_WRITE,
            reverses_with=reversal(inverse_action="undo"),
        )
    ]
    level, _ = implied_floor(tasks)
    assert level is RiskLevel.MODERATE


def test_an_irreversible_write_implies_elevated() -> None:
    tasks = [
        task(
            "a",
            "write",
            goals=("g",),
            side_effect=SideEffectClass.IRREVERSIBLE_WRITE,
            irreversible_accepted_by="lead",
        )
    ]
    level, driver = implied_floor(tasks)
    assert level is RiskLevel.ELEVATED
    assert "irreversible" in driver


def test_a_destructive_task_implies_severe() -> None:
    tasks = [
        task(
            "a",
            "delete",
            goals=("g",),
            side_effect=SideEffectClass.DESTRUCTIVE,
            irreversible_accepted_by="lead",
        )
    ]
    level, driver = implied_floor(tasks)
    assert level is RiskLevel.SEVERE
    assert "destructive" in driver


def test_an_assessment_below_the_floor_is_refused() -> None:
    """Risk that can be argued down without changing anything else is a mood."""
    tasks = [
        task(
            "a",
            "delete",
            goals=("g",),
            side_effect=SideEffectClass.DESTRUCTIVE,
            irreversible_accepted_by="lead",
        )
    ]
    with pytest.raises(RiskUnderstated) as caught:
        RiskAssessment.create(RiskLevel.LOW).assert_covers(tasks)
    assert caught.value.implied == "severe"


def test_the_floor_is_a_floor_not_a_ceiling() -> None:
    """Reading the wrong production database at the wrong moment is a real risk."""
    tasks = [task("a", "read", goals=("g",))]
    RiskAssessment.create(RiskLevel.SEVERE, risks=()).assert_covers(tasks)


def test_an_overall_below_its_own_worst_risk_is_refused() -> None:
    severe = risk("this could take everything down", RiskLevel.SEVERE, mitigation="a canary")
    with pytest.raises(ContractViolation):
        RiskAssessment.create(RiskLevel.LOW, risks=[severe])


def test_an_elevated_risk_must_state_its_mitigation() -> None:
    with pytest.raises(ContractViolation):
        risk("something bad", RiskLevel.ELEVATED)


def test_a_low_risk_needs_no_mitigation() -> None:
    assert not risk("something minor", RiskLevel.LOW).is_mitigated


def test_risk_levels_rank_in_the_order_they_read() -> None:
    ranks = [
        RiskLevel.LOW.rank,
        RiskLevel.MODERATE.rank,
        RiskLevel.ELEVATED.rank,
        RiskLevel.SEVERE.rank,
    ]
    assert ranks == sorted(ranks)
    assert RiskLevel.LOW < RiskLevel.SEVERE


def test_likelihood_ranks_too() -> None:
    assert Likelihood.UNLIKELY.rank < Likelihood.POSSIBLE.rank < Likelihood.LIKELY.rank
