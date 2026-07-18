"""
Governance Center API Routes  (CortexPrime)
===========================================
Read-only observability + replay endpoints for the Governance Center UI.

Routes
------
GET /governance-center/overview            – Live pipeline state + compliance summary
GET /governance-center/risk                – Risk distribution (low/med/high) by window
GET /governance-center/events              – Tool approval stream + guardrail events
GET /governance-center/compliance          – Compliance score breakdown
GET /governance-center/replay/{exec_id}    – Mission governance replay timeline
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.auth.dependencies import require_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/governance-center", tags=["Governance Center"])

_SECURE = [Depends(require_user)]

# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------

class PipelineStage(BaseModel):
    id:       str
    label:    str
    status:   str          # idle | active | approved | warned | blocked
    latency:  Optional[float]   # ms
    count:    int
    last_at:  Optional[str]


class OverviewResponse(BaseModel):
    pipeline:         List[PipelineStage]
    active_missions:  int
    blocked_today:    int
    approved_today:   int
    guardrail_hits:   int
    emergency_stop:   bool
    compliance_score: float       # 0-100


class RiskBucket(BaseModel):
    label:      str
    low:        int
    medium:     int
    high:       int
    critical:   int
    total:      int
    timestamp:  str


class RiskResponse(BaseModel):
    today:     RiskBucket
    seven_day: RiskBucket
    thirty_day: RiskBucket
    series:    List[Dict[str, Any]]   # [{date, low, medium, high, critical}] last 30 days


class GovernanceEvent(BaseModel):
    id:          str
    event_type:  str      # tool_approved | tool_blocked | memory_approved | guardrail_blocked | mission_approved
    agent:       str
    action:      str
    target:      str
    risk_level:  str
    decision:    str      # approved | blocked | warned
    reason:      str
    timestamp:   str
    risk_score:  Optional[float]
    execution_id: Optional[str]


class EventsResponse(BaseModel):
    total:    int
    events:   List[GovernanceEvent]
    guardrail_summary: Dict[str, int]   # violation_type -> count


class ComplianceCategory(BaseModel):
    label:    str
    score:    float
    trend:    float    # +/- delta vs previous period
    details:  List[str]


class ComplianceResponse(BaseModel):
    overall:   float
    grade:     str
    categories: List[ComplianceCategory]
    updated_at: str


class ReplayGovernanceEvent(BaseModel):
    sequence:     int
    stage:        str          # input_validation | tool_approval | memory_approval | execution_approval | output_validation
    agent:        str
    action:       str
    decision:     str
    risk_level:   str
    reason:       str
    offset_ms:    int
    timestamp:    str
    metadata:     Dict[str, Any]


class GovernanceReplayResponse(BaseModel):
    execution_id:  str
    total_events:  int
    duration_ms:   int
    events:        List[ReplayGovernanceEvent]
    summary:       Dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.utcnow().isoformat()


def _iso(dt: Any) -> str:
    if dt is None:
        return _iso_now()
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _risk_score_to_level(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def _compliance_grade(score: float) -> str:
    if score >= 92:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 78:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


# ---------------------------------------------------------------------------
# Safety pipeline stage builder
# ---------------------------------------------------------------------------

def _build_pipeline(
    audit_entries: List[Dict[str, Any]],
    guardrail_snap: Dict[str, Any],
    pending_approvals: int,
) -> List[PipelineStage]:
    """Build live safety pipeline stages from audit + guardrail data."""

    # Count audit events by category within last hour
    now  = time.time()
    hour = 3600

    stage_defs = [
        ("input_validation",    "Input Guardrails"),
        ("policy_engine",       "Policy Engine"),
        ("tool_approval",       "Tool Approval"),
        ("execution_approval",  "Execution Approval"),
        ("output_validation",   "Output Validation"),
        ("response_release",    "Response Release"),
    ]

    # Map audit outcomes → status colour

    # Bucket audit entries by rough category
    by_cat: Dict[str, List[Dict]] = defaultdict(list)
    for e in audit_entries:
        action = (e.get("action") or "").lower()
        (e.get("outcome") or "").lower()
        ts_str = e.get("timestamp", "")
        try:
            datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            pass

        if "input" in action or "guardrail" in action or "injection" in action or "jailbreak" in action:
            by_cat["input_validation"].append(e)
        elif "policy" in action:
            by_cat["policy_engine"].append(e)
        elif "tool" in action or "browser" in action or "computer" in action:
            by_cat["tool_approval"].append(e)
        elif "execut" in action or "mission" in action:
            by_cat["execution_approval"].append(e)
        elif "output" in action or "response" in action or "stream" in action:
            by_cat["output_validation"].append(e)
        else:
            by_cat["response_release"].append(e)

    # Guardrail-sourced input counts
    g_blocked = guardrail_snap.get("total_blocked", 0)
    g_checked = guardrail_snap.get("total_checked", 0)

    stages: List[PipelineStage] = []

    for stage_id, stage_label in stage_defs:
        entries = by_cat.get(stage_id, [])

        # Input stage gets guardrail injection
        if stage_id == "input_validation":
            count   = max(g_checked, len(entries))
            blocked = g_blocked > 0
            warned  = guardrail_snap.get("total_warned", 0) > 0
            status  = "blocked" if blocked else ("warned" if warned else ("approved" if count > 0 else "idle"))
            last_viol = guardrail_snap.get("recent_violations", [])
            last_at = _iso(datetime.fromtimestamp(last_viol[0]["timestamp"], tz=timezone.utc)) if last_viol else None
        else:
            count  = len(entries)
            [e for e in entries if abs(now - _ts(e.get("timestamp"))) < hour]
            outcomes = [e.get("outcome", "").lower() for e in entries]
            if "blocked" in outcomes or "rejected" in outcomes:
                status = "blocked"
            elif "timed_out" in outcomes or "failed" in outcomes:
                status = "warned"
            elif pending_approvals > 0 and stage_id == "tool_approval":
                status = "warned"
            elif count > 0:
                status = "approved"
            else:
                status = "idle"

            ts_vals = [_ts(e.get("timestamp")) for e in entries if e.get("timestamp")]
            last_at = _iso(datetime.fromtimestamp(max(ts_vals), tz=timezone.utc)) if ts_vals else None

        stages.append(PipelineStage(
            id      = stage_id,
            label   = stage_label,
            status  = status,
            latency = None,
            count   = count,
            last_at = last_at,
        ))

    return stages


def _ts(val: Optional[str]) -> float:
    if not val:
        return 0.0
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# GET /governance-center/overview
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=OverviewResponse, dependencies=_SECURE)
async def get_overview():
    """
    Live safety pipeline state + top-line compliance summary.
    Aggregates: audit_log + guardrails telemetry + approval queue + emergency stop.
    """
    audit_entries:     List[Dict[str, Any]] = []
    guardrail_snap:    Dict[str, Any]        = {}
    pending_approvals: int                   = 0
    emergency_active:  bool                  = False

    # ── Audit log ─────────────────────────────────────────────────────
    try:
        from backend.safety.audit_logger import audit_logger
        audit_entries = audit_logger.get_all(limit=500)
    except Exception as e:
        log.debug("audit_logger unavailable: %s", e)

    # ── Guardrails telemetry ──────────────────────────────────────────
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        guardrail_snap = guardrails_engine.telemetry.snapshot(recent_n=20)
    except Exception as e:
        log.debug("guardrails_engine unavailable: %s", e)

    # ── Approval queue ────────────────────────────────────────────────
    try:
        from backend.safety.approval_queue import approval_queue
        pending = approval_queue.get_pending()
        pending_approvals = len(pending)
    except Exception as e:
        log.debug("approval_queue unavailable: %s", e)

    # ── Emergency stop ────────────────────────────────────────────────
    try:
        from backend.safety.emergency_stop import emergency_stop
        emergency_active = emergency_stop.is_active()
    except Exception as e:
        log.debug("emergency_stop unavailable: %s", e)

    # ── Counters ──────────────────────────────────────────────────────
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    blocked_today  = sum(
        1 for e in audit_entries
        if e.get("outcome") in {"blocked", "rejected"}
        and (e.get("timestamp") or "") >= today_start
    )
    approved_today = sum(
        1 for e in audit_entries
        if e.get("outcome") in {"approved", "allowed", "completed"}
        and (e.get("timestamp") or "") >= today_start
    )
    guardrail_hits = guardrail_snap.get("total_blocked", 0) + guardrail_snap.get("total_warned", 0)

    # ── Compliance score ──────────────────────────────────────────────
    total_events = len(audit_entries) or 1
    safe_events  = sum(1 for e in audit_entries if e.get("outcome") in {"approved", "allowed", "completed"})
    raw_score    = 100.0 * safe_events / total_events
    g_block_rate = guardrail_snap.get("block_rate") or 0.0
    compliance   = max(0.0, round(raw_score * (1.0 - g_block_rate * 0.3), 1))
    compliance   = min(compliance, 99.9)

    # ── Pipeline ──────────────────────────────────────────────────────
    pipeline = _build_pipeline(audit_entries, guardrail_snap, pending_approvals)

    # ── Active missions ───────────────────────────────────────────────
    active_missions = 0
    try:
        from backend.runtime.agent_registry import agent_registry
        active_missions = len([a for a in agent_registry.get_all() if getattr(a, "status", "") == "active"])
    except Exception:
        pass

    return OverviewResponse(
        pipeline         = pipeline,
        active_missions  = active_missions,
        blocked_today    = blocked_today,
        approved_today   = approved_today,
        guardrail_hits   = guardrail_hits,
        emergency_stop   = emergency_active,
        compliance_score = compliance,
    )


# ---------------------------------------------------------------------------
# GET /governance-center/risk
# ---------------------------------------------------------------------------

@router.get("/risk", response_model=RiskResponse, dependencies=_SECURE)
async def get_risk(
    window: str = Query(default="30d", pattern="^(today|7d|30d)$"),
):
    """Risk distribution across time windows + 30-day series for charts."""

    audit_entries: List[Dict[str, Any]] = []
    try:
        from backend.safety.audit_logger import audit_logger
        audit_entries = audit_logger.get_all(limit=2000)
    except Exception as e:
        log.debug("audit_logger unavailable: %s", e)

    now        = datetime.utcnow()
    today_0    = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_7d  = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    def _bucket(entries: List[Dict]) -> RiskBucket:
        counts: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for e in entries:
            rl = (e.get("risk_level") or "low").lower()
            if rl not in counts:
                rl = "low"
            counts[rl] += 1
        total = sum(counts.values())
        return RiskBucket(
            label    = "",
            low      = counts["low"],
            medium   = counts["medium"],
            high     = counts["high"],
            critical = counts["critical"],
            total    = total,
            timestamp = _iso_now(),
        )

    def _filter(cutoff: datetime) -> List[Dict]:
        result = []
        for e in audit_entries:
            ts_str = e.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
                if ts >= cutoff:
                    result.append(e)
            except Exception:
                pass
        return result

    today_entries  = _filter(today_0)
    week_entries   = _filter(cutoff_7d)
    month_entries  = _filter(cutoff_30d)

    today_bkt  = _bucket(today_entries)
    today_bkt.label  = "Today"
    week_bkt   = _bucket(week_entries)
    week_bkt.label   = "7 Days"
    month_bkt  = _bucket(month_entries)
    month_bkt.label  = "30 Days"

    # 30-day series for Recharts
    series: List[Dict[str, Any]] = []
    for i in range(30):
        day_start = (now - timedelta(days=29 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        day_entries = [
            e for e in audit_entries
            if _ts(e.get("timestamp")) >= day_start.timestamp()
            and _ts(e.get("timestamp")) < day_end.timestamp()
        ]
        day_bkt = _bucket(day_entries)
        series.append({
            "date":     day_start.strftime("%m/%d"),
            "low":      day_bkt.low,
            "medium":   day_bkt.medium,
            "high":     day_bkt.high,
            "critical": day_bkt.critical,
            "total":    day_bkt.total,
        })

    return RiskResponse(
        today      = today_bkt,
        seven_day  = week_bkt,
        thirty_day = month_bkt,
        series     = series,
    )


# ---------------------------------------------------------------------------
# GET /governance-center/events
# ---------------------------------------------------------------------------

@router.get("/events", response_model=EventsResponse, dependencies=_SECURE)
async def get_events(
    limit:      int = Query(default=50, ge=1, le=200),
    event_type: Optional[str] = Query(default=None),
    decision:   Optional[str] = Query(default=None),
):
    """
    Unified event feed: tool approvals + guardrail violations + memory decisions.
    """
    events:     List[GovernanceEvent] = []
    audit_entries: List[Dict[str, Any]] = []
    guardrail_violations: List[Dict[str, Any]] = []

    # ── Audit log ─────────────────────────────────────────────────────
    try:
        from backend.safety.audit_logger import audit_logger
        audit_entries = audit_logger.get_all(limit=limit * 2)
    except Exception as e:
        log.debug("audit_logger unavailable: %s", e)

    # ── Guardrails recent violations ──────────────────────────────────
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        snap = guardrails_engine.telemetry.snapshot(recent_n=50)
        guardrail_violations = snap.get("recent_violations", [])
    except Exception as e:
        log.debug("guardrails_engine unavailable: %s", e)

    # Map guardrail violations → GovernanceEvent
    for i, v in enumerate(guardrail_violations):
        vtype = v.get("violation_type", "guardrail")
        events.append(GovernanceEvent(
            id          = f"g-{i}-{int(v.get('timestamp', time.time()))}",
            event_type  = "guardrail_blocked",
            agent       = "guardrails",
            action      = v.get("matched_rule", vtype),
            target      = v.get("text_preview", "")[:80],
            risk_level  = "high",
            decision    = "blocked",
            reason      = vtype.replace("_", " ").title(),
            timestamp   = _iso(datetime.fromtimestamp(v.get("timestamp", time.time()), tz=timezone.utc)),
            risk_score  = 0.9,
            execution_id = None,
        ))

    # Map audit entries → GovernanceEvent
    outcome_to_decision = {
        "approved":  "approved",
        "allowed":   "approved",
        "completed": "approved",
        "blocked":   "blocked",
        "rejected":  "blocked",
        "timed_out": "blocked",
        "failed":    "blocked",
        "started":   "approved",
    }

    for e in audit_entries:
        action   = (e.get("action") or "").lower()
        outcome  = (e.get("outcome") or "allowed").lower()
        decision_val = outcome_to_decision.get(outcome, "approved")
        rl = (e.get("risk_level") or "low").lower()

        # Classify event_type
        if "tool" in action or "browser" in action or "computer" in action:
            etype = "tool_blocked" if decision_val == "blocked" else "tool_approved"
        elif "memory" in action:
            etype = "memory_approved"
        elif "mission" in action or "execut" in action:
            etype = "mission_approved"
        else:
            etype = "policy_decision"

        events.append(GovernanceEvent(
            id           = str(e.get("audit_id", f"a-{id(e)}")),
            event_type   = etype,
            agent        = str(e.get("agent", "system")),
            action       = str(e.get("action", ""))[:120],
            target       = str(e.get("target", ""))[:120],
            risk_level   = rl,
            decision     = decision_val,
            reason       = str(e.get("reason", ""))[:256],
            timestamp    = str(e.get("timestamp", _iso_now())),
            risk_score   = None,
            execution_id = str(e.get("execution_id")) if e.get("execution_id") else None,
        ))

    # Sort by timestamp descending
    events.sort(key=lambda x: x.timestamp, reverse=True)

    # Filter
    if event_type:
        events = [ev for ev in events if ev.event_type == event_type]
    if decision:
        events = [ev for ev in events if ev.decision == decision]

    events = events[:limit]

    # Guardrail summary
    by_type: Dict[str, int] = {}
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        by_type = guardrails_engine.telemetry.snapshot(recent_n=1).get("by_violation", {})
    except Exception:
        pass

    return EventsResponse(
        total             = len(events),
        events            = events,
        guardrail_summary = by_type,
    )


# ---------------------------------------------------------------------------
# GET /governance-center/compliance
# ---------------------------------------------------------------------------

@router.get("/compliance", response_model=ComplianceResponse, dependencies=_SECURE)
async def get_compliance():
    """
    Compliance score breakdown: Safety, Policy, Governance health.
    """
    audit_entries: List[Dict[str, Any]] = []
    guardrail_snap: Dict[str, Any] = {}

    try:
        from backend.safety.audit_logger import audit_logger
        audit_entries = audit_logger.get_all(limit=1000)
    except Exception:
        pass

    try:
        from backend.safety.guardrails_engine import guardrails_engine
        guardrail_snap = guardrails_engine.telemetry.snapshot(recent_n=5)
    except Exception:
        pass

    total = max(len(audit_entries), 1)

    # Safety score — based on guardrail block rate + audit safe ratio
    g_block_rate = guardrail_snap.get("block_rate") or 0.0
    safe_ratio   = sum(1 for e in audit_entries if e.get("outcome") in {"approved", "allowed", "completed"}) / total
    safety_score = round(max(0.0, (safe_ratio * 100) - (g_block_rate * 30)), 1)

    # Policy score — based on how many went through approval vs bypassed
    approved_count = sum(1 for e in audit_entries if e.get("outcome") == "approved")
    high_risk      = sum(1 for e in audit_entries if (e.get("risk_level") or "").lower() in {"high", "critical"})
    policy_score   = round(min(99.5, 75.0 + (approved_count / total) * 25.0), 1) if total > 1 else 85.0

    # Governance score — approval queue responsiveness + no timed_out
    timed_out  = sum(1 for e in audit_entries if e.get("outcome") == "timed_out")
    gov_score  = round(max(50.0, 100.0 - (timed_out / total * 100) - (high_risk / total * 20)), 1)

    overall = round((safety_score + policy_score + gov_score) / 3, 1)

    # Compute simple trend (last 100 vs first 100 of dataset)
    def _trend(current: float) -> float:
        # Stable baseline for now
        return round((current - 85.0) / 10.0, 2)

    categories = [
        ComplianceCategory(
            label   = "Safety Score",
            score   = safety_score,
            trend   = _trend(safety_score),
            details = [
                f"{guardrail_snap.get('total_blocked', 0)} inputs blocked by guardrails",
                f"{guardrail_snap.get('total_warned', 0)} warnings issued",
                f"Block rate: {round(g_block_rate * 100, 2)}%",
            ],
        ),
        ComplianceCategory(
            label   = "Policy Score",
            score   = policy_score,
            trend   = _trend(policy_score),
            details = [
                f"{approved_count} actions approved through policy engine",
                f"{high_risk} high/critical risk events",
                f"Approval ratio: {round(approved_count / total * 100, 1)}%",
            ],
        ),
        ComplianceCategory(
            label   = "Governance Score",
            score   = gov_score,
            trend   = _trend(gov_score),
            details = [
                f"{timed_out} approvals timed out",
                f"{total} total governance events",
                f"High-risk event rate: {round(high_risk / total * 100, 1)}%",
            ],
        ),
    ]

    return ComplianceResponse(
        overall    = overall,
        grade      = _compliance_grade(overall),
        categories = categories,
        updated_at = _iso_now(),
    )


# ---------------------------------------------------------------------------
# GET /governance-center/replay/{execution_id}
# ---------------------------------------------------------------------------

@router.get("/replay/{execution_id}", response_model=GovernanceReplayResponse, dependencies=_SECURE)
async def get_governance_replay(execution_id: str):
    """
    Governance-filtered replay for a specific mission execution.
    Extracts governance decision points: input validation, tool approval,
    memory access, execution approval, output validation.
    """
    raw_events: List[Dict[str, Any]] = []

    # Pull from replay store (Redis hot + Postgres cold)
    try:
        from backend.services.mission_replay_store import replay_store
        raw_events = await replay_store.get_events(execution_id)
    except Exception as e:
        log.debug("replay_store unavailable: %s", e)

    # Also pull from audit log filtered by execution_id
    audit_events: List[Dict[str, Any]] = []
    try:
        from backend.safety.audit_logger import audit_logger
        audit_events = audit_logger.get_by_execution(execution_id)
    except Exception as e:
        log.debug("audit_logger unavailable: %s", e)

    gov_events: List[ReplayGovernanceEvent] = []
    base_ts: Optional[float] = None

    GOVERNANCE_EVENT_TYPES = {
        "mission_started", "mission_completed", "mission_failed",
        "tool_called", "tool_completed", "tool_failed",
        "memory_retrieved", "memory_stored",
        "agent_started", "agent_completed",
        "execution_started", "execution_completed",
        "response_generated",
    }

    # Build stage mapping from raw replay events
    for seq, ev in enumerate(raw_events):
        etype = str(ev.get("event_type") or ev.get("type") or "")
        if etype not in GOVERNANCE_EVENT_TYPES:
            continue

        ts_str = str(ev.get("event_ts") or ev.get("timestamp") or "")
        ts     = _ts(ts_str)
        if base_ts is None and ts > 0:
            base_ts = ts

        offset_ms = int((ts - (base_ts or ts)) * 1000) if ts > 0 else seq * 100

        # Map event type → governance stage
        if "mission" in etype and "start" in etype:
            stage = "input_validation"
        elif "tool" in etype:
            stage = "tool_approval"
        elif "memory" in etype:
            stage = "memory_approval"
        elif "execut" in etype:
            stage = "execution_approval"
        elif "response" in etype:
            stage = "output_validation"
        elif "agent" in etype and "complet" in etype:
            stage = "output_validation"
        else:
            stage = "execution_approval"

        # Determine decision from status
        status = str(ev.get("status") or "completed").lower()
        if status in {"failed", "blocked", "rejected"}:
            decision   = "blocked"
            risk_level = "high"
        elif status in {"warning", "warned"}:
            decision   = "warned"
            risk_level = "medium"
        else:
            decision   = "approved"
            risk_level = "low"

        payload = ev.get("payload") or {}
        if isinstance(payload, str):
            try:
                import json
                payload = json.loads(payload)
            except Exception:
                payload = {"raw": payload}

        gov_events.append(ReplayGovernanceEvent(
            sequence     = seq,
            stage        = stage,
            agent        = str(ev.get("agent") or "system"),
            action       = str(ev.get("message") or etype)[:200],
            decision     = decision,
            risk_level   = risk_level,
            reason       = str(payload.get("reason") or decision),
            offset_ms    = offset_ms,
            timestamp    = ts_str or _iso_now(),
            metadata     = payload if isinstance(payload, dict) else {},
        ))

    # Merge in audit trail events for this execution
    for i, ae in enumerate(audit_events):
        action_str = str(ae.get("action") or "audit_event")
        outcome    = str(ae.get("outcome") or "allowed").lower()
        decision   = "approved" if outcome in {"approved", "allowed", "completed"} else "blocked"
        rl         = str(ae.get("risk_level") or "low").lower()
        ts_str     = str(ae.get("timestamp") or _iso_now())
        ts         = _ts(ts_str)
        offset_ms  = int((ts - (base_ts or ts)) * 1000) if ts > 0 and base_ts else len(gov_events) * 100

        # Classify by action
        if "tool" in action_str.lower() or "browser" in action_str.lower():
            stage = "tool_approval"
        elif "memory" in action_str.lower():
            stage = "memory_approval"
        else:
            stage = "execution_approval"

        gov_events.append(ReplayGovernanceEvent(
            sequence     = len(gov_events),
            stage        = stage,
            agent        = str(ae.get("agent") or "audit"),
            action       = action_str[:200],
            decision     = decision,
            risk_level   = rl,
            reason       = str(ae.get("reason") or "")[:200],
            offset_ms    = offset_ms,
            timestamp    = ts_str,
            metadata     = {},
        ))

    # Re-sort by offset_ms
    gov_events.sort(key=lambda x: x.offset_ms)
    for i, ev in enumerate(gov_events):
        ev.sequence = i

    # Summary
    duration_ms = gov_events[-1].offset_ms if gov_events else 0
    summary = {
        "total":      len(gov_events),
        "approved":   sum(1 for e in gov_events if e.decision == "approved"),
        "blocked":    sum(1 for e in gov_events if e.decision == "blocked"),
        "warned":     sum(1 for e in gov_events if e.decision == "warned"),
        "by_stage":   {
            s: sum(1 for e in gov_events if e.stage == s)
            for s in {"input_validation","tool_approval","memory_approval","execution_approval","output_validation"}
        },
    }

    return GovernanceReplayResponse(
        execution_id = execution_id,
        total_events = len(gov_events),
        duration_ms  = duration_ms,
        events       = gov_events,
        summary      = summary,
    )
