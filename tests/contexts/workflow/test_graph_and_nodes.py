"""The control-flow graph and the constructs a workflow is assembled from.

The graph tests carry the most weight. Four questions only the whole graph can
answer -- acyclicity, reachability, independence, and the longest forward path --
and each prevents a distinct failure an executor would otherwise discover at
three in the morning.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contexts.workflow import (
    BackoffKind,
    BranchTooNarrow,
    BranchWithoutDefault,
    ConditionKind,
    CyclicWorkflow,
    DanglingEdge,
    EdgeKind,
    JoinPolicy,
    NodeKind,
    ParallelGroupTooSmall,
    RetryWithoutIdempotency,
    UnreachableNode,
    WorkflowCondition,
    WorkflowGraph,
    WorkflowRetryPolicy,
    WorkflowTimeout,
    arm,
    branch_node,
    compensation_node,
    edge,
    normalise_node_id,
    parallel_group,
    resume_point,
    retry,
    task_node,
    timeout,
)


def _edge(a: str, b: str, kind: EdgeKind = EdgeKind.NORMAL):
    return edge(a, b, kind=kind)


# ----------------------------------------------------------------------
# The graph
# ----------------------------------------------------------------------


def test_a_diamond_reports_its_layers() -> None:
    graph = WorkflowGraph(
        nodes=("a", "b", "c", "d"),
        edges=(_edge("a", "b"), _edge("a", "c"), _edge("b", "d"), _edge("c", "d")),
    )
    assert graph.layers() == (("a",), ("b", "c"), ("d",))
    assert graph.entry_points == ("a",)
    assert graph.exit_points == ("d",)
    assert graph.depth == 3
    assert graph.widest_layer == 2


def test_a_cycle_is_refused_and_names_the_path() -> None:
    with pytest.raises(CyclicWorkflow) as caught:
        WorkflowGraph(
            nodes=("a", "b", "c"),
            edges=(_edge("a", "b"), _edge("b", "c"), _edge("c", "a")),
        )
    assert set(caught.value.cycle) == {"a", "b", "c"}
    assert "->" in str(caught.value)


def test_a_cycle_through_a_failure_edge_is_still_a_cycle() -> None:
    """Failure edges are part of the graph; a loop through one still never ends."""
    with pytest.raises(CyclicWorkflow):
        WorkflowGraph(
            nodes=("a", "b"),
            edges=(_edge("a", "b"), _edge("b", "a", EdgeKind.ON_FAILURE)),
        )


def test_an_edge_to_itself_is_refused() -> None:
    with pytest.raises(ContractViolation):
        edge("a", "a")


def test_a_dangling_edge_is_refused() -> None:
    with pytest.raises(DanglingEdge) as caught:
        WorkflowGraph(nodes=("a",), edges=(_edge("a", "ghost"),))
    assert caught.value.missing == ("ghost",)


def test_an_unreachable_node_is_refused() -> None:
    """The workflow would complete successfully having never run it."""
    graph = WorkflowGraph(nodes=("a", "b", "orphan"), edges=(_edge("a", "b"),))
    with pytest.raises(UnreachableNode) as caught:
        graph.assert_fully_reachable()
    assert caught.value.unreachable == ("orphan",)


def test_a_deep_chain_does_not_hit_a_recursion_limit() -> None:
    nodes = tuple(f"n{i}" for i in range(2000))
    edges = tuple(_edge(f"n{i}", f"n{i + 1}") for i in range(1999))
    assert WorkflowGraph(nodes=nodes, edges=edges).depth == 2000


def test_independence_is_transitive() -> None:
    """Declaring two nodes parallel does not make them independent."""
    graph = WorkflowGraph(
        nodes=("a", "b", "c", "d"),
        edges=(_edge("a", "b"), _edge("b", "c"), _edge("a", "d")),
    )
    assert graph.are_independent("c", "d")
    assert not graph.are_independent("a", "c")
    assert not graph.are_independent("b", "c")
    assert not graph.are_independent("a", "a")


def test_ancestors_are_what_a_condition_may_read() -> None:
    graph = WorkflowGraph(
        nodes=("a", "b", "c"), edges=(_edge("a", "b"), _edge("b", "c"))
    )
    assert sorted(graph.ancestors_of("c")) == ["a", "b"]
    assert graph.ancestors_of("a") == frozenset()


def test_the_critical_path_is_the_longest_forward_route() -> None:
    graph = WorkflowGraph(
        nodes=("a", "b", "c", "d"),
        edges=(_edge("a", "b"), _edge("a", "c"), _edge("b", "d"), _edge("c", "d")),
    )
    seconds, path = graph.critical_path({"a": 10, "b": 30, "c": 5, "d": 10})
    assert seconds == 50
    assert path == ("a", "b", "d")


def test_the_critical_path_excludes_the_failure_path() -> None:
    """Budgeting the deadline for the failure path would make every timeout absurd."""
    graph = WorkflowGraph(
        nodes=("a", "b", "comp"),
        edges=(_edge("a", "b"), _edge("a", "comp", EdgeKind.ON_FAILURE)),
    )
    seconds, path = graph.critical_path({"a": 1, "b": 2, "comp": 1000})
    assert seconds == 3
    assert path == ("a", "b")
    assert graph.forward_reachable == ("a", "b")


def test_the_topological_order_is_stable() -> None:
    """Two executors must not disagree about a graph both consider valid."""
    graph = WorkflowGraph(
        nodes=("a", "b", "c"), edges=(_edge("a", "b"), _edge("a", "c"))
    )
    assert graph.topological_order() == graph.topological_order() == ("a", "b", "c")


def test_descendants_are_what_a_failure_would_strand() -> None:
    graph = WorkflowGraph(
        nodes=("a", "b", "c"), edges=(_edge("a", "b"), _edge("b", "c"))
    )
    assert sorted(graph.descendants_of("a")) == ["b", "c"]


# ----------------------------------------------------------------------
# Node ids stay readable
# ----------------------------------------------------------------------


def test_a_node_id_with_surrounding_whitespace_is_refused() -> None:
    with pytest.raises(ContractViolation):
        normalise_node_id(" audit ")


def test_a_node_id_with_a_newline_is_refused() -> None:
    with pytest.raises(ContractViolation):
        normalise_node_id("audit\ndb")


# ----------------------------------------------------------------------
# Nodes
# ----------------------------------------------------------------------


def test_a_task_node_must_name_the_plan_task_it_runs() -> None:
    """Orchestration runs what was planned, never work of its own."""
    with pytest.raises(ContractViolation):
        task_node("audit", "list things", "")


def test_a_control_flow_node_runs_no_plan_task() -> None:
    node = branch_node(
        "choose",
        "pick a path",
        [
            arm("a", WorkflowCondition.on_success("upstream")),
            arm("b", WorkflowCondition.always()),
        ],
    )
    assert node.plan_task_id is None
    assert node.kind.is_control_flow


def test_a_control_flow_node_cannot_classify_a_side_effect() -> None:
    from backend.contexts.workflow import WorkflowNode

    with pytest.raises(ContractViolation):
        WorkflowNode(
            node_id="join",
            kind=NodeKind.JOIN,
            purpose="wait",
            side_effect=SideEffectClass.DESTRUCTIVE,
        )


def test_a_compensation_must_name_what_it_walks_back() -> None:
    with pytest.raises(ContractViolation):
        compensation_node("restore", "restore", "")


def test_a_compensation_cannot_compensate_itself() -> None:
    with pytest.raises(ContractViolation):
        compensation_node("restore", "restore", "restore")


def test_a_node_must_state_its_purpose() -> None:
    with pytest.raises(ContractViolation):
        task_node("audit", "   ", "audit")


def test_the_worst_case_includes_retries_and_waits() -> None:
    """A budget computed from the happy path is only ever wrong when it matters."""
    node = task_node(
        "resize",
        "resize",
        "resize",
        side_effect=SideEffectClass.REVERSIBLE_WRITE,
        retry_policy=retry(3, initial_delay_seconds=2, idempotency_key="k"),
        node_timeout=timeout(10),
    )
    # three attempts of 10s, plus 2s + 4s of exponential backoff
    assert node.worst_case_seconds == 36


# ----------------------------------------------------------------------
# Branches
# ----------------------------------------------------------------------


def test_a_branch_without_a_default_is_refused() -> None:
    """A branch with no default stalls on the case nobody thought of."""
    with pytest.raises(BranchWithoutDefault):
        branch_node(
            "choose",
            "pick",
            [
                arm("a", WorkflowCondition.on_success("x")),
                arm("b", WorkflowCondition.on_failure("x")),
            ],
        )


def test_a_branch_with_one_arm_is_refused() -> None:
    with pytest.raises(BranchTooNarrow):
        branch_node("choose", "pick", [arm("a", WorkflowCondition.always())])


def test_a_branch_with_two_defaults_is_refused() -> None:
    with pytest.raises(ContractViolation):
        branch_node(
            "choose",
            "pick",
            [arm("a", WorkflowCondition.always()), arm("b", WorkflowCondition.always())],
        )


def test_a_branch_sending_two_arms_to_one_node_is_refused() -> None:
    """The condition that chose between them decides nothing."""
    with pytest.raises(ContractViolation):
        branch_node(
            "choose",
            "pick",
            [
                arm("a", WorkflowCondition.on_success("x")),
                arm("a", WorkflowCondition.always()),
            ],
        )


def test_a_valid_branch_reports_its_default() -> None:
    node = branch_node(
        "choose",
        "pick",
        [
            arm("bulk", WorkflowCondition.on_output("audit", "count > 10")),
            arm("single", WorkflowCondition.always()),
        ],
    )
    assert node.default_arm.to_node == "single"


# ----------------------------------------------------------------------
# Conditions
# ----------------------------------------------------------------------


def test_a_condition_that_reads_an_outcome_must_name_the_node() -> None:
    with pytest.raises(ContractViolation):
        WorkflowCondition(kind=ConditionKind.ON_SUCCESS)


def test_an_always_condition_reads_no_node() -> None:
    with pytest.raises(ContractViolation):
        WorkflowCondition(kind=ConditionKind.ALWAYS, source_node="x")


def test_an_output_condition_must_carry_its_expression() -> None:
    with pytest.raises(ContractViolation):
        WorkflowCondition(kind=ConditionKind.ON_OUTPUT, source_node="x")


def test_conditions_render_readably() -> None:
    assert str(WorkflowCondition.always()) == "always"
    assert "on_success(x)" in str(WorkflowCondition.on_success("x"))
    assert "count > 10" in str(WorkflowCondition.on_output("x", "count > 10"))


# ----------------------------------------------------------------------
# Retry policies
# ----------------------------------------------------------------------


def test_retrying_a_mutating_node_without_idempotency_is_refused() -> None:
    """A retry after an ambiguous failure may apply the action twice."""
    with pytest.raises(RetryWithoutIdempotency):
        task_node(
            "purge",
            "delete",
            "purge",
            side_effect=SideEffectClass.DESTRUCTIVE,
            retry_policy=retry(3),
        )


def test_retrying_a_read_needs_no_idempotency_key() -> None:
    node = task_node("audit", "read", "audit", retry_policy=retry(3))
    assert node.retry.retries
    assert not node.retry.is_idempotent


def test_a_mutating_node_with_an_idempotency_key_may_retry() -> None:
    node = task_node(
        "resize",
        "resize",
        "resize",
        side_effect=SideEffectClass.REVERSIBLE_WRITE,
        retry_policy=retry(3, idempotency_key="resize-2026-08"),
    )
    assert node.retry.is_idempotent


def test_a_retry_with_no_backoff_and_no_delay_is_refused() -> None:
    """Against a system failing because it is overloaded, that is the worst response."""
    with pytest.raises(ContractViolation):
        WorkflowRetryPolicy(max_attempts=3, backoff=BackoffKind.NONE)


def test_backoff_needs_a_delay_to_grow_from() -> None:
    with pytest.raises(ContractViolation):
        WorkflowRetryPolicy(
            max_attempts=3, backoff=BackoffKind.EXPONENTIAL, initial_delay_seconds=0
        )


def test_max_attempts_is_at_least_one() -> None:
    with pytest.raises(ContractViolation):
        WorkflowRetryPolicy(max_attempts=0)


def test_exponential_backoff_is_capped_when_a_max_is_given() -> None:
    policy = WorkflowRetryPolicy(
        max_attempts=5,
        backoff=BackoffKind.EXPONENTIAL,
        initial_delay_seconds=1,
        max_delay_seconds=3,
        idempotency_key="k",
    )
    # 1 + 2 + 3 + 3, capped rather than 1 + 2 + 4 + 8
    assert policy.worst_case_seconds() == 9


# ----------------------------------------------------------------------
# Timeouts
# ----------------------------------------------------------------------


def test_a_zero_timeout_is_refused() -> None:
    with pytest.raises(ContractViolation):
        WorkflowTimeout(seconds=0)


def test_an_unknown_timeout_response_is_refused() -> None:
    with pytest.raises(ContractViolation):
        WorkflowTimeout(seconds=10, on_timeout="shrug")


def test_a_timeout_that_compensates_says_so() -> None:
    """A timed-out write may still have applied."""
    assert WorkflowTimeout(seconds=10, on_timeout="compensate").compensates
    assert not WorkflowTimeout(seconds=10).compensates


def test_grace_counts_towards_the_total() -> None:
    assert WorkflowTimeout(seconds=10, grace_seconds=5).total_seconds == 15


# ----------------------------------------------------------------------
# Parallel groups
# ----------------------------------------------------------------------


def test_a_group_of_one_is_refused() -> None:
    with pytest.raises(ParallelGroupTooSmall):
        parallel_group("solo", ["a"])


def test_a_group_listing_a_member_twice_is_refused() -> None:
    with pytest.raises(ContractViolation):
        parallel_group("dup", ["a", "a"])


def test_a_quorum_join_must_say_how_many() -> None:
    with pytest.raises(ContractViolation):
        parallel_group("g", ["a", "b", "c"], join=JoinPolicy.QUORUM)


def test_a_quorum_of_everything_is_an_all_join() -> None:
    with pytest.raises(ContractViolation):
        parallel_group("g", ["a", "b"], join=JoinPolicy.QUORUM, quorum=2)


def test_a_quorum_larger_than_the_group_is_refused() -> None:
    with pytest.raises(ContractViolation):
        parallel_group("g", ["a", "b"], join=JoinPolicy.QUORUM, quorum=5)


def test_max_concurrency_of_one_is_refused() -> None:
    with pytest.raises(ContractViolation):
        parallel_group("g", ["a", "b"], max_concurrency=1)


def test_effective_concurrency_is_capped_by_size() -> None:
    assert parallel_group("g", ["a", "b"], max_concurrency=8).effective_concurrency == 2
    assert parallel_group("g", ["a", "b", "c"]).effective_concurrency == 3


def test_only_an_all_join_waits_for_everything() -> None:
    assert JoinPolicy.ALL.waits_for_everything
    assert JoinPolicy.ANY.may_abandon_members
    assert JoinPolicy.QUORUM.may_abandon_members


# ----------------------------------------------------------------------
# Resume points and compensations
# ----------------------------------------------------------------------


def test_a_resume_point_renders_its_label() -> None:
    assert str(resume_point("checkpoint", "after the snapshot")) == "after the snapshot"
    assert str(resume_point("checkpoint")) == "checkpoint"


def test_a_compensation_rule_cannot_target_itself() -> None:
    from backend.contexts.workflow import compensation

    with pytest.raises(ContractViolation):
        compensation("a", "a")


def test_a_compensation_trigger_must_be_known() -> None:
    from backend.contexts.workflow import compensation

    with pytest.raises(ContractViolation):
        compensation("a", "b", trigger="whenever")


def test_a_timeout_triggered_compensation_is_identifiable() -> None:
    from backend.contexts.workflow import compensation

    assert compensation("a", "b", trigger="on_timeout").triggers_on_timeout
    assert not compensation("a", "b").triggers_on_timeout
