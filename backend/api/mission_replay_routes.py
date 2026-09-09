"""
Mission Replay API Routes
=========================

GET  /mission-replay/{execution_id}           — full replay data + summary
GET  /mission-replay/{execution_id}/timeline  — ordered timeline with offset_ms
GET  /mission-replay/{execution_id}/graph     — per-step agent-state graph
GET  /mission-replay/                         — list recent replay sessions
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.services.mission_replay_store import replay_store

log = logging.getLogger(__name__)
router = APIRouter(prefix="/mission-replay", tags=["mission-replay"])


# ============================================================
# RESPONSE MODELS
# ============================================================

class ReplayEventSchema(BaseModel):
    event_id:       Optional[str]
    execution_id:   str
    sequence:       int
    event_type:     str
    original_type:  Optional[str]
    agent:          str
    status:         str
    message:        str
    timestamp:      Optional[str]
    offset_ms:      Optional[float]
    latency_ms:     Optional[float]
    phase:          Optional[str]
    confidence_score: Optional[float]
    token_usage:    Optional[Dict[str, Any]]
    payload:        Dict[str, Any]

    class Config:
        extra = "allow"


class ReplaySummarySchema(BaseModel):
    execution_id:   str
    found:          bool
    total_events:   Optional[int]
    event_counts:   Optional[Dict[str, int]]
    agents:         Optional[List[str]]
    first_ts:       Optional[str]
    last_ts:        Optional[str]
    duration_ms:    Optional[float]
    avg_latency_ms: Optional[float]
    is_complete:    Optional[bool]


class ReplayFullSchema(BaseModel):
    summary: ReplaySummarySchema
    events:  List[ReplayEventSchema]


class GraphStepSchema(BaseModel):
    sequence:     int
    event_type:   str
    agent:        str
    message:      str
    timestamp:    Optional[str]
    agent_states: Dict[str, str]


class ReplayGraphSchema(BaseModel):
    execution_id:  str
    total_steps:   int
    steps:         List[GraphStepSchema]
    final_states:  Dict[str, str]


# ============================================================
# GET /mission-replay/{execution_id}
# Returns full replay (summary + all events)
# ============================================================

@router.get("/{execution_id}", response_model=ReplayFullSchema)
async def get_replay(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> ReplayFullSchema:
    """Return complete replay data for a mission execution."""
    summary_raw = await replay_store.get_summary(execution_id)
    if not summary_raw.get("found"):
        raise HTTPException(status_code=404, detail=f"No replay data for execution '{execution_id}'")

    events_raw = await replay_store.get_timeline(execution_id)  # includes offset_ms

    return ReplayFullSchema(
        summary=ReplaySummarySchema(**summary_raw),
        events=[
            ReplayEventSchema(
                event_id       = e.get("event_id"),
                execution_id   = e.get("execution_id", execution_id),
                sequence       = e.get("sequence", 0),
                event_type     = e.get("event_type", ""),
                original_type  = e.get("original_type"),
                agent          = e.get("agent", ""),
                status         = e.get("status", "info"),
                message        = e.get("message", ""),
                timestamp      = e.get("timestamp"),
                offset_ms      = e.get("offset_ms"),
                latency_ms     = e.get("latency_ms"),
                phase          = e.get("phase"),
                confidence_score = e.get("confidence_score"),
                token_usage    = e.get("token_usage"),
                payload        = e.get("payload") or {},
            )
            for e in events_raw
        ],
    )


# ============================================================
# GET /mission-replay/{execution_id}/timeline
# Lightweight timeline — only what the UI timeline panel needs
# ============================================================

@router.get("/{execution_id}/timeline")
async def get_timeline(
    execution_id:  str,
    agent:         Optional[str] = Query(default=None, description="Filter by agent name"),
    event_type:    Optional[str] = Query(default=None, description="Filter by event_type"),
    current_user:  dict          = Depends(require_user),
) -> Dict[str, Any]:
    """Return the ordered timeline for a mission execution."""
    events = await replay_store.get_timeline(execution_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"No timeline data for execution '{execution_id}'")

    # Apply optional filters
    if agent:
        events = [e for e in events if e.get("agent") == agent]
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type or e.get("original_type") == event_type]

    return {
        "execution_id": execution_id,
        "count":        len(events),
        "events":       events,
    }


# ============================================================
# GET /mission-replay/{execution_id}/graph
# Per-step agent-state snapshots for AgentGraph animation
# ============================================================

@router.get("/{execution_id}/graph", response_model=ReplayGraphSchema)
async def get_graph(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> ReplayGraphSchema:
    """Return per-step agent-state graph for replay animation."""
    graph = await replay_store.get_graph(execution_id)
    if not graph.get("steps"):
        raise HTTPException(status_code=404, detail=f"No graph data for execution '{execution_id}'")

    return ReplayGraphSchema(
        execution_id = graph["execution_id"],
        total_steps  = graph["total_steps"],
        steps=[
            GraphStepSchema(
                sequence     = s["sequence"],
                event_type   = s["event_type"],
                agent        = s["agent"],
                message      = s["message"],
                timestamp    = s["timestamp"],
                agent_states = s["agent_states"],
            )
            for s in graph["steps"]
        ],
        final_states = graph["final_states"],
    )


# ============================================================
# GET /mission-replay/
# List recent execution IDs that have replay data
# ============================================================

@router.get("/")
async def list_replays(
    limit:        int  = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """
    List recent execution IDs that have replay data stored in Redis.
    Falls back to PostgreSQL for historical data.
    """
    try:
        from backend.infrastructure.redis.connection import redis_connection
        client = redis_connection.client
        if client:
            keys = await client.keys("cx:replay:events:*")
            exec_ids = [k.replace("cx:replay:events:", "") for k in (keys or [])]
            exec_ids = exec_ids[:limit]
            if not exec_ids:
                # Phase 10.26 (ADR-118): Redis only holds the 72 h hot window.
                # An empty window is not "no replays" -- consult the durable
                # store the way an unavailable Redis already does.
                raise RuntimeError("Redis holds no replay keys")
        else:
            raise RuntimeError("Redis unavailable")
    except Exception:
        # PostgreSQL fallback
        try:
            from sqlalchemy import distinct, select

            from backend.database.engine import AsyncSessionLocal
            from backend.database.models.mission_replay import MissionReplayEvent

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(distinct(MissionReplayEvent.execution_id))
                    .order_by(MissionReplayEvent.execution_id.desc())
                    .limit(limit)
                )
                exec_ids = [row[0] for row in result.fetchall()]
        except Exception as exc:
            log.warning("list_replays DB fallback failed: %s", exc)
            exec_ids = []

    return {"executions": exec_ids, "count": len(exec_ids)}
