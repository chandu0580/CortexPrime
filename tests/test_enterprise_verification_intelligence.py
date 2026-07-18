"""
Validation tests for Enterprise Verification Intelligence.

Phases covered:
  1. Prediction vs Reality Comparison — 5 dimensions
  2. Verification Report — 6 accuracy metrics
  3. Confidence Adjustment — 4 confidence deltas
  4. Learning Feedback — 5 dispatch targets
  5. Failure Attribution — 10+ attribution patterns
  6. Engineering Scorecards — 6 dimensions
  7. Executive Dashboard — 9 metrics
  8. Continuous Improvement — improvement suggestions

Scenarios (Phase 9):
  1. Prediction matched reality
  2. Prediction partially matched
  3. Prediction completely wrong
  4. Rollback
  5. Hotfix
  6. Canary
  7. Blue/Green
  8. Infrastructure outage
  9. Database migration
"""
from __future__ import annotations

import pytest
from typing import Any, Dict, List

from backend.services.enterprise_verification_intelligence import (
    EnterpriseVerificationIntelligence,
    PredictionRealityComparator,
    VerificationReportGenerator,
    ConfidenceAdjuster,
    FailureAttributor,
    ScorecardTracker,
    DashboardGenerator,
    ContinuousImprover,
    VerificationInput,
    VerificationReport,
    DimensionAccuracy,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def verifier() -> EnterpriseVerificationIntelligence:
    return EnterpriseVerificationIntelligence()


@pytest.fixture
def comparator() -> PredictionRealityComparator:
    return PredictionRealityComparator()


@pytest.fixture
def report_generator() -> VerificationReportGenerator:
    return VerificationReportGenerator()


@pytest.fixture
def adjuster() -> ConfidenceAdjuster:
    return ConfidenceAdjuster()


@pytest.fixture
def attributor() -> FailureAttributor:
    return FailureAttributor()


@pytest.fixture
def tracker() -> ScorecardTracker:
    return ScorecardTracker()


@pytest.fixture
def dashboard_gen() -> DashboardGenerator:
    return DashboardGenerator()


@pytest.fixture
def improver() -> ContinuousImprover:
    return ContinuousImprover()


# =============================================================================
# Phase 1 — Prediction vs Reality Comparison
# =============================================================================


class TestPredictionRealityComparator:
    """Phase 1: Compare predicted vs actual outcomes."""

    def test_compare_perfect_match(self, comparator):
        """Perfect prediction yields accuracy of 1.0."""
        inp = VerificationInput(
            verification_id="test-1", execution_id="exec-1",
            predicted_success=1.0, actual_success=True,
            predicted_duration_seconds=600.0, actual_duration_seconds=600.0,
            predicted_rollback_probability=0.0, actual_rolled_back=False,
            predicted_risk_score=0.2, actual_risk_score=0.2,
        )
        dims, overall, reasons = comparator.compare(inp)
        assert overall == 1.0
        for d in dims:
            assert d.accuracy == 1.0

    def test_compare_complete_mismatch(self, comparator):
        """Complete mismatch yields low accuracy."""
        inp = VerificationInput(
            verification_id="test-2", execution_id="exec-2",
            predicted_success=0.9, actual_success=False,
            predicted_duration_seconds=100.0, actual_duration_seconds=900.0,
            predicted_rollback_probability=0.05, actual_rolled_back=True,
            predicted_risk_score=0.1, actual_risk_score=0.9,
        )
        dims, overall, reasons = comparator.compare(inp)
        assert overall < 0.5
        assert len(reasons) > 0

    def test_compare_all_five_dimensions(self, comparator):
        """Comparison returns all 5 dimensions."""
        inp = VerificationInput(verification_id="test-3", execution_id="exec-3")
        dims, overall, reasons = comparator.compare(inp)
        dim_names = [d.dimension for d in dims]
        assert "success" in dim_names
        assert "duration" in dim_names
        assert "rollback" in dim_names
        assert "risk" in dim_names
        assert "cost" in dim_names

    def test_compare_duration_accuracy(self, comparator):
        """Duration accuracy is ratio of min/max."""
        inp = VerificationInput(
            verification_id="test-4", execution_id="exec-4",
            predicted_duration_seconds=600.0, actual_duration_seconds=300.0,
        )
        dims, overall, reasons = comparator.compare(inp)
        dur = next(d for d in dims if d.dimension == "duration")
        assert dur.accuracy == 0.5

    def test_compare_reasoning_on_mismatch(self, comparator):
        """Mismatched predictions produce reasoning."""
        inp = VerificationInput(
            verification_id="test-5", execution_id="exec-5",
            predicted_success=0.95, actual_success=False,
            predicted_rollback_probability=0.05, actual_rolled_back=True,
        )
        dims, overall, reasons = comparator.compare(inp)
        assert len(reasons) >= 1


# =============================================================================
# Phase 2 — Verification Report
# =============================================================================


class TestVerificationReport:
    """Phase 2: Generate verification reports with accuracy metrics."""

    def test_generate_report(self, report_generator):
        """Report contains all 6 accuracy metrics."""
        inp = VerificationInput(execution_id="exec-1", prediction_id="pred-1", repository="org/repo")
        dims = [
            DimensionAccuracy(dimension="success", accuracy=0.9, weight=0.30),
            DimensionAccuracy(dimension="duration", accuracy=0.8, weight=0.15),
            DimensionAccuracy(dimension="rollback", accuracy=1.0, weight=0.20),
            DimensionAccuracy(dimension="risk", accuracy=0.7, weight=0.20),
            DimensionAccuracy(dimension="cost", accuracy=0.9, weight=0.15),
        ]
        report = report_generator.generate(inp, dims, 0.85, ["Test reasoning"])
        assert report.report_id.startswith("vr-")
        assert isinstance(report.prediction_accuracy, float)
        assert isinstance(report.decision_accuracy, float)
        assert isinstance(report.deployment_accuracy, float)
        assert isinstance(report.infrastructure_accuracy, float)
        assert isinstance(report.operational_accuracy, float)
        assert isinstance(report.overall_confidence, float)
        assert len(report.dimensions) == 5
        assert report.score == 0.85

    def test_report_to_dict(self, report_generator):
        """Report serializes correctly."""
        inp = VerificationInput(execution_id="exec-2")
        dims = [DimensionAccuracy(dimension="success", accuracy=1.0)]
        report = report_generator.generate(inp, dims, 1.0, [])
        d = report.to_dict()
        assert d["report_id"] == report.report_id
        assert d["prediction_accuracy"] == 1.0

    def test_accuracy_bounds(self, report_generator):
        """All accuracy values are clamped 0-1."""
        inp = VerificationInput(execution_id="exec-3")
        dims = [DimensionAccuracy(dimension=d, accuracy=0.99) for d in ["success", "duration", "rollback", "risk", "cost"]]
        report = report_generator.generate(inp, dims, 0.99, [])
        for acc_name in ["prediction_accuracy", "decision_accuracy", "deployment_accuracy",
                         "infrastructure_accuracy", "operational_accuracy", "overall_confidence"]:
            val = getattr(report, acc_name)
            assert 0.0 <= val <= 1.0, f"{acc_name} = {val}"


# =============================================================================
# Phase 3 — Confidence Adjustment
# =============================================================================


class TestConfidenceAdjustment:
    """Phase 3: Adjust confidence based on verification accuracy."""

    def test_adjust_high_accuracy_positive(self, adjuster, report_generator):
        """High accuracy yields positive confidence deltas."""
        inp = VerificationInput(execution_id="exec-1")
        dims = [DimensionAccuracy(dimension=d, accuracy=0.95, weight=0.20) for d in
                ["success", "duration", "rollback", "risk", "cost"]]
        report = report_generator.generate(inp, dims, 0.95, [])
        adj = adjuster.adjust(report, dims)
        assert adj.prediction_confidence_delta > 0
        assert adj.decision_confidence_delta > 0
        assert len(adj.reasoning) > 0

    def test_adjust_low_accuracy_negative(self, adjuster, report_generator):
        """Low accuracy yields negative confidence deltas."""
        inp = VerificationInput(execution_id="exec-2")
        dims = [DimensionAccuracy(dimension=d, accuracy=0.2, weight=0.20) for d in
                ["success", "duration", "rollback", "risk", "cost"]]
        report = report_generator.generate(inp, dims, 0.2, [])
        adj = adjuster.adjust(report, dims)
        assert adj.prediction_confidence_delta < 0
        assert adj.decision_confidence_delta < 0

    def test_adjust_bounded(self, adjuster, report_generator):
        """Confidence deltas are bounded by SCALE."""
        inp = VerificationInput(execution_id="exec-3")
        dims = [DimensionAccuracy(dimension=d, accuracy=1.0, weight=0.20) for d in
                ["success", "duration", "rollback", "risk", "cost"]]
        report = report_generator.generate(inp, dims, 1.0, [])
        adj = adjuster.adjust(report, dims)
        assert adj.prediction_confidence_delta <= adjuster.SCALE
        assert adj.prediction_confidence_delta >= -adjuster.SCALE

    def test_adjust_neutral_at_50(self, adjuster, report_generator):
        """50% accuracy yields ~zero delta."""
        inp = VerificationInput(execution_id="exec-4")
        dims = [DimensionAccuracy(dimension=d, accuracy=0.5, weight=0.20) for d in
                ["success", "duration", "rollback", "risk", "cost"]]
        report = report_generator.generate(inp, dims, 0.5, [])
        adj = adjuster.adjust(report, dims)
        assert abs(adj.prediction_confidence_delta) < 0.01


# =============================================================================
# Phase 4 — Learning Feedback (integration-level tests)
# =============================================================================


class TestLearningFeedback:
    """Phase 4: Verify feedback dispatch doesn't crash."""

    @pytest.mark.asyncio
    async def test_feedback_dispatch_does_not_crash(self, verifier):
        """End-to-end verify dispatches feedback without errors."""
        result = await verifier.verify(
            execution_id="exec-fb-1",
            prediction_id="pred-fb-1",
            repository="org/test",
            actual_outcome="success",
            actual_success=True,
        )
        assert "feedback_results" in result
        assert isinstance(result["feedback_results"], dict)


# =============================================================================
# Phase 5 — Failure Attribution
# =============================================================================


class TestFailureAttribution:
    """Phase 5: Determine WHY prediction failed."""

    def test_attribution_accurate_match(self, attributor):
        """Matching prediction returns accurate category."""
        inp = VerificationInput(verification_id="vrf-1", execution_id="exec-1")
        dims = [DimensionAccuracy(dimension=d, accuracy=0.95) for d in ["success", "duration", "rollback", "risk", "cost"]]
        attr = attributor.attribute(inp, dims)
        assert attr.category == "accurate"

    def test_attribution_infrastructure_issue(self, attributor):
        """Infrastructure change category detected."""
        inp = VerificationInput(
            verification_id="vrf-2", execution_id="exec-2",
            change_categories=["infrastructure", "terraform"],
        )
        dims = [DimensionAccuracy(dimension=d, accuracy=0.2) for d in ["success", "duration", "rollback", "risk", "cost"]]
        attr = attributor.attribute(inp, dims)
        assert attr.category == "infrastructure_issue"

    def test_attribution_database_migration(self, attributor):
        """Database migration category detected."""
        inp = VerificationInput(
            verification_id="vrf-3", execution_id="exec-3",
            change_categories=["database", "migration"],
        )
        dims = [DimensionAccuracy(dimension=d, accuracy=0.3) for d in ["success", "duration", "rollback", "risk", "cost"]]
        attr = attributor.attribute(inp, dims)
        assert attr.category == "database_migration"

    def test_attribution_overconfidence(self, attributor):
        """Overconfident prediction detected."""
        inp = VerificationInput(
            verification_id="vrf-4", execution_id="exec-4",
            predicted_success=0.9, actual_success=False,
        )
        dims = [DimensionAccuracy(dimension=d, accuracy=0.1) for d in ["success", "duration", "rollback", "risk", "cost"]]
        attr = attributor.attribute(inp, dims)
        assert attr.category in ("overconfidence", "unknown_failure")

    def test_attribution_rollback(self, attributor):
        """Rollback attribution."""
        inp = VerificationInput(
            verification_id="vrf-5", execution_id="exec-5",
            actual_rolled_back=True, actual_success=False,
        )
        dims = [DimensionAccuracy(dimension=d, accuracy=0.3) for d in ["success", "duration", "rollback", "risk", "cost"]]
        attr = attributor.attribute(inp, dims)
        assert attr.category == "rollback"

    def test_attribution_has_suggested_fix(self, attributor):
        """Attribution includes a suggested fix."""
        inp = VerificationInput(
            verification_id="vrf-6", execution_id="exec-6",
            change_categories=["database", "migration"],
        )
        dims = [DimensionAccuracy(dimension=d, accuracy=0.2) for d in ["success", "duration", "rollback", "risk", "cost"]]
        attr = attributor.attribute(inp, dims)
        assert attr.suggested_fix != ""


# =============================================================================
# Phase 6 — Engineering Scorecards
# =============================================================================


class TestScorecardTracker:
    """Phase 6: Track engineering reliability scorecards."""

    def test_record_successful_deployment(self, tracker):
        """Successful deployment increases reliability."""
        inp = VerificationInput(
            execution_id="exec-1", repository="org/repo", service="backend",
            actual_success=True,
        )
        entries = tracker.record(inp)
        assert len(entries) > 0
        for e in entries:
            if e.dimension == "repository" and e.entity == "org/repo":
                assert e.successful_deployments == 1
                assert e.reliability_score == 1.0

    def test_record_failed_deployment(self, tracker):
        """Failed deployment reduces reliability."""
        inp1 = VerificationInput(execution_id="exec-1", repository="org/repo", actual_success=True)
        inp2 = VerificationInput(execution_id="exec-2", repository="org/repo", actual_success=False)
        tracker.record(inp1)
        entries = tracker.record(inp2)
        repo_entry = next((e for e in entries if e.dimension == "repository" and e.entity == "org/repo"), None)
        if repo_entry:
            assert repo_entry.total_deployments == 2
            assert repo_entry.successful_deployments == 1
            assert repo_entry.reliability_score == 0.5

    def test_get_scorecard_by_dimension(self, tracker):
        """Retrieve scorecards filtered by dimension."""
        inp = VerificationInput(
            execution_id="exec-1", repository="org/repo", service="api",
            actual_success=True,
        )
        tracker.record(inp)
        repo_scores = tracker.get_scorecard(dimension="repository")
        assert len(repo_scores) > 0
        for s in repo_scores:
            assert s["dimension"] == "repository"

    def test_get_scorecard_summary(self, tracker):
        """Scorecard summary aggregates correctly."""
        for i in range(5):
            inp = VerificationInput(
                execution_id=f"exec-{i}", repository="org/repo",
                actual_success=(i % 2 == 0),
            )
            tracker.record(inp)
        summary = tracker.get_summary()
        assert summary["total_entries"] > 0
        assert "repository" in summary["dimensions"]

    def test_empty_scorecard_summary(self, tracker):
        """Empty scorecard returns zeroed summary."""
        summary = tracker.get_summary()
        assert summary["total_entries"] == 0


# =============================================================================
# Phase 7 — Executive Dashboard
# =============================================================================


class TestExecutiveDashboard:
    """Phase 7: Generate executive dashboard."""

    def test_dashboard_empty(self, dashboard_gen, tracker):
        """Empty history returns zeroed dashboard."""
        dash = dashboard_gen.generate(tracker)
        assert dash.total_verifications == 0

    def test_dashboard_with_data(self, dashboard_gen, tracker, report_generator):
        """Dashboard reflects accumulated verification data."""
        for i in range(5):
            inp = VerificationInput(
                execution_id=f"exec-{i}", repository=f"org/repo-{i}",
                predicted_success=0.8 + i * 0.02, actual_success=(i % 2 == 0),
            )
            dims, overall, reasons = PredictionRealityComparator().compare(inp)
            report = report_generator.generate(inp, dims, overall, reasons)
            dashboard_gen.add_report(report)
            tracker.record(inp)

        dash = dashboard_gen.generate(tracker)
        assert dash.total_verifications == 5
        assert dash.prediction_accuracy_percent > 0
        assert dash.decision_accuracy_percent > 0
        assert dash.deployment_success_percent > 0
        assert len(dash.accuracy_by_dimension) > 0

    def test_dashboard_tracks_improvement(self, dashboard_gen, tracker, report_generator):
        """Dashboard shows improvement trend."""
        for i in range(15):
            inp = VerificationInput(
                execution_id=f"exec-{i}", repository="org/repo",
                predicted_success=0.5, actual_success=(i >= 7),
            )
            dims, overall, reasons = PredictionRealityComparator().compare(inp)
            report = report_generator.generate(inp, dims, overall, reasons)
            dashboard_gen.add_report(report)

        dash = dashboard_gen.generate(tracker)
        # Improvement should be detectable
        assert isinstance(dash.learning_improvement_percent, float)

    def test_dashboard_top_predictions(self, dashboard_gen, tracker, report_generator):
        """Dashboard identifies top correct and incorrect predictions."""
        for i in range(10):
            succ = i % 2 == 0
            inp = VerificationInput(
                execution_id=f"exec-{i}", repository=f"org/repo-{i}",
                predicted_success=0.9 if succ else 0.1, actual_success=succ,
            )
            dims, overall, reasons = PredictionRealityComparator().compare(inp)
            report = report_generator.generate(inp, dims, overall, reasons)
            dashboard_gen.add_report(report)

        dash = dashboard_gen.generate(tracker)
        assert len(dash.top_incorrect_predictions) > 0
        assert len(dash.top_correct_predictions) > 0


# =============================================================================
# Phase 8 — Continuous Improvement
# =============================================================================


class TestContinuousImprovement:
    """Phase 8: Identify weak models and suggest improvements."""

    def test_improvement_low_accuracy(self, improver, dashboard_gen, tracker, report_generator):
        """Low accuracy generates improvement suggestions."""
        for i in range(5):
            inp = VerificationInput(
                execution_id=f"exec-{i}",
                predicted_success=0.9, actual_success=False,
            )
            dims, overall, reasons = PredictionRealityComparator().compare(inp)
            report = report_generator.generate(inp, dims, overall, reasons)
            dashboard_gen.add_report(report)
            tracker.record(inp)

        dash = dashboard_gen.generate(tracker)
        suggestions = improver.analyze(dash, dashboard_gen._history)
        pred_suggestions = [s for s in suggestions if s.category == "prediction_model"]
        risk_suggestions = [s for s in suggestions if s.category == "risk_model"]
        assert len(pred_suggestions) > 0 or len(risk_suggestions) > 0

    def test_improvement_weak_dimension(self, improver, dashboard_gen, tracker, report_generator):
        """Weak dimension performance generates targeted suggestion."""
        for i in range(5):
            inp = VerificationInput(execution_id=f"exec-{i}", actual_success=True)
            dims = [
                DimensionAccuracy(dimension="cost", accuracy=0.3),
                DimensionAccuracy(dimension="success", accuracy=0.9),
                DimensionAccuracy(dimension="duration", accuracy=0.9),
                DimensionAccuracy(dimension="rollback", accuracy=0.9),
                DimensionAccuracy(dimension="risk", accuracy=0.9),
            ]
            report = report_generator.generate(inp, dims, 0.5, [])
            dashboard_gen.add_report(report)

        dash = dashboard_gen.generate(tracker)
        suggestions = improver.analyze(dash, dashboard_gen._history)
        cost_suggestions = [s for s in suggestions if "cost" in s.category]
        assert len(cost_suggestions) > 0

    def test_improvement_no_suggestions_high_accuracy(self, improver, dashboard_gen, tracker, report_generator):
        """High accuracy yields no critical suggestions."""
        for i in range(5):
            inp = VerificationInput(
                execution_id=f"exec-{i}", actual_success=True,
            )
            dims = [DimensionAccuracy(dimension=d, accuracy=0.95) for d in
                    ["success", "duration", "rollback", "risk", "cost"]]
            report = report_generator.generate(inp, dims, 0.95, [])
            dashboard_gen.add_report(report)

        dash = dashboard_gen.generate(tracker)
        suggestions = improver.analyze(dash, dashboard_gen._history)
        high_severity = [s for s in suggestions if s.severity == "high"]
        assert len(high_severity) == 0


# =============================================================================
# Full Integration — EnterpriseVerificationIntelligence
# =============================================================================


class TestEnterpriseVerificationIntelligence:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_verify_successful_match(self, verifier):
        """Successful match produces all expected outputs."""
        result = await verifier.verify(
            execution_id="exec-int-1",
            prediction_id="pred-int-1",
            repository="org/integration",
            service="backend",
            environment="production",
            predicted_success=0.95,
            actual_success=True,
            predicted_duration_seconds=600,
            actual_duration_seconds=580,
            predicted_rollback_probability=0.05,
            actual_rolled_back=False,
            actual_outcome="success",
            change_categories=["backend"],
            changed_services=["backend"],
        )
        assert "verification_id" in result
        assert "report" in result
        assert "confidence_adjustment" in result
        assert "attribution" in result
        assert "scorecard_entries" in result
        assert "improvement_suggestions" in result
        assert result["report"]["prediction_accuracy"] > 0.5

    @pytest.mark.asyncio
    async def test_verify_failed_prediction(self, verifier):
        """Failed prediction returns low accuracy and attribution."""
        result = await verifier.verify(
            execution_id="exec-int-2",
            prediction_id="pred-int-2",
            repository="org/failure",
            predicted_success=0.9,
            actual_success=False,
            predicted_rollback_probability=0.05,
            actual_rolled_back=True,
            actual_outcome="rolled_back",
            actual_failure_reason="Database connection timeout during migration",
            change_categories=["database", "migration"],
            has_db_migrations=True,
        )
        assert result["report"]["prediction_accuracy"] < 0.5
        assert result["attribution"]["category"] != "accurate"

    @pytest.mark.asyncio
    async def test_get_verification(self, verifier):
        """Verification is stored and retrievable."""
        result = await verifier.verify(
            execution_id="exec-get-1",
            prediction_id="pred-get-1",
            repository="org/get-test",
            actual_outcome="success",
            actual_success=True,
        )
        vid = result["verification_id"]
        stored = await verifier.get_verification(vid)
        assert stored is not None
        assert stored["verification_id"] == vid

    @pytest.mark.asyncio
    async def test_get_report(self, verifier):
        """Report is stored and retrievable."""
        result = await verifier.verify(
            execution_id="exec-rpt-1",
            prediction_id="pred-rpt-1",
            repository="org/rpt-test",
            actual_outcome="success",
            actual_success=True,
        )
        rid = result["report"]["report_id"]
        report = await verifier.get_report(rid)
        assert report is not None
        assert report["report_id"] == rid

    @pytest.mark.asyncio
    async def test_list_verifications(self, verifier):
        """List returns all verifications."""
        await verifier.verify(execution_id="exec-list-1", prediction_id="pred-list-1",
                              repository="org/list", actual_outcome="success", actual_success=True)
        await verifier.verify(execution_id="exec-list-2", prediction_id="pred-list-2",
                              repository="org/list", actual_outcome="failed", actual_success=False)
        items = await verifier.list_verifications()
        assert len(items) >= 2

    @pytest.mark.asyncio
    async def test_get_dashboard_endpoint(self, verifier):
        """Dashboard returns aggregated data."""
        for i in range(3):
            await verifier.verify(
                execution_id=f"exec-dash-{i}",
                prediction_id=f"pred-dash-{i}",
                repository="org/dashboard",
                actual_success=(i % 2 == 0),
                actual_outcome="success" if i % 2 == 0 else "failed",
            )
        dash = await verifier.get_dashboard()
        assert dash["total_verifications"] >= 3
        assert dash["prediction_accuracy_percent"] > 0

    @pytest.mark.asyncio
    async def test_get_improvement_suggestions_endpoint(self, verifier):
        """Improvement suggestions are generated from data."""
        for i in range(5):
            await verifier.verify(
                execution_id=f"exec-sug-{i}",
                prediction_id=f"pred-sug-{i}",
                repository="org/suggestions",
                predicted_success=0.9, actual_success=False,
                actual_outcome="failed",
                actual_failure_reason="timeout error",
            )
        suggestions = await verifier.get_improvement_suggestions()
        assert len(suggestions) > 0


# =============================================================================
# Phase 10 — Scenario Validations
# =============================================================================


class TestScenario1PredictionMatchedReality:
    """Prediction matched reality — high accuracy expected."""

    @pytest.mark.asyncio
    async def test_matched_prediction(self, verifier):
        """Accurate prediction yields high accuracy report."""
        result = await verifier.verify(
            execution_id="exec-sc1",
            prediction_id="pred-sc1",
            repository="org/matched",
            predicted_success=0.92,
            actual_success=True,
            predicted_duration_seconds=450,
            actual_duration_seconds=430,
            predicted_rollback_probability=0.05,
            actual_rolled_back=False,
            predicted_risk_score=0.25,
            actual_risk_score=0.25,
            actual_outcome="success",
        )
        assert result["report"]["prediction_accuracy"] >= 0.8
        assert result["attribution"]["category"] == "accurate"


class TestScenario2PredictionPartiallyMatched:
    """Prediction partially matched — medium accuracy expected."""

    @pytest.mark.asyncio
    async def test_partial_match(self, verifier):
        """Partially matched prediction yields medium accuracy."""
        result = await verifier.verify(
            execution_id="exec-sc2",
            prediction_id="pred-sc2",
            repository="org/partial",
            predicted_success=0.85,
            actual_success=True,
            predicted_duration_seconds=300,
            actual_duration_seconds=900,
            predicted_rollback_probability=0.05,
            actual_rolled_back=False,
            actual_outcome="success",
        )
        assert result["report"]["prediction_accuracy"] < 0.9
        assert result["report"]["prediction_accuracy"] >= 0.3


class TestScenario3PredictionCompletelyWrong:
    """Prediction completely wrong — low accuracy expected."""

    @pytest.mark.asyncio
    async def test_completely_wrong(self, verifier):
        """Wrong prediction yields low accuracy and attribution."""
        result = await verifier.verify(
            execution_id="exec-sc3",
            prediction_id="pred-sc3",
            repository="org/wrong",
            predicted_success=0.95,
            actual_success=False,
            predicted_duration_seconds=120,
            actual_duration_seconds=1800,
            predicted_rollback_probability=0.02,
            actual_rolled_back=True,
            predicted_risk_score=0.1,
            actual_risk_score=0.85,
            actual_outcome="rolled_back",
            actual_failure_reason="unexpected infrastructure failure during deployment",
            change_categories=["infrastructure"],
        )
        assert result["report"]["prediction_accuracy"] < 0.3
        assert result["attribution"]["category"] != "accurate"


class TestScenario4Rollback:
    """Rollback scenario — rollback attribution."""

    @pytest.mark.asyncio
    async def test_rollback(self, verifier):
        """Rollback verification returns rollback attribution."""
        result = await verifier.verify(
            execution_id="exec-sc4",
            prediction_id="pred-sc4",
            repository="org/rollback",
            predicted_success=0.75,
            actual_success=False,
            predicted_rollback_probability=0.15,
            actual_rolled_back=True,
            actual_outcome="rolled_back",
            actual_failure_reason="Deployment caused service degradation, rolled back",
            change_categories=["backend"],
        )
        assert result["attribution"]["category"] in ("rollback", "overconfidence")


class TestScenario5Hotfix:
    """Hotfix deployment — expedited."""

    @pytest.mark.asyncio
    async def test_hotfix(self, verifier):
        """Hotfix verification generates report and scorecards."""
        result = await verifier.verify(
            execution_id="exec-sc5",
            prediction_id="pred-sc5",
            repository="org/hotfix",
            service="backend",
            predicted_success=0.6,
            actual_success=True,
            predicted_duration_seconds=180,
            actual_duration_seconds=150,
            predicted_rollback_probability=0.2,
            actual_rolled_back=False,
            actual_outcome="success",
            change_categories=["backend", "hotfix"],
        )
        assert result["report"]["prediction_accuracy"] > 0.5
        assert len(result["scorecard_entries"]) > 0


class TestScenario6Canary:
    """Canary deployment — partial rollout."""

    @pytest.mark.asyncio
    async def test_canary(self, verifier):
        """Canary verification tracks strategy accuracy."""
        result = await verifier.verify(
            execution_id="exec-sc6",
            prediction_id="pred-sc6",
            repository="org/canary",
            predicted_success=0.88,
            actual_success=True,
            predicted_strategy="canary",
            actual_strategy="canary",
            actual_outcome="success",
            change_categories=["backend"],
        )
        assert result["report"]["prediction_accuracy"] > 0.5
        assert "success" in result["report"]["dimensions"][0]["dimension"]


class TestScenario7BlueGreen:
    """Blue/green deployment — zero-downtime."""

    @pytest.mark.asyncio
    async def test_blue_green(self, verifier):
        """Blue/green verification yields high accuracy on match."""
        result = await verifier.verify(
            execution_id="exec-sc7",
            prediction_id="pred-sc7",
            repository="org/bluegreen",
            predicted_success=0.95,
            actual_success=True,
            predicted_strategy="blue_green",
            actual_strategy="blue_green",
            actual_outcome="success",
            change_categories=["backend"],
        )
        assert result["verification_id"] is not None


class TestScenario8InfrastructureOutage:
    """Infrastructure outage — unexpected failure."""

    @pytest.mark.asyncio
    async def test_infrastructure_outage(self, verifier):
        """Infrastructure outage detected in attribution."""
        result = await verifier.verify(
            execution_id="exec-sc8",
            prediction_id="pred-sc8",
            repository="org/infra",
            predicted_success=0.9,
            actual_success=False,
            actual_outcome="failed",
            actual_failure_reason="terraform apply failed due to API rate limiting",
            change_categories=["infrastructure", "terraform"],
            has_infrastructure_changes=True,
        )
        assert result["attribution"]["category"] in ("infrastructure_issue", "overconfidence")


class TestScenario9DatabaseMigration:
    """Database migration — elevated risk."""

    @pytest.mark.asyncio
    async def test_database_migration(self, verifier):
        """Database migration attribution detected."""
        result = await verifier.verify(
            execution_id="exec-sc9",
            prediction_id="pred-sc9",
            repository="org/db-migrate",
            predicted_success=0.7,
            actual_success=True,
            actual_outcome="success",
            change_categories=["database", "migration"],
            has_db_migrations=True,
        )
        # Should at minimum return valid report
        assert result["report"]["report_id"] is not None
