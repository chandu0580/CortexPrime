from __future__ import annotations

import logging

from backend.agents.builtin.compliance import ComplianceAgent
from backend.agents.builtin.planner import PlannerAgent
from backend.agents.builtin.platform_engineer import PlatformEngineerAgent
from backend.agents.builtin.qa import QAAgent
from backend.agents.builtin.release import ReleaseAgent
from backend.agents.builtin.research import ResearchAgent
from backend.agents.builtin.security import SecurityAgent
from backend.agents.builtin.sre import SREAgent
from backend.agents.registry import agent_registry

log = logging.getLogger(__name__)


def register_agent_services() -> None:
    try:
        from backend.core.dependency_container import container

        agents = [
            ("planner_agent", PlannerAgent()),
            ("research_agent", ResearchAgent()),
            ("platform_engineer_agent", PlatformEngineerAgent()),
            ("sre_agent", SREAgent()),
            ("security_agent", SecurityAgent()),
            ("compliance_agent", ComplianceAgent()),
            ("release_agent", ReleaseAgent()),
            ("qa_agent", QAAgent()),
        ]

        for name, agent in agents:
            agent_registry.register(agent)
            container.register(name, agent, startup_priority=70)

        container.register("agent_coordinator", coordinator, startup_priority=70)
        container.register("agent_registry", agent_registry, startup_priority=70)

        log.info("Registered %d multi-agent services", len(agents) + 2)
    except Exception as exc:
        log.warning("Multi-agent DI registration failed: %s", exc)


from backend.agents.coordinator import coordinator
