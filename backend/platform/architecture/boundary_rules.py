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
    "LegacyAuditQuarantineRule",
    "AmbientProviderCredentialRule",
    "DirectProviderHttpRule",
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
class LegacyAuditQuarantineRule:
    """The legacy approval-audit facade may only shrink (ADR-057).

    ``enterprise_integrity_audit`` is a strangled surface: an adapter over the
    platform ``AuditRuntime`` whose sink the application root rebinds to the
    durable authority. Its *interface* survives for the approval dispatcher;
    its *reach* must not grow. In particular the governed composition — the
    bounded contexts, the composition roots under ``backend.api``, the durable
    layer — must never import it: governed execution audits through the
    platform runtime directly, and a second route into audit is how a second
    authority quietly begins.

    Allowed importers, exactly: the approval action dispatcher (the facade's
    one production caller, which *records through* it) and the governed
    application runtime (the composition root, which *rebinds its sink* to
    the durable authority and records nothing through it). Everything else
    is a violation. Removing a name from this list is progress; adding one
    needs an ADR.
    """

    rule_id: str = "BND-LEGACY-AUDIT"
    description: str = (
        "enterprise_integrity_audit is quarantined: only the approval "
        "dispatcher and the rebinding composition root may import it"
    )
    legacy_module: str = "backend.services.enterprise_integrity_audit"
    allowed_importers: tuple[str, ...] = (
        "backend.services.enterprise_approval_action_dispatcher",
        "backend.api.application_runtime",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if module.name == self.legacy_module:
                continue
            checked += 1
            for imported, line in module.imports_matching(self.legacy_module):
                if module.name in self.allowed_importers:
                    continue
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        module=module.name,
                        line=line,
                        offender=imported,
                        detail=(
                            f"imports {imported!r}; the legacy approval-audit "
                            "facade is quarantined to "
                            f"{', '.join(self.allowed_importers)} (ADR-057). "
                            "Audit through backend.platform.audit instead"
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
class AmbientProviderCredentialRule:
    """Provider credentials are a composition decision, not ambient state.

    Phase 5.15 (ADR-058) moved every V1 connector credential read out of the
    connector modules and into one composition act
    (``backend.api.connector_credential_composition``). This rule keeps them
    out: an ``os.getenv``/``os.environ`` access naming a provider credential
    variable, anywhere outside the allowlisted composition/bootstrap sites, is
    a violation. AST-based — a variable name in a comment, docstring, or log
    message does not trip it; only an actual environment access does.

    ``VAULT_TOKEN`` is deliberately not in the name list: it is the
    platform's own bootstrap secret (ADR-040), read by the production
    connectivity builder as part of the bootstrap trust model.
    """

    rule_id: str = "BND-AMBIENT-CREDENTIALS"
    description: str = (
        "provider credential environment variables are read only by the "
        "allowlisted composition roots"
    )
    credential_variables: tuple[str, ...] = (
        "GITHUB_TOKEN", "GH_TOKEN", "GITLAB_TOKEN", "JIRA_API_TOKEN",
        "JIRA_EMAIL", "CONFLUENCE_API_TOKEN", "CONFLUENCE_EMAIL",
        "SLACK_BOT_TOKEN", "TEAMS_ACCESS_TOKEN", "NOTION_API_KEY",
        "CIRCLECI_TOKEN", "AZURE_DEVOPS_PAT", "JENKINS_PASS",
        "SERVICENOW_PASSWORD", "SERVICENOW_USERNAME",
    )
    allowed_modules: tuple[str, ...] = (
        "backend.api.connector_credential_composition",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        import ast as _ast

        wanted = set(self.credential_variables)
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if module.name in self.allowed_modules:
                continue
            checked += 1
            try:
                tree = _ast.parse(module.path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in _ast.walk(tree):
                name: Optional[str] = None
                # os.getenv("X") / os.environ.get("X")
                if (isinstance(node, _ast.Call)
                        and isinstance(node.func, _ast.Attribute)
                        and node.func.attr in ("getenv", "get")
                        and node.args
                        and isinstance(node.args[0], _ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    name = node.args[0].value
                # os.environ["X"]
                elif (isinstance(node, _ast.Subscript)
                        and isinstance(node.value, _ast.Attribute)
                        and node.value.attr == "environ"
                        and isinstance(node.slice, _ast.Constant)
                        and isinstance(node.slice.value, str)):
                    name = node.slice.value
                if name in wanted:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=node.lineno,
                            offender=name,
                            detail=(
                                f"reads provider credential {name!r} from the "
                                "environment; credentials reach connectors only "
                                "through connector_credential_composition "
                                "(ADR-058)"
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
class DirectProviderHttpRule:
    """The governed path speaks to providers only through the transport broker.

    Inside the bounded contexts and the platform credential fabric, importing
    an HTTP client library directly is a violation: a context that can open
    its own connections has a second transport, and a second transport is how
    connection policy, budgets, and audit stop being facts. The one home for
    HTTP client code is ``backend.platform.transport`` (ADR-041). The V1
    connector zone (``backend.connectors``) is a documented quarantine, not an
    endorsement — it is outside this rule's scope and inside the legacy
    boundary's.
    """

    rule_id: str = "BND-DIRECT-HTTP"
    description: str = (
        "bounded contexts and the credential fabric import no HTTP client "
        "library; transport lives in backend.platform.transport"
    )
    scopes: tuple[str, ...] = (
        "backend.contexts",
        "backend.platform.credentials",
    )
    http_libraries: tuple[str, ...] = ("httpx", "requests", "aiohttp", "urllib3")
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not any(module.name == scope or module.name.startswith(scope + ".")
                       for scope in self.scopes):
                continue
            checked += 1
            for library in self.http_libraries:
                for imported, line in module.imports_matching(library):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"imports {imported!r} inside the governed "
                                "path; provider connections go through the "
                                "TransportBroker (ADR-041)"
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
        LegacyAuditQuarantineRule(),
        AmbientProviderCredentialRule(),
        DirectProviderHttpRule(),
        InterfacePurityRule(),
    )
