"""
Enterprise Context Intelligence — aggregates engineering context from every
existing subsystem into a single immutable ContextSnapshot BEFORE any
engineering decision is made.

Reuses every existing subsystem. Does NOT duplicate storage, logic, or
orchestration. Only aggregates, normalizes, correlates, and provides context.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Phase 2 — Dependency Context
# =============================================================================


@dataclass(frozen=True)
class DependencyContext:
    impacted_services: List[str] = field(default_factory=list)
    upstream_services: List[str] = field(default_factory=list)
    downstream_services: List[str] = field(default_factory=list)
    deployment_dependencies: List[str] = field(default_factory=list)
    infrastructure_dependencies: List[str] = field(default_factory=list)
    shared_databases: List[str] = field(default_factory=list)
    shared_apis: List[str] = field(default_factory=list)
    shared_queues: List[str] = field(default_factory=list)
    critical_paths: List[str] = field(default_factory=list)


# =============================================================================
# Phase 3 — Operational Context
# =============================================================================


@dataclass(frozen=True)
class OperationalContext:
    active_alerts: List[Dict[str, Any]] = field(default_factory=list)
    active_incidents: List[Dict[str, Any]] = field(default_factory=list)
    deployment_health: Dict[str, str] = field(default_factory=dict)
    runtime_health: str = ""
    node_health: List[Dict[str, Any]] = field(default_factory=list)
    pod_health: List[Dict[str, Any]] = field(default_factory=list)
    service_health: List[Dict[str, Any]] = field(default_factory=list)
    traffic: Dict[str, float] = field(default_factory=dict)
    error_rate: Dict[str, float] = field(default_factory=dict)
    latency: Dict[str, float] = field(default_factory=dict)
    ongoing_deployments: List[Dict[str, Any]] = field(default_factory=list)
    rollbacks: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Phase 4 — Historical Context
# =============================================================================


@dataclass(frozen=True)
class HistoricalContext:
    previous_deployments: List[Dict[str, Any]] = field(default_factory=list)
    previous_failures: List[Dict[str, Any]] = field(default_factory=list)
    previous_rca: List[Dict[str, Any]] = field(default_factory=list)
    previous_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    previous_approvals: List[Dict[str, Any]] = field(default_factory=list)
    replay_history: List[Dict[str, Any]] = field(default_factory=list)
    learning_history: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Phase 5 — Business Context
# =============================================================================


@dataclass(frozen=True)
class BusinessContext:
    environment: str = "development"
    maintenance_window: bool = False
    deployment_freeze: bool = False
    business_hours: bool = True
    hotfix_mode: bool = False
    time_of_day: str = ""
    day_of_week: str = ""
    on_call_team: str = ""


# =============================================================================
# Phase 1 — Context Snapshot (Aggregation)
# =============================================================================


@dataclass(frozen=True)
class ContextSnapshot:
    """Immutable snapshot of all engineering context at decision time.

    This is the single source of engineering context for every autonomous
    decision. All fields are populated by aggregating from existing services.
    """

    # Correlation IDs
    execution_id: str = ""
    mission_id: str = ""
    pipeline_id: str = ""
    delivery_id: str = ""
    repository: str = ""
    commit: str = ""
    branch: str = ""
    service: str = ""
    cluster: str = ""
    environment: str = ""

    # Timestamp
    snapshot_timestamp: str = ""

    # Phase 2 — Dependency Context
    dependency: DependencyContext = field(default_factory=DependencyContext)

    # Phase 3 — Operational Context
    operational: OperationalContext = field(default_factory=OperationalContext)

    # Phase 4 — Historical Context
    historical: HistoricalContext = field(default_factory=HistoricalContext)

    # Phase 5 — Business Context
    business: BusinessContext = field(default_factory=BusinessContext)

    # Runtime execution records (from RuntimeStore)
    recent_executions: List[Dict[str, Any]] = field(default_factory=list)

    # Code intelligence graph
    code_graph: Dict[str, Any] = field(default_factory=dict)

    # Infrastructure snapshot
    infrastructure: Dict[str, Any] = field(default_factory=dict)

    # CI/CD snapshot
    cicd: Dict[str, Any] = field(default_factory=dict)

    # GitHub activity
    github: Dict[str, Any] = field(default_factory=dict)

    # Knowledge graph summary
    knowledge_graph: Dict[str, Any] = field(default_factory=dict)

    # Alert status
    alerts: Dict[str, Any] = field(default_factory=dict)

    # Prometheus metrics
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Source services that contributed data
    sources_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "mission_id": self.mission_id,
            "pipeline_id": self.pipeline_id,
            "delivery_id": self.delivery_id,
            "repository": self.repository,
            "commit": self.commit,
            "branch": self.branch,
            "service": self.service,
            "cluster": self.cluster,
            "environment": self.environment,
            "snapshot_timestamp": self.snapshot_timestamp,
            "dependency": {
                "impacted_services": self.dependency.impacted_services,
                "upstream_services": self.dependency.upstream_services,
                "downstream_services": self.dependency.downstream_services,
                "deployment_dependencies": self.dependency.deployment_dependencies,
                "infrastructure_dependencies": self.dependency.infrastructure_dependencies,
                "shared_databases": self.dependency.shared_databases,
                "shared_apis": self.dependency.shared_apis,
                "shared_queues": self.dependency.shared_queues,
                "critical_paths": self.dependency.critical_paths,
            },
            "operational": {
                "active_alerts_count": len(self.operational.active_alerts),
                "active_incidents_count": len(self.operational.active_incidents),
                "runtime_health": self.operational.runtime_health,
                "node_count": len(self.operational.node_health),
                "pod_count": len(self.operational.pod_health),
                "service_health": self.operational.service_health,
                "ongoing_deployments_count": len(self.operational.ongoing_deployments),
                "rollbacks_count": len(self.operational.rollbacks),
            },
            "historical": {
                "previous_deployments_count": len(self.historical.previous_deployments),
                "previous_failures_count": len(self.historical.previous_failures),
                "previous_rca_count": len(self.historical.previous_rca),
                "previous_recommendations_count": len(self.historical.previous_recommendations),
            },
            "business": {
                "environment": self.business.environment,
                "maintenance_window": self.business.maintenance_window,
                "deployment_freeze": self.business.deployment_freeze,
                "business_hours": self.business.business_hours,
                "hotfix_mode": self.business.hotfix_mode,
            },
            "sources_used": self.sources_used,
        }


# =============================================================================
# Enterprise Context Intelligence — Aggregation Service
# =============================================================================


class EnterpriseContextIntelligence:
    """Aggregates engineering context from all existing enterprise services.

    This is NOT a new service that stores data. It is a coordination layer
    that queries all existing services and combines their responses into
    a single ContextSnapshot.
    """

    def __init__(self) -> None:
        self._context_cache: Dict[str, ContextSnapshot] = {}

    # ── Main Entry Point ──────────────────────────────────────────────────

    async def build_snapshot(
        self,
        repository: str = "",
        branch: str = "",
        commit: str = "",
        service: str = "",
        execution_id: str = "",
        environment: str = "",
        include_historical: bool = True,
        include_operational: bool = True,
        include_dependency: bool = True,
        include_business: bool = True,
    ) -> ContextSnapshot:
        """Build a complete ContextSnapshot by aggregating all subsystems.

        Each phase can be independently enabled/disabled for performance.
        """
        snapshot = ContextSnapshot(
            execution_id=execution_id,
            repository=repository,
            commit=commit,
            branch=branch,
            service=service,
            environment=environment,
            snapshot_timestamp=_now(),
        )

        sources: List[str] = []

        # Phase 1: Runtime store (executions)
        sources.append("RuntimeStore")
        try:
            snapshot = await self._collect_runtime_context(snapshot)
        except Exception as exc:
            log.debug("RuntimeStore context collection failed: %s", exc)

        # Phase 1: Code intelligence
        sources.append("CodeIntelligence")
        try:
            snapshot = await self._collect_code_context(snapshot, repository)
        except Exception as exc:
            log.debug("Code intelligence context collection failed: %s", exc)

        # Phase 2: Dependency context
        if include_dependency:
            sources.append("KnowledgeGraph")
            try:
                snapshot = await self._collect_dependency_context(snapshot, execution_id or repository)
            except Exception as exc:
                log.debug("Dependency context collection failed: %s", exc)

        # Phase 3: Operational context
        if include_operational:
            sources.append("PrometheusIntelligence")
            try:
                snapshot = await self._collect_prometheus_context(snapshot)
            except Exception as exc:
                log.debug("Prometheus context collection failed: %s", exc)

            sources.append("LokiIntelligence")
            try:
                snapshot = await self._collect_loki_context(snapshot)
            except Exception as exc:
                log.debug("Loki context collection failed: %s", exc)

            sources.append("InfrastructureIntelligence")
            try:
                snapshot = await self._collect_infrastructure_context(snapshot)
            except Exception as exc:
                log.debug("Infrastructure context collection failed: %s", exc)

            sources.append("ArgoCDIntelligence")
            try:
                snapshot = await self._collect_argocd_context(snapshot)
            except Exception as exc:
                log.debug("ArgoCD context collection failed: %s", exc)

            sources.append("GitHubIntegration")
            try:
                snapshot = await self._collect_github_context(snapshot, repository)
            except Exception as exc:
                log.debug("GitHub context collection failed: %s", exc)

            sources.append("CICDIntelligence")
            try:
                snapshot = await self._collect_cicd_context(snapshot)
            except Exception as exc:
                log.debug("CI/CD context collection failed: %s", exc)

            sources.append("TerraformIntelligence")
            try:
                snapshot = await self._collect_terraform_context(snapshot)
            except Exception as exc:
                log.debug("Terraform context collection failed: %s", exc)

        # Phase 4: Historical context
        if include_historical:
            sources.append("LearningService")
            try:
                snapshot = await self._collect_learning_context(snapshot)
            except Exception as exc:
                log.debug("Learning context collection failed: %s", exc)

            sources.append("RecommendationEngine")
            try:
                snapshot = await self._collect_recommendation_context(snapshot)
            except Exception as exc:
                log.debug("Recommendation context collection failed: %s", exc)

            sources.append("RCA")
            try:
                snapshot = await self._collect_rca_context(snapshot)
            except Exception as exc:
                log.debug("RCA context collection failed: %s", exc)

            sources.append("ReplayStore")
            try:
                snapshot = await self._collect_replay_context(snapshot, execution_id)
            except Exception as exc:
                log.debug("Replay context collection failed: %s", exc)

        # Phase 5: Business context
        if include_business:
            snapshot = self._collect_business_context(snapshot, environment)

        object.__setattr__(snapshot, "sources_used", sources)
        self._context_cache[execution_id or snapshot.snapshot_timestamp] = snapshot
        return snapshot

    # ── Phase 1: Runtime Context ──────────────────────────────────────────

    async def _collect_runtime_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_runtime_store import runtime_store

        dashboard = runtime_store.get_dashboard()
        recent = runtime_store.list_executions(limit=20)

        data = {
            "dashboard": dashboard,
            "recent_count": len(recent),
            "builds_passed": dashboard.get("builds_passed", 0),
            "builds_failed": dashboard.get("builds_failed", 0),
            "deployments_successful": dashboard.get("deployments_successful", 0),
            "deployments_failed": dashboard.get("deployments_failed", 0),
        }

        object.__setattr__(snapshot, "recent_executions", [dict(e) if hasattr(e, "items") else e for e in recent])
        object.__setattr__(snapshot, "infrastructure", {**snapshot.infrastructure, "runtime": data})
        return snapshot

    # ── Phase 1: Code Intelligence Context ────────────────────────────────

    async def _collect_code_context(self, snapshot: ContextSnapshot, repo: str = "") -> ContextSnapshot:
        from backend.services.enterprise_code_intelligence import code_intelligence

        graph = await code_intelligence.get_graph(repo_id=repo)
        repos = await code_intelligence.list_repositories()

        object.__setattr__(snapshot, "code_graph", {
            "repository_count": len(repos),
            "graph_summary": {
                "nodes": len(graph.get("nodes", [])),
                "edges": len(graph.get("edges", [])),
            } if graph else {},
            "repositories": repos[:10],
        })
        return snapshot

    # ── Phase 2: Dependency Context ───────────────────────────────────────

    async def _collect_dependency_context(self, snapshot: ContextSnapshot, entity_id: str) -> ContextSnapshot:
        from backend.services.enterprise_graph_service import enterprise_graph

        graph = await enterprise_graph.get_mission_graph(entity_id)
        connected = None
        if entity_id:
            connected = await enterprise_graph.get_connected_nodes(entity_id)

        services: List[str] = []
        upstream: List[str] = []
        downstream: List[str] = []

        if graph:
            for rel in graph.get("relationships", []):
                src = rel.get("source", "")
                tgt = rel.get("target", "")
                rtype = rel.get("type", "")
                if rtype == "DEPENDS_ON":
                    downstream.append(tgt)
                if rtype == "CALLS":
                    upstream.append(src)
                if src and src not in services:
                    services.append(src)
                if tgt and tgt not in services:
                    services.append(tgt)

        dep = DependencyContext(
            impacted_services=services,
            upstream_services=list(set(upstream)),
            downstream_services=list(set(downstream)),
        )
        object.__setattr__(snapshot, "dependency", dep)
        object.__setattr__(snapshot, "knowledge_graph", {
            "entity_id": entity_id,
            "relationships_count": len(graph.get("relationships", [])) if graph else 0,
            "connected_nodes": len(connected.get("nodes", [])) if connected else 0,
        })
        return snapshot

    # ── Phase 3: Prometheus Context ───────────────────────────────────────

    async def _collect_prometheus_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_prometheus_intelligence import prometheus_intelligence

        alerts_data = prometheus_intelligence.get_alerts()
        rules_data = prometheus_intelligence.get_rules()
        targets = prometheus_intelligence.get_targets()

        alerts_list = []
        if isinstance(alerts_data, dict):
            for group in alerts_data.get("data", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if rule.get("type") == "alert" and rule.get("state") == "firing":
                        alerts_list.append({
                            "name": rule.get("name", rule.get("alert", "")),
                            "state": rule.get("state", ""),
                            "severity": rule.get("labels", {}).get("severity", "unknown"),
                            "annotations": rule.get("annotations", {}),
                        })

        object.__setattr__(snapshot, "alerts", {
            "active_alert_count": len(alerts_list),
            "alerts": alerts_list[:20],
            "rule_count": len(rules_data.get("data", {}).get("groups", [])) if isinstance(rules_data, dict) else 0,
            "target_count": len(targets.get("data", [])) if isinstance(targets, dict) else 0,
        })

        [a for a in alerts_list if a.get("state") == "firing"]
        op_ctx = OperationalContext(
            active_alerts=alerts_list[:20],
        )
        object.__setattr__(snapshot, "operational", op_ctx)

        metrics = {}
        try:
            node_metrics = prometheus_intelligence.collect_node_metrics()
            if isinstance(node_metrics, dict):
                metrics["nodes"] = {
                    k: v for k, v in node_metrics.items()
                    if isinstance(v, (int, float)) and k != "error"
                }
        except Exception:
            pass

        object.__setattr__(snapshot, "metrics", metrics)
        return snapshot

    # ── Phase 3: Loki Context ─────────────────────────────────────────────

    async def _collect_loki_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_loki_intelligence import loki_intelligence

        labels = loki_intelligence.list_labels()
        streams = loki_intelligence.list_streams()

        object.__setattr__(snapshot, "infrastructure", {
            **snapshot.infrastructure,
            "loki": {
                "label_count": len(labels),
                "stream_count": len(streams),
                "labels": labels[:20],
            },
        })
        return snapshot

    # ── Phase 3: Infrastructure Context ───────────────────────────────────

    async def _collect_infrastructure_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_infrastructure_intelligence import infra_intelligence

        result: Dict[str, Any] = {}

        try:
            k8s_result = infra_intelligence.sync_from_kubernetes()
            if isinstance(k8s_result, dict):
                clusters = k8s_result.get("clusters", k8s_result.get("data", []))
                result["cluster_count"] = len(clusters) if isinstance(clusters, list) else 0
                if isinstance(clusters, list) and clusters:
                    result["cluster_health"] = clusters[0].get("health", clusters[0].get("status", "unknown"))
        except Exception:
            pass

        try:
            docker_result = infra_intelligence.sync_from_docker()
            if isinstance(docker_result, dict):
                containers = docker_result.get("containers", docker_result.get("data", []))
                result["container_count"] = len(containers) if isinstance(containers, list) else 0
        except Exception:
            pass

        object.__setattr__(snapshot, "infrastructure", {
            **snapshot.infrastructure,
            "kubernetes": result,
        })
        return snapshot

    # ── Phase 3: ArgoCD Context ──────────────────────────────────────────

    async def _collect_argocd_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_argocd_intelligence import argocd_intelligence

        apps = argocd_intelligence.discover_all()

        object.__setattr__(snapshot, "infrastructure", {
            **snapshot.infrastructure,
            "argocd": {
                "app_count": len(apps.get("applications", [])) if isinstance(apps, dict) else 0,
                "synced": apps.get("synced_count", 0),
                "out_of_sync": apps.get("out_of_sync_count", 0),
                "healthy": apps.get("healthy_count", 0),
                "degraded": apps.get("degraded_count", 0),
            } if isinstance(apps, dict) else {},
        })
        return snapshot

    # ── Phase 3: GitHub Context ──────────────────────────────────────────

    async def _collect_github_context(self, snapshot: ContextSnapshot, repo: str = "") -> ContextSnapshot:
        from backend.services.enterprise_github_integration import github_integration

        activity = await github_integration.get_recent_activity(limit=5)
        dashboard = await github_integration.get_dashboard_stats()

        owner = ""
        repo_name = ""
        if repo and "/" in repo:
            owner, repo_name = repo.split("/", 1)

        recent_runs = []
        if owner and repo_name:
            try:
                runs = await github_integration.list_runs(owner, repo_name, per_page=5)
                recent_runs = runs.get("workflow_runs", runs.get("data", []))[:5]
            except Exception:
                pass

        object.__setattr__(snapshot, "github", {
            "recent_activity": activity if isinstance(activity, list) else [],
            "dashboard": dashboard if isinstance(dashboard, dict) else {},
            "recent_workflow_runs": recent_runs,
        })
        return snapshot

    # ── Phase 3: CI/CD Context ────────────────────────────────────────────

    async def _collect_cicd_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_cicd_intelligence import cicd_intelligence

        dashboard = cicd_intelligence.get_dashboard()
        timeline = cicd_intelligence.get_timeline(limit=10)

        object.__setattr__(snapshot, "cicd", {
            "dashboard": dashboard if isinstance(dashboard, dict) else {},
            "recent_timeline": timeline if isinstance(timeline, list) else [],
        })
        return snapshot

    # ── Phase 3: Terraform Context ───────────────────────────────────────

    async def _collect_terraform_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_terraform_intelligence import terraform_intelligence

        workspaces = terraform_intelligence.discover_all()
        state = terraform_intelligence.get_state_summary()

        object.__setattr__(snapshot, "infrastructure", {
            **snapshot.infrastructure,
            "terraform": {
                "workspace_count": len(workspaces.get("workspaces", [])) if isinstance(workspaces, dict) else 0,
                "state_summary": state if isinstance(state, dict) else {},
            },
        })
        return snapshot

    # ── Phase 4: Learning Context ────────────────────────────────────────

    async def _collect_learning_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_learning_service import enterprise_learning

        dashboard = await enterprise_learning.get_dashboard()
        failures = await enterprise_learning.get_failure_patterns(limit=10)
        lessons = await enterprise_learning.get_lessons(limit=10)
        practices = await enterprise_learning.get_best_practices(limit=5)

        hist = HistoricalContext(
            previous_failures=failures,
        )
        object.__setattr__(snapshot, "historical", hist)
        object.__setattr__(snapshot, "learning_history", {
            "dashboard": dashboard if isinstance(dashboard, dict) else {},
            "failure_patterns": failures,
            "lessons_count": len(lessons),
            "best_practices_count": len(practices),
        })
        return snapshot

    # ── Phase 4: Recommendation Context ──────────────────────────────────

    async def _collect_recommendation_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine

        active = enterprise_recommendation_engine.get_active()
        enterprise_recommendation_engine.get_dashboard()

        hist = HistoricalContext(
            previous_recommendations=active[:10],
        )
        object.__setattr__(snapshot, "historical", hist)
        return snapshot

    # ── Phase 4: RCA Context ─────────────────────────────────────────────

    async def _collect_rca_context(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        from backend.services.enterprise_root_cause_analysis import root_cause_analysis

        root_cause_analysis.list_incidents(limit=10)
        analyses = root_cause_analysis.list_analyses(limit=5)

        hist = HistoricalContext(
            previous_rca=analyses[:5],
        )
        object.__setattr__(snapshot, "historical", hist)
        return snapshot

    # ── Phase 4: Replay Context ──────────────────────────────────────────

    async def _collect_replay_context(self, snapshot: ContextSnapshot, execution_id: str = "") -> ContextSnapshot:
        from backend.services.mission_replay_store import replay_store

        if execution_id:
            try:
                events = await replay_store.get_events(execution_id, 0, 20)
                await replay_store.get_summary(execution_id)
                await replay_store.get_timeline(execution_id)
                object.__setattr__(snapshot, "historical", HistoricalContext(
                    replay_history=events[:20],
                ))
            except Exception:
                pass
        return snapshot

    # ── Phase 5: Business Context ────────────────────────────────────────

    def _collect_business_context(self, snapshot: ContextSnapshot, environment: str = "") -> ContextSnapshot:
        now = datetime.now(timezone.utc)
        hour = now.hour
        day = now.strftime("%A")

        is_business_hours = 8 <= hour < 18 and day not in ("Saturday", "Sunday")
        env = environment or snapshot.environment or "development"

        bc = BusinessContext(
            environment=env,
            maintenance_window=hour < 6,
            deployment_freeze=False,
            business_hours=is_business_hours,
            hotfix_mode=False,
            time_of_day=now.strftime("%H:%M UTC"),
            day_of_week=day,
            on_call_team="primary",
        )
        object.__setattr__(snapshot, "business", bc)
        return snapshot


# =============================================================================
# Singleton
# =============================================================================

enterprise_context_intelligence = EnterpriseContextIntelligence()
