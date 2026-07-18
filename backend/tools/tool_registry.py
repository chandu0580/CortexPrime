import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List
from uuid import uuid4

from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent

# ==========================================
# TOOL REGISTRY
# ==========================================

class ToolRegistry:

    def __init__(self):

        # ==========================================
        # REGISTERED TOOLS
        # ==========================================

        self.tools: Dict[
            str,
            Dict[str, Any]
        ] = {}


    # ==========================================
    # REGISTER TOOL
    # ==========================================

    def register_tool(

        self,

        name: str,

        description: str,

        handler: Callable,

        tool_type: str = "general"

    ):

        self.tools[name] = {

            "name":
                name,

            "description":
                description,

            "handler":
                handler,

            "tool_type":
                tool_type,

            "registered_at":
                datetime.utcnow()
                .isoformat()
        }

        print(
            f"🛠️ Registered tool: {name}"
        )


    # ==========================================
    # EXECUTE TOOL
    # ==========================================

    async def execute_tool(

        self,

        tool_name: str,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        # ==========================================
        # TOOL EXISTS
        # ==========================================

        if tool_name not in self.tools:

            return {

                "success":
                    False,

                "error":
                    f"Tool '{tool_name}' "
                    f"not found"
            }

        tool = self.tools[
            tool_name
        ]

        execution_id = str(
            uuid4()
        )

        # ==========================================
        # EXECUTION START EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent="tool_registry",

                event_type=
                    "tool_execution_started",

                status="running",

                phase=
                    "tool_execution",

                execution_id=
                    execution_id,

                message=(
                    f"Executing tool: "
                    f"{tool_name}"
                ),

                payload={

                    "tool_name":
                        tool_name,

                    "tool_type":
                        tool.get(
                            "tool_type"
                        )
                }
            )
        )

        try:

            # ==========================================
            # EXECUTE HANDLER
            # ==========================================

            handler = tool["handler"]

            if asyncio.iscoroutinefunction(
                handler
            ):

                result = await handler(
                    payload
                )

            else:

                result = handler(
                    payload
                )

            # ==========================================
            # SUCCESS EVENT
            # ==========================================

            await event_bus.publish(

                CognitionEvent(

                    agent="tool_registry",

                    event_type=
                        "tool_execution_completed",

                    status="completed",

                    phase=
                        "tool_execution",

                    execution_id=
                        execution_id,

                    message=(
                        f"Completed tool: "
                        f"{tool_name}"
                    ),

                    payload={

                        "tool_name":
                            tool_name,

                        "result":
                            result
                    }
                )
            )

            return {

                "success":
                    True,

                "tool":
                    tool_name,

                "execution_id":
                    execution_id,

                "result":
                    result
            }

        except Exception as error:

            # ==========================================
            # FAILURE EVENT
            # ==========================================

            await event_bus.publish(

                CognitionEvent(

                    agent="tool_registry",

                    event_type=
                        "tool_execution_failed",

                    status="failed",

                    phase=
                        "tool_execution",

                    execution_id=
                        execution_id,

                    message=(
                        f"Tool execution failed: "
                        f"{tool_name}"
                    ),

                    payload={

                        "tool_name":
                            tool_name,

                        "error":
                            str(error)
                    }
                )
            )

            return {

                "success":
                    False,

                "tool":
                    tool_name,

                "error":
                    str(error)
            }


    # ==========================================
    # GET TOOL
    # ==========================================

    def get_tool(

        self,

        tool_name: str

    ) -> Dict[str, Any]:

        return self.tools.get(
            tool_name,
            {}
        )


    # ==========================================
    # LIST TOOLS
    # ==========================================

    def list_tools(

        self

    ) -> List[Dict[str, Any]]:

        return list(
            self.tools.values()
        )


    # ==========================================
    # TOOL COUNT
    # ==========================================

    def tool_count(self) -> int:

        return len(
            self.tools
        )


# ==========================================
# SAMPLE TOOLS
# ==========================================

async def health_check_tool(

    payload: Dict[str, Any]

) -> Dict[str, Any]:

    return {

        "status":
            "healthy",

        "timestamp":
            datetime.utcnow()
            .isoformat()
    }


async def echo_tool(

    payload: Dict[str, Any]

) -> Dict[str, Any]:

    return {

        "echo":
            payload
    }


# ==========================================
# SINGLETON
# ==========================================

tool_registry = ToolRegistry()


# ==========================================
# REGISTER DEFAULT TOOLS
# ==========================================

tool_registry.register_tool(

    name="health_check",

    description=
        "Runtime health monitoring tool",

    handler=
        health_check_tool,

    tool_type=
        "system"
)

tool_registry.register_tool(

    name="echo",

    description=
        "Echo payload tool",

    handler=
        echo_tool,

    tool_type=
        "utility"
)
