"""Phase 7.4 — the World Query layer is covered by EXISTING architecture rules.

No new fitness rule is added (Part V: only where a new invariant is exposed).
The query layer lives under ``backend/world/application``, so it is already:
  * fenced from execution by WorldCannotExecuteRule (no connector/gateway/
    transport/credential/scheduler/execution) — proven: a synthetic connector
    import FAILs;
  * kept database-free by WorldApplicationPureRule (it depends on reader ports,
    not a store) — proven: a synthetic database import FAILs.
Authority/freshness are deterministic config, not model-defined, and cannot
mutate facts (BND-OBSERVATION-APPEND-ONLY covers all of backend/world). The
current tree passes.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from backend.platform.architecture.boundary_rules import (
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


class TestCurrentQueryLayerPasses:
    def test_current_world_including_query_passes(self):
        graph = ModuleGraph.build(REPO_BACKEND)
        assert WorldCannotExecuteRule().evaluate(graph).passed
        assert WorldApplicationPureRule().evaluate(graph).passed
        assert ObservationAppendOnlyRule().evaluate(graph).passed


class TestQueryCannotExecute:
    def test_query_importing_a_connector_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/query_leak.py":
                "from backend.connectors.kubernetes import KubernetesConnector\n"})
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_query_importing_the_gateway_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/query_leak.py": (
                "from backend.contexts.execution.application.invocation_gateway "
                "import SecureCapabilityInvocationGateway\n")})
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_query_importing_transport_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/query_leak.py":
                "from backend.platform.transport import TransportBroker\n"})
        assert not WorldCannotExecuteRule().evaluate(graph).passed


class TestQueryStaysDatabaseFree:
    def test_query_importing_a_database_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/query_leak.py":
                "from backend.database.durable.tables import world_fact_table\n"})
        assert not WorldApplicationPureRule().evaluate(graph).passed
