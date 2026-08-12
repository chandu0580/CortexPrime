"""Phase 7.7 — the Assurance Plane is fenced by architecture rules (Part T).

One genuinely new rule (BND-ASSURANCE-CANNOT-EXECUTE) fences the new plane from
execution; the append-only rule is extended to cover verifications too. Model
planes still cannot mint a WorldVerification (BND-MODEL-CANNOT-CREATE-FACT,
Phase 7.6). Current tree PASSES; synthetic violations FAIL.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from backend.platform.architecture.boundary_rules import (
    AssuranceCannotExecuteRule,
    ModelCannotCreateFactRule,
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


class TestCurrentAssurancePasses:
    def test_current_assurance_plane_passes(self):
        graph = ModuleGraph.build(REPO_BACKEND)
        assert AssuranceCannotExecuteRule().evaluate(graph).passed
        assert ObservationAppendOnlyRule().evaluate(graph).passed
        assert ModelCannotCreateFactRule().evaluate(graph).passed


class TestAssuranceCannotExecute:
    def test_assurance_importing_a_connector_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "assurance/application/leak.py":
                "from backend.connectors.kubernetes import KubernetesConnector\n"})
        result = AssuranceCannotExecuteRule().evaluate(graph)
        assert not result.passed
        assert any("connectors" in v.offender for v in result.violations)

    def test_assurance_importing_the_gateway_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "assurance/application/leak.py": (
                "from backend.contexts.execution.application.invocation_gateway "
                "import SecureCapabilityInvocationGateway\n")})
        assert not AssuranceCannotExecuteRule().evaluate(graph).passed

    def test_assurance_importing_the_harness_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "assurance/application/leak.py": "from backend.harness.loop import HarnessLoop\n"})
        assert not AssuranceCannotExecuteRule().evaluate(graph).passed

    def test_assurance_reading_the_durable_store_is_allowed(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "assurance/infrastructure/ok.py":
                "from backend.database.durable.session import DurableStore\n"})
        assert AssuranceCannotExecuteRule().evaluate(graph).passed


class TestVerificationsAreAppendOnly:
    def test_updating_a_verification_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "assurance/infrastructure/leak.py": textwrap.dedent("""
                import sqlalchemy as sa
                def bad(t, work):
                    work.execute(sa.update(t).values(verdict='supported'))
            """)})
        result = ObservationAppendOnlyRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "sa.update" for v in result.violations)

    def test_deleting_a_verification_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "assurance/infrastructure/leak.py": textwrap.dedent("""
                import sqlalchemy as sa
                def bad(t, work):
                    work.execute(sa.delete(t))
            """)})
        assert not ObservationAppendOnlyRule().evaluate(graph).passed


class TestModelCannotMintVerification:
    def test_harness_importing_worldverification_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "harness/verify_leak.py": "from backend.contracts.world import WorldVerification\n"})
        assert not ModelCannotCreateFactRule().evaluate(graph).passed
