"""
Enterprise Learning Engine — active learning from every enterprise event.

Subscribes to EventBus and extracts:
  - Lessons learned from mission outcomes, failures, recoveries, approvals
  - Best practices from successful execution patterns
  - Failure patterns clustered by error type, connector, operation
  - Recovery patterns ranked by effectiveness
  - Recommendations synthesised from accumulated intelligence

All knowledge is persisted to semantic memory (PostgreSQL + pgvector)
for long-term retention and similarity search.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.events.enterprise_event_types import EnterpriseEventTypes as EET
from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent
from backend.memory.memory_orchestrator import memory_orchestrator
from backend.memory.stores.semantic_store import semantic_store

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LESSON_CONCEPT_PREFIX     = "lesson"
_BEST_PRACTICE_PREFIX      = "best_practice"
_FAILURE_PATTERN_PREFIX    = "failure_pattern"
_RECOVERY_PATTERN_PREFIX   = "recovery_pattern"
_RECOMMENDATION_PREFIX     = "recommendation"


def _concept(*parts: str) -> str:
    return ":".join(parts)


# ---------------------------------------------------------------------------
# Learning Engine
# ---------------------------------------------------------------------------

class EnterpriseLearningEngine:
    """
    Continuous learning engine that improves from every mission event.

    Two data paths:
      1. Event-driven — _on_event processes every EventBus message in real time
      2. On-demand    — analyze_mission() / analyze_all() for bulk analysis
    """

    def __init__(self) -> None:
        self._initialized = False

        # In-memory aggregators (fast dashboard queries)
        self._lessons:        List[Dict[str, Any]] = []
        self._best_practices: List[Dict[str, Any]] = []
        self._failure_patterns: Dict[str, Dict[str, Any]] = {}
        self._recovery_patterns: Dict[str, Dict[str, Any]] = {}
        self._recommendations: List[Dict[str, Any]] = []

        # Event tracking for deduplication
        self._processed_events: set[str] = set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Subscribe to EventBus and load persisted intelligence."""
        if self._initialized:
            return
        event_bus.subscribe(self._on_event)
        await self._load_persisted()
        self._initialized = True
        log.info("EnterpriseLearningEngine initialized — subscribed to EventBus")

    async def _load_persisted(self) -> None:
        """Load existing lessons/patterns/recommendations from semantic memory."""
        try:
            # Load recent lessons
            rows = await semantic_store.get_by_concept(_LESSON_CONCEPT_PREFIX, limit=200)
            for r in rows:
                self._lessons.append({
                    "id": r.id,
                    "concept": r.concept,
                    "content": r.content,
                    "source": r.source,
                    "confidence": r.confidence,
                    "metadata": r.metadata,
                    "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
                })

            # Load best practices
            rows = await semantic_store.get_by_concept(_BEST_PRACTICE_PREFIX, limit=100)
            for r in rows:
                self._best_practices.append({
                    "id": r.id,
                    "concept": r.concept,
                    "content": r.content,
                    "source": r.source,
                    "confidence": r.confidence,
                    "metadata": r.metadata,
                    "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
                })

            # Load failure patterns
            rows = await semantic_store.get_by_concept(_FAILURE_PATTERN_PREFIX, limit=100)
            for r in rows:
                sig = r.concept.split(":", 1)[1] if ":" in r.concept else r.concept
                self._failure_patterns[sig] = {
                    "id": r.id,
                    "signature": sig,
                    "content": r.content,
                    "confidence": r.confidence,
                    "metadata": r.metadata,
                    "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
                }

            # Load recovery patterns
            rows = await semantic_store.get_by_concept(_RECOVERY_PATTERN_PREFIX, limit=50)
            for r in rows:
                rt = r.concept.split(":", 1)[1] if ":" in r.concept else r.concept
                self._recovery_patterns[rt] = {
                    "id": r.id,
                    "recovery_type": rt,
                    "content": r.content,
                    "confidence": r.confidence,
                    "metadata": r.metadata,
                    "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
                }

            # Load recommendations
            rows = await semantic_store.get_by_concept(_RECOMMENDATION_PREFIX, limit=50)
            for r in rows:
                self._recommendations.append({
                    "id": r.id,
                    "concept": r.concept,
                    "content": r.content,
                    "source": r.source,
                    "confidence": r.confidence,
                    "metadata": r.metadata,
                    "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
                })

            log.info(
                "Loaded %d lessons, %d best practices, %d failure patterns, "
                "%d recovery patterns, %d recommendations",
                len(self._lessons), len(self._best_practices),
                len(self._failure_patterns), len(self._recovery_patterns),
                len(self._recommendations),
            )
        except Exception as exc:
            log.warning("Failed to load persisted intelligence: %s", exc)

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    async def _on_event(self, event: CognitionEvent) -> None:
        """Process incoming enterprise events for learning extraction."""
        event_type = event.event_type or ""
        event_id = event.event_id or ""

        if event_id and event_id in self._processed_events:
            return
        if event_id:
            self._processed_events.add(event_id)
        if len(self._processed_events) > 100000:
            self._processed_events.clear()

        try:
            # Mission lifecycle events
            if event_type == EET.MISSION_COMPLETED:
                await self._extract_lesson_from_success(event)
            elif event_type == EET.MISSION_FAILED:
                await self._extract_lessons_from_failure(event)

            # Step-level events
            elif event_type == EET.MISSION_STEP:
                await self._extract_step_lesson(event)

            # Connector events
            elif event_type == EET.CONNECTOR_ACTION_FAILED:
                await self._extract_connector_failure_pattern(event)

            # Recovery events
            elif event_type in (EET.RECOVERY_RETRY, EET.RECOVERY_FALLBACK,
                                EET.RECOVERY_ROLLBACK, EET.RECOVERY_ESCALATION):
                await self._track_recovery(event, event_type)

            # Approval events
            elif event_type in (EET.APPROVAL_GRANTED, EET.APPROVAL_REJECTED):
                await self._extract_governance_lesson(event)

            # Verification events
            elif event_type in (EET.VERIFICATION_COMPLETED, EET.VERIFICATION_FAILED):
                await self._extract_verification_lesson(event)

        except Exception as exc:
            log.debug("Learning engine event processing error: %s", exc)

    # ------------------------------------------------------------------
    # Lesson extraction — Success
    # ------------------------------------------------------------------

    async def _extract_lesson_from_success(self, event: CognitionEvent) -> None:
        """Extract a positive lesson from a completed mission."""
        payload = event.payload or {}
        execution_id = event.execution_id or payload.get("execution_id", "unknown")
        template = payload.get("template", payload.get("agent", "unknown"))
        step_count = payload.get("step_count", 0)

        str(uuid4())
        content = (
            f"Mission completed successfully using template '{template}' "
            f"({step_count} steps, execution {execution_id}). "
            f"The execution strategy was effective and can be reused."
        )

        meta = {
            "execution_id": execution_id,
            "template": template,
            "step_count": step_count,
            "domain": "mission",
            "outcome": "success",
            "lesson_type": "success_pattern",
        }

        mem_id = await memory_orchestrator.store_semantic_knowledge(
            concept=_concept(_LESSON_CONCEPT_PREFIX, "mission", "success"),
            content=content,
            agent="enterprise_learning",
            source=f"mission:{execution_id}",
            confidence=0.8,
            metadata=meta,
        )

        entry = {
            "id": mem_id,
            "concept": _concept(_LESSON_CONCEPT_PREFIX, "mission", "success"),
            "content": content,
            "source": f"mission:{execution_id}",
            "confidence": 0.8,
            "metadata": meta,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._lessons.append(entry)
        if len(self._lessons) > 500:
            self._lessons = self._lessons[-500:]

    async def _extract_lessons_from_failure(self, event: CognitionEvent) -> None:
        """Extract lessons from a mission failure."""
        payload = event.payload or {}
        execution_id = event.execution_id or payload.get("execution_id", "unknown")
        error = payload.get("error", event.message or "Unknown error")
        template = payload.get("template", payload.get("agent", "unknown"))
        step_count = payload.get("step_count", 0)

        str(uuid4())
        content = (
            f"Mission failed using template '{template}': {error}. "
            f"Execution {execution_id} encountered failure after {step_count} steps."
        )

        meta = {
            "execution_id": execution_id,
            "template": template,
            "error": error,
            "step_count": step_count,
            "domain": "mission",
            "outcome": "failure",
            "lesson_type": "failure_analysis",
        }

        mem_id = await memory_orchestrator.store_semantic_knowledge(
            concept=_concept(_LESSON_CONCEPT_PREFIX, "mission", "failure"),
            content=content,
            agent="enterprise_learning",
            source=f"mission:{execution_id}",
            confidence=0.9,
            metadata=meta,
        )

        entry = {
            "id": mem_id,
            "concept": _concept(_LESSON_CONCEPT_PREFIX, "mission", "failure"),
            "content": content,
            "source": f"mission:{execution_id}",
            "confidence": 0.9,
            "metadata": meta,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._lessons.append(entry)
        if len(self._lessons) > 500:
            self._lessons = self._lessons[-500:]

        # Also extract failure pattern
        error_sig = self._normalize_error(error)
        await self._upsert_failure_pattern(error_sig, template, error, execution_id)

    async def _extract_step_lesson(self, event: CognitionEvent) -> None:
        """Extract a lesson from a completed step."""
        payload = event.payload or {}
        execution_id = event.execution_id or payload.get("execution_id", "unknown")
        connector = payload.get("connector", "unknown")
        operation = payload.get("operation", "unknown")
        description = payload.get("description", "Step completed")

        meta = {
            "execution_id": execution_id,
            "connector": connector,
            "operation": operation,
            "domain": "mission",
            "lesson_type": "step_pattern",
        }

        await memory_orchestrator.store_semantic_knowledge(
            concept=_concept(_LESSON_CONCEPT_PREFIX, "step", connector, operation),
            content=f"Step execution pattern: {connector}.{operation} — {description} (mission {execution_id})",
            agent="enterprise_learning",
            source=f"mission:{execution_id}",
            confidence=0.6,
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # Failure pattern extraction
    # ------------------------------------------------------------------

    async def _extract_connector_failure_pattern(self, event: CognitionEvent) -> None:
        """Track a connector action failure."""
        payload = event.payload or {}
        execution_id = event.execution_id or payload.get("execution_id", "unknown")
        connector = payload.get("connector", "unknown")
        operation = payload.get("operation", "unknown")
        error = payload.get("error", event.message or "Connector action failed")

        error_sig = self._normalize_error(f"{connector}.{operation}: {error}")
        await self._upsert_failure_pattern(error_sig, connector, error, execution_id, operation)

    async def _upsert_failure_pattern(
        self,
        signature: str,
        source_type: str,
        error: str,
        execution_id: str,
        operation: str = "unknown",
    ) -> None:
        """Create or update a failure pattern entry."""
        existing = self._failure_patterns.get(signature)
        if existing:
            meta = existing.get("metadata", {})
            count = meta.get("count", 1) + 1
            execution_ids = meta.get("execution_ids", [])
            if execution_id not in execution_ids:
                execution_ids.append(execution_id)
            if len(execution_ids) > 20:
                execution_ids = execution_ids[-20:]
            meta["count"] = count
            meta["execution_ids"] = execution_ids
            meta["last_seen"] = datetime.now(timezone.utc).isoformat()

            existing["confidence"] = min(0.95, existing.get("confidence", 0.5) + 0.05)
            existing["metadata"] = meta
            existing["content"] = (
                f"Failure pattern '{signature}' occurred {count} time(s), "
                f"last seen on {source_type}. Recent executions: {len(execution_ids)}"
            )

            await memory_orchestrator.store_semantic_knowledge(
                concept=_concept(_FAILURE_PATTERN_PREFIX, signature),
                content=existing["content"],
                agent="enterprise_learning",
                source=f"aggregated:{signature}",
                confidence=existing["confidence"],
                metadata=meta,
            )
        else:
            meta: Dict[str, Any] = {
                "count": 1,
                "error": error,
                "source_type": source_type,
                "operation": operation,
                "execution_ids": [execution_id],
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "domain": "failure_pattern",
            }

            content = (
                f"Failure pattern detected: '{signature}' on {source_type}.{operation}. "
                f"First observed in mission {execution_id}."
            )

            mem_id = await memory_orchestrator.store_semantic_knowledge(
                concept=_concept(_FAILURE_PATTERN_PREFIX, signature),
                content=content,
                agent="enterprise_learning",
                source=f"mission:{execution_id}",
                confidence=0.5,
                metadata=meta,
            )

            self._failure_patterns[signature] = {
                "id": mem_id,
                "signature": signature,
                "content": content,
                "confidence": 0.5,
                "metadata": meta,
                "created_at": meta["first_seen"],
            }

    # ------------------------------------------------------------------
    # Recovery tracking
    # ------------------------------------------------------------------

    async def _track_recovery(self, event: CognitionEvent, event_type: str) -> None:
        """Track recovery strategy usage and effectiveness."""
        payload = event.payload or {}
        recovery_type = payload.get("recovery_type") or event_type.split(".")[-1]
        execution_id = event.execution_id or payload.get("execution_id", "unknown")

        recovery_map = {
            EET.RECOVERY_RETRY: "retry",
            EET.RECOVERY_FALLBACK: "fallback",
            EET.RECOVERY_ROLLBACK: "rollback",
            EET.RECOVERY_ESCALATION: "escalation",
        }
        rt = recovery_map.get(event_type, recovery_type)

        existing = self._recovery_patterns.get(rt)
        if existing:
            meta = existing.get("metadata", {})
            count = meta.get("count", 1) + 1
            meta["count"] = count
            meta["last_used"] = datetime.now(timezone.utc).isoformat()

            existing["confidence"] = min(0.95, existing.get("confidence", 0.5) + 0.02)
            existing["metadata"] = meta
            existing["content"] = (
                f"Recovery strategy '{rt}' used {count} time(s). "
                f"Last triggered by mission {execution_id}."
            )

            await memory_orchestrator.store_semantic_knowledge(
                concept=_concept(_RECOVERY_PATTERN_PREFIX, rt),
                content=existing["content"],
                agent="enterprise_learning",
                source=f"aggregated:{rt}",
                confidence=existing["confidence"],
                metadata=meta,
            )
        else:
            meta: Dict[str, Any] = {
                "count": 1,
                "execution_ids": [execution_id],
                "first_used": datetime.now(timezone.utc).isoformat(),
                "last_used": datetime.now(timezone.utc).isoformat(),
                "domain": "recovery_pattern",
            }

            content = (
                f"Recovery strategy '{rt}' used for the first time on mission {execution_id}. "
                f"This strategy attempts to resolve execution failures."
            )

            mem_id = await memory_orchestrator.store_semantic_knowledge(
                concept=_concept(_RECOVERY_PATTERN_PREFIX, rt),
                content=content,
                agent="enterprise_learning",
                source=f"mission:{execution_id}",
                confidence=0.5,
                metadata=meta,
            )

            self._recovery_patterns[rt] = {
                "id": mem_id,
                "recovery_type": rt,
                "content": content,
                "confidence": 0.5,
                "metadata": meta,
                "created_at": meta["first_used"],
            }

    # ------------------------------------------------------------------
    # Governance lesson extraction
    # ------------------------------------------------------------------

    async def _extract_governance_lesson(self, event: CognitionEvent) -> None:
        """Extract lesson from approval/rejection events."""
        payload = event.payload or {}
        execution_id = event.execution_id or payload.get("execution_id", "unknown")
        decision = payload.get("decision", "unknown")
        reason = payload.get("reason", event.message or "No reason provided")
        is_approved = event.event_type == EET.APPROVAL_GRANTED

        lesson_type = "approval" if is_approved else "rejection"

        meta = {
            "execution_id": execution_id,
            "decision": decision,
            "reason": reason,
            "domain": "governance",
            "lesson_type": lesson_type,
        }

        content = (
            f"Governance lesson: Approval was {'granted' if is_approved else 'rejected'} "
            f"for mission {execution_id}. Reason: {reason}"
        )

        await memory_orchestrator.store_semantic_knowledge(
            concept=_concept(_LESSON_CONCEPT_PREFIX, "governance", lesson_type),
            content=content,
            agent="enterprise_learning",
            source=f"mission:{execution_id}",
            confidence=0.7,
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # Verification lesson extraction
    # ------------------------------------------------------------------

    async def _extract_verification_lesson(self, event: CognitionEvent) -> None:
        """Extract lesson from verification results."""
        payload = event.payload or {}
        execution_id = event.execution_id or payload.get("execution_id", "unknown")
        verified = payload.get("verified", False)
        connector = payload.get("connector", "unknown")
        operation = payload.get("operation", "unknown")

        meta = {
            "execution_id": execution_id,
            "connector": connector,
            "operation": operation,
            "verified": verified,
            "domain": "verification",
            "lesson_type": "verification",
        }

        outcome = "passed" if verified else "failed"
        content = (
            f"Verification {outcome} for {connector}.{operation} "
            f"on mission {execution_id}."
        )

        await memory_orchestrator.store_semantic_knowledge(
            concept=_concept(_LESSON_CONCEPT_PREFIX, "verification", outcome),
            content=content,
            agent="enterprise_learning",
            source=f"mission:{execution_id}",
            confidence=0.7 if verified else 0.9,
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # On-demand analysis
    # ------------------------------------------------------------------

    async def analyze_mission(self, execution_id: str) -> Dict[str, Any]:
        """Analyze a specific mission by looking up its events and generating lessons."""
        try:
            from backend.services.mission_replay_store import replay_store
            events = await replay_store.get_events(execution_id)
        except Exception:
            events = []

        if not events:
            return {"execution_id": execution_id, "lessons_generated": 0, "status": "no_events_found"}

        lessons_generated = 0
        for ev in events:
            if isinstance(ev, dict):
                event_type = ev.get("event_type", "")
                if event_type in (EET.MISSION_COMPLETED, EET.MISSION_FAILED,
                                  EET.CONNECTOR_ACTION_FAILED):
                    cognition_event = CognitionEvent(
                        agent=ev.get("agent", "system"),
                        event_type=event_type,
                        status=ev.get("status", "info"),
                        message=ev.get("message", ""),
                        execution_id=execution_id,
                        payload=ev.get("payload", {}),
                    )
                    await self._on_event(cognition_event)
                    lessons_generated += 1

        return {
            "execution_id": execution_id,
            "lessons_generated": lessons_generated,
            "status": "completed",
        }

    async def analyze_all(self, limit: int = 50) -> Dict[str, Any]:
        """Analyze recent missions that haven't been processed yet."""
        try:
            from backend.services.mission_replay_store import replay_store
            all_events = await replay_store.get_recent(limit=limit * 5)
        except Exception:
            all_events = []

        if not all_events:
            return {"analyzed": 0, "status": "no_events_found"}

        execution_ids: set[str] = set()
        for ev in all_events:
            if isinstance(ev, dict):
                eid = ev.get("execution_id") or ev.get("payload", {}).get("execution_id")
                if eid:
                    execution_ids.add(str(eid))

        results = []
        for eid in list(execution_ids)[:limit]:
            result = await self.analyze_mission(eid)
            results.append(result)

        return {
            "analyzed": len(results),
            "status": "completed",
            "execution_ids": [r["execution_id"] for r in results],
        }

    # ------------------------------------------------------------------
    # Recommendation generation
    # ------------------------------------------------------------------

    async def generate_recommendations(self) -> int:
        """Synthesize recommendations from accumulated intelligence."""
        count = 0

        # 1. Recommendations from failure patterns
        for sig, pattern in sorted(
            self._failure_patterns.items(),
            key=lambda x: x[1].get("metadata", {}).get("count", 0),
            reverse=True,
        ):
            meta = pattern.get("metadata", {})
            freq = meta.get("count", 1)
            source = meta.get("source_type", "unknown")
            error = meta.get("error", "unknown")

            priority = "high" if freq >= 5 else ("medium" if freq >= 2 else "low")
            content = (
                f"RECOMMENDATION: The failure pattern '{sig}' has occurred {freq} time(s) "
                f"on {source}. Error: {error}. "
                f"{'Immediate attention recommended.' if priority == 'high' else 'Monitor and address proactively.'}"
            )

            existing_recommendation = None
            for r in self._recommendations:
                if r.get("metadata", {}).get("pattern_signature") == sig:
                    existing_recommendation = r
                    break

            if existing_recommendation:
                existing_recommendation["content"] = content
                existing_recommendation["confidence"] = min(0.95, existing_recommendation.get("confidence", 0.5) + 0.05)
            else:
                mem_id = await memory_orchestrator.store_semantic_knowledge(
                    concept=_concept(_RECOMMENDATION_PREFIX, priority),
                    content=content,
                    agent="enterprise_learning",
                    source=f"recommendation:{sig}",
                    confidence=0.6,
                    metadata={
                        "priority": priority,
                        "pattern_signature": sig,
                        "frequency": freq,
                        "domain": "failure",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                self._recommendations.append({
                    "id": mem_id,
                    "concept": _concept(_RECOMMENDATION_PREFIX, priority),
                    "content": content,
                    "source": f"recommendation:{sig}",
                    "confidence": 0.6,
                    "metadata": {
                        "priority": priority,
                        "pattern_signature": sig,
                    },
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                count += 1

        # 2. Recommendations from frequent recoveries
        for rt, pattern in self._recovery_patterns.items():
            meta_p = pattern.get("metadata", {})
            freq = meta_p.get("count", 1)
            if freq >= 3:
                content = (
                    f"RECOMMENDATION: Recovery strategy '{rt}' has been used {freq} time(s). "
                    f"Consider reviewing the reliability of contributing connectors or operations."
                )
                self._recommendations.append({
                    "id": str(uuid4()),
                    "concept": _concept(_RECOMMENDATION_PREFIX, "medium"),
                    "content": content,
                    "source": f"recommendation:recovery:{rt}",
                    "confidence": 0.5,
                    "metadata": {
                        "priority": "medium",
                        "recovery_type": rt,
                        "frequency": freq,
                        "domain": "recovery",
                    },
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                count += 1

        # Trim to last 100
        if len(self._recommendations) > 100:
            self._recommendations = self._recommendations[-100:]

        return count

    # ------------------------------------------------------------------
    # Dashboard / Query methods
    # ------------------------------------------------------------------

    async def get_dashboard(self) -> Dict[str, Any]:
        """Return aggregated dashboard data for the learning UI."""
        total_lessons = len(self._lessons)
        total_failure_patterns = len(self._failure_patterns)
        total_recovery_patterns = len(self._recovery_patterns)
        total_recommendations = len(self._recommendations)

        success_lessons = sum(
            1 for lesson in self._lessons
            if lesson.get("metadata", {}).get("outcome") == "success"
        )
        failure_lessons = sum(
            1 for lesson in self._lessons
            if lesson.get("metadata", {}).get("outcome") == "failure"
        )

        # Sort failure patterns by frequency
        sorted(
            self._failure_patterns.values(),
            key=lambda x: x.get("metadata", {}).get("count", 0),
            reverse=True,
        )

        # Recovery stats
        recovery_stats = {
            rt: {
                "count": p.get("metadata", {}).get("count", 0),
                "last_used": p.get("metadata", {}).get("last_used", ""),
            }
            for rt, p in self._recovery_patterns.items()
        }

        return {
            "summary": {
                "total_lessons": total_lessons,
                "success_lessons": success_lessons,
                "failure_lessons": failure_lessons,
                "total_failure_patterns": total_failure_patterns,
                "total_recovery_patterns": total_recovery_patterns,
                "total_recommendations": total_recommendations,
            },
            "recovery_stats": recovery_stats,
            "top_failure_patterns": [
                {
                    "signature": p.get("signature", sig),
                    "count": p.get("metadata", {}).get("count", 1),
                    "error": p.get("metadata", {}).get("error", ""),
                    "source": p.get("metadata", {}).get("source_type", ""),
                }
                for sig, p in sorted(
                    self._failure_patterns.items(),
                    key=lambda x: x[1].get("metadata", {}).get("count", 0),
                    reverse=True,
                )[:10]
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_lessons(
        self,
        limit: int = 50,
        domain: Optional[str] = None,
        lesson_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get lessons with optional filtering."""
        results = list(self._lessons)
        if domain:
            results = [lesson for lesson in results if lesson.get("metadata", {}).get("domain") == domain]
        if lesson_type:
            results = [lesson for lesson in results if lesson.get("metadata", {}).get("lesson_type") == lesson_type]
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    async def get_best_practices(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get discovered best practices."""
        practices = list(self._best_practices)
        practices.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return practices[:limit]

    async def recommend(self, limit: int = 20, priority: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recommendations, optionally filtered by priority."""
        results = list(self._recommendations)
        if priority:
            results = [r for r in results if r.get("metadata", {}).get("priority") == priority]
        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return results[:limit]

    async def get_failure_patterns(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get failure patterns sorted by frequency."""
        patterns = sorted(
            self._failure_patterns.values(),
            key=lambda x: x.get("metadata", {}).get("count", 0),
            reverse=True,
        )
        return patterns[:limit]

    async def get_recovery_patterns(self) -> List[Dict[str, Any]]:
        """Get recovery patterns."""
        return list(self._recovery_patterns.values())

    # ------------------------------------------------------------------
    # Confidence / Experience Timeline
    # ------------------------------------------------------------------

    async def get_confidence_trends(self) -> Dict[str, Any]:
        """Confidence trends over accumulated intelligence."""
        return {
            "avg_lesson_confidence": (
                sum(lesson.get("confidence", 0.5) for lesson in self._lessons) / max(len(self._lessons), 1)
            ),
            "avg_pattern_confidence": (
                sum(p.get("confidence", 0.5) for p in self._failure_patterns.values())
                / max(len(self._failure_patterns), 1)
            ),
            "avg_recommendation_confidence": (
                sum(r.get("confidence", 0.5) for r in self._recommendations)
                / max(len(self._recommendations), 1)
            ),
            "total_intelligence_entries": (
                len(self._lessons) + len(self._failure_patterns)
                + len(self._recovery_patterns) + len(self._recommendations)
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_error(error: str) -> str:
        """Normalize error strings for consistent pattern matching."""
        clean = error.strip().lower()
        for token in ["timeout", "time out", "timed out"]:
            if token in clean:
                return "timeout_error"
        for token in ["auth", "unauthorized", "forbidden", "permission", "access denied"]:
            if token in clean:
                return "authentication_error"
        for token in ["not found", "404", "does not exist", "missing"]:
            if token in clean:
                return "not_found_error"
        for token in ["rate limit", "too many", "throttle", "quota"]:
            if token in clean:
                return "rate_limit_error"
        for token in ["connection", "network", "refused", "unreachable"]:
            if token in clean:
                return "connection_error"
        for token in ["validation", "invalid", "bad request", "malformed"]:
            if token in clean:
                return "validation_error"
        return clean[:100]


# =========================================================
# Singleton
# =========================================================

enterprise_learning = EnterpriseLearningEngine()
