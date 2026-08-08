"""The drift test that makes the duplicated blast-radius matcher safe.

PR-E4's ContextBundle *records* a blast radius without matching against it.
This context matches, because its rule is enforcement: changed files must stay
within the WorkOrder's declared radius, and enforcement requires a verdict this
context computes rather than one the caller supplies.

That leaves two copies of security-relevant matching logic. This file is the
answer: both matchers run over a shared corpus and must agree on every pair. A
divergence means a path one context calls out-of-scope the other calls in-scope,
which is exactly the failure the duplication risks.

The corpus is written to hurt -- ``**`` at every position, single-star boundary
cases, dotfiles, extensions, and the trailing-``/**``-matches-the-directory rule
that a naive translation gets wrong.
"""

from __future__ import annotations

import pytest

from backend.contexts.implementation_record.domain.paths import (
    BlastRadiusScope,
    PathPattern,
    normalise_path,
)
from backend.contexts.workorder.domain.blast_radius import (
    BlastRadius as WorkOrderBlastRadius,
)
from backend.contexts.workorder.domain.blast_radius import (
    PathPattern as WorkOrderPathPattern,
)
from backend.contracts.errors import ContractViolation

#: Patterns exercised against every path below. Both matchers see the same list.
PATTERNS = (
    "backend/**",
    "backend/*",
    "backend/*.py",
    "backend/**/*.py",
    "backend/**/test_*.py",
    "backend/contexts/**",
    "backend/contexts/*/domain/**",
    "backend/api/routes.py",
    "backend/?.py",
    "**/conftest.py",
    "**",
    "docs/adr/ADR-*.md",
)

PATHS = (
    "backend",
    "backend/",
    "./backend/main.py",
    "backend/main.py",
    "backend/api/routes.py",
    "backend/api/routes/index.py",
    "backend/contexts/workorder/domain/states.py",
    "backend/contexts/implementation_record/domain/paths.py",
    "backend/x.py",
    "backend/xy.py",
    "conftest.py",
    "tests/conftest.py",
    "tests/contexts/conftest.py",
    "docs/adr/ADR-023-implementation-record.md",
    "docs/adr/index.md",
    "frontend/app/page.tsx",
    "backend\\api\\routes.py",
    ".github/workflows/architecture.yml",
)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_matcher_agrees_with_the_workorder_context(pattern: str) -> None:
    """Every pattern/path pair must produce the same verdict in both contexts.

    Asserted pair by pair rather than as a summary count, so a failure names the
    exact pair that diverged instead of reporting that some number of them did.
    """
    ours = PathPattern(pattern)
    theirs = WorkOrderPathPattern(pattern)

    for path in PATHS:
        assert ours.matches(path) is theirs.matches(path), (
            f"blast-radius matchers disagree: pattern {pattern!r} against {path!r} -- "
            f"implementation_record says {ours.matches(path)}, "
            f"workorder says {theirs.matches(path)}"
        )


def test_scope_level_agreement_including_forbidden_precedence() -> None:
    """Agreement holds at the scope level too, not just per-pattern.

    ``forbidden`` beating ``allowed`` is a scope-level rule; a per-pattern test
    could pass while the two contexts resolved the conflict differently.
    """
    ours = BlastRadiusScope.of(
        ["backend/**"], forbidden=["backend/database/**", "backend/**/secrets.py"]
    )
    theirs = WorkOrderBlastRadius.of(
        ["backend/**"], forbidden=["backend/database/**", "backend/**/secrets.py"]
    )

    for path in PATHS + (
        "backend/database/models.py",
        "backend/api/secrets.py",
        "backend/secrets.py",
    ):
        assert ours.permits_write(path) is theirs.permits_write(path), (
            f"scopes disagree on write permission for {path!r}"
        )
        assert ours.forbids(path) is theirs.forbids(path), (
            f"scopes disagree on forbidden for {path!r}"
        )


def test_normalisation_agrees() -> None:
    """A pattern normalised differently would make every later comparison a lie."""
    for raw in ("./backend/main.py", "backend/main.py/", "backend\\main.py", "backend"):
        assert str(PathPattern(raw)) == str(WorkOrderPathPattern(raw))


# ----------------------------------------------------------------------
# The semantics this context depends on, stated directly
# ----------------------------------------------------------------------


def test_trailing_double_star_covers_the_directory_itself() -> None:
    """``a/**`` matches ``a``.

    The rule a naive ``fnmatch`` translation gets wrong: without it, a WorkOrder
    scoped to ``backend/**`` would refuse a change to ``backend`` itself.
    """
    assert PathPattern("backend/**").matches("backend")
    assert PathPattern("backend/**").matches("backend/main.py")
    assert PathPattern("backend/**").matches("backend/a/b/c.py")


def test_double_star_crosses_separators_and_single_star_does_not() -> None:
    assert PathPattern("backend/**/x.py").matches("backend/a/b/x.py")
    assert PathPattern("backend/**/x.py").matches("backend/x.py")
    assert PathPattern("backend/*").matches("backend/x.py")
    assert not PathPattern("backend/*").matches("backend/a/x.py")


def test_question_mark_does_not_cross_a_separator() -> None:
    assert PathPattern("backend/?.py").matches("backend/x.py")
    assert not PathPattern("backend/?.py").matches("backend/xy.py")
    assert not PathPattern("a/?/b").matches("a//b")


def test_forbidden_beats_allowed() -> None:
    """Ambiguity resolves to refusal, not to permission."""
    scope = BlastRadiusScope.of(["backend/**"], forbidden=["backend/database/**"])
    assert scope.permits_write("backend/api/routes.py")
    assert not scope.permits_write("backend/database/models.py")
    assert scope.refusal_reason("backend/database/models.py") == (
        "is explicitly forbidden by the declared blast radius"
    )
    assert scope.refusal_reason("frontend/page.tsx") == (
        "is outside the declared blast radius"
    )


def test_the_two_refusal_reasons_are_distinguished() -> None:
    """They call for different responses, so they must not read the same.

    Outside means the scope was predicted wrongly and should be re-approved
    wider. Forbidden means the Architect ruled it out on purpose, and expanding
    is the wrong answer.
    """
    scope = BlastRadiusScope.of(["backend/**"], forbidden=["backend/database/**"])
    assert scope.refusal_reason("backend/database/x.py") != scope.refusal_reason(
        "frontend/x.tsx"
    )


def test_a_scope_that_allows_nothing_is_refused() -> None:
    with pytest.raises(ContractViolation, match="authorises nothing"):
        BlastRadiusScope.of([])


@pytest.mark.parametrize("bad", ["", "   ", "/absolute/path", "../escape/**", "a/../b"])
def test_patterns_that_would_escape_the_repository_are_refused(bad: str) -> None:
    with pytest.raises(ContractViolation):
        PathPattern(bad)


def test_normalise_path_is_idempotent() -> None:
    """A normaliser that changed its answer on a second pass would make the
    stored form depend on how many times it happened to be applied."""
    for raw in PATHS:
        once = normalise_path(raw)
        assert normalise_path(once) == once


def test_untouched_patterns_reports_what_the_radius_over_claimed() -> None:
    scope = BlastRadiusScope.of(["backend/**", "frontend/**", "docs/**"])
    assert scope.untouched_patterns(["backend/main.py"]) == ("docs/**", "frontend/**")
    assert scope.untouched_patterns(
        ["backend/a.py", "frontend/b.tsx", "docs/c.md"]
    ) == ()
