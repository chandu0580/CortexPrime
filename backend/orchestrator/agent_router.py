import asyncio
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from backend.computer.computer_agent import computer_agent
from backend.events.event_bus import event_bus, publish_event
from backend.events.event_models import CognitionEvent
from backend.research.deep_research_engine import deep_research_engine
from backend.tools.browser_agent import browser_agent

# ==========================================
# AGENT ROUTER
# ==========================================

class AgentRouter:

    def __init__(self):

        # ==========================================
        # AVAILABLE AGENTS
        # ==========================================

        self.available_agents = {

            "computer_agent": {

                "type":
                    "computer",

                "capabilities": [

                    "desktop_control",

                    "window_management",

                    "workflow_execution",

                    "computer_use",

                    "visual_ui_interaction"
                ]
            },

            "browser_agent": {

                "type":
                    "browser",

                "capabilities": [

                    "web_navigation",

                    "internet_browsing",

                    "website_interaction",

                    "dom_analysis"
                ]
            },

            "research_agent": {

                "type":
                    "research",

                "capabilities": [

                    "deep_research",

                    "evidence_reasoning",

                    "source_analysis",

                    "fact_validation"
                ]
            },

            "voice_agent": {

                "type":
                    "voice",

                "capabilities": [

                    "speech_synthesis",

                    "speech_recognition",

                    "voice_interaction"
                ]
            }
        }

        # ==========================================
        # ROUTING HISTORY
        # ==========================================

        self.routing_history = []


    # ==========================================
    # EVENT HELPER
    # ==========================================

    async def publish_event(

        self,

        execution_id: str,

        event_type: str,

        status: str,

        phase: str,

        message: str,

        payload: Dict[str, Any] = None
    ):

        await publish_event("agent_router", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # ANALYZE GOAL
    # ==========================================

    async def analyze_goal(

        self,

        goal: str
    ) -> Dict[str, Any]:

        goal_lower = goal.lower()

        required_capabilities = []

        # ======================================
        # COMPUTER INTENT
        # ======================================

        computer_keywords = [

            "click",

            "desktop",

            "computer",

            "window",

            "application",

            "screen",

            "mouse",

            "keyboard",

            "open app"
        ]

        # ======================================
        # BROWSER INTENT
        # ======================================

        browser_keywords = [

            "website",

            "browser",

            "google",

            "internet",

            "web",

            "search online"
        ]

        # ======================================
        # RESEARCH INTENT
        # ======================================

        research_keywords = [

            "research",

            "analyze",

            "study",

            "investigate",

            "find information"
        ]

        # ======================================
        # VOICE INTENT
        # ======================================

        voice_keywords = [

            "speak",

            "voice",

            "audio",

            "talk"
        ]

        # ======================================
        # DETECT CAPABILITIES
        # ======================================

        if any(

            keyword in goal_lower

            for keyword in computer_keywords
        ):

            required_capabilities.append(
                "computer_use"
            )

        if any(

            keyword in goal_lower

            for keyword in browser_keywords
        ):

            required_capabilities.append(
                "web_navigation"
            )

        if any(

            keyword in goal_lower

            for keyword in research_keywords
        ):

            required_capabilities.append(
                "deep_research"
            )

        if any(

            keyword in goal_lower

            for keyword in voice_keywords
        ):

            required_capabilities.append(
                "speech_synthesis"
            )

        return {

            "goal":
                goal,

            "required_capabilities":
                required_capabilities
        }


    # ==========================================
    # SELECT BEST AGENTS
    # ==========================================

    async def select_agents(

        self,

        capabilities: List[str]
    ) -> List[str]:

        selected_agents = []

        for (

            agent_name,

            agent_info

        ) in self.available_agents.items():

            agent_capabilities = (

                agent_info[
                    "capabilities"
                ]
            )

            if any(

                capability in agent_capabilities

                for capability in capabilities
            ):

                selected_agents.append(
                    agent_name
                )

        return selected_agents


    # ==========================================
    # EXECUTE AGENT
    # ==========================================

    async def execute_agent(

        self,

        agent_name: str,

        goal: str
    ) -> Dict[str, Any]:

        # ======================================
        # COMPUTER AGENT
        # ======================================

        if agent_name == "computer_agent":

            return await (

                computer_agent
                .execute_mission({

                    "mission_name":
                        goal,

                    "steps": [

                        {

                            "action":
                                "analyze_screen"
                        }
                    ]
                })
            )

        # ======================================
        # BROWSER AGENT
        # ======================================

        elif agent_name == "browser_agent":

            return await (

                browser_agent
                .browse({

                    "task":
                        goal
                })
            )

        # ======================================
        # RESEARCH AGENT
        # ======================================

        elif agent_name == "research_agent":

            return await (

                deep_research_engine
                .execute_research({

                    "query":
                        goal
                })
            )

        # ======================================
        # VOICE AGENT
        # ======================================

        elif agent_name == "voice_agent":

            return {

                "success": True,

                "message":
                    "Voice interaction processed"
            }

        return {

            "success": False,

            "error":
                f"Unknown agent: {agent_name}"
        }


    # ==========================================
    # ROUTE GOAL
    # ==========================================

    async def route_goal(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        goal = payload.get(
            "goal"
        )

        if not goal:

            return {

                "success": False,

                "error":
                    "Missing goal"
            }

        await self.publish_event(

            execution_id,

            "routing_started",

            "running",

            "agent_routing",

            f"Routing goal: {goal}"
        )

        # ==========================================
        # ANALYZE GOAL
        # ==========================================

        analysis = await (

            self.analyze_goal(
                goal
            )
        )

        capabilities = analysis[
            "required_capabilities"
        ]

        # ==========================================
        # SELECT AGENTS
        # ==========================================

        selected_agents = await (

            self.select_agents(
                capabilities
            )
        )

        await self.publish_event(

            execution_id,

            "agents_selected",

            "running",

            "agent_selection",

            (
                f"Selected agents: "
                f"{', '.join(selected_agents)}"
            )
        )

        # ==========================================
        # EXECUTE AGENTS
        # ==========================================

        results = []

        for agent_name in selected_agents:

            try:

                await self.publish_event(

                    execution_id,

                    "agent_execution_started",

                    "running",

                    "agent_execution",

                    f"Executing agent: {agent_name}"
                )

                result = await (

                    self.execute_agent(

                        agent_name,

                        goal
                    )
                )

                results.append({

                    "agent":
                        agent_name,

                    "result":
                        result
                })

                await self.publish_event(

                    execution_id,

                    "agent_execution_completed",

                    "completed",

                    "agent_execution",

                    (
                        f"Completed agent: "
                        f"{agent_name}"
                    )
                )

                await asyncio.sleep(1)

            except Exception as error:

                results.append({

                    "agent":
                        agent_name,

                    "error":
                        str(error)
                })

        # ==========================================
        # STORE HISTORY
        # ==========================================

        routing_result = {

            "execution_id":
                execution_id,

            "goal":
                goal,

            "selected_agents":
                selected_agents,

            "results":
                results,

            "completed_at":
                datetime.utcnow()
                .isoformat()
        }

        self.routing_history.append(
            routing_result
        )

        await self.publish_event(

            execution_id,

            "routing_completed",

            "completed",

            "agent_routing",

            f"Routing completed for: {goal}"
        )

        return {

            "success": True,

            "routing":
                routing_result
        }


    # ==========================================
    # GET AGENTS
    # ==========================================

    async def get_available_agents(

        self

    ) -> Dict[str, Any]:

        return {

            "success": True,

            "agents":
                self.available_agents
        }


    # ==========================================
    # GET ROUTING HISTORY
    # ==========================================

    async def get_routing_history(

        self

    ) -> Dict[str, Any]:

        return {

            "success": True,

            "history":
                self.routing_history
        }


# ==========================================
# SINGLETON
# ==========================================

agent_router = (
    AgentRouter()
)
