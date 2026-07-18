import logging
import os
from typing import Any, Dict, Optional
from uuid import uuid4

from dotenv import load_dotenv

from backend.events.event_bus import publish_event

# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

log = logging.getLogger(__name__)


# =========================================================
# LLM GATEWAY
# =========================================================

class LLMGateway:

    def __init__(self):

        self._llm_service: Optional[Any] = None
        self._openai_client: Optional[Any] = None
        self._azure_client: Optional[Any] = None

    async def _ensure_llm_service(self) -> Any:
        if self._llm_service is not None:
            return self._llm_service
        try:
            from backend.llm_provider.registry import registry
            registry.discover()
            from backend.llm_provider.service import LLMService
            svc = LLMService()
            await svc.initialize()
            self._llm_service = svc
        except Exception as exc:
            log.warning("LLM Provider Runtime unavailable, using direct clients: %s", exc)
            self._llm_service = None
        return self._llm_service

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )
        return self._openai_client

    def _get_azure_client(self):
        if self._azure_client is None:
            from openai import AsyncAzureOpenAI
            self._azure_client = AsyncAzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            )
        return self._azure_client


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

        payload: Dict[str, Any] = None
    ):

        await publish_event("llm_gateway", execution_id, event_type, status, phase, message, payload)


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

        str(uuid4())
        model = self.get_model_for_agent(agent_type)

        svc = await self._ensure_llm_service()
        if svc:
            try:
                response = await svc.generate(
                    prompt=prompt,
                    model=model,
                    provider="openai",
                    system_prompt=system_prompt,
                )
                if response.content:
                    return {
                        "success": True,
                        "provider": "azure_openai",
                        "model": model,
                        "agent_type": agent_type,
                        "output": response.content,
                    }
            except Exception as exc:
                log.warning("LLM Provider Runtime azure fallback: %s", exc)

        try:
            client = self._get_azure_client()
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                timeout=60,
            )
            output = response.choices[0].message.content
            return {
                "success": True,
                "provider": "azure_openai",
                "model": model,
                "agent_type": agent_type,
                "output": output,
            }
        except Exception as error:
            log.error("AZURE ERROR: %s", error)
            return {
                "success": False,
                "provider": "azure_openai",
                "model": model,
                "error": str(error),
            }


    # =====================================================
    # OPENAI FALLBACK
    # =====================================================

    async def generate_openai(
        self,
        prompt: str,
        model: str = "gpt-4o-mini"
    ) -> Dict[str, Any]:

        svc = await self._ensure_llm_service()
        if svc:
            try:
                response = await svc.generate(
                    prompt=prompt,
                    model=model,
                    provider="openai",
                )
                if response.content:
                    return {
                        "success": True,
                        "provider": "openai",
                        "model": model,
                        "output": response.content,
                    }
            except Exception as exc:
                log.warning("LLM Provider Runtime openai fallback: %s", exc)

        try:
            client = self._get_openai_client()
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are CortexPrime, an autonomous AI assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                timeout=60,
            )
            output = response.choices[0].message.content
            return {
                "success": True,
                "provider": "openai",
                "model": model,
                "output": output,
            }
        except Exception as error:
            log.error("OPENAI ERROR: %s", error)
            return {
                "success": False,
                "provider": "openai",
                "error": str(error),
            }


    # =====================================================
    # COMPLETE (backward-compat for callers using llm_gateway.complete())
    # =====================================================

    async def complete(
        self,
        prompt: str,
        system_prompt: str = "You are CortexPrime, an autonomous AI assistant.",
        model: str = "gpt-4o",
    ) -> str:
        svc = await self._ensure_llm_service()
        if svc:
            try:
                response = await svc.generate(
                    prompt=prompt,
                    model=model,
                    system_prompt=system_prompt,
                )
                if response.content:
                    return response.content
            except Exception as exc:
                log.warning("LLM Provider Runtime complete() fallback: %s", exc)

        try:
            client = self._get_openai_client()
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                timeout=60,
            )
            return response.choices[0].message.content or ""
        except Exception as error:
            log.error("complete() error: %s", error)
            return ""


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

                log.warning(
                    "FALLING BACK TO OPENAI"
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
