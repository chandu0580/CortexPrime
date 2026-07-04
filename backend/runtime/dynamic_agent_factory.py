
from typing import Dict, Any, List
from uuid import uuid4

from backend.runtime.base_agent import (
    BaseAgent
)

from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent,
    EventTypes
)


# ==========================================
# DYNAMIC AGENT
# ==========================================

class DynamicAgent(BaseAgent):

    def __init__(

        self,

        agent_name: str,

        specialization: str

    ):

        super().__init__(
            agent_name=agent_name
        )

        self.specialization = (
            specialization
        )

    # ==========================================
    # EXECUTE
    # ==========================================

    async def execute(

        self,

        task: Dict[str, Any]

    ) -> Dict[str, Any]:

        objective = task.get(
            "objective",
            "No objective"
        )

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=
                    "dynamic_agent_execution",

                status="running",

                phase=
                    "dynamic_reasoning",

                message=(
                    f"{self.agent_name} "
                    f"processing objective"
                ),

                payload={

                    "specialization":
                        self.specialization,

                    "objective":
                        objective
                }
            )
        )

        return {

            "agent":
                self.agent_name,

            "specialization":
                self.specialization,

            "objective":
                objective,

            "status":
                "completed",

            "analysis": (

                f"{self.agent_name} completed "

                f"{self.specialization} analysis"
            )
        }


# ==========================================
# DYNAMIC AGENT FACTORY
# ==========================================

class DynamicAgentFactory:

    def __init__(self):

        self.dynamic_agents: Dict[
            str,
            DynamicAgent
        ] = {}

    # ==========================================
    # ANALYZE OBJECTIVE
    # ==========================================

    def analyze_objective(

        self,

        objective: str

    ) -> List[str]:

        objective_lower = (
            objective.lower()
        )

        specializations = []

        # ==========================================
        # FINANCE
        # ==========================================

        if any(

            keyword in objective_lower

            for keyword in [

                "finance",
                "fintech",
                "investment",
                "banking",
                "fraud",
                "stock"
            ]
        ):

            specializations.extend([

                "financial_analysis",

                "risk_assessment",

                "market_research"
            ])

        # ==========================================
        # AI / ML
        # ==========================================

        if any(

            keyword in objective_lower

            for keyword in [

                "ai",
                "machine learning",
                "llm",
                "rag",
                "deep learning"
            ]
        ):

            specializations.extend([

                "ml_architecture",

                "model_evaluation",

                "data_engineering"
            ])

        # ==========================================
        # CYBERSECURITY
        # ==========================================

        if any(

            keyword in objective_lower

            for keyword in [

                "cyber",
                "security",
                "malware",
                "threat",
                "attack"
            ]
        ):

            specializations.extend([

                "threat_analysis",

                "security_validation",

                "risk_detection"
            ])

        # ==========================================
        # SOFTWARE ENGINEERING
        # ==========================================

        if any(

            keyword in objective_lower

            for keyword in [

                "app",
                "application",
                "software",
                "dashboard",
                "platform",
                "api"
            ]
        ):

            specializations.extend([

                "backend_engineering",

                "frontend_engineering",

                "system_design"
            ])

        # ==========================================
        # DEFAULT
        # ==========================================

        if not specializations:

            specializations.extend([

                "general_reasoning",

                "research_analysis"
            ])

        return list(
            set(specializations)
        )

    # ==========================================
    # CREATE AGENT
    # ==========================================

    async def create_agent(

        self,

        specialization: str

    ) -> DynamicAgent:

        agent_id = str(
            uuid4()
        )[:8]

        agent_name = (

            f"{specialization}_agent_"

            f"{agent_id}"
        )

        dynamic_agent = DynamicAgent(

            agent_name=
                agent_name,

            specialization=
                specialization
        )

        self.dynamic_agents[
            agent_name
        ] = dynamic_agent

        # ==========================================
        # EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=agent_name,

                event_type=
                    "dynamic_agent_created",

                status="completed",

                phase=
                    "agent_spawning",

                message=(

                    f"Spawned dynamic agent: "

                    f"{specialization}"
                ),

                payload={

                    "agent_name":
                        agent_name,

                    "specialization":
                        specialization
                }
            )
        )

        return dynamic_agent

    # ==========================================
    # SPAWN AGENTS
    # ==========================================

    async def spawn_agents_for_objective(

        self,

        objective: str

    ) -> List[DynamicAgent]:

        specializations = (

            self.analyze_objective(
                objective
            )
        )

        agents = []

        for specialization in (
            specializations
        ):

            agent = await self.create_agent(
                specialization
            )

            agents.append(agent)

        return agents

    # ==========================================
    # GET AGENTS
    # ==========================================

    def get_dynamic_agents(self):

        return self.dynamic_agents


# ==========================================
# SINGLETON
# ==========================================

dynamic_agent_factory = (
    DynamicAgentFactory()
)
