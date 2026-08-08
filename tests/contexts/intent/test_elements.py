"""The six elements an intent must contain, and what makes each one real.

Every rule here is refused at *construction*, not flagged later. An element this
weak is consumed by whatever reads the intent the moment it exists, and by then
the damage is a plan built on an unfalsifiable goal.

The priority drift test lives here too: ``IntentPriority`` mirrors
``MissionPriority`` deliberately, and the mirror is only safe while something
checks it.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.intent import (
    ConstraintEnforcement,
    ConstraintKind,
    ContradictoryScope,
    Environment,
    EmptyScope,
    ImpactLevel,
    IntentPriority,
    MIRRORED_PRIORITY_VALUES,
    OutcomeKind,
    RiskAppetite,
    ScopeTarget,
    UnboundedConstraint,
    UnmeasurableCriterion,
    constraint,
    criterion,
    objective,
    risk,
    scope,
)


# ----------------------------------------------------------------------
# Priority mirrors the Mission context -- checked, not assumed
# ----------------------------------------------------------------------


def test_intent_priority_mirrors_mission_priority() -> None:
    """S2 forbids importing the other context, so the duplication is drift-tested.

    An approved intent becomes a mission. A priority that existed on one side and
    not the other would silently downgrade in translation, and nothing else in
    the system would notice.
    """
    from backend.contexts.mission import MissionPriority

    assert {p.value for p in IntentPriority} == {p.value for p in MissionPriority}


def test_the_two_priority_vocabularies_rank_the_same_way() -> None:
    """Equal names are not enough -- equal *ordering* is what carries across."""
    from backend.contexts.mission import MissionPriority

    for value in MIRRORED_PRIORITY_VALUES:
        assert IntentPriority(value).rank == MissionPriority(value).rank


def test_the_two_vocabularies_agree_on_urgency() -> None:
    from backend.contexts.mission import MissionPriority

    for value in MIRRORED_PRIORITY_VALUES:
        assert (
            IntentPriority(value).demands_immediate_attention
            is MissionPriority(value).demands_immediate_attention
        )


def test_only_critical_refuses_to_wait_for_approval() -> None:
    assert not IntentPriority.CRITICAL.tolerates_deferred_approval
    for other in (IntentPriority.ROUTINE, IntentPriority.ELEVATED, IntentPriority.URGENT):
        assert other.tolerates_deferred_approval


# ----------------------------------------------------------------------
# Success criteria -- a criterion nobody can check is a wish
# ----------------------------------------------------------------------


def test_a_criterion_without_a_measure_is_refused() -> None:
    """The rule the whole context turns on."""
    with pytest.raises(UnmeasurableCriterion):
        criterion("the system should be faster", "")


def test_a_criterion_with_a_measure_is_accepted() -> None:
    settled = criterion("p99 latency under 200ms", "Grafana: api_latency_p99")
    assert settled.measure == "Grafana: api_latency_p99"


def test_a_criterion_must_state_something() -> None:
    with pytest.raises(ContractViolation):
        criterion("   ", "some measure")


def test_a_comparative_criterion_without_a_baseline_is_flagged_not_refused() -> None:
    """The baseline is sometimes genuinely established later."""
    comparative = criterion("30% fewer errors", "error rate", threshold="-30%")
    assert comparative.is_comparative

    anchored = criterion(
        "30% fewer errors", "error rate", threshold="-30%", baseline="Jul: 4.2%"
    )
    assert not anchored.is_comparative


def test_a_criterion_with_no_threshold_is_not_comparative() -> None:
    assert not criterion("the alert fires", "pagerduty incident created").is_comparative


# ----------------------------------------------------------------------
# Constraints -- a quantitative constraint carries its limit
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind", [ConstraintKind.BUDGET, ConstraintKind.DEADLINE, ConstraintKind.RATE]
)
def test_a_quantitative_constraint_without_a_limit_is_refused(kind) -> None:
    with pytest.raises(UnboundedConstraint):
        constraint(kind, "keep it reasonable")


@pytest.mark.parametrize(
    "kind",
    [
        ConstraintKind.COMPLIANCE,
        ConstraintKind.SAFETY,
        ConstraintKind.APPROVAL,
        ConstraintKind.DATA_RESIDENCY,
        ConstraintKind.AVAILABILITY,
    ],
)
def test_a_qualitative_constraint_needs_no_limit(kind) -> None:
    """Forcing a number onto 'do not violate GDPR' would produce a fake one."""
    assert constraint(kind, "the boundary").limit is None


def test_a_quantitative_constraint_with_a_limit_is_accepted() -> None:
    bounded = constraint(ConstraintKind.BUDGET, "spend cap", limit="$5000")
    assert bounded.limit == "$5000"


@pytest.mark.parametrize(
    "kind",
    [
        ConstraintKind.COMPLIANCE,
        ConstraintKind.SAFETY,
        ConstraintKind.APPROVAL,
        ConstraintKind.DATA_RESIDENCY,
    ],
)
def test_an_inviolable_constraint_cannot_be_soft(kind) -> None:
    """Marking a regulation tradeable is how it gets traded."""
    with pytest.raises(ContractViolation):
        constraint(kind, "the boundary", enforcement=ConstraintEnforcement.SOFT)


def test_a_negotiable_constraint_may_be_soft() -> None:
    soft = constraint(
        ConstraintKind.AVAILABILITY,
        "prefer no downtime",
        enforcement=ConstraintEnforcement.SOFT,
    )
    assert not soft.is_hard


def test_which_kinds_are_inviolable_is_explicit() -> None:
    inviolable = {k.value for k in ConstraintKind if k.is_inviolable}
    assert inviolable == {"compliance", "safety", "approval", "data_residency"}


def test_a_constraint_must_state_what_it_limits() -> None:
    with pytest.raises(ContractViolation):
        constraint(ConstraintKind.SAFETY, "  ")


# ----------------------------------------------------------------------
# Scope
# ----------------------------------------------------------------------


def test_a_scope_that_includes_nothing_is_refused() -> None:
    """The natural reading of 'no scope' is 'everything'."""
    with pytest.raises(EmptyScope):
        scope([])


def test_a_target_both_included_and_excluded_is_refused() -> None:
    with pytest.raises(ContradictoryScope) as caught:
        scope(["payments", "billing"], excluded=["payments"])
    assert caught.value.overlapping == ("payments",)


def test_a_scope_must_name_an_environment() -> None:
    with pytest.raises(ContractViolation):
        scope(["a"], environments=())


def test_exclusions_are_preserved() -> None:
    """The interesting half of scope is usually what somebody ruled out."""
    bounded = scope(["payments/*"], excluded=["payments/settlement"])
    assert bounded.excluded_identifiers == ("payments/settlement",)


def test_scope_reports_whether_it_touches_production() -> None:
    assert scope(["a"], environments=(Environment.PRODUCTION,)).touches_production
    assert not scope(["a"], environments=(Environment.STAGING,)).touches_production


def test_scope_coverage_lets_exclusion_win() -> None:
    bounded = scope(["a", "b"], excluded=["c"])
    assert bounded.covers("a")
    assert not bounded.covers("c")
    assert not bounded.covers("unknown")


def test_scope_breadth_counts_included_targets() -> None:
    assert scope(["a", "b", "c"]).breadth == 3


def test_widening_is_visible() -> None:
    """An intent whose scope grew approved something the earlier reader never saw."""
    before = scope(["a"])
    after = scope(["a", "b", "c"])
    assert before.widened_by(after) == ("b", "c")
    assert after.widened_by(before) == ()


def test_a_scope_target_must_have_an_identifier() -> None:
    with pytest.raises(ContractViolation):
        ScopeTarget("  ")


# ----------------------------------------------------------------------
# Objective
# ----------------------------------------------------------------------


def test_an_objective_must_state_an_outcome() -> None:
    with pytest.raises(ContractViolation):
        objective("   ")


@pytest.mark.parametrize("kind", [OutcomeKind.REDUCE, OutcomeKind.RESTORE])
def test_acting_objectives_are_identified(kind) -> None:
    assert objective("do the thing", kind).changes_the_world


@pytest.mark.parametrize(
    "kind",
    [OutcomeKind.UNDERSTAND, OutcomeKind.DETECT, OutcomeKind.PROTECT, OutcomeKind.PROVE],
)
def test_observing_objectives_are_identified(kind) -> None:
    assert not objective("look at the thing", kind).changes_the_world


def test_detection_has_no_natural_end() -> None:
    assert OutcomeKind.DETECT.is_continuous
    assert not OutcomeKind.REDUCE.is_continuous


# ----------------------------------------------------------------------
# Risk
# ----------------------------------------------------------------------


def test_a_high_impact_risk_must_be_accepted_by_somebody() -> None:
    """One acknowledged and not accepted is one nobody has decided about."""
    with pytest.raises(ContractViolation):
        risk("this could take down checkout", ImpactLevel.HIGH)


def test_a_high_impact_risk_with_an_acceptor_is_fine() -> None:
    accepted = risk("could take down checkout", ImpactLevel.HIGH, accepted_by="vp-eng")
    assert accepted.accepted_by == "vp-eng"


@pytest.mark.parametrize("impact", [ImpactLevel.LOW, ImpactLevel.MEDIUM])
def test_lesser_risks_need_no_acceptor(impact) -> None:
    assert risk("some risk", impact).accepted_by is None


def test_a_risk_must_state_what_could_go_wrong() -> None:
    with pytest.raises(ContractViolation):
        risk("  ")


def test_appetite_ranks_and_averse_prefers_blocked() -> None:
    """Constitution S6's 'prefer blocked over wrong', stated by the requester."""
    assert RiskAppetite.AVERSE.prefers_blocked_over_wrong
    assert not RiskAppetite.TOLERANT.prefers_blocked_over_wrong
    assert RiskAppetite.AVERSE.rank < RiskAppetite.MEASURED.rank < RiskAppetite.TOLERANT.rank
