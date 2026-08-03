"""Tests for Enterprise Infrastructure Intelligence."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_infrastructure_intelligence import (
    InfrastructureIntelligenceService,
    KubernetesIntelligence,
    DockerIntelligence,
    HelmIntelligence,
    PrometheusIntelligence,
    GrafanaIntelligence,
    LokiLogIntelligence,
    OpenTelemetryTraceIntelligence,
    INFRA_EVENTS,
    SUPPORTED_PLATFORMS,
)

# =============================================================================
# Fixtures — isolate data files
# =============================================================================


@pytest.fixture(autouse=True)
def _isolate_data(tmp_path: Path):
    """Redirect all JSON data files to a temp directory."""
    import backend.services.enterprise_infrastructure_intelligence as mod
    original = mod._DATA_DIR
    mod._DATA_DIR = tmp_path / "infra"
    mod._DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in [
        "_CLUSTERS_FILE", "_PODS_FILE", "_NODES_FILE", "_DEPLOYMENTS_FILE",
        "_CONTAINERS_FILE", "_HELM_RELEASES_FILE", "_PROMETHEUS_ALERTS_FILE",
        "_GRAFANA_DASHBOARDS_FILE", "_LOKI_LOGS_FILE", "_TRACES_FILE",
        "_PVCS_FILE", "_DOCKER_CONTAINERS_FILE", "_NETWORK_FAILURES_FILE",
    ]:
        setattr(mod, name, mod._DATA_DIR / getattr(mod, name).name)
    yield
    mod._DATA_DIR = original


@pytest.fixture
def infra():
    svc = InfrastructureIntelligenceService()
    return svc


# =============================================================================
# Constants & helpers
# =============================================================================


class TestConstants:
    def test_infra_events_count(self):
        assert len(INFRA_EVENTS) == 66

    def test_supported_platforms(self):
        assert "kubernetes" in SUPPORTED_PLATFORMS
        assert "docker" in SUPPORTED_PLATFORMS
        assert "helm" in SUPPORTED_PLATFORMS
        assert "prometheus" in SUPPORTED_PLATFORMS
        assert "grafana" in SUPPORTED_PLATFORMS
        assert "loki" in SUPPORTED_PLATFORMS
        assert "opentelemetry" in SUPPORTED_PLATFORMS


# =============================================================================
# Kubernetes Intelligence
# =============================================================================


class TestKubernetesIntelligence:
    def test_track_and_list_clusters(self):
        KubernetesIntelligence.track_cluster("prod", "eks", "1.28", 5, 5)
        clusters = KubernetesIntelligence.list_clusters()
        assert len(clusters) == 1
        assert clusters[0]["name"] == "prod"
        assert clusters[0]["status"] == "healthy"

    def test_track_degraded_cluster(self):
        KubernetesIntelligence.track_cluster("staging", "gke", "1.27", 3, 2)
        c = KubernetesIntelligence.get_cluster("invalid")
        assert c is None
        clusters = KubernetesIntelligence.list_clusters()
        assert clusters[0]["status"] == "degraded"

    def test_get_cluster_health(self):
        KubernetesIntelligence.track_cluster("a", "aks", "", 2, 2)
        KubernetesIntelligence.track_cluster("b", "eks", "", 3, 2)
        h = KubernetesIntelligence.get_cluster_health()
        assert h["total"] == 2
        assert h["healthy"] == 1
        assert h["degraded"] == 1

    def test_track_and_list_nodes(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "1.28", 2, 2)
        clusters = KubernetesIntelligence.list_clusters()
        cid = clusters[0]["cluster_id"]
        KubernetesIntelligence.track_node(cid, "node-1", "ready", 0.45, 0.62, 0.3)
        KubernetesIntelligence.track_node(cid, "node-2", "ready", 0.78, 0.81, 0.5)
        nodes = KubernetesIntelligence.list_nodes(cid)
        assert len(nodes) == 2
        util = KubernetesIntelligence.get_node_utilization(cid)
        assert util["node_count"] == 2
        assert 0 < util["avg_cpu"] < 1

    def test_track_and_list_pods(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "", 1, 1)
        cid = KubernetesIntelligence.list_clusters()[0]["cluster_id"]
        p = KubernetesIntelligence.track_pod(cid, "default", "web-1", "running", 0)
        assert p["status"] == "running"
        pods = KubernetesIntelligence.list_pods("default")
        assert len(pods) == 1

    def test_pod_oom_detection(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "", 1, 1)
        cid = KubernetesIntelligence.list_clusters()[0]["cluster_id"]
        cs = [{"last_state": {"terminated": {"reason": "OOMKilled", "exit_code": 137}}}]
        result = KubernetesIntelligence.track_pod(cid, "default", "web-oom", "running", 1, cs)
        assert result["oom_detected"] is True

    def test_pod_crashloop_detection(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "", 1, 1)
        cid = KubernetesIntelligence.list_clusters()[0]["cluster_id"]
        cs = [{"last_state": {"waiting": {"reason": "CrashLoopBackOff", "message": "backoff"}}}]
        result = KubernetesIntelligence.track_pod(cid, "default", "web-cl", "crashloop", 5, cs)
        assert result["crashloop_detected"] is True

    def test_pod_health(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "", 1, 1)
        cid = KubernetesIntelligence.list_clusters()[0]["cluster_id"]
        KubernetesIntelligence.track_pod(cid, "default", "p1", "running")
        KubernetesIntelligence.track_pod(cid, "default", "p2", "failed")
        KubernetesIntelligence.track_pod(cid, "default", "p3", "running")
        h = KubernetesIntelligence.get_pod_health("default")
        assert h["total"] == 3
        assert h["running"] == 2
        assert h["failed"] == 1

    def test_track_and_list_deployments(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "", 1, 1)
        cid = KubernetesIntelligence.list_clusters()[0]["cluster_id"]
        KubernetesIntelligence.track_deployment(cid, "default", "app1", 3, 3, "available", "completed")
        deps = KubernetesIntelligence.list_deployments("default")
        assert len(deps) == 1
        assert deps[0]["name"] == "app1"

    def test_deployment_health(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "", 1, 1)
        cid = KubernetesIntelligence.list_clusters()[0]["cluster_id"]
        KubernetesIntelligence.track_deployment(cid, "default", "d1", 3, 3, "available", "completed")
        KubernetesIntelligence.track_deployment(cid, "default", "d2", 2, 0, "unavailable", "rollback")
        h = KubernetesIntelligence.get_deployment_health()
        assert h["total"] == 2
        assert h["available"] == 1
        assert h["rollbacks"] == 1

    def test_track_and_list_pvcs(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "", 1, 1)
        cid = KubernetesIntelligence.list_clusters()[0]["cluster_id"]
        KubernetesIntelligence.track_pvc(cid, "default", "data-pvc", "bound", 1073741824, 536870912)
        pvcs = KubernetesIntelligence.list_pvcs("default")
        assert len(pvcs) == 1
        assert pvcs[0]["status"] == "bound"

    def test_track_network_failure(self):
        KubernetesIntelligence.track_cluster("c1", "eks", "", 1, 1)
        cid = KubernetesIntelligence.list_clusters()[0]["cluster_id"]
        f = KubernetesIntelligence.track_network_failure(cid, "default", "svc-a", "svc-b", "connection_timeout")
        assert f["resolved"] is False
        nfs = KubernetesIntelligence.list_network_failures(resolved=False)
        assert len(nfs) == 1

    def test_list_by_status(self):
        KubernetesIntelligence.list_pods(status="running")
        KubernetesIntelligence.list_nodes(cluster_id="nonexistent")


# =============================================================================
# Docker Intelligence
# =============================================================================


class TestDockerIntelligence:
    def test_track_and_list_containers(self):
        DockerIntelligence.track_container("abc123", "web", "nginx:latest", "running", ["80/tcp"], 0)
        containers = DockerIntelligence.list_containers()
        assert len(containers) == 1
        assert containers[0]["name"] == "web"

    def test_get_container_health(self):
        DockerIntelligence.track_container("a", "w1", "img", "running")
        DockerIntelligence.track_container("b", "w2", "img", "exited")
        h = DockerIntelligence.get_container_health()
        assert h["total"] == 2
        assert h["running"] == 1
        assert h["stopped"] == 1

    def test_get_container(self):
        c = DockerIntelligence.get_container("nonexistent")
        assert c is None


# =============================================================================
# Helm Intelligence
# =============================================================================


class TestHelmIntelligence:
    def test_track_and_list_releases(self):
        HelmIntelligence.track_release("myapp", "default", "stable/nginx", "3.0.0", 1, "deployed")
        releases = HelmIntelligence.list_releases()
        assert len(releases) == 1
        assert releases[0]["chart"] == "stable/nginx"

    def test_track_existing_release(self):
        HelmIntelligence.track_release("myapp", "default", "stable/nginx", "3.0.0", 1)
        r = HelmIntelligence.track_release("myapp", "default", "stable/nginx", "3.0.1", 2)
        assert r["revision"] == 2

    def test_get_release_health(self):
        HelmIntelligence.track_release("a", "ns1", "chart1", "1.0", 1, "deployed")
        HelmIntelligence.track_release("b", "ns1", "chart2", "1.0", 1, "failed")
        h = HelmIntelligence.get_release_health()
        assert h["total"] == 2
        assert h["failed"] == 1


# =============================================================================
# Prometheus Intelligence
# =============================================================================


class TestPrometheusIntelligence:
    def test_track_and_list_alerts(self):
        PrometheusIntelligence.track_alert("HighCPU", "warning", "firing", {"instance": "node-1"})
        alerts = PrometheusIntelligence.list_alerts()
        assert len(alerts) == 1
        assert alerts[0]["alert_name"] == "HighCPU"

    def test_alert_stats(self):
        PrometheusIntelligence.track_alert("A", "critical")
        PrometheusIntelligence.track_alert("B", "warning", "firing")
        s = PrometheusIntelligence.get_alert_stats()
        assert s["total"] == 2
        assert s["critical"] == 1

    def test_correlate_alerts(self):
        for i in range(5):
            PrometheusIntelligence.track_alert(f"Alert_{i}", "critical", "firing", {"severity": "critical"})
        c = PrometheusIntelligence.correlate_alerts(threshold=3)
        assert c["count"] >= 1


# =============================================================================
# Grafana Intelligence
# =============================================================================


class TestGrafanaIntelligence:
    def test_discover_and_list_dashboards(self):
        GrafanaIntelligence.discover_dashboard("uid-1", "Infra Overview", "Infrastructure", "", ["prometheus"])
        ds = GrafanaIntelligence.list_dashboards()
        assert len(ds) == 1
        assert ds[0]["title"] == "Infra Overview"

    def test_dashboard_stats(self):
        GrafanaIntelligence.discover_dashboard("u1", "DBoard 1", "Folder A", "", ["prometheus", "loki"])
        GrafanaIntelligence.discover_dashboard("u2", "DBoard 2", "Folder B", "", ["prometheus"])
        s = GrafanaIntelligence.get_dashboard_stats()
        assert s["total"] == 2
        assert s["folders"] == 2


# =============================================================================
# Loki Log Intelligence
# =============================================================================


class TestLokiLogIntelligence:
    def test_analyze_logs(self):
        logs = ["INFO started", "WARN high mem", "ERROR connection refused", "INFO completed"]
        result = LokiLogIntelligence.analyze_logs("app-prod", ["{app=\"myapp\"}"], {"app": "myapp"}, logs)
        assert result["total_lines"] == 4
        assert result["error_count"] == 1
        assert result["warn_count"] == 1

    def test_list_analyses(self):
        LokiLogIntelligence.analyze_logs("stream-1", [], {}, ["line1"])
        analyses = LokiLogIntelligence.list_analyses("stream-1")
        assert len(analyses) >= 1

    def test_search_logs(self):
        LokiLogIntelligence.analyze_logs("stream-1", [], {}, ["INFO ok", "ERROR failed"])
        results = LokiLogIntelligence.search_logs("ERROR")
        assert len(results) >= 1


# =============================================================================
# OpenTelemetry Trace Intelligence
# =============================================================================


class TestOpenTelemetryTraceIntelligence:
    def test_analyze_trace(self):
        spans = [
            {"span_id": "s1", "operation": "GET /api", "duration_ms": 50, "status": "ok"},
            {"span_id": "s2", "operation": "db.query", "duration_ms": 150, "status": "ok"},
        ]
        result = OpenTelemetryTraceIntelligence.analyze_trace("trace-abc", "order-svc", spans, "GET /api", 200, "ok")
        assert result["total_spans"] == 2
        assert result["latency_p50"] > 0
        assert result["latency_p95"] > 0

    def test_analyze_trace_with_errors(self):
        spans = [
            {"span_id": "s1", "duration_ms": 30, "status": "ok"},
            {"span_id": "s2", "duration_ms": 500, "status": "error"},
        ]
        result = OpenTelemetryTraceIntelligence.analyze_trace("trace-err", "svc", spans, "op", 530, "error")
        assert result["error_spans"] == 1
        assert result["status"] == "error"

    def test_trace_health(self):
        OpenTelemetryTraceIntelligence.analyze_trace("t1", "svc-a", [], "op1", 100, "ok")
        OpenTelemetryTraceIntelligence.analyze_trace("t2", "svc-b", [], "op2", 200, "error")
        h = OpenTelemetryTraceIntelligence.get_trace_health()
        assert h["total"] == 2
        assert h["error"] == 1
        assert h["avg_duration_ms"] > 0


# =============================================================================
# Infrastructure Intelligence Service (orchestrator)
# =============================================================================


class TestInfrastructureService:
    @pytest.mark.asyncio
    async def test_ingest_cluster_event(self, infra):
        result = await infra.ingest_cluster_event("cluster_health", {
            "name": "prod", "provider": "eks", "version": "1.28", "nodes_total": 5, "nodes_ready": 5,
        })
        assert result["status"] == "healthy"
        assert result["name"] == "prod"

        result2 = await infra.ingest_cluster_event("cluster_health", {
            "name": "staging", "provider": "gke", "nodes_total": 3, "nodes_ready": 2,
        })
        assert result2["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_ingest_pod_event(self, infra):
        result = await infra.ingest_pod_event({
            "cluster_id": "c1", "namespace": "default", "name": "web-1", "status": "running",
        })
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_oom_detected_in_pod_health(self, infra):
        cs = [{"last_state": {"terminated": {"reason": "OOMKilled", "exit_code": 137}}}]
        await infra.ingest_pod_event({
            "cluster_id": "c1", "namespace": "test", "name": "oom-pod", "status": "running",
            "restarts": 1, "container_statuses": cs,
        })
        h = KubernetesIntelligence.get_pod_health("test")
        assert h["oom"] == 1, f"Expected 1 OOM pod, got {h}"

    @pytest.mark.asyncio
    async def test_ingest_pod_event_with_oom(self, infra):
        cs = [{"last_state": {"terminated": {"reason": "OOMKilled", "exit_code": 137}}}]
        result = await infra.ingest_pod_event({
            "cluster_id": "c1", "namespace": "default", "name": "web-oom", "status": "running", "restarts": 1,
            "container_statuses": cs,
        })
        assert result["oom_detected"] is True

    @pytest.mark.asyncio
    async def test_ingest_node_event(self, infra):
        result = await infra.ingest_node_event({
            "cluster_id": "c1", "name": "node-1", "status": "ready", "cpu_usage": 0.5, "memory_usage": 0.6, "disk_usage": 0.3,
        })
        assert result["status"] == "ready"

    @pytest.mark.asyncio
    async def test_ingest_deployment_event(self, infra):
        result = await infra.ingest_deployment_event({
            "cluster_id": "c1", "namespace": "default", "name": "app1", "replicas": 3, "available": 3,
            "status": "available", "rollout_status": "completed", "image": "nginx:1.25",
        })
        assert result["rollout_status"] == "completed"

    @pytest.mark.asyncio
    async def test_ingest_deployment_rollback(self, infra):
        result = await infra.ingest_deployment_event({
            "cluster_id": "c1", "namespace": "default", "name": "app2", "replicas": 3, "available": 0,
            "status": "unavailable", "rollout_status": "rollback",
        })
        assert result["rollout_status"] == "rollback"

    @pytest.mark.asyncio
    async def test_ingest_pvc_event(self, infra):
        result = await infra.ingest_pvc_event({
            "cluster_id": "c1", "namespace": "default", "name": "data-pvc", "status": "bound",
            "capacity_bytes": 1073741824,
        })
        assert result["status"] == "bound"

    @pytest.mark.asyncio
    async def test_ingest_network_failure_event(self, infra):
        result = await infra.ingest_network_failure_event({
            "cluster_id": "c1", "namespace": "default", "source": "svc-a", "destination": "svc-b",
            "reason": "timeout", "protocol": "TCP", "port": 8080,
        })
        assert result["resolved"] is False

    @pytest.mark.asyncio
    async def test_ingest_docker_event(self, infra):
        result = await infra.ingest_docker_event({
            "container_id": "abc123", "name": "web", "image": "nginx:latest", "status": "running",
        })
        assert result["name"] == "web"

    @pytest.mark.asyncio
    async def test_ingest_helm_event(self, infra):
        result = await infra.ingest_helm_event({
            "name": "myapp", "namespace": "default", "chart": "stable/nginx", "version": "3.0.0",
            "revision": 1, "status": "deployed",
        })
        assert result["status"] == "deployed"

    @pytest.mark.asyncio
    async def test_ingest_prometheus_event(self, infra):
        result = await infra.ingest_prometheus_event({
            "alert_name": "HighCPU", "severity": "warning", "status": "firing",
        })
        assert result["alert_name"] == "HighCPU"

    @pytest.mark.asyncio
    async def test_ingest_grafana_event(self, infra):
        result = await infra.ingest_grafana_event({
            "uid": "uid-1", "title": "Infra Overview", "folder": "Infrastructure",
            "datasources": ["prometheus"], "panels": 12,
        })
        assert result["title"] == "Infra Overview"

    @pytest.mark.asyncio
    async def test_ingest_loki_event(self, infra):
        result = await infra.ingest_loki_event({
            "stream": "app-prod", "log_sample": ["INFO ok", "ERROR failed"],
        })
        assert result["error_count"] == 1

    @pytest.mark.asyncio
    async def test_ingest_opentelemetry_event(self, infra):
        result = await infra.ingest_opentelemetry_event({
            "trace_id": "trace-abc", "service_name": "order-svc",
            "spans": [{"span_id": "s1", "duration_ms": 50, "status": "ok"}],
            "root_operation": "GET /orders", "duration_ms": 50, "status": "ok",
        })
        assert result["service_name"] == "order-svc"

    @pytest.mark.asyncio
    async def test_ingest_kubernetes_webhook_pod(self, infra):
        results = await infra.ingest_kubernetes_webhook({
            "kind": "Pod",
            "object": {"cluster_id": "c1", "namespace": "default", "name": "webhook-pod", "status": "running"},
        })
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_ingest_kubernetes_webhook_deployment(self, infra):
        results = await infra.ingest_kubernetes_webhook({
            "kind": "Deployment",
            "object": {"cluster_id": "c1", "namespace": "default", "name": "webhook-dep", "replicas": 3, "available": 3, "status": "available", "rollout_status": "completed"},
        })
        assert len(results) == 1

    def test_dashboard(self, infra):
        d = infra.get_dashboard()
        assert "clusters" in d
        assert "pods" in d
        assert "deployments" in d
        assert "nodes" in d
        assert "containers" in d
        assert "helm_releases" in d
        assert "alerts" in d
        assert "grafana_dashboards" in d
        assert "traces" in d

    def test_timeline(self, infra):
        tl = infra.get_timeline()
        assert isinstance(tl, list)


# =============================================================================
# Cross-service integration stubs
# =============================================================================


class TestIntegrationStubs:
    @pytest.mark.asyncio
    async def test_generate_recommendation(self, infra):
        result = await infra.generate_recommendation()
        # Should handle unavailable services gracefully
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_sync_engineering_executive(self, infra):
        result = await infra.sync_engineering_executive("Test incident", "medium")
        assert isinstance(result, dict)


# =============================================================================
# Event emission verification
# =============================================================================


class TestInfraEvents:
    # Event values now carry per-integration prefixes (docker., argocd.,
    # grafana., loki., otel., prometheus., terraform.), not just infra.
    _KNOWN_PREFIXES = (
        "infra.", "docker.", "argocd.", "grafana.", "loki.", "otel.", "prometheus.", "terraform.",
    )

    def test_all_event_types_are_strings(self):
        for key, val in INFRA_EVENTS.items():
            assert isinstance(key, str)
            assert isinstance(val, str)
            assert val.startswith(self._KNOWN_PREFIXES), val

    def test_event_hub_topic_routing(self):
        from backend.services.enterprise_event_hub import _topic_for_event
        topic = _topic_for_event("infra.cluster_health_changed")
        assert topic == "enterprise:infrastructure"

    @pytest.mark.asyncio
    async def test_service_emits_events(self, infra):
        with patch.object(infra, "_emit", new_callable=AsyncMock) as mock_emit:
            await infra.ingest_cluster_event("cluster_health", {"name": "test", "nodes_total": 1, "nodes_ready": 1})
            assert mock_emit.called


# =============================================================================
# E2E scenario: Cluster → Pod → Deployment → Monitoring → Trace
# =============================================================================


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_infrastructure_pipeline(self, infra):
        # 1. Cluster
        cluster = await infra.ingest_cluster_event("cluster_health", {"name": "prod", "provider": "eks", "nodes_total": 3, "nodes_ready": 3})
        assert cluster["status"] == "healthy"

        # 2. Node
        await infra.ingest_node_event({"cluster_id": cluster["cluster_id"], "name": "node-1", "status": "ready", "cpu_usage": 0.5, "memory_usage": 0.6, "disk_usage": 0.3})

        # 3. Pod
        pod = await infra.ingest_pod_event({"cluster_id": cluster["cluster_id"], "namespace": "prod", "name": "web-1", "status": "running"})
        assert pod["status"] == "running"

        # 4. OOM Pod
        cs = [{"last_state": {"terminated": {"reason": "OOMKilled", "exit_code": 137}}}]
        await infra.ingest_pod_event({"cluster_id": cluster["cluster_id"], "namespace": "prod", "name": "web-oom", "status": "running", "restarts": 1, "container_statuses": cs})

        # 5. Deployment
        dep = await infra.ingest_deployment_event({"cluster_id": cluster["cluster_id"], "namespace": "prod", "name": "app", "replicas": 3, "available": 3, "status": "available", "rollout_status": "completed"})
        assert dep["rollout_status"] == "completed"

        # 6. Docker
        await infra.ingest_docker_event({"container_id": "abc", "name": "web", "image": "nginx", "status": "running"})

        # 7. Helm
        await infra.ingest_helm_event({"name": "release-1", "namespace": "prod", "chart": "stable/nginx", "version": "1.0", "status": "deployed"})

        # 8. Prometheus Alert
        await infra.ingest_prometheus_event({"alert_name": "HighCPU", "severity": "warning", "status": "firing"})

        # 9. Grafana Dashboard
        await infra.ingest_grafana_event({"uid": "u1", "title": "Dashboard", "folder": "General", "datasources": ["prometheus"]})

        # 10. Loki Logs
        await infra.ingest_loki_event({"stream": "prod", "log_sample": ["INFO ok", "ERROR failed"]})

        # 11. OpenTelemetry Trace
        await infra.ingest_opentelemetry_event({"trace_id": "t1", "service_name": "svc", "spans": [{"span_id": "s1", "duration_ms": 50, "status": "ok"}], "root_operation": "GET /api", "duration_ms": 50, "status": "ok"})

        # 12. Dashboard should reflect all data
        d = infra.get_dashboard()
        assert d["clusters"]["total"] >= 1
        assert d["pods"]["total"] >= 2
        assert d["deployments"]["total"] >= 1
        assert d["containers"]["total"] >= 1
        assert d["helm_releases"]["total"] >= 1
        assert d["alerts"]["total"] >= 1
        assert d["grafana_dashboards"]["total"] >= 1
        assert d["traces"]["total"] >= 1

        # 13. Timeline populated
        tl = infra.get_timeline()
        assert len(tl) >= 1
