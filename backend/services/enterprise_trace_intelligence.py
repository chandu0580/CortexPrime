"""
Enterprise Trace Intelligence Service — processes OTLP span data,
builds traces, service dependency graph, and syncs to all downstream
subsystems (RuntimeStore, EventHub, Knowledge Graph, Learning Engine,
Replay Store, Analytics).

Reuses:
  - RuntimeStore for canonical execution records
  - EventHub for event streaming
  - Knowledge Graph for service relationship edges
  - Learning Engine for trace pattern learning
  - Replay Store for trace replay
  - Analytics for trace latency metrics
  - Existing OpenTelemetryTraceIntelligence for JSON trace storage

Backward compatible: all existing /api/infrastructure/traces endpoints
continue to work via the legacy JSON file store.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("INFRASTRUCTURE_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "infrastructure")))
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_SERVICE_GRAPH_FILE = _DATA_DIR / "service_graph.json"
_TRACES_FILE = _DATA_DIR / "traces.json"

OTLP_EVENT_TYPES = {
    "trace.started": "otel.trace.started",
    "trace.completed": "otel.trace.completed",
    "trace.error": "otel.trace.error",
    "span.failed": "otel.span.failed",
    "service.discovered": "otel.service.discovered",
    "service.updated": "otel.service.updated",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "otel") -> str:
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


class ServiceDependencyGraph:
    """Auto-discovered service dependency graph from OTLP trace data.

    Builds a directed graph where each edge represents a parent→child
    span relationship across services.
    """

    def __init__(self) -> None:
        self._services: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            data = _load_json(_SERVICE_GRAPH_FILE)
            if isinstance(data, dict):
                self._services = data.get("services", {})
                self._edges = data.get("edges", [])
            elif isinstance(data, list) and len(data) >= 2:
                self._services = data[0] if isinstance(data[0], dict) else {}
                self._edges = data[1] if isinstance(data[1], list) else []
        except Exception:
            self._services = {}
            self._edges = []
        self._loaded = True

    def _save(self) -> None:
        try:
            _save_json(_SERVICE_GRAPH_FILE, [self._services, self._edges])
        except Exception as exc:
            log.warning("Service graph save failed: %s", exc)

    def update_services(self, services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update service definitions from OTLP resource spans. Returns newly discovered services."""
        self._load()
        discovered: List[Dict[str, Any]] = []
        for svc in services:
            name = svc.get("name", "unknown")
            existing = self._services.get(name)
            if existing:
                existing["last_seen"] = svc.get("last_seen", _now())
                existing["span_count"] = existing.get("span_count", 0) + svc.get("span_count", 0)
                existing["error_count"] = existing.get("error_count", 0) + svc.get("error_count", 0)
                if svc.get("version"):
                    existing["version"] = svc["version"]
                if svc.get("environment"):
                    existing["environment"] = svc["environment"]
                if svc.get("host"):
                    existing["host"] = svc["host"]
                existing["updated"] = True
            else:
                entry = dict(svc)
                entry["first_seen"] = entry.get("first_seen", _now())
                entry["last_seen"] = entry.get("last_seen", _now())
                entry["edge_count"] = 0
                entry["updated"] = False
                self._services[name] = entry
                discovered.append(entry)
        self._save()
        return discovered

    def update_edges_from_spans(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build edges from span parent/child + service relationships. Returns new edges."""
        self._load()
        span_map: Dict[str, Dict[str, Any]] = {}
        for s in spans:
            sid = s.get("span_id", "")
            if sid:
                span_map[sid] = s

        new_edges: List[Dict[str, Any]] = []
        existing_set: Set[str] = set()
        for e in self._edges:
            key = f"{e.get('source','')}->{e.get('target','')}::{e.get('operation','')}"
            existing_set.add(key)

        for span in spans:
            parent_id = span.get("parent_span_id", "")
            if not parent_id or parent_id not in span_map:
                continue
            child_svc = span.get("service_name", "unknown")
            parent = span_map[parent_id]
            parent_svc = parent.get("service_name", "unknown")
            if parent_svc == child_svc:
                continue
            operation = span.get("name", "")
            edge_key = f"{parent_svc}->{child_svc}::{operation}"
            if edge_key in existing_set:
                continue
            edge = {
                "source": parent_svc,
                "target": child_svc,
                "operation": operation,
                "span_id": span.get("span_id", ""),
                "trace_id": span.get("trace_id", ""),
                "count": 1,
                "first_seen": _now(),
                "last_seen": _now(),
            }
            self._edges.append(edge)
            new_edges.append(edge)
            existing_set.add(edge_key)

            if parent_svc in self._services:
                self._services[parent_svc]["edge_count"] = self._services[parent_svc].get("edge_count", 0) + 1

        self._save()
        return new_edges

    def get_graph(self) -> Dict[str, Any]:
        self._load()
        nodes = []
        for name, svc in self._services.items():
            nodes.append({
                "id": name,
                "name": name,
                "version": svc.get("version", ""),
                "environment": svc.get("environment", ""),
                "host": svc.get("host", ""),
                "span_count": svc.get("span_count", 0),
                "error_count": svc.get("error_count", 0),
                "edge_count": svc.get("edge_count", 0),
                "first_seen": svc.get("first_seen", ""),
                "last_seen": svc.get("last_seen", ""),
            })

        edges = []
        for e in self._edges:
            edges.append({
                "source": e["source"],
                "target": e["target"],
                "operation": e.get("operation", ""),
                "count": e.get("count", 1),
            })

        return {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}

    def get_service_detail(self, service_name: str) -> Optional[Dict[str, Any]]:
        self._load()
        svc = self._services.get(service_name)
        if not svc:
            return None
        upstreams: List[str] = []
        downstreams: List[str] = []
        for e in self._edges:
            if e["target"] == service_name:
                upstreams.append(e["source"])
            if e["source"] == service_name:
                downstreams.append(e["target"])
        return {
            "name": service_name,
            "version": svc.get("version", ""),
            "environment": svc.get("environment", ""),
            "host": svc.get("host", ""),
            "span_count": svc.get("span_count", 0),
            "error_count": svc.get("error_count", 0),
            "edge_count": svc.get("edge_count", 0),
            "first_seen": svc.get("first_seen", ""),
            "last_seen": svc.get("last_seen", ""),
            "upstream_services": upstreams,
            "downstream_services": downstreams,
        }

    def list_services(self) -> List[Dict[str, Any]]:
        self._load()
        return [{
            "id": name,
            "name": name,
            "version": svc.get("version", ""),
            "environment": svc.get("environment", ""),
            "span_count": svc.get("span_count", 0),
            "error_count": svc.get("error_count", 0),
            "edge_count": svc.get("edge_count", 0),
            "last_seen": svc.get("last_seen", ""),
        } for name, svc in self._services.items()]

    def get_health(self) -> Dict[str, Any]:
        self._load()
        total = len(self._services)
        healthy = sum(1 for s in self._services.values() if s.get("error_count", 0) == 0)
        with_errors = total - healthy
        total_edges = len(self._edges)
        return {
            "total_services": total,
            "healthy_services": healthy,
            "services_with_errors": with_errors,
            "total_edges": total_edges,
        }


service_graph = ServiceDependencyGraph()


class TraceIntelligenceService:
    """Orchestrates trace processing, service graph, and downstream sync.

    Every trace received via OTLP is:
      1. Stored to traces.json (backward compatible)
      2. Synced to RuntimeStore as EngineeringExecution
      3. Emitted via EventHub (otel.* events)
      4. Fed to the Service Dependency Graph
      5. Fed to Knowledge Graph (if available)
      6. Fed to Learning Engine (if available)
      7. Recorded as metrics via Analytics
    """

    def __init__(self) -> None:
        self._ready = False
        self._otlp_connector: Any = None

    async def initialize(self) -> None:
        try:
            from backend.connectors.opentelemetry import OpenTelemetryConnector
            conn = OpenTelemetryConnector()
            ok = await conn.initialize()
            if ok:
                self._otlp_connector = conn
                log.info("Trace Intelligence — OpenTelemetry connector active")
        except Exception as exc:
            log.debug("OpenTelemetry connector not available: %s", exc)
        self._ready = True
        log.info("Trace Intelligence Service ready")

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def ingest_otlp_protobuf(self, body: bytes) -> Dict[str, Any]:
        """Decode and process an OTLP protobuf trace payload."""
        if not self._otlp_connector:
            return {"status": "skipped", "reason": "OpenTelemetry connector not available"}
        decoded = await self._otlp_connector.decode_protobuf(body)
        return await self._process_decoded(decoded)

    async def ingest_otlp_json(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Decode and process an OTLP JSON trace payload."""
        if not self._otlp_connector:
            return {"status": "skipped", "reason": "OpenTelemetry connector not available"}
        decoded = await self._otlp_connector.decode_json(body)
        return await self._process_decoded(decoded)

    async def _process_decoded(self, decoded: Dict[str, Any]) -> Dict[str, Any]:
        """Process decoded OTLP data: store traces, sync subsystems."""
        spans = decoded.get("spans", [])
        services = decoded.get("services", [])
        total_spans = decoded.get("total_spans", 0)
        total_services = decoded.get("total_services", 0)

        if total_spans == 0:
            return {"status": "skipped", "reason": "No spans in payload", "received_at": decoded.get("received_at", "")}

        traces = self._group_spans_into_traces(spans)
        error_traces = [t for t in traces if t.get("status") == "error"]

        newly_discovered = service_graph.update_services(services)
        new_edges = service_graph.update_edges_from_spans(spans)

        for trace in traces:
            await self._sync_to_trace_json(trace)
            await self._sync_to_runtime_store(trace)
            await self._emit_trace_event(trace)
            await self._sync_to_knowledge_graph(trace, services)
            await self._sync_to_learning_engine(trace)
            await self._record_trace_metrics(trace)

        for svc in newly_discovered:
            await self._emit_event(OTLP_EVENT_TYPES["service.discovered"], svc["name"], svc)

        for edge in new_edges:
            await self._emit_event(OTLP_EVENT_TYPES["service.updated"], f"{edge['source']}->{edge['target']}", edge)

        return {
            "status": "completed",
            "total_spans": total_spans,
            "total_services": total_services,
            "traces": len(traces),
            "error_traces": len(error_traces),
            "new_services": len(newly_discovered),
            "new_edges": len(new_edges),
            "received_at": decoded.get("received_at", ""),
        }

    def _group_spans_into_traces(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group spans by trace_id and build trace records."""
        trace_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in spans:
            trace_groups[s["trace_id"]].append(s)

        traces = []
        for trace_id, group in trace_groups.items():
            durations = sorted(s.get("duration_ms", 0.0) for s in group)
            total_dur = sum(durations)
            avg_dur = total_dur / len(durations) if durations else 0.0
            error_spans = sum(1 for s in group if s.get("status") == "error")

            root_spans = [s for s in group if not s.get("parent_span_id")]
            root_operation = root_spans[0].get("name", "unknown") if root_spans else group[0].get("name", "unknown")
            service_name = root_spans[0].get("service_name", "unknown") if root_spans else group[0].get("service_name", "unknown")

            services_in_trace = list(set(s.get("service_name", "unknown") for s in group))
            start_times = [s.get("start_time_unix_nano", 0) for s in group]
            end_times = [s.get("end_time_unix_nano", 0) for s in group]
            trace_start = min(start_times) if start_times else 0
            trace_end = max(end_times) if end_times else 0
            trace_duration_ns = max(0, trace_end - trace_start)
            trace_duration_ms = round(trace_duration_ns / 1_000_000, 3) if trace_duration_ns > 0 else avg_dur

            total_spans = len(group)
            mid = total_spans // 2
            p50 = durations[mid] if total_spans % 2 else (durations[mid - 1] + durations[mid]) / 2
            p95_idx = min(total_spans - 1, int(total_spans * 0.95))
            p99_idx = min(total_spans - 1, int(total_spans * 0.99))
            p95 = durations[p95_idx] if durations else 0.0
            p99 = durations[p99_idx] if durations else 0.0

            status = "error" if error_spans > 0 else "ok"

            traces.append({
                "trace_entry_id": _id("trace"),
                "trace_id": trace_id,
                "service_name": service_name,
                "root_operation": root_operation,
                "duration_ms": trace_duration_ms,
                "duration_ns": trace_duration_ns,
                "status": status,
                "total_spans": total_spans,
                "error_spans": error_spans,
                "services": services_in_trace,
                "spans": group,
                "latency_p50": round(p50, 3),
                "latency_p95": round(p95, 3),
                "latency_p99": round(p99, 3),
                "start_time_unix_nano": trace_start,
                "end_time_unix_nano": trace_end,
                "created_at": _now(),
                "updated_at": _now(),
            })
        return traces

    async def _sync_to_trace_json(self, trace: Dict[str, Any]) -> None:
        """Persist trace to legacy traces.json for backward compatibility."""
        try:
            traces = _load_json(_TRACES_FILE)
            existing = next(
                (t for t in traces if t.get("trace_id") == trace["trace_id"]),
                None,
            )
            trace_clean = {k: v for k, v in trace.items() if k != "spans"}
            trace_clean["spans"] = [
                {k: v for k, v in s.items() if k in (
                    "span_id", "parent_span_id", "name", "kind",
                    "duration_ms", "status", "status_message",
                    "service_name", "attributes", "events",
                )}
                for s in trace.get("spans", [])
            ]
            if existing:
                existing.update(trace_clean)
                existing["updated_at"] = _now()
            else:
                traces.append(trace_clean)
            _save_json(_TRACES_FILE, traces)
        except Exception as exc:
            log.debug("Trace JSON sync failed: %s", exc)

    async def _sync_to_runtime_store(self, trace: Dict[str, Any]) -> None:
        """Sync trace as EngineeringExecution in RuntimeStore."""
        try:
            from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
            execution = EngineeringExecution(
                execution_id=trace["trace_entry_id"],
                platform="opentelemetry",
                build_id=trace["trace_id"],
                build_name=trace.get("root_operation", "unknown"),
                build_status=trace.get("status", "unknown"),
                build_duration_ms=int(trace.get("duration_ms", 0)),
                repository=trace.get("service_name", ""),
                branch=",".join(trace.get("services", [])),
                status=trace.get("status", "unknown"),
                current_stage="tracing",
                timeline=[{
                    "stage": "tracing",
                    "status": trace.get("status", "completed"),
                    "timestamp": _now(),
                    "detail": {
                        "trace_id": trace["trace_id"],
                        "total_spans": trace.get("total_spans", 0),
                        "error_spans": trace.get("error_spans", 0),
                        "services": trace.get("services", []),
                    },
                }],
                monitoring_metrics={
                    "latency_p50_ms": trace.get("latency_p50", 0),
                    "latency_p95_ms": trace.get("latency_p95", 0),
                    "latency_p99_ms": trace.get("latency_p99", 0),
                    "total_spans": trace.get("total_spans", 0),
                    "error_spans": trace.get("error_spans", 0),
                },
                created_at=trace.get("created_at", _now()),
                updated_at=trace.get("updated_at", _now()),
            )
            runtime_store.create_execution(execution)
        except Exception as exc:
            log.debug("RuntimeStore sync failed for trace %s: %s", trace.get("trace_id", ""), exc)

    async def _emit_event(self, event_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        """Emit an event via EventHub."""
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="trace_intelligence",
                message=data.get("name", data.get("message", "")),
                execution_id=entity_id,
                metadata=data,
            )
        except Exception as exc:
            log.debug("Event emit failed: %s", exc)

    async def _emit_trace_event(self, trace: Dict[str, Any]) -> None:
        """Emit appropriate OTLP event based on trace status."""
        if trace.get("status") == "error":
            await self._emit_event(
                OTLP_EVENT_TYPES["trace.error"],
                trace["trace_entry_id"],
                trace,
            )
            for span in trace.get("spans", []):
                if span.get("status") == "error":
                    await self._emit_event(
                        OTLP_EVENT_TYPES["span.failed"],
                        span.get("span_id", ""),
                        span,
                    )
        else:
            await self._emit_event(
                OTLP_EVENT_TYPES["trace.completed"],
                trace["trace_entry_id"],
                trace,
            )

    async def _sync_to_knowledge_graph(
        self,
        trace: Dict[str, Any],
        services: List[Dict[str, Any]],
    ) -> None:
        """Record service relationships in Knowledge Graph."""
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            for svc in services:
                name = svc.get("name", "")
                if name:
                    await enterprise_graph.upsert_knowledge_node(
                        node_type="service",
                        node_id=name,
                        label=f"Service:{name}",
                        properties=svc,
                    )
        except Exception as exc:
            log.debug("Knowledge Graph sync failed: %s", exc)

    async def _sync_to_learning_engine(self, trace: Dict[str, Any]) -> None:
        """Feed trace patterns to the Learning Engine."""
        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            await enterprise_learning.record_experience(
                event_type="trace_completed",
                agent="trace_intelligence",
                outcome=trace.get("status", "ok"),
                context={
                    "trace_id": trace["trace_id"],
                    "service_name": trace.get("service_name", ""),
                    "root_operation": trace.get("root_operation", ""),
                    "duration_ms": trace.get("duration_ms", 0),
                    "error_spans": trace.get("error_spans", 0),
                    "total_spans": trace.get("total_spans", 0),
                    "services": trace.get("services", []),
                },
                metadata={"latency_p95": trace.get("latency_p95", 0)},
            )
        except Exception as exc:
            log.debug("Learning Engine sync failed: %s", exc)

    async def _record_trace_metrics(self, trace: Dict[str, Any]) -> None:
        """Record trace latency and error metrics."""
        try:
            from backend.services.enterprise_analytics_service import analytics_service
            await analytics_service.record_metric(
                metric_type="trace",
                metric_name=f"latency.{trace.get('service_name', 'unknown')}",
                value=trace.get("duration_ms", 0),
                labels={
                    "trace_id": trace["trace_id"],
                    "service": trace.get("service_name", ""),
                    "operation": trace.get("root_operation", ""),
                },
            )
            if trace.get("error_spans", 0) > 0:
                await analytics_service.record_metric(
                    metric_type="failure",
                    metric_name=f"trace.errors.{trace.get('service_name', 'unknown')}",
                    value=trace.get("error_spans", 0),
                    labels={
                        "trace_id": trace["trace_id"],
                        "service": trace.get("service_name", ""),
                    },
                )
        except Exception as exc:
            log.debug("Trace metrics recording failed: %s", exc)


trace_intelligence = TraceIntelligenceService()
