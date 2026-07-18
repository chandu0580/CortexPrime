"""
Enterprise Knowledge Routes — universal search + graph exploration.

Endpoints
---------
  GET /api/enterprise/search         — universal search across all sources
  GET /api/enterprise/graph/entities — list entity types
  GET /api/enterprise/graph/entities/{type} — list entities by type
  GET /api/enterprise/graph/node/{node_id}  — get node + relationships
  GET /api/enterprise/graph/mission/{execution_id} — full mission subgraph
  GET /api/enterprise/graph/recent-missions    — recent missions
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from backend.connectors.registry import connector_registry
from backend.services.enterprise_graph_service import enterprise_graph

log = logging.getLogger(__name__)


# ======================================================================
# ROUTER
# ======================================================================

router = APIRouter(prefix="/api/enterprise", tags=["Enterprise Knowledge"])


# ======================================================================
# HEALTH
# ======================================================================


@router.get("/knowledge/health")
async def knowledge_health():
    return {"status": "available"}


# ======================================================================
# UNIVERSAL SEARCH
# ======================================================================


@router.get("/search")
async def universal_search(
    q: str = Query("", description="Search query"),
    sources: Optional[str] = Query(None, description="Comma-separated source filter: neo4j,connectors,replay,audit,memory"),
    limit: int = Query(20, ge=1, le=100),
):
    """Search across all enterprise knowledge sources."""
    if not q or not q.strip():
        return {
            "query": q,
            "results": [],
            "total": 0,
            "sources_queried": [],
        }

    query = q.strip()
    source_list = [s.strip().lower() for s in sources.split(",")] if sources else []
    results: List[Dict[str, Any]] = []
    tasks = []

    # Source 1: Neo4j enterprise graph entities
    if not source_list or "neo4j" in source_list:
        tasks.append(_search_neo4j(query, limit))

    # Source 2: Connector operations via registry
    if not source_list or "connectors" in source_list:
        tasks.append(_search_connectors(query, limit))

    # Source 3: Replay store
    if not source_list or "replay" in source_list:
        tasks.append(_search_replay(query, limit))

    # Source 4: Audit log
    if not source_list or "audit" in source_list:
        tasks.append(_search_audit(query, limit))

    # Source 5: Memory context
    if not source_list or "memory" in source_list:
        tasks.append(_search_memory(query, limit))

    completed = await asyncio.gather(*tasks, return_exceptions=True)
    for res in completed:
        if isinstance(res, list):
            results.extend(res)

    results.sort(key=lambda r: r.get("score", 0) or 0, reverse=True)
    results = results[:limit]

    return {
        "query": query,
        "results": results,
        "total": len(results),
        "sources_queried": source_list or ["neo4j", "connectors", "replay", "audit", "memory"],
    }


async def _search_neo4j(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search Neo4j enterprise graph entities."""
    try:
        entities = await enterprise_graph.search_entities(query, limit=limit)
        return [
            {
                "source": "neo4j",
                "label": e.get("label", "Entity"),
                "score": e.get("score", 0),
                "title": e.get("node", {}).get("objective")
                         or e.get("node", {}).get("description")
                         or e.get("node", {}).get("name")
                         or e.get("node", {}).get("summary", ""),
                "description": e.get("node", {}),
                "id": (e.get("node", {}).get("execution_id")
                       or e.get("node", {}).get("action_id")
                       or e.get("node", {}).get("artifact_key")
                       or ""),
            }
            for e in entities
        ]
    except Exception as exc:
        log.warning("Neo4j search failed: %s", exc)
        return []


async def _search_connectors(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search connector names, types, and operations."""
    results = []
    ql = query.lower()
    for ctype in connector_registry.list_types():
        connector = connector_registry.get(ctype)
        if not connector:
            continue

        # Match connector name/type
        name = getattr(connector, "connector_name", "")
        score = 0
        if ql in name.lower():
            score = 0.9
        elif ql in ctype.lower():
            score = 0.8

        if score > 0:
            results.append({
                "source": "connectors",
                "label": "Connector",
                "score": score,
                "title": name or ctype,
                "description": {"connector_type": ctype, "connector_name": name},
                "id": ctype,
            })

        # Search operations
        try:
            ops = connector.get_operations()
            for op_name, op_meta in ops.items():
                op_score = 0
                desc = op_meta.get("description", "")
                if ql in op_name.lower():
                    op_score = 0.7
                elif ql in desc.lower():
                    op_score = 0.6
                if op_score > 0:
                    results.append({
                        "source": "connectors",
                        "label": "ConnectorOperation",
                        "score": op_score,
                        "title": f"{ctype}.{op_name}",
                        "description": op_meta,
                        "id": f"{ctype}.{op_name}",
                    })
        except Exception:
            pass

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


async def _search_replay(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search replay store for matching execution events."""
    try:
        from backend.services.mission_replay_store import replay_store
        ql = query.lower()
        results = []

        # Get recent executions from replay store metadata
        recent = await replay_store.get_summary("__recent__")
        if isinstance(recent, list):
            for item in recent[:20]:
                exec_id = item.get("execution_id", "")
                if ql in exec_id.lower():
                    results.append({
                        "source": "replay",
                        "label": "ReplayExecution",
                        "score": 0.5,
                        "title": f"Execution {exec_id[:12]}...",
                        "description": item,
                        "id": exec_id,
                    })
    except Exception as exc:
        log.warning("Replay search failed: %s", exc)
    return []


async def _search_audit(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search audit log entries."""
    try:
        from backend.safety.audit_logger import audit_logger
        ql = query.lower()
        results = []

        entries = await audit_logger.get_all_async(limit=100)
        for entry in entries:
            score = 0
            if ql in entry.get("action", "").lower():
                score = 0.6
            elif ql in entry.get("reason", "").lower():
                score = 0.5
            elif ql in entry.get("agent", "").lower():
                score = 0.4
            if score > 0:
                results.append({
                    "source": "audit",
                    "label": "AuditEntry",
                    "score": score,
                    "title": entry.get("action", ""),
                    "description": entry,
                    "id": entry.get("audit_id", entry.get("id", "")),
                })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]
    except Exception as exc:
        log.warning("Audit search failed: %s", exc)
        return []


async def _search_memory(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search memory context via memory orchestrator."""
    try:
        from backend.memory.memory_orchestrator import memory_orchestrator
        memories = await memory_orchestrator.search_memories(query, n=limit)
        return [
            {
                "source": "memory",
                "label": "Memory",
                "score": m.get("score", 0) if isinstance(m, dict) else 0.5,
                "title": m.get("content", "")[:120] if isinstance(m, dict) else str(m)[:120],
                "description": m if isinstance(m, dict) else {"content": str(m)},
                "id": m.get("memory_id", m.get("id", "")) if isinstance(m, dict) else "",
            }
            for m in memories
        ]
    except Exception as exc:
        log.warning("Memory search failed: %s", exc)
        return []


# ======================================================================
# GRAPH EXPLORATION
# ======================================================================


@router.get("/graph/entities")
async def list_entity_types():
    """List available enterprise entity types in the graph."""
    return {
        "types": [
            {"label": "EnterpriseMission", "description": "Launched enterprise missions"},
            {"label": "ConnectorAction", "description": "Individual connector step executions"},
            {"label": "Decision", "description": "Approval/rejection decisions"},
            {"label": "Approval", "description": "Approval gate records"},
            {"label": "Risk", "description": "Risk events and guardrails blocks"},
            {"label": "Recovery", "description": "Recovery actions (retry, fallback, rollback)"},
            {"label": "Evidence", "description": "Verification results and evidence"},
            {"label": "Artifact", "description": "Produced artifacts (issues, PRs, pages)"},
            {"label": "Outcome", "description": "Final mission outcomes"},
        ]
    }


@router.get("/graph/entities/{entity_type}")
async def list_entities(
    entity_type: str,
    limit: int = Query(50, ge=1, le=200),
):
    """List all entities of a given type."""
    entities = await enterprise_graph.list_entities_by_type(entity_type, limit=limit)
    return {
        "type": entity_type,
        "entities": entities,
        "total": len(entities),
    }


@router.get("/graph/node/{node_id}")
async def get_node(node_id: str):
    """Get a node and its immediate relationships."""
    result = await enterprise_graph.get_connected_nodes(node_id)
    if result is None:
        return {"error": "Node not found", "node_id": node_id}
    return result


@router.get("/graph/mission/{execution_id}")
async def get_mission_graph(execution_id: str):
    """Get the full enterprise subgraph for a mission."""
    result = await enterprise_graph.get_mission_graph(execution_id)
    if result is None:
        return {"error": "Mission not found", "execution_id": execution_id}
    return result


@router.get("/graph/recent-missions")
async def recent_missions(limit: int = Query(20, ge=1, le=100)):
    """List recent enterprise missions from the graph."""
    missions = await enterprise_graph.list_recent_missions(limit=limit)
    return {
        "missions": missions,
        "total": len(missions),
    }
