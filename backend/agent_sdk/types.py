from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class AgentConfig:
    agent_type: str
    agent_name: str
    version: str = "1.0.0"
    description: str = ""
    tags: List[str] = field(default_factory=list)
    max_retries: int = 3
    timeout_seconds: int = 300
    permissions: List[str] = field(default_factory=list)


@dataclass
class MissionResult:
    mission_id: str
    status: AgentStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    token_usage: Dict[str, int] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    fn: Optional[Callable] = None


@dataclass
class AgentMetadata:
    agent_id: str
    agent_type: str
    agent_name: str
    version: str
    status: AgentStatus
    created_at: datetime
    tools: List[ToolSpec] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
