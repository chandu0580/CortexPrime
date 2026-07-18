"""
Enterprise Root Cause Analysis Intelligence — correlates GitHub, CI/CD,
Deployment, Infrastructure, Kubernetes, Docker, Helm, Prometheus, Grafana,
Loki, and OpenTelemetry data to identify root causes of production incidents.

Reuses every existing subsystem — no AI duplication, no new executives.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("RCA_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "rca")))
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_INCIDENTS_FILE = _DATA_DIR / "incidents.json"
_ANALYSES_FILE = _DATA_DIR / "analyses.json"

# =============================================================================
# Event constants
# =============================================================================

RCA_EVENTS: Dict[str, str] = {
    "incident_detected": "rca.incident_detected",
    "analysis_started": "rca.analysis_started",
    "correlation_completed": "rca.correlation_completed",
    "evidence_collected": "rca.evidence_collected",
    "root_cause_identified": "rca.root_cause_identified",
    "analysis_completed": "rca.analysis_completed",
    "engineering_story_generated": "rca.engineering_story_generated",
}

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


def _id(prefix: str = "rca") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_time(ts: Any) -> datetime:
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc)


# =============================================================================
# Typed result containers
# =============================================================================

RCA_TIMELINE_BUCKETS = [
    "github_push", "github_pr", "github_deploy",
    "cicd_pipeline", "cicd_build",
    "k8s_pod", "k8s_deployment", "k8s_rollback",
    "docker_container", "helm_release",
    "prometheus_alert",
    "loki_log",
    "otel_trace",
    "network_failure",
]


# =============================================================================
# Part 1 — Correlation Engine
# =============================================================================


class CorrelationEngine:
    """Correlates events across GitHub, CI/CD, Infrastructure, and Monitoring
    to identify related incidents."""

    @staticmethod
    def correlate_by_time(
        events: List[Dict[str, Any]],
        time_window_seconds: int = 300,
    ) -> List[Dict[str, Any]]:
        """Group events within a time window into correlation groups."""
        sorted_events = sorted(events, key=lambda e: _parse_time(e.get("timestamp", "")))
        groups: List[List[Dict[str, Any]]] = []
        current_group: List[Dict[str, Any]] = []
        current_time: Optional[datetime] = None

        for ev in sorted_events:
            ev_time = _parse_time(ev.get("timestamp", ""))
            if current_time is None:
                current_group = [ev]
                current_time = ev_time
            elif (ev_time - current_time).total_seconds() <= time_window_seconds:
                current_group.append(ev)
            else:
                if len(current_group) >= 2:
                    groups.append(current_group)
                current_group = [ev]
                current_time = ev_time

        if len(current_group) >= 2:
            groups.append(current_group)

        return [
            {
                "correlation_id": _id("corr"),
                "event_count": len(g),
                "time_start": min(_parse_time(e.get("timestamp", "")) for e in g).isoformat(),
                "time_end": max(_parse_time(e.get("timestamp", "")) for e in g).isoformat(),
                "sources": list(set(e.get("source", "") for e in g)),
                "events": [
                    {
                        "source": e.get("source", ""),
                        "entity_id": e.get("entity_id", ""),
                        "name": e.get("name", ""),
                        "status": e.get("status", ""),
                        "timestamp": e.get("timestamp", ""),
                    }
                    for e in g
                ],
            }
            for g in groups
        ]

    @staticmethod
    def correlate_by_entity(
        events: List[Dict[str, Any]],
        entity_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Group events sharing the same entity identifiers."""
        entity_keys = entity_keys or ["entity_id", "name", "namespace"]
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for ev in events:
            for key in entity_keys:
                val = ev.get(key)
                if val:
                    groups.setdefault(str(val), []).append(ev)
                    break
        return [
            {
                "correlation_id": _id("corr_entity"),
                "entity_key": key,
                "event_count": len(events),
                "sources": list(set(e.get("source", "") for e in events)),
                "events": [
                    {
                        "source": e.get("source", ""),
                        "entity_id": e.get("entity_id", ""),
                        "name": e.get("name", ""),
                        "status": e.get("status", ""),
                        "timestamp": e.get("timestamp", ""),
                    }
                    for e in events
                ],
            }
            for key, events in groups.items()
            if len(events) >= 2
        ]

    @staticmethod
    def correlate_prometheus_to_k8s(
        prometheus_alerts: List[Dict[str, Any]],
        k8s_pods: List[Dict[str, Any]],
        k8s_deployments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Link Prometheus alerts to Kubernetes resources."""
        correlations: List[Dict[str, Any]] = []
        for alert in prometheus_alerts:
            labels = alert.get("labels", {})
            alert_name = alert.get("alert_name", "")
            pod_match = None
            dep_match = None
            for pod in k8s_pods:
                pod_name = pod.get("name", "")
                if pod_name in str(labels) or pod_name == labels.get("pod", labels.get("kubernetes_pod", "")):
                    pod_match = pod
                    break
            for dep in k8s_deployments:
                dep_name = dep.get("name", "")
                if dep_name in str(labels) or dep_name == labels.get("deployment", labels.get("kubernetes_deployment", "")):
                    dep_match = dep
                    break
            correlations.append({
                "correlation_id": _id("prom_k8s"),
                "alert_name": alert_name,
                "severity": alert.get("severity", ""),
                "alert_timestamp": alert.get("updated_at", alert.get("created_at", "")),
                "related_pod": pod_match.get("name") if pod_match else None,
                "related_deployment": dep_match.get("name") if dep_match else None,
                "pod_status": pod_match.get("status") if pod_match else None,
                "deployment_status": dep_match.get("status") if dep_match else None,
            })
        return correlations

    @staticmethod
    def correlate_loki_to_traces(
        log_streams: List[Dict[str, Any]],
        traces: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Correlate log error streams to traces with errors."""
        correlations: List[Dict[str, Any]] = []
        for log_entry in log_streams:
            error_count = log_entry.get("error_count", 0)
            if error_count == 0:
                continue
            stream = log_entry.get("stream", "")
            matching_traces = [
                t for t in traces
                if t.get("error_spans", 0) > 0
                and (stream.startswith(t.get("service_name", "")) or t.get("service_name", "") in stream)
            ]
            correlations.append({
                "correlation_id": _id("log_trace"),
                "log_stream": stream,
                "log_errors": error_count,
                "trace_count": len(matching_traces),
                "trace_ids": [t.get("trace_id", "") for t in matching_traces[:5]],
                "total_error_spans": sum(t.get("error_spans", 0) for t in matching_traces),
            })
        return correlations

    @staticmethod
    def correlate_cicd_to_k8s(
        deployments: List[Dict[str, Any]],
        k8s_deployments: List[Dict[str, Any]],
        k8s_pods: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Correlate CI/CD deployments to Kubernetes resources by name."""
        correlations: List[Dict[str, Any]] = []
        for dep in deployments:
            dep_name = dep.get("name", dep.get("workflow_name", ""))
            env = dep.get("environment", dep.get("namespace", ""))
            image = dep.get("image", dep.get("version", ""))
            related_k8s = [d for d in k8s_deployments if dep_name in d.get("name", "") or d.get("image", "") == image]
            related_pods = [p for p in k8s_pods if p.get("namespace") == env or dep_name in p.get("name", "")]
            correlations.append({
                "correlation_id": _id("cicd_k8s"),
                "cicd_deployment_name": dep_name,
                "environment": env,
                "version": image,
                "k8s_deployments": [d.get("name") for d in related_k8s],
                "k8s_pods": [p.get("name") for p in related_pods],
                "k8s_deployment_count": len(related_k8s),
                "k8s_pod_count": len(related_pods),
            })
        return correlations


# =============================================================================
# Part 2 — Timeline Correlator
# =============================================================================


class TimelineCorrelator:
    """Builds a unified event timeline from all data sources."""

    @staticmethod
    def build_timeline(
        hours_back: int = 24,
        github_events: Optional[List[Dict[str, Any]]] = None,
        cicd_events: Optional[List[Dict[str, Any]]] = None,
        infra_events: Optional[List[Dict[str, Any]]] = None,
        log_analyses: Optional[List[Dict[str, Any]]] = None,
        traces: Optional[List[Dict[str, Any]]] = None,
        network_failures: Optional[List[Dict[str, Any]]] = None,
        prometheus_alerts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Merge events from all sources into a single sorted timeline."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        entries: List[Dict[str, Any]] = []

        for ev in (github_events or []):
            ts = _parse_time(ev.get("timestamp", ev.get("updated_at", "")))
            if ts >= cutoff:
                entries.append({
                    "source": "github",
                    "type": ev.get("event_type", ev.get("type", "github_event")),
                    "entity_id": ev.get("id", ev.get("entity_id", "")),
                    "name": ev.get("name", ev.get("title", ev.get("workflow_name", ""))),
                    "status": ev.get("status", ev.get("conclusion", ev.get("state", ""))),
                    "timestamp": ts.isoformat(),
                    "details": ev,
                })

        for ev in (cicd_events or []):
            ts = _parse_time(ev.get("timestamp", ev.get("updated_at", ev.get("created_at", ""))))
            if ts >= cutoff:
                entries.append({
                    "source": "cicd",
                    "type": ev.get("event_type", ev.get("source", "cicd_event")),
                    "entity_id": ev.get("entity_id", ev.get("pipeline_id", ev.get("build_id", ev.get("deployment_id", "")))),
                    "name": ev.get("name", ev.get("workflow_name", ev.get("environment", ""))),
                    "status": ev.get("status", ev.get("conclusion", "")),
                    "timestamp": ts.isoformat(),
                    "details": ev,
                })

        for ev in (infra_events or []):
            ts = _parse_time(ev.get("timestamp", ev.get("updated_at", ev.get("created_at", ""))))
            if ts >= cutoff:
                entries.append({
                    "source": "infrastructure",
                    "type": ev.get("source", ev.get("type", "infra_event")),
                    "entity_id": ev.get("entity_id", ev.get("pod_id", ev.get("deployment_id", ev.get("node_id", "")))),
                    "name": ev.get("name", ev.get("alert_name", "")),
                    "status": ev.get("status", ev.get("rollout_status", ev.get("phase", ""))),
                    "timestamp": ts.isoformat(),
                    "details": ev,
                })

        for ev in (prometheus_alerts or []):
            ts = _parse_time(ev.get("timestamp", ev.get("updated_at", ev.get("starts_at", ""))))
            if ts >= cutoff:
                entries.append({
                    "source": "prometheus",
                    "type": "alert",
                    "entity_id": ev.get("alert_id", ev.get("entity_id", "")),
                    "name": ev.get("alert_name", ev.get("name", "alert")),
                    "status": ev.get("status", ""),
                    "timestamp": ts.isoformat(),
                    "details": ev,
                })

        for ev in (log_analyses or []):
            ts = _parse_time(ev.get("analyzed_at", ""))
            if ts >= cutoff:
                entries.append({
                    "source": "loki",
                    "type": "log_analysis",
                    "entity_id": ev.get("analysis_id", ""),
                    "name": ev.get("stream", "log_stream"),
                    "status": "error" if ev.get("error_count", 0) > 0 else "ok",
                    "timestamp": ts.isoformat(),
                    "details": ev,
                })

        for ev in (traces or []):
            ts = _parse_time(ev.get("timestamp", ev.get("updated_at", ev.get("created_at", ""))))
            if ts >= cutoff:
                entries.append({
                    "source": "opentelemetry",
                    "type": "trace",
                    "entity_id": ev.get("trace_entry_id", ev.get("entity_id", "")),
                    "name": f"{ev.get('service_name', 'unknown')}/{ev.get('root_operation', 'unknown')}",
                    "status": "error" if ev.get("error_spans", 0) > 0 else ev.get("status", "ok"),
                    "timestamp": ts.isoformat(),
                    "details": ev,
                })

        for ev in (network_failures or []):
            ts = _parse_time(ev.get("detected_at", ""))
            if ts >= cutoff:
                entries.append({
                    "source": "network",
                    "type": "failure",
                    "entity_id": ev.get("failure_id", ""),
                    "name": f"{ev.get('source', '?')} -> {ev.get('destination', '?')}",
                    "status": "unresolved" if not ev.get("resolved", True) else "resolved",
                    "timestamp": ts.isoformat(),
                    "details": ev,
                })

        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return entries

    @staticmethod
    def extract_error_events(timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter timeline to only events with error/failure status."""
        error_statuses = {"failed", "error", "firing", "crashloop", "oom", "unavailable",
                          "degraded", "unresolved", "rollback", "cancelled", "timed_out"}
        return [
            e for e in timeline
            if e.get("status", "").lower() in error_statuses
        ]

    @staticmethod
    def find_adjacent_events(
        timeline: List[Dict[str, Any]],
        event_index: int,
        window_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """Find events adjacent to a given event index within a time window."""
        if event_index < 0 or event_index >= len(timeline):
            return []
        target = timeline[event_index]
        target_time = _parse_time(target["timestamp"])
        adjacent: List[Dict[str, Any]] = []
        for i, ev in enumerate(timeline):
            if i == event_index:
                continue
            ev_time = _parse_time(ev["timestamp"])
            diff_minutes = abs((ev_time - target_time).total_seconds()) / 60
            if diff_minutes <= window_minutes:
                adjacent.append(ev)
        return adjacent


# =============================================================================
# Part 3 — Evidence Collector
# =============================================================================


class EvidenceCollector:
    """Collects evidence from all enterprise subsystems."""

    @staticmethod
    def collect_from_pods(pods: List[Dict[str, Any]], namespace: str = "") -> Dict[str, Any]:
        filtered = [p for p in pods if not namespace or p.get("namespace") == namespace]
        error_pods = [p for p in filtered if p.get("status") in ("failed", "crashloop", "error")]
        oom_pods = [p for p in filtered if p.get("oom_detected")]
        crashloop_pods = [p for p in filtered if p.get("crashloop_detected")]
        return {
            "total_pods": len(filtered),
            "error_pods": len(error_pods),
            "oom_pods": len(oom_pods),
            "crashloop_pods": len(crashloop_pods),
            "pod_details": [
                {"name": p["name"], "namespace": p.get("namespace", ""),
                 "status": p["status"], "restarts": p.get("restarts", 0),
                 "oom_detected": p.get("oom_detected", False),
                 "crashloop_detected": p.get("crashloop_detected", False)}
                for p in error_pods + oom_pods + crashloop_pods
            ][:50],
        }

    @staticmethod
    def collect_from_deployments(deployments: List[Dict[str, Any]], namespace: str = "") -> Dict[str, Any]:
        filtered = [d for d in deployments if not namespace or d.get("namespace") == namespace]
        rollbacks = [d for d in filtered if d.get("rollout_status") == "rollback"]
        unavailable = [d for d in filtered if d.get("status") in ("unavailable", "failed")]
        return {
            "total_deployments": len(filtered),
            "rollbacks": len(rollbacks),
            "unavailable": len(unavailable),
            "deployment_details": [
                {"name": d["name"], "namespace": d.get("namespace", ""),
                 "status": d["status"], "rollout_status": d.get("rollout_status", "")}
                for d in (rollbacks + unavailable)
            ][:50],
        }

    @staticmethod
    def collect_from_alerts(alerts: List[Dict[str, Any]], min_severity: str = "warning") -> Dict[str, Any]:
        sev_levels = {"info": 0, "warning": 1, "critical": 2}
        min_level = sev_levels.get(min_severity, 1)
        firing = [
            a for a in alerts
            if a.get("status") == "firing"
            and sev_levels.get(a.get("severity", "info"), 0) >= min_level
        ]
        return {
            "total_firing_alerts": len(firing),
            "alert_details": [
                {"alert_name": a["alert_name"], "severity": a.get("severity", ""),
                 "value": a.get("value", 0), "labels": a.get("labels", {})}
                for a in firing
            ][:50],
        }

    @staticmethod
    def collect_from_logs(analyses: List[Dict[str, Any]], min_errors: int = 1) -> Dict[str, Any]:
        with_errors = [a for a in analyses if a.get("error_count", 0) >= min_errors]
        return {
            "total_log_streams_with_errors": len(with_errors),
            "log_details": [
                {"stream": a["stream"], "error_count": a.get("error_count", 0),
                 "warn_count": a.get("warn_count", 0), "total_lines": a.get("total_lines", 0),
                 "log_sample": a.get("log_sample", [])[:10]}
                for a in with_errors
            ][:50],
        }

    @staticmethod
    def collect_from_traces(traces: List[Dict[str, Any]], min_error_spans: int = 1) -> Dict[str, Any]:
        with_errors = [t for t in traces if t.get("error_spans", 0) >= min_error_spans]
        return {
            "total_traces_with_errors": len(with_errors),
            "trace_details": [
                {"trace_id": t["trace_id"], "service_name": t.get("service_name", ""),
                 "error_spans": t.get("error_spans", 0), "total_spans": t.get("total_spans", 0),
                 "duration_ms": t.get("duration_ms", 0), "p95_ms": t.get("latency_p95", 0)}
                for t in with_errors
            ][:50],
        }

    @staticmethod
    def collect_from_network(network_failures: List[Dict[str, Any]]) -> Dict[str, Any]:
        unresolved = [f for f in network_failures if not f.get("resolved", True)]
        return {
            "total_unresolved_failures": len(unresolved),
            "failure_details": [
                {"source": f["source"], "destination": f.get("destination", ""),
                 "reason": f.get("reason", ""), "protocol": f.get("protocol", ""),
                 "port": f.get("port", 0), "namespace": f.get("namespace", "")}
                for f in unresolved
            ][:50],
        }

    @staticmethod
    def collect_all_subsystem_evidence() -> Dict[str, Any]:
        """Collect evidence from all available subsystems."""
        evidence: Dict[str, Any] = {}

        try:
            from backend.services.enterprise_infrastructure_intelligence import (
                KubernetesIntelligence,
                LokiLogIntelligence,
                OpenTelemetryTraceIntelligence,
                PrometheusIntelligence,
            )
            evidence["pods"] = EvidenceCollector.collect_from_pods(KubernetesIntelligence.list_pods())
            evidence["deployments"] = EvidenceCollector.collect_from_deployments(KubernetesIntelligence.list_deployments())
            evidence["alerts"] = EvidenceCollector.collect_from_alerts(PrometheusIntelligence.list_alerts(status="firing"))
            evidence["logs"] = EvidenceCollector.collect_from_logs(LokiLogIntelligence.list_analyses())
            evidence["traces"] = EvidenceCollector.collect_from_traces(OpenTelemetryTraceIntelligence.list_traces())
            evidence["network"] = EvidenceCollector.collect_from_network(KubernetesIntelligence.list_network_failures())
        except Exception as exc:
            log.debug("Infrastructure evidence unavailable: %s", exc)

        try:
            from backend.services.enterprise_cicd_intelligence import BuildIntelligence, DeploymentIntelligence
            evidence["builds"] = {
                "total_builds": len(BuildIntelligence.list_builds()),
                "failed_builds": len(BuildIntelligence.list_builds(status="failed")),
            }
            evidence["cicd_deployments"] = {
                "total": len(DeploymentIntelligence.list_deployments()),
                "failed": len(DeploymentIntelligence.list_deployments(status="failed")),
            }
        except Exception as exc:
            log.debug("CI/CD evidence unavailable: %s", exc)

        try:
            from backend.services.enterprise_github_integration import github_integration
            evidence["github"] = {
                "workflow_runs": len(github_integration.list_workflow_runs() if hasattr(github_integration, 'list_workflow_runs') else []),
                "open_issues": github_integration.get_open_issue_count() if hasattr(github_integration, 'get_open_issue_count') else 0,
            }
        except Exception as exc:
            log.debug("GitHub evidence unavailable: %s", exc)

        return evidence


# =============================================================================
# Part 4 — Root Cause Builder
# =============================================================================


class RootCauseBuilder:
    """Constructs root cause hypotheses from collected evidence."""

    PATTERNS = [
        {
            "pattern_id": "deploy_failure_causes_pod_crash",
            "description": "Recent deployment failure followed by pod crashes",
            "conditions": lambda ev: (
                any(e["source"] == "cicd" and e["status"] in ("failed", "error") for e in ev)
                and any(e["source"] == "infrastructure" and e["status"] in ("crashloop", "error", "failed") for e in ev)
            ),
            "root_cause": "Failed deployment triggered pod instability",
            "category": "deployment",
        },
        {
            "pattern_id": "prometheus_alert_precedes_pod_failure",
            "description": "Prometheus alert firing before pod crash events",
            "conditions": lambda ev: (
                any(e["source"] == "prometheus" and e["status"] == "firing" for e in ev)
                and any(e["source"] == "infrastructure" and e["status"] in ("crashloop", "oom", "failed") for e in ev)
            ),
            "root_cause": "Resource exhaustion detected by monitoring before pod failure",
            "category": "resource",
        },
        {
            "pattern_id": "log_errors_with_trace_errors",
            "description": "Log errors correlated with trace error spans",
            "conditions": lambda ev: (
                any(e["source"] == "loki" and e["status"] == "error" for e in ev)
                and any(e["source"] == "opentelemetry" and e["status"] == "error" for e in ev)
            ),
            "root_cause": "Application error detected in logs and confirmed by distributed tracing",
            "category": "application",
        },
        {
            "pattern_id": "network_failure_with_pod_issues",
            "description": "Network failures followed by pod or deployment issues",
            "conditions": lambda ev: (
                any(e["source"] == "network" for e in ev)
                and any(e["source"] in ("infrastructure", "prometheus") and e["status"] in ("failed", "firing") for e in ev)
            ),
            "root_cause": "Network connectivity issues causing cascading pod failures",
            "category": "network",
        },
        {
            "pattern_id": "rollback_after_deploy_failure",
            "description": "Deployment rollback following CI/CD build/deploy failure",
            "conditions": lambda ev: (
                any(e["source"] == "infrastructure" and e["status"] == "rollback" for e in ev)
                and any(e["source"] == "cicd" and e["status"] in ("failed", "error") for e in ev)
            ),
            "root_cause": "CI/CD pipeline failure triggered automated rollback",
            "category": "deployment",
        },
        {
            "pattern_id": "oom_killed_with_memory_pressure",
            "description": "OOMKilled pods with prior memory-related Prometheus alerts",
            "conditions": lambda ev: (
                any(e["status"] == "oom" for e in ev)
                or any(e.get("details", {}).get("oom_detected") for e in ev)
            ),
            "root_cause": "Out of memory: containers exceeded memory limits",
            "category": "resource",
        },
        {
            "pattern_id": "crashloop_after_image_update",
            "description": "CrashLoopBackOff following a deployment image change",
            "conditions": lambda ev: (
                any(e["status"] == "crashloop" for e in ev)
                and any(e["source"] == "cicd" or e["source"] == "github" for e in ev)
            ),
            "root_cause": "Application crash loop triggered by recent image or configuration change",
            "category": "application",
        },
        {
            "pattern_id": "multiple_alerts_precede_failure",
            "description": "Multiple Prometheus alerts firing before infrastructure failure",
            "conditions": lambda ev: (
                len([e for e in ev if e["source"] == "prometheus"]) >= 2
                and any(e["source"] in ("infrastructure", "network", "loki") for e in ev)
            ),
            "root_cause": "Systemic issue indicated by multiple monitoring alerts",
            "category": "systemic",
        },
    ]

    @staticmethod
    def build_hypotheses(timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluate all patterns against the timeline and generate hypotheses."""
        hypotheses: List[Dict[str, Any]] = []
        for pattern in RootCauseBuilder.PATTERNS:
            try:
                if pattern["conditions"](timeline):
                    matching_events = [
                        {"source": e["source"], "type": e.get("type", ""),
                         "name": e["name"], "status": e["status"], "timestamp": e["timestamp"]}
                        for e in timeline
                        if pattern["conditions"]([e])
                    ]
                    hypotheses.append({
                        "hypothesis_id": _id("hyp"),
                        "pattern_id": pattern["pattern_id"],
                        "description": pattern["description"],
                        "root_cause": pattern["root_cause"],
                        "category": pattern["category"],
                        "matching_event_count": len(matching_events),
                        "matching_events": matching_events[:20],
                    })
            except Exception as exc:
                log.debug("Pattern %s evaluation failed: %s", pattern["pattern_id"], exc)
        return hypotheses

    @staticmethod
    def classify_by_severity(hypotheses: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Classify hypotheses by severity category."""
        categories: Dict[str, List[Dict[str, Any]]] = {
            "deployment": [], "resource": [], "application": [], "network": [], "systemic": [],
        }
        for h in hypotheses:
            cat = h.get("category", "systemic")
            categories.setdefault(cat, []).append(h)
        return categories


# =============================================================================
# Part 5 — Confidence Calculator
# =============================================================================


class ConfidenceCalculator:
    """Calculates confidence scores for root cause hypotheses."""

    @staticmethod
    def calculate(hypothesis: Dict[str, Any], timeline: List[Dict[str, Any]], total_evidence_sources: int = 3) -> float:
        """Calculate confidence score (0.0 - 1.0) for a hypothesis."""
        score = 0.0

        # Factor 1: Event evidence coverage (0-0.4)
        event_count = len(timeline)
        if event_count >= 20:
            score += 0.4
        elif event_count >= 10:
            score += 0.3
        elif event_count >= 5:
            score += 0.2
        elif event_count >= 2:
            score += 0.1

        # Factor 2: Source diversity (0-0.25)
        sources = set(e["source"] for e in timeline)
        source_count = len(sources)
        score += min(source_count * 0.05, 0.25)

        # Factor 3: Matching events support (0-0.2)
        matching = hypothesis.get("matching_event_count", 0)
        score += min(matching * 0.04, 0.2)

        # Factor 4: Timeliness - recent events are stronger evidence (0-0.15)
        now = datetime.now(timezone.utc)
        recent_count = sum(
            1 for e in timeline
            if (_parse_time(e["timestamp"]) - now).total_seconds() > -3600
        )
        score += min(recent_count * 0.03, 0.15)

        return round(min(score, 1.0), 2)

    @staticmethod
    def rank_hypotheses(hypotheses: List[Dict[str, Any]], timeline: List[Dict[str, Any]], total_sources: int = 3) -> List[Dict[str, Any]]:
        """Rank hypotheses by confidence score."""
        ranked = []
        for h in hypotheses:
            confidence = ConfidenceCalculator.calculate(h, timeline, total_sources)
            ranked.append({**h, "confidence": confidence})
        ranked.sort(key=lambda h: h["confidence"], reverse=True)
        return ranked

    @staticmethod
    def get_confidence_label(score: float) -> str:
        if score >= 0.8:
            return "very_high"
        if score >= 0.6:
            return "high"
        if score >= 0.4:
            return "medium"
        if score >= 0.2:
            return "low"
        return "very_low"


# =============================================================================
# Part 6 — Impact Analyzer
# =============================================================================


class ImpactAnalyzer:
    """Determines blast radius of incidents across all tracked entities."""

    @staticmethod
    def analyze(timeline: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze impact from timeline events."""
        affected_services: set = set()
        affected_deployments: set = set()
        affected_commits: set = set()
        affected_prs: set = set()
        affected_builds: set = set()
        affected_infrastructure: set = set()

        for ev in timeline:
            details = ev.get("details", {})
            source = ev.get("source", "")
            name = ev.get("name", "")
            entity_id = ev.get("entity_id", "")

            if source == "github":
                ev_type = ev.get("type", "")
                if "pr" in ev_type or "pull_request" in ev_type:
                    affected_prs.add(name)
                if "commit" in ev_type or "push" in ev_type:
                    affected_commits.add(name)
                if "deploy" in ev_type:
                    affected_deployments.add(name)
                affected_services.add(details.get("repository", name))

            elif source == "cicd":
                ev_type = ev.get("type", "")
                if "build" in ev_type or ev.get("entity_id", "").startswith("build_"):
                    affected_builds.add(name or entity_id)
                if "deploy" in ev_type:
                    affected_deployments.add(name or entity_id)
                    affected_services.add(details.get("repository", details.get("environment", name)))
                if "pipeline" in ev_type:
                    affected_services.add(name or entity_id)

            elif source in ("infrastructure", "prometheus", "network"):
                ns = details.get("namespace", details.get("namespace", ""))
                affected_infrastructure.add(f"{ns}/{name}" if ns else name)
                affected_services.add(f"k8s:{ns}" if ns else name)

            elif source == "loki":
                stream = details.get("stream", name)
                affected_services.add(stream)

            elif source == "opentelemetry":
                svc = details.get("service_name", name)
                affected_services.add(svc)

        return {
            "affected_services": sorted(affected_services),
            "affected_deployments": sorted(affected_deployments),
            "affected_commits": sorted(affected_commits),
            "affected_prs": sorted(affected_prs),
            "affected_builds": sorted(affected_builds),
            "affected_infrastructure": sorted(affected_infrastructure),
        }

    @staticmethod
    def count_impacted(impact: Dict[str, Any]) -> int:
        return sum(len(v) for v in impact.values())


# =============================================================================
# Part 7 — Engineering Story Generator
# =============================================================================


class EngineeringStoryGenerator:
    """Generates human-readable engineering incident narratives."""

    @staticmethod
    def generate(
        problem: str,
        timeline: List[Dict[str, Any]],
        top_hypothesis: Optional[Dict[str, Any]],
        impact: Dict[str, Any],
        confidence: float,
        evidence_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = _now()
        story_id = _id("story")

        # Determine the most affected areas
        top_failing_source = max(
            set(e["source"] for e in timeline),
            key=lambda s: sum(1 for e in timeline if e["source"] == s and e["status"] in ("failed", "error", "firing", "crashloop")),
            default="unknown",
        )

        time_window = ""
        if timeline:
            times = [_parse_time(e["timestamp"]) for e in timeline]
            time_window = f"{min(times).strftime('%H:%M UTC')} – {max(times).strftime('%H:%M UTC')}"

        confidence_label = ConfidenceCalculator.get_confidence_label(confidence)

        story_parts: List[str] = []
        story_parts.append(f"## Incident Overview\n\n**Problem:** {problem}\n")
        story_parts.append(f"**Timeline Window:** {time_window}" if time_window else "")
        story_parts.append(f"**Primary Source:** {top_failing_source}\n")
        story_parts.append(f"**Confidence:** {confidence_label} ({confidence:.0%})\n")

        # What happened (executive summary)
        if top_hypothesis:
            story_parts.append(f"## Likely Root Cause\n\n{top_hypothesis['root_cause']}\n")
            story_parts.append(f"Based on pattern `{top_hypothesis['pattern_id']}`: {top_hypothesis['description']}\n")

        # Impact
        story_parts.append("## Impact Analysis\n")
        impact_lines = []
        for category, items in impact.items():
            label = category.replace("affected_", "").replace("_", " ").title()
            if items:
                impact_lines.append(f"- **{label}** ({len(items)}): {', '.join(items[:5])}")
        story_parts.extend(impact_lines)

        # Evidence summary
        story_parts.append("\n## Evidence\n")
        for key, val in evidence_summary.items():
            if isinstance(val, dict):
                if val.get("total_firing_alerts", 0) > 0:
                    story_parts.append(f"- **Alerts:** {val['total_firing_alerts']} firing")
                if val.get("error_pods", 0) > 0:
                    story_parts.append(f"- **Pods:** {val['error_pods']} in error, {val.get('oom_pods', 0)} OOM, {val.get('crashloop_pods', 0)} crashloop")
                if val.get("rollbacks", 0) > 0:
                    story_parts.append(f"- **Deployments:** {val['rollbacks']} rollbacks, {val.get('unavailable', 0)} unavailable")
                if val.get("total_log_streams_with_errors", 0) > 0:
                    story_parts.append(f"- **Logs:** {val['total_log_streams_with_errors']} streams with errors")
                if val.get("total_traces_with_errors", 0) > 0:
                    story_parts.append(f"- **Traces:** {val['total_traces_with_errors']} traces with error spans")
                if val.get("total_unresolved_failures", 0) > 0:
                    story_parts.append(f"- **Network:** {val['total_unresolved_failures']} unresolved failures")

        # Timeline
        story_parts.append("\n## Event Timeline\n")
        for ev in timeline[:30]:
            ts = _parse_time(ev["timestamp"])
            story_parts.append(f"- [{ts.strftime('%H:%M:%S')}] **{ev['source']}** — {ev['name']} ({ev['status']})")

        story = "\n".join(story_parts)

        return {
            "story_id": story_id,
            "problem": problem,
            "story": story,
            "story_parts": story_parts,
            "generated_at": now,
            "confidence_label": confidence_label,
            "confidence_score": confidence,
        }


# =============================================================================
# Part 8 — Root Cause Analysis Service (orchestrator)
# =============================================================================


class RootCauseAnalysisService:
    """Orchestrator for enterprise root cause analysis — runs the full RCA
    pipeline: detect → correlate → collect evidence → build hypotheses →
    calculate confidence → analyze impact → generate story."""

    def __init__(self) -> None:
        self._ready = False

    async def initialize(self) -> None:
        self._ready = True
        log.info("Enterprise Root Cause Analysis Service ready")

    async def _emit(self, event_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="root_cause_analysis",
                message=data.get("message", "RCA event"),
                execution_id=entity_id,
                metadata=data,
            )
        except Exception as exc:
            log.warning("RCA event emit failed: %s", exc)

    async def _record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        try:
            from backend.services.enterprise_analytics_service import analytics_service
            await analytics_service.record_metric(
                metric_type="quality",
                name=name,
                value=value,
                labels=labels or {},
            )
        except Exception as exc:
            log.debug("RCA metric recording failed: %s", exc)

    async def _get_learning_patterns(self) -> List[Dict[str, Any]]:
        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            patterns = await enterprise_learning.list_patterns() if hasattr(enterprise_learning, 'list_patterns') else []
            return patterns or []
        except Exception:
            return []

    async def _get_knowledge_graph_entities(self, query: str = "") -> List[Dict[str, Any]]:
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            if hasattr(enterprise_graph, 'search_entities'):
                return await enterprise_graph.search_entities(query) if query else (await enterprise_graph.list_entities() if hasattr(enterprise_graph, 'list_entities') else [])
            return []
        except Exception:
            return []

    async def _get_recommendation(self, context: str, summary: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
            return await enterprise_recommendation_engine.generate(
                context=context,
                summary=summary,
                metrics=metrics,
            )
        except Exception as exc:
            log.debug("Recommendation unavailable: %s", exc)
            return {"status": "unavailable", "error": str(exc)}

    async def _get_explainability(self, incident_id: str, root_cause: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.services.enterprise_explainability_service import enterprise_explainability
            if hasattr(enterprise_explainability, 'explain'):
                return await enterprise_explainability.explain(
                    entity_id=incident_id,
                    conclusion=root_cause,
                    evidence=evidence,
                )
            return {"explanation": root_cause, "method": "rule_based"}
        except Exception:
            return {"explanation": root_cause, "method": "rule_based"}

    async def _sync_engineering_executive(self, problem: str, severity: str = "medium") -> Dict[str, Any]:
        try:
            from backend.services.enterprise_engineering_executive import get_engineering_executive
            ee = get_engineering_executive()
            task = await ee.create_task(
                title=f"RCA: {problem[:100]}",
                description=problem,
                priority=severity,
                source="root_cause_analysis",
            )
            return task
        except Exception as exc:
            log.debug("Engineering Executive sync failed: %s", exc)
            return {"status": "unavailable", "error": str(exc)}

    def _collect_all_timeline_data(self, hours_back: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        data: Dict[str, List[Dict[str, Any]]] = {}
        try:
            from backend.services.enterprise_infrastructure_intelligence import (
                KubernetesIntelligence,
                LokiLogIntelligence,
                OpenTelemetryTraceIntelligence,
                PrometheusIntelligence,
            )
            data["k8s_pods"] = KubernetesIntelligence.list_pods()
            data["k8s_deployments"] = KubernetesIntelligence.list_deployments()
            data["prometheus_alerts"] = PrometheusIntelligence.list_alerts()
            data["loki_logs"] = LokiLogIntelligence.list_analyses()
            data["traces"] = OpenTelemetryTraceIntelligence.list_traces()
            data["network_failures"] = KubernetesIntelligence.list_network_failures()
        except Exception as exc:
            log.debug("Infrastructure data unavailable: %s", exc)

        try:
            from backend.services.enterprise_cicd_intelligence import (
                BuildIntelligence,
                DeploymentIntelligence,
                cicd_intelligence,
            )
            data["cicd_builds"] = BuildIntelligence.list_builds()
            data["cicd_deployments"] = DeploymentIntelligence.list_deployments()
            raw_timeline = cicd_intelligence.get_timeline(limit=200) if hasattr(cicd_intelligence, 'get_timeline') else []
            data["cicd_events"] = raw_timeline.get("timeline", raw_timeline) if isinstance(raw_timeline, dict) else raw_timeline
        except Exception as exc:
            log.debug("CI/CD data unavailable: %s", exc)

        try:
            from backend.services.enterprise_github_integration import github_integration
            if hasattr(github_integration, 'list_workflow_runs'):
                data["github_events"] = github_integration.list_workflow_runs()
        except Exception as exc:
            log.debug("GitHub data unavailable: %s", exc)

        return data

    async def run_full_analysis(
        self,
        problem: str = "",
        hours_back: int = 24,
        incident_id: str = "",
    ) -> Dict[str, Any]:
        """Run the complete RCA pipeline and return a full analysis report."""
        analysis_id = _id("analysis")
        incident_id = incident_id or _id("incident")
        now = _now()

        if not problem:
            problem = f"Production incident detected at {now}"

        await self._emit(RCA_EVENTS["incident_detected"], incident_id, {"message": problem})

        # 1. Collect all source data
        source_data = self._collect_all_timeline_data(hours_back)
        await self._emit(RCA_EVENTS["analysis_started"], analysis_id, {"incident_id": incident_id})

        # 2. Build unified timeline
        timeline = TimelineCorrelator.build_timeline(
            hours_back=hours_back,
            github_events=source_data.get("github_events", []),
            cicd_events=source_data.get("cicd_events", []),
            infra_events=[],
            log_analyses=source_data.get("loki_logs", []),
            traces=source_data.get("traces", []),
            network_failures=source_data.get("network_failures", []),
            prometheus_alerts=source_data.get("prometheus_alerts", []),
        )

        # Add infrastructure events separately (they're raw, not pre-formatted)
        for ev in source_data.get("k8s_pods", []) + source_data.get("k8s_deployments", []):
            ts = _parse_time(ev.get("updated_at", ev.get("created_at", "")))
            if ts >= datetime.now(timezone.utc) - timedelta(hours=hours_back):
                timeline.append({
                    "source": "infrastructure",
                    "type": ev.get("source", "k8s_resource"),
                    "entity_id": ev.get("pod_id", ev.get("deployment_id", ev.get("entity_id", ""))),
                    "name": ev.get("name", ""),
                    "status": ev.get("status", ev.get("rollout_status", "")),
                    "timestamp": ts.isoformat(),
                    "details": ev,
                })

        timeline.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        await self._emit(RCA_EVENTS["correlation_completed"], analysis_id, {"timeline_count": len(timeline)})

        # 3. Collect evidence
        evidence_summary: Dict[str, Any] = {}
        if source_data.get("k8s_pods"):
            evidence_summary["pods"] = EvidenceCollector.collect_from_pods(source_data["k8s_pods"])
        if source_data.get("k8s_deployments"):
            evidence_summary["deployments"] = EvidenceCollector.collect_from_deployments(source_data["k8s_deployments"])
        if source_data.get("prometheus_alerts"):
            evidence_summary["alerts"] = EvidenceCollector.collect_from_alerts(source_data["prometheus_alerts"])
        if source_data.get("loki_logs"):
            evidence_summary["logs"] = EvidenceCollector.collect_from_logs(source_data["loki_logs"])
        if source_data.get("traces"):
            evidence_summary["traces"] = EvidenceCollector.collect_from_traces(source_data["traces"])
        if source_data.get("network_failures"):
            evidence_summary["network"] = EvidenceCollector.collect_from_network(source_data["network_failures"])

        # Try to use explainability to explain the evidence
        try:
            KG_entities = await self._get_knowledge_graph_entities()
            if KG_entities:
                evidence_summary["knowledge_graph"] = {"entities_found": len(KG_entities)}
        except Exception:
            pass

        await self._emit(RCA_EVENTS["evidence_collected"], analysis_id, {"evidence_sources": list(evidence_summary.keys())})

        # 4. Build root cause hypotheses
        error_timeline = TimelineCorrelator.extract_error_events(timeline)
        hypotheses = RootCauseBuilder.build_hypotheses(error_timeline if error_timeline else timeline)
        if not hypotheses:
            hypotheses.append({
                "hypothesis_id": _id("hyp"),
                "pattern_id": "generic_incident",
                "description": "No specific pattern matched — general incident analysis",
                "root_cause": "Unknown — insufficient correlating evidence",
                "category": "systemic",
                "matching_event_count": len(timeline),
                "matching_events": [{"source": e["source"], "name": e["name"], "status": e["status"], "timestamp": e["timestamp"]} for e in timeline[:10]],
            })

        # 5. Calculate confidence and rank
        ranked = ConfidenceCalculator.rank_hypotheses(hypotheses, timeline)
        top_hypothesis = ranked[0] if ranked else None

        await self._emit(RCA_EVENTS["root_cause_identified"], analysis_id, {
            "root_cause": top_hypothesis["root_cause"] if top_hypothesis else "Unknown",
            "confidence": top_hypothesis["confidence"] if top_hypothesis else 0,
        })

        # 6. Analyze impact
        impact = ImpactAnalyzer.analyze(timeline)

        # 7. Generate engineering story
        confidence_score = top_hypothesis["confidence"] if top_hypothesis else 0.0
        story = EngineeringStoryGenerator.generate(
            problem=problem,
            timeline=timeline,
            top_hypothesis=top_hypothesis,
            impact=impact,
            confidence=confidence_score,
            evidence_summary=evidence_summary,
        )
        await self._emit(RCA_EVENTS["engineering_story_generated"], analysis_id, {"story_id": story["story_id"]})

        # 8. Generate recommendation (reuses recommendation engine)
        recommendation = await self._get_recommendation(
            context="root_cause_analysis",
            summary=top_hypothesis["root_cause"] if top_hypothesis else problem,
            metrics={"impacted_entities": ImpactAnalyzer.count_impacted(impact), "confidence": confidence_score},
        )

        # 9. Build recovery actions
        recovery_actions: List[str] = []
        if impact.get("affected_deployments"):
            recovery_actions.append(f"Roll back {len(impact['affected_deployments'])} affected deployment(s)")
        if impact.get("affected_infrastructure"):
            recovery_actions.append("Investigate and resolve infrastructure issues")
        if source_data.get("network_failures"):
            recovery_actions.append("Resolve active network failures")
        if evidence_summary.get("pods", {}).get("crashloop_pods", 0) > 0:
            recovery_actions.append("Investigate CrashLoopBackOff pods — check resource limits and application health")
        if evidence_summary.get("pods", {}).get("oom_pods", 0) > 0:
            recovery_actions.append("Increase memory limits for OOMKilled containers")
        if evidence_summary.get("alerts", {}).get("total_firing_alerts", 0) > 0:
            recovery_actions.append("Address firing Prometheus alerts")
        if not recovery_actions:
            recovery_actions.append("Manual investigation required — no automated recovery identified")

        # 10. Sync to Engineering Executive
        await self._sync_engineering_executive(problem)

        # Record metrics
        await self._record_metric("rca.analyses", 1)
        await self._record_metric(f"rca.confidence.{confidence_score:.0%}", confidence_score)
        await self._record_metric("rca.hypotheses", len(hypotheses))

        # Build final analysis report
        analysis: Dict[str, Any] = {
            "analysis_id": analysis_id,
            "incident_id": incident_id,
            "problem": problem,
            "timestamp": now,
            "time_window_hours": hours_back,
            "timeline": timeline,
            "evidence": evidence_summary,
            "hypotheses": ranked,
            "top_hypothesis": top_hypothesis,
            "impact": impact,
            "recommendation": recommendation,
            "recovery_actions": recovery_actions,
            "story": story,
            "summary": {
                "total_events_in_timeline": len(timeline),
                "error_events": len(error_timeline),
                "total_hypotheses": len(ranked),
                "top_root_cause": top_hypothesis["root_cause"] if top_hypothesis else "Unknown",
                "confidence_score": confidence_score,
                "confidence_label": ConfidenceCalculator.get_confidence_label(confidence_score),
                "affected_services_count": len(impact.get("affected_services", [])),
                "affected_deployments_count": len(impact.get("affected_deployments", [])),
                "affected_builds_count": len(impact.get("affected_builds", [])),
            },
            "correlations": {
                "prometheus_to_k8s": CorrelationEngine.correlate_prometheus_to_k8s(
                    source_data.get("prometheus_alerts", []),
                    source_data.get("k8s_pods", []),
                    source_data.get("k8s_deployments", []),
                ),
                "loki_to_traces": CorrelationEngine.correlate_loki_to_traces(
                    source_data.get("loki_logs", []),
                    source_data.get("traces", []),
                ),
                "cicd_to_k8s": CorrelationEngine.correlate_cicd_to_k8s(
                    source_data.get("cicd_deployments", []),
                    source_data.get("k8s_deployments", []),
                    source_data.get("k8s_pods", []),
                ),
            },
        }

        # Persist analysis
        analyses = _load_json(_ANALYSES_FILE)
        analyses.append(analysis)
        if len(analyses) > 500:
            analyses = analyses[-500:]
        _save_json(_ANALYSES_FILE, analyses)

        # Persist incident
        incidents = _load_json(_INCIDENTS_FILE)
        incidents.append({
            "incident_id": incident_id,
            "analysis_id": analysis_id,
            "problem": problem,
            "root_cause": top_hypothesis["root_cause"] if top_hypothesis else "Unknown",
            "confidence": confidence_score,
            "timestamp": now,
        })
        if len(incidents) > 500:
            incidents = incidents[-500:]
        _save_json(_INCIDENTS_FILE, incidents)

        await self._emit(RCA_EVENTS["analysis_completed"], analysis_id, {"analysis_id": analysis_id})
        return analysis

    async def run_analysis(self, incident_id: str = "", problem: str = "", hours_back: int = 24) -> Dict[str, Any]:
        """Public entry point for running an analysis."""
        return await self.run_full_analysis(problem=problem, hours_back=hours_back, incident_id=incident_id)

    def list_analyses(self, limit: int = 50) -> List[Dict[str, Any]]:
        return _load_json(_ANALYSES_FILE)[:limit]

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        return next((a for a in _load_json(_ANALYSES_FILE) if a.get("analysis_id") == analysis_id), None)

    def list_incidents(self, limit: int = 50) -> List[Dict[str, Any]]:
        return _load_json(_INCIDENTS_FILE)[:limit]

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return next((i for i in _load_json(_INCIDENTS_FILE) if i.get("incident_id") == incident_id), None)

    def get_dashboard(self) -> Dict[str, Any]:
        analyses = _load_json(_ANALYSES_FILE)
        incidents = _load_json(_INCIDENTS_FILE)
        total = len(analyses)
        if total == 0:
            return {
                "total_analyses": 0,
                "total_incidents": len(incidents),
                "top_root_causes": [],
                "avg_confidence": 0.0,
                "recent_analyses": [],
            }
        causes: Dict[str, int] = {}
        confidences: List[float] = []
        for a in analyses:
            rc = a.get("summary", {}).get("top_root_cause", "Unknown")
            causes[rc] = causes.get(rc, 0) + 1
            confidences.append(a.get("summary", {}).get("confidence_score", 0.0))
        top_causes = sorted(causes.items(), key=lambda x: -x[1])[:10]
        return {
            "total_analyses": total,
            "total_incidents": len(incidents),
            "top_root_causes": [{"cause": c, "count": n} for c, n in top_causes],
            "avg_confidence": round(sum(confidences) / len(confidences), 2),
            "recent_analyses": [
                {
                    "analysis_id": a["analysis_id"],
                    "problem": a.get("problem", "")[:100],
                    "root_cause": a.get("summary", {}).get("top_root_cause", ""),
                    "confidence": a.get("summary", {}).get("confidence_score", 0),
                    "timestamp": a.get("timestamp", ""),
                }
                for a in analyses[:20]
            ],
        }


root_cause_analysis = RootCauseAnalysisService()
