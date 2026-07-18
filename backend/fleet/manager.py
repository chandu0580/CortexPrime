from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.fleet.health import fleet_health_monitor
from backend.fleet.models import (
    AgentHealth,
    DeploymentStrategy,
    Fleet,
    FleetAgent,
    FleetDeployment,
    FleetStatus,
)

log = logging.getLogger(__name__)


class FleetManager:
    def __init__(self):
        self._fleets: Dict[str, Fleet] = {}
        self._agents: Dict[str, List[FleetAgent]] = {}
        self._deployments: Dict[str, List[FleetDeployment]] = {}

    async def create_fleet(
        self,
        name: str,
        org_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Fleet:
        fleet = Fleet(name=name, org_id=org_id, config=config)
        self._fleets[fleet.id] = fleet
        self._agents[fleet.id] = []
        self._deployments[fleet.id] = []
        log.info("Fleet created: %s (%s)", fleet.name, fleet.id)
        return fleet

    async def get_fleet(self, fleet_id: str) -> Optional[Fleet]:
        return self._fleets.get(fleet_id)

    async def list_fleets(self, org_id: Optional[str] = None) -> List[Fleet]:
        if org_id:
            return [f for f in self._fleets.values() if f.org_id == org_id]
        return list(self._fleets.values())

    async def delete_fleet(self, fleet_id: str) -> bool:
        if fleet_id in self._fleets:
            self._fleets[fleet_id].status = FleetStatus.DELETED
            self._fleets.pop(fleet_id, None)
            self._agents.pop(fleet_id, None)
            self._deployments.pop(fleet_id, None)
            log.info("Fleet deleted: %s", fleet_id)
            return True
        return False

    async def register_agent(
        self,
        fleet_id: str,
        agent_type: str,
        agent_name: str,
        version: str = "1.0.0",
        region: str = "default",
        labels: Optional[Dict[str, str]] = None,
    ) -> Optional[FleetAgent]:
        if fleet_id not in self._fleets:
            return None
        agent = FleetAgent(
            fleet_id=fleet_id,
            agent_type=agent_type,
            agent_name=agent_name,
            version=version,
            region=region,
            labels=labels,
        )
        self._agents[fleet_id].append(agent)
        log.info("Agent registered: %s in fleet %s", agent.agent_name, fleet_id)
        return agent

    async def list_agents(self, fleet_id: str) -> List[FleetAgent]:
        return self._agents.get(fleet_id, [])

    async def get_agent(self, fleet_id: str, agent_id: str) -> Optional[FleetAgent]:
        agents = self._agents.get(fleet_id, [])
        for agent in agents:
            if agent.id == agent_id:
                return agent
        return None

    async def update_agent_health(
        self,
        fleet_id: str,
        agent_id: str,
        health: AgentHealth,
    ) -> bool:
        agent = await self.get_agent(fleet_id, agent_id)
        if agent:
            agent.status = health
            return True
        return False

    async def report_heartbeat(self, fleet_id: str, agent_id: str) -> bool:
        agent = await self.get_agent(fleet_id, agent_id)
        if agent:
            from datetime import datetime, timezone
            agent.last_heartbeat = datetime.now(timezone.utc)
            return True
        return False

    async def create_deployment(
        self,
        fleet_id: str,
        target_environment: str,
        strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[FleetDeployment]:
        if fleet_id not in self._fleets:
            return None
        deployment = FleetDeployment(
            fleet_id=fleet_id,
            target_environment=target_environment,
            strategy=strategy,
            config=config,
        )
        self._deployments[fleet_id].append(deployment)
        log.info("Deployment created: %s → %s (%s)", fleet_id, target_environment, strategy.value)
        return deployment

    async def list_deployments(self, fleet_id: str) -> List[FleetDeployment]:
        return self._deployments.get(fleet_id, [])

    async def get_fleet_health(self, fleet_id: str) -> Dict[str, Any]:
        agents = await self.list_agents(fleet_id)
        agent_dicts = [a.to_dict() for a in agents]
        snapshot = fleet_health_monitor.compute_snapshot(
            fleet_id=fleet_id,
            agents=agent_dicts,
        )
        return snapshot.to_dict()

    async def health(self) -> Dict[str, Any]:
        fleet_count = len(self._fleets)
        agent_count = sum(len(agents) for agents in self._agents.values())
        return {
            "status": "healthy",
            "fleets": fleet_count,
            "agents": agent_count,
            "deployments": sum(len(deps) for deps in self._deployments.values()),
        }


fleet_manager = FleetManager()
