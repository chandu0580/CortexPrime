"""The Intent aggregate: capture, expansion, validation, approval, digest.

Two rules carry the weight here:

* **expansion invalidates validation** -- a validated intent that gained a
  constraint is a statement about a document that no longer exists;
* **approval seals the mandate** -- planning acts on it, so an intent that
  changed afterwards would mean the plan was built from something nobody
  approved.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.intent import (
    ARTIFACT_KIND,
    ConstraintKind,
    DigestMismatch,
    DigestNotComputed,
    DuplicateConstraint,
    Environment,
    GOVERNED_FIELDS,
    IllegalIntentTransition,
    ImpactLevel,
    IncompleteIntent,
    Intent,
    IntentApprovedError,
    IntentId,
    IntentIsSuperseded,
    IntentOrigin,
    IntentPriority,
    IntentStatus,
    OutcomeKind,
    REQUIRED_ELEMENTS,
    RiskAppetite,
    UnknownConstraint,
    UnknownCriterion,
    capture_intent,
    constraint,
    criterion,
    objective,
    risk,
    scope,
)
from backend.platform.context import ExecutionContext

CONTEXT = ExecutionContext.platform_internal(
    reason="intent-domain-tests", component="tests", source="pytest"
)


def _captured(**overrides) -> Intent:
    fields = dict(
        stated_goal="Our AWS bill is out of control, cut it",
        requested_by=CONTEXT.security_context,
        title="Reduce AWS cost",
    )
    fields.update(overrides)
    return capture_intent(**fields)


def _complete(**overrides) -> Intent:
    """An intent with all six elements, ready to validate."""
    intent = _captured(**overrides)
    intent = intent.set_objective(
        objective("Cut monthly AWS spend by 20%", OutcomeKind.REDUCE, subject="aws")
    )
    intent = intent.set_scope(scope(["ec2", "rds"], environments=(Environment.STAGING,)))
    intent = intent.add_constraint(
        constraint(ConstraintKind.BUDGET, "spend cap on the work", limit="$500")
    )
    intent = intent.add_success_criterion(
        criterion(
            "monthly spend drops 20%",
            "AWS Cost Explorer month-over-month",
            threshold="-20%",
            baseline="Jul 2026: $42k",
        )
    )
    return intent.set_priority(IntentPriority.ELEVATED)


# ----------------------------------------------------------------------
# Capture
# ----------------------------------------------------------------------


def test_capture_keeps_the_requesters_own_words() -> None:
    """Storing only an interpretation makes it impossible to audit whether the
    mandate matches what was asked for."""
    intent = _captured()
    assert intent.stated_goal == "Our AWS bill is out of control, cut it"
    assert intent.status is IntentStatus.DRAFT


def test_a_captured_intent_carries_a_tenant_scoped_security_context() -> None:
    """BC-9: every cross-context message carries one. Non-negotiable."""
    assert _captured().raw.requested_by == CONTEXT.security_context


def test_a_captured_intent_has_no_structure_yet() -> None:
    """Capturing the sentence first is deliberate -- inventing the constraints on
    the requester's behalf would produce boundaries that look decided."""
    intent = _captured()
    assert intent.objective is None
    assert intent.constraints == ()
    assert intent.scope is None
    assert intent.success_criteria == ()
    assert not intent.is_complete


def test_the_missing_elements_are_named() -> None:
    missing = set(_captured().missing_elements)
    assert missing == {"objective", "constraints", "scope", "success criteria"}
    assert missing <= set(REQUIRED_ELEMENTS)


def test_a_derived_intent_must_name_its_source() -> None:
    with pytest.raises(ContractViolation):
        _captured(origin=IntentOrigin.DERIVED)


def test_a_derived_intent_with_a_source_is_accepted() -> None:
    derived = _captured(origin=IntentOrigin.DERIVED, derived_from="INT-1")
    assert derived.metadata.derived_from == "INT-1"


def test_an_intent_must_have_a_goal_and_a_title() -> None:
    with pytest.raises(ContractViolation):
        _captured(stated_goal="   ")
    with pytest.raises(ContractViolation):
        _captured(title="  ")


# ----------------------------------------------------------------------
# Expansion
# ----------------------------------------------------------------------


def test_each_expansion_is_counted() -> None:
    intent = _captured().set_objective(objective("do a thing"))
    assert intent.expansion_count == 1
    assert intent.set_priority(IntentPriority.URGENT).expansion_count == 2


def test_expanding_a_validated_intent_returns_it_to_draft() -> None:
    """The thing that was validated is no longer the thing on record."""
    validated = _complete().validate()
    assert validated.status is IntentStatus.VALIDATED

    expanded = validated.add_constraint(
        constraint(ConstraintKind.SAFETY, "do not touch the settlement job")
    )
    assert expanded.status is IntentStatus.DRAFT
    assert expanded.validated_at is None


def test_expanding_a_draft_leaves_it_a_draft() -> None:
    intent = _complete()
    assert intent.status is IntentStatus.DRAFT
    assert intent.set_priority(IntentPriority.URGENT).status is IntentStatus.DRAFT


def test_removing_a_constraint_counts_as_an_expansion() -> None:
    """Dropping a boundary widens the mandate, so it invalidates the check."""
    validated = _complete().validate()
    target = validated.constraints[0].constraint_id

    widened = validated.remove_constraint(target)
    assert widened.status is IntentStatus.DRAFT
    assert widened.constraints == ()


def test_removing_an_unknown_constraint_is_refused() -> None:
    from backend.contexts.intent import ConstraintId

    with pytest.raises(UnknownConstraint):
        _complete().remove_constraint(ConstraintId.new())


def test_removing_an_unknown_criterion_is_refused() -> None:
    from backend.contexts.intent import CriterionId

    with pytest.raises(UnknownCriterion):
        _complete().remove_success_criterion(CriterionId.new())


def test_the_same_constraint_twice_is_refused() -> None:
    intent = _complete()
    duplicate = constraint(ConstraintKind.BUDGET, "spend cap on the work", limit="$500")
    with pytest.raises(DuplicateConstraint):
        intent.add_constraint(duplicate)


def test_the_same_criterion_twice_is_refused() -> None:
    intent = _complete()
    with pytest.raises(ContractViolation):
        intent.add_success_criterion(
            criterion("monthly spend drops 20%", "some other measure")
        )


def test_acknowledging_a_risk_is_an_expansion() -> None:
    intent = _complete()
    acknowledged = intent.acknowledge_risk(
        risk("rightsizing may throttle batch jobs", ImpactLevel.MEDIUM)
    )
    assert len(acknowledged.acknowledged_risks) == 1
    assert acknowledged.expansion_count == intent.expansion_count + 1


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


def test_validating_an_incomplete_intent_is_refused_and_names_what_is_missing() -> None:
    with pytest.raises(IncompleteIntent) as caught:
        _captured().validate()
    assert set(caught.value.missing) == {
        "objective",
        "constraints",
        "scope",
        "success criteria",
    }


def test_a_complete_intent_validates() -> None:
    validated = _complete().validate()
    assert validated.status is IntentStatus.VALIDATED
    assert validated.validated_at is not None


def test_an_incomplete_intent_cannot_be_assembled_as_validated() -> None:
    """The refusal holds for a record built directly, which is the path replay takes."""
    captured = _captured()
    with pytest.raises(IncompleteIntent):
        dataclasses.replace(captured, status=IntentStatus.VALIDATED)


def test_a_validated_intent_is_not_yet_planable() -> None:
    """Coherent is not the same as authorised."""
    validated = _complete().validate()
    assert not validated.is_planable
    assert validated.approve("cfo").is_planable


# ----------------------------------------------------------------------
# Approval
# ----------------------------------------------------------------------


def test_approving_seals_the_mandate_and_binds_a_digest() -> None:
    approved = _complete().validate().approve("cfo")
    assert approved.status is IntentStatus.APPROVED
    assert approved.digest
    approved.verify_digest()


def test_approving_a_draft_is_refused_with_the_argument() -> None:
    from backend.contexts.intent import refusal_reason

    with pytest.raises(IllegalIntentTransition):
        _complete().approve("cfo")
    reason = refusal_reason(IntentStatus.DRAFT, IntentStatus.APPROVED)
    assert "validated before it is approved" in reason


def test_an_approval_must_name_who_gave_it() -> None:
    with pytest.raises(ContractViolation):
        _complete().validate().approve("   ")


def test_an_approved_intent_without_a_digest_cannot_exist() -> None:
    approved = _complete().validate().approve("cfo")
    with pytest.raises(ContractViolation):
        dataclasses.replace(approved, digest=None)


def test_an_approved_intent_must_name_its_approver() -> None:
    approved = _complete().validate().approve("cfo")
    with pytest.raises(ContractViolation):
        dataclasses.replace(approved, approved_by=None)


_MUTATIONS = {
    "set_objective": lambda i: i.set_objective(objective("something else")),
    "set_scope": lambda i: i.set_scope(scope(["other"])),
    "set_priority": lambda i: i.set_priority(IntentPriority.CRITICAL),
    "set_risk_appetite": lambda i: i.set_risk_appetite(RiskAppetite.TOLERANT),
    "add_constraint": lambda i: i.add_constraint(
        constraint(ConstraintKind.SAFETY, "late boundary")
    ),
    "remove_constraint": lambda i: i.remove_constraint(i.constraints[0].constraint_id),
    "add_success_criterion": lambda i: i.add_success_criterion(
        criterion("late criterion", "some measure")
    ),
    "remove_success_criterion": lambda i: i.remove_success_criterion(
        i.success_criteria[0].criterion_id
    ),
    "acknowledge_risk": lambda i: i.acknowledge_risk(risk("late risk")),
    "validate": lambda i: i.validate(),
    "approve": lambda i: i.approve("someone-else"),
    "reject": lambda i: i.reject("changed my mind"),
}


@pytest.mark.parametrize("name", sorted(_MUTATIONS))
def test_every_mutation_refuses_on_an_approved_intent(name: str) -> None:
    approved = _complete().validate().approve("cfo")
    with pytest.raises(IntentApprovedError):
        _MUTATIONS[name](approved)


def test_every_mutation_is_covered_by_the_immutability_test() -> None:
    """Fails if a mutation is added to the aggregate without an entry above."""
    exposed = {
        name
        for name in dir(Intent)
        if not name.startswith("_")
        and callable(getattr(Intent, name))
        and name
        not in {
            "compute_digest",
            "digest_payload",
            "verify_digest",
            "constraint",
            "criterion",
            "permitted_transitions",
            "supersede",
            "to_dict",
            "from_dict",
            "contract_name",
            "contract_version",
        }
    }
    assert exposed == set(_MUTATIONS), exposed.symmetric_difference(set(_MUTATIONS))


# ----------------------------------------------------------------------
# Rejection and supersession
# ----------------------------------------------------------------------


def test_rejecting_must_say_why() -> None:
    """An unexplained refusal produces the same intent again."""
    with pytest.raises(ContractViolation):
        _captured().reject("   ")


def test_a_rejected_intent_records_its_reason() -> None:
    rejected = _captured().reject("the objective duplicates INT-4")
    assert rejected.status is IntentStatus.REJECTED
    assert rejected.rejection_reason == "the objective duplicates INT-4"


def test_a_rejected_intent_cannot_be_reopened() -> None:
    from backend.contexts.intent import refusal_reason

    rejected = _captured().reject("no")
    assert "cites it" in refusal_reason(IntentStatus.REJECTED, IntentStatus.DRAFT)
    with pytest.raises(IntentApprovedError):
        rejected.set_priority(IntentPriority.URGENT)


def test_superseding_is_permitted_on_an_approved_intent() -> None:
    """It changes whether the intent is current, not what it said."""
    approved = _complete().validate().approve("cfo")
    successor = IntentId.new()
    superseded = approved.supersede(successor)

    assert superseded.status is IntentStatus.SUPERSEDED
    assert superseded.superseded_by == successor
    superseded.verify_digest()


def test_a_superseded_intent_refuses_mutations_with_its_own_error() -> None:
    superseded = _captured().supersede(IntentId.new())
    with pytest.raises(IntentIsSuperseded):
        superseded.set_priority(IntentPriority.URGENT)


def test_an_intent_cannot_supersede_itself() -> None:
    intent = _captured()
    with pytest.raises(ContractViolation):
        intent.supersede(intent.intent_id)


def test_an_intent_cannot_be_superseded_twice() -> None:
    superseded = _captured().supersede(IntentId.new())
    with pytest.raises(ContractViolation):
        superseded.supersede(IntentId.new())


# ----------------------------------------------------------------------
# Digest
# ----------------------------------------------------------------------


def test_verifying_an_unapproved_intent_says_so_rather_than_passing() -> None:
    with pytest.raises(DigestNotComputed):
        _complete().verify_digest()


def test_tampering_with_a_governed_field_is_caught() -> None:
    approved = _complete().validate().approve("cfo")
    tampered = dataclasses.replace(approved, priority=IntentPriority.CRITICAL)
    with pytest.raises(DigestMismatch):
        tampered.verify_digest()


def test_the_digest_covers_the_governed_fields_and_nothing_else() -> None:
    payload = _complete().validate().approve("cfo").digest_payload()
    covered = set(payload) - {"__artifact__", "__canonical_form__"}
    assert covered == set(GOVERNED_FIELDS)


def test_status_and_approval_metadata_are_not_governed() -> None:
    """Superseding an approved intent is legal and must not invalidate the digest."""
    for excluded in ("status", "digest", "approved_at", "approved_by", "expansion_count"):
        assert excluded not in GOVERNED_FIELDS


def test_the_artifact_kind_is_named_in_the_payload() -> None:
    assert _complete().validate().approve("cfo").digest_payload()["__artifact__"] == ARTIFACT_KIND


def test_the_digest_is_stable_across_the_order_things_were_added() -> None:
    """Two intents built in different orders with the same content agree."""
    first = _captured()
    first = first.set_objective(objective("same outcome", OutcomeKind.PROTECT))
    first = first.set_scope(scope(["a"]))

    second = _captured()
    second = second.set_scope(scope(["a"]))
    second = second.set_objective(objective("same outcome", OutcomeKind.PROTECT))

    payload_one = first.digest_payload()
    payload_two = second.digest_payload()
    # Ids differ by construction, so compare the parts that describe the mandate.
    assert payload_one["objective"] == payload_two["objective"]
    assert payload_one["scope"] == payload_two["scope"]


def test_two_intents_do_not_collide() -> None:
    first = _complete().validate().approve("cfo")
    second = _complete().validate().approve("cfo")
    assert first.digest != second.digest


# ----------------------------------------------------------------------
# Intent never plans
# ----------------------------------------------------------------------


def test_the_aggregate_exposes_no_way_to_express_a_plan() -> None:
    """The boundary that lets a human approve the goal without approving the how.

    If a field named for tasks, steps, or ordering ever appears here, an intent
    could carry a plan -- and the approval of one would silently become approval
    of the other.
    """
    planner_shaped = {"tasks", "steps", "actions", "sequence", "dependencies", "tools"}
    fields = {f.name for f in dataclasses.fields(Intent)}
    assert fields & planner_shaped == set()
