"""Validation rules V1-V10.

Each rule is tested against a WorkOrder that violates it and one that does not.
A validator only ever observed passing has not been shown to check anything.

The rules split three ways by decidability, and the tests assert that split
holds: a heuristic rule must produce ADVISORY findings, because a heuristic that
blocks a merge will be worked around within a week.
"""

from __future__ import annotations

import pytest

from backend.contexts.workorder.domain import (
    AssumptionResolution,
    AssumptionSpec,
    BlastRadius,
    Decidability,
    EvidenceRef,
    Severity,
    StaticReferenceResolver,
    WorkOrderState,
    validate,
)

from tests.contexts.workorder.conftest import make_draft


def _report(work_order, resolver, **kwargs):
    return validate(work_order, resolver=resolver, **kwargs)


def _rules(report) -> set:
    return {f.rule for f in report.findings}


# ----------------------------------------------------------------------
# A well-formed WorkOrder passes
# ----------------------------------------------------------------------


def test_a_valid_work_order_is_approvable(resolver):
    report = _report(make_draft(), resolver)
    assert report.approvable
    assert report.blocking == ()


# ----------------------------------------------------------------------
# V1 -- one intent
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "intent",
    [
        "Refuse uncontexted reads; also add a cache",
        "Refuse uncontexted reads and then migrate the schema",
        "Refuse uncontexted reads. Add a cache.",
    ],
)
def test_v1_detects_multiple_intents(resolver, intent):
    report = _report(make_draft(intent=intent), resolver)
    assert "V1" in _rules(report)


def test_v1_is_advisory_because_it_is_heuristic(resolver):
    """It cannot decide the semantic question, so it must not block a merge."""
    report = _report(make_draft(intent="Do a thing; do another thing"), resolver)
    finding = next(f for f in report.findings if f.rule == "V1")
    assert finding.severity is Severity.ADVISORY
    assert finding.decidability is Decidability.HEURISTIC


def test_v1_accepts_a_single_outcome(resolver):
    report = _report(make_draft(intent="The storage boundary refuses uncontexted reads"), resolver)
    assert "V1" not in _rules(report)


# ----------------------------------------------------------------------
# V2 -- criteria are implementation-independent
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "criterion",
    [
        "authorize() raises when the context is missing",
        "guard.py refuses the call",
        "the call returns a StorageAccess",
    ],
)
def test_v2_detects_implementation_leakage(resolver, criterion):
    report = _report(make_draft(acceptance_criteria={criterion}), resolver)
    assert "V2" in _rules(report)


def test_v2_accepts_a_behavioural_criterion(resolver):
    report = _report(
        make_draft(acceptance_criteria={"A read with no execution context is refused"}), resolver
    )
    assert "V2" not in _rules(report)


# ----------------------------------------------------------------------
# V3 -- every assumption has a rejection ground
# ----------------------------------------------------------------------


def test_v3_blocks_an_assumption_with_no_rejection_ground(resolver):
    """The factory pairs them; this constructs the unpaired case directly."""
    from dataclasses import replace

    work_order = make_draft()
    orphaned = replace(work_order, rejection_grounds=())
    report = _report(orphaned, resolver)

    finding = next(f for f in report.findings if f.rule == "V3")
    assert finding.severity is Severity.BLOCKING
    assert not report.approvable


def test_v3_passes_when_the_factory_pairs_them(resolver):
    work_order = make_draft(
        assumptions=[
            AssumptionSpec("first belief", "check one"),
            AssumptionSpec("second belief", "check two"),
        ]
    )
    assert "V3" not in _rules(_report(work_order, resolver))


# ----------------------------------------------------------------------
# V4 / V5 / V9 -- references resolve
# ----------------------------------------------------------------------


def test_v4_blocks_unresolvable_evidence(resolver):
    report = _report(make_draft(evidence=["EV-NONEXISTENT"]), resolver)
    assert "V4" in _rules(report)
    assert not report.approvable


def test_v4_blocks_stale_evidence(resolver):
    report = _report(make_draft(evidence=["EV-STALE"]), resolver)
    finding = next(f for f in report.findings if f.rule == "V4")
    assert "stale" in finding.detail


def test_v5_blocks_an_unknown_adr(resolver):
    assert "V5" in _rules(_report(make_draft(adr_references=["ADR-999"]), resolver))


def test_v5_blocks_a_superseded_adr(resolver):
    """A WorkOrder governed by a dead decision is ungoverned."""
    report = _report(make_draft(adr_references=["ADR-002"]), resolver)
    finding = next(f for f in report.findings if f.rule == "V5")
    assert "superseded" in finding.detail


def test_v9_blocks_an_unenforceable_constraint(resolver):
    assert "V9" in _rules(_report(make_draft(constraints=["NOT-A-RULE"]), resolver))


def test_an_empty_resolver_fails_closed():
    """Unknown resolves to absent. There is deliberately no permissive mode."""
    report = _report(make_draft(), StaticReferenceResolver())
    assert not report.approvable
    assert {"V4", "V5", "V9"} <= _rules(report)


def test_validation_refuses_a_non_resolver():
    with pytest.raises(TypeError):
        validate(make_draft(), resolver="anything")  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# V6 -- blast radius against the repository
# ----------------------------------------------------------------------


def test_v6_reports_a_pattern_matching_nothing(resolver):
    work_order = make_draft(radius=BlastRadius.of(["backend/nowhere/**"]))
    report = _report(work_order, resolver, repository_paths=["backend/a.py"])
    assert "V6" in _rules(report)


def test_v6_is_skipped_without_repository_paths(resolver):
    """The same radius is legitimately empty against one commit and full against another."""
    work_order = make_draft(radius=BlastRadius.of(["backend/nowhere/**"]))
    assert "V6" not in _rules(_report(work_order, resolver))


# ----------------------------------------------------------------------
# V7 -- dependency cycles
# ----------------------------------------------------------------------


def test_v7_detects_a_two_node_cycle(resolver):
    from backend.contexts.workorder.domain import WorkOrderId

    other = WorkOrderId.new()
    work_order = make_draft()
    from dataclasses import replace

    dependent = replace(work_order, dependencies=frozenset({other}))
    graph = {str(other): {str(work_order.work_id)}}

    report = _report(dependent, resolver, dependency_graph=graph)
    finding = next(f for f in report.findings if f.rule == "V7")
    assert "cycle" in finding.detail
    assert not report.approvable


def test_v7_accepts_an_acyclic_graph(resolver):
    from dataclasses import replace

    from backend.contexts.workorder.domain import WorkOrderId

    other = WorkOrderId.new()
    dependent = replace(make_draft(), dependencies=frozenset({other}))
    assert "V7" not in _rules(_report(dependent, resolver, dependency_graph={str(other): set()}))


# ----------------------------------------------------------------------
# V10 -- definition_of_done does not restate a universal condition
# ----------------------------------------------------------------------


def test_v10_detects_a_restated_universal_condition(resolver):
    report = _report(
        make_draft(definition_of_done={"the architecture gate is green"}), resolver
    )
    finding = next(f for f in report.findings if f.rule == "V10")
    assert finding.severity is Severity.ADVISORY


def test_v10_accepts_a_work_order_specific_condition(resolver):
    report = _report(
        make_draft(definition_of_done={"the guard refuses an unattributed write"}), resolver
    )
    assert "V10" not in _rules(report)


# ----------------------------------------------------------------------
# Assumption resolution blocks approval
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "resolution",
    [AssumptionResolution.CONTRADICTED, AssumptionResolution.UNVERIFIABLE],
)
def test_a_non_confirmed_assumption_blocks(resolver, resolution):
    """Proceeding on an unchecked belief carries the same risk as a false one."""
    approved = make_draft().approve()
    working = approved.transition(WorkOrderState.ASSIGNED).transition(WorkOrderState.SPEC_TESTS)
    resolved = working.resolve_assumption(
        working.assumptions[0].assumption_id, resolution, EvidenceRef("EV-1")
    )

    report = _report(resolved, resolver)
    assert not report.approvable
    assert "ASSUMPTION" in _rules(report)


def test_a_confirmed_assumption_does_not_block(resolver):
    approved = make_draft().approve()
    working = approved.transition(WorkOrderState.ASSIGNED).transition(WorkOrderState.SPEC_TESTS)
    resolved = working.resolve_assumption(
        working.assumptions[0].assumption_id,
        AssumptionResolution.CONFIRMED,
        EvidenceRef("EV-1"),
    )
    assert _report(resolved, resolver).approvable


# ----------------------------------------------------------------------
# Report shape
# ----------------------------------------------------------------------


def test_all_findings_are_returned_not_just_the_first(resolver):
    """Fixing them one round-trip at a time is how a Draft takes six approvals."""
    work_order = make_draft(
        intent="Do a thing; do another",
        evidence=["EV-NONEXISTENT"],
        adr_references=["ADR-999"],
        constraints=["NOT-A-RULE"],
    )
    report = _report(work_order, resolver)
    assert {"V1", "V4", "V5", "V9"} <= _rules(report)
