from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

try:
    from backend.database.repositories.factory import RepositoryFactory
    from backend.database.repositories.factory import repo_factory as _repo_factory
except ImportError:
    _repo_factory = None
from backend.learning.detector import PatternDetector
from backend.learning.events import LearningEvent, LearningEventPublisher, learning_event_publisher
from backend.learning.models import (
    LearningContext,
    LearningResult,
    LearningSession,
    LearningSessionStatus,
    Pattern,
    Recommendation,
)
from backend.learning.recommender import RecommendationEngine

log = logging.getLogger(__name__)


class LearningEngine:
    def __init__(
        self,
        detector: Optional[PatternDetector] = None,
        recommender: Optional[RecommendationEngine] = None,
        events: Optional[LearningEventPublisher] = None,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._detector = detector or PatternDetector(repo_factory=repo_factory)
        self._recommender = recommender or RecommendationEngine()
        self._events = events or learning_event_publisher
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    async def run_session(
        self,
        session: LearningSession,
        context: Optional[LearningContext] = None,
    ) -> LearningResult:
        session_id = session.session_id or f"ls-{uuid.uuid4().hex[:12]}"
        start = time.monotonic()

        await self._events.publish(LearningEvent(
            event_type="learning.session.started",
            session_id=session_id,
            message=f"Learning session started for {session.mission_type or 'all'}",
        ))

        patterns = await self._detect_patterns(session, context)
        recommendations = await self._recommender.generate_all(patterns)

        await self._persist_session(session_id, session, patterns)
        await self._persist_patterns(patterns)
        await self._persist_recommendations(recommendations)

        duration_ms = (time.monotonic() - start) * 1000
        score = self._compute_score(patterns, recommendations)

        await self._events.publish(LearningEvent(
            event_type="learning.completed",
            session_id=session_id,
            message=f"Learning session completed: {len(patterns)} patterns, {len(recommendations)} recommendations",
            payload={
                "patterns_found": len(patterns),
                "recommendations": len(recommendations),
                "score": score,
                "duration_ms": duration_ms,
            },
        ))

        return LearningResult(
            session_id=session_id,
            patterns_found=patterns,
            recommendations=recommendations,
            score=score,
            summary=f"Found {len(patterns)} patterns and generated {len(recommendations)} recommendations in {duration_ms:.0f}ms",
            duration_ms=duration_ms,
        )

    async def run_mission_analysis(
        self,
        mission_data: dict[str, Any],
        session: Optional[LearningSession] = None,
    ) -> LearningResult:
        if not session:
            session = LearningSession(
                session_id=f"ls-{uuid.uuid4().hex[:12]}",
                mission_type=mission_data.get("mission_type", "standard"),
                status=LearningSessionStatus.ACTIVE.value,
                metadata={"mission_id": mission_data.get("mission_id", "")},
            )
        context = LearningContext(
            mission_id=mission_data.get("mission_id"),
            source="mission_runtime",
        )
        result = await self.run_session(session, context)

        mission_recs = await self._recommender.generate_for_mission(mission_data)
        result.recommendations.extend(mission_recs)
        return result

    async def run_execution_analysis(
        self,
        execution_data: dict[str, Any],
    ) -> LearningResult:
        session = LearningSession(
            session_id=f"ls-{uuid.uuid4().hex[:12]}",
            mission_type="execution",
            status=LearningSessionStatus.ACTIVE.value,
            metadata={"execution_id": execution_data.get("execution_id", "")},
        )
        pattern_results = await self._detector.detect_execution_patterns()
        recs = await self._recommender.generate_for_execution(execution_data)

        result = LearningResult(
            session_id=session.session_id,
            patterns_found=pattern_results,
            recommendations=recs,
            summary=f"Found {len(pattern_results)} execution patterns, {len(recs)} recommendations",
        )
        return result

    async def run_connector_analysis(
        self,
        connector_data: dict[str, Any],
    ) -> LearningResult:
        session = LearningSession(
            session_id=f"ls-{uuid.uuid4().hex[:12]}",
            mission_type="connector",
            status=LearningSessionStatus.ACTIVE.value,
            metadata={"connector_id": connector_data.get("connector_id", "")},
        )
        pattern_results = await self._detector.detect_connector_patterns()
        recs = await self._recommender.generate_for_connector(connector_data)

        return LearningResult(
            session_id=session.session_id,
            patterns_found=pattern_results,
            recommendations=recs,
            summary=f"Found {len(pattern_results)} connector patterns, {len(recs)} recommendations",
        )

    async def run_governance_analysis(
        self,
        governance_data: dict[str, Any],
    ) -> LearningResult:
        pattern_results = await self._detector.detect_governance_patterns()
        recs = await self._recommender.generate_for_governance(governance_data)

        return LearningResult(
            session_id=f"ls-{uuid.uuid4().hex[:12]}",
            patterns_found=pattern_results,
            recommendations=recs,
            summary=f"Found {len(pattern_results)} governance patterns, {len(recs)} recommendations",
        )

    async def _detect_patterns(
        self,
        session: LearningSession,
        context: Optional[LearningContext],
    ) -> list[Pattern]:
        if context and context.source == "mission_runtime":
            return await self._detector.detect_mission_patterns()
        return await self._detector.detect_all()

    async def _persist_session(
        self,
        session_id: str,
        session: LearningSession,
        patterns: list[Pattern],
    ) -> None:
        try:
            from backend.database.repositories.learning import LearningSessionModel
            repo = await self._repo_factory.learning_session_repo()
            model = LearningSessionModel(
                id=uuid.uuid4(),
                session_id=session_id,
                mission_type=session.mission_type or "general",
                status=LearningSessionStatus.COMPLETED.value,
                outcome="completed",
                score=self._compute_score(patterns, []),
                patterns_extracted=[p.__dict__ for p in patterns],
                lessons_learned=[],
                metadata_=session.metadata,
            )
            await repo.create(model)
        except Exception as exc:
            log.warning("Failed to persist learning session: %s", exc)

    async def _persist_patterns(self, patterns: list[Pattern]) -> None:
        try:
            from backend.database.repositories.learning import LearningPatternModel
            repo = await self._repo_factory.learning_pattern_repo()
            for p in patterns:
                model = LearningPatternModel(
                    id=uuid.uuid4(),
                    name=p.name,
                    description=p.description,
                    category=p.category,
                    confidence=p.confidence,
                    occurrences=p.occurrences,
                    pattern_data=p.pattern_data,
                    is_active=True,
                )
                await repo.create(model)
                await self._events.publish(LearningEvent(
                    event_type="learning.pattern.detected",
                    session_id="",
                    pattern_id=str(model.id),
                    pattern_name=p.name,
                    category=p.category,
                    message=f"Pattern detected: {p.name}",
                ))
        except Exception as exc:
            log.warning("Failed to persist pattern: %s", exc)

    async def _persist_recommendations(self, recommendations: list[Recommendation]) -> None:
        for rec in recommendations:
            await self._events.publish(LearningEvent(
                event_type="learning.recommendation.created",
                session_id="",
                recommendation_id=rec.id or str(uuid.uuid4()),
                category=rec.category,
                message=f"Recommendation: {rec.title}",
            ))

    def _compute_score(
        self,
        patterns: list[Pattern],
        recommendations: list[Recommendation],
    ) -> float:
        if not patterns and not recommendations:
            return 0.0
        avg_confidence = 0.0
        if patterns:
            avg_confidence = sum(p.confidence for p in patterns) / len(patterns)
        rec_weight = len(recommendations) / max(len(patterns) + len(recommendations), 1)
        return round((avg_confidence * 0.7 + rec_weight * 0.3), 2)
