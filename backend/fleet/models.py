from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class FleetStatus(str, Enum):
    CREATING = "creating"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SCALING = "scaling"
    FAILED = "failed"
    DELETED = "deleted"


class AgentHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class DeploymentStrategy(str, Enum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"


class Fleet:
    def __init__(
        self,
        name: str,
        org_id: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.id: str = str(uuid4())
        self.name: str = name
        self.org_id: str = org_id
        self.status: FleetStatus = FleetStatus.CREATING
        self.config: Dict[str, Any] = config or {}
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "org_id": self.org_id,
            "status": self.status.value,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class FleetAgent:
    def __init__(
        self,
        fleet_id: str,
        agent_type: str,
        agent_name: str,
        version: str = "1.0.0",
        region: str = "default",
        labels: Optional[Dict[str, str]] = None,
    ):
        self.id: str = str(uuid4())
        self.fleet_id: str = fleet_id
        self.agent_type: str = agent_type
        self.agent_name: str = agent_name
        self.version: str = version
        self.region: str = region
        self.labels: Dict[str, str] = labels or {}
        self.status: AgentHealth = AgentHealth.UNKNOWN
        self.created_at: datetime = datetime.now(timezone.utc)
        self.last_heartbeat: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fleet_id": self.fleet_id,
            "agent_type": self.agent_type,
            "agent_name": self.agent_name,
            "version": self.version,
            "region": self.region,
            "labels": self.labels,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
        }


class FleetDeployment:
    def __init__(
        self,
        fleet_id: str,
        target_environment: str,
        strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.id: str = str(uuid4())
        self.fleet_id: str = fleet_id
        self.target_environment: str = target_environment
        self.strategy: DeploymentStrategy = strategy
        self.config: Dict[str, Any] = config or {}
        self.status: str = "pending"
        self.created_at: datetime = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fleet_id": self.fleet_id,
            "target_environment": self.target_environment,
            "strategy": self.strategy.value,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class FleetMetricsSnapshot:
    def __init__(self, fleet_id: str):
        self.fleet_id: str = fleet_id
        self.timestamp: datetime = datetime.now(timezone.utc)
        self.total_agents: int = 0
        self.healthy_agents: int = 0
        self.degraded_agents: int = 0
        self.unhealthy_agents: int = 0
        self.mission_count: int = 0
        self.error_rate: float = 0.0
        self.avg_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fleet_id": self.fleet_id,
            "timestamp": self.timestamp.isoformat(),
            "total_agents": self.total_agents,
            "healthy_agents": self.healthy_agents,
            "degraded_agents": self.degraded_agents,
            "unhealthy_agents": self.unhealthy_agents,
            "mission_count": self.mission_count,
            "error_rate": self.error_rate,
            "avg_latency_ms": self.avg_latency_ms,
        }
