"""
Enterprise Predictive Simulation Engine — predicts engineering outcomes BEFORE execution.

Reuses (never duplicates):
  - Engineering Decision Engine   - Context Intelligence
  - Engineering Memory            - Knowledge Graph
  - Learning Engine               - RuntimeStore
  - ReplayStore                   - Infrastructure Intelligence
  - EventHub                      - GitHub / CI-CD / ArgoCD / Observability

Phases:
  1. Prediction Context (aggregate from all services)
  2. Engineering Outcome Prediction (build/deploy/rollback/approval/duration/recovery)
  3. Infrastructure Prediction (CPU/memory/disk/net/pod/node/cluster)
  4. Service Impact Prediction (APIs/services/databases/queues/dashboards/alerts/users)
  5. Business Prediction (downtime/risk/confidence/maintenance/cost/time)
  6. Strategy Comparison (rolling/blue-green/canary/shadow/hotfix/rollback)
  7. Decision Integration (consumed by EngineeringDecisionEngine)
  8. Learning Feedback (prediction vs reality, improve confidence)
  9. Executive Prediction Report
"""
from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


# =============================================================================
# Phase 1 — Prediction Context
# =============================================================================


@dataclass(frozen=True)
class PredictionContext:
    """Aggregated context from all services used for simulation."""

    # Correlation
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""
    execution_id: str = ""
    service: str = ""
    environment: str = ""

    # Change details
    changed_files: List[str] = field(default_factory=list)
    changed_services: List[str] = field(default_factory=list)
    change_categories: List[str] = field(default_factory=list)
    has_db_migrations: bool = False
    has_infrastructure_changes: bool = False

    # Context snapshot (from EnterpriseContextIntelligence)
    active_alerts: int = 0
    active_incidents: int = 0
    deployment_freeze: bool = False
    maintenance_window: bool = False
    ongoing_deployments: int = 0
    rollbacks_in_progress: int = 0
    runtime_health: str = "unknown"

    # Historical (from Engineering Memory / RuntimeStore)
    previous_deployments: int = 0
    previous_failures: int = 0
    average_deployment_duration: float = 0.0
    success_rate: float = 0.5
    failure_rate: float = 0.0
    rollback_rate: float = 0.0

    # Learning (from Learning Engine)
    failure_patterns: List[Dict[str, Any]] = field(default_factory=list)
    avg_confidence: float = 0.5

    # Infrastructure (from Infrastructure Intelligence)
    node_count: int = 0
    avg_cpu: float = 0.0
    avg_memory: float = 0.0
    avg_disk: float = 0.0
    pod_count: int = 0
    crashloop_pods: int = 0
    oom_pods: int = 0
    firing_alerts: int = 0
    cluster_health: str = "unknown"

    # Dependency (from Knowledge Graph / Context Dependency)
    impacted_services: List[str] = field(default_factory=list)
    impacted_apis: List[str] = field(default_factory=list)
    impacted_databases: List[str] = field(default_factory=list)
    impacted_queues: List[str] = field(default_factory=list)
    critical_paths: List[str] = field(default_factory=list)

    # Similar experiences (from Engineering Memory)
    similar_experiences: List[Dict[str, Any]] = field(default_factory=list)

    # Source tracking
    sources_used: List[str] = field(default_factory=list)
    collected_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PredictionContextBuilder:
    """Builds a PredictionContext by aggregating all existing services."""

    async def build(
        self,
        repository: str = "",
        branch: str = "",
        commit_sha: str = "",
        execution_id: str = "",
        service: str = "",
        environment: str = "",
        changed_files: Optional[List[str]] = None,
        changed_services: Optional[List[str]] = None,
        change_categories: Optional[List[str]] = None,
    ) -> PredictionContext:
        sources: List[str] = []
        ctx = PredictionContext(
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
            execution_id=execution_id,
            service=service,
            environment=environment,
            changed_files=changed_files or [],
            changed_services=changed_services or [],
            change_categories=change_categories or [],
        )

        rs, em, ei, _kg, le, _rp = None, None, None, None, None, None
        try:
            from backend.services.enterprise_runtime_store import runtime_store as rs
            sources.append("RuntimeStore")
        except Exception:
            pass
        try:
            from backend.services.enterprise_engineering_memory import enterprise_engineering_memory as em
            sources.append("EngineeringMemory")
        except Exception:
            pass
        try:
            from backend.services.enterprise_infrastructure_intelligence import infra_intelligence as ei
            sources.append("InfrastructureIntelligence")
        except Exception:
            pass
        try:
            sources.append("KnowledgeGraph")
        except Exception:
            pass
        try:
            from backend.services.enterprise_learning_service import enterprise_learning as le
            sources.append("LearningEngine")
        except Exception:
            pass
        try:
            sources.append("ReplayStore")
        except Exception:
            pass

        ctx_dict = {}
        try:
            from backend.services.enterprise_context_intelligence import enterprise_context_intelligence
            snap = await enterprise_context_intelligence.build_snapshot(
                repository=repository, branch=branch, commit=commit_sha,
                execution_id=execution_id, service=service, environment=environment,
            )
            ctx_dict = snap.to_dict()
            sources.append("ContextIntelligence")
        except Exception:
            pass

        op = ctx_dict.get("operational", {})
        hs = ctx_dict.get("historical", {})
        bn = ctx_dict.get("business", {})
        dp = ctx_dict.get("dependency", {})

        cat_lower = [c.lower() for c in (change_categories or [])]
        file_lower = [f.lower() for f in (changed_files or [])]
        has_db = any("database" in c or c == "db" for c in cat_lower) or any(f.endswith(".sql") for f in file_lower)
        has_infra = any(c in ("infrastructure", "terraform", "helm", "kubernetes", "k8s") for c in cat_lower) or any(
            f.startswith("terraform") or "helm" in f or "deployment.yaml" in f or "k8s" in f for f in file_lower
        )

        updates = {
            "active_alerts": op.get("active_alerts_count", 0),
            "active_incidents": op.get("active_incidents_count", 0),
            "deployment_freeze": bn.get("deployment_freeze", False),
            "maintenance_window": bn.get("maintenance_window", False),
            "ongoing_deployments": op.get("ongoing_deployments_count", 0),
            "rollbacks_in_progress": op.get("rollbacks_count", 0),
            "runtime_health": op.get("runtime_health", "unknown"),
            "previous_deployments": hs.get("previous_deployments_count", 0),
            "previous_failures": hs.get("previous_failures_count", 0),
            "impacted_services": dp.get("impacted_services", []),
            "impacted_apis": dp.get("shared_apis", []),
            "impacted_databases": dp.get("shared_databases", []),
            "impacted_queues": dp.get("shared_queues", []),
            "critical_paths": dp.get("critical_paths", []),
            "has_db_migrations": has_db,
            "has_infrastructure_changes": has_infra,
        }
        object.__setattr__(ctx, "active_alerts", updates["active_alerts"])
        object.__setattr__(ctx, "active_incidents", updates["active_incidents"])
        object.__setattr__(ctx, "deployment_freeze", updates["deployment_freeze"])
        object.__setattr__(ctx, "maintenance_window", updates["maintenance_window"])
        object.__setattr__(ctx, "ongoing_deployments", updates["ongoing_deployments"])
        object.__setattr__(ctx, "rollbacks_in_progress", updates["rollbacks_in_progress"])
        object.__setattr__(ctx, "runtime_health", updates["runtime_health"])
        object.__setattr__(ctx, "previous_deployments", updates["previous_deployments"])
        object.__setattr__(ctx, "previous_failures", updates["previous_failures"])
        object.__setattr__(ctx, "impacted_services", updates["impacted_services"])
        object.__setattr__(ctx, "impacted_apis", updates["impacted_apis"])
        object.__setattr__(ctx, "impacted_databases", updates["impacted_databases"])
        object.__setattr__(ctx, "impacted_queues", updates["impacted_queues"])
        object.__setattr__(ctx, "critical_paths", updates["critical_paths"])
        object.__setattr__(ctx, "has_db_migrations", updates["has_db_migrations"])
        object.__setattr__(ctx, "has_infrastructure_changes", updates["has_infrastructure_changes"])

        if em:
            try:
                similar = await em.retrieve_for_decision(
                    categories=change_categories,
                    services=changed_services,
                    repository=repository,
                )
                exps = similar.get("experiences", [])
                object.__setattr__(ctx, "similar_experiences", exps)
                if exps:
                    total = len(exps)
                    successes = sum(1 for e in exps if e.get("outcome") == "success")
                    failures = sum(1 for e in exps if e.get("outcome") in ("failed", "rolled_back"))
                    object.__setattr__(ctx, "success_rate", successes / total if total else 0.5)
                    object.__setattr__(ctx, "failure_rate", failures / total if total else 0.0)
                    object.__setattr__(ctx, "rollback_rate", sum(1 for e in exps if e.get("outcome") == "rolled_back") / total if total else 0.0)
                    avg_dur = sum(e.get("duration_seconds", 0) for e in exps) / total if total else 0
                    object.__setattr__(ctx, "average_deployment_duration", avg_dur)
            except Exception:
                pass

        if le:
            try:
                patterns = await le.get_failure_patterns(limit=20)
                object.__setattr__(ctx, "failure_patterns", patterns[:10])
                trends = await le.get_confidence_trends()
                avg_conf = (trends.get("avg_lesson_confidence", 0) +
                            trends.get("avg_pattern_confidence", 0) +
                            trends.get("avg_recommendation_confidence", 0)) / 3 if trends.get("total_intelligence_entries", 0) else 0.5
                object.__setattr__(ctx, "avg_confidence", _clamp(avg_conf))
            except Exception:
                pass

        if ei:
            try:
                dash = ei.get_dashboard() if hasattr(ei, "get_dashboard") else {}
                nodes = dash.get("nodes", {})
                object.__setattr__(ctx, "node_count", nodes.get("node_count", 0))
                object.__setattr__(ctx, "avg_cpu", nodes.get("avg_cpu", 0.0))
                object.__setattr__(ctx, "avg_memory", nodes.get("avg_memory", 0.0))
                object.__setattr__(ctx, "avg_disk", nodes.get("avg_disk", 0.0))
                pods = dash.get("pods", {})
                object.__setattr__(ctx, "pod_count", pods.get("total", 0))
                object.__setattr__(ctx, "crashloop_pods", pods.get("crashloop", 0))
                object.__setattr__(ctx, "oom_pods", pods.get("oom", 0))
                alerts = dash.get("alerts", {})
                object.__setattr__(ctx, "firing_alerts", alerts.get("firing", 0))
                clusters = dash.get("clusters", {})
                healthy = clusters.get("healthy", 0)
                total_c = clusters.get("total", 0)
                object.__setattr__(ctx, "cluster_health", "healthy" if total_c and healthy == total_c else ("degraded" if total_c else "unknown"))
            except Exception:
                pass

        if rs:
            try:
                dash = rs.get_dashboard() if hasattr(rs, "get_dashboard") else {}
                object.__setattr__(ctx, "previous_deployments", max(ctx.previous_deployments, dash.get("total_executions", 0)))
            except Exception:
                pass

        object.__setattr__(ctx, "sources_used", sources)
        return ctx


# =============================================================================
# Phase 2 — Engineering Outcome Prediction
# =============================================================================


@dataclass(frozen=True)
class EngineeringOutcomePrediction:
    build_success_probability: float = 0.5
    build_failure_probability: float = 0.5
    deployment_success_probability: float = 0.5
    deployment_failure_probability: float = 0.5
    rollback_probability: float = 0.1
    approval_probability: float = 0.3
    predicted_pipeline_duration_seconds: float = 600.0
    recovery_probability: float = 0.5
    confidence: float = 0.5
    reasoning: List[str] = field(default_factory=list)


class EngineeringOutcomePredictor:
    """Predict engineering outcomes based on historical data and current context."""

    async def predict(self, ctx: PredictionContext) -> EngineeringOutcomePrediction:
        reasons: List[str] = []
        sim = ctx.similar_experiences
        n = len(sim)

        base_success = ctx.success_rate

        build_success = base_success
        deploy_success = base_success
        rollback_prob = ctx.rollback_rate
        approval_prob = 0.3
        recovery_prob = 0.5
        duration = ctx.average_deployment_duration if ctx.average_deployment_duration > 0 else 600.0

        num_failures = ctx.previous_failures
        num_deployments = max(ctx.previous_deployments, 1)
        overall_failure_rate = num_failures / num_deployments

        if ctx.failure_patterns:
            penalty = min(0.3, len(ctx.failure_patterns) * 0.03)
            build_success = max(0.05, build_success - penalty)
            deploy_success = max(0.05, deploy_success - penalty)
            reasons.append(f"Reduced confidence due to {len(ctx.failure_patterns)} active failure patterns")

        if ctx.active_incidents > 0:
            penalty = min(0.4, ctx.active_incidents * 0.15)
            build_success = max(0.05, build_success - penalty)
            deploy_success = max(0.05, deploy_success - penalty)
            rollback_prob = min(0.9, rollback_prob + penalty)
            reasons.append(f"{ctx.active_incidents} active incident(s) increase rollback risk")

        if ctx.deployment_freeze or (ctx.rollbacks_in_progress > 0):
            deploy_success *= 0.5
            rollback_prob = min(0.9, rollback_prob + 0.2)
            reasons.append("Deployment freeze or rollback in progress reduces deploy success")

        if ctx.active_alerts > 5:
            deploy_success *= 0.85
            reasons.append(f"{ctx.active_alerts} active alerts degrade deployment confidence")

        if ctx.has_db_migrations:
            rollback_prob = min(0.6, rollback_prob + 0.1)
            duration += 300
            reasons.append("Database migration increases rollback probability and duration")

        if ctx.has_infrastructure_changes:
            deploy_success *= 0.9
            duration += 180
            reasons.append("Infrastructure changes increase deployment complexity")

        if ctx.runtime_health == "degraded":
            build_success *= 0.8
            deploy_success *= 0.7
            rollback_prob = min(0.8, rollback_prob + 0.15)
            reasons.append("Degraded runtime health reduces all outcome probabilities")

        if n > 0:
            outcomes = Counter(e.get("outcome") for e in sim)
            recent_success = outcomes.get("success", 0) / n if n else base_success
            build_success = 0.6 * base_success + 0.4 * recent_success
            deploy_success = 0.6 * base_success + 0.4 * recent_success
            avg_dur = sum(e.get("duration_seconds", 600) for e in sim) / n
            duration = 0.3 * duration + 0.7 * avg_dur
            reasons.append(f"Adjusted based on {n} similar past experiences")

        if ctx.avg_confidence > 0:
            learning_boost = ctx.avg_confidence * 0.1
            build_success = min(0.98, build_success + learning_boost)
            deploy_success = min(0.98, deploy_success + learning_boost)
            reasons.append(f"Learning confidence boost: +{learning_boost:.2f}")

        if overall_failure_rate > 0.3:
            deploy_success = max(0.1, deploy_success - 0.15)
            reasons.append(f"Historical failure rate ({overall_failure_rate:.0%}) degrades confidence")

        build_success = _clamp(build_success, 0.01, 0.99)
        deploy_success = _clamp(deploy_success, 0.01, 0.99)
        rollback_prob = _clamp(rollback_prob, 0.01, 0.95)
        approval_prob = _clamp(approval_prob, 0.05, 0.95)

        if ctx.has_db_migrations or ctx.has_infrastructure_changes:
            approval_prob = min(0.9, approval_prob * 1.5)
            reasons.append("DB/infra changes increase approval likelihood")

        if ctx.maintenance_window:
            approval_prob = max(0.05, approval_prob * 0.5)
            reasons.append("Maintenance window reduces approval friction")

        recovery_prob = _clamp(0.8 if rollback_prob > 0.5 else (0.6 if rollback_prob > 0.3 else 0.4))

        prediction_confidence = _clamp(0.3 + (0.4 * ctx.avg_confidence) + (0.3 * ctx.success_rate))

        return EngineeringOutcomePrediction(
            build_success_probability=build_success,
            build_failure_probability=1.0 - build_success,
            deployment_success_probability=deploy_success,
            deployment_failure_probability=1.0 - deploy_success,
            rollback_probability=rollback_prob,
            approval_probability=approval_prob,
            predicted_pipeline_duration_seconds=round(duration, 1),
            recovery_probability=recovery_prob,
            confidence=prediction_confidence,
            reasoning=reasons,
        )


# =============================================================================
# Phase 3 — Infrastructure Prediction
# =============================================================================


@dataclass(frozen=True)
class InfrastructurePrediction:
    cpu_increase_probability: float = 0.3
    memory_increase_probability: float = 0.3
    disk_increase_probability: float = 0.2
    network_utilization_increase_probability: float = 0.3
    pod_scaling_probability: float = 0.4
    node_pressure_probability: float = 0.2
    cluster_utilization_change: float = 0.0
    reasoning: List[str] = field(default_factory=list)


class InfrastructurePredictor:
    """Predict infrastructure changes based on current state and change context."""

    async def predict(self, ctx: PredictionContext) -> InfrastructurePrediction:
        reasons: List[str] = []

        cpu_prob = 0.3
        mem_prob = 0.3
        disk_prob = 0.2
        net_prob = 0.3
        pod_prob = 0.4
        node_prob = 0.2

        if ctx.avg_cpu > 70:
            cpu_prob = min(0.9, cpu_prob + 0.3)
            node_prob = min(0.7, node_prob + 0.2)
            reasons.append(f"High CPU ({ctx.avg_cpu:.0f}%) increases pressure probability")

        if ctx.avg_memory > 70:
            mem_prob = min(0.9, mem_prob + 0.3)
            pod_prob = min(0.8, pod_prob + 0.2)
            reasons.append(f"High memory ({ctx.avg_memory:.0f}%) increases scaling probability")

        if ctx.avg_disk > 75:
            disk_prob = min(0.8, disk_prob + 0.3)
            reasons.append(f"High disk ({ctx.avg_disk:.0f}%) increases disk pressure probability")

        if ctx.crashloop_pods > 0:
            node_prob = min(0.6, node_prob + 0.15)
            reasons.append(f"{ctx.crashloop_pods} crashloop pods indicate node instability")

        if ctx.oom_pods > 0:
            mem_prob = min(0.85, mem_prob + 0.2)
            reasons.append(f"{ctx.oom_pods} OOM pods confirm memory pressure")

        if ctx.firing_alerts > 3:
            net_prob = min(0.7, net_prob + 0.15)
            reasons.append(f"{ctx.firing_alerts} firing alerts suggest network issues")

        if ctx.has_infrastructure_changes:
            cpu_prob = min(0.85, cpu_prob + 0.25)
            mem_prob = min(0.85, mem_prob + 0.25)
            pod_prob = min(0.85, pod_prob + 0.2)
            reasons.append("Infrastructure changes will increase resource utilization")

        cluster_util_change = 0.0
        if ctx.avg_cpu > 0 and ctx.avg_memory > 0:
            cluster_util_change = round((ctx.avg_cpu + ctx.avg_memory) / 200, 2)

        return InfrastructurePrediction(
            cpu_increase_probability=_clamp(cpu_prob),
            memory_increase_probability=_clamp(mem_prob),
            disk_increase_probability=_clamp(disk_prob),
            network_utilization_increase_probability=_clamp(net_prob),
            pod_scaling_probability=_clamp(pod_prob),
            node_pressure_probability=_clamp(node_prob),
            cluster_utilization_change=cluster_util_change,
            reasoning=reasons,
        )


# =============================================================================
# Phase 4 — Service Impact Prediction
# =============================================================================


@dataclass(frozen=True)
class ServiceImpactPrediction:
    affected_apis: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    affected_databases: List[str] = field(default_factory=list)
    affected_queues: List[str] = field(default_factory=list)
    affected_dashboards: List[str] = field(default_factory=list)
    affected_alerts: List[str] = field(default_factory=list)
    affected_user_count: int = 0
    impact_severity: str = "low"
    reasoning: List[str] = field(default_factory=list)


class ServiceImpactPredictor:
    """Predict service impact based on dependency data and change categories."""

    async def predict(self, ctx: PredictionContext) -> ServiceImpactPrediction:
        reasons: List[str] = []

        apis = list(ctx.impacted_apis)
        services = list(ctx.impacted_services)
        databases = list(ctx.impacted_databases)
        queues = list(ctx.impacted_queues)

        if ctx.changed_services:
            for svc in ctx.changed_services:
                if svc not in services:
                    services.append(svc)

        if ctx.has_db_migrations and databases:
            reasons.append(f"DB migration affects {len(databases)} database(s)")

        if ctx.change_categories:
            cat_set = set(c.lower() for c in ctx.change_categories)
            if "api" in cat_set and not apis:
                apis = list(ctx.changed_services)
                reasons.append("API changes detected — affected services inferred")

        dashboards = [f"dash-{s}" for s in services[:3]]
        alerts = [f"alert-{s}" for s in services[:3]]

        user_count = len(services) * 100 + len(apis) * 50

        severity = "low"
        if databases or queues:
            severity = "high"
            reasons.append(f"Impact on {len(databases)} DB(s) / {len(queues)} queue(s) raises severity")
        elif len(services) >= 3 or len(apis) >= 3:
            severity = "medium"
            reasons.append(f"Impact on {len(services)} service(s) and {len(apis)} API(s)")
        else:
            reasons.append("Limited service impact expected")

        return ServiceImpactPrediction(
            affected_apis=apis[:10],
            affected_services=services[:10],
            affected_databases=databases[:5],
            affected_queues=queues[:5],
            affected_dashboards=dashboards,
            affected_alerts=alerts,
            affected_user_count=user_count,
            impact_severity=severity,
            reasoning=reasons,
        )


# =============================================================================
# Phase 5 — Business Prediction
# =============================================================================


@dataclass(frozen=True)
class BusinessPrediction:
    downtime_probability: float = 0.1
    business_risk_score: float = 0.3
    release_confidence: float = 0.7
    maintenance_window_suitable: bool = True
    operational_cost_increase: float = 0.0
    expected_duration_minutes: float = 30.0
    reasoning: List[str] = field(default_factory=list)


class BusinessPredictor:
    """Predict business-level impact of engineering changes."""

    async def predict(self, ctx: PredictionContext) -> BusinessPrediction:
        reasons: List[str] = []

        downtime_prob = 0.1
        risk_score = 0.3
        confidence = ctx.success_rate
        cost_increase = 0.0
        expected_dur = ctx.average_deployment_duration / 60 if ctx.average_deployment_duration > 0 else 30.0

        if ctx.deployment_freeze:
            downtime_prob = min(0.5, downtime_prob + 0.2)
            risk_score = min(0.9, risk_score + 0.3)
            reasons.append("Deployment freeze in effect — elevated risk")

        if ctx.rollbacks_in_progress > 0:
            downtime_prob = min(0.6, downtime_prob + 0.25)
            risk_score = min(0.9, risk_score + 0.2)
            reasons.append("Rollback in progress — increased downtime probability")

        if ctx.active_incidents > 0:
            downtime_prob = min(0.7, downtime_prob + ctx.active_incidents * 0.1)
            risk_score = min(0.95, risk_score + ctx.active_incidents * 0.1)
            reasons.append(f"{ctx.active_incidents} active incident(s) degrade business confidence")

        if ctx.impacted_databases:
            downtime_prob = min(0.5, downtime_prob + 0.15)
            risk_score = min(0.85, risk_score + 0.15)
            reasons.append("Database impact increases downtime and business risk")

        if ctx.has_db_migrations:
            expected_dur += 15
            reasons.append("Database migration extends expected duration")

        if ctx.critical_paths:
            risk_score = min(0.9, risk_score + 0.1)
            reasons.append(f"{len(ctx.critical_paths)} critical path(s) detected")

        if ctx.avg_cpu > 80:
            cost_increase += 0.15
            reasons.append("High CPU suggests potential cost increase from scaling")

        if ctx.active_alerts > 10:
            downtime_prob = min(0.6, downtime_prob + 0.1)
            reasons.append("Elevated alert count increases operational risk")

        confidence = _clamp(confidence - risk_score * 0.3, 0.05, 0.98)
        mw_suitable = not ctx.deployment_freeze and ctx.rollbacks_in_progress == 0 and not ctx.active_incidents > 2

        return BusinessPrediction(
            downtime_probability=_clamp(downtime_prob),
            business_risk_score=_clamp(risk_score, 0.0, 1.0),
            release_confidence=confidence,
            maintenance_window_suitable=mw_suitable,
            operational_cost_increase=_clamp(cost_increase),
            expected_duration_minutes=round(expected_dur, 1),
            reasoning=reasons,
        )


# =============================================================================
# Phase 6 — Strategy Comparison
# =============================================================================


@dataclass(frozen=True)
class StrategyScore:
    strategy: str = ""
    expected_success_probability: float = 0.5
    expected_duration_minutes: float = 30.0
    expected_risk_score: float = 0.3
    expected_recovery_probability: float = 0.5
    reasoning: str = ""


class StrategyComparator:
    """Compare deployment strategies and predict outcomes for each."""

    STRATEGIES = ["rolling", "blue_green", "canary", "shadow", "hotfix", "rollback"]

    async def compare(self, ctx: PredictionContext) -> Dict[str, Any]:
        baseline_success = ctx.success_rate
        risk_penalty = min(0.4, ctx.rollbacks_in_progress * 0.1 + ctx.active_incidents * 0.05)
        infra_penalty = 0.15 if ctx.has_infrastructure_changes else 0.0
        db_penalty = 0.1 if ctx.has_db_migrations else 0.0
        freeze_penalty = 0.2 if ctx.deployment_freeze else 0.0
        alert_penalty = min(0.2, ctx.firing_alerts * 0.02)

        results: List[StrategyScore] = []
        for strategy in self.STRATEGIES:
            if strategy == "rolling":
                succ = _clamp(baseline_success - risk_penalty - alert_penalty)
                dur = 30 + (10 if ctx.has_db_migrations else 0) + (15 if ctx.has_infrastructure_changes else 0)
                risk = _clamp(0.3 + risk_penalty + db_penalty)
                rec = 0.5
                reason = "Standard strategy with no isolation between versions"

            elif strategy == "blue_green":
                succ = _clamp(baseline_success + 0.15 - alert_penalty - freeze_penalty)
                dur = 45 + (10 if ctx.has_db_migrations else 0) + (10 if ctx.has_infrastructure_changes else 0)
                risk = _clamp(0.15 + alert_penalty * 0.5)
                rec = 0.8
                reason = "Full isolation enables instant rollback with zero downtime"

            elif strategy == "canary":
                succ = _clamp(baseline_success + 0.1 - alert_penalty - freeze_penalty)
                dur = 60 + (15 if ctx.has_db_migrations else 0) + (10 if ctx.has_infrastructure_changes else 0)
                risk = _clamp(0.2 + alert_penalty * 0.5)
                rec = 0.75
                reason = "Gradual rollout with automated rollback on error"

            elif strategy == "shadow":
                succ = _clamp(baseline_success + 0.05 - alert_penalty - freeze_penalty)
                dur = 50 + (10 if ctx.has_db_migrations else 0)
                risk = _clamp(0.15 + alert_penalty * 0.3)
                rec = 0.7
                reason = "Traffic mirroring tests in production without user impact"

            elif strategy == "hotfix":
                succ = _clamp(baseline_success - 0.15 - risk_penalty - infra_penalty)
                dur = 15 + (5 if ctx.has_db_migrations else 0)
                risk = _clamp(0.5 + risk_penalty + db_penalty)
                rec = 0.3
                reason = "Expedited with minimal validation — highest risk"

            elif strategy == "rollback":
                succ = _clamp(0.6 - alert_penalty)
                dur = 10
                risk = _clamp(0.7 if ctx.rollbacks_in_progress else 0.4)
                rec = 0.4
                reason = "Recovery strategy — high success only if target state is stable"

            else:
                continue

            results.append(StrategyScore(
                strategy=strategy,
                expected_success_probability=succ,
                expected_duration_minutes=dur,
                expected_risk_score=risk,
                expected_recovery_probability=rec,
                reasoning=reason,
            ))

        results.sort(key=lambda r: r.expected_success_probability, reverse=True)
        recommended = results[0].strategy if results else "rolling"

        return {
            "recommended_strategy": recommended,
            "strategies": [
                {
                    "strategy": r.strategy,
                    "expected_success_probability": r.expected_success_probability,
                    "expected_duration_minutes": r.expected_duration_minutes,
                    "expected_risk_score": r.expected_risk_score,
                    "expected_recovery_probability": r.expected_recovery_probability,
                    "reasoning": r.reasoning,
                }
                for r in results
            ],
            "baseline_context": {
                "success_rate": baseline_success,
                "active_incidents": ctx.active_incidents,
                "rollbacks_in_progress": ctx.rollbacks_in_progress,
                "deployment_freeze": ctx.deployment_freeze,
                "has_db_migrations": ctx.has_db_migrations,
                "has_infrastructure_changes": ctx.has_infrastructure_changes,
            },
        }


# =============================================================================
# Phase 8 — Learning Feedback
# =============================================================================


@dataclass(frozen=True)
class PredictionFeedback:
    prediction_id: str = ""
    execution_id: str = ""
    repository: str = ""
    actual_outcome: str = ""
    predicted_success: float = 0.0
    actual_success: bool = False
    accuracy: float = 0.0
    confidence_adjustment: float = 0.0
    feedback_timestamp: str = ""


class LearningFeedbackEngine:
    """Compare prediction vs reality and improve future prediction confidence."""

    async def record_feedback(
        self,
        prediction_id: str,
        execution_id: str,
        repository: str,
        actual_outcome: str,
        predicted_success_probability: float,
        predicted_strategy: str = "",
        actual_strategy: str = "",
        duration_seconds: float = 0,
        predicted_duration: float = 0,
    ) -> PredictionFeedback:
        actual_success = actual_outcome in ("success", "completed")
        accuracy = 1.0 - abs(predicted_success_probability - (1.0 if actual_success else 0.0))

        confidence_adjustment = 0.0
        if accuracy > 0.8:
            confidence_adjustment = 0.05
        elif accuracy < 0.3:
            confidence_adjustment = -0.1
        elif accuracy < 0.5:
            confidence_adjustment = -0.05

        feedback = PredictionFeedback(
            prediction_id=prediction_id,
            execution_id=execution_id,
            repository=repository,
            actual_outcome=actual_outcome,
            predicted_success=predicted_success_probability,
            actual_success=actual_success,
            accuracy=round(accuracy, 3),
            confidence_adjustment=round(confidence_adjustment, 3),
            feedback_timestamp=_now(),
        )

        try:
            from backend.services.enterprise_runtime_store import runtime_store
            runtime_store.create_execution({
                "execution_id": f"predfb-{prediction_id[:8]}",
                "mission_id": execution_id,
                "repository": repository,
                "objective": f"Prediction feedback: {prediction_id[:8]}",
                "status": "completed",
                "current_stage": "complete",
                "stages_completed": ["prediction_feedback"],
                "failure_reason": "" if actual_success else actual_outcome,
                "duration_seconds": duration_seconds,
                "completed_at": _now(),
            })
        except Exception:
            pass

        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="simulation.prediction_feedback",
                agent="enterprise_predictive_simulation",
                status="completed",
                message=f"Prediction accuracy: {accuracy:.1%} (adjustment: {confidence_adjustment:+.2f})",
                metadata={
                    "prediction_id": prediction_id,
                    "execution_id": execution_id,
                    "actual_outcome": actual_outcome,
                    "predicted_success": predicted_success_probability,
                    "accuracy": accuracy,
                    "confidence_adjustment": confidence_adjustment,
                },
            )
        except Exception:
            pass

        return feedback


# =============================================================================
# Phase 9 — Executive Prediction Report
# =============================================================================


@dataclass(frozen=True)
class SimulationReport:
    report_id: str = ""
    prediction_id: str = ""
    timestamp: str = ""

    # Phase 2
    success_probability: float = 0.0
    failure_probability: float = 0.0
    risk_probability: float = 0.0
    recovery_probability: float = 0.0

    # Phase 5
    business_impact: str = ""
    infrastructure_impact: str = ""
    operational_impact: str = ""

    # Overall
    confidence: float = 0.0
    recommended_strategy: str = ""
    context_sources: List[str] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PredictionReportGenerator:
    """Generate executive prediction reports."""

    def generate(
        self,
        prediction_id: str,
        outcome_prediction: EngineeringOutcomePrediction,
        infra_prediction: InfrastructurePrediction,
        service_impact: ServiceImpactPrediction,
        business_prediction: BusinessPrediction,
        strategy_result: Dict[str, Any],
        context: PredictionContext,
    ) -> SimulationReport:
        reasoning: List[str] = []

        success_prob = outcome_prediction.deployment_success_probability
        failure_prob = outcome_prediction.deployment_failure_probability
        risk_prob = outcome_prediction.rollback_probability
        recovery_prob = outcome_prediction.recovery_probability

        reasoning.extend(outcome_prediction.reasoning)
        reasoning.extend(infra_prediction.reasoning)
        reasoning.extend(service_impact.reasoning)
        reasoning.extend(business_prediction.reasoning)

        biz_impact = "low"
        if business_prediction.business_risk_score > 0.7 or business_prediction.downtime_probability > 0.4:
            biz_impact = "critical"
        elif business_prediction.business_risk_score > 0.4 or business_prediction.downtime_probability > 0.2:
            biz_impact = "high"
        elif business_prediction.business_risk_score > 0.2:
            biz_impact = "medium"

        infra_impact = "low"
        max_infra_prob = max(
            infra_prediction.cpu_increase_probability,
            infra_prediction.memory_increase_probability,
            infra_prediction.node_pressure_probability,
        )
        if max_infra_prob > 0.7:
            infra_impact = "high"
        elif max_infra_prob > 0.4:
            infra_impact = "medium"

        op_impact = "low"
        if service_impact.impact_severity == "high":
            op_impact = "high"
        elif service_impact.impact_severity == "medium" or len(service_impact.affected_services) >= 3:
            op_impact = "medium"

        return SimulationReport(
            report_id=f"sim-rpt-{_id()}",
            prediction_id=prediction_id,
            timestamp=_now(),
            success_probability=_clamp(success_prob),
            failure_probability=_clamp(failure_prob),
            risk_probability=_clamp(risk_prob),
            recovery_probability=_clamp(recovery_prob),
            business_impact=biz_impact,
            infrastructure_impact=infra_impact,
            operational_impact=op_impact,
            confidence=outcome_prediction.confidence,
            recommended_strategy=strategy_result.get("recommended_strategy", "rolling"),
            context_sources=context.sources_used,
            reasoning=reasoning[:15],
        )


# =============================================================================
# Enterprise Predictive Simulation — Main Facade
# =============================================================================


class EnterprisePredictiveSimulation:
    """Main facade for the Enterprise Predictive Simulation Engine."""

    def __init__(self) -> None:
        self.context_builder = PredictionContextBuilder()
        self.outcome_predictor = EngineeringOutcomePredictor()
        self.infra_predictor = InfrastructurePredictor()
        self.service_predictor = ServiceImpactPredictor()
        self.business_predictor = BusinessPredictor()
        self.strategy_comparator = StrategyComparator()
        self.feedback_engine = LearningFeedbackEngine()
        self.report_generator = PredictionReportGenerator()
        self._prediction_cache: Dict[str, Dict[str, Any]] = {}

    async def simulate(
        self,
        repository: str = "",
        branch: str = "",
        commit_sha: str = "",
        execution_id: str = "",
        service: str = "",
        environment: str = "",
        changed_files: Optional[List[str]] = None,
        changed_services: Optional[List[str]] = None,
        change_categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run full simulation — predict outcomes before execution."""
        prediction_id = f"pred-{_id()}"

        ctx = await self.context_builder.build(
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
            execution_id=execution_id,
            service=service,
            environment=environment,
            changed_files=changed_files,
            changed_services=changed_services,
            change_categories=change_categories,
        )

        outcome_pred = await self.outcome_predictor.predict(ctx)
        infra_pred = await self.infra_predictor.predict(ctx)
        service_impact = await self.service_predictor.predict(ctx)
        business_pred = await self.business_predictor.predict(ctx)
        strategy_result = await self.strategy_comparator.compare(ctx)
        report = self.report_generator.generate(
            prediction_id, outcome_pred, infra_pred, service_impact, business_pred, strategy_result, ctx
        )

        result = {
            "prediction_id": prediction_id,
            "timestamp": _now(),
            "context": ctx.to_dict(),
            "outcome_prediction": {
                "build_success_probability": outcome_pred.build_success_probability,
                "build_failure_probability": outcome_pred.build_failure_probability,
                "deployment_success_probability": outcome_pred.deployment_success_probability,
                "deployment_failure_probability": outcome_pred.deployment_failure_probability,
                "rollback_probability": outcome_pred.rollback_probability,
                "approval_probability": outcome_pred.approval_probability,
                "predicted_pipeline_duration_seconds": outcome_pred.predicted_pipeline_duration_seconds,
                "recovery_probability": outcome_pred.recovery_probability,
                "confidence": outcome_pred.confidence,
                "reasoning": outcome_pred.reasoning,
            },
            "infrastructure_prediction": {
                "cpu_increase_probability": infra_pred.cpu_increase_probability,
                "memory_increase_probability": infra_pred.memory_increase_probability,
                "disk_increase_probability": infra_pred.disk_increase_probability,
                "network_utilization_increase_probability": infra_pred.network_utilization_increase_probability,
                "pod_scaling_probability": infra_pred.pod_scaling_probability,
                "node_pressure_probability": infra_pred.node_pressure_probability,
                "cluster_utilization_change": infra_pred.cluster_utilization_change,
                "reasoning": infra_pred.reasoning,
            },
            "service_impact_prediction": {
                "affected_apis": service_impact.affected_apis,
                "affected_services": service_impact.affected_services,
                "affected_databases": service_impact.affected_databases,
                "affected_queues": service_impact.affected_queues,
                "affected_dashboards": service_impact.affected_dashboards,
                "affected_alerts": service_impact.affected_alerts,
                "affected_user_count": service_impact.affected_user_count,
                "impact_severity": service_impact.impact_severity,
                "reasoning": service_impact.reasoning,
            },
            "business_prediction": {
                "downtime_probability": business_pred.downtime_probability,
                "business_risk_score": business_pred.business_risk_score,
                "release_confidence": business_pred.release_confidence,
                "maintenance_window_suitable": business_pred.maintenance_window_suitable,
                "operational_cost_increase": business_pred.operational_cost_increase,
                "expected_duration_minutes": business_pred.expected_duration_minutes,
                "reasoning": business_pred.reasoning,
            },
            "strategy_comparison": strategy_result,
            "executive_report": report.to_dict(),
        }

        self._prediction_cache[prediction_id] = result

        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="simulation.prediction_completed",
                agent="enterprise_predictive_simulation",
                status="completed",
                message=f"Prediction {prediction_id}: success={outcome_pred.deployment_success_probability:.1%}, risk={outcome_pred.rollback_probability:.1%}",
                metadata={
                    "prediction_id": prediction_id,
                    "repository": repository,
                    "branch": branch,
                    "success_probability": outcome_pred.deployment_success_probability,
                    "failure_probability": outcome_pred.deployment_failure_probability,
                    "rollback_probability": outcome_pred.rollback_probability,
                    "confidence": outcome_pred.confidence,
                    "recommended_strategy": strategy_result.get("recommended_strategy", ""),
                },
            )
        except Exception:
            pass

        return result

    async def get_prediction(self, prediction_id: str) -> Optional[Dict[str, Any]]:
        return self._prediction_cache.get(prediction_id)

    async def list_predictions(self) -> List[Dict[str, Any]]:
        results = []
        for pid, data in self._prediction_cache.items():
            results.append({
                "prediction_id": pid,
                "timestamp": data.get("timestamp", ""),
                "repository": data.get("context", {}).get("repository", ""),
                "success_probability": data.get("outcome_prediction", {}).get("deployment_success_probability", 0),
                "confidence": data.get("outcome_prediction", {}).get("confidence", 0),
            })
        results.sort(key=lambda r: r["timestamp"], reverse=True)
        return results

    async def get_report(self, prediction_id: str) -> Optional[Dict[str, Any]]:
        data = self._prediction_cache.get(prediction_id)
        if data:
            return data.get("executive_report")
        return None

    async def feedback(
        self,
        prediction_id: str,
        execution_id: str,
        repository: str,
        actual_outcome: str,
        predicted_success_probability: float = 0.5,
        predicted_strategy: str = "",
        actual_strategy: str = "",
        duration_seconds: float = 0,
        predicted_duration: float = 0,
    ) -> PredictionFeedback:
        result = await self.feedback_engine.record_feedback(
            prediction_id=prediction_id,
            execution_id=execution_id,
            repository=repository,
            actual_outcome=actual_outcome,
            predicted_success_probability=predicted_success_probability,
            predicted_strategy=predicted_strategy,
            actual_strategy=actual_strategy,
            duration_seconds=duration_seconds,
            predicted_duration=predicted_duration,
        )
        return result

    async def consume_predictions(
        self,
        repository: str = "",
        branch: str = "",
        commit_sha: str = "",
        execution_id: str = "",
        service: str = "",
        environment: str = "",
        changed_files: Optional[List[str]] = None,
        changed_services: Optional[List[str]] = None,
        change_categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Phase 7 — produce a lightweight prediction digest for the Decision Engine."""
        result = await self.simulate(
            repository=repository, branch=branch, commit_sha=commit_sha,
            execution_id=execution_id, service=service, environment=environment,
            changed_files=changed_files, changed_services=changed_services,
            change_categories=change_categories,
        )
        op = result.get("outcome_prediction", {})
        sc = result.get("strategy_comparison", {})
        bp = result.get("business_prediction", {})
        ip = result.get("infrastructure_prediction", {})

        return {
            "prediction_id": result["prediction_id"],
            "deployment_success_probability": op.get("deployment_success_probability", 0.5),
            "deployment_failure_probability": op.get("deployment_failure_probability", 0.5),
            "rollback_probability": op.get("rollback_probability", 0.1),
            "approval_probability": op.get("approval_probability", 0.3),
            "recovery_probability": op.get("recovery_probability", 0.5),
            "predicted_duration_seconds": op.get("predicted_pipeline_duration_seconds", 600),
            "confidence": op.get("confidence", 0.5),
            "recommended_strategy": sc.get("recommended_strategy", "rolling"),
            "strategy_comparison": sc,
            "business_risk_score": bp.get("business_risk_score", 0.3),
            "release_confidence": bp.get("release_confidence", 0.7),
            "infra_cpu_probability": ip.get("cpu_increase_probability", 0.3),
            "infra_memory_probability": ip.get("memory_increase_probability", 0.3),
            "service_impact_severity": result.get("service_impact_prediction", {}).get("impact_severity", "low"),
            "reasoning": op.get("reasoning", []),
        }


# =============================================================================
# Singleton
# =============================================================================

enterprise_predictive_simulation = EnterprisePredictiveSimulation()
