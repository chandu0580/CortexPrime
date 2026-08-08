"""Blast radius: matching, subtraction, and conflict detection.

Conflict detection is the part worth testing hardest. A false conflict costs
serialised work; a false non-conflict costs two agents editing the same file and
a corrupted merge. The tests assert the asymmetry is preserved.
"""

from __future__ import annotations

import random

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.workorder.domain import BlastRadius, PathPattern
from backend.contexts.workorder.domain.blast_radius import (
    MAX_FILES_WITHOUT_JUSTIFICATION,
    MAX_PACKAGES_WITHOUT_JUSTIFICATION,
)

SEED = 20260805


# ----------------------------------------------------------------------
# Patterns
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern,path,expected",
    [
        ("backend/**", "backend/a/b/c.py", True),
        ("backend/*", "backend/a.py", True),
        ("backend/*", "backend/a/b.py", False),          # single star stops at a separator
        ("backend/a/**", "backend/a/b/c.py", True),
        ("backend/a/**", "backend/ab/c.py", False),
        ("backend/a/**", "backend/a", True),             # `**` matches zero directories
        ("backend/?.py", "backend/x.py", True),
        ("backend/?.py", "backend/xy.py", False),
        ("backend/x.py", "backend/x.py", True),
    ],
)
def test_pattern_matching(pattern, path, expected):
    assert PathPattern(pattern).matches(path) is expected


def test_pattern_normalises_separators_and_prefix():
    assert PathPattern("./backend\\a/").value == "backend/a"


@pytest.mark.parametrize("bad", ["", "   ", "/absolute/path", "backend/../etc"])
def test_pattern_rejects_malformed(bad):
    with pytest.raises(ContractViolation):
        PathPattern(bad)


# ----------------------------------------------------------------------
# Subtraction
# ----------------------------------------------------------------------


def test_forbidden_wins_over_allowed():
    radius = BlastRadius.of(["backend/**"], forbidden=["backend/platform/architecture/**"])
    assert radius.permits_write("backend/platform/storage/guard.py")
    assert not radius.permits_write("backend/platform/architecture/rules.py")


def test_refusal_reason_distinguishes_forbidden_from_outside():
    radius = BlastRadius.of(["backend/a/**"], forbidden=["backend/a/secret.py"])
    assert "explicitly forbidden" in radius.refusal_reason("backend/a/secret.py")
    assert "outside" in radius.refusal_reason("backend/b/x.py")
    assert radius.refusal_reason("backend/a/ok.py") is None


def test_read_only_permits_reading_but_not_writing():
    radius = BlastRadius.of(["backend/a/**"], read_only=["backend/contracts/**"])
    assert radius.permits_read("backend/contracts/approval.py")
    assert not radius.permits_write("backend/contracts/approval.py")


def test_a_path_cannot_be_both_writable_and_read_only():
    with pytest.raises(ContractViolation):
        BlastRadius.of(["backend/a/**"], read_only=["backend/a/b/**"])


def test_empty_allowed_is_refused():
    """Authorising nothing is the absence of a scope, not a narrow one."""
    with pytest.raises(ContractViolation):
        BlastRadius.of([])


# ----------------------------------------------------------------------
# Conflict detection
# ----------------------------------------------------------------------


def test_nested_patterns_conflict():
    assert BlastRadius.of(["backend/platform/**"]).conflicts_with(
        BlastRadius.of(["backend/platform/storage/**"])
    )


def test_sibling_patterns_do_not_conflict():
    assert not BlastRadius.of(["backend/contexts/**"]).conflicts_with(
        BlastRadius.of(["backend/platform/**"])
    )


def test_conflict_detection_is_segment_aware():
    """A raw string prefix check would call these a conflict. They are disjoint."""
    assert not BlastRadius.of(["backend/b"]).conflicts_with(BlastRadius.of(["backend/bc.py"]))


def test_conflict_is_symmetric():
    rng = random.Random(SEED)
    packages = ["backend", "tests", "docs", "scripts"]
    for _ in range(60):
        left = BlastRadius.of([f"{rng.choice(packages)}/{rng.choice('abcd')}/**"])
        right = BlastRadius.of([f"{rng.choice(packages)}/{rng.choice('abcd')}/**"])
        assert left.conflicts_with(right) == right.conflicts_with(left)


def test_a_radius_always_conflicts_with_itself():
    rng = random.Random(SEED)
    for index in range(30):
        radius = BlastRadius.of([f"backend/pkg{rng.randrange(5)}/**", f"tests/t{index}/**"])
        assert radius.conflicts_with(radius)


def test_read_only_overlap_is_not_a_conflict():
    """Two WorkOrders may read the same paths concurrently. Only writes contend."""
    left = BlastRadius.of(["backend/a/**"], read_only=["backend/contracts/**"])
    right = BlastRadius.of(["backend/b/**"], read_only=["backend/contracts/**"])
    assert not left.conflicts_with(right)


def test_conflicting_patterns_names_the_pairs():
    left = BlastRadius.of(["backend/platform/**"])
    right = BlastRadius.of(["backend/platform/storage/**"])
    pairs = left.conflicting_patterns(right)
    assert pairs == (("backend/platform/**", "backend/platform/storage/**"),)


# ----------------------------------------------------------------------
# Size thresholds
# ----------------------------------------------------------------------


def test_many_packages_require_justification():
    packages = [f"pkg{i}/**" for i in range(MAX_PACKAGES_WITHOUT_JUSTIFICATION + 1)]
    with pytest.raises(ContractViolation):
        BlastRadius.of(packages)
    assert BlastRadius.of(packages, justification="a stated reason").requires_justification


def test_many_files_report_a_finding_rather_than_raising():
    """Legitimately empty against one commit and full against another."""
    radius = BlastRadius.of(["backend/**"])
    paths = [f"backend/mod{i}.py" for i in range(MAX_FILES_WITHOUT_JUSTIFICATION + 5)]
    findings = radius.validate_against_paths(paths)
    assert any("above the limit" in f for f in findings)


def test_a_pattern_matching_nothing_is_reported():
    findings = BlastRadius.of(["backend/nowhere/**"]).validate_against_paths(["backend/a.py"])
    assert any("matches no existing path" in f for f in findings)


def test_untouched_patterns_are_reported():
    """Declaring more than the work needs weakens conflict detection for everyone."""
    radius = BlastRadius.of(["backend/a/**", "backend/b/**"])
    assert radius.untouched_patterns(["backend/a/x.py"]) == ("backend/b/**",)


def test_excess_names_the_offending_paths():
    radius = BlastRadius.of(["backend/a/**"])
    assert radius.excess(["backend/a/x.py", "backend/b/y.py"]) == ("backend/b/y.py",)
