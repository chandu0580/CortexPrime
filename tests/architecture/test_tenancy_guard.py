"""The repository context rule, proven to catch its own violation.

Every rule in this codebase must be shown to fail when the thing it forbids is
actually present. A rule that has only ever been observed passing is a rule
nobody has any reason to trust -- it could be checking nothing at all and the
suite would look identical.

The violations here are written to a temporary tree and scanned from disk,
because that is exactly how the rule runs in CI. Asserting against a hand-built
AST would test the analyser and skip the file discovery that most often goes
wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.platform.architecture.rules import ModuleGraph, Severity
from backend.platform.architecture.tenancy_rules import (
    CONTEXT_PARAMETER_NAMES,
    GRANDFATHERED_REPOSITORIES,
    RepositoryContextRule,
    scan_repository_methods,
    stale_grandfather_entries,
)


def _graph(tmp_path: Path, source: str, *, filename: str = "repositories/widgets.py") -> ModuleGraph:
    """Build a module graph from one synthetic repository module."""
    target = tmp_path / "backend" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    (tmp_path / "backend" / "__init__.py").write_text("", encoding="utf-8")
    (target.parent / "__init__.py").write_text("", encoding="utf-8")
    return ModuleGraph.build(tmp_path / "backend", package_root="backend")


# ----------------------------------------------------------------------
# The rule fails when it should
# ----------------------------------------------------------------------


def test_a_method_without_a_context_is_an_error(tmp_path):
    graph = _graph(
        tmp_path,
        """
class WidgetRepository:
    async def get(self, pk):
        return None
""",
    )
    result = RepositoryContextRule().evaluate(graph)

    assert not result.passed
    assert len(result.blocking_violations) == 1
    assert "takes no execution context" in result.blocking_violations[0].detail


def test_a_method_accepting_tenant_id_is_an_error(tmp_path):
    """The anti-pattern the invariant exists to prevent.

    Worse than a missing context: the caller is choosing the isolation boundary.
    """
    graph = _graph(
        tmp_path,
        """
class WidgetRepository:
    async def list_for(self, context, tenant_id):
        return []
""",
    )
    result = RepositoryContextRule().evaluate(graph)

    assert not result.passed
    detail = result.blocking_violations[0].detail
    assert "tenant_id" in detail and "derived from the ExecutionContext" in detail


def test_taking_a_tenant_is_flagged_even_alongside_a_context(tmp_path):
    """Having a context does not excuse also accepting a tenant."""
    graph = _graph(
        tmp_path,
        """
class WidgetRepository:
    async def get(self, context, tenant_id, pk):
        return None
""",
    )
    result = RepositoryContextRule().evaluate(graph)
    assert len(result.blocking_violations) == 1


@pytest.mark.parametrize("parameter", sorted(CONTEXT_PARAMETER_NAMES))
def test_each_accepted_context_name_satisfies_the_rule(tmp_path, parameter):
    graph = _graph(
        tmp_path,
        f"""
class WidgetRepository:
    async def get(self, {parameter}, pk):
        return None
""",
    )
    assert RepositoryContextRule().evaluate(graph).passed


def test_violations_carry_a_line_number(tmp_path):
    """A finding without a location is a finding nobody will act on."""
    graph = _graph(
        tmp_path,
        """
class WidgetRepository:
    async def ok(self, context):
        return None

    async def bad(self, pk):
        return None
""",
    )
    violation = RepositoryContextRule().evaluate(graph).blocking_violations[0]
    assert violation.line == 6
    assert violation.offender == "WidgetRepository.bad"


# ----------------------------------------------------------------------
# What it correctly leaves alone
# ----------------------------------------------------------------------


def test_private_methods_are_not_checked(tmp_path):
    graph = _graph(
        tmp_path,
        """
class WidgetRepository:
    async def _fetch(self, pk):
        return None
""",
    )
    assert RepositoryContextRule().evaluate(graph).passed


def test_subclasses_of_the_scoped_base_are_exempt(tmp_path):
    """The base threads the context through; its subclasses inherit that."""
    graph = _graph(
        tmp_path,
        """
class WidgetRepository(TenantScopedRepository[WidgetModel]):
    __scope_column__ = "tenant_id"

    async def by_name(self, name):
        return []
""",
    )
    assert RepositoryContextRule().evaluate(graph).passed


def test_non_repository_classes_are_ignored(tmp_path):
    graph = _graph(
        tmp_path,
        """
class WidgetService:
    async def get(self, pk):
        return None
""",
    )
    assert RepositoryContextRule().evaluate(graph).skipped


def test_repositories_outside_a_persistence_path_are_ignored(tmp_path):
    """A ``*Repository`` in an unrelated package is something else."""
    graph = _graph(
        tmp_path,
        """
class WidgetRepository:
    async def get(self, pk):
        return None
""",
        filename="api/handlers.py",
    )
    assert RepositoryContextRule().evaluate(graph).skipped


def test_staticmethods_are_exempt(tmp_path):
    """No instance, therefore no guard to hold."""
    graph = _graph(
        tmp_path,
        """
class WidgetRepository:
    @staticmethod
    def to_dict(row):
        return {}
""",
    )
    assert RepositoryContextRule().evaluate(graph).passed


# ----------------------------------------------------------------------
# The ratchet
# ----------------------------------------------------------------------


def test_grandfathered_repositories_warn_rather_than_block(tmp_path):
    """Legacy repositories keep the gate green while they migrate."""
    graph = _graph(
        tmp_path,
        """
class MissionRepository:
    async def get(self, pk):
        return None
""",
    )
    result = RepositoryContextRule().evaluate(graph)

    assert result.passed, "a grandfathered repository must not block the merge"
    assert len(result.warnings) == 1
    assert result.warnings[0].severity is Severity.WARNING


def test_a_new_repository_blocks_even_beside_a_grandfathered_one(tmp_path):
    """Adding to the ratchet is the only way past, and that is a visible diff."""
    graph = _graph(
        tmp_path,
        """
class MissionRepository:
    async def get(self, pk):
        return None


class BrandNewRepository:
    async def get(self, pk):
        return None
""",
    )
    result = RepositoryContextRule().evaluate(graph)

    assert not result.passed
    assert {v.offender for v in result.blocking_violations} == {"BrandNewRepository.get"}


# ----------------------------------------------------------------------
# Against the real codebase
# ----------------------------------------------------------------------


def test_real_codebase_has_no_blocking_violations():
    graph = ModuleGraph.build(Path("backend"), package_root="backend")
    result = RepositoryContextRule().evaluate(graph)

    assert result.passed, [str(v) for v in result.blocking_violations]


def test_the_ratchet_has_no_stale_entries():
    """Every grandfathered name still names a live repository.

    A stale entry silently widens the exemption: a future repository reusing the
    name inherits a pass it never earned.
    """
    graph = ModuleGraph.build(Path("backend"), package_root="backend")
    assert stale_grandfather_entries(graph) == ()


def test_the_scoped_base_is_not_grandfathered():
    """The compliant base must pass on merit, not by exemption."""
    assert "TenantScopedRepository" not in GRANDFATHERED_REPOSITORIES


def test_every_real_repository_is_accounted_for():
    """Any repository with a violating method must be grandfathered.

    Originally this exempted ``TenantScopedRepository`` by name, which was wrong:
    it made compliance look like a special case rather than the default, so every
    new compliant repository failed the test until someone added its name. A
    compliant repository needs no exemption at all -- only a violating one does.
    """
    graph = ModuleGraph.build(Path("backend"), package_root="backend")
    violating = {
        method.repository
        for method in scan_repository_methods(graph)
        if not method.takes_context or method.takes_tenant
    }

    unaccounted = violating - GRANDFATHERED_REPOSITORIES
    assert unaccounted == set(), f"repositories neither compliant nor grandfathered: {unaccounted}"
