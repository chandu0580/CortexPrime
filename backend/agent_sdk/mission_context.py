from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MissionContext:
    mission_id: str
    org_id: Optional[str] = None
    user_id: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    _knowledge: Any = None
    _governance: Any = None
    _memory: Any = None
    _event_bus: Any = None
    _llm_router: Any = None

    @property
    def knowledge(self):
        if self._knowledge is None:
            from backend.knowledge import KnowledgeService
            self._knowledge = KnowledgeService()
        return self._knowledge

    @property
    def governance(self):
        if self._governance is None:
            from backend.governance import GovernanceService
            self._governance = GovernanceService()
        return self._governance

    @property
    def memory(self):
        if self._memory is None:
            from backend.memory.memory_orchestrator import MemoryOrchestrator
            self._memory = MemoryOrchestrator()
        return self._memory

    @property
    def event_bus(self):
        if self._event_bus is None:
            from backend.events.event_bus import event_bus
            self._event_bus = event_bus
        return self._event_bus

    @property
    def llm_router(self):
        if self._llm_router is None:
            from backend.llm.llm_router import LLMRouter
            self._llm_router = LLMRouter()
        return self._llm_router

    async def emit_event(self, event_type: str, status: str, message: str, payload: Optional[Dict] = None):
        from backend.events.event_bus import CognitionEvent
        event = CognitionEvent(
            agent=self.mission_id,
            event_type=event_type,
            status=status,
            message=message,
            payload=payload,
        )
        await self.event_bus.publish(event)

    async def query(self, collection: str, query: str, limit: int = 10) -> List[Dict]:
        ws = self.workspace
        if ws:
            return await ws.query(collection=collection, query=query, limit=limit)
        return []

    @property
    def workspace(self):
        from backend.workspace.workspace_service import WorkspaceService
        return WorkspaceService()
