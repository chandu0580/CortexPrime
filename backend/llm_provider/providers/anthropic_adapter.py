from __future__ import annotations

import logging
import os
import time
from typing import Any, AsyncGenerator, Optional

from dotenv import load_dotenv

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


class AnthropicAdapter(LLMProvider):
    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._initialized = False
        self._default_model = os.getenv("MODEL_CLAUDE", "claude-opus-4-5")

        default_models = [
            LLMModelInfo(
                name="claude-opus-4-5", provider="anthropic",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.STRUCTURED_OUTPUT,
                              ModelCapability.VISION, ModelCapability.TOOL_USE},
                context_window=200000, max_output_tokens=8192,
                cost_per_1k_input=15.00, cost_per_1k_output=75.00,
                version="claude-opus-4-5-20250514", is_default=True,
            ),
            LLMModelInfo(
                name="claude-sonnet-4-5", provider="anthropic",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.STRUCTURED_OUTPUT,
                              ModelCapability.VISION, ModelCapability.TOOL_USE},
                context_window=200000, max_output_tokens=8192,
                cost_per_1k_input=3.00, cost_per_1k_output=15.00,
                version="claude-sonnet-4-5-20250514",
            ),
            LLMModelInfo(
                name="claude-haiku-3-5", provider="anthropic",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.STRUCTURED_OUTPUT,
                              ModelCapability.VISION, ModelCapability.TOOL_USE},
                context_window=200000, max_output_tokens=8192,
                cost_per_1k_input=0.80, cost_per_1k_output=4.00,
                version="claude-3-5-haiku-20241022",
            ),
        ]

        self._info = LLMProviderInfo(
            name="anthropic",
            display_name="Anthropic Claude",
            version="1.0",
            models=default_models,
            priority=20,
        )

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def provider_info(self) -> LLMProviderInfo:
        return self._info

    async def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            from anthropic import AsyncAnthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self._client = AsyncAnthropic(api_key=api_key)
                self._initialized = True
                log.info("AnthropicAdapter initialized")
                return True
            log.warning("No ANTHROPIC_API_KEY configured")
            return False
        except Exception as exc:
            log.warning("AnthropicAdapter initialization failed: %s", exc)
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
                    error="Anthropic client not configured",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )
            model = request.model or self._default_model
            system = request.system_prompt
            messages = self._convert_messages(request.messages)

            kwargs: dict[str, Any] = dict(
                model=model, messages=messages,
                max_tokens=request.max_tokens or 4096,
            )
            if system:
                kwargs["system"] = system
            if request.temperature:
                kwargs["temperature"] = request.temperature
            if request.stop:
                kwargs["stop_sequences"] = request.stop

            response = await self._client.messages.create(**kwargs)
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=content, model=model, provider=self.name,
                usage={"input_tokens": response.usage.input_tokens,
                       "output_tokens": response.usage.output_tokens}
                if hasattr(response, "usage") else None,
                finish_reason=FinishReason.STOP,
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
                yield StreamChunk(done=True, error="Anthropic client not configured")
                return
            model = request.model or self._default_model
            system = request.system_prompt
            messages = self._convert_messages(request.messages)

            kwargs: dict[str, Any] = dict(
                model=model, messages=messages,
                max_tokens=request.max_tokens or 4096,
                stream=True,
            )
            if system:
                kwargs["system"] = system

            async with self._client.messages.stream(**kwargs) as stream:
                idx = 0
                async for text in stream.text_stream:
                    yield StreamChunk(
                        content=text, index=idx,
                        request_id=request.request_id,
                        model=model, provider=self.name,
                    )
                    idx += 1
            yield StreamChunk(
                finish_reason=FinishReason.STOP, done=True,
                request_id=request.request_id, model=model, provider=self.name,
            )
        except Exception as exc:
            log.warning("Anthropic stream error: %s", exc)
            yield StreamChunk(
                finish_reason=FinishReason.ERROR, done=True,
                error=str(exc), request_id=request.request_id,
                model=request.model or "", provider=self.name,
            )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return EmbeddingResult(
            error="Anthropic does not support embeddings",
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
                    error="Anthropic client not configured",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )
            model = request.model or self._default_model
            system = request.system_prompt
            messages = self._convert_messages(request.messages)
            tools = self._convert_functions_to_tools(request.functions)

            kwargs: dict[str, Any] = dict(
                model=model, messages=messages,
                max_tokens=request.max_tokens or 4096,
                tools=tools,
            )
            if system:
                kwargs["system"] = system

            response = await self._client.messages.create(**kwargs)
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=content, model=model, provider=self.name,
                finish_reason=FinishReason.TOOL_CALL
                if any(hasattr(b, "tool_use") for b in response.content) else FinishReason.STOP,
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

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        return [m for m in messages if m.get("role") != "system"]

    @staticmethod
    def _convert_functions_to_tools(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tools = []
        for fn in functions:
            tools.append({
                "name": fn.get("name", "unknown"),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {}),
            })
        return tools
