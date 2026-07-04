"""
Relevance scoring and ranking for memory retrieval results.

Combines:
  - Semantic similarity (from pgvector cosine distance)
  - Recency decay (exponential, half-life configurable)
  - Agent-match boost (same-agent memories are slightly preferred)
"""
from __future__ import annotations

import math
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def recency_score(created_at: datetime, half_life_hours: float = 24.0) -> float:
    """
    Exponential decay score in [0, 1].
    Score = 1.0 at creation, halves every *half_life_hours* hours.
    """
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_h = max((now - created_at).total_seconds() / 3600, 0)
    return math.exp(-0.693 * age_h / half_life_hours)   # 0.693 ≈ ln(2)


class RankingEngine:
    """
    Composite relevance ranker.

    Score formula (weights):
      60% — semantic relevance (pre-computed by pgvector, 0–1)
      30% — recency decay      (1.0 = just created, fades over time)
      10% — same-agent boost   (0.1 if agent matches, else 0)
    """

    def rank(
        self,
        items:         List[Any],          # EpisodicEntry | SemanticEntry | dict
        current_agent: str   = "",
        top_k:         int   = 10,
        half_life_h:   float = 24.0,
    ) -> List[Any]:
        """
        Return the top-k items sorted by composite relevance score.
        Works with any object that has `.relevance`, `.created_at`, `.agent`
        attributes, or a dict with the same keys.
        """
        scored: List[tuple[float, Any]] = []

        for item in items:
            score = self._score(item, current_agent, half_life_h)
            scored.append((score, item))

        scored.sort(key=lambda t: t[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _score(
        self,
        item:          Any,
        current_agent: str,
        half_life_h:   float,
    ) -> float:
        # Semantic relevance (already computed by postgres, range 0-1)
        sem = self._attr(item, "relevance") or 0.0

        # Recency
        created_at = self._attr(item, "created_at")
        rec = recency_score(created_at, half_life_h) if created_at else 0.5

        # Agent boost
        agent       = self._attr(item, "agent") or ""
        agent_boost = 0.1 if (current_agent and agent == current_agent) else 0.0

        return sem * 0.6 + rec * 0.3 + agent_boost

    @staticmethod
    def _attr(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)


ranking_engine = RankingEngine()
