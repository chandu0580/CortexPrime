import os

from dotenv import load_dotenv
from tavily import TavilyClient

# ==========================================
# LOAD ENVIRONMENT
# ==========================================

load_dotenv(
    "backend/.env"
)


# ==========================================
# TAVILY CLIENT
# ==========================================

client = TavilyClient(

    api_key=os.getenv(
        "TAVILY_API_KEY"
    )
)


# ==========================================
# SEARCH TOOL
# ==========================================

class TavilySearchTool:

    # ==========================================
    # SEARCH
    # ==========================================

    async def search(

        self,

        query: str,

        max_results: int = 5

    ):

        try:

            response = client.search(

                query=query,

                search_depth="advanced",

                max_results=max_results
            )

            return {

                "status":
                    "success",

                "query":
                    query,

                "results":
                    response.get(
                        "results",
                        []
                    )
            }

        except Exception as error:

            return {

                "status":
                    "error",

                "message":
                    str(error)
            }


# ==========================================
# GLOBAL TOOL
# ==========================================

tavily_search_tool = (
    TavilySearchTool()
)
