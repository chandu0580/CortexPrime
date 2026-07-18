import logging

from tooling.tool_registry import (
    ToolRegistry
)

from datetime import datetime

log = logging.getLogger(__name__)


# ==========================================
# TOOL EXECUTOR
# ==========================================

class ToolExecutor:

    def __init__(self):

        self.registry = (
            ToolRegistry()
        )

    # ==========================================
    # EXECUTE TOOL
    # ==========================================

    def execute_tool(
        self,
        tool_name: str,
        tool_input: dict
    ):

        started_at = (
            datetime.utcnow()
        )

        log.info(
            "Executing Tool: %s",
            tool_name
        )

        try:

            tool = (
                self.registry
                .get_tool(tool_name)
            )

            result = tool.execute(
                tool_input
            )

            completed_at = (
                datetime.utcnow()
            )

            return {

                "tool_name": tool_name,

                "status": "success",

                "started_at": (
                    started_at.isoformat()
                ),

                "completed_at": (
                    completed_at.isoformat()
                ),

                "duration_seconds": round(

                    (
                        completed_at
                        -
                        started_at
                    ).total_seconds(),

                    2
                ),

                "result": result
            }

        except Exception as error:

            completed_at = (
                datetime.utcnow()
            )

            return {

                "tool_name": tool_name,

                "status": "failed",

                "started_at": (
                    started_at.isoformat()
                ),

                "completed_at": (
                    completed_at.isoformat()
                ),

                "duration_seconds": round(

                    (
                        completed_at
                        -
                        started_at
                    ).total_seconds(),

                    2
                ),

                "error": str(error)
            }
