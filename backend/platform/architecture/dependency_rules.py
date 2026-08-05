"""Dependency rules: who may import whom, and cycle detection.

Constitution S10 states the dependency rule as prose::

    contracts/  depends on nothing
    platform/   may import contracts/, never contexts/ or legacy/
    contexts/   may import contracts/ and platform/, never each other
    interfaces/ may import contracts and context entry points only
    legacy/     may import anything; nothing new may import legacy/

This module turns that into rules a build can fail on. Prose in a document is
advice; a rule in CI is a constraint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from backend.platform.architecture.rules import (
    ModuleGraph,
    RuleResult,
    Severity,
    Violation,
)

__all__ = [
    "ForbiddenImportRule",
    "AllowedRootsRule",
    "NoCyclesRule",
    "LayerRule",
    "default_dependency_rules",
]


@dataclass(frozen=True)
class ForbiddenImportRule:
    """A package subtree must not import from named other subtrees."""

    rule_id: str
    description: str
    source_prefix: str
    forbidden_prefixes: tuple[str, ...]
    severity: Severity = Severity.ERROR
    exempt_modules: frozenset[str] = field(default_factory=frozenset)

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        modules = graph.modules_under(self.source_prefix)
        if not modules:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason=f"no modules found under {self.source_prefix!r}",
            )

        violations: list[Violation] = []
        for module in modules:
            if module.name in self.exempt_modules:
                continue
            for forbidden in self.forbidden_prefixes:
                for imported, line in module.imports_matching(forbidden):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"{self.source_prefix} must not import {forbidden}; "
                                f"found {imported!r}"
                            ),
                        )
                    )
        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=len(modules),
        )


@dataclass(frozen=True)
class AllowedRootsRule:
    """A subtree may import only from an explicit allowlist of root modules.

    Used for ``contracts``, where the allowlist is the standard library plus
    itself. An allowlist rather than a denylist because the whole point is that
    a *new* dependency should require a decision, and a denylist cannot express
    that.
    """

    rule_id: str
    description: str
    source_prefix: str
    allowed_roots: frozenset[str]
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        modules = graph.modules_under(self.source_prefix)
        if not modules:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason=f"no modules found under {self.source_prefix!r}",
            )

        violations: list[Violation] = []
        for module in modules:
            for imported, line in module.imports:
                root = imported.split(".")[0]
                if root in self.allowed_roots:
                    continue
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        module=module.name,
                        line=line,
                        offender=imported,
                        detail=(
                            f"{imported!r} is not in the allowlist for "
                            f"{self.source_prefix}; adding a dependency here requires an ADR"
                        ),
                    )
                )
        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=len(modules),
        )


@dataclass(frozen=True)
class NoCyclesRule:
    """No import cycles within a package subtree.

    A cycle means two modules cannot be understood, tested, or replaced
    independently. Reported as the actual cycle path rather than a bare
    assertion, because "there is a cycle somewhere in 698 files" is not
    actionable.
    """

    rule_id: str = "DEP-CYCLE"
    description: str = "No circular imports within the package"
    scope_prefix: Optional[str] = None
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        edges = graph.internal_edges()
        if self.scope_prefix is not None:
            scoped = {
                name: {
                    target
                    for target in targets
                    if target == self.scope_prefix
                    or target.startswith(self.scope_prefix + ".")
                }
                for name, targets in edges.items()
                if name == self.scope_prefix or name.startswith(self.scope_prefix + ".")
            }
            edges = scoped

        if not edges:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason=f"no modules found under {self.scope_prefix!r}",
            )

        violations: list[Violation] = []
        seen_cycles: set[frozenset[str]] = set()

        WHITE, GREY, BLACK = 0, 1, 2
        colour = {name: WHITE for name in edges}

        def walk(node: str, stack: list[str]) -> None:
            colour[node] = GREY
            stack.append(node)
            for target in sorted(edges.get(node, ())):
                if target not in colour:
                    continue
                if colour[target] == GREY:
                    cycle = stack[stack.index(target) :] + [target]
                    signature = frozenset(cycle)
                    if signature not in seen_cycles:
                        seen_cycles.add(signature)
                        violations.append(
                            Violation(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                module=node,
                                offender=target,
                                detail="import cycle: " + " -> ".join(cycle),
                            )
                        )
                elif colour[target] == WHITE:
                    walk(target, stack)
            stack.pop()
            colour[node] = BLACK

        for name in sorted(edges):
            if colour[name] == WHITE:
                walk(name, [])

        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=len(edges),
        )


@dataclass(frozen=True)
class LayerRule:
    """A layer may import only from layers at or below its own level.

    Expresses the Constitution's stack in one rule rather than N pairwise
    forbidden-import rules, so adding a layer does not mean remembering to add
    every pairing.
    """

    rule_id: str
    description: str
    layers: tuple[tuple[str, int], ...]
    """``(package_prefix, level)``. Lower levels are more foundational."""

    severity: Severity = Severity.ERROR

    def _level_of(self, module_name: str) -> Optional[int]:
        best: Optional[tuple[int, int]] = None
        for prefix, level in self.layers:
            if module_name == prefix or module_name.startswith(prefix + "."):
                depth = len(prefix)
                if best is None or depth > best[0]:
                    best = (depth, level)
        return best[1] if best else None

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            source_level = self._level_of(module.name)
            if source_level is None:
                continue
            checked += 1
            for imported, line in module.imports:
                target_level = self._level_of(imported)
                if target_level is None:
                    continue
                if target_level > source_level:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"layer violation: level-{source_level} module imports "
                                f"level-{target_level} module {imported!r}; dependencies "
                                "must point downward"
                            ),
                        )
                    )

        if not checked:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason="no layered modules found",
            )
        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=checked,
        )


#: Standard library modules the contracts package may use. Mirrors the
#: allowlist in ``tests/contracts/test_dependency_isolation.py``; the two are
#: kept deliberately consistent, and this is the canonical copy.
CONTRACTS_ALLOWED_ROOTS = frozenset(
    {
        "__future__", "abc", "dataclasses", "datetime", "enum", "hmac",
        "types", "typing", "uuid", "backend",
    }
)


def default_dependency_rules(package_root: str = "backend") -> tuple:
    """The dependency rules the Constitution defines for CortexPrime."""
    contracts = f"{package_root}.contracts"
    platform = f"{package_root}.platform"

    return (
        AllowedRootsRule(
            rule_id="DEP-CONTRACTS-LEAF",
            description="contracts/ depends on nothing but the standard library",
            source_prefix=contracts,
            allowed_roots=CONTRACTS_ALLOWED_ROOTS,
        ),
        ForbiddenImportRule(
            rule_id="DEP-CONTRACTS-NO-BACKEND",
            description="contracts/ imports no other backend package",
            source_prefix=contracts,
            forbidden_prefixes=(
                f"{package_root}.platform",
                f"{package_root}.contexts",
                f"{package_root}.services",
                f"{package_root}.api",
                f"{package_root}.database",
                f"{package_root}.legacy",
            ),
        ),
        ForbiddenImportRule(
            rule_id="DEP-PLATFORM-NO-CONTEXTS",
            description="platform/ never imports a bounded context or legacy code",
            source_prefix=platform,
            forbidden_prefixes=(
                f"{package_root}.contexts",
                f"{package_root}.services",
                f"{package_root}.api",
                f"{package_root}.legacy",
                f"{package_root}.database",
            ),
        ),
        LayerRule(
            rule_id="DEP-LAYERS",
            description="Dependencies point downward through the architectural layers",
            layers=(
                (contracts, 0),
                (platform, 1),
                (f"{package_root}.contexts", 2),
                (f"{package_root}.api", 3),
            ),
        ),
        NoCyclesRule(rule_id="DEP-CYCLE-CONTRACTS", scope_prefix=contracts,
                     description="No import cycles within contracts/"),
        NoCyclesRule(rule_id="DEP-CYCLE-PLATFORM", scope_prefix=platform,
                     description="No import cycles within platform/"),
    )
