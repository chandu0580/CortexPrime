"""The architecture enforces itself.

Two halves, and the second is the one that matters:

**The gate passes today.** Every enforced rule and invariant holds against the
real codebase. This is the check CI runs on every commit.

**Every rule fails when violated.** Each rule is run against a synthesized
module tree that breaks it, and asserted to catch the breach. Without this half,
a rule that silently stopped working would still report green forever -- and a
green suite that cannot fail is worse than no suite, because it is trusted.

Synthesized trees are used rather than the real repository so a violation can be
constructed without committing one.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from backend.platform.architecture import (
    AllowedRootsRule,
    ArchitectureSuite,
    ContextIsolationRule,
    ForbiddenImportRule,
    InterfacePurityRule,
    InvariantStatus,
    LayerRule,
    ModuleGraph,
    NoCyclesRule,
    NoLegacyImportRule,
    PersistenceEncapsulationRule,
    Severity,
    constitutional_invariants,
    default_suite,
    dependency_summary,
    render_markdown,
    render_text,
    to_dict,
)
from tests.architecture.probes import SERVICE_LEVEL_PROBES

REPO_BACKEND = Path(__file__).resolve().parents[2] / "backend"


def write_tree(root: Path, files: dict[str, str]) -> ModuleGraph:
    """Materialize a synthetic package and return its module graph."""
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
    return ModuleGraph.build(root, package_root=root.name)


@pytest.fixture(scope="module")
def real_graph() -> ModuleGraph:
    return ModuleGraph.build(REPO_BACKEND)


@pytest.fixture(scope="module")
def real_result(real_graph):
    return default_suite(SERVICE_LEVEL_PROBES).run(real_graph)


# ======================================================================
# The gate passes today
# ======================================================================


class TestGatePassesToday:
    def test_architecture_gate_passes(self, real_result) -> None:
        """The check CI runs. Failure here blocks a merge."""
        assert real_result.gate_passed, "\n".join(
            str(v) for v in real_result.blocking_violations
        )

    def test_no_blocking_violations(self, real_result) -> None:
        assert real_result.blocking_violations == ()

    def test_the_suite_actually_checked_something(self, real_result, real_graph) -> None:
        """Guards against a graph that silently found no modules."""
        assert len(real_graph) > 100
        assert len(real_result.passed) >= 10

    @pytest.mark.parametrize(
        "rule_id",
        [
            "DEP-CONTRACTS-LEAF",
            "DEP-CONTRACTS-NO-BACKEND",
            "DEP-PLATFORM-NO-CONTEXTS",
            "DEP-LAYERS",
            "DEP-CYCLE-CONTRACTS",
            "DEP-CYCLE-PLATFORM",
        ],
    )
    def test_dependency_rules_pass(self, real_result, rule_id: str) -> None:
        result = real_result.result_for(rule_id)
        assert result is not None, f"{rule_id} was not evaluated"
        assert result.passed, "\n".join(str(v) for v in result.violations)

    @pytest.mark.parametrize("invariant_id", ["I2", "I3", "I6", "I7", "SELF-AUTH", "IMMUTABLE"])
    def test_enforced_invariants_hold(self, real_result, invariant_id: str) -> None:
        result = real_result.result_for(f"INV-{invariant_id}")
        assert result is not None
        assert not result.skipped, f"{invariant_id} is registered but not enforced"
        assert result.passed, "\n".join(str(v) for v in result.violations)

    def test_unenforced_invariants_report_as_skipped_not_passed(self, real_result) -> None:
        """A skip counted as a pass is how an unenforced invariant looks enforced."""
        for invariant_id in ("I1", "I4", "I5", "I8"):
            result = real_result.result_for(f"INV-{invariant_id}")
            assert result is not None
            assert result.skipped, f"{invariant_id} is no longer skipped — update its status"
            assert not result.passed, f"{invariant_id} reports as passed while skipped"
            assert result.skip_reason

    def test_every_constitutional_invariant_is_registered(self) -> None:
        registered = {check.invariant_id for check in constitutional_invariants()}
        for expected in ("I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8"):
            assert expected in registered, f"{expected} is missing from the suite"


# ======================================================================
# Every rule fails when violated
# ======================================================================


class TestDependencyRulesDetectViolations:
    def test_allowed_roots_rule_catches_a_new_dependency(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {"contracts/thing.py": "import requests\n"},
        )
        rule = AllowedRootsRule(
            rule_id="T", description="", source_prefix="pkg.contracts",
            allowed_roots=frozenset({"dataclasses"}),
        )
        result = rule.evaluate(graph)
        assert not result.passed
        assert result.violations[0].offender == "requests"
        assert result.violations[0].line == 1

    def test_allowed_roots_rule_passes_when_compliant(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg", {"contracts/thing.py": "import dataclasses\n"}
        )
        rule = AllowedRootsRule(
            rule_id="T", description="", source_prefix="pkg.contracts",
            allowed_roots=frozenset({"dataclasses"}),
        )
        assert rule.evaluate(graph).passed

    def test_forbidden_import_rule_catches_a_layer_breach(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {"platform/util.py": "from pkg.services.thing import go\n"},
        )
        rule = ForbiddenImportRule(
            rule_id="T", description="", source_prefix="pkg.platform",
            forbidden_prefixes=("pkg.services",),
        )
        result = rule.evaluate(graph)
        assert not result.passed
        assert "pkg.services.thing" in result.violations[0].offender

    def test_layer_rule_catches_an_upward_dependency(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "contracts/a.py": "from pkg.platform.b import thing\n",
                "platform/b.py": "thing = 1\n",
            },
        )
        rule = LayerRule(
            rule_id="T", description="",
            layers=(("pkg.contracts", 0), ("pkg.platform", 1)),
        )
        result = rule.evaluate(graph)
        assert not result.passed
        assert "layer violation" in result.violations[0].detail

    def test_layer_rule_allows_a_downward_dependency(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "contracts/a.py": "thing = 1\n",
                "platform/b.py": "from pkg.contracts.a import thing\n",
            },
        )
        rule = LayerRule(
            rule_id="T", description="",
            layers=(("pkg.contracts", 0), ("pkg.platform", 1)),
        )
        assert rule.evaluate(graph).passed

    def test_cycle_rule_detects_a_two_module_cycle(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "a.py": "from pkg.b import thing\n",
                "b.py": "from pkg.a import other\n",
            },
        )
        result = NoCyclesRule(rule_id="T", description="").evaluate(graph)
        assert not result.passed
        assert "import cycle" in result.violations[0].detail

    def test_cycle_rule_detects_a_longer_cycle(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "a.py": "from pkg.b import x\n",
                "b.py": "from pkg.c import x\n",
                "c.py": "from pkg.a import x\n",
            },
        )
        result = NoCyclesRule(rule_id="T", description="").evaluate(graph)
        assert not result.passed
        assert result.violations[0].detail.count("->") >= 3

    def test_cycle_rule_passes_on_an_acyclic_tree(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {"a.py": "from pkg.b import x\n", "b.py": "x = 1\n"},
        )
        assert NoCyclesRule(rule_id="T", description="").evaluate(graph).passed


class TestBoundaryRulesDetectViolations:
    def test_context_isolation_catches_a_cross_context_import(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "contexts/mission/service.py": "from pkg.contexts.execution.runner import go\n",
                "contexts/execution/runner.py": "def go(): ...\n",
            },
        )
        rule = ContextIsolationRule(contexts_root="pkg.contexts")
        result = rule.evaluate(graph)
        assert not result.passed
        assert "contexts communicate by published contract only" in result.violations[0].detail

    def test_context_isolation_allows_contract_imports(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "contexts/mission/service.py": "from pkg.contracts.mission import MissionRef\n",
                "contexts/execution/runner.py": "def go(): ...\n",
                "contracts/mission.py": "MissionRef = 1\n",
            },
        )
        assert ContextIsolationRule(contexts_root="pkg.contexts").evaluate(graph).passed

    def test_persistence_rule_catches_reaching_into_another_schema(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "contexts/mission/service.py": (
                    "from pkg.contexts.execution.repository import ExecutionRepo\n"
                ),
                "contexts/execution/repository.py": "class ExecutionRepo: ...\n",
            },
        )
        rule = PersistenceEncapsulationRule(contexts_root="pkg.contexts")
        result = rule.evaluate(graph)
        assert not result.passed
        assert "couples two schemas" in result.violations[0].detail

    def test_persistence_rule_allows_own_repository(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "contexts/mission/service.py": "from pkg.contexts.mission.repository import R\n",
                "contexts/mission/repository.py": "class R: ...\n",
            },
        )
        assert PersistenceEncapsulationRule(contexts_root="pkg.contexts").evaluate(graph).passed

    def test_legacy_rule_catches_a_new_dependent(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "legacy/old.py": "def thing(): ...\n",
                "platform/new.py": "from pkg.legacy.old import thing\n",
            },
        )
        result = NoLegacyImportRule(legacy_prefix="pkg.legacy").evaluate(graph)
        assert not result.passed
        assert "may only shrink" in result.violations[0].detail

    def test_legacy_rule_allows_legacy_importing_itself(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "legacy/old.py": "def thing(): ...\n",
                "legacy/other.py": "from pkg.legacy.old import thing\n",
            },
        )
        assert NoLegacyImportRule(legacy_prefix="pkg.legacy").evaluate(graph).passed

    def test_interface_purity_reports_a_warning_not_a_failure(self, tmp_path) -> None:
        """Warning severity: the existing API layer violates this widely, and a
        permanently red suite is one people learn to ignore."""
        graph = write_tree(
            tmp_path / "pkg", {"api/routes.py": "from pkg.database.models import Thing\n"}
        )
        rule = InterfacePurityRule(
            interface_prefixes=("pkg.api",), forbidden_prefixes=("pkg.database",)
        )
        result = rule.evaluate(graph)
        assert result.violations
        assert result.passed, "warnings must not block the gate"
        assert result.violations[0].severity is Severity.WARNING


class TestInvariantProbesDetectViolations:
    """A probe must fail when the invariant is actually violated.

    Verified by giving the check a probe that reports a breach, proving the
    reporting path works end to end -- rather than trusting that a probe which
    has only ever passed would fail if it needed to.
    """

    def test_a_breaching_probe_fails_the_check(self, real_graph) -> None:
        from backend.platform.architecture import InvariantCheck

        check = InvariantCheck(
            invariant_id="TEST",
            statement="probe reports a breach",
            status=InvariantStatus.ENFORCED,
            probe=lambda _: "the invariant was violated",
        )
        result = check.evaluate(real_graph)
        assert not result.passed
        assert result.violations[0].detail == "the invariant was violated"

    def test_a_crashing_probe_fails_rather_than_passing(self, real_graph) -> None:
        from backend.platform.architecture import InvariantCheck

        def _explode(_):
            raise RuntimeError("probe is broken")

        check = InvariantCheck(
            invariant_id="TEST",
            statement="",
            status=InvariantStatus.ENFORCED,
            probe=_explode,
        )
        result = check.evaluate(real_graph)
        assert not result.passed
        assert "RuntimeError" in result.violations[0].detail

    def test_an_unregistered_probe_reports_skipped_not_passed(self, real_graph) -> None:
        """I2 without its injected probe must not look enforced."""
        invariants = {check.invariant_id: check for check in constitutional_invariants()}
        result = invariants["I2"].evaluate(real_graph)
        assert result.skipped
        assert not result.passed

    def test_i2_probe_detects_a_real_breach(self, real_graph) -> None:
        """Sanity-check the injected probe against a deliberately broken input."""
        from backend.services.enterprise_approval_integrity import verify_record

        legacy = {"action_type": "rollback", "payload": {}}
        assert not verify_record("wf", legacy).ok, (
            "the I2 probe relies on legacy records being refused; that guard is gone"
        )

    def test_suite_reports_a_failing_rule(self, real_graph) -> None:
        """A broken rule must surface as a failure, not crash the run."""

        class Exploding:
            rule_id = "BOOM"
            description = "always raises"

            def evaluate(self, graph):
                raise ValueError("kaboom")

        suite = ArchitectureSuite(rules=(Exploding(),))
        result = suite.run(real_graph)
        assert not result.gate_passed
        assert "kaboom" in result.blocking_violations[0].detail


# ======================================================================
# Reporting
# ======================================================================


class TestReporting:
    def test_text_report_renders(self, real_result, real_graph) -> None:
        report = render_text(
            real_result, graph=real_graph, invariants=constitutional_invariants()
        )
        assert "ARCHITECTURE GATE" in report
        assert "CONSTITUTIONAL INVARIANTS" in report
        assert "DEPENDENCY GRAPH" in report

    def test_markdown_report_renders(self, real_result, real_graph) -> None:
        report = render_markdown(
            real_result, graph=real_graph, invariants=constitutional_invariants()
        )
        assert report.startswith("# Architecture Report")
        assert "| Module | Dependents |" in report

    def test_json_report_is_serializable(self, real_result, real_graph) -> None:
        payload = to_dict(
            real_result, graph=real_graph, invariants=constitutional_invariants()
        )
        encoded = json.dumps(payload)
        assert json.loads(encoded)["gate_passed"] is real_result.gate_passed

    def test_report_names_the_offending_module_and_line(self, tmp_path) -> None:
        """A report that cannot locate a breach makes deleting the rule the
        cheapest route to green."""
        graph = write_tree(tmp_path / "pkg", {"contracts/a.py": "\nimport requests\n"})
        rule = AllowedRootsRule(
            rule_id="T", description="", source_prefix="pkg.contracts",
            allowed_roots=frozenset(),
        )
        suite = ArchitectureSuite(rules=(rule,))
        report = render_text(suite.run(graph))
        assert "pkg.contracts.a:2" in report
        assert "requests" in report

    def test_dependency_summary_ranks_by_fan_in(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {
                "core.py": "x = 1\n",
                "a.py": "from pkg.core import x\n",
                "b.py": "from pkg.core import x\n",
            },
        )
        summary = dependency_summary(graph)
        assert summary["most_depended_upon"][0]["module"] == "pkg.core"
        assert summary["most_depended_upon"][0]["dependents"] == 2

    def test_summary_line_states_the_gate(self, real_result) -> None:
        assert ("PASS" if real_result.gate_passed else "FAIL") in real_result.summary()


class TestGraphConstruction:
    def test_unparseable_file_is_skipped_not_fatal(self, tmp_path) -> None:
        """One broken file must not stop the whole suite."""
        graph = write_tree(
            tmp_path / "pkg",
            {"good.py": "import dataclasses\n", "bad.py": "def (((\n"},
        )
        assert "pkg.good" in graph
        assert "pkg.bad" not in graph

    def test_package_init_maps_to_the_package_name(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "pkg", {"sub/__init__.py": "x = 1\n"})
        assert "pkg.sub" in graph

    def test_pycache_is_excluded(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "pkg",
            {"a.py": "x = 1\n", "__pycache__/a.cpython-313.py": "x = 1\n"},
        )
        assert len(graph) == 1

    def test_imports_record_line_numbers(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "pkg", {"a.py": "\n\nimport json\n"})
        module = graph.get("pkg.a")
        assert module is not None
        assert module.imports == (("json", 3),)


class TestCliEntryPoint:
    def test_cli_exits_zero_when_the_gate_passes(self) -> None:
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "backend.platform.architecture"],
            cwd=REPO_BACKEND.parent,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stdout[-2000:]
        assert "ARCHITECTURE GATE: PASS" in result.stdout
