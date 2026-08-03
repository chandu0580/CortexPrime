"""
Phase 9 Validation — Enterprise Context Intelligence end-to-end tests.

Each scenario validates context-aware decision making by constructing
ContextSnapshot objects and verifying the Engineering Decision Engine
adjusts its behavior accordingly.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.services.engineering_decision_engine import (
    ApprovalCategory,
    ChangeCategory,
    ChangeReport,
    DeploymentStrategy,
    EngineeringDecisionEngine,
    ImpactGraph,
    RiskLevel,
)
from backend.services.enterprise_context_intelligence import (
    BusinessContext,
    ContextSnapshot,
    DependencyContext,
    EnterpriseContextIntelligence,
    HistoricalContext,
    OperationalContext,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_snapshot(
    overrides: dict | None = None,
    operational: dict | None = None,
    dependency: dict | None = None,
    historical: dict | None = None,
    business: dict | None = None,
) -> ContextSnapshot:
    """Build a ContextSnapshot with custom overrides for testing."""
    op = OperationalContext(**(operational or {}))
    dep = DependencyContext(**(dependency or {}))
    hist = HistoricalContext(**(historical or {}))
    biz_defaults = {
        "environment": "production",
        "maintenance_window": False,
        "deployment_freeze": False,
        "business_hours": True,
        "hotfix_mode": False,
        "time_of_day": "14:00 UTC",
        "day_of_week": "Monday",
        "on_call_team": "primary",
    }
    if business:
        biz_defaults.update(business)
    biz = BusinessContext(**biz_defaults)

    base = ContextSnapshot(
        execution_id="test-exec-1",
        repository="org/repo",
        branch="main",
        commit="abc123",
        environment="production",
        snapshot_timestamp=datetime.now(timezone.utc).isoformat(),
        operational=op,
        dependency=dep,
        historical=hist,
        business=biz,
        sources_used=["test"],
        **(overrides or {}),
    )
    return base


PAYLOAD_CSS = {
    "modified_files": ["frontend/styles/main.css"],
    "head_commit": {"modified": ["frontend/styles/main.css"]},
}

PAYLOAD_PAYMENT = {
    "modified_files": ["backend/services/payment/processor.py"],
    "head_commit": {"modified": ["backend/services/payment/processor.py"]},
}

PAYLOAD_INFRA = {
    "modified_files": ["terraform/aws/main.tf"],
    "head_commit": {"modified": ["terraform/aws/main.tf"]},
}


# ── Test: ContextSnapshot model ───────────────────────────────────────────────


class TestContextSnapshotModel:
    def test_snapshot_immutable(self):
        """ContextSnapshot must be immutable (frozen=True)."""
        snap = _make_snapshot()
        with pytest.raises(Exception):
            snap.repository = "other/repo"

    def test_snapshot_to_dict(self):
        """to_dict() returns a serializable dictionary."""
        snap = _make_snapshot()
        d = snap.to_dict()
        assert isinstance(d, dict)
        assert d["repository"] == "org/repo"
        assert d["environment"] == "production"
        assert d["sources_used"] == ["test"]
        assert "operational" in d
        assert "dependency" in d
        assert "historical" in d
        assert "business" in d

    def test_snapshot_operational_context(self):
        """Operational context is preserved in snapshot."""
        snap = _make_snapshot(operational={"active_alerts": [{"name": "HighCPU"}]})
        assert len(snap.operational.active_alerts) == 1
        assert snap.operational.active_alerts[0]["name"] == "HighCPU"

    def test_snapshot_business_context(self):
        """Business context is preserved."""
        snap = _make_snapshot(business={"deployment_freeze": True, "hotfix_mode": True})
        assert snap.business.deployment_freeze is True
        assert snap.business.hotfix_mode is True

    def test_snapshot_dependency_context(self):
        """Dependency context is preserved."""
        snap = _make_snapshot(dependency={
            "impacted_services": ["payment", "auth"],
            "shared_databases": ["postgres-primary"],
        })
        assert "payment" in snap.dependency.impacted_services
        assert "postgres-primary" in snap.dependency.shared_databases


# ── Test: Context Intelligence aggregation ────────────────────────────────────


class TestEnterpriseContextIntelligence:
    @pytest.mark.asyncio
    async def test_build_snapshot_basic(self):
        """Can build a basic snapshot even when services are unavailable."""
        ctx = EnterpriseContextIntelligence()
        snap = await ctx.build_snapshot(
            repository="org/repo",
            branch="main",
            environment="production",
            include_historical=False,
            include_operational=False,
            include_dependency=False,
        )
        assert snap.repository == "org/repo"
        assert snap.branch == "main"
        assert snap.environment == "production"
        assert isinstance(snap.snapshot_timestamp, str)
        assert len(snap.snapshot_timestamp) > 0

    @pytest.mark.asyncio
    async def test_build_snapshot_sources_tracked(self):
        """Sources used are tracked in the snapshot."""
        ctx = EnterpriseContextIntelligence()
        snap = await ctx.build_snapshot(
            include_historical=False,
            include_operational=False,
            include_dependency=False,
        )
        assert isinstance(snap.sources_used, list)
        assert "RuntimeStore" in snap.sources_used
        assert "CodeIntelligence" in snap.sources_used

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """All collector failures are caught and don't crash the snapshot."""
        ctx = EnterpriseContextIntelligence()
        snap = await ctx.build_snapshot(
            repository="nonexistent/repo",
            execution_id="nonexistent-id",
        )
        # Even with failures, we still get a valid snapshot
        assert snap is not None
        assert snap.repository == "nonexistent/repo"


# ── Test: Phase 7 — Decision Integration ──────────────────────────────────────


class TestDecisionIntegration:
    @pytest.fixture
    def engine(self):
        return EngineeringDecisionEngine()

    @pytest.mark.asyncio
    async def test_decision_without_context_still_works(self, engine):
        """Decision engine works without context (backward compatible)."""
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_CSS,
            repository="org/repo",
            branch="main",
            commit_sha="abc123",
            # Explicit empty dict (not None) — without this, analyze()
            # auto-builds a real repository brain for "org/repo", and that
            # generic identifier's on-disk history is polluted by 231
            # other test-file references across the suite, non-deterministically
            # adding risk factors this "without_context" test isn't
            # exercising on purpose.
            repository_brain={},
        )
        assert report is not None
        assert report.change_report.has_frontend_changes is True
        assert report.risk_assessment.level == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_decision_with_context_snapshot(self, engine):
        """Decision engine accepts optional context_snapshot."""
        snap = _make_snapshot()
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_CSS,
            repository="org/repo",
            branch="main",
            commit_sha="abc123",
            context_snapshot=snap,
        )
        assert report is not None
        assert report.change_report.has_frontend_changes is True

    @pytest.mark.asyncio
    async def test_context_built_automatically_when_missing(self, engine):
        """Context is auto-built if not provided."""
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_CSS,
            repository="org/repo",
        )
        assert report is not None


# ── Scenario 1: Healthy Production ────────────────────────────────────────────


class TestScenario1HealthyProduction:
    @pytest.mark.asyncio
    async def test_healthy_production_low_risk(self):
        """Healthy production + CSS change → LOW risk, rolling, no approval."""
        engine = EngineeringDecisionEngine()
        snap = _make_snapshot()
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_CSS,
            context_snapshot=snap,
        )

        assert report.risk_assessment.level == RiskLevel.LOW
        assert report.approval_requirements.approval_required is False
        assert report.deployment_strategy.strategy in (
            DeploymentStrategy.ROLLING, DeploymentStrategy.NO_DEPLOYMENT,
        )


# ── Scenario 2: Active Incident ───────────────────────────────────────────────


class TestScenario2ActiveIncident:
    @pytest.mark.asyncio
    async def test_active_incident_increases_risk(self):
        """Active incident + payment change → risk boosted by context."""
        engine = EngineeringDecisionEngine()
        snap = _make_snapshot(operational={
            "active_alerts": [{"name": "HighErrorRate", "state": "firing"}],
        })
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_PAYMENT,
            context_snapshot=snap,
        )

        # Risk should include alert factor
        factor_names = [f.get("factor", "") for f in report.risk_assessment.factors]
        has_alert_factor = any("active_alerts" in fn for fn in factor_names)
        assert has_alert_factor, f"Expected alert factor in {factor_names}"
        assert report.risk_assessment.score > 50
        assert report.approval_requirements.approval_required is True


# ── Scenario 3: Cluster Degradation ───────────────────────────────────────────


class TestScenario3ClusterDegradation:
    @pytest.mark.asyncio
    async def test_cluster_degradation_prefers_blue_green(self):
        """Degraded cluster → prefer Blue/Green for safety."""
        engine = EngineeringDecisionEngine()
        snap = _make_snapshot(operational={"runtime_health": "degraded"})
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_INFRA,
            context_snapshot=snap,
        )

        # Blue/Green should be preferred due to cluster degradation
        assert report.deployment_strategy.strategy == DeploymentStrategy.BLUE_GREEN


# ── Scenario 4: High Latency ──────────────────────────────────────────────────


class TestScenario4HighLatency:
    @pytest.mark.asyncio
    async def test_high_latency_context_preserved(self):
        """High latency context is preserved in the operational snapshot."""
        snap = _make_snapshot(operational={
            "latency": {"p99": 2500.0, "p95": 1500.0},
            "error_rate": {"api-gateway": 5.2},
        })
        assert snap.operational.latency["p99"] == 2500.0
        assert snap.operational.error_rate["api-gateway"] == 5.2


# ── Scenario 5: Existing Rollback ─────────────────────────────────────────────


class TestScenario5ExistingRollback:
    @pytest.mark.asyncio
    async def test_rollback_in_progress_blocks_deployment(self):
        """Ongoing rollback → no deployment."""
        engine = EngineeringDecisionEngine()
        snap = _make_snapshot(operational={
            "rollbacks": [{"id": "rb-1", "reason": "Failed deploy"}],
        })
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_PAYMENT,
            context_snapshot=snap,
        )

        # Should skip deployment due to ongoing rollback
        assert report.deployment_strategy.strategy == DeploymentStrategy.NO_DEPLOYMENT

# ── Scenario 6: Multiple Active Alerts ────────────────────────────────────────


class TestScenario6MultipleActiveAlerts:
    @pytest.mark.asyncio
    async def test_multiple_alerts_escalate_risk(self):
        """Multiple active alerts → risk score increases."""
        engine = EngineeringDecisionEngine()
        snap = _make_snapshot(operational={
            "active_alerts": [
                {"name": "HighCPU", "state": "firing"},
                {"name": "HighMemory", "state": "firing"},
                {"name": "PodCrashLoop", "state": "firing"},
            ],
        })
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_CSS,
            context_snapshot=snap,
        )

        # Risk should still be low (CSS change) but with alert adjustment
        assert report.risk_assessment.score > 0
        factor_names = [f.get("factor", "") for f in report.risk_assessment.factors]
        has_alert_factor = any("active_alerts" in fn for fn in factor_names)
        assert has_alert_factor


# ── Scenario 7: Deployment Freeze ─────────────────────────────────────────────


class TestScenario7DeploymentFreeze:
    @pytest.mark.asyncio
    async def test_deployment_freeze_blocks_deploy(self):
        """Deployment freeze → no deployment."""
        engine = EngineeringDecisionEngine()
        snap = _make_snapshot(business={"deployment_freeze": True})
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_CSS,
            context_snapshot=snap,
        )

        assert report.deployment_strategy.strategy == DeploymentStrategy.NO_DEPLOYMENT

    @pytest.mark.asyncio
    async def test_deployment_freeze_requires_platform_approval(self):
        """Deployment freeze + change → platform approval required."""
        engine = EngineeringDecisionEngine()
        snap = _make_snapshot(business={"deployment_freeze": True})
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_PAYMENT,
            context_snapshot=snap,
        )

        assert report.approval_requirements.approval_required is True
        assert ApprovalCategory.PLATFORM in report.approval_requirements.required_approvers


# ── Scenario 8: Cross-Service Dependency Impact ───────────────────────────────


class TestScenario8CrossServiceDependency:
    @pytest.mark.asyncio
    async def test_dependency_context_impacts_decision(self):
        """Dependency context shows cross-service impact."""
        snap = _make_snapshot(dependency={
            "impacted_services": ["payment", "auth", "user-service"],
            "upstream_services": ["api-gateway"],
            "downstream_services": ["notification-service"],
            "shared_databases": ["postgres-primary"],
            "critical_paths": ["api-gateway → payment → notification"],
        })
        assert len(snap.dependency.impacted_services) == 3
        assert "postgres-primary" in snap.dependency.shared_databases
        assert "api-gateway" in snap.dependency.upstream_services


# ── Scenario 9: Full Integration ──────────────────────────────────────────────


class TestScenario9FullIntegration:
    @pytest.mark.asyncio
    async def test_full_context_decision_pipeline(self):
        """Full context snapshot flows through all 11 decision phases."""
        engine = EngineeringDecisionEngine()
        snap = _make_snapshot(
            operational={
                "active_alerts": [{"name": "HighErrorRate", "state": "firing"}],
                "runtime_health": "healthy",
            },
            business={
                "environment": "production",
                "deployment_freeze": False,
                "business_hours": True,
            },
            dependency={
                "impacted_services": ["payment", "auth"],
                "shared_databases": ["postgres-primary"],
            },
        )
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_PAYMENT,
            context_snapshot=snap,
        )

        # Phase 1: Change detection
        assert report.change_report.has_backend_changes is True
        assert len(report.change_report.changed_files) > 0

        # Phase 2: Impact analysis
        assert report.impact_graph is not None

        # Phase 3: Risk assessment (with context adjustments)
        assert report.risk_assessment.score > 0
        assert len(report.risk_assessment.factors) > 0
        factor_names = [f.get("factor", "") for f in report.risk_assessment.factors]
        has_alert = any("active_alerts" in fn for fn in factor_names)
        assert has_alert, f"Expected context factor in {factor_names}"

        # Phase 4: Execution plan
        assert len(report.execution_plan.required_stages) > 0
        assert report.execution_plan.reasoning != ""

        # Phase 5: Approval requirements
        assert report.approval_requirements.approval_required is True

        # Phase 6: Deployment strategy
        assert report.deployment_strategy.strategy is not None
        assert report.deployment_strategy.confidence > 0

        # Phase 10: Explainability includes context evidence
        assert report.explanation.why != ""
        evidence_steps = [e.get("step", "") for e in report.explanation.evidence_chain]
        assert "enterprise_context" in evidence_steps, f"Expected context evidence in {evidence_steps}"

        # Phase 11: Executive summary
        assert report.executive_summary.risk_score > 0
        assert report.executive_summary.key_decision != ""
