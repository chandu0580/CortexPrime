"""Phase 6.2 sensitivity tests — the harness-plane fitness rules catch real
violations. Part M: current code PASSes, a synthetic violation FAILs."""

from __future__ import annotations

import textwrap
from pathlib import Path

from backend.platform.architecture.boundary_rules import (
    HarnessCredentialIsolationRule,
    HarnessNoDynamicDispatchRule,
    HarnessNoExecutionRule,
)
from backend.platform.architecture.rules import ModuleGraph

REPO_BACKEND = Path(__file__).resolve().parents[2] / "backend"


def write_tree(root: Path, files: dict[str, str]) -> ModuleGraph:
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
    return ModuleGraph.build(root, package_root=root.name)


class TestHarnessCredentialIsolation:
    def test_current_harness_passes(self) -> None:
        graph = ModuleGraph.build(REPO_BACKEND)
        assert HarnessCredentialIsolationRule().evaluate(graph).passed

    def test_importing_the_broker_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": """
                from backend.platform.credentials.broker import CredentialBroker
            """,
        })
        result = HarnessCredentialIsolationRule().evaluate(graph)
        assert not result.passed
        assert any("broker" in v.offender for v in result.violations)

    def test_importing_credential_material_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": "from backend.platform.credentials.material import X\n",
        })
        assert not HarnessCredentialIsolationRule().evaluate(graph).passed

    def test_importing_the_redactor_is_allowed(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/ok.py": "from backend.platform.credentials.redaction import scrub_text\n",
        })
        assert HarnessCredentialIsolationRule().evaluate(graph).passed


class TestHarnessNoExecution:
    def test_current_harness_passes(self) -> None:
        graph = ModuleGraph.build(REPO_BACKEND)
        assert HarnessNoExecutionRule().evaluate(graph).passed

    def test_importing_a_connector_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": "from backend.connectors.github import GitHubConnector\n",
        })
        result = HarnessNoExecutionRule().evaluate(graph)
        assert not result.passed
        assert any("connectors" in v.offender for v in result.violations)

    def test_importing_the_gateway_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": (
                "from backend.contexts.execution.application.invocation_gateway "
                "import SecureCapabilityInvocationGateway\n"
            ),
        })
        assert not HarnessNoExecutionRule().evaluate(graph).passed

    def test_importing_an_adapter_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": (
                "from backend.contexts.execution.infrastructure.adapters.connector "
                "import ConnectorAdapter\n"
            ),
        })
        assert not HarnessNoExecutionRule().evaluate(graph).passed

    def test_importing_transport_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": "from backend.platform.transport import TransportBroker\n",
        })
        assert not HarnessNoExecutionRule().evaluate(graph).passed

    def test_importing_the_durable_trace_store_is_allowed(self, tmp_path) -> None:
        """Writing the trace table is not a provider side effect."""
        graph = write_tree(tmp_path / "backend", {
            "harness/trace_sql.py": "from backend.database.durable.tables import x\n",
        })
        assert HarnessNoExecutionRule().evaluate(graph).passed


class TestHarnessNoDynamicDispatch:
    def test_current_harness_passes(self) -> None:
        graph = ModuleGraph.build(REPO_BACKEND)
        assert HarnessNoDynamicDispatchRule().evaluate(graph).passed

    def test_importlib_on_model_output_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": """
                import importlib

                def dispatch(model_named):
                    return importlib.import_module(model_named)
            """,
        })
        result = HarnessNoDynamicDispatchRule().evaluate(graph)
        assert not result.passed
        assert any("import_module" in v.offender for v in result.violations)

    def test_eval_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": "def run(s):\n    return eval(s)\n",
        })
        assert not HarnessNoDynamicDispatchRule().evaluate(graph).passed

    def test_exec_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": "def run(s):\n    exec(s)\n",
        })
        assert not HarnessNoDynamicDispatchRule().evaluate(graph).passed

    def test_dunder_import_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py": "def run(s):\n    return __import__(s)\n",
        })
        assert not HarnessNoDynamicDispatchRule().evaluate(graph).passed

    def test_static_import_and_getattr_on_known_object_are_allowed(self, tmp_path) -> None:
        """The legitimate patterns the real harness uses must not trip."""
        graph = write_tree(tmp_path / "backend", {
            "harness/ok.py": """
                from backend.platform.hashing import compute_digest

                def read(response):
                    return getattr(response, "provider", "")
            """,
        })
        assert HarnessNoDynamicDispatchRule().evaluate(graph).passed
