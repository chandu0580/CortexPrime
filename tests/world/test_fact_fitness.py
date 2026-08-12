"""Phase 7.3 — the fact layer is covered by the EXISTING architecture rules.

No new fitness rule is added (STEP 20: only where a new invariant is exposed).
The bitemporal fact ledger lives under ``backend/world``, so:
  * ObservationAppendOnlyRule already forbids UPDATE/DELETE there — supersession
    is a new row, never a mutation (proven: a synthetic sa.update in the fact
    infrastructure FAILs);
  * ModelCannotCreateFactRule already forbids the model planes importing Fact —
    a model cannot construct a fact (proven: a synthetic import FAILs);
  * WorldCannotExecuteRule / WorldApplicationPureRule already fence the new
    modules (proven: current code PASSES, a synthetic violation FAILS).
These sensitivity tests demonstrate the coverage; the current tree passes.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from backend.platform.architecture.boundary_rules import (
    ModelCannotCreateFactRule,
    ObservationAppendOnlyRule,
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


class TestCurrentFactLayerPasses:
    def test_current_world_including_facts_passes_all(self):
        graph = ModuleGraph.build(REPO_BACKEND)
        assert WorldCannotExecuteRule().evaluate(graph).passed
        assert WorldApplicationPureRule().evaluate(graph).passed
        assert ObservationAppendOnlyRule().evaluate(graph).passed
        assert ModelCannotCreateFactRule().evaluate(graph).passed


class TestFactSupersessionIsAppendOnly:
    def test_updating_a_fact_row_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/infrastructure/sql_fact_leak.py": textwrap.dedent("""
                import sqlalchemy as sa
                def supersede(t, work):
                    work.execute(sa.update(t).values(value_digest='x'))
            """)})
        result = ObservationAppendOnlyRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "sa.update" for v in result.violations)

    def test_deleting_a_fact_row_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/infrastructure/sql_fact_leak.py": textwrap.dedent("""
                import sqlalchemy as sa
                def prune(t, work):
                    work.execute(sa.delete(t))
            """)})
        assert not ObservationAppendOnlyRule().evaluate(graph).passed


class TestModelCannotCreateFact:
    def test_harness_importing_fact_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "harness/fact_leak.py":
                "from backend.contracts.world.epistemic import Fact\n"})
        result = ModelCannotCreateFactRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "Fact" for v in result.violations)

    def test_agents_importing_fact_via_package_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "agents/fact_leak.py":
                "from backend.contracts.world import Fact\n"})
        assert not ModelCannotCreateFactRule().evaluate(graph).passed


class TestFactInfraStaysFenced:
    def test_fact_infrastructure_importing_a_connector_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/infrastructure/sql_fact_leak.py":
                "from backend.connectors.kubernetes import KubernetesConnector\n"})
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_fact_application_importing_a_database_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/fact_leak.py":
                "from backend.database.durable.tables import world_fact_table\n"})
        assert not WorldApplicationPureRule().evaluate(graph).passed
