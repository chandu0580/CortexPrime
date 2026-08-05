"""Bounded context boundary rules.

Constitution S2: contexts communicate by published contract only -- no shared
tables, no reaching through. Two rules enforce that shape.

**Contexts do not import each other.** A direct import is the most common way a
boundary erodes, and it is invisible in review once the codebase is large enough
that nobody reads the import block.

**Nothing reaches another context's persistence.** This is the subtler and more
damaging violation: importing a repository or model from another context couples
two schemas together permanently, and it looks harmless at the call site.

Both are reported with the specific offending import, because "there is a
boundary violation somewhere" is not something anyone can act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.platform.architecture.rules import (
    ModuleGraph,
    RuleResult,
    Severity,
    Violation,
)

__all__ = [
    "ContextIsolationRule",
    "PersistenceEncapsulationRule",
    "NoLegacyImportRule",
    "InterfacePurityRule",
    "default_boundary_rules",
    "BOUNDED_CONTEXTS",
]

#: The nine bounded contexts named in the Constitution.
BOUNDED_CONTEXTS = (
    "mission",
    "evidence",
    "reasoning",
    "verification",
    "execution",
    "governance",
    "knowledge",
    "connectivity",
    "tenancy",
)


@dataclass(frozen=True)
class ContextIsolationRule:
    """No bounded context imports another directly."""

    rule_id: str = "BND-CONTEXT-ISOLATION"
    description: str = "Bounded contexts do not import each other"
    contexts_root: str = "backend.contexts"
    contexts: tuple[str, ...] = BOUNDED_CONTEXTS
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        present = [
            name
            for name in self.contexts
            if graph.modules_under(f"{self.contexts_root}.{name}")
        ]
        if not present:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason=(
                    f"no contexts found under {self.contexts_root!r}; the strangler "
                    "migration has not created them yet (PR-40)"
                ),
            )

        violations: list[Violation] = []
        checked = 0
        for context in present:
            own_prefix = f"{self.contexts_root}.{context}"
            for module in graph.modules_under(own_prefix):
                checked += 1
                for other in present:
                    if other == context:
                        continue
                    other_prefix = f"{self.contexts_root}.{other}"
                    for imported, line in module.imports_matching(other_prefix):
                        violations.append(
                            Violation(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                module=module.name,
                                line=line,
                                offender=imported,
                                detail=(
                                    f"context {context!r} imports context {other!r}; "
                                    "contexts communicate by published contract only"
                                ),
                            )
                        )
        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=checked,
        )


@dataclass(frozen=True)
class PersistenceEncapsulationRule:
    """No module reaches into another context's persistence layer.

    Matches any import naming a persistence submodule (``repository``,
    ``models``, ``store``, ``schema``, ``tables``) inside a context other than
    the importer's own.
    """

    rule_id: str = "BND-PERSISTENCE"
    description: str = "No context reaches into another context's persistence"
    contexts_root: str = "backend.contexts"
    contexts: tuple[str, ...] = BOUNDED_CONTEXTS
    persistence_markers: tuple[str, ...] = (
        "repository",
        "repositories",
        "models",
        "store",
        "stores",
        "schema",
        "tables",
        "persistence",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        present = [
            name
            for name in self.contexts
            if graph.modules_under(f"{self.contexts_root}.{name}")
        ]
        if not present:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason=f"no contexts found under {self.contexts_root!r}",
            )

        violations: list[Violation] = []
        checked = 0
        for context in present:
            own_prefix = f"{self.contexts_root}.{context}"
            for module in graph.modules_under(own_prefix):
                checked += 1
                for imported, line in module.imports:
                    if not imported.startswith(self.contexts_root + "."):
                        continue
                    segments = imported.split(".")
                    target_context = segments[len(self.contexts_root.split("."))]
                    if target_context == context:
                        continue
                    if any(marker in segments for marker in self.persistence_markers):
                        violations.append(
                            Violation(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                module=module.name,
                                line=line,
                                offender=imported,
                                detail=(
                                    f"reaches into {target_context!r} persistence via "
                                    f"{imported!r}; couples two schemas permanently"
                                ),
                            )
                        )
        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=checked,
        )


@dataclass(frozen=True)
class NoLegacyImportRule:
    """New code must not depend on the strangler zone.

    The ratchet that makes incremental migration finish: ``legacy/`` may import
    anything, but nothing outside it may import ``legacy/``. Without this the
    zone grows dependents and never shrinks.
    """

    rule_id: str = "BND-NO-LEGACY"
    description: str = "No module outside legacy/ imports from legacy/"
    legacy_prefix: str = "backend.legacy"
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        if not graph.modules_under(self.legacy_prefix):
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason=(
                    f"{self.legacy_prefix!r} does not exist yet; the strangler "
                    "boundary is created in PR-40"
                ),
            )

        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if module.name == self.legacy_prefix or module.name.startswith(
                self.legacy_prefix + "."
            ):
                continue
            checked += 1
            for imported, line in module.imports_matching(self.legacy_prefix):
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        module=module.name,
                        line=line,
                        offender=imported,
                        detail=(
                            f"imports {imported!r} from the strangler zone; legacy/ "
                            "may only shrink"
                        ),
                    )
                )
        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=checked,
        )


@dataclass(frozen=True)
class InterfacePurityRule:
    """Delivery interfaces contain translation, not business logic.

    Approximated by checking that interface modules do not import persistence
    directly -- an API handler that talks to a repository has skipped the
    context that owns the rule.
    """

    rule_id: str = "BND-INTERFACE-PURITY"
    description: str = "Interfaces do not import persistence directly"
    interface_prefixes: tuple[str, ...] = ("backend.interfaces", "backend.api")
    forbidden_prefixes: tuple[str, ...] = ("backend.database",)
    severity: Severity = Severity.WARNING
    """Warning rather than error: the existing ``backend/api`` predates this
    rule and violates it widely. Reporting it as an error would make the suite
    permanently red, which teaches people to ignore it. It becomes an error
    once the API layer migrates."""

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for prefix in self.interface_prefixes:
            for module in graph.modules_under(prefix):
                checked += 1
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
                                    f"interface module imports persistence {imported!r}; "
                                    "interfaces translate, contexts decide"
                                ),
                            )
                        )
        if not checked:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason="no interface modules found",
            )
        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=checked,
        )


def default_boundary_rules() -> tuple:
    """The boundary rules the Constitution defines."""
    return (
        ContextIsolationRule(),
        PersistenceEncapsulationRule(),
        NoLegacyImportRule(),
        InterfacePurityRule(),
    )
