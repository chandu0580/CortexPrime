"""
Tavily Search Client — CortexPrime Live Research Runtime.

Wraps the Tavily REST API with:
  - search()         — general web search
  - search_news()    — news-focused search (recency-biased)
  - search_domain()  — restrict to one or more domains
  - get_answer()     — single-sentence direct answer

Every method is async and returns a normalised TavilyResponse dict so
callers never have to touch raw Tavily shapes.

Configuration (backend/.env):
  TAVILY_API_KEY          — required
  TAVILY_MAX_RESULTS      — default 8
  TAVILY_SEARCH_TIMEOUT   — seconds, default 30
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_API_BASE      = "https://api.tavily.com"
_SEARCH_URL    = f"{_API_BASE}/search"

LIVE_TRIGGERS  = frozenset({
    "latest", "today", "current", "news", "recent", "research",
    "compare", "comparison", "vs", "versus", "2024", "2025", "2026",
    "breaking", "update", "now", "live",
})


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class TavilySource:
    title:     str
    url:       str
    snippet:   str
    score:     float
    published: Optional[str] = None
    domain:    str            = field(default="", init=False)

    def __post_init__(self) -> None:
        try:
            from urllib.parse import urlparse
            self.domain = urlparse(self.url).netloc.lstrip("www.")
        except Exception:
            self.domain = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title":     self.title,
            "url":       self.url,
            "snippet":   self.snippet,
            "score":     self.score,
            "published": self.published,
            "domain":    self.domain,
        }


@dataclass
class TavilyResponse:
    query:      str
    sources:    List[TavilySource]
    answer:     Optional[str]
    latency_ms: float
    search_type: str

    @property
    def source_count(self) -> int:
        return len(self.sources)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query":        self.query,
            "answer":       self.answer,
            "sources":      [s.to_dict() for s in self.sources],
            "source_count": self.source_count,
            "latency_ms":   self.latency_ms,
            "search_type":  self.search_type,
        }


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class TavilyClient:
    """
    Async Tavily search client with per-call telemetry and graceful error
    handling.  Falls back to an empty result set on API errors so that the
    research pipeline can still synthesise from memory context.
    """

    def __init__(self) -> None:
        self.api_key     = os.getenv("TAVILY_API_KEY", "")
        self.max_results = int(os.getenv("TAVILY_MAX_RESULTS", "8"))
        self.timeout     = float(os.getenv("TAVILY_SEARCH_TIMEOUT", "30"))

        if not self.api_key:
            logger.warning(
                "TAVILY_API_KEY not set — live search will not function. "
                "Set TAVILY_API_KEY in backend/.env to enable live research."
            )

    # ------------------------------------------------------------------
    # Public search methods
    # ------------------------------------------------------------------

    async def search(
        self,
        query:       str,
        max_results: Optional[int]  = None,
        search_depth: str           = "advanced",
    ) -> TavilyResponse:
        """General web search, comprehensive depth."""
        return await self._call(
            query        = query,
            search_depth = search_depth,
            topic        = "general",
            max_results  = max_results or self.max_results,
            search_type  = "general",
        )

    async def search_news(
        self,
        query:       str,
        max_results: Optional[int] = None,
        days:        int           = 7,
    ) -> TavilyResponse:
        """News-focused search, recent articles prioritised."""
        return await self._call(
            query        = query,
            search_depth = "basic",
            topic        = "news",
            max_results  = max_results or self.max_results,
            search_type  = "news",
            days         = days,
        )

    async def search_domain(
        self,
        query:         str,
        include_domains: List[str],
        max_results:   Optional[int] = None,
    ) -> TavilyResponse:
        """Restrict search to specific domains (e.g. arxiv.org, github.com)."""
        return await self._call(
            query           = query,
            search_depth    = "advanced",
            topic           = "general",
            max_results     = max_results or self.max_results,
            include_domains = include_domains,
            search_type     = "domain",
        )

    async def get_answer(self, query: str) -> str:
        """Return a single direct-answer string, or empty string on failure."""
        resp = await self.search(query, max_results=3, search_depth="basic")
        return resp.answer or ""

    # ------------------------------------------------------------------
    # Live-trigger detection
    # ------------------------------------------------------------------

    @staticmethod
    def needs_live_search(query: str) -> bool:
        """
        Return True if the query contains keywords that indicate the user
        needs current / real-time information and cannot be satisfied by
        static memory alone.

        Uses substring containment so multi-word phrases like "today's" and
        partial matches like "latest" are caught reliably.
        """
        q = query.lower()
        return any(kw in q for kw in LIVE_TRIGGERS)

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _call(
        self,
        query:           str,
        search_depth:    str           = "advanced",
        topic:           str           = "general",
        max_results:     int           = 8,
        include_domains: List[str]     = (),
        search_type:     str           = "general",
        days:            Optional[int] = None,
    ) -> TavilyResponse:
        if not self.api_key:
            logger.error("Tavily search called but TAVILY_API_KEY is not set")
            return TavilyResponse(
                query        = query,
                sources      = [],
                answer       = None,
                latency_ms   = 0.0,
                search_type  = search_type,
            )

        payload: Dict[str, Any] = {
            "api_key":              self.api_key,
            "query":                query,
            "search_depth":         search_depth,
            "topic":                topic,
            "max_results":          max_results,
            "include_answer":       True,
            "include_raw_content":  False,
            "include_images":       False,
        }
        if include_domains:
            payload["include_domains"] = list(include_domains)
        if days is not None:
            payload["days"] = days

        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                resp = await http.post(_SEARCH_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Tavily API returned HTTP %d for query=%r: %s",
                exc.response.status_code, query[:80], exc.response.text[:200],
            )
            return TavilyResponse(
                query=query, sources=[], answer=None,
                latency_ms=0.0, search_type=search_type,
            )
        except Exception as exc:
            logger.error("Tavily search failed for query=%r: %s", query[:80], exc)
            return TavilyResponse(
                query=query, sources=[], answer=None,
                latency_ms=0.0, search_type=search_type,
            )

        latency_ms = (time.perf_counter() - t0) * 1000

        sources = [
            TavilySource(
                title     = r.get("title", ""),
                url       = r.get("url", ""),
                snippet   = r.get("content", ""),
                score     = float(r.get("score", 0.5)),
                published = r.get("published_date"),
            )
            for r in data.get("results", [])
        ]

        logger.info(
            "Tavily %s | query=%r | sources=%d | latency=%.0fms",
            search_type, query[:60], len(sources), latency_ms,
        )

        return TavilyResponse(
            query        = query,
            sources      = sources,
            answer       = data.get("answer"),
            latency_ms   = latency_ms,
            search_type  = search_type,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

tavily_client = TavilyClient()
