from __future__ import annotations

import logging
import time
from typing import Any, Optional

from backend.llm_provider.interface import LLMProvider
from backend.llm_provider.models import ProviderHealth
from backend.llm_provider.providers.anthropic_adapter import AnthropicAdapter
from backend.llm_provider.providers.deepseek_provider import DeepSeekAdapter
from backend.llm_provider.providers.gemini_adapter import GeminiAdapter
from backend.llm_provider.providers.groq_adapter import GroqAdapter
from backend.llm_provider.providers.ollama_adapter import OllamaAdapter
from backend.llm_provider.providers.openai_adapter import OpenAIAdapter
from backend.llm_provider.providers.openai_compatible_adapter import OpenAICompatibleAdapter
from backend.llm_provider.providers.openrouter_adapter import OpenRouterAdapter
from backend.llm_provider.providers.together_adapter import TogetherAdapter

log = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._health_cache: dict[str, ProviderHealth] = {}
        self._health_cache_ttl: float = 30.0
        self._last_health_check: dict[str, float] = {}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider
        log.info("Provider registered: %s (priority=%d)", provider.name, provider.provider_info.priority)

    def unregister(self, name: str) -> None:
        self._providers.pop(name, None)
        self._health_cache.pop(name, None)
        self._last_health_check.pop(name, None)
        log.info("Provider unregistered: %s", name)

    def get(self, name: str) -> Optional[LLMProvider]:
        return self._providers.get(name)

    def list_providers(self) -> list[LLMProvider]:
        return list(self._providers.values())

    def list_available(self) -> list[LLMProvider]:
        return [p for p in self._providers.values() if p.provider_info.is_available]

    def get_sorted(self) -> list[LLMProvider]:
        return sorted(self._providers.values(), key=lambda p: p.provider_info.priority)

    async def initialize_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name, provider in self._providers.items():
            try:
                ok = await provider.initialize()
                results[name] = ok
                log.info("Provider %s initialized: %s", name, ok)
            except Exception as exc:
                results[name] = False
                log.warning("Provider %s initialization error: %s", name, exc)
        return results

    async def health_check_all(self) -> dict[str, ProviderHealth]:
        results: dict[str, ProviderHealth] = {}
        for name, provider in self._providers.items():
            now = time.monotonic()
            last = self._last_health_check.get(name, 0.0)
            if now - last < self._health_cache_ttl and name in self._health_cache:
                results[name] = self._health_cache[name]
                continue
            try:
                health = await provider.health_check()
                results[name] = health
                self._health_cache[name] = health
                self._last_health_check[name] = now
            except Exception as exc:
                health = ProviderHealth(
                    provider=name, is_available=False,
                    error=str(exc),
                )
                results[name] = health
                self._health_cache[name] = health
                self._last_health_check[name] = now
        return results

    async def shutdown_all(self) -> None:
        for provider in self._providers.values():
            try:
                await provider.shutdown()
            except Exception as exc:
                log.warning("Provider %s shutdown error: %s", provider.name, exc)
        self._providers.clear()
        self._health_cache.clear()
        self._last_health_check.clear()

    def discover(self) -> list[LLMProvider]:
        builtins = [
            OpenAIAdapter(),
            AnthropicAdapter(),
            OpenRouterAdapter(),
            GroqAdapter(),
            TogetherAdapter(),
            GeminiAdapter(),
            DeepSeekAdapter(),
            OllamaAdapter(),
            OpenAICompatibleAdapter(),
        ]
        for p in builtins:
            if p.name not in self._providers:
                self.register(p)
        return builtins

    def get_by_capability(self, capability: str) -> list[LLMProvider]:
        from backend.llm_provider.models import ModelCapability
        cap = ModelCapability(capability) if capability in [c.value for c in ModelCapability] else None
        if not cap:
            return []
        return [
            p for p in self._providers.values()
            if any(cap in m.capabilities for m in p.provider_info.models)
        ]

    def get_providers_info(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.get_sorted()]


registry = ProviderRegistry()
