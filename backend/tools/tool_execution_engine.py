from typing import Any, Dict, List
from uuid import uuid4

from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent
from backend.tools.tool_registry import tool_registry

# ==========================================
# TOOL EXECUTION ENGINE
# ==========================================

class ToolExecutionEngine:

    def __init__(self):

        # ==========================================
        # MAX RETRIES
        # ==========================================

        self.max_retries = 2


    # ==========================================
    # EXECUTE SINGLE TOOL
    # ==========================================

    async def execute_single_tool(

        self,

        tool_name: str,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        # ==========================================
        # EXECUTION START EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "tool_execution_engine",

                event_type=
                    "tool_chain_started",

                status=
                    "running",

                phase=
                    "tool_execution",

                execution_id=
                    execution_id,

                message=(
                    f"Starting tool execution: "
                    f"{tool_name}"
                ),

                payload={

                    "tool_name":
                        tool_name
                }
            )
        )

        # ==========================================
        # EXECUTE TOOL
        # ==========================================

        result = await tool_registry.execute_tool(

            tool_name=
                tool_name,

            payload=
                payload
        )

        # ==========================================
        # VALIDATE RESULT
        # ==========================================

        validated_result = (

            await self.validate_tool_result(
                result
            )
        )

        return {

            "execution_id":
                execution_id,

            "tool":
                tool_name,

            "validated_result":
                validated_result
        }


    # ==========================================
    # EXECUTE TOOL CHAIN
    # ==========================================

    async def execute_tool_chain(

        self,

        chain_name: str,

        tool_chain:
            List[Dict[str, Any]]

    ) -> Dict[str, Any]:

        chain_id = str(
            uuid4()
        )

        # ==========================================
        # CHAIN START EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "tool_execution_engine",

                event_type=
                    "tool_chain_started",

                status=
                    "running",

                phase=
                    "workflow_execution",

                execution_id=
                    chain_id,

                message=(
                    f"Executing tool chain: "
                    f"{chain_name}"
                ),

                payload={

                    "tool_count":
                        len(tool_chain),

                    "chain_name":
                        chain_name
                }
            )
        )

        results = []

        # ==========================================
        # EXECUTE EACH TOOL
        # ==========================================

        for step_index, step in enumerate(
            tool_chain
        ):

            tool_name = step.get(
                "tool"
            )

            payload = step.get(
                "payload",
                {}
            )

            # ==========================================
            # STEP EVENT
            # ==========================================

            await event_bus.publish(

                CognitionEvent(

                    agent=
                        "tool_execution_engine",

                    event_type=
                        "tool_step_execution",

                    status=
                        "running",

                    phase=
                        "workflow_step",

                    execution_id=
                        chain_id,

                    message=(
                        f"Executing workflow step "
                        f"{step_index + 1}: "
                        f"{tool_name}"
                    ),

                    payload={

                        "step":
                            step_index + 1,

                        "tool":
                            tool_name
                    }
                )
            )

            # ==========================================
            # EXECUTE STEP
            # ==========================================

            result = await self.execute_with_retry(

                tool_name=
                    tool_name,

                payload=
                    payload
            )

            results.append({

                "step":
                    step_index + 1,

                "tool":
                    tool_name,

                "result":
                    result
            })

        # ==========================================
        # CHAIN COMPLETED EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "tool_execution_engine",

                event_type=
                    "tool_chain_completed",

                status=
                    "completed",

                phase=
                    "workflow_execution",

                execution_id=
                    chain_id,

                message=(
                    f"Completed workflow: "
                    f"{chain_name}"
                ),

                payload={

                    "results":
                        results
                }
            )
        )

        return {

            "chain_id":
                chain_id,

            "chain_name":
                chain_name,

            "results":
                results
        }


    # ==========================================
    # EXECUTE WITH RETRY
    # ==========================================

    async def execute_with_retry(

        self,

        tool_name: str,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        last_error = None

        for attempt in range(

            self.max_retries + 1
        ):

            result = await tool_registry.execute_tool(

                tool_name=
                    tool_name,

                payload=
                    payload
            )

            # ==========================================
            # SUCCESS
            # ==========================================

            if result.get("success"):

                return result

            # ==========================================
            # FAILURE
            # ==========================================

            last_error = result.get(
                "error"
            )

            await event_bus.publish(

                CognitionEvent(

                    agent=
                        "tool_execution_engine",

                    event_type=
                        "tool_retry",

                    status=
                        "retrying",

                    phase=
                        "tool_retry",

                    message=(
                        f"Retrying tool "
                        f"{tool_name} "
                        f"(attempt {attempt + 1})"
                    ),

                    payload={

                        "tool":
                            tool_name,

                        "attempt":
                            attempt + 1
                    }
                )
            )

        return {

            "success":
                False,

            "tool":
                tool_name,

            "error":
                last_error
        }


    # ==========================================
    # VALIDATE TOOL RESULT
    # ==========================================

    async def validate_tool_result(

        self,

        result: Dict[str, Any]

    ) -> Dict[str, Any]:

        valid = result.get(
            "success",
            False
        )

        confidence = (
            0.95 if valid else 0.2
        )

        # ==========================================
        # VALIDATION EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "tool_execution_engine",

                event_type=
                    "tool_validation",

                status=
                    "completed",

                phase=
                    "tool_validation",

                message=
                    "Validated tool output",

                confidence_score=
                    confidence,

                payload={

                    "valid":
                        valid,

                    "tool":
                        result.get(
                            "tool"
                        )
                }
            )
        )

        return {

            "valid":
                valid,

            "confidence":
                confidence,

            "result":
                result
        }


    # ==========================================
    # AUTONOMOUS TOOL PLANNER
    # ==========================================

    async def autonomous_tool_selection(

        self,

        objective: str

    ) -> List[Dict[str, Any]]:

        available_tools = (
            tool_registry.list_tools()
        )

        workflow = []
        # ==========================================
        # SIMPLE OBJECTIVE ROUTING
        # ==========================================

        objective_lower = (
            objective.lower()
        )

        # ==========================================
        # HEALTH CHECK
        # ==========================================

        if "health" in objective_lower:

            workflow.append({

                "tool":
                    "health_check",

                "payload":
                    {}
            })

        # ==========================================
        # WEB SEARCH
        # ==========================================

        elif (

            "search" in objective_lower

            or

            "research" in objective_lower

            or

            "find" in objective_lower
        ):

            workflow.append({

                "tool":
                    "browser_search_web",

                "payload": {

                    "query":
                        objective
                }
            })

        # ==========================================
        # OPEN WEBSITE
        # ==========================================

        elif (

            "open" in objective_lower

            or

            "website" in objective_lower

            or

            "visit" in objective_lower
        ):

            workflow.append({

                "tool":
                    "browser_open_page",

                "payload": {

                    "url":
                        "https://example.com"
                }
            })

        # ==========================================
        # LINK EXTRACTION
        # ==========================================

        elif "extract" in objective_lower:

            workflow.append({

                "tool":
                    "browser_extract_links",

                "payload": {

                    "url":
                        "https://example.com"
                }
            })

        # ==========================================
        # DEFAULT FALLBACK
        # ==========================================

        else:

            workflow.append({

                "tool":
                    "echo",

                "payload": {

                    "objective":
                        objective
                }
            })

        # ==========================================
        # PLANNING EVENT
        # ==========================================

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "tool_execution_engine",

                event_type=
                    "autonomous_tool_planning",

                status=
                    "completed",

                phase=
                    "workflow_planning",

                message=(
                    "Generated autonomous "
                    "tool workflow"
                ),

                payload={

                    "workflow":
                        workflow,

                    "available_tools":
                        len(available_tools)
                }
            )
        )

        return workflow


# ==========================================
# SINGLETON
# ==========================================

tool_execution_engine = (
    ToolExecutionEngine()
)
