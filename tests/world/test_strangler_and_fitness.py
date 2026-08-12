"""Phase 7.2 — the V1 strangler (Part P) and the new world fitness rules (Part R)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from backend.api.legacy_execution_boundary import (
    LEGACY_EXECUTION_FLAG,
    LegacyExecutionRefused,
)
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


# ======================================================================
# Part P — the strangled destructive V1 world-state path
# ======================================================================

class TestTrackPodStrangler:
    @pytest.fixture(autouse=True)
    def _isolate_pods_file(self, tmp_path, monkeypatch):
        import backend.services.enterprise_infrastructure_intelligence as m
        monkeypatch.setattr(m, "_PODS_FILE", tmp_path / "pods.json")
        yield

    def test_track_pod_is_refused_by_default(self, monkeypatch):
        """Quarantined: non-authoritative unless the legacy flag is set."""
        monkeypatch.delenv(LEGACY_EXECUTION_FLAG, raising=False)
        from backend.services.enterprise_infrastructure_intelligence import (
            KubernetesIntelligence,
        )
        with pytest.raises(LegacyExecutionRefused):
            KubernetesIntelligence.track_pod("c1", "default", "pod-a", status="running")

    def test_track_pod_wrote_nothing_when_refused(self, monkeypatch):
        import backend.services.enterprise_infrastructure_intelligence as m
        monkeypatch.delenv(LEGACY_EXECUTION_FLAG, raising=False)
        with pytest.raises(LegacyExecutionRefused):
            m.KubernetesIntelligence.track_pod("c1", "default", "pod-a")
        assert not m._PODS_FILE.exists()  # no destructive write happened

    def test_the_old_behavior_was_destructive(self, monkeypatch):
        """With the flag set, track_pod still exhibits the destructive upsert the
        strangler exists to replace: a second call MUTATES the first in place,
        losing the prior observation (only one record survives)."""
        monkeypatch.setenv(LEGACY_EXECUTION_FLAG, "1")
        from backend.services.enterprise_infrastructure_intelligence import (
            KubernetesIntelligence, KubernetesIntelligence as K,
        )
        import backend.services.enterprise_infrastructure_intelligence as m

        K.track_pod("c1", "default", "pod-a", status="running", restarts=0)
        K.track_pod("c1", "default", "pod-a", status="crashloop", restarts=5)
        pods = m._load_json(m._PODS_FILE)
        # Destructive: one record, prior "running/0" overwritten by "crashloop/5".
        matching = [p for p in pods if p["name"] == "pod-a"]
        assert len(matching) == 1
        assert matching[0]["status"] == "crashloop"
        assert matching[0]["restarts"] == 5
        # The prior observation ("running", 0 restarts) is GONE — this is exactly
        # what the append-only World Plane observation ledger fixes.


# ======================================================================
# Part R — the world fitness rules catch real violations
# ======================================================================

class TestWorldFitnessRules:
    def test_current_world_passes_all_three(self):
        graph = ModuleGraph.build(REPO_BACKEND)
        assert WorldCannotExecuteRule().evaluate(graph).passed
        assert WorldApplicationPureRule().evaluate(graph).passed
        assert ObservationAppendOnlyRule().evaluate(graph).passed

    def test_world_importing_a_connector_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/leak.py": "from backend.connectors.github import X\n"})
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_world_importing_a_credential_carrier_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/leak.py": "from backend.platform.credentials.broker import X\n"})
        assert not WorldCannotExecuteRule().evaluate(graph).passed

    def test_world_importing_the_secret_detector_is_allowed(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/ok.py":
                "from backend.platform.credentials.inspection import find_secrets\n"})
        assert WorldCannotExecuteRule().evaluate(graph).passed

    def test_infrastructure_importing_the_durable_store_is_allowed(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/infrastructure/ok.py":
                "from backend.database.durable.session import DurableStore\n"})
        assert WorldCannotExecuteRule().evaluate(graph).passed

    def test_application_importing_a_database_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/application/leak.py":
                "from backend.database.durable.tables import x\n"})
        assert not WorldApplicationPureRule().evaluate(graph).passed

    def test_infrastructure_importing_a_database_passes_application_rule(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/infrastructure/ok.py":
                "from backend.database.durable.tables import x\n"})
        assert WorldApplicationPureRule().evaluate(graph).passed

    def test_world_issuing_an_update_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/infrastructure/leak.py": textwrap.dedent("""
                import sqlalchemy as sa
                def bad(t, work):
                    work.execute(sa.update(t).values(x=1))
            """)})
        result = ObservationAppendOnlyRule().evaluate(graph)
        assert not result.passed
        assert any(v.offender == "sa.update" for v in result.violations)

    def test_world_issuing_a_delete_fails(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/infrastructure/leak.py": textwrap.dedent("""
                import sqlalchemy as sa
                def bad(t, work):
                    work.execute(sa.delete(t))
            """)})
        assert not ObservationAppendOnlyRule().evaluate(graph).passed

    def test_world_insert_and_select_are_allowed(self, tmp_path):
        graph = write_tree(tmp_path / "backend", {
            "world/infrastructure/ok.py": textwrap.dedent("""
                import sqlalchemy as sa
                def fine(t, work):
                    work.execute(sa.insert(t).values(x=1))
                    return work.execute(sa.select(t.c.x))
            """)})
        assert ObservationAppendOnlyRule().evaluate(graph).passed
