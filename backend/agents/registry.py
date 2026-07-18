from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.base import AgentTask, BaseAgent

log = logging.getLogger(__name__)


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}
        self._capability_index: Dict[str, List[str]] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.agent_id] = agent
        for cap in agent.capabilities:
            self._capability_index.setdefault(cap.capability_type, []).append(agent.agent_id)

    def unregister(self, agent_id: str) -> None:
        agent = self._agents.pop(agent_id, None)
        if agent:
            for cap in agent.capabilities:
                agents = self._capability_index.get(cap.capability_type, [])
                if agent_id in agents:
                    agents.remove(agent_id)

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        return self._agents.get(agent_id)

    def get_by_type(self, agent_type: str) -> List[BaseAgent]:
        return [a for a in self._agents.values() if a.agent_type == agent_type]

    def find_by_capability(self, capability: str) -> List[BaseAgent]:
        agent_ids = set()
        q = capability.lower()
        for cap_type, ids in self._capability_index.items():
            if q in cap_type.lower() or cap_type.lower() in q:
                agent_ids.update(ids)
        results = [self._agents[a_id] for a_id in agent_ids if a_id in self._agents]
        for a in self._agents.values():
            if a not in results and any(c.matches(capability) for c in a.capabilities):
                results.append(a)
        return results

    def find_idle(self, agent_type: str = "") -> List[BaseAgent]:
        from backend.agents.base import AgentStatus
        agents = self.get_by_type(agent_type) if agent_type else list(self._agents.values())
        return [a for a in agents if a.status == AgentStatus.IDLE]

    def assign(self, task: AgentTask) -> Optional[BaseAgent]:
        candidates = self.find_idle(task.agent_type) if task.agent_type else self.find_by_capability(task.description)
        if not candidates:
            candidates = [a for a in self._agents.values() if a.status == type(a.status).IDLE]
        if candidates:
            agent = candidates[0]
            agent.status = type(agent.status).ASSIGNED
            task.assigned_agent = agent.agent_id
            return agent
        return None

    def list_agents(self) -> List[Dict[str, Any]]:
        return [a.info for a in self._agents.values()]

    @property
    def agent_count(self) -> int:
        return len(self._agents)


agent_registry = AgentRegistry()
