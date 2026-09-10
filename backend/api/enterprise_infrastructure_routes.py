"""Enterprise Infrastructure Intelligence — REST API.

Exposes Kubernetes, Docker, Helm, Prometheus, Grafana, Loki, OpenTelemetry
endpoints matching the frontend service expectations.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.api.legacy_execution_boundary import guard_legacy_execution
from backend.auth.dependencies import require_user
from backend.safety.ingress_boundary import (
    IngressEnvelope,
    IngressPrincipal,
    audit_ingress,
    bound_body,
    require_ingest_principal,
)

from backend.services.enterprise_argocd_intelligence import (
    argocd_event_emitter,
    drift_detector,
    gitops_app_intel,
    gitops_cluster_intel,
    gitops_correlation,
    gitops_project_intel,
    gitops_repo_intel,
    sync_manager,
)
from backend.services.enterprise_grafana_intelligence import (
    correlation_chain as corr_chain,
)
from backend.services.enterprise_grafana_intelligence import (
    dashboard_intelligence as grafana_dash_intel,
)
from backend.services.enterprise_grafana_intelligence import (
    datasource_intelligence as grafana_ds_intel,
)
from backend.services.enterprise_grafana_intelligence import (
    unified_observability as unified_obs,
)
from backend.services.enterprise_infrastructure_intelligence import (
    INFRA_EVENTS,
    SUPPORTED_PLATFORMS,
    DockerIntelligence,
    GrafanaIntelligence,
    HelmIntelligence,
    KubernetesIntelligence,
    LokiLogIntelligence,
    OpenTelemetryTraceIntelligence,
    PrometheusIntelligence,
    infrastructure_intelligence,
)
from backend.services.enterprise_loki_intelligence import (
    log_analyzer as loki_analyzer,
)
from backend.services.enterprise_loki_intelligence import (
    log_correlator as loki_corr,
)
from backend.services.enterprise_loki_intelligence import (
    log_intelligence as loki_intel,
)
from backend.services.enterprise_loki_intelligence import (
    loki_connector as loki_conn,
)
from backend.services.enterprise_prometheus_intelligence import (
    alert_intelligence as prom_alerts,
)
from backend.services.enterprise_prometheus_intelligence import (
    prometheus_metrics as prom_metrics,
)
from backend.services.enterprise_terraform_intelligence import (
    drift_detector as tf_drift,
)
from backend.services.enterprise_terraform_intelligence import (
    infra_graph_builder as tf_graph,
)
from backend.services.enterprise_terraform_intelligence import (
    progressive_delivery as tf_progressive,
)
from backend.services.enterprise_terraform_intelligence import (
    terraform_correlation as tf_corr,
)
from backend.services.enterprise_terraform_intelligence import (
    terraform_event_emitter as tf_emitter,
)
from backend.services.enterprise_terraform_intelligence import (
    workspace_intel as tf_ws_intel,
)

log = logging.getLogger(__name__)

# Phase 11.1 (ADR-121). Every route on this router needs a verified access
# token: the reads expose one tenant's infrastructure, the ingestion routes
# write into a tenant-unaware store, and the terraform/ArgoCD routes reach real
# providers. Ingestion routes additionally go through the ingress boundary
# (tenant fence, body bound, canonical event identity, audit), and the
# provider-mutating routes sit behind the legacy execution guard, which refuses
# by default (ADR-038): they are V1 execution surfaces that bypass the
# invocation gateway, and were ungated until this phase.
router = APIRouter(
    prefix="/api/infrastructure",
    tags=["Enterprise Infrastructure Intelligence"],
    dependencies=[Depends(require_user)],
)


async def _ingested(request: Request, principal: IngressPrincipal, *, event_type: str,
                    payload: Any, result: Any) -> Dict[str, Any]:
    """Stamp an accepted ingestion with its envelope and audit it."""
    envelope = IngressEnvelope.build(
        source="infrastructure.ingest", event_type=event_type, payload=payload,
        principal=principal,
        event_id=str(payload.get("id") or payload.get("uid") or "") if isinstance(payload, dict) else "",
    )
    await audit_ingress(request, outcome="accepted", source="infrastructure.ingest",
                        principal=principal, envelope=envelope, reason="ingested")
    return {"status": "ingested", "entity": result, "ingress": envelope.to_dict()}


# ---- Request schemas ----

class IngestClusterRequest(BaseModel):
    payload: Dict[str, Any]


class IngestPodRequest(BaseModel):
    payload: Dict[str, Any]


class IngestNodeRequest(BaseModel):
    payload: Dict[str, Any]


class IngestDeploymentRequest(BaseModel):
    payload: Dict[str, Any]


class IngestPvcRequest(BaseModel):
    payload: Dict[str, Any]


class IngestNetworkFailureRequest(BaseModel):
    payload: Dict[str, Any]


class IngestDockerRequest(BaseModel):
    payload: Dict[str, Any]


class IngestHelmRequest(BaseModel):
    payload: Dict[str, Any]


class IngestPrometheusRequest(BaseModel):
    payload: Dict[str, Any]


class IngestGrafanaRequest(BaseModel):
    payload: Dict[str, Any]


class IngestLokiRequest(BaseModel):
    payload: Dict[str, Any]


class IngestOpenTelemetryRequest(BaseModel):
    payload: Dict[str, Any]


class SyncKubernetesRequest(BaseModel):
    context: str = ""


# ---- Platform / Event info -----------------------------------------------------

@router.get("/platforms")
async def list_platforms():
    return {"platforms": SUPPORTED_PLATFORMS}


@router.get("/events")
async def list_events():
    return {"events": INFRA_EVENTS}


# ---- Health / Dashboard ---------------------------------------------------------

@router.get("/health")
async def infrastructure_health():
    return {"status": "ok", "service": "infrastructure_intelligence"}


@router.get("/dashboard")
async def get_dashboard():
    return infrastructure_intelligence.get_dashboard()


@router.get("/timeline")
async def get_timeline(limit: int = Query(50, ge=1, le=500)):
    return {"timeline": infrastructure_intelligence.get_timeline(limit=limit)}


@router.post("/sync")
async def sync_kubernetes(req: SyncKubernetesRequest):
    """Pull live data from the Kubernetes connector for all contexts."""
    result = await infrastructure_intelligence.sync_from_kubernetes(context=req.context)
    if result.get("status") == "skipped":
        raise HTTPException(status_code=503, detail=result.get("reason", "Kubernetes connector not available"))
    return result


# ---- Ingestion (individual endpoints matching frontend) -------------------------

@router.post("/ingest/cluster")
async def ingest_cluster(req: IngestClusterRequest, request: Request,
                         principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_cluster_event("cluster", req.payload)
    return await _ingested(request, principal, event_type="cluster", payload=req.payload, result=result)


@router.post("/ingest/pod")
async def ingest_pod(req: IngestPodRequest, request: Request,
                     principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_pod_event(req.payload)
    return await _ingested(request, principal, event_type="pod", payload=req.payload, result=result)


@router.post("/ingest/node")
async def ingest_node(req: IngestNodeRequest, request: Request,
                      principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_node_event(req.payload)
    return await _ingested(request, principal, event_type="node", payload=req.payload, result=result)


@router.post("/ingest/deployment")
async def ingest_deployment(req: IngestDeploymentRequest, request: Request,
                            principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_deployment_event(req.payload)
    return await _ingested(request, principal, event_type="deployment", payload=req.payload, result=result)


@router.post("/ingest/pvc")
async def ingest_pvc(req: IngestPvcRequest, request: Request,
                     principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_pvc_event(req.payload)
    return await _ingested(request, principal, event_type="pvc", payload=req.payload, result=result)


@router.post("/ingest/network-failure")
async def ingest_network_failure(req: IngestNetworkFailureRequest, request: Request,
                                 principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_network_failure_event(req.payload)
    return await _ingested(request, principal, event_type="network_failure", payload=req.payload, result=result)


@router.post("/ingest/docker")
async def ingest_docker(req: IngestDockerRequest, request: Request,
                        principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_docker_event(req.payload)
    return await _ingested(request, principal, event_type="docker", payload=req.payload, result=result)


@router.post("/ingest/helm")
async def ingest_helm(req: IngestHelmRequest, request: Request,
                      principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_helm_event(req.payload)
    return await _ingested(request, principal, event_type="helm", payload=req.payload, result=result)


@router.post("/ingest/prometheus")
async def ingest_prometheus(req: IngestPrometheusRequest, request: Request,
                            principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_prometheus_event(req.payload)
    return await _ingested(request, principal, event_type="prometheus", payload=req.payload, result=result)


@router.post("/ingest/grafana")
async def ingest_grafana(req: IngestGrafanaRequest, request: Request,
                         principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_grafana_event(req.payload)
    return await _ingested(request, principal, event_type="grafana", payload=req.payload, result=result)


@router.post("/ingest/loki")
async def ingest_loki(req: IngestLokiRequest, request: Request,
                      principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_loki_event(req.payload)
    return await _ingested(request, principal, event_type="loki", payload=req.payload, result=result)


@router.post("/ingest/opentelemetry")
async def ingest_opentelemetry(req: IngestOpenTelemetryRequest, request: Request,
                               principal: IngressPrincipal = Depends(require_ingest_principal)):
    result = await infrastructure_intelligence.ingest_opentelemetry_event(req.payload)
    return await _ingested(request, principal, event_type="opentelemetry", payload=req.payload, result=result)


# ---- Webhook --------------------------------------------------------------------

@router.post("/webhook/kubernetes")
async def kubernetes_webhook(payload: Dict[str, Any], request: Request,
                             principal: IngressPrincipal = Depends(require_ingest_principal)):
    # Kubernetes has no signing scheme for a pushed webhook; the pusher holds a
    # CortexPrime access token and is judged like any other ingestion caller.
    results = await infrastructure_intelligence.ingest_kubernetes_webhook(payload)
    envelope = IngressEnvelope.build(
        source="infrastructure.webhook.kubernetes", event_type="kubernetes",
        payload=payload, principal=principal,
        event_id=str(payload.get("uid") or payload.get("id") or ""),
    )
    await audit_ingress(request, outcome="accepted", source="infrastructure.webhook.kubernetes",
                        principal=principal, envelope=envelope, reason="ingested")
    return {"status": "ingested", "entities": results, "ingress": envelope.to_dict()}


# ---- Clusters ------------------------------------------------------------------

@router.get("/clusters")
async def list_clusters(limit: int = Query(100, ge=1, le=1000)):
    return {"clusters": KubernetesIntelligence.list_clusters(limit=limit)}


@router.get("/clusters/health")
async def get_cluster_health():
    return KubernetesIntelligence.get_cluster_health()


@router.get("/clusters/{cluster_id}")
async def get_cluster(cluster_id: str):
    cluster = KubernetesIntelligence.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


# ---- Nodes ---------------------------------------------------------------------

@router.get("/nodes")
async def list_nodes(
    cluster_id: str = Query("", description="Filter by cluster ID"),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"nodes": KubernetesIntelligence.list_nodes(cluster_id=cluster_id, limit=limit)}


@router.get("/nodes/utilization")
async def get_node_utilization(cluster_id: str = Query("", description="Filter by cluster ID")):
    return KubernetesIntelligence.get_node_utilization(cluster_id=cluster_id)


# ---- Pods ----------------------------------------------------------------------

@router.get("/pods")
async def list_pods(
    namespace: str = Query("", description="Filter by namespace"),
    status: str = Query("", description="Filter by status (running, pending, failed)"),
    cluster_id: str = Query("", description="Filter by cluster ID"),
    limit: int = Query(200, ge=1, le=2000),
):
    return {"pods": KubernetesIntelligence.list_pods(namespace=namespace, status=status, cluster_id=cluster_id, limit=limit)}


@router.get("/pods/health")
async def get_pod_health(namespace: str = Query(""), cluster_id: str = Query("")):
    return KubernetesIntelligence.get_pod_health(namespace=namespace, cluster_id=cluster_id)


# ---- Deployments ---------------------------------------------------------------

@router.get("/deployments")
async def list_deployments(
    namespace: str = Query(""),
    cluster_id: str = Query(""),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"deployments": KubernetesIntelligence.list_deployments(namespace=namespace, cluster_id=cluster_id, limit=limit)}


@router.get("/deployments/health")
async def get_deployment_health(cluster_id: str = Query("")):
    return KubernetesIntelligence.get_deployment_health(cluster_id=cluster_id)


# ---- PVCs ----------------------------------------------------------------------

@router.get("/pvcs")
async def list_pvcs(
    namespace: str = Query(""),
    cluster_id: str = Query(""),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"pvcs": KubernetesIntelligence.list_pvcs(namespace=namespace, cluster_id=cluster_id, limit=limit)}


# ---- Network Failures ----------------------------------------------------------

@router.get("/network-failures")
async def list_network_failures(
    cluster_id: str = Query(""),
    resolved: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"network_failures": KubernetesIntelligence.list_network_failures(cluster_id=cluster_id, resolved=resolved, limit=limit)}


# ---- Docker --------------------------------------------------------------------

@router.get("/docker/containers")
async def list_containers(
    status: str = Query(""),
    host: str = Query(""),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"containers": DockerIntelligence.list_containers(status=status, host=host, limit=limit)}


@router.get("/docker/containers/{docker_id}")
async def get_container(docker_id: str):
    container = DockerIntelligence.get_container(docker_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    return container


@router.get("/docker/health")
async def get_container_health():
    return DockerIntelligence.get_container_health()


# ---- Docker Images -----------------------------------------------------------

@router.get("/docker/images")
async def list_docker_images(limit: int = Query(100, ge=1, le=1000)):
    return {"images": DockerIntelligence.list_images(limit=limit)}


@router.get("/docker/images/{image_entry_id}")
async def get_docker_image(image_entry_id: str):
    image = DockerIntelligence.get_image(image_entry_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


# ---- Docker Volumes -----------------------------------------------------------

@router.get("/docker/volumes")
async def list_docker_volumes(limit: int = Query(100, ge=1, le=1000)):
    return {"volumes": DockerIntelligence.list_volumes(limit=limit)}


# ---- Docker Networks ----------------------------------------------------------

@router.get("/docker/networks")
async def list_docker_networks(limit: int = Query(100, ge=1, le=1000)):
    return {"networks": DockerIntelligence.list_networks(limit=limit)}


# ---- Docker Sync --------------------------------------------------------------

@router.post("/docker/sync")
async def sync_docker():
    result = await infrastructure_intelligence.sync_from_docker()
    if result.get("status") == "skipped":
        raise HTTPException(status_code=503, detail=result.get("reason", "Docker connector not available"))
    return result


# ---- Helm ----------------------------------------------------------------------

@router.get("/helm/releases")
async def list_helm_releases(
    namespace: str = Query(""),
    status: str = Query(""),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"releases": HelmIntelligence.list_releases(namespace=namespace, status=status, limit=limit)}


@router.get("/helm/releases/{release_id}")
async def get_helm_release(release_id: str):
    release = HelmIntelligence.get_release(release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


@router.get("/helm/health")
async def get_helm_health():
    return HelmIntelligence.get_release_health()


# ---- Prometheus ----------------------------------------------------------------

@router.get("/prometheus/alerts")
async def list_alerts(
    severity: str = Query(""),
    status: str = Query(""),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"alerts": PrometheusIntelligence.list_alerts(severity=severity, status=status, limit=limit)}


@router.get("/prometheus/alerts/correlated")
async def get_correlated_alerts(threshold: int = Query(3, ge=1)):
    return PrometheusIntelligence.correlate_alerts(threshold=threshold)


@router.get("/prometheus/stats")
async def get_alert_stats():
    return PrometheusIntelligence.get_alert_stats()


# ---- Prometheus Live Query / Targets / Rules / Metrics -------------------------

@router.post("/prometheus/query")
async def prometheus_query(query: str = Query(..., description="PromQL query string"),
                           time: Optional[str] = Query(None, description="Evaluation timestamp")):
    """Execute an instant PromQL query against the live Prometheus server."""
    try:
        result = await prom_metrics.query(query)
        if result.get("status") == "error":
            raise HTTPException(status_code=503, detail=result.get("error", "Prometheus query failed"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/prometheus/query_range")
async def prometheus_query_range(
    query: str = Query(..., description="PromQL query string"),
    start: str = Query(..., description="Start timestamp (RFC3339 or Unix)"),
    end: str = Query(..., description="End timestamp"),
    step: str = Query("15s", description="Resolution step"),
):
    """Execute a range PromQL query against the live Prometheus server."""
    try:
        result = await prom_metrics.query_range(query, start, end, step)
        if result.get("status") == "error":
            raise HTTPException(status_code=503, detail=result.get("error", "Prometheus range query failed"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/prometheus/targets")
async def prometheus_targets():
    """List scrape targets from the live Prometheus server."""
    try:
        result = await prom_metrics.get_targets()
        if result.get("status") == "error":
            raise HTTPException(status_code=503, detail=result.get("error", "Targets unavailable"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/prometheus/rules")
async def prometheus_rules():
    """List recording and alert rules from the live Prometheus server."""
    try:
        result = await prom_metrics.get_rules()
        if result.get("status") == "error":
            raise HTTPException(status_code=503, detail=result.get("error", "Rules unavailable"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/prometheus/live-alerts")
async def prometheus_live_alerts():
    """Fetch active alerts directly from the live Prometheus Alertmanager API."""
    try:
        result = await prom_alerts.sync_alerts()
        if result.get("status") == "error":
            raise HTTPException(status_code=503, detail=result.get("error", "Alerts unavailable"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/prometheus/metrics")
async def prometheus_metrics_snapshot():
    """Return the latest metric snapshot collected from Prometheus."""
    try:
        return prom_metrics.get_metric_latest()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/prometheus/collect")
async def prometheus_collect():
    """Trigger an immediate collection of all standard Prometheus metrics."""
    try:
        result = await prom_metrics.collect_all_metrics()
        if result.get("errors"):
            return {"status": "partial", "metrics": result.get("metrics", {}), "errors": result.get("errors", [])}
        return {"status": "completed", "metrics": result.get("metrics", {})}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/prometheus/sync-alerts")
async def prometheus_sync_alerts():
    """Sync alerts from Prometheus, correlate with infrastructure, emit events."""
    try:
        result = await prom_alerts.sync_alerts()
        if result.get("status") == "skipped":
            raise HTTPException(status_code=503, detail=result.get("reason", "Prometheus not available"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Grafana (Real Grafana HTTP API) --------------------------------------------

@router.get("/grafana/ready")
async def grafana_ready():
    from backend.connectors.grafana import grafana_connector as gcon
    return {"ready": gcon.is_ready, "org": gcon.org_name}


@router.get("/grafana/health")
async def grafana_health():
    from backend.connectors.grafana import grafana_connector as gcon
    result = await gcon.health()
    if result.get("status") == "success":
        return result.get("data", {})
    raise HTTPException(status_code=502, detail=result.get("error", "Grafana unreachable"))


@router.get("/grafana/org")
async def grafana_org():
    from backend.connectors.grafana import grafana_connector as gcon
    result = await gcon.org()
    if result.get("status") == "success":
        return result.get("data", {})
    raise HTTPException(status_code=502, detail=result.get("error", "Grafana unreachable"))


@router.get("/grafana/dashboards")
async def list_grafana_dashboards(query: str = Query(""), limit: int = Query(100, ge=1, le=500)):
    result = await grafana_dash_intel.discover_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Grafana unreachable"))
    dashboards = result.get("dashboards", [])
    if query:
        q = query.lower()
        dashboards = [d for d in dashboards if q in d.get("title", "").lower() or q in d.get("folder", "").lower()]
    return {"dashboards": dashboards[:limit], "total": len(result.get("dashboards", [])), "discovered_at": result.get("discovered_at", "")}


@router.get("/grafana/dashboards/uid/{uid}")
async def get_grafana_dashboard_by_uid(uid: str):
    result = await grafana_dash_intel.get_dashboard_detail(uid)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return result


@router.get("/grafana/dashboards/{dashboard_id}")
async def get_grafana_dashboard(dashboard_id: str):
    dashboard = GrafanaIntelligence.get_dashboard(dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dashboard


@router.get("/grafana/folders")
async def list_grafana_folders():
    from backend.connectors.grafana import grafana_connector as gcon
    result = await gcon.list_folders()
    if result.get("status") == "success":
        return {"folders": result.get("data", [])}
    raise HTTPException(status_code=502, detail=result.get("error", "Grafana unreachable"))


@router.get("/grafana/datasources")
async def list_grafana_datasources():
    result = await grafana_ds_intel.discover_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Grafana unreachable"))
    return result


@router.get("/grafana/annotations")
async def list_grafana_annotations(limit: int = Query(100, ge=1, le=1000)):
    from backend.connectors.grafana import grafana_connector as gcon
    result = await gcon.list_annotations(limit=limit)
    if result.get("status") == "success":
        return {"annotations": result.get("data", [])}
    raise HTTPException(status_code=502, detail=result.get("error", "Grafana unreachable"))


@router.get("/grafana/alerts")
async def list_grafana_alerts(limit: int = Query(100, ge=1, le=500)):
    from backend.connectors.grafana import grafana_connector as gcon
    result = await gcon.list_alerts(limit=limit)
    if result.get("status") == "success":
        return {"alerts": result.get("data", [])}
    raise HTTPException(status_code=502, detail=result.get("error", "Grafana unreachable"))


@router.get("/grafana/rules")
async def list_grafana_rules():
    from backend.connectors.grafana import grafana_connector as gcon
    result = await gcon.ruler_rules()
    if result.get("status") == "success":
        return {"rules": result.get("data", {})}
    raise HTTPException(status_code=502, detail=result.get("error", "Grafana unreachable"))


@router.get("/grafana/stats")
async def get_grafana_stats():
    return GrafanaIntelligence.get_dashboard_stats()


# ---- Unified Observability Center ------------------------------------------------

@router.get("/observability")
async def get_unified_observability():
    """Aggregate all observability data — infrastructure, metrics, logs, traces, alerts, datasources, recommendations — in one response."""
    result = await unified_obs.get_unified()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail="Unified observability aggregation failed")
    return result


# ---- Correlation Chain ------------------------------------------------------------

@router.post("/correlate")
async def correlate_from_alert(payload: Dict[str, Any]):
    """Drill-down correlation chain: alert → metric → trace → logs → deploy → pod → Knowledge Graph → Learning → Recommendation."""
    alert_name = payload.get("alert", payload.get("alert_name", ""))
    if not alert_name:
        raise HTTPException(status_code=400, detail="'alert' or 'alert_name' required")
    result = await corr_chain.from_alert(alert_name)
    return result


# ---- ArgoCD (Enterprise GitOps) ---------------------------------------------------

@router.get("/argocd/ready")
async def argocd_ready():
    from backend.connectors.argocd import argocd_connector as acon
    return {"ready": acon.is_ready}


@router.get("/argocd/applications")
async def list_argocd_applications():
    result = await gitops_app_intel.discover_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "ArgoCD unreachable"))
    return result


@router.get("/argocd/applications/{name}")
async def get_argocd_application(name: str):
    result = await gitops_app_intel.get_application_detail(name)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail="Application not found")
    return result


@router.get("/argocd/applications/{name}/revisions")
async def get_argocd_revisions(name: str):
    return await gitops_app_intel.get_revision_history(name)


@router.get("/argocd/applications/{name}/resources")
async def get_argocd_resources(name: str):
    return await gitops_app_intel.get_resource_tree(name)


@router.get("/argocd/applications/{name}/events")
async def get_argocd_events(name: str):
    return await gitops_app_intel.get_events(name)


@router.post("/argocd/applications/{name}/sync",
             dependencies=[Depends(guard_legacy_execution("POST /api/infrastructure/argocd/applications/{name}/sync"))])
async def sync_argocd_application(name: str, payload: Dict[str, Any] = {}):
    revision = payload.get("revision", "")
    result = await sync_manager.sync(name, revision=revision)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Sync failed"))
    await argocd_event_emitter.emit_sync_started(name, revision)
    return result


@router.post("/argocd/applications/{name}/refresh",
             dependencies=[Depends(guard_legacy_execution("POST /api/infrastructure/argocd/applications/{name}/refresh"))])
async def refresh_argocd_application(name: str):
    result = await sync_manager.refresh(name)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Refresh failed"))
    return result


@router.post("/argocd/applications/{name}/rollback",
             dependencies=[Depends(guard_legacy_execution("POST /api/infrastructure/argocd/applications/{name}/rollback"))])
async def rollback_argocd_application(name: str, payload: Dict[str, Any]):
    revision_id = payload.get("revision_id", 0)
    if not revision_id:
        raise HTTPException(status_code=400, detail="'revision_id' required")
    await argocd_event_emitter.emit_rollback_started(name, revision_id)
    result = await sync_manager.rollback(name, revision_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Rollback failed"))
    await argocd_event_emitter.emit_rollback_completed(name, revision_id)
    return result


@router.get("/argocd/projects")
async def list_argocd_projects():
    result = await gitops_project_intel.discover_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "ArgoCD unreachable"))
    return result


@router.get("/argocd/repositories")
async def list_argocd_repositories():
    result = await gitops_repo_intel.discover_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "ArgoCD unreachable"))
    return result


@router.get("/argocd/clusters")
async def list_argocd_clusters():
    result = await gitops_cluster_intel.discover_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "ArgoCD unreachable"))
    return result


@router.get("/argocd/drift")
async def detect_argocd_drift():
    apps_result = await gitops_app_intel.discover_all()
    if apps_result.get("status") == "error":
        raise HTTPException(status_code=502, detail=apps_result.get("error", "ArgoCD unreachable"))
    applications = apps_result.get("applications", [])
    result = await drift_detector.detect_all(applications)
    return result


@router.post("/argocd/correlate")
async def correlate_gitops_application(payload: Dict[str, Any]):
    """Drill-down from an ArgoCD app through revision, deployments, pods, logs, traces, metrics, learning, recommendations, Knowledge Graph."""
    app_name = payload.get("application", payload.get("app_name", ""))
    if not app_name:
        raise HTTPException(status_code=400, detail="'application' or 'app_name' required")
    result = await gitops_correlation.from_application(app_name)
    return result


# ---- Terraform (Enterprise Infrastructure as Code) --------------------------------

@router.get("/terraform/ready")
async def terraform_ready():
    from backend.connectors.terraform import terraform_connector as tcon
    return {"ready": tcon.is_ready, "version": tcon.version, "workspace_dir": str(tcon.workspace_dir)}


@router.get("/terraform/version")
async def terraform_version():
    from backend.connectors.terraform import terraform_connector as tcon
    result = await tcon.version()
    return {"version": tcon.version, "output": result.stdout}


@router.get("/terraform/workspaces")
async def terraform_workspaces():
    result = await tf_ws_intel.discover_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Terraform unavailable"))
    return result


@router.get("/terraform/workspaces/current")
async def terraform_current_workspace():
    from backend.connectors.terraform import terraform_connector as tcon
    result = await tcon.workspace_show()
    return {"workspace": result.stdout.strip() if result.success else "default"}


@router.post("/terraform/workspaces/select",
             dependencies=[Depends(guard_legacy_execution("POST /api/infrastructure/terraform/workspaces/select"))])
async def terraform_select_workspace(payload: Dict[str, Any]):
    name = payload.get("name", "default")
    from backend.connectors.terraform import terraform_connector as tcon
    result = await tcon.workspace_select(name)
    if not result.success:
        raise HTTPException(status_code=502, detail=result.stderr[:300])
    return {"status": "success", "workspace": name}


@router.get("/terraform/state")
async def terraform_state():
    result = await tf_ws_intel.get_state_summary()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Terraform unavailable"))
    return result


@router.get("/terraform/outputs")
async def terraform_outputs():
    result = await tf_ws_intel.get_outputs()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Terraform unavailable"))
    return result


@router.get("/terraform/providers")
async def terraform_providers():
    result = await tf_ws_intel.get_providers()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Terraform unavailable"))
    return result


@router.get("/terraform/graph")
async def terraform_graph():
    state_result = await tf_ws_intel.get_state_summary()
    resources = state_result.get("resources", []) if state_result.get("status") == "success" else []
    graph = tf_graph.build_from_state(resources)
    return {"status": "success", "graph": graph}


@router.get("/terraform/drift")
async def terraform_drift():
    result = await tf_drift.detect()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Drift detection failed"))
    await tf_emitter.emit_drift_detected(result.get("drift_count", 0), result.get("risk_score", 0))
    return result


@router.post("/terraform/init",
             dependencies=[Depends(guard_legacy_execution("POST /api/infrastructure/terraform/init"))])
async def terraform_init(payload: Dict[str, Any] = {}):
    upgrade = payload.get("upgrade", False)
    workspace = payload.get("workspace", "default")
    await tf_emitter.emit_init_started(workspace)
    from backend.connectors.terraform import terraform_connector as tcon
    if workspace != "default":
        await tcon.workspace_select(workspace)
    result = await tcon.init(upgrade=upgrade)
    return {
        "status": "success" if result.success else "error",
        "stdout": result.stdout[:3000],
        "stderr": result.stderr[:1000],
        "duration_seconds": result.duration_seconds,
    }


@router.post("/terraform/validate")
async def terraform_validate():
    from backend.connectors.terraform import terraform_connector as tcon
    result = await tcon.validate()
    return {
        "status": "success" if result.success else "error",
        "stdout": result.stdout[:3000],
        "stderr": result.stderr[:1000],
    }


@router.post("/terraform/plan",
             dependencies=[Depends(guard_legacy_execution("POST /api/infrastructure/terraform/plan"))])
async def terraform_plan(payload: Dict[str, Any] = {}):
    workspace = payload.get("workspace", "default")
    destroy = payload.get("destroy", False)
    var_file = payload.get("var_file", "")

    result = await tf_progressive.create_plan(workspace=workspace, destroy=destroy, var_file=var_file)
    if result.get("status") == "success":
        await tf_emitter.emit_plan_completed(
            workspace,
            result["plan"].get("changes", {}),
        )
    return result


@router.post("/terraform/apply",
             dependencies=[Depends(guard_legacy_execution("POST /api/infrastructure/terraform/apply"))])
async def terraform_apply(payload: Dict[str, Any]):
    plan_id = payload.get("plan_id", "")
    workspace = payload.get("workspace", "default")
    if not plan_id:
        raise HTTPException(status_code=400, detail="'plan_id' required")

    await tf_emitter.emit_apply_started(workspace, plan_id)
    result = await tf_progressive.approve_and_apply(plan_id)
    await tf_emitter.emit_apply_completed(workspace, result.get("status") == "success")

    if result.get("plan"):
        for r in result["plan"].get("resources", []):
            if r.get("action") == "create":
                await tf_emitter.emit_resource_created(r["address"], r.get("type", ""), workspace)
    return result


@router.post("/terraform/destroy",
             dependencies=[Depends(guard_legacy_execution("POST /api/infrastructure/terraform/destroy"))])
async def terraform_destroy(payload: Dict[str, Any] = {}):
    workspace = payload.get("workspace", "default")
    await tf_emitter.emit_destroy_started(workspace)
    result = await tf_progressive.destroy_workspace(workspace=workspace)
    await tf_emitter.emit_destroy_completed(workspace, result.get("status") == "success")
    return result


@router.get("/terraform/plans")
async def terraform_list_plans():
    return {"plans": tf_progressive.list_plans()}


@router.post("/terraform/correlate")
async def terraform_correlate(payload: Dict[str, Any]):
    workspace = payload.get("workspace", "default")
    result = await tf_corr.from_workspace(workspace)
    return result


# ---- Loki ----------------------------------------------------------------------

@router.get("/loki/ready")
async def loki_ready():
    return {"ready": loki_conn.is_ready}


@router.get("/loki/labels")
async def loki_labels():
    labels = await loki_intel.list_labels()
    return {"status": "success", "labels": labels}


@router.get("/loki/labels/{label}/values")
async def loki_label_values(label: str):
    values = await loki_intel.list_label_values(label)
    return {"status": "success", "label": label, "values": values}


@router.get("/loki/query")
async def loki_query(
    query: str = Query(..., description="LogQL query string"),
    limit: int = Query(100, ge=1, le=5000),
):
    result = await loki_intel.query(query, limit=limit)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Loki query failed"))
    return result


@router.get("/loki/query_range")
async def loki_query_range(
    query: str = Query(..., description="LogQL query string"),
    start: str = Query(..., description="Start time (nanosecond epoch)"),
    end: str = Query(..., description="End time (nanosecond epoch)"),
    step: str = Query("1m"),
    limit: int = Query(1000, ge=1, le=10000),
):
    result = await loki_intel.query_range(query, start, end, step, limit)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Loki query failed"))
    return result


@router.get("/loki/streams")
async def loki_streams(match: str = Query('{}', description="Label matcher")):
    streams = await loki_intel.list_streams(matchers=[match])
    return {"status": "success", "streams": [s.labels for s in streams]}


@router.get("/loki/streams/logs")
async def loki_stream_logs(
    stream_selector: str = Query(..., description="LogQL stream selector like {pod=\"foo\"}"),
    start: str = Query(...),
    end: str = Query(...),
    limit: int = Query(500, ge=1, le=5000),
):
    result = await loki_intel.get_stream_logs(stream_selector, start, end, limit)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Loki query failed"))
    return result


@router.get("/loki/targets")
async def loki_target_logs(
    target_type: str = Query(..., description="pod|container|deployment|service|namespace|node|app|ingress|job|cronjob"),
    target_name: str = Query(...),
    minutes: int = Query(15, ge=1, le=1440),
    limit: int = Query(500, ge=1, le=5000),
):
    result = await loki_intel.collect_logs_for_target(target_type, target_name, minutes, limit)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Loki query failed"))
    return result


@router.post("/loki/analyze")
async def loki_analyze(payload: Dict[str, Any]):
    logql = payload.get("logql", '{}')
    limit = payload.get("limit", 1000)
    start = payload.get("start", "")
    end = payload.get("end", "")

    if start and end:
        result = await loki_intel.query_range(logql, start, end, limit=limit)
    else:
        result = await loki_intel.query(logql, limit=limit)

    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Loki query failed"))

    streams_data = result.get("streams", [])
    streams = []
    for s in streams_data:
        entries = s.get("entries", [])
        values = [[e.get("timestamp_ns", "0"), e.get("line", "")] for e in entries]
        from backend.services.enterprise_loki_intelligence import LogStream
        streams.append(LogStream(s.get("labels", {}), values))

    analysis = loki_analyzer.analyze_all_streams(streams)
    return {"status": "success", "analysis": analysis}


@router.post("/loki/analyze/stream")
async def loki_analyze_stream(payload: Dict[str, Any]):
    logql = payload.get("logql", '{}')
    limit = payload.get("limit", 500)
    result = await loki_intel.query(logql, limit=limit)

    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Loki query failed"))

    streams_data = result.get("streams", [])
    analyses = []
    for s in streams_data:
        entries = s.get("entries", [])
        values = [[e.get("timestamp_ns", "0"), e.get("line", "")] for e in entries]
        from backend.services.enterprise_loki_intelligence import LogStream
        stream = LogStream(s.get("labels", {}), values)
        analyses.append({
            "labels": stream.labels,
            "analysis": loki_analyzer.analyze_stream(stream),
        })

    return {"status": "success", "stream_analyses": analyses}


@router.post("/loki/correlate")
async def loki_correlate(payload: Dict[str, Any]):
    logql = payload.get("logql", '{}')
    entities = payload.get("entities", {})
    limit = payload.get("limit", 1000)

    result = await loki_intel.query(logql, limit=limit)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Loki query failed"))

    correlation = loki_corr.correlate_batch(result, entities=entities)
    return {"status": "success", "correlation": correlation}


@router.get("/loki/search")
async def loki_search(query: str = Query(...), limit: int = Query(50, ge=1, le=500)):
    logql = f'{{__name__=~".+"}} |= "{query}"'
    result = await loki_intel.query(logql, limit=limit)
    if result.get("status") == "error":
        return {"results": LokiLogIntelligence.search_logs(query=query, limit=limit)}
    entries = []
    for s in result.get("streams", []):
        for e in s.get("entries", []):
            entries.append(e.get("line", ""))
    return {"results": entries[:limit], "source": "loki"}


# ---- Legacy Loki compatibility --------------------------------------------------

@router.get("/loki/analyses")
async def list_loki_analyses(
    stream: str = Query(""),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"analyses": LokiLogIntelligence.list_analyses(stream=stream, limit=limit)}


@router.get("/loki/analyses/{analysis_id}")
async def get_loki_analysis(analysis_id: str):
    analysis = LokiLogIntelligence.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


# ---- OpenTelemetry -------------------------------------------------------------

@router.get("/traces")
async def list_traces(
    service_name: str = Query(""),
    status: str = Query(""),
    limit: int = Query(100, ge=1, le=1000),
):
    return {"traces": OpenTelemetryTraceIntelligence.list_traces(service_name=service_name, status=status, limit=limit)}


@router.get("/traces/{trace_entry_id}")
async def get_trace(trace_entry_id: str):
    trace = OpenTelemetryTraceIntelligence.get_trace(trace_entry_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.get("/traces/health")
async def get_trace_health():
    return OpenTelemetryTraceIntelligence.get_trace_health()


# ---- OTLP HTTP Receiver (standard OpenTelemetry Protocol) ---------------------

@router.post("/otel/v1/traces")
async def otlp_receive_traces(request: Request,
                              principal: IngressPrincipal = Depends(require_ingest_principal)):
    """Standard OTLP HTTP traces endpoint.

    Accepts ExportTraceServiceRequest in protobuf (application/x-protobuf)
    or JSON (application/json) format, as specified by the OpenTelemetry
    Protocol specification. The exporter authenticates with a CortexPrime
    access token in its ``Authorization`` header (Phase 11.1).
    """
    content_type = request.headers.get("content-type", "").lower()
    body = await bound_body(request, source="infrastructure.otlp", principal=principal)

    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")

    try:
        if "json" in content_type:
            result = await infrastructure_intelligence.ingest_otlp_trace(body, content_type="application/json")
        else:
            result = await infrastructure_intelligence.ingest_otlp_trace(body, content_type="application/x-protobuf")

        if result.get("status") == "skipped":
            return JSONResponse(
                status_code=503,
                content={"status": "skipped", "reason": result.get("reason", "OTLP receiver not available")},
            )
        envelope = IngressEnvelope.build(
            source="infrastructure.otlp", event_type="otlp.traces",
            payload={"content_type": content_type, "bytes": len(body),
                     "digest": hashlib.sha256(body).hexdigest()},
            principal=principal,
        )
        await audit_ingress(request, outcome="accepted", source="infrastructure.otlp",
                            principal=principal, envelope=envelope, reason="ingested")
        if isinstance(result, dict):
            result["ingress"] = envelope.to_dict()
        return result
    except Exception as exc:
        log.warning("OTLP /v1/traces handler failed: %s", exc)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


# ---- Service Dependency Graph -------------------------------------------------

@router.get("/traces/graph")
async def get_service_dependency_graph():
    """Return the auto-discovered service dependency graph from OTLP trace data."""
    try:
        from backend.services.enterprise_trace_intelligence import service_graph
        return service_graph.get_graph()
    except Exception as exc:
        log.warning("Service graph unavailable: %s", exc)
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}


@router.get("/traces/services")
async def list_otel_services():
    """List all discovered services from OTLP trace data."""
    try:
        from backend.services.enterprise_trace_intelligence import service_graph
        return {"services": service_graph.list_services()}
    except Exception as exc:
        log.warning("Service list unavailable: %s", exc)
        return {"services": []}


@router.get("/traces/services/{service_name}")
async def get_otel_service_detail(service_name: str):
    """Get detailed info about a specific discovered service."""
    try:
        from backend.services.enterprise_trace_intelligence import service_graph
        detail = service_graph.get_service_detail(service_name)
        if not detail:
            raise HTTPException(status_code=404, detail="Service not found")
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("Service detail unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Service graph not available")


@router.get("/traces/graph/health")
async def get_service_graph_health():
    """Health summary of the service dependency graph."""
    try:
        from backend.services.enterprise_trace_intelligence import service_graph
        return service_graph.get_health()
    except Exception as exc:
        log.warning("Service graph health unavailable: %s", exc)
        return {"total_services": 0, "healthy_services": 0, "services_with_errors": 0, "total_edges": 0}


# ---- Recommendations -----------------------------------------------------------

@router.post("/recommend")
async def generate_recommendation(cluster_id: str = Query("")):
    return await infrastructure_intelligence.generate_recommendation(cluster_id=cluster_id)
