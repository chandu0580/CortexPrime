from __future__ import annotations

import logging
import os
import time
from typing import Any, AsyncGenerator, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

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


class DeepSeekAdapter(LLMProvider):
    def __init__(self) -> None:
        self._client: Optional[AsyncOpenAI] = None
        self._initialized = False
        self._default_model = os.getenv("MODEL_DEEPSEEK", "deepseek-chat")

        default_models = [
            LLMModelInfo(
                name="deepseek-chat", provider="deepseek",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.STRUCTURED_OUTPUT},
                context_window=64000, max_output_tokens=8192,
                cost_per_1k_input=0.27, cost_per_1k_output=1.10,
                version="deepseek-chat", is_default=True,
            ),
            LLMModelInfo(
                name="deepseek-reasoner", provider="deepseek",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING},
                context_window=64000, max_output_tokens=8192,
                cost_per_1k_input=0.55, cost_per_1k_output=2.19,
                version="deepseek-reasoner",
            ),
        ]

        self._info = LLMProviderInfo(
            name="deepseek",
            display_name="DeepSeek",
            version="1.0",
            models=default_models,
            priority=50,
        )

    @property
    def name(self) -> str:
        return "deepseek"

    @property
    def provider_info(self) -> LLMProviderInfo:
        return self._info

    async def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if api_key:
                self._client = AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com",
                )
                self._initialized = True
                log.info("DeepSeekAdapter initialized")
                return True
            log.warning("No DEEPSEEK_API_KEY configured")
            return False
        except Exception as exc:
            log.warning("DeepSeekAdapter initialization failed: %s", exc)
            return False

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            available = self._client is not None
            latency = (time.monotonic() - start) * 1000
            self._info.latency_ms = latency
            self._info.is_available = available
            return ProviderHealth(
                provider=self.name, is_available=available,
                latency_ms=latency,
                models_available=[m.name for m in self._info.models],
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.name, is_available=False,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
            )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        try:
            if not self._client:
                return LLMResponse(
                    content="", model=request.model or "", provider=self.name,
                    error="DeepSeek client not configured",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )
            model = request.model or self._default_model
            messages = self._build_messages(request)
            kwargs: dict[str, Any] = dict(
                model=model, messages=messages,
                temperature=request.temperature,
                timeout=request.timeout_seconds,
            )
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens
            if request.stop:
                kwargs["stop"] = request.stop

            response = await self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=choice.message.content or "",
                model=model, provider=self.name,
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

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        try:
            if not self._client:
                yield StreamChunk(done=True, error="DeepSeek client not configured")
                return
            model = request.model or self._default_model
            messages = self._build_messages(request)
            stream = await self._client.chat.completions.create(
                model=model, messages=messages,
                temperature=request.temperature,
                stream=True, timeout=request.timeout_seconds,
            )
            idx = 0
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = delta.content or ""
                yield StreamChunk(
                    content=content, index=idx,
                    request_id=request.request_id,
                    model=model, provider=self.name,
                )
                idx += 1
            yield StreamChunk(
                finish_reason=FinishReason.STOP, done=True,
                request_id=request.request_id, model=model, provider=self.name,
            )
        except Exception as exc:
            log.warning("DeepSeek stream error: %s", exc)
            yield StreamChunk(
                finish_reason=FinishReason.ERROR, done=True,
                error=str(exc), request_id=request.request_id,
                model=request.model or "", provider=self.name,
            )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return EmbeddingResult(
            error="DeepSeek does not support embeddings in this adapter",
            request_id=request.request_id, provider=self.name,
        )

    async def function_call(self, request: LLMRequest) -> LLMResponse:
        if not request.functions:
            return LLMResponse(
                content="", model=request.model or "", provider=self.name,
                error="No functions provided", finish_reason=FinishReason.ERROR,
                request_id=request.request_id,
            )
        start = time.monotonic()
        try:
            if not self._client:
                return LLMResponse(
                    content="", model=request.model or "", provider=self.name,
                    error="DeepSeek client not configured",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )
            model = request.model or self._default_model
            messages = self._build_messages(request)
            response = await self._client.chat.completions.create(
                model=model, messages=messages,
                functions=request.functions,
                function_call=request.function_call or "auto",
                temperature=request.temperature,
                timeout=request.timeout_seconds,
            )
            choice = response.choices[0]
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=choice.message.content or "",
                model=model, provider=self.name,
                function_call=choice.message.function_call.model_dump()
                if hasattr(choice.message.function_call, "model_dump") else None,
                finish_reason=FinishReason.FUNCTION_CALL,
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
        self._client = None

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
