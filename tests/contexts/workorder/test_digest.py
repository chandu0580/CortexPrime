"""The canonical digest.

Property-based, using a seeded generator rather than Hypothesis, which is not a
dependency of this project. Seeded so a failure is reproducible: an unseeded
random property test that fails once and passes on rerun is worse than no test,
because it trains people to rerun rather than investigate.
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from backend.contexts.workorder.domain import (
    ARTIFACT_KIND,
    CANONICAL_FORM_VERSION,
    GOVERNED_FIELDS,
    AssumptionResolution,
    BlastRadius,
    EvidenceRef,
    Priority,
    WorkOrderState,
    compute_work_order_digest,
    digest_matches,
    digest_payload,
)

from tests.contexts.workorder.conftest import make_draft

SEED = 20260805


# ----------------------------------------------------------------------
# Determinism
# ----------------------------------------------------------------------


def test_digest_is_deterministic():
    work_order = make_draft()
    assert compute_work_order_digest(work_order) == compute_work_order_digest(work_order)


def test_set_ordering_does_not_change_the_digest():
    """Sets are unordered; a digest is not. Sorting is what reconciles them."""
    criteria = ["alpha holds", "beta holds", "gamma holds"]
    rng = random.Random(SEED)

    base = make_draft(acceptance_criteria=set(criteria))
    digests = set()
    for _ in range(12):
        shuffled = criteria[:]
        rng.shuffle(shuffled)
        variant = replace(base, acceptance_criteria=frozenset(shuffled))
        digests.add(compute_work_order_digest(variant).value)

    assert len(digests) == 1


def test_payload_carries_domain_separation_and_canonical_version():
    """Without these, a digest could be replayed as one over another artifact."""
    payload = digest_payload(make_draft())
    assert payload["__artifact__"] == ARTIFACT_KIND
    assert payload["__canonical_form__"] == CANONICAL_FORM_VERSION


def test_payload_contains_exactly_the_governed_fields():
    payload = digest_payload(make_draft())
    covered = set(payload) - {"__artifact__", "__canonical_form__"}
    assert covered == set(GOVERNED_FIELDS)


# ----------------------------------------------------------------------
# What the digest must react to
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutation",
    [
        lambda w: replace(w, intent="a completely different outcome"),
        lambda w: replace(w, acceptance_criteria=frozenset({"something else entirely"})),
        lambda w: replace(w, blast_radius=BlastRadius.of(["backend/other/**"])),
        lambda w: replace(w, definition_of_done=frozenset({"a different condition"})),
        lambda w: replace(w, version=w.version + 1),
    ],
    ids=["intent", "criteria", "radius", "done", "version"],
)
def test_changing_a_governed_field_changes_the_digest(mutation):
    original = make_draft()
    assert compute_work_order_digest(mutation(original)) != compute_work_order_digest(original)


# ----------------------------------------------------------------------
# What the digest must NOT react to
# ----------------------------------------------------------------------


def test_priority_is_excluded():
    """Re-ordering the queue must not require re-approving the work."""
    original = make_draft()
    assert compute_work_order_digest(
        replace(original, priority=Priority.P0)
    ) == compute_work_order_digest(original)


def test_state_is_excluded():
    """Including it would invalidate the digest on the first legal transition."""
    original = make_draft()
    approved = original.approve()
    assert digest_matches(approved, approved.digest)
    assert compute_work_order_digest(approved) == compute_work_order_digest(original)


def test_assumption_resolution_is_excluded():
    """Checking an assumption must not break the approval that demanded it."""
    approved = make_draft().approve()
    assigned = approved.transition(WorkOrderState.ASSIGNED)
    in_tests = assigned.transition(WorkOrderState.SPEC_TESTS)

    resolved = in_tests.resolve_assumption(
        in_tests.assumptions[0].assumption_id,
        AssumptionResolution.CONFIRMED,
        EvidenceRef("EV-checked"),
    )
    resolved.verify_digest()
    assert resolved.digest == approved.digest


def test_created_at_is_excluded():
    from datetime import datetime, timedelta, timezone

    original = make_draft()
    later = replace(original, created_at=datetime.now(timezone.utc) + timedelta(days=1))
    assert compute_work_order_digest(later) == compute_work_order_digest(original)


# ----------------------------------------------------------------------
# Property: any governed mutation is detected
# ----------------------------------------------------------------------


def test_property_random_governed_mutations_are_always_detected():
    """Fifty seeded mutations, none of which may pass verification."""
    rng = random.Random(SEED)
    approved = make_draft().approve()

    undetected = []
    for index in range(50):
        choice = rng.randrange(4)
        if choice == 0:
            mutated = replace(approved, intent=f"mutated intent {index}")
        elif choice == 1:
            mutated = replace(
                approved, acceptance_criteria=frozenset({f"criterion {index}"})
            )
        elif choice == 2:
            mutated = replace(approved, blast_radius=BlastRadius.of([f"backend/x{index}/**"]))
        else:
            mutated = replace(approved, definition_of_done=frozenset({f"done {index}"}))

        if digest_matches(mutated, approved.digest):
            undetected.append(index)

    assert undetected == [], f"mutations that escaped detection: {undetected}"


def test_property_distinct_work_orders_have_distinct_digests():
    """Sixty independently drafted WorkOrders, no collisions."""
    digests = {compute_work_order_digest(make_draft(intent=f"outcome {i}")).value for i in range(60)}
    assert len(digests) == 60


def test_digest_matches_uses_the_recorded_algorithm():
    """An algorithm upgrade must not retroactively invalidate stored approvals."""
    approved = make_draft().approve()
    assert digest_matches(approved, approved.digest)
    assert approved.digest.algorithm.value in {"sha256", "sha512", "blake2b"}
