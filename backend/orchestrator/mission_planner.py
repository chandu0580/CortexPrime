import asyncio
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from backend.events.event_bus import event_bus, publish_event
from backend.events.event_models import CognitionEvent
from backend.memory.episodic_memory_engine import episodic_memory_engine
from backend.orchestrator.agent_router import agent_router

# ==========================================
# MISSION AGENT RUNTIME
# ==========================================

class MissionAgentRuntime:

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
        # FAILED MISSIONS
        # ==========================================

        self.failed_missions = []


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

        await publish_event("mission_agent_runtime", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # DECOMPOSE MISSION
    # ==========================================

    async def decompose_mission(

        self,

        goal: str
    ) -> List[Dict[str, Any]]:

        goal_lower = goal.lower()

        subtasks = []

        # ======================================
        # RESEARCH TASK
        # ======================================

        if any(

            keyword in goal_lower

            for keyword in [

                "research",

                "analyze",

                "investigate"
            ]
        ):

            subtasks.append({

                "task":
                    f"Research task: {goal}",

                "type":
                    "research"
            })

        # ======================================
        # BROWSER TASK
        # ======================================

        if any(

            keyword in goal_lower

            for keyword in [

                "website",

                "browser",

                "google",

                "search"
            ]
        ):

            subtasks.append({

                "task":
                    f"Browser task: {goal}",

                "type":
                    "browser"
            })

        # ======================================
        # COMPUTER TASK
        # ======================================

        if any(

            keyword in goal_lower

            for keyword in [

                "click",

                "desktop",

                "window",

                "application",

                "computer"
            ]
        ):

            subtasks.append({

                "task":
                    f"Computer task: {goal}",

                "type":
                    "computer"
            })

        # ======================================
        # DEFAULT
        # ======================================

        if not subtasks:

            subtasks.append({

                "task":
                    goal,

                "type":
                    "general"
            })

        return subtasks


    # ==========================================
    # EXECUTE SUBTASK
    # ==========================================

    async def execute_subtask(

        self,

        subtask: Dict[str, Any]
    ) -> Dict[str, Any]:

        return await (

            agent_router
            .route_goal({

                "goal":
                    subtask["task"]
            })
        )


    # ==========================================
    # REFLECTION
    # ==========================================

    async def reflect_on_mission(

        self,

        goal: str,

        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:

        success_count = len([

            result

            for result in results

            if result.get(
                "success"
            )
        ])

        failed_count = (

            len(results)

            - success_count
        )

        reflection = {

            "goal":
                goal,

            "success_count":
                success_count,

            "failed_count":
                failed_count,

            "overall_status":

                "successful"

                if failed_count == 0

                else

                "partial_success",

            "timestamp":
                datetime.utcnow()
                .isoformat()
        }

        return reflection


    # ==========================================
    # STORE MEMORY
    # ==========================================

    async def store_mission_memory(

        self,

        goal: str,

        reflection: Dict[str, Any]
    ):

        try:

            await episodic_memory_engine.store_memory({

                "content":
                    f"Mission completed: {goal}",

                "metadata": {

                    "reflection":
                        reflection
                }
            })

        except Exception:

            pass


    # ==========================================
    # MAIN MISSION LOOP
    # ==========================================

    async def execute_mission(

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
        # REGISTER
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

            "mission_started",

            "running",

            "mission_runtime",

            f"Mission started: {goal}"
        )

        # ==========================================
        # DECOMPOSE
        # ==========================================

        subtasks = await (

            self.decompose_mission(
                goal
            )
        )

        await self.publish_event(

            execution_id,

            "mission_decomposed",

            "running",

            "mission_planning",

            (
                f"Generated "
                f"{len(subtasks)} subtasks"
            )
        )

        # ==========================================
        # EXECUTE SUBTASKS
        # ==========================================

        results = []

        for index, subtask in enumerate(
            subtasks
        ):

            try:

                await self.publish_event(

                    execution_id,

                    "subtask_started",

                    "running",

                    "subtask_execution",

                    (
                        f"Executing subtask "
                        f"{index + 1}"
                    ),

                    {

                        "subtask":
                            subtask
                    }
                )

                result = await (

                    self.execute_subtask(
                        subtask
                    )
                )

                results.append({

                    "subtask":
                        subtask,

                    "result":
                        result,

                    "success":
                        result.get(
                            "success",
                            False
                        )
                })

                await self.publish_event(

                    execution_id,

                    "subtask_completed",

                    "completed",

                    "subtask_execution",

                    (
                        f"Completed subtask "
                        f"{index + 1}"
                    )
                )

                await asyncio.sleep(1)

            except Exception as error:

                results.append({

                    "subtask":
                        subtask,

                    "success":
                        False,

                    "error":
                        str(error)
                })

                await self.publish_event(

                    execution_id,

                    "subtask_failed",

                    "failed",

                    "subtask_execution",

                    (
                        f"Failed subtask "
                        f"{index + 1}"
                    ),

                    {

                        "error":
                            str(error)
                    }
                )

        # ==========================================
        # REFLECT
        # ==========================================

        reflection = await (

            self.reflect_on_mission(

                goal,

                results
            )
        )

        # ==========================================
        # STORE MEMORY
        # ==========================================

        await self.store_mission_memory(

            goal,

            reflection
        )

        # ==========================================
        # COMPLETE
        # ==========================================

        self.active_missions[
            execution_id
        ]["status"] = "completed"

        mission_result = {

            "execution_id":
                execution_id,

            "goal":
                goal,

            "results":
                results,

            "reflection":
                reflection,

            "completed_at":
                datetime.utcnow()
                .isoformat()
        }

        self.completed_missions.append(
            mission_result
        )

        await self.publish_event(

            execution_id,

            "mission_completed",

            "completed",

            "mission_runtime",

            f"Mission completed: {goal}"
        )

        return {

            "success": True,

            "mission":
                mission_result
        }


    # ==========================================
    # GET ACTIVE MISSIONS
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
    # GET COMPLETED MISSIONS
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

mission_agent_runtime = (
    MissionAgentRuntime()
)
