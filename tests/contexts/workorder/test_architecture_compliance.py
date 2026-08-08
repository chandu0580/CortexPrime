"""The WorkOrder context obeys the rules it was written under.

Not a duplicate of the architecture gate. The gate checks the whole repository
and would keep passing if this context were deleted; these tests fail if *this
context* drifts, which is the failure a context-scoped suite should catch.

The most important one is ``test_repository_methods_all_take_a_context``. That
rule was written in PR-10, this repository is the first written after it, and it
is deliberately not on the grandfathered list -- so the rule gets exercised
against real code that had to comply rather than only against synthetic
violations in its own test file.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from backend.contexts.workorder.domain import ARTIFACT_KIND
from backend.platform.architecture.rules import ModuleGraph
from backend.platform.architecture.tenancy_rules import (
    CONTEXT_PARAMETER_NAMES,
    GRANDFATHERED_REPOSITORIES,
    RepositoryContextRule,
    scan_repository_methods,
)

CONTEXT_ROOT = Path("backend/contexts/workorder")


def _modules() -> list:
    return [p for p in CONTEXT_ROOT.rglob("*.py") if "__pycache__" not in p.parts]


def _imports(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
    return found


# ----------------------------------------------------------------------
# Dependency direction
# ----------------------------------------------------------------------


def test_the_context_imports_only_contracts_and_platform():
    """DEP-LAYERS: contexts sit above platform and below api."""
    permitted = ("backend.contracts", "backend.platform", "backend.contexts.workorder")
    offences = []
    for path in _modules():
        for imported in _imports(path):
            if not imported.startswith("backend."):
                continue
            if not imported.startswith(permitted):
                offences.append(f"{path}: {imported}")
    assert offences == [], offences


@pytest.mark.parametrize(
    "forbidden",
    ["backend.api", "backend.services", "backend.database", "backend.legacy"],
)
def test_the_context_never_imports_a_higher_or_sibling_layer(forbidden):
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith(forbidden)
    ]
    assert offences == [], offences


def test_the_domain_layer_imports_no_infrastructure():
    """A domain that knew about its repository could not be tested without one."""
    offences = [
        f"{path}: {imported}"
        for path in (CONTEXT_ROOT / "domain").rglob("*.py")
        if "__pycache__" not in path.parts
        for imported in _imports(path)
        if "infrastructure" in imported or "application" in imported
    ]
    assert offences == [], offences


def test_the_domain_layer_does_no_io():
    """Pure: no filesystem, no network, no clock beyond the one default."""
    banned = {"pathlib", "os", "socket", "requests", "httpx", "sqlite3", "json"}
    offences = []
    for path in (CONTEXT_ROOT / "domain").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for imported in _imports(path):
            if imported.split(".")[0] in banned:
                offences.append(f"{path}: {imported}")
    assert offences == [], offences


# ----------------------------------------------------------------------
# The tenant guard rule
# ----------------------------------------------------------------------


def test_repository_methods_all_take_a_context():
    """PR-10's rule, exercised against the first repository written after it."""
    graph = ModuleGraph.build(Path("backend"), package_root="backend")
    methods = [
        m
        for m in scan_repository_methods(graph)
        if m.repository in {"WorkOrderRepository", "InMemoryWorkOrderRepository"}
    ]
    assert methods, "the scanner found no WorkOrder repository methods to check"

    missing = [str(m) for m in methods if not m.takes_context]
    assert missing == [], missing


def test_no_repository_method_accepts_a_tenant_directly():
    """Tenant identity is derived from the context, never chosen by the caller."""
    graph = ModuleGraph.build(Path("backend"), package_root="backend")
    offences = [
        f"{m}: {m.takes_tenant}"
        for m in scan_repository_methods(graph)
        if m.repository.endswith("WorkOrderRepository") and m.takes_tenant
    ]
    assert offences == [], offences


def test_the_work_order_repository_is_not_grandfathered():
    """It must pass on merit. The ratchet may only shrink."""
    for name in ("WorkOrderRepository", "InMemoryWorkOrderRepository"):
        assert name not in GRANDFATHERED_REPOSITORIES


def test_the_rule_reports_no_blocking_violation_for_this_context():
    graph = ModuleGraph.build(Path("backend"), package_root="backend")
    result = RepositoryContextRule().evaluate(graph)
    ours = [
        v for v in result.blocking_violations if "workorder" in v.module or "WorkOrder" in str(v.offender)
    ]
    assert ours == [], [str(v) for v in ours]


def test_context_parameter_is_named_conventionally():
    """The static rule matches on parameter *name*; the runtime one on shape.

    If this repository named its parameter something else, the static rule would
    report a false violation for code that is actually correct -- so the naming
    convention is load-bearing and worth pinning.
    """
    from backend.contexts.workorder.infrastructure.repository import (
        InMemoryWorkOrderRepository,
    )

    for name in ("save", "get", "find", "list_active", "dependency_graph"):
        parameters = list(
            inspect.signature(getattr(InMemoryWorkOrderRepository, name)).parameters
        )
        assert parameters[1] in CONTEXT_PARAMETER_NAMES, (name, parameters)


# ----------------------------------------------------------------------
# State guard
# ----------------------------------------------------------------------


def test_the_context_writes_no_state_file():
    """STATE-NO-NEW-FILE-STORES: no forty-fourth JSON store."""
    writers = {"json", "pickle", "yaml", "shelve", "sqlite3"}
    offences = []
    for path in _modules():
        for imported in _imports(path):
            if imported.split(".")[0] in writers:
                offences.append(f"{path}: {imported}")
    assert offences == [], offences


# ----------------------------------------------------------------------
# Digest domain separation
# ----------------------------------------------------------------------


def test_the_artifact_kind_is_unique_to_this_context():
    """A digest over a WorkOrder must not be replayable as one over anything else."""
    assert ARTIFACT_KIND == "cortexprime.engineering.workorder"
    assert ARTIFACT_KIND.startswith("cortexprime.")


def test_every_contract_name_in_this_context_is_namespaced():
    """CONTRACT_NAME is globally unique; a clash raises at import time."""
    from backend.contexts.workorder.domain.assumption import Assumption
    from backend.contexts.workorder.domain.blast_radius import BlastRadius
    from backend.contexts.workorder.domain.rejection import RejectionGround
    from backend.contexts.workorder.domain.work_order import WorkOrder

    for contract in (WorkOrder, Assumption, RejectionGround, BlastRadius):
        assert contract.CONTRACT_NAME.startswith("cortexprime.engineering.")
