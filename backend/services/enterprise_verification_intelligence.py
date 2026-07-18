"""
Enterprise Verification Intelligence — continuously compares predicted engineering
outcomes with actual outcomes and automatically improves CortexPrime.

Reuses (never duplicates):
  - Predictive Simulation   - Engineering Memory
  - Learning Engine         - Knowledge Graph
  - Recommendation Engine   - ReplayStore / RuntimeStore
  - Decision Engine         - EventHub

Phases:
  1. Prediction vs Reality  2. Verification Report  3. Confidence Adjustment
  4. Learning Feedback      5. Failure Attribution  6. Engineering Scorecards
  7. Executive Dashboard    8. Continuous Improvement  9. Validation
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


# =============================================================================
# Phase 1 — Prediction vs Reality Data
# =============================================================================


@dataclass(frozen=True)
class VerificationInput:
    """Input data comparing a prediction against actual results."""
    verification_id: str = ""
    execution_id: str = ""
    prediction_id: str = ""
    repository: str = ""
    team: str = ""
    service: str = ""
    environment: str = ""

    predicted_success: float = 0.5
    actual_success: bool = False
    predicted_duration_seconds: float = 600.0
    actual_duration_seconds: float = 0.0
    predicted_rollback_probability: float = 0.1
    actual_rolled_back: bool = False
    predicted_risk_score: float = 0.3
    actual_risk_score: float = 0.0
    predicted_cost_increase: float = 0.0
    actual_cost_increase: float = 0.0

    predicted_strategy: str = ""
    actual_strategy: str = ""
    actual_outcome: str = ""
    actual_failure_reason: str = ""
    change_categories: List[str] = field(default_factory=list)
    changed_services: List[str] = field(default_factory=list)
    has_db_migrations: bool = False
    has_infrastructure_changes: bool = False

    created_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class DimensionAccuracy:
    """Accuracy for a single prediction dimension."""
    dimension: str = ""
    predicted_value: float = 0.0
    actual_value: float = 0.0
    error: float = 0.0
    absolute_error: float = 0.0
    accuracy: float = 0.0
    weight: float = 1.0


# =============================================================================
# Phase 2 — Verification Report
# =============================================================================


@dataclass(frozen=True)
class VerificationReport:
    report_id: str = ""
    execution_id: str = ""
    prediction_id: str = ""
    repository: str = ""
    timestamp: str = ""

    prediction_accuracy: float = 0.0
    decision_accuracy: float = 0.0
    deployment_accuracy: float = 0.0
    infrastructure_accuracy: float = 0.0
    operational_accuracy: float = 0.0
    overall_confidence: float = 0.0

    dimensions: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Phase 5 — Failure Attribution
# =============================================================================


@dataclass(frozen=True)
class FailureAttribution:
    attribution_id: str = ""
    verification_id: str = ""
    primary_reason: str = ""
    secondary_reasons: List[str] = field(default_factory=list)
    category: str = "unknown"
    confidence: float = 0.5
    suggested_fix: str = ""


# =============================================================================
# Phase 6 — Scorecards
# =============================================================================


@dataclass(frozen=True)
class ScorecardEntry:
    dimension: str = ""
    entity: str = ""
    total_deployments: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    rolled_back_deployments: int = 0
    reliability_score: float = 1.0
    trend: str = "stable"
    last_updated: str = ""


# =============================================================================
# Phase 1 — Prediction vs Reality Comparator
# =============================================================================


class PredictionRealityComparator:
    """Compare predicted vs actual outcomes across all dimensions."""

    def compare(self, inp: VerificationInput) -> Tuple[List[DimensionAccuracy], float, List[str]]:
        dimensions: List[DimensionAccuracy] = []
        reasons: List[str] = []

        # Success accuracy
        pred_success = inp.predicted_success
        actual_success_val = 1.0 if inp.actual_success else 0.0
        success_err = pred_success - actual_success_val
        success_acc = 1.0 - abs(success_err)
        dimensions.append(DimensionAccuracy(
            dimension="success", predicted_value=pred_success,
            actual_value=actual_success_val, error=success_err,
            absolute_error=abs(success_err), accuracy=_clamp(success_acc),
            weight=0.30,
        ))
        if success_err > 0.3:
            reasons.append(f"Predicted {pred_success:.0%} success but {'succeeded' if inp.actual_success else 'failed'}")
        elif success_err < -0.3:
            reasons.append(f"Underestimated success probability ({pred_success:.0%} vs actual success)")

        # Duration accuracy
        pred_dur = inp.predicted_duration_seconds
        act_dur = inp.actual_duration_seconds if inp.actual_duration_seconds > 0 else pred_dur
        dur_ratio = min(pred_dur, act_dur) / max(pred_dur, act_dur, 1)
        dimensions.append(DimensionAccuracy(
            dimension="duration", predicted_value=pred_dur,
            actual_value=act_dur, error=pred_dur - act_dur,
            absolute_error=abs(pred_dur - act_dur), accuracy=_clamp(dur_ratio),
            weight=0.15,
        ))
        if abs(pred_dur - act_dur) > 300 and act_dur > 0:
            reasons.append(f"Duration off by {abs(pred_dur - act_dur):.0f}s (predicted {pred_dur:.0f}s, actual {act_dur:.0f}s)")

        # Rollback accuracy
        pred_rb = inp.predicted_rollback_probability
        actual_rb_val = 1.0 if inp.actual_rolled_back else 0.0
        rb_err = pred_rb - actual_rb_val
        rb_acc = 1.0 - abs(rb_err)
        dimensions.append(DimensionAccuracy(
            dimension="rollback", predicted_value=pred_rb,
            actual_value=actual_rb_val, error=rb_err,
            absolute_error=abs(rb_err), accuracy=_clamp(rb_acc),
            weight=0.20,
        ))
        if inp.actual_rolled_back and pred_rb < 0.3:
            reasons.append("Rollback occurred but was predicted unlikely")

        # Risk accuracy
        pred_risk = inp.predicted_risk_score
        act_risk = inp.actual_risk_score if inp.actual_risk_score > 0 else (0.8 if inp.actual_failure_reason else 0.2)
        risk_err = pred_risk - act_risk
        risk_acc = 1.0 - abs(risk_err)
        dimensions.append(DimensionAccuracy(
            dimension="risk", predicted_value=pred_risk,
            actual_value=act_risk, error=risk_err,
            absolute_error=abs(risk_err), accuracy=_clamp(risk_acc),
            weight=0.20,
        ))

        # Cost accuracy
        pred_cost = inp.predicted_cost_increase
        act_cost = inp.actual_cost_increase
        cost_acc = 1.0 - abs(pred_cost - act_cost) if max(pred_cost, act_cost) > 0 else 1.0
        dimensions.append(DimensionAccuracy(
            dimension="cost", predicted_value=pred_cost,
            actual_value=act_cost, error=pred_cost - act_cost,
            absolute_error=abs(pred_cost - act_cost), accuracy=_clamp(cost_acc),
            weight=0.15,
        ))

        # Weighted overall score
        total_weight = sum(d.weight for d in dimensions)
        weighted = sum(d.accuracy * d.weight for d in dimensions) / total_weight if total_weight > 0 else 0

        return dimensions, _clamp(weighted), reasons


# =============================================================================
# Phase 2 — Verification Report Generator
# =============================================================================


class VerificationReportGenerator:
    """Generate comprehensive verification reports."""

    def generate(
        self,
        inp: VerificationInput,
        dimensions: List[DimensionAccuracy],
        overall_accuracy: float,
        reasoning: List[str],
        decision_accuracy: float = 0.0,
    ) -> VerificationReport:
        dim_dicts = [asdict(d) for d in dimensions]

        pred_acc = overall_accuracy
        dec_acc = decision_accuracy if decision_accuracy > 0 else overall_accuracy
        dep_acc = self._compute_sub_accuracy(dimensions, "success", "rollback")
        infra_acc = self._compute_sub_accuracy(dimensions, "risk", "cost")
        op_acc = self._compute_sub_accuracy(dimensions, "duration", "cost")

        overall_confidence = _clamp(
            0.3 * pred_acc + 0.2 * dec_acc + 0.2 * dep_acc + 0.15 * infra_acc + 0.15 * op_acc
        )

        report = VerificationReport(
            report_id=f"vr-{_id()}",
            execution_id=inp.execution_id,
            prediction_id=inp.prediction_id,
            repository=inp.repository,
            timestamp=_now(),
            prediction_accuracy=pred_acc,
            decision_accuracy=dec_acc,
            deployment_accuracy=dep_acc,
            infrastructure_accuracy=infra_acc,
            operational_accuracy=op_acc,
            overall_confidence=overall_confidence,
            dimensions=dim_dicts,
            reasoning=reasoning,
            score=overall_accuracy,
        )
        return report

    def _compute_sub_accuracy(self, dims: List[DimensionAccuracy], *keys: str) -> float:
        relevant = [d for d in dims if d.dimension in keys]
        if not relevant:
            return 0.5
        return _clamp(sum(d.accuracy for d in relevant) / len(relevant))


# =============================================================================
# Phase 3 — Confidence Adjustment
# =============================================================================


@dataclass(frozen=True)
class ConfidenceAdjustment:
    prediction_confidence_delta: float = 0.0
    decision_confidence_delta: float = 0.0
    strategy_confidence_delta: float = 0.0
    risk_confidence_delta: float = 0.0
    reasoning: List[str] = field(default_factory=list)


class ConfidenceAdjuster:
    """Adjust confidence values based on verification accuracy."""

    SCALE = 0.15

    def adjust(self, report: VerificationReport, dimensions: List[DimensionAccuracy]) -> ConfidenceAdjustment:
        reasoning: List[str] = []

        pred_delta = self._delta(report.prediction_accuracy)
        if abs(pred_delta) > 0.01:
            reasoning.append(f"Prediction confidence {'+' if pred_delta > 0 else ''}{pred_delta:+.2f} (accuracy: {report.prediction_accuracy:.1%})")

        dec_delta = self._delta(report.decision_accuracy)
        if abs(dec_delta) > 0.01:
            reasoning.append(f"Decision confidence {'+' if dec_delta > 0 else ''}{dec_delta:+.2f} (accuracy: {report.decision_accuracy:.1%})")

        strategy_delta = dec_delta * 0.8
        if abs(strategy_delta) > 0.01:
            reasoning.append(f"Strategy confidence {'+' if strategy_delta > 0 else ''}{strategy_delta:+.2f}")

        risk_delta = self._delta(report.infrastructure_accuracy) * 0.7
        if abs(risk_delta) > 0.01:
            reasoning.append(f"Risk confidence {'+' if risk_delta > 0 else ''}{risk_delta:+.2f} (infrastructure accuracy: {report.infrastructure_accuracy:.1%})")

        return ConfidenceAdjustment(
            prediction_confidence_delta=round(pred_delta, 3),
            decision_confidence_delta=round(dec_delta, 3),
            strategy_confidence_delta=round(strategy_delta, 3),
            risk_confidence_delta=round(risk_delta, 3),
            reasoning=reasoning,
        )

    def _delta(self, accuracy: float) -> float:
        return _clamp((accuracy - 0.5) * self.SCALE, -self.SCALE, self.SCALE)


# =============================================================================
# Phase 4 — Learning Feedback Dispatcher
# =============================================================================


class LearningFeedbackDispatcher:
    """Send verification results into Learning Engine, Memory, Graph, Replay, Recommendations."""

    async def dispatch(
        self,
        inp: VerificationInput,
        report: VerificationReport,
        attribution: Optional[FailureAttribution] = None,
    ) -> Dict[str, bool]:
        results: Dict[str, bool] = {}

        if inp.actual_failure_reason:
            results["learning"] = await self._send_to_learning(inp, report, attribution)
        results["memory"] = await self._send_to_memory(inp, report)
        results["graph"] = await self._send_to_graph(inp, report)
        results["replay"] = await self._send_to_replay(inp, report)
        results["recommendations"] = await self._send_to_recommendations(inp, report, attribution)

        return results

    async def _send_to_learning(
        self, inp: VerificationInput, report: VerificationReport, attribution: Optional[FailureAttribution] = None,
    ) -> bool:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            metadata = {
                "execution_id": inp.execution_id,
                "prediction_id": inp.prediction_id,
                "repository": inp.repository,
                "actual_outcome": inp.actual_outcome,
                "prediction_accuracy": report.prediction_accuracy,
                "overall_confidence": report.overall_confidence,
            }
            if attribution:
                metadata["failure_reason"] = attribution.primary_reason
                metadata["failure_category"] = attribution.category
            await enterprise_hub.emit(
                event_type="learning.lesson_discovered",
                agent="enterprise_verification_intelligence",
                status="completed" if inp.actual_success else "failed",
                message=f"Verification: {inp.repository} accuracy={report.prediction_accuracy:.1%}",
                execution_id=inp.execution_id,
                metadata=metadata,
            )
            return True
        except Exception as exc:
            log.debug("Learning feedback failed: %s", exc)
            return False

    async def _send_to_memory(self, inp: VerificationInput, report: VerificationReport) -> bool:
        try:
            from backend.services.enterprise_engineering_memory import enterprise_engineering_memory
            await enterprise_engineering_memory.build_experience(
                execution_id=inp.execution_id,
                repository=inp.repository,
                outcome=inp.actual_outcome,
                duration_seconds=inp.actual_duration_seconds,
                changed_services=inp.changed_services,
                change_categories=inp.change_categories,
                failure_reason=inp.actual_failure_reason,
            )
            return True
        except Exception as exc:
            log.debug("Memory feedback failed: %s", exc)
            return False

    async def _send_to_graph(self, inp: VerificationInput, report: VerificationReport) -> bool:
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            await enterprise_graph.record_outcome(
                execution_id=inp.execution_id,
                outcome_id=f"vrf-{_id()}",
                outcome_type="verification",
                summary=f"Verification accuracy: {report.prediction_accuracy:.1%}",
                details={
                    "prediction_id": inp.prediction_id,
                    "prediction_accuracy": report.prediction_accuracy,
                    "actual_outcome": inp.actual_outcome,
                    "dimensions": report.dimensions,
                },
            )
            return True
        except Exception as exc:
            log.debug("Graph feedback failed: %s", exc)
            return False

    async def _send_to_replay(self, inp: VerificationInput, report: VerificationReport) -> bool:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="simulation.prediction_feedback",
                agent="enterprise_verification_intelligence",
                status="completed",
                message=f"Verification report: {report.report_id} accuracy={report.prediction_accuracy:.1%}",
                execution_id=inp.execution_id,
                metadata={
                    "report_id": report.report_id,
                    "prediction_id": inp.prediction_id,
                    "execution_id": inp.execution_id,
                    "repository": inp.repository,
                    "prediction_accuracy": report.prediction_accuracy,
                    "overall_confidence": report.overall_confidence,
                    "actual_outcome": inp.actual_outcome,
                },
            )
            return True
        except Exception as exc:
            log.debug("Replay feedback failed: %s", exc)
            return False

    async def _send_to_recommendations(
        self, inp: VerificationInput, report: VerificationReport, attribution: Optional[FailureAttribution] = None,
    ) -> bool:
        try:
            from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
            if not report.prediction_accuracy >= 0.7 and attribution:
                rec = enterprise_recommendation_engine._add_if_new(
                    type(enterprise_recommendation_engine).Recommendation(
                        category="verification",
                        title=f"Prediction accuracy gap: {attribution.primary_reason}",
                        description=f"Verification for {inp.repository} (execution {inp.execution_id}) "
                                    f"showed accuracy {report.prediction_accuracy:.1%}. "
                                    f"Primary reason: {attribution.primary_reason}",
                        reason=f"Accuracy {report.prediction_accuracy:.1%} below 70% threshold",
                        evidence=[{
                            "source": "verification_intelligence",
                            "report_id": report.report_id,
                            "execution_id": inp.execution_id,
                            "prediction_accuracy": report.prediction_accuracy,
                            "failure_reason": inp.actual_failure_reason,
                        }],
                        confidence=0.7,
                        risk="medium",
                        priority="medium",
                        source="verification",
                    )
                )
                return bool(rec)
            return False
        except Exception as exc:
            log.debug("Recommendation feedback failed: %s", exc)
            return False


# =============================================================================
# Phase 5 — Failure Attribution
# =============================================================================


class FailureAttributor:
    """Determine WHY a prediction failed."""

    PATTERNS: List[Tuple[List[str], str, str, str]] = [
        (["infrastructure", "terraform", "helm"], "infrastructure_issue",
         "Unexpected infrastructure issue", "Improve infrastructure change detection and add pre-flight validation"),
        (["traffic", "load", "scale", "latency"], "traffic_spike",
         "Unexpected traffic spike", "Add traffic pattern analysis to prediction model"),
        (["dependency", "api", "integration"], "dependency_analysis",
         "Incorrect dependency analysis", "Expand dependency graph coverage and add runtime dependency verification"),
        (["unknown", "new_service", "onboarding"], "missing_history",
         "Missing historical data", "Seed prediction with conservative defaults for unseen services"),
        (["database", "migration", "schema"], "database_migration",
         "Database migration complexity understated", "Add migration dry-run validation before prediction"),
        (["rollback", "revert"], "rollback_failure",
         "Incorrect rollout strategy", "Evaluate rollback成功率 of chosen strategy against historical data"),
        (["config", "environment", "variable"], "configuration_error",
         "Configuration drift between environments", "Add configuration validation to prediction pipeline"),
        (["auth", "permission", "rbac"], "authorization_failure",
         "Missing authorization configuration", "Include authorization checks in deployment planning"),
        (["timeout", "time_out", "deadline"], "timeout",
         "Operation timed out during execution", "Review timeout thresholds and add deadline monitoring"),
        (["memory", "oom", "crash"], "resource_exhaustion",
         "Resource limits exceeded during execution", "Adjust resource request/limit recommendations"),
    ]

    def attribute(self, inp: VerificationInput, dimensions: List[DimensionAccuracy]) -> FailureAttribution:
        reasons: List[str] = []
        category = "unknown"
        suggested = "Review prediction model inputs"

        failed_dimensions = [d for d in dimensions if d.accuracy < 0.5]
        if not failed_dimensions:
            return FailureAttribution(
                attribution_id=f"fa-{_id()}",
                verification_id=inp.verification_id,
                primary_reason="Prediction matched reality within acceptable tolerance",
                category="accurate",
                confidence=0.9,
            )

        failure_text = (inp.actual_failure_reason or "").lower()
        change_text = " ".join(c.lower() for c in inp.change_categories)
        service_text = " ".join(s.lower() for s in inp.changed_services)
        combined = f"{failure_text} {change_text} {service_text}"

        for keywords, cat, reason, fix in self.PATTERNS:
            if any(k in combined for k in keywords):
                category = cat
                reasons.append(reason)
                suggested = fix
                break

        if not reasons:
            if inp.actual_rolled_back:
                category = "rollback"
                reasons.append("Rollback occurred — deployment strategy may need adjustment")
                suggested = "Review rollback triggers and consider blue-green or canary deployment"
            elif not inp.actual_success and inp.predicted_success > 0.7:
                category = "overconfidence"
                reasons.append("Prediction was overconfident — actual execution failed unexpectedly")
                suggested = "Increase risk penalty for similar change categories"
            else:
                category = "unknown_failure"
                reasons.append("Prediction accuracy gap with no clear attribution pattern")
                suggested = "Review execution logs and expand attribution patterns"

        confidence = _clamp(0.5 + 0.1 * (6 - len(failed_dimensions)), 0.3, 0.95)

        return FailureAttribution(
            attribution_id=f"fa-{_id()}",
            verification_id=inp.verification_id,
            primary_reason=reasons[0] if reasons else "Unknown",
            secondary_reasons=reasons[1:] if len(reasons) > 1 else [],
            category=category,
            confidence=confidence,
            suggested_fix=suggested,
        )


# =============================================================================
# Phase 6 — Scorecard Tracker
# =============================================================================


class ScorecardTracker:
    """Track engineering reliability scorecards across dimensions."""

    def __init__(self) -> None:
        self._scorecards: Dict[str, Dict[str, ScorecardEntry]] = defaultdict(dict)

    def record(self, inp: VerificationInput) -> List[ScorecardEntry]:
        """Record verification outcome into all applicable scorecards."""
        entries: List[ScorecardEntry] = []
        entities = self._resolve_entities(inp)

        for dimension, entity in entities:
            existing = self._scorecards[dimension].get(entity)
            if existing:
                total = existing.total_deployments + 1
                success = existing.successful_deployments + (1 if inp.actual_success else 0)
                failed = existing.failed_deployments + (0 if inp.actual_success else (0 if inp.actual_rolled_back else 1))
                rolled = existing.rolled_back_deployments + (1 if inp.actual_rolled_back else 0)
            else:
                total = 1
                success = 1 if inp.actual_success else 0
                failed = 0 if inp.actual_success else (0 if inp.actual_rolled_back else 1)
                rolled = 1 if inp.actual_rolled_back else 0

            reliability = success / total if total > 0 else 1.0

            prev_score = existing.reliability_score if existing else 1.0
            if reliability > prev_score + 0.05:
                trend = "improving"
            elif reliability < prev_score - 0.05:
                trend = "declining"
            else:
                trend = "stable"

            entry = ScorecardEntry(
                dimension=dimension,
                entity=entity,
                total_deployments=total,
                successful_deployments=success,
                failed_deployments=failed,
                rolled_back_deployments=rolled,
                reliability_score=round(reliability, 3),
                trend=trend,
                last_updated=_now(),
            )
            self._scorecards[dimension][entity] = entry
            entries.append(entry)

        return entries

    def _resolve_entities(self, inp: VerificationInput) -> List[Tuple[str, str]]:
        entities: List[Tuple[str, str]] = []
        if inp.repository:
            entities.append(("repository", inp.repository))
        if inp.team:
            entities.append(("team", inp.team))
        else:
            repo_parts = inp.repository.split("/")
            if len(repo_parts) >= 2:
                entities.append(("team", repo_parts[0]))
        if inp.service:
            entities.append(("service", inp.service))
        if inp.changed_services:
            for svc in inp.changed_services:
                entities.append(("service", svc))
        entities.append(("deployment", inp.environment or "production"))
        if inp.has_infrastructure_changes:
            entities.append(("infrastructure", inp.repository))
        pipeline_name = f"{inp.repository}-pipeline"
        entities.append(("pipeline", pipeline_name))
        return entities

    def get_scorecard(self, dimension: str = "", entity: str = "") -> List[Dict[str, Any]]:
        results: List[ScorecardEntry] = []
        for dim, entities in self._scorecards.items():
            if dimension and dim != dimension:
                continue
            for ent, entry in entities.items():
                if entity and ent != entity:
                    continue
                results.append(entry)
        return [asdict(r) for r in results]

    def get_summary(self) -> Dict[str, Any]:
        total_entries = sum(len(v) for v in self._scorecards.values())
        if total_entries == 0:
            return {"total_entries": 0, "average_reliability": 0, "dimensions": {}}

        dim_summary = {}
        overall_total = 0
        overall_success = 0
        for dim, entities in self._scorecards.items():
            entries = list(entities.values())
            avg = sum(e.reliability_score for e in entries) / len(entries) if entries else 0
            dim_summary[dim] = {
                "total_entries": len(entries),
                "average_reliability": round(avg, 3),
                "declining": sum(1 for e in entries if e.trend == "declining"),
                "improving": sum(1 for e in entries if e.trend == "improving"),
            }
            overall_total += sum(e.total_deployments for e in entries)
            overall_success += sum(e.successful_deployments for e in entries)

        return {
            "total_entries": total_entries,
            "average_reliability": round(overall_success / overall_total, 3) if overall_total > 0 else 0,
            "dimensions": dim_summary,
        }


# =============================================================================
# Phase 7 — Executive Dashboard
# =============================================================================


@dataclass(frozen=True)
class ExecutiveDashboard:
    total_verifications: int = 0
    prediction_accuracy_percent: float = 0.0
    decision_accuracy_percent: float = 0.0
    deployment_success_percent: float = 0.0
    learning_improvement_percent: float = 0.0
    top_incorrect_predictions: List[Dict[str, Any]] = field(default_factory=list)
    top_correct_predictions: List[Dict[str, Any]] = field(default_factory=list)
    confidence_trend: List[Dict[str, Any]] = field(default_factory=list)
    accuracy_by_dimension: Dict[str, float] = field(default_factory=dict)
    scorecard_summary: Dict[str, Any] = field(default_factory=dict)


class DashboardGenerator:
    """Generate the executive dashboard from stored verification data."""

    def __init__(self) -> None:
        self._history: List[VerificationReport] = []
        self._max_history = 500

    def add_report(self, report: VerificationReport) -> None:
        self._history.append(report)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def generate(self, scorecard_tracker: ScorecardTracker) -> ExecutiveDashboard:
        n = len(self._history)
        if n == 0:
            return ExecutiveDashboard()

        avg_pred_acc = sum(r.prediction_accuracy for r in self._history) / n
        avg_dec_acc = sum(r.decision_accuracy for r in self._history) / n
        avg_dep_acc = sum(r.deployment_accuracy for r in self._history) / n

        # Improvement trend (last 10 vs previous 10)
        recent = self._history[-10:] if n >= 10 else self._history
        older = self._history[-20:-10] if n >= 20 else self._history[:-10] if n > 10 else []
        recent_avg = sum(r.prediction_accuracy for r in recent) / len(recent) if recent else 0
        older_avg = sum(r.prediction_accuracy for r in older) / len(older) if older else recent_avg
        improvement = recent_avg - older_avg

        # Top correct/incorrect
        sorted_by_acc = sorted(self._history, key=lambda r: r.prediction_accuracy)
        top_incorrect = [
            {"execution_id": r.execution_id, "repository": r.repository, "accuracy": r.prediction_accuracy}
            for r in sorted_by_acc[:5]
        ]
        top_correct = [
            {"execution_id": r.execution_id, "repository": r.repository, "accuracy": r.prediction_accuracy}
            for r in sorted_by_acc[-5:]
        ][::-1]

        # Confidence trend (last 20 points)
        conf_trend = [
            {"index": i, "accuracy": r.prediction_accuracy, "confidence": r.overall_confidence}
            for i, r in enumerate(self._history[-20:])
        ]

        # Accuracy by dimension
        dim_accs: Dict[str, List[float]] = defaultdict(list)
        for r in self._history:
            for d in r.dimensions:
                dim_accs[d["dimension"]].append(d["accuracy"])
        acc_by_dim = {dim: round(sum(vals) / len(vals), 3) for dim, vals in dim_accs.items()}

        return ExecutiveDashboard(
            total_verifications=n,
            prediction_accuracy_percent=round(avg_pred_acc * 100, 1),
            decision_accuracy_percent=round(avg_dec_acc * 100, 1),
            deployment_success_percent=round(avg_dep_acc * 100, 1),
            learning_improvement_percent=round(improvement * 100, 1),
            top_incorrect_predictions=top_incorrect,
            top_correct_predictions=top_correct,
            confidence_trend=conf_trend,
            accuracy_by_dimension=acc_by_dim,
            scorecard_summary=scorecard_tracker.get_summary(),
        )


# =============================================================================
# Phase 8 — Continuous Improvement
# =============================================================================


@dataclass(frozen=True)
class ImprovementSuggestion:
    suggestion_id: str = ""
    category: str = ""
    title: str = ""
    description: str = ""
    severity: str = "medium"
    estimated_impact: str = ""


class ContinuousImprover:
    """Analyze verification data to identify weak points and suggest improvements."""

    def analyze(self, dashboard: ExecutiveDashboard, history: List[VerificationReport]) -> List[ImprovementSuggestion]:
        suggestions: List[ImprovementSuggestion] = []

        # Weak prediction models
        if dashboard.prediction_accuracy_percent < 70:
            suggestions.append(ImprovementSuggestion(
                suggestion_id=f"is-{_id()}",
                category="prediction_model",
                title="Prediction accuracy below threshold",
                description=f"Overall prediction accuracy is {dashboard.prediction_accuracy_percent:.1f}% (target: 70%). "
                            "Review prediction model weights and add more historical data points.",
                severity="high",
                estimated_impact="Improving prediction accuracy directly improves decision quality",
            ))

        # Weak dimensions
        for dim, acc in dashboard.accuracy_by_dimension.items():
            if acc < 0.6:
                suggestions.append(ImprovementSuggestion(
                    suggestion_id=f"is-{_id()}",
                    category=f"weak_{dim}_prediction",
                    title=f"Weak {dim} prediction accuracy",
                    description=f"Accuracy for '{dim}' dimension is {acc:.1%}. Consider adjusting {dim} prediction factors.",
                    severity="medium",
                    estimated_impact=f"Better {dim} predictions improve overall verification score",
                ))

        # Weak deployment strategies
        if history:
            strategy_results: Dict[str, List[float]] = defaultdict(list)
            for r in history:
                next((h for h in self._get_inputs() if False), None)
            for r in history:
                for d in r.dimensions:
                    if d["dimension"] == "success":
                        strategy_results["general"].append(d["accuracy"])
            for strat, accs in strategy_results.items():
                avg = sum(accs) / len(accs) if accs else 0
                if avg < 0.6:
                    suggestions.append(ImprovementSuggestion(
                        suggestion_id=f"is-{_id()}",
                        category="weak_strategy",
                        title="Low success rate for deployment strategy",
                        description=f"Average accuracy for is {avg:.1%}. Consider alternative strategies or pre-validation.",
                        severity="medium",
                        estimated_impact="Better strategy selection reduces rollback risk",
                    ))

        # Weak approval rules
        if dashboard.deployment_success_percent < 80:
            suggestions.append(ImprovementSuggestion(
                suggestion_id=f"is-{_id()}",
                category="approval_rules",
                title="Deployment success rate below target",
                description=f"Deployment success is {dashboard.deployment_success_percent:.1f}% (target: 80%). "
                            "Review approval criteria and deployment gating rules.",
                severity="medium",
                estimated_impact="Stronger approval rules prevent failed deployments",
            ))

        # Weak risk models
        risk_acc = dashboard.accuracy_by_dimension.get("risk", 1.0)
        if risk_acc < 0.6:
            suggestions.append(ImprovementSuggestion(
                suggestion_id=f"is-{_id()}",
                category="risk_model",
                title="Risk assessment accuracy below threshold",
                description=f"Risk prediction accuracy is {risk_acc:.1%}. Review risk scoring factors and weightings.",
                severity="high",
                estimated_impact="Accurate risk assessment prevents high-risk deployments",
            ))

        return suggestions

    def _get_inputs(self) -> List[Any]:
        return []


# =============================================================================
# Enterprise Verification Intelligence — Main Facade
# =============================================================================


class EnterpriseVerificationIntelligence:
    """Main facade for the Enterprise Verification Intelligence service."""

    def __init__(self) -> None:
        self.comparator = PredictionRealityComparator()
        self.report_generator = VerificationReportGenerator()
        self.confidence_adjuster = ConfidenceAdjuster()
        self.feedback_dispatcher = LearningFeedbackDispatcher()
        self.attributor = FailureAttributor()
        self.scorecard_tracker = ScorecardTracker()
        self.dashboard_generator = DashboardGenerator()
        self.improver = ContinuousImprover()
        self._verification_store: Dict[str, VerificationInput] = {}
        self._report_store: Dict[str, VerificationReport] = {}

    async def verify(
        self,
        execution_id: str,
        prediction_id: str,
        repository: str = "",
        team: str = "",
        service: str = "",
        environment: str = "",
        predicted_success: float = 0.5,
        actual_success: bool = False,
        predicted_duration_seconds: float = 600.0,
        actual_duration_seconds: float = 0.0,
        predicted_rollback_probability: float = 0.1,
        actual_rolled_back: bool = False,
        predicted_risk_score: float = 0.3,
        actual_risk_score: float = 0.0,
        predicted_cost_increase: float = 0.0,
        actual_cost_increase: float = 0.0,
        predicted_strategy: str = "",
        actual_strategy: str = "",
        actual_outcome: str = "",
        actual_failure_reason: str = "",
        change_categories: Optional[List[str]] = None,
        changed_services: Optional[List[str]] = None,
        has_db_migrations: bool = False,
        has_infrastructure_changes: bool = False,
        decision_accuracy: float = 0.0,
    ) -> Dict[str, Any]:
        """Run full verification — compare prediction vs reality, generate report, adjust confidence."""
        verification_id = f"vrf-{_id()}"

        inp = VerificationInput(
            verification_id=verification_id,
            execution_id=execution_id,
            prediction_id=prediction_id,
            repository=repository,
            team=team,
            service=service,
            environment=environment,
            predicted_success=predicted_success,
            actual_success=actual_success,
            predicted_duration_seconds=predicted_duration_seconds,
            actual_duration_seconds=actual_duration_seconds,
            predicted_rollback_probability=predicted_rollback_probability,
            actual_rolled_back=actual_rolled_back,
            predicted_risk_score=predicted_risk_score,
            actual_risk_score=actual_risk_score,
            predicted_cost_increase=predicted_cost_increase,
            actual_cost_increase=actual_cost_increase,
            predicted_strategy=predicted_strategy,
            actual_strategy=actual_strategy,
            actual_outcome=actual_outcome,
            actual_failure_reason=actual_failure_reason,
            change_categories=change_categories or [],
            changed_services=changed_services or [],
            has_db_migrations=has_db_migrations,
            has_infrastructure_changes=has_infrastructure_changes,
        )
        self._verification_store[verification_id] = inp

        # Phase 1 — Compare prediction vs reality
        dimensions, overall_accuracy, reasoning = self.comparator.compare(inp)

        # Phase 5 — Attribute failures
        attribution = self.attributor.attribute(inp, dimensions)

        # Phase 2 — Generate verification report
        report = self.report_generator.generate(inp, dimensions, overall_accuracy, reasoning, decision_accuracy)
        self._report_store[report.report_id] = report
        self.dashboard_generator.add_report(report)

        # Phase 3 — Adjust confidence
        confidence_adjustment = self.confidence_adjuster.adjust(report, dimensions)

        # Phase 6 — Update scorecards
        scorecard_entries = self.scorecard_tracker.record(inp)

        # Phase 4 — Dispatch learning feedback
        feedback_results = await self.feedback_dispatcher.dispatch(inp, report, attribution)

        # Phase 8 — Analyze for continuous improvement suggestions
        dashboard = self.dashboard_generator.generate(self.scorecard_tracker)
        suggestions = self.improver.analyze(dashboard, self.dashboard_generator._history)

        # Emit verification event
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="engineering.verification_completed",
                agent="enterprise_verification_intelligence",
                status="completed",
                message=f"Verification {verification_id}: accuracy={report.prediction_accuracy:.1%}",
                execution_id=execution_id,
                metadata={
                    "verification_id": verification_id,
                    "report_id": report.report_id,
                    "prediction_id": prediction_id,
                    "repository": repository,
                    "prediction_accuracy": report.prediction_accuracy,
                    "overall_confidence": report.overall_confidence,
                    "actual_outcome": actual_outcome,
                    "attribution_category": attribution.category,
                },
            )
        except Exception:
            pass

        return {
            "verification_id": verification_id,
            "execution_id": execution_id,
            "prediction_id": prediction_id,
            "report": report.to_dict(),
            "confidence_adjustment": asdict(confidence_adjustment),
            "attribution": asdict(attribution),
            "scorecard_entries": [asdict(e) for e in scorecard_entries],
            "feedback_results": feedback_results,
            "improvement_suggestions": [asdict(s) for s in suggestions],
            "timestamp": _now(),
        }

    async def get_verification(self, verification_id: str) -> Optional[Dict[str, Any]]:
        inp = self._verification_store.get(verification_id)
        if not inp:
            return None
        return asdict(inp)

    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        report = self._report_store.get(report_id)
        if not report:
            return None
        return report.to_dict()

    async def list_verifications(self) -> List[Dict[str, Any]]:
        results = []
        for vid, inp in self._verification_store.items():
            results.append({
                "verification_id": vid,
                "execution_id": inp.execution_id,
                "prediction_id": inp.prediction_id,
                "repository": inp.repository,
                "actual_outcome": inp.actual_outcome,
                "created_at": inp.created_at,
            })
        results.sort(key=lambda r: r["created_at"], reverse=True)
        return results

    async def get_scorecards(self, dimension: str = "", entity: str = "") -> List[Dict[str, Any]]:
        return self.scorecard_tracker.get_scorecard(dimension, entity)

    async def get_scorecard_summary(self) -> Dict[str, Any]:
        return self.scorecard_tracker.get_summary()

    async def get_dashboard(self) -> Dict[str, Any]:
        dashboard = self.dashboard_generator.generate(self.scorecard_tracker)
        return asdict(dashboard)

    async def get_improvement_suggestions(self) -> List[Dict[str, Any]]:
        dashboard = self.dashboard_generator.generate(self.scorecard_tracker)
        suggestions = self.improver.analyze(dashboard, self.dashboard_generator._history)
        return [asdict(s) for s in suggestions]


# =============================================================================
# Singleton
# =============================================================================

enterprise_verification_intelligence = EnterpriseVerificationIntelligence()
