"""Phase 6.1 sensitivity tests — the L1 quarantine rules catch violations.

A fitness rule that has never been seen to fail is decoration. Each test here
synthesizes a violating tree (or mutates a copy of the gated source) and
asserts the rule goes red — the same discipline as the existing state/tenancy
guard tests. Plus the runtime probe: ``ungated_surfaces()`` stays empty and
the effect gate refuses with the flag unset.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from backend.api.legacy_execution_boundary import (
    LEGACY_EXECUTION_FLAG,
    LegacyExecutionRefused,
    ungated_surfaces,
)
from backend.platform.architecture.boundary_rules import (
    ConnectorEffectGateRule,
    ProcessSpawnQuarantineRule,
    ProviderSdkImportRule,
)
from backend.platform.architecture.rules import ModuleGraph

REPO_BACKEND = Path(__file__).resolve().parents[2] / "backend"


def write_tree(root: Path, files: dict[str, str]) -> ModuleGraph:
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
    return ModuleGraph.build(root, package_root=root.name)


class TestProcessSpawnRuleSensitivity:
    def test_new_spawn_site_fails(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "backend",
            {
                "services/sneaky.py": """
                    import subprocess

                    def go():
                        subprocess.Popen(["rm", "-rf", "/"])
                    """,
            },
        )
        result = ProcessSpawnQuarantineRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "subprocess.Popen" for v in result.violations)

    def test_async_spawn_fails(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "backend",
            {
                "services/sneaky.py": """
                    import asyncio

                    async def go():
                        await asyncio.create_subprocess_exec("terraform", "apply")
                    """,
            },
        )
        result = ProcessSpawnQuarantineRule().evaluate(graph)
        assert not result.passed

    def test_bare_name_alias_fails(self, tmp_path) -> None:
        """``from subprocess import Popen`` does not evade the rule."""
        graph = write_tree(
            tmp_path / "backend",
            {
                "services/sneaky.py": """
                    from subprocess import Popen

                    def go():
                        Popen(["evil"])
                    """,
            },
        )
        result = ProcessSpawnQuarantineRule().evaluate(graph)
        assert not result.passed

    def test_asyncio_run_is_not_a_spawn(self, tmp_path) -> None:
        """The event-loop runner must not false-positive."""
        graph = write_tree(
            tmp_path / "backend",
            {
                "services/fine.py": """
                    import asyncio

                    def go():
                        asyncio.run(main())
                    """,
            },
        )
        result = ProcessSpawnQuarantineRule().evaluate(graph)
        assert result.passed

    def test_comment_and_docstring_do_not_trip(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "backend",
            {
                "services/fine.py": '''
                    """Mentions subprocess.Popen in prose only."""

                    # subprocess.Popen(["not", "code"])
                    def go():
                        return "subprocess.Popen"
                    ''',
            },
        )
        result = ProcessSpawnQuarantineRule().evaluate(graph)
        assert result.passed


class TestProviderSdkRuleSensitivity:
    def test_new_docker_import_fails(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "backend",
            {
                "services/sneaky.py": """
                    import docker

                    def go():
                        docker.from_env().containers.list()
                    """,
            },
        )
        result = ProviderSdkImportRule().evaluate(graph)
        assert not result.passed

    def test_dynamic_import_fails(self, tmp_path) -> None:
        """``importlib.import_module('docker')`` is not an escape hatch."""
        graph = write_tree(
            tmp_path / "backend",
            {
                "services/sneaky.py": """
                    import importlib

                    def go():
                        sdk = importlib.import_module("docker")
                        return sdk.from_env()
                    """,
            },
        )
        result = ProviderSdkImportRule().evaluate(graph)
        assert not result.passed

    def test_dunder_import_fails(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "backend",
            {
                "services/sneaky.py": """
                    def go():
                        return __import__("kubernetes")
                    """,
            },
        )
        result = ProviderSdkImportRule().evaluate(graph)
        assert not result.passed

    def test_allowlisted_connector_passes(self, tmp_path) -> None:
        graph = write_tree(
            tmp_path / "backend",
            {
                "connectors/docker.py": """
                    import docker
                    """,
            },
        )
        result = ProviderSdkImportRule().evaluate(graph)
        assert result.passed


class TestEffectGateRuleSensitivity:
    """Mutated copies of the real gated modules must fail the rule."""

    def _real_graph_with_mutation(self, tmp_path, module_rel: str, mutate) -> ModuleGraph:
        root = tmp_path / "backend"
        # Every module the rule gates (Phase 11.1-K added the raw-request
        # sites), so the unmutated copy is the real, complete gated surface.
        gated = {site[0] for site in ConnectorEffectGateRule.gate_sites}
        rels = sorted({m.split(".", 1)[1].replace(".", "/") + ".py" for m in gated}
                      | {"connectors/base.py", "connectors/terraform.py"})
        for rel in rels:
            src = (REPO_BACKEND / rel).read_text(encoding="utf-8")
            if rel == module_rel:
                src = mutate(src)
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(src, encoding="utf-8")
        return ModuleGraph.build(root, package_root="backend")

    def test_current_sources_pass(self, tmp_path) -> None:
        graph = self._real_graph_with_mutation(tmp_path, "", lambda s: s)
        result = ConnectorEffectGateRule().evaluate(graph)
        assert result.passed, "\n".join(str(v) for v in result.violations)

    def test_removing_gate_from_execute_fails(self, tmp_path) -> None:
        graph = self._real_graph_with_mutation(
            tmp_path,
            "connectors/base.py",
            lambda s: s.replace(
                "assert_effect_permitted(self.connector_type, operation)", "pass"
            ),
        )
        result = ConnectorEffectGateRule().evaluate(graph)
        assert not result.passed

    def test_gate_not_first_statement_fails(self, tmp_path) -> None:
        graph = self._real_graph_with_mutation(
            tmp_path,
            "connectors/base.py",
            lambda s: s.replace(
                "assert_effect_permitted(self.connector_type, operation)\n        start = time.monotonic()",
                "start = time.monotonic()\n        assert_effect_permitted(self.connector_type, operation)",
            ),
        )
        result = ConnectorEffectGateRule().evaluate(graph)
        assert not result.passed

    def test_removing_terraform_gate_fails(self, tmp_path) -> None:
        graph = self._real_graph_with_mutation(
            tmp_path,
            "connectors/terraform.py",
            lambda s: s.replace("assert_effect_permitted(", "print("),
        )
        result = ConnectorEffectGateRule().evaluate(graph)
        assert not result.passed

    def test_missing_gated_module_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {"connectors/other.py": "x = 1\n"})
        result = ConnectorEffectGateRule().evaluate(graph)
        assert not result.passed


class TestRuntimeQuarantineProbe:
    """The L1 runtime facts, asserted directly — the CI form of the invariant
    'zero known ungoverned side-effect paths on the acting path'."""

    def test_no_ungated_surfaces(self) -> None:
        assert ungated_surfaces() == ()

    def test_effect_gate_refuses_write_with_flag_unset(self, monkeypatch) -> None:
        monkeypatch.delenv(LEGACY_EXECUTION_FLAG, raising=False)
        from backend.connectors.effects import assert_effect_permitted

        with pytest.raises(LegacyExecutionRefused):
            assert_effect_permitted("github", "create_issue")

    def test_sandbox_spawn_refuses_with_flag_unset(self, monkeypatch) -> None:
        monkeypatch.delenv(LEGACY_EXECUTION_FLAG, raising=False)
        from backend.api.legacy_execution_boundary import guard_legacy_internal

        with pytest.raises(LegacyExecutionRefused):
            guard_legacy_internal("sandbox:subprocess git")
