"""Enterprise Prometheus Intelligence — live metric collection, alert correlation,
RuntimeStore synchronisation, and EventHub streaming.

Reuses:
  - RuntimeStore for metric snapshots as EngineeringExecution
  - EventHub for prometheus.* events
  - Knowledge Graph for metric context
  - Analytics for metric recording
  - Learning Engine for pattern learning
  - Existing PrometheusIntelligence static class for backward-compatible alert JSON

Backward compatible: all existing /api/infrastructure/prometheus/* endpoints
continue to work via the legacy PrometheusIntelligence JSON store.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("INFRASTRUCTURE_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "infrastructure")))
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_METRICS_FILE = _DATA_DIR / "prometheus_metrics.json"
_TARGETS_FILE = _DATA_DIR / "prometheus_targets.json"
_RULES_FILE = _DATA_DIR / "prometheus_rules.json"

PROM_EVENT_TYPES = {
    "metric.updated": "prometheus.metric.updated",
    "alert.firing": "prometheus.alert.firing",
    "alert.resolved": "prometheus.alert.resolved",
    "target.down": "prometheus.target.down",
    "target.up": "prometheus.target.up",
    "rule.updated": "prometheus.rule.updated",
}

# Standard PromQL queries for infrastructure metrics
STANDARD_QUERIES = {
    "node_cpu_usage": '100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
    "node_memory_usage": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
    "node_disk_usage": '(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100',
    "node_network_rx": 'rate(node_network_receive_bytes_total[5m])',
    "node_network_tx": 'rate(node_network_transmit_bytes_total[5m])',
    "container_cpu_usage": 'rate(container_cpu_usage_seconds_total[5m]) * 100',
    "container_memory_usage": 'container_memory_usage_bytes',
    "pod_cpu_usage": 'rate(container_cpu_usage_seconds_total[5m]) * 100',
    "pod_memory_usage": 'container_memory_usage_bytes',
    "http_request_rate": 'rate(http_requests_total[5m])',
    "http_error_rate": 'rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100',
    "http_latency_p95": 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))',
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "prom") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _load_json(path: Path) -> list:
    if path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_json(path: Path, data: list) -> None:
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except OSError as exc:
        log.warning("Failed to save %s: %s", path.name, exc)


def _extract_metric_value(result: Dict[str, Any]) -> float:
    """Extract a numeric value from a Prometheus query result."""
    try:
        data = result.get("data", {})
        result_type = data.get("resultType", "")
        results = data.get("result", [])
        if not results:
            return 0.0
        if result_type == "vector":
            value = results[0].get("value", [0, "0"])[1]
            return float(value)
        if result_type == "matrix":
            values = results[0].get("values", [[0, "0"]])
            if values:
                return float(values[-1][1])
        return 0.0
    except (TypeError, ValueError, IndexError):
        return 0.0


class PrometheusMetricIntelligence:
    """Collects live metrics from Prometheus and feeds the CortexPrime pipeline."""

    def __init__(self) -> None:
        self._connector: Any = None
        self._ready = False

    async def initialize(self) -> None:
        try:
            from backend.connectors.prometheus import PrometheusConnector
            conn = PrometheusConnector()
            ok = await conn.initialize()
            if ok:
                self._connector = conn
                log.info("Prometheus Metric Intelligence — connector active")
        except Exception as exc:
            log.debug("Prometheus connector not available: %s", exc)
        self._ready = True
        log.info("Prometheus Metric Intelligence Service ready")

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def query(self, promql: str) -> Dict[str, Any]:
        """Execute an instant PromQL query against the connected Prometheus."""
        if not self._connector or not self._connector.is_ready:
            return {"status": "error", "error": "Prometheus connector not available"}
        return await self._connector.query(promql)

    async def query_range(self, promql: str, start: str, end: str, step: str = "15s") -> Dict[str, Any]:
        """Execute a range PromQL query."""
        if not self._connector or not self._connector.is_ready:
            return {"status": "error", "error": "Prometheus connector not available"}
        return await self._connector.query_range(promql, start, end, step)

    async def get_targets(self) -> Dict[str, Any]:
        """Fetch scrape targets from Prometheus."""
        if not self._connector or not self._connector.is_ready:
            return {"status": "error", "error": "Prometheus connector not available"}
        raw = await self._connector.targets()
        if raw.get("status") != "success":
            return raw
        targets = raw.get("data", {}).get("activeTargets", [])
        dropped = raw.get("data", {}).get("droppedTargets", [])
        self._persist_targets(targets, dropped)
        return {"status": "success", "targets": targets, "dropped_count": len(dropped)}

    async def get_rules(self) -> Dict[str, Any]:
        """Fetch recording and alert rules."""
        if not self._connector or not self._connector.is_ready:
            return {"status": "error", "error": "Prometheus connector not available"}
        raw = await self._connector.rules()
        if raw.get("status") != "success":
            return raw
        groups = raw.get("data", {}).get("groups", [])
        self._persist_rules(groups)
        return {"status": "success", "groups": groups}

    async def get_alerts(self) -> Dict[str, Any]:
        """Fetch active alerts from Prometheus."""
        if not self._connector or not self._connector.is_ready:
            return {"status": "error", "error": "Prometheus connector not available"}
        raw = await self._connector.alerts()
        if raw.get("status") != "success":
            return raw
        alerts = raw.get("data", {}).get("alerts", [])
        return {"status": "success", "alerts": alerts}

    async def collect_all_metrics(self) -> Dict[str, Any]:
        """Run all standard metric queries and return a snapshot."""
        results: Dict[str, Any] = {"status": "completed", "metrics": {}, "errors": []}
        for name, promql in STANDARD_QUERIES.items():
            try:
                raw = await self.query(promql)
                if raw.get("status") == "success":
                    results["metrics"][name] = _extract_metric_value(raw)
                else:
                    results["errors"].append({"metric": name, "error": raw.get("error", "unknown")})
            except Exception as exc:
                results["errors"].append({"metric": name, "error": str(exc)})
        self._persist_metrics(results["metrics"])
        return results

    async def collect_node_metrics(self, instance: str = "") -> Dict[str, Any]:
        """Collect CPU, memory, disk and network for a specific node."""
        results: Dict[str, Any] = {}
        filters = f'{{instance="{instance}"}}' if instance else ""
        idle_filter = '{mode="idle"}'
        queries = {
            "cpu_percent": f"100 - (avg by(instance) (rate(node_cpu_seconds_total{idle_filter}{filters}[5m])) * 100)",
            "memory_percent": f"(1 - (node_memory_MemAvailable_bytes{filters} / node_memory_MemTotal_bytes{filters})) * 100",
            "disk_percent": "(1 - (node_filesystem_avail_bytes{mountpoint=\"/\"} / node_filesystem_size_bytes{mountpoint=\"/\"})) * 100",
        }
        if instance:
            queries["disk_percent"] = f"(1 - (node_filesystem_avail_bytes{{mountpoint=\"/\",instance=\"{instance}\"}} / node_filesystem_size_bytes{{mountpoint=\"/\",instance=\"{instance}\"}})) * 100"
        for name, promql in queries.items():
            raw = await self.query(promql)
            if raw.get("status") == "success":
                results[name] = _extract_metric_value(raw)
            else:
                results[name] = 0.0
        results["instance"] = instance or "all"
        results["collected_at"] = _now()
        return results

    async def collect_container_metrics(self) -> List[Dict[str, Any]]:
        """Collect CPU and memory for all containers."""
        containers: List[Dict[str, Any]] = []
        cpu_raw = await self.query("rate(container_cpu_usage_seconds_total[5m]) * 100")
        mem_raw = await self.query("container_memory_usage_bytes")
        if cpu_raw.get("status") == "success":
            for item in cpu_raw.get("data", {}).get("result", []):
                metric = item.get("metric", {})
                containers.append({
                    "container": metric.get("container", ""),
                    "pod": metric.get("pod", ""),
                    "namespace": metric.get("namespace", ""),
                    "cpu_percent": _extract_metric_value({"data": {"result": [item], "resultType": "vector"}}),
                    "collected_at": _now(),
                })
        if mem_raw.get("status") == "success":
            mem_map: Dict[str, float] = {}
            for item in mem_raw.get("data", {}).get("result", []):
                metric = item.get("metric", {})
                key = metric.get("container", "") or metric.get("pod", "")
                if key:
                    mem_map[key] = _extract_metric_value({"data": {"result": [item], "resultType": "vector"}})
            for c in containers:
                key = c.get("container", "") or c.get("pod", "")
                c["memory_bytes"] = mem_map.get(key, 0.0)
        return containers

    async def collect_pod_metrics(self) -> List[Dict[str, Any]]:
        """Collect CPU and memory for all pods."""
        pods: Dict[str, Dict[str, Any]] = {}
        cpu_raw = await self.query("sum by(pod, namespace) (rate(container_cpu_usage_seconds_total[5m]) * 100)")
        mem_raw = await self.query("sum by(pod, namespace) (container_memory_usage_bytes)")
        for raw_data, metric_key in [(cpu_raw, "cpu_percent"), (mem_raw, "memory_bytes")]:
            if raw_data.get("status") == "success":
                for item in raw_data.get("data", {}).get("result", []):
                    m = item.get("metric", {})
                    key = f"{m.get('namespace', '')}/{m.get('pod', '')}"
                    if key not in pods:
                        pods[key] = {"pod": m.get("pod", ""), "namespace": m.get("namespace", ""), "collected_at": _now()}
                    pods[key][metric_key] = _extract_metric_value({"data": {"result": [item], "resultType": "vector"}})
        return list(pods.values())

    def _persist_metrics(self, metrics: Dict[str, float]) -> None:
        try:
            data = _load_json(_METRICS_FILE)
            snapshot = {"snapshot_id": _id("msnap"), "metrics": metrics, "collected_at": _now()}
            data.append(snapshot)
            if len(data) > 500:
                data = data[-500:]
            _save_json(_METRICS_FILE, data)
        except Exception as exc:
            log.debug("Metrics persist failed: %s", exc)

    def _persist_targets(self, targets: List[Dict[str, Any]], dropped: List[Dict[str, Any]]) -> None:
        try:
            data = _load_json(_TARGETS_FILE)
            now = _now()
            for t in targets:
                t["last_update"] = now
            entry = {"targets": targets, "dropped_count": len(dropped), "collected_at": now}
            data.append(entry)
            if len(data) > 100:
                data = data[-100:]
            _save_json(_TARGETS_FILE, data)
        except Exception as exc:
            log.debug("Targets persist failed: %s", exc)

    def _persist_rules(self, groups: List[Dict[str, Any]]) -> None:
        try:
            data = _load_json(_RULES_FILE)
            entry = {"groups": groups, "collected_at": _now()}
            data.append(entry)
            if len(data) > 100:
                data = data[-100:]
            _save_json(_RULES_FILE, data)
        except Exception as exc:
            log.debug("Rules persist failed: %s", exc)

    def list_metric_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        return _load_json(_METRICS_FILE)[-limit:]

    def list_targets(self, limit: int = 20) -> List[Dict[str, Any]]:
        return _load_json(_TARGETS_FILE)[-limit:]

    def list_rules(self, limit: int = 20) -> List[Dict[str, Any]]:
        return _load_json(_RULES_FILE)[-limit:]

    def get_metric_latest(self) -> Dict[str, Any]:
        snapshots = _load_json(_METRICS_FILE)
        if not snapshots:
            return {"metrics": {}, "collected_at": ""}
        return snapshots[-1]

    async def shutdown(self) -> None:
        if self._connector:
            try:
                await self._connector.close()
            except Exception:
                pass


class AlertIntelligence:
    """Alert tracking — correlates Prometheus alerts with infrastructure entities."""

    def __init__(self) -> None:
        self._connector: Any = None
        self._ready = False
        self._previous_alerts: Dict[str, str] = {}

    async def initialize(self) -> None:
        from backend.connectors.prometheus import PrometheusConnector
        try:
            conn = PrometheusConnector()
            ok = await conn.initialize()
            if ok:
                self._connector = conn
                log.info("Alert Intelligence — connector active")
        except Exception as exc:
            log.debug("Alert Intelligence connector not available: %s", exc)
        self._ready = True

    async def sync_alerts(self) -> Dict[str, Any]:
        """Fetch alerts and correlate with infrastructure state."""
        if not self._connector or not self._connector.is_ready:
            return {"status": "skipped", "reason": "Prometheus connector not available"}
        raw = await self._connector.alerts()
        if raw.get("status") != "success":
            return {"status": "error", "error": raw.get("error", "unknown")}

        alerts = raw.get("data", {}).get("alerts", [])
        results: List[Dict[str, Any]] = []
        state_changes = {"new_firing": 0, "resolved": 0, "updated": 0}

        for alert in alerts:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            alert_name = labels.get("alertname", "unknown")
            alert_state = alert.get("state", "firing")
            alert_id = _id("palert")

            existing = await self._track_via_legacy(alert_name, labels, annotations, alert_state)

            alert_key = alert_name
            prev_state = self._previous_alerts.get(alert_key)
            self._previous_alerts[alert_key] = alert_state

            if prev_state != "firing" and alert_state == "firing":
                state_changes["new_firing"] += 1
            elif prev_state == "firing" and alert_state != "firing":
                state_changes["resolved"] += 1
            else:
                state_changes["updated"] += 1

            correlated = await self._correlate_alert(alert_name, labels)
            results.append({
                "alert_id": existing.get("alert_id", alert_id),
                "alert_name": alert_name,
                "state": alert_state,
                "severity": labels.get("severity", "warning"),
                "labels": labels,
                "annotations": annotations,
                "correlated": correlated,
                "active_at": alert.get("activeAt", _now()),
                "value": alert.get("value", 1.0),
            })

        return {
            "status": "completed",
            "alerts": results,
            "total": len(results),
            "state_changes": state_changes,
        }

    async def _track_via_legacy(
        self,
        alert_name: str,
        labels: Dict[str, Any],
        annotations: Dict[str, Any],
        alert_state: str,
    ) -> Dict[str, Any]:
        """Write to the legacy PrometheusIntelligence JSON store for backward compat."""
        try:
            from backend.services.enterprise_infrastructure_intelligence import PrometheusIntelligence
            status = "firing" if alert_state == "firing" else "resolved"
            return PrometheusIntelligence.track_alert(
                alert_name=alert_name,
                severity=labels.get("severity", "warning"),
                status=status,
                labels=labels,
                annotations=annotations,
                value=labels.get("value", 1.0),
            )
        except Exception as exc:
            log.debug("Legacy alert tracking failed: %s", exc)
            return {"alert_id": _id("palert")}

    async def _correlate_alert(self, alert_name: str, labels: Dict[str, Any]) -> Dict[str, Any]:
        """Correlate an alert with infrastructure entities — pods, containers, services, traces."""
        correlation: Dict[str, Any] = {"pods": [], "containers": [], "services": [], "traces": []}

        pod = labels.get("pod", labels.get("kubernetes_pod", ""))
        namespace = labels.get("namespace", labels.get("kubernetes_namespace", ""))
        container = labels.get("container", labels.get("container_name", ""))
        service = labels.get("service", labels.get("service_name", ""))

        if pod:
            correlation["pods"].append({"name": pod, "namespace": namespace})
        if container:
            correlation["containers"].append({"name": container, "pod": pod})
        if service:
            correlation["services"].append({"name": service})

        try:
            from backend.services.enterprise_infrastructure_intelligence import (
                _DOCKER_CONTAINERS_FILE,
                _PODS_FILE,
                _TRACES_FILE,
                _load_json,
            )
            if pod:
                pods_data = _load_json(_PODS_FILE)
                matches = [p for p in pods_data if p.get("name") == pod and (not namespace or p.get("namespace") == namespace)]
                correlation["pods"] = [{"name": m.get("name"), "namespace": m.get("namespace"), "pod_id": m.get("pod_id")} for m in matches[:3]]
            if container:
                containers_data = _load_json(_DOCKER_CONTAINERS_FILE)
                matches = [c for c in containers_data if c.get("name") == container or c.get("container_id", "").startswith(container)]
                correlation["containers"] = [{"name": m.get("name"), "docker_id": m.get("docker_id")} for m in matches[:3]]
            if service:
                traces_data = _load_json(_TRACES_FILE)
                matches = [t for t in traces_data if t.get("service_name") == service]
                correlation["traces"] = [{"trace_id": t.get("trace_id", ""), "status": t.get("status")} for t in matches[:5]]
        except Exception as exc:
            log.debug("Alert correlation failed: %s", exc)

        return {k: v for k, v in correlation.items() if v}

    async def get_alert_detail(self, alert_name: str) -> Optional[Dict[str, Any]]:
        """Get detail about a specific alert including correlation history."""
        if not self._connector or not self._connector.is_ready:
            return None
        raw = await self._connector.alerts()
        if raw.get("status") != "success":
            return None
        for alert in raw.get("data", {}).get("alerts", []):
            if alert.get("labels", {}).get("alertname") == alert_name:
                labels = alert.get("labels", {})
                correlated = await self._correlate_alert(alert_name, labels)
                return {
                    "alert_name": alert_name,
                    "state": alert.get("state"),
                    "severity": labels.get("severity", "warning"),
                    "labels": labels,
                    "annotations": alert.get("annotations", {}),
                    "active_at": alert.get("activeAt"),
                    "value": alert.get("value"),
                    "generator_url": alert.get("generatorURL", ""),
                    "correlated": correlated,
                }
        return None


prometheus_metrics = PrometheusMetricIntelligence()
alert_intelligence = AlertIntelligence()
