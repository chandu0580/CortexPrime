"""Storage boundary tenant enforcement, checked statically.

Constitution I6 requires tenant identity to reach the storage layer. A guard that
enforces it exists (:mod:`backend.platform.storage`), but a guard only protects
the repositories that use it -- and nothing in the type system compels a new
repository to. This rule is that compulsion.

What it detects
---------------
A *repository* is a class whose name ends in ``Repository`` and which is defined
under a persistence path. For each, every public method is checked for a
parameter that could carry an execution context. A method with none cannot be
deriving tenant identity from one, because there is nothing to derive it from.

It also flags the inverse mistake: a method that accepts ``tenant_id`` as a
parameter. That is not an oversight, it is the anti-pattern the invariant names
-- a repository whose caller chooses the isolation boundary is not isolating
anything.

The ratchet
-----------
:data:`GRANDFATHERED_REPOSITORIES` records the repositories that predate the
guard. They are reported as warnings, not errors, so the gate stays green while
they are migrated one at a time. Anything *not* on the list is an error and
blocks the merge.

This is the same one-way ratchet ``state_rules.GRANDFATHERED_STORES`` uses, with
the same rule: **the list may only shrink.** A change that adds an entry is
adding a known cross-tenant hazard, and reviewing it as a one-line diff to a
frozenset is the point -- it is much harder to wave through than a new file.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.platform.architecture.rules import (
    ModuleGraph,
    RuleResult,
    Severity,
    Violation,
)

__all__ = [
    "CONTEXT_PARAMETER_NAMES",
    "TENANT_PARAMETER_NAMES",
    "GRANDFATHERED_REPOSITORIES",
    "RepositoryMethod",
    "scan_repository_classes",
    "scan_repository_methods",
    "RepositoryContextRule",
]


# A parameter carrying an execution context. Names rather than annotations,
# because most of this codebase is unannotated and a rule that only understood
# ``context: ExecutionContext`` would pass every unannotated repository in it.
CONTEXT_PARAMETER_NAMES = frozenset({"context", "ctx", "execution_context", "exec_context"})

# A parameter naming a tenant directly. Accepting one is the violation, not the
# fix: tenant identity must be derived from the context, never chosen by the
# caller. ``organization_id`` is deliberately absent -- an organization is not an
# isolation boundary (see backend/contracts/tenant.py), so scoping by one is a
# separate and lesser concern this rule does not adjudicate.
TENANT_PARAMETER_NAMES = frozenset({"tenant_id", "tenant", "tenant_ref"})

# Where repositories live. A class named ``*Repository`` outside these paths is
# something else -- a client, a test double -- and not this rule's business.
_PERSISTENCE_PATH_PARTS = frozenset(
    {"repositories", "repository", "stores", "store", "persistence"}
)

_EXEMPT_PATH_PARTS = frozenset({"__pycache__", "tests", "test", "migrations", "legacy"})

# Methods that are structurally incapable of touching tenant-scoped rows.
_EXEMPT_METHOD_NAMES = frozenset(
    {"to_dict", "from_dict", "to_enterprise_dict", "health", "close", "dispose"}
)


# ----------------------------------------------------------------------
# The ratchet -- may only shrink
# ----------------------------------------------------------------------

GRANDFATHERED_REPOSITORIES: frozenset[str] = frozenset(
    {
        # backend/database/repositories/ -- the SQLAlchemy layer. None of these
        # can be scoped until their models carry a tenant column; see ADR-018
        # "Remaining risks" and PR-11.
        "AgentConfigRepository",
        "AgentStateRepository",
        "AnalyticsRepository",
        "ApiKeyRepository",
        "ApprovalRequestRepository",
        "BaseRepository",
        "ComplianceRuleRepository",
        "ConnectorActivityRepository",
        "ConnectorConfigRepository",
        "DepartmentRepository",
        "EmbeddingCacheRepository",
        "EnterpriseAuditRepository",
        "EpisodicRepository",
        "ExecutionEventRepository",
        "ExecutionRepository",
        "FeatureFlagRepository",
        "InfrastructureMetricRepository",
        "InfrastructureModelRepository",
        "InfrastructureRelationshipRepository",
        "InvoiceRepository",
        "KnowledgeEntryRepository",
        "KnowledgeRelationshipRepository",
        "LearningPatternRepository",
        "LearningSessionRepository",
        "MissionRepository",
        "MissionStepRepository",
        "OrganizationRepository",
        "PlatformSettingRepository",
        "PolicyRepository",
        "ProjectRepository",
        "ReflectionRepository",
        "RoleRepository",
        "SemanticRepository",
        "UsageRecordRepository",
        "UserRepository",
        # Repositories outside backend/database/
        "CostRepository",
        "FleetRepository",
        "WorkflowRepository",
        # backend/infrastructure/neo4j/repositories/ -- graph storage
        "AgentRepository",
        "CognitionRepository",
        "MemoryRepository",
        "WorldModelRepository",
    }
)


@dataclass(frozen=True)
class RepositoryMethod:
    """One public repository method and what it accepts."""

    module: str
    path: Path
    repository: str
    method: str
    line: int
    parameters: tuple[str, ...]

    @property
    def takes_context(self) -> bool:
        return any(name in CONTEXT_PARAMETER_NAMES for name in self.parameters)

    @property
    def takes_tenant(self) -> tuple[str, ...]:
        """Tenant parameters accepted directly -- each one a violation."""
        return tuple(name for name in self.parameters if name in TENANT_PARAMETER_NAMES)

    @property
    def is_grandfathered(self) -> bool:
        return self.repository in GRANDFATHERED_REPOSITORIES

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.repository}.{self.method}"


def _is_exempt_path(path: Path) -> bool:
    return any(part in _EXEMPT_PATH_PARTS for part in path.parts)


def _is_persistence_path(path: Path) -> bool:
    return any(part.lower() in _PERSISTENCE_PATH_PARTS for part in path.parts) or any(
        part.lower() in _PERSISTENCE_PATH_PARTS for part in path.stem.split("_")
    )


def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """Every parameter name, positional through keyword-only, minus ``self``."""
    args = node.args
    names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    if args.vararg:
        names.append(args.vararg.arg)
    if args.kwarg:
        names.append(args.kwarg.arg)
    return tuple(name for name in names if name not in {"self", "cls"})


def _is_scoped_base(node: ast.ClassDef) -> bool:
    """Whether a class already inherits the guarded base.

    A ``TenantScopedRepository`` subclass has the context threaded through it by
    construction, so its own methods need no separate check.
    """
    for base in node.bases:
        name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
        if name == "TenantScopedRepository":
            return True
        # TenantScopedRepository[Model]
        if isinstance(base, ast.Subscript):
            inner = base.value
            inner_name = inner.id if isinstance(inner, ast.Name) else getattr(inner, "attr", None)
            if inner_name == "TenantScopedRepository":
                return True
    return False


def scan_repository_classes(graph: ModuleGraph) -> frozenset[str]:
    """Every repository class the rule considers in scope.

    Separate from :func:`scan_repository_methods` because the two answer
    different questions, and conflating them made the rule report a *skip* for a
    repository whose methods were all private -- which reads as "not checked"
    when in fact it was checked and was clean.
    """
    return frozenset(name for name, _ in _scan(graph)[0])


def scan_repository_methods(graph: ModuleGraph) -> list[RepositoryMethod]:
    """Every public method of every repository class in the graph."""
    return _scan(graph)[1]


def _scan(graph: ModuleGraph) -> tuple[list[tuple[str, str]], list[RepositoryMethod]]:
    """Walk the graph once, returning ``(classes, methods)``."""
    classes: list[tuple[str, str]] = []
    found: list[RepositoryMethod] = []

    for module in graph.modules():
        if _is_exempt_path(module.path) or not _is_persistence_path(module.path):
            continue
        try:
            tree = ast.parse(module.path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("Repository"):
                continue
            # Counted as checked either way. A TenantScopedRepository subclass
            # has the context threaded through it by construction, so its own
            # methods need no inspection -- but recording it as "nothing to
            # check" would report compliance as absence.
            classes.append((node.name, module.name))
            if _is_scoped_base(node):
                continue

            for member in node.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name.startswith("_") or member.name in _EXEMPT_METHOD_NAMES:
                    continue
                # A @staticmethod has no instance and cannot hold a guard.
                decorators = {
                    d.id if isinstance(d, ast.Name) else getattr(d, "attr", "")
                    for d in member.decorator_list
                }
                if "staticmethod" in decorators or "property" in decorators:
                    continue

                found.append(
                    RepositoryMethod(
                        module=module.name,
                        path=module.path,
                        repository=node.name,
                        method=member.name,
                        line=member.lineno,
                        parameters=_parameter_names(member),
                    )
                )

    return classes, found


@dataclass(frozen=True)
class RepositoryContextRule:
    """Every repository method must accept an execution context.

    Errors for repositories written after the guard existed; warnings for the
    grandfathered ones, so the gate stays green while they migrate.
    """

    rule_id: str = "TENANT-REPOSITORY-CONTEXT"
    description: str = "Repository methods require an ExecutionContext and never take a tenant_id"
    grandfathered: frozenset[str] = field(default_factory=lambda: GRANDFATHERED_REPOSITORIES)

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        classes, methods = _scan(graph)

        # A skip means "nothing to check". A repository whose methods are all
        # private or static *was* checked, so it is a pass -- reporting it as a
        # skip would understate the coverage the gate actually has.
        if not classes:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                skipped=True,
                skip_reason="no repository classes found",
            )

        violations: list[Violation] = []

        for method in methods:
            legacy = method.repository in self.grandfathered
            severity = Severity.WARNING if legacy else Severity.ERROR

            # Accepting a tenant directly is the stronger finding: the method is
            # not merely unscoped, it hands the isolation boundary to its caller.
            tenant_params = method.takes_tenant
            if tenant_params:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        severity=severity,
                        module=method.module,
                        detail=(
                            f"{method.repository}.{method.method} accepts "
                            f"{', '.join(tenant_params)} directly; tenant identity must be "
                            "derived from the ExecutionContext, never supplied by the caller"
                        ),
                        line=method.line,
                        offender=str(method),
                    )
                )
                continue

            if not method.takes_context:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        severity=severity,
                        module=method.module,
                        detail=(
                            f"{method.repository}.{method.method} takes no execution context "
                            f"(expected one of: {', '.join(sorted(CONTEXT_PARAMETER_NAMES))})"
                        ),
                        line=method.line,
                        offender=str(method),
                    )
                )

        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=len({module for _, module in classes}),
        )


def stale_grandfather_entries(graph: ModuleGraph) -> tuple[str, ...]:
    """Grandfathered names no repository in the graph still uses.

    The ratchet only tightens if dead entries are removed. Reported rather than
    enforced -- a stale entry is untidy, not a hazard, and failing the build over
    one would make deleting a repository harder than keeping it.
    """
    live = {method.repository for method in scan_repository_methods(graph)}
    return tuple(sorted(GRANDFATHERED_REPOSITORIES - live))
