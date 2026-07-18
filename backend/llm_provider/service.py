from __future__ import annotations

import logging
import time
from typing import Any, AsyncGenerator, Optional

from backend.llm_provider.embedding import EmbeddingProviderInterface
from backend.llm_provider.models import (
    EmbeddingResult,
    FinishReason,
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    StreamChunk,
)
from backend.llm_provider.prompt import PromptRuntime, prompt_runtime
from backend.llm_provider.registry import ProviderRegistry, registry
from backend.llm_provider.router import ModelRouter, router as model_router
from backend.llm_provider.streaming import StreamManager, stream_manager
from backend.llm_provider.structured import StructuredOutputHandler

log = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        provider_registry: Optional[ProviderRegistry] = None,
        model_router_instance: Optional[ModelRouter] = None,
        prompt_runtime_instance: Optional[PromptRuntime] = None,
        stream_mgr: Optional[StreamManager] = None,
        embedding: Optional[EmbeddingProviderInterface] = None,
        structured: Optional[StructuredOutputHandler] = None,
    ) -> None:
        self._registry = provider_registry or registry
        self._router = model_router_instance or model_router
        self._prompt = prompt_runtime_instance or prompt_runtime
        self._stream_mgr = stream_mgr or stream_manager
        self._embedding = embedding or EmbeddingProviderInterface(self._registry)
        self._structured = structured or StructuredOutputHandler()

    async def initialize(self) -> bool:
        self._registry.discover()
        results = await self._registry.initialize_all()
        await self._registry.health_check_all()
        success = any(results.values())
        log.info("LLMService initialized. Providers: %d available",
                 len(self._registry.list_available()))
        return success

    async def generate(
        self,
        prompt: str,
        *,
        model: str = "",
        provider: str = "",
        system_prompt: Optional[str] = None,
        system_prompt_name: str = "default",
        messages: Optional[list[dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
        functions: Optional[list[dict[str, Any]]] = None,
        response_format: Optional[dict[str, Any]] = None,
        timeout_seconds: float = 60.0,
    ) -> LLMResponse:
        llm_request = self._prompt.build_request(
            prompt=prompt,
            system_prompt_name=system_prompt_name,
            custom_system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            functions=functions,
            response_format=response_format,
            timeout_seconds=timeout_seconds,
        )

        resolved_model, resolved_provider = self._router.select_model(
            request=llm_request,
            model=model,
            provider=provider,
        )
        llm_request.model = resolved_model or "gpt-4o"

        prov = self._registry.get(resolved_provider or "openai")
        if not prov:
            return LLMResponse(
                content="", error=f"No provider found: {resolved_provider}",
                finish_reason=FinishReason.ERROR, model=llm_request.model,
            )

        if functions:
            return await prov.function_call(llm_request)
        return await prov.generate(llm_request)

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        model: str = "",
        provider: str = "",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> LLMResponse:
        llm_request = self._prompt.build_request(
            prompt=prompt,
            custom_system_prompt=system_prompt,
            temperature=temperature,
        )

        resolved_model, resolved_provider = self._router.select_model(
            request=llm_request, model=model, provider=provider,
        )
        llm_request.model = resolved_model or "gpt-4o"

        prov = self._registry.get(resolved_provider or "openai")
        if not prov:
            return LLMResponse(
                content="", error=f"No provider found: {resolved_provider}",
                finish_reason=FinishReason.ERROR,
            )

        return await self._structured.generate_structured(
            prov.generate, llm_request, schema, max_retries=max_retries,
        )

    async def stream(
        self,
        prompt: str,
        *,
        model: str = "",
        provider: str = "",
        system_prompt: Optional[str] = None,
        system_prompt_name: str = "default",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        llm_request = self._prompt.build_request(
            prompt=prompt,
            system_prompt_name=system_prompt_name,
            custom_system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        resolved_model, resolved_provider = self._router.select_model(
            request=llm_request, model=model, provider=provider,
        )
        llm_request.model = resolved_model or "gpt-4o"

        prov = self._registry.get(resolved_provider or "openai")
        if not prov:
            yield StreamChunk(
                finish_reason=FinishReason.ERROR, done=True,
                error=f"No provider found: {resolved_provider}",
            )
            return

        stream_gen = prov.stream(llm_request)
        async for chunk in self._stream_mgr.handle_stream(
            stream_gen, llm_request.request_id,
        ):
            yield chunk

    async def embed(
        self,
        texts: list[str],
        model: str = "",
        provider: str = "",
    ) -> EmbeddingResult:
        return await self._embedding.embed(texts, model=model, provider=provider)

    async def health(self) -> list[ProviderHealth]:
        results = await self._registry.health_check_all()
        return list(results.values())

    async def list_providers(self) -> list[dict[str, Any]]:
        return self._registry.get_providers_info()

    async def list_models(self) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        for pinfo in self._registry.get_providers_info():
            for m in pinfo.get("models", []):
                models.append({**m, "provider": pinfo["name"]})
        return models

    async def get_provider(self, name: str) -> Optional[dict[str, Any]]:
        prov = self._registry.get(name)
        return prov.to_dict() if prov else None

    async def cancel_stream(self, request_id: str) -> bool:
        return self._stream_mgr.cancel_stream(request_id)

    def get_routing_stats(self) -> dict[str, Any]:
        return self._router.get_routing_stats()

    def reset_routing_stats(self) -> None:
        self._router.reset_routing_stats()

    async def shutdown(self) -> None:
        await self._registry.shutdown_all()
