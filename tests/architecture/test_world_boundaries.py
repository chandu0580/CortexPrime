"""Phase 7.1 sensitivity tests — the World Plane fitness rules catch real
violations. Part U/V: current code PASSes, a synthetic violation FAILs."""

from __future__ import annotations

import textwrap
from pathlib import Path

from backend.platform.architecture.boundary_rules import (
    ModelCannotCreateFactRule,
    WorldCannotExecuteRule,
)
from backend.platform.architecture.rules import ModuleGraph

REPO_BACKEND = Path(__file__).resolve().parents[2] / "backend"


def write_tree(root: Path, files: dict[str, str]) -> ModuleGraph:
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
    return ModuleGraph.build(root, package_root=root.name)


class TestWorldCannotExecute:
    def test_current_world_plane_passes(self) -> None:
        graph = ModuleGraph.build(REPO_BACKEND)
        assert WorldCannotExecuteRule().evaluate(graph).passed

    def test_world_importing_a_connector_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "contracts/world/leak.py":
                "from backend.connectors.github import GitHubConnector\n",
        })
        result = WorldCannotExecuteRule().evaluate(graph)
        assert not result.passed
        assert any("connectors" in v.offender for v in result.violations)

    def test_world_importing_the_gateway_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "contracts/world/leak.py": (
                "from backend.contexts.execution.application.invocation_gateway "
                "import SecureCapabilityInvocationGateway\n"
            ),
        })
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_world_importing_credentials_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "contracts/world/leak.py":
                "from backend.platform.credentials.broker import CredentialBroker\n",
        })
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_world_importing_a_database_impl_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "contracts/world/leak.py":
                "from backend.database.durable.tables import x\n",
        })
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_world_importing_the_harness_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "contracts/world/leak.py": "from backend.harness.loop import HarnessLoop\n",
        })
        assert not WorldCannotExecuteRule().evaluate(graph).passed


class TestModelCannotCreateFact:
    def test_current_planes_pass(self) -> None:
        graph = ModuleGraph.build(REPO_BACKEND)
        assert ModelCannotCreateFactRule().evaluate(graph).passed

    def test_harness_importing_fact_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py":
                "from backend.contracts.world.epistemic import Fact\n",
        })
        result = ModelCannotCreateFactRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "Fact" for v in result.violations)

    def test_harness_importing_observation_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "harness/leak.py":
                "from backend.contracts.world import Observation\n",
        })
        assert not ModelCannotCreateFactRule().evaluate(graph).passed

    def test_agents_importing_fact_fails(self, tmp_path) -> None:
        graph = write_tree(tmp_path / "backend", {
            "agents/leak.py":
                "from backend.contracts.world.epistemic import Fact, Observation\n",
        })
        assert not ModelCannotCreateFactRule().evaluate(graph).passed

    def test_harness_importing_proposal_and_hypothesis_is_allowed(self, tmp_path) -> None:
        """A model plane MAY import the types it is allowed to produce."""
        graph = write_tree(tmp_path / "backend", {
            "harness/ok.py":
                "from backend.contracts.world import ModelProposal, Hypothesis\n",
        })
        assert ModelCannotCreateFactRule().evaluate(graph).passed
