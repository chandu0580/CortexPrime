from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MissionDependency:
    step_id: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class MissionConstraint:
    name: str
    description: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionArtifact:
    name: str
    description: Optional[str] = None
    artifact_type: str = "generic"
    path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionStep:
    step_id: str
    order: int
    name: str
    description: Optional[str] = None
    agent: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3
    artifacts: list[MissionArtifact] = field(default_factory=list)


@dataclass
class MissionPlan:
    plan_id: str
    mission_id: str
    steps: list[MissionStep]
    dependencies: list[MissionDependency] = field(default_factory=list)
    constraints: list[MissionConstraint] = field(default_factory=list)
    estimated_duration_ms: Optional[int] = None
    risk_level: str = "low"
    metadata: dict[str, Any] = field(default_factory=dict)


class MissionPlanner(ABC):
    @abstractmethod
    async def create_plan(self, mission_id: str, title: str, objective: str,
                          context: dict[str, Any]) -> MissionPlan:
        ...

    @abstractmethod
    async def get_plan(self, plan_id: str) -> Optional[MissionPlan]:
        ...

    @abstractmethod
    async def get_plan_for_mission(self, mission_id: str) -> Optional[MissionPlan]:
        ...
