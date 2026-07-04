"""
Source Ranker — scores Tavily results by relevance, recency, and authority.

Scoring formula (0.0–1.0):
  final_score = 0.50 * relevance + 0.30 * recency + 0.20 * authority

  relevance  — Tavily's own score (0–1)
  recency    — exponential decay from published_date; no date → 0.5
  authority  — heuristic from known-authority domain list + HTTPS check
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.research.tavily_client import TavilySource

# ---------------------------------------------------------------------------
# Authority tiers — assign a base score per domain suffix / known domain
# ---------------------------------------------------------------------------

_AUTHORITY_HIGH = frozenset({
    # Academic / preprint
    "arxiv.org", "nature.com", "science.org", "pubmed.ncbi.nlm.nih.gov",
    "scholar.google.com", "semanticscholar.org", "ieee.org", "acm.org",
    # Official / government
    "gov", "edu", "who.int", "un.org",
    # Major tech reference
    "github.com", "stackoverflow.com", "docs.python.org", "developer.mozilla.org",
    "openai.com", "anthropic.com", "deepmind.com", "huggingface.co",
    # Quality news
    "reuters.com", "apnews.com", "bbc.com", "economist.com",
    "techcrunch.com", "wired.com", "arstechnica.com", "theverge.com",
})

_AUTHORITY_MED = frozenset({
    "medium.com", "substack.com", "towardsdatascience.com",
    "hackernoon.com", "dev.to", "zdnet.com", "cnet.com",
})

_AUTHORITY_SCORE = {
    "high": 1.0,
    "med":  0.6,
    "low":  0.3,
}

# Recency decay half-life in days
_HALF_LIFE_DAYS = 30.0

# Weight coefficients
_W_RELEVANCE  = 0.50
_W_RECENCY    = 0.30
_W_AUTHORITY  = 0.20


class SourceRanker:
    """
    Re-ranks a list of TavilySource objects using a weighted multi-factor score.

    Usage::

        ranker  = SourceRanker()
        ranked  = ranker.rank(sources, top_k=5)
    """

    def rank(
        self,
        sources:  List[TavilySource],
        top_k:    int = 8,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Return up to *top_k* scored source dicts, sorted by final_score DESC.

        Each dict adds ``relevance_score``, ``recency_score``,
        ``authority_score``, and ``final_score`` to the raw source fields.
        """
        scored = []
        for src in sources:
            rel   = self._relevance(src)
            rec   = self._recency(src)
            auth  = self._authority(src)
            final = _W_RELEVANCE * rel + _W_RECENCY * rec + _W_AUTHORITY * auth
            if final >= min_score:
                d = src.to_dict()
                d["relevance_score"]  = round(rel,   3)
                d["recency_score"]    = round(rec,   3)
                d["authority_score"]  = round(auth,  3)
                d["final_score"]      = round(final, 3)
                scored.append(d)

        scored.sort(key=lambda x: x["final_score"], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Scoring components
    # ------------------------------------------------------------------

    @staticmethod
    def _relevance(src: TavilySource) -> float:
        """Tavily's own score, clamped to [0, 1]."""
        return max(0.0, min(1.0, float(src.score)))

    @staticmethod
    def _recency(src: TavilySource) -> float:
        """Exponential decay from published_date; unknown date → 0.5."""
        if not src.published:
            return 0.5

        # Try common date formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%B %d, %Y"):
            try:
                pub = datetime.strptime(src.published[:len(fmt)+2].strip(), fmt)
                break
            except ValueError:
                continue
        else:
            # Fallback: try to extract YYYY-MM-DD from the string
            m = re.search(r"(\d{4}-\d{2}-\d{2})", src.published)
            if m:
                try:
                    pub = datetime.strptime(m.group(1), "%Y-%m-%d")
                except ValueError:
                    return 0.5
            else:
                return 0.5

        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if pub.tzinfo:
            pub = pub.replace(tzinfo=None)
        age_days = max(0.0, (now_naive - pub).total_seconds() / 86400.0)
        return math.exp(-age_days / _HALF_LIFE_DAYS)

    @staticmethod
    def _authority(src: TavilySource) -> float:
        """
        Heuristic authority from domain tier list + HTTPS check.
        """
        domain = src.domain.lower()

        # Check high tier
        if domain in _AUTHORITY_HIGH:
            tier = "high"
        elif any(domain.endswith(f".{h}") for h in _AUTHORITY_HIGH):
            tier = "high"
        elif domain.endswith(".gov") or domain.endswith(".edu"):
            tier = "high"
        elif domain in _AUTHORITY_MED:
            tier = "med"
        else:
            tier = "low"

        score = _AUTHORITY_SCORE[tier]

        # Small boost for HTTPS
        if src.url.startswith("https://"):
            score = min(1.0, score + 0.05)

        return score


source_ranker = SourceRanker()
