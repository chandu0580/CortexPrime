from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.knowledge.models import KnowledgeQuery, KnowledgeSearchResult
from backend.knowledge.service import KnowledgeService
from backend.mission_intel.models import (
    KnowledgeInsight,
    MissionAnalysis,
)

log = logging.getLogger(__name__)


class KnowledgePlanner:

    def __init__(self, knowledge_service: Optional[KnowledgeService] = None) -> None:
        self._ks = knowledge_service

    async def plan(
        self,
        analysis: MissionAnalysis,
        knowledge_service: Optional[KnowledgeService] = None,
    ) -> KnowledgeInsight:
        ks = knowledge_service or self._ks
        similar_missions: List[Dict[str, Any]] = []
        previous_failures: List[Dict[str, Any]] = []
        best_practices: List[str] = []
        relevant_documents: List[str] = []
        confidence: float = 0.0

        if ks is None:
            return KnowledgeInsight(confidence=0.0)

        try:
            query = KnowledgeQuery(
                query=analysis.goal,
                category=analysis.category,
                tags=analysis.tags,
                limit=5,
                include_relationships=True,
            )
            result: KnowledgeSearchResult = await ks.search(query)
            for entry in result.entries:
                doc_info = {
                    "id": entry.id,
                    "title": entry.title,
                    "summary": entry.summary,
                    "category": entry.category,
                    "confidence": entry.confidence,
                }
                similar_missions.append(doc_info)
                if entry.category == "execution" and entry.confidence < 0.5:
                    previous_failures.append(doc_info)
                if entry.tags:
                    best_practices.extend(entry.tags)
                if entry.title:
                    relevant_documents.append(entry.title)

            confidence = min(0.9, len(similar_missions) * 0.15 + 0.2)
            best_practices = list(set(best_practices))[:5]

        except Exception as exc:
            log.warning("Knowledge planner query failed: %s", exc)
            confidence = 0.0

        return KnowledgeInsight(
            similar_missions=similar_missions,
            previous_failures=previous_failures,
            best_practices=best_practices,
            relevant_documents=relevant_documents,
            confidence=confidence,
        )


knowledge_planner = KnowledgePlanner()
