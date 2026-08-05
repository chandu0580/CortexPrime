"""Executable architecture — the Constitution as fitness functions.

The Constitution says *"Violation of any invariant is a defect, regardless of
tests passing."* This package is what makes that true: every structural rule and
every constitutional invariant becomes a check CI runs on every commit.

    from backend.platform.architecture import analyze, render_text

    result = analyze()
    print(render_text(result))
    assert result.gate_passed

Two kinds of check
------------------
**Structural rules** analyse the import graph, parsed with :mod:`ast` rather
than imported, so nothing executes application code.

**Invariant probes** actively construct a violating state and assert the system
refuses it. The distinction matters: a structural check confirms a guard is
*present*, a probe confirms it *works*. Deleting the digest comparison in the
dispatcher would leave the module in place — the structural check still passes,
the probe does not.

Honest status
-------------
Not every invariant is enforced yet. Unenforced ones report as **skipped, never
as passed**, with the PR that will enforce them. A skip counted as a pass is how
an unenforced invariant comes to look enforced.

CLI::

    python -m backend.platform.architecture            # text report, exit 1 on failure
    python -m backend.platform.architecture --markdown
    python -m backend.platform.architecture --json

See ``docs/adr/ADR-016-architecture-fitness-functions.md``.
"""

from __future__ import annotations

from backend.platform.architecture.architecture_report import (
    dependency_summary,
    render_markdown,
    render_text,
    to_dict,
)
from backend.platform.architecture.boundary_rules import (
    BOUNDED_CONTEXTS,
    ContextIsolationRule,
    InterfacePurityRule,
    NoLegacyImportRule,
    PersistenceEncapsulationRule,
    default_boundary_rules,
)
from backend.platform.architecture.dependency_rules import (
    AllowedRootsRule,
    ForbiddenImportRule,
    LayerRule,
    NoCyclesRule,
    default_dependency_rules,
)
from backend.platform.architecture.fitness_functions import (
    ArchitectureSuite,
    SuiteResult,
    analyze,
    default_suite,
)
from backend.platform.architecture.invariant_tests import (
    InvariantCheck,
    InvariantStatus,
    constitutional_invariants,
)
from backend.platform.architecture.state_rules import (
    APPROVED_STORES,
    GRANDFATHERED_STORES,
    STATE_FILE_EXTENSIONS,
    FileStateRule,
    scan_state_files,
)
from backend.platform.architecture.rules import (
    ArchitectureRule,
    ModuleGraph,
    ModuleInfo,
    RuleResult,
    Severity,
    Violation,
)

__all__ = [
    # entry points
    "analyze",
    "default_suite",
    "ArchitectureSuite",
    "SuiteResult",
    # core types
    "ArchitectureRule",
    "ModuleGraph",
    "ModuleInfo",
    "RuleResult",
    "Severity",
    "Violation",
    # dependency rules
    "AllowedRootsRule",
    "ForbiddenImportRule",
    "LayerRule",
    "NoCyclesRule",
    "default_dependency_rules",
    # boundary rules
    "BOUNDED_CONTEXTS",
    "ContextIsolationRule",
    "PersistenceEncapsulationRule",
    "NoLegacyImportRule",
    "InterfacePurityRule",
    "default_boundary_rules",
    # state guard
    "FileStateRule",
    "APPROVED_STORES",
    "GRANDFATHERED_STORES",
    "STATE_FILE_EXTENSIONS",
    "scan_state_files",
    # invariants
    "InvariantCheck",
    "InvariantStatus",
    "constitutional_invariants",
    # reporting
    "render_text",
    "render_markdown",
    "to_dict",
    "dependency_summary",
]
