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


class GeminiAdapter(LLMProvider):
    def __init__(self) -> None:
        self._model: Optional[Any] = None
        self._initialized = False
        self._default_model = os.getenv("MODEL_GEMINI", "gemini-2.0-flash-exp")

        default_models = [
            LLMModelInfo(
                name="gemini-2.0-flash-exp", provider="gemini",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.VISION,
                              ModelCapability.TOOL_USE},
                context_window=1048576, max_output_tokens=8192,
                cost_per_1k_input=0.10, cost_per_1k_output=0.40,
                version="gemini-2.0-flash-exp", is_default=True,
            ),
            LLMModelInfo(
                name="gemini-1.5-pro", provider="gemini",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.VISION,
                              ModelCapability.TOOL_USE},
                context_window=2097152, max_output_tokens=8192,
                cost_per_1k_input=1.25, cost_per_1k_output=5.00,
                version="gemini-1.5-pro-002",
            ),
            LLMModelInfo(
                name="gemini-1.5-flash", provider="gemini",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING,
                              ModelCapability.FUNCTION_CALLING, ModelCapability.VISION,
                              ModelCapability.TOOL_USE},
                context_window=1048576, max_output_tokens=8192,
                cost_per_1k_input=0.075, cost_per_1k_output=0.30,
                version="gemini-1.5-flash-002",
            ),
        ]

        self._info = LLMProviderInfo(
            name="gemini",
            display_name="Google Gemini",
            version="1.0",
            models=default_models,
            priority=30,
        )

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def provider_info(self) -> LLMProviderInfo:
        return self._info

    async def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            import google.generativeai as genai
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self._model = genai
                self._initialized = True
                log.info("GeminiAdapter initialized")
                return True
            log.warning("No GOOGLE_API_KEY configured")
            return False
        except Exception as exc:
            log.warning("GeminiAdapter initialization failed: %s", exc)
            return False

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            available = self._model is not None
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
            if not self._model:
                return LLMResponse(
                    content="", model=request.model or "", provider=self.name,
                    error="Gemini client not configured",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )
            model_name = request.model or self._default_model
            genai_model = self._model.GenerativeModel(model_name)
            prompt = self._build_gemini_prompt(request)
            response = genai_model.generate_content(prompt)
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=response.text if hasattr(response, "text") else "",
                model=model_name, provider=self.name,
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
            if not self._model:
                yield StreamChunk(done=True, error="Gemini client not configured")
                return
            model_name = request.model or self._default_model
            genai_model = self._model.GenerativeModel(model_name)
            prompt = self._build_gemini_prompt(request)
            response = genai_model.generate_content(prompt, stream=True)
            idx = 0
            for chunk in response:
                if hasattr(chunk, "text") and chunk.text:
                    yield StreamChunk(
                        content=chunk.text, index=idx,
                        request_id=request.request_id,
                        model=model_name, provider=self.name,
                    )
                    idx += 1
            yield StreamChunk(
                finish_reason=FinishReason.STOP, done=True,
                request_id=request.request_id, model=model_name, provider=self.name,
            )
        except Exception as exc:
            log.warning("Gemini stream error: %s", exc)
            yield StreamChunk(
                finish_reason=FinishReason.ERROR, done=True,
                error=str(exc), request_id=request.request_id,
                model=request.model or "", provider=self.name,
            )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        start = time.monotonic()
        try:
            if not self._model:
                return EmbeddingResult(
                    error="Gemini client not configured",
                    request_id=request.request_id, provider=self.name,
                )
            result = self._model.embed_content(
                model="models/embedding-001",
                content=request.texts,
            )
            embeddings = result["embedding"] if isinstance(result, dict) else []
            if not isinstance(embeddings[0], list) if embeddings else False:
                embeddings = [embeddings]
            latency = (time.monotonic() - start) * 1000
            return EmbeddingResult(
                embeddings=embeddings if isinstance(embeddings, list) else [embeddings],
                model="embedding-001", provider=self.name,
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
                error="No functions provided", finish_reason=FinishReason.ERROR,
                request_id=request.request_id,
            )
        start = time.monotonic()
        try:
            if not self._model:
                return LLMResponse(
                    content="", model=request.model or "", provider=self.name,
                    error="Gemini client not configured",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )
            model_name = request.model or self._default_model
            genai_model = self._model.GenerativeModel(model_name)
            prompt = self._build_gemini_prompt(request)
            response = genai_model.generate_content(prompt)
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=response.text if hasattr(response, "text") else "",
                model=model_name, provider=self.name,
                finish_reason=FinishReason.TOOL_CALL,
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
        self._model = None

    def _build_gemini_prompt(self, request: LLMRequest) -> str:
        parts: list[str] = []
        if request.system_prompt:
            parts.append(f"[System Instructions]\n{request.system_prompt}\n")
        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(content)
        return "\n".join(parts)
