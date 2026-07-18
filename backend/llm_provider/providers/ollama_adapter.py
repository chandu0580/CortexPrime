from __future__ import annotations

import json
import logging
import os
import time
from typing import AsyncGenerator, Optional

import httpx

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

log = logging.getLogger(__name__)


class OllamaAdapter(LLMProvider):
    def __init__(self) -> None:
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._http_client: Optional[httpx.AsyncClient] = None
        self._initialized = False
        self._default_model = os.getenv("MODEL_OLLAMA", "llama3.2")

        default_models = [
            LLMModelInfo(
                name="llama3.2", provider="ollama",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING},
                context_window=8192, max_output_tokens=4096,
                cost_per_1k_input=0.0, cost_per_1k_output=0.0,
                version="3.2", is_default=True,
            ),
            LLMModelInfo(
                name="llama3.1", provider="ollama",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING},
                context_window=8192, max_output_tokens=4096,
                cost_per_1k_input=0.0, cost_per_1k_output=0.0,
                version="3.1",
            ),
            LLMModelInfo(
                name="mistral", provider="ollama",
                capabilities={ModelCapability.CHAT, ModelCapability.STREAMING},
                context_window=8192, max_output_tokens=4096,
                cost_per_1k_input=0.0, cost_per_1k_output=0.0,
                version="7b",
            ),
        ]

        self._info = LLMProviderInfo(
            name="ollama",
            display_name="Ollama (Local)",
            version="1.0",
            models=default_models,
            priority=40,
        )

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def provider_info(self) -> LLMProviderInfo:
        return self._info

    async def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            self._http_client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
            self._initialized = True
            log.info("OllamaAdapter initialized (base_url=%s)", self._base_url)
            return True
        except Exception as exc:
            log.warning("OllamaAdapter initialization failed: %s", exc)
            return False

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            if not self._http_client:
                return ProviderHealth(
                    provider=self.name, is_available=False,
                    latency_ms=(time.monotonic() - start) * 1000,
                    error="HTTP client not initialized",
                )
            response = await self._http_client.get("/api/tags")
            available = response.status_code == 200
            models = []
            if available:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
            latency = (time.monotonic() - start) * 1000
            self._info.latency_ms = latency
            self._info.is_available = available
            return ProviderHealth(
                provider=self.name, is_available=available,
                latency_ms=latency, models_available=models or [m.name for m in self._info.models],
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
            if not self._http_client:
                return LLMResponse(
                    content="", model=request.model or "", provider=self.name,
                    error="Ollama client not initialized",
                    finish_reason=FinishReason.ERROR,
                    latency_ms=(time.monotonic() - start) * 1000,
                    request_id=request.request_id,
                )
            model = request.model or self._default_model
            prompt = self._build_prompt(request)
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                },
            }
            if request.max_tokens:
                payload["options"]["num_predict"] = request.max_tokens
            if request.stop:
                payload["options"]["stop"] = request.stop

            response = await self._http_client.post("/api/generate", json=payload)
            data = response.json()
            latency = (time.monotonic() - start) * 1000
            return LLMResponse(
                content=data.get("response", ""),
                model=model, provider=self.name,
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
            if not self._http_client:
                yield StreamChunk(done=True, error="Ollama client not initialized")
                return
            model = request.model or self._default_model
            prompt = self._build_prompt(request)
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": request.temperature},
            }
            async with self._http_client.stream("POST", "/api/generate", json=payload) as response:
                idx = 0
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("response", "")
                        done = data.get("done", False)
                        yield StreamChunk(
                            content=content, index=idx,
                            request_id=request.request_id,
                            model=model, provider=self.name,
                            done=done,
                        )
                        idx += 1
                        if done:
                            break
                    except json.JSONDecodeError:
                        continue
            yield StreamChunk(
                finish_reason=FinishReason.STOP, done=True,
                request_id=request.request_id, model=model, provider=self.name,
            )
        except Exception as exc:
            log.warning("Ollama stream error: %s", exc)
            yield StreamChunk(
                finish_reason=FinishReason.ERROR, done=True,
                error=str(exc), request_id=request.request_id,
                model=request.model or "", provider=self.name,
            )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        start = time.monotonic()
        try:
            if not self._http_client:
                return EmbeddingResult(
                    error="Ollama client not initialized",
                    request_id=request.request_id, provider=self.name,
                )
            model = request.model or self._default_model
            embeddings = []
            for text in request.texts:
                response = await self._http_client.post("/api/embeddings", json={
                    "model": model, "prompt": text,
                })
                data = response.json()
                embeddings.append(data.get("embedding", []))
            latency = (time.monotonic() - start) * 1000
            return EmbeddingResult(
                embeddings=embeddings, model=model, provider=self.name,
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
        return LLMResponse(
            content="", model=request.model or "", provider=self.name,
            error="Ollama does not support function calling in this adapter",
            finish_reason=FinishReason.ERROR, request_id=request.request_id,
        )

    async def shutdown(self) -> None:
        self._initialized = False
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _build_prompt(self, request: LLMRequest) -> str:
        parts: list[str] = []
        if request.system_prompt:
            parts.append(f"System: {request.system_prompt}")
        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)
