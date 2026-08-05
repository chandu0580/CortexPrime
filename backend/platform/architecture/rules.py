"""Core types for architecture rules.

An architecture rule is a *fitness function*: a check that either holds over the
codebase or reports precisely where it does not. Rules are data, not prose, so
that the Constitution can be executed rather than merely cited.

Design constraint that shapes everything here: every rule operates on a
:class:`ModuleGraph` built from a root directory, never on hard-coded paths.
That is what makes a rule testable in both directions -- a test can synthesize a
tree that *violates* the rule and assert the rule catches it. A rule that can
only be run against the real repository can only ever be shown to pass, which
proves nothing about whether it would catch a regression.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional, Protocol, runtime_checkable

__all__ = [
    "Severity",
    "Violation",
    "RuleResult",
    "ArchitectureRule",
    "ModuleInfo",
    "ModuleGraph",
]


class Severity(str, Enum):
    """How a violation should be treated.

    ``ERROR`` blocks a merge. ``WARNING`` is reported and does not. The
    distinction exists because some rules describe a destination the codebase is
    still migrating toward -- reporting those as errors would mean the suite is
    red permanently, which trains people to ignore it.
    """

    ERROR = "error"
    WARNING = "warning"

    @property
    def blocks_merge(self) -> bool:
        return self is Severity.ERROR


@dataclass(frozen=True)
class Violation:
    """One specific breach, located precisely enough to fix without searching."""

    rule_id: str
    severity: Severity
    module: str
    detail: str
    line: Optional[int] = None
    offender: Optional[str] = None

    def location(self) -> str:
        return f"{self.module}:{self.line}" if self.line else self.module

    def __str__(self) -> str:
        return f"[{self.rule_id}] {self.location()} — {self.detail}"

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "module": self.module,
            "line": self.line,
            "offender": self.offender,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RuleResult:
    """The outcome of evaluating one rule."""

    rule_id: str
    description: str
    violations: tuple[Violation, ...] = field(default_factory=tuple)
    modules_checked: int = 0
    skipped: bool = False
    skip_reason: Optional[str] = None

    @property
    def passed(self) -> bool:
        """A skipped rule does not pass -- it was not evaluated.

        Reporting a skip as a pass is how an unenforced invariant comes to look
        enforced, which is worse than knowing it is not.
        """
        if self.skipped:
            return False
        return not any(v.severity.blocks_merge for v in self.violations)

    @property
    def blocking_violations(self) -> tuple[Violation, ...]:
        return tuple(v for v in self.violations if v.severity.blocks_merge)

    @property
    def warnings(self) -> tuple[Violation, ...]:
        return tuple(v for v in self.violations if not v.severity.blocks_merge)

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "passed": self.passed,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "modules_checked": self.modules_checked,
            "violations": [v.to_dict() for v in self.violations],
        }


@runtime_checkable
class ArchitectureRule(Protocol):
    """A checkable architectural constraint.

    Implementations must be pure: the same graph must always produce the same
    result, with no I/O beyond reading the graph it was given.
    """

    rule_id: str
    description: str

    def evaluate(self, graph: "ModuleGraph") -> RuleResult: ...


@dataclass(frozen=True)
class ModuleInfo:
    """One Python module and the imports it declares."""

    name: str
    """Dotted module path, e.g. ``backend.contracts.approval``."""

    path: Path
    imports: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    """``(imported_module, line_number)`` pairs, in source order."""

    def imports_matching(self, prefix: str) -> tuple[tuple[str, int], ...]:
        return tuple(
            (name, line)
            for name, line in self.imports
            if name == prefix or name.startswith(prefix + ".")
        )

    @property
    def import_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.imports)


class ModuleGraph:
    """The import graph of a package tree.

    Built by parsing source with :mod:`ast` rather than importing, so analysis
    never executes application code and never depends on import side effects
    resolving cleanly.
    """

    __slots__ = ("_modules", "_root", "_package_root")

    def __init__(self, modules: dict[str, ModuleInfo], root: Path, package_root: str) -> None:
        self._modules = modules
        self._root = root
        self._package_root = package_root

    # -- construction -------------------------------------------------

    @classmethod
    def build(
        cls,
        root: Path,
        package_root: str = "backend",
        *,
        exclude: Iterable[str] = ("__pycache__", ".venv", "node_modules"),
    ) -> "ModuleGraph":
        """Parse every module under ``root`` into a graph.

        A file that cannot be parsed is skipped rather than raising: a syntax
        error is the type checker's problem, and an architecture suite that
        cannot run because one unrelated file is broken is an architecture suite
        nobody keeps green.
        """
        root = Path(root).resolve()
        excluded = tuple(exclude)
        modules: dict[str, ModuleInfo] = {}

        for path in sorted(root.rglob("*.py")):
            if any(part in excluded for part in path.parts):
                continue
            relative = path.relative_to(root.parent)
            parts = list(relative.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            name = ".".join(parts) if parts else package_root

            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue

            imports: list[tuple[str, int]] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append((alias.name, node.lineno))
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        # Relative import: resolve against the containing package.
                        base = name.rsplit(".", node.level) if "." in name else [name]
                        prefix = base[0] if base else name
                        resolved = f"{prefix}.{node.module}" if node.module else prefix
                        imports.append((resolved, node.lineno))
                    elif node.module:
                        imports.append((node.module, node.lineno))

            modules[name] = ModuleInfo(name=name, path=path, imports=tuple(imports))

        return cls(modules, root, package_root)

    # -- access -------------------------------------------------------

    @property
    def package_root(self) -> str:
        return self._package_root

    @property
    def root(self) -> Path:
        return self._root

    def __len__(self) -> int:
        return len(self._modules)

    def __contains__(self, name: object) -> bool:
        return name in self._modules

    def get(self, name: str) -> Optional[ModuleInfo]:
        return self._modules.get(name)

    def modules(self) -> tuple[ModuleInfo, ...]:
        return tuple(self._modules.values())

    def modules_under(self, prefix: str) -> tuple[ModuleInfo, ...]:
        """Every module in a package subtree, e.g. ``backend.contracts``."""
        return tuple(
            module
            for module in self._modules.values()
            if module.name == prefix or module.name.startswith(prefix + ".")
        )

    def internal_edges(self) -> dict[str, set[str]]:
        """Adjacency restricted to modules present in this graph.

        External imports are excluded because a dependency on a library is not
        an architectural relationship this package can reason about.
        """
        known = set(self._modules)
        edges: dict[str, set[str]] = {}
        for module in self._modules.values():
            targets: set[str] = set()
            for imported, _ in module.imports:
                if imported in known:
                    targets.add(imported)
                    continue
                # An import of a submodule resolves to the nearest known package.
                parts = imported.split(".")
                while parts:
                    parts.pop()
                    candidate = ".".join(parts)
                    if candidate in known:
                        targets.add(candidate)
                        break
            targets.discard(module.name)
            edges[module.name] = targets
        return edges
