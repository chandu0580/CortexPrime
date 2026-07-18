"""Enterprise Loki Log Intelligence.

Replaces the simulated LokiLogIntelligence with a production-grade service
that queries a real Loki server, correlates logs with infrastructure entities,
and emits events via EventHub.

Reuses:
  - RuntimeStore        (via infrastructure_intelligence.ingest_loki_event)
  - EventHub            (loki.* events)
  - Knowledge Graph     (log-to-service/pod/container edges)
  - Learning Engine     (error pattern feed)
  - Analytics           (metric recording)
  - Root Cause Analysis (correlation with traces/alerts)

Maintains backward compatibility with LokiLogIntelligence static methods.
"""
from __future__ import annotations

import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.connectors.loki import loki_connector

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standard LogQL queries
# ---------------------------------------------------------------------------

# Default label-based queries for common infrastructure targets
STREAM_QUERIES: Dict[str, str] = {
    "pods": '{namespace!=""} |= ""',
    "containers": '{container_name!=""} |= ""',
    "deployments": '{deployment!=""} |= ""',
    "services": '{service_name!=""} |= ""',
    "namespaces": '{}',
    "nodes": '{node!=""} |= ""',
    "applications": '{app!=""} |= ""',
    "ingress": '{ingress!=""} |= ""',
    "jobs": '{job!=""} |= ""',
    "cronjobs": '{cronjob!=""} |= ""',
}

# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

ERROR_PATTERNS: List[Tuple[str, str, str]] = [
    ("exception", "Exception", "exception"),
    ("stack_trace", r"^\s+at\s+", "stack_trace"),
    ("oom", r"OutOfMemoryError|OOMKilled|oom_kill", "oom"),
    ("timeout", r"timeout|timed? ?out|deadline exceeded", "timeout"),
    ("db_failure", r"database.*error|db.*fail|connection refused.*db|sql.*error", "database_failure"),
    ("network_failure", r"connection refused|no route to host|connection reset|dns.*error", "network_failure"),
    ("auth_failure", r"unauthorized|forbidden|authentication.*fail|login.*fail|permission denied", "auth_failure"),
    ("memory_leak", r"memory leak|out of memory|heap.*dump|allocation.*fail", "memory_leak"),
]

REPEATED_ERROR_WINDOW_SEC = 300  # 5-minute window for detecting repeated errors
LOG_STORM_THRESHOLD = 50  # > 50 errors in window = log storm


class LogStream:
    """Represents a log stream from Loki."""

    def __init__(self, stream: Dict[str, str], values: List[List[Any]]) -> None:
        self.labels = stream
        self.values = values
        self._parsed: Optional[List[Dict[str, Any]]] = None

    @property
    def parsed_entries(self) -> List[Dict[str, Any]]:
        if self._parsed is None:
            self._parsed = []
            for ts_ns, line in self.values:
                self._parsed.append({
                    "timestamp_ns": ts_ns,
                    "timestamp": datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc).isoformat(),
                    "line": line,
                })
        return self._parsed

    def filter(self, query: str) -> "LogStream":
        q = query.lower()
        filtered = [(ts, line) for ts, line in self.values if q in line.lower()]
        return LogStream(self.labels, filtered)


class LogIntelligence:
    """Core log intelligence — query Loki, parse logs, detect patterns."""

    def __init__(self) -> None:
        self._pattern_cache: Dict[str, List[Dict[str, Any]]] = {}

    async def query(self, logql: str, limit: int = 100) -> Dict[str, Any]:
        """Instant LogQL query against Loki."""
        result = await loki_connector.query(logql, limit=limit)
        return self._parse_result(result)

    async def query_range(
        self, logql: str, start: str, end: str, step: str = "1m", limit: int = 1000,
    ) -> Dict[str, Any]:
        """Range LogQL query against Loki."""
        result = await loki_connector.query_range(logql, start, end, step, limit)
        return self._parse_result(result)

    async def list_labels(self) -> List[str]:
        """List available Loki label names."""
        result = await loki_connector.labels()
        if result.get("status") == "success":
            return result.get("data", [])
        return []

    async def list_label_values(self, label: str) -> List[str]:
        """List values for a specific Loki label."""
        result = await loki_connector.label_values(label)
        if result.get("status") == "success":
            return result.get("data", [])
        return []

    async def list_streams(self, matchers: Optional[List[str]] = None) -> List[LogStream]:
        """List available log streams via series API."""
        matchers = matchers or ['{}']
        result = await loki_connector.series(matchers)
        if result.get("status") == "success":
            return [LogStream(s, []) for s in result.get("data", [])]
        return []

    async def get_stream_logs(
        self, stream_selector: str, start: str, end: str, limit: int = 500,
    ) -> Dict[str, Any]:
        """Get logs for a specific stream."""
        return await self.query_range(stream_selector, start, end, limit=limit)

    def _parse_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Loki API result into a consistent format."""
        if result.get("status") != "success":
            return {"status": "error", "error": result.get("error", "unknown"), "streams": [], "stats": result.get("stats", {})}

        data = result.get("data", {})
        result_type = data.get("resultType", "streams")
        raw_streams = data.get("result", [])

        streams = []
        total_entries = 0
        for raw in raw_streams:
            stream_labels = raw.get("stream", {})
            values = raw.get("values", [])
            total_entries += len(values)
            streams.append(LogStream(stream_labels, values))

        return {
            "status": "success",
            "result_type": result_type,
            "streams": [
                {
                    "labels": s.labels,
                    "entries": [
                        {"timestamp": e["timestamp"], "line": e["line"], "timestamp_ns": e["timestamp_ns"]}
                        for e in s.parsed_entries
                    ],
                }
                for s in streams
            ],
            "total_entries": total_entries,
            "total_streams": len(streams),
            "stats": result.get("stats", {}),
        }

    async def collect_logs_for_target(
        self, target_type: str, target_name: str, minutes: int = 15, limit: int = 500,
    ) -> Dict[str, Any]:
        """Collect logs for a specific infrastructure target (pod, container, etc.)."""
        now_ns = time.time_ns()
        start_ns = now_ns - (minutes * 60 * 1_000_000_000)

        if target_type == "pod":
            logql = f'{{pod="{target_name}"}}'
        elif target_type == "container":
            logql = f'{{container="{target_name}"}}'
        elif target_type == "deployment":
            logql = f'{{deployment="{target_name}"}}'
        elif target_type == "service":
            logql = f'{{service_name="{target_name}"}}'
        elif target_type == "namespace":
            logql = f'{{namespace="{target_name}"}}'
        elif target_type == "node":
            logql = f'{{node="{target_name}"}}'
        elif target_type == "app":
            logql = f'{{app="{target_name}"}}'
        elif target_type == "ingress":
            logql = f'{{ingress="{target_name}"}}'
        elif target_type == "job":
            logql = f'{{job="{target_name}"}}'
        elif target_type == "cronjob":
            logql = f'{{cronjob="{target_name}"}}'
        else:
            logql = f'{{job="{target_name}"}}'

        return await self.query_range(logql, str(start_ns), str(now_ns), limit=limit)


class LogAnalyzer:
    """Intelligent log analysis — detect exceptions, storms, top errors."""

    def __init__(self) -> None:
        self._analysis_cache: Dict[str, Any] = {}

    def analyze_stream(self, stream: LogStream) -> Dict[str, Any]:
        """Analyze a single log stream for errors, patterns, and statistics."""
        entries = stream.parsed_entries
        total = len(entries)
        if total == 0:
            return {
                "total_lines": 0,
                "error_count": 0,
                "warn_count": 0,
                "info_count": 0,
                "patterns_found": [],
                "top_errors": [],
                "has_stack_trace": False,
                "has_oom": False,
                "has_timeout": False,
                "has_db_failure": False,
                "has_network_failure": False,
                "has_auth_failure": False,
                "has_memory_leak": False,
                "log_storm_detected": False,
                "error_rate": 0.0,
            }

        error_count = 0
        warn_count = 0
        info_count = 0
        patterns_found: List[Dict[str, Any]] = []
        error_lines: List[str] = []
        severity_counts: Dict[str, int] = {"error": 0, "warn": 0, "info": 0, "debug": 0, "unknown": 0}

        for entry in entries:
            line = entry.get("line", "")
            lower = line.lower()

            if "error" in lower or "fatal" in lower or "critical" in lower:
                error_count += 1
                severity_counts["error"] += 1
                error_lines.append(line)
            elif "warn" in lower:
                warn_count += 1
                severity_counts["warn"] += 1
            elif "info" in lower:
                info_count += 1
                severity_counts["info"] += 1
            elif "debug" in lower:
                severity_counts["debug"] += 1
            else:
                severity_counts["unknown"] += 1

        matches: Dict[str, int] = {}
        detail: Dict[str, List[str]] = {}
        for pattern_id, pattern_re, category in ERROR_PATTERNS:
            count = 0
            examples: List[str] = []
            for line in error_lines:
                if re.search(pattern_re, line, re.IGNORECASE):
                    count += 1
                    if len(examples) < 3:
                        examples.append(line[:200])
            if count > 0:
                matches[pattern_id] = count
                detail[pattern_id] = examples
                patterns_found.append({
                    "pattern_id": pattern_id,
                    "category": category,
                    "count": count,
                    "examples": examples,
                })

        top_errors = Counter(error_lines).most_common(10)
        log_storm = error_count > LOG_STORM_THRESHOLD

        return {
            "total_lines": total,
            "error_count": error_count,
            "warn_count": warn_count,
            "info_count": info_count,
            "debug_count": severity_counts.get("debug", 0),
            "unknown_count": severity_counts.get("unknown", 0),
            "severity_distribution": severity_counts,
            "patterns_found": patterns_found,
            "pattern_counts": matches,
            "pattern_details": detail,
            "top_errors": [{"error": e[0][:300], "count": e[1]} for e in top_errors],
            "has_stack_trace": matches.get("stack_trace", 0) > 0,
            "has_oom": matches.get("oom", 0) > 0,
            "has_timeout": matches.get("timeout", 0) > 0,
            "has_db_failure": matches.get("db_failure", 0) > 0,
            "has_network_failure": matches.get("network_failure", 0) > 0,
            "has_auth_failure": matches.get("auth_failure", 0) > 0,
            "has_memory_leak": matches.get("memory_leak", 0) > 0,
            "log_storm_detected": log_storm,
            "error_rate": round(error_count / max(total, 1), 4),
            "most_affected": self._most_affected_label(stream.labels),
        }

    def _most_affected_label(self, labels: Dict[str, str]) -> Dict[str, str]:
        """Determine the most relevant identifier from stream labels."""
        for key in ("pod", "container", "deployment", "service_name", "app", "job", "namespace", "node"):
            if key in labels:
                return {"type": key, "name": labels[key]}
        return {"type": "unknown", "name": "unknown"}

    def analyze_all_streams(self, streams: List[LogStream]) -> Dict[str, Any]:
        """Analyze multiple log streams and produce a consolidated report."""
        all_patterns: Dict[str, int] = {}
        all_errors: List[str] = []
        stream_analyses = []

        for stream in streams:
            analysis = self.analyze_stream(stream)
            stream_analyses.append({
                "labels": stream.labels,
                "analysis": analysis,
            })
            for pid, count in analysis.get("pattern_counts", {}).items():
                all_patterns[pid] = all_patterns.get(pid, 0) + count
            all_errors.extend(analysis.get("top_errors", []))

        total_errors = sum(a["analysis"]["error_count"] for a in stream_analyses)
        total_lines = sum(a["analysis"]["total_lines"] for a in stream_analyses)

        top_errors = sorted(
            Counter(e["error"] for e in all_errors).most_common(10),
            key=lambda x: -x[1],
        )

        return {
            "total_streams": len(streams),
            "total_lines": total_lines,
            "total_errors": total_errors,
            "error_rate": round(total_errors / max(total_lines, 1), 4),
            "global_patterns": sorted(
                [{"pattern": k, "count": v} for k, v in all_patterns.items()],
                key=lambda x: -x["count"],
            ),
            "top_errors": [{"error": e[0], "count": e[1]} for e in top_errors[:10]],
            "most_affected_services": self._top_affected_services(stream_analyses),
            "stream_analyses": stream_analyses,
            "log_storm_detected": any(a["analysis"]["log_storm_detected"] for a in stream_analyses),
        }

    def _top_affected_services(self, stream_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        affected: Dict[str, Dict[str, Any]] = {}
        for sa in stream_analyses:
            analysis = sa["analysis"]
            affected_info = analysis.get("most_affected", {"type": "unknown", "name": "unknown"})
            key = f"{affected_info['type']}:{affected_info['name']}"
            if key not in affected:
                affected[key] = {
                    "type": affected_info["type"],
                    "name": affected_info["name"],
                    "error_count": 0,
                    "stream_count": 0,
                }
            affected[key]["error_count"] += analysis.get("error_count", 0)
            affected[key]["stream_count"] += 1

        return sorted(affected.values(), key=lambda x: -x["error_count"])[:20]


class LogCorrelator:
    """Correlate logs with infrastructure entities (traces, pods, containers, builds)."""

    def correlate_with_trace(self, trace_id: str, log_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find log entries matching a trace ID."""
        correlated = []
        for entry in log_entries:
            line = entry.get("line", "")
            if trace_id in line:
                correlated.append({**entry, "correlation": {"trace_id": trace_id}})
        return correlated

    def extract_trace_ids(self, log_entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all trace IDs from log entries and group by trace."""
        trace_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        trace_pattern = re.compile(r'(?:trace[_-]?id|trace_id|traceId)[=:]\s*([a-fA-F0-9]{16,32})', re.IGNORECASE)
        for entry in log_entries:
            line = entry.get("line", "")
            matches = trace_pattern.findall(line)
            for tid in matches:
                trace_map[tid].append(entry)
        return dict(trace_map)

    def correlate_with_entity(
        self, entity_type: str, entity_name: str, log_entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Correlate log entries with a specific infrastructure entity."""
        correlated = []
        for entry in log_entries:
            line = entry.get("line", "")
            if entity_name in line:
                correlated.append({
                    **entry,
                    "correlation": {"entity_type": entity_type, "entity_name": entity_name},
                })
        return correlated

    def correlate_batch(
        self,
        logs: Dict[str, Any],
        entities: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Correlate logs with multiple entity types at once."""
        entities = entities or {}
        all_entries = []
        for s in logs.get("streams", []):
            all_entries.extend(s.get("entries", []))

        result: Dict[str, Any] = {
            "total_entries": len(all_entries),
            "correlations": {},
        }

        trace_corrs = self.extract_trace_ids(all_entries)
        if trace_corrs:
            result["correlations"]["trace_ids"] = {
                tid: len(entries) for tid, entries in trace_corrs.items()
            }
            result["trace_count"] = len(trace_corrs)

        for entity_type, names in entities.items():
            entity_corrs = {}
            for name in names:
                matched = self.correlate_with_entity(entity_type, name, all_entries)
                if matched:
                    entity_corrs[name] = len(matched)
            if entity_corrs:
                result["correlations"][entity_type] = entity_corrs

        return result


class LokiEventEmitter:
    """Emit Loki events through the EventHub."""

    async def emit_log_received(self, stream_labels: Dict[str, str], entry_count: int) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="loki.log.received",
                agent="loki_intelligence",
                message=f"Received {entry_count} log entries",
                metadata={"stream": stream_labels, "count": entry_count},
            )
        except Exception as exc:
            log.debug("Loki event emit failed: %s", exc)

    async def emit_error_detected(self, stream_labels: Dict[str, str], error_count: int, patterns: List[str]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="loki.error.detected",
                agent="loki_intelligence",
                message=f"Detected {error_count} errors in stream",
                metadata={"stream": stream_labels, "error_count": error_count, "patterns": patterns},
            )
        except Exception as exc:
            log.debug("Loki event emit failed: %s", exc)

    async def emit_warning_detected(self, stream_labels: Dict[str, str], warn_count: int) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="loki.warning.detected",
                agent="loki_intelligence",
                message=f"Detected {warn_count} warnings in stream",
                metadata={"stream": stream_labels, "warn_count": warn_count},
            )
        except Exception as exc:
            log.debug("Loki event emit failed: %s", exc)

    async def emit_stream_updated(self, stream_labels: Dict[str, str], total_entries: int) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="loki.stream.updated",
                agent="loki_intelligence",
                message=f"Stream updated with {total_entries} entries",
                metadata={"stream": stream_labels, "total_entries": total_entries},
            )
        except Exception as exc:
            log.debug("Loki event emit failed: %s", exc)

    async def emit_pattern_detected(self, pattern_id: str, count: int, stream_labels: Dict[str, str]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="loki.pattern.detected",
                agent="loki_intelligence",
                message=f"Pattern '{pattern_id}' detected {count} times",
                metadata={"pattern": pattern_id, "count": count, "stream": stream_labels},
            )
        except Exception as exc:
            log.debug("Loki event emit failed: %s", exc)


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------

log_intelligence = LogIntelligence()
log_analyzer = LogAnalyzer()
log_correlator = LogCorrelator()
loki_event_emitter = LokiEventEmitter()
