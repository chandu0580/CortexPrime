from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from backend.computer.computer_agent import computer_agent
from backend.events.event_bus import publish_event
from backend.memory.episodic_memory_engine import episodic_memory_engine
from backend.research.deep_research_engine import deep_research_engine
from backend.tools.browser_agent import browser_agent

# ==========================================
# MASTER AGENT RUNTIME
# ==========================================

class MasterAgentRuntime:

    def __init__(self):

        # ==========================================
        # ACTIVE MISSIONS
        # ==========================================

        self.active_missions = {}

        # ==========================================
        # COMPLETED MISSIONS
        # ==========================================

        self.completed_missions = []


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

        await publish_event("master_agent_runtime", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # MISSION CLASSIFICATION
    # ==========================================

    async def classify_mission(

        self,

        goal: str
    ) -> str:

        goal_lower = goal.lower()

        # ======================================
        # COMPUTER TASKS
        # ======================================

        computer_keywords = [

            "open",

            "click",

            "desktop",

            "application",

            "window",

            "computer",

            "screen",

            "type"
        ]

        # ======================================
        # RESEARCH TASKS
        # ======================================

        research_keywords = [

            "research",

            "find",

            "analyze",

            "study",

            "search",

            "information"
        ]

        # ======================================
        # BROWSER TASKS
        # ======================================

        browser_keywords = [

            "website",

            "browser",

            "internet",

            "web",

            "google"
        ]

        # ======================================
        # CLASSIFY
        # ======================================

        if any(

            keyword in goal_lower

            for keyword in computer_keywords
        ):

            return "computer"

        if any(

            keyword in goal_lower

            for keyword in browser_keywords
        ):

            return "browser"

        if any(

            keyword in goal_lower

            for keyword in research_keywords
        ):

            return "research"

        return "general"


    # ==========================================
    # MEMORY CONTEXT
    # ==========================================

    async def retrieve_memory_context(

        self,

        goal: str
    ) -> Dict[str, Any]:

        try:

            memory_result = await (

                episodic_memory_engine
                .retrieve_memories({

                    "query":
                        goal,

                    "limit":
                        5
                })
            )

            return memory_result

        except Exception:

            return {

                "success": False,

                "memories": []
            }


    # ==========================================
    # EXECUTE COMPUTER MISSION
    # ==========================================

    async def execute_computer_mission(

        self,

        goal: str
    ) -> Dict[str, Any]:

        # ======================================
        # SIMPLE PLANNING
        # ======================================

        steps = []

        goal_lower = goal.lower()

        # ======================================
        # OPEN WEBSITE
        # ======================================

        if "google" in goal_lower:

            steps.append({

                "action":
                    "open_website",

                "url":
                    "https://www.google.com"
            })

        # ======================================
        # SEARCH
        # ======================================

        if "search" in goal_lower:

            query = goal.replace(
                "search",
                ""
            )

            steps.append({

                "action":
                    "google_search",

                "query":
                    query
            })

        # ======================================
        # ANALYZE SCREEN
        # ======================================

        steps.append({

            "action":
                "analyze_screen"
        })

        return await (

            computer_agent
            .execute_mission({

                "mission_name":
                    goal,

                "steps":
                    steps
            })
        )


    # ==========================================
    # EXECUTE RESEARCH MISSION
    # ==========================================

    async def execute_research_mission(

        self,

        goal: str
    ) -> Dict[str, Any]:

        return await (

            deep_research_engine
            .execute_research({

                "query":
                    goal
            })
        )


    # ==========================================
    # EXECUTE BROWSER MISSION
    # ==========================================

    async def execute_browser_mission(

        self,

        goal: str
    ) -> Dict[str, Any]:

        return await (

            browser_agent
            .browse({

                "task":
                    goal
            })
        )


    # ==========================================
    # REFLECTION LOOP
    # ==========================================

    async def reflect_on_result(

        self,

        goal: str,

        result: Dict[str, Any]
    ) -> Dict[str, Any]:

        success = result.get(
            "success",
            False
        )

        reflection = {

            "goal":
                goal,

            "success":
                success,

            "reflection":
                (
                    "Mission completed successfully"

                    if success

                    else

                    "Mission requires recovery"
                ),

            "timestamp":
                datetime.utcnow()
                .isoformat()
        }

        return reflection


    # ==========================================
    # MAIN AUTONOMOUS LOOP
    # ==========================================

    async def execute_goal(

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

        # ==========================================
        # REGISTER MISSION
        # ==========================================

        self.active_missions[
            execution_id
        ] = {

            "goal":
                goal,

            "status":
                "running",

            "started_at":
                datetime.utcnow()
                .isoformat()
        }

        await self.publish_event(

            execution_id,

            "master_goal_started",

            "running",

            "master_orchestration",

            f"Executing goal: {goal}"
        )

        # ==========================================
        # MEMORY CONTEXT
        # ==========================================

        await (

            self.retrieve_memory_context(
                goal
            )
        )

        await self.publish_event(

            execution_id,

            "memory_context_loaded",

            "running",

            "memory_context",

            "Retrieved episodic memory context"
        )

        # ==========================================
        # CLASSIFY MISSION
        # ==========================================

        mission_type = await (

            self.classify_mission(
                goal
            )
        )

        await self.publish_event(

            execution_id,

            "mission_classified",

            "running",

            "mission_routing",

            f"Mission classified as: {mission_type}"
        )

        # ==========================================
        # EXECUTION ROUTING
        # ==========================================

        if mission_type == "computer":

            result = await (

                self.execute_computer_mission(
                    goal
                )
            )

        elif mission_type == "browser":

            result = await (

                self.execute_browser_mission(
                    goal
                )
            )

        elif mission_type == "research":

            result = await (

                self.execute_research_mission(
                    goal
                )
            )

        else:

            result = {

                "success": True,

                "message":
                    "General reasoning completed"
            }

        # ==========================================
        # REFLECTION
        # ==========================================

        reflection = await (

            self.reflect_on_result(

                goal,

                result
            )
        )

        # ==========================================
        # STORE MEMORY
        # ==========================================

        try:

            await episodic_memory_engine.store_memory({

                "content":
                    f"Goal: {goal}",

                "metadata": {

                    "result":
                        result,

                    "reflection":
                        reflection
                }
            })

        except Exception:

            pass

        # ==========================================
        # COMPLETE
        # ==========================================

        self.active_missions[
            execution_id
        ]["status"] = "completed"

        completed_result = {

            "execution_id":
                execution_id,

            "goal":
                goal,

            "mission_type":
                mission_type,

            "result":
                result,

            "reflection":
                reflection,

            "completed_at":
                datetime.utcnow()
                .isoformat()
        }

        self.completed_missions.append(
            completed_result
        )

        await self.publish_event(

            execution_id,

            "master_goal_completed",

            "completed",

            "master_orchestration",

            f"Goal completed: {goal}"
        )

        return {

            "success": True,

            "execution":
                completed_result
        }


    # ==========================================
    # ACTIVE MISSIONS
    # ==========================================

    async def get_active_missions(

        self

    ) -> Dict[str, Any]:

        return {

            "success": True,

            "active_missions":
                self.active_missions
        }


    # ==========================================
    # COMPLETED MISSIONS
    # ==========================================

    async def get_completed_missions(

        self

    ) -> Dict[str, Any]:

        return {

            "success": True,

            "completed_missions":
                self.completed_missions
        }


# ==========================================
# SINGLETON
# ==========================================

master_agent_runtime = (
    MasterAgentRuntime()
)
