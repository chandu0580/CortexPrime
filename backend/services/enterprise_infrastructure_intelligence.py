"""
Enterprise Infrastructure Intelligence — Kubernetes, Docker, Helm, Prometheus,
Grafana, Loki, and OpenTelemetry integration.

Reuses Monitoring, Recommendation, Learning, Knowledge Graph, Replay,
Analytics, Delivery, Engineering Executive, and CI/CD Intelligence.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("INFRASTRUCTURE_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "infrastructure")))
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_CLUSTERS_FILE = _DATA_DIR / "clusters.json"
_PODS_FILE = _DATA_DIR / "pods.json"
_NODES_FILE = _DATA_DIR / "nodes.json"
_DEPLOYMENTS_FILE = _DATA_DIR / "deployments.json"
_CONTAINERS_FILE = _DATA_DIR / "containers.json"
_HELM_RELEASES_FILE = _DATA_DIR / "helm_releases.json"
_PROMETHEUS_ALERTS_FILE = _DATA_DIR / "prometheus_alerts.json"
_GRAFANA_DASHBOARDS_FILE = _DATA_DIR / "grafana_dashboards.json"
_LOKI_LOGS_FILE = _DATA_DIR / "loki_logs.json"
_TRACES_FILE = _DATA_DIR / "traces.json"
_PVCS_FILE = _DATA_DIR / "pvcs.json"
_DOCKER_CONTAINERS_FILE = _DATA_DIR / "docker_containers.json"
_DOCKER_IMAGES_FILE = _DATA_DIR / "docker_images.json"
_DOCKER_VOLUMES_FILE = _DATA_DIR / "docker_volumes.json"
_DOCKER_NETWORKS_FILE = _DATA_DIR / "docker_networks.json"
_NETWORK_FAILURES_FILE = _DATA_DIR / "network_failures.json"

# =============================================================================
# Event constants
# =============================================================================

INFRA_EVENTS: Dict[str, str] = {
    "cluster_health_changed": "infra.cluster_health_changed",
    "pod_status_changed": "infra.pod_status_changed",
    "node_status_changed": "infra.node_status_changed",
    "node_utilization_updated": "infra.node_utilization_updated",
    "deployment_rollout_updated": "infra.deployment_rollout_updated",
    "deployment_rollback_detected": "infra.deployment_rollback_detected",
    "container_restarted": "infra.container_restarted",
    "container_oomkilled": "infra.container_oomkilled",
    "container_crashloop": "infra.container_crashloop",
    "pvc_health_changed": "infra.pvc_health_changed",
    "network_failure_detected": "infra.network_failure_detected",
    "docker_container_tracked": "infra.docker_container_tracked",
    "docker_container_started": "docker.container.started",
    "docker_container_stopped": "docker.container.stopped",
    "docker_container_restarted": "docker.container.restarted",
    "docker_container_failed": "docker.container.failed",
    "docker_container_paused": "docker.container.paused",
    "docker_image_pulled": "docker.image.pulled",
    "docker_image_removed": "docker.image.removed",
    "docker_network_created": "docker.network.created",
    "docker_volume_created": "docker.volume.created",
    "helm_release_tracked": "infra.helm_release_tracked",
    "prometheus_alert_correlated": "infra.prometheus_alert_correlated",
    "grafana_dashboard_discovered": "infra.grafana_dashboard_discovered",
    "grafana_dashboard_updated": "grafana.dashboard.updated",
    "grafana_alert_created": "grafana.alert.created",
    "grafana_alert_resolved": "grafana.alert.resolved",
    "grafana_datasource_updated": "grafana.datasource.updated",
    "grafana_folder_updated": "grafana.folder.updated",
    "grafana_annotation_created": "grafana.annotation.created",
    "argocd_app_synced": "argocd.app.synced",
    "argocd_sync_started": "argocd.sync.started",
    "argocd_sync_failed": "argocd.sync.failed",
    "argocd_health_degraded": "argocd.health.degraded",
    "argocd_rollback_started": "argocd.rollback.started",
    "argocd_rollback_completed": "argocd.rollback.completed",
    "argocd_drift_detected": "argocd.drift.detected",
    "terraform_init_started": "terraform.init.started",
    "terraform_plan_completed": "terraform.plan.completed",
    "terraform_apply_started": "terraform.apply.started",
    "terraform_apply_completed": "terraform.apply.completed",
    "terraform_destroy_started": "terraform.destroy.started",
    "terraform_destroy_completed": "terraform.destroy.completed",
    "terraform_drift_detected": "terraform.drift.detected",
    "terraform_workspace_updated": "terraform.workspace.updated",
    "terraform_resource_created": "terraform.resource.created",
    "terraform_resource_deleted": "terraform.resource.deleted",
    "loki_log_analysis_completed": "infra.loki_log_analysis_completed",
    "opentelemetry_trace_analyzed": "infra.opentelemetry_trace_analyzed",
    "loki_log_received": "loki.log.received",
    "loki_error_detected": "loki.error.detected",
    "loki_warning_detected": "loki.warning.detected",
    "loki_stream_updated": "loki.stream.updated",
    "loki_pattern_detected": "loki.pattern.detected",
    "otel_trace_started": "otel.trace.started",
    "otel_trace_completed": "otel.trace.completed",
    "otel_span_failed": "otel.span.failed",
    "otel_trace_error": "otel.trace.error",
    "otel_service_discovered": "otel.service.discovered",
    "otel_service_updated": "otel.service.updated",
    "prometheus_metric_updated": "prometheus.metric.updated",
    "prometheus_alert_firing": "prometheus.alert.firing",
    "prometheus_alert_resolved": "prometheus.alert.resolved",
    "prometheus_target_down": "prometheus.target.down",
    "prometheus_target_up": "prometheus.target.up",
    "prometheus_rule_updated": "prometheus.rule.updated",
}

SUPPORTED_PLATFORMS = [
    "kubernetes", "docker", "helm", "prometheus", "grafana", "loki", "opentelemetry",
]

# =============================================================================
# Helpers
# =============================================================================


def _load_json(path: Path) -> List[Dict[str, Any]]:
    if path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except OSError as exc:
        log.warning("Failed to save %s: %s", path.name, exc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "infra") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# =============================================================================
# Part 1 — Kubernetes Intelligence
# =============================================================================


class KubernetesIntelligence:
    """Cluster, node, pod, and deployment health tracking."""

    @staticmethod
    def track_cluster(name: str, provider: str = "", version: str = "", nodes_total: int = 0, nodes_ready: int = 0) -> Dict[str, Any]:
        clusters = _load_json(_CLUSTERS_FILE)
        existing = next((c for c in clusters if c.get("name") == name), None)
        if existing:
            existing["provider"] = provider or existing["provider"]
            existing["version"] = version or existing["version"]
            existing["nodes_total"] = nodes_total
            existing["nodes_ready"] = nodes_ready
            existing["status"] = "healthy" if nodes_ready == nodes_total else "degraded"
            existing["updated_at"] = _now()
            result = existing
        else:
            cluster = {
                "cluster_id": _id("cluster"),
                "name": name,
                "provider": provider,
                "version": version,
                "nodes_total": nodes_total,
                "nodes_ready": nodes_ready,
                "status": "healthy" if nodes_ready == nodes_total else "degraded",
                "created_at": _now(),
                "updated_at": _now(),
            }
            clusters.append(cluster)
            result = cluster
        _save_json(_CLUSTERS_FILE, clusters)
        return result

    @staticmethod
    def list_clusters(limit: int = 100) -> List[Dict[str, Any]]:
        return _load_json(_CLUSTERS_FILE)[:limit]

    @staticmethod
    def get_cluster(cluster_id: str) -> Optional[Dict[str, Any]]:
        return next((c for c in _load_json(_CLUSTERS_FILE) if c.get("cluster_id") == cluster_id), None)

    @staticmethod
    def get_cluster_health() -> Dict[str, Any]:
        clusters = _load_json(_CLUSTERS_FILE)
        total = len(clusters)
        healthy = sum(1 for c in clusters if c.get("status") == "healthy")
        degraded = total - healthy
        return {"total": total, "healthy": healthy, "degraded": degraded}

    @staticmethod
    def track_node(cluster_id: str, name: str, status: str = "ready", cpu_usage: float = 0.0, memory_usage: float = 0.0, disk_usage: float = 0.0) -> Dict[str, Any]:
        nodes = _load_json(_NODES_FILE)
        existing = next((n for n in nodes if n.get("name") == name), None)
        if existing:
            existing["status"] = status
            existing["cpu_usage"] = cpu_usage
            existing["memory_usage"] = memory_usage
            existing["disk_usage"] = disk_usage
            existing["updated_at"] = _now()
            result = existing
        else:
            node = {
                "node_id": _id("node"),
                "cluster_id": cluster_id,
                "name": name,
                "status": status,
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "disk_usage": disk_usage,
                "created_at": _now(),
                "updated_at": _now(),
            }
            nodes.append(node)
            result = node
        _save_json(_NODES_FILE, nodes)
        return result

    @staticmethod
    def list_nodes(cluster_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        nodes = _load_json(_NODES_FILE)
        if cluster_id:
            nodes = [n for n in nodes if n.get("cluster_id") == cluster_id]
        return nodes[:limit]

    @staticmethod
    def get_node_utilization(cluster_id: str = "") -> Dict[str, Any]:
        nodes = _load_json(_NODES_FILE)
        if cluster_id:
            nodes = [n for n in nodes if n.get("cluster_id") == cluster_id]
        if not nodes:
            return {"avg_cpu": 0.0, "avg_memory": 0.0, "avg_disk": 0.0, "node_count": 0}
        return {
            "avg_cpu": round(sum(n.get("cpu_usage", 0.0) for n in nodes) / len(nodes), 2),
            "avg_memory": round(sum(n.get("memory_usage", 0.0) for n in nodes) / len(nodes), 2),
            "avg_disk": round(sum(n.get("disk_usage", 0.0) for n in nodes) / len(nodes), 2),
            "node_count": len(nodes),
        }

    @staticmethod
    def track_pod(cluster_id: str, namespace: str, name: str, status: str = "running",
                  restarts: int = 0, container_statuses: Optional[List[Dict[str, Any]]] = None,
                  node_name: str = "", phase: str = "Running") -> Dict[str, Any]:
        pods = _load_json(_PODS_FILE)
        existing = next((p for p in pods if p.get("name") == name and p.get("namespace") == namespace), None)
        now = _now()
        container_statuses = container_statuses or []
        oom = False
        crashloop = False
        for cs_item in container_statuses:
            if isinstance(cs_item, dict):
                if "last_state" in cs_item:
                    lst = cs_item["last_state"]
                    if isinstance(lst, dict) and lst.get("terminated", {}).get("reason") == "OOMKilled":
                        oom = True
                    if isinstance(lst, dict) and lst.get("waiting", {}).get("reason") == "CrashLoopBackOff":
                        crashloop = True

        if existing:
            existing["status"] = status
            existing["phase"] = phase
            existing["restarts"] = restarts
            existing["container_statuses"] = container_statuses
            existing["node_name"] = node_name or existing["node_name"]
            existing["updated_at"] = now
            existing["oom_detected"] = oom
            existing["crashloop_detected"] = crashloop
            result = existing
        else:
            pod = {
                "pod_id": _id("pod"),
                "cluster_id": cluster_id,
                "namespace": namespace,
                "name": name,
                "status": status,
                "phase": phase,
                "restarts": restarts,
                "container_statuses": container_statuses,
                "node_name": node_name,
                "oom_detected": oom,
                "crashloop_detected": crashloop,
                "created_at": now,
                "updated_at": now,
            }
            pods.append(pod)
            result = pod
        _save_json(_PODS_FILE, pods)

        return result

    @staticmethod
    def list_pods(namespace: str = "", status: str = "", cluster_id: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        pods = _load_json(_PODS_FILE)
        if namespace:
            pods = [p for p in pods if p.get("namespace") == namespace]
        if status:
            pods = [p for p in pods if p.get("status") == status]
        if cluster_id:
            pods = [p for p in pods if p.get("cluster_id") == cluster_id]
        return pods[:limit]

    @staticmethod
    def get_pod_health(namespace: str = "", cluster_id: str = "") -> Dict[str, Any]:
        pods = _load_json(_PODS_FILE)
        if namespace:
            pods = [p for p in pods if p.get("namespace") == namespace]
        if cluster_id:
            pods = [p for p in pods if p.get("cluster_id") == cluster_id]
        total = len(pods)
        running = sum(1 for p in pods if p.get("status") == "running")
        pending = sum(1 for p in pods if p.get("status") == "pending")
        failed = sum(1 for p in pods if p.get("status") in ("failed", "error", "crashloop"))
        oom = sum(1 for p in pods if p.get("oom_detected"))
        crashloop = sum(1 for p in pods if p.get("crashloop_detected"))
        return {"total": total, "running": running, "pending": pending, "failed": failed, "oom": oom, "crashloop": crashloop}

    @staticmethod
    def track_deployment(cluster_id: str, namespace: str, name: str, replicas: int = 0,
                         available: int = 0, status: str = "available",
                         rollout_status: str = "completed", image: str = "",
                         strategy: str = "rolling_update") -> Dict[str, Any]:
        deps = _load_json(_DEPLOYMENTS_FILE)
        existing = next((d for d in deps if d.get("name") == name and d.get("namespace") == namespace), None)
        now = _now()
        if existing:
            existing["replicas"] = replicas
            existing["available"] = available
            existing["status"] = status
            existing["rollout_status"] = rollout_status
            existing["image"] = image or existing["image"]
            existing["strategy"] = strategy or existing["strategy"]
            existing["updated_at"] = now
            result = existing
        else:
            dep = {
                "deployment_id": _id("dep"),
                "cluster_id": cluster_id,
                "namespace": namespace,
                "name": name,
                "replicas": replicas,
                "available": available,
                "status": status,
                "rollout_status": rollout_status,
                "image": image,
                "strategy": strategy,
                "created_at": now,
                "updated_at": now,
            }
            deps.append(dep)
            result = dep
        _save_json(_DEPLOYMENTS_FILE, deps)
        return result

    @staticmethod
    def list_deployments(namespace: str = "", cluster_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        deps = _load_json(_DEPLOYMENTS_FILE)
        if namespace:
            deps = [d for d in deps if d.get("namespace") == namespace]
        if cluster_id:
            deps = [d for d in deps if d.get("cluster_id") == cluster_id]
        return deps[:limit]

    @staticmethod
    def get_deployment_health(cluster_id: str = "") -> Dict[str, Any]:
        deps = _load_json(_DEPLOYMENTS_FILE)
        if cluster_id:
            deps = [d for d in deps if d.get("cluster_id") == cluster_id]
        total = len(deps)
        available = sum(1 for d in deps if d.get("status") == "available")
        degraded = sum(1 for d in deps if d.get("status") == "degraded")
        unavailable = sum(1 for d in deps if d.get("status") in ("unavailable", "failed"))
        rollouts = sum(1 for d in deps if d.get("rollout_status") == "progressing")
        rollbacks = sum(1 for d in deps if d.get("rollout_status") == "rollback")
        return {"total": total, "available": available, "degraded": degraded, "unavailable": unavailable, "rollouts_in_progress": rollouts, "rollbacks": rollbacks}

    @staticmethod
    def track_pvc(cluster_id: str, namespace: str, name: str, status: str = "bound",
                  capacity_bytes: int = 0, used_bytes: int = 0, volume_name: str = "") -> Dict[str, Any]:
        pvcs = _load_json(_PVCS_FILE)
        existing = next((p for p in pvcs if p.get("name") == name and p.get("namespace") == namespace), None)
        now = _now()
        if existing:
            existing["status"] = status
            existing["capacity_bytes"] = capacity_bytes
            existing["used_bytes"] = used_bytes
            existing["volume_name"] = volume_name or existing["volume_name"]
            existing["updated_at"] = now
            result = existing
        else:
            pvc = {
                "pvc_id": _id("pvc"),
                "cluster_id": cluster_id,
                "namespace": namespace,
                "name": name,
                "status": status,
                "capacity_bytes": capacity_bytes,
                "used_bytes": used_bytes,
                "volume_name": volume_name,
                "created_at": now,
                "updated_at": now,
            }
            pvcs.append(pvc)
            result = pvc
        _save_json(_PVCS_FILE, pvcs)
        return result

    @staticmethod
    def list_pvcs(namespace: str = "", cluster_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        pvcs = _load_json(_PVCS_FILE)
        if namespace:
            pvcs = [p for p in pvcs if p.get("namespace") == namespace]
        if cluster_id:
            pvcs = [p for p in pvcs if p.get("cluster_id") == cluster_id]
        return pvcs[:limit]

    @staticmethod
    def track_network_failure(cluster_id: str, namespace: str, source: str, destination: str,
                              reason: str = "timeout", protocol: str = "TCP", port: int = 0) -> Dict[str, Any]:
        failures = _load_json(_NETWORK_FAILURES_FILE)
        nf = {
            "failure_id": _id("netfail"),
            "cluster_id": cluster_id,
            "namespace": namespace,
            "source": source,
            "destination": destination,
            "reason": reason,
            "protocol": protocol,
            "port": port,
            "detected_at": _now(),
            "resolved": False,
        }
        failures.append(nf)
        _save_json(_NETWORK_FAILURES_FILE, failures)
        return nf

    @staticmethod
    def list_network_failures(cluster_id: str = "", resolved: Optional[bool] = None, limit: int = 100) -> List[Dict[str, Any]]:
        nfs = _load_json(_NETWORK_FAILURES_FILE)
        if cluster_id:
            nfs = [n for n in nfs if n.get("cluster_id") == cluster_id]
        if resolved is not None:
            nfs = [n for n in nfs if n.get("resolved") == resolved]
        return nfs[:limit]


# =============================================================================
# Part 2 — Docker Intelligence
# =============================================================================


class DockerIntelligence:
    """Docker container, image, volume, and network tracking."""

    @staticmethod
    def track_container(container_id: str, name: str, image: str, status: str = "running",
                        ports: Optional[List[str]] = None, restart_count: int = 0,
                        host: str = "localhost", created_at: str = "",
                        health: str = "", labels: Optional[Dict[str, str]] = None,
                        volumes: Optional[List[Dict[str, Any]]] = None,
                        networks: Optional[List[str]] = None,
                        environment: Optional[List[str]] = None) -> Dict[str, Any]:
        containers = _load_json(_DOCKER_CONTAINERS_FILE)
        existing = next((c for c in containers if c.get("container_id") == container_id), None)
        now = _now()
        docker_id = existing.get("docker_id") if existing else _id("docker")
        if existing:
            existing["name"] = name
            existing["image"] = image
            existing["status"] = status
            existing["ports"] = ports or existing.get("ports", [])
            existing["restart_count"] = restart_count
            existing["health"] = health or existing.get("health", "")
            if labels is not None:
                existing["labels"] = labels
            if volumes is not None:
                existing["volumes"] = volumes
            if networks is not None:
                existing["networks"] = networks
            if environment is not None:
                existing["environment"] = environment
            existing["updated_at"] = now
            result = existing
        else:
            c = {
                "docker_id": docker_id,
                "container_id": container_id,
                "name": name,
                "image": image,
                "status": status,
                "ports": ports or [],
                "restart_count": restart_count,
                "host": host,
                "health": health,
                "labels": labels or {},
                "volumes": volumes or [],
                "networks": networks or [],
                "environment": environment or [],
                "created_at": created_at or now,
                "updated_at": now,
            }
            containers.append(c)
            result = c
        _save_json(_DOCKER_CONTAINERS_FILE, containers)
        return result

    @staticmethod
    def list_containers(status: str = "", host: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        containers = _load_json(_DOCKER_CONTAINERS_FILE)
        if status:
            containers = [c for c in containers if c.get("status") == status]
        if host:
            containers = [c for c in containers if c.get("host") == host]
        return containers[:limit]

    @staticmethod
    def get_container(docker_id: str) -> Optional[Dict[str, Any]]:
        return next((c for c in _load_json(_DOCKER_CONTAINERS_FILE) if c.get("docker_id") == docker_id), None)

    @staticmethod
    def get_container_health() -> Dict[str, Any]:
        containers = _load_json(_DOCKER_CONTAINERS_FILE)
        total = len(containers)
        running = sum(1 for c in containers if c.get("status") in ("running", "up"))
        stopped = sum(1 for c in containers if c.get("status") in ("stopped", "exited"))
        paused = sum(1 for c in containers if c.get("status") == "paused")
        unhealthy = sum(1 for c in containers if c.get("health") == "unhealthy" or c.get("status") in ("dead", "error"))
        return {"total": total, "running": running, "stopped": stopped, "paused": paused, "unhealthy": unhealthy}

    # ---- Images ----

    @staticmethod
    def track_image(image_id: str, tags: Optional[List[str]] = None,
                    size_bytes: int = 0, created_at: str = "",
                    repository: str = "", digest: str = "",
                    architecture: str = "") -> Dict[str, Any]:
        images = _load_json(_DOCKER_IMAGES_FILE)
        existing = next((i for i in images if i.get("image_id") == image_id), None)
        now = _now()
        if existing:
            existing["tags"] = tags or existing.get("tags", [])
            existing["size_bytes"] = size_bytes
            existing["digest"] = digest or existing.get("digest", "")
            existing["repository"] = repository or existing.get("repository", "")
            existing["updated_at"] = now
            result = existing
        else:
            img = {
                "image_entry_id": _id("dimg"),
                "image_id": image_id,
                "tags": tags or [],
                "size_bytes": size_bytes,
                "created_at": created_at or now,
                "repository": repository,
                "digest": digest,
                "architecture": architecture,
                "updated_at": now,
            }
            images.append(img)
            result = img
        _save_json(_DOCKER_IMAGES_FILE, images)
        return result

    @staticmethod
    def list_images(limit: int = 100) -> List[Dict[str, Any]]:
        images = _load_json(_DOCKER_IMAGES_FILE)
        return images[:limit]

    @staticmethod
    def get_image(image_entry_id: str) -> Optional[Dict[str, Any]]:
        return next((i for i in _load_json(_DOCKER_IMAGES_FILE) if i.get("image_entry_id") == image_entry_id), None)

    @staticmethod
    def get_image_health() -> Dict[str, Any]:
        images = _load_json(_DOCKER_IMAGES_FILE)
        total = len(images)
        with_digest = sum(1 for i in images if i.get("digest"))
        return {"total": total, "with_digest": with_digest}

    # ---- Volumes ----

    @staticmethod
    def track_volume(name: str, driver: str = "local", mountpoint: str = "",
                     labels: Optional[Dict[str, str]] = None,
                     created_at: str = "") -> Dict[str, Any]:
        volumes = _load_json(_DOCKER_VOLUMES_FILE)
        existing = next((v for v in volumes if v.get("name") == name), None)
        now = _now()
        if existing:
            existing["driver"] = driver or existing.get("driver", "local")
            existing["labels"] = labels or existing.get("labels", {})
            existing["updated_at"] = now
            result = existing
        else:
            vol = {
                "volume_id": _id("dvol"),
                "name": name,
                "driver": driver,
                "mountpoint": mountpoint,
                "labels": labels or {},
                "created_at": created_at or now,
                "updated_at": now,
            }
            volumes.append(vol)
            result = vol
        _save_json(_DOCKER_VOLUMES_FILE, volumes)
        return result

    @staticmethod
    def list_volumes(limit: int = 100) -> List[Dict[str, Any]]:
        volumes = _load_json(_DOCKER_VOLUMES_FILE)
        return volumes[:limit]

    @staticmethod
    def get_volume_health() -> Dict[str, Any]:
        volumes = _load_json(_DOCKER_VOLUMES_FILE)
        return {"total": len(volumes)}

    # ---- Networks ----

    @staticmethod
    def track_network(name: str, driver: str = "bridge", scope: str = "local",
                      subnet: str = "", labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        networks = _load_json(_DOCKER_NETWORKS_FILE)
        existing = next((n for n in networks if n.get("name") == name), None)
        now = _now()
        if existing:
            existing["driver"] = driver or existing.get("driver", "bridge")
            existing["scope"] = scope or existing.get("scope", "local")
            existing["updated_at"] = now
            result = existing
        else:
            net = {
                "network_id": _id("dnet"),
                "name": name,
                "driver": driver,
                "scope": scope,
                "subnet": subnet,
                "labels": labels or {},
                "created_at": now,
                "updated_at": now,
            }
            networks.append(net)
            result = net
        _save_json(_DOCKER_NETWORKS_FILE, networks)
        return result

    @staticmethod
    def list_networks(limit: int = 100) -> List[Dict[str, Any]]:
        networks = _load_json(_DOCKER_NETWORKS_FILE)
        return networks[:limit]

    @staticmethod
    def get_network_health() -> Dict[str, Any]:
        networks = _load_json(_DOCKER_NETWORKS_FILE)
        return {"total": len(networks)}


# =============================================================================
# Part 3 — Helm Intelligence
# =============================================================================


class HelmIntelligence:
    """Helm release tracking."""

    @staticmethod
    def track_release(name: str, namespace: str, chart: str, version: str = "",
                      revision: int = 1, status: str = "deployed",
                      cluster_id: str = "", values: Optional[Dict[str, Any]] = None,
                      notes: str = "") -> Dict[str, Any]:
        releases = _load_json(_HELM_RELEASES_FILE)
        existing = next((r for r in releases if r.get("name") == name and r.get("namespace") == namespace), None)
        now = _now()
        if existing:
            existing["chart"] = chart or existing["chart"]
            existing["version"] = version or existing["version"]
            existing["revision"] = revision
            existing["status"] = status
            existing["values"] = values or existing.get("values")
            existing["notes"] = notes or existing.get("notes", "")
            existing["updated_at"] = now
            result = existing
        else:
            r = {
                "release_id": _id("helm"),
                "name": name,
                "namespace": namespace,
                "chart": chart,
                "version": version,
                "revision": revision,
                "status": status,
                "cluster_id": cluster_id,
                "values": values,
                "notes": notes,
                "created_at": now,
                "updated_at": now,
            }
            releases.append(r)
            result = r
        _save_json(_HELM_RELEASES_FILE, releases)
        return result

    @staticmethod
    def list_releases(namespace: str = "", status: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        releases = _load_json(_HELM_RELEASES_FILE)
        if namespace:
            releases = [r for r in releases if r.get("namespace") == namespace]
        if status:
            releases = [r for r in releases if r.get("status") == status]
        return releases[:limit]

    @staticmethod
    def get_release(release_id: str) -> Optional[Dict[str, Any]]:
        return next((r for r in _load_json(_HELM_RELEASES_FILE) if r.get("release_id") == release_id), None)

    @staticmethod
    def get_release_health() -> Dict[str, Any]:
        releases = _load_json(_HELM_RELEASES_FILE)
        total = len(releases)
        deployed = sum(1 for r in releases if r.get("status") == "deployed")
        failed = sum(1 for r in releases if r.get("status") == "failed")
        pending = sum(1 for r in releases if r.get("status") in ("pending-install", "pending-upgrade"))
        return {"total": total, "deployed": deployed, "failed": failed, "pending": pending}


# =============================================================================
# Part 4 — Prometheus Intelligence
# =============================================================================


class PrometheusIntelligence:
    """Prometheus alert correlation and tracking."""

    @staticmethod
    def track_alert(alert_name: str, severity: str = "warning", status: str = "firing",
                    labels: Optional[Dict[str, str]] = None, annotations: Optional[Dict[str, str]] = None,
                    starts_at: str = "", ends_at: str = "", value: float = 1.0,
                    generator_url: str = "") -> Dict[str, Any]:
        alerts = _load_json(_PROMETHEUS_ALERTS_FILE)
        existing = next((a for a in alerts if a.get("alert_name") == alert_name and a.get("status") == "firing"), None)
        now = _now()
        if existing:
            existing["severity"] = severity
            existing["value"] = value
            existing["annotations"] = annotations or existing.get("annotations")
            existing["updated_at"] = now
            result = existing
        else:
            a = {
                "alert_id": _id("alert"),
                "alert_name": alert_name,
                "severity": severity,
                "status": status,
                "labels": labels or {},
                "annotations": annotations or {},
                "starts_at": starts_at or now,
                "ends_at": ends_at,
                "value": value,
                "generator_url": generator_url,
                "created_at": now,
                "updated_at": now,
            }
            alerts.append(a)
            result = a
        _save_json(_PROMETHEUS_ALERTS_FILE, alerts)
        return result

    @staticmethod
    def list_alerts(severity: str = "", status: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        alerts = _load_json(_PROMETHEUS_ALERTS_FILE)
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity]
        if status:
            alerts = [a for a in alerts if a.get("status") == status]
        return alerts[:limit]

    @staticmethod
    def correlate_alerts(source_type: str = "infrastructure", threshold: int = 3) -> Dict[str, Any]:
        alerts = _load_json(_PROMETHEUS_ALERTS_FILE)
        firing = [a for a in alerts if a.get("status") == "firing"]
        if not firing:
            return {"correlated": [], "count": 0}
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for a in firing:
            group_key = a.get("labels", {}).get("severity", a.get("severity", "unknown"))
            groups.setdefault(group_key, []).append(a)
        correlated = []
        for gkey, galerts in groups.items():
            if len(galerts) >= threshold:
                correlated.append({
                    "correlation_key": gkey,
                    "alert_count": len(galerts),
                    "severity": gkey,
                    "alerts": [{"alert_name": a["alert_name"], "alert_id": a["alert_id"]} for a in galerts[:10]],
                })
        return {"correlated": correlated, "count": len(correlated)}

    @staticmethod
    def get_alert_stats() -> Dict[str, Any]:
        alerts = _load_json(_PROMETHEUS_ALERTS_FILE)
        total = len(alerts)
        firing = sum(1 for a in alerts if a.get("status") == "firing")
        resolved = sum(1 for a in alerts if a.get("status") == "resolved")
        critical = sum(1 for a in alerts if a.get("severity") == "critical")
        warning = sum(1 for a in alerts if a.get("severity") == "warning")
        info = sum(1 for a in alerts if a.get("severity") == "info")
        return {"total": total, "firing": firing, "resolved": resolved, "critical": critical, "warning": warning, "info": info}


# =============================================================================
# Part 5 — Grafana Intelligence
# =============================================================================


class GrafanaIntelligence:
    """Grafana dashboard discovery and tracking."""

    @staticmethod
    def discover_dashboard(uid: str, title: str, folder: str = "General",
                           url: str = "", datasources: Optional[List[str]] = None,
                           tags: Optional[List[str]] = None, panels: int = 0,
                           starred: bool = False) -> Dict[str, Any]:
        dashboards = _load_json(_GRAFANA_DASHBOARDS_FILE)
        existing = next((d for d in dashboards if d.get("uid") == uid), None)
        now = _now()
        if existing:
            existing["title"] = title
            existing["folder"] = folder
            existing["datasources"] = datasources or existing.get("datasources", [])
            existing["tags"] = tags or existing.get("tags", [])
            existing["panels"] = panels
            existing["starred"] = starred
            existing["updated_at"] = now
            result = existing
        else:
            d = {
                "dashboard_id": _id("grafana"),
                "uid": uid,
                "title": title,
                "folder": folder,
                "url": url,
                "datasources": datasources or [],
                "tags": tags or [],
                "panels": panels,
                "starred": starred,
                "created_at": now,
                "updated_at": now,
            }
            dashboards.append(d)
            result = d
        _save_json(_GRAFANA_DASHBOARDS_FILE, dashboards)
        return result

    @staticmethod
    def list_dashboards(folder: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        dashboards = _load_json(_GRAFANA_DASHBOARDS_FILE)
        if folder:
            dashboards = [d for d in dashboards if d.get("folder") == folder]
        return dashboards[:limit]

    @staticmethod
    def get_dashboard(dashboard_id: str) -> Optional[Dict[str, Any]]:
        return next((d for d in _load_json(_GRAFANA_DASHBOARDS_FILE) if d.get("dashboard_id") == dashboard_id), None)

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        dashboards = _load_json(_GRAFANA_DASHBOARDS_FILE)
        total = len(dashboards)
        folders = len(set(d.get("folder", "General") for d in dashboards))
        datasources = set()
        for d in dashboards:
            for ds in d.get("datasources", []):
                datasources.add(ds)
        return {"total": total, "folders": folders, "datasource_count": len(datasources)}


# =============================================================================
# Part 6 — Loki Log Intelligence
# =============================================================================


class LokiLogIntelligence:
    """Loki log analysis — query, analyze, and detect patterns."""

    @staticmethod
    def analyze_logs(stream: str, queries: Optional[List[str]] = None,
                     labels: Optional[Dict[str, str]] = None,
                     log_sample: Optional[List[str]] = None) -> Dict[str, Any]:
        logs = _load_json(_LOKI_LOGS_FILE)
        now = _now()
        queries = queries or []
        labels = labels or {}
        log_sample = log_sample or []

        error_count = sum(1 for line in log_sample if "error" in line.lower())
        warn_count = sum(1 for line in log_sample if "warn" in line.lower())
        info_count = sum(1 for line in log_sample if "info" in line.lower())

        analysis: Dict[str, Any] = {
            "analysis_id": _id("loki"),
            "stream": stream,
            "queries": queries,
            "labels": labels,
            "total_lines": len(log_sample),
            "error_count": error_count,
            "warn_count": warn_count,
            "info_count": info_count,
            "log_sample": log_sample[:20],
            "analyzed_at": now,
        }

        logs.append(analysis)
        if len(logs) > 1000:
            logs = logs[-1000:]
        _save_json(_LOKI_LOGS_FILE, logs)
        return analysis

    @staticmethod
    def list_analyses(stream: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        analyses = _load_json(_LOKI_LOGS_FILE)
        if stream:
            analyses = [a for a in analyses if a.get("stream") == stream]
        return analyses[:limit]

    @staticmethod
    def get_analysis(analysis_id: str) -> Optional[Dict[str, Any]]:
        return next((a for a in _load_json(_LOKI_LOGS_FILE) if a.get("analysis_id") == analysis_id), None)

    @staticmethod
    def search_logs(query: str, limit: int = 100) -> List[Dict[str, Any]]:
        analyses = _load_json(_LOKI_LOGS_FILE)
        results = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        for a in analyses:
            sample = a.get("log_sample", [])
            matched = [line for line in sample if pattern.search(line)]
            if matched:
                results.append({"analysis_id": a["analysis_id"], "stream": a["stream"], "matches": len(matched), "matched_lines": matched[:10]})
        return results[:limit]


# =============================================================================
# Part 7 — OpenTelemetry Trace Intelligence
# =============================================================================


class OpenTelemetryTraceIntelligence:
    """Distributed trace analysis — spans, services, latency."""

    @staticmethod
    def analyze_trace(trace_id: str, service_name: str, spans: Optional[List[Dict[str, Any]]] = None,
                      root_operation: str = "", duration_ms: float = 0.0,
                      status: str = "ok", tags: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        traces = _load_json(_TRACES_FILE)
        existing = next((t for t in traces if t.get("trace_id") == trace_id), None)
        now = _now()
        spans = spans or []
        tags = tags or {}
        error_spans = sum(1 for s in spans if s.get("status") == "error")
        total_spans = len(spans)
        latency_p50 = 0.0
        latency_p95 = 0.0
        latency_p99 = 0.0

        if total_spans > 0:
            durations = sorted(s.get("duration_ms", 0.0) for s in spans)
            mid = total_spans // 2
            latency_p50 = durations[mid] if total_spans % 2 else (durations[mid - 1] + durations[mid]) / 2
            p95_idx = min(total_spans - 1, int(total_spans * 0.95))
            p99_idx = min(total_spans - 1, int(total_spans * 0.99))
            latency_p95 = durations[p95_idx]
            latency_p99 = durations[p99_idx]

        if existing:
            existing["service_name"] = service_name or existing["service_name"]
            existing["spans"] = spans
            existing["total_spans"] = total_spans
            existing["error_spans"] = error_spans
            existing["root_operation"] = root_operation or existing.get("root_operation", "")
            existing["duration_ms"] = duration_ms
            existing["status"] = status
            existing["latency_p50"] = latency_p50
            existing["latency_p95"] = latency_p95
            existing["latency_p99"] = latency_p99
            existing["tags"] = tags
            existing["updated_at"] = now
            result = existing
        else:
            t = {
                "trace_entry_id": _id("trace"),
                "trace_id": trace_id,
                "service_name": service_name,
                "spans": spans,
                "total_spans": total_spans,
                "error_spans": error_spans,
                "root_operation": root_operation,
                "duration_ms": duration_ms,
                "status": status,
                "latency_p50": latency_p50,
                "latency_p95": latency_p95,
                "latency_p99": latency_p99,
                "tags": tags,
                "created_at": now,
                "updated_at": now,
            }
            traces.append(t)
            result = t
        _save_json(_TRACES_FILE, traces)
        return result

    @staticmethod
    def list_traces(service_name: str = "", status: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        traces = _load_json(_TRACES_FILE)
        if service_name:
            traces = [t for t in traces if t.get("service_name") == service_name]
        if status:
            traces = [t for t in traces if t.get("status") == status]
        return traces[:limit]

    @staticmethod
    def get_trace(trace_entry_id: str) -> Optional[Dict[str, Any]]:
        return next((t for t in _load_json(_TRACES_FILE) if t.get("trace_entry_id") == trace_entry_id), None)

    @staticmethod
    def get_trace_health() -> Dict[str, Any]:
        traces = _load_json(_TRACES_FILE)
        total = len(traces)
        ok = sum(1 for t in traces if t.get("status") == "ok")
        error = sum(1 for t in traces if t.get("status") == "error")
        avg_latency = round(sum(t.get("duration_ms", 0.0) for t in traces) / total, 2) if total else 0.0
        avg_p95 = round(sum(t.get("latency_p95", 0.0) for t in traces) / total, 2) if total else 0.0
        return {"total": total, "ok": ok, "error": error, "avg_duration_ms": avg_latency, "avg_p95_ms": avg_p95}


# =============================================================================
# Part 8 — Infrastructure Intelligence Service (orchestrator)
# =============================================================================


class InfrastructureIntelligenceService:
    """Orchestrator for infrastructure intelligence — integrates with existing
    CortexPrime services (Monitoring, Recommendation, Learning, Knowledge Graph,
    Analytics, Delivery, Engineering Executive, CI/CD Intelligence, RuntimeStore).

    Uses the Kubernetes connector (when available) to pull live data from real
    clusters, then feeds it through the existing ingest pipeline so that all
    downstream consumers (JSON files, events, metrics, recommendations) work
    identically regardless of data source.
    """

    def __init__(self) -> None:
        self._ready = False
        self._k8s: Any = None
        self._docker: Any = None

    async def initialize(self) -> None:
        try:
            from backend.connectors.kubernetes import KubernetesConnector
            k8s = KubernetesConnector()
            ok = await k8s.initialize()
            if ok:
                self._k8s = k8s
                log.info("Infrastructure Intelligence — Kubernetes connector active")
        except Exception as exc:
            log.debug("Kubernetes connector not available: %s", exc)
        try:
            from backend.connectors.docker import DockerConnector
            docker = DockerConnector()
            ok = await docker.initialize()
            if ok:
                self._docker = docker
                log.info("Infrastructure Intelligence — Docker connector active")
                # Start background Docker event listener. Skipped under pytest:
                # stream_events() blocks on a real socket read via asyncio.to_thread,
                # which cannot be cancelled once started — if no Docker event arrives
                # before a test's event loop tears down, task cancellation hangs
                # forever waiting for the blocked thread to return.
                import os
                if "PYTEST_CURRENT_TEST" not in os.environ:
                    import asyncio
                    asyncio.create_task(self._start_docker_event_listener())
        except Exception as exc:
            log.debug("Docker connector not available: %s", exc)
        self._ready = True
        log.info("Infrastructure Intelligence Service ready")

    async def _emit(self, event_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="infrastructure_intelligence",
                message=data.get("message", ""),
                execution_id=entity_id,
                metadata=data,
            )
        except Exception as exc:
            log.warning("Infrastructure event emit failed: %s", exc)

    async def _notify_monitoring(self, source: str, detail: Dict[str, Any]) -> None:
        try:
            from backend.services.monitoring_rules_engine import monitoring_rules
            await monitoring_rules.evaluate_event({"source": source, "detail": detail})
        except Exception as exc:
            log.debug("Monitoring notification failed: %s", exc)

    async def _record_metric(self, metric_type: str, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        try:
            from backend.services.enterprise_analytics_service import analytics_service
            await analytics_service.record_metric(
                metric_type=metric_type,
                metric_name=metric_name,
                value=value,
                labels=labels or {},
            )
        except Exception as exc:
            log.debug("Metric recording failed: %s", exc)

    async def _sync_runtime_store(self, source: str, entity: Dict[str, Any]) -> None:
        """Write infrastructure entity state to RuntimeStore as an EngineeringExecution."""
        try:
            from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
            exec_id = entity.get(f"{source}_id") or entity.get("cluster_id") or _id("infra")
            execution = EngineeringExecution(
                execution_id=exec_id,
                platform="kubernetes",
                deployment_id=entity.get("deployment_id", ""),
                build_status=entity.get("status", ""),
                build_name=entity.get("name", ""),
                repository=entity.get("cluster_id", ""),
                branch=entity.get("namespace", ""),
                status=entity.get("status", "unknown"),
                current_stage=source,
                timeline=[{
                    "stage": source,
                    "status": entity.get("status", "synced"),
                    "timestamp": _now(),
                    "detail": {k: v for k, v in entity.items() if k not in ("timeline",)},
                }],
                created_at=entity.get("created_at", _now()),
                updated_at=entity.get("updated_at", _now()),
            )
            runtime_store.create_execution(execution)
        except Exception as exc:
            log.debug("RuntimeStore sync failed for %s: %s", source, exc)

    async def shutdown(self) -> None:
        if self._k8s:
            try:
                await self._k8s.shutdown()
            except Exception as exc:
                log.debug("K8s connector shutdown: %s", exc)
        if self._docker:
            try:
                await self._docker.shutdown()
            except Exception as exc:
                log.debug("Docker connector shutdown: %s", exc)

    async def sync_from_kubernetes(self, context: str = "") -> Dict[str, Any]:
        """Pull live data from the Kubernetes connector and feed through the
        ingest pipeline, which emits events, records metrics, writes to JSON
        files, and syncs to RuntimeStore.

        Returns a summary of what was ingested.
        """
        if not self._k8s:
            return {"status": "skipped", "reason": "Kubernetes connector not available"}
        try:
            clusters = await self._k8s.list_clusters()
            summary: Dict[str, int] = {"clusters": 0, "nodes": 0, "pods": 0, "deployments": 0, "pvcs": 0}
            for c in clusters:
                ctx = c.get("context", context)
                await self.ingest_cluster_event("sync", c)
                summary["clusters"] += 1

                nodes = await self._k8s.list_nodes(context=ctx)
                for n in nodes:
                    await self.ingest_node_event({**n, "cluster_id": ctx})
                    summary["nodes"] += 1

                pods = await self._k8s.list_pods(context=ctx)
                for p in pods:
                    await self.ingest_pod_event({**p, "cluster_id": ctx})
                    summary["pods"] += 1

                deps = await self._k8s.list_deployments(context=ctx)
                for d in deps:
                    await self.ingest_deployment_event({**d, "cluster_id": ctx})
                    summary["deployments"] += 1

                pvcs = await self._k8s.list_pvcs(context=ctx)
                for pvc in pvcs:
                    await self.ingest_pvc_event({**pvc, "cluster_id": ctx})
                    summary["pvcs"] += 1

            return {"status": "completed", **summary}
        except Exception as exc:
            log.warning("Kubernetes sync failed: %s", exc)
            return {"status": "failed", "error": str(exc)}

    async def sync_from_docker(self) -> Dict[str, Any]:
        """Pull live containers, images, volumes, and networks from the Docker
        connector and feed through the ingest pipeline.

        Returns a summary of what was ingested.
        """
        if not self._docker:
            return {"status": "skipped", "reason": "Docker connector not available"}
        try:
            containers = await self._docker.list_containers(all=True)
            images = await self._docker.list_images(all=True)
            volumes = await self._docker.list_volumes()
            networks = await self._docker.list_networks()

            summary: Dict[str, int] = {"containers": 0, "images": 0, "volumes": 0, "networks": 0}

            for c in containers:
                await self.ingest_docker_event(c)
                summary["containers"] += 1

            for img in images:
                await self.ingest_docker_image_event(img)
                summary["images"] += 1

            for v in volumes:
                await self.ingest_docker_volume_event(v)
                summary["volumes"] += 1

            for n in networks:
                await self.ingest_docker_network_event(n)
                summary["networks"] += 1

            return {"status": "completed", **summary}
        except Exception as exc:
            log.warning("Docker sync failed: %s", exc)
            return {"status": "failed", "error": str(exc)}

    async def ingest_cluster_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload.get("name", payload.get("cluster_name", "unknown"))
        provider = payload.get("provider", "")
        version = payload.get("version", "")
        nodes_total = payload.get("nodes_total", payload.get("node_count", 0))
        nodes_ready = payload.get("nodes_ready", 0)
        result = KubernetesIntelligence.track_cluster(name, provider, version, nodes_total, nodes_ready)
        await self._emit(INFRA_EVENTS["cluster_health_changed"], result["cluster_id"], result)
        await self._record_metric("health", f"cluster.{name}.healthy", 1 if result["status"] == "healthy" else 0)
        await self._sync_runtime_store("cluster", result)
        return result

    async def ingest_pod_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cluster_id = payload.get("cluster_id", payload.get("cluster", "default"))
        namespace = payload.get("namespace", "default")
        name = payload.get("name", payload.get("pod_name", "unknown"))
        status = payload.get("status", "running")
        restarts = payload.get("restarts", 0)
        container_statuses = payload.get("container_statuses", payload.get("containers", []))
        node_name = payload.get("node_name", "")
        phase = payload.get("phase", "Running")

        result = KubernetesIntelligence.track_pod(cluster_id, namespace, name, status, restarts, container_statuses, node_name, phase)
        await self._emit(INFRA_EVENTS["pod_status_changed"], result["pod_id"], result)

        if result.get("oom_detected"):
            await self._emit(INFRA_EVENTS["container_oomkilled"], result["pod_id"], {"pod": name, "namespace": namespace, "message": f"OOMKilled detected in pod {name}"})
            await self._record_metric("failure", "pod.oom", 1, {"namespace": namespace, "pod": name})

        if result.get("crashloop_detected"):
            await self._emit(INFRA_EVENTS["container_crashloop"], result["pod_id"], {"pod": name, "namespace": namespace, "message": f"CrashLoopBackOff detected in pod {name}"})
            await self._record_metric("failure", "pod.crashloop", 1, {"namespace": namespace, "pod": name})

        if restarts > 0:
            await self._emit(INFRA_EVENTS["container_restarted"], result["pod_id"], {"pod": name, "restarts": restarts})

        await self._sync_runtime_store("pod", result)
        return result

    async def ingest_node_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cluster_id = payload.get("cluster_id", "")
        name = payload.get("name", payload.get("node_name", "unknown"))
        status = payload.get("status", "ready")
        cpu = payload.get("cpu_usage", 0.0)
        mem = payload.get("memory_usage", 0.0)
        disk = payload.get("disk_usage", 0.0)
        result = KubernetesIntelligence.track_node(cluster_id, name, status, cpu, mem, disk)
        await self._emit(INFRA_EVENTS["node_status_changed"], result["node_id"], result)
        await self._emit(INFRA_EVENTS["node_utilization_updated"], result["node_id"], result)
        await self._sync_runtime_store("node", result)
        return result

    async def ingest_deployment_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cluster_id = payload.get("cluster_id", "")
        namespace = payload.get("namespace", "default")
        name = payload.get("name", payload.get("deployment_name", "unknown"))
        replicas = payload.get("replicas", 0)
        available = payload.get("available", 0)
        status = payload.get("status", "available")
        rollout_status = payload.get("rollout_status", payload.get("rollout", "completed"))
        image = payload.get("image", "")
        strategy = payload.get("strategy", "rolling_update")
        prev_status = payload.get("previous_rollout_status", "")
        is_rollback = rollout_status == "rollback" or (prev_status == "progressing" and status != "available")

        result = KubernetesIntelligence.track_deployment(cluster_id, namespace, name, replicas, available, status, rollout_status, image, strategy)
        await self._emit(INFRA_EVENTS["deployment_rollout_updated"], result["deployment_id"], result)

        if is_rollback:
            await self._emit(INFRA_EVENTS["deployment_rollback_detected"], result["deployment_id"], {"message": f"Rollback detected for deployment {name}", "deployment": name, "namespace": namespace})
            await self._record_metric("action", "deployment.rollback", 1, {"namespace": namespace, "deployment": name})

        await self._sync_runtime_store("deployment", result)
        return result

    async def ingest_pvc_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cluster_id = payload.get("cluster_id", "")
        namespace = payload.get("namespace", "default")
        name = payload.get("name", payload.get("pvc_name", "unknown"))
        status = payload.get("status", "bound")
        capacity = payload.get("capacity_bytes", 0)
        used = payload.get("used_bytes", 0)
        volume = payload.get("volume_name", "")
        result = KubernetesIntelligence.track_pvc(cluster_id, namespace, name, status, capacity, used, volume)
        await self._emit(INFRA_EVENTS["pvc_health_changed"], result["pvc_id"], result)
        await self._sync_runtime_store("pvc", result)
        return result

    async def ingest_network_failure_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cluster_id = payload.get("cluster_id", "")
        namespace = payload.get("namespace", "default")
        source = payload.get("source", "")
        destination = payload.get("destination", "")
        reason = payload.get("reason", "timeout")
        protocol = payload.get("protocol", "TCP")
        port = payload.get("port", 0)
        result = KubernetesIntelligence.track_network_failure(cluster_id, namespace, source, destination, reason, protocol, port)
        await self._emit(INFRA_EVENTS["network_failure_detected"], result["failure_id"], result)
        return result

    async def _start_docker_event_listener(self) -> None:
        """Background task that streams Docker events and emits them via EventHub."""
        if not self._docker:
            return
        try:
            log.info("Docker event listener started")
            async for event in self._docker.stream_events():
                event_type = event.get("Type", "")
                action = event.get("action", "")
                actor = event.get("Actor", {})
                actor_id = actor.get("ID", "")[:12] if actor.get("ID") else ""
                actor_attrs = actor.get("Attributes", {})

                infra_key = f"docker_{event_type}_{action}"
                event_key = INFRA_EVENTS.get(infra_key, "")
                if not event_key:
                    event_key = f"docker.{event_type}.{action}"

                payload = {
                    "container_id": actor_id,
                    "name": actor_attrs.get("name", actor_id),
                    "image": actor_attrs.get("image", ""),
                    "status": action,
                    "labels": actor_attrs,
                    "host": self._docker._host if self._docker else "",
                }
                # Feed live events through ingest pipeline
                if event_type == "container":
                    await self.ingest_docker_event(payload)
                elif event_type == "image" and action in ("pull", "push", "tag", "untag", "delete"):
                    await self._emit(event_key or INFRA_EVENTS["docker_image_pulled"], actor_id, payload)
                elif event_type == "network":
                    await self._emit(event_key or INFRA_EVENTS["docker_network_created"], actor_id, payload)
                elif event_type == "volume":
                    await self._emit(event_key or INFRA_EVENTS["docker_volume_created"], actor_id, payload)
        except Exception as exc:
            log.warning("Docker event listener ended: %s", exc)

    async def ingest_docker_image_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        image_id = payload.get("image_id", "")
        tags = payload.get("tags", [])
        size_bytes = payload.get("size_bytes", 0)
        created_at = payload.get("created_at", "")
        repository = payload.get("repository", "")
        digest = payload.get("digest", "")
        architecture = payload.get("architecture", "")
        result = DockerIntelligence.track_image(image_id, tags, size_bytes, created_at, repository, digest, architecture)
        await self._emit(INFRA_EVENTS["docker_image_pulled"], result.get("image_entry_id", ""), result)
        await self._sync_runtime_store("docker_image", result)
        return result

    async def ingest_docker_volume_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload.get("name", payload.get("volume_name", "unknown"))
        driver = payload.get("driver", "local")
        mountpoint = payload.get("mountpoint", "")
        labels = payload.get("labels", {})
        created_at = payload.get("created_at", "")
        result = DockerIntelligence.track_volume(name, driver, mountpoint, labels, created_at)
        await self._emit(INFRA_EVENTS["docker_volume_created"], result["volume_id"], result)
        await self._sync_runtime_store("docker_volume", result)
        return result

    async def ingest_docker_network_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload.get("name", payload.get("network_name", "unknown"))
        driver = payload.get("driver", "bridge")
        scope = payload.get("scope", "local")
        subnet = payload.get("subnet", "")
        labels = payload.get("labels", {})
        result = DockerIntelligence.track_network(name, driver, scope, subnet, labels)
        await self._emit(INFRA_EVENTS["docker_network_created"], result["network_id"], result)
        return result

    async def ingest_docker_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        container_id = payload.get("container_id", "")
        name = payload.get("name", payload.get("container_name", "unknown"))
        image = payload.get("image", "")
        status = payload.get("status", payload.get("state", "running"))
        ports = payload.get("ports", [])
        restart_count = payload.get("restart_count", 0)
        host = payload.get("host", self._docker._host if self._docker else "localhost")
        created = payload.get("created_at", "")
        health = payload.get("health", "")
        labels = payload.get("labels", {})
        volumes = payload.get("volumes", [])
        networks = payload.get("networks", [])
        environment = payload.get("environment", [])

        result = DockerIntelligence.track_container(
            container_id, name, image, status, ports, restart_count, host, created,
            health=health, labels=labels, volumes=volumes,
            networks=networks, environment=environment,
        )

        event_key = "docker_container_tracked"
        s_lower = status.lower()
        if s_lower in ("running", "up"):
            event_key = "docker_container_started"
        elif s_lower in ("exited", "dead"):
            event_key = "docker_container_failed"
        elif s_lower == "paused":
            event_key = "docker_container_paused"

        await self._emit(INFRA_EVENTS.get(event_key, INFRA_EVENTS["docker_container_tracked"]), result["docker_id"], result)
        await self._record_metric("docker", f"container.{s_lower}", 1, {"name": name, "host": host})
        await self._sync_runtime_store("docker", result)
        return result

    async def ingest_helm_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload.get("name", payload.get("release_name", "unknown"))
        namespace = payload.get("namespace", "default")
        chart = payload.get("chart", "")
        version = payload.get("version", "")
        revision = payload.get("revision", 1)
        status = payload.get("status", "deployed")
        cluster_id = payload.get("cluster_id", "")
        values = payload.get("values")
        notes = payload.get("notes", "")
        result = HelmIntelligence.track_release(name, namespace, chart, version, revision, status, cluster_id, values, notes)
        await self._emit(INFRA_EVENTS["helm_release_tracked"], result["release_id"], result)
        return result

    async def ingest_prometheus_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        alert_name = payload.get("alert_name", payload.get("name", "unknown"))
        severity = payload.get("severity", "warning")
        status = payload.get("status", payload.get("alert_status", "firing"))
        labels = payload.get("labels", {})
        annotations = payload.get("annotations", {})
        starts_at = payload.get("starts_at", "")
        ends_at = payload.get("ends_at", "")
        value = payload.get("value", 1.0)
        generator_url = payload.get("generator_url", "")
        result = PrometheusIntelligence.track_alert(alert_name, severity, status, labels, annotations, starts_at, ends_at, value, generator_url)

        if status == "firing":
            await self._notify_monitoring("prometheus_alert", {"alert_name": alert_name, "severity": severity})
            correlation = PrometheusIntelligence.correlate_alerts(threshold=3)
            if correlation["count"] > 0:
                await self._emit(INFRA_EVENTS["prometheus_alert_correlated"], result["alert_id"], {"correlation": correlation})

        await self._emit(INFRA_EVENTS["prometheus_alert_correlated"], result["alert_id"], result)
        return result

    async def ingest_grafana_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        uid = payload.get("uid", "")
        title = payload.get("title", payload.get("dashboard_title", "Unknown Dashboard"))
        folder = payload.get("folder", "General")
        url = payload.get("url", "")
        datasources = payload.get("datasources", [])
        tags = payload.get("tags", [])
        panels = payload.get("panels", 0)
        starred = payload.get("starred", False)
        result = GrafanaIntelligence.discover_dashboard(uid, title, folder, url, datasources, tags, panels, starred)
        await self._emit(INFRA_EVENTS["grafana_dashboard_discovered"], result["dashboard_id"], result)
        return result

    async def ingest_loki_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        stream = payload.get("stream", payload.get("log_stream", "unknown"))
        queries = payload.get("queries", [])
        labels = payload.get("labels", {})
        log_sample = payload.get("log_sample", payload.get("logs", []))
        result = LokiLogIntelligence.analyze_logs(stream, queries, labels, log_sample)
        await self._emit(INFRA_EVENTS["loki_log_analysis_completed"], result["analysis_id"], result)
        if result.get("error_count", 0) > 0:
            await self._record_metric("failure", "loki.errors", result["error_count"], {"stream": stream})
        return result

    async def ingest_opentelemetry_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        trace_id = payload.get("trace_id", "")
        service_name = payload.get("service_name", payload.get("service", "unknown"))
        spans = payload.get("spans", [])
        root_operation = payload.get("root_operation", "")
        duration_ms = payload.get("duration_ms", 0.0)
        status = payload.get("status", "ok")
        tags = payload.get("tags", {})
        result = OpenTelemetryTraceIntelligence.analyze_trace(trace_id, service_name, spans, root_operation, duration_ms, status, tags)
        await self._emit(INFRA_EVENTS["opentelemetry_trace_analyzed"], result["trace_entry_id"], result)
        if result.get("error_spans", 0) > 0:
            await self._record_metric("failure", "trace.errors", result["error_spans"], {"service": service_name, "trace": trace_id})
        return result

    async def ingest_otlp_trace(self, body: bytes, content_type: str = "application/x-protobuf") -> Dict[str, Any]:
        """Ingest a raw OTLP trace payload (protobuf or JSON) through the Trace Intelligence Service."""
        try:
            from backend.services.enterprise_trace_intelligence import trace_intelligence
            if content_type == "application/json":
                import json
                decoded = json.loads(body) if isinstance(body, bytes) else body
                return await trace_intelligence.ingest_otlp_json(decoded)
            return await trace_intelligence.ingest_otlp_protobuf(body)
        except Exception as exc:
            log.warning("OTLP trace ingestion failed: %s", exc)
            return {"status": "failed", "error": str(exc)}

    def get_dashboard(self) -> Dict[str, Any]:
        cluster_health = KubernetesIntelligence.get_cluster_health()
        pod_health = KubernetesIntelligence.get_pod_health()
        dep_health = KubernetesIntelligence.get_deployment_health()
        node_util = KubernetesIntelligence.get_node_utilization()
        docker_health = DockerIntelligence.get_container_health()
        docker_images = DockerIntelligence.get_image_health()
        docker_volumes = DockerIntelligence.get_volume_health()
        docker_networks = DockerIntelligence.get_network_health()
        helm_health = HelmIntelligence.get_release_health()
        alert_stats = PrometheusIntelligence.get_alert_stats()
        grafana_stats = GrafanaIntelligence.get_dashboard_stats()
        trace_health = OpenTelemetryTraceIntelligence.get_trace_health()
        nfs = KubernetesIntelligence.list_network_failures(resolved=False, limit=10)
        pvcs = KubernetesIntelligence.list_pvcs(limit=10)
        return {
            "clusters": cluster_health,
            "pods": pod_health,
            "deployments": dep_health,
            "nodes": node_util,
            "containers": docker_health,
            "images": docker_images,
            "volumes": docker_volumes,
            "networks": docker_networks,
            "helm_releases": helm_health,
            "alerts": alert_stats,
            "grafana_dashboards": grafana_stats,
            "traces": trace_health,
            "active_network_failures": len(nfs),
            "total_pvcs": len(pvcs),
        }

    def get_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        from collections import defaultdict
        defaultdict(list)

        for cls, file, source, name_key in [
            (KubernetesIntelligence, _PODS_FILE, "pod", "name"),
            (KubernetesIntelligence, _DEPLOYMENTS_FILE, "deployment", "name"),
            (KubernetesIntelligence, _NODES_FILE, "node", "name"),
            (HelmIntelligence, _HELM_RELEASES_FILE, "helm", "name"),
            (DockerIntelligence, _DOCKER_CONTAINERS_FILE, "docker", "name"),
            (PrometheusIntelligence, _PROMETHEUS_ALERTS_FILE, "prometheus", "alert_name"),
            (GrafanaIntelligence, _GRAFANA_DASHBOARDS_FILE, "grafana", "title"),
            (OpenTelemetryTraceIntelligence, _TRACES_FILE, "trace", "trace_id"),
            (KubernetesIntelligence, _PVCS_FILE, "pvc", "name"),
            (KubernetesIntelligence, _NETWORK_FAILURES_FILE, "network", "failure_id"),
        ]:
            items = _load_json(file)
            for item in items:
                entries.append({
                    "source": source,
                    "entity_id": item.get(f"{source}_id") or item.get("alert_id") or item.get("trace_entry_id") or item.get("pod_id") or item.get("deployment_id") or item.get("node_id") or item.get("release_id") or item.get("docker_id") or item.get("dashboard_id") or item.get("pvc_id") or item.get("failure_id") or "",
                    "name": item.get(name_key, "Unknown"),
                    "status": item.get("status", item.get("rollout_status", item.get("phase", ""))),
                    "timestamp": item.get("updated_at", item.get("created_at", item.get("analyzed_at", item.get("detected_at", "")))),
                    "namespace": item.get("namespace", ""),
                    "cluster_id": item.get("cluster_id", ""),
                })
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return entries[:limit]

    async def generate_recommendation(self, cluster_id: str = "") -> Dict[str, Any]:
        try:
            from backend.services.enterprise_recommendation_engine import enterprise_recommendation
            dashboard = self.get_dashboard()
            pod_health = dashboard.get("pods", {})
            dep_health = dashboard.get("deployments", {})

            issues: List[str] = []
            if pod_health.get("crashloop", 0) > 0:
                issues.append(f"{pod_health['crashloop']} pods in CrashLoopBackOff")
            if pod_health.get("oom", 0) > 0:
                issues.append(f"{pod_health['oom']} pods OOMKilled")
            if dep_health.get("rollbacks", 0) > 0:
                issues.append(f"{dep_health['rollbacks']} deployments rolled back")
            if dashboard.get("active_network_failures", 0) > 0:
                issues.append(f"{dashboard['active_network_failures']} active network failures")
            if dashboard.get("alerts", {}).get("critical", 0) > 0:
                issues.append(f"{dashboard['alerts']['critical']} critical Prometheus alerts")

            return await enterprise_recommendation.generate(
                context="infrastructure_intelligence",
                summary="; ".join(issues) if issues else "Infrastructure healthy",
                metrics=dashboard,
            )
        except Exception as exc:
            log.debug("Recommendation generation failed: %s", exc)
            return {"status": "unavailable", "error": str(exc)}

    async def sync_engineering_executive(self, incident_summary: str, severity: str = "medium") -> Dict[str, Any]:
        try:
            from backend.services.enterprise_engineering_executive import get_engineering_executive
            ee = get_engineering_executive()
            task = await ee.create_task(
                title=f"Infrastructure Incident: {incident_summary[:100]}",
                description=incident_summary,
                priority=severity,
                source="infrastructure_intelligence",
            )
            return task
        except Exception as exc:
            log.debug("Engineering Executive sync failed: %s", exc)
            return {"status": "unavailable", "error": str(exc)}

    async def ingest_kubernetes_webhook(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        kind = payload.get("kind", "").lower()
        results: List[Dict[str, Any]] = []
        obj = payload.get("object", payload.get("metadata", payload))

        if kind == "pod":
            result = await self.ingest_pod_event(obj)
            results.append(result)
        elif kind == "deployment":
            result = await self.ingest_deployment_event(obj)
            results.append(result)
        elif kind == "node":
            result = await self.ingest_node_event(obj)
            results.append(result)
        elif kind in ("persistentvolumeclaim", "pvc"):
            result = await self.ingest_pvc_event(obj)
            results.append(result)
        elif kind == "":
            if "cluster_id" in payload or "cluster_name" in payload or "name" in payload:
                result = await self.ingest_cluster_event("cluster_health", payload)
                results.append(result)
            else:
                result = await self.ingest_pod_event(payload)
                results.append(result)
        return results


infrastructure_intelligence = InfrastructureIntelligenceService()
