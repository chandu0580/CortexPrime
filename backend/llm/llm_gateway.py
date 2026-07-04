import os

from uuid import uuid4

from typing import Dict, Any

from dotenv import load_dotenv

from openai import (
    AsyncOpenAI,
    AsyncAzureOpenAI
)

from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent
)


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# LLM GATEWAY
# =========================================================

class LLMGateway:

    def __init__(self):

        # =================================================
        # DEBUG ENV VARIABLES
        # =================================================

        print("\n🔥 INITIALIZING CORTEXPRIME LLM GATEWAY")

        print(
            "🔥 AZURE API VERSION:",
            os.getenv(
                "AZURE_OPENAI_API_VERSION"
            )
        )

        print(
            "🔥 AZURE ENDPOINT:",
            os.getenv(
                "AZURE_OPENAI_ENDPOINT"
            )
        )

        # =================================================
        # OPENAI CLIENT
        # =================================================

        self.openai_client = AsyncOpenAI(

            api_key=os.getenv(
                "OPENAI_API_KEY"
            )
        )

        # =================================================
        # AZURE OPENAI CLIENT
        # =================================================

        self.azure_client = AsyncAzureOpenAI(

            api_key=os.getenv(
                "AZURE_OPENAI_API_KEY"
            ),

            api_version=os.getenv(
                "AZURE_OPENAI_API_VERSION"
            ),

            azure_endpoint=os.getenv(
                "AZURE_OPENAI_ENDPOINT"
            )
        )


    # =====================================================
    # EVENT PUBLISHER
    # =====================================================

    async def publish_event(

        self,

        execution_id: str,

        event_type: str,

        status: str,

        phase: str,

        message: str,

        payload: Dict[str, Any] = {}
    ):

        await event_bus.publish(

            CognitionEvent(

                agent="llm_gateway",

                event_type=event_type,

                status=status,

                phase=phase,

                execution_id=execution_id,

                message=message,

                payload=payload
            )
        )


    # =====================================================
    # MODEL ROUTING
    # =====================================================

    def get_model_for_agent(

        self,

        agent_type: str
    ) -> str:

        routing = {

            "orchestrator":
                os.getenv(
                    "MODEL_ORCHESTRATOR",
                    "gpt-4o"
                ),

            "planner":
                os.getenv(
                    "MODEL_PLANNER",
                    "o3-mini"
                ),

            "critic":
                os.getenv(
                    "MODEL_CRITIC",
                    "gpt-4.1-mini-1"
                ),

            "runtime":
                os.getenv(
                    "MODEL_RUNTIME_FAST",
                    "gpt-5-mini-1"
                ),

            "realtime":
                os.getenv(
                    "MODEL_REALTIME",
                    "gpt-realtime"
                ),

            "general":
                os.getenv(
                    "MODEL_GENERAL",
                    "gpt-4o"
                )
        }

        return routing.get(

            agent_type,

            routing["general"]
        )


    # =====================================================
    # AZURE GENERATION
    # =====================================================

    async def generate_azure(

        self,

        prompt: str,

        agent_type: str = "general",

        system_prompt: str = (
            "You are CortexPrime, "
            "an autonomous AI assistant."
        )
    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        model = self.get_model_for_agent(
            agent_type
        )

        try:

            await self.publish_event(

                execution_id,

                "azure_generation_started",

                "running",

                "llm_generation",

                f"Using Azure model: {model}",

                {
                    "agent_type": agent_type
                }
            )

            response = await (

                self.azure_client
                .chat.completions.create(

                    model=model,

                    messages=[

                        {

                            "role":
                                "system",

                            "content":
                                system_prompt
                        },

                        {

                            "role":
                                "user",

                            "content":
                                prompt
                        }
                    ],

                    # Note: temperature omitted — o-series reasoning models do not support it

                    timeout=60
                )
            )

            output = (

                response
                .choices[0]
                .message.content
            )

            await self.publish_event(

                execution_id,

                "azure_generation_completed",

                "completed",

                "llm_generation",

                "Azure generation completed",

                {
                    "model": model
                }
            )

            return {

                "success": True,

                "provider":
                    "azure_openai",

                "model":
                    model,

                "agent_type":
                    agent_type,

                "output":
                    output
            }

        except Exception as error:

            print(
                "\n❌ AZURE ERROR:",
                str(error)
            )

            await self.publish_event(

                execution_id,

                "azure_generation_failed",

                "failed",

                "llm_generation",

                str(error)
            )

            return {

                "success": False,

                "provider":
                    "azure_openai",

                "model":
                    model,

                "error":
                    str(error)
            }


    # =====================================================
    # OPENAI FALLBACK
    # =====================================================

    async def generate_openai(

        self,

        prompt: str,

        model: str = "gpt-4o-mini"
    ) -> Dict[str, Any]:

        try:

            response = await (

                self.openai_client
                .chat.completions.create(

                    model=model,

                    messages=[

                        {

                            "role":
                                "system",

                            "content":
                                (
                                    "You are CortexPrime, "
                                    "an autonomous AI assistant."
                                )
                        },

                        {

                            "role":
                                "user",

                            "content":
                                prompt
                        }
                    ],

                    temperature=0.7,

                    timeout=60
                )
            )

            output = (

                response
                .choices[0]
                .message.content
            )

            return {

                "success": True,

                "provider":
                    "openai",

                "model":
                    model,

                "output":
                    output
            }

        except Exception as error:

            print(
                "\n❌ OPENAI ERROR:",
                str(error)
            )

            return {

                "success": False,

                "provider":
                    "openai",

                "error":
                    str(error)
            }


    # =====================================================
    # UNIFIED GENERATION
    # =====================================================

    async def generate(

        self,

        payload: Dict[str, Any]
    ) -> Dict[str, Any]:

        prompt = payload.get(
            "prompt"
        )

        if not prompt:

            return {

                "success": False,

                "error":
                    "Prompt is required"
            }

        provider = payload.get(

            "provider",

            "azure"
        )

        agent_type = payload.get(

            "agent_type",

            "general"
        )

        # =================================================
        # AZURE PRIMARY
        # =================================================

        if provider == "azure":

            result = await self.generate_azure(

                prompt=prompt,

                agent_type=agent_type
            )

            # =============================================
            # OPENAI FALLBACK
            # =============================================

            if not result.get(
                "success"
            ):

                print(
                    "\n⚠️ FALLING BACK TO OPENAI"
                )

                return await self.generate_openai(
                    prompt=prompt
                )

            return result

        # =================================================
        # OPENAI DIRECT
        # =================================================

        elif provider == "openai":

            return await self.generate_openai(

                prompt=prompt
            )

        return {

            "success": False,

            "error":
                f"Unsupported provider: {provider}"
        }


# =========================================================
# SINGLETON
# =========================================================

llm_gateway = LLMGateway()