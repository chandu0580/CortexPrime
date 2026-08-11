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
# TAVILY CLIENT — lazily constructed (Phase 5.15, ADR-058)
# ==========================================
# Some tavily SDK versions raise at construction when the key is absent,
# which would make a credential a precondition for importing this module.
# Built on first use instead; a missing key fails the search that needed it.

_client = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(
            api_key=os.getenv("TAVILY_API_KEY")
        )
    return _client


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

            response = _get_client().search(

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
