from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

try:
    from backend.database.repositories.factory import RepositoryFactory
    from backend.database.repositories.factory import repo_factory as _repo_factory
except ImportError:
    _repo_factory = None
from backend.learning.engine import LearningEngine
from backend.learning.events import LearningEventPublisher, learning_event_publisher
from backend.learning.models import (
    LearningContext,
    LearningResult,
    LearningSession,
    Pattern,
)

log = logging.getLogger(__name__)


class LearningService:
    def __init__(
        self,
        engine: Optional[LearningEngine] = None,
        events: Optional[LearningEventPublisher] = None,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._engine = engine or LearningEngine(events=events, repo_factory=repo_factory)
        self._events = events or learning_event_publisher
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start_session(
        self,
        mission_type: str = "general",
        metadata: Optional[dict[str, Any]] = None,
    ) -> LearningSession:
        session = LearningSession(
            id=str(uuid.uuid4()),
            session_id=f"ls-{uuid.uuid4().hex[:12]}",
            mission_type=mission_type,
            status="active",
            metadata=metadata or {},
        )
        return session

    async def run_full_analysis(
        self,
        session: LearningSession,
        context: Optional[LearningContext] = None,
    ) -> LearningResult:
        return await self._engine.run_session(session, context)

    async def analyze_mission(
        self,
        mission_data: dict[str, Any],
    ) -> LearningResult:
        session = await self.start_session(
            mission_type=mission_data.get("mission_type", "mission"),
            metadata={"mission_id": mission_data.get("mission_id", "")},
        )
        return await self._engine.run_mission_analysis(mission_data, session)

    async def analyze_execution(
        self,
        execution_data: dict[str, Any],
    ) -> LearningResult:
        return await self._engine.run_execution_analysis(execution_data)

    async def analyze_connector(
        self,
        connector_data: dict[str, Any],
    ) -> LearningResult:
        return await self._engine.run_connector_analysis(connector_data)

    async def analyze_governance(
        self,
        governance_data: dict[str, Any],
    ) -> LearningResult:
        return await self._engine.run_governance_analysis(governance_data)

    # ------------------------------------------------------------------
    # Pattern queries
    # ------------------------------------------------------------------

    async def list_patterns(
        self,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Pattern]:
        try:
            repo = await self._repo_factory.learning_pattern_repo()
            if category:
                models = await repo.list_by_category(category)
            elif min_confidence > 0:
                models = await repo.list_high_confidence(min_confidence=min_confidence, limit=limit)
            else:
                models = await repo.list(limit=limit, offset=offset)
            return [
                Pattern(
                    id=str(m.id),
                    name=m.name,
                    description=m.description or "",
                    category=m.category,
                    confidence=m.confidence,
                    occurrences=m.occurrences,
                    pattern_data=m.pattern_data or {},
                    is_active=m.is_active,
                    created_at=m.created_at.isoformat() if m.created_at else None,
                    updated_at=m.updated_at.isoformat() if m.updated_at else None,
                )
                for m in models
            ]
        except Exception as exc:
            log.warning("Failed to list patterns: %s", exc)
            return []

    async def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        try:
            repo = await self._repo_factory.learning_pattern_repo()
            model = await repo.get(uuid.UUID(pattern_id))
            if not model:
                return None
            return Pattern(
                id=str(model.id),
                name=model.name,
                description=model.description or "",
                category=model.category,
                confidence=model.confidence,
                occurrences=model.occurrences,
                pattern_data=model.pattern_data or {},
                is_active=model.is_active,
                created_at=model.created_at.isoformat() if model.created_at else None,
                updated_at=model.updated_at.isoformat() if model.updated_at else None,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Session queries
    # ------------------------------------------------------------------

    async def list_sessions(
        self,
        mission_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LearningSession]:
        try:
            repo = await self._repo_factory.learning_session_repo()
            if mission_type:
                models = await repo.list_by_mission_type(mission_type, limit=limit, offset=offset)
            else:
                models = await repo.list(limit=limit, offset=offset)
            return [
                LearningSession(
                    id=str(m.id),
                    session_id=m.session_id,
                    mission_type=m.mission_type,
                    status=m.status,
                    outcome=m.outcome,
                    score=m.score,
                    patterns_extracted=m.patterns_extracted or [],
                    lessons_learned=m.lessons_learned or [],
                    metadata=m.metadata_ or {},
                    created_at=m.created_at.isoformat() if m.created_at else None,
                    updated_at=m.updated_at.isoformat() if m.updated_at else None,
                )
                for m in models
            ]
        except Exception as exc:
            log.warning("Failed to list sessions: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_statistics(self) -> dict[str, Any]:
        try:
            pattern_repo = await self._repo_factory.learning_pattern_repo()
            session_repo = await self._repo_factory.learning_session_repo()
            patterns = await pattern_repo.list(limit=1000)
            sessions = await session_repo.list(limit=1000)
            pattern_categories: dict[str, int] = {}
            for p in patterns:
                pattern_categories[p.category] = pattern_categories.get(p.category, 0) + 1
            return {
                "total_patterns": len(patterns),
                "total_sessions": len(sessions),
                "patterns_by_category": pattern_categories,
                "high_confidence_patterns": len([p for p in patterns if p.confidence >= 0.7]),
                "active_patterns": len([p for p in patterns if p.is_active]),
            }
        except Exception as exc:
            log.warning("Failed to get learning statistics: %s", exc)
            return {
                "total_patterns": 0,
                "total_sessions": 0,
                "patterns_by_category": {},
                "high_confidence_patterns": 0,
                "active_patterns": 0,
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        try:
            stats = await self.get_statistics()
            if stats.get("error"):
                return {
                    "status": "degraded",
                    "error": stats["error"],
                    "service": "learning_runtime",
                }
            return {
                "status": "healthy",
                "total_patterns": stats["total_patterns"],
                "total_sessions": stats["total_sessions"],
                "service": "learning_runtime",
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "error": str(exc),
                "service": "learning_runtime",
            }
