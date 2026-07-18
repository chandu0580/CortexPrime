from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.learning.models import Pattern, Recommendation
from backend.learning.service import LearningService
from backend.mission_intel.models import (
    KnowledgeInsight,
    LearningInsight,
    MissionAnalysis,
)

log = logging.getLogger(__name__)


class LearningPlanner:

    def __init__(self, learning_service: Optional[LearningService] = None) -> None:
        self._ls = learning_service

    async def plan(
        self,
        analysis: MissionAnalysis,
        knowledge_insight: KnowledgeInsight,
        learning_service: Optional[LearningService] = None,
    ) -> LearningInsight:
        ls = learning_service or self._ls
        patterns: List[Dict[str, Any]] = []
        recommendations: List[Dict[str, Any]] = []
        risk_indicators: List[str] = []
        success_rate: Optional[float] = None

        if ls is None:
            return LearningInsight()

        try:
            found_patterns: List[Pattern] = await ls.list_patterns(
                category=analysis.category,
                min_confidence=0.3,
                limit=5,
            )
            for p in found_patterns:
                patterns.append({
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "category": p.category,
                    "confidence": p.confidence,
                    "occurrences": p.occurrences,
                })
                if p.confidence < 0.5:
                    risk_indicators.append(f"Low-confidence pattern '{p.name}'")

            all_sessions = await ls.list_sessions(
                mission_type=analysis.category,
                limit=10,
            )
            completed = [s for s in all_sessions if s.outcome == "success"]
            total = len(all_sessions) or 1
            success_rate = len(completed) / total

            if knowledge_insight.previous_failures:
                risk_indicators.append(
                    f"{len(knowledge_insight.previous_failures)} previous failures found"
                )

            if knowledge_insight.similar_missions and success_rate and success_rate < 0.5:
                risk_indicators.append(
                    f"Historical success rate {success_rate:.0%} is below threshold"
                )

        except Exception as exc:
            log.warning("Learning planner query failed: %s", exc)

        return LearningInsight(
            patterns=patterns,
            recommendations=recommendations,
            risk_indicators=risk_indicators,
            success_rate=success_rate,
        )


learning_planner = LearningPlanner()
