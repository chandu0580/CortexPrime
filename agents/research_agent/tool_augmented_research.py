import logging

from agents.research_agent.research import ResearchAgent
from tooling.tool_executor import ToolExecutor

log = logging.getLogger(__name__)


# ==========================================
# TOOL-AUGMENTED RESEARCH
# ==========================================

class ToolAugmentedResearchAgent:

    def __init__(self):

        self.tool_executor = (
            ToolExecutor()
        )

        self.research_agent = (
            ResearchAgent()
        )

    # ==========================================
    # EXECUTE RESEARCH
    # ==========================================

    def execute(
        self,
        user_goal: str
    ):

        log.info(
            "Executing "
            "Tool-Augmented Research..."
        )

        # ==========================================
        # WEB SEARCH
        # ==========================================

        tool_result = (

            self.tool_executor.execute_tool(

                tool_name="web_search",

                tool_input={
                    "query": user_goal
                }
            )
        )

        web_results = (
            tool_result.get(
                "result",
                {}
            )
        )

        # ==========================================
        # BUILD AUGMENTED GOAL
        # ==========================================

        augmented_goal = f"""

USER GOAL:
{user_goal}

LIVE WEB INTELLIGENCE:
{web_results}

Use this live intelligence
to improve reasoning quality,
reduce hallucinations,
and generate grounded analysis.
"""

        # ==========================================
        # EXECUTE RESEARCH AGENT
        # ==========================================

        result = (
            self.research_agent.execute(
                augmented_goal
            )
        )

        # ==========================================
        # ATTACH TOOL OUTPUT
        # ==========================================

        result["tool_augmented"] = True

        result["web_intelligence"] = (
            web_results
        )

        return result
