from typing import Dict, Any
from datetime import datetime

from backend.runtime.base_agent import BaseAgent

from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent,
    EventTypes
)

from backend.runtime.runtime_state import (
    runtime_state
)


# ==========================================
# PLANNER AGENT
# ==========================================

class PlannerAgent(BaseAgent):

    def __init__(self):

        super().__init__(
            agent_name="planner"
        )

    # ==========================================
    # EXECUTE
    # ==========================================

    async def execute(

        self,

        task: Dict[str, Any]

    ) -> Dict[str, Any]:

        self.set_status(
            "running"
        )

        # ==========================================
        # UPDATE RUNTIME STATE
        # ==========================================

        runtime_state.update_agent_state(

            self.agent_name,

            "running"
        )

        objective = task.get(
            "objective",
            "No objective provided"
        )

        self.log_event(
            f"Planning objective: {objective}"
        )

        # ==========================================
        # EVENT :: START
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .PLANNING_STARTED
                ),

                status="running",

                message=(
                    f"Planning started for: "
                    f"{objective}"
                ),

                payload={

                    "objective":
                        objective
                }
            )
        )

        # ==========================================
        # TASK DECOMPOSITION
        # ==========================================

        execution_plan = [

            {
                "step": 1,
                "action": "Research objective",

                "agent":
                    "research"
            },

            {
                "step": 2,
                "action": "Analyze findings",

                "agent":
                    "critic"
            },

            {
                "step": 3,

                "action": (
                    "Generate execution strategy"
                ),

                "agent":
                    "planner"
            },

            {
                "step": 4,
                "action": "Optimize workflow",

                "agent":
                    "optimizer"
            },

            {
                "step": 5,
                "action": "Store execution memory",

                "agent":
                    "memory"
            }
        ]

        # ==========================================
        # RESPONSE
        # ==========================================

        response = {

            "status":
                "success",

            "agent":
                self.agent_name,

            "objective":
                objective,

            "timestamp":
                datetime.utcnow()
                .isoformat(),

            "execution_plan":
                execution_plan,

            "plan_metadata": {

                "total_steps":
                    len(
                        execution_plan
                    ),

                "execution_strategy":
                    "multi-agent-sequential",

                "runtime_state":
                    "active"
            }
        }

        # ==========================================
        # EVENT :: COMPLETE
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=self.agent_name,

                event_type=(
                    EventTypes
                    .PLANNING_COMPLETED
                ),

                status="completed",

                message=(
                    f"Planning completed for: "
                    f"{objective}"
                ),

                payload={

                    "objective":
                        objective,

                    "execution_plan":
                        execution_plan
                }
            )
        )

        # ==========================================
        # UPDATE RUNTIME STATE
        # ==========================================

        runtime_state.update_agent_state(

            self.agent_name,

            "completed"
        )

        self.log_event(
            "Planning completed"
        )

        self.set_status(
            "idle"
        )

        return response