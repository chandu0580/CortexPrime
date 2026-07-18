"""
Enterprise Advanced Analytics — engineering velocity, quality trends, and
failure pattern analysis across builds, deployments, patches, and workspaces.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_METRICS_FILE = _DATA_DIR / "analytics_metrics.json"
_REPORTS_FILE = _DATA_DIR / "analytics_reports.json"

ANALYTICS_EVENT_METRICS_UPDATED  = "analytics.metrics_updated"
ANALYTICS_EVENT_REPORT_GENERATED = "analytics.report_generated"
ANALYTICS_EVENT_TREND_DETECTED   = "analytics.trend_detected"

METRIC_TYPES = ["build", "deploy", "patch", "workspace", "engineering", "quality"]

TREND_DIRECTIONS = ["improving", "declining", "stable"]


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.error("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


class AnalyticsService:
    """Collects engineering metrics, detects trends, and generates reports."""

    def __init__(self, event_bus=None) -> None:
        self._event_bus = event_bus

    # ── Metrics ──────────────────────────────────────────────────────────

    async def record_metric(
        self,
        metric_type: str,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        source: str = "system",
        unit: str = "count",
    ) -> Dict[str, Any]:
        records = _load_json(_METRICS_FILE)
        now = datetime.now(timezone.utc).isoformat()
        metric = {
            "id": f"m-{uuid.uuid4().hex[:12]}",
            "metric_type": metric_type,
            "name": name,
            "value": value,
            "labels": labels or {},
            "source": source,
            "unit": unit,
            "timestamp": now,
        }
        records.append(metric)
        _save_json(_METRICS_FILE, records)
        await self._emit(ANALYTICS_EVENT_METRICS_UPDATED, metric)
        return metric

    async def get_metrics(self, metric_type: str = "", name: str = "",
                           from_time: str = "", to_time: str = "",
                           limit: int = 200) -> List[Dict[str, Any]]:
        records = _load_json(_METRICS_FILE)
        if metric_type:
            records = [r for r in records if r["metric_type"] == metric_type]
        if name:
            records = [r for r in records if r["name"] == name]
        if from_time:
            records = [r for r in records if r["timestamp"] >= from_time]
        if to_time:
            records = [r for r in records if r["timestamp"] <= to_time]
        return records[-limit:]

    async def get_metric_summary(self, metric_type: str = "") -> Dict[str, Any]:
        records = await self.get_metrics(metric_type=metric_type, limit=10000)
        if not records:
            return {}
        by_name: Dict[str, List[float]] = defaultdict(list)
        for r in records:
            by_name[r["name"]].append(r["value"])
        summary = {}
        for name, values in by_name.items():
            summary[name] = {
                "count": len(values),
                "sum": round(sum(values), 2),
                "avg": round(sum(values) / len(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "latest": values[-1],
            }
        return summary

    # ── Trends ───────────────────────────────────────────────────────────

    async def detect_trends(self, metric_type: str = "", window: int = 10) -> List[Dict[str, Any]]:
        records = await self.get_metrics(metric_type=metric_type, limit=1000)
        if len(records) < window:
            return []
        by_name: Dict[str, List[Dict]] = defaultdict(list)
        for r in records:
            by_name[r["name"]].append(r)
        trends = []
        for name, data_points in by_name.items():
            if len(data_points) < window:
                continue
            recent = data_points[-window:]
            values = [d["value"] for d in recent]
            first_half = values[:window // 2]
            second_half = values[window // 2:]
            avg_first = sum(first_half) / max(len(first_half), 1)
            avg_second = sum(second_half) / max(len(second_half), 1)
            change_pct = round(((avg_second - avg_first) / max(abs(avg_first), 0.001)) * 100, 1)
            if abs(change_pct) < 5:
                direction = "stable"
            elif change_pct > 0:
                direction = "improving" if metric_type in ("quality", "patch") else "declining"
            else:
                direction = "declining" if metric_type in ("quality", "patch") else "improving"
            trends.append({
                "metric_name": name,
                "metric_type": metric_type or "all",
                "direction": direction,
                "change_pct": change_pct,
                "avg_first": round(avg_first, 2),
                "avg_second": round(avg_second, 2),
                "window": window,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })
            await self._emit(ANALYTICS_EVENT_TREND_DETECTED, trends[-1])
        return sorted(trends, key=lambda t: abs(t["change_pct"]), reverse=True)

    # ── Reports ──────────────────────────────────────────────────────────

    async def generate_report(
        self,
        title: str,
        report_type: str = "summary",
        metric_types: Optional[List[str]] = None,
        include_trends: bool = True,
        time_range: str = "7d",
    ) -> Dict[str, Any]:
        types = metric_types or METRIC_TYPES
        sections = {}
        for mt in types:
            summary = await self.get_metric_summary(metric_type=mt)
            if summary:
                sections[mt] = {"summary": summary}
                if include_trends:
                    sections[mt]["trends"] = await self.detect_trends(metric_type=mt)
        now = datetime.now(timezone.utc).isoformat()
        report = {
            "id": f"rpt-{uuid.uuid4().hex[:12]}",
            "title": title,
            "type": report_type,
            "time_range": time_range,
            "metric_types": types,
            "sections": sections,
            "generated_at": now,
            "metrics_count": sum(len(s.get("summary", {})) for s in sections.values()),
        }
        reports = _load_json(_REPORTS_FILE)
        reports.insert(0, report)
        _save_json(_REPORTS_FILE, reports)
        await self._emit(ANALYTICS_EVENT_REPORT_GENERATED, report)
        return report

    async def list_reports(self, report_type: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        reports = _load_json(_REPORTS_FILE)
        if report_type:
            reports = [r for r in reports if r.get("type") == report_type]
        return reports[:limit]

    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        for r in _load_json(_REPORTS_FILE):
            if r["id"] == report_id:
                return r
        return None

    # ── Dashboard ────────────────────────────────────────────────────────

    async def get_dashboard(self) -> Dict[str, Any]:
        metrics = _load_json(_METRICS_FILE)
        reports = _load_json(_REPORTS_FILE)
        by_type = Counter(m.get("metric_type", "unknown") for m in metrics)
        return {
            "total_metrics": len(metrics),
            "metrics_by_type": dict(by_type),
            "total_reports": len(reports),
            "recent_trends": await self.detect_trends(window=10),
            "latest_metrics": metrics[-10:] if metrics else [],
        }

    async def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._event_bus:
            try:
                from backend.events.event_models import CognitionEvent
                await self._event_bus.publish(CognitionEvent(event_type=event_type, data=payload))
            except Exception as exc:
                log.warning("Analytics event emit failed: %s", exc)
