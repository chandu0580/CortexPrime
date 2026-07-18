from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.agent_sdk.mission_context import MissionContext
from backend.agent_sdk.tool import get_registered_tools
from backend.agent_sdk.types import (
    AgentConfig,
    AgentMetadata,
    AgentStatus,
    MissionResult,
    ToolSpec,
)

log = logging.getLogger(__name__)


class CortexAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent_id: str = str(uuid4())
        self.status: AgentStatus = AgentStatus.IDLE
        self.created_at: datetime = datetime.now(timezone.utc)
        self._tools: Dict[str, ToolSpec] = {}
        self._discover_tools()

    def _discover_tools(self):
        for name, spec in get_registered_tools().items():
            self._tools[name] = ToolSpec(
                name=spec["name"],
                description=spec["description"],
                parameters=spec["parameters"],
                fn=spec["fn"],
            )

    @property
    def agent_type(self) -> str:
        return self.config.agent_type

    @property
    def name(self) -> str:
        return self.config.agent_name

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id=self.agent_id,
            agent_type=self.config.agent_type,
            agent_name=self.config.agent_name,
            version=self.config.version,
            status=self.status,
            created_at=self.created_at,
            tools=list(self._tools.values()),
            tags=self.config.tags,
        )

    def get_tools(self) -> List[ToolSpec]:
        return list(self._tools.values())

    async def execute(self, context: MissionContext) -> MissionResult:
        raise NotImplementedError("Subclasses must implement execute()")

    async def run(self, context: MissionContext) -> MissionResult:
        self.status = AgentStatus.RUNNING
        started_at = datetime.now(timezone.utc)
        try:
            result = await asyncio.wait_for(
                self.execute(context),
                timeout=self.config.timeout_seconds,
            )
            result.started_at = started_at
            result.completed_at = datetime.now(timezone.utc)
            result.mission_id = context.mission_id
            self.status = result.status
            return result
        except asyncio.TimeoutError:
            self.status = AgentStatus.FAILED
            return MissionResult(
                mission_id=context.mission_id,
                status=AgentStatus.FAILED,
                error=f"Execution timed out after {self.config.timeout_seconds}s",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            self.status = AgentStatus.FAILED
            log.exception("Agent execution failed")
            return MissionResult(
                mission_id=context.mission_id,
                status=AgentStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

    async def cleanup(self):
        self.status = AgentStatus.IDLE
