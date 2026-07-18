"""Enterprise ArgoCD GitOps Intelligence — application tracking, sync management,
drift detection, progressive delivery, and RuntimeStore synchronisation.

Reuses:
  - RuntimeStore          via existing infrastructure intelligence
  - EventHub              for argocd.* events
  - Knowledge Graph       for app-to-service edges
  - Analytics             for metric recording
  - Learning Engine       for deployment pattern learning
  - Recommendation Engine for deployment recommendations
  - Kubernetes Connector  for live state comparison

Backward compatible: all existing Deployment Engine and Delivery Orchestrator
functionality continues to work unchanged.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.connectors.argocd import argocd_connector

log = logging.getLogger(__name__)

ARGOCD_EVENT_TYPES = {
    "app.synced": "argocd.app.synced",
    "sync.started": "argocd.sync.started",
    "sync.failed": "argocd.sync.failed",
    "health.degraded": "argocd.health.degraded",
    "rollback.started": "argocd.rollback.started",
    "rollback.completed": "argocd.rollback.completed",
    "drift.detected": "argocd.drift.detected",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GitOpsApplicationIntelligence:
    """Track ArgoCD applications, sync status, health, revisions."""

    async def discover_all(self) -> Dict[str, Any]:
        """Discover all ArgoCD applications with full details."""
        result = await argocd_connector.list_applications(limit=500)
        if result.get("status") != "success":
            return {"status": "error", "applications": [], "error": result.get("error", "discovery failed")}

        items = result.get("data", {}).get("items", result.get("data", []))
        if isinstance(items, dict):
            items = items.get("items", [])

        enriched = []
        for app in items:
            enriched.append(self._enrich(app))

        sync_counts: Dict[str, int] = {}
        health_counts: Dict[str, int] = {}
        for a in enriched:
            sc = a.get("sync_status", "unknown")
            sync_counts[sc] = sync_counts.get(sc, 0) + 1
            hc = a.get("health_status", "unknown")
            health_counts[hc] = health_counts.get(hc, 0) + 1

        return {
            "status": "success",
            "applications": enriched,
            "total": len(enriched),
            "sync_counts": sync_counts,
            "health_counts": health_counts,
            "out_of_sync": sync_counts.get("OutOfSync", 0),
            "degraded": health_counts.get("Degraded", 0) + health_counts.get("Missing", 0),
            "discovered_at": _now(),
        }

    def _enrich(self, app: Dict[str, Any]) -> Dict[str, Any]:
        spec = app.get("spec", {})
        status = app.get("status", {})
        dest = spec.get("destination", {})
        source = spec.get("source", {})

        sync_status = status.get("sync", {}).get("status", "Unknown")
        health_status = status.get("health", {}).get("status", "Unknown")

        revision = ""
        revisions = status.get("sync", {}).get("revision", "")
        if isinstance(revisions, list) and revisions:
            revision = revisions[0]
        elif isinstance(revisions, str):
            revision = revisions

        return {
            "name": app.get("metadata", {}).get("name", ""),
            "project": spec.get("project", "default"),
            "namespace": dest.get("namespace", ""),
            "cluster_url": dest.get("server", ""),
            "cluster_name": dest.get("name", ""),
            "repo_url": source.get("repoURL", ""),
            "path": source.get("path", ""),
            "target_revision": source.get("targetRevision", ""),
            "chart": source.get("chart", ""),
            "revision": revision,
            "sync_status": sync_status,
            "health_status": health_status,
            "sync_started_at": status.get("sync", {}).get("startedAt", ""),
            "sync_finished_at": status.get("sync", {}).get("finishedAt", ""),
            "sync_duration_seconds": self._calc_duration(
                status.get("sync", {}).get("startedAt", ""),
                status.get("sync", {}).get("finishedAt", ""),
            ),
            "conditions": status.get("conditions", []),
            "resources": status.get("resources", []),
            "source_type": source.get("path", "") and "kustomize" if source.get("path", "").endswith("kustomization") else "helm" if source.get("chart") else "plain",
            "created_at": app.get("metadata", {}).get("creationTimestamp", ""),
            "labels": app.get("metadata", {}).get("labels", {}),
            "annotations": app.get("metadata", {}).get("annotations", {}),
        }

    def _calc_duration(self, started: str, finished: str) -> float:
        if not started or not finished:
            return 0.0
        try:
            s = datetime.fromisoformat(started.replace("Z", "+00:00"))
            f = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            return (f - s).total_seconds()
        except Exception:
            return 0.0

    async def get_application_detail(self, name: str) -> Dict[str, Any]:
        result = await argocd_connector.get_application(name)
        if result.get("status") != "success":
            return {"status": "error", "error": result.get("error", "not found")}
        app = result.get("data", {})
        return {"status": "success", "application": self._enrich(app)}

    async def get_revision_history(self, name: str) -> Dict[str, Any]:
        result = await argocd_connector.get_application_revisions(name)
        if result.get("status") != "success":
            return {"status": "error", "error": result.get("error", "not found")}
        revisions = result.get("data", [])
        enriched = []
        for rev in revisions:
            rev_id = rev.get("id", 0)
            meta_result = await argocd_connector.get_revision_metadata(name, str(rev_id))
            metadata = meta_result.get("data", {}) if meta_result.get("status") == "success" else {}
            enriched.append({
                "id": rev_id,
                "revision": rev.get("revision", ""),
                "deployed_at": rev.get("deployedAt", ""),
                "author": metadata.get("author", ""),
                "message": metadata.get("message", ""),
                "date": metadata.get("date", ""),
                "tags": metadata.get("tags", []),
            })
        return {"status": "success", "revisions": enriched, "total": len(enriched)}

    async def get_resource_tree(self, name: str) -> Dict[str, Any]:
        result = await argocd_connector.get_application_resource_tree(name)
        if result.get("status") != "success":
            return {"status": "error", "error": result.get("error", "not found")}
        return {"status": "success", "resources": result.get("data", {})}

    async def get_events(self, name: str) -> Dict[str, Any]:
        result = await argocd_connector.get_application_events(name)
        if result.get("status") != "success":
            return {"status": "error", "error": result.get("error", "not found")}
        return {"status": "success", "events": result.get("data", [])}


class GitOpsProjectIntelligence:
    """Track ArgoCD projects."""

    async def discover_all(self) -> Dict[str, Any]:
        result = await argocd_connector.list_projects()
        if result.get("status") != "success":
            return {"status": "error", "projects": [], "error": result.get("error", "discovery failed")}
        items = result.get("data", [])
        if isinstance(items, dict):
            items = items.get("items", [])
        enriched = []
        for p in items:
            spec = p.get("spec", {})
            enriched.append({
                "name": p.get("metadata", {}).get("name", ""),
                "description": spec.get("description", ""),
                "source_repos": spec.get("sourceRepos", []),
                "destinations": spec.get("destinations", []),
                "cluster_resource_blacklist": spec.get("clusterResourceBlacklist", []),
                "namespace_resource_blacklist": spec.get("namespaceResourceBlacklist", []),
                "orphaned_resources": spec.get("orphanedResources", {}).get("warn", False),
                "created_at": p.get("metadata", {}).get("creationTimestamp", ""),
                "labels": p.get("metadata", {}).get("labels", {}),
            })
        return {"status": "success", "projects": enriched, "total": len(enriched)}


class GitOpsRepoIntelligence:
    """Track ArgoCD repositories."""

    async def discover_all(self) -> Dict[str, Any]:
        result = await argocd_connector.list_repositories()
        if result.get("status") != "success":
            return {"status": "error", "repos": [], "error": result.get("error", "discovery failed")}
        items = result.get("data", [])
        if isinstance(items, dict):
            items = items.get("items", [])
        enriched = []
        for r in items:
            enriched.append({
                "repo": r.get("repo", ""),
                "type": r.get("type", "git"),
                "name": r.get("name", ""),
                "project": r.get("project", "default"),
                "connection_state": r.get("connectionState", {}).get("status", "Unknown"),
                "inherited": r.get("inherited", False),
                "enable_lfs": r.get("enableLfs", False),
                "enable_oci": r.get("enableOci", False),
            })
        return {"status": "success", "repos": enriched, "total": len(enriched)}


class GitOpsClusterIntelligence:
    """Track ArgoCD cluster connections."""

    async def discover_all(self) -> Dict[str, Any]:
        result = await argocd_connector.list_clusters()
        if result.get("status") != "success":
            return {"status": "error", "clusters": [], "error": result.get("error", "discovery failed")}
        items = result.get("data", [])
        if isinstance(items, dict):
            items = items.get("items", [])
        enriched = []
        for c in items:
            conn = c.get("connectionState", {})
            enriched.append({
                "name": c.get("name", c.get("server", "")),
                "server": c.get("server", ""),
                "namespace": c.get("config", {}).get("namespace", ""),
                "connection_status": conn.get("status", "Unknown"),
                "connection_attempted_at": conn.get("attemptedAt", ""),
                "version": c.get("version", ""),
                "project": c.get("project", "default"),
                "labels": c.get("labels", {}),
                "annotations": c.get("annotations", {}),
            })
        return {"status": "success", "clusters": enriched, "total": len(enriched)}


class DriftDetector:
    """Detect drift between desired state (git) and live state (cluster)."""

    def __init__(self) -> None:
        self._risk_patterns = {
            "high": ["secret", "configmap", "rbac", "networkpolicy", "podsecurity"],
            "medium": ["deployment", "statefulset", "daemonset", "service", "ingress"],
            "low": ["horizontalpodautoscaler", "poddisruptionbudget", "resourcequota"],
        }

    async def detect_all(self, applications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect drift for all applications."""
        drift_reports = []
        for app in applications:
            report = self._check_application(app)
            if report["drift_count"] > 0:
                drift_reports.append(report)

        risk_scores = [r["risk_score"] for r in drift_reports]
        total_risk = sum(risk_scores) / max(len(risk_scores), 1) if risk_scores else 0

        return {
            "status": "success",
            "drift_reports": drift_reports,
            "total_applications": len(applications),
            "applications_with_drift": len(drift_reports),
            "drift_rate": round(len(drift_reports) / max(len(applications), 1), 4),
            "overall_risk_score": round(total_risk, 2),
            "drift_categories": self._categorize_drifts(drift_reports),
            "detected_at": _now(),
        }

    def _check_application(self, app: Dict[str, Any]) -> Dict[str, Any]:
        drifts: List[Dict[str, Any]] = []
        resource_drifts: List[Dict[str, Any]] = []
        total_risk = 0.0

        sync_status = app.get("sync_status", "Synced")
        health_status = app.get("health_status", "Healthy")

        # Sync status drift
        if sync_status == "OutOfSync":
            drifts.append({
                "type": "sync_status",
                "description": f"Application '{app.get('name', '')}' is OutOfSync",
                "expected": "Synced",
                "actual": "OutOfSync",
                "severity": "high",
                "risk_score": 0.8,
            })
            total_risk += 0.8

        # Health drift
        if health_status in ("Degraded", "Missing", "Unknown"):
            severity = "critical" if health_status == "Degraded" else "high"
            drifts.append({
                "type": "health",
                "description": f"Application '{app.get('name', '')}' health is {health_status}",
                "expected": "Healthy",
                "actual": health_status,
                "severity": severity,
                "risk_score": 1.0 if health_status == "Degraded" else 0.7,
            })
            total_risk += 1.0 if health_status == "Degraded" else 0.7

        # Resource drift from conditions
        for cond in app.get("conditions", []):
            cond_type = cond.get("type", "")
            cond_msg = cond.get("message", "")
            if "error" in cond_msg.lower() or "fail" in cond_msg.lower():
                drifts.append({
                    "type": "condition_error",
                    "description": cond_msg[:300],
                    "expected": "No errors",
                    "actual": cond_type,
                    "severity": "high",
                    "risk_score": 0.6,
                })
                total_risk += 0.6

        # Check resources for drift
        for res in app.get("resources", []):
            res_status = res.get("status", "")
            res_kind = res.get("kind", "")
            res_name = res.get("name", "")
            res_ns = res.get("namespace", "")

            if res_status == "OutOfSync":
                severity = self._classify_resource_risk(res_kind)
                risk = 0.5 if severity == "high" else 0.3 if severity == "medium" else 0.1
                resource_drifts.append({
                    "kind": res_kind,
                    "name": res_name,
                    "namespace": res_ns,
                    "status": "OutOfSync",
                    "severity": severity,
                    "risk_score": risk,
                })
                drifts.append({
                    "type": "resource_drift",
                    "description": f"{res_kind}/{res_name} in {res_ns} is OutOfSync",
                    "expected": "Synced",
                    "actual": "OutOfSync",
                    "severity": severity,
                    "resource": f"{res_kind}/{res_name}",
                    "risk_score": risk,
                })
                total_risk += risk

        return {
            "app_name": app.get("name", ""),
            "project": app.get("project", "default"),
            "drift_count": len(drifts),
            "resource_drift_count": len(resource_drifts),
            "drifts": drifts,
            "resource_drifts": resource_drifts,
            "risk_score": round(total_risk, 2),
            "severity": "critical" if total_risk >= 2.0 else "high" if total_risk >= 1.0 else "medium" if total_risk > 0 else "none",
        }

    def _classify_resource_risk(self, kind: str) -> str:
        k = kind.lower()
        for sev, kinds in self._risk_patterns.items():
            if any(pattern in k for pattern in kinds):
                return sev
        return "low"

    def _categorize_drifts(self, reports: List[Dict[str, Any]]) -> Dict[str, int]:
        categories: Dict[str, int] = {}
        for r in reports:
            for d in r.get("drifts", []):
                t = d.get("type", "unknown")
                categories[t] = categories.get(t, 0) + 1
        return categories


class ArgoCDSyncManager:
    """Manage sync, refresh, and rollback operations."""

    async def sync(self, app_name: str, revision: str = "") -> Dict[str, Any]:
        result = await argocd_connector.sync_application(app_name, revision=revision)
        if result.get("status") != "success":
            return {"status": "error", "error": result.get("error", "sync failed")}
        return {"status": "success", "operation": result.get("data", {}), "app_name": app_name}

    async def refresh(self, app_name: str) -> Dict[str, Any]:
        result = await argocd_connector.refresh_application(app_name)
        if result.get("status") != "success":
            return {"status": "error", "error": result.get("error", "refresh failed")}
        return {"status": "success", "app_name": app_name}

    async def rollback(self, app_name: str, revision_id: int) -> Dict[str, Any]:
        result = await argocd_connector.rollback_application(app_name, revision_id)
        if result.get("status") != "success":
            return {"status": "error", "error": result.get("error", "rollback failed")}
        return {"status": "success", "operation": result.get("data", {}), "app_name": app_name, "revision_id": revision_id}

    async def promote(self, app_name: str, target_revision: str = "") -> Dict[str, Any]:
        """Promote — sync to a specific revision (progressive delivery step)."""
        return await self.sync(app_name, revision=target_revision)


class ArgoCDEventEmitter:
    """Emit ArgoCD events through the EventHub."""

    async def emit_app_synced(self, app: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="argocd.app.synced",
                agent="argocd_intelligence",
                message=f"Application '{app.get('name', '')}' synced to {app.get('revision', '')[:8]}",
                metadata=app,
            )
        except Exception as exc:
            log.debug("ArgoCD event emit failed: %s", exc)

    async def emit_sync_started(self, app_name: str, revision: str) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="argocd.sync.started",
                agent="argocd_intelligence",
                message=f"Sync started for '{app_name}' to {revision[:8] if revision else 'HEAD'}",
                metadata={"app_name": app_name, "revision": revision},
            )
        except Exception as exc:
            log.debug("ArgoCD event emit failed: %s", exc)

    async def emit_sync_failed(self, app_name: str, error: str) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="argocd.sync.failed",
                agent="argocd_intelligence",
                message=f"Sync failed for '{app_name}': {error[:200]}",
                metadata={"app_name": app_name, "error": error},
            )
        except Exception as exc:
            log.debug("ArgoCD event emit failed: %s", exc)

    async def emit_health_degraded(self, app: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="argocd.health.degraded",
                agent="argocd_intelligence",
                message=f"Application '{app.get('name', '')}' health degraded: {app.get('health_status', 'Unknown')}",
                metadata=app,
            )
        except Exception as exc:
            log.debug("ArgoCD event emit failed: %s", exc)

    async def emit_rollback_started(self, app_name: str, revision_id: int) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="argocd.rollback.started",
                agent="argocd_intelligence",
                message=f"Rollback started for '{app_name}' to revision {revision_id}",
                metadata={"app_name": app_name, "revision_id": revision_id},
            )
        except Exception as exc:
            log.debug("ArgoCD event emit failed: %s", exc)

    async def emit_rollback_completed(self, app_name: str, revision_id: int) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="argocd.rollback.completed",
                agent="argocd_intelligence",
                message=f"Rollback completed for '{app_name}' to revision {revision_id}",
                metadata={"app_name": app_name, "revision_id": revision_id},
            )
        except Exception as exc:
            log.debug("ArgoCD event emit failed: %s", exc)

    async def emit_drift_detected(self, report: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="argocd.drift.detected",
                agent="argocd_intelligence",
                message=f"Drift detected in '{report.get('app_name', '')}': {report.get('drift_count', 0)} drifts, risk {report.get('risk_score', 0)}",
                metadata=report,
            )
        except Exception as exc:
            log.debug("ArgoCD event emit failed: %s", exc)


class GitOpsCorrelationChain:
    """Drill-down correlation: app → revision → commit → pipeline → build → image → deployment → pod → logs → trace → metrics → learning → recommendations → Knowledge Graph."""

    async def from_application(self, app_name: str) -> Dict[str, Any]:
        chain: Dict[str, Any] = {"application": app_name, "steps": []}
        chain["steps"].append({"step": "application", "data": app_name})

        # Application → Revision
        try:
            detail = await GitOpsApplicationIntelligence().get_application_detail(app_name)
            app_detail = detail.get("application", {})
            chain["revision"] = app_detail.get("revision", "")
            chain["repo"] = app_detail.get("repo_url", "")
            chain["path"] = app_detail.get("path", "")
            chain["namespace"] = app_detail.get("namespace", "")
            chain["cluster"] = app_detail.get("cluster_url", "")
            chain["steps"].append({"step": "revision", "data": chain["revision"][:8] if chain["revision"] else "HEAD"})
        except Exception:
            pass

        # Revision → Deployments
        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            deps = infrastructure_intelligence.get_dashboard().get("deployments", {})
            chain["deployments"] = deps
            chain["steps"].append({"step": "deployments", "data": deps})
        except Exception:
            pass

        # Deployments → Pods
        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            pods = infrastructure_intelligence.get_dashboard().get("pods", {})
            chain["pods"] = pods
            chain["steps"].append({"step": "pods", "data": pods})
        except Exception:
            pass

        # Pods → Logs
        try:
            from backend.connectors.loki import loki_connector
            if loki_connector.is_ready:
                ns = chain.get("namespace", "")
                log_result = await loki_connector.query(f'{{namespace="{ns}"}} |= "error"', limit=50)
                chain["logs"] = {"entries": len(log_result.get("data", {}).get("result", []))}
                chain["steps"].append({"step": "logs", "count": chain["logs"]["entries"]})
        except Exception:
            pass

        # Logs → Traces
        try:
            from backend.services.enterprise_trace_intelligence import trace_intelligence
            chain["traces"] = await trace_intelligence.get_graph_health()
            chain["steps"].append({"step": "traces", "data": chain["traces"]})
        except Exception:
            pass

        # Traces → Metrics
        try:
            from backend.services.enterprise_prometheus_intelligence import prometheus_metrics
            metrics = await prometheus_metrics.collect_all_metrics()
            chain["metrics"] = {k: v.get("status") for k, v in metrics.items() if isinstance(v, dict)}
            chain["steps"].append({"step": "metrics", "count": len(chain["metrics"])})
        except Exception:
            pass

        # Metrics → Learning
        try:
            from backend.services.enterprise_learning_service import learning_engine
            patterns = learning_engine.get_patterns() if hasattr(learning_engine, "get_patterns") else []
            chain["learning"] = {"patterns": len(patterns)}
            chain["steps"].append({"step": "learning", "data": chain["learning"]})
        except Exception:
            pass

        # Learning → Recommendations
        try:
            from backend.services.enterprise_recommendation_engine import recommendation_engine
            recs = recommendation_engine.get_recommendations(limit=5)
            chain["recommendations"] = recs
            chain["steps"].append({"step": "recommendations", "count": len(recs)})
        except Exception:
            pass

        # Recommendations → Knowledge Graph
        try:
            from backend.services.enterprise_graph_service import knowledge_graph
            chain["knowledge_graph"] = {
                "nodes": len(knowledge_graph.get_all_nodes()),
                "edges": len(knowledge_graph.get_all_edges()),
            }
            chain["steps"].append({"step": "knowledge_graph", "data": chain["knowledge_graph"]})
        except Exception:
            pass

        chain["correlation_id"] = f"gitops_{abs(hash(app_name)) % 10**8:08x}"
        return chain


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------

gitops_app_intel = GitOpsApplicationIntelligence()
gitops_project_intel = GitOpsProjectIntelligence()
gitops_repo_intel = GitOpsRepoIntelligence()
gitops_cluster_intel = GitOpsClusterIntelligence()
drift_detector = DriftDetector()
sync_manager = ArgoCDSyncManager()
argocd_event_emitter = ArgoCDEventEmitter()
gitops_correlation = GitOpsCorrelationChain()
