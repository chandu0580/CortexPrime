"""The fitness-function runner: evaluate every rule and decide the CI gate.

A fitness function is a check the architecture must keep passing as the code
evolves. Running them together, on every commit, is what turns the Constitution
from a document into a constraint.

The gate
--------
:meth:`ArchitectureSuite.run` returns a :class:`SuiteResult` whose
``gate_passed`` decides whether a merge is allowed. Three categories, treated
differently on purpose:

**Blocking failures** -- an enforced rule or invariant is violated. Merge stops.

**Warnings** -- a rule the codebase is still migrating toward. Reported, does
not block. Without this category the suite would be permanently red, and a
permanently red suite is one people learn to ignore.

**Skips** -- a rule with nothing to check yet, or an invariant with no
enforcement point. Reported as skipped, **never as passed**, because a skip
counted as a pass is how an unenforced invariant comes to look enforced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence

from backend.platform.architecture.boundary_rules import default_boundary_rules
from backend.platform.architecture.dependency_rules import default_dependency_rules
from backend.platform.architecture.invariant_tests import (
    InvariantCheck,
    InvariantStatus,
    constitutional_invariants,
)
from backend.platform.architecture.state_rules import (
    GRANDFATHERED_STORES,
    FileStateRule,
)
from backend.platform.architecture.tenancy_rules import (
    GRANDFATHERED_REPOSITORIES,
    RepositoryContextRule,
)
from backend.platform.architecture.rules import (
    ArchitectureRule,
    ModuleGraph,
    RuleResult,
    Severity,
    Violation,
)

__all__ = ["SuiteResult", "ArchitectureSuite", "default_suite"]


@dataclass(frozen=True)
class SuiteResult:
    """The outcome of a full architecture evaluation."""

    results: tuple[RuleResult, ...]
    modules_analyzed: int
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def passed(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if r.passed)

    @property
    def failed(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if not r.passed and not r.skipped)

    @property
    def skipped(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if r.skipped)

    @property
    def warned(self) -> tuple[RuleResult, ...]:
        """Rules that produced only non-blocking violations."""
        return tuple(r for r in self.results if r.warnings and not r.blocking_violations)

    @property
    def blocking_violations(self) -> tuple[Violation, ...]:
        return tuple(v for r in self.results for v in r.blocking_violations)

    @property
    def all_warnings(self) -> tuple[Violation, ...]:
        return tuple(v for r in self.results for v in r.warnings)

    @property
    def gate_passed(self) -> bool:
        """Whether a merge is permitted. The single value CI reads."""
        return not self.blocking_violations

    def result_for(self, rule_id: str) -> Optional[RuleResult]:
        for result in self.results:
            if result.rule_id == rule_id:
                return result
        return None

    def summary(self) -> str:
        state = "PASS" if self.gate_passed else "FAIL"
        return (
            f"architecture {state}: {len(self.passed)} passed, "
            f"{len(self.failed)} failed, {len(self.skipped)} skipped, "
            f"{len(self.all_warnings)} warning(s) across "
            f"{self.modules_analyzed} modules"
        )


class ArchitectureSuite:
    """A collection of rules and invariants evaluated together."""

    __slots__ = ("_rules", "_invariants")

    def __init__(
        self,
        rules: Sequence[ArchitectureRule] = (),
        invariants: Sequence[InvariantCheck] = (),
    ) -> None:
        self._rules = tuple(rules)
        self._invariants = tuple(invariants)

    @property
    def rules(self) -> tuple[ArchitectureRule, ...]:
        return self._rules

    @property
    def invariants(self) -> tuple[InvariantCheck, ...]:
        return self._invariants

    @property
    def gated_invariants(self) -> tuple[InvariantCheck, ...]:
        """Invariants whose failure blocks a merge."""
        return tuple(check for check in self._invariants if check.status.is_gated)

    def run(self, graph: ModuleGraph) -> SuiteResult:
        """Evaluate everything against ``graph``.

        A rule that raises is reported as a failure rather than crashing the
        run: one broken rule must not hide the results of the other twenty.
        """
        results: list[RuleResult] = []

        for rule in list(self._rules) + list(self._invariants):
            try:
                results.append(rule.evaluate(graph))
            except Exception as exc:  # noqa: BLE001 - a broken rule is a failure
                results.append(
                    RuleResult(
                        rule_id=getattr(rule, "rule_id", type(rule).__name__),
                        description=getattr(rule, "description", ""),
                        violations=(
                            Violation(
                                rule_id=getattr(rule, "rule_id", "UNKNOWN"),
                                severity=Severity.ERROR,
                                module="<rule>",
                                detail=f"rule raised {type(exc).__name__}: {exc}",
                            ),
                        ),
                    )
                )

        return SuiteResult(results=tuple(results), modules_analyzed=len(graph))


def default_suite(probes: Optional[dict] = None) -> ArchitectureSuite:
    """The suite CortexPrime's Constitution defines.

    ``probes`` is forwarded to :func:`constitutional_invariants` for invariants
    whose enforcement lives outside ``platform/`` and which this package
    therefore may not import.
    """
    return ArchitectureSuite(
        rules=(
            default_dependency_rules()
            + default_boundary_rules()
            + (
                FileStateRule(grandfathered=GRANDFATHERED_STORES),
                RepositoryContextRule(grandfathered=GRANDFATHERED_REPOSITORIES),
            )
        ),
        invariants=constitutional_invariants(probes),
    )


def analyze(
    root: Optional[Path] = None,
    *,
    suite: Optional[ArchitectureSuite] = None,
    probes: Optional[dict] = None,
) -> SuiteResult:
    """Build the graph and run the suite. The one-call entry point for CI."""
    if root is None:
        root = Path(__file__).resolve().parents[2]  # backend/
    graph = ModuleGraph.build(root)
    return (suite or default_suite(probes)).run(graph)
