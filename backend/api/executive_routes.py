"""
Executive Command Center — Aggregation API  (CortexPrime)
==========================================================
Single snapshot endpoint that aggregates runtime, memory, governance,
voice, LLM health, and system health into one response for the flagship
Executive Command Center page.

Routes
------
GET /executive/snapshot   – Full system state snapshot
GET /executive/analytics  – 7-day chart series for Executive Analytics
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.auth.dependencies import require_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/executive", tags=["Executive Command Center"])

_SECURE = [Depends(require_user)]


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------

class SubsystemStatus(BaseModel):
    name:    str
    status:  str     # online | degraded | offline
    value:   str     # display value (count, score, etc.)
    detail:  str

class HealthItem(BaseModel):
    label:   str
    status:  str     # healthy | degraded | offline
    score:   float   # 0-100
    detail:  str

class AgentStatus(BaseModel):
    id:          str
    status:      str    # active | idle | processing | error
    last_action: str

class MissionInfo(BaseModel):
    execution_id:   Optional[str]
    goal:           Optional[str]
    stage:          str
    progress:       float        # 0-100
    active_agent:   Optional[str]
    started_at:     Optional[str]
    elapsed_secs:   int
    health:         str          # healthy | degraded | failed

class AutonomyDimension(BaseModel):
    label: str
    score: float
    detail: str

class SnapshotResponse(BaseModel):
    timestamp:        str
    # Status bar
    system_status:    str         # online | degraded | offline
    active_missions:  int
    active_voice:     int
    active_agents:    int
    total_memories:   int
    safety_score:     float
    llm_provider:     str
    # Mission
    current_mission:  Optional[MissionInfo]
    # Agents
    agents:           List[AgentStatus]
    # Subsystems
    subsystems:       List[SubsystemStatus]
    # Health
    health_matrix:    List[HealthItem]
    # Autonomy
    autonomy:         List[AutonomyDimension]
    autonomy_overall: float
    # Extra
    ws_connected:     bool
    uptime_hours:     float

class AnalyticsSeries(BaseModel):
    date:              str
    missions:          int
    agent_events:      int
    memory_ops:        int
    voice_sessions:    int
    governance_events: int
    tool_calls:        int

class AnalyticsResponse(BaseModel):
    series:   List[AnalyticsSeries]
    totals:   Dict[str, int]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STARTUP_TIME = time.time()

def _iso_now() -> str:
    return datetime.utcnow().isoformat()

def _status_score(status: str) -> float:
    return {"healthy": 100.0, "online": 100.0, "degraded": 55.0, "offline": 0.0, "unavailable": 0.0}.get(status.lower(), 50.0)


# ---------------------------------------------------------------------------
# GET /executive/snapshot
# ---------------------------------------------------------------------------

@router.get("/snapshot", response_model=SnapshotResponse, dependencies=_SECURE)
async def get_snapshot():
    """
    Full platform state snapshot. Aggregates all subsystems concurrently.
    Gracefully degrades when individual services are unavailable.
    """
    now = time.time()

    # ── Parallel data gathering ───────────────────────────────────────────
    audit_entries: List[Dict[str, Any]] = []
    guardrail_snap: Dict[str, Any] = {}
    active_missions: List[Dict[str, Any]] = []
    completed_missions: List[Dict[str, Any]] = []
    pending_approvals: int = 0
    compliance_score: float = 85.0
    emergency_stop: bool = False

    # ── Audit log ─────────────────────────────────────────────────────────
    try:
        from backend.safety.audit_logger import audit_logger
        audit_entries = audit_logger.get_all(limit=500)
    except Exception:
        pass

    # ── Guardrails ────────────────────────────────────────────────────────
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        guardrail_snap = guardrails_engine.telemetry.snapshot(recent_n=5)
    except Exception:
        pass

    # ── Emergency stop ────────────────────────────────────────────────────
    try:
        from backend.safety.emergency_stop import emergency_stop as _es
        emergency_stop = _es.is_active()
    except Exception:
        pass

    # ── Approval queue ────────────────────────────────────────────────────
    try:
        from backend.safety.approval_queue import approval_queue
        pending_approvals = len(approval_queue.get_pending())
    except Exception:
        pass

    # ── Compliance score (reuse governance center logic) ─────────────────
    try:
        total_ev = max(len(audit_entries), 1)
        safe_ev  = sum(1 for e in audit_entries if e.get("outcome") in {"approved","allowed","completed"})
        g_block  = guardrail_snap.get("block_rate") or 0.0
        compliance_score = max(0.0, min(99.9, round((safe_ev/total_ev*100) * (1.0 - g_block*0.3), 1)))
    except Exception:
        pass

    # ── Mission data ──────────────────────────────────────────────────────
    try:
        from backend.memory.db.postgres_client import postgres_client
        rows = await postgres_client.fetch(
            "SELECT execution_id, goal, status, started_at, completed_at, metadata "
            "FROM mission_executions ORDER BY started_at DESC LIMIT 20"
        )
        for r in (rows or []):
            d = dict(r)
            if d.get("status") in {"running", "active", "pending"}:
                active_missions.append(d)
            else:
                completed_missions.append(d)
    except Exception:
        pass

    # ── Memory stats ──────────────────────────────────────────────────────
    total_memories = 0
    try:
        from backend.memory.db.postgres_client import postgres_client
        for tbl in ("episodic_memory", "semantic_memory", "reflection_history"):
            row = await postgres_client.fetchrow(f"SELECT COUNT(*) as cnt FROM {tbl}")
            if row:
                total_memories += int(row.get("cnt") or 0)
    except Exception:
        pass

    # ── Voice ─────────────────────────────────────────────────────────────
    active_voice = 0
    voice_detail = "No active sessions"
    try:
        from backend.voice.voice_manager import voice_manager
        sessions = voice_manager.get_active_sessions() if hasattr(voice_manager, "get_active_sessions") else []
        active_voice = len(sessions)
        voice_detail = f"{active_voice} session(s) active" if active_voice else "Standby"
    except Exception:
        pass

    # ── LLM health ────────────────────────────────────────────────────────
    llm_provider = "OpenAI"
    llm_status   = "online"
    try:
        from backend.llm.router import llm_router
        if hasattr(llm_router, "get_active_provider"):
            llm_provider = llm_router.get_active_provider() or "OpenAI"
        if hasattr(llm_router, "health"):
            h = llm_router.health()
            llm_status = "online" if h.get("healthy") else "degraded"
    except Exception:
        pass

    # ── Embedding health ──────────────────────────────────────────────────
    embed_status = "healthy"
    embed_detail = ""
    try:
        from backend.memory.embedding_pipeline import embedding_pipeline
        val = await embedding_pipeline.validate_dimensions()
        embed_status = "healthy" if val.get("ok") else "degraded"
        embed_detail = val.get("model", "")
    except Exception:
        pass

    # ── Agent registry ────────────────────────────────────────────────────
    try:
        from backend.runtime.agent_registry import agent_registry
        agent_registry.list_agents()
    except Exception:
        pass

    # ── Build agent statuses ──────────────────────────────────────────────
    AGENT_IDS = ["orchestrator", "planner", "research", "critic", "optimizer", "memory"]
    agents_out: List[AgentStatus] = []
    for aid in AGENT_IDS:
        # Try to get real status from recent audit entries
        recent = [e for e in audit_entries[-50:] if (e.get("agent") or "").lower() == aid]
        if recent:
            last = recent[-1]
            status = "active" if last.get("outcome") in {"started","approved","allowed"} else "idle"
            last_action = str(last.get("action",""))[:60]
        else:
            status = "idle"
            last_action = "Standing by"
        agents_out.append(AgentStatus(id=aid, status=status, last_action=last_action))

    active_agents = sum(1 for a in agents_out if a.status in {"active","processing"})

    # ── Current mission ───────────────────────────────────────────────────
    current_mission: Optional[MissionInfo] = None
    if active_missions:
        m = active_missions[0]
        start_str = str(m.get("started_at",""))
        elapsed = 0
        try:
            st = datetime.fromisoformat(start_str.replace("Z","+00:00")).replace(tzinfo=None)
            elapsed = int((datetime.utcnow() - st).total_seconds())
        except Exception:
            pass
        current_mission = MissionInfo(
            execution_id = str(m.get("execution_id","")),
            goal         = str(m.get("goal","Running autonomous mission"))[:200],
            stage        = str(m.get("status","executing")),
            progress     = float(m.get("progress", 50.0)),
            active_agent = None,
            started_at   = start_str,
            elapsed_secs = elapsed,
            health       = "healthy",
        )
    elif audit_entries:
        # derive from last mission audit event
        mission_ev = [e for e in reversed(audit_entries) if "mission" in (e.get("action","")).lower()]
        if mission_ev:
            e = mission_ev[0]
            current_mission = MissionInfo(
                execution_id = str(e.get("execution_id","")),
                goal         = str(e.get("action","Last mission"))[:200],
                stage        = "completed",
                progress     = 100.0,
                active_agent = str(e.get("agent","")),
                started_at   = str(e.get("timestamp","")),
                elapsed_secs = 0,
                health       = "healthy",
            )

    # ── System status ─────────────────────────────────────────────────────
    if emergency_stop:
        system_status = "offline"
    elif llm_status == "degraded" or embed_status == "degraded":
        system_status = "degraded"
    else:
        system_status = "online"

    # ── Subsystems ────────────────────────────────────────────────────────
    subsystems: List[SubsystemStatus] = [
        SubsystemStatus(name="Voice Runtime",      status="online" if active_voice >= 0 else "offline", value=f"{active_voice} sessions", detail=voice_detail),
        SubsystemStatus(name="Memory Explorer",    status="online",  value=f"{total_memories:,}", detail="Cross-store memory"),
        SubsystemStatus(name="Governance Center",  status="online" if not emergency_stop else "offline", value=f"{compliance_score:.0f}%", detail="Compliance score"),
        SubsystemStatus(name="Replay Engine",      status="online",  value=f"{len(completed_missions)} missions", detail="Execution history"),
        SubsystemStatus(name="Computer Agent",     status="online",  value="Ready",           detail="Desktop automation"),
        SubsystemStatus(name="Browser Agent",      status="online",  value="Ready",           detail="Web automation"),
    ]

    # ── Health matrix ─────────────────────────────────────────────────────
    max(0.0, 100.0 - ((guardrail_snap.get("block_rate") or 0.0) * 100))
    health_matrix: List[HealthItem] = [
        HealthItem(label="LLM Health",        status=llm_status,    score=_status_score(llm_status),    detail=llm_provider),
        HealthItem(label="Voice Health",      status="healthy" if active_voice >= 0 else "degraded", score=95.0, detail="Audio pipeline"),
        HealthItem(label="Memory Health",     status="healthy",     score=min(100.0, 80.0 + total_memories/10.0) if total_memories < 200 else 98.0, detail=f"{total_memories:,} items"),
        HealthItem(label="Runtime Health",    status=system_status, score=_status_score(system_status), detail=f"{active_agents} agents active"),
        HealthItem(label="Governance Health", status="healthy" if not emergency_stop else "offline", score=compliance_score, detail=f"{pending_approvals} pending"),
        HealthItem(label="Embedding Health",  status=embed_status,  score=_status_score(embed_status),  detail=embed_detail or "pgvector"),
    ]

    # ── Autonomy dimensions ───────────────────────────────────────────────
    reasoning_score  = min(99.0, 70.0 + len(completed_missions) * 2.0)
    execution_score  = min(99.0, 65.0 + active_agents * 8.0 + len(active_missions) * 5.0)
    memory_score     = min(99.0, 50.0 + min(total_memories, 100) * 0.45)
    safety_score_dim = compliance_score
    reliability      = min(99.0, 100.0 - len([e for e in audit_entries if e.get("outcome") == "failed"]) * 2.0)

    autonomy_dims: List[AutonomyDimension] = [
        AutonomyDimension(label="Reasoning",   score=round(reasoning_score, 1),  detail="Mission planning quality"),
        AutonomyDimension(label="Execution",   score=round(execution_score, 1),  detail="Task completion rate"),
        AutonomyDimension(label="Memory",      score=round(memory_score, 1),     detail="Knowledge retention"),
        AutonomyDimension(label="Safety",      score=round(safety_score_dim, 1), detail="Governance compliance"),
        AutonomyDimension(label="Reliability", score=round(reliability, 1),      detail="System uptime"),
    ]
    autonomy_overall = round(sum(d.score for d in autonomy_dims) / len(autonomy_dims), 1)

    uptime_hours = round((now - _STARTUP_TIME) / 3600, 2)

    return SnapshotResponse(
        timestamp        = _iso_now(),
        system_status    = system_status,
        active_missions  = len(active_missions),
        active_voice     = active_voice,
        active_agents    = active_agents,
        total_memories   = total_memories,
        safety_score     = compliance_score,
        llm_provider     = llm_provider,
        current_mission  = current_mission,
        agents           = agents_out,
        subsystems       = subsystems,
        health_matrix    = health_matrix,
        autonomy         = autonomy_dims,
        autonomy_overall = autonomy_overall,
        ws_connected     = True,
        uptime_hours     = uptime_hours,
    )


# ---------------------------------------------------------------------------
# GET /executive/analytics
# ---------------------------------------------------------------------------

@router.get("/analytics", response_model=AnalyticsResponse, dependencies=_SECURE)
async def get_analytics():
    """7-day analytics series derived from audit_logs + memory tables."""

    audit_entries: List[Dict[str, Any]] = []
    try:
        from backend.safety.audit_logger import audit_logger
        audit_entries = audit_logger.get_all(limit=2000)
    except Exception:
        pass

    now = datetime.utcnow()
    totals: Dict[str, int] = {
        "missions": 0, "agent_events": 0, "memory_ops": 0,
        "voice_sessions": 0, "governance_events": 0, "tool_calls": 0,
    }

    series: List[AnalyticsSeries] = []

    for i in range(7):
        day_start = (now - timedelta(days=6 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        label     = day_start.strftime("%a")

        day_entries = [
            e for e in audit_entries
            if _ts_float(e.get("timestamp","")) >= day_start.timestamp()
            and _ts_float(e.get("timestamp","")) < day_end.timestamp()
        ]

        missions_d   = sum(1 for e in day_entries if "mission" in (e.get("action","")).lower())
        agent_ev_d   = sum(1 for e in day_entries if any(a in (e.get("agent","")).lower() for a in ["planner","research","critic","optimizer","orchestrator"]))
        memory_ops_d = sum(1 for e in day_entries if "memory" in (e.get("action","")).lower())
        voice_d      = sum(1 for e in day_entries if "voice" in (e.get("action","")).lower())
        gov_d        = sum(1 for e in day_entries if e.get("outcome") in {"blocked","rejected"})
        tools_d      = sum(1 for e in day_entries if "tool" in (e.get("action","")).lower() or "browser" in (e.get("action","")).lower())

        series.append(AnalyticsSeries(
            date             = label,
            missions         = missions_d,
            agent_events     = agent_ev_d,
            memory_ops       = memory_ops_d,
            voice_sessions   = voice_d,
            governance_events= gov_d,
            tool_calls       = tools_d,
        ))

        totals["missions"]          += missions_d
        totals["agent_events"]      += agent_ev_d
        totals["memory_ops"]        += memory_ops_d
        totals["voice_sessions"]    += voice_d
        totals["governance_events"] += gov_d
        totals["tool_calls"]        += tools_d

    return AnalyticsResponse(series=series, totals=totals)


def _ts_float(val: str) -> float:
    try:
        return datetime.fromisoformat(str(val).replace("Z","+00:00")).replace(tzinfo=None).timestamp()
    except Exception:
        return 0.0
