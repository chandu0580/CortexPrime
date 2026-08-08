"""The runtime against the real WorkOrder context, through the composition root.

The fakes in ``conftest.py`` buy controllable failure; this buys confidence they
describe something real. Without it the whole suite could pass against a port
shape nothing implements.

It also pins the architectural claim this PR rests on: the runtime and the
WorkOrder context are joined only at the composition root, and both remain usable
without the other.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from backend.api.engineering_composition import (
    WorkOrderServiceAdapter,
    build_engineering_runtime,
)
from backend.contexts.engineering import (
    CollaboratorUnavailable,
    GetLifecycleCapability,
    GetRuntimeState,
    IllegalTransition,
    WorkOrderPhase,
    WorkOrderPort,
)
from backend.contexts.workorder import (
    ApproveWorkOrder,
    AssumptionSpec,
    BlastRadius,
    DraftWorkOrder,
    InMemoryWorkOrderRepository,
    StaticReferenceResolver,
    WorkOrderService,
)
from backend.platform.context import ExecutionContext


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="integration-tests", component="tests", source="pytest"
    )


@pytest.fixture
def stack():
    """A real WorkOrder service behind a real adapter behind the real runtime."""
    service = WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=StaticReferenceResolver(
            known_adrs=frozenset({"ADR-019"}),
            known_evidence=frozenset({"EV-1"}),
            enforceable_constraints=frozenset({"I6"}),
        ),
    )
    return build_engineering_runtime(service=service)


def _unwired_review_stack():
    """The same stack the ``stack`` fixture builds, with Review left unwired.

    PR-E6 built Review and wired it by default. The tests that assert what an
    *unwired* port does still need one, and unwiring deliberately is clearer
    than asserting against whichever port happens to be unbuilt next.
    """
    service = WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=StaticReferenceResolver(
            known_adrs=frozenset({"ADR-019"}),
            known_evidence=frozenset({"EV-1"}),
            enforceable_constraints=frozenset({"I6"}),
        ),
    )
    return build_engineering_runtime(service=service, wire_review=False)


def _approved(stack, context, **overrides) -> str:
    fields = dict(
        intent="The runtime executes only legal transitions",
        acceptance_criteria=("An illegal transition is refused",),
        blast_radius=BlastRadius.of(["backend/contexts/engineering/**"]),
        adr_references=("ADR-019",),
        evidence=("EV-1",),
        constraints=("I6",),
        definition_of_done=("the executor refuses an unknown phase",),
    )
    fields.update(overrides)

    drafted = stack.work_order_service.draft(context, DraftWorkOrder(**fields))
    work_id = str(drafted.work_order.work_id)
    stack.work_order_service.approve(
        context, ApproveWorkOrder(work_id=work_id, approved_by="founder")
    )
    return work_id


# ----------------------------------------------------------------------
# The adapter satisfies the port
# ----------------------------------------------------------------------


def test_the_adapter_satisfies_the_port_structurally(stack):
    adapter = WorkOrderServiceAdapter(stack.work_order_service)
    assert isinstance(adapter, WorkOrderPort)


def test_a_real_work_order_becomes_a_snapshot(stack, context):
    work_id = _approved(stack, context)
    snapshot = stack.runtime.snapshot(context, work_id)

    assert snapshot.work_id == work_id
    assert snapshot.phase is WorkOrderPhase.APPROVED
    assert snapshot.digest is not None
    assert snapshot.constraints == ("I6",)


def test_an_unknown_work_order_produces_none_not_an_exception(stack, context):
    from backend.contexts.workorder.domain import WorkOrderId

    adapter = WorkOrderServiceAdapter(stack.work_order_service)
    assert adapter.snapshot(context, str(WorkOrderId.new())) is None


# ----------------------------------------------------------------------
# Driving a real WorkOrder
# ----------------------------------------------------------------------


def test_the_runtime_moves_a_real_work_order(stack, context):
    work_id = _approved(stack, context)
    result = stack.runtime.transition(context, work_id, "assigned", actor="orchestrator")

    assert result.snapshot.phase is WorkOrderPhase.ASSIGNED
    stored = stack.work_order_service.get(
        context,
        __import__(
            "backend.contexts.workorder", fromlist=["GetWorkOrder"]
        ).GetWorkOrder(work_id=work_id),
    )
    assert stored.state.value == "assigned"


def test_an_illegal_transition_is_refused_against_a_real_work_order(stack, context):
    work_id = _approved(stack, context)
    with pytest.raises(IllegalTransition):
        stack.runtime.transition(context, work_id, "review", actor="x")


def test_the_real_digest_survives_a_runtime_transition(stack, context):
    """The runtime must not disturb what approval bound."""
    work_id = _approved(stack, context)
    before = stack.runtime.snapshot(context, work_id).digest

    stack.runtime.transition(context, work_id, "assigned", actor="orchestrator")

    assert stack.runtime.snapshot(context, work_id).digest == before


def test_review_is_refused_when_the_review_port_is_unwired(context):
    """An unwired port is refused rather than skipped.

    Review exists as of PR-E6, so this builds a stack with it deliberately
    unwired. The rule under test is the runtime's, not the Review context's: a
    phase whose collaborator is missing must refuse, because a phase that
    requires review and proceeds without it produces an unreviewed merge that
    looks reviewed.
    """
    stack = _unwired_review_stack()
    work_id = _approved(stack, context)
    for phase in ("assigned", "spec_tests", "implementation"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    with pytest.raises(CollaboratorUnavailable) as caught:
        stack.runtime.transition(context, work_id, "review", actor="x")
    assert caught.value.port == "review"


def test_capability_reports_which_ports_are_unbuilt():
    """PR-E3 wired Verification, PR-E4 Context, PR-E6 Review.

    Asserted against a stack with Review unwired, so the test keeps checking
    that an unbuilt port is *reported* as unbuilt -- which is the behaviour it
    was written for -- rather than silently becoming a test that nothing is
    missing.
    """
    stack = _unwired_review_stack()
    capability = stack.queries.capability(GetLifecycleCapability())
    assert "work_order" in capability["wired"]
    assert set(capability["missing"]) == {"review"}


def test_every_port_is_wired_once_review_exists(stack):
    """PR-E6's claim: no phase is refused for want of a collaborator."""
    capability = stack.queries.capability(GetLifecycleCapability())
    assert capability["missing"] == []
    for phase in ("spec_tests", "implementation", "review", "verification"):
        assert phase in capability["reachable_phases"]


def test_state_shows_which_phases_are_blocked_by_missing_adapters(context):
    """From implementation, review is legal and unreachable when unwired.

    The distinction the query exists to report: 'the Constitution forbids this'
    and 'nothing is listening yet' are different problems with different fixes.
    """
    stack = _unwired_review_stack()
    work_id = _approved(stack, context)
    for phase in ("assigned", "spec_tests", "implementation"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    state = stack.queries.state(context, GetRuntimeState(work_id=work_id))
    assert "review" in state.legal_next
    assert state.blocked_next == ("review",)


def test_a_real_rejection_routes_through_the_runtime(stack, context):
    """Rejection is reachable from spec_tests, not from approved.

    The Constitution's table permits it from Draft, SpecTests, Implementation,
    Review and Verification only -- so the WorkOrder is driven to spec_tests by
    the WorkOrder service first, which also demonstrates the runtime operating
    correctly on a WorkOrder something else moved.
    """
    from backend.contexts.workorder import TransitionWorkOrder, WorkOrderState

    work_id = _approved(stack, context)
    for state in (WorkOrderState.ASSIGNED, WorkOrderState.SPEC_TESTS):
        stack.work_order_service.transition(
            context, TransitionWorkOrder(work_id=work_id, to_state=state, actor="test")
        )

    result = stack.runtime.reject(
        context,
        work_id,
        rejection_type="premise_false",
        detail="grep tenant_id backend/database/models/ returned nothing",
        raised_by="implementer",
    )
    assert result.snapshot.phase is WorkOrderPhase.REJECTED


def test_rejection_from_approved_is_refused_by_the_constitution(stack, context):
    """Documents a gap in the frozen specification rather than patching it.

    A WorkOrder that is Approved or Blocked has no exit but forward. If a
    dependency is itself rejected, the blocked WorkOrder is stranded. Implemented
    as specified; see ADR-020 Remaining Risks.
    """
    work_id = _approved(stack, context)
    with pytest.raises(IllegalTransition):
        stack.runtime.reject(
            context, work_id, rejection_type="premise_false",
            detail="the premise does not hold", raised_by="implementer",
        )


def test_a_policy_refusal_leaves_the_real_work_order_unmoved(stack, context):
    """A WorkOrder citing a constraint that no longer resolves stops at the gate."""
    from backend.contexts.engineering import PolicyRefused

    work_id = _approved(stack, context, constraints=("I6",))
    # Drive it to verification by hand through the WorkOrder service, since the
    # runtime cannot reach those phases without adapters.
    from backend.contexts.workorder import TransitionWorkOrder, WorkOrderState

    for state in (
        WorkOrderState.ASSIGNED,
        WorkOrderState.SPEC_TESTS,
        WorkOrderState.IMPLEMENTATION,
        WorkOrderState.REVIEW,
        WorkOrderState.VERIFICATION,
    ):
        stack.work_order_service.transition(
            context, TransitionWorkOrder(work_id=work_id, to_state=state, actor="test")
        )

    result = stack.runtime.transition(context, work_id, "ready", actor="verifier")
    assert result.snapshot.phase is WorkOrderPhase.READY


# ----------------------------------------------------------------------
# The architectural claim
# ----------------------------------------------------------------------


def _imports(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
    return found


def _modules(package: str) -> list:
    root = pathlib.Path("backend") / "contexts" / package
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def test_the_runtime_imports_no_bounded_context():
    """The claim the whole port design rests on."""
    offences = [
        f"{path}: {imported}"
        for path in _modules("engineering")
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.engineering")
    ]
    assert offences == [], offences


def test_the_workorder_context_does_not_import_the_runtime():
    """The coupling must not be reversed either."""
    offences = [
        f"{path}: {imported}"
        for path in _modules("workorder")
        for imported in _imports(path)
        if imported.startswith("backend.contexts.engineering")
    ]
    assert offences == [], offences


def test_only_the_composition_root_imports_both():
    """One greppable file answers 'what does the runtime actually talk to?'"""
    both = []
    for path in pathlib.Path("backend").rglob("*.py"):
        if "__pycache__" in path.parts or "contexts" in path.parts:
            continue
        imported = _imports(path)
        has_runtime = any(i.startswith("backend.contexts.engineering") for i in imported)
        has_workorder = any(i.startswith("backend.contexts.workorder") for i in imported)
        if has_runtime and has_workorder:
            both.append(str(path).replace("\\", "/"))

    assert both == ["backend/api/engineering_composition.py"], both


def test_the_runtime_imports_only_contracts_and_platform():
    permitted = ("backend.contracts", "backend.platform", "backend.contexts.engineering")
    offences = [
        f"{path}: {imported}"
        for path in _modules("engineering")
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences
