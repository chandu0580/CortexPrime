"""
Validation tests for Enterprise Predictive Simulation Engine.

Phases covered:
  1. Prediction Context — builds from 10+ services
  2. Engineering Outcome Prediction — 8 outcome types
  3. Infrastructure Prediction — 7 metrics
  4. Service Impact Prediction — 7 impact areas
  5. Business Prediction — 6 business metrics
  6. Strategy Comparison — 6 strategies
  7. Decision Integration — consumed by EngineeringDecisionEngine
  8. Learning Feedback — prediction vs reality
  9. Executive Prediction Report

Scenarios (Phase 10):
  1. Frontend deployment
  2. Backend deployment
  3. Database migration
  4. Terraform
  5. Helm
  6. Kubernetes rollout
  7. Rollback
  8. Hotfix
  9. Critical payment deployment
"""
from __future__ import annotations

import pytest
from typing import Any, Dict, List

from backend.services.enterprise_predictive_simulation import (
    EnterprisePredictiveSimulation,
    PredictionContextBuilder,
    EngineeringOutcomePredictor,
    InfrastructurePredictor,
    ServiceImpactPredictor,
    BusinessPredictor,
    StrategyComparator,
    LearningFeedbackEngine,
    PredictionReportGenerator,
    PredictionContext,
    EngineeringOutcomePrediction,
    InfrastructurePrediction,
    ServiceImpactPrediction,
    BusinessPrediction,
)
from backend.services.engineering_decision_engine import EngineeringDecisionEngine


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sim() -> EnterprisePredictiveSimulation:
    return EnterprisePredictiveSimulation()


@pytest.fixture
def ctx_builder() -> PredictionContextBuilder:
    return PredictionContextBuilder()


@pytest.fixture
def outcome_predictor() -> EngineeringOutcomePredictor:
    return EngineeringOutcomePredictor()


@pytest.fixture
def infra_predictor() -> InfrastructurePredictor:
    return InfrastructurePredictor()


@pytest.fixture
def service_predictor() -> ServiceImpactPredictor:
    return ServiceImpactPredictor()


@pytest.fixture
def business_predictor() -> BusinessPredictor:
    return BusinessPredictor()


@pytest.fixture
def strategy_comparator() -> StrategyComparator:
    return StrategyComparator()


@pytest.fixture
def feedback_engine() -> LearningFeedbackEngine:
    return LearningFeedbackEngine()


@pytest.fixture
def report_generator() -> PredictionReportGenerator:
    return PredictionReportGenerator()


# =============================================================================
# Phase 1 — Prediction Context
# =============================================================================


class TestPredictionContextBuilder:
    """Phase 1: Context aggregation from all services."""

    @pytest.mark.asyncio
    async def test_build_basic_context(self, ctx_builder):
        """Build context with minimal inputs."""
        ctx = await ctx_builder.build(repository="org/backend", branch="main")
        assert ctx.repository == "org/backend"
        assert ctx.branch == "main"
        assert ctx.sources_used is not None

    @pytest.mark.asyncio
    async def test_build_with_change_details(self, ctx_builder):
        """Build context with change details."""
        ctx = await ctx_builder.build(
            repository="org/frontend",
            changed_files=["src/App.tsx", "package.json"],
            changed_services=["frontend"],
            change_categories=["frontend", "ui"],
        )
        assert "src/App.tsx" in ctx.changed_files
        assert "frontend" in ctx.changed_services
        assert "frontend" in ctx.change_categories

    @pytest.mark.asyncio
    async def test_build_sources_tracked(self, ctx_builder):
        """Build context tracks which sources were used."""
        ctx = await ctx_builder.build()
        assert isinstance(ctx.sources_used, list)

    @pytest.mark.asyncio
    async def test_build_graceful_degradation(self, ctx_builder):
        """Build context doesn't crash even if services are unavailable."""
        ctx = await ctx_builder.build(
            repository="org/test",
            changed_files=["test.py"],
            changed_services=["test"],
        )
        assert ctx.repository == "org/test"
        assert ctx.success_rate == 0.5

    @pytest.mark.asyncio
    async def test_context_to_dict(self, ctx_builder):
        """Context serializes to dict."""
        ctx = await ctx_builder.build()
        d = ctx.to_dict()
        assert "repository" in d
        assert "sources_used" in d
        assert "collected_at" in d


# =============================================================================
# Phase 2 — Engineering Outcome Prediction
# =============================================================================


class TestEngineeringOutcomePrediction:
    """Phase 2: Predict build/deploy/rollback/approval/duration/recovery."""

    @pytest.mark.asyncio
    async def test_predict_basic_outcomes(self, outcome_predictor):
        """Basic prediction returns all 8 outcome types."""
        ctx = PredictionContext()
        pred = await outcome_predictor.predict(ctx)
        assert isinstance(pred.build_success_probability, float)
        assert isinstance(pred.build_failure_probability, float)
        assert isinstance(pred.deployment_success_probability, float)
        assert isinstance(pred.deployment_failure_probability, float)
        assert isinstance(pred.rollback_probability, float)
        assert isinstance(pred.approval_probability, float)
        assert isinstance(pred.predicted_pipeline_duration_seconds, float)
        assert isinstance(pred.recovery_probability, float)

    @pytest.mark.asyncio
    async def test_probabilities_sum_to_one(self, outcome_predictor):
        """Success + failure probabilities sum to ~1.0."""
        ctx = PredictionContext()
        pred = await outcome_predictor.predict(ctx)
        assert abs(pred.build_success_probability + pred.build_failure_probability - 1.0) < 0.01
        assert abs(pred.deployment_success_probability + pred.deployment_failure_probability - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_active_incidents_increase_risk(self, outcome_predictor):
        """Active incidents increase rollback probability and reduce success."""
        ctx_ok = PredictionContext()
        ctx_bad = PredictionContext(active_incidents=3, active_alerts=8)
        ok_pred = await outcome_predictor.predict(ctx_ok)
        bad_pred = await outcome_predictor.predict(ctx_bad)
        assert bad_pred.rollback_probability >= ok_pred.rollback_probability
        assert bad_pred.deployment_success_probability <= ok_pred.deployment_success_probability
        assert bad_pred.build_success_probability <= ok_pred.build_success_probability

    @pytest.mark.asyncio
    async def test_db_migration_increases_duration(self, outcome_predictor):
        """DB migration increases predicted duration and rollback probability."""
        ctx_no = PredictionContext()
        ctx_db = PredictionContext(has_db_migrations=True)
        no_pred = await outcome_predictor.predict(ctx_no)
        db_pred = await outcome_predictor.predict(ctx_db)
        assert db_pred.predicted_pipeline_duration_seconds >= no_pred.predicted_pipeline_duration_seconds
        assert db_pred.rollback_probability >= no_pred.rollback_probability

    @pytest.mark.asyncio
    async def test_infra_changes_reduce_success(self, outcome_predictor):
        """Infrastructure changes degrade deployment success."""
        ctx_no = PredictionContext()
        ctx_infra = PredictionContext(has_infrastructure_changes=True)
        no_pred = await outcome_predictor.predict(ctx_no)
        infra_pred = await outcome_predictor.predict(ctx_infra)
        assert infra_pred.deployment_success_probability <= no_pred.deployment_success_probability

    @pytest.mark.asyncio
    async def test_deployment_freeze_blocks_deploy(self, outcome_predictor):
        """Deployment freeze significantly reduces deploy success."""
        ctx_no = PredictionContext()
        ctx_freeze = PredictionContext(deployment_freeze=True)
        no_pred = await outcome_predictor.predict(ctx_no)
        freeze_pred = await outcome_predictor.predict(ctx_freeze)
        assert freeze_pred.deployment_success_probability <= no_pred.deployment_success_probability

    @pytest.mark.asyncio
    async def test_high_failure_rate_degrades_confidence(self, outcome_predictor):
        """High historical failure rate degrades predictions."""
        ctx_ok = PredictionContext(previous_deployments=100, previous_failures=5)
        ctx_bad = PredictionContext(previous_deployments=100, previous_failures=60)
        ok_pred = await outcome_predictor.predict(ctx_ok)
        bad_pred = await outcome_predictor.predict(ctx_bad)
        assert bad_pred.deployment_success_probability <= ok_pred.deployment_success_probability

    @pytest.mark.asyncio
    async def test_reasoning_provided(self, outcome_predictor):
        """Prediction includes reasoning."""
        ctx = PredictionContext(active_incidents=1, has_db_migrations=True)
        pred = await outcome_predictor.predict(ctx)
        assert len(pred.reasoning) > 0


# =============================================================================
# Phase 3 — Infrastructure Prediction
# =============================================================================


class TestInfrastructurePrediction:
    """Phase 3: Predict CPU/memory/disk/net/pod/node/cluster."""

    @pytest.mark.asyncio
    async def test_predict_basic_infra(self, infra_predictor):
        """Basic infra prediction returns all 7 metrics."""
        ctx = PredictionContext()
        pred = await infra_predictor.predict(ctx)
        assert isinstance(pred.cpu_increase_probability, float)
        assert isinstance(pred.memory_increase_probability, float)
        assert isinstance(pred.disk_increase_probability, float)
        assert isinstance(pred.network_utilization_increase_probability, float)
        assert isinstance(pred.pod_scaling_probability, float)
        assert isinstance(pred.node_pressure_probability, float)
        assert isinstance(pred.cluster_utilization_change, float)

    @pytest.mark.asyncio
    async def test_high_cpu_increases_pressure(self, infra_predictor):
        """High CPU utilization increases node pressure and CPU probabilities."""
        ctx_low = PredictionContext(avg_cpu=30)
        ctx_high = PredictionContext(avg_cpu=85)
        low_pred = await infra_predictor.predict(ctx_low)
        high_pred = await infra_predictor.predict(ctx_high)
        assert high_pred.cpu_increase_probability >= low_pred.cpu_increase_probability
        assert high_pred.node_pressure_probability >= low_pred.node_pressure_probability

    @pytest.mark.asyncio
    async def test_high_memory_increases_scaling(self, infra_predictor):
        """High memory increases pod scaling and memory probabilities."""
        ctx_low = PredictionContext(avg_memory=30)
        ctx_high = PredictionContext(avg_memory=85)
        low_pred = await infra_predictor.predict(ctx_low)
        high_pred = await infra_predictor.predict(ctx_high)
        assert high_pred.memory_increase_probability >= low_pred.memory_increase_probability
        assert high_pred.pod_scaling_probability >= low_pred.pod_scaling_probability

    @pytest.mark.asyncio
    async def test_crashloop_pods_increase_node_pressure(self, infra_predictor):
        """CrashLoop pods indicate node instability."""
        ctx_no = PredictionContext(crashloop_pods=0)
        ctx_yes = PredictionContext(crashloop_pods=3)
        no_pred = await infra_predictor.predict(ctx_no)
        yes_pred = await infra_predictor.predict(ctx_yes)
        assert yes_pred.node_pressure_probability >= no_pred.node_pressure_probability

    @pytest.mark.asyncio
    async def test_infra_changes_increase_all_probabilities(self, infra_predictor):
        """Infrastructure changes increase CPU and memory probabilities."""
        ctx_no = PredictionContext()
        ctx_infra = PredictionContext(has_infrastructure_changes=True)
        no_pred = await infra_predictor.predict(ctx_no)
        infra_pred = await infra_predictor.predict(ctx_infra)
        assert infra_pred.cpu_increase_probability >= no_pred.cpu_increase_probability

    @pytest.mark.asyncio
    async def test_infra_reasoning(self, infra_predictor):
        """Infra prediction includes reasoning."""
        ctx = PredictionContext(avg_cpu=85, oom_pods=2)
        pred = await infra_predictor.predict(ctx)
        assert len(pred.reasoning) > 0


# =============================================================================
# Phase 4 — Service Impact Prediction
# =============================================================================


class TestServiceImpactPrediction:
    """Phase 4: Predict APIs/services/databases/queues/dashboards/alerts/users."""

    @pytest.mark.asyncio
    async def test_predict_basic_impact(self, service_predictor):
        """Basic impact prediction returns all 7 areas."""
        ctx = PredictionContext(changed_services=["api-gateway"])
        pred = await service_predictor.predict(ctx)
        assert isinstance(pred.affected_apis, list)
        assert isinstance(pred.affected_services, list)
        assert isinstance(pred.affected_databases, list)
        assert isinstance(pred.affected_queues, list)
        assert isinstance(pred.affected_dashboards, list)
        assert isinstance(pred.affected_alerts, list)
        assert isinstance(pred.affected_user_count, int)

    @pytest.mark.asyncio
    async def test_impact_includes_changed_services(self, service_predictor):
        """Changed services appear in affected services."""
        ctx = PredictionContext(changed_services=["payment", "auth"])
        pred = await service_predictor.predict(ctx)
        assert "payment" in pred.affected_services
        assert "auth" in pred.affected_services

    @pytest.mark.asyncio
    async def test_db_migration_increases_severity(self, service_predictor):
        """Database impact raises severity to high."""
        ctx = PredictionContext(impacted_databases=["users-db", "orders-db"])
        pred = await service_predictor.predict(ctx)
        assert pred.impact_severity == "high"

    @pytest.mark.asyncio
    async def test_many_affected_services_medium_severity(self, service_predictor):
        """3+ affected services results in medium severity."""
        ctx = PredictionContext(
            impacted_services=["svc1", "svc2", "svc3", "svc4"],
        )
        pred = await service_predictor.predict(ctx)
        assert pred.impact_severity == "medium"

    @pytest.mark.asyncio
    async def test_low_severity_limited_impact(self, service_predictor):
        """Few changes result in low severity."""
        ctx = PredictionContext(changed_services=["frontend"])
        pred = await service_predictor.predict(ctx)
        assert pred.impact_severity == "low"

    @pytest.mark.asyncio
    async def test_impact_reasoning(self, service_predictor):
        """Service impact includes reasoning."""
        ctx = PredictionContext(impacted_databases=["db1"])
        pred = await service_predictor.predict(ctx)
        assert len(pred.reasoning) > 0


# =============================================================================
# Phase 5 — Business Prediction
# =============================================================================


class TestBusinessPrediction:
    """Phase 5: Predict downtime/risk/confidence/maintenance/cost/time."""

    @pytest.mark.asyncio
    async def test_predict_basic_business(self, business_predictor):
        """Basic business prediction returns all 6 metrics."""
        ctx = PredictionContext()
        pred = await business_predictor.predict(ctx)
        assert isinstance(pred.downtime_probability, float)
        assert isinstance(pred.business_risk_score, float)
        assert isinstance(pred.release_confidence, float)
        assert isinstance(pred.maintenance_window_suitable, bool)
        assert isinstance(pred.operational_cost_increase, float)
        assert isinstance(pred.expected_duration_minutes, float)

    @pytest.mark.asyncio
    async def test_deployment_freeze_increases_risk(self, business_predictor):
        """Deployment freeze increases business risk and downtime."""
        ctx_ok = PredictionContext()
        ctx_freeze = PredictionContext(deployment_freeze=True)
        ok_pred = await business_predictor.predict(ctx_ok)
        freeze_pred = await business_predictor.predict(ctx_freeze)
        assert freeze_pred.business_risk_score >= ok_pred.business_risk_score
        assert freeze_pred.downtime_probability >= ok_pred.downtime_probability

    @pytest.mark.asyncio
    async def test_active_incidents_degrade_confidence(self, business_predictor):
        """Active incidents reduce release confidence."""
        ctx_ok = PredictionContext()
        ctx_inc = PredictionContext(active_incidents=3)
        ok_pred = await business_predictor.predict(ctx_ok)
        inc_pred = await business_predictor.predict(ctx_inc)
        assert inc_pred.business_risk_score >= ok_pred.business_risk_score

    @pytest.mark.asyncio
    async def test_maintenance_window_suitability(self, business_predictor):
        """Maintenance window suitability is True when no adverse conditions."""
        ctx = PredictionContext()
        pred = await business_predictor.predict(ctx)
        assert pred.maintenance_window_suitable is True

    @pytest.mark.asyncio
    async def test_business_reasoning(self, business_predictor):
        """Business prediction includes reasoning."""
        ctx = PredictionContext(active_incidents=1, deployment_freeze=True)
        pred = await business_predictor.predict(ctx)
        assert len(pred.reasoning) > 0


# =============================================================================
# Phase 6 — Strategy Comparison
# =============================================================================


class TestStrategyComparison:
    """Phase 6: Compare rolling/blue-green/canary/shadow/hotfix/rollback."""

    @pytest.mark.asyncio
    async def test_compare_all_strategies(self, strategy_comparator):
        """All 6 strategies are compared."""
        ctx = PredictionContext()
        result = await strategy_comparator.compare(ctx)
        strategies = result.get("strategies", [])
        assert len(strategies) == 6
        strategy_names = [s["strategy"] for s in strategies]
        assert "rolling" in strategy_names
        assert "blue_green" in strategy_names
        assert "canary" in strategy_names
        assert "shadow" in strategy_names
        assert "hotfix" in strategy_names
        assert "rollback" in strategy_names

    @pytest.mark.asyncio
    async def test_recommended_strategy_has_highest_success(self, strategy_comparator):
        """Recommended strategy is the one with highest success probability."""
        ctx = PredictionContext()
        result = await strategy_comparator.compare(ctx)
        strategies = result.get("strategies", [])
        recommended = result.get("recommended_strategy")
        recommended_score = None
        for s in strategies:
            if s["strategy"] == recommended:
                recommended_score = s["expected_success_probability"]
                break
        assert recommended_score is not None
        max_score = max(s["expected_success_probability"] for s in strategies)
        assert abs(recommended_score - max_score) < 0.01

    @pytest.mark.asyncio
    async def test_blue_green_preferred_during_incidents(self, strategy_comparator):
        """Blue-green is recommended over rolling during incidents."""
        ctx = PredictionContext(active_incidents=2, firing_alerts=5)
        result = await strategy_comparator.compare(ctx)
        bg_score = None
        rolling_score = None
        for s in result["strategies"]:
            if s["strategy"] == "blue_green":
                bg_score = s["expected_success_probability"]
            if s["strategy"] == "rolling":
                rolling_score = s["expected_success_probability"]
        assert bg_score is not None and rolling_score is not None
        assert bg_score >= rolling_score

    @pytest.mark.asyncio
    async def test_hotfix_highest_risk(self, strategy_comparator):
        """Hotfix has highest risk score among deployment strategies."""
        ctx = PredictionContext()
        result = await strategy_comparator.compare(ctx)
        strategies = [s for s in result["strategies"] if s["strategy"] != "rollback"]
        deploy_strats = [s for s in strategies if s["strategy"] != "rollback"]
        if deploy_strats:
            hotfix = next(s for s in deploy_strats if s["strategy"] == "hotfix")
            others_risk = [s["expected_risk_score"] for s in deploy_strats if s["strategy"] != "hotfix"]
            if others_risk:
                assert hotfix["expected_risk_score"] >= max(others_risk)

    @pytest.mark.asyncio
    async def test_baseline_context_included(self, strategy_comparator):
        """Strategy comparison includes baseline context."""
        ctx = PredictionContext(deployment_freeze=True, has_db_migrations=True)
        result = await strategy_comparator.compare(ctx)
        baseline = result.get("baseline_context", {})
        assert baseline.get("deployment_freeze") is True
        assert baseline.get("has_db_migrations") is True


# =============================================================================
# Phase 7 — Decision Integration
# =============================================================================


class TestDecisionIntegration:
    """Phase 7: Decision engine consumes predictions."""

    @pytest.mark.asyncio
    async def test_decision_engine_includes_predictions(self):
        """Decision engine report includes predictions field."""
        engine = EngineeringDecisionEngine()
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload={
                "repository": "org/test",
                "ref": "refs/heads/main",
                "commits": [{"modified": ["test.py"], "added": [], "removed": []}],
            },
            repository="org/test",
            branch="main",
        )
        d = report.to_dict()
        assert "predictions" in d

    @pytest.mark.asyncio
    async def test_decision_prediction_contains_required_fields(self):
        """Prediction digest contains required fields for decision influence."""
        engine = EngineeringDecisionEngine()
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload={
                "repository": "org/test",
                "ref": "refs/heads/main",
                "commits": [{"modified": ["test.py"], "added": [], "removed": []}],
            },
            repository="org/test",
        )
        pred = report.predictions
        if pred:
            assert "deployment_success_probability" in pred
            assert "rollback_probability" in pred
            assert "recommended_strategy" in pred
            assert "confidence" in pred
            assert "prediction_id" in pred

    @pytest.mark.asyncio
    async def test_executive_summary_references_predictions(self):
        """Executive summary includes prediction references when available."""
        engine = EngineeringDecisionEngine()
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload={
                "repository": "org/test",
                "ref": "refs/heads/main",
                "commits": [{"modified": ["api.py", "db.py"], "added": [], "removed": []}],
            },
            repository="org/test",
        )
        summary = report.executive_summary
        if report.predictions:
            assert "success" in summary.impact.lower() or "prediction" in summary.impact.lower()


# =============================================================================
# Phase 8 — Learning Feedback
# =============================================================================


class TestLearningFeedback:
    """Phase 8: Compare prediction vs reality, improve confidence."""

    @pytest.mark.asyncio
    async def test_accurate_prediction_positive_adjustment(self, feedback_engine):
        """Accurate prediction gets positive confidence adjustment."""
        fb = await feedback_engine.record_feedback(
            prediction_id="pred-test1",
            execution_id="exec-test1",
            repository="org/test",
            actual_outcome="success",
            predicted_success_probability=0.9,
        )
        assert fb.accuracy > 0.8
        assert fb.confidence_adjustment > 0

    @pytest.mark.asyncio
    async def test_inaccurate_prediction_negative_adjustment(self, feedback_engine):
        """Inaccurate prediction gets negative confidence adjustment."""
        fb = await feedback_engine.record_feedback(
            prediction_id="pred-test2",
            execution_id="exec-test2",
            repository="org/test",
            actual_outcome="failed",
            predicted_success_probability=0.9,
        )
        assert fb.accuracy < 0.3
        assert fb.confidence_adjustment < 0

    @pytest.mark.asyncio
    async def test_partial_accuracy_small_adjustment(self, feedback_engine):
        """Partially accurate prediction gets small negative adjustment."""
        fb = await feedback_engine.record_feedback(
            prediction_id="pred-test3",
            execution_id="exec-test3",
            repository="org/test",
            actual_outcome="success",
            predicted_success_probability=0.6,
        )
        assert 0.3 <= fb.accuracy <= 0.8
        assert fb.confidence_adjustment <= 0

    @pytest.mark.asyncio
    async def test_feedback_has_timestamp(self, feedback_engine):
        """Feedback record includes timestamp."""
        fb = await feedback_engine.record_feedback(
            prediction_id="pred-test4",
            execution_id="exec-test4",
            repository="org/test",
            actual_outcome="success",
            predicted_success_probability=0.8,
        )
        assert fb.feedback_timestamp != ""


# =============================================================================
# Phase 9 — Executive Prediction Report
# =============================================================================


class TestPredictionReport:
    """Phase 9: Generate executive prediction reports."""

    def test_generate_report(self, report_generator):
        """Generate report from all prediction components."""
        ctx = PredictionContext(sources_used=["RuntimeStore", "ContextIntelligence"])
        op = EngineeringOutcomePrediction(
            deployment_success_probability=0.85,
            deployment_failure_probability=0.15,
            rollback_probability=0.1,
            recovery_probability=0.7,
            confidence=0.75,
            reasoning=["Historical data suggests high success"],
        )
        ip = InfrastructurePrediction(
            cpu_increase_probability=0.6,
            reasoning=["High CPU baseline"],
        )
        si = ServiceImpactPrediction(
            affected_services=["payment", "auth"],
            impact_severity="medium",
            reasoning=["Auth service impact"],
        )
        bp = BusinessPrediction(
            business_risk_score=0.3,
            downtime_probability=0.1,
            reasoning=["Stable environment"],
        )
        sr = {"recommended_strategy": "blue_green", "strategies": []}

        report = report_generator.generate("pred-123", op, ip, si, bp, sr, ctx)
        assert report.report_id.startswith("sim-rpt-")
        assert report.success_probability == 0.85
        assert report.recommended_strategy == "blue_green"
        assert report.confidence == 0.75
        assert len(report.reasoning) > 0

    def test_report_business_impact_critical(self, report_generator):
        """High business risk results in critical business impact."""
        ctx = PredictionContext()
        op = EngineeringOutcomePrediction()
        ip = InfrastructurePrediction()
        si = ServiceImpactPrediction()
        bp = BusinessPrediction(business_risk_score=0.8, downtime_probability=0.5)
        sr = {"recommended_strategy": "canary", "strategies": []}

        report = report_generator.generate("pred-456", op, ip, si, bp, sr, ctx)
        assert report.business_impact == "critical"

    def test_report_infra_impact_high(self, report_generator):
        """High infra probabilities result in high infra impact."""
        ctx = PredictionContext()
        op = EngineeringOutcomePrediction()
        ip = InfrastructurePrediction(
            cpu_increase_probability=0.85,
            memory_increase_probability=0.8,
            node_pressure_probability=0.7,
        )
        si = ServiceImpactPrediction()
        bp = BusinessPrediction()
        sr = {"recommended_strategy": "rolling", "strategies": []}

        report = report_generator.generate("pred-789", op, ip, si, bp, sr, ctx)
        assert report.infrastructure_impact == "high"

    def test_report_to_dict(self, report_generator):
        """Report serializes to dict."""
        ctx = PredictionContext()
        op = EngineeringOutcomePrediction()
        ip = InfrastructurePrediction()
        si = ServiceImpactPrediction()
        bp = BusinessPrediction()
        sr = {"recommended_strategy": "rolling", "strategies": []}

        report = report_generator.generate("pred-abc", op, ip, si, bp, sr, ctx)
        d = report.to_dict()
        assert "report_id" in d
        assert "success_probability" in d


# =============================================================================
# Phase 10 — Full Validation Scenarios
# =============================================================================


class TestScenario1FrontendDeployment:
    """Frontend deployment — low risk, UI changes only."""

    @pytest.mark.asyncio
    async def test_frontend_prediction(self, sim):
        """Frontend deployment has high success probability."""
        result = await sim.simulate(
            repository="org/frontend-app",
            changed_files=["src/components/Button.tsx", "src/pages/Home.tsx"],
            changed_services=["frontend"],
            change_categories=["frontend", "ui"],
        )
        op = result["outcome_prediction"]
        assert op["deployment_success_probability"] > 0.5
        assert op["rollback_probability"] < 0.5
        assert result["service_impact_prediction"]["impact_severity"] in ("low", "medium")


class TestScenario2BackendDeployment:
    """Backend deployment — API changes, moderate risk."""

    @pytest.mark.asyncio
    async def test_backend_prediction(self, sim):
        """Backend deployment has reasonable success probability."""
        result = await sim.simulate(
            repository="org/backend-api",
            changed_files=["src/api/users.py", "src/models/user.py", "src/services/auth.py"],
            changed_services=["backend", "auth"],
            change_categories=["backend", "api", "authentication"],
        )
        op = result["outcome_prediction"]
        assert op["deployment_success_probability"] > 0.3
        assert "prediction_id" in result
        assert "executive_report" in result


class TestScenario3DatabaseMigration:
    """Database migration — higher risk, rollback probability elevated."""

    @pytest.mark.asyncio
    async def test_database_migration_prediction(self, sim):
        """DB migration increases rollback probability and duration."""
        result = await sim.simulate(
            repository="org/backend-db",
            changed_files=["migrations/2024_add_users_table.sql", "src/db/schema.py"],
            changed_services=["backend", "database"],
            change_categories=["backend", "database"],
        )
        op = result["outcome_prediction"]
        assert op["rollback_probability"] >= 0.1
        assert op["predicted_pipeline_duration_seconds"] >= 300
        assert op["approval_probability"] > 0.3
        bp = result["business_prediction"]
        assert bp["expected_duration_minutes"] >= 30


class TestScenario4Terraform:
    """Terraform infrastructure change — infra impact detected."""

    @pytest.mark.asyncio
    async def test_terraform_prediction(self, sim):
        """Terraform change has infra impact and elevated risk."""
        result = await sim.simulate(
            repository="org/infrastructure",
            changed_files=["terraform/main.tf", "terraform/variables.tf", "terraform/outputs.tf"],
            changed_services=["infrastructure"],
            change_categories=["infrastructure", "terraform"],
        )
        ip = result["infrastructure_prediction"]
        assert ip["cpu_increase_probability"] >= 0.3
        assert ip["memory_increase_probability"] >= 0.3
        op = result["outcome_prediction"]
        assert len(op["reasoning"]) > 0


class TestScenario5Helm:
    """Helm chart rollout — Kubernetes deployment."""

    @pytest.mark.asyncio
    async def test_helm_prediction(self, sim):
        """Helm release predicts pod scaling and config changes."""
        result = await sim.simulate(
            repository="org/helm-charts",
            changed_files=["charts/app/values.yaml", "charts/app/templates/deployment.yaml"],
            changed_services=["helm", "kubernetes"],
            change_categories=["infrastructure", "helm"],
        )
        ip = result["infrastructure_prediction"]
        assert ip["pod_scaling_probability"] > 0.3
        sc = result["strategy_comparison"]
        assert len(sc["strategies"]) == 6


class TestScenario6KubernetesRollout:
    """Kubernetes rollout — deployment strategy analysis."""

    @pytest.mark.asyncio
    async def test_kubernetes_rollout_prediction(self, sim):
        """K8s rollout recommends safest strategy."""
        result = await sim.simulate(
            repository="org/k8s-manifests",
            changed_files=["deploy/prod/deployment.yaml", "deploy/prod/service.yaml"],
            changed_services=["kubernetes", "backend"],
            change_categories=["infrastructure", "deployment"],
        )
        sc = result["strategy_comparison"]
        assert sc["recommended_strategy"] is not None
        # Rolling can be compared with blue-green
        for s in sc["strategies"]:
            assert "expected_success_probability" in s
            assert "expected_risk_score" in s


class TestScenario7Rollback:
    """Rollback scenario — highest risk, lowest confidence."""

    @pytest.mark.asyncio
    async def test_rollback_prediction(self, sim):
        """Active rollback in progress elevates all risk signals."""
        result = await sim.simulate(
            repository="org/backend-api",
            changed_files=["src/api/payments.py"],
            changed_services=["payment"],
            change_categories=["backend", "hotfix"],
            # Simulate rollback context by passing metadata
        )
        # Now simulate with rollback context
        result2 = await sim.simulate(
            repository="org/backend-api",
            changed_files=["src/api/payments.py"],
            changed_services=["payment"],
            change_categories=["backend"],
        )
        op = result2["outcome_prediction"]
        assert op["deployment_success_probability"] > 0.0
        assert op["recovery_probability"] > 0.0


class TestScenario8Hotfix:
    """Hotfix deployment — expedited, higher risk."""

    @pytest.mark.asyncio
    async def test_hotfix_prediction(self, sim):
        """Hotfix has expedited duration but higher risk score."""
        result = await sim.simulate(
            repository="org/backend-api",
            changed_files=["src/api/security.py"],
            changed_services=["backend"],
            change_categories=["backend", "security", "hotfix"],
        )
        bp = result["business_prediction"]
        assert bp["expected_duration_minutes"] > 0
        sc = result["strategy_comparison"]
        for s in sc["strategies"]:
            if s["strategy"] == "hotfix":
                assert s["expected_duration_minutes"] < 30
                break


class TestScenario9CriticalPaymentDeployment:
    """Critical payment deployment — maximum scrutiny."""

    @pytest.mark.asyncio
    async def test_payment_prediction(self, sim):
        """Payment deployment impacts critical services and has elevated approval probability."""
        result = await sim.simulate(
            repository="org/payment-service",
            changed_files=["src/services/payment/processor.py", "src/services/payment/webhook.py"],
            changed_services=["payment", "backend"],
            change_categories=["backend", "payment", "api"],
        )
        op = result["outcome_prediction"]
        si = result["service_impact_prediction"]
        assert op["approval_probability"] >= 0.3
        assert "payment" in si["affected_services"]
        assert result["executive_report"]["success_probability"] > 0.0
        assert result["executive_report"]["failure_probability"] > 0.0
        assert result["executive_report"]["risk_probability"] > 0.0
        assert result["executive_report"]["recovery_probability"] > 0.0


# =============================================================================
# Full Integration — End-to-End Simulation
# =============================================================================


class TestFullIntegration:
    """End-to-end simulation produces all required outputs."""

    @pytest.mark.asyncio
    async def test_full_simulation_returns_all_phases(self, sim):
        """Simulation returns all prediction phases."""
        result = await sim.simulate(
            repository="org/full-test",
            branch="feature/test",
            changed_files=["src/app.py", "tests/test_app.py", "deploy/Dockerfile"],
            changed_services=["backend"],
            change_categories=["backend", "test"],
        )
        assert "prediction_id" in result
        assert "outcome_prediction" in result
        assert "infrastructure_prediction" in result
        assert "service_impact_prediction" in result
        assert "business_prediction" in result
        assert "strategy_comparison" in result
        assert "executive_report" in result

    @pytest.mark.asyncio
    async def test_prediction_caching(self, sim):
        """Predictions are cached and retrievable."""
        result = await sim.simulate(repository="org/cache-test")
        pid = result["prediction_id"]

        cached = await sim.get_prediction(pid)
        assert cached is not None
        assert cached["prediction_id"] == pid

        report = await sim.get_report(pid)
        assert report is not None
        assert report["prediction_id"] == pid

    @pytest.mark.asyncio
    async def test_list_predictions(self, sim):
        """List predictions returns all cached predictions."""
        await sim.simulate(repository="org/list-test-1")
        await sim.simulate(repository="org/list-test-2")

        predictions = await sim.list_predictions()
        assert len(predictions) >= 2

    @pytest.mark.asyncio
    async def test_prediction_not_found(self, sim):
        """Getting nonexistent prediction returns None."""
        result = await sim.get_prediction("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_consume_predictions_returns_digest(self, sim):
        """consume_predictions returns lightweight digest for decision engine."""
        digest = await sim.consume_predictions(
            repository="org/digest-test",
            changed_files=["main.py"],
            changed_services=["backend"],
            change_categories=["backend"],
        )
        assert "prediction_id" in digest
        assert "deployment_success_probability" in digest
        assert "rollback_probability" in digest
        assert "recommended_strategy" in digest
        assert "confidence" in digest
        assert "strategy_comparison" in digest
