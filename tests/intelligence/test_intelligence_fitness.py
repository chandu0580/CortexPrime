"""Phase 8.1 — the Intelligence Plane is fenced by architecture rules (Part T).

Two genuinely new rules (BND-INTELLIGENCE-CANNOT-EXECUTE, BND-NO-V1-INTELLIGENCE-
IMPORT); the model-cannot-create-world rule is extended to backend.intelligence
and the append-only rule to its ledger. Current tree PASSES; synthetic violations
FAIL.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from backend.platform.architecture.boundary_rules import (
    IntelligenceCannotBypassWorldRule,
    IntelligenceCannotExecuteRule,
    ModelCannotCreateFactRule,
    NoV1IntelligenceImportRule,
    ObservationAppendOnlyRule,
)
from backend.platform.architecture.rules import ModuleGraph

REPO_BACKEND = Path(__file__).resolve().parents[2] / "backend"


def write_tree(root: Path, files: dict[str, str]) -> ModuleGraph:
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
    return ModuleGraph.build(root, package_root=root.name)


class TestCurrentIntelligencePasses:
    def test_current_tree_passes_all(self):
        graph = ModuleGraph.build(REPO_BACKEND)
        assert IntelligenceCannotExecuteRule().evaluate(graph).passed
        assert NoV1IntelligenceImportRule().evaluate(graph).passed
        assert IntelligenceCannotBypassWorldRule().evaluate(graph).passed
        assert ModelCannotCreateFactRule().evaluate(graph).passed
        assert ObservationAppendOnlyRule().evaluate(graph).passed


class TestIntelligenceCannotBypassWorld:
    """Phase 8.4 (Part T): the Intelligence Plane reads reality only through the
    World application layer — never the World's storage."""

    def test_importing_world_infrastructure_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/rogue.py":
                "from backend.world.infrastructure import SqlFactRepository\n"})
        assert not IntelligenceCannotBypassWorldRule().evaluate(graph).passed

    def test_importing_a_world_sql_repo_module_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/rogue.py":
                "from backend.world.infrastructure.sql_fact import SqlFactRepository\n"})
        assert not IntelligenceCannotBypassWorldRule().evaluate(graph).passed

    def test_world_application_query_is_allowed(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/ok.py":
                "from backend.world.application import WorldQuery, BeliefFormation\n"})
        assert IntelligenceCannotBypassWorldRule().evaluate(graph).passed

    def test_own_investigation_ledger_is_allowed(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/infrastructure/ok.py":
                "from backend.database.durable.tables import world_investigation_table\n"})
        assert IntelligenceCannotBypassWorldRule().evaluate(graph).passed


class TestIntelligenceCannotExecute:
    def test_importing_a_connector_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/leak.py":
                "from backend.connectors.kubernetes import KubernetesConnector\n"})
        assert not IntelligenceCannotExecuteRule().evaluate(graph).passed

    def test_importing_the_gateway_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/leak.py": (
                "from backend.contexts.execution.application.invocation_gateway "
                "import SecureCapabilityInvocationGateway\n")})
        assert not IntelligenceCannotExecuteRule().evaluate(graph).passed

    def test_importing_a_direct_llm_provider_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/leak.py":
                "from backend.llm.llm_gateway import LLMGateway\n"})
        assert not IntelligenceCannotExecuteRule().evaluate(graph).passed

    def test_importing_computer_use_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/leak.py":
                "from backend.computer.desktop_controller import DesktopController\n"})
        assert not IntelligenceCannotExecuteRule().evaluate(graph).passed

    def test_reading_the_durable_store_is_allowed(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/infrastructure/ok.py":
                "from backend.database.durable.session import DurableStore\n"})
        assert IntelligenceCannotExecuteRule().evaluate(graph).passed

    def test_harness_governed_boundary_is_allowed(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/ok.py":
                "from backend.harness.llm_boundary import GovernedModelBoundary\n"})
        assert IntelligenceCannotExecuteRule().evaluate(graph).passed


class TestNoV1IntelligenceImport:
    def test_importing_v1_memory_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/leak.py":
                "from backend.memory.vector_memory import VectorMemory\n"})
        result = NoV1IntelligenceImportRule().evaluate(graph)
        assert not result.passed
        assert any("memory" in v.offender for v in result.violations)

    def test_importing_v1_orchestrator_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/leak.py":
                "from backend.orchestration.cognition_pipeline import CognitionPipeline\n"})
        assert not NoV1IntelligenceImportRule().evaluate(graph).passed


class TestIntelligenceCannotWriteWorld:
    def test_importing_fact_constructor_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/leak.py":
                "from backend.contracts.world import Fact\n"})
        result = ModelCannotCreateFactRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "Fact" for v in result.violations)

    def test_importing_verification_or_outcome_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/leak.py":
                "from backend.contracts.world import WorldVerification, Outcome\n"})
        assert not ModelCannotCreateFactRule().evaluate(graph).passed

    def test_may_import_hypothesis_and_prediction(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/application/ok.py":
                "from backend.contracts.world import Hypothesis, Prediction, ModelHypothesisProposal\n"})
        assert ModelCannotCreateFactRule().evaluate(graph).passed


class TestInvestigationLedgerAppendOnly:
    def test_updating_investigation_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "intelligence/infrastructure/leak.py": textwrap.dedent("""
                import sqlalchemy as sa
                def bad(t, work):
                    work.execute(sa.update(t).values(to_status='completed'))
            """)})
        result = ObservationAppendOnlyRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "sa.update" for v in result.violations)
