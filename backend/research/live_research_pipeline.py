"""
Live Research Pipeline — CortexPrime.

Full end-to-end research flow:

  User Query
    ↓  live-trigger detection
  Tavily Search  (general or news based on query)
    ↓
  Source Ranking  (relevance × recency × authority)
    ↓
  Citation Engine  (build numbered citation list)
    ↓
  LLM Synthesis   (prompt includes sources + citation markers)
    ↓
  Citation Annotation  (append References section)
    ↓
  Memory Store    (search query → semantic_memory, summary → semantic_memory)
    ↓
  Governance Audit  (log external lookup)
    ↓
  Telemetry Record
    ↓
  ResearchResult  (returned to caller / research_agent)

All operations are async.  LLM synthesis uses the existing llm_gateway so
the pipeline respects whatever model is configured at runtime.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.research.tavily_client    import tavily_client, TavilyResponse
from backend.research.source_ranker    import source_ranker
from backend.research.citation_engine  import citation_engine, Citation
from backend.research.research_telemetry import research_telemetry

logger = logging.getLogger(__name__)

# LLM synthesis prompt template
_SYNTHESIS_PROMPT = """You are CortexPrime, a precise AI research engine.

Your task: answer the user's query using ONLY the verified sources provided.
Ground every factual claim with a citation marker like [1], [2], etc.

USER QUERY:
{query}

{citation_block}

INSTRUCTIONS:
- Be factual, structured, and cite sources inline using [N] markers.
- If sources conflict, note the discrepancy and cite both.
- If the answer is time-sensitive, highlight the most recent source.
- Do NOT hallucinate facts not present in the sources.
- Structure: Summary paragraph → Key Findings (bullet list) → Analysis.
"""

# News-specific trigger keywords
_NEWS_TRIGGERS = frozenset({
    "news", "latest", "today", "breaking", "update", "this week",
    "this month", "announcement", "released", "launched", "published",
})


@dataclass
class ResearchResult:
    query:       str
    execution_id: str
    search_type: str
    sources:     List[Dict[str, Any]]
    citations:   List[Dict[str, Any]]
    answer:      Optional[str]          # Tavily direct answer
    synthesis:   str                    # LLM-generated response with citations
    annotated:   str                    # synthesis + References footer
    latency_ms:  float
    success:     bool
    error:       Optional[str] = None
    timestamp:   str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query":        self.query,
            "execution_id": self.execution_id,
            "search_type":  self.search_type,
            "sources":      self.sources,
            "citations":    self.citations,
            "answer":       self.answer,
            "synthesis":    self.synthesis,
            "response":     self.annotated,
            "source_count": len(self.sources),
            "latency_ms":   round(self.latency_ms, 1),
            "success":      self.success,
            "error":        self.error,
            "timestamp":    self.timestamp,
        }


class LiveResearchPipeline:
    """
    Orchestrates the complete live research flow.

    This is the canonical integration point for any agent or route that
    needs real-time web intelligence.
    """

    def __init__(self) -> None:
        self._top_k_sources = int(__import__("os").getenv("RESEARCH_TOP_K", "6"))

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        query:      str,
        mission_id: Optional[str] = None,
        agent:      str           = "research",
        force_live: bool          = False,
    ) -> ResearchResult:
        """
        Execute the full research pipeline and return a ResearchResult.

        Parameters
        ----------
        query:      The user's research query.
        mission_id: Associate the result with an ongoing mission (optional).
        agent:      Name of the calling agent — used for audit logging.
        force_live: Always invoke Tavily even if no live-trigger keywords detected.
        """
        execution_id = str(uuid4())
        t0           = time.perf_counter()

        logger.info("Research pipeline start | exec=%s query=%r", execution_id[:8], query[:80])

        # ── 1. Detect search type ────────────────────────────────────
        use_news    = any(kw in query.lower() for kw in _NEWS_TRIGGERS)
        needs_live  = force_live or tavily_client.needs_live_search(query)
        search_type = "news" if use_news else "general"

        if not needs_live and not force_live:
            logger.debug(
                "Query does not trigger live search: %r — using memory only", query[:80]
            )

        # ── 2. Tavily search ─────────────────────────────────────────
        tavily_resp: TavilyResponse
        if needs_live and tavily_client.is_configured():
            try:
                if use_news:
                    tavily_resp = await tavily_client.search_news(query)
                else:
                    tavily_resp = await tavily_client.search(query)
            except Exception as exc:
                logger.error("Tavily search raised: %s", exc)
                tavily_resp = TavilyResponse(
                    query=query, sources=[], answer=None,
                    latency_ms=0.0, search_type=search_type,
                )
        else:
            tavily_resp = TavilyResponse(
                query=query, sources=[], answer=None,
                latency_ms=0.0, search_type=search_type,
            )

        # ── 3. Source ranking ────────────────────────────────────────
        ranked = source_ranker.rank(tavily_resp.sources, top_k=self._top_k_sources)

        # ── 4. Citation list ─────────────────────────────────────────
        citations = citation_engine.build(ranked)
        cite_block = citation_engine.format_for_prompt(citations)

        # ── 5. LLM synthesis ─────────────────────────────────────────
        synthesis = await self._synthesize(query, cite_block)

        # ── 6. Annotate with References section ─────────────────────
        annotated = citation_engine.annotate_response(synthesis, citations)

        latency_ms = (time.perf_counter() - t0) * 1000
        success    = bool(ranked)   # success if at least one source

        # ── 7. Memory store (fire-and-forget) ───────────────────────
        asyncio.ensure_future(
            self._store_memory(query, ranked, synthesis, mission_id)
        )

        # ── 8. Governance audit (fire-and-forget) ────────────────────
        asyncio.ensure_future(
            self._audit(query, agent, execution_id, len(ranked), mission_id)
        )

        # ── 9. Telemetry ─────────────────────────────────────────────
        research_telemetry.record(
            query        = query,
            search_type  = search_type,
            source_count = len(ranked),
            latency_ms   = latency_ms,
            success      = success,
        )

        result = ResearchResult(
            query        = query,
            execution_id = execution_id,
            search_type  = search_type,
            sources      = ranked,
            citations    = [c.to_dict() for c in citations],
            answer       = tavily_resp.answer,
            synthesis    = synthesis,
            annotated    = annotated,
            latency_ms   = latency_ms,
            success      = success,
        )

        logger.info(
            "Research pipeline done | exec=%s sources=%d latency=%.0fms",
            execution_id[:8], len(ranked), latency_ms,
        )
        return result

    # ------------------------------------------------------------------
    # LLM synthesis
    # ------------------------------------------------------------------

    async def _synthesize(self, query: str, cite_block: str) -> str:
        prompt = _SYNTHESIS_PROMPT.format(
            query         = query,
            citation_block = cite_block,
        )
        try:
            from backend.llm.llm_gateway import llm_gateway
            response = await llm_gateway.generate(payload={"prompt": prompt})
            return response.get("content", response) if isinstance(response, dict) else str(response)
        except Exception as exc:
            logger.error("LLM synthesis failed: %s", exc)
            # Fallback: return Tavily direct answer + sources as plain text
            lines = [f"Research results for: {query}\n"]
            lines.append(cite_block)
            return "\n".join(lines)

    # ------------------------------------------------------------------
    # Memory store
    # ------------------------------------------------------------------

    async def _store_memory(
        self,
        query:      str,
        sources:    List[Dict[str, Any]],
        synthesis:  str,
        mission_id: Optional[str],
    ) -> None:
        try:
            from backend.memory.stores.semantic_store import semantic_store

            # Store the query + summary as a semantic memory entry
            top_domains = list({s.get("domain", "") for s in sources[:3]})
            await semantic_store.store(
                concept  = f"research:{query[:120]}",
                content  = synthesis[:2000],
                source   = ", ".join(top_domains) if top_domains else "tavily",
                metadata = {
                    "source_count": len(sources),
                    "mission_id":   mission_id,
                    "type":         "live_research",
                    "top_urls":     [s.get("url", "") for s in sources[:3]],
                },
            )
        except Exception as exc:
            logger.warning("Failed to store research in semantic memory: %s", exc)

    # ------------------------------------------------------------------
    # Governance audit
    # ------------------------------------------------------------------

    async def _audit(
        self,
        query:        str,
        agent:        str,
        execution_id: str,
        source_count: int,
        mission_id:   Optional[str],
    ) -> None:
        try:
            from backend.safety.audit_logger import audit_logger
            audit_logger.log(
                execution_id = execution_id,
                agent        = agent,
                action       = "live_web_search",
                target       = "tavily_api",
                risk_level   = "low",
                outcome      = "allowed",
                reason       = f"Research query: {query[:200]}",
                metadata     = {
                    "query":        query[:200],
                    "source_count": source_count,
                    "mission_id":   mission_id,
                },
            )
        except Exception as exc:
            logger.warning("Failed to write research audit event: %s", exc)


# Singleton
live_research_pipeline = LiveResearchPipeline()
