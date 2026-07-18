from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.orchestrator.models import MissionArtifact, MissionLifecycleState


class ArtifactManager:
    def __init__(self) -> None:
        self._artifacts: Dict[str, Dict[str, MissionArtifact]] = {}

    def add(
        self,
        mission_id: str,
        name: str,
        artifact_type: str,
        data: Any,
        source: str = "",
        state: MissionLifecycleState = MissionLifecycleState.RECEIVED,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MissionArtifact:
        artifact = MissionArtifact(
            artifact_id=uuid4().hex[:12],
            name=name,
            artifact_type=artifact_type,
            data=data,
            source=source,
            state=state,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        self._artifacts.setdefault(mission_id, {})[artifact.artifact_id] = artifact
        return artifact

    def get(self, mission_id: str, artifact_id: str) -> Optional[MissionArtifact]:
        return self._artifacts.get(mission_id, {}).get(artifact_id)

    def list_by_mission(self, mission_id: str) -> List[MissionArtifact]:
        return list(self._artifacts.get(mission_id, {}).values())

    def list_by_type(self, mission_id: str, artifact_type: str) -> List[MissionArtifact]:
        return [
            a for a in self._artifacts.get(mission_id, {}).values()
            if a.artifact_type == artifact_type
        ]

    def list_by_state(self, mission_id: str, state: MissionLifecycleState) -> List[MissionArtifact]:
        return [
            a for a in self._artifacts.get(mission_id, {}).values()
            if a.state == state
        ]

    def delete(self, mission_id: str, artifact_id: str) -> bool:
        artifacts = self._artifacts.get(mission_id)
        if artifacts and artifact_id in artifacts:
            del artifacts[artifact_id]
            return True
        return False

    def clear_mission(self, mission_id: str) -> None:
        self._artifacts.pop(mission_id, None)


artifact_manager = ArtifactManager()
