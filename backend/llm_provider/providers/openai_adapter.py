from __future__ import annotations

import logging
import os
import time
from typing import Any, AsyncGenerator, Optional

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI, AsyncOpenAI

from backend.llm_provider.interface import LLMProvider
from backend.llm_provider.models import (
    EmbeddingRequest,
    EmbeddingResult,
    FinishReason,
    LLMModelInfo,
    LLMProviderInfo,
    LLMRequest,
    LLMResponse,
    ModelCapability,
    ProviderHealth,
    StreamChunk,
)

load_dotenv()
log = logging.getLogger(__name__)


class OpenAIAdapter(LLMProvider):
    def __init__(self) -> None:
        self._openai_client: Optional[AsyncOpenAI] = None
        self._azure_client: Optional[AsyncAzureOpenAI] = None
        self._initialized = False

        self._azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
        self._embedding_model = os.getenv("MODEL_EMBEDDING_PRIMARY", "text-embedding-3-small")

        default_models = [
            LLMModelInfo(
                name="gpt-4o", provider="openai",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.STRUCTURED_OUTPUT,
                              ModelCapability.VISION, ModelCapability.TOOL_USE},
                context_window=128000, max_output_tokens=16384,
                cost_per_1k_input=2.50, cost_per_1k_output=10.00,
                version="gpt-4o-2024-08-06", is_default=True,
            ),
            LLMModelInfo(
                name="gpt-4o-mini", provider="openai",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.STRUCTURED_OUTPUT,
                              ModelCapability.VISION, ModelCapability.TOOL_USE},
                context_window=128000, max_output_tokens=16384,
                cost_per_1k_input=0.15, cost_per_1k_output=0.60,
                version="gpt-4o-mini-2024-07-18",
            ),
            LLMModelInfo(
                name="o3-mini", provider="openai",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.STRUCTURED_OUTPUT},
                context_window=200000, max_output_tokens=100000,
                cost_per_1k_input=1.10, cost_per_1k_output=4.40,
                version="o3-mini-2025-01-31",
            ),
        ]

        self._info = LLMProviderInfo(
            name="openai",
            display_name="OpenAI / Azure OpenAI",
            version="1.0",
            models=default_models,
            priority=10,
        )

    @property
    def name(self) -> str:
        return "openai"

    @property
    def provider_info(self) -> LLMProviderInfo:
        return self._info

    async def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._openai_client = AsyncOpenAI(api_key=api_key)

            azure_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
            if azure_key and azure_endpoint:
                self._azure_client = AsyncAzureOpenAI(
                    api_key=azure_key,
                    azure_endpoint=azure_endpoint,
                    api_version=azure_version,
                )

            self._initialized = True
            log.info("OpenAIAdapter initialized (openai=%s, azure=%s)",
                     self._openai_client is not None, self._azure_client is not None)
            return True
        except Exception as exc:
            log.warning("OpenAIAdapter initialization failed: %s", exc)
            return False

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        models = []
        try:
            client = self._azure_client or self._openai_client
            if client:
                models = [m.name for m in self._info.models]
            latency = (time.monotonic() - start) * 1000
            self._info.latency_ms = latency
            self._info.is_available = client is not None
            return ProviderHealth(
                provider=self.name,
                is_available=client is not None,
                latency_ms=latency,
                models_available=models,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            self._info.is_available = False
            return ProviderHealth(
                provider=self.name, is_available=False,
                latency_ms=latency, error=str(exc),
            )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        try:
            model = request.model or self._azure_deployment or "gpt-4o"
            messages = self._build_messages(request)
            client = self._azure_client or self._openai_client
            if not client:
                return LLMResponse(
                    content="", model=model, provider=self.name,
                    error="No OpenAI/Azure client configured",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )

            kwargs: dict[str, Any] = dict(
                model=model,
                messages=messages,
                temperature=request.temperature,
                timeout=request.timeout_seconds,
            )
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens
            if request.stop:
                kwargs["stop"] = request.stop
            if request.response_format:
                kwargs["response_format"] = request.response_format

            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            content = choice.message.content or ""
            finish = self._map_finish_reason(choice.finish_reason)

            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=content,
                model=model,
                provider=self.name,
                usage=response.usage.model_dump() if hasattr(response.usage, "model_dump") else None,
                finish_reason=finish,
                latency_ms=latency,
                request_id=request.request_id,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content="", model=request.model or "", provider=self.name,
                error=str(exc), finish_reason=FinishReason.ERROR,
                latency_ms=latency, request_id=request.request_id,
            )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        try:
            model = request.model or self._azure_deployment or "gpt-4o"
            messages = self._build_messages(request)
            client = self._azure_client or self._openai_client
            if not client:
                yield StreamChunk(
                    content="", finish_reason=FinishReason.ERROR,
                    done=True, request_id=request.request_id,
                    model=model, provider=self.name,
                )
                return

            kwargs: dict[str, Any] = dict(
                model=model, messages=messages,
                temperature=request.temperature,
                stream=True, timeout=request.timeout_seconds,
            )
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens

            stream = await client.chat.completions.create(**kwargs)
            idx = 0
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = delta.content or ""
                finish = self._map_finish_reason(chunk.choices[0].finish_reason) if chunk.choices[0].finish_reason else None
                yield StreamChunk(
                    content=content,
                    finish_reason=finish,
                    index=idx,
                    request_id=request.request_id,
                    model=model,
                    provider=self.name,
                    done=finish is not None,
                )
                idx += 1
                if finish is not None:
                    break
        except Exception as exc:
            log.warning("OpenAI stream error: %s", exc)
            yield StreamChunk(
                content="", finish_reason=FinishReason.ERROR,
                done=True, request_id=request.request_id,
                model=request.model or "", provider=self.name,
            )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        start = time.monotonic()
        try:
            client = self._openai_client
            if not client:
                return EmbeddingResult(
                    error="OpenAI client not configured",
                    request_id=request.request_id,
                    latency_ms=(time.monotonic() - start) * 1000,
                )
            model = request.model or self._embedding_model
            response = await client.embeddings.create(
                model=model, input=request.texts,
            )
            embeddings = [item.embedding for item in response.data]
            latency = (time.monotonic() - start) * 1000
            return EmbeddingResult(
                embeddings=embeddings,
                model=model, provider=self.name,
                dimensions=len(embeddings[0]) if embeddings else 0,
                latency_ms=latency, request_id=request.request_id,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return EmbeddingResult(
                error=str(exc), request_id=request.request_id,
                latency_ms=latency, provider=self.name,
            )

    async def function_call(self, request: LLMRequest) -> LLMResponse:
        if not request.functions:
            return LLMResponse(
                content="", model=request.model or "", provider=self.name,
                error="No functions provided for function_call",
                finish_reason=FinishReason.ERROR, request_id=request.request_id,
            )
        start = time.monotonic()
        try:
            model = request.model or self._azure_deployment or "gpt-4o"
            messages = self._build_messages(request)
            client = self._azure_client or self._openai_client
            if not client:
                return LLMResponse(
                    content="", model=model, provider=self.name,
                    error="No OpenAI/Azure client configured",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )
            response = await client.chat.completions.create(
                model=model, messages=messages,
                functions=request.functions,
                function_call=request.function_call or "auto",
                temperature=request.temperature,
                timeout=request.timeout_seconds,
            )
            choice = response.choices[0]
            msg = choice.message
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=msg.content or "",
                model=model, provider=self.name,
                function_call=msg.function_call.model_dump() if hasattr(msg.function_call, "model_dump") else None,
                finish_reason=self._map_finish_reason(choice.finish_reason),
                usage=response.usage.model_dump() if hasattr(response.usage, "model_dump") else None,
                latency_ms=latency, request_id=request.request_id,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content="", model=request.model or "", provider=self.name,
                error=str(exc), finish_reason=FinishReason.ERROR,
                latency_ms=latency, request_id=request.request_id,
            )

    async def shutdown(self) -> None:
        self._initialized = False
        self._openai_client = None
        self._azure_client = None

    def _build_messages(self, request: LLMRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)
        return messages

    @staticmethod
    def _map_finish_reason(reason: Optional[str]) -> Optional[FinishReason]:
        if not reason:
            return None
        mapping = {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
            "content_filter": FinishReason.CONTENT_FILTER,
            "function_call": FinishReason.FUNCTION_CALL,
            "tool_calls": FinishReason.TOOL_CALL,
        }
        return mapping.get(reason, FinishReason.STOP)
