"""
Memory Explorer API Routes
==========================

Read-only observability endpoints for the Memory Explorer UI.
All endpoints are authenticated (require_user) and gracefully degrade
when PostgreSQL / Redis is unavailable.

Routes
------
GET /memory/explorer/search    - Cross-store similarity + text search
GET /memory/explorer/timeline  - All memories ordered by date, grouped by day
GET /memory/explorer/graph     - Node/edge data for memory concept graph
GET /memory/explorer/stats     - Aggregate stats + heatmap data per memory
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.memory.stores.episodic_store    import episodic_store
from backend.memory.stores.semantic_store    import semantic_store
from backend.memory.stores.reflection_store  import reflection_store
from backend.memory.db.postgres_client       import postgres_client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/memory/explorer", tags=["Memory Explorer"])


# ===========================================================================
# RESPONSE SCHEMAS
# ===========================================================================

class MemoryRecord(BaseModel):
    id:               str
    memory_type:      str            # episodic | semantic | reflection | workspace | voice | browser
    content:          str
    agent:            Optional[str]
    concept:          Optional[str]
    event_type:       Optional[str]
    session_id:       Optional[str]
    mission_id:       Optional[str]
    source:           Optional[str]
    similarity_score: Optional[float]
    confidence:       Optional[float]
    retrieval_count:  int
    created_at:       str            # ISO-8601
    last_retrieved:   Optional[str]
    metadata:         Dict[str, Any]

    class Config:
        extra = "allow"


class TimelineDay(BaseModel):
    date:    str                  # YYYY-MM-DD
    count:   int
    records: List[MemoryRecord]


class GraphNode(BaseModel):
    id:          str
    label:       str
    memory_type: str
    agent:       Optional[str]
    weight:      float           # retrieval_count or confidence
    created_at:  str


class GraphEdge(BaseModel):
    source:   str
    target:   str
    relation: str
    weight:   float


class HeatmapCell(BaseModel):
    id:              str
    label:           str
    memory_type:     str
    retrieval_count: int
    created_at:      str
    agent:           Optional[str]


class MemoryStats(BaseModel):
    total:            int
    by_type:          Dict[str, int]
    by_agent:         Dict[str, int]
    avg_similarity:   Optional[float]
    heatmap:          List[HeatmapCell]      # top-50 most retrieved
    date_distribution: Dict[str, int]        # YYYY-MM-DD -> count


# ===========================================================================
# HELPERS
# ===========================================================================

def _iso(dt: Any) -> str:
    if dt is None:
        return datetime.utcnow().isoformat()
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _record_from_episodic(e: Any, mem_type: str = "episodic") -> MemoryRecord:
    meta = e.metadata if isinstance(e.metadata, dict) else {}
    return MemoryRecord(
        id               = str(e.id),
        memory_type      = mem_type,
        content          = e.content,
        agent            = e.agent,
        concept          = None,
        event_type       = e.event_type,
        session_id       = getattr(e, "session_id", None),
        mission_id       = meta.get("mission_id"),
        source           = meta.get("source"),
        similarity_score = getattr(e, "relevance", None),
        confidence       = None,
        retrieval_count  = int(meta.get("retrieval_count", 0)),
        created_at       = _iso(e.created_at),
        last_retrieved   = meta.get("last_retrieved"),
        metadata         = meta,
    )


def _record_from_semantic(e: Any) -> MemoryRecord:
    meta = e.metadata if isinstance(e.metadata, dict) else {}
    return MemoryRecord(
        id               = str(e.id),
        memory_type      = "semantic",
        content          = e.content,
        agent            = meta.get("agent"),
        concept          = e.concept,
        event_type       = None,
        session_id       = None,
        mission_id       = meta.get("mission_id"),
        source           = e.source,
        similarity_score = getattr(e, "relevance", None),
        confidence       = e.confidence,
        retrieval_count  = int(meta.get("retrieval_count", 0)),
        created_at       = _iso(e.created_at),
        last_retrieved   = meta.get("last_retrieved"),
        metadata         = meta,
    )


def _record_from_reflection(e: Any) -> MemoryRecord:
    meta = e.metadata if isinstance(e.metadata, dict) else {}
    return MemoryRecord(
        id               = str(e.id),
        memory_type      = "reflection",
        content          = e.reflection,
        agent            = e.agent,
        concept          = None,
        event_type       = "reflection",
        session_id       = None,
        mission_id       = e.mission_id,
        source           = None,
        similarity_score = None,
        confidence       = e.score,
        retrieval_count  = int(meta.get("retrieval_count", 0)),
        created_at       = _iso(e.created_at),
        last_retrieved   = meta.get("last_retrieved"),
        metadata         = meta,
    )


def _infer_source_type(e: Any, base_type: str) -> str:
    """Map agent name → specialized memory type when applicable."""
    agent = (getattr(e, "agent", "") or "").lower()
    event = (getattr(e, "event_type", "") or "").lower()
    if "voice" in agent or "voice" in event:
        return "voice"
    if "browser" in agent or "computer" in agent or "operator" in agent:
        return "browser"
    if "workspace" in agent or "workspace" in event:
        return "workspace"
    return base_type


# ===========================================================================
# SEARCH  — cross-store vector + text search
# ===========================================================================

@router.get("/search")
async def search_memories(
    q:               str   = Query(...,                 description="Search query"),
    limit:           int   = Query(default=20, ge=1, le=100),
    memory_types:    str   = Query(default="all",       description="Comma-separated: episodic,semantic,reflection,workspace,voice,browser,all"),
    min_score:       float = Query(default=0.0, ge=0.0, le=1.0),
    agent_filter:    Optional[str] = Query(default=None),
    current_user:    dict  = Depends(require_user),
) -> Dict[str, Any]:
    """
    Cross-store similarity search across Episodic, Semantic, and Reflection memory.
    Returns deduplicated, scored, and sorted results.
    """
    requested = {t.strip().lower() for t in memory_types.split(",")}
    include_all = "all" in requested

    records: List[MemoryRecord] = []

    # ── Episodic (+ voice/browser/workspace inferred) ─────────────────
    if include_all or requested & {"episodic", "voice", "browser", "workspace"}:
        try:
            hits = await episodic_store.search_similar(q, limit=limit)
            for e in hits:
                mem_type = _infer_source_type(e, "episodic")
                if not include_all and mem_type not in requested:
                    continue
                rec = _record_from_episodic(e, mem_type)
                if (rec.similarity_score or 0.0) >= min_score:
                    records.append(rec)
        except Exception as exc:
            log.debug("episodic search failed: %s", exc)

    # ── Semantic ──────────────────────────────────────────────────────
    if include_all or "semantic" in requested:
        try:
            hits = await semantic_store.search(q, limit=limit, min_relevance=min_score)
            for e in hits:
                records.append(_record_from_semantic(e))
        except Exception as exc:
            log.debug("semantic search failed: %s", exc)

    # ── Reflection ────────────────────────────────────────────────────
    if include_all or "reflection" in requested:
        try:
            hits = await reflection_store.search_similar(q, limit=limit)
            for e in hits:
                records.append(_record_from_reflection(e))
        except Exception as exc:
            log.debug("reflection search failed: %s", exc)

    # ── Agent filter ──────────────────────────────────────────────────
    if agent_filter:
        af = agent_filter.lower()
        records = [r for r in records if af in (r.agent or "").lower()]

    # ── Sort by similarity descending, then recency ───────────────────
    records.sort(
        key=lambda r: (-(r.similarity_score or 0.0), r.created_at),
        reverse=False,
    )

    return {
        "query":   q,
        "count":   len(records),
        "results": [r.model_dump() for r in records[:limit]],
    }


# ===========================================================================
# TIMELINE  — all memories ordered by date, grouped by day
# ===========================================================================

@router.get("/timeline")
async def memory_timeline(
    days:         int  = Query(default=30,  ge=1, le=365),
    limit_per_day: int = Query(default=50,  ge=1, le=200),
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """
    Return all memories from the last N days grouped by date.
    Used to power the MemoryTimeline component.
    """
    since = datetime.utcnow() - timedelta(days=days)
    all_records: List[MemoryRecord] = []

    # Episodic — query last N records; filter by date client-side
    try:
        rows = await postgres_client.fetch(
            """
            SELECT id, session_id, agent, event_type, content, metadata, created_at
            FROM episodic_memory
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            since,
            days * limit_per_day,
        )
        for row in rows:
            from backend.memory.stores.episodic_store import EpisodicStore
            e = EpisodicStore._row(row)
            mem_type = _infer_source_type(e, "episodic")
            all_records.append(_record_from_episodic(e, mem_type))
    except Exception as exc:
        log.debug("timeline episodic query failed: %s", exc)

    # Semantic
    try:
        rows = await postgres_client.fetch(
            """
            SELECT id, concept, content, source, confidence, metadata, created_at
            FROM semantic_memory
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            since,
            days * limit_per_day,
        )
        for row in rows:
            from backend.memory.stores.semantic_store import SemanticStore
            e = SemanticStore._row(row)
            all_records.append(_record_from_semantic(e))
    except Exception as exc:
        log.debug("timeline semantic query failed: %s", exc)

    # Reflection
    try:
        rows = await postgres_client.fetch(
            """
            SELECT id, mission_id, agent, reflection, score, metadata, created_at
            FROM reflection_history
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            since,
            days * limit_per_day,
        )
        for row in rows:
            from backend.memory.stores.reflection_store import ReflectionStore
            e = ReflectionStore._row(row)
            all_records.append(_record_from_reflection(e))
    except Exception as exc:
        log.debug("timeline reflection query failed: %s", exc)

    # Sort all by created_at descending
    all_records.sort(key=lambda r: r.created_at, reverse=True)

    # Group by date (YYYY-MM-DD)
    by_day: Dict[str, List[MemoryRecord]] = defaultdict(list)
    for rec in all_records:
        date_key = rec.created_at[:10]
        by_day[date_key].append(rec)

    timeline = [
        TimelineDay(
            date=d,
            count=len(recs),
            records=recs[:limit_per_day],
        )
        for d, recs in sorted(by_day.items(), reverse=True)
    ]

    return {
        "days":        days,
        "total":       len(all_records),
        "day_count":   len(timeline),
        "timeline":    [t.model_dump() for t in timeline],
    }


# ===========================================================================
# GRAPH  — concept/agent node-edge structure for MemoryGraph
# ===========================================================================

@router.get("/graph")
async def memory_graph(
    limit:        int  = Query(default=80,  ge=5, le=300),
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """
    Build a lightweight node/edge graph from memory entries.

    Nodes = individual memory records (sized by confidence/retrieval).
    Edges = inferred via shared agent, session, or mission.
    """
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []

    # Semantic concepts → prominent nodes
    try:
        rows = await postgres_client.fetch(
            """
            SELECT id, concept, content, source, confidence, metadata, created_at
            FROM semantic_memory
            ORDER BY confidence DESC, created_at DESC
            LIMIT $1
            """,
            limit // 2,
        )
        for row in rows:
            meta = row["metadata"] or {}
            if isinstance(meta, str):
                import json
                meta = json.loads(meta)
            nodes.append(GraphNode(
                id          = str(row["id"]),
                label       = row["concept"][:40],
                memory_type = "semantic",
                agent       = meta.get("agent"),
                weight      = float(row.get("confidence") or 1.0),
                created_at  = _iso(row["created_at"]),
            ))
    except Exception as exc:
        log.debug("graph semantic failed: %s", exc)

    # Episodic agent-grouped nodes
    try:
        rows = await postgres_client.fetch(
            """
            SELECT id, agent, event_type, content, metadata, created_at
            FROM episodic_memory
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit // 2,
        )
        for row in rows:
            meta = row["metadata"] or {}
            if isinstance(meta, str):
                import json
                meta = json.loads(meta)
            nodes.append(GraphNode(
                id          = str(row["id"]),
                label       = (row["content"] or "")[:40],
                memory_type = _infer_source_type(
                    type("_", (), {"agent": row["agent"], "event_type": row["event_type"]})(),
                    "episodic",
                ),
                agent       = row["agent"],
                weight      = 1.0,
                created_at  = _iso(row["created_at"]),
            ))
    except Exception as exc:
        log.debug("graph episodic failed: %s", exc)

    # Build edges: same-agent memories within 5 minutes
    agent_buckets: Dict[str, List[GraphNode]] = defaultdict(list)
    for n in nodes:
        if n.agent:
            agent_buckets[n.agent].append(n)

    for agent, ag_nodes in agent_buckets.items():
        for i, a in enumerate(ag_nodes[:10]):
            for b in ag_nodes[i + 1:i + 4]:
                edges.append(GraphEdge(
                    source   = a.id,
                    target   = b.id,
                    relation = "same_agent",
                    weight   = 0.5,
                ))

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes":      [n.model_dump() for n in nodes],
        "edges":      [e.model_dump() for e in edges],
    }


# ===========================================================================
# STATS  — aggregate stats + heatmap
# ===========================================================================

@router.get("/stats")
async def memory_stats(
    current_user: dict = Depends(require_user),
) -> Dict[str, Any]:
    """
    Aggregate memory statistics for the explorer overview panel.
    Returns total counts, per-type breakdown, per-agent breakdown,
    and a heatmap of most frequently retrieved memory entries.
    """
    by_type:  Dict[str, int] = {}
    by_agent: Dict[str, int] = {}
    date_dist: Dict[str, int] = {}
    heatmap:  List[HeatmapCell] = []

    # Count totals per store
    count_queries = [
        ("episodic",   "SELECT COUNT(*) FROM episodic_memory"),
        ("semantic",   "SELECT COUNT(*) FROM semantic_memory"),
        ("reflection", "SELECT COUNT(*) FROM reflection_history"),
    ]
    for store_type, sql in count_queries:
        try:
            row = await postgres_client.fetchrow(sql)
            by_type[store_type] = int(row["count"]) if row else 0
        except Exception:
            by_type[store_type] = 0

    # Per-agent breakdown (episodic + reflection)
    for sql in [
        "SELECT agent, COUNT(*) as cnt FROM episodic_memory GROUP BY agent",
        "SELECT agent, COUNT(*) as cnt FROM reflection_history GROUP BY agent",
    ]:
        try:
            rows = await postgres_client.fetch(sql)
            for row in rows:
                a = row["agent"] or "unknown"
                by_agent[a] = by_agent.get(a, 0) + int(row["cnt"])
        except Exception:
            pass

    # Date distribution (last 30 days, episodic)
    try:
        rows = await postgres_client.fetch(
            """
            SELECT DATE(created_at) as d, COUNT(*) as cnt
            FROM episodic_memory
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY d
            ORDER BY d
            """
        )
        for row in rows:
            date_dist[str(row["d"])] = int(row["cnt"])
    except Exception:
        pass

    # Heatmap: top-50 most-retrieved memories via metadata->retrieval_count
    # Fall back to most recent episodic entries if metadata not populated
    try:
        rows = await postgres_client.fetch(
            """
            SELECT id, agent, event_type, content,
                   COALESCE((metadata->>'retrieval_count')::int, 0) AS rc,
                   created_at
            FROM episodic_memory
            ORDER BY rc DESC, created_at DESC
            LIMIT 50
            """
        )
        for row in rows:
            heatmap.append(HeatmapCell(
                id              = str(row["id"]),
                label           = (row["content"] or "")[:60],
                memory_type     = "episodic",
                retrieval_count = int(row["rc"] or 0),
                created_at      = _iso(row["created_at"]),
                agent           = row["agent"],
            ))
    except Exception:
        pass

    # Also pull semantic memories into heatmap
    try:
        rows = await postgres_client.fetch(
            """
            SELECT id, concept, content, source,
                   COALESCE((metadata->>'retrieval_count')::int, 0) AS rc,
                   confidence, created_at
            FROM semantic_memory
            ORDER BY rc DESC, confidence DESC, created_at DESC
            LIMIT 25
            """
        )
        for row in rows:
            heatmap.append(HeatmapCell(
                id              = str(row["id"]),
                label           = row["concept"][:60],
                memory_type     = "semantic",
                retrieval_count = int(row["rc"] or 0),
                created_at      = _iso(row["created_at"]),
                agent           = None,
            ))
    except Exception:
        pass

    # Sort heatmap by retrieval_count desc
    heatmap.sort(key=lambda c: c.retrieval_count, reverse=True)

    total = sum(by_type.values())

    return MemoryStats(
        total            = total,
        by_type          = by_type,
        by_agent         = by_agent,
        avg_similarity   = None,
        heatmap          = heatmap[:50],
        date_distribution = date_dist,
    ).model_dump()
