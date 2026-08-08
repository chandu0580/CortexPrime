"""Application service and repository.

Integration-level: real service, real repository, real storage guard, real
execution contexts. Nothing mocked -- the guard's refusals are part of what is
being tested, and a mock would return whatever the test wanted.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.workorder import (
    ApproveWorkOrder,
    AssumptionSpec,
    BlastRadius,
    CheckBlastRadiusConflicts,
    DraftWorkOrder,
    ExpandBlastRadius,
    GetWorkOrder,
    InMemoryWorkOrderRepository,
    ListWorkOrders,
    Priority,
    RejectionType,
    RejectWorkOrder,
    Reprioritise,
    ResolveAssumption,
    TransitionWorkOrder,
    WorkOrderState,
)
from backend.contexts.workorder.domain.assumption import AssumptionResolution
from backend.contexts.workorder.domain.errors import (
    DuplicateWorkOrder,
    ValidationFailed,
    WorkOrderNotFound,
)
from backend.contexts.workorder.infrastructure.persistence import from_record, to_record
from backend.platform.storage import MissingExecutionContext

from tests.contexts.workorder.conftest import make_draft


def _draft_command(**overrides) -> DraftWorkOrder:
    fields = dict(
        intent="The storage boundary refuses operations without an ExecutionContext",
        acceptance_criteria=("A read with no context is refused",),
        blast_radius=BlastRadius.of(["backend/contexts/workorder/**"]),
        adr_references=("ADR-018",),
        evidence=("EV-1",),
        constraints=("I6",),
        definition_of_done=("the guard refuses an unattributed write",),
        assumptions=(AssumptionSpec("Models carry a tenant column", "grep tenant_id"),),
    )
    fields.update(overrides)
    return DraftWorkOrder(**fields)


# ----------------------------------------------------------------------
# The repository requires a context
# ----------------------------------------------------------------------


def test_every_repository_method_refuses_a_missing_context(repository):
    """TENANT-REPOSITORY-CONTEXT, enforced at runtime as well as statically."""
    from backend.contexts.workorder.domain import WorkOrderId

    work_order = make_draft()
    with pytest.raises(MissingExecutionContext):
        repository.save(None, work_order)
    with pytest.raises(MissingExecutionContext):
        repository.find(None, work_order.work_id)
    with pytest.raises(MissingExecutionContext):
        repository.list_active(None)
    with pytest.raises(MissingExecutionContext):
        repository.list_by_state(None, WorkOrderState.DRAFT)
    with pytest.raises(MissingExecutionContext):
        repository.dependency_graph(None)
    with pytest.raises(MissingExecutionContext):
        repository.versions(None, WorkOrderId.new())


def test_a_tenant_context_does_not_see_another_tenants_work_orders(repository, tenant_context):
    from backend.platform.context import ExecutionContext
    from backend.platform.context.identity import IdentityContext

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    repository.save(tenant_context, make_draft())

    assert len(repository.list_active(tenant_context)) == 1
    assert repository.list_active(other) == ()


def test_a_platform_internal_context_sees_every_tenant(repository, tenant_context, context):
    repository.save(tenant_context, make_draft())
    assert len(repository.list_active(context)) == 1


def test_saving_the_same_version_twice_is_refused(repository, context):
    """A version is immutable: its digest is what an approval binds to."""
    work_order = make_draft()
    repository.save(context, work_order)
    with pytest.raises(DuplicateWorkOrder):
        repository.save(context, work_order)


def test_get_of_an_unknown_work_order_raises(repository, context):
    from backend.contexts.workorder.domain import WorkOrderId

    with pytest.raises(WorkOrderNotFound):
        repository.get(context, WorkOrderId.new())


# ----------------------------------------------------------------------
# Record round trip
# ----------------------------------------------------------------------


def test_record_round_trip_preserves_everything():
    original = make_draft().approve()
    restored = from_record(to_record(original, tenant_id="tenant-a"))
    assert restored == original
    restored.verify_digest()


def test_round_trip_preserves_a_resolved_assumption():
    approved = make_draft().approve()
    working = approved.transition(WorkOrderState.ASSIGNED).transition(WorkOrderState.SPEC_TESTS)
    from backend.contexts.workorder.domain import EvidenceRef

    resolved = working.resolve_assumption(
        working.assumptions[0].assumption_id,
        AssumptionResolution.CONFIRMED,
        EvidenceRef("EV-checked"),
    )
    assert from_record(to_record(resolved, tenant_id="t")) == resolved


def test_an_unknown_record_schema_is_refused():
    """Refusing beats guessing at a shape this build does not know."""
    record = to_record(make_draft(), tenant_id="t")
    record["schema_version"] = 999
    with pytest.raises(ContractViolation):
        from_record(record)


def test_a_record_requires_a_tenant():
    with pytest.raises(ContractViolation):
        to_record(make_draft(), tenant_id="   ")


# ----------------------------------------------------------------------
# Service commands
# ----------------------------------------------------------------------


def test_draft_persists_and_emits(service, context, repository):
    result = service.draft(context, _draft_command())
    assert result.work_order.state is WorkOrderState.DRAFT
    assert [e.EVENT_TYPE for e in result.events] == ["engineering.work_order.drafted"]
    assert len(repository) == 1


def test_approve_validates_before_transitioning(service, context):
    """Approving first and validating after would bind a digest to unchecked content."""
    drafted = service.draft(context, _draft_command(evidence=("EV-NONEXISTENT",)))
    with pytest.raises(ValidationFailed) as caught:
        service.approve(
            context, ApproveWorkOrder(work_id=str(drafted.work_order.work_id), approved_by="founder")
        )
    assert any(f.rule == "V4" for f in caught.value.findings)

    # And the WorkOrder is still a Draft.
    stored = service.get(context, GetWorkOrder(work_id=str(drafted.work_order.work_id)))
    assert stored.state is WorkOrderState.DRAFT


def test_approve_binds_a_digest_and_emits_both_events(service, context):
    drafted = service.draft(context, _draft_command())
    approved = service.approve(
        context, ApproveWorkOrder(work_id=str(drafted.work_order.work_id), approved_by="founder")
    )
    assert approved.work_order.digest is not None
    assert {e.EVENT_TYPE for e in approved.events} == {
        "engineering.work_order.approved",
        "engineering.work_order.state_changed",
    }


def test_transition_emits_a_digest_validation(service, context):
    drafted = service.draft(context, _draft_command())
    work_id = str(drafted.work_order.work_id)
    service.approve(context, ApproveWorkOrder(work_id=work_id, approved_by="founder"))

    result = service.transition(
        context,
        TransitionWorkOrder(work_id=work_id, to_state=WorkOrderState.ASSIGNED, actor="orchestrator"),
    )
    digest_events = [e for e in result.events if e.EVENT_TYPE.endswith("digest_validated")]
    assert len(digest_events) == 1
    assert digest_events[0].valid is True


def test_the_full_lifecycle_reaches_closed(service, context):
    drafted = service.draft(context, _draft_command())
    work_id = str(drafted.work_order.work_id)
    service.approve(context, ApproveWorkOrder(work_id=work_id, approved_by="founder"))

    for state in (
        WorkOrderState.ASSIGNED,
        WorkOrderState.SPEC_TESTS,
        WorkOrderState.IMPLEMENTATION,
        WorkOrderState.REVIEW,
        WorkOrderState.VERIFICATION,
        WorkOrderState.READY,
        WorkOrderState.MERGED,
        WorkOrderState.CLOSED,
    ):
        result = service.transition(
            context, TransitionWorkOrder(work_id=work_id, to_state=state, actor="founder")
        )
    assert result.work_order.state is WorkOrderState.CLOSED


def test_reject_records_the_verdict_and_its_resolver(service, context):
    drafted = service.draft(context, _draft_command())
    result = service.reject(
        context,
        RejectWorkOrder(
            work_id=str(drafted.work_order.work_id),
            rejection_type=RejectionType.PREMISE_FALSE,
            detail="grep tenant_id backend/database/models/ returned nothing",
            raised_by="implementer",
        ),
    )
    assert result.work_order.state is WorkOrderState.REJECTED
    assert result.work_order.rejection_type is RejectionType.PREMISE_FALSE


def test_reprioritise_does_not_break_the_digest(service, context):
    drafted = service.draft(context, _draft_command())
    work_id = str(drafted.work_order.work_id)
    service.approve(context, ApproveWorkOrder(work_id=work_id, approved_by="founder"))

    result = service.reprioritise(
        context, Reprioritise(work_id=work_id, priority=Priority.P0, actor="founder")
    )
    result.work_order.verify_digest()
    assert result.work_order.priority is Priority.P0


# ----------------------------------------------------------------------
# Blast-radius conflicts
# ----------------------------------------------------------------------


def _assigned(service, context, radius):
    drafted = service.draft(context, _draft_command(blast_radius=radius))
    work_id = str(drafted.work_order.work_id)
    service.approve(context, ApproveWorkOrder(work_id=work_id, approved_by="founder"))
    service.transition(
        context,
        TransitionWorkOrder(work_id=work_id, to_state=WorkOrderState.ASSIGNED, actor="orchestrator"),
    )
    return work_id


def test_an_assigned_work_order_holds_its_radius(service, context):
    _assigned(service, context, BlastRadius.of(["backend/platform/**"]))
    conflicts = service.conflicts(
        context, CheckBlastRadiusConflicts(radius=BlastRadius.of(["backend/platform/storage/**"]))
    )
    assert len(conflicts) == 1
    assert conflicts[0].state == "assigned"


def test_an_approved_but_unassigned_work_order_holds_nothing(service, context):
    """The lock is acquired at Assigned, not at Approved."""
    drafted = service.draft(context, _draft_command(blast_radius=BlastRadius.of(["backend/x/**"])))
    service.approve(
        context, ApproveWorkOrder(work_id=str(drafted.work_order.work_id), approved_by="founder")
    )
    assert service.conflicts(
        context, CheckBlastRadiusConflicts(radius=BlastRadius.of(["backend/x/**"]))
    ) == ()


def test_a_disjoint_radius_does_not_conflict(service, context):
    _assigned(service, context, BlastRadius.of(["backend/platform/**"]))
    assert service.conflicts(
        context, CheckBlastRadiusConflicts(radius=BlastRadius.of(["backend/contexts/**"]))
    ) == ()


def test_a_rejected_work_order_releases_its_lock(service, context):
    work_id = _assigned(service, context, BlastRadius.of(["backend/platform/**"]))
    # Rejection is not reachable from Assigned -- the Constitution's table allows
    # it from Draft, SpecTests, Implementation, Review, and Verification only.
    service.transition(
        context,
        TransitionWorkOrder(work_id=work_id, to_state=WorkOrderState.SPEC_TESTS, actor="author"),
    )
    service.reject(
        context,
        RejectWorkOrder(
            work_id=work_id,
            rejection_type=RejectionType.SCOPE_INDIVISIBLE,
            detail="fitness_functions.py:38 imports state_rules",
            raised_by="implementer",
        ),
    )
    assert service.conflicts(
        context, CheckBlastRadiusConflicts(radius=BlastRadius.of(["backend/platform/**"]))
    ) == ()


def test_expansion_is_refused_when_it_would_collide(service, context):
    _assigned(service, context, BlastRadius.of(["backend/platform/**"]))
    mine = _assigned(service, context, BlastRadius.of(["backend/contexts/**"]))

    with pytest.raises(ContractViolation) as caught:
        service.expand_blast_radius(
            context,
            ExpandBlastRadius(
                work_id=mine,
                radius=BlastRadius.of(["backend/contexts/**", "backend/platform/storage/**"]),
                justification="the change turned out to need the guard too",
                requested_by="implementer",
            ),
        )
    assert "conflicts with active WorkOrder" in str(caught.value)


def test_expansion_creates_a_new_version(service, context, repository):
    work_id = _assigned(service, context, BlastRadius.of(["backend/contexts/**"]))
    result = service.expand_blast_radius(
        context,
        ExpandBlastRadius(
            work_id=work_id,
            radius=BlastRadius.of(["backend/contexts/**", "tests/contexts/**"]),
            justification="tests live outside the original radius",
            requested_by="implementer",
        ),
    )
    assert result.work_order.version == 2
    assert len(service.versions(context, work_id)) == 2


# ----------------------------------------------------------------------
# Assumption resolution through the service
# ----------------------------------------------------------------------


def test_a_contradicted_assumption_leads_to_premise_false(service, context):
    """The PR-10 scenario, end to end."""
    drafted = service.draft(context, _draft_command())
    work_id = str(drafted.work_order.work_id)
    service.approve(context, ApproveWorkOrder(work_id=work_id, approved_by="founder"))
    service.transition(
        context,
        TransitionWorkOrder(work_id=work_id, to_state=WorkOrderState.ASSIGNED, actor="orchestrator"),
    )
    working = service.transition(
        context,
        TransitionWorkOrder(work_id=work_id, to_state=WorkOrderState.SPEC_TESTS, actor="author"),
    )

    assumption_id = str(working.work_order.assumptions[0].assumption_id)
    resolved = service.resolve_assumption(
        context,
        ResolveAssumption(
            work_id=work_id,
            assumption_id=assumption_id,
            resolution=AssumptionResolution.CONTRADICTED,
            evidence="EV-grep-empty",
            resolved_by="implementer",
        ),
    )
    assert resolved.work_order.blocking_assumptions

    rejected = service.reject(
        context,
        RejectWorkOrder(
            work_id=work_id,
            rejection_type=RejectionType.PREMISE_FALSE,
            detail="grep tenant_id backend/database/models/ returned nothing",
            raised_by="implementer",
        ),
    )
    assert rejected.work_order.state is WorkOrderState.REJECTED
