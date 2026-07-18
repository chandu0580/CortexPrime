import logging
import os

from tavily import TavilyClient

from dotenv import load_dotenv

log = logging.getLogger(__name__)


# ==========================================
# LOAD ENV VARIABLES
# ==========================================

load_dotenv()


# ==========================================
# WEB SEARCH TOOL
# ==========================================

class WebSearchTool:

    def __init__(self):

        api_key = os.getenv(
            "TAVILY_API_KEY"
        )

        if not api_key:

            raise Exception(
                "Missing TAVILY_API_KEY"
            )

        self.client = TavilyClient(
            api_key=api_key
        )

    # ==========================================
    # EXECUTE WEB SEARCH
    # ==========================================

    def execute(
        self,
        tool_input: dict
    ):

        query = tool_input.get(
            "query",
            ""
        )

        if not query:

            raise Exception(
                "Missing search query."
            )

        log.info(
            "Tavily Searching For: %s",
            query
        )

        # ==========================================
        # EXECUTE SEARCH
        # ==========================================

        response = self.client.search(

            query=query,

            search_depth="advanced",

            max_results=5
        )

        results = []

        # ==========================================
        # PROCESS RESULTS
        # ==========================================

        for item in response.get(
            "results",
            []
        ):

            results.append({

                "title": item.get(
                    "title"
                ),

                "url": item.get(
                    "url"
                ),

                "content": item.get(
                    "content"
                )
            })

        # ==========================================
        # RETURN RESULTS
        # ==========================================

        return {

            "query": query,

            "total_results": len(results),

            "results": results
        }
