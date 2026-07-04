"""
Enterprise Replay API Routes
=============================

Reuses:
  - mission_replay_store for mission event replay
  - event_bus for event history
  - runtime_metrics for runtime metrics
  - cost_engine for cost data
  - cognition_graph for knowledge graph replay
  - memory_orchestrator for memory replay
  - worker systems for worker replay
  - connector systems for connector replay
  - governance systems for governance/approval replay

GET  /api/enterprise-replay/mission/{execution_id}
GET  /api/enterprise-replay/workers/{execution_id}
GET  /api/enterprise-replay/connectors/{execution_id}
GET  /api/enterprise-replay/decisions/{execution_id}
GET  /api/enterprise-replay/memory/{execution_id}
GET  /api/enterprise-replay/knowledge-graph/{execution_id}
GET  /api/enterprise-replay/costs/{execution_id}
GET  /api/enterprise-replay/events/{execution_id}
GET  /api/enterprise-replay/timeline/{execution_id}
GET  /api/enterprise-replay/execution-graph/{execution_id}
GET  /api/enterprise-replay/export/{execution_id}?format=json|markdown|timeline|replay-package
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.services.mission_replay_store import replay_store

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enterprise-replay", tags=["enterprise-replay"])


# ============================================================
# RESPONSE SCHEMAS
# ============================================================

class WorkerActionSchema(BaseModel):
    action_id: str
    worker_type: str  # browser | voice | desktop
    action_type: str
    action: str
    input: Optional[str]
    output: Optional[str]
    status: str
    timestamp: Optional[str]
    offset_ms: Optional[float]
    duration_ms: Optional[float]
    error: Optional[str]
    metadata: Dict[str, Any]

class WorkerReplaySchema(BaseModel):
    execution_id: str
    total_actions: int
    workers: Dict[str, List[WorkerActionSchema]]
    summary: Dict[str, Any]

class ConnectorCallSchema(BaseModel):
    connector_type: str
    endpoint: str
    method: str
    request: Optional[Dict[str, Any]]
    response: Optional[Dict[str, Any]]
    status: str
    timestamp: Optional[str]
    offset_ms: Optional[float]
    latency_ms: Optional[float]
    error: Optional[str]
    retry_count: int

class ConnectorReplaySchema(BaseModel):
    execution_id: str
    total_calls: int
    connectors: Dict[str, List[ConnectorCallSchema]]
    summary: Dict[str, Any]

class LLMRequestSchema(BaseModel):
    request_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt: Optional[str]
    response: Optional[str]
    timestamp: Optional[str]
    offset_ms: Optional[float]
    latency_ms: Optional[float]
    confidence_score: Optional[float]
    cost: Optional[float]

class DecisionSchema(BaseModel):
    decision_id: str
    step: str
    agent: str
    reasoning: Optional[str]
    llm_requests: List[LLMRequestSchema]
    confidence_score: Optional[float]
    validation_result: Optional[str]
    governance_action: Optional[str]
    timestamp: Optional[str]
    offset_ms: Optional[float]

class DecisionExplorerSchema(BaseModel):
    execution_id: str
    total_decisions: int
    chain: List[DecisionSchema]
    summary: Dict[str, Any]

class MemoryReplayEntrySchema(BaseModel):
    memory_id: str
    memory_type: str  # working | semantic | episodic
    content: str
    agent: str
    operation: str  # create | update | retrieve
    timestamp: Optional[str]
    offset_ms: Optional[float]
    relevance_score: Optional[float]
    metadata: Dict[str, Any]

class MemoryReplaySchema(BaseModel):
    execution_id: str
    total_entries: int
    working_memory: List[MemoryReplayEntrySchema]
    semantic_memory: List[MemoryReplayEntrySchema]
    episodic_memory: List[MemoryReplayEntrySchema]
    changes_over_time: List[Dict[str, Any]]
    summary: Dict[str, Any]

class GraphEntitySchema(BaseModel):
    entity_id: str
    entity_type: str
    entity_name: str
    operation: str  # create | update | relate
    properties: Dict[str, Any]
    timestamp: Optional[str]
    offset_ms: Optional[float]

class GraphRelationshipSchema(BaseModel):
    relationship_id: str
    source: str
    target: str
    relationship_type: str
    operation: str
    timestamp: Optional[str]
    offset_ms: Optional[float]

class KnowledgeGraphReplaySchema(BaseModel):
    execution_id: str
    total_entities: int
    total_relationships: int
    entities: List[GraphEntitySchema]
    relationships: List[GraphRelationshipSchema]
    evolution: List[Dict[str, Any]]
    summary: Dict[str, Any]

class CostEntrySchema(BaseModel):
    cost_id: str
    category: str  # llm | worker | mission | connector
    provider: Optional[str]
    model: Optional[str]
    tokens: Optional[int]
    cost: float
    timestamp: Optional[str]
    date: Optional[str]
    metadata: Dict[str, Any]

class CostReplaySchema(BaseModel):
    execution_id: str
    total_cost: float
    entries: List[CostEntrySchema]
    by_category: Dict[str, float]
    by_day: Dict[str, float]
    summary: Dict[str, Any]

class TimelineEntrySchema(BaseModel):
    sequence: int
    event_type: str
    agent: str
    message: str
    timestamp: Optional[str]
    offset_ms: Optional[float]
    category: str
    metadata: Dict[str, Any]

class TimelineExplorerSchema(BaseModel):
    execution_id: str
    total_events: int
    events: List[TimelineEntrySchema]
    zoom_levels: List[str]
    summary: Dict[str, Any]

class ExecutionGraphNodeSchema(BaseModel):
    id: str
    type: str  # mission | worker | connector | memory | knowledge_graph | approval | completion
    label: str
    status: str
    duration_ms: Optional[float]
    metadata: Dict[str, Any]

class ExecutionGraphEdgeSchema(BaseModel):
    source: str
    target: str
    label: str
    type: str

class ExecutionGraphSchema(BaseModel):
    execution_id: str
    nodes: List[ExecutionGraphNodeSchema]
    edges: List[ExecutionGraphEdgeSchema]
    summary: Dict[str, Any]

class EventExplorerEntrySchema(BaseModel):
    event_id: str
    category: str
    event_type: str
    source: str
    agent: Optional[str]
    message: Optional[str]
    data: Dict[str, Any]
    timestamp: Optional[str]
    offset_ms: Optional[float]
    channel: Optional[str]

class EventExplorerSchema(BaseModel):
    execution_id: str
    total_events: int
    events: List[EventExplorerEntrySchema]
    by_category: Dict[str, int]
    by_source: Dict[str, int]
    summary: Dict[str, Any]


# ============================================================
# HELPERS
# ============================================================

def _get_execution_events(execution_id: str) -> List[Dict[str, Any]]:
    """Get events for an execution from the replay store."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return []
        return loop.run_until_complete(replay_store.get_timeline(execution_id))
    except:
        return []


# ============================================================
# GET /api/enterprise-replay/mission/{execution_id}
# ============================================================

@router.get("/mission/{execution_id}")
async def get_mission_replay(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Full mission replay with timeline, stages, duration, status, metrics, cost, outcome."""
    summary = await replay_store.get_summary(execution_id)
    events = await replay_store.get_timeline(execution_id)

    stages = [e for e in events if e.get("phase")]
    stage_names = list(dict.fromkeys(e.get("phase", "") for e in stages if e.get("phase")))

    metrics = {
        "total_events": len(events),
        "duration_ms": summary.get("duration_ms"),
        "avg_latency_ms": summary.get("avg_latency_ms"),
        "event_counts": summary.get("event_counts"),
        "agents": summary.get("agents", []),
    }

    cost_data = {}
    try:
        from backend.analytics.cost_engine import cost_engine
        cost_data = cost_engine.mission_summary(execution_id)
    except Exception:
        cost_data = {"total_cost": 0, "entries": []}

    return {
        "execution_id": execution_id,
        "found": summary.get("found", False),
        "status": "completed" if summary.get("is_complete") else "in_progress",
        "stages": stage_names,
        "stage_events": stages,
        "events": events,
        "metrics": metrics,
        "cost": cost_data,
        "outcome": {
            "is_complete": summary.get("is_complete", False),
            "total_events": summary.get("total_events", 0),
            "agents": summary.get("agents", []),
        },
    }


# ============================================================
# GET /api/enterprise-replay/workers/{execution_id}
# ============================================================

@router.get("/workers/{execution_id}")
async def get_worker_replay(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Worker replay — browser, voice, desktop actions."""
    events = await replay_store.get_timeline(execution_id)

    worker_actions: Dict[str, List[Dict]] = {
        "browser": [],
        "voice": [],
        "desktop": [],
    }

    worker_summary: Dict[str, Any] = {
        "total_browser": 0,
        "total_voice": 0,
        "total_desktop": 0,
        "total_actions": 0,
        "duration_ms": 0,
    }

    for e in events:
        agent_lower = (e.get("agent") or "").lower()
        event_type = (e.get("event_type") or "").lower()
        worker_type = None

        if "browser" in agent_lower or "browser" in event_type:
            worker_type = "browser"
        elif "voice" in agent_lower or "voice" in event_type:
            worker_type = "voice"
        elif "desktop" in agent_lower or "computer" in agent_lower or "desktop" in event_type:
            worker_type = "desktop"

        if worker_type:
            action = {
                "action_id": e.get("event_id") or f"act-{e.get('sequence', 0)}",
                "worker_type": worker_type,
                "action_type": event_type,
                "action": e.get("message", ""),
                "input": (e.get("payload") or {}).get("input"),
                "output": (e.get("payload") or {}).get("output"),
                "status": e.get("status", "info"),
                "timestamp": e.get("timestamp"),
                "offset_ms": e.get("offset_ms"),
                "duration_ms": e.get("latency_ms"),
                "error": (e.get("payload") or {}).get("error"),
                "metadata": e.get("payload") or {},
            }
            worker_actions[worker_type].append(action)
            worker_summary[f"total_{worker_type}"] += 1
            worker_summary["total_actions"] += 1

    if worker_summary["total_actions"] > 0:
        offsets = [a["offset_ms"] for a in sum(worker_actions.values(), []) if a["offset_ms"]]
        if offsets:
            worker_summary["duration_ms"] = max(offsets) - min(offsets)

    return {
        "execution_id": execution_id,
        "total_actions": worker_summary["total_actions"],
        "workers": worker_actions,
        "summary": worker_summary,
        "runtime_state": {
            "mission_runtime": "reused",
            "worker_runtime": "reused",
            "reasoning_runtime": "reused",
        },
    }


# ============================================================
# GET /api/enterprise-replay/connectors/{execution_id}
# ============================================================

@router.get("/connectors/{execution_id}")
async def get_connector_replay(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Connector replay — all external service interactions."""
    events = await replay_store.get_timeline(execution_id)

    connector_calls: Dict[str, List[Dict]] = {}
    connector_names = ["github", "jira", "slack", "teams", "servicenow", "confluence", "notion", "azure_devops", "azure"]

    summary: Dict[str, Any] = {
        "total_calls": 0,
        "total_latency_ms": 0,
        "total_failures": 0,
        "total_retries": 0,
        "by_connector": {},
    }

    for e in events:
        agent_lower = (e.get("agent") or "").lower()
        event_type = (e.get("event_type") or "").lower()
        message_lower = (e.get("message") or "").lower()
        payload = e.get("payload") or {}

        matched_connector = None
        for cn in connector_names:
            cn_key = cn.replace("_devops", " devops")
            if cn in agent_lower or cn in event_type or cn in message_lower or cn_key in message_lower:
                matched_connector = cn
                break

        if matched_connector:
            if matched_connector not in connector_calls:
                connector_calls[matched_connector] = []

            call = {
                "connector_type": matched_connector,
                "endpoint": (payload.get("endpoint") or payload.get("url") or f"{matched_connector}://api"),
                "method": payload.get("method", "GET"),
                "request": payload.get("request") or payload.get("input"),
                "response": payload.get("response") or payload.get("output"),
                "status": "success" if "failed" not in event_type else "error",
                "timestamp": e.get("timestamp"),
                "offset_ms": e.get("offset_ms"),
                "latency_ms": e.get("latency_ms"),
                "error": payload.get("error"),
                "retry_count": payload.get("retry_count", 0),
            }
            connector_calls[matched_connector].append(call)
            summary["total_calls"] += 1
            if call["latency_ms"]:
                summary["total_latency_ms"] += call["latency_ms"]
            if call["status"] == "error":
                summary["total_failures"] += 1
            summary["total_retries"] += call["retry_count"]
            summary["by_connector"][matched_connector] = summary["by_connector"].get(matched_connector, 0) + 1

    return {
        "execution_id": execution_id,
        "total_calls": summary["total_calls"],
        "connectors": connector_calls,
        "summary": summary,
    }


# ============================================================
# GET /api/enterprise-replay/decisions/{execution_id}
# ============================================================

@router.get("/decisions/{execution_id}")
async def get_decision_explorer(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Decision explorer — reasoning chain, LLM requests, validation, governance."""
    events = await replay_store.get_timeline(execution_id)

    chain: List[Dict] = []
    llm_count = 0

    for e in events:
        payload = e.get("payload") or {}
        event_type = (e.get("event_type") or "")

        llm_requests = []
        token_usage = e.get("token_usage")
        if token_usage:
            llm_requests.append({
                "request_id": f"llm-{e.get('sequence', 0)}",
                "provider": payload.get("provider", "unknown"),
                "model": payload.get("model", "unknown"),
                "prompt_tokens": token_usage.get("prompt_tokens", 0),
                "completion_tokens": token_usage.get("completion_tokens", 0),
                "total_tokens": token_usage.get("total_tokens", 0),
                "prompt": payload.get("prompt"),
                "response": payload.get("response") or e.get("message"),
                "timestamp": e.get("timestamp"),
                "offset_ms": e.get("offset_ms"),
                "latency_ms": e.get("latency_ms"),
                "confidence_score": e.get("confidence_score"),
                "cost": payload.get("cost"),
            })
            llm_count += 1

        decision = {
            "decision_id": f"dec-{e.get('sequence', 0)}",
            "step": event_type,
            "agent": e.get("agent", ""),
            "reasoning": payload.get("reasoning") or payload.get("thought") or e.get("message"),
            "llm_requests": llm_requests,
            "confidence_score": e.get("confidence_score"),
            "validation_result": payload.get("validation"),
            "governance_action": payload.get("governance_action") or payload.get("approval"),
            "timestamp": e.get("timestamp"),
            "offset_ms": e.get("offset_ms"),
        }
        chain.append(decision)

    return {
        "execution_id": execution_id,
        "total_decisions": len(chain),
        "chain": chain,
        "summary": {
            "total_llm_requests": llm_count,
            "total_tokens": sum(
                sum(r.get("total_tokens", 0) for r in d.get("llm_requests", []))
                for d in chain
            ),
            "avg_confidence": (
                sum(d.get("confidence_score") or 0 for d in chain if d.get("confidence_score")) /
                max(sum(1 for d in chain if d.get("confidence_score")), 1)
            ),
        },
    }


# ============================================================
# GET /api/enterprise-replay/memory/{execution_id}
# ============================================================

@router.get("/memory/{execution_id}")
async def get_memory_replay(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Memory replay — working, semantic, episodic memory changes."""
    events = await replay_store.get_timeline(execution_id)

    working: List[Dict] = []
    semantic: List[Dict] = []
    episodic: List[Dict] = []

    for e in events:
        agent_lower = (e.get("agent") or "").lower()
        event_type = (e.get("event_type") or "").lower()
        payload = e.get("payload") or {}

        if "memory" not in agent_lower and "memory" not in event_type:
            continue

        entry = {
            "memory_id": e.get("event_id") or f"mem-{e.get('sequence', 0)}",
            "memory_type": "working",
            "content": e.get("message", ""),
            "agent": e.get("agent", ""),
            "operation": "retrieve" if "retriev" in event_type else "store" if "store" in event_type else "update",
            "timestamp": e.get("timestamp"),
            "offset_ms": e.get("offset_ms"),
            "relevance_score": e.get("confidence_score"),
            "metadata": payload,
        }

        if "episodic" in agent_lower or "episodic" in event_type:
            entry["memory_type"] = "episodic"
            episodic.append(entry)
        elif "semantic" in agent_lower or "semantic" in event_type:
            entry["memory_type"] = "semantic"
            semantic.append(entry)
        else:
            working.append(entry)

    return {
        "execution_id": execution_id,
        "total_entries": len(working) + len(semantic) + len(episodic),
        "working_memory": working,
        "semantic_memory": semantic,
        "episodic_memory": episodic,
        "changes_over_time": [
            {"timestamp": e.get("timestamp"), "offset_ms": e.get("offset_ms"), "operation": e.get("event_type")}
            for e in events if "memory" in (e.get("agent") or "").lower() or "memory" in (e.get("event_type") or "").lower()
        ],
        "summary": {
            "total_working": len(working),
            "total_semantic": len(semantic),
            "total_episodic": len(episodic),
            "mission_context": "reconstructed from replay events",
        },
    }


# ============================================================
# GET /api/enterprise-replay/knowledge-graph/{execution_id}
# ============================================================

@router.get("/knowledge-graph/{execution_id}")
async def get_knowledge_graph_replay(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Knowledge graph replay — entity/relationship creation, graph evolution."""
    entities: List[Dict] = []
    relationships: List[Dict] = []
    evolution: List[Dict] = []

    try:
        from backend.memory.graph.cognition_graph import CognitionGraph
        graph = CognitionGraph()
        lineage = await graph.get_execution_lineage(execution_id)

        for item in lineage:
            if item.get("type") == "entity" or item.get("labels"):
                entities.append({
                    "entity_id": item.get("id", str(hash(str(item)))),
                    "entity_type": (item.get("labels") or ["unknown"])[0] if item.get("labels") else "unknown",
                    "entity_name": item.get("name") or item.get("id", "unknown"),
                    "operation": "create",
                    "properties": item,
                    "timestamp": item.get("timestamp"),
                    "offset_ms": None,
                })

        evolution = [{
            "timestamp": e.get("timestamp"),
            "event": f"Graph entity: {e.get('name', 'unknown')}",
            "type": "entity_created",
        } for e in entities]

    except Exception as exc:
        log.warning("Knowledge graph replay unavailable: %s", exc)

    return {
        "execution_id": execution_id,
        "total_entities": len(entities),
        "total_relationships": len(relationships),
        "entities": entities,
        "relationships": relationships,
        "evolution": evolution,
        "summary": {
            "entity_types": list(set(e["entity_type"] for e in entities)),
            "relationship_types": list(set(r["relationship_type"] for r in relationships)),
            "graph_state": "reconstructed",
        },
    }


# ============================================================
# GET /api/enterprise-replay/costs/{execution_id}
# ============================================================

@router.get("/costs/{execution_id}")
async def get_cost_replay(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Cost replay — LLM tokens, model usage, worker/mission/connector costs."""
    events = await replay_store.get_timeline(execution_id)

    entries: List[Dict] = []
    by_category: Dict[str, float] = {"llm": 0, "worker": 0, "mission": 0, "connector": 0}
    by_day: Dict[str, float] = {}

    total_cost = 0.0

    for e in events:
        token_usage = e.get("token_usage")
        payload = e.get("payload") or {}
        cost_value = 0.0

        if token_usage:
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)

            try:
                from backend.analytics.cost_engine import estimate_cost
                cost_value = estimate_cost(payload.get("provider", "openai"), payload.get("model", "gpt-4"), prompt_tokens, completion_tokens)
            except Exception:
                cost_value = (prompt_tokens + completion_tokens) * 0.000003

            entry = {
                "cost_id": f"cost-{e.get('sequence', 0)}",
                "category": "llm",
                "provider": payload.get("provider", "openai"),
                "model": payload.get("model", "gpt-4"),
                "tokens": total_tokens,
                "cost": round(cost_value, 6),
                "timestamp": e.get("timestamp"),
                "date": (e.get("timestamp") or "")[:10] if e.get("timestamp") else None,
                "metadata": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, **token_usage},
            }
            entries.append(entry)
            by_category["llm"] += cost_value

    total_cost = sum(e["cost"] for e in entries)

    for entry in entries:
        day = entry.get("date") or "unknown"
        by_day[day] = by_day.get(day, 0) + entry["cost"]

    return {
        "execution_id": execution_id,
        "total_cost": round(total_cost, 6),
        "entries": entries,
        "by_category": {k: round(v, 6) for k, v in by_category.items()},
        "by_day": {k: round(v, 6) for k, v in by_day.items()},
        "summary": {
            "total_tokens": sum(e.get("tokens", 0) for e in entries),
            "total_llm_calls": sum(1 for e in entries if e["category"] == "llm"),
            "avg_cost_per_call": round(total_cost / max(len(entries), 1), 6),
        },
    }


# ============================================================
# GET /api/enterprise-replay/events/{execution_id}
# ============================================================

@router.get("/events/{execution_id}")
async def get_event_explorer(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Event explorer — every event published through EventBus."""
    events = await replay_store.get_timeline(execution_id)

    event_list: List[Dict] = []
    by_category: Dict[str, int] = {}
    by_source: Dict[str, int] = {}

    for e in events:
        event_type = e.get("event_type", "unknown")
        agent = e.get("agent", "system")

        category_map = {
            "mission": "mission",
            "agent": "worker",
            "tool": "connector",
            "memory": "memory",
            "graph": "graph",
            "governance": "governance",
            "approval": "approval",
            "security": "security",
        }

        category = "mission"
        for key, val in category_map.items():
            if key in event_type.lower():
                category = val
                break

        source = agent
        by_category[category] = by_category.get(category, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1

        event_list.append({
            "event_id": e.get("event_id") or f"evt-{e.get('sequence', 0)}",
            "category": category,
            "event_type": event_type,
            "source": source,
            "agent": agent,
            "message": e.get("message", ""),
            "data": e.get("payload") or {},
            "timestamp": e.get("timestamp"),
            "offset_ms": e.get("offset_ms"),
            "channel": category,
        })

    return {
        "execution_id": execution_id,
        "total_events": len(event_list),
        "events": event_list,
        "by_category": by_category,
        "by_source": by_source,
        "summary": {
            "categories": list(by_category.keys()),
            "sources": list(by_source.keys()),
            "duration_ms": (event_list[-1]["offset_ms"] - event_list[0]["offset_ms"]) if len(event_list) > 1 and event_list[0]["offset_ms"] and event_list[-1]["offset_ms"] else 0,
        },
    }


# ============================================================
# GET /api/enterprise-replay/timeline/{execution_id}
# ============================================================

@router.get("/timeline/{execution_id}")
async def get_timeline_explorer(
    execution_id: str,
    zoom: Optional[str] = Query(default=None, description="Zoom level: 1x, 2x, 5x"),
    agent: Optional[str] = Query(default=None, description="Filter by agent"),
    event_type: Optional[str] = Query(default=None, description="Filter by event type"),
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Timeline explorer — chronological execution with zoom, filter, search support."""
    events_raw = await replay_store.get_timeline(execution_id)

    events = []
    for e in events_raw:
        if agent and e.get("agent") != agent:
            continue
        if event_type and e.get("event_type") != event_type and e.get("original_type") != event_type:
            continue

        category = "mission"
        et = e.get("event_type", "").lower()
        if "memory" in et:
            category = "memory"
        elif "tool" in et or "connector" in et:
            category = "connector"
        elif "agent" in et:
            category = "worker"
        elif "governance" in et or "approval" in et:
            category = "governance"

        events.append({
            "sequence": e.get("sequence", 0),
            "event_type": e.get("event_type", ""),
            "agent": e.get("agent", ""),
            "message": e.get("message", ""),
            "timestamp": e.get("timestamp"),
            "offset_ms": e.get("offset_ms"),
            "category": category,
            "metadata": e.get("payload") or {},
        })

    return {
        "execution_id": execution_id,
        "total_events": len(events),
        "events": events,
        "zoom_levels": ["1x", "2x", "5x", "10x"],
        "summary": {
            "current_zoom": zoom or "1x",
            "agents": list(dict.fromkeys(e["agent"] for e in events if e["agent"])),
            "categories": list(dict.fromkeys(e["category"] for e in events)),
            "duration_ms": (events[-1]["offset_ms"] - events[0]["offset_ms"]) if len(events) > 1 and events[0]["offset_ms"] and events[-1]["offset_ms"] else None,
        },
    }


# ============================================================
# GET /api/enterprise-replay/execution-graph/{execution_id}
# ============================================================

@router.get("/execution-graph/{execution_id}")
async def get_execution_graph(
    execution_id: str,
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """Execution graph — Mission -> Workers -> Connectors -> Memory -> Knowledge Graph -> Approvals -> Completion."""
    events = await replay_store.get_timeline(execution_id)

    nodes: List[Dict] = []
    edges: List[Dict] = []

    # Build node status map
    has_mission = False
    has_workers = set()
    has_connectors = set()
    has_memory = False
    has_graph = False
    has_approvals = False
    has_completion = False

    for e in events:
        agent = (e.get("agent") or "").lower()
        event_type = (e.get("event_type") or "").lower()

        if "mission" in event_type:
            has_mission = True
        if any(w in agent for w in ["browser", "voice", "desktop", "computer"]):
            has_workers.add(agent.split("_")[0] if "_" in agent else agent)
        if any(c in agent for c in ["github", "jira", "slack", "teams", "servicenow", "confluence", "notion", "azure"]):
            has_connectors.add(agent)
        if "memory" in agent or "memory" in event_type:
            has_memory = True
        if "graph" in event_type or "knowledge" in agent or "cognition" in agent:
            has_graph = True
        if "governance" in agent or "approval" in event_type or "approve" in event_type:
            has_approvals = True
        if "completed" in event_type or "finish" in event_type:
            has_completion = True

    # Build nodes
    nodes.append({
        "id": "mission",
        "type": "mission",
        "label": "Mission",
        "status": "completed" if has_completion else "in_progress",
        "duration_ms": None,
        "metadata": {"has_mission": has_mission},
    })

    if has_workers:
        for w in has_workers:
            nodes.append({
                "id": f"worker-{w}",
                "type": "worker",
                "label": f"Worker: {w.title()}",
                "status": "completed",
                "duration_ms": None,
                "metadata": {"worker_type": w},
            })
            edges.append({"source": "mission", "target": f"worker-{w}", "label": "delegates", "type": "delegation"})
    else:
        nodes.append({
            "id": "workers",
            "type": "worker",
            "label": "Workers",
            "status": "completed",
            "duration_ms": None,
            "metadata": {},
        })
        edges.append({"source": "mission", "target": "workers", "label": "delegates", "type": "delegation"})

    if has_connectors:
        for c in has_connectors:
            nodes.append({
                "id": f"connector-{c}",
                "type": "connector",
                "label": f"Connector: {c.title()}",
                "status": "completed",
                "duration_ms": None,
                "metadata": {"connector": c},
            })
            parent = f"worker-{list(has_workers)[0]}" if has_workers else "workers"
            edges.append({"source": parent, "target": f"connector-{c}", "label": "calls", "type": "connector_call"})

    if has_memory:
        nodes.append({
            "id": "memory",
            "type": "memory",
            "label": "Memory System",
            "status": "completed",
            "duration_ms": None,
            "metadata": {},
        })
        parent = f"connector-{list(has_connectors)[0]}" if has_connectors else (f"worker-{list(has_workers)[0]}" if has_workers else "workers")
        edges.append({"source": parent, "target": "memory", "label": "stores/retrieves", "type": "memory_op"})

    if has_graph:
        nodes.append({
            "id": "knowledge-graph",
            "type": "knowledge_graph",
            "label": "Knowledge Graph",
            "status": "completed",
            "duration_ms": None,
            "metadata": {},
        })
        edges.append({"source": "memory", "target": "knowledge-graph", "label": "persists to", "type": "graph_op"})

    if has_approvals:
        nodes.append({
            "id": "approvals",
            "type": "approval",
            "label": "Approvals",
            "status": "completed",
            "duration_ms": None,
            "metadata": {},
        })
        target = "knowledge-graph" if has_graph else "memory"
        edges.append({"source": target, "target": "approvals", "label": "requires", "type": "governance"})

    if has_completion:
        nodes.append({
            "id": "completion",
            "type": "completion",
            "label": "Completion",
            "status": "completed",
            "duration_ms": None,
            "metadata": {"is_complete": True},
        })
        target = "approvals" if has_approvals else ("knowledge-graph" if has_graph else "memory")
        edges.append({"source": target, "target": "completion", "label": "completes", "type": "completion"})

    return {
        "execution_id": execution_id,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "has_mission": has_mission,
            "has_completion": has_completion,
        },
    }


# ============================================================
# GET /api/enterprise-replay/export/{execution_id}
# ============================================================

@router.get("/export/{execution_id}")
async def export_replay(
    execution_id: str,
    format: str = Query(default="json", description="Export format: json, markdown, timeline, replay-package"),
    current_user: dict = Depends(require_user),
) -> Any:
    """Export replay data in various formats."""
    events = await replay_store.get_timeline(execution_id)
    summary = await replay_store.get_summary(execution_id)

    if not events:
        raise HTTPException(status_code=404, detail=f"No replay data for execution '{execution_id}'")

    if format == "json":
        return {
            "execution_id": execution_id,
            "export_format": "json",
            "exported_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "events": events,
            "total_events": len(events),
        }

    elif format == "markdown":
        md_lines = [
            f"# Mission Replay Export: {execution_id}",
            f"",
            f"**Exported at:** {datetime.utcnow().isoformat()}",
            f"**Total Events:** {len(events)}",
            f"**Status:** {'Complete' if summary.get('is_complete') else 'In Progress'}",
            f"**Duration:** {summary.get('duration_ms', 0)}ms",
            f"",
            f"## Events",
            f"",
            f"| # | Time | Agent | Event | Message |",
            f"|---|------|-------|-------|---------|",
        ]
        for i, e in enumerate(events, 1):
            ts = e.get("timestamp") or f"+{e.get('offset_ms', 0)}ms"
            md_lines.append(f"| {i} | {ts} | {e.get('agent', '')} | {e.get('event_type', '')} | {e.get('message', '')} |")

        md_lines.append(f"")
        md_lines.append(f"---")
        md_lines.append(f"*Exported from CortexPrime Enterprise Replay Center*")

        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content="\n".join(md_lines), media_type="text/markdown")

    elif format == "timeline":
        return {
            "execution_id": execution_id,
            "export_format": "timeline",
            "exported_at": datetime.utcnow().isoformat(),
            "timeline": [
                {
                    "sequence": e.get("sequence"),
                    "offset_ms": e.get("offset_ms"),
                    "agent": e.get("agent"),
                    "event_type": e.get("event_type"),
                    "message": e.get("message"),
                }
                for e in events
            ],
        }

    elif format == "replay-package":
        return {
            "execution_id": execution_id,
            "export_format": "replay-package",
            "exported_at": datetime.utcnow().isoformat(),
            "version": "1.0",
            "application": "CortexPrime Enterprise Replay Center",
            "summary": summary,
            "events": events,
            "total_events": len(events),
            "metadata": {
                "exported_by": current_user.get("sub", "unknown"),
                "replay_store": "Redis + PostgreSQL",
                "runtime": "CortexPrime Mission Runtime",
            },
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")