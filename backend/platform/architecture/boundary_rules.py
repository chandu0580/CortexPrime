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
    "ProcessSpawnQuarantineRule",
    "ProviderSdkImportRule",
    "ConnectorEffectGateRule",
    "HarnessCredentialIsolationRule",
    "HarnessNoExecutionRule",
    "HarnessNoDynamicDispatchRule",
    "WorldCannotExecuteRule",
    "ModelCannotCreateFactRule",
    "WorldApplicationPureRule",
    "ObservationAppendOnlyRule",
    "AssuranceCannotExecuteRule",
    "IntelligenceCannotExecuteRule",
    "NoV1IntelligenceImportRule",
    "IntelligenceCannotBypassWorldRule",
    "WorldCannotImportV1MemoryRule",
    "AuthCannotExecuteRule",
    "ProductCannotBypassExecutionRule",
    "AutonomyNotModelDrivenRule",
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


@dataclass(frozen=True)
class ProcessSpawnQuarantineRule:
    """Process creation happens in exactly four named modules (Phase 6.1, L1).

    A spawned process is a machine side effect no gateway can see. Phase 6.1
    discovery found exactly four spawn sites in the backend — the terraform
    connector, the execution sandbox, the shell-sandbox interface, and the
    (already-quarantined) computer task engine — and put each behind the
    legacy-execution flag or its own refusal. This rule keeps the count at
    four: a new ``subprocess.Popen`` / ``asyncio.create_subprocess_*`` /
    ``os.system`` call site anywhere else is an ERROR, not a review comment.

    AST-based over source, so a spawn in a comment or docstring does not trip
    it — and an alias (``from subprocess import Popen; Popen(...)``) does,
    because bare-name calls matching the spawn vocabulary are matched too.
    """

    rule_id: str = "BND-PROCESS-SPAWN"
    description: str = (
        "process-spawning calls are quarantined to the four audited modules"
    )
    allowed_modules: tuple[str, ...] = (
        "backend.connectors.terraform",
        "backend.services.enterprise_execution_sandbox",
        "backend.execution.sandbox.interfaces",
        "backend.computer.computer_task_engine",
    )
    severity: Severity = Severity.ERROR

    #: Spawn vocabulary per owner. ``run`` is a spawn only on ``subprocess``;
    #: ``asyncio.run`` is the event-loop runner and must not match.
    SPAWN_BY_OWNER = {
        "subprocess": {"Popen", "run", "call", "check_call", "check_output"},
        "asyncio": {"create_subprocess_exec", "create_subprocess_shell"},
        "os": {"system", "popen", "spawnl", "spawnle", "spawnlp", "spawnv",
               "spawnve"},
    }

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        import ast as _ast

        bare_names = {"create_subprocess_exec", "create_subprocess_shell", "Popen"}
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
                if not isinstance(node, _ast.Call):
                    continue
                offender: Optional[str] = None
                func = node.func
                if (isinstance(func, _ast.Attribute)
                        and isinstance(func.value, _ast.Name)
                        and func.attr in self.SPAWN_BY_OWNER.get(func.value.id, ())):
                    offender = f"{func.value.id}.{func.attr}"
                elif isinstance(func, _ast.Name) and func.id in bare_names:
                    offender = func.id
                if offender is not None:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=node.lineno,
                            offender=offender,
                            detail=(
                                f"spawns a process via {offender}; process "
                                "creation is quarantined to "
                                f"{', '.join(self.allowed_modules)} (Phase 6.1, "
                                "L1). Reach the machine through the governed "
                                "execution path instead"
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
class ProviderSdkImportRule:
    """Provider SDKs are imported only by their own connector modules (L1).

    ``docker`` and ``kubernetes`` are direct channels to real infrastructure —
    the local daemon socket and the cluster credential — with no HTTP boundary
    a transport rule could see. Exactly two modules may import them: the two
    V1 connectors that wrap them (both of whose writes sit behind the effect
    gate). A third importer is a new ungoverned side-effect channel.

    Also refuses the dynamic escape: ``importlib.import_module("docker")`` /
    ``__import__("kubernetes")`` with a constant argument, anywhere. The
    import graph cannot see those; this rule's AST pass can.
    """

    rule_id: str = "BND-PROVIDER-SDK"
    description: str = (
        "provider SDK imports (docker, kubernetes) are quarantined to their "
        "connector modules"
    )
    sdk_roots: tuple[str, ...] = ("docker", "kubernetes")
    allowed_modules: tuple[str, ...] = (
        "backend.connectors.docker",
        "backend.connectors.kubernetes",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        import ast as _ast

        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if module.name in self.allowed_modules:
                continue
            checked += 1
            for imported, line in module.imports:
                root = imported.split(".")[0]
                if root in self.sdk_roots:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"imports provider SDK {imported!r}; only "
                                f"{', '.join(self.allowed_modules)} may (Phase "
                                "6.1, L1)"
                            ),
                        )
                    )
            try:
                tree = _ast.parse(module.path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in _ast.walk(tree):
                if not isinstance(node, _ast.Call):
                    continue
                target: Optional[str] = None
                if (isinstance(node.func, _ast.Attribute)
                        and node.func.attr == "import_module"
                        and node.args
                        and isinstance(node.args[0], _ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    target = node.args[0].value
                elif (isinstance(node.func, _ast.Name)
                        and node.func.id == "__import__"
                        and node.args
                        and isinstance(node.args[0], _ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    target = node.args[0].value
                if target is not None and target.split(".")[0] in self.sdk_roots:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=node.lineno,
                            offender=target,
                            detail=(
                                f"dynamically imports provider SDK {target!r}; "
                                "dynamic import does not exempt a module from "
                                "the SDK quarantine (Phase 6.1, L1)"
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
class ConnectorEffectGateRule:
    """The connector effect gate stays where Phase 6.1 put it (L1).

    ``BaseConnector._execute`` must call ``assert_effect_permitted`` as its
    first statement, and each of the three bypass seams discovery found —
    ``ArgoCDConnector._post``, ``GitHubConnector.graphql_request``,
    ``TerraformConnector._run`` — must call it somewhere in its body. Removing
    or reordering the gate turns this gate red; that is the rule's whole job.
    The gate being *first* in ``_execute`` matters: nothing (activity
    recording included) may run for a refused write.
    """

    rule_id: str = "BND-EFFECT-GATE"
    description: str = (
        "the connector effect gate is present at all four enforcement points"
    )
    #: (module, function, must_be_first_statement)
    gate_sites: tuple[tuple[str, str, bool], ...] = (
        ("backend.connectors.base", "_execute", True),
        ("backend.connectors.argocd", "_post", False),
        ("backend.connectors.github", "graphql_request", False),
        ("backend.connectors.terraform", "_run", False),
    )
    severity: Severity = Severity.ERROR

    @staticmethod
    def _calls_gate(node) -> bool:
        import ast as _ast

        for sub in _ast.walk(node):
            if (isinstance(sub, _ast.Call)
                    and isinstance(sub.func, _ast.Name)
                    and sub.func.id == "assert_effect_permitted"):
                return True
        return False

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        import ast as _ast

        by_name = {m.name: m for m in graph.modules()}
        violations: list[Violation] = []
        checked = 0
        for module_name, function_name, must_be_first in self.gate_sites:
            module = by_name.get(module_name)
            if module is None:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        module=module_name,
                        line=0,
                        offender=function_name,
                        detail=f"gated module {module_name!r} is missing",
                    )
                )
                continue
            checked += 1
            try:
                tree = _ast.parse(module.path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        module=module_name,
                        line=0,
                        offender=function_name,
                        detail="gated module is unparseable — the gate cannot "
                        "be verified, which counts as absent",
                    )
                )
                continue
            found = None
            for node in _ast.walk(tree):
                if (isinstance(node, (_ast.AsyncFunctionDef, _ast.FunctionDef))
                        and node.name == function_name):
                    found = node
                    break
            if found is None or not self._calls_gate(found):
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        module=module_name,
                        line=getattr(found, "lineno", 0),
                        offender=function_name,
                        detail=(
                            f"{function_name} no longer calls "
                            "assert_effect_permitted — the effect gate has "
                            "been removed (Phase 6.1, L1)"
                        ),
                    )
                )
                continue
            if must_be_first:
                body = list(found.body)
                # A docstring is not a statement for gate-ordering purposes.
                if (body and isinstance(body[0], _ast.Expr)
                        and isinstance(body[0].value, _ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body = body[1:]
                first_ok = bool(body) and self._calls_gate(body[0])
                if not first_ok:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module_name,
                            line=found.lineno,
                            offender=function_name,
                            detail=(
                                "assert_effect_permitted is not the first "
                                "statement of _execute; a refused write must "
                                "run nothing, record nothing (Phase 6.1, L1)"
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
class HarnessCredentialIsolationRule:
    """The harness plane never handles credential material (Phase 6.2, Part F).

    Credentials are minted at the last gateway stage and never enter a model
    context, a model output, or a trace span. The structural guarantee behind
    that is: no module under ``backend/harness/`` may import a credential
    *carrier* — the broker, the vault adapter, credential material, the
    credential request builder, or the credential composition root. It may
    import ``credentials.redaction``, which holds no secret and exists to
    *remove* them; that is the firewall's own tool, not a leak.

    A future import of the broker into the harness is exactly how a credential
    would acquire a path into a prompt. This rule makes that a red gate.
    """

    rule_id: str = "BND-HARNESS-CREDENTIALS"
    description: str = (
        "the harness plane imports no credential carrier — only the redactor"
    )
    harness_root: str = "backend.harness"
    forbidden: tuple[str, ...] = (
        "backend.platform.credentials.broker",
        "backend.platform.credentials.vault",
        "backend.platform.credentials.material",
        "backend.platform.credentials.request",
        "backend.platform.credentials.development",
        "backend.api.credential_composition",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not module.name.startswith(self.harness_root + "."):
                continue
            checked += 1
            for imported, line in module.imports:
                if imported in self.forbidden or any(
                    imported.startswith(f + ".") for f in self.forbidden
                ):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"the harness imports credential carrier "
                                f"{imported!r}; credentials are minted at the "
                                "gateway and never enter the harness (Phase 6.2, "
                                "Part F). Only credentials.redaction is allowed"
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
class HarnessNoExecutionRule:
    """The harness proposes and records; it never itself reaches a provider
    (Phase 6.2, BND-MODEL-NO-SIDE-EFFECT).

    The model plane's whole safety rests on it having no side-effect path of
    its own: it hands a proposal to a composed ``ActionPort`` that goes through
    the governed invocation gateway. So no module under ``backend/harness/``
    may import a connector, the invocation gateway, a provider adapter, or the
    transport broker. Writing the trace store (``database.durable``) is not a
    provider side effect and is allowed; reaching a provider is not.
    """

    rule_id: str = "BND-HARNESS-NO-EXECUTION"
    description: str = (
        "the harness plane imports no connector, gateway, adapter or transport"
    )
    harness_root: str = "backend.harness"
    forbidden_roots: tuple[str, ...] = (
        "backend.connectors",
        "backend.contexts.execution.application.invocation_gateway",
        "backend.contexts.execution.infrastructure.adapters",
        "backend.platform.transport",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not module.name.startswith(self.harness_root + "."):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(
                    imported == f or imported.startswith(f + ".")
                    for f in self.forbidden_roots
                ):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"the harness imports {imported!r}; the harness "
                                "proposes and records — the composed ActionPort "
                                "reaches a provider through the governed gateway, "
                                "never the harness itself (Phase 6.2)"
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
class HarnessNoDynamicDispatchRule:
    """The harness never dynamically dispatches (Phase 6.3, Part M).

    Tool exposure's whole premise is that a model-named tool is a KEY into a
    frozen registry — never a value that reaches dynamic code execution. So no
    module under ``backend/harness/`` may call ``eval``, ``exec``, ``compile``,
    ``__import__``, or ``importlib.import_module``. A regression that let model
    output reach any of these would turn "the model names a tool" back into
    "the model names an arbitrary Python target", which is exactly what the
    resolver exists to prevent. Static ``import`` / ``from ... import`` are
    fine (they name no model-derived string); this bans the dynamic forms.
    """

    rule_id: str = "BND-HARNESS-NO-DYNAMIC-DISPATCH"
    description: str = (
        "the harness plane uses no eval/exec/compile/__import__/import_module"
    )
    harness_root: str = "backend.harness"
    banned_names: tuple[str, ...] = ("eval", "exec", "compile", "__import__")
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        import ast as _ast

        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not module.name.startswith(self.harness_root + "."):
                continue
            checked += 1
            try:
                tree = _ast.parse(module.path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in _ast.walk(tree):
                if not isinstance(node, _ast.Call):
                    continue
                offender: Optional[str] = None
                func = node.func
                if isinstance(func, _ast.Name) and func.id in self.banned_names:
                    offender = func.id
                elif (isinstance(func, _ast.Attribute)
                        and func.attr == "import_module"
                        and isinstance(func.value, _ast.Name)
                        and func.value.id == "importlib"):
                    offender = "importlib.import_module"
                if offender is not None:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=node.lineno,
                            offender=offender,
                            detail=(
                                f"the harness calls {offender}; model output "
                                "must never reach dynamic dispatch — a tool is "
                                "a registry key, not a Python target (Phase 6.3)"
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
class WorldCannotExecuteRule:
    """The World Plane describes reality; it never acts on it (Phase 7.1, ADR-062).

    The World Plane sits *below* execution authority — knowledge informs action
    through Intelligence→Harness→Governance→Execution, never directly. So no
    module under ``backend/contracts/world`` (and, as the World Plane grows,
    ``backend/world``) may import a connector, the invocation gateway, a
    provider adapter, the transport fabric, the credential fabric, the
    scheduler/dispatcher, or a database implementation. A world contract that
    could reach any of those would be a second execution path wearing an
    epistemic type.
    """

    rule_id: str = "BND-WORLD-CANNOT-EXECUTE"
    description: str = (
        "the World Plane imports no connector, gateway, adapter, transport, "
        "credential carrier, harness, scheduler, or execution plane"
    )
    world_roots: tuple[str, ...] = ("backend.contracts.world", "backend.world")
    #: The *execution* set — reaching a provider or acting. Persisting an
    #: observation (``backend.database.durable``) is NOT executing, and detecting
    #: secrets (``credentials.inspection`` / ``.redaction``) is the ingestion
    #: firewall, not a credential — both are allowed, mirroring how
    #: BND-HARNESS-CREDENTIALS permits the redactor while forbidding the carriers.
    forbidden_roots: tuple[str, ...] = (
        "backend.connectors",
        "backend.contexts.execution",
        "backend.platform.transport",
        "backend.platform.credentials.broker",
        "backend.platform.credentials.vault",
        "backend.platform.credentials.material",
        "backend.platform.credentials.request",
        "backend.platform.credentials.development",
        "backend.harness",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not any(module.name.startswith(r + ".") or module.name == r
                       for r in self.world_roots):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.forbidden_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"the World Plane imports {imported!r}; it "
                                "describes reality and never executes — knowledge "
                                "informs action through governance, never directly "
                                "(ADR-062)"
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
class ModelCannotCreateFactRule:
    """Model output never becomes a world Fact or Belief (Phase 7.1/7.5, ADR-062).

    The intelligence and harness planes — where model output lives — must not
    import the World Plane's *grounded/derived* record constructors (``Fact``,
    ``Observation``, ``Belief``). They may propose (``ModelProposal``,
    ``Hypothesis``), but only the deterministic World Plane boundaries (the
    ingestion boundary for observations, the derivation boundary for facts, the
    belief-formation boundary for beliefs — all outside these planes) may
    construct them. This is the import-level half of the firewall; the type level
    (no ``ModelProposal.to_fact``/``to_belief``, no ``Fact.from_text``, no MODEL
    observation source, Belief requires structured evidence basis) is the other.

    Enforced by symbol: importing ``Fact``, ``Observation`` or ``Belief`` (by
    name or via the ``world`` package) from a model-plane module is the
    violation. Importing the proposal/hypothesis types, or the whole package for
    type annotations in a non-model plane, is fine. A model plane consumes a
    belief as structured data (``BeliefView.to_dict``), never by constructing the
    ``Belief`` contract itself.
    """

    rule_id: str = "BND-MODEL-CANNOT-CREATE-FACT"
    description: str = (
        "the intelligence/harness planes do not import the World Plane grounded "
        "constructors (Fact, Observation, Belief, WorldVerification, Outcome)"
    )
    model_roots: tuple[str, ...] = ("backend.harness", "backend.agents",
                                    "backend.orchestration", "backend.orchestrator",
                                    "backend.intelligence")
    grounded_module: str = "backend.contracts.world.epistemic"
    # A model plane may propose (ModelProposal, ModelHypothesisProposal,
    # Hypothesis, Prediction) but may not import the constructors of grounded or
    # execution-grounded world state: a Fact/Observation (instrument-grounded), a
    # Belief (evidence-grounded), a WorldVerification (procedure + independent
    # verifier), or an Outcome (real execution_ref). Those are minted only by the
    # World Plane's deterministic boundaries.
    grounded_symbols: tuple[str, ...] = (
        "Fact", "Observation", "Belief", "WorldVerification", "Outcome")
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        import ast as _ast

        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not any(module.name.startswith(r + ".") or module.name == r
                       for r in self.model_roots):
                continue
            checked += 1
            try:
                tree = _ast.parse(module.path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in _ast.walk(tree):
                # from backend.contracts.world[.epistemic] import Fact/Observation
                if isinstance(node, _ast.ImportFrom) and node.module in (
                    self.grounded_module, "backend.contracts.world",
                ):
                    for alias in node.names:
                        if alias.name in self.grounded_symbols:
                            violations.append(
                                Violation(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    module=module.name,
                                    line=node.lineno,
                                    offender=alias.name,
                                    detail=(
                                        f"a model-plane module imports the "
                                        f"grounded constructor {alias.name!r}; "
                                        "model output becomes a ModelProposal or "
                                        "Hypothesis, never a Fact/Observation — "
                                        "only the ingestion boundary grounds "
                                        "those (ADR-062, Part Q)"
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
class WorldApplicationPureRule:
    """The World Plane application layer persists through a port, not a database
    (Phase 7.2, hexagonal boundary).

    ``backend.world.application`` holds the ingestion service and the
    repository *port* — it depends on the abstraction, not on a database
    implementation. Only ``backend.world.infrastructure`` may import
    ``backend.database``. Keeping the application database-free is what lets the
    ingestion logic be tested and reasoned about without a store, and keeps the
    dependency arrow pointing inward.
    """

    rule_id: str = "BND-WORLD-APPLICATION-PURE"
    description: str = (
        "the World Plane application layer imports no database implementation"
    )
    application_root: str = "backend.world.application"
    forbidden_roots: tuple[str, ...] = ("backend.database",)
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not (module.name.startswith(self.application_root + ".")
                    or module.name == self.application_root):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.forbidden_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"the World Plane application imports {imported!r}; "
                                "it depends on the ObservationRepository port, not "
                                "a database — persistence belongs to "
                                "backend.world.infrastructure (Phase 7.2)"
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
class ObservationAppendOnlyRule:
    """World Plane observations are immutable — append-only (Phase 7.2, Part K).

    An observation is evidence; a newer observation is a new row, never an
    overwrite (the destructive-upsert the V1 infra JSON did is exactly what the
    ledger replaces). So no module under ``backend/world`` may construct a
    SQLAlchemy ``UPDATE`` or ``DELETE`` — the repository inserts and selects,
    nothing more. A regression that added ``sa.update`` / ``sa.delete`` (or a
    ``.update(`` / ``.delete(`` statement builder) would make world state
    mutable, and this turns that red.
    """

    rule_id: str = "BND-OBSERVATION-APPEND-ONLY"
    description: str = (
        "the World and Assurance planes issue no UPDATE or DELETE — observations, "
        "facts and verifications are immutable"
    )
    world_roots: tuple[str, ...] = ("backend.world", "backend.assurance",
                                    "backend.intelligence")
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        import ast as _ast

        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not any(module.name.startswith(r + ".") or module.name == r
                       for r in self.world_roots):
                continue
            checked += 1
            try:
                tree = _ast.parse(module.path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in _ast.walk(tree):
                if not isinstance(node, _ast.Call):
                    continue
                func = node.func
                offender: Optional[str] = None
                # sa.update(...) / sa.delete(...)
                if (isinstance(func, _ast.Attribute)
                        and func.attr in ("update", "delete")
                        and isinstance(func.value, _ast.Name)
                        and func.value.id in ("sa", "sqlalchemy")):
                    offender = f"{func.value.id}.{func.attr}"
                if offender is not None:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=node.lineno,
                            offender=offender,
                            detail=(
                                f"the World Plane builds a {offender} statement; "
                                "observations are immutable append-only evidence — "
                                "a newer observation is a new row, never an "
                                "overwrite (Phase 7.2, Part K)"
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
class AssuranceCannotExecuteRule:
    """The Assurance Plane evaluates; it never acts (Phase 7.7, ADR-069).

    Assurance sits between Intelligence and the Harness: it adjudicates claims
    against evidence it obtains from the World Plane, and mints a
    ``WorldVerification``. It must never itself reach a provider or execute — a
    verifier that could act would be an ungoverned side-effect channel wearing an
    evaluator's clothes. So no module under ``backend/assurance`` may import a
    connector, the invocation gateway, a provider adapter, the transport fabric, a
    credential carrier, the scheduler/dispatcher, or the harness. Reading the
    durable verification ledger (``backend.database.durable``) and the World read
    layer is allowed; acting is not — mirroring BND-WORLD-CANNOT-EXECUTE.
    """

    rule_id: str = "BND-ASSURANCE-CANNOT-EXECUTE"
    description: str = (
        "the Assurance Plane imports no connector, gateway, adapter, transport, "
        "credential carrier, scheduler, dispatcher, or harness"
    )
    assurance_root: str = "backend.assurance"
    forbidden_roots: tuple[str, ...] = (
        "backend.connectors",
        "backend.contexts.execution",
        "backend.platform.transport",
        "backend.platform.credentials.broker",
        "backend.platform.credentials.vault",
        "backend.platform.credentials.material",
        "backend.platform.credentials.request",
        "backend.platform.credentials.development",
        "backend.harness",
        "backend.orchestrator",
        "backend.computer",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not (module.name.startswith(self.assurance_root + ".")
                    or module.name == self.assurance_root):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.forbidden_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            module=module.name,
                            line=line,
                            offender=imported,
                            detail=(
                                f"the Assurance Plane imports {imported!r}; it "
                                "evaluates claims against evidence and never "
                                "executes — verification informs governance, it "
                                "does not act (ADR-069)"
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
class IntelligenceCannotExecuteRule:
    """The Intelligence Plane proposes and consumes evidence; it never acts
    (Phase 8.1, ADR-071/072).

    Intelligence orchestrates investigations: it queries the World, obtains
    schema-validated model proposals through the harness governed model boundary,
    and maintains investigation state. It must never reach a provider or execute —
    a reasoning plane that could act would reintroduce the exact V1 hazard (inline
    ungoverned execution). So no module under ``backend/intelligence`` may import a
    connector, the execution context, a provider adapter, the transport fabric, a
    credential carrier, the scheduler/dispatcher, computer-use/browser, the MCP
    gateway, or a **direct LLM provider** (``backend.llm`` / ``backend.llm_provider``
    / ``backend.providers``) — the model is reached only through
    ``backend.harness`` (the governed model boundary). Reading the durable ledger
    (``backend.database.durable``) and the World read layer is allowed; acting is
    not.
    """

    rule_id: str = "BND-INTELLIGENCE-CANNOT-EXECUTE"
    description: str = (
        "the Intelligence Plane imports no connector, execution, transport, "
        "credential carrier, scheduler, computer/browser, MCP, or direct LLM "
        "provider — only the harness governed model boundary"
    )
    intelligence_root: str = "backend.intelligence"
    forbidden_roots: tuple[str, ...] = (
        "backend.connectors",
        "backend.contexts.execution",
        "backend.platform.transport",
        "backend.platform.credentials.broker",
        "backend.platform.credentials.vault",
        "backend.platform.credentials.material",
        "backend.platform.credentials.request",
        "backend.platform.credentials.development",
        "backend.computer",
        "backend.tools",
        "backend.mcp",
        "backend.llm",
        "backend.llm_provider",
        "backend.providers",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not (module.name.startswith(self.intelligence_root + ".")
                    or module.name == self.intelligence_root):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.forbidden_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id, severity=self.severity,
                            module=module.name, line=line, offender=imported,
                            detail=(
                                f"the Intelligence Plane imports {imported!r}; it "
                                "proposes and consumes evidence and never executes "
                                "or reaches a provider directly — the model is "
                                "reached only through the harness governed boundary "
                                "(ADR-071/072)"
                            ),
                        )
                    )
        return RuleResult(
            rule_id=self.rule_id, description=self.description,
            violations=tuple(violations), modules_checked=checked)


@dataclass(frozen=True)
class NoV1IntelligenceImportRule:
    """New governed code does not import the quarantined V1 intelligence stack
    (Phase 8.1, the strangler ratchet).

    Phase 8.0 classified the V1 intelligence packages (agents/memory/RAG/
    orchestration/...) as QUARANTINE/REPLACE/DELETE: they let model output become
    "truth", lack tenant scoping, execute inline, and hold provider keys. The new
    governed Intelligence Plane must not depend on any of them, so the strangler
    zone can only shrink. A module under ``backend/intelligence`` importing a V1
    package is an ERROR.
    """

    rule_id: str = "BND-NO-V1-INTELLIGENCE-IMPORT"
    description: str = (
        "the governed Intelligence Plane imports none of the quarantined V1 "
        "intelligence packages"
    )
    intelligence_root: str = "backend.intelligence"
    v1_roots: tuple[str, ...] = (
        "backend.agents", "backend.agent_sdk", "backend.ai", "backend.autonomy",
        "backend.cognitive_memory", "backend.cortex_memory", "backend.memory",
        "backend.orchestration", "backend.orchestrator", "backend.research",
        "backend.learning", "backend.knowledge", "backend.mission_intel",
        "backend.runtime", "backend.vision", "backend.voice", "backend.voice_v2",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not (module.name.startswith(self.intelligence_root + ".")
                    or module.name == self.intelligence_root):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.v1_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id, severity=self.severity,
                            module=module.name, line=line, offender=imported,
                            detail=(
                                f"the Intelligence Plane imports quarantined V1 "
                                f"package {imported!r}; the V1 intelligence stack is "
                                "strangled, not extended (Phase 8.0/8.1)"
                            ),
                        )
                    )
        return RuleResult(
            rule_id=self.rule_id, description=self.description,
            violations=tuple(violations), modules_checked=checked)


@dataclass(frozen=True)
class IntelligenceCannotBypassWorldRule:
    """The Intelligence Plane reads reality only through the World application layer
    (Phase 8.4).

    ``IntelligenceCannotExecuteRule`` forbids acting; it does not forbid reaching
    the World's *storage*. A reasoning plane that imported ``backend.world.infrastructure``
    (the World's SQL fact/observation repositories) could read raw fact rows and
    re-derive freshness / authority / corroboration / bitemporal truth itself —
    reintroducing the exact V1 hazard where an intelligence layer computes its own
    parallel notion of what is true. So no module under ``backend/intelligence`` may
    import ``backend.world.infrastructure``: evidence is obtained only through the
    World application layer (``WorldQuery`` / ``BeliefFormation``), supplied by
    composition as a read port. The Intelligence Plane consumes World verdicts; it
    never reconstructs them (ADR-075).
    """

    rule_id: str = "BND-INTELLIGENCE-CANNOT-BYPASS-WORLD"
    description: str = (
        "the Intelligence Plane imports no World storage (backend.world.infrastructure); "
        "it consumes evidence only through the World application layer / read ports"
    )
    intelligence_root: str = "backend.intelligence"
    forbidden_roots: tuple[str, ...] = (
        "backend.world.infrastructure",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not (module.name.startswith(self.intelligence_root + ".")
                    or module.name == self.intelligence_root):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.forbidden_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id, severity=self.severity,
                            module=module.name, line=line, offender=imported,
                            detail=(
                                f"the Intelligence Plane imports World storage "
                                f"{imported!r}; it must read reality through the World "
                                "application layer (WorldQuery/BeliefFormation) as a "
                                "read port, never the raw fact/observation repositories "
                                "— it consumes World verdicts, never reconstructs them "
                                "(ADR-075)"
                            ),
                        )
                    )
        return RuleResult(
            rule_id=self.rule_id, description=self.description,
            violations=tuple(violations), modules_checked=checked)




@dataclass(frozen=True)
class AuthCannotExecuteRule:
    """The plane that decides WHO you are and WHAT you may do never acts
    (Phase 10.5, ADR-098).

    Why an existing rule does not already cover this
    ------------------------------------------------
    ``BND-PRODUCT-CANNOT-BYPASS-EXECUTION`` scopes to ``backend/api/product``;
    ``BND-DIRECT-HTTP`` to the bounded contexts and the credential fabric; the
    three ``*-CANNOT-EXECUTE`` rules each to their own plane. **None names
    ``backend/auth``.** Injecting ``from backend.platform.transport import
    broker`` into the approver-authority module left the gate PASS -- a real,
    measured gap, which is the only justification for a new rule (Part R).

    Why it matters more than it looks
    ---------------------------------
    Authorization code runs BEFORE every governed decision, holds the caller's
    identity, and is the one place a reviewer least expects to find a side
    effect. A module that answers "may this person approve?" and can also reach
    a gateway, a worker, the transport broker or the credential broker could
    decide and act in the same breath -- which is the shape of a system
    authorizing itself.

    Deliberately NOT forbidden: ``backend.infrastructure.redis``. The token
    blacklist needs it, and reading a revocation list is not executing.
    """

    rule_id: str = "BND-AUTH-CANNOT-EXECUTE"
    description: str = (
        "the authentication/authorization plane imports no gateway, dispatcher, "
        "connector, adapter, transport, credential broker or scheduler — it "
        "decides who you are and what you may do, and never acts"
    )
    auth_root: str = "backend.auth"
    forbidden_roots: tuple[str, ...] = (
        "backend.platform.transport",
        "backend.platform.credentials",
        "backend.contexts.execution",
        "backend.contexts.connectivity.infrastructure.adapters",
        "backend.api.capability_execution_composition",
        "backend.api.application_runtime",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not (module.name.startswith(self.auth_root + ".")
                    or module.name == self.auth_root):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.forbidden_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id, severity=self.severity,
                            module=module.name, line=line, offender=imported,
                            detail=(
                                f"the auth plane imports {imported!r}; a module "
                                "that decides whether somebody may approve must "
                                "not also be able to execute, dispatch, reach a "
                                "provider or mint a credential -- deciding and "
                                "acting in one place is the shape of a system "
                                "authorizing itself (ADR-098)"
                            ),
                        )
                    )
        return RuleResult(
            rule_id=self.rule_id, description=self.description,
            violations=tuple(violations), modules_checked=checked)


@dataclass(frozen=True)
class ProductCannotBypassExecutionRule:
    """The product API reaches the world only through the one execution door
    (Phase 10.3, ADR-096).

    Why an existing rule does not already cover this
    ------------------------------------------------
    ``BND-DIRECT-HTTP`` scopes to the bounded contexts and the credential
    fabric; ``BND-PROVIDER-SDK`` quarantines SDK imports to connector modules;
    ``BND-WORLD-CANNOT-EXECUTE``, ``BND-ASSURANCE-CANNOT-EXECUTE`` and
    ``BND-INTELLIGENCE-CANNOT-EXECUTE`` each scope to their own plane. None of
    them names ``backend/api/product``, which did not exist when they were
    written. So a product module could import the invocation gateway, the
    dispatcher, a connector adapter, the transport broker or the credential
    broker directly and dispatch around authorization -- and every existing rule
    would still pass. That is a genuine uncovered bypass, which is the only
    justification for a new rule (Phase 10.3, Part X).

    What the product may do instead
    --------------------------------
    Exactly one thing: call ``backend.api.capability_execution_composition``,
    which is the composed governed chain -- capability binding, authorization,
    approval validation, the gateway, then the CONTAINED worker. That module is
    an allowed import precisely because going through it IS the governed path.

    Note what is deliberately NOT forbidden: the approval STORE
    (``sql_approval``). Storing and reading approvals is not executing, and the
    decision about whether an approval covers an action still lives in
    ``ApprovalFacts`` and the gateway.
    """

    rule_id: str = "BND-PRODUCT-CANNOT-BYPASS-EXECUTION"
    description: str = (
        "the product API imports no gateway, dispatcher, connector adapter, "
        "transport or credential broker — it acts only through the composed "
        "governed execution door"
    )
    product_root: str = "backend.api.product"
    forbidden_roots: tuple[str, ...] = (
        "backend.contexts.execution.application.gateway",
        "backend.contexts.execution.application.dispatch",
        "backend.contexts.execution.infrastructure.adapters",
        "backend.contexts.connectivity.infrastructure.adapters",
        "backend.platform.transport",
        "backend.platform.credentials",
        "backend.contexts.execution.application.scheduler",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not (module.name.startswith(self.product_root + ".")
                    or module.name == self.product_root):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.forbidden_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id, severity=self.severity,
                            module=module.name, line=line, offender=imported,
                            detail=(
                                f"the product API imports {imported!r}; a product "
                                "surface must reach the world only through "
                                "backend.api.capability_execution_composition, "
                                "which is the governed chain (binding, "
                                "authorization, approval, gateway, contained "
                                "worker). Importing a gateway, dispatcher, "
                                "adapter, transport or credential broker "
                                "directly would dispatch around authorization "
                                "(ADR-096)"
                            ),
                        )
                    )
        return RuleResult(
            rule_id=self.rule_id, description=self.description,
            violations=tuple(violations), modules_checked=checked)


@dataclass(frozen=True)
class AutonomyNotModelDrivenRule:
    """The autonomy decision is outside the model's mutation surface (Phase 8.8).

    Autonomy is delegated authority the PLATFORM grants from independent evidence
    (calibration, assurance, risk, world) — the model must never be an input to it,
    or a model could argue itself into more authority (the self-reinforcing loop of
    Part X). ``BND-INTELLIGENCE-CANNOT-EXECUTE`` already stops the autonomy module
    from reaching the execution gateway; this closes the other side: the autonomy
    decision module (``backend.intelligence.application.autonomy``) may not import
    the governed model boundary or any model-proposal seam. It decides from typed
    evidence and emits a value; model text never crosses the authority boundary
    (ADR-079).
    """

    rule_id: str = "BND-AUTONOMY-NOT-MODEL-DRIVEN"
    description: str = (
        "the autonomy decision module imports no model boundary / model-proposal "
        "seam — autonomy is decided from independent evidence, never model output"
    )
    autonomy_module: str = "backend.intelligence.application.autonomy"
    forbidden_roots: tuple[str, ...] = (
        "backend.harness.llm_boundary",
        "backend.harness.trace",
        "backend.intelligence.application.model_boundary",
        "backend.llm",
        "backend.llm_provider",
        "backend.providers",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not (module.name == self.autonomy_module
                    or module.name.startswith(self.autonomy_module + ".")):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.forbidden_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id, severity=self.severity,
                            module=module.name, line=line, offender=imported,
                            detail=(
                                f"the autonomy decision imports the model seam "
                                f"{imported!r}; autonomy is decided from independent "
                                "evidence (calibration/assurance/risk/world), never "
                                "model output — the model may not influence its own "
                                "authority (ADR-079, Part X)"
                            ),
                        )
                    )
        return RuleResult(
            rule_id=self.rule_id, description=self.description,
            violations=tuple(violations), modules_checked=checked)


@dataclass(frozen=True)
class WorldCannotImportV1MemoryRule:
    """Historical experience never enters the World Plane as truth (Phase 8.6).

    The V1 memory stack (``backend.memory``'s MemoryOrchestrator/semantic store,
    ``backend.cognitive_memory``) turns stored model memory into prompt-injected
    "KNOWN FACTS" — the exact anti-pattern that lets experience masquerade as truth.
    ``BND-NO-V1-INTELLIGENCE-IMPORT`` already fences ``backend.intelligence`` from it,
    but the WORLD/ASSURANCE planes (and the durable reasoning ledger, which lives
    under ``backend.world.application``) were NOT gated — a dual-write from V1 memory
    into the fact/observation/reasoning ledgers would be catastrophic. This forbids
    any module under ``backend.world`` or ``backend.assurance`` from importing a V1
    memory package. World truth is grounded only in observations; experience is a
    projection over the ledgers, never a source of them (ADR-077, Part O/W).
    """

    rule_id: str = "BND-WORLD-CANNOT-IMPORT-V1-MEMORY"
    description: str = (
        "the World and Assurance planes import no V1 memory package — historical "
        "experience never dual-writes into the World ledgers as truth"
    )
    world_roots: tuple[str, ...] = ("backend.world", "backend.assurance")
    v1_memory_roots: tuple[str, ...] = (
        "backend.memory",
        "backend.cognitive_memory",
        "backend.cortex_memory",
        "backend.services.memory_context_service",
        "backend.services.enterprise_engineering_memory",
    )
    severity: Severity = Severity.ERROR

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        violations: list[Violation] = []
        checked = 0
        for module in graph.modules():
            if not any(module.name == r or module.name.startswith(r + ".")
                       for r in self.world_roots):
                continue
            checked += 1
            for imported, line in module.imports:
                if any(imported == f or imported.startswith(f + ".")
                       for f in self.v1_memory_roots):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id, severity=self.severity,
                            module=module.name, line=line, offender=imported,
                            detail=(
                                f"the World/Assurance plane imports V1 memory "
                                f"{imported!r}; historical/model memory must never "
                                "dual-write into the World ledgers as truth — the "
                                "World is grounded only in observations (ADR-077)"
                            ),
                        )
                    )
        return RuleResult(
            rule_id=self.rule_id, description=self.description,
            violations=tuple(violations), modules_checked=checked)


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
        ProcessSpawnQuarantineRule(),
        ProviderSdkImportRule(),
        ConnectorEffectGateRule(),
        HarnessCredentialIsolationRule(),
        HarnessNoExecutionRule(),
        HarnessNoDynamicDispatchRule(),
        WorldCannotExecuteRule(),
        ModelCannotCreateFactRule(),
        WorldApplicationPureRule(),
        ObservationAppendOnlyRule(),
        AssuranceCannotExecuteRule(),
        IntelligenceCannotExecuteRule(),
        NoV1IntelligenceImportRule(),
        IntelligenceCannotBypassWorldRule(),
        WorldCannotImportV1MemoryRule(),
        AutonomyNotModelDrivenRule(),
        ProductCannotBypassExecutionRule(),
        AuthCannotExecuteRule(),
    )
