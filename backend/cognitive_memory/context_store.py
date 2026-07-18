from __future__ import annotations

import logging
from typing import Dict, List, Optional

from backend.cognitive_memory.models import MemoryArtifact, MemoryContext, MemorySnapshot

log = logging.getLogger(__name__)


class ContextStore:
    def __init__(self) -> None:
        self._contexts: Dict[str, MemoryContext] = {}
        self._snapshots: Dict[str, List[MemorySnapshot]] = {}
        self._artifacts: Dict[str, List[MemoryArtifact]] = {}

    def put(self, context: MemoryContext) -> None:
        self._contexts[context.mission_id] = context

    def get(self, mission_id: str) -> Optional[MemoryContext]:
        return self._contexts.get(mission_id)

    def delete(self, mission_id: str) -> bool:
        if mission_id in self._contexts:
            del self._contexts[mission_id]
            return True
        return False

    def list_all(self) -> List[MemoryContext]:
        return list(self._contexts.values())

    def count(self) -> int:
        return len(self._contexts)

    def put_snapshot(self, mission_id: str, snapshot: MemorySnapshot) -> None:
        if mission_id not in self._snapshots:
            self._snapshots[mission_id] = []
        self._snapshots[mission_id].append(snapshot)

    def get_snapshots(self, mission_id: str) -> List[MemorySnapshot]:
        return self._snapshots.get(mission_id, [])

    def get_snapshot(self, mission_id: str, snapshot_id: str) -> Optional[MemorySnapshot]:
        snapshots = self._snapshots.get(mission_id, [])
        for s in snapshots:
            if s.snapshot_id == snapshot_id:
                return s
        return None

    def delete_snapshots(self, mission_id: str) -> bool:
        return self._snapshots.pop(mission_id, None) is not None

    def add_artifact(self, mission_id: str, artifact: MemoryArtifact) -> None:
        if mission_id not in self._artifacts:
            self._artifacts[mission_id] = []
        self._artifacts[mission_id].append(artifact)

    def get_artifacts(self, mission_id: str) -> List[MemoryArtifact]:
        return self._artifacts.get(mission_id, [])

    def delete_artifacts(self, mission_id: str) -> bool:
        return self._artifacts.pop(mission_id, None) is not None

    def find_by_user(self, user_id: str) -> List[MemoryContext]:
        return [c for c in self._contexts.values() if c.user_id == user_id]

    def find_by_tenant(self, tenant_id: str) -> List[MemoryContext]:
        return [c for c in self._contexts.values() if c.tenant_id == tenant_id]

    def find_by_trace(self, trace_id: str) -> List[MemoryContext]:
        return [c for c in self._contexts.values() if c.trace_id == trace_id]

    def find_by_correlation(self, correlation_id: str) -> List[MemoryContext]:
        return [c for c in self._contexts.values() if c.correlation_id == correlation_id]

    def clear(self) -> None:
        self._contexts.clear()
        self._snapshots.clear()
        self._artifacts.clear()


context_store = ContextStore()
