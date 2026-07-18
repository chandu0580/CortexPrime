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

    def __init__(self):

        self.client = AsyncAzureOpenAI(

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

        self.deployment_name = os.getenv(
            "AZURE_OPENAI_CHAT_DEPLOYMENT"
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
