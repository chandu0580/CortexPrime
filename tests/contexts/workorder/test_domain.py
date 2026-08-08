"""Domain invariants: identifiers, states, assumptions, rejections, the aggregate.

Most of these assert a refusal. An aggregate whose tests only demonstrate the
happy path has not been shown to enforce anything.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.workorder.domain import (
    ALLOWED,
    FORBIDDEN,
    TERMINAL_STATES,
    Assumption,
    AssumptionResolution,
    AssumptionId,
    AssumptionSpec,
    BlastRadius,
    DigestMismatch,
    EvidenceRef,
    ImmutableAfterApproval,
    InvalidIdentifier,
    InvalidTransition,
    Priority,
    RejectionGround,
    RejectionType,
    Resolver,
    TerminalState,
    WorkOrderId,
    WorkOrderState,
    is_allowed,
    transition_reason,
)

from tests.contexts.workorder.conftest import make_draft


# ----------------------------------------------------------------------
# Identifiers
# ----------------------------------------------------------------------


def test_identifier_rejects_a_non_ulid():
    with pytest.raises(InvalidIdentifier):
        WorkOrderId("not-a-ulid")


def test_identifier_rejects_a_non_string():
    with pytest.raises(InvalidIdentifier):
        WorkOrderId(12345)  # type: ignore[arg-type]


def test_identifiers_of_different_kinds_are_not_interchangeable():
    """The entire reason these are types rather than strings."""
    work_id = WorkOrderId.new()
    assumption_id = AssumptionId(work_id.value)
    assert work_id != assumption_id
    assert type(work_id) is not type(assumption_id)


def test_identifiers_sort_in_creation_order():
    ids = [WorkOrderId.new() for _ in range(20)]
    assert ids == sorted(ids)


def test_identifier_recovers_its_own_timestamp():
    identifier = WorkOrderId.new()
    assert identifier.created_at_ms > 0


# ----------------------------------------------------------------------
# State machine
# ----------------------------------------------------------------------


def test_every_state_appears_in_the_transition_table():
    """A state absent from ALLOWED would silently be a dead end."""
    assert set(ALLOWED) == set(WorkOrderState)


def test_terminal_states_permit_nothing():
    for state in TERMINAL_STATES:
        assert ALLOWED[state] == frozenset()


def test_spec_tests_precede_implementation():
    assert is_allowed(WorkOrderState.SPEC_TESTS, WorkOrderState.IMPLEMENTATION)
    assert not is_allowed(WorkOrderState.IMPLEMENTATION, WorkOrderState.SPEC_TESTS)


@pytest.mark.parametrize(
    "pair",
    [
        (WorkOrderState.DRAFT, WorkOrderState.ASSIGNED),
        (WorkOrderState.IMPLEMENTATION, WorkOrderState.SPEC_TESTS),
        (WorkOrderState.IMPLEMENTATION, WorkOrderState.VERIFICATION),
        (WorkOrderState.REVIEW, WorkOrderState.READY),
        (WorkOrderState.VERIFICATION, WorkOrderState.MERGED),
    ],
)
def test_forbidden_transitions_carry_their_specific_reason(pair):
    """A generic refusal teaches nothing; these are the ones people attempt."""
    current, requested = pair
    reason = transition_reason(current, requested)
    assert reason is not None
    assert reason == FORBIDDEN[pair]
    assert "may only move to" not in reason


def test_no_agent_may_merge_is_encoded_as_a_transition():
    assert not is_allowed(WorkOrderState.VERIFICATION, WorkOrderState.MERGED)
    assert "human gate" in transition_reason(WorkOrderState.VERIFICATION, WorkOrderState.MERGED)


def test_reapproval_is_forbidden_from_every_governed_state():
    for state in WorkOrderState:
        if state in (WorkOrderState.DRAFT, WorkOrderState.BLOCKED, WorkOrderState.APPROVED):
            continue
        assert not is_allowed(state, WorkOrderState.APPROVED)
        assert "single-use" in transition_reason(state, WorkOrderState.APPROVED)


def test_permitted_transition_has_no_reason():
    assert transition_reason(WorkOrderState.DRAFT, WorkOrderState.APPROVED) is None


# ----------------------------------------------------------------------
# Assumptions
# ----------------------------------------------------------------------


def test_resolution_without_evidence_is_refused():
    assumption = Assumption.create("models carry a tenant column", "grep")
    with pytest.raises(ContractViolation):
        Assumption(
            assumption_id=assumption.assumption_id,
            statement=assumption.statement,
            verification_method=assumption.verification_method,
            resolution=AssumptionResolution.CONFIRMED,
        )


def test_evidence_without_resolution_is_refused():
    assumption = Assumption.create("x", "y")
    with pytest.raises(ContractViolation):
        Assumption(
            assumption_id=assumption.assumption_id,
            statement="x",
            verification_method="y",
            resolution_evidence=EvidenceRef("EV-1"),
        )


def test_unverifiable_still_requires_evidence():
    """'I could not determine' must say what was tried."""
    assumption = Assumption.create("x", "y")
    resolved = assumption.resolve(AssumptionResolution.UNVERIFIABLE, EvidenceRef("EV-1"))
    assert resolved.resolution_evidence is not None


def test_unverifiable_does_not_permit_progress():
    assert not AssumptionResolution.UNVERIFIABLE.permits_progress
    assert not AssumptionResolution.CONTRADICTED.permits_progress
    assert AssumptionResolution.CONFIRMED.permits_progress


def test_re_resolving_is_refused():
    """A second answer to a settled question means one of them is wrong."""
    assumption = Assumption.create("x", "y").resolve(
        AssumptionResolution.CONFIRMED, EvidenceRef("EV-1")
    )
    with pytest.raises(ContractViolation):
        assumption.resolve(AssumptionResolution.CONTRADICTED, EvidenceRef("EV-2"))


# ----------------------------------------------------------------------
# Rejection grounds
# ----------------------------------------------------------------------


def test_constraint_conflict_escalates_to_the_founder():
    """A conflict between a goal and an invariant is a governance decision."""
    assert RejectionType.CONSTRAINT_CONFLICT.resolver is Resolver.FOUNDER


def test_every_other_rejection_resolves_to_the_architect():
    for kind in RejectionType:
        if kind is RejectionType.CONSTRAINT_CONFLICT:
            continue
        assert kind.resolver is Resolver.ARCHITECT


def test_every_rejection_type_states_its_evidence_requirement():
    for kind in RejectionType:
        assert kind.requires_evidence
        assert len(kind.evidence_requirement) > 20
        assert kind.raisers


def test_ground_requires_a_non_blank_condition():
    with pytest.raises(ContractViolation):
        RejectionGround.create("   ", RejectionType.PREMISE_FALSE)


# ----------------------------------------------------------------------
# The aggregate
# ----------------------------------------------------------------------


def test_a_draft_has_no_digest():
    assert make_draft().digest is None


def test_approval_binds_a_digest():
    approved = make_draft().approve()
    assert approved.digest is not None
    approved.verify_digest()


def test_governed_state_without_a_digest_cannot_be_constructed():
    from dataclasses import replace

    with pytest.raises(ContractViolation):
        replace(make_draft(), state=WorkOrderState.ASSIGNED)


def test_changing_a_governed_field_after_approval_is_refused():
    approved = make_draft().approve()
    with pytest.raises(ImmutableAfterApproval):
        approved.with_governed_change(intent="something else")


def test_a_tampered_governed_field_fails_digest_verification():
    """The check that makes approval bind to content rather than to a name."""
    from dataclasses import replace

    approved = make_draft().approve()
    tampered = replace(approved, intent="a different outcome entirely")
    with pytest.raises(DigestMismatch):
        tampered.verify_digest()


def test_priority_change_does_not_invalidate_the_digest():
    """Re-ordering the queue must not require re-approving the work."""
    approved = make_draft().approve()
    reprioritised = approved.reprioritise(Priority.P0)
    reprioritised.verify_digest()


def test_self_dependency_is_structurally_impossible():
    work_order = make_draft()
    from dataclasses import replace

    with pytest.raises(ContractViolation):
        replace(work_order, dependencies=frozenset({work_order.work_id}))


def test_transition_out_of_a_terminal_state_is_refused():
    rejected = make_draft().reject(RejectionType.PREMISE_FALSE, "grep returned nothing")
    with pytest.raises(TerminalState):
        rejected.transition(WorkOrderState.APPROVED)


def test_rejection_requires_detail():
    with pytest.raises(ContractViolation):
        make_draft().reject(RejectionType.PREMISE_FALSE, "   ")


def test_rejected_work_order_carries_its_verdict():
    rejected = make_draft().reject(
        RejectionType.PREMISE_FALSE, "grep tenant_id backend/database/models/ returned nothing"
    )
    assert rejected.state is WorkOrderState.REJECTED
    assert rejected.rejection_type is RejectionType.PREMISE_FALSE
    assert "grep" in rejected.rejection_detail


def test_assumptions_may_not_be_resolved_after_ready():
    """Resolving then would mean it was never actually checked."""
    approved = make_draft().approve()
    assumption_id = approved.assumptions[0].assumption_id
    with pytest.raises(ContractViolation):
        approved.resolve_assumption(
            assumption_id, AssumptionResolution.CONFIRMED, EvidenceRef("EV-1")
        )


def test_blast_radius_expansion_increments_the_version_and_rehashes():
    approved = make_draft().approve()
    expanded = approved.expand_blast_radius(
        BlastRadius.of(["backend/contexts/workorder/**", "tests/contexts/**"])
    )
    assert expanded.version == approved.version + 1
    assert expanded.digest != approved.digest
    expanded.verify_digest()


def test_narrowing_a_blast_radius_is_refused():
    """Already-authorised work must not become retroactively out of scope."""
    approved = make_draft(radius=BlastRadius.of(["backend/a/**", "backend/b/**"])).approve()
    with pytest.raises(ContractViolation):
        approved.expand_blast_radius(BlastRadius.of(["backend/a/**"]))


def test_supersede_refuses_a_second_successor():
    work_order = make_draft().supersede(WorkOrderId.new())
    with pytest.raises(ContractViolation):
        work_order.supersede(WorkOrderId.new())


def test_a_work_order_cannot_supersede_itself():
    work_order = make_draft()
    with pytest.raises(ContractViolation):
        work_order.supersede(work_order.work_id)


def test_transitions_return_new_instances():
    """Immutability: a caller holding the old value must still see the old state."""
    draft = make_draft()
    approved = draft.approve()
    assert draft.state is WorkOrderState.DRAFT
    assert approved.state is WorkOrderState.APPROVED
    assert draft is not approved
