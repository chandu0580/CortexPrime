"""Phase 7.5 — belief formation is fenced by architecture rules.

One genuinely new invariant is added (Part U): a model plane cannot import the
``Belief`` constructor (extends BND-MODEL-CANNOT-CREATE-FACT). Everything else is
already covered — belief formation lives under ``backend/world/application`` and
so is fenced from execution and from the database by the existing rules. Current
tree PASSES; synthetic violations FAIL.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from backend.platform.architecture.boundary_rules import (
    ModelCannotCreateFactRule,
    WorldApplicationPureRule,
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


class TestCurrentBeliefLayerPasses:
    def test_current_world_including_belief_passes(self):
        graph = ModuleGraph.build(REPO_BACKEND)
        assert WorldCannotExecuteRule().evaluate(graph).passed
        assert WorldApplicationPureRule().evaluate(graph).passed
        assert ModelCannotCreateFactRule().evaluate(graph).passed


class TestModelCannotCreateBelief:
    def test_harness_importing_belief_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "harness/belief_leak.py":
                "from backend.contracts.world import Belief\n"})
        result = ModelCannotCreateFactRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "Belief" for v in result.violations)

    def test_agents_importing_belief_via_epistemic_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "agents/belief_leak.py":
                "from backend.contracts.world.epistemic import Belief\n"})
        assert not ModelCannotCreateFactRule().evaluate(graph).passed

    def test_a_model_plane_may_still_import_proposal(self, tmp_path):
        # the firewall forbids the derived constructors, not the proposal types
        graph = write_tree(tmp_path / "backend", {
            "harness/ok.py":
                "from backend.contracts.world import ModelProposal, Hypothesis\n"})
        assert ModelCannotCreateFactRule().evaluate(graph).passed


class TestBeliefCannotExecute:
    def test_belief_importing_a_connector_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/belief_leak.py":
                "from backend.connectors.kubernetes import KubernetesConnector\n"})
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_belief_importing_a_database_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/belief_leak.py":
                "from backend.database.durable.tables import world_fact_table\n"})
        assert not WorldApplicationPureRule().evaluate(graph).passed
