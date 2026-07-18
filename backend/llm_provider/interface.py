from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional

from backend.llm_provider.models import (
    EmbeddingRequest,
    EmbeddingResult,
    LLMProviderInfo,
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    StreamChunk,
)


class LLMProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def provider_info(self) -> LLMProviderInfo:
        ...

    @abstractmethod
    async def initialize(self) -> bool:
        ...

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        ...

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        ...

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        ...

    @abstractmethod
    async def function_call(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...

    def to_dict(self) -> dict[str, Any]:
        info = self.provider_info
        return {
            "name": self.name,
            "display_name": info.display_name,
            "version": info.version,
            "priority": info.priority,
            "is_available": info.is_available,
            "latency_ms": info.latency_ms,
            "last_health_check": info.last_health_check,
            "models": [
                {
                    "name": m.name,
                    "capabilities": [c.value for c in m.capabilities],
                    "context_window": m.context_window,
                    "max_output_tokens": m.max_output_tokens,
                    "cost_per_1k_input": m.cost_per_1k_input,
                    "cost_per_1k_output": m.cost_per_1k_output,
                    "version": m.version,
                    "is_default": m.is_default,
                }
                for m in info.models
            ],
        }
