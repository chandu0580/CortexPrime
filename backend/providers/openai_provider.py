import asyncio
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

# ==========================================
# LOAD ENV
# ==========================================

load_dotenv()


# ==========================================
# AZURE OPENAI PROVIDER
# ==========================================

class OpenAIProvider:
    """Azure OpenAI provider with a LAZILY built client (Phase 5.15, ADR-058).

    The SDK client used to be constructed in ``__init__`` at module import,
    which made three Azure environment variables a precondition for importing
    this module: with any of them absent the ``openai`` SDK raises, and every
    transitive importer inherits the crash. Construction now happens on first
    use, so importing is a pure definition and a missing credential fails the
    completion call that actually needed it, with the SDK's own precise error.
    """

    def __init__(self):

        self._client = None

        self.deployment_name = os.getenv(
            "AZURE_OPENAI_CHAT_DEPLOYMENT"
        )

    @property
    def client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self):

        return AsyncAzureOpenAI(

            api_key=os.getenv(
                "AZURE_OPENAI_API_KEY"
            ),

            azure_endpoint=os.getenv(
                "AZURE_OPENAI_ENDPOINT"
            ),

            api_version=os.getenv(
                "AZURE_OPENAI_API_VERSION"
            )
        )


    # ==========================================
    # STANDARD RESPONSE
    # ==========================================

    async def generate_response(

        self,

        prompt: str

    ) -> str:

        response = (

            await self.client.chat.completions.create(

                model=self.deployment_name,

                messages=[

                    {
                        "role": "system",

                        "content": (
                            "You are CortexPrime, "
                            "an enterprise cognitive "
                            "AI runtime."
                        )
                    },

                    {
                        "role": "user",

                        "content": prompt
                    }
                ],

                temperature=0.7
            )
        )

        return (

            response
            .choices[0]
            .message.content
        )


    # ==========================================
    # STREAMING RESPONSE
    # ==========================================

    async def stream_response(

        self,

        prompt: str

    ) -> AsyncGenerator[str, None]:

        stream = (

            await self.client.chat.completions.create(

                model=self.deployment_name,

                messages=[

                    {
                        "role": "system",

                        "content": (
                            "You are CortexPrime, "
                            "a realtime cognitive "
                            "execution engine."
                        )
                    },

                    {
                        "role": "user",

                        "content": prompt
                    }
                ],

                temperature=0.7,

                stream=True
            )
        )

        async for chunk in stream:

            try:

                delta = (

                    chunk
                    .choices[0]
                    .delta
                )

                if (

                    delta and

                    delta.content
                ):

                    yield delta.content

                    await asyncio.sleep(
                        0.01
                    )

            except Exception:

                continue


# ==========================================
# SINGLETON
# ==========================================

openai_provider = OpenAIProvider()
