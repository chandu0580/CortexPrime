import logging
from typing import Dict

log = logging.getLogger(__name__)

try:
    from backend.agents.orchestrator_agent.orchestrator_agent import OrchestratorAgent
    _OrchestratorAgent = OrchestratorAgent
except Exception as _e:
    log.warning("OrchestratorAgent unavailable: %s", _e)
    _OrchestratorAgent = None

try:
    from backend.agents.research_agent.research_agent import ResearchAgent
    _ResearchAgent = ResearchAgent
except Exception as _e:
    log.warning("ResearchAgent unavailable: %s", _e)
    _ResearchAgent = None

try:
    from backend.agents.planner_agent.planner_agent import PlannerAgent
    _PlannerAgent = PlannerAgent
except Exception as _e:
    log.warning("PlannerAgent unavailable: %s", _e)
    _PlannerAgent = None

try:
    from backend.agents.critic_agent.critic_agent import CriticAgent
    _CriticAgent = CriticAgent
except Exception as _e:
    log.warning("CriticAgent unavailable: %s", _e)
    _CriticAgent = None

try:
    from backend.agents.optimizer_agent.optimizer_agent import OptimizerAgent
    _OptimizerAgent = OptimizerAgent
except Exception as _e:
    log.warning("OptimizerAgent unavailable: %s", _e)
    _OptimizerAgent = None

try:
    from backend.agents.memory_agent.memory_agent import MemoryAgent
    _MemoryAgent = MemoryAgent
except Exception as _e:
    log.warning("MemoryAgent unavailable: %s", _e)
    _MemoryAgent = None

try:
    from backend.agents.reflection_agent.reflection_agent import ReflectionAgent
    _ReflectionAgent = ReflectionAgent
except Exception as _e:
    log.warning("ReflectionAgent unavailable: %s", _e)
    _ReflectionAgent = None


# ==========================================
# AGENT REGISTRY
# ==========================================

class AgentRegistry:

    def __init__(self):

        self.agents: Dict = {}

        self._register_default_agents()

    # ==========================================
    # REGISTER DEFAULT AGENTS
    # ==========================================

    def _register_default_agents(self):

        _candidates = {
            "orchestrator": _OrchestratorAgent,
            "research":     _ResearchAgent,
            "planner":      _PlannerAgent,
            "critic":       _CriticAgent,
            "optimizer":    _OptimizerAgent,
            "memory":       _MemoryAgent,
            "reflection":   _ReflectionAgent,
        }

        for name, AgentClass in _candidates.items():
            if AgentClass is None:
                continue
            try:
                self.register_agent(name, AgentClass())
            except Exception as _e:
                log.warning("Failed to register agent '%s': %s", name, _e)

    # ==========================================
    # REGISTER AGENT
    # ==========================================

    def register_agent(

        self,

        agent_name: str,

        agent_instance

    ):

        self.agents[agent_name] = agent_instance
        log.info("Registered agent: %s", agent_name)

    # ==========================================
    # GET AGENT
    # ==========================================

    def get_agent(

        self,

        agent_name: str

    ):

        return self.agents.get(
            agent_name
        )

    # ==========================================
    # LIST AGENTS
    # ==========================================

    def list_agents(self):

        return list(
            self.agents.keys()
        )

    # ==========================================
    # GET ALL METADATA
    # ==========================================

    def get_all_metadata(self):

        return {

            name: agent.metadata()

            for name, agent in

            self.agents.items()
        }


# ==========================================
# GLOBAL REGISTRY
# ==========================================

agent_registry = AgentRegistry()
