import asyncio
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from backend.events.event_bus import publish_event
from backend.tools.tool_registry import tool_registry

# ==========================================
# AUTONOMOUS RUNTIME
# ==========================================

class AutonomousRuntime:

    def __init__(self):

        # ==========================================
        # ACTIVE AGENTS
        # ==========================================

        self.active_agents: Dict[
            str,
            Dict[str, Any]
        ] = {}

        # ==========================================
        # WORKFLOW HISTORY
        # ==========================================

        self.workflow_history: List[
            Dict[str, Any]
        ] = []

        # ==========================================
        # RUNTIME STATE
        # ==========================================

        self.runtime_active = False


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

        await publish_event("autonomous_runtime", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # START AUTONOMOUS RUNTIME
    # ==========================================

    async def start_runtime(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        if self.runtime_active:

            return {

                "success": False,

                "error":
                    "Runtime already active"
            }

        self.runtime_active = True

        await self.publish_event(

            execution_id,

            "autonomous_runtime_started",

            "completed",

            "autonomous_runtime",

            "Autonomous runtime started"
        )

        return {

            "success": True,

            "runtime_active":
                self.runtime_active
        }


    # ==========================================
    # STOP AUTONOMOUS RUNTIME
    # ==========================================

    async def stop_runtime(

        self

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        self.runtime_active = False

        await self.publish_event(

            execution_id,

            "autonomous_runtime_stopped",

            "completed",

            "autonomous_runtime",

            "Autonomous runtime stopped"
        )

        return {

            "success": True,

            "runtime_active":
                self.runtime_active
        }


    # ==========================================
    # REGISTER AUTONOMOUS AGENT
    # ==========================================

    async def register_agent(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        agent_name = payload.get(
            "agent_name"
        )

        interval = payload.get(
            "interval",
            10
        )

        if not agent_name:

            return {

                "success": False,

                "error":
                    "Missing agent_name"
            }

        agent_id = str(
            uuid4()
        )

        agent = {

            "agent_id":
                agent_id,

            "agent_name":
                agent_name,

            "interval":
                interval,

            "status":
                "active",

            "registered_at":
                datetime.utcnow()
                .isoformat()
        }

        self.active_agents[
            agent_id
        ] = agent

        await self.publish_event(

            execution_id,

            "autonomous_agent_registered",

            "completed",

            "agent_registration",

            f"Registered autonomous agent: {agent_name}",

            {

                "agent_id":
                    agent_id,

                "interval":
                    interval
            }
        )

        return {

            "success": True,

            "agent":
                agent
        }


    # ==========================================
    # EXECUTE WORKFLOW
    # ==========================================

    async def execute_workflow(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        workflow_name = payload.get(
            "workflow_name"
        )

        steps = payload.get(
            "steps",
            []
        )

        if not workflow_name:

            return {

                "success": False,

                "error":
                    "Missing workflow_name"
            }

        await self.publish_event(

            execution_id,

            "workflow_execution_started",

            "running",

            "workflow_execution",

            f"Executing workflow: {workflow_name}"
        )

        completed_steps = []

        # ==========================================
        # EXECUTE STEPS
        # ==========================================

        for step in steps:

            await asyncio.sleep(
                1
            )

            completed_steps.append({

                "step":
                    step,

                "status":
                    "completed"
            })

        workflow_result = {

            "workflow_id":
                execution_id,

            "workflow_name":
                workflow_name,

            "completed_steps":
                completed_steps,

            "timestamp":
                datetime.utcnow()
                .isoformat()
        }

        self.workflow_history.append(
            workflow_result
        )

        await self.publish_event(

            execution_id,

            "workflow_execution_completed",

            "completed",

            "workflow_execution",

            f"Workflow completed: {workflow_name}",

            {

                "completed_steps":
                    len(completed_steps)
            }
        )

        return {

            "success": True,

            "workflow":
                workflow_result
        }


    # ==========================================
    # AUTONOMOUS LOOP
    # ==========================================

    async def autonomous_loop(

        self

    ):

        while self.runtime_active:

            for agent_id, agent in (

                self.active_agents.items()
            ):

                await self.publish_event(

                    str(uuid4()),

                    "autonomous_agent_cycle",

                    "running",

                    "continuous_execution",

                    (
                        f"Running autonomous "
                        f"cycle for "
                        f"{agent['agent_name']}"
                    ),

                    {

                        "agent_id":
                            agent_id
                    }
                )

            await asyncio.sleep(5)


    # ==========================================
    # GET STATUS
    # ==========================================

    async def runtime_status(

        self

    ) -> Dict[str, Any]:

        return {

            "success": True,

            "runtime_active":
                self.runtime_active,

            "active_agents":
                len(
                    self.active_agents
                ),

            "workflow_history":
                len(
                    self.workflow_history
                )
        }


# ==========================================
# SINGLETON
# ==========================================

autonomous_runtime = (
    AutonomousRuntime()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="autonomous_start_runtime",

    description=
        "Start autonomous runtime",

    handler=
        autonomous_runtime.start_runtime,

    tool_type=
        "autonomy"
)

tool_registry.register_tool(

    name="autonomous_stop_runtime",

    description=
        "Stop autonomous runtime",

    handler=
        autonomous_runtime.stop_runtime,

    tool_type=
        "autonomy"
)

tool_registry.register_tool(

    name="autonomous_register_agent",

    description=
        "Register autonomous agents",

    handler=
        autonomous_runtime.register_agent,

    tool_type=
        "autonomy"
)

tool_registry.register_tool(

    name="autonomous_execute_workflow",

    description=
        "Execute autonomous workflows",

    handler=
        autonomous_runtime.execute_workflow,

    tool_type=
        "autonomy"
)

tool_registry.register_tool(

    name="autonomous_runtime_status",

    description=
        "Get autonomous runtime status",

    handler=
        autonomous_runtime.runtime_status,

    tool_type=
        "autonomy"
)
