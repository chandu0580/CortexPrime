from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.cognitive_memory.manager import MemoryManager, memory_manager
from backend.cognitive_memory.models import (
    MemoryArtifact,
    MemoryContext,
    MemorySnapshot,
)

log = logging.getLogger(__name__)


class CognitiveMemoryService:
    def __init__(self, manager: Optional[MemoryManager] = None) -> None:
        self._manager = manager or memory_manager

    # Context lifecycle
    def create_context(
        self,
        mission_id: str,
        user_id: str = "",
        tenant_id: str = "",
        trace_id: str = "",
        correlation_id: str = "",
        ttl_hours: int = 24,
        initial_goal: str = "",
        mission_name: str = "",
        objective: str = "",
        category: str = "",
    ) -> MemoryContext:
        return self._manager.create_context(
            mission_id=mission_id,
            user_id=user_id,
            tenant_id=tenant_id,
            trace_id=trace_id,
            correlation_id=correlation_id,
            ttl_hours=ttl_hours,
            initial_goal=initial_goal,
            mission_name=mission_name,
            objective=objective,
            category=category,
        )

    def get_context(self, mission_id: str) -> Optional[MemoryContext]:
        return self._manager.get_context(mission_id)

    def update_context(self, mission_id: str, updates: Dict[str, Any]) -> Optional[MemoryContext]:
        return self._manager.update_context(mission_id, updates)

    def delete_context(self, mission_id: str) -> bool:
        return self._manager.delete_context(mission_id)

    # Reasoning
    def add_reasoning_step(
        self,
        mission_id: str,
        description: str,
        decision: str = "",
        alternatives: Optional[List[str]] = None,
        confidence: float = 1.0,
        critical: bool = False,
    ) -> Optional[MemoryContext]:
        return self._manager.add_reasoning_step(
            mission_id=mission_id,
            description=description,
            decision=decision,
            alternatives=alternatives,
            confidence=confidence,
            critical=critical,
        )

    # Conversation
    def add_conversation_turn(
        self,
        mission_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryContext]:
        return self._manager.add_conversation_turn(
            mission_id=mission_id,
            role=role,
            content=content,
            metadata=metadata,
        )

    # Execution
    def record_connector_output(
        self,
        mission_id: str,
        connector: str,
        operation: str,
        output: Any,
    ) -> Optional[MemoryContext]:
        return self._manager.record_connector_output(
            mission_id=mission_id,
            connector=connector,
            operation=operation,
            output=output,
        )

    def record_error(
        self,
        mission_id: str,
        source: str,
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryContext]:
        return self._manager.record_error(
            mission_id=mission_id,
            source=source,
            error=error,
            details=details,
        )

    def add_artifact(
        self,
        mission_id: str,
        name: str,
        artifact_type: str,
        data: Any,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryArtifact]:
        return self._manager.add_artifact(
            mission_id=mission_id,
            name=name,
            artifact_type=artifact_type,
            data=data,
            source=source,
            metadata=metadata,
        )

    # Snapshot / Restore
    def snapshot(self, mission_id: str) -> Optional[MemorySnapshot]:
        return self._manager.snapshot(mission_id)

    def restore(self, mission_id: str, snapshot_id: str) -> Optional[MemoryContext]:
        return self._manager.restore(mission_id, snapshot_id)

    def list_snapshots(self, mission_id: str) -> List[MemorySnapshot]:
        return self._manager.list_snapshots(mission_id)

    # Compression
    def compress(self, mission_id: str) -> Optional[MemoryContext]:
        return self._manager.compress(mission_id)

    # Expiry / Archive
    def expire_context(self, mission_id: str) -> bool:
        return self._manager.expire_context(mission_id)

    def archive_context(self, mission_id: str) -> bool:
        return self._manager.archive_context(mission_id)

    # Retrieval
    def find_by_user(self, user_id: str) -> List[MemoryContext]:
        return self._manager.find_by_user(user_id)

    def find_by_tenant(self, tenant_id: str) -> List[MemoryContext]:
        return self._manager.find_by_tenant(tenant_id)

    def find_by_trace(self, trace_id: str) -> List[MemoryContext]:
        return self._manager.find_by_trace(trace_id)

    def find_by_correlation(self, correlation_id: str) -> List[MemoryContext]:
        return self._manager.find_by_correlation(correlation_id)

    # Health
    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "active_contexts": self._manager.count(),
            "service": "cognitive_memory",
        }


cognitive_memory_service = CognitiveMemoryService()
