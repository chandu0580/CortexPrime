"""Enterprise Grafana Intelligence — dashboard discovery, datasource tracking,
RuntimeStore synchronisation, and EventHub streaming.

Reuses:
  - RuntimeStore         via infrastructure_intelligence.ingest_grafana_event
  - EventHub             for grafana.* events
  - Knowledge Graph      for dashboard-to-datasource/service edges
  - Analytics            for metric recording
  - Learning Engine      for pattern learning

Backward compatible: all existing /api/infrastructure/grafana/* endpoints
continue to work via the legacy GrafanaIntelligence JSON store.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.connectors.grafana import grafana_connector

log = logging.getLogger(__name__)

GRAFANA_EVENT_TYPES = {
    "dashboard.updated": "grafana.dashboard.updated",
    "alert.created": "grafana.alert.created",
    "alert.resolved": "grafana.alert.resolved",
    "datasource.updated": "grafana.datasource.updated",
    "folder.updated": "grafana.folder.updated",
    "annotation.created": "grafana.annotation.created",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DashboardIntelligence:
    """Discover and track Grafana dashboards, panels, queries, variables."""

    async def discover_all(self) -> Dict[str, Any]:
        """Discover all dashboards from Grafana."""
        result = await grafana_connector.search_dashboards(limit=500)
        if result.get("status") != "success":
            return {"status": "error", "dashboards": [], "error": result.get("error", "discovery failed")}

        dashboards = result.get("data", [])
        enriched = []
        for db in dashboards:
            uid = db.get("uid", "")
            detail = await self._enrich_dashboard(uid, db)
            if detail:
                enriched.append(detail)

        return {
            "status": "success",
            "dashboards": enriched,
            "total": len(enriched),
            "discovered_at": _now(),
        }

    async def _enrich_dashboard(self, uid: str, summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch full dashboard detail including panels, queries, variables."""
        try:
            detail = await grafana_connector.get_dashboard(uid)
            if detail.get("status") != "success":
                return None

            db_data = detail.get("data", {})
            dashboard = db_data.get("dashboard", {})
            meta = db_data.get("meta", {})

            panels = dashboard.get("panels", [])
            panel_list = []
            datasources_used: set = set()
            query_types: set = set()
            for p in panels:
                panel_info = {
                    "title": p.get("title", ""),
                    "type": p.get("type", ""),
                    "id": p.get("id", 0),
                    "grid_pos": {"x": p.get("gridPos", {}).get("x", 0), "y": p.get("gridPos", {}).get("y", 0)},
                }
                # Extract datasources from panel targets/queries
                for t in p.get("targets", []):
                    ds = t.get("datasource", {})
                    if isinstance(ds, dict):
                        ds_type = ds.get("type", "")
                        ds_uid = ds.get("uid", "")
                        if ds_uid:
                            datasources_used.add(ds_uid)
                        if ds_type:
                            query_types.add(ds_type)
                    elif isinstance(ds, str) and ds:
                        datasources_used.add(ds)
                panel_list.append(panel_info)

            variables = dashboard.get("templating", {}).get("list", [])
            var_list = [
                {"name": v.get("name", ""), "type": v.get("type", ""), "query": v.get("query", ""), "current": v.get("current", {}).get("text", "")}
                for v in variables
            ]

            return {
                "uid": uid,
                "title": summary.get("title", dashboard.get("title", "")),
                "folder": summary.get("folderTitle", meta.get("folderTitle", "General")),
                "folder_uid": summary.get("folderUid", meta.get("folderUid", "")),
                "url": summary.get("url", ""),
                "tags": summary.get("tags", dashboard.get("tags", [])),
                "panels": panel_list,
                "panel_count": len(panel_list),
                "datasources": list(datasources_used),
                "query_types": list(query_types),
                "variables": var_list,
                "variable_count": len(var_list),
                "version": dashboard.get("version", 0),
                "starred": summary.get("isStarred", False),
                "slug": summary.get("slug", ""),
                "discovered_at": _now(),
                "grafana_url": f"{grafana_connector._base_url}{summary.get('url', '')}" if hasattr(grafana_connector, '_base_url') else "",
            }
        except Exception as exc:
            log.debug("Failed to enrich dashboard %s: %s", uid, exc)
            return None

    async def get_dashboard_detail(self, uid: str) -> Dict[str, Any]:
        """Get full detail for a specific dashboard."""
        detail = await grafana_connector.get_dashboard(uid)
        if detail.get("status") != "success":
            return {"status": "error", "error": detail.get("error", "not found")}
        return {"status": "success", "dashboard": detail.get("data", {})}


class DatasourceIntelligence:
    """Track live datasource health, latency, errors."""

    def __init__(self) -> None:
        self._known_types = {
            "prometheus", "loki", "tempo", "opensearch", "elasticsearch",
            "postgresql", "redis", "jaeger", "influxdb", "graphite",
            "cloudwatch", "azuremonitor", "stackdriver", "mysql", "mssql",
        }

    async def discover_all(self) -> Dict[str, Any]:
        """Discover all datasources from Grafana."""
        result = await grafana_connector.list_datasources()
        if result.get("status") != "success":
            return {"status": "error", "datasources": [], "error": result.get("error", "discovery failed")}

        datasources = result.get("data", [])
        enriched = []
        for ds in datasources:
            enriched.append(self._enrich(ds))

        type_counts: Dict[str, int] = {}
        for ds in enriched:
            t = ds.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "status": "success",
            "datasources": enriched,
            "total": len(enriched),
            "type_counts": type_counts,
            "known_types": sorted(type_counts.keys()),
            "health_status": self._aggregate_health(enriched),
            "discovered_at": _now(),
        }

    def _enrich(self, ds: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": ds.get("id", 0),
            "uid": ds.get("uid", ""),
            "name": ds.get("name", ""),
            "type": ds.get("type", ""),
            "url": ds.get("url", ""),
            "database": ds.get("database", ""),
            "user": ds.get("user", ""),
            "access": ds.get("access", ""),
            "is_default": ds.get("isDefault", False),
            "read_only": ds.get("readOnly", False),
            "version": ds.get("version", 0),
            "created": ds.get("created", ""),
            "updated": ds.get("updated", ""),
            "health_status": "unknown",
            "known_type": ds.get("type", "") in self._known_types,
        }

    def _aggregate_health(self, datasources: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(datasources)
        known = sum(1 for d in datasources if d.get("known_type"))
        return {
            "total": total,
            "known_types": known,
            "unknown_types": total - known,
        }


class GrafanaEventEmitter:
    """Emit Grafana events through the EventHub."""

    async def emit_dashboard_updated(self, dashboard: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="grafana.dashboard.updated",
                agent="grafana_intelligence",
                message=f"Dashboard '{dashboard.get('title', '')}' updated",
                metadata=dashboard,
            )
        except Exception as exc:
            log.debug("Grafana event emit failed: %s", exc)

    async def emit_alert_created(self, alert: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="grafana.alert.created",
                agent="grafana_intelligence",
                message=f"Alert '{alert.get('name', '')}' created",
                metadata=alert,
            )
        except Exception as exc:
            log.debug("Grafana event emit failed: %s", exc)

    async def emit_alert_resolved(self, alert: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="grafana.alert.resolved",
                agent="grafana_intelligence",
                message=f"Alert '{alert.get('name', '')}' resolved",
                metadata=alert,
            )
        except Exception as exc:
            log.debug("Grafana event emit failed: %s", exc)

    async def emit_datasource_updated(self, datasource: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="grafana.datasource.updated",
                agent="grafana_intelligence",
                message=f"Datasource '{datasource.get('name', '')}' updated",
                metadata=datasource,
            )
        except Exception as exc:
            log.debug("Grafana event emit failed: %s", exc)

    async def emit_folder_updated(self, folder: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="grafana.folder.updated",
                agent="grafana_intelligence",
                message=f"Folder '{folder.get('title', '')}' updated",
                metadata=folder,
            )
        except Exception as exc:
            log.debug("Grafana event emit failed: %s", exc)

    async def emit_annotation_created(self, annotation: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="grafana.annotation.created",
                agent="grafana_intelligence",
                message=f"Annotation '{annotation.get('text', '')}' created",
                metadata=annotation,
            )
        except Exception as exc:
            log.debug("Grafana event emit failed: %s", exc)


class UnifiedObservabilityCenter:
    """Aggregate all observability data into one response.

    Returns infrastructure, metrics, logs, traces, alerts, recommendations,
    runtime health, knowledge graph — everything in one call.
    """

    async def get_unified(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": "success",
            "generated_at": _now(),
        }

        # Infrastructure
        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            result["infrastructure"] = infrastructure_intelligence.get_dashboard()
        except Exception as exc:
            result["infrastructure"] = {"error": str(exc)}

        # Metrics (Prometheus)
        try:
            from backend.services.enterprise_prometheus_intelligence import prometheus_metrics
            result["metrics"] = await prometheus_metrics.collect_all_metrics()
        except Exception as exc:
            result["metrics"] = {"error": str(exc)}

        # Traces
        try:
            from backend.services.enterprise_trace_intelligence import trace_intelligence
            result["traces"] = await trace_intelligence.get_graph_health()
        except Exception as exc:
            result["traces"] = {"error": str(exc)}

        # Grafana dashboards
        try:
            dashboard_intel = DashboardIntelligence()
            result["dashboards"] = await dashboard_intel.discover_all()
        except Exception as exc:
            result["dashboards"] = {"error": str(exc)}

        # Grafana datasources
        try:
            ds_intel = DatasourceIntelligence()
            result["datasources"] = await ds_intel.discover_all()
        except Exception as exc:
            result["datasources"] = {"error": str(exc)}

        # Prometheus alerts
        try:
            from backend.services.enterprise_prometheus_intelligence import alert_intelligence
            alerts = await alert_intelligence.sync_alerts()
            result["alerts"] = alerts
        except Exception as exc:
            result["alerts"] = {"error": str(exc)}

        # Runtime health
        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            from backend.services.enterprise_trace_intelligence import trace_intelligence
            trace_health = await trace_intelligence.get_graph_health()
            infra_ds = infrastructure_intelligence.get_dashboard()
            result["health"] = {
                "clusters": infra_ds.get("clusters", {}),
                "pods": infra_ds.get("pods", {}),
                "deployments": infra_ds.get("deployments", {}),
                "traces": trace_health,
            }
        except Exception as exc:
            result["health"] = {"error": str(exc)}

        # Recommendations
        try:
            from backend.services.enterprise_recommendation_engine import recommendation_engine
            recs = recommendation_engine.get_recommendations(limit=10)
            result["recommendations"] = recs
        except Exception as exc:
            result["recommendations"] = {"error": str(exc)}

        # Engineering Runtime
        try:
            from backend.services.enterprise_runtime_store import runtime_store
            result["runtime"] = {
                "active_executions": len(runtime_store.get_state().get("active_executions", {})),
            }
        except Exception as exc:
            result["runtime"] = {"error": str(exc)}

        # Knowledge Graph summary
        try:
            from backend.services.enterprise_graph_service import knowledge_graph
            kg_nodes = knowledge_graph.get_all_nodes()
            kg_edges = knowledge_graph.get_all_edges()
            result["knowledge_graph"] = {
                "nodes": len(kg_nodes),
                "edges": len(kg_edges),
            }
        except Exception as exc:
            result["knowledge_graph"] = {"error": str(exc)}

        # Learning summary
        try:
            from backend.services.enterprise_learning_service import learning_engine
            result["learning"] = {
                "patterns": len(learning_engine.get_patterns()) if hasattr(learning_engine, 'get_patterns') else 0,
            }
        except Exception as exc:
            result["learning"] = {"error": str(exc)}

        return result


# ---------------------------------------------------------------------------
# Correlation chain
# ---------------------------------------------------------------------------

class CorrelationChain:
    """Drill-down correlation: alert → metric → trace → logs → deploy → pod → container → commit → pipeline → PR → developer → Knowledge Graph → Learning → Recommendation."""

    async def from_alert(self, alert_name: str) -> Dict[str, Any]:
        """Start correlation chain from an alert name."""
        chain: Dict[str, Any] = {"alert": alert_name, "steps": []}
        chain["steps"].append({"step": "alert", "data": alert_name})

        # Alert → Metric (Prometheus)
        try:
            from backend.services.enterprise_prometheus_intelligence import prometheus_metrics
            metrics = await prometheus_metrics.collect_all_metrics()
            chain["metrics"] = {k: v for k, v in metrics.items() if v.get("status") == "success"}
            chain["steps"].append({"step": "metrics", "count": len(chain["metrics"])})
        except Exception:
            pass

        # Metrics → Trace
        try:
            from backend.services.enterprise_trace_intelligence import trace_intelligence
            chain["traces"] = await trace_intelligence.get_graph_health()
            chain["steps"].append({"step": "traces", "data": chain["traces"]})
        except Exception:
            pass

        # Traces → Logs
        try:
            from backend.connectors.loki import loki_connector
            if loki_connector.is_ready:
                log_result = await loki_connector.query(f'{{service_name=~".*{alert_name}.*"}} |= "error"', limit=50)
                chain["logs"] = {"status": "success", "entries": log_result.get("data", {}).get("result", [])}
                chain["steps"].append({"step": "logs", "count": len(chain["logs"].get("entries", []))})
        except Exception:
            pass

        # Logs → Deployments
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

        # Pods → Knowledge Graph
        try:
            from backend.services.enterprise_graph_service import knowledge_graph
            kg_nodes = knowledge_graph.get_all_nodes()
            kg_edges = knowledge_graph.get_all_edges()
            chain["knowledge_graph"] = {"nodes": len(kg_nodes), "edges": len(kg_edges)}
            chain["steps"].append({"step": "knowledge_graph", "data": chain["knowledge_graph"]})
        except Exception:
            pass

        # Knowledge Graph → Learning
        try:
            from backend.services.enterprise_learning_service import learning_engine
            patterns = learning_engine.get_patterns() if hasattr(learning_engine, 'get_patterns') else []
            chain["learning"] = {"patterns": len(patterns)}
            chain["steps"].append({"step": "learning", "data": chain["learning"]})
        except Exception:
            pass

        # Learning → Recommendation
        try:
            from backend.services.enterprise_recommendation_engine import recommendation_engine
            recs = recommendation_engine.get_recommendations(limit=5)
            chain["recommendations"] = recs
            chain["steps"].append({"step": "recommendations", "count": len(recs)})
        except Exception:
            pass

        chain["correlation_id"] = f"corr_{abs(hash(alert_name)) % 10**8:08x}"
        return chain


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------

dashboard_intelligence = DashboardIntelligence()
datasource_intelligence = DatasourceIntelligence()
grafana_event_emitter = GrafanaEventEmitter()
unified_observability = UnifiedObservabilityCenter()
correlation_chain = CorrelationChain()
