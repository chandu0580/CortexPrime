"""
Enterprise Analytics Routes — aggregated dashboard + advanced metrics/reports.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.services.enterprise_analytics_service import AnalyticsService

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/analytics",
    tags=["Enterprise Analytics"],
    dependencies=[Depends(require_user)],
)

analytics = AnalyticsService()


class RecordMetricRequest(BaseModel):
    metric_type: str
    name: str
    value: float
    labels: Optional[Dict[str, str]] = None
    source: str = "system"
    unit: str = "count"


class GenerateReportRequest(BaseModel):
    title: str
    report_type: str = "summary"
    metric_types: Optional[List[str]] = None
    include_trends: bool = True
    time_range: str = "7d"


# =============================================================================
# Dashboard — aggregated enterprise intelligence
# =============================================================================

@router.get("/dashboard")
async def analytics_dashboard(
    days: int = Query(7, ge=1, le=90, description="Look-back window in days"),
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    _today = date.today()

    metrics = _get_runtime_metrics()
    state = _get_runtime_state()
    agents = _list_agents()
    audit_entries = _get_audit_entries()
    pending = _get_pending_approvals()
    guardrail = _get_guardrail_snapshot()
    connector_activity = _get_connector_activity_summary()
    events = _get_recent_events()

    cost_summary = await _get_cost_summary()
    cost_daily = await _get_cost_daily(days)
    cost_providers = await _get_cost_providers()

    exec_series = _build_exec_series(audit_entries, days)

    mission_analytics = _build_mission_analytics(metrics, state, exec_series)
    connector_analytics = _build_connector_analytics(connector_activity)
    agent_analytics = _build_agent_analytics(metrics, agents, audit_entries)
    workflow_analytics = _build_workflow_analytics(state, pending, guardrail)
    executive_analytics = _build_executive_analytics(exec_series, metrics, state)
    cost_analytics = _build_cost_analytics(cost_summary, cost_daily, cost_providers)
    infra_analytics = _build_infra_analytics(metrics, agents, events, now)
    governance_analytics = _build_governance_analytics(audit_entries, pending, guardrail, metrics)

    total_execs = metrics.get("total_executions", 0)
    completed = metrics.get("completed_executions", 0)
    failed = metrics.get("failed_executions", 0)
    success_rate = (completed / max(total_execs, 1)) * 100
    _arrow = "\u2191" if success_rate > 90 else "\u2193"

    kpi_cards = [
        {
            "title": "Total Sessions",
            "value": str(total_execs),
            "change": f"\u2191 {_pct_change(total_execs, max(total_execs - 10, 1)):.1f}%",
            "isPositive": True,
            "vsText": "all time",
            "sparkline": _build_sparkline(7, total_execs),
            "color": "#38B88A",
            "icon": "sessions",
        },
        {
            "title": "Total Actions",
            "value": _fmt_num(exec_series["totals"].get("tool_calls", 0) + exec_series["totals"].get("agent_events", 0)),
            "change": f"\u2191 {_pct_change(completed, max(completed - 5, 1)):.1f}%",
            "isPositive": True,
            "vsText": f"last {days} days",
            "sparkline": _build_sparkline(7, completed + failed),
            "color": "#8B5CF6",
            "icon": "actions",
        },
        {
            "title": "Compute Time",
            "value": f"{_fmt_duration(metrics.get('total_latency_ms', 0) / 1000)}",
            "change": "N/A",
            "isPositive": True,
            "vsText": "runtime lifetime",
            "sparkline": _build_sparkline(7, completed),
            "color": "#38B88A",
            "icon": "compute",
        },
        {
            "title": "Data Processed",
            "value": f"{_fmt_tokens(metrics.get('total_tokens', 0))}",
            "change": "N/A",
            "isPositive": True,
            "vsText": "total tokens",
            "sparkline": _build_sparkline(7, metrics.get("total_tokens", 0)),
            "color": "#F59E0B",
            "icon": "data",
        },
        {
            "title": "Success Rate",
            "value": f"{success_rate:.1f}%",
            "change": f"{_arrow} {abs(success_rate - 90):.1f}%",
            "isPositive": success_rate >= 90,
            "vsText": f"({completed}/{total_execs})",
            "sparkline": _build_sparkline(7, round(success_rate)),
            "color": "#38B88A",
            "icon": "success",
        },
        {
            "title": "Errors",
            "value": str(failed),
            "change": "\u2193" if failed <= max(failed - 1, 0) else "\u2191",
            "isPositive": failed <= max(failed, 1),
            "vsText": f"{failed}/{total_execs} executions",
            "sparkline": _build_sparkline(7, failed),
            "color": "#EF4444",
            "icon": "errors",
        },
    ]

    performance_series = _build_performance_series(exec_series, completed, failed)

    return {
        "kpiCards": kpi_cards,
        "performanceSeries": performance_series,
        "topAgents": agent_analytics["topAgents"],
        "actionTypes": _build_action_types(audit_entries),
        "successRateOverTime": _build_success_rate_series(exec_series),
        "keyInsights": _build_insights(metrics, state, agent_analytics, infra_analytics),
        "activityHeatmap": _build_heatmap(audit_entries),
        "heatmapHours": _heatmap_hours(),
        "summary": _build_summary(metrics, state, agents, cost_summary, infra_analytics),
        "mission": mission_analytics,
        "connector": connector_analytics,
        "agent": agent_analytics,
        "workflow": workflow_analytics,
        "executive": executive_analytics,
        "cost": cost_analytics,
        "infrastructure": infra_analytics,
        "governance": governance_analytics,
    }


# =============================================================================
# Metrics CRUD
# =============================================================================

@router.post("/metrics")
async def record_metric(body: RecordMetricRequest):
    return await analytics.record_metric(**body.model_dump())


@router.get("/metrics")
async def get_metrics(metric_type: str = "", name: str = "", from_time: str = "", to_time: str = "", limit: int = 200):
    return {"metrics": await analytics.get_metrics(metric_type, name, from_time, to_time, limit)}


@router.get("/metrics/summary")
async def metric_summary(metric_type: str = ""):
    return await analytics.get_metric_summary(metric_type)


@router.get("/trends")
async def detect_trends(metric_type: str = "", window: int = 10):
    return {"trends": await analytics.detect_trends(metric_type, window)}


@router.post("/reports")
async def generate_report(body: GenerateReportRequest):
    return await analytics.generate_report(**body.model_dump())


@router.get("/reports")
async def list_reports(report_type: str = "", limit: int = 20):
    return {"reports": await analytics.list_reports(report_type, limit)}


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    report = await analytics.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# =============================================================================
# Data gathering helpers
# =============================================================================

def _get_runtime_metrics() -> Dict[str, Any]:
    try:
        from backend.runtime.runtime_metrics import runtime_metrics
        return runtime_metrics.export_metrics()
    except Exception:
        return {}


def _get_runtime_state() -> Dict[str, Any]:
    try:
        from backend.runtime.runtime_state import runtime_state
        return runtime_state.get_state()
    except Exception:
        return {"active_executions": {}, "execution_history": []}


def _list_agents() -> List[str]:
    try:
        from backend.runtime.agent_registry import agent_registry
        return agent_registry.list_agents()
    except Exception:
        return []


def _get_audit_entries() -> List[Dict[str, Any]]:
    try:
        from backend.safety.audit_logger import audit_logger
        return audit_logger.get_all(limit=2000)
    except Exception:
        return []


def _get_pending_approvals() -> int:
    try:
        from backend.safety.approval_queue import approval_queue
        return len(approval_queue.get_pending())
    except Exception:
        return 0


def _get_guardrail_snapshot() -> Dict[str, Any]:
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        return guardrails_engine.telemetry.snapshot(recent_n=10)
    except Exception:
        return {}


def _get_connector_activity_summary() -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    return dict(counts)


def _get_recent_events() -> List[Dict[str, Any]]:
    try:
        from backend.events.event_bus import event_bus
        if hasattr(event_bus, "_events"):
            return list(event_bus._events[-100:])
        return event_bus.get_events() if hasattr(event_bus, "get_events") else []
    except Exception:
        return []


async def _get_cost_summary() -> Dict[str, Any]:
    try:
        from backend.analytics.cost_engine import cost_engine
        return await cost_engine.executive_summary()
    except Exception:
        return {"today_spend": 0.0, "month_spend": 0.0, "top_missions": [], "by_provider": [], "daily_trend": []}


async def _get_cost_daily(days: int) -> List[Dict[str, Any]]:
    try:
        from backend.analytics.cost_engine import cost_engine
        return await cost_engine.daily_summary(days=days)
    except Exception:
        return []


async def _get_cost_providers() -> List[Dict[str, Any]]:
    try:
        from backend.analytics.cost_engine import cost_engine
        return await cost_engine.provider_breakdown(days=30)
    except Exception:
        return []


def _ts_float(val: Any) -> float:
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).replace(tzinfo=None).timestamp()
    except Exception:
        return 0.0


# =============================================================================
# Analytics builders
# =============================================================================

def _build_exec_series(audit_entries: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    now = datetime.utcnow()
    totals: Dict[str, int] = {
        "missions": 0, "agent_events": 0, "memory_ops": 0,
        "voice_sessions": 0, "governance_events": 0, "tool_calls": 0,
    }
    series = []
    for i in range(days):
        day_start = (now - timedelta(days=days - 1 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        label = day_start.strftime("%a" if days <= 14 else "%m/%d")

        day_entries = [
            e for e in audit_entries
            if _ts_float(e.get("timestamp", "")) >= day_start.timestamp()
            and _ts_float(e.get("timestamp", "")) < day_end.timestamp()
        ]

        missions_d = sum(1 for e in day_entries if "mission" in (e.get("action", "")).lower())
        agent_ev_d = sum(1 for e in day_entries if any(a in (e.get("agent", "")).lower() for a in ["planner", "research", "critic", "optimizer", "orchestrator"]))
        memory_ops_d = sum(1 for e in day_entries if "memory" in (e.get("action", "")).lower())
        voice_d = sum(1 for e in day_entries if "voice" in (e.get("action", "")).lower())
        gov_d = sum(1 for e in day_entries if e.get("outcome") in {"blocked", "rejected"})
        tools_d = sum(1 for e in day_entries if "tool" in (e.get("action", "")).lower() or "browser" in (e.get("action", "")).lower())

        series.append({
            "date": label,
            "missions": missions_d,
            "agent_events": agent_ev_d,
            "memory_ops": memory_ops_d,
            "voice_sessions": voice_d,
            "governance_events": gov_d,
            "tool_calls": tools_d,
        })
        totals["missions"] += missions_d
        totals["agent_events"] += agent_ev_d
        totals["memory_ops"] += memory_ops_d
        totals["voice_sessions"] += voice_d
        totals["governance_events"] += gov_d
        totals["tool_calls"] += tools_d
    return {"series": series, "totals": totals}


def _build_mission_analytics(metrics: Dict[str, Any], state: Dict[str, Any], exec_series: Dict[str, Any]) -> Dict[str, Any]:
    active = len(state.get("active_executions", {}))
    return {
        "activeExecutions": active,
        "completedExecutions": metrics.get("completed_executions", 0),
        "failedExecutions": metrics.get("failed_executions", 0),
        "totalExecutions": metrics.get("total_executions", 0),
        "successRate": (metrics.get("completed_executions", 0) / max(metrics.get("total_executions", 1), 1)) * 100,
        "averageLatencyMs": metrics.get("average_latency_ms", 0),
        "dailySeries": exec_series.get("series", []),
    }


def _build_connector_analytics(activity: Dict[str, int]) -> Dict[str, Any]:
    total = sum(activity.values()) if activity else 0
    return {
        "totalOperations": total,
        "byConnector": [{"name": k, "count": v} for k, v in activity.items()],
        "activeConnectors": len(activity),
    }


def _build_agent_analytics(metrics: Dict[str, Any], agents: List[str], audit_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    agent_actions: Dict[str, int] = defaultdict(int)
    for e in audit_entries:
        agent = e.get("agent", "").lower()
        if agent:
            agent_actions[agent] += 1

    top_agents = sorted(agent_actions.items(), key=lambda x: -x[1])[:5]
    max_actions = top_agents[0][1] if top_agents else 1
    colors = ["#38B88A", "#3B82F6", "#8B5CF6", "#F59E0B", "#9CA3AF"]

    agent_list = []
    for i, (name, count) in enumerate(top_agents):
        c = colors[i % len(colors)]
        pct = (count / max_actions) * 100
        change = f"\u2191 {pct:.0f}%" if pct > 50 else "\u2193 {:.0f}%".format(100 - pct)
        agent_list.append({
            "name": name.title(),
            "actions": count,
            "change": change,
            "isPositive": pct >= 50,
            "color": c,
        })

    return {
        "totalAgents": len(agents),
        "activeAgents": metrics.get("active_agent_count", 0),
        "topAgents": agent_list,
        "agentNames": agents,
    }


def _build_workflow_analytics(state: Dict[str, Any], pending: int, guardrail: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pendingApprovals": pending,
        "activeWorkflows": len(state.get("active_executions", {})),
        "completedWorkflows": len(state.get("execution_history", [])),
        "blockRate": guardrail.get("block_rate", 0) * 100,
    }


def _build_executive_analytics(exec_series: Dict[str, Any], metrics: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    s = exec_series.get("series", [])
    return {
        "dailyTrend": s,
        "totals": exec_series.get("totals", {}),
        "confidenceScore": metrics.get("average_confidence_score", 0),
        "hallucinationScore": metrics.get("average_hallucination_score", 0),
    }


def _build_cost_analytics(summary: Dict[str, Any], daily: List[Dict[str, Any]], providers: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "todaySpend": summary.get("today_spend", 0.0),
        "monthSpend": summary.get("month_spend", 0.0),
        "topMissions": summary.get("top_missions", []),
        "byProvider": providers,
        "dailyTrend": daily,
    }


def _build_infra_analytics(metrics: Dict[str, Any], agents: List[str], events: List, now: datetime) -> Dict[str, Any]:
    return {
        "activeExecutions": metrics.get("active_executions", 0),
        "activeAgents": metrics.get("active_agent_count", 0),
        "totalAgents": len(agents),
        "uptimeHours": metrics.get("runtime_started_at", ""),
        "totalTokens": metrics.get("total_tokens", 0),
        "averageLatencyMs": metrics.get("average_latency_ms", 0),
        "eventsLastHour": len([e for e in events if _ts_float(getattr(e, "timestamp", e.get("timestamp", ""))) >= (now.timestamp() - 3600)]),
    }


def _build_governance_analytics(audit_entries: List[Dict[str, Any]], pending: int, guardrail: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    blocked = sum(1 for e in audit_entries if e.get("outcome") in {"blocked", "rejected"})
    approved = sum(1 for e in audit_entries if e.get("outcome") in {"approved", "allowed"})
    total = len(audit_entries)
    return {
        "pendingApprovals": pending,
        "blockedActions": blocked,
        "approvedActions": approved,
        "totalEvents": total,
        "complianceRate": (approved / max(total, 1)) * 100,
        "blockRate": guardrail.get("block_rate", 0) * 100,
    }


# =============================================================================
# UI data builders
# =============================================================================

def _build_performance_series(exec_series: Dict[str, Any], completed: int, failed: int) -> List[Dict[str, Any]]:
    series = exec_series.get("series", [])
    if not series:
        return [
            {"date": "Day 1", "sessions": 0, "actions": 0, "successRate": 100},
            {"date": "Day 2", "sessions": 0, "actions": 0, "successRate": 100},
            {"date": "Day 3", "sessions": 0, "actions": 0, "successRate": 100},
            {"date": "Day 4", "sessions": 0, "actions": 0, "successRate": 100},
            {"date": "Day 5", "sessions": 0, "actions": 0, "successRate": 100},
            {"date": "Day 6", "sessions": 0, "actions": 0, "successRate": 100},
            {"date": "Day 7", "sessions": 0, "actions": 0, "successRate": 100},
        ]
    result = []
    for s in series:
        total = s.get("missions", 0) + s.get("agent_events", 0) + s.get("tool_calls", 0)
        sr = 100
        if s.get("governance_events", 0) > 0:
            sr = max(0, 100 - (s["governance_events"] / max(total, 1)) * 100)
        result.append({
            "date": s["date"],
            "sessions": s.get("missions", 0) + s.get("agent_events", 0),
            "actions": total,
            "successRate": round(sr, 1),
        })
    return result


def _build_action_types(audit_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    action_counts: Dict[str, int] = defaultdict(int)
    for e in audit_entries:
        a = e.get("action", "").lower()
        if "extract" in a or "fetch" in a:
            action_counts["Data Extraction"] += 1
        elif "search" in a:
            action_counts["Web Search"] += 1
        elif "file" in a:
            action_counts["File Operations"] += 1
        elif "report" in a or "generate" in a:
            action_counts["Report Generation"] += 1
        elif "analyz" in a or "analyze" in a:
            action_counts["Data Analysis"] += 1
        else:
            action_counts["Other"] += 1

    total = sum(action_counts.values()) or 1
    colors_map = {
        "Data Extraction": "#38B88A",
        "Web Search": "#3B82F6",
        "File Operations": "#8B5CF6",
        "Report Generation": "#EC4899",
        "Data Analysis": "#F59E0B",
        "Other": "#9CA3AF",
    }
    return [
        {"type": k, "actions": v, "percentage": round((v / total) * 100, 1), "color": colors_map.get(k, "#9CA3AF")}
        for k, v in sorted(action_counts.items(), key=lambda x: -x[1])
    ]


def _build_success_rate_series(exec_series: Dict[str, Any]) -> List[Dict[str, Any]]:
    series = exec_series.get("series", [])
    if not series:
        return [{"date": "Day", "rate": 100}]
    result = []
    for s in series:
        total = s.get("missions", 0) + s.get("agent_events", 0)
        gov = s.get("governance_events", 0)
        rate = 100 if total == 0 else max(0, 100 - (gov / max(total, 1)) * 100)
        result.append({"date": s["date"], "rate": round(rate, 1)})
    return result


def _build_insights(metrics: Dict[str, Any], state: Dict[str, Any], agent_analytics: Dict[str, Any], infra: Dict[str, Any]) -> List[Dict[str, Any]]:
    insights = []
    completed = metrics.get("completed_executions", 0)
    failed = metrics.get("failed_executions", 0)
    total = metrics.get("total_executions", 0) or 1

    sr = (completed / total) * 100
    if sr >= 90:
        insights.append({"type": "success", "title": "Performance Improving", "text": f"Success rate at {sr:.1f}% with {completed} completed executions."})
    else:
        insights.append({"type": "warning", "title": "Performance Needs Attention", "text": f"Success rate at {sr:.1f}%. Review failed executions ({failed} total)."})

    top = agent_analytics.get("topAgents", [])
    if top:
        insights.append({"type": "info", "title": "Most Active Agent", "text": f"\"{top[0]['name']}\" leads with {top[0]['actions']} actions."})
    else:
        insights.append({"type": "info", "title": "No Agent Activity", "text": "No agent actions recorded yet."})

    lat = metrics.get("average_latency_ms", 0)
    if lat > 5000:
        insights.append({"type": "warning", "title": "High Latency Detected", "text": f"Average latency at {lat:.0f}ms. Consider scaling."})
    else:
        insights.append({"type": "purple", "title": "Latency Healthy", "text": f"Average response time {lat:.0f}ms is within normal range."})

    gov_count = sum(1 for e in _get_audit_entries() if e.get("outcome") in {"blocked", "rejected"})
    if gov_count > 5:
        insights.append({"type": "warning", "title": "Governance Alerts", "text": f"{gov_count} actions blocked by guardrails. Review policies."})
    else:
        insights.append({"type": "success", "title": "Governance Clear", "text": "No significant governance issues detected."})

    return insights


def _build_heatmap(audit_entries: List[Dict[str, Any]]) -> List[List[int]]:
    matrix = [[0] * 12 for _ in range(7)]
    for i in range(7):
        datetime.utcnow() - timedelta(days=6 - i)

    for e in audit_entries:
        ts = e.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
            day_offset = (datetime.utcnow() - dt).days
            if 0 <= day_offset < 7:
                hour_bucket = (dt.hour // 2) % 12
                row = 6 - day_offset
                matrix[row][hour_bucket] = min(10, matrix[row][hour_bucket] + 1)
        except Exception:
            pass
    return matrix


def _heatmap_hours() -> List[str]:
    return ["12 AM", "2 AM", "4 AM", "6 AM", "8 AM", "10 AM", "12 PM", "2 PM", "4 PM", "6 PM", "8 PM", "10 PM"]


def _build_summary(
    metrics: Dict[str, Any],
    state: Dict[str, Any],
    agents: List[str],
    cost_summary: Dict[str, Any],
    infra: Dict[str, Any],
) -> List[Dict[str, Any]]:
    active = len(state.get("active_executions", {}))
    return [
        {"label": "Total Users", "value": "N/A", "change": None, "isPositive": True},
        {"label": "Active Missions", "value": str(active), "change": None, "isPositive": True},
        {"label": "Active Agents", "value": str(metrics.get("active_agent_count", 0)), "change": None, "isPositive": True},
        {"label": "Total Agents", "value": str(len(agents)), "change": None, "isPositive": True},
        {"label": "System Uptime", "value": "Running", "change": None, "isPositive": True},
        {"label": "Avg. Response Time", "value": f"{metrics.get('average_latency_ms', 0):.0f}ms", "change": None, "isPositive": True},
        {"label": "Month Spend", "value": f"${cost_summary.get('month_spend', 0):.2f}", "change": None, "isPositive": True},
    ]


# =============================================================================
# Utility helpers
# =============================================================================

def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def _build_sparkline(points: int, base: float) -> List[float]:
    return [max(0, base * (0.7 + 0.6 * (i / max(points - 1, 1)))) for i in range(points)]


def _fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _fmt_tokens(tokens: int) -> str:
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    if tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    return str(tokens)
