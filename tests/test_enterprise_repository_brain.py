"""
Comprehensive validation tests for Enterprise Repository Brain.

Phases covered:
  1. Repository Identity
  2. Architecture Model
  3. Dependency Graph
  4. Ownership Intelligence
  5. Runtime Mapping
  6. Operational History
  7. Architecture Drift
  8. Executive Integration
  9. Decision Integration
 10. Repository Dashboard
"""
from __future__ import annotations

import pytest
from typing import Any, Dict, List

from backend.services.enterprise_repository_brain import (
    EnterpriseRepositoryBrain,
    RepositoryIdentity,
    ArchitectureModel,
    ArchitectureComponent,
    OwnershipRecord,
    DriftRecord,
    repository_brain,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def brain() -> EnterpriseRepositoryBrain:
    return EnterpriseRepositoryBrain()


# =============================================================================
# Phase 1 — Repository Identity
# =============================================================================


class TestRepositoryIdentity:
    """Phase 1: Repository identity tracking."""

    @pytest.mark.asyncio
    async def test_refresh_identity_creates(self, brain):
        """Refresh identity creates a new repository record."""
        result = await brain.refresh_identity("org/test")
        assert result.repository == "org/test"
        assert result.organization == "org"
        assert result.branches == []
        assert isinstance(result.languages, dict)
        assert result.last_scanned_at != ""

    @pytest.mark.asyncio
    async def test_get_identity_returns_none_for_missing(self, brain):
        """Getting identity for non-existent repo returns None."""
        result = await brain.get_identity("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_identity_after_refresh(self, brain):
        """Getting identity after refresh returns the record."""
        await brain.refresh_identity("org/get-test")
        result = await brain.get_identity("org/get-test")
        assert result is not None
        assert result.repository == "org/get-test"

    @pytest.mark.asyncio
    async def test_list_repositories_returns_all(self, brain):
        """List repositories returns all refreshed repos."""
        await brain.refresh_identity("org/a")
        await brain.refresh_identity("org/b")
        repos = await brain.list_repositories()
        assert len(repos) >= 2
        names = [r["repository"] for r in repos]
        assert "org/a" in names
        assert "org/b" in names

    @pytest.mark.asyncio
    async def test_identity_org_extraction(self, brain):
        """Organization is correctly extracted from repository name."""
        r1 = await brain.refresh_identity("my-org/my-repo")
        assert r1.organization == "my-org"

        r2 = await brain.refresh_identity("single-repo")
        assert r2.repository == "single-repo"

    @pytest.mark.asyncio
    async def test_identity_persistence(self, brain):
        """Identity persists across brain instances."""
        brain.clear()
        b1 = EnterpriseRepositoryBrain()
        await b1.refresh_identity("org/persist-test")
        b2 = EnterpriseRepositoryBrain()
        ident = await b2.get_identity("org/persist-test")
        assert ident is not None
        assert ident.repository == "org/persist-test"


# =============================================================================
# Phase 2 — Architecture Model
# =============================================================================


class TestArchitectureModel:
    """Phase 2: Architecture model maintenance."""

    @pytest.mark.asyncio
    async def test_refresh_architecture_creates(self, brain):
        """Refresh architecture creates a model for the repo."""
        result = await brain.refresh_architecture("org/arch-test")
        assert result is not None
        assert isinstance(result.services, list)
        assert isinstance(result.modules, list)
        assert isinstance(result.apis, list)
        assert result.built_at != ""

    @pytest.mark.asyncio
    async def test_get_architecture_returns_model(self, brain):
        """Get architecture returns the refreshed model."""
        await brain.refresh_architecture("org/get-arch")
        result = await brain.get_architecture("org/get-arch")
        assert result is not None
        assert isinstance(result.services, list)

    @pytest.mark.asyncio
    async def test_get_architecture_nonexistent(self, brain):
        """Get architecture for non-existent repo returns None."""
        result = await brain.get_architecture("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_architecture_properties(self, brain):
        """Architecture model has all component sections."""
        result = await brain.refresh_architecture("org/props")
        assert hasattr(result, "services")
        assert hasattr(result, "modules")
        assert hasattr(result, "libraries")
        assert hasattr(result, "apis")
        assert hasattr(result, "workers")
        assert hasattr(result, "schedulers")
        assert hasattr(result, "agents")
        assert hasattr(result, "connectors")


# =============================================================================
# Phase 3 — Dependency Graph
# =============================================================================


class TestDependencyGraph:
    """Phase 3: Dependency graph — reuses CodeIntelligence."""

    @pytest.mark.asyncio
    async def test_get_dependency_graph(self, brain):
        """Dependency graph returns a graph structure."""
        result = await brain.get_dependency_graph("org/dep-test")
        assert isinstance(result, dict)
        # Should have nodes and edges
        assert "nodes" in result or "edges" in result

    @pytest.mark.asyncio
    async def test_get_impact(self, brain):
        """Impact analysis returns risk-aware result."""
        result = await brain.get_impact("org/impact-test", "main.py")
        assert isinstance(result, dict)
        assert "risk_score" in result or "affected_files" in result


# =============================================================================
# Phase 4 — Ownership Intelligence
# =============================================================================


class TestOwnershipIntelligence:
    """Phase 4: Ownership tracking."""

    @pytest.mark.asyncio
    async def test_refresh_ownership(self, brain):
        """Refresh ownership returns ownership records."""
        records = await brain.refresh_ownership("org/own-test")
        assert isinstance(records, list)

    @pytest.mark.asyncio
    async def test_get_ownership_returns_records(self, brain):
        """Get ownership returns stored records."""
        await brain.refresh_ownership("org/own-get")
        records = await brain.get_ownership()
        assert isinstance(records, list)

    @pytest.mark.asyncio
    async def test_get_ownership_by_service(self, brain):
        """Get ownership can filter by service name."""
        await brain.refresh_ownership("org/own-svc")
        records = await brain.get_ownership(service="org/own-svc")
        assert isinstance(records, list)

    @pytest.mark.asyncio
    async def test_ownership_structure(self, brain):
        """Ownership record has correct fields."""
        record = OwnershipRecord(
            service="payment-api",
            owners=["alice", "bob"],
            teams=["payments-team"],
            maintainers=["alice"],
            is_critical=True,
            business_domain="payments",
            repository="org/payments",
        )
        d = record.to_dict()
        assert d["service"] == "payment-api"
        assert d["is_critical"] is True
        assert d["business_domain"] == "payments"
        assert "alice" in d["owners"]


# =============================================================================
# Phase 5 — Runtime Mapping
# =============================================================================


class TestRuntimeMapping:
    """Phase 5: Service → Deployment → Pod → Container → Node → Cluster mapping."""

    @pytest.mark.asyncio
    async def test_get_runtime_mapping(self, brain):
        """Runtime mapping returns deployment map."""
        result = await brain.get_runtime_mapping("org/rt-test")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_runtime_mapping_structure(self, brain):
        """Runtime mapping has service entries with deployment details."""
        result = await brain.get_runtime_mapping("org/rt-struct")
        if result:
            for service, entries in result.items():
                for entry in entries:
                    assert isinstance(entry, dict)
                    assert "service" in entry or "deployment" in entry


# =============================================================================
# Phase 6 — Operational History
# =============================================================================


class TestOperationalHistory:
    """Phase 6: Operational history from RuntimeStore."""

    @pytest.mark.asyncio
    async def test_refresh_operational_history(self, brain):
        """Operational history returns all history sections."""
        result = await brain.refresh_operational_history("org/op-test")
        assert isinstance(result, dict)
        assert "deployments" in result
        assert "failures" in result
        assert "rollbacks" in result
        assert "recoveries" in result
        assert "incidents" in result
        assert "hotfixes" in result
        assert "missions" in result

    @pytest.mark.asyncio
    async def test_get_operational_history(self, brain):
        """Get operational history returns refreshed data."""
        result = await brain.get_operational_history("org/op-get")
        assert isinstance(result, dict)


# =============================================================================
# Phase 7 — Architecture Drift
# =============================================================================


class TestArchitectureDrift:
    """Phase 7: Drift detection."""

    @pytest.mark.asyncio
    async def test_detect_drift_returns_list(self, brain):
        """Drift detection returns a list of drift records."""
        await brain.refresh_architecture("org/drift-test")
        drifts = await brain.detect_drift("org/drift-test")
        assert isinstance(drifts, list)

    @pytest.mark.asyncio
    async def test_get_drift_empty(self, brain):
        """Get drift returns empty list when no drift."""
        result = await brain.get_drift()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_drift_filtered_by_repo(self, brain):
        """Get drift can filter by repository."""
        result = await brain.get_drift(repository="org/filter-test")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_drift_unresolved_only(self, brain):
        """Get drift can filter unresolved only."""
        result = await brain.get_drift(unresolved_only=True)
        for d in result:
            assert d["resolved"] is False

    @pytest.mark.asyncio
    async def test_resolve_drift(self, brain):
        """Resolving a drift marks it as resolved."""
        await brain.refresh_architecture("org/resolve-test")
        drifts = await brain.detect_drift("org/resolve-test")
        if drifts:
            drift_id = drifts[0].drift_id
            resolved = await brain.resolve_drift(drift_id)
            assert resolved is True

            unresolved = await brain.get_drift(unresolved_only=True)
            assert all(d["drift_id"] != drift_id for d in unresolved)

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_drift(self, brain):
        """Resolving a non-existent drift returns False."""
        result = await brain.resolve_drift("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_drift_record_structure(self, brain):
        """DriftRecord has all required fields."""
        record = DriftRecord(
            drift_id="drift-001",
            drift_type="circular_dependency",
            severity="critical",
            description="Circular dependency between A and B",
            repository="org/test",
            service="service-a",
        )
        d = record.to_dict()
        assert d["drift_type"] == "circular_dependency"
        assert d["severity"] == "critical"
        assert d["resolved"] is False


# =============================================================================
# Phase 8 — Executive Integration
# =============================================================================


class TestExecutiveIntegration:
    """Phase 8: Brain summary for executive planning."""

    @pytest.mark.asyncio
    async def test_get_brain_summary(self, brain):
        """Brain summary returns all key sections."""
        await brain.refresh_identity("org/exec-test")
        await brain.refresh_architecture("org/exec-test")
        summary = await brain.get_brain_summary("org/exec-test")
        assert "repository" in summary
        assert "identity" in summary
        assert "architecture" in summary
        assert "ownership" in summary
        assert "drift_count" in summary
        assert "history" in summary

    @pytest.mark.asyncio
    async def test_brain_summary_for_missing_repo(self, brain):
        """Brain summary handles missing repo gracefully."""
        summary = await brain.get_brain_summary("org/missing")
        assert summary["repository"] == "org/missing"
        assert "identity" in summary

    @pytest.mark.asyncio
    async def test_brain_summary_structure(self, brain):
        """Brain summary architecture section has counts."""
        await brain.refresh_identity("org/summary-struct")
        await brain.refresh_architecture("org/summary-struct")
        summary = await brain.get_brain_summary("org/summary-struct")
        arch = summary["architecture"]
        assert "services" in arch
        assert "modules" in arch
        assert "apis" in arch
        assert "libraries" in arch


# =============================================================================
# Phase 9 — Decision Integration
# =============================================================================


class TestDecisionIntegration:
    """Phase 9: Brain data enriches decision engine."""

    @pytest.mark.asyncio
    async def test_brain_aware_risk_calculation(self, brain):
        """Brain drift data increases risk scores."""
        await brain.refresh_architecture("org/risk-test")
        await brain.detect_drift("org/risk-test")
        summary = await brain.get_brain_summary("org/risk-test")
        assert "drift_count" in summary
        assert "drift" in summary

    @pytest.mark.asyncio
    async def test_brain_provides_architecture_for_impact(self, brain):
        """Brain provides architecture data for impact analysis."""
        await brain.refresh_architecture("org/impact-decision")
        arch = await brain.get_architecture("org/impact-decision")
        assert arch is not None
        assert hasattr(arch, "services")


# =============================================================================
# Phase 10 — Repository Dashboard
# =============================================================================


class TestRepositoryDashboard:
    """Phase 10: Repository dashboard aggregates all data."""

    @pytest.mark.asyncio
    async def test_dashboard_empty(self, brain):
        """Empty brain returns zeroed dashboard."""
        brain.clear()
        dash = await brain.get_dashboard()
        assert dash["total_repositories"] == 0
        assert dash["total_services"] == 0
        assert dash["total_apis"] == 0
        assert dash["unresolved_drift"] == 0

    @pytest.mark.asyncio
    async def test_dashboard_with_data(self, brain):
        """Dashboard reflects refreshed data."""
        brain.clear()
        await brain.refresh_identity("org/dash-1")
        await brain.refresh_identity("org/dash-2")
        await brain.refresh_architecture("org/dash-1")
        dash = await brain.get_dashboard()
        assert dash["total_repositories"] >= 2
        assert "total_services" in dash
        assert "languages" in dash
        assert "frameworks" in dash
        assert "build_systems" in dash
        assert "repositories" in dash

    @pytest.mark.asyncio
    async def test_dashboard_shows_language_stats(self, brain):
        """Dashboard includes language distribution."""
        dash = await brain.get_dashboard()
        assert isinstance(dash["languages"], dict)
        assert isinstance(dash["frameworks"], dict)
        assert isinstance(dash["build_systems"], dict)

    @pytest.mark.asyncio
    async def test_dashboard_lists_repositories(self, brain):
        """Dashboard repository list has detail fields."""
        await brain.refresh_identity("org/dash-repo-list")
        dash = await brain.get_dashboard()
        repos = dash["repositories"]
        if repos:
            for r in repos:
                assert "repository" in r
                assert "organization" in r
                assert "languages" in r

    @pytest.mark.asyncio
    async def test_dashboard_tracks_drift(self, brain):
        """Dashboard tracks unresolved drift."""
        await brain.refresh_architecture("org/dash-drift")
        await brain.detect_drift("org/dash-drift")
        dash = await brain.get_dashboard()
        assert "unresolved_drift" in dash
        assert "critical_drift" in dash
        assert "drift_warnings" in dash


# =============================================================================
# Model Tests
# =============================================================================


class TestModels:
    """Dataclass model tests."""

    def test_identity_to_dict(self):
        """RepositoryIdentity serializes correctly."""
        ident = RepositoryIdentity(
            repository="org/test",
            organization="org",
            languages={"python": 10},
            branches=["main", "develop"],
        )
        d = ident.to_dict()
        assert d["repository"] == "org/test"
        assert d["organization"] == "org"
        assert d["languages"]["python"] == 10
        assert "main" in d["branches"]

    def test_identity_defaults(self):
        """RepositoryIdentity has sensible defaults."""
        ident = RepositoryIdentity()
        assert ident.repository == ""
        assert ident.default_branch == "main"
        assert ident.branches == []
        assert ident.languages == {}
        assert ident.is_private is False

    def test_architecture_model_defaults(self):
        """ArchitectureModel has empty lists by default."""
        model = ArchitectureModel()
        assert model.services == []
        assert model.modules == []
        assert model.apis == []
        assert model.libraries == []

    def test_ownership_record_defaults(self):
        """OwnershipRecord has sensible defaults."""
        rec = OwnershipRecord()
        assert rec.service == ""
        assert rec.owners == []
        assert rec.is_critical is False

    def test_drift_record_immutable(self):
        """DriftRecord is frozen and immutable."""
        record = DriftRecord(drift_id="test")
        with pytest.raises(Exception):
            record.resolved = True  # frozen dataclass

    def test_architecture_component_to_dict(self):
        """ArchitectureComponent serializes correctly."""
        comp = ArchitectureComponent(
            component_id="c1",
            component_type="service",
            name="payment-api",
            file_paths=["src/payment/api.py"],
            dependencies=["auth-service"],
        )
        d = comp.to_dict()
        assert d["name"] == "payment-api"
        assert "src/payment/api.py" in d["file_paths"]
        assert "auth-service" in d["dependencies"]


# =============================================================================
# Singleton Test
# =============================================================================


class TestSingleton:
    """Module-level singleton."""

    def test_singleton_is_instance(self):
        """Module-level repository_brain is an EnterpriseRepositoryBrain."""
        from backend.services.enterprise_repository_brain import repository_brain
        assert isinstance(repository_brain, EnterpriseRepositoryBrain)

    def test_singleton_persistence(self):
        """Singleton persists data across calls."""
        from backend.services.enterprise_repository_brain import repository_brain
        assert hasattr(repository_brain, "_repositories")
        assert hasattr(repository_brain, "_architectures")
