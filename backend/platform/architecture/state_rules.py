"""Guard against new file-based authoritative state.

The Phase 1 compliance report names file-based state as the most expensive
defect in the codebase (V3). It has already caused one total outage: a ~200ms
synchronous JSON rewrite firing on every Docker event starved the event loop
until ``/api/auth/login`` hung indefinitely.

PR-11 migrates the security-critical stores to PostgreSQL. This rule exists for
the interval before that: **nothing today prevents a forty-fourth JSON store
appearing**, and every one added between now and then is another thing to
migrate.

The rule converts the migration from a cleanup somebody must remember into a
ratchet that cannot slip backwards.

Three tiers, not two
--------------------
The brief specifies an allowlist of three stores with everything else failing
CI. Applied literally to this repository that produces roughly eighty-four
blocking violations on the first run, because 81 modules already write state
files. A gate that is red on the day it ships is a gate people learn to route
around -- ADR-016 rejected exactly that.

So the tiers are:

``APPROVED_STORES``
    The three the brief names. Security-critical, actively migrating in PR-11.
    **Warning**, tracked.

``GRANDFATHERED_STORES``
    Everything that already existed when this rule was written, captured as a
    frozen inventory. **Warning**. The list may only shrink; adding to it
    requires an ADR.

Anything else
    **Error.** This is the tier that does the work.

Detection is a heuristic, stated plainly
----------------------------------------
A module is flagged when it both performs a write operation *and* mentions a
state-file literal. That cannot see a filename assembled at runtime, and it will
occasionally attribute a filename to the wrong write in a module doing several
things.

It is deliberately biased toward false positives over false negatives: a false
positive costs one line in the inventory and a moment's thought, a false
negative is a store nobody notices until PR-11 has to migrate it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.platform.architecture.rules import (
    ModuleGraph,
    ModuleInfo,
    RuleResult,
    Severity,
    Violation,
)

__all__ = [
    "APPROVED_STORES",
    "GRANDFATHERED_STORES",
    "STATE_FILE_EXTENSIONS",
    "FileStateRule",
    "scan_state_files",
]

#: Stores the Constitution has explicitly approved pending PR-11 migration.
#: These are the security-critical three; they carry the highest priority.
APPROVED_STORES = frozenset(
    {
        "pending_approval_actions.json",
        "approval_decisions.json",
        "integrity_audit.jsonl",
    }
)

#: Extensions that indicate persisted state rather than source or config.
STATE_FILE_EXTENSIONS = frozenset(
    {
        ".json", ".jsonl", ".ndjson",
        ".yaml", ".yml",
        ".db", ".sqlite", ".sqlite3",
        ".pickle", ".pkl",
        ".csv", ".tsv",
        ".toml",
        ".msgpack", ".mpk",
        ".dat", ".bin", ".state",
    }
)

#: Filenames that are configuration or tooling, never operational state.
#:
#: Many appear in this codebase as *string literals a connector looks for* --
#: the repository-analysis service names ``Cargo.toml`` and ``.gitlab-ci.yml``
#: to detect them in a customer repo, it does not write them. Detecting those
#: as state stores would fill the inventory with entries nobody can act on.
_CONFIG_FILENAMES = frozenset(
    {
        # Python
        "pyproject.toml", "poetry.lock", "setup.cfg", "mypy.ini", "alembic.ini",
        "pipfile.lock", "requirements.json",
        # JavaScript / TypeScript
        "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
        "tsconfig.json", ".mocharc.json", "composer.json",
        # Other ecosystems
        "cargo.toml", "cargo.lock", "go.sum", "gemfile.lock",
        # CI and orchestration
        "docker-compose.yml", "docker-compose.yaml", ".gitlab-ci.yml",
        "azure-pipelines.yml", "azure-pipelines.yaml", "build.yml",
        "config.yml", "config.yaml", "config.json", "settings.json",
        # API descriptions
        "openapi.json", "swagger.json",
    }
)

#: Path fragments whose contents are never authoritative state.
_EXEMPT_PATH_PARTS = frozenset(
    {
        "tests", "test", "conftest", "fixtures", "fixture", "samples", "sample",
        "examples", "example", "docs", "doc", "migrations", "alembic",
        "scripts", "benchmarks", "__pycache__", "node_modules",
    }
)

#: Calls that write bytes or text to a local file.
_WRITE_CALLS = frozenset(
    {
        "dump", "dumps_to_file", "write_text", "write_bytes", "writelines",
        "to_json", "to_csv", "to_pickle", "to_parquet", "savez", "save",
    }
)

#: Modules whose mere use implies local persistence.
_PERSISTENCE_MODULES = frozenset({"pickle", "shelve", "sqlite3", "dbm", "marshal"})


def _is_exempt_path(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    if lowered & _EXEMPT_PATH_PARTS:
        return True
    name = path.name.lower()
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def _looks_like_state_file(literal: str) -> bool:
    """Whether a string literal names a state file rather than config."""
    candidate = literal.strip().strip("/\\")
    if not candidate or "*" in candidate:
        return False
    # A format placeholder means the name is assembled at runtime; the literal
    # itself names nothing.
    if "{" in candidate or "}" in candidate:
        return False
    name = Path(candidate).name
    if not name or name.lower() in _CONFIG_FILENAMES:
        return False
    # Dotfiles are tool configuration by convention, never operational state.
    if name.startswith("."):
        return False
    return Path(name).suffix.lower() in STATE_FILE_EXTENSIONS


@dataclass(frozen=True)
class StateWrite:
    """One detected write of persistent state to a file."""

    module: str
    path: Path
    filename: str
    line: int
    mechanism: str

    @property
    def is_approved(self) -> bool:
        return self.filename in APPROVED_STORES


def _write_evidence(tree: ast.AST) -> list[tuple[str, int]]:
    """Find write operations in a module. Returns ``(mechanism, line)``."""
    found: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func

            # json.dump(...), pickle.dump(...), yaml.dump(...)
            if isinstance(func, ast.Attribute):
                if func.attr in _WRITE_CALLS:
                    owner = func.value
                    owner_name = owner.id if isinstance(owner, ast.Name) else None
                    if func.attr == "dump" and owner_name in {
                        "json", "yaml", "pickle", "toml", "msgpack"
                    }:
                        found.append((f"{owner_name}.dump", node.lineno))
                    elif func.attr in {"write_text", "write_bytes", "writelines"}:
                        found.append((func.attr, node.lineno))
                    elif func.attr in {"to_json", "to_csv", "to_pickle"}:
                        found.append((func.attr, node.lineno))

                # sqlite3.connect(...), shelve.open(...)
                if isinstance(func.value, ast.Name):
                    if func.value.id in _PERSISTENCE_MODULES:
                        found.append((f"{func.value.id}.{func.attr}", node.lineno))

            # open(path, "w") / open(path, "a")
            if isinstance(func, ast.Name) and func.id == "open":
                mode: Optional[str] = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = str(node.args[1].value)
                for keyword in node.keywords:
                    if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                        mode = str(keyword.value.value)
                if mode and any(flag in mode for flag in ("w", "a", "x", "+")):
                    found.append((f"open(mode={mode!r})", node.lineno))

    return found


def _state_literals(tree: ast.AST) -> list[tuple[str, int]]:
    """Find string literals naming a state file."""
    return [
        (Path(node.value.strip()).name, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _looks_like_state_file(node.value)
    ]


def scan_state_files(graph: ModuleGraph) -> list[StateWrite]:
    """Find every module that both writes and names a state file.

    Correlating the two is what avoids flagging a module that merely *reads*
    configuration -- reading a JSON file is fine, and most modules mentioning
    one only read it.
    """
    writes: list[StateWrite] = []

    for module in graph.modules():
        if _is_exempt_path(module.path):
            continue
        try:
            tree = ast.parse(module.path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        write_ops = _write_evidence(tree)
        if not write_ops:
            continue

        literals = _state_literals(tree)
        if not literals:
            continue

        mechanism = write_ops[0][0]
        for filename, line in sorted(set(literals)):
            writes.append(
                StateWrite(
                    module=module.name,
                    path=module.path,
                    filename=filename,
                    line=line,
                    mechanism=mechanism,
                )
            )

    return writes


def _suggestion_for(filename: str, approved: bool) -> str:
    if approved:
        return (
            "Migrating to PostgreSQL in PR-11 together with the other "
            "security-critical stores; no action needed here."
        )
    return (
        "Persist this through a repository backed by the transactional store "
        "(see backend/database/repositories) rather than a file. If it is genuinely "
        "not authoritative state -- a cache, an export, a fixture -- move it out of "
        "an operational path or name it so its purpose is obvious."
    )


@dataclass(frozen=True)
class FileStateRule:
    """No *new* authoritative state may be persisted to a local file."""

    rule_id: str = "STATE-NO-NEW-FILE-STORES"
    description: str = "No new authoritative state persisted to local files"
    approved: frozenset[str] = APPROVED_STORES
    grandfathered: frozenset[str] = field(default_factory=frozenset)
    """Stores that predate this rule. May only shrink; growing it needs an ADR."""

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        writes = scan_state_files(graph)
        if not writes:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.description,
                modules_checked=len(graph),
            )

        violations: list[Violation] = []
        for write in writes:
            if write.filename in self.approved:
                severity = Severity.WARNING
                reason = "approved store, pending PR-11 migration"
            elif write.filename in self.grandfathered:
                severity = Severity.WARNING
                reason = "pre-existing store, grandfathered"
            else:
                severity = Severity.ERROR
                reason = "NEW file-based authoritative state"

            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    severity=severity,
                    module=write.module,
                    line=write.line,
                    offender=write.filename,
                    detail=(
                        f"{reason}: {write.filename!r} written via {write.mechanism}. "
                        + _suggestion_for(write.filename, severity is Severity.WARNING)
                    ),
                )
            )

        return RuleResult(
            rule_id=self.rule_id,
            description=self.description,
            violations=tuple(violations),
            modules_checked=len(graph),
        )


#: Stores that existed when this rule was written (2026-08-04). Frozen
#: inventory: the rule fails on anything not listed here or in APPROVED_STORES.
#:
#: **This list may only shrink.** Removing an entry -- because the store was
#: migrated or deleted -- is ordinary work. Adding one means a new file store
#: was introduced, which requires an ADR explaining why the transactional store
#: was insufficient.
GRANDFATHERED_STORES: frozenset[str] = frozenset(
    {
        "alert_incident_history.json",
        "analyses.json",
        "analytics_metrics.json",
        "analytics_reports.json",
        "architecture_analyses.json",
        "architecture_projects.json",
        "autonomy.json",
        "branch_protection_history.json",
        "builds.json",
        "cicd_artifacts.json",
        "cicd_builds.json",
        "cicd_deployments.json",
        "cicd_failures.json",
        "cicd_pipelines.json",
        "cicd_recoveries.json",
        "cicd_timelines.json",
        "clusters.json",
        "cognition_runtime_state.json",
        "cognition_timeline.json",
        "compliance.json",
        "containers.json",
        "cost_anomaly_history.json",
        "credential_check_history.json",
        "deploy_check_history.json",
        "deployments.json",
        "docker_containers.json",
        "docker_health_history.json",
        "docker_images.json",
        "docker_networks.json",
        "docker_volumes.json",
        "environments.json",
        "execution_engine.json",
        "flaky_test_history.json",
        "flaky_test_pending_retries.json",
        "git_branches.json",
        "git_commits.json",
        "git_history.json",
        "git_pull_requests.json",
        "github_webhook_deliveries.json",
        "governance_audit.json",
        "grafana_dashboards.json",
        "helm_releases.json",
        "incidents.json",
        "loki_logs.json",
        "monitoring_rules.json",
        "network_failures.json",
        "nodes.json",
        "patch_candidates.json",
        "patch_plans.json",
        "patches.json",
        "pending_deploy_checks.json",
        "pipelines.json",
        "plans.json",
        "pods.json",
        "policies.json",
        "prometheus_alerts.json",
        "prometheus_metrics.json",
        "prometheus_rules.json",
        "prometheus_targets.json",
        "pvcs.json",
        "recommendations.json",
        "reports.json",
        "repositories.json",
        "repository_brain.json",
        "rollback_history.json",
        "runtime_store.json",
        "sandboxes.json",
        "service_graph.json",
        "tasks.json",
        "traces.json",
        "trigger_history.json",
        "trigger_policies.json",
        "vulnerability_check_history.json",
        "workspaces.json",
    }
)
