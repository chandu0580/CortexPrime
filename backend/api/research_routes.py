"""
Live Research API Routes.

Endpoints:
  POST /api/research/search          — run live research pipeline
  POST /api/research/news            — news-focused search
  POST /api/research/domain          — domain-restricted search
  GET  /api/research/history         — recent search history (telemetry)
  GET  /health/research              — provider status + telemetry snapshot
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_user

router = APIRouter(prefix="/api/research", tags=["research"], dependencies=[Depends(require_user)])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    query:      str       = Field(..., min_length=1, max_length=2000)
    mission_id: Optional[str] = None
    agent:      str       = "research"
    force_live: bool      = True
    top_k:      int       = Field(default=6, ge=1, le=20)

class NewsRequest(BaseModel):
    query:      str       = Field(..., min_length=1, max_length=2000)
    days:       int       = Field(default=7, ge=1, le=30)
    mission_id: Optional[str] = None

class DomainRequest(BaseModel):
    query:          str         = Field(..., min_length=1, max_length=2000)
    include_domains: List[str]  = Field(..., min_items=1)
    mission_id:     Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/search")
async def live_search(req: ResearchRequest) -> Dict[str, Any]:
    """
    Run a full live research pipeline: Tavily → ranking → citation → LLM synthesis.

    Returns the synthesised response with inline citation markers and a
    References section, plus the ranked source list and citation metadata.
    """
    from backend.research.live_research_pipeline import live_research_pipeline
    try:
        result = await live_research_pipeline.run(
            query      = req.query,
            mission_id = req.mission_id,
            agent      = req.agent,
            force_live = req.force_live,
        )
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/news")
async def live_news_search(req: NewsRequest) -> Dict[str, Any]:
    """News-focused search with recency bias."""
    import time

    from backend.research.citation_engine import citation_engine
    from backend.research.live_research_pipeline import live_research_pipeline
    from backend.research.research_telemetry import research_telemetry
    from backend.research.source_ranker import source_ranker
    from backend.research.tavily_client import tavily_client

    t0 = time.perf_counter()
    try:
        tavily_resp = await tavily_client.search_news(req.query, days=req.days)
        ranked      = source_ranker.rank(tavily_resp.sources, top_k=8)
        citations   = citation_engine.build(ranked)
        cite_block  = citation_engine.format_for_prompt(citations)

        synthesis  = await live_research_pipeline._synthesize(req.query, cite_block)
        annotated  = citation_engine.annotate_response(synthesis, citations)
        latency_ms = (time.perf_counter() - t0) * 1000

        research_telemetry.record(
            query=req.query, search_type="news",
            source_count=len(ranked), latency_ms=latency_ms, success=bool(ranked),
        )

        return {
            "query":       req.query,
            "search_type": "news",
            "sources":     ranked,
            "citations":   [c.to_dict() for c in citations],
            "response":    annotated,
            "answer":      tavily_resp.answer,
            "source_count": len(ranked),
            "latency_ms":  round(latency_ms, 1),
            "success":     bool(ranked),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/domain")
async def domain_search(req: DomainRequest) -> Dict[str, Any]:
    """Domain-restricted search — e.g. arxiv.org, github.com."""
    import time

    from backend.research.citation_engine import citation_engine
    from backend.research.live_research_pipeline import live_research_pipeline
    from backend.research.research_telemetry import research_telemetry
    from backend.research.source_ranker import source_ranker
    from backend.research.tavily_client import tavily_client

    t0 = time.perf_counter()
    try:
        tavily_resp = await tavily_client.search_domain(
            req.query, include_domains=req.include_domains
        )
        ranked     = source_ranker.rank(tavily_resp.sources, top_k=8)
        citations  = citation_engine.build(ranked)
        cite_block = citation_engine.format_for_prompt(citations)
        synthesis  = await live_research_pipeline._synthesize(req.query, cite_block)
        annotated  = citation_engine.annotate_response(synthesis, citations)
        latency_ms = (time.perf_counter() - t0) * 1000

        research_telemetry.record(
            query=req.query, search_type="domain",
            source_count=len(ranked), latency_ms=latency_ms, success=bool(ranked),
        )

        return {
            "query":          req.query,
            "search_type":    "domain",
            "domains":        req.include_domains,
            "sources":        ranked,
            "citations":      [c.to_dict() for c in citations],
            "response":       annotated,
            "answer":         tavily_resp.answer,
            "source_count":   len(ranked),
            "latency_ms":     round(latency_ms, 1),
            "success":        bool(ranked),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/history")
async def search_history(limit: int = 20) -> Dict[str, Any]:
    """Return recent search history from in-memory telemetry."""
    from backend.research.research_telemetry import research_telemetry
    snap = research_telemetry.snapshot(recent_n=limit)
    return snap
