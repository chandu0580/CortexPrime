from tooling.web_search_tool import (
    WebSearchTool
)

from tooling.document_tool import (
    DocumentTool
)

from tooling.code_execution_tool import (
    CodeExecutionTool
)

from tooling.api_tool import (
    APITool
)


# ==========================================
# TOOL REGISTRY
# ==========================================

class ToolRegistry:

    def __init__(self):

        self.tools = {

            "web_search": (
                WebSearchTool()
            ),

            "document_tool": (
                DocumentTool()
            ),

            "code_execution": (
                CodeExecutionTool()
            ),

            "api_tool": (
                APITool()
            )
        }

    # ==========================================
    # GET TOOL
    # ==========================================

    def get_tool(
        self,
        tool_name: str
    ):

        tool = self.tools.get(
            tool_name
        )

        if not tool:

            raise Exception(
                f"Tool not found: "
                f"{tool_name}"
            )

        return tool

    # ==========================================
    # LIST TOOLS
    # ==========================================

    def list_tools(self):

        return list(
            self.tools.keys()
        )