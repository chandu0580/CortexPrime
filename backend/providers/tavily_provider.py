import os
import httpx

from dotenv import load_dotenv


# ==========================================
# LOAD ENV
# ==========================================

load_dotenv()


# ==========================================
# TAVILY PROVIDER
# ==========================================

class TavilyProvider:

    def __init__(self):

        self.api_key = os.getenv(
            "TAVILY_API_KEY"
        )

        self.base_url = (
            "https://api.tavily.com/search"
        )


    # ==========================================
    # SEARCH
    # ==========================================

    async def search(

        self,

        query: str,

        max_results: int = 5

    ):

        payload = {

            "api_key":
                self.api_key,

            "query":
                query,

            "search_depth":
                "advanced",

            "include_answer":
                True,

            "include_raw_content":
                False,

            "max_results":
                max_results
        }

        async with httpx.AsyncClient() as client:

            response = await client.post(

                self.base_url,

                json=payload,

                timeout=60
            )

            return response.json()


# ==========================================
# SINGLETON
# ==========================================

tavily_provider = TavilyProvider()